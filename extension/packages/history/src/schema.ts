/** The history store (spec §6.1): IndexedDB in the extension's own origin, one object store per
 * kind, each keyed by its own fields. The schema is versioned: each migration takes the database
 * from the version before it to its own, and opening runs every one the database has not had. */

export const DATABASE = "steadyhand-history";

/** Each kind's object store. */
export const STORES = {
  closes: "closes",
  series: "chart-series",
  dividends: "dividends",
  /** The period each dividend read covered, by stock (spec §7.1). */
  dividendReads: "dividend-reads",
  cashMovements: "cash-movements",
  corporateActions: "corporate-actions",
  /** The period each corporate action read covered, for every stock (#480). */
  corporateActionReads: "corporate-action-reads",
  memory: "memory",
  settings: "settings",
  /** The portfolio's value on each trading day an after-close read showed (spec §8). */
  valuations: "valuations",
  /** The period each cash-movement read covered (spec §8). */
  cashMovementReads: "cash-movement-reads",
  /** Deposits and withdrawals the user typed, kept as typed. */
  typedMovements: "typed-movements",
  /** Each period the user said is complete: every entry typed, or none. */
  answered: "answered",
  /** Each resume of a halt, by the instant it was made. */
  resumes: "resumes",
} as const;

export type StoreName = (typeof STORES)[keyof typeof STORES];

/** A schema step, given the database and the upgrade's own transaction, which it may read and
 * write rows through. */
export type Migration = (db: IDBDatabase, upgrade: IDBTransaction) => void;

/** Rebuild `store` under `keyPath`, each row it held given `entry` "#1": the rows were unique by
 * the old key, so each is the first of its kind (#470). */
const rekeyed = (db: IDBDatabase, upgrade: IDBTransaction, store: StoreName, keyPath: string[]) => {
  const read = upgrade.objectStore(store).getAll();
  read.onsuccess = () => {
    db.deleteObjectStore(store);
    const fresh = db.createObjectStore(store, { keyPath });
    for (const row of read.result as object[]) {
      fresh.put({ ...row, entry: "#1" });
    }
  };
};

/** Migration `i` takes the database to version `i + 1`. Never edit one that has shipped: add
 * the next. */
export const MIGRATIONS: readonly Migration[] = [
  (db) => {
    db.createObjectStore(STORES.closes, { keyPath: ["symbol", "day"] });
    db.createObjectStore(STORES.series, { keyPath: ["symbol", "readAt"] });
    db.createObjectStore(STORES.dividends, {
      keyPath: ["symbol", "exDate", "paymentDate", "grossPerShare"],
    });
    db.createObjectStore(STORES.cashMovements, { keyPath: ["day", "kind", "amount"] });
    db.createObjectStore(STORES.corporateActions, { keyPath: ["symbol", "exDate", "from", "to"] });
    db.createObjectStore(STORES.memory, { keyPath: "strategy" });
    db.createObjectStore(STORES.settings, { keyPath: "name" });
  },
  // #470: two equal deposits on one day are two rows. Each row carries an `entry`: the broker's
  // reference where the page shows one, else its place among identical rows in the same read.
  (db, upgrade) => {
    rekeyed(db, upgrade, STORES.dividends, [
      "symbol",
      "exDate",
      "paymentDate",
      "grossPerShare",
      "entry",
    ]);
    rekeyed(db, upgrade, STORES.cashMovements, ["day", "kind", "amount", "entry"]);
    rekeyed(db, upgrade, STORES.corporateActions, ["symbol", "exDate", "from", "to", "entry"]);
  },
  // #230: each dividend read records the period it covers for its stock, so a year inside it
  // with no dividend is known to have none (spec §7.1). Dividends recorded before have no period.
  (db) => {
    db.createObjectStore(STORES.dividendReads, { keyPath: ["symbol", "from", "to"] });
  },
  // #480: each corporate action read records the period it covers, which lists every stock's
  // splits, so an action found by price inside it is settled. Splits recorded before have none.
  (db) => {
    db.createObjectStore(STORES.corporateActionReads, { keyPath: ["from", "to"] });
  },
  // #236: the risk halts' record (spec §8). Cash-movement reads made before have no period, so
  // the time since the last read is asked about again.
  (db) => {
    db.createObjectStore(STORES.valuations, { keyPath: "day" });
    db.createObjectStore(STORES.cashMovementReads, { keyPath: ["from", "to"] });
    db.createObjectStore(STORES.typedMovements, { keyPath: "typedAt" });
    db.createObjectStore(STORES.answered, { keyPath: ["from", "to"] });
    db.createObjectStore(STORES.resumes, { keyPath: "at" });
  },
];

/** The version this release reads and writes. */
export const VERSION = MIGRATIONS.length;

/** The error IndexedDB gave for `what`, or one naming it when IndexedDB gave none. */
export const failure = (error: DOMException | null, what: string): Error =>
  error ?? new Error(`${what} failed with no error`);

/** Settle `request` as a promise: its result, or its error. */
export const requested = <T>(request: IDBRequest<T>): Promise<T> =>
  new Promise((resolve, reject) => {
    request.onsuccess = () => {
      resolve(request.result);
    };
    request.onerror = () => {
      reject(failure(request.error, "an IndexedDB request"));
    };
  });

/** Open the history database from `factory`, running each of `migrations` it has not had.
 *
 * A database a newer release wrote is refused, never read. An upgrade that another open tab
 * blocks is refused at once, naming it, rather than waited on. */
export const openHistory = (
  factory: IDBFactory,
  migrations: readonly Migration[] = MIGRATIONS,
): Promise<IDBDatabase> =>
  new Promise((resolve, reject) => {
    const request = factory.open(DATABASE, migrations.length);
    let refused = false;
    request.onupgradeneeded = (event) => {
      // IndexedDB gives every upgrade its own transaction.
      const upgrade = request.transaction as IDBTransaction;
      for (const migrate of migrations.slice(event.oldVersion)) {
        migrate(request.result, upgrade);
      }
    };
    request.onblocked = () => {
      refused = true;
      reject(new Error(`${DATABASE} is open in another tab of an older release: close it first`));
    };
    request.onsuccess = () => {
      if (refused) {
        request.result.close();
        return;
      }
      resolve(request.result);
    };
    request.onerror = () => {
      const error = failure(request.error, `opening ${DATABASE}`);
      reject(
        error.name === "VersionError"
          ? new Error(
              `${DATABASE} is at a newer version than this release reads (${String(migrations.length)})`,
            )
          : error,
      );
    };
  });
