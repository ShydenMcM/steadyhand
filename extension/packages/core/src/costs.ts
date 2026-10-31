/**
 * Which way a trade goes, and what it costs on top of its gross value, ported from Python's
 * `steadyhand.types.Side` and `Costs`.
 */
import { CurrencyMismatchError, Money, type Currency } from "./money.ts";

export const Side = {
  BUY: "buy",
  SELL: "sell",
} as const;
export type Side = (typeof Side)[keyof typeof Side];

/** What one trade costs on top of its gross value: broker fee, exchange levy, sell tax.
 *
 * `estimate` marks a fee worked out from a broker preset, which the panel labels as an estimate
 * (spec §4.2): the broker's own confirmation is the real figure. */
export class Costs {
  constructor(
    readonly fee: Money,
    readonly levy: Money,
    readonly tax: Money,
    readonly estimate = false,
  ) {
    for (const [name, part] of [
      ["fee", fee],
      ["levy", levy],
      ["tax", tax],
    ] as const) {
      if (!part.currency.equals(fee.currency)) {
        throw new CurrencyMismatchError(fee.currency, part.currency);
      }
      if (part.amount < 0n) {
        throw new RangeError(`${name} cannot be negative, got ${part.toString()}`);
      }
    }
  }

  static zero(currency: Currency): Costs {
    const nothing = Money.zero(currency);
    return new Costs(nothing, nothing, nothing);
  }

  get total(): Money {
    return this.fee.plus(this.levy).plus(this.tax);
  }
}
