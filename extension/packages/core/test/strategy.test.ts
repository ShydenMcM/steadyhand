import { expect, test } from "vitest";
import { IDR, Money } from "../src/money.ts";
import type { PortfolioView } from "../src/sizing.ts";
import {
  memoryFor,
  plus,
  readSet,
  storedAfter,
  universeOf,
  weightOf,
  writeSet,
  type Memory,
} from "../src/strategy.ts";
import { RuleDecimal } from "../src/ratio.ts";

// The strategy protocol's parts (#229 AC1, AC2): weights, sets, the universe and the memory a day
// starts from.

const rp = (amount: bigint): Money => new Money(amount, IDR);
const portfolio: PortfolioView = {
  value: rp(3n),
  spendable: rp(1n),
  holdings: new Map([["BBCA", rp(2n)]]),
};

test("a holding's weight is its share of the value, rounded down", () => {
  expect(weightOf(portfolio, "BBCA").toString()).toBe("0.6666666666666666666666666666");
});

test("a stock not held weighs nothing", () => {
  expect(weightOf(portfolio, "TLKM").toString()).toBe("0");
});

test("weights add at 28 digits, half-even, as Python's do", () => {
  const third = new RuleDecimal("0.1428571428571428571428571428");
  expect(plus(third, new RuleDecimal("0.02857142857142857142857142857")).toString()).toBe(
    "0.1714285714285714285714285714",
  );
  expect(plus(undefined, third).toString()).toBe(third.toString());
});

test("a set is written in order, each stock with its market", () => {
  expect(writeSet(["TLKM", "BBCA"])).toBe("IDX:BBCA IDX:TLKM");
  expect(writeSet([])).toBe("");
});

test("a set is read back to its stocks, and an empty one to none", () => {
  expect(readSet("IDX:BBCA IDX:TLKM", "s")).toEqual(["BBCA", "TLKM"]);
  expect(readSet("", "s")).toEqual([]);
});

const watchlist = { stocks: [{ symbol: "BBCA", lastPrice: rp(9_000n) }] };

test("the universe is the listed stocks the watchlist read gives", () => {
  expect(universeOf(["BBCA"], new Set(), watchlist)).toEqual({
    members: new Set(["BBCA"]),
    missing: [],
  });
});

test("every listed stock missing from the watchlist is a gap, named", () => {
  expect(universeOf(["BBCA", "BBRI", "TLKM"], new Set(), watchlist).missing).toEqual([
    { code: "missing.page", text: "open the watchlist page for BBRI" },
    { code: "missing.page", text: "open the watchlist page for TLKM" },
  ]);
});

test("a stock Settings excludes is neither judged nor needs a read", () => {
  expect(universeOf(["BBCA", "TLKM"], new Set(["TLKM", "BBCA"]), watchlist)).toEqual({
    members: new Set(),
    missing: [],
  });
});

const began: Memory = new Map([["set", "IDX:BBCA"]]);
const ended: Memory = new Map([["set", "IDX:BBCA IDX:TLKM"]]);
const stored = storedAfter("2025-06-17", began, ended);

test("a first advice day starts from no memory", () => {
  expect(memoryFor(undefined, "2025-06-17")).toEqual(new Map());
});

test("advising again on the same day starts from the memory that day began with", () => {
  expect(memoryFor(stored, "2025-06-17")).toBe(began);
});

test("a later advice day starts from the memory the last one ended with", () => {
  expect(memoryFor(stored, "2025-06-18")).toBe(ended);
});

test("memory written for a later day than the advice day is refused", () => {
  expect(() => memoryFor(stored, "2025-06-16")).toThrow(
    new RangeError("strategy memory is for 2025-06-17, later than the advice day 2025-06-16"),
  );
});
