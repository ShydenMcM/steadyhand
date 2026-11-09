/** `low-volatility`: hold the stocks whose total return moved most evenly over the last year, as
 * spec §7.3 states it (Shyden, 2026-11-09, #247). There is no Python reference.
 *
 * A stock's look-back is its total-return closes (§6.5) from the close on the last trading day on
 * or before the date `volatilityMonths` calendar months before the advice day, up to the advice
 * day. A daily move is a close over the close before it, less 1, and its volatility is the standard
 * deviation of those moves, compared as the variance so no square root rounds. It reviews on the
 * first advice day of each calendar month, and on its first advice day. A review targets the
 * `volatilityStocks` lowest, ties broken by symbol (every stock is of IDX), at 1/`volatilityStocks`
 * each, and sells everything else; fewer stocks to judge leave the rest in cash, with a note.
 * Between reviews it keeps its holdings and puts new cash into its picks, never above
 * 1/`volatilityStocks`.
 *
 * Missing versus ineligible (spec §7.1): as momentum-rotation, except that a look-back of fewer than
 * 15 closes a month is ineligible too, because a stock that hardly traded would look calm. */

import type Decimal from "decimal.js";
import { monthsBefore } from "./months.ts";
import { missingHistory, missingPage, note, NOTE_CODES, type Note } from "./notes.ts";
import { ratioDown, RuleDecimal } from "./ratio.ts";
import { chartReach } from "./series.ts";
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
import { totalReturn } from "./total-return.ts";

const NAME = "low-volatility";
/** The memory key holding the stocks it picked. */
const SET = "set";
/** The memory key holding the month it last reviewed, as `2025-01`. */
const MONTH = "month";
/** The fewest closes a month of look-back needs for a stock to be judged. */
const CLOSES_A_MONTH = 15n;

/** Its settings' defaults (spec §7.3). */
export const LOW_VOLATILITY = {
  volatilityStocks: 10n,
  volatilityMonths: 12n,
} as const;

export interface LowVolatility extends Strategy {
  /** The most stocks it holds, each at 1/`volatilityStocks`. */
  readonly volatilityStocks: bigint;
  /** How many calendar months back its look-back starts. */
  readonly volatilityMonths: bigint;
}

/** A stock a review ranks. */
interface Judged {
  readonly symbol: string;
  readonly variance: Decimal;
}

/** Why a stock with a read chart is not judged. */
type Ineligible = "not trading" | "too few closes";

/** The variance of the daily moves of `closes`, which hold at least two: over all the moves,
 * dividing by their number. */
export const dailyVariance = (closes: readonly Decimal[]): Decimal => {
  const moves: Decimal[] = [];
  let before: Decimal | undefined;
  for (const close of closes) {
    if (before !== undefined) {
      moves.push(new RuleDecimal(close).dividedBy(before).minus(1));
    }
    before = close;
  }
  const count = new RuleDecimal(BigInt(moves.length).toString());
  const mean = moves.reduce((sum, move) => sum.plus(move), new RuleDecimal(0)).dividedBy(count);
  return moves
    .reduce((sum, move) => sum.plus(move.minus(mean).pow(2)), new RuleDecimal(0))
    .dividedBy(count);
};

export const lowVolatility = (
  volatilityStocks: bigint = LOW_VOLATILITY.volatilityStocks,
  volatilityMonths: bigint = LOW_VOLATILITY.volatilityMonths,
): LowVolatility => {
  if (volatilityStocks < 1n) {
    throw new RangeError(
      `volatility_stocks must be at least 1, got ${volatilityStocks.toString()}`,
    );
  }
  if (volatilityMonths < 1n) {
    throw new RangeError(
      `volatility_months must be at least 1, got ${volatilityMonths.toString()}`,
    );
  }
  const target = ratioDown(1n, volatilityStocks);
  const calmest = `the ${volatilityStocks.toString()} calmest by daily moves`;

  /** `symbol`'s variance on `view`'s day, why it cannot be judged, or the gaps that keep it so. */
  const judge = (
    view: MarketView,
    symbol: string,
  ): { readonly judged: Judged | Ineligible | null; readonly missing: readonly Note[] } => {
    const series = view.series.get(symbol);
    const first = series?.closes[0];
    if (series === undefined || first === undefined) {
      return { judged: null, missing: [missingPage("stock-detail", symbol)] };
    }
    const startDay = monthsBefore(view.day, volatilityMonths);
    const reach = chartReach(series, startDay);
    if (reach === "ineligible") {
      return { judged: "not trading", missing: [] };
    }
    const found = totalReturn(symbol, series, view.dividends.get(symbol), view.splits, view.day);
    if (found.missing.length > 0) {
      return { judged: null, missing: found.missing };
    }
    if (reach === "missing") {
      const held = BigInt(found.closes.length);
      return {
        judged: null,
        missing: [missingHistory(symbol, { from: first.day, to: view.day }, held)],
      };
    }
    let closes: Decimal[] = [];
    for (const daily of found.closes) {
      if (daily.day <= startDay) {
        closes = [daily.close];
      } else if (daily.day <= view.day) {
        closes.push(daily.close);
      }
    }
    if (BigInt(closes.length) < CLOSES_A_MONTH * volatilityMonths) {
      return { judged: "too few closes", missing: [] };
    }
    return { judged: { symbol, variance: dailyVariance(closes) }, missing: [] };
  };

  const tooFew = (count: bigint): string => {
    if (count === 0n) {
      return "No stock could be judged by its daily moves; everything is held as cash until one can.";
    }
    const judged =
      count === 1n ? "stock could be judged by its" : "stocks could be judged by their";
    return `Only ${count.toString()} ${judged} daily moves; the rest is held as cash until more can.`;
  };

  const review = (view: MarketView, portfolio: PortfolioView, memory: Memory): StrategyDecision => {
    const { members, buyable } = view.tradable;
    const reachable = [...new Set([...buyable, ...portfolio.holdings.keys()])]
      .filter((symbol) => members.has(symbol))
      .sort();
    const ranked: Judged[] = [];
    const ineligible = new Map<string, Ineligible>();
    const missing: Note[] = [];
    for (const symbol of reachable) {
      const { judged, missing: gaps } = judge(view, symbol);
      missing.push(...gaps);
      if (judged === "not trading" || judged === "too few closes") {
        ineligible.set(symbol, judged);
      } else if (judged !== null) {
        ranked.push(judged);
      }
    }
    if (missing.length > 0) {
      return { weights: new Map(), reasons: new Map(), missing, memory, notes: [] };
    }
    // Calmest first; `ranked` is in symbol order and the sort is stable, so a tie keeps it.
    ranked.sort((one, other) => one.variance.comparedTo(other.variance));
    const picked: Judged[] = [];
    for (const stock of ranked) {
      if (BigInt(picked.length) < volatilityStocks) {
        picked.push(stock);
      }
    }
    const weights = new Map<string, Decimal>();
    const reasons = new Map<string, string>();
    for (const symbol of portfolio.holdings.keys()) {
      reasons.set(symbol, `${NAME}: no longer in the universe`);
    }
    const startDay = monthsBefore(view.day, volatilityMonths);
    for (const [symbol, why] of ineligible) {
      reasons.set(
        symbol,
        why === "not trading"
          ? `${NAME}: not judged, it had not started trading by ${startDay}`
          : `${NAME}: not judged, it traded on too few days since ${startDay}`,
      );
    }
    for (const stock of ranked) {
      reasons.set(stock.symbol, `${NAME}: not among ${calmest}`);
    }
    for (const stock of picked) {
      weights.set(stock.symbol, target);
      reasons.set(stock.symbol, `${NAME}: among ${calmest}`);
    }
    const count = BigInt(picked.length);
    const notes =
      count < volatilityStocks ? [note(NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED, tooFew(count))] : [];
    const remembered = new Map([
      [SET, writeSet(picked.map((stock) => stock.symbol))],
      [MONTH, view.day.slice(0, 7)],
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
      throw new Error(`${NAME}'s memory has a month but no set`);
    }
    const picks = readSet(set, NAME);
    const { weights, reasons } = keepAndTopUp(NAME, view, portfolio, picks, target);
    return { weights, reasons, missing: [], memory, notes: [] };
  };

  return {
    name: NAME,
    volatilityStocks,
    volatilityMonths,
    decide(view, portfolio, memory) {
      return memory.get(MONTH) === view.day.slice(0, 7)
        ? between(view, portfolio, memory)
        : review(view, portfolio, memory);
    },
  };
};
