import Decimal from "decimal.js";
import { expect, test } from "vitest";
import { Money, IDR, Rounding } from "../src/money.ts";
import { Ratio, ratioDown, roundRatio } from "../src/ratio.ts";
import fixture from "./ratios.json" with { type: "json" };

// Python's digits for seeded inputs, written by scripts/core_fixtures.py from Python's own code.

test.each(fixture.ratio_down)("ratioDown(%s, %s) is Python's %s", (part, whole, expected) => {
  const found = ratioDown(BigInt(part), BigInt(whole));
  expect(found.eq(expected)).toBe(true);
  expect(found.toString()).toBe(new Decimal(expected).toString());
});

test.each(fixture.rounded)("roundRatio(%s) is Python's %s", (value, expected) => {
  expect(roundRatio(new Ratio(value)).toFixed()).toBe(new Decimal(expected).toFixed());
});

test("the fixture holds the cases it was written with", () => {
  expect(fixture.ratio_down.length).toBe(208);
  expect(fixture.rounded.length).toBe(212);
});

test("ratioDown takes Decimals as well as bigints", () => {
  expect(ratioDown(new Decimal(1), new Decimal(4)).toString()).toBe("0.25");
});

test("ratioDown by zero is zero", () => {
  expect(ratioDown(5n, 0n).isZero()).toBe(true);
});

test("ratioDown rounds down, never to nearest", () => {
  expect(ratioDown(2n, 3n).toString()).toBe("0.6666666666666666666666666666");
  expect(ratioDown(-1n, 3n).toString()).toBe("-0.3333333333333333333333333334");
});

test("roundRatio rounds a tie to even", () => {
  // decimal.js keeps no trailing zeros: Python's 0E-8 and 2E-8 are 0 and 0.00000002.
  expect(roundRatio(new Decimal("0.000000005")).toFixed()).toBe("0");
  expect(roundRatio(new Decimal("0.000000015")).toFixed()).toBe("0.00000002");
  expect(roundRatio(new Decimal("-0.000000025")).toFixed()).toBe("-0.00000002");
});

test("a ratio's value multiplies Money, a clone being a Decimal too", () => {
  expect(new Money(1_000n, IDR).timesRate(ratioDown(1n, 4n), Rounding.DOWN).amount).toBe(250n);
});
