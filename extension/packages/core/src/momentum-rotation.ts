/** `momentum-rotation`: hold the stocks whose total return rose most over the last year, less its
 * last month (M7 decision 7), as spec §7.2 restates it. There is no Python reference.
 *
 * A stock's momentum is its total-return change (§6.5) from the close on the last trading day on
 * or before the date `momentumMonths` calendar months before the advice day, to the close on the
 * last trading day on or before the date `skipMonths` months before it. It reviews on the first
 * advice day of each calendar month, and on its first advice day. A review targets the
 * `momentumStocks` highest, ties broken by symbol (every stock is of IDX), at 1/`momentumStocks`
 * each, and sells everything else; fewer stocks to rank leave the rest in cash, with a note.
 * Between reviews it keeps its holdings and puts new cash into its picks, never above
 * 1/`momentumStocks`.
 *
 * Missing versus ineligible (spec §7.1, ruled on #490): a review judges every universe stock it can
 * buy or holds, and ranks one once its chart proves it traded at the window's start. A stock whose
 * chart reaches the start but whose first close comes after it was not trading then: it is
 * ineligible, not ranked, and the others still are. A stock with no series, a series asking for
 * its chart again, an unread dividend window or no chart reaching the start is missing: nothing
 * is ordered, and the memory is kept so the next advice day reviews again. */

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

const NAME = "momentum-rotation";
/** The memory key holding the stocks it picked. */
const SET = "set";
/** The memory key holding the month it last reviewed, as `2025-01`. */
const MONTH = "month";

/** Its settings' defaults (spec §7). */
export const MOMENTUM_ROTATION = {
  momentumStocks: 10n,
  momentumMonths: 12n,
  skipMonths: 1n,
} as const;

export interface MomentumRotation extends Strategy {
  /** The most stocks it holds, each at 1/`momentumStocks`. */
  readonly momentumStocks: bigint;
  /** How many calendar months back its window starts. */
  readonly momentumMonths: bigint;
  /** How many calendar months back its window ends; fewer than `momentumMonths`. */
  readonly skipMonths: bigint;
}

/** A stock a review ranks: its window's first and last total-return closes. */
interface Ranked {
  readonly symbol: string;
  readonly start: Decimal;
  readonly end: Decimal;
}

export const momentumRotation = (
  momentumStocks: bigint = MOMENTUM_ROTATION.momentumStocks,
  momentumMonths: bigint = MOMENTUM_ROTATION.momentumMonths,
  skipMonths: bigint = MOMENTUM_ROTATION.skipMonths,
): MomentumRotation => {
  if (momentumStocks < 1n) {
    throw new RangeError(`momentum_stocks must be at least 1, got ${momentumStocks.toString()}`);
  }
  if (skipMonths < 0n) {
    throw new RangeError(`skip_months must be at least 0, got ${skipMonths.toString()}`);
  }
  if (skipMonths >= momentumMonths) {
    throw new RangeError(
      `skip_months must be below momentum_months, got ${skipMonths.toString()} and ${momentumMonths.toString()}`,
    );
  }
  const target = ratioDown(1n, momentumStocks);
  const strongest = `the ${momentumStocks.toString()} strongest by momentum`;

  /** `symbol`'s window on `view`'s day, `ineligible`, or the gaps that keep it from being ranked. */
  const judge = (
    view: MarketView,
    symbol: string,
  ): { readonly ranked: Ranked | "ineligible" | null; readonly missing: readonly Note[] } => {
    const series = view.series.get(symbol);
    const first = series?.closes[0];
    if (series === undefined || first === undefined) {
      return { ranked: null, missing: [missingPage("stock-detail", symbol)] };
    }
    const startDay = monthsBefore(view.day, momentumMonths);
    const reach = chartReach(series, startDay);
    if (reach === "ineligible") {
      return { ranked: "ineligible", missing: [] };
    }
    const found = totalReturn(symbol, series, view.dividends.get(symbol), view.splits, view.day);
    if (found.missing.length > 0) {
      return { ranked: null, missing: found.missing };
    }
    if (reach === "missing") {
      const held = BigInt(found.closes.length);
      return {
        ranked: null,
        missing: [missingHistory(symbol, { from: first.day, to: view.day }, held)],
      };
    }
    const endDay = monthsBefore(view.day, skipMonths);
    // The chart covers the window's start, so its first close is on or before `startDay` and both
    // are set from a close; the end is on or after the start.
    let start: Decimal = new RuleDecimal(0);
    let end: Decimal = new RuleDecimal(0);
    for (const daily of found.closes) {
      if (daily.day <= startDay) {
        start = daily.close;
      }
      if (daily.day <= endDay) {
        end = daily.close;
      }
    }
    return { ranked: { symbol, start, end }, missing: [] };
  };

  const tooFew = (count: bigint): string => {
    if (count === 0n) {
      return "No stock could be ranked by momentum; everything is held as cash until one can.";
    }
    const stocks = count === 1n ? "stock" : "stocks";
    return `Only ${count.toString()} ${stocks} could be ranked by momentum; the rest is held as cash until more can.`;
  };

  const review = (view: MarketView, portfolio: PortfolioView, memory: Memory): StrategyDecision => {
    const { members, buyable } = view.tradable;
    const reachable = [...new Set([...buyable, ...portfolio.holdings.keys()])]
      .filter((symbol) => members.has(symbol))
      .sort();
    const ranked: Ranked[] = [];
    const ineligible: string[] = [];
    const missing: Note[] = [];
    for (const symbol of reachable) {
      const judged = judge(view, symbol);
      missing.push(...judged.missing);
      if (judged.ranked === "ineligible") {
        ineligible.push(symbol);
      } else if (judged.ranked !== null) {
        ranked.push(judged.ranked);
      }
    }
    if (missing.length > 0) {
      return { weights: new Map(), reasons: new Map(), missing, memory, notes: [] };
    }
    // Strongest first, compared as cross products so no division rounds; `ranked` is in symbol
    // order and the sort is stable, so a tie keeps it.
    ranked.sort((one, other) => other.end.times(one.start).comparedTo(one.end.times(other.start)));
    const picked: Ranked[] = [];
    for (const stock of ranked) {
      if (BigInt(picked.length) < momentumStocks) {
        picked.push(stock);
      }
    }
    const weights = new Map<string, Decimal>();
    const reasons = new Map<string, string>();
    for (const symbol of portfolio.holdings.keys()) {
      reasons.set(symbol, `${NAME}: no longer in the universe`);
    }
    const startDay = monthsBefore(view.day, momentumMonths);
    for (const symbol of ineligible) {
      reasons.set(symbol, `${NAME}: not ranked, it had not started trading by ${startDay}`);
    }
    for (const stock of ranked) {
      reasons.set(stock.symbol, `${NAME}: not among ${strongest}`);
    }
    for (const stock of picked) {
      weights.set(stock.symbol, target);
      reasons.set(stock.symbol, `${NAME}: among ${strongest}`);
    }
    const count = BigInt(picked.length);
    const notes =
      count < momentumStocks ? [note(NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED, tooFew(count))] : [];
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
    momentumStocks,
    momentumMonths,
    skipMonths,
    decide(view, portfolio, memory) {
      return memory.get(MONTH) === view.day.slice(0, 7)
        ? between(view, portfolio, memory)
        : review(view, portfolio, memory);
    },
  };
};
