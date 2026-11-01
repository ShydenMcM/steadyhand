import type Decimal from "decimal.js";
import { expect, test } from "vitest";
import { monthlySavings } from "../src/monthly-savings.ts";
import { IDR, Money } from "../src/money.ts";
import { ratioDown, RuleDecimal } from "../src/ratio.ts";
import type { PortfolioView } from "../src/sizing.ts";
import { plus, weightOf, type MarketView, type Memory } from "../src/strategy.ts";

// Ported from Python's tests/engine/test_monthly_savings.py, one test per case (M6 spec §5), with
// the extension's bounds on `instalments` (12 by default, from 1 to 120, #229 AC4).

const JUNE = "2025-06-02";
const LATER_IN_JUNE = "2025-06-03";
const JULY = "2025-07-01";
const AUGUST = "2025-08-01";

const rp = (amount: bigint): Money => new Money(amount, IDR);

const view = (day: string, buyable: readonly string[]): MarketView => ({
  day,
  tradable: {
    day,
    buyable: new Set(buyable),
    sellable: new Set(),
    reasons: new Map(),
    members: new Set(buyable),
  },
});

const portfolioOf = (
  spendable: bigint,
  held: Readonly<Record<string, bigint>> = {},
): PortfolioView => {
  const worth = Object.values(held).reduce((sum, amount) => sum + amount, 0n);
  return {
    value: rp(spendable + worth),
    spendable: rp(spendable),
    holdings: new Map(Object.entries(held).map(([symbol, amount]) => [symbol, rp(amount)])),
  };
};

const memoryOf = (entries: Readonly<Record<string, string>>): Memory =>
  new Map(Object.entries(entries));
const NONE: Memory = new Map();

const text = (weights: ReadonlyMap<string, Decimal>) =>
  Object.fromEntries([...weights].map(([symbol, weight]) => [symbol, weight.toString()]));
const textOf = (weights: Readonly<Record<string, Decimal>>) =>
  Object.fromEntries(
    Object.entries(weights).map(([symbol, weight]) => [symbol, weight.toString()]),
  );

test("it is a strategy named monthly-savings, of 12 instalments by default", () => {
  expect(monthlySavings().name).toBe("monthly-savings");
  expect(monthlySavings().instalments).toBe(12n);
});

test.each([1n, 120n])("%s instalments is allowed", (instalments) => {
  expect(monthlySavings(instalments).instalments).toBe(instalments);
});

test.each([0n, 121n])("%s instalments is refused", (instalments) => {
  expect(() => monthlySavings(instalments)).toThrow(
    new RangeError(`instalments must be from 1 to 120, got ${instalments.toString()}`),
  );
});

test("its first day fixes the instalment and buys one, split equally", () => {
  const decision = monthlySavings(12n).decide(
    view(JUNE, ["BBCA", "BBRI"]),
    portfolioOf(12_000_000n),
    NONE,
  );
  const each = ratioDown(500_000n, 12_000_000n);
  expect(each.toString()).toBe("0.04166666666666666666666666666");
  expect(text(decision.weights)).toEqual(textOf({ BBCA: each, BBRI: each }));
  expect(Object.fromEntries(decision.memory)).toEqual({
    instalment: "1000000",
    due: "11",
    month: "2025-06",
  });
  expect(decision.notes).toEqual([]);
});

test("the instalment is whole and rounded down", () => {
  const decision = monthlySavings(7n).decide(view(JUNE, ["BBCA"]), portfolioOf(1_000_000n), NONE);
  expect(decision.memory.get("instalment")).toBe("142857");
  expect(text(decision.weights)).toEqual(
    textOf({ BBCA: ratioDown(1_000_000n - 6n * 142_857n, 1_000_000n) }),
  );
});

test("later days in the month keep every holding and buy nothing", () => {
  const memory = memoryOf({ instalment: "1000000", due: "11", month: "2025-06" });
  const held = portfolioOf(11_300_000n, { BBCA: 600_000n, ASII: 400_000n });
  const decision = monthlySavings(12n).decide(view(LATER_IN_JUNE, ["BBCA", "BBRI"]), held, memory);
  expect(text(decision.weights)).toEqual(
    textOf({ BBCA: weightOf(held, "BBCA"), ASII: weightOf(held, "ASII") }),
  );
  expect(decision.memory).toEqual(memory);
});

test("the next month buys its instalment with the cash that arrived since", () => {
  const memory = memoryOf({ instalment: "1000000", due: "11", month: "2025-06" });
  const held = portfolioOf(11_300_000n, { BBCA: 1_000_000n });
  const decision = monthlySavings(12n).decide(view(JULY, ["BBCA", "BBRI"]), held, memory);
  const each = ratioDown(650_000n, 12_300_000n);
  expect(text(decision.weights)).toEqual(
    textOf({ BBCA: plus(weightOf(held, "BBCA"), each), BBRI: each }),
  );
  expect(Object.fromEntries(decision.memory)).toEqual({
    instalment: "1000000",
    due: "10",
    month: "2025-07",
  });
});

test("the last instalment spends everything, and so does every month after", () => {
  const last = memoryOf({ instalment: "1000000", due: "1", month: "2025-06" });
  const decision = monthlySavings(12n).decide(view(JULY, ["BBCA"]), portfolioOf(1_250_000n), last);
  expect(text(decision.weights)).toEqual({ BBCA: "1" });
  expect(Object.fromEntries(decision.memory)).toEqual({
    instalment: "1000000",
    due: "0",
    month: "2025-07",
  });
  const after = monthlySavings(12n).decide(
    view(AUGUST, ["BBCA"]),
    portfolioOf(80_000n),
    decision.memory,
  );
  expect(text(after.weights)).toEqual({ BBCA: "1" });
  expect(Object.fromEntries(after.memory)).toEqual({
    instalment: "1000000",
    due: "0",
    month: "2025-08",
  });
});

test("one instalment is a lump sum, then monthly reinvestment", () => {
  const decision = monthlySavings(1n).decide(
    view(JUNE, ["BBCA", "BBRI"]),
    portfolioOf(9_000_000n),
    NONE,
  );
  expect(text(decision.weights)).toEqual({ BBCA: "0.5", BBRI: "0.5" });
  expect(Object.fromEntries(decision.memory)).toEqual({
    instalment: "9000000",
    due: "0",
    month: "2025-06",
  });
});

test("a month with nothing buyable waits for a day that has something", () => {
  const first = monthlySavings(12n).decide(view(JUNE, []), portfolioOf(12_000_000n), NONE);
  expect(first.weights.size).toBe(0);
  expect(Object.fromEntries(first.memory)).toEqual({ instalment: "1000000", due: "12" });
  const retry = monthlySavings(12n).decide(
    view(LATER_IN_JUNE, ["BBCA"]),
    portfolioOf(12_000_000n),
    first.memory,
  );
  expect(text(retry.weights)).toEqual(textOf({ BBCA: ratioDown(1_000_000n, 12_000_000n) }));
  expect(Object.fromEntries(retry.memory)).toEqual({
    instalment: "1000000",
    due: "11",
    month: "2025-06",
  });
});

test("it never sells, and keeps a stock that left the universe", () => {
  const memory = memoryOf({ instalment: "1000000", due: "5", month: "2025-06" });
  const held = portfolioOf(5_000_000n, { TLKM: 2_000_000n });
  const decision = monthlySavings(12n).decide(view(JULY, ["BBCA"]), held, memory);
  expect(text(decision.weights)).toEqual(
    textOf({ TLKM: weightOf(held, "TLKM"), BBCA: ratioDown(1_000_000n, 7_000_000n) }),
  );
});

test("a first day on a portfolio that holds stocks sizes the instalment from cash", () => {
  const held = portfolioOf(4_000_000n, { TLKM: 6_000_000n });
  const decision = monthlySavings(4n).decide(view(JUNE, ["BBCA"]), held, NONE);
  expect(Object.fromEntries(decision.memory)).toEqual({
    instalment: "1000000",
    due: "3",
    month: "2025-06",
  });
  expect(text(decision.weights)).toEqual(
    textOf({ TLKM: weightOf(held, "TLKM"), BBCA: ratioDown(1_000_000n, 10_000_000n) }),
  );
});

test("memory with an instalment but nothing due is refused by name", () => {
  expect(() =>
    monthlySavings(12n).decide(
      view(JUNE, ["BBCA"]),
      portfolioOf(1_000n),
      memoryOf({ instalment: "100" }),
    ),
  ).toThrow(new Error("monthly-savings's memory has an instalment but no due"));
});

test("every stock it weights carries its reason", () => {
  const held = portfolioOf(4_000_000n, { TLKM: 6_000_000n });
  const decision = monthlySavings(4n).decide(view(JUNE, ["BBCA"]), held, NONE);
  expect(Object.fromEntries(decision.reasons)).toEqual({
    BBCA: "monthly-savings: this month's instalment, split equally",
    TLKM: "monthly-savings: held, never sold",
  });
});

// The journeys of Python's property stand-ins (#290): each month the cash that arrives at its
// end, the stocks it can buy (Python's first `buyable` of ASII, BBCA, BBRI, TLKM), and its days,
// from `start` in cash.
type Month = readonly [arrived: bigint, buyable: readonly string[], days: bigint];
interface Journey {
  readonly name: string;
  readonly instalments: bigint;
  readonly start: bigint;
  readonly months: readonly Month[];
}

const STOCKS = ["ASII", "BBCA", "BBRI", "TLKM"];
const ASII = ["ASII"];

const repeated = (month: Month, count: bigint): Month[] => {
  const months: Month[] = [];
  for (let made = 0n; made < count; made += 1n) {
    months.push(month);
  }
  return months;
};

const ONE_INSTALMENT: Journey = {
  name: "one instalment",
  instalments: 1n,
  start: 1_000n,
  months: [[0n, [], 1n]],
};
const THE_MOST: Journey = {
  name: "the most",
  instalments: 24n,
  start: 10n ** 10n,
  months: repeated([10n ** 8n, STOCKS, 3n], 30n),
};
const GAPS: Journey = {
  name: "gaps",
  instalments: 3n,
  start: 50_000n,
  months: [
    [0n, ASII, 2n],
    [10_000n, [], 1n],
    [0n, STOCKS, 3n],
    [5n, ["ASII", "BBCA"], 1n],
    [0n, ASII, 1n],
  ],
};

interface Day {
  readonly held: PortfolioView;
  readonly weights: ReadonlyMap<string, Decimal>;
  readonly memory: Memory;
  readonly cash: bigint;
  readonly due: bigint;
}

/** Walk `journey` day by day, buying only BBCA's holding up, as Python's `_saved` does. */
const saved = (journey: Journey) => {
  const strategy = monthlySavings(journey.instalments);
  let memory: Memory = NONE;
  let cash = journey.start;
  let invested = 0n;
  let bought = 0n;
  let number = 0n;
  const run: Day[] = [];
  for (const [arrived, buyable, days] of journey.months) {
    if (buyable.length > 0) {
      bought += 1n;
    }
    for (let day = 1n; day <= days; day += 1n) {
      const held = portfolioOf(cash, invested > 0n ? { BBCA: invested } : {});
      const year = (2025n + number / 12n).toString();
      const month = ((number % 12n) + 1n).toString().padStart(2, "0");
      const when = `${year}-${month}-${day.toString().padStart(2, "0")}`;
      const decision = strategy.decide(view(when, buyable), held, memory);
      memory = decision.memory;
      // As Python works it: the weights summed, less the holding's, times the value, each step
      // at its default 28 digits, then truncated to whole rupiah.
      const total = [...decision.weights.values()].reduce(
        (sum, weight) => sum.plus(weight),
        new RuleDecimal(0),
      );
      const added = total.minus(weightOf(held, "BBCA")).times(held.value.amount.toString());
      const spent = BigInt(added.toDecimalPlaces(0, RuleDecimal.ROUND_DOWN).toFixed());
      cash -= spent;
      invested += spent;
      const left = journey.instalments - bought;
      run.push({ held, weights: decision.weights, memory, cash, due: left > 0n ? left : 0n });
    }
    cash += arrived;
    number += 1n;
  }
  return { run, cash, invested, memory };
};

test.each([ONE_INSTALMENT, THE_MOST, GAPS])(
  "the reserve for the instalments still due is never spent before its month: $name",
  (journey) => {
    for (const day of saved(journey).run) {
      for (const symbol of day.held.holdings.keys()) {
        expect(day.weights.get(symbol)?.gte(weightOf(day.held, symbol))).toBe(true);
      }
      expect(day.memory.get("due")).toBe(day.due.toString());
      expect(day.cash >= day.due * BigInt(day.memory.get("instalment") ?? "")).toBe(true);
    }
  },
);

test.each([
  { journey: ONE_INSTALMENT, total: 1_000n, memory: { instalment: "1000", due: "1" } },
  {
    journey: THE_MOST,
    total: 10n ** 10n + 30n * 10n ** 8n,
    memory: { instalment: "416666666", due: "0", month: "2027-06" },
  },
  { journey: GAPS, total: 60_005n, memory: { instalment: "16666", due: "0", month: "2025-05" } },
])(
  "each stand-in journey's total and memory are worked by hand: $journey.name",
  ({ journey, total, memory }) => {
    const end = saved(journey);
    expect([end.cash + end.invested, Object.fromEntries(end.memory)]).toEqual([total, memory]);
  },
);

test.each([
  { journey: ONE_INSTALMENT, cash: 1_000n, invested: 0n },
  { journey: GAPS, cash: 0n, invested: 60_005n },
])(
  "a journey's cash and holding are worked by hand: $journey.name",
  ({ journey, cash, invested }) => {
    const end = saved(journey);
    expect([end.cash, end.invested]).toEqual([cash, invested]);
  },
);
