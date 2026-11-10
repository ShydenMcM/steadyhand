import { expect, test } from "vitest";
import type { Dividend, Dividends } from "../src/broker-view.ts";
import { runRate, type RunRate } from "../src/income.ts";
import { IDR, Money } from "../src/money.ts";
import { missingPage, NOTE_CODES } from "../src/notes.ts";
import {
  incomeGrowth,
  PROJECTION_LABEL,
  project,
  type IncomeGrowth,
  type ProjectionInputs,
} from "../src/projection.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { IdxMarketRules } from "../src/rules.ts";

// #254 (spec §9.1): each paying holding's dividend growth over four years and the years until
// the income goal is met in three scenarios, as Python's `dividend_growth` and `project` give
// them. Every figure below is Python's answer for the same holdings. The run rate's window is
// 2024-06-18 to 2025-06-17; the earlier year ends on 2021-06-17.

const RULES = new IdxMarketRules();
const DAY = "2025-06-17";
const FIVE_YEARS_BACK = "2020-06-17";

const rp = (amount: bigint): Money => new Money(amount, IDR);

const dividend = (symbol: string, exDate: string, perShare: string): Dividend => ({
  symbol,
  exDate,
  paymentDate: exDate,
  grossPerShare: new RuleDecimal(perShare),
});

const read = (symbol: string, rows: readonly Dividend[], from = "2019-01-01"): Dividends => ({
  symbol,
  covered: { from, to: DAY },
  dividends: rows,
});

// BBRI's dividend a share grew from 100 to 121 over the four years; TLKM paid nothing in the
// earlier year.
const GROWING = new Map([
  [
    "BBRI",
    read("BBRI", [dividend("BBRI", "2021-03-20", "100"), dividend("BBRI", "2025-03-25", "121")]),
  ],
  ["TLKM", read("TLKM", [dividend("TLKM", "2025-05-30", "250")])],
]);
const HELD = new Map([
  ["BBRI", 1_000n],
  ["TLKM", 500n],
]);

const rated = (dividends: ReadonlyMap<string, Dividends>, held = HELD): RunRate => {
  const found = runRate({
    rules: RULES,
    held,
    dividends,
    splits: [],
    unknownActions: new Map(),
    asOf: DAY,
  });
  if (found.rate === null) {
    throw new Error(`no run rate: ${JSON.stringify(found.missing)}`);
  }
  return found.rate;
};

const grown = (dividends: ReadonlyMap<string, Dividends>, held = HELD): IncomeGrowth => {
  const found = incomeGrowth(rated(dividends, held), dividends, []);
  if (found.growth === null) {
    throw new Error(`no growth: ${JSON.stringify(found.missing)}`);
  }
  return found.growth;
};

const inputs = (over: Partial<ProjectionInputs> = {}): ProjectionInputs => ({
  rate: rated(GROWING),
  growth: grown(GROWING),
  holdingsValue: rp(10_000_000n),
  target: rp(50_000n),
  contribution: rp(0n),
  rules: RULES,
  ...over,
});

const outcomes = (over: Partial<ProjectionInputs> = {}) =>
  project(inputs(over)).scenarios.map((found) => [
    found.scenario,
    found.outcome,
    found.years === null ? null : found.years.toFixed(1),
  ]);

test("each paying holding's growth is the fourth root of its dividends' ratio, less 1", () => {
  const growth = grown(GROWING);
  expect(
    growth.holdings.map((found) => [
      found.symbol,
      found.recent.toString(),
      found.earlier.toString(),
      found.growth.toString(),
    ]),
  ).toEqual([
    ["BBRI", "121", "100", "0.04880885"],
    ["TLKM", "250", "0", "0"],
  ]);
  expect(growth.portfolio.toString()).toBe("0.02400761");
});

test("a holding with nothing in the earlier year counts as 0% and says so", () => {
  expect(grown(GROWING).notes).toEqual([
    {
      code: NOTE_CODES.INCOME_GROWTH_SHORT_HISTORY,
      text: "TLKM: no dividend was found in the year ending 2021-06-17, so its dividend growth is taken as 0%",
    },
  ]);
});

test("a holding that pays nothing has no growth, and a portfolio paying nothing grows 0%", () => {
  const unpaid = new Map([["BBRI", read("BBRI", [dividend("BBRI", "2021-03-20", "100")])]]);
  const growth = grown(unpaid, new Map([["BBRI", 1_000n]]));
  expect(growth.holdings).toEqual([]);
  expect(growth.portfolio.toString()).toBe("0");
});

test("a paying holding whose dividends are not read back five years is missing (AC2)", () => {
  const short = new Map([
    ...GROWING,
    ["TLKM", read("TLKM", [dividend("TLKM", "2025-05-30", "250")], "2020-06-18")],
  ]);
  expect(incomeGrowth(rated(short), short, [])).toEqual({
    growth: null,
    missing: [missingPage("dividends", "TLKM")],
  });
});

test("a read reaching back exactly five years covers the holding", () => {
  const exact = new Map([
    ...GROWING,
    ["TLKM", read("TLKM", [dividend("TLKM", "2025-05-30", "250")], FIVE_YEARS_BACK)],
  ]);
  expect(incomeGrowth(rated(exact), exact, []).missing).toEqual([]);
});

test("a goal already met is met in no time, in every scenario", () => {
  expect(outcomes({ target: rp(10_000n) })).toEqual([
    ["pessimistic", "reached", "0.0"],
    ["base", "reached", "0.0"],
    ["optimistic", "reached", "0.0"],
  ]);
});

test("the pessimistic scenario starts at 80% of the run rate and may not reach the goal", () => {
  const found = project(inputs());
  expect(
    found.scenarios.map((scenario) => [scenario.start.amount, scenario.growth.toString()]),
  ).toEqual([
    [196_800n, "0"],
    [246_000n, "0.02400761"],
    [246_000n, "0.02400761"],
  ]);
  expect(outcomes()).toEqual([
    ["pessimistic", "not-within", null],
    ["base", "reached", "19.7"],
    ["optimistic", "reached", "19.7"],
  ]);
});

test("a monthly contribution reaches the goal sooner", () => {
  expect(outcomes({ contribution: rp(1_000_000n) })).toEqual([
    ["pessimistic", "reached", "2.0"],
    ["base", "reached", "1.4"],
    ["optimistic", "reached", "1.4"],
  ]);
});

test("a goal out of reach is not met within 50 years", () => {
  expect(outcomes({ target: rp(1_000_000_000n) })).toEqual([
    ["pessimistic", "not-within", null],
    ["base", "not-within", null],
    ["optimistic", "not-within", null],
  ]);
});

test("with no holdings value or no income there is nothing to project", () => {
  const cannot = [
    ["pessimistic", "cannot", null],
    ["base", "cannot", null],
    ["optimistic", "cannot", null],
  ];
  expect(outcomes({ holdingsValue: rp(0n) })).toEqual(cannot);
  const unpaid = new Map([["BBRI", read("BBRI", [dividend("BBRI", "2021-03-20", "100")])]]);
  const held = new Map([["BBRI", 1_000n]]);
  expect(outcomes({ rate: rated(unpaid, held), growth: grown(unpaid, held) })).toEqual(cannot);
});

test("growth is capped at 5% in the base scenario, 10% in the optimistic, 0% in the pessimistic", () => {
  const fast = new Map([
    [
      "BBRI",
      read("BBRI", [dividend("BBRI", "2021-03-20", "100"), dividend("BBRI", "2025-03-25", "300")]),
    ],
    [
      "TLKM",
      read("TLKM", [dividend("TLKM", "2021-05-30", "300"), dividend("TLKM", "2025-05-30", "200")]),
    ],
  ]);
  const growth = grown(fast);
  expect(growth.holdings.map((found) => found.growth.toString())).toEqual([
    "0.31607401",
    "-0.096398",
  ]);
  expect(growth.portfolio.toString()).toBe("0.21295601");
  const found = project(inputs({ rate: rated(fast), growth }));
  expect(
    found.scenarios.map((scenario) => [scenario.growth.toString(), scenario.years?.toFixed(1)]),
  ).toEqual([
    ["0", "25.6"],
    ["0.05", "6.0"],
    ["0.1", "4.0"],
  ]);
});

test("falling dividends fall in every scenario", () => {
  const falling = new Map([
    [
      "BBRI",
      read("BBRI", [dividend("BBRI", "2021-03-20", "300"), dividend("BBRI", "2025-03-25", "100")]),
    ],
  ]);
  const held = new Map([["BBRI", 1_000n]]);
  const growth = grown(falling, held);
  expect(growth.portfolio.toString()).toBe("-0.24016431");
  const found = project(inputs({ rate: rated(falling, held), growth }));
  expect(found.scenarios.map((scenario) => [scenario.growth.toString(), scenario.outcome])).toEqual(
    [
      ["-0.24016431", "not-within"],
      ["-0.24016431", "not-within"],
      ["-0.24016431", "not-within"],
    ],
  );
});

test("the projection keeps its target and contribution and says it leaves out trading costs", () => {
  const found = project(inputs({ contribution: rp(1_000_000n) }));
  expect(found.target).toEqual(rp(50_000n));
  expect(found.contribution).toEqual(rp(1_000_000n));
  expect(found.notes).toEqual([
    {
      code: NOTE_CODES.INCOME_PROJECTION_COSTS_IGNORED,
      text: "Reinvesting costs broker fees and levies, which this projection leaves out, so it reaches the target a little sooner than a real portfolio would",
    },
  ]);
});

test("the projection is labelled as Python labels it", () => {
  expect(PROJECTION_LABEL).toBe("Projection, not a promise");
});
