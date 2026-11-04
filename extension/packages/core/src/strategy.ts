/** The strategy protocol (spec §4.3, §7), ported from Python's `strategies.protocol`: a strategy
 * says what share of the portfolio each stock should be, never orders. The sizer and the risk
 * manager turn weights into legal orders, so every rule about lots, cash and caps stays in one
 * place. */

import type Decimal from "decimal.js";
import type { Day, Dividends, Split, Watchlist } from "./broker-view.ts";
import type { Decision } from "./advice.ts";
import type { IdxCalendar } from "./calendar.ts";
import type { Money } from "./money.ts";
import { missingPage, type Note } from "./notes.ts";
import { ratioDown, rupiahUp, RuleDecimal } from "./ratio.ts";
import type { StockSeries } from "./series.ts";
import type { PortfolioView } from "./sizing.ts";
import type { Tradable } from "./tradable.ts";

/** What a strategy keeps from one advice day to the next, as text, as Python's `Memory`. */
export type Memory = ReadonlyMap<string, string>;

/** The market as a strategy sees it on its advice day. */
export interface MarketView {
  readonly day: Day;
  readonly tradable: Tradable;
  /** Each stock's close on the advice day, from the watchlist and portfolio reads. */
  readonly closes: ReadonlyMap<string, Money>;
  /** Each stock's dividend read, by symbol: its rows and the period it covers (spec §7.1). A
   * stock with no read is absent. */
  readonly dividends: ReadonlyMap<string, Dividends>;
  /** Every split a page has shown, to restate dividends in today's shares (spec §6.6). */
  readonly splits: readonly Split[];
  /** Each stock's last corporate action found by price with no known ratio, by symbol: the day of
   * the first close after it (spec §6.4, `lastUnknownAction`). A dividend figure crossing it is
   * missing (§6.6). A stock with none is absent. */
  readonly unknownActions: ReadonlyMap<string, Day>;
  /** Each stock's price series in today's shares (spec §6.3), by symbol, for the strategies that
   * judge total return (§6.5). A stock with no chart and no recorded closes is absent. */
  readonly series: ReadonlyMap<string, StockSeries>;
  /** The IDX trading days, to find where a window of trading days starts (spec §7.1). */
  readonly calendar: IdxCalendar;
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

/** Each of `buying` at its weight after the portfolio's spendable cash is shared out by
 * water-filling, as Python's `strategies._top_up.top_up` (#486). The stocks with the least room
 * below `target` are filled first, ties by symbol. Each is offered an equal part of the cash still
 * unspent, rounded down to the rupiah, and takes no more than its room, so what one stock cannot
 * take goes to the rest, and cash stays idle only when every stock is at `target`. A stock filled
 * to its room uses the rupiah that room needs, rounded up, so no rupiah is offered twice. */
export const topUp = (
  portfolio: PortfolioView,
  buying: readonly string[],
  target: Decimal,
): Map<string, Decimal> => {
  const order = [...buying]
    .sort()
    .map((symbol) => {
      const held = weightOf(portfolio, symbol);
      return { symbol, held, room: RuleDecimal.max(new RuleDecimal(target).minus(held), 0) };
    })
    .sort((first, second) => first.room.comparedTo(second.room));
  const value = portfolio.value.amount;
  const weights = new Map<string, Decimal>();
  let unspent = portfolio.spendable.amount;
  let left = BigInt(order.length);
  for (const { symbol, held, room } of order) {
    const offered = unspent / left;
    const share = ratioDown(offered, value);
    if (share.lessThanOrEqualTo(room)) {
      weights.set(symbol, plus(held, share));
      unspent -= offered;
    } else {
      weights.set(symbol, plus(held, room));
      unspent -= rupiahUp(room, value);
    }
    left -= 1n;
  }
  return weights;
};

/** Between reviews, as Python's reviewing strategies do: every holding keeps its weight, and new
 * cash goes to the picks it can buy, each topped up to no more than `target` (`topUp`). */
export const keepAndTopUp = (
  strategy: string,
  view: MarketView,
  portfolio: PortfolioView,
  picks: readonly string[],
  target: Decimal,
): { readonly weights: Map<string, Decimal>; readonly reasons: Map<string, string> } => {
  const weights = new Map<string, Decimal>();
  const reasons = new Map<string, string>();
  for (const symbol of portfolio.holdings.keys()) {
    weights.set(symbol, weightOf(portfolio, symbol));
    reasons.set(symbol, `${strategy}: held until the next review`);
  }
  const buying = picks.filter((symbol) => view.tradable.buyable.has(symbol));
  for (const [symbol, weight] of topUp(portfolio, buying, target)) {
    weights.set(symbol, weight);
    reasons.set(symbol, `${strategy}: picked at the last review, topped up to its share`);
  }
  return { weights, reasons };
};

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
