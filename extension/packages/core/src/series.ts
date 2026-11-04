/** A stock's series (spec §6.3): the daily closes a strategy reads for one stock, in today's
 * shares.
 *
 * The latest chart read wins on every day it holds; the self-recorded closes after its last day
 * follow. An adjusted chart legitimately differs from raw closes before its latest action, so
 * only its last day is compared: its close must equal the self-recorded close for that day, if
 * there is one. A disagreement drops the self-recorded part and asks for the chart again. A
 * corporate action found by price between self-recorded closes (§6.4) drops everything before it,
 * the chart included, and asks for the chart once. Closes not yet adjusted for a known split
 * after them are restated into today's shares, so the series has one share basis throughout. */

import type Decimal from "decimal.js";
import { actionBetween } from "./actions.ts";
import type { Covered, DailyClose, Day, Split } from "./broker-view.ts";
import type { IdxCalendar } from "./calendar.ts";
import { Money } from "./money.ts";
import { missingPage, type Note } from "./notes.ts";
import { RuleDecimal } from "./ratio.ts";
import type { IdxMarketRules } from "./rules.ts";

/** How a broker's chart series is adjusted, as its reader declares (spec §5.2). */
export type Adjustment = "none" | "splits" | "splits-and-dividends";

export interface ChartRead {
  readonly adjustment: Adjustment;
  /** The days the chart's range spans: a stock with no close in part of it was not trading then. */
  readonly covered: Covered;
  /** In day order, as the chart shows them. */
  readonly closes: readonly DailyClose[];
}

/** A close in today's shares: exact rupiah, which a split restatement can make a fraction of. */
export interface SeriesClose {
  readonly day: Day;
  readonly close: Decimal;
}

export interface StockSeries {
  /** In day order. */
  readonly closes: readonly SeriesClose[];
  /** The range of the chart read the closes start with, or `null` with none: no chart was read,
   * or a corporate action found by price after it dropped it. */
  readonly covered: Covered | null;
  /** The last day the closes are already adjusted for dividends to (a `splits-and-dividends`
   * chart's last day), or `null`: total return adjusts only for dividends after it. */
  readonly dividendsAdjustedTo: Day | null;
  readonly missing: readonly Note[];
}

export interface SeriesInputs {
  readonly symbol: string;
  readonly chart: ChartRead | undefined;
  /** The closes self-recorded from portfolio and watchlist reads (spec §6.2), in day order. */
  readonly recorded: readonly DailyClose[];
  /** Every split of the stock a page has shown. */
  readonly splits: readonly Split[];
}

/** `daily` in the shares after every split later than its day, but for those on or before
 * `adjustedTo`, which the chart it came from already shows adjusted. */
const inTodaysShares = (
  daily: DailyClose,
  splits: readonly Split[],
  adjustedTo: Day | null,
): SeriesClose => {
  let close = new RuleDecimal(daily.close.amount.toString());
  for (const split of splits) {
    const later = daily.day < split.exDate;
    const shown = adjustedTo !== null && split.exDate <= adjustedTo;
    if (later && !shown) {
      close = close.times(split.from.toString()).div(split.to.toString());
    }
  }
  return { day: daily.day, close };
};

/** The chart's closes in today's shares. */
const chartCloses = (chart: ChartRead, last: DailyClose, splits: readonly Split[]) =>
  chart.closes.map((daily) =>
    inTodaysShares(daily, splits, chart.adjustment === "none" ? null : last.day),
  );

/** `earlier` in the shares of `later`'s day, by every known split between them, rounded down to
 * whole rupiah: a known split is not a move, so only the market's part is checked. */
const acrossSplits = (
  earlier: DailyClose,
  later: DailyClose,
  splits: readonly Split[],
): DailyClose => {
  let amount = earlier.close.amount;
  for (const split of splits) {
    if (earlier.day < split.exDate && split.exDate <= later.day) {
      amount = (amount * split.from) / split.to;
    }
  }
  return { day: earlier.day, close: new Money(amount, earlier.close.currency) };
};

/** The self-recorded closes from the last corporate action found by price on, and that action's
 * day: the day of the first close after it, or `undefined` when none was found. */
const sinceLastAction = (
  symbol: string,
  recorded: readonly DailyClose[],
  splits: readonly Split[],
  rules: IdxMarketRules,
  calendar: IdxCalendar,
): { readonly closes: readonly DailyClose[]; readonly found: Day | undefined } => {
  let since: DailyClose[] = [];
  let found: Day | undefined;
  let previous: DailyClose | undefined;
  for (const daily of recorded) {
    if (
      previous !== undefined &&
      actionBetween(symbol, acrossSplits(previous, daily, splits), daily, rules, calendar)
    ) {
      since = [];
      found = daily.day;
    }
    since.push(daily);
    previous = daily;
  }
  return { closes: since, found };
};

/** The day of the last corporate action found by price (spec §6.4) in `symbol`'s self-recorded
 * closes that neither a known split explains nor a corporate action read settles, dated by the
 * first close after it, or `undefined`. A read whose period covers the closes either side of the
 * action settles it whatever it shows: the page lists every stock's splits, so none there means
 * no share change (#480 AC5). A dividend figure crossing an unsettled one cannot be restated in
 * today's shares (§6.6). */
export const lastUnknownAction = (
  symbol: string,
  recorded: readonly DailyClose[],
  splits: readonly Split[],
  actionReads: readonly Covered[],
  rules: IdxMarketRules,
  calendar: IdxCalendar,
): Day | undefined => {
  let found: Day | undefined;
  let previous: DailyClose | undefined;
  for (const daily of recorded) {
    if (
      previous !== undefined &&
      actionBetween(symbol, acrossSplits(previous, daily, splits), daily, rules, calendar)
    ) {
      const before = previous.day;
      const settled = actionReads.some((read) => read.from <= before && daily.day <= read.to);
      if (!settled) {
        found = daily.day;
      }
    }
    previous = daily;
  }
  return found;
};

export const stockSeries = (
  inputs: SeriesInputs,
  rules: IdxMarketRules,
  calendar: IdxCalendar,
): StockSeries => {
  const { symbol, chart, splits } = inputs;
  const last = chart?.closes.at(-1);
  if (chart === undefined || last === undefined) {
    const own = sinceLastAction(symbol, inputs.recorded, splits, rules, calendar);
    return {
      closes: own.closes.map((daily) => inTodaysShares(daily, splits, null)),
      covered: chart?.covered ?? null,
      dividendsAdjustedTo: null,
      missing: own.found !== undefined ? [missingPage("stock-detail", symbol)] : [],
    };
  }
  const dividendsAdjustedTo = chart.adjustment === "splits-and-dividends" ? last.day : null;
  const after = inputs.recorded.filter((daily) => daily.day >= last.day);
  const same = after.find((daily) => daily.day === last.day);
  if (same !== undefined && !same.close.equals(last.close)) {
    return {
      closes: chartCloses(chart, last, splits),
      covered: chart.covered,
      dividendsAdjustedTo,
      missing: [missingPage("stock-detail", symbol)],
    };
  }
  const own = sinceLastAction(symbol, after, splits, rules, calendar);
  if (own.found !== undefined) {
    return {
      closes: own.closes.map((daily) => inTodaysShares(daily, splits, null)),
      covered: null,
      dividendsAdjustedTo: null,
      missing: [missingPage("stock-detail", symbol)],
    };
  }
  return {
    closes: [
      ...chartCloses(chart, last, splits),
      ...own.closes
        .filter((daily) => daily.day > last.day)
        .map((daily) => inTodaysShares(daily, splits, null)),
    ],
    covered: chart.covered,
    dividendsAdjustedTo,
    missing: [],
  };
};

/** How far `series`'s chart read reaches back towards `start`, a window's first day (spec §7.1,
 * M7 decision 4): `missing` when there is no series or chart range, or its range starts after
 * `start`, so the facts are unread; `ineligible` when its range reaches `start` but its first
 * close comes after it, so the stock was not trading then; else `covers`. */
export const chartReach = (
  series: StockSeries | undefined,
  start: Day,
): "missing" | "ineligible" | "covers" => {
  if (series === undefined || series.covered === null || series.covered.from > start) {
    return "missing";
  }
  const first = series.closes[0];
  return first === undefined || first.day > start ? "ineligible" : "covers";
};
