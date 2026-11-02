/** `dividend-growth`: the stocks that paid a dividend every year and grew it, spread across the
 * months they pay in (M6 spec §6), ported from Python's `strategies.dividend_growth`. It is the
 * default strategy (core §8).
 *
 * It reviews on its first advice day in each calendar year, which is also its first advice day.
 * A stock passes in year Y when it is in the universe, it paid a cash dividend in every calendar
 * year from Y - growth_years - 1 to Y - 1 (by ex-date, restated in today's shares), and its total
 * for Y - 1 is at least its total for Y - growth_years - 1. The passers it can buy, and those it
 * holds, are its candidates. Up to `max_stocks` are held, in equal parts of
 * 1 / max(`min_stocks`, number held); with more candidates than that it picks them one at a time
 * to spread the months they pay in, then by trailing yield, then by symbol. Everything else is
 * sold. Fewer than `min_stocks` leaves the rest in cash, with a note. Between reviews it keeps
 * its holdings and puts new cash into the stocks it picked, never above the review's target.
 *
 * Missing versus ineligible (spec §7.1): a review judges every universe stock it can buy or
 * holds, and each needs a dividend read covering 1 January of Y - growth_years - 1 to the advice
 * day. A stock without one is missing: it is listed with the page to open and nothing is
 * ordered, and the memory is kept so the next advice day reviews again. A stock whose read
 * covers that and fails the test is ineligible: it is simply not picked. */

import type Decimal from "decimal.js";
import type { Day, Dividends } from "./broker-view.ts";
import { missingPage, note, NOTE_CODES, type Note } from "./notes.ts";
import { ratioDown, RuleDecimal } from "./ratio.ts";
import { restatedPerShare } from "./restated.ts";
import type { PortfolioView } from "./sizing.ts";
import {
  plus,
  readSet,
  weightOf,
  writeSet,
  type MarketView,
  type Memory,
  type Strategy,
  type StrategyDecision,
} from "./strategy.ts";

const NAME = "dividend-growth";
/** The memory key holding the stocks it picked, written as buy-and-hold writes its set. */
const SET = "set";
/** The memory key holding the calendar year it last reviewed. */
const YEAR = "year";
/** The window of the trailing yield that breaks a tie: the dividends of the last 365 days. */
const TRAILING_DAYS = 365;

/** The strategy Settings starts with (core §8). */
export const DEFAULT_STRATEGY = NAME;

/** Its settings' defaults (spec §7). */
export const DIVIDEND_GROWTH = { minStocks: 15n, maxStocks: 25n, growthYears: 5n } as const;

export interface DividendGrowth extends Strategy {
  /** Below this many picked stocks, the rest of the money is held as cash. */
  readonly minStocks: bigint;
  /** The most stocks it holds. */
  readonly maxStocks: bigint;
  /** The years over which a stock's dividends must have grown. */
  readonly growthYears: bigint;
}

/** A stock a review judges, with its dividends read. */
interface Judged {
  readonly symbol: string;
  readonly paid: readonly Paid[];
}

/** A dividend as the strategy reads it: per share in today's shares. */
interface Paid {
  readonly exDate: Day;
  readonly paymentDate: Day;
  readonly perShare: Decimal;
}

const larger = (first: bigint, second: bigint): bigint => (first > second ? first : second);

const atLeastOne = (value: bigint, setting: string): void => {
  if (value < 1n) {
    throw new RangeError(`${setting} must be at least 1, got ${value.toString()}`);
  }
};

/** The day `TRAILING_DAYS` calendar days before `day`. */
const trailingStart = (day: Day): Day => {
  const moved = new Date(`${day}T00:00:00Z`);
  moved.setUTCDate(moved.getUTCDate() - TRAILING_DAYS);
  return moved.toISOString().slice(0, 10);
};

/** The dividends `read` lists with an ex-date by `day`, restated in `day`'s shares. A dividend
 * announced for later has not been paid yet. */
const paidBy = (view: MarketView, read: Dividends): Paid[] =>
  read.dividends
    .filter((dividend) => dividend.exDate <= view.day)
    .map((dividend) => ({
      exDate: dividend.exDate,
      paymentDate: dividend.paymentDate,
      perShare: restatedPerShare(dividend, view.splits, view.day),
    }));

/** The stock's dividends of the last 365 days over its close, or 0 with no close to divide by. */
const trailingYield = (view: MarketView, symbol: string, paid: readonly Paid[]): Decimal => {
  const since = trailingStart(view.day);
  const total = paid
    .filter((dividend) => dividend.exDate > since)
    .reduce((sum, dividend) => sum.plus(dividend.perShare), new RuleDecimal(0));
  const lastClose = view.closes.get(symbol);
  return lastClose === undefined || lastClose.amount === 0n
    ? new RuleDecimal(0)
    : total.div(lastClose.amount.toString());
};

const tooFew = (count: bigint): string => {
  if (count === 0n) {
    return "No stock passed the dividend test; everything is held as cash until one does.";
  }
  const stocks = count === 1n ? "stock" : "stocks";
  return `Only ${count.toString()} ${stocks} passed the dividend test; the rest is held as cash until more do.`;
};

export const dividendGrowth = (
  minStocks: bigint = DIVIDEND_GROWTH.minStocks,
  maxStocks: bigint = DIVIDEND_GROWTH.maxStocks,
  growthYears: bigint = DIVIDEND_GROWTH.growthYears,
): DividendGrowth => {
  atLeastOne(minStocks, "min_stocks");
  atLeastOne(maxStocks, "max_stocks");
  atLeastOne(growthYears, "growth_years");
  if (maxStocks < minStocks) {
    throw new RangeError(
      `max_stocks must be at least min_stocks (${minStocks.toString()}), got ${maxStocks.toString()}`,
    );
  }

  /** Whether `paid` passes the dividend test in `year`: a dividend in every year of the
   * look-back, and the last year's total at least the first's. */
  const passes = (paid: readonly Paid[], year: bigint): boolean => {
    const totalIn = (paidIn: bigint): Decimal =>
      paid
        .filter((dividend) => dividend.exDate.startsWith(paidIn.toString()))
        .reduce((sum, dividend) => sum.plus(dividend.perShare), new RuleDecimal(0));
    const first = year - growthYears - 1n;
    for (let paidIn = first; paidIn < year; paidIn += 1n) {
      if (totalIn(paidIn).isZero()) {
        return false;
      }
    }
    return totalIn(year - 1n).gte(totalIn(first));
  };

  /** `maxStocks` of `candidates`, in symbol order, picked one at a time: each time the one whose
   * least crowded pay month has the fewest stocks already picked, then the higher trailing
   * yield; a tie keeps the earlier symbol. */
  const spread = (view: MarketView, candidates: readonly Judged[], year: bigint): Judged[] => {
    const lastYear = (year - 1n).toString();
    const ranked = candidates.map((judged) => ({
      judged,
      // A passer paid last year, so it has at least one month.
      months: [
        ...new Set(
          judged.paid
            .filter((dividend) => dividend.exDate.startsWith(lastYear))
            .map((dividend) => dividend.paymentDate.slice(5, 7)),
        ),
      ],
      trailing: trailingYield(view, judged.symbol, judged.paid),
    }));
    const crowding = new Map<string, bigint>();
    const crowded = (month: string): bigint => crowding.get(month) ?? 0n;
    const least = (months: readonly string[]): bigint =>
      months.map(crowded).reduce((low, count) => (count < low ? count : low));
    const better = (challenger: (typeof ranked)[0], holder: (typeof ranked)[0]): boolean => {
      const [mine, theirs] = [least(challenger.months), least(holder.months)];
      return mine < theirs || (mine === theirs && challenger.trailing.gt(holder.trailing));
    };
    const picked: Judged[] = [];
    let left = ranked;
    while (BigInt(picked.length) < maxStocks) {
      const best = left.reduce((holder, challenger) =>
        better(challenger, holder) ? challenger : holder,
      );
      picked.push(best.judged);
      left = left.filter((entry) => entry !== best);
      for (const month of best.months) {
        crowding.set(month, crowded(month) + 1n);
      }
    }
    return picked;
  };

  const review = (
    view: MarketView,
    portfolio: PortfolioView,
    memory: Memory,
    year: bigint,
  ): StrategyDecision => {
    const reachable = [...new Set([...view.tradable.buyable, ...portfolio.holdings.keys()])].sort();
    const windowStart = `${(year - growthYears - 1n).toString()}-01-01`;
    const judged: Judged[] = [];
    const missing: Note[] = [];
    for (const symbol of reachable.filter((held) => view.tradable.members.has(held))) {
      const read = view.dividends.get(symbol);
      if (read === undefined || read.covered.from > windowStart || read.covered.to < view.day) {
        missing.push(missingPage("dividends", symbol));
      } else {
        judged.push({ symbol, paid: paidBy(view, read) });
      }
    }
    if (missing.length > 0) {
      return { weights: new Map(), reasons: new Map(), missing, memory, notes: [] };
    }
    const passers = judged.filter((stock) => passes(stock.paid, year));
    const candidates = passers.map((stock) => stock.symbol);
    const picked = (
      BigInt(passers.length) <= maxStocks ? passers : spread(view, passers, year)
    ).map((stock) => stock.symbol);
    const target = ratioDown(1n, larger(minStocks, BigInt(picked.length)));
    const weights = new Map<string, Decimal>();
    const reasons = new Map<string, string>();
    for (const symbol of portfolio.holdings.keys()) {
      reasons.set(symbol, `${NAME}: no longer passes the dividend test`);
    }
    for (const symbol of candidates) {
      reasons.set(symbol, `${NAME}: not picked, to spread the months paid in`);
    }
    for (const symbol of picked) {
      weights.set(symbol, target);
      reasons.set(symbol, `${NAME}: paid a dividend every year and grew it`);
    }
    const count = BigInt(picked.length);
    const notes =
      count < minStocks ? [note(NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED, tooFew(count))] : [];
    const remembered = new Map([
      [SET, writeSet(picked)],
      [YEAR, year.toString()],
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
      throw new Error(`${NAME}'s memory has a year but no set`);
    }
    const chosen = readSet(set, NAME);
    const target = ratioDown(1n, larger(minStocks, BigInt(chosen.length)));
    const weights = new Map<string, Decimal>();
    const reasons = new Map<string, string>();
    for (const symbol of portfolio.holdings.keys()) {
      weights.set(symbol, weightOf(portfolio, symbol));
      reasons.set(symbol, `${NAME}: held until the next review`);
    }
    const buying = chosen.filter((symbol) => view.tradable.buyable.has(symbol));
    if (buying.length > 0) {
      const each = ratioDown(
        portfolio.spendable.amount / BigInt(buying.length),
        portfolio.value.amount,
      );
      for (const symbol of buying) {
        const held = weights.get(symbol) ?? new RuleDecimal(0);
        const room = RuleDecimal.max(new RuleDecimal(target).minus(held), 0);
        weights.set(symbol, plus(held, RuleDecimal.min(each, room)));
        reasons.set(symbol, `${NAME}: picked at the last review, topped up to its share`);
      }
    }
    return { weights, reasons, missing: [], memory, notes: [] };
  };

  return {
    name: NAME,
    minStocks,
    maxStocks,
    growthYears,
    decide(view, portfolio, memory) {
      const year = BigInt(view.day.slice(0, 4));
      return memory.get(YEAR) === year.toString()
        ? between(view, portfolio, memory)
        : review(view, portfolio, memory, year);
    },
  };
};
