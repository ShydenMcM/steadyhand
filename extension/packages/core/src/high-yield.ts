/** `high-yield`: the stocks that kept paying, with the highest dividend yields (M7 decision 5),
 * as spec §7.2 restates it. There is no Python reference.
 *
 * It reviews on its first advice day in each calendar quarter, which is the first advice day on
 * or after the quarter's first trading day, and on its first advice day. A stock passes when it
 * paid a cash dividend, by ex-date, in each of the `paid_years` calendar years before this one.
 * Its yield is its dividends per share with an ex-date in the 365 days up to the advice day,
 * restated in today's shares (§6.6), over the advice day's close. A review targets the
 * `yield_stocks` passers with the highest yield, ties broken by symbol (every stock is of IDX),
 * at 1/`yield_stocks` each, and sells everything else. Fewer passers leave the rest in cash, with
 * a note. Between reviews it keeps its holdings and puts new cash into its picks, never above
 * 1/`yield_stocks`.
 *
 * Missing versus ineligible (spec §7.1): a review judges every universe stock it can buy or
 * holds, and each needs a dividend read covering 1 January of the first of the `paid_years` years
 * to the advice day. A stock without one, or with a corporate action found by price and no known
 * ratio after that day (§6.6), is missing: its page is listed, nothing is ordered, and the memory
 * is kept so the next advice day reviews again. */

import type Decimal from "decimal.js";
import type { Day } from "./broker-view.ts";
import { missingPage, note, NOTE_CODES, type Note } from "./notes.ts";
import { ratioDown } from "./ratio.ts";
import { paidBy, trailingYield, type PaidDividend } from "./restated.ts";
import type { PortfolioView } from "./sizing.ts";
import {
  keepAndTopUp,
  readSet,
  writeSet,
  type MarketView,
  type Memory,
  type Strategy,
  type StrategyDecision,
} from "./strategy.ts";

const NAME = "high-yield";
/** The memory key holding the stocks it picked. */
const SET = "set";
/** The memory key holding the quarter it last reviewed, as `2025-1`. */
const QUARTER = "quarter";

/** Its settings' defaults (spec §7). */
export const HIGH_YIELD = { yieldStocks: 10n, paidYears: 3n } as const;

export interface HighYield extends Strategy {
  /** The most stocks it holds, each at 1/`yieldStocks`. */
  readonly yieldStocks: bigint;
  /** The calendar years before this one in each of which a stock must have paid. */
  readonly paidYears: bigint;
}

/** A stock a review judges: its yield, and whether it passes. */
interface Judged {
  readonly symbol: string;
  readonly passes: boolean;
  readonly yielded: Decimal;
}

const atLeastOne = (value: bigint, setting: string): void => {
  if (value < 1n) {
    throw new RangeError(`${setting} must be at least 1, got ${value.toString()}`);
  }
};

/** `day`'s calendar quarter, as `2025-1` for January to March 2025. */
const quarterOf = (day: Day): string =>
  `${day.slice(0, 4)}-${((BigInt(day.slice(5, 7)) + 2n) / 3n).toString()}`;

export const highYield = (
  yieldStocks: bigint = HIGH_YIELD.yieldStocks,
  paidYears: bigint = HIGH_YIELD.paidYears,
): HighYield => {
  atLeastOne(yieldStocks, "yield_stocks");
  atLeastOne(paidYears, "paid_years");
  const target = ratioDown(1n, yieldStocks);
  const years = `the last ${paidYears.toString()} years`;

  /** Whether `paid` holds a dividend in each of the `paidYears` calendar years before `year`. */
  const passes = (paid: readonly PaidDividend[], year: bigint): boolean => {
    for (let paidIn = year - paidYears; paidIn < year; paidIn += 1n) {
      const prefix = `${paidIn.toString()}-`;
      if (!paid.some((dividend) => dividend.exDate.startsWith(prefix))) {
        return false;
      }
    }
    return true;
  };

  const tooFew = (count: bigint): string => {
    if (count === 0n) {
      return `No stock paid a dividend in each of ${years}; everything is held as cash until one does.`;
    }
    const stocks = count === 1n ? "stock" : "stocks";
    return `Only ${count.toString()} ${stocks} paid a dividend in each of ${years}; the rest is held as cash until more do.`;
  };

  const review = (view: MarketView, portfolio: PortfolioView, memory: Memory): StrategyDecision => {
    const year = BigInt(view.day.slice(0, 4));
    const reachable = [...new Set([...view.tradable.buyable, ...portfolio.holdings.keys()])].sort();
    const windowStart = `${(year - paidYears).toString()}-01-01`;
    const judged: Judged[] = [];
    const missing: Note[] = [];
    for (const symbol of reachable.filter((held) => view.tradable.members.has(held))) {
      const read = view.dividends.get(symbol);
      const unread =
        read === undefined || read.covered.from > windowStart || read.covered.to < view.day;
      const action = view.unknownActions.get(symbol);
      const crossed = action !== undefined && action > windowStart;
      if (unread) {
        missing.push(missingPage("dividends", symbol));
      }
      if (crossed) {
        missing.push(missingPage("corporate-actions", symbol));
      }
      if (!unread && !crossed) {
        const paid = paidBy(read, view.splits, view.day);
        judged.push({
          symbol,
          passes: passes(paid, year),
          yielded: trailingYield(paid, view.day, view.closes.get(symbol)),
        });
      }
    }
    if (missing.length > 0) {
      return { weights: new Map(), reasons: new Map(), missing, memory, notes: [] };
    }
    // Highest yield first; `judged` is in symbol order and the sort is stable, so a tie keeps it.
    const passers = judged
      .filter((stock) => stock.passes)
      .sort((first, second) => second.yielded.comparedTo(first.yielded));
    const picked: Judged[] = [];
    for (const stock of passers) {
      if (BigInt(picked.length) < yieldStocks) {
        picked.push(stock);
      }
    }
    const weights = new Map<string, Decimal>();
    const reasons = new Map<string, string>();
    for (const symbol of portfolio.holdings.keys()) {
      reasons.set(symbol, `${NAME}: no longer paid a dividend in each of ${years}`);
    }
    for (const stock of passers) {
      reasons.set(
        stock.symbol,
        `${NAME}: not among the ${yieldStocks.toString()} highest dividend yields`,
      );
    }
    for (const stock of picked) {
      weights.set(stock.symbol, target);
      reasons.set(
        stock.symbol,
        `${NAME}: among the ${yieldStocks.toString()} highest dividend yields`,
      );
    }
    const count = BigInt(picked.length);
    const notes =
      count < yieldStocks ? [note(NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED, tooFew(count))] : [];
    const remembered = new Map([
      [SET, writeSet(picked.map((stock) => stock.symbol))],
      [QUARTER, quarterOf(view.day)],
    ]);
    return { weights, reasons, missing: [], memory: remembered, notes };
  };

  const between = (
    view: MarketView,
    portfolio: PortfolioView,
    memory: Memory,
  ): StrategyDecision => {
    const set = memory.get(SET);
    if (set === undefined) {
      throw new Error(`${NAME}'s memory has a quarter but no set`);
    }
    const picks = readSet(set, NAME);
    const { weights, reasons } = keepAndTopUp(NAME, view, portfolio, picks, target);
    return { weights, reasons, missing: [], memory, notes: [] };
  };

  return {
    name: NAME,
    yieldStocks,
    paidYears,
    decide(view, portfolio, memory) {
      return memory.get(QUARTER) === quarterOf(view.day)
        ? between(view, portfolio, memory)
        : review(view, portfolio, memory);
    },
  };
};
