/** Advice for an advice day: a strategy's weights sized, checked and priced (spec §4.4, §4.5).
 *
 * Each order's limit is the advice day's close, it carries its estimated fees and the strategy's
 * reason, and the stamp duty is charged once on the day's orders together, as Python charges it.
 * A strategy that lacks data for any stock it must judge gives no orders at all and lists every
 * gap, never advice on partial data. */

import type Decimal from "decimal.js";
import type { Day, Portfolio, Watchlist } from "./broker-view.ts";
import { Side, type Costs } from "./costs.ts";
import { Money } from "./money.ts";
import { RuleDecimal } from "./ratio.ts";
import type { Note } from "./notes.ts";
import { checkOrders, type Cut, type Rejected, type RiskLimits } from "./risk.ts";
import type { IdxMarketRules } from "./rules.ts";
import { priceOf, sizeOrders, type HeldView, type Order } from "./sizing.ts";
import type { Tradable } from "./tradable.ts";

/** A strategy's answer for one advice day. A stock missing from `weights` is targeted at zero;
 * `reasons` says why, for every stock it orders; `missing` lists every gap in its data. */
export interface Decision {
  readonly weights: ReadonlyMap<string, Decimal>;
  readonly reasons: ReadonlyMap<string, string>;
  readonly missing: readonly Note[];
}

export interface AdvisedOrder {
  readonly order: Order;
  /** The advice day's close. */
  readonly limitPrice: Money;
  /** The trade's costs at the limit, an estimate (spec §4.2). */
  readonly costs: Costs;
  readonly reason: string;
}

export interface Advice {
  readonly day: Day;
  readonly orders: readonly AdvisedOrder[];
  readonly rejected: readonly Rejected[];
  readonly cuts: readonly Cut[];
  /** Charged once on the day's orders together. */
  readonly stampDuty: Money;
  readonly missing: readonly Note[];
  /** What stopped every buy: the halt in force and each fact a halt needs that is missing
   * (spec §8). Empty when buys may be given. */
  readonly stops: readonly Note[];
}

export interface AdviceInputs {
  readonly rules: IdxMarketRules;
  readonly limits: RiskLimits;
  /** `buyStops` of the risk state: while any is listed, every buy is rejected with the first,
   * and sells are still given. */
  readonly stops: readonly Note[];
  readonly decision: Decision;
  readonly portfolio: HeldView;
  readonly tradable: Tradable;
  /** The advice day's close of every stock weighted or held. */
  readonly prices: ReadonlyMap<string, Money>;
  readonly day: Day;
}

/** Refuse weights that cannot be a portfolio, as Python's `Decision` does: each finite and not
 * negative, together at most 1 (the rest is held as cash). */
const checkWeights = (weights: ReadonlyMap<string, Decimal>): void => {
  let total = new RuleDecimal(0);
  for (const [symbol, weight] of weights) {
    if (!weight.isFinite() || weight.isNegative()) {
      throw new RangeError(
        `${symbol}: a weight must be finite and not negative, got ${weight.toString()}`,
      );
    }
    total = total.plus(weight);
  }
  if (total.gt(1)) {
    throw new RangeError(`weights sum to ${total.toString()}, more than 1`);
  }
};

export const advise = (inputs: AdviceInputs): Advice => {
  const { rules, decision, portfolio, prices, day, stops } = inputs;
  const nothing = Money.zero(portfolio.value.currency);
  if (decision.missing.length > 0) {
    return {
      day,
      orders: [],
      rejected: [],
      cuts: [],
      stampDuty: nothing,
      missing: decision.missing,
      stops,
    };
  }
  checkWeights(decision.weights);
  const sized = sizeOrders(rules, decision.weights, portfolio, portfolio.held, prices, day);
  const [stop] = stops;
  const stopped: Rejected[] = [];
  const allowed: Order[] = [];
  for (const order of sized) {
    if (stop !== undefined && order.side === Side.BUY) {
      stopped.push({ order, reason: stop });
    } else {
      allowed.push(order);
    }
  }
  const checked = checkOrders(rules, inputs.limits, allowed, portfolio, inputs.tradable, prices);
  let traded = nothing;
  const orders = checked.orders.map((order): AdvisedOrder => {
    const reason = decision.reasons.get(order.symbol);
    if (reason === undefined) {
      throw new Error(`the strategy gave no reason for its order in ${order.symbol}`);
    }
    const limitPrice = priceOf(prices, order.symbol, day);
    const gross = limitPrice.times(order.quantity);
    traded = traded.plus(gross);
    return { order, limitPrice, costs: rules.costs(order.side, gross, day), reason };
  });
  const stampDuty = orders.length === 0 ? nothing : rules.dailyCosts(traded, day);
  const rejected = [...checked.rejected, ...stopped];
  return { day, orders, rejected, cuts: checked.cuts, stampDuty, missing: [], stops };
};

/** The advice day's close of each holding and each watched stock: its last price on pages read
 * after the close (spec §4.3). A stock whose two pages disagree is refused by name. */
export const closesFrom = (
  portfolio: Portfolio,
  watchlist: Watchlist,
): ReadonlyMap<string, Money> => {
  const closes = new Map<string, Money>();
  for (const holding of portfolio.holdings) {
    closes.set(holding.symbol, holding.lastPrice);
  }
  const watchedSymbols = new Set<string>();
  for (const watched of watchlist.stocks) {
    if (watchedSymbols.has(watched.symbol)) {
      throw new Error(`the watchlist lists ${watched.symbol} twice`);
    }
    watchedSymbols.add(watched.symbol);
    const held = closes.get(watched.symbol);
    if (held !== undefined && !held.equals(watched.lastPrice)) {
      throw new Error(
        `${watched.symbol}'s last price is ${held.toString()} on the portfolio and ` +
          `${watched.lastPrice.toString()} on the watchlist`,
      );
    }
    closes.set(watched.symbol, watched.lastPrice);
  }
  return closes;
};
