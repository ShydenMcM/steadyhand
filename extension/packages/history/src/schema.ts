/** The history store (spec §6.1): IndexedDB in the extension's own origin, one object store per
 * kind, each keyed by its own fields. The schema is versioned: each migration takes the database
 * from the version before it to its own, and opening runs every one the database has not had. */

export const DATABASE = "steadyhand-history";

/** Each kind's object store. */
export const STORES = {
  closes: "closes",
  series: "chart-series",
  dividends: "dividends",
  cashMovements: "cash-movements",
  corporateActions: "corporate-actions",
  memory: "memory",
  settings: "settings",
} as const;

export type StoreName = (typeof STORES)[keyof typeof STORES];

export type Migration = (db: IDBDatabase) => void;

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
      for (const migrate of migrations.slice(event.oldVersion)) {
        migrate(request.result);
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
