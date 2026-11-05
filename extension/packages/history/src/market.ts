/** What the panel reads back to advise with (#238): each stock's recorded closes, its dividend
 * record and the period it covers (spec §7.1), every split and corporate action read (#480), and
 * the settings. */

import {
  dayAfter,
  RuleDecimal,
  type Covered,
  type DailyClose,
  type Day,
  type Dividend,
  type Dividends,
  type Split,
} from "@steadyhand/core";
import { rowsOf } from "./record.ts";
import { amountOf } from "./risk.ts";
import { requested, STORES } from "./schema.ts";

interface CloseRow {
  readonly symbol: string;
  readonly day: Day;
  readonly close: bigint;
  readonly currency: string;
}

interface DividendRow {
  readonly symbol: string;
  readonly exDate: Day;
  readonly paymentDate: Day;
  readonly grossPerShare: string;
  readonly reference?: string;
}

interface DividendReadRow extends Covered {
  readonly symbol: string;
}

interface SplitRow {
  readonly symbol: string;
  readonly exDate: Day;
  readonly from: string;
  readonly to: string;
  readonly reference?: string;
}

/** `rows` grouped by `key`, each group in the rows' order. */
const grouped = <T, V>(rows: readonly T[], key: (row: T) => string, value: (row: T) => V) => {
  const groups = new Map<string, V[]>();
  for (const row of rows) {
    const group = groups.get(key(row));
    if (group === undefined) {
      groups.set(key(row), [value(row)]);
    } else {
      group.push(value(row));
    }
  }
  return groups;
};

/** Each stock's recorded closes, in day order, as rupiah. */
export const recordedCloses = async (db: IDBDatabase): Promise<Map<string, DailyClose[]>> => {
  const rows = (await rowsOf(db, STORES.closes)) as CloseRow[];
  return grouped(
    rows,
    (row) => row.symbol,
    (row): DailyClose => ({ day: row.day, close: amountOf(row.close, row.currency) }),
  );
};

/** The latest period `reads` cover without a break, joining reads that overlap or meet end to
 * end. `reads` is in key order, by `from`. */
const latestCovered = (reads: readonly Covered[]): Covered => {
  const [first, ...rest] = reads as [Covered, ...Covered[]];
  let span: Covered = { from: first.from, to: first.to };
  for (const read of rest) {
    if (read.from <= dayAfter(span.to)) {
      span = { from: span.from, to: read.to > span.to ? read.to : span.to };
    } else {
      span = { from: read.from, to: read.to };
    }
  }
  return span;
};

const dividendOf = (row: DividendRow): Dividend => ({
  symbol: row.symbol,
  exDate: row.exDate,
  paymentDate: row.paymentDate,
  grossPerShare: new RuleDecimal(row.grossPerShare),
  ...(row.reference === undefined ? {} : { reference: row.reference }),
});

/** Each read stock's dividends and the latest period its reads cover without a break (spec
 * §7.1). A stock with no read is absent: dividends recorded before reads kept their period say
 * nothing about the years with none. */
export const dividendRecord = async (db: IDBDatabase): Promise<Map<string, Dividends>> => {
  const reads = grouped(
    (await rowsOf(db, STORES.dividendReads)) as DividendReadRow[],
    (row) => row.symbol,
    (row): Covered => ({ from: row.from, to: row.to }),
  );
  const rows = grouped(
    (await rowsOf(db, STORES.dividends)) as DividendRow[],
    (row) => row.symbol,
    dividendOf,
  );
  return new Map(
    [...reads].map(([symbol, covered]) => [
      symbol,
      { symbol, covered: latestCovered(covered), dividends: rows.get(symbol) ?? [] },
    ]),
  );
};

/** Every split a page has shown and the period each corporate action read covered (#480). */
export const corporateActionRecord = async (
  db: IDBDatabase,
): Promise<{ splits: Split[]; reads: Covered[] }> => {
  const splits = (await rowsOf(db, STORES.corporateActions)) as SplitRow[];
  const reads = (await rowsOf(db, STORES.corporateActionReads)) as Covered[];
  return {
    splits: splits.map((row): Split => ({
      symbol: row.symbol,
      exDate: row.exDate,
      from: BigInt(row.from),
      to: BigInt(row.to),
      ...(row.reference === undefined ? {} : { reference: row.reference }),
    })),
    reads: reads.map((row): Covered => ({ from: row.from, to: row.to })),
  };
};

/** The setting `name` as last kept, or `undefined` when it never was. */
export const settingOf = async (db: IDBDatabase, name: string): Promise<unknown> => {
  const read = db.transaction(STORES.settings, "readonly").objectStore(STORES.settings);
  const row = (await requested(read.get(name))) as { readonly value: unknown } | undefined;
  return row?.value;
};
