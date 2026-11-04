/** `ma-trend`: hold the stocks whose total return is trending up (M7 decisions 2 and 6), as spec
 * §7.2 restates it. There is no Python reference.
 *
 * Every advice day it judges afresh, with no memory. A stock is in an uptrend when the simple
 * average of its last `fast_days` total-return closes (§6.5) is strictly above the average of its
 * last `slow_days`. N is the number of universe members that day. A held stock in an uptrend keeps
 * its weight; new cash goes to the uptrend stocks it can buy, each to no more than 1/N, the ones
 * with least room first (`topUp`), so a stock not held reaches 1/N when the cash allows.
 * A downtrend, or leaving the universe, sells the whole holding. The rest is cash.
 *
 * Missing versus ineligible (spec §7.1): it judges every universe stock it can buy or holds, and
 * each needs `slow_days` total-return closes. A stock with fewer whose chart reaches back to the
 * window's start, the `slow_days`-th trading day back, but whose first close comes after it, was
 * not trading then: it is ineligible, not in an uptrend, and the others are still judged (#490).
 * A stock with no series, a series asking for its chart again, an unread dividend window or
 * fewer closes otherwise is missing, and nothing is ordered. */

import type Decimal from "decimal.js";
import { missingHistory, missingPage, type Note } from "./notes.ts";
import { ratioDown, RuleDecimal } from "./ratio.ts";
import { chartReach, type SeriesClose } from "./series.ts";
import type { PortfolioView } from "./sizing.ts";
import { topUp, weightOf, type MarketView, type Memory, type Strategy } from "./strategy.ts";
import { totalReturn } from "./total-return.ts";

const NAME = "ma-trend";

/** Its settings' defaults (spec §7). */
export const MA_TREND = { fastDays: 50n, slowDays: 200n } as const;

export interface MaTrend extends Strategy {
  /** The closes in the fast average. */
  readonly fastDays: bigint;
  /** The closes in the slow average; more than `fastDays`. */
  readonly slowDays: bigint;
}

/** The sum of the last `count` of `closes`. */
const lastSum = (closes: readonly SeriesClose[], count: bigint): Decimal => {
  let sum: Decimal = new RuleDecimal(0);
  let taken = 0n;
  for (const daily of [...closes].reverse()) {
    if (taken < count) {
      sum = sum.plus(daily.close);
      taken += 1n;
    }
  }
  return sum;
};

export const maTrend = (
  fastDays: bigint = MA_TREND.fastDays,
  slowDays: bigint = MA_TREND.slowDays,
): MaTrend => {
  if (fastDays < 1n) {
    throw new RangeError(`fast_days must be at least 1, got ${fastDays.toString()}`);
  }
  if (fastDays >= slowDays) {
    throw new RangeError(
      `fast_days must be below slow_days, got ${fastDays.toString()} and ${slowDays.toString()}`,
    );
  }
  const fast = fastDays.toString();
  const slow = slowDays.toString();
  const up = `${NAME}: in an uptrend, its ${fast}-day average above its ${slow}-day average`;
  const down = `${NAME}: not in an uptrend, its ${fast}-day average not above its ${slow}-day average`;
  const short = `${NAME}: not in an uptrend, its history is shorter than ${slow} trading days`;

  /** Whether `closes`, at least `slowDays` of them, are in an uptrend: the fast average above the
   * slow one, compared as sums scaled by the other's count so no division rounds. */
  const rising = (closes: readonly SeriesClose[]): boolean =>
    lastSum(closes, fastDays).times(slow).greaterThan(lastSum(closes, slowDays).times(fast));

  /** Whether `symbol` is in an uptrend on `view`'s day, or ineligible, or the gaps that keep it
   * from being judged. */
  const judge = (
    view: MarketView,
    symbol: string,
  ): { readonly up: boolean; readonly ineligible: boolean; readonly missing: readonly Note[] } => {
    const series = view.series.get(symbol);
    const first = series?.closes[0];
    if (series === undefined || first === undefined) {
      return { up: false, ineligible: false, missing: [missingPage("stock-detail", symbol)] };
    }
    const held = BigInt(series.closes.length);
    const isShort = held < slowDays;
    if (
      isShort &&
      chartReach(series, view.calendar.windowStart(view.day, slowDays)) === "ineligible"
    ) {
      return { up: false, ineligible: true, missing: [] };
    }
    const found = totalReturn(symbol, series, view.dividends.get(symbol), view.splits, view.day);
    if (found.missing.length > 0) {
      return { up: false, ineligible: false, missing: found.missing };
    }
    if (isShort) {
      return {
        up: false,
        ineligible: false,
        missing: [missingHistory(symbol, { from: first.day, to: view.day }, held)],
      };
    }
    return { up: rising(found.closes), ineligible: false, missing: [] };
  };

  return {
    name: NAME,
    fastDays,
    slowDays,
    decide(view: MarketView, portfolio: PortfolioView, memory: Memory) {
      const { members, buyable } = view.tradable;
      const reachable = [...new Set([...buyable, ...portfolio.holdings.keys()])]
        .filter((symbol) => members.has(symbol))
        .sort();
      const trending: string[] = [];
      const ineligible = new Set<string>();
      const missing: Note[] = [];
      for (const symbol of reachable) {
        const judged = judge(view, symbol);
        missing.push(...judged.missing);
        if (judged.up) {
          trending.push(symbol);
        }
        if (judged.ineligible) {
          ineligible.add(symbol);
        }
      }
      if (missing.length > 0) {
        return { weights: new Map(), reasons: new Map(), missing, memory, notes: [] };
      }
      const weights = new Map<string, Decimal>();
      const reasons = new Map<string, string>();
      for (const symbol of portfolio.holdings.keys()) {
        const why = ineligible.has(symbol) ? short : down;
        reasons.set(symbol, members.has(symbol) ? why : `${NAME}: no longer in the universe`);
      }
      for (const symbol of trending) {
        reasons.set(symbol, up);
        if (portfolio.holdings.has(symbol)) {
          weights.set(symbol, weightOf(portfolio, symbol));
        }
      }
      // With no member, nothing trends: 1/N is worked out only when a stock does.
      if (trending.length > 0) {
        const target = ratioDown(1n, BigInt(members.size));
        const buying = trending.filter((symbol) => buyable.has(symbol));
        for (const [symbol, weight] of topUp(portfolio, buying, target)) {
          weights.set(symbol, weight);
        }
      }
      return { weights, reasons, missing: [], memory, notes: [] };
    },
  };
};
