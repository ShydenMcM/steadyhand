/** Sizing: target weights to orders of whole lots (spec §4.4), ported from Python's
 * `CompoundingSizer`.
 *
 * The sizer only does the arithmetic. Every limit that can drop or cut an order, cash included,
 * is the risk manager's, so each carries its note in one place. */

import type Decimal from "decimal.js";
import type { Day, Portfolio } from "./broker-view.ts";
import { Side } from "./costs.ts";
import { Money, Rounding } from "./money.ts";
import { MARKET, type IdxMarketRules, type Instrument } from "./rules.ts";

/** An order of `quantity` shares (whole lots), placed on the advice day `day`. */
export interface Order {
  readonly symbol: string;
  readonly side: Side;
  readonly quantity: bigint;
  readonly day: Day;
}

/** The portfolio as sizing and risk see it, as Python's `PortfolioView`. */
export interface PortfolioView {
  /** All cash plus every holding at the advice day's close. */
  readonly value: Money;
  /** What may be spent on buys now. */
  readonly spendable: Money;
  /** Each holding's worth at the advice day's close. */
  readonly holdings: ReadonlyMap<string, Money>;
}

/** A portfolio view with the shares of each holding. */
export interface HeldView extends PortfolioView {
  readonly held: ReadonlyMap<string, bigint>;
}

export const instrument = (symbol: string, rules: IdxMarketRules): Instrument => ({
  symbol,
  market: MARKET,
  currency: rules.currency,
});

/** The broker's portfolio as sizing sees it. Cash is the settled balance plus the unsettled one,
 * which is signed (a buy not yet settled lowers it); what may be spent is the broker's cash
 * available to buy. */
export const portfolioView = (rules: IdxMarketRules, portfolio: Portfolio, day: Day): HeldView => {
  const holdings = new Map<string, Money>();
  const held = new Map<string, bigint>();
  let value = portfolio.cashSettled.plus(portfolio.cashUnsettled);
  for (const holding of portfolio.holdings) {
    if (held.has(holding.symbol)) {
      throw new Error(`the portfolio lists ${holding.symbol} twice`);
    }
    const shares = holding.lots * rules.lotSize(instrument(holding.symbol, rules), day);
    const worth = holding.lastPrice.times(shares);
    held.set(holding.symbol, shares);
    holdings.set(holding.symbol, worth);
    value = value.plus(worth);
  }
  return { value, spendable: portfolio.cashAvailable, holdings, held };
};

/** The last close of `symbol` in `prices`, refused by name when there is none. */
export const priceOf = (prices: ReadonlyMap<string, Money>, symbol: string, day: Day): Money => {
  const price = prices.get(symbol);
  if (price === undefined) {
    throw new Error(`no price for ${symbol} on ${day} to size it with`);
  }
  return price;
};

const absolute = (amount: bigint): bigint => (amount < 0n ? -amount : amount);

const lesser = (first: bigint, second: bigint): bigint => (first < second ? first : second);

/** Orders placed on `day`: every sell first, then every buy, each by symbol.
 *
 * Each stock's target is its weight times the value. The difference from what is held becomes
 * whole lots at the last close, rounded towards zero, so a target within a lot of the holding
 * places no order. A stock missing from `weights` is targeted at zero. `held` is the shares of
 * each holding and `prices` the last close of every stock weighted or held. */
export const sizeOrders = (
  rules: IdxMarketRules,
  weights: ReadonlyMap<string, Decimal>,
  portfolio: PortfolioView,
  held: ReadonlyMap<string, bigint>,
  prices: ReadonlyMap<string, Money>,
  day: Day,
): readonly Order[] => {
  const sells: Order[] = [];
  const buys: Order[] = [];
  const symbols = [...new Set([...weights.keys(), ...held.keys()])].sort();
  for (const symbol of symbols) {
    const price = priceOf(prices, symbol, day);
    const weight = weights.get(symbol);
    const target =
      weight === undefined
        ? Money.zero(portfolio.value.currency)
        : portfolio.value.timesRate(weight, Rounding.DOWN);
    const current = portfolio.holdings.get(symbol) ?? Money.zero(portfolio.value.currency);
    const lot = rules.lotSize(instrument(symbol, rules), day);
    const lots = absolute(target.minus(current).amount) / price.times(lot).amount;
    if (target.lt(current)) {
      const quantity = lesser(lots * lot, ((held.get(symbol) ?? 0n) / lot) * lot);
      if (quantity > 0n) {
        sells.push({ symbol, side: Side.SELL, quantity, day });
      }
    } else if (lots > 0n) {
      buys.push({ symbol, side: Side.BUY, quantity: lots * lot, day });
    }
  }
  return [...sells, ...buys];
};
