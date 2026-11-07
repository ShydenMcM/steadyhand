/** What the History tab shows (#239 AC2): per stock, the days recorded, the chart reads and the
 * dividends kept. */

import { rowsOf } from "./record.ts";
import { STORES, type StoreName } from "./schema.ts";

export interface StockHistory {
  readonly symbol: string;
  readonly days: bigint;
  readonly chartReads: bigint;
  readonly dividends: bigint;
}

type Counted = "days" | "chartReads" | "dividends";

const COUNTED: readonly (readonly [StoreName, Counted])[] = [
  [STORES.closes, "days"],
  [STORES.series, "chartReads"],
  [STORES.dividends, "dividends"],
];

/** The stock code `row` of `store` was recorded under; refused when it has none. */
const symbolOf = (row: unknown, store: StoreName): string => {
  const symbol: unknown = (row as { symbol?: unknown }).symbol;
  if (typeof symbol !== "string") {
    throw new TypeError(`${store} holds a row with no stock code`);
  }
  return symbol;
};

/** Each stock anything is recorded for, by symbol, with its rows in each counted store. */
export const stockHistory = async (db: IDBDatabase): Promise<readonly StockHistory[]> => {
  const stocks = new Map<string, Record<Counted, bigint>>();
  for (const [store, counted] of COUNTED) {
    for (const row of await rowsOf(db, store)) {
      const symbol = symbolOf(row, store);
      const counts = stocks.get(symbol) ?? { days: 0n, chartReads: 0n, dividends: 0n };
      counts[counted] += 1n;
      stocks.set(symbol, counts);
    }
  }
  return [...stocks]
    .sort(([one], [other]) => one.localeCompare(other))
    .map(([symbol, counts]) => ({ symbol, ...counts }));
};
