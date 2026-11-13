/** The risk halts' record (spec §8, EXT S12, #236): the portfolio's value on each after-close
 * read, the deposits and withdrawals the user typed, each period the user answered for, and each
 * resume, read back as the `RiskRecord` core judges the halts from. Cash-movement page reads are
 * recorded by `recordCashMovements`, with the period each covers. */

import {
  adviceDayAt,
  IDR,
  Money,
  portfolioView,
  type CashMovement,
  type Covered,
  type Day,
  type IdxMarketRules,
  type Part,
  type Portfolio,
  type MovementRead,
  type Resumed,
  type RiskRecord,
  type TypedMovement,
  type Valuation,
} from "@steadyhand/core";
import { putAll, rowsOf, type ReadRules } from "./record.ts";
import { STORES } from "./schema.ts";

/** The tables a valuation needs: which day's close a read shows, and each stock's lot size. */
export interface ValuationRules extends ReadRules {
  readonly market: IdxMarketRules;
}

interface ValuationRow {
  readonly day: Day;
  readonly readAt: Date;
  readonly value: bigint;
  readonly currency: string;
  /** The cost basis invested (#256); a row stored before it has none. */
  readonly invested?: bigint;
}

interface MovementRow {
  readonly day: Day;
  readonly kind: CashMovement["kind"];
  readonly amount: string;
  readonly currency: string;
  readonly reference?: string;
}

interface TypedRow extends MovementRow {
  readonly typedAt: Date;
}

interface ResumeRow {
  readonly haltDay: Day;
  readonly at: Date;
  readonly strategy: string;
}

/** A recorded amount as money. steadyhand knows rupiah alone. */
export const amountOf = (amount: string | bigint, currency: string): Money => {
  if (currency !== IDR.code) {
    throw new Error(`a recorded amount is in ${currency}, not ${IDR.code}`);
  }
  return new Money(BigInt(amount), IDR);
};

/** Record the portfolio's value, all cash and every holding at its last price, and its cost basis
 * invested (#256), for the trading day whose close a portfolio read shows, and return that day. A read during a session shows
 * no close: it records nothing and returns `null`. A day read twice keeps the later read. */
export const recordValuation = async (
  db: IDBDatabase,
  read: Part<Portfolio>,
  rules: ValuationRules,
): Promise<Day | null> => {
  const day = adviceDayAt(read.readAt, rules.calendar, rules.sessions).adviceDay;
  if (day === null) {
    return null;
  }
  const view = portfolioView(rules.market, read.value, day);
  const row: ValuationRow = {
    day,
    readAt: read.readAt,
    value: view.value.amount,
    currency: view.value.currency.code,
    invested: view.invested.amount,
  };
  await putAll(db, STORES.valuations, [row]);
  return day;
};

/** Keep a deposit or withdrawal the user typed, as typed, under the instant it was typed. */
export const recordTyped = (db: IDBDatabase, entry: TypedMovement): Promise<void> => {
  const row: TypedRow = {
    day: entry.day,
    kind: entry.kind,
    amount: entry.amount.amount.toString(),
    currency: entry.amount.currency.code,
    typedAt: entry.typedAt,
  };
  return putAll(db, STORES.typedMovements, [row]);
};

/** Keep the user's answer that `period` is complete: every entry in it typed, or none. */
export const recordAnswered = (db: IDBDatabase, period: Covered, at: Date): Promise<void> =>
  putAll(db, STORES.answered, [{ from: period.from, to: period.to, at }]);

/** Keep a resume and the instant it was made (spec §8). */
export const recordResume = (db: IDBDatabase, resumed: Resumed): Promise<void> => {
  const row: ResumeRow = { haltDay: resumed.haltDay, at: resumed.at, strategy: resumed.strategy };
  return putAll(db, STORES.resumes, [row]);
};

const movementOf = (row: MovementRow): CashMovement => ({
  day: row.day,
  kind: row.kind,
  amount: amountOf(row.amount, row.currency),
  ...(row.reference === undefined ? {} : { reference: row.reference }),
});

const periodOf = (row: Covered): Covered => ({ from: row.from, to: row.to });

/** A cash-movement read's period and read time; a row stored before #499 has no time. */
const movementReadOf = (row: MovementRead): MovementRead => ({
  ...periodOf(row),
  ...(row.readAt === undefined ? {} : { readAt: row.readAt }),
});

/** Everything recorded that the halts are judged from, each kind in key order. */
export const riskRecord = async (db: IDBDatabase): Promise<RiskRecord> => {
  const valuations = (await rowsOf(db, STORES.valuations)) as ValuationRow[];
  const movements = (await rowsOf(db, STORES.cashMovements)) as MovementRow[];
  const movementReads = (await rowsOf(db, STORES.cashMovementReads)) as MovementRead[];
  const typed = (await rowsOf(db, STORES.typedMovements)) as TypedRow[];
  const answered = (await rowsOf(db, STORES.answered)) as Covered[];
  const resumes = (await rowsOf(db, STORES.resumes)) as ResumeRow[];
  return {
    valuations: valuations.map((row): Valuation => ({
      day: row.day,
      readAt: row.readAt,
      value: amountOf(row.value, row.currency),
      ...(row.invested === undefined ? {} : { invested: amountOf(row.invested, row.currency) }),
    })),
    movements: movements.map(movementOf),
    movementReads: movementReads.map(movementReadOf),
    typed: typed.map((row): TypedMovement => ({
      day: row.day,
      kind: row.kind,
      amount: amountOf(row.amount, row.currency),
      typedAt: row.typedAt,
    })),
    answered: answered.map(periodOf),
    resumes: resumes.map((row): Resumed => ({
      haltDay: row.haltDay,
      at: row.at,
      strategy: row.strategy,
    })),
  };
};
