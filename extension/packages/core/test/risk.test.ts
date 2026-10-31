import { expect, test } from "vitest";
import { Side } from "../src/costs.ts";
import { IDR, Money } from "../src/money.ts";
import type { Note } from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { checkOrders, percent, RiskLimits, type RiskLimitValues } from "../src/risk.ts";
import { IdxMarketRules } from "../src/rules.ts";
import type { Order } from "../src/sizing.ts";
import type { Tradable } from "../src/tradable.ts";

// Ported from Python's tests/engine/test_risk.py, one test per case: the limits and the order
// check. Halts and the unit value are EXT S12's.

const DAY = "2025-06-02";
const PRICES: ReadonlyMap<string, Money> = new Map([
  ["BBCA", new Money(9_000n, IDR)],
  ["BBRI", new Money(4_000n, IDR)],
]);
const MERGER: Note = { code: "trade.frozen", text: "frozen: merger" };
const OPEN: Tradable = {
  day: DAY,
  buyable: new Set(["BBCA", "BBRI"]),
  sellable: new Set(["BBCA", "BBRI"]),
  reasons: new Map([["TLKM", MERGER]]),
  members: new Set(["BBCA", "BBRI", "TLKM"]),
};

const RULES = new IdxMarketRules();

const rp = (amount: bigint): Money => new Money(amount, IDR);

const buy = (quantity: bigint, symbol = "BBCA"): Order => ({
  symbol,
  side: Side.BUY,
  quantity,
  day: DAY,
});

const sell = (quantity: bigint, symbol = "BBCA"): Order => ({
  symbol,
  side: Side.SELL,
  quantity,
  day: DAY,
});

interface Checking {
  readonly value?: bigint;
  readonly spendable?: bigint;
  readonly held?: Readonly<Record<string, bigint>>;
  readonly limits?: RiskLimits;
}

/** Check `orders` for a portfolio worth `value`, spending all of it not `held` by default. */
const check = (orders: readonly Order[], checking: Checking = {}) => {
  const value = checking.value ?? 100_000_000n;
  const held = Object.entries(checking.held ?? {});
  const cash = checking.spendable ?? value - held.reduce((sum, [, amount]) => sum + amount, 0n);
  const portfolio = {
    value: rp(value),
    spendable: rp(cash),
    holdings: new Map(held.map(([symbol, amount]) => [symbol, rp(amount)])),
  };
  const result = checkOrders(
    RULES,
    checking.limits ?? new RiskLimits(),
    orders,
    portfolio,
    OPEN,
    PRICES,
  );
  return {
    passed: result.orders,
    rejected: result.rejected.map((dropped) => [dropped.order, dropped.reason]),
    cuts: result.cuts.map((cut) => [cut.quantity, cut.reason]),
  };
};

test("the defaults are the core spec's", () => {
  const limits = new RiskLimits();
  expect([limits.maxWeight.toString(), limits.minLots, limits.dailyLoss.toString()]).toEqual([
    "0.1",
    1n,
    "0.05",
  ]);
  expect(limits.maxDrawdown.toString()).toBe("0.25");
});

test.each([
  [{ dailyLoss: new RuleDecimal(NaN) }, "dailyLoss must be a finite decimal, got NaN"],
  [{ minLots: 0n }, "minLots must be at least 1, got 0"],
  [{ maxWeight: new RuleDecimal(0) }, "maxWeight must be above 0 and at most 1, got 0"],
  [{ maxWeight: new RuleDecimal("1.01") }, "maxWeight must be above 0 and at most 1, got 1.01"],
  [{ dailyLoss: new RuleDecimal(1) }, "dailyLoss must be above 0 and below 1, got 1"],
  [{ maxDrawdown: new RuleDecimal(0) }, "maxDrawdown must be above 0 and below 1, got 0"],
] as const)("limits are checked: %o", (values: RiskLimitValues, message) => {
  expect(() => new RiskLimits(values)).toThrow(new RangeError(message));
});

test("a weight limit of exactly 1 is allowed", () => {
  expect(new RiskLimits({ maxWeight: new RuleDecimal(1) }).maxWeight.toString()).toBe("1");
});

test("a limit is written as a percentage to two places, rounded down", () => {
  expect(percent(new RuleDecimal("0.10"))).toBe("10.00%");
  expect(percent(new RuleDecimal("0.123456"))).toBe("12.34%");
});

test("a stock outside the tradable set is dropped with its reason", () => {
  const { passed, rejected } = check([buy(100n, "TLKM"), sell(100n, "TLKM"), buy(100n, "ASII")]);
  expect(passed).toEqual([]);
  expect(rejected).toEqual([
    [buy(100n, "TLKM"), MERGER],
    [sell(100n, "TLKM"), MERGER],
    [
      buy(100n, "ASII"),
      { code: "trade.not_in_universe", text: "not in the universe on 2025-06-02" },
    ],
  ]);
});

test("sales pass and their proceeds fund nothing", () => {
  const { passed, rejected } = check([sell(1_000n), buy(100n)], { spendable: 0n });
  expect(passed).toEqual([sell(1_000n)]);
  expect(rejected).toEqual([
    [buy(100n), { code: "limit.cash.short", text: "not enough cash: IDR 0 can be spent" }],
  ]);
});

test("a buy is cut to the limit per stock exactly at its edge", () => {
  const { passed, cuts } = check([buy(300n)], { value: 18_000_000n });
  expect(passed).toEqual([buy(200n)]);
  expect(cuts).toEqual([
    [200n, { code: "limit.weight.cut", text: "cut to the 10.00% limit per stock" }],
  ]);
});

test("a buy is cut a lot further one rupiah below the edge", () => {
  expect(check([buy(300n)], { value: 17_999_990n }).passed).toEqual([buy(100n)]);
});

test("a buy for a stock already at the limit is dropped", () => {
  const { rejected } = check([buy(100n)], { value: 10_000_000n, held: { BBCA: 900_001n } });
  expect(rejected).toEqual([
    [buy(100n), { code: "limit.weight.full", text: "already at the 10.00% limit per stock" }],
  ]);
});

test("a buy below the minimum lots is dropped", () => {
  const { passed, rejected } = check([buy(100n), buy(200n, "BBRI")], {
    limits: new RiskLimits({ minLots: 2n }),
  });
  expect(rejected).toEqual([
    [buy(100n), { code: "limit.min_lots", text: "below the minimum buy of 2 lot(s)" }],
  ]);
  expect(passed).toEqual([buy(200n, "BBRI")]);
});

const WHOLE = new RiskLimits({ maxWeight: new RuleDecimal(1) });

test("buys together spend no more than the cash, costs included", () => {
  const { passed, rejected } = check([buy(100n), buy(100n, "BBRI")], {
    spendable: 1_000_000n,
    limits: WHOLE,
  });
  expect(passed).toEqual([buy(100n)]);
  expect(rejected).toEqual([
    [
      buy(100n, "BBRI"),
      { code: "limit.cash.short", text: "not enough cash: IDR 98,111 can be spent" },
    ],
  ]);
});

test("a buy is cut to the cash exactly at its edge", () => {
  const { passed, cuts } = check([buy(300n)], { spendable: 1_803_777n, limits: WHOLE });
  expect(passed).toEqual([buy(200n)]);
  expect(cuts).toEqual([
    [200n, { code: "limit.cash.cut", text: "cut to the IDR 1,803,777 that can be spent" }],
  ]);
});

test("a buy is cut a lot further one rupiah below the cash edge", () => {
  expect(check([buy(300n)], { spendable: 1_803_776n, limits: WHOLE }).passed).toEqual([buy(100n)]);
});

test("a negative cash figure buys nothing", () => {
  const { rejected } = check([buy(100n)], { spendable: -5n, limits: WHOLE });
  expect(rejected).toEqual([
    [buy(100n), { code: "limit.cash.short", text: "not enough cash: IDR -5 can be spent" }],
  ]);
});

test("a buy for a stock held above the limit is dropped", () => {
  const { rejected } = check([buy(100n)], { value: 10_000_000n, held: { BBCA: 1_000_001n } });
  expect(rejected).toEqual([
    [buy(100n), { code: "limit.weight.full", text: "already at the 10.00% limit per stock" }],
  ]);
});
