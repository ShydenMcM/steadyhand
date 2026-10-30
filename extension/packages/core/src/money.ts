/**
 * Money in integer minor units, with explicit rounding (spec §4.1), ported from Python's
 * `steadyhand.money`. A `number` never holds money: it cannot hold most decimal amounts exactly,
 * and a figure that drifts by a rupiah a day is wrong.
 */
import Decimal from "decimal.js";

/** The most decimal places a currency's minor unit may have. */
export const MAX_MINOR_UNITS = 4n;

const CURRENCY_CODE = /^[A-Z]{3}$/u;

/** Two amounts in different currencies were combined or compared. */
export class CurrencyMismatchError extends Error {
  constructor(left: Currency, right: Currency) {
    super(`cannot combine ${left.code} with ${right.code}`);
    this.name = "CurrencyMismatchError";
  }
}

/** An ISO 4217 currency and the number of decimal places in its minor unit. */
export class Currency {
  readonly code: string;
  readonly minorUnits: bigint;

  constructor(code: string, minorUnits: bigint) {
    if (typeof code !== "string") {
      throw new TypeError(`currency code must be a string, got ${typeof code}`);
    }
    if (!CURRENCY_CODE.test(code)) {
      throw new RangeError(
        `currency code must be three capital letters, got ${JSON.stringify(code)}`,
      );
    }
    if (typeof minorUnits !== "bigint" || minorUnits < 0n || minorUnits > MAX_MINOR_UNITS) {
      throw new RangeError(
        `minorUnits must be a bigint from 0 to ${String(MAX_MINOR_UNITS)}, got ${String(minorUnits)}`,
      );
    }
    this.code = code;
    this.minorUnits = minorUnits;
  }

  equals(other: Currency): boolean {
    return this.code === other.code && this.minorUnits === other.minorUnits;
  }
}

/** Indonesian rupiah. It has no minor unit in practical use, so one unit is one rupiah. */
export const IDR = new Currency("IDR", 0n);

/** Which way a rate calculation rounds to a whole minor unit. */
export const Rounding = {
  /** Towards positive infinity. Use it for what you pay: costs and buy prices. */
  UP: "up",
  /** Towards negative infinity. Use it for what you receive: proceeds and dividends. */
  DOWN: "down",
} as const;
export type Rounding = (typeof Rounding)[keyof typeof Rounding];

/** `numerator / denominator` (denominator positive), rounded the way `rounding` says. */
const divide = (numerator: bigint, denominator: bigint, rounding: Rounding): bigint => {
  const quotient = numerator / denominator;
  if (numerator % denominator === 0n) {
    return quotient;
  }
  // BigInt division truncates towards zero, which is down for a positive result, up for a negative.
  const positive = numerator > 0n;
  if (rounding === Rounding.UP) {
    return positive ? quotient + 1n : quotient;
  }
  return positive ? quotient : quotient - 1n;
};

/** An exact amount: a `bigint` of minor units plus its currency. */
export class Money {
  readonly amount: bigint;
  readonly currency: Currency;

  constructor(amount: bigint, currency: Currency) {
    if (typeof amount !== "bigint") {
      throw new TypeError(`Money amount must be a bigint of minor units, got ${typeof amount}`);
    }
    if (!(currency instanceof Currency)) {
      throw new TypeError(`Money currency must be a Currency, got ${typeof currency}`);
    }
    this.amount = amount;
    this.currency = currency;
  }

  static zero(currency: Currency): Money {
    return new Money(0n, currency);
  }

  /** The other operand's amount, once it is known to be Money in this currency. */
  private same(other: Money, operation: string): bigint {
    if (!(other instanceof Money)) {
      throw new TypeError(`${operation} needs Money, got ${typeof other}`);
    }
    if (!other.currency.equals(this.currency)) {
      throw new CurrencyMismatchError(this.currency, other.currency);
    }
    return other.amount;
  }

  equals(other: Money): boolean {
    return this.amount === other.amount && this.currency.equals(other.currency);
  }

  plus(other: Money): Money {
    return new Money(this.amount + this.same(other, "plus"), this.currency);
  }

  minus(other: Money): Money {
    return new Money(this.amount - this.same(other, "minus"), this.currency);
  }

  negated(): Money {
    return new Money(-this.amount, this.currency);
  }

  lt(other: Money): boolean {
    return this.amount < this.same(other, "lt");
  }

  le(other: Money): boolean {
    return this.amount <= this.same(other, "le");
  }

  gt(other: Money): boolean {
    return this.amount > this.same(other, "gt");
  }

  ge(other: Money): boolean {
    return this.amount >= this.same(other, "ge");
  }

  /** Multiply by a whole quantity, such as a share count. */
  times(quantity: bigint): Money {
    if (typeof quantity !== "bigint") {
      throw new TypeError(
        `multiply Money by a bigint quantity, got ${typeof quantity}; use timesRate() for a rate`,
      );
    }
    return new Money(this.amount * quantity, this.currency);
  }

  /** Multiply by `rate` exactly, then round once to a whole minor unit. */
  timesRate(rate: Decimal, rounding: Rounding): Money {
    if (!(rate instanceof Decimal)) {
      throw new TypeError(`rate must be a Decimal, got ${typeof rate}`);
    }
    if (!rate.isFinite()) {
      throw new RangeError(`rate must be finite, got ${rate.toString()}`);
    }
    // The rate's digits as a whole number over a power of ten, so the product is exact in bigint
    // and rounded once, where a Decimal context could round it twice.
    const [whole = "", fraction = ""] = rate.toFixed().split(".");
    const numerator = this.amount * BigInt(whole + fraction);
    return new Money(divide(numerator, 10n ** BigInt(fraction.length), rounding), this.currency);
  }

  toString(): string {
    const sign = this.amount < 0n ? "-" : "";
    const places = this.currency.minorUnits;
    const scale = 10n ** places;
    const magnitude = this.amount < 0n ? -this.amount : this.amount;
    const units = (magnitude / scale).toLocaleString("en-US");
    if (places === 0n) {
      return `${this.currency.code} ${sign}${units}`;
    }
    // The minor part with its leading zeros: one more digit than it has places, minus the first.
    const minor = (scale + (magnitude % scale)).toString().slice(1);
    return `${this.currency.code} ${sign}${units}.${minor}`;
  }
}
