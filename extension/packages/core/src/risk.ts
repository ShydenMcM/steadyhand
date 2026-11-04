/** Risk limits on orders and the halts they judge (spec §4.4, §8), ported from Python's
 * `RiskLimits`, `RiskManager.check`, `RiskManager.halt` and `UnitValue`. */

import Decimal from "decimal.js";
import type { Day } from "./broker-view.ts";
import { Side } from "./costs.ts";
import { Money, Rounding } from "./money.ts";
import { NOTE_CODES, note, type Note } from "./notes.ts";
import { Ratio, ratioDown, RuleDecimal } from "./ratio.ts";
import type { IdxMarketRules } from "./rules.ts";
import { instrument, priceOf, type Order, type PortfolioView } from "./sizing.ts";
import { whyNot, type Tradable } from "./tradable.ts";

/** `rate` as a percentage to two places, rounded down: how a limit is written, so a breach never
 * reads as more than it is. */
export const percent = (rate: Decimal): string =>
  `${new RuleDecimal(rate).times(100).toDecimalPlaces(2, Decimal.ROUND_FLOOR).toFixed(2)}%`;

export interface RiskLimitValues {
  /** The most one stock may be of the portfolio's value. A buy is cut to it. */
  readonly maxWeight?: Decimal;
  /** The smallest buy, in lots. A smaller buy is dropped. */
  readonly minLots?: bigint;
  /** A fall in the unit value this large in one day halts ordering. */
  readonly dailyLoss?: Decimal;
  /** A fall this far below the unit value's high-water mark halts ordering. */
  readonly maxDrawdown?: Decimal;
}

/** Every limit the risk manager applies. The defaults are core spec §6.1's. */
export class RiskLimits {
  readonly maxWeight: Decimal;
  readonly minLots: bigint;
  readonly dailyLoss: Decimal;
  readonly maxDrawdown: Decimal;

  constructor(values: RiskLimitValues = {}) {
    this.maxWeight = values.maxWeight ?? new RuleDecimal("0.10");
    this.minLots = values.minLots ?? 1n;
    this.dailyLoss = values.dailyLoss ?? new RuleDecimal("0.05");
    this.maxDrawdown = values.maxDrawdown ?? new RuleDecimal("0.25");
    for (const [name, rate] of [
      ["maxWeight", this.maxWeight],
      ["dailyLoss", this.dailyLoss],
      ["maxDrawdown", this.maxDrawdown],
    ] as const) {
      if (!rate.isFinite()) {
        throw new RangeError(`${name} must be a finite decimal, got ${rate.toString()}`);
      }
    }
    if (this.minLots < 1n) {
      throw new RangeError(`minLots must be at least 1, got ${String(this.minLots)}`);
    }
    if (this.maxWeight.lte(0) || this.maxWeight.gt(1)) {
      throw new RangeError(
        `maxWeight must be above 0 and at most 1, got ${this.maxWeight.toString()}`,
      );
    }
    for (const [name, rate] of [
      ["dailyLoss", this.dailyLoss],
      ["maxDrawdown", this.maxDrawdown],
    ] as const) {
      if (rate.lte(0) || rate.gte(1)) {
        throw new RangeError(`${name} must be above 0 and below 1, got ${rate.toString()}`);
      }
    }
  }
}

/** Ordering stopped on `day`, for `cause`, a note under the key of the limit reached. It lasts
 * until the user resumes it. */
export interface Halt {
  readonly day: Day;
  readonly cause: Note;
}

/** The portfolio as a fund: `units` outstanding, each worth `price` at the last valuation, and
 * the highest price yet. Before the first deposit there are no units and the price is 1. A
 * deposit buys units at the price, so it never looks like a gain; a withdrawal sells them. */
export class UnitValue {
  readonly units: Decimal;
  readonly price: Decimal;
  readonly highWater: Decimal;

  constructor(
    units: Decimal = new Ratio(0),
    price: Decimal = new Ratio(1),
    highWater: Decimal = new Ratio(1),
  ) {
    for (const [field, value] of [
      ["units", units],
      ["price", price],
      ["highWater", highWater],
    ] as const) {
      if (!value.isFinite()) {
        throw new RangeError(`${field} must be a finite decimal, got ${value.toString()}`);
      }
      if (value.isNegative() && !value.isZero()) {
        throw new RangeError(`${field} cannot be negative, got ${value.toString()}`);
      }
    }
    this.units = units;
    this.price = price;
    this.highWater = highWater;
  }

  /** How far the price is below the high-water mark, as a share of it. */
  get drawdown(): Decimal {
    return new RuleDecimal(1).minus(ratioDown(this.price, this.highWater));
  }

  /** The price per unit when the portfolio is worth `value`. Nothing changes before units. */
  revalue(value: Money): UnitValue {
    if (this.units.isZero()) {
      return this;
    }
    const price = ratioDown(value.amount, this.units);
    return new UnitValue(this.units, price, Decimal.max(this.highWater, price));
  }

  /** Buy units with `amount` at the current price, which the deposit leaves unchanged. A
   * negative amount is a withdrawal. */
  deposit(amount: Money): UnitValue {
    if (this.price.isZero()) {
      throw new RangeError("no units can be bought at a price of 0");
    }
    const units = new RuleDecimal(this.units).plus(ratioDown(amount.amount, this.price));
    return new UnitValue(units, this.price, this.highWater);
  }
}

/** A halt when `after` breaches a limit, reaching it included; else `null`. `before` is the unit
 * value at the previous read: the previous trading day's, or, when `since` is given, the latest
 * earlier read's, on `since`, and the note gives that span (spec §8, decision 21). */
export const haltOn = (
  limits: RiskLimits,
  before: UnitValue,
  after: UnitValue,
  day: Day,
  since?: Day,
): Halt | null => {
  if (before.units.gt(0)) {
    const fall = new RuleDecimal(1).minus(ratioDown(after.price, before.price));
    if (fall.gte(limits.dailyLoss)) {
      const where =
        since === undefined
          ? ","
          : ` from ${since} to ${day}, with no read on the trading days between;`;
      return {
        day,
        cause: note(
          NOTE_CODES.RISK_HALT_DAILY_LOSS,
          `daily loss limit: the unit value fell ${percent(fall)}${where} the limit is ` +
            percent(limits.dailyLoss),
        ),
      };
    }
  }
  const drawdown = after.drawdown;
  if (after.units.gt(0) && drawdown.gte(limits.maxDrawdown)) {
    return {
      day,
      cause: note(
        NOTE_CODES.RISK_HALT_DRAWDOWN,
        `drawdown kill switch: the unit value is ${percent(drawdown)} below its high-water ` +
          `mark, the limit is ${percent(limits.maxDrawdown)}`,
      ),
    };
  }
  return null;
};

export interface Rejected {
  readonly order: Order;
  readonly reason: Note;
}

export interface Cut {
  readonly order: Order;
  readonly quantity: bigint;
  readonly reason: Note;
}

/** Orders the risk manager passed, and those it dropped or cut, each with its reason. */
export interface Checked {
  readonly orders: readonly Order[];
  readonly rejected: readonly Rejected[];
  readonly cuts: readonly Cut[];
}

const larger = (first: bigint, second: bigint): bigint => (first > second ? first : second);

const smaller = (first: bigint, second: bigint): bigint => (first < second ? first : second);

/** What `quantity` shares bought at `price` cost on `day`, the trade's costs included. */
const cost = (rules: IdxMarketRules, quantity: bigint, price: Money, day: Day): Money => {
  const gross = price.times(quantity);
  return gross.plus(rules.costs(Side.BUY, gross, day).total);
};

/** The most of `quantity` that `budget` buys, in whole lots, costs included. */
const affordable = (
  rules: IdxMarketRules,
  lot: bigint,
  quantity: bigint,
  price: Money,
  budget: Money,
  day: Day,
): bigint => {
  let most = smaller(quantity, (larger(budget.amount, 0n) / price.times(lot).amount) * lot);
  while (most > 0n && cost(rules, most, price, day).gt(budget)) {
    most -= lot;
  }
  return most;
};

/** The lots `room` leaves for a stock already worth `held`, below the weight cap; never negative. */
const roomUnder = (cap: Money, held: Money, price: Money, lot: bigint): bigint => {
  const left = cap.minus(held).amount;
  return left <= 0n ? 0n : (left / price.times(lot).amount) * lot;
};

/** Drop or cut `orders` placed on the tradable set's day, in the order given.
 *
 * Buys are sized at the last close in `prices`, costs included, and together never spend more
 * than `portfolio.spendable`. Sale proceeds are not counted: they are not settled. */
export const checkOrders = (
  rules: IdxMarketRules,
  limits: RiskLimits,
  orders: readonly Order[],
  portfolio: PortfolioView,
  tradable: Tradable,
  prices: ReadonlyMap<string, Money>,
): Checked => {
  const day = tradable.day;
  const passed: Order[] = [];
  const rejected: Rejected[] = [];
  const cuts: Cut[] = [];
  let budget = portfolio.spendable;
  const cap = portfolio.value.timesRate(limits.maxWeight, Rounding.DOWN);
  const limit = percent(limits.maxWeight);
  for (const order of orders) {
    const kept = whyNot(tradable, order.symbol, order.side);
    if (kept !== null) {
      rejected.push({ order, reason: kept });
      continue;
    }
    if (order.side === Side.SELL) {
      passed.push(order);
      continue;
    }
    const price = priceOf(prices, order.symbol, day);
    const lot = rules.lotSize(instrument(order.symbol, rules), day);
    const held = portfolio.holdings.get(order.symbol) ?? Money.zero(price.currency);
    const quantity = smaller(order.quantity, roomUnder(cap, held, price, lot));
    if (quantity < order.quantity) {
      if (quantity === 0n) {
        const full = note(NOTE_CODES.LIMIT_WEIGHT_FULL, `already at the ${limit} limit per stock`);
        rejected.push({ order, reason: full });
        continue;
      }
      const reason = note(NOTE_CODES.LIMIT_WEIGHT_CUT, `cut to the ${limit} limit per stock`);
      cuts.push({ order, quantity, reason });
    }
    if (quantity < limits.minLots * lot) {
      const reason = note(
        NOTE_CODES.LIMIT_MIN_LOTS,
        `below the minimum buy of ${String(limits.minLots)} lot(s)`,
      );
      rejected.push({ order, reason });
      continue;
    }
    const bought = affordable(rules, lot, quantity, price, budget, day);
    if (bought === 0n) {
      const short = note(
        NOTE_CODES.LIMIT_CASH_SHORT,
        `not enough cash: ${budget.toString()} can be spent`,
      );
      rejected.push({ order, reason: short });
      continue;
    }
    if (bought < quantity) {
      const reason = note(
        NOTE_CODES.LIMIT_CASH_CUT,
        `cut to the ${budget.toString()} that can be spent`,
      );
      cuts.push({ order, quantity: bought, reason });
    }
    budget = budget.minus(cost(rules, bought, price, day));
    passed.push({ ...order, quantity: bought });
  }
  return { orders: passed, rejected, cuts };
};
