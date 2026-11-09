/** The strategies Settings offers, each with its settings' defaults and bounds (#239 AC1).
 *
 * The bounds are Python's registry `Setting` for buy-and-hold, monthly-savings and
 * dividend-growth, and Shyden's ruling of 2026-11-06 (#239) for the three M7 strategies, which
 * Python never registered. A value outside its bounds is refused by the setting's name, as
 * Python's `Setting.check` refuses it; the rules between two settings (such as `fast_days` below
 * `slow_days`) stay with each strategy. */

import { buyAndHold } from "./buy-and-hold.ts";
import { DIVIDEND_GROWTH, dividendGrowth } from "./dividend-growth.ts";
import { HIGH_YIELD, highYield } from "./high-yield.ts";
import { MA_TREND, maTrend } from "./ma-trend.ts";
import { LOW_VOLATILITY, lowVolatility } from "./low-volatility.ts";
import { MOMENTUM_ROTATION, momentumRotation } from "./momentum-rotation.ts";
import { INSTALMENTS, monthlySavings } from "./monthly-savings.ts";
import type { Strategy } from "./strategy.ts";

/** One of a strategy's settings: a whole number, its default and bounds, and one line of help. */
export interface StrategySetting {
  readonly name: string;
  readonly default: bigint;
  readonly least: bigint;
  readonly most: bigint;
  readonly help: string;
}

/** A strategy Settings offers, and how to make it from its settings' values. */
export interface RegisteredStrategy {
  readonly name: string;
  readonly summary: string;
  readonly settings: readonly StrategySetting[];
  /** The strategy, from a value for every one of `settings`, each within its bounds. */
  make(values: ReadonlyMap<string, bigint>): Strategy;
}

const setting = (
  name: string,
  value: bigint,
  least: bigint,
  most: bigint,
  help: string,
): StrategySetting => ({
  name,
  default: value,
  least,
  most,
  help: `${help}: ${least.toString()} to ${most.toString()}.`,
});

/** The value `values` holds for `name`, which `strategyFrom` has always filled in. */
const valueOf = (values: ReadonlyMap<string, bigint>, name: string): bigint => {
  const value = values.get(name);
  if (value === undefined) {
    throw new Error(`missing the setting ${name}`);
  }
  return value;
};

const REGISTERED: readonly RegisteredStrategy[] = [
  {
    name: "dividend-growth",
    summary:
      "Holds the stocks that paid a dividend in each of the last six years and grew it, " +
      "spread across pay months, and reviews them yearly.",
    settings: [
      setting(
        "min_stocks",
        DIVIDEND_GROWTH.minStocks,
        1n,
        45n,
        "Below this many passing stocks, the rest is held as cash",
      ),
      setting(
        "max_stocks",
        DIVIDEND_GROWTH.maxStocks,
        1n,
        45n,
        "The most stocks held, and at least min_stocks",
      ),
      setting(
        "growth_years",
        DIVIDEND_GROWTH.growthYears,
        1n,
        10n,
        "The years over which dividends must have grown",
      ),
    ],
    make: (values) =>
      dividendGrowth(
        valueOf(values, "min_stocks"),
        valueOf(values, "max_stocks"),
        valueOf(values, "growth_years"),
      ),
  },
  {
    name: "buy-and-hold",
    summary: "Buys every stock it can on its first day in equal parts, then holds and reinvests.",
    settings: [],
    make: () => buyAndHold,
  },
  {
    name: "monthly-savings",
    summary:
      "Invests the starting cash in monthly instalments across every stock it can buy, " +
      "and never sells.",
    settings: [
      setting(
        "instalments",
        INSTALMENTS.default,
        INSTALMENTS.least,
        INSTALMENTS.most,
        "The months the starting cash is spread over",
      ),
    ],
    make: (values) => monthlySavings(valueOf(values, "instalments")),
  },
  {
    name: "high-yield",
    summary:
      "Holds the highest-yielding stocks that paid a dividend in each recent year, " +
      "and reviews them quarterly.",
    settings: [
      setting("yield_stocks", HIGH_YIELD.yieldStocks, 1n, 45n, "The most stocks held"),
      setting(
        "paid_years",
        HIGH_YIELD.paidYears,
        1n,
        10n,
        "The calendar years before this one in which each must have paid a dividend",
      ),
    ],
    make: (values) => highYield(valueOf(values, "yield_stocks"), valueOf(values, "paid_years")),
  },
  {
    name: "ma-trend",
    summary:
      "Holds the stocks whose short average price is above their long one, checked every day.",
    settings: [
      setting(
        "fast_days",
        MA_TREND.fastDays,
        1n,
        499n,
        "The trading days of the short average, fewer than slow_days",
      ),
      setting("slow_days", MA_TREND.slowDays, 2n, 500n, "The trading days of the long average"),
    ],
    make: (values) => maTrend(valueOf(values, "fast_days"), valueOf(values, "slow_days")),
  },
  {
    name: "momentum-rotation",
    summary: "Holds the stocks whose total return rose most over the last year, reviewed monthly.",
    settings: [
      setting("momentum_stocks", MOMENTUM_ROTATION.momentumStocks, 1n, 45n, "The most stocks held"),
      setting(
        "momentum_months",
        MOMENTUM_ROTATION.momentumMonths,
        2n,
        24n,
        "The months over which the rise is measured",
      ),
      setting(
        "skip_months",
        MOMENTUM_ROTATION.skipMonths,
        0n,
        23n,
        "The latest months left out of the rise, fewer than momentum_months",
      ),
    ],
    make: (values) =>
      momentumRotation(
        valueOf(values, "momentum_stocks"),
        valueOf(values, "momentum_months"),
        valueOf(values, "skip_months"),
      ),
  },
  {
    name: "low-volatility",
    summary:
      "Holds the stocks whose total return moved most evenly over the last year, reviewed monthly.",
    settings: [
      setting(
        "volatility_stocks",
        LOW_VOLATILITY.volatilityStocks,
        1n,
        45n,
        "The most stocks held",
      ),
      setting(
        "volatility_months",
        LOW_VOLATILITY.volatilityMonths,
        2n,
        24n,
        "The months over which the daily moves are measured",
      ),
    ],
    make: (values) =>
      lowVolatility(valueOf(values, "volatility_stocks"), valueOf(values, "volatility_months")),
  },
];

/** Every strategy Settings offers, by name; the first is the default (core §8). */
export const STRATEGIES: ReadonlyMap<string, RegisteredStrategy> = new Map(
  REGISTERED.map((entry) => [entry.name, entry]),
);

/** The strategy `name`, with `values` for the settings given and the default for the rest. A
 * strategy, a setting or a value Settings does not allow is refused by name. */
export const strategyFrom = (name: string, values: ReadonlyMap<string, bigint>): Strategy => {
  const entry = STRATEGIES.get(name);
  if (entry === undefined) {
    throw new RangeError(`no strategy is named ${name}`);
  }
  const known = new Set(entry.settings.map((each) => each.name));
  const unknown = [...values.keys()].find((given) => !known.has(given));
  if (unknown !== undefined) {
    throw new RangeError(`${name} has no setting named ${unknown}`);
  }
  const checked = new Map<string, bigint>();
  for (const each of entry.settings) {
    const value = values.get(each.name) ?? each.default;
    if (value < each.least || value > each.most) {
      throw new RangeError(
        `${each.name} must be from ${each.least.toString()} to ${each.most.toString()}, ` +
          `got ${value.toString()}`,
      );
    }
    checked.set(each.name, value);
  }
  return entry.make(checked);
};
