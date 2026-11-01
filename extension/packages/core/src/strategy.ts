/** The strategy protocol (spec §4.3, §7), ported from Python's `strategies.protocol`: a strategy
 * says what share of the portfolio each stock should be, never orders. The sizer and the risk
 * manager turn weights into legal orders, so every rule about lots, cash and caps stays in one
 * place. */

import type Decimal from "decimal.js";
import type { Day, Watchlist } from "./broker-view.ts";
import type { Decision } from "./advice.ts";
import { missingPage, type Note } from "./notes.ts";
import { ratioDown, RuleDecimal } from "./ratio.ts";
import type { PortfolioView } from "./sizing.ts";
import type { Tradable } from "./tradable.ts";

/** What a strategy keeps from one advice day to the next, as text, as Python's `Memory`. */
export type Memory = ReadonlyMap<string, string>;

/** The market as a strategy sees it on its advice day. Strategies that read prices or
 * dividends add them in their own stories (EXT S7b, S8b). */
export interface MarketView {
  readonly day: Day;
  readonly tradable: Tradable;
}

/** A strategy's answer for one advice day: advice's `Decision`, what to remember until the next
 * advice day, and anything it says about the day. */
export interface StrategyDecision extends Decision {
  readonly memory: Memory;
  readonly notes: readonly Note[];
}

export interface Strategy {
  /** The name Settings and the guide use, such as `buy-and-hold`. */
  readonly name: string;
  decide(view: MarketView, portfolio: PortfolioView, memory: Memory): StrategyDecision;
}

/** `symbol`'s share of the portfolio's value, rounded down so weights never sum above 1, as
 * Python's `PortfolioView.weight`. */
export const weightOf = (portfolio: PortfolioView, symbol: string): Decimal => {
  const held = portfolio.holdings.get(symbol);
  return held === undefined ? new RuleDecimal(0) : ratioDown(held.amount, portfolio.value.amount);
};

/** `weight` plus `more`, at Python's default context (28 digits, half-even). */
export const plus = (weight: Decimal | undefined, more: Decimal): Decimal =>
  new RuleDecimal(weight ?? 0).plus(more);

/** A set of stocks as a strategy remembers it, as Python's `write_set`: `IDX:SYMBOL` entries in
 * order, separated by spaces, so the same set is always the same text. */
export const writeSet = (symbols: Iterable<string>): string =>
  [...symbols]
    .map((symbol) => `IDX:${symbol}`)
    .sort()
    .join(" ");

/** The symbols of a set `strategy` remembered; an entry of any other market is refused. */
export const readSet = (text: string, strategy: string): string[] =>
  text
    .split(" ")
    .filter((entry) => entry !== "")
    .map((entry) => {
      if (!entry.startsWith("IDX:")) {
        throw new Error(`${strategy}'s memory names ${entry}, not a stock of IDX`);
      }
      return entry.slice("IDX:".length);
    });

/** The universe a strategy judges (decision 9): the stocks Settings lists, each of which must be
 * in the watchlist read, since that read gives its close. A stock Settings excludes is not
 * judged, so it needs no read; a listed stock missing from the watchlist is a gap, named. Stocks
 * the broker flags stay members and are kept out of trading by the tradable set. */
export const universeOf = (
  listed: readonly string[],
  excluded: ReadonlySet<string>,
  watchlist: Watchlist,
): { readonly members: ReadonlySet<string>; readonly missing: readonly Note[] } => {
  const read = new Set(watchlist.stocks.map((stock) => stock.symbol));
  const judged = listed.filter((symbol) => !excluded.has(symbol));
  return {
    members: new Set(judged.filter((symbol) => read.has(symbol))),
    missing: judged
      .filter((symbol) => !read.has(symbol))
      .map((symbol) => missingPage("watchlist", symbol)),
  };
};

/** A strategy's memory as stored: the advice day it was written for, the memory that day began
 * with, and the memory it ended with (spec §4.3). */
export interface StoredMemory {
  readonly day: Day;
  readonly began: Memory;
  readonly ended: Memory;
}

/** The memory to advise on `day` with: the memory `day` began with when it was advised before,
 * so the advice for a day is the same however often it is asked for; else the last day's end. */
export const memoryFor = (stored: StoredMemory | undefined, day: Day): Memory => {
  if (stored === undefined) {
    return new Map();
  }
  if (day < stored.day) {
    throw new RangeError(`strategy memory is for ${stored.day}, later than the advice day ${day}`);
  }
  return day === stored.day ? stored.began : stored.ended;
};

/** What to store after advising on `day` from `began`, ending with `ended`. */
export const storedAfter = (day: Day, began: Memory, ended: Memory): StoredMemory => ({
  day,
  began,
  ended,
});
