/** `monthly-savings`: the starting cash invested in monthly instalments (M6 spec §5), ported from
 * Python's `strategies.monthly_savings`.
 *
 * On its first advice day it fixes the instalment: the cash it may spend that day divided by
 * `instalments`, rounded down to a whole rupiah. On the first advice day of each calendar month it
 * spends its cash less a reserve for the instalments still due after this one, split equally
 * across the stocks buyable that day, and keeps every holding at its current weight. It never
 * sells. Top-ups and dividends go in with the next instalment; after the last one it spends all
 * its cash each month. A month in which nothing can be bought is not counted. */

import type Decimal from "decimal.js";
import { ratioDown } from "./ratio.ts";
import { plus, weightOf, type Strategy } from "./strategy.ts";

const NAME = "monthly-savings";
const INSTALMENT = "instalment";
const DUE = "due";
const MONTH = "month";

/** The fewest and the most instalments Settings allows (#229 AC4), and the default. */
export const INSTALMENTS = { least: 1n, most: 120n, default: 12n } as const;

export interface MonthlySavings extends Strategy {
  readonly instalments: bigint;
}

const larger = (first: bigint, second: bigint): bigint => (first > second ? first : second);

/** The whole number remembered under `key`, which the memory must hold. */
const recalled = (memory: ReadonlyMap<string, string>, key: string): bigint => {
  const text = memory.get(key);
  if (text === undefined) {
    throw new Error(`${NAME}'s memory has an instalment but no ${key}`);
  }
  return BigInt(text);
};

export const monthlySavings = (instalments: bigint = INSTALMENTS.default): MonthlySavings => {
  if (instalments < INSTALMENTS.least || instalments > INSTALMENTS.most) {
    throw new RangeError(`instalments must be from 1 to 120, got ${instalments.toString()}`);
  }
  return {
    name: NAME,
    instalments,
    decide(view, portfolio, memory) {
      const cash = portfolio.spendable.amount;
      const fixed = memory.get(INSTALMENT);
      const instalment = fixed === undefined ? cash / instalments : BigInt(fixed);
      let due = fixed === undefined ? instalments : recalled(memory, DUE);
      let bought = memory.get(MONTH);
      const weights = new Map<string, Decimal>();
      const reasons = new Map<string, string>();
      for (const symbol of portfolio.holdings.keys()) {
        weights.set(symbol, weightOf(portfolio, symbol));
        reasons.set(symbol, `${NAME}: held, never sold`);
      }
      const month = view.day.slice(0, 7);
      const buying = [...view.tradable.buyable];
      if (buying.length > 0 && bought !== month) {
        const reserve = due > 0n ? (due - 1n) * instalment : 0n;
        const each = ratioDown(
          larger(cash - reserve, 0n) / BigInt(buying.length),
          portfolio.value.amount,
        );
        for (const symbol of buying) {
          weights.set(symbol, plus(weights.get(symbol), each));
          reasons.set(symbol, `${NAME}: this month's instalment, split equally`);
        }
        due = larger(due - 1n, 0n);
        bought = month;
      }
      const remembered = new Map([
        [INSTALMENT, instalment.toString()],
        [DUE, due.toString()],
      ]);
      if (bought !== undefined) {
        remembered.set(MONTH, bought);
      }
      return { weights, reasons, missing: [], memory: remembered, notes: [] };
    },
  };
};
