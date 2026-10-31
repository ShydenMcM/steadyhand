import Decimal from "decimal.js";
import { expect, test } from "vitest";
import { Currency, CurrencyMismatchError, IDR, Money, Rounding } from "../src/money.ts";

// Ported from Python's tests/engine/test_money.py, one test per case.

const usd = (): Currency => new Currency("USD", 2n);
const rp = (amount: bigint): Money => new Money(amount, IDR);

/** A value a JavaScript caller could pass where the types forbid it. */
const untyped = (value: unknown): never => value as never;

// The ends of what Python's money property draws, the smallest rate that rounds, and a value with
// a long fraction, each with its hand-worked (down, up).
const TIMES_CASES: [bigint, string, bigint, bigint][] = [
  [0n, "0", 0n, 0n],
  [10n ** 15n, "1", 10n ** 15n, 10n ** 15n],
  [1n, "0.000001", 0n, 1n],
  [10n ** 15n, "0.999999", 999_999_000_000_000n, 999_999_000_000_000n],
  [7n, "0.333333", 2n, 3n],
];

test("IDR has no minor unit", () => {
  expect(IDR.code).toBe("IDR");
  expect(IDR.minorUnits).toBe(0n);
});

test.each(["idr", "ID", "IDRX", "", "I1R"])("currency code %j is refused", (code) => {
  expect(() => new Currency(code, 0n)).toThrow(
    new RangeError(`currency code must be three capital letters, got ${JSON.stringify(code)}`),
  );
});

test("currency code must be a string", () => {
  expect(() => new Currency(untyped(null), 0n)).toThrow(
    new TypeError("currency code must be a string, got object"),
  );
});

test.each([-1n, 5n])("minor units %s are refused", (minorUnits) => {
  expect(() => new Currency("USD", minorUnits)).toThrow(
    new RangeError(`minorUnits must be a bigint from 0 to 4, got ${String(minorUnits)}`),
  );
});

test("minor units that are not a bigint are refused", () => {
  expect(() => new Currency("USD", untyped(true))).toThrow(
    new RangeError("minorUnits must be a bigint from 0 to 4, got true"),
  );
});

test.each([0n, 4n])("minor units %s are accepted", (minorUnits) => {
  expect(new Currency("XTS", minorUnits).minorUnits).toBe(minorUnits);
});

test("currencies are equal by code and minor units", () => {
  expect(usd().equals(usd())).toBe(true);
  expect(usd().equals(new Currency("USD", 3n))).toBe(false);
  expect(usd().equals(IDR)).toBe(false);
});

test.each([[untyped(1)], ["1"], [untyped(true)]])("amount %j is refused", (amount) => {
  expect(() => new Money(untyped(amount), IDR)).toThrow(
    new TypeError(`Money amount must be a bigint of minor units, got ${typeof amount}`),
  );
});

test("currency must be a Currency", () => {
  expect(() => new Money(1n, untyped("IDR"))).toThrow(
    new TypeError("Money currency must be a Currency, got string"),
  );
});

test("zero", () => {
  expect(Money.zero(usd()).equals(new Money(0n, usd()))).toBe(true);
});

test("equality includes the currency", () => {
  expect(new Money(0n, IDR).equals(new Money(0n, usd()))).toBe(false);
  expect(rp(5n).equals(rp(5n))).toBe(true);
  expect(rp(5n).equals(rp(6n))).toBe(false);
});

test("add, subtract, negate", () => {
  expect(rp(7n).plus(rp(5n))).toEqual(rp(12n));
  expect(rp(7n).minus(rp(12n))).toEqual(rp(-5n));
  expect(rp(7n).negated()).toEqual(rp(-7n));
});

test.each(["plus", "minus", "lt", "le", "gt", "ge"] as const)(
  "%s refuses mixed currencies",
  (name) => {
    expect(() => rp(1n)[name](new Money(1n, usd()))).toThrow(new CurrencyMismatchError(IDR, usd()));
    expect(() => rp(1n)[name](new Money(1n, usd()))).toThrow("cannot combine IDR with USD");
  },
);

test.each(["plus", "minus", "lt", "le", "gt", "ge"] as const)(
  "%s refuses an operand that is not Money",
  (name) => {
    expect(() => rp(1n)[name](untyped(1n))).toThrow(
      new TypeError(`${name} needs Money, got bigint`),
    );
  },
);

test("ordering", () => {
  const pairs = [
    [rp(1n), rp(2n)],
    [rp(2n), rp(2n)],
    [rp(3n), rp(2n)],
  ] as const;
  expect(pairs.map(([a, b]) => [a.lt(b), a.le(b), a.gt(b), a.ge(b)])).toEqual([
    [true, true, false, false],
    [false, true, false, true],
    [false, false, true, true],
  ]);
});

test("multiply by a share count", () => {
  expect(rp(4_150n).times(300n)).toEqual(rp(1_245_000n));
});

test.each([[new Decimal("1.5")], [untyped(true)], [untyped(1.5)]])(
  "multiply refuses %j",
  (factor) => {
    expect(() => rp(10n).times(untyped(factor))).toThrow(
      /^multiply Money by a bigint quantity, got .*; use timesRate\(\) for a rate$/u,
    );
  },
);

test("rounds up for what you pay", () => {
  // A 0.15% fee on Rp 1,000,001 is Rp 1,500.0015 before rounding.
  expect(rp(1_000_001n).timesRate(new Decimal("0.0015"), Rounding.UP)).toEqual(rp(1_501n));
});

test("rounds down for what you receive", () => {
  expect(rp(1_000_001n).timesRate(new Decimal("0.0015"), Rounding.DOWN)).toEqual(rp(1_500n));
});

test("exact results are not moved", () => {
  expect(rp(1_000_000n).timesRate(new Decimal("0.001"), Rounding.UP)).toEqual(rp(1_000n));
  expect(rp(1_000_000n).timesRate(new Decimal("0.001"), Rounding.DOWN)).toEqual(rp(1_000n));
});

test("direction is by value, not by magnitude", () => {
  expect(rp(-3n).timesRate(new Decimal("0.5"), Rounding.UP)).toEqual(rp(-1n));
  expect(rp(-3n).timesRate(new Decimal("0.5"), Rounding.DOWN)).toEqual(rp(-2n));
});

test("huge amounts are exact", () => {
  // 41 significant digits: more than decimal.js's default 20, and Python's default 28.
  const amount = 10n ** 40n + 1n;
  expect(rp(amount).timesRate(new Decimal("0.0015"), Rounding.UP)).toEqual(
    rp(15n * 10n ** 36n + 1n),
  );
  expect(rp(amount).timesRate(new Decimal("0.0015"), Rounding.DOWN)).toEqual(rp(15n * 10n ** 36n));
});

test("a rate with a huge exponent is exact", () => {
  expect(rp(3n).timesRate(new Decimal("1e-30"), Rounding.UP)).toEqual(rp(1n));
  expect(rp(3n).timesRate(new Decimal("1e30"), Rounding.DOWN)).toEqual(rp(3n * 10n ** 30n));
});

test.each(["NaN", "Infinity", "-Infinity"])("rate %s is refused", (rate) => {
  expect(() => rp(1n).timesRate(new Decimal(rate), Rounding.UP)).toThrow(
    new RangeError(`rate must be finite, got ${rate}`),
  );
});

test("rate must be a Decimal", () => {
  expect(() => rp(1n).timesRate(untyped(1n), Rounding.UP)).toThrow(
    new TypeError("rate must be a Decimal, got bigint"),
  );
});

test.each(TIMES_CASES)("Rp %s at %s: down and up bracket the exact value", (amount, rate) => {
  const down = new Decimal(
    rp(amount).timesRate(new Decimal(rate), Rounding.DOWN).amount.toString(),
  );
  const up = new Decimal(rp(amount).timesRate(new Decimal(rate), Rounding.UP).amount.toString());
  const exact = new Decimal(amount.toString()).times(rate);
  expect(down.lte(exact) && exact.lte(up)).toBe(true);
  expect(up.minus(down).toString()).toBe(exact.isInteger() ? "0" : "1");
});

test.each(TIMES_CASES)("Rp %s at %s rounds to its hand-worked pair", (amount, rate, down, up) => {
  expect([
    rp(amount).timesRate(new Decimal(rate), Rounding.DOWN).amount,
    rp(amount).timesRate(new Decimal(rate), Rounding.UP).amount,
  ]).toEqual([down, up]);
});

test.each([
  [1_500_000n, "IDR", 0n, "IDR 1,500,000"],
  [-1_500n, "IDR", 0n, "IDR -1,500"],
  [0n, "IDR", 0n, "IDR 0"],
  [1_205n, "USD", 2n, "USD 12.05"],
  [-5n, "USD", 2n, "USD -0.05"],
])("%s %s with %s minor units reads %j", (amount, code, minorUnits, text) => {
  expect(new Money(amount, new Currency(code, minorUnits)).toString()).toBe(text);
});
