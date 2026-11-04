import type Decimal from "decimal.js";
import { expect, test } from "vitest";
import { IDR, Money } from "../src/money.ts";
import { NOTE_CODES } from "../src/notes.ts";
import { Ratio } from "../src/ratio.ts";
import { haltOn, RiskLimits, UnitValue } from "../src/risk.ts";

// Ported from Python's tests/engine/test_risk.py, one test per case: the fund-style unit value
// and the halt it judges (EXT S12, #236).

const DAY = "2025-06-02";
const LIMITS = new RiskLimits();

const rp = (amount: bigint): Money => new Money(amount, IDR);

const dec = (text: string): Decimal => new Ratio(text);

const fund = (price: string, highWater = "1"): UnitValue =>
  new UnitValue(dec("100"), dec(price), dec(highWater));

const parts = (value: UnitValue): string[] => [
  value.units.toString(),
  value.price.toString(),
  value.highWater.toString(),
];

test("the first deposit buys units at 1", () => {
  expect(parts(new UnitValue().deposit(rp(10_000_000n)))).toEqual(["10000000", "1", "1"]);
});

test("a deposit leaves the unit value unchanged", () => {
  const topped = new UnitValue()
    .deposit(rp(10_000_000n))
    .revalue(rp(12_000_000n))
    .deposit(rp(1_200_000n));
  expect([topped.units.toString(), topped.price.toString()]).toEqual(["11000000", "1.2"]);
  expect(topped.revalue(rp(13_200_000n)).price.toString()).toBe("1.2");
});

test("revaluing moves the price and the high-water mark", () => {
  const moved = new UnitValue().deposit(rp(1_000n)).revalue(rp(1_500n)).revalue(rp(1_200n));
  expect([moved.price.toString(), moved.highWater.toString()]).toEqual(["1.2", "1.5"]);
});

test("revaluing before there are units changes nothing", () => {
  expect(parts(new UnitValue().revalue(rp(5n)))).toEqual(["0", "1", "1"]);
});

test("units cannot be bought at a price of 0", () => {
  const worthless = new UnitValue(dec("10"), dec("0"), dec("1"));
  expect(() => worthless.deposit(rp(1n))).toThrow(/^no units can be bought at a price of 0$/);
});

test.each([
  ["units", () => new UnitValue(dec("-1"))],
  ["price", () => new UnitValue(dec("1"), dec("-1"))],
  ["highWater", () => new UnitValue(dec("1"), dec("1"), dec("-1"))],
])("%s cannot be negative", (field, make) => {
  expect(make).toThrow(new RegExp(`^${field} cannot be negative, got -1$`));
});

test.each([
  ["units", () => new UnitValue(dec("NaN"))],
  ["price", () => new UnitValue(dec("1"), dec("Infinity"))],
  ["highWater", () => new UnitValue(dec("1"), dec("1"), dec("-Infinity"))],
])("%s must be finite", (field, make) => {
  expect(make).toThrow(new RegExp(`^${field} must be a finite decimal, got `));
});

test("minus zero is zero, not negative", () => {
  expect(new UnitValue(dec("-0")).units.isZero()).toBe(true);
});

test("the drawdown is the fall below the high-water mark, as a share of it", () => {
  expect(fund("0.75").drawdown.toString()).toBe("0.25");
  expect(fund("1.5", "1.5").drawdown.toString()).toBe("0");
});

// The deposit stand-in cases of Python's #290, worked by hand there: in each the price valued
// again with the deposit in it is the price exactly.
test.each([
  [1n, 1n, 1n, "1", "2"],
  [10n ** 12n, 10n ** 13n, 10n ** 12n, "10", "1100000000000"],
  [10n ** 12n, 1n, 10n ** 12n, "1e-12", "1.000000000001e+24"],
  [3n, 10n, 7n, "3.333333333333333333333333333", "5.1"],
])(
  "%s units worth %s take a deposit of %s at an unchanged price",
  (units, value, paid, price, after) => {
    const before = new UnitValue(new Ratio(units.toString())).revalue(rp(value));
    const topped = before.deposit(rp(paid));
    expect([before.price.toString(), topped.units.toString()]).toEqual([price, after]);
    expect(topped.price.toString()).toBe(price);
    expect(topped.revalue(rp(value + paid)).price.toString()).toBe(price);
  },
);

test("a withdrawal sells units at the price, which it leaves unchanged", () => {
  const drawn = new UnitValue().deposit(rp(1_000n)).revalue(rp(2_000n)).deposit(rp(-500n));
  expect([drawn.units.toString(), drawn.price.toString()]).toEqual(["750", "2"]);
});

test("a daily loss at the limit halts", () => {
  expect(haltOn(LIMITS, fund("1"), fund("0.95"), DAY)).toEqual({
    day: DAY,
    cause: {
      code: NOTE_CODES.RISK_HALT_DAILY_LOSS,
      text: "daily loss limit: the unit value fell 5.00%, the limit is 5.00%",
    },
  });
});

test("a daily loss just inside the limit does not halt", () => {
  expect(haltOn(LIMITS, fund("1"), fund("0.9501"), DAY)).toBeNull();
});

test("a fall over several days names the span it was judged over", () => {
  expect(haltOn(LIMITS, fund("1"), fund("0.94"), DAY, "2025-05-27")).toEqual({
    day: DAY,
    cause: {
      code: NOTE_CODES.RISK_HALT_DAILY_LOSS,
      text:
        "daily loss limit: the unit value fell 6.00% from 2025-05-27 to 2025-06-02, with no " +
        "read on the trading days between; the limit is 5.00%",
    },
  });
});

test("a drawdown at the kill switch halts", () => {
  expect(haltOn(LIMITS, fund("0.76"), fund("0.75"), DAY)).toEqual({
    day: DAY,
    cause: {
      code: NOTE_CODES.RISK_HALT_DRAWDOWN,
      text:
        "drawdown kill switch: the unit value is 25.00% below its high-water mark, " +
        "the limit is 25.00%",
    },
  });
});

test("a drawdown just inside the kill switch does not halt", () => {
  expect(haltOn(LIMITS, fund("0.76"), fund("0.7501"), DAY)).toBeNull();
});

test("no units today: neither a 90% fall nor a 90% drawdown halts", () => {
  expect(haltOn(LIMITS, new UnitValue(), new UnitValue(dec("0"), dec("0.1")), DAY)).toBeNull();
});

test("no units the day before: a 6% fall does not halt", () => {
  expect(haltOn(LIMITS, new UnitValue(), fund("0.94"), DAY)).toBeNull();
});
