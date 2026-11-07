import { RiskLimits, RuleDecimal } from "@steadyhand/core";
import { expect, test } from "vitest";
import {
  FEE_PRESETS,
  feePresetOf,
  limitsOf,
  storedLimits,
  storedStrategy,
  strategyOf,
  typedLimits,
  typedStrategy,
} from "../src/settings.ts";

// What Settings keeps for the strategy, the risk limits and the fee preset, and how it reads what
// the user typed (#239 AC1): each refused by the name of what is wrong.

const refused = (name: string): Error =>
  new Error(`the setting ${name} is not as Settings keeps it`);

test("before anything is chosen the strategy is dividend-growth with its defaults", () => {
  expect(strategyOf(undefined)).toEqual({ name: "dividend-growth", values: new Map() });
});

test("a kept strategy is read back with its values", () => {
  expect(strategyOf({ name: "ma-trend", values: [["fast_days", "20"]] })).toEqual({
    name: "ma-trend",
    values: new Map([["fast_days", 20n]]),
  });
});

test("a kept strategy is kept as its name and its values in digits", () => {
  expect(storedStrategy({ name: "ma-trend", values: new Map([["fast_days", 20n]]) })).toEqual({
    name: "ma-trend",
    values: [["fast_days", "20"]],
  });
});

test("a kept strategy that is not a record is refused", () => {
  expect(() => strategyOf("ma-trend")).toThrow(refused("strategy"));
});

test("a kept strategy with no name is refused", () => {
  expect(() => strategyOf({ values: [] })).toThrow(refused("strategy"));
});

test("a kept strategy whose values are not a list is refused", () => {
  expect(() => strategyOf({ name: "ma-trend", values: "fast_days" })).toThrow(refused("strategy"));
});

test("a kept strategy value that is not digits is refused", () => {
  expect(() => strategyOf({ name: "ma-trend", values: [["fast_days", "2x"]] })).toThrow(
    refused("strategy"),
  );
});

test("a kept strategy value that is not a pair is refused", () => {
  expect(() => strategyOf({ name: "ma-trend", values: [["fast_days"]] })).toThrow(
    refused("strategy"),
  );
});

test("typed settings make the strategy's values", () => {
  expect(
    typedStrategy(
      "momentum-rotation",
      new Map([
        ["momentum_stocks", "5"],
        ["momentum_months", " 6 "],
        ["skip_months", "0"],
      ]),
    ),
  ).toEqual({
    name: "momentum-rotation",
    values: new Map([
      ["momentum_stocks", 5n],
      ["momentum_months", 6n],
      ["skip_months", 0n],
    ]),
  });
});

test("a typed setting that is not a whole number is refused by name", () => {
  expect(() => typedStrategy("monthly-savings", new Map([["instalments", "1.5"]]))).toThrow(
    new RangeError('instalments must be a whole number, got "1.5"'),
  );
});

test("an empty typed setting is refused by name", () => {
  expect(() => typedStrategy("monthly-savings", new Map([["instalments", ""]]))).toThrow(
    new RangeError('instalments must be a whole number, got ""'),
  );
});

test("a typed setting out of its bounds is refused by name", () => {
  expect(() => typedStrategy("monthly-savings", new Map([["instalments", "121"]]))).toThrow(
    new RangeError("instalments must be from 1 to 120, got 121"),
  );
});

test("typed settings breaking a rule between two settings are refused", () => {
  expect(() =>
    typedStrategy(
      "dividend-growth",
      new Map([
        ["min_stocks", "20"],
        ["max_stocks", "10"],
        ["growth_years", "5"],
      ]),
    ),
  ).toThrow(new RangeError("max_stocks must be at least min_stocks (20), got 10"));
});

test("before any are set the risk limits are the defaults", () => {
  expect(limitsOf(undefined)).toEqual(new RiskLimits());
});

test("kept risk limits are read back", () => {
  expect(
    limitsOf({ maxWeight: "0.2", minLots: "2", dailyLoss: "0.04", maxDrawdown: "0.3" }),
  ).toEqual(
    new RiskLimits({
      maxWeight: new RuleDecimal("0.2"),
      minLots: 2n,
      dailyLoss: new RuleDecimal("0.04"),
      maxDrawdown: new RuleDecimal("0.3"),
    }),
  );
});

test("risk limits are kept as decimal text", () => {
  expect(storedLimits(new RiskLimits())).toEqual({
    maxWeight: "0.1",
    minLots: "1",
    dailyLoss: "0.05",
    maxDrawdown: "0.25",
  });
});

test("kept risk limits that are not a record are refused", () => {
  expect(() => limitsOf("0.1")).toThrow(refused("risk-limits"));
});

test("a kept risk limit that is not decimal text is refused", () => {
  expect(() =>
    limitsOf({ maxWeight: 0.2, minLots: "2", dailyLoss: "0.04", maxDrawdown: "0.3" }),
  ).toThrow(refused("risk-limits"));
});

test("kept minimum lots that are not digits are refused", () => {
  expect(() =>
    limitsOf({ maxWeight: "0.2", minLots: "2.5", dailyLoss: "0.04", maxDrawdown: "0.3" }),
  ).toThrow(refused("risk-limits"));
});

test("typed risk limits are read as percentages and lots", () => {
  expect(
    typedLimits({ maxWeight: "20", minLots: "2", dailyLoss: "4", maxDrawdown: "30.5" }),
  ).toEqual(
    new RiskLimits({
      maxWeight: new RuleDecimal("0.2"),
      minLots: 2n,
      dailyLoss: new RuleDecimal("0.04"),
      maxDrawdown: new RuleDecimal("0.305"),
    }),
  );
});

test("a typed percentage that is not a number is refused by name", () => {
  expect(() =>
    typedLimits({ maxWeight: "ten", minLots: "1", dailyLoss: "5", maxDrawdown: "25" }),
  ).toThrow(new RangeError('the largest share of one stock must be a percentage, got "ten"'));
});

test("typed minimum lots that are not whole are refused by name", () => {
  expect(() =>
    typedLimits({ maxWeight: "10", minLots: "1.5", dailyLoss: "5", maxDrawdown: "25" }),
  ).toThrow(new RangeError('the smallest buy in lots must be a whole number, got "1.5"'));
});

test("a typed percentage out of its range is refused by the limit's rule", () => {
  expect(() =>
    typedLimits({ maxWeight: "10", minLots: "1", dailyLoss: "100", maxDrawdown: "25" }),
  ).toThrow(new RangeError("dailyLoss must be above 0 and below 1, got 1"));
});

test("the fee presets are the shipped ones", () => {
  expect(FEE_PRESETS).toEqual(["ajaib", "custom"]);
});

test("before one is chosen the fee preset is custom", () => {
  expect(feePresetOf(undefined)).toBe("custom");
});

test("a kept fee preset is read back", () => {
  expect(feePresetOf("ajaib")).toBe("ajaib");
});

test("a kept fee preset that is not shipped is refused", () => {
  expect(() => feePresetOf("stockbit")).toThrow(refused("fee-preset"));
});
