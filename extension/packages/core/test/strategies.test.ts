import { expect, test } from "vitest";
import { STRATEGIES, strategyFrom, type StrategySetting } from "../src/strategies.ts";

// The strategies Settings offers and their bounds (#239 AC1): Python's registry `Setting` for
// the three it has, and Shyden's ruling of 2026-11-06 (#239) for the three M7 strategies.

const bounds = (name: string): readonly (readonly [string, bigint, bigint, bigint])[] =>
  (STRATEGIES.get(name)?.settings ?? []).map((setting: StrategySetting) => [
    setting.name,
    setting.default,
    setting.least,
    setting.most,
  ]);

test("Settings offers the six strategies, dividend-growth first as the default", () => {
  expect([...STRATEGIES.keys()]).toEqual([
    "dividend-growth",
    "buy-and-hold",
    "monthly-savings",
    "high-yield",
    "ma-trend",
    "momentum-rotation",
  ]);
});

test("each strategy is registered under its own name", () => {
  expect([...STRATEGIES.values()].map((entry) => entry.name)).toEqual([...STRATEGIES.keys()]);
});

test("each strategy has a one-line summary", () => {
  for (const entry of STRATEGIES.values()) {
    expect(entry.summary.trim()).not.toBe("");
    expect(entry.summary).not.toContain("\n");
  }
});

test("each setting has one line of help naming its bounds", () => {
  for (const entry of STRATEGIES.values()) {
    for (const setting of entry.settings) {
      expect(setting.help).not.toContain("\n");
      expect(setting.help).toContain(`${setting.least.toString()} to ${setting.most.toString()}`);
    }
  }
});

test("buy-and-hold has no settings", () => {
  expect(bounds("buy-and-hold")).toEqual([]);
});

test("monthly-savings is bounded as Python's registry", () => {
  expect(bounds("monthly-savings")).toEqual([["instalments", 12n, 1n, 120n]]);
});

test("dividend-growth is bounded as Python's registry", () => {
  expect(bounds("dividend-growth")).toEqual([
    ["min_stocks", 15n, 1n, 45n],
    ["max_stocks", 25n, 1n, 45n],
    ["growth_years", 5n, 1n, 10n],
  ]);
});

test("high-yield is bounded as ruled on 2026-11-06", () => {
  expect(bounds("high-yield")).toEqual([
    ["yield_stocks", 10n, 1n, 45n],
    ["paid_years", 3n, 1n, 10n],
  ]);
});

test("ma-trend is bounded as ruled on 2026-11-06", () => {
  expect(bounds("ma-trend")).toEqual([
    ["fast_days", 50n, 1n, 499n],
    ["slow_days", 200n, 2n, 500n],
  ]);
});

test("momentum-rotation is bounded as ruled on 2026-11-06", () => {
  expect(bounds("momentum-rotation")).toEqual([
    ["momentum_stocks", 10n, 1n, 45n],
    ["momentum_months", 12n, 2n, 24n],
    ["skip_months", 1n, 0n, 23n],
  ]);
});

test("a strategy made with no values takes every default", () => {
  const made = strategyFrom("dividend-growth", new Map());
  expect(made).toMatchObject({ name: "dividend-growth", minStocks: 15n, maxStocks: 25n });
});

test("a strategy is made with the values given", () => {
  const made = strategyFrom(
    "momentum-rotation",
    new Map([
      ["momentum_stocks", 5n],
      ["momentum_months", 6n],
      ["skip_months", 0n],
    ]),
  );
  expect(made).toMatchObject({
    name: "momentum-rotation",
    momentumStocks: 5n,
    momentumMonths: 6n,
    skipMonths: 0n,
  });
});

test("each strategy is made under its own name", () => {
  for (const name of STRATEGIES.keys()) {
    expect(strategyFrom(name, new Map()).name).toBe(name);
  }
});

test("a value at its lowest bound is taken", () => {
  expect(strategyFrom("monthly-savings", new Map([["instalments", 1n]]))).toMatchObject({
    instalments: 1n,
  });
});

test("a value at its highest bound is taken", () => {
  expect(strategyFrom("monthly-savings", new Map([["instalments", 120n]]))).toMatchObject({
    instalments: 120n,
  });
});

test("a value below its lowest bound is refused by name", () => {
  expect(() => strategyFrom("momentum-rotation", new Map([["skip_months", -1n]]))).toThrow(
    new RangeError("skip_months must be from 0 to 23, got -1"),
  );
});

test("a value above its highest bound is refused by name", () => {
  expect(() => strategyFrom("dividend-growth", new Map([["max_stocks", 46n]]))).toThrow(
    new RangeError("max_stocks must be from 1 to 45, got 46"),
  );
});

test("growth_years above 10 is refused, as Python refuses it", () => {
  expect(() => strategyFrom("dividend-growth", new Map([["growth_years", 11n]]))).toThrow(
    new RangeError("growth_years must be from 1 to 10, got 11"),
  );
});

test("fast_days not below slow_days is refused", () => {
  expect(() =>
    strategyFrom(
      "ma-trend",
      new Map([
        ["fast_days", 300n],
        ["slow_days", 300n],
      ]),
    ),
  ).toThrow(RangeError);
});

test("a setting the strategy does not have is refused by name", () => {
  expect(() => strategyFrom("buy-and-hold", new Map([["instalments", 12n]]))).toThrow(
    new RangeError("buy-and-hold has no setting named instalments"),
  );
});

test("a strategy that is not registered is refused by name", () => {
  expect(() => strategyFrom("day-trading", new Map())).toThrow(
    new RangeError("no strategy is named day-trading"),
  );
});

test("a strategy is made only with a value for every setting", () => {
  expect(() => STRATEGIES.get("monthly-savings")?.make(new Map())).toThrow(
    new Error("missing the setting instalments"),
  );
});
