import type Decimal from "decimal.js";
import { expect, test } from "vitest";
import { buyAndHold } from "../src/buy-and-hold.ts";
import { IDR, Money } from "../src/money.ts";
import type { PortfolioView } from "../src/sizing.ts";
import { weightOf, type MarketView, type Memory } from "../src/strategy.ts";

// Ported from Python's tests/engine/test_buy_and_hold.py, one test per case (M3 spec §6.6). The
// Decision checks are advice's (`advice.test.ts`); the types refuse a float weight, a non-text
// key or memory, and a note that is not one.

const D0 = "2025-06-02";
const STOCKS = ["ASII", "BBCA", "BBRI", "TLKM", "UNVR"] as const;

const rp = (amount: bigint): Money => new Money(amount, IDR);

const view = (buyable: readonly string[], sellable: readonly string[] = []): MarketView => ({
  day: D0,
  tradable: {
    day: D0,
    buyable: new Set(buyable),
    sellable: new Set(sellable),
    reasons: new Map(),
    members: new Set(buyable),
  },
  closes: new Map(),
  dividends: new Map(),
  splits: [],
});

const portfolioOf = (
  value: bigint,
  spendable: bigint,
  held: Readonly<Record<string, bigint>> = {},
): PortfolioView => ({
  value: rp(value),
  spendable: rp(spendable),
  holdings: new Map(Object.entries(held).map(([symbol, amount]) => [symbol, rp(amount)])),
});

const NONE: Memory = new Map();

const weightsOf = (weights: ReadonlyMap<string, Decimal>) =>
  Object.fromEntries([...weights].map(([symbol, weight]) => [symbol, weight.toString()]));

test("it is a strategy named buy-and-hold", () => {
  expect(buyAndHold.name).toBe("buy-and-hold");
});

test("day one fixes the set and splits the cash equally", () => {
  const decision = buyAndHold.decide(
    view(["BBCA", "BBRI", "TLKM"]),
    portfolioOf(9_000_000n, 9_000_000n),
    NONE,
  );
  const third = "0.3333333333333333333333333333";
  expect(weightsOf(decision.weights)).toEqual({ BBCA: third, BBRI: third, TLKM: third });
  expect(Object.fromEntries(decision.memory)).toEqual({ set: "IDX:BBCA IDX:BBRI IDX:TLKM" });
  expect(decision.notes).toEqual([]);
});

test("later days keep holdings and buy only the set", () => {
  const portfolio = portfolioOf(10_000_000n, 900_000n, { BBCA: 4_000_000n, BBRI: 5_000_000n });
  const memory: Memory = new Map([["set", "IDX:BBCA IDX:BBRI IDX:TLKM"]]);
  const decision = buyAndHold.decide(
    view(["BBCA", "TLKM", "ASII"], ["BBCA", "BBRI"]),
    portfolio,
    memory,
  );
  expect(weightsOf(decision.weights)).toEqual({ BBCA: "0.445", BBRI: "0.5", TLKM: "0.045" });
  expect(decision.memory).toEqual(memory);
});

test("an empty first day leaves an empty set", () => {
  const portfolio = portfolioOf(1_000_000n, 1_000_000n);
  const first = buyAndHold.decide(view([]), portfolio, NONE);
  expect(first.weights.size).toBe(0);
  const later = buyAndHold.decide(view(["BBCA"]), portfolio, first.memory);
  expect(later.weights.size).toBe(0);
});

test("every stock it weights carries its reason", () => {
  const decision = buyAndHold.decide(
    view(["BBCA"]),
    portfolioOf(2_000_000n, 1_000_000n, { TLKM: 1_000_000n }),
    NONE,
  );
  expect(Object.fromEntries(decision.reasons)).toEqual({
    BBCA: "buy-and-hold: part of its day-one set, bought with an equal share of the cash",
    TLKM: "buy-and-hold: held, never sold",
  });
});

test("a set written by another market is refused by name", () => {
  expect(() =>
    buyAndHold.decide(view([]), portfolioOf(0n, 0n), new Map([["set", "NYSE:IBM"]])),
  ).toThrow(new Error("buy-and-hold's memory names NYSE:IBM, not a stock of IDX"));
});

// The buy-and-hold property's stand-in cases (#290), worked by hand there at Python's default
// 28 digits: nothing at all; every stock held, chosen and buyable at the largest amounts (each
// holding 1/7 of Rp70bn rounded down plus 1/35, whose 29-digit sum rounds half-even); and a set
// that only partly overlaps what can be bought.
interface HoldCase {
  readonly name: string;
  readonly held: Readonly<Record<string, bigint>>;
  readonly spendable: bigint;
  readonly unsettled: bigint;
  readonly chosen: readonly string[];
  readonly buyable: readonly string[];
  readonly weights: Readonly<Record<string, string>>;
}

const everything = (amount: bigint): Readonly<Record<string, bigint>> =>
  Object.fromEntries(STOCKS.map((symbol) => [symbol, amount]));

const HOLD_CASES: readonly HoldCase[] = [
  { name: "nothing", held: {}, spendable: 0n, unsettled: 0n, chosen: [], buyable: [], weights: {} },
  {
    name: "the most",
    held: everything(10n ** 10n),
    spendable: 10n ** 10n,
    unsettled: 10n ** 10n,
    chosen: STOCKS,
    buyable: STOCKS,
    weights: Object.fromEntries(STOCKS.map((symbol) => [symbol, "0.1714285714285714285714285714"])),
  },
  {
    name: "a partial overlap",
    held: { ASII: 1n, TLKM: 9_892n },
    spendable: 100n,
    unsettled: 7n,
    chosen: ["ASII", "BBCA", "BBRI"],
    buyable: ["BBRI", "UNVR"],
    weights: { ASII: "0.0001", TLKM: "0.9892", BBRI: "0.01" },
  },
];

const decided = (hold: HoldCase) => {
  const worth = Object.values(hold.held).reduce((sum, amount) => sum + amount, 0n);
  const portfolio = portfolioOf(worth + hold.spendable + hold.unsettled, hold.spendable, hold.held);
  const memory: Memory = new Map([
    [
      "set",
      [...hold.chosen]
        .sort()
        .map((symbol) => `IDX:${symbol}`)
        .join(" "),
    ],
  ]);
  return { portfolio, memory, decision: buyAndHold.decide(view(hold.buyable), portfolio, memory) };
};

test.each(HOLD_CASES)("it never sells and buys only its set: $name", (hold) => {
  const { portfolio, memory, decision } = decided(hold);
  const buying = hold.chosen.filter((symbol) => hold.buyable.includes(symbol));
  expect(new Set(decision.weights.keys())).toEqual(new Set([...Object.keys(hold.held), ...buying]));
  for (const symbol of Object.keys(hold.held).filter((held) => !buying.includes(held))) {
    expect(decision.weights.get(symbol)?.toString()).toBe(weightOf(portfolio, symbol).toString());
  }
  for (const symbol of buying) {
    expect(decision.weights.get(symbol)?.gte(weightOf(portfolio, symbol))).toBe(true);
  }
  expect(decision.memory).toEqual(memory);
});

test.each(HOLD_CASES)("each stand-in case's weights are worked by hand: $name", (hold) => {
  expect(weightsOf(decided(hold).decision.weights)).toEqual(hold.weights);
});
