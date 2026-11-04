/** What a read records (spec §6.2). Every row is plain data, so IndexedDB's structured clone
 * keeps it whole: money as a `bigint` of minor units with its currency's code, and any key field
 * as text, since a `bigint` cannot be part of a key. */

import {
  adviceDayAt,
  memoryFor,
  totalsMismatch,
  type Memory,
  type StoredMemory,
  type CashMovements,
  type CorporateActions,
  type Dated,
  type Day,
  type Dividends,
  type IdxCalendar,
  type Part,
  type Portfolio,
  type SessionRow,
  type StockDetail,
  type Watchlist,
} from "@steadyhand/core";
import { failure, requested, STORES, type StoreName } from "./schema.ts";

/** How a broker's chart series is adjusted, as its reader declares (spec §5.2). */
export type Adjustment = "none" | "splits" | "splits-and-dividends";

/** The tables that say which trading day's close a read shows. */
export interface ReadRules {
  readonly calendar: IdxCalendar;
  readonly sessions: Dated<SessionRow>;
}

/** Write each store's rows in one transaction, settled when it commits. */
const putEach = (
  db: IDBDatabase,
  writes: readonly (readonly [StoreName, readonly object[]])[],
): Promise<void> =>
  new Promise((resolve, reject) => {
    const stores = writes.map(([store]) => store);
    const write = db.transaction(stores, "readwrite");
    for (const [store, rows] of writes) {
      for (const row of rows) {
        write.objectStore(store).put(row);
      }
    }
    write.oncomplete = () => {
      resolve();
    };
    write.onerror = () => {
      reject(failure(write.error, `writing ${stores.join(" and ")}`));
    };
  });

/** Write `rows` to `store` in one transaction, settled when it commits. */
export const putAll = (db: IDBDatabase, store: StoreName, rows: readonly object[]): Promise<void> =>
  putEach(db, [[store, rows]]);

/** `rows` each given its `entry` (#470): `ref` and the broker's reference where the row has one,
 * else `#` and its place among the rows of the same read with the same fields, so two equal
 * deposits on one day are two rows and reading the page again writes the same keys. */
const entered = <T extends object>(
  rows: readonly T[],
  reference: (row: T) => string | undefined,
): (T & { readonly entry: string })[] => {
  const seen = new Map<string, bigint>();
  return rows.map((row) => {
    const own = reference(row);
    if (own !== undefined) {
      return { ...row, entry: `ref ${own}` };
    }
    const fields = JSON.stringify(row);
    const place = (seen.get(fields) ?? 0n) + 1n;
    seen.set(fields, place);
    return { ...row, entry: `#${place.toString()}` };
  });
};

/** Every row of `store`, in key order. */
export const rowsOf = (db: IDBDatabase, store: StoreName): Promise<unknown[]> =>
  requested(db.transaction(store, "readonly").objectStore(store).getAll());

/** Record the close each stock shows in a portfolio or watchlist read, and return its day.
 *
 * A read from the second a trading day's close is final until the next trading day's
 * pre-opening shows that day's close; a read during a session shows none, records nothing and
 * returns `null`. A stock read twice for one day keeps the later read's close. */
export const recordCloses = async (
  db: IDBDatabase,
  read: Part<Portfolio> | Part<Watchlist>,
  rules: ReadRules,
): Promise<Day | null> => {
  const day = adviceDayAt(read.readAt, rules.calendar, rules.sessions).adviceDay;
  if (day === null) {
    return null;
  }
  const shown = "holdings" in read.value ? read.value.holdings : read.value.stocks;
  await putAll(
    db,
    STORES.closes,
    shown.map((stock) => ({
      symbol: stock.symbol,
      day,
      close: stock.lastPrice.amount,
      currency: stock.lastPrice.currency.code,
      source: read.source,
    })),
  );
  return day;
};

/** Record a stock detail read's chart series as shown, under the instant it was read, with the
 * adjustment its reader declares. */
export const recordSeries = (
  db: IDBDatabase,
  read: Part<StockDetail>,
  adjustment: Adjustment,
): Promise<void> =>
  putAll(db, STORES.series, [
    {
      symbol: read.value.symbol,
      readAt: read.readAt.toISOString(),
      adjustment,
      covered: read.value.covered,
      closes: read.value.closes.map((daily) => ({
        day: daily.day,
        close: daily.close.amount,
        currency: daily.close.currency.code,
      })),
      source: read.source,
    },
  ]);

/** Record each dividend a page lists, once: keyed by its own fields and its entry, and the
 * period the read covers for its stock, in the same transaction (spec §7.1). */
export const recordDividends = (db: IDBDatabase, read: Part<Dividends>): Promise<void> =>
  putEach(db, [
    [STORES.dividendReads, [{ symbol: read.value.symbol, ...read.value.covered }]],
    [
      STORES.dividends,
      entered(
        read.value.dividends.map((dividend) => ({
          symbol: dividend.symbol,
          exDate: dividend.exDate,
          paymentDate: dividend.paymentDate,
          grossPerShare: dividend.grossPerShare.toString(),
          ...(dividend.reference === undefined ? {} : { reference: dividend.reference }),
        })),
        (row) => ("reference" in row ? row.reference : undefined),
      ),
    ],
  ]);

/** Record each cash movement a page lists, once: keyed by its own fields and its entry, and the
 * period the read covers, in the same transaction (#236). A read
 * whose rows do not add up to the totals its page shows is refused and nothing is written,
 * whichever reader made it (#477): a page cut short must never be recorded as the whole period. */
export const recordCashMovements = (db: IDBDatabase, read: Part<CashMovements>): Promise<void> => {
  const mismatch = totalsMismatch(read.value);
  if (mismatch !== undefined) {
    return Promise.reject(new Error(`refusing a cash-movement read: ${mismatch}`));
  }
  return putEach(db, [
    [STORES.cashMovementReads, [read.value.covered]],
    [
      STORES.cashMovements,
      entered(
        read.value.movements.map((movement) => ({
          day: movement.day,
          kind: movement.kind,
          amount: movement.amount.amount.toString(),
          currency: movement.amount.currency.code,
          ...(movement.reference === undefined ? {} : { reference: movement.reference }),
        })),
        (row) => ("reference" in row ? row.reference : undefined),
      ),
    ],
  ]);
};

/** Record each split a page lists, once: keyed by its own fields and its entry, and the period
 * the read covers, in the same transaction (#480). */
export const recordCorporateActions = (
  db: IDBDatabase,
  read: Part<CorporateActions>,
): Promise<void> =>
  putEach(db, [
    [STORES.corporateActionReads, [read.value.covered]],
    [
      STORES.corporateActions,
      entered(
        read.value.splits.map((split) => ({
          symbol: split.symbol,
          exDate: split.exDate,
          from: split.from.toString(),
          to: split.to.toString(),
          ...(split.reference === undefined ? {} : { reference: split.reference }),
        })),
        (row) => ("reference" in row ? row.reference : undefined),
      ),
    ],
  ]);

/** Keep `strategy`'s memory with the advice day it was written for (spec §4.3, #229 AC1). */
export const remember = (db: IDBDatabase, strategy: string, stored: StoredMemory): Promise<void> =>
  putAll(db, STORES.memory, [{ strategy, ...stored }]);

/** The memory `strategy` advises with on `day`: the memory that day began with when it was
 * advised before, so the advice for a day is the same however often it is asked for. */
export const rememberedFor = async (
  db: IDBDatabase,
  strategy: string,
  day: Day,
): Promise<Memory> => {
  const read = db.transaction(STORES.memory, "readonly").objectStore(STORES.memory);
  const stored = (await requested(read.get(strategy))) as StoredMemory | undefined;
  return memoryFor(stored, day);
};

/** Keep one setting. */
export const putSetting = (db: IDBDatabase, name: string, value: unknown): Promise<void> =>
  putAll(db, STORES.settings, [{ name, value }]);
