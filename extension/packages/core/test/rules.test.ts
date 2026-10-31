import { expect, test } from "vitest";
import feesFile from "../rules/fees.json" with { type: "json" };
import { bandLimits } from "../src/bands.ts";
import { Side } from "../src/costs.ts";
import { parseFees } from "../src/fees.ts";
import { Currency, IDR, Money } from "../src/money.ts";
import { RulesFileError, UnsupportedDateError } from "../src/rules-file.ts";
import { IdxMarketRules, shippedTables, type Instrument } from "../src/rules.ts";
import { isValidPrice } from "../src/ticks.ts";
import parity from "./rules.json" with { type: "json" };

// Ported from Python's tests/idx/test_rules.py, one test per case.

const rules = (): IdxMarketRules => new IdxMarketRules();

const BBCA: Instrument = { symbol: "BBCA", market: "IDX", currency: IDR };
const TODAY = "2026-09-25";
const USD = new Currency("USD", 2n);

const rp = (amount: bigint): Money => new Money(amount, IDR);

test("the rules are in rupiah", () => {
  expect(rules().currency).toBe(IDR);
});

test("the verified date is 2021, set by the stamp duty", () => {
  expect(rules().verifiedFrom).toBe("2021-01-01");
  rules().requireSupported("2021-01-01");
  expect(() => {
    rules().requireSupported("2020-12-31");
  }).toThrow(
    new UnsupportedDateError(
      "steadyhand's IDX rules are primary-verified from 2021-01-01, the first date of " +
        "fees.json [stamp_duty]; 2020-12-31 is earlier",
      "2020",
    ),
  );
});

test("the verified date is derived from the files", () => {
  const document = structuredClone(feesFile);
  const [first] = document.stamp_duty;
  if (first === undefined) {
    throw new Error("the shipped stamp duty table has no row");
  }
  first.from = "2019-01-01";
  const moved = new IdxMarketRules({ ...shippedTables(), fees: parseFees(document) });
  // The next-latest first date is 13 Mar 2020, shared by three tables; the first listed names it.
  expect(moved.verifiedFrom).toBe("2020-03-13");
  expect(() => {
    moved.requireSupported("2020-03-12");
  }).toThrow(/first date of tick_sizes\.json \[ticks\];/u);
});

test("a year past the holiday data is refused", () => {
  expect(() => {
    rules().requireSupported("2028-01-03");
  }).toThrow(/^holidays\.json has no IDX holidays for 2028/u);
});

test.each([
  ["lotSize", () => rules().lotSize(BBCA, "2020-12-31")],
  ["roundToTick", () => rules().roundToTick(BBCA, rp(201n), Side.BUY, "2020-12-31")],
  ["priceBand", () => rules().priceBand(BBCA, rp(1000n), "2020-12-31")],
  ["costs", () => rules().costs(Side.BUY, rp(1000n), "2020-12-31")],
  ["dailyCosts", () => rules().dailyCosts(rp(1000n), "2020-12-31")],
  ["settlementDate", () => rules().settlementDate("2020-12-30")],
  ["dividendTax", () => rules().dividendTax(rp(1000n), "2020-12-31")],
  ["reinvestmentDeadline", () => rules().reinvestmentDeadline("2020-12-31")],
  ["protectionEnd", () => rules().protectionEnd("2020-12-31")],
])("%s refuses an unverified day", (_, call) => {
  expect(call).toThrow(/primary-verified from 2021-01-01/u);
});

test("another market is refused", () => {
  expect(() => rules().lotSize({ symbol: "AAPL", market: "NASDAQ", currency: USD }, TODAY)).toThrow(
    new RangeError("AAPL is a NASDAQ USD instrument; these rules are for IDX IDR"),
  );
});

test("an IDX instrument in another currency is refused", () => {
  expect(() => rules().lotSize({ symbol: "BBCA", market: "IDX", currency: USD }, TODAY)).toThrow(
    new RangeError("BBCA is a IDX USD instrument; these rules are for IDX IDR"),
  );
});

test("a price in another currency is refused", () => {
  expect(() => rules().roundToTick(BBCA, new Money(201n, USD), Side.BUY, TODAY)).toThrow(
    new RangeError("price must be in IDR, got USD 2.01"),
  );
});

test("a band reference in another currency is refused", () => {
  expect(() => rules().priceBand(BBCA, new Money(201n, USD), TODAY)).toThrow(
    new RangeError("reference must be in IDR, got USD 2.01"),
  );
});

test("a dividend in another currency is refused", () => {
  expect(() => rules().dividendTax(new Money(1n, USD), TODAY)).toThrow(
    new RangeError("gross must be in IDR, got USD 0.01"),
  );
});

test("the exemption dates come from the fee tables", () => {
  expect(rules().reinvestmentDeadline("2021-02-16")).toBeNull();
  expect(rules().reinvestmentDeadline(TODAY)).toBe("2027-03-31");
  expect(rules().protectionEnd(TODAY)).toBe("2028-12-31");
});

test("lots and ticks: a buy rounds up, a sell down", () => {
  expect(rules().lotSize(BBCA, TODAY)).toBe(100n);
  expect(rules().roundToTick(BBCA, rp(5_001n), Side.BUY, TODAY).amount).toBe(5_025n);
  expect(rules().roundToTick(BBCA, rp(5_001n), Side.SELL, TODAY).amount).toBe(5_000n);
});

test.each([
  [TODAY, 1_000n, 850n, 1_250n, "25% up and 15% down, both on the Rp5 grid"],
  [TODAY, 200n, 170n, 270n, "200 is in the 35% tier for bands"],
  [TODAY, 5_000n, 4_250n, 6_250n, "5,000 is in the 25% tier for bands"],
  [TODAY, 5_025n, 4_280n, 6_025n, "6,030 is off the Rp25 grid; 4,271.25 rounds up to Rp10's 4,280"],
  [TODAY, 50n, 50n, 67n, "the bottom (42.5) is raised to the Rp50 minimum"],
  ["2026-09-28", 7n, 6n, 8n, "the Rp1-10 tier moves Rp1 either way"],
  ["2026-09-28", 1n, 1n, 2n, "never below the Rp1 minimum"],
  ["2027-01-01", 1_000n, 750n, 1_250n, "symmetric 25% from 2027"],
  // The band property's stand-in cases below, each edge worked by hand from auto_reject.toml and
  // tick_sizes.toml: the band's bottom and top, the bottom raised to the minimum price, then the
  // bottom rounded up and the top rounded down onto the tick grid.
  [
    "2021-01-04",
    50n,
    50n,
    67n,
    "2020-03-13 row, up to 200: +35% / -7%; 46.5 is raised to Rp50, 67.5 floors to 67",
  ],
  [
    "2021-01-04",
    1_000_000n,
    930_000n,
    1_200_000n,
    "the 2020-03-13 row's top tier: +20% / -7%, both edges on the Rp25 grid",
  ],
  [
    "2023-06-05",
    199n,
    170n,
    268n,
    "2023-06-05 row, up to 200: +35% / -15%; 169.15 rounds up to 170, 268.65 floors to 268",
  ],
  ["2023-06-05", 200n, 170n, 270n, "the same row at 200: exactly 170 and 270"],
  ["2023-09-04", 5_000n, 3_750n, 6_250n, "2023-09-04 row, up to 5,000: +-25%"],
  [
    "2023-09-04",
    5_001n,
    4_010n,
    6_000n,
    "past 5,000 +-20%: 4,000.8 rounds up to 4,010 (tick 10), 6,001.2 down to 6,000",
  ],
  [
    TODAY,
    4_999n,
    4_250n,
    6_225n,
    "2025-04-08 row, up to 5,000 +25% / -15%: 4,249.15 rounds up, 6,248.75 down to 6,225",
  ],
  [TODAY, 1_000_000n, 850_000n, 1_200_000n, "the 2025-04-08 row's top tier: +20% / -15%"],
])("on %s the band around %s is %s to %s: %s", (on, reference, low, high) => {
  const [lowest, highest] = rules().priceBand(BBCA, rp(reference), on);
  expect([lowest.amount, highest.amount]).toEqual([low, high]);
});

test("a reference below the minimum price is refused", () => {
  expect(() => rules().priceBand(BBCA, rp(40n), TODAY)).toThrow(
    new RangeError("reference IDR 40 is below the minimum price, Rp50"),
  );
});

/** The valid prices from `from` to `to`, both included. */
const validBetween = (on: string, from: bigint, to: bigint): bigint[] => {
  const ticks = shippedTables().ticks.on(on);
  const found: bigint[] = [];
  for (let price = from; price <= to; price += 1n) {
    if (isValidPrice(ticks, price)) {
      found.push(price);
    }
  }
  return found;
};

// Python's unit stand-in (#290): each band table's date, at the ends of the references drawn and
// across each side of the band tiers' edges at 200 and 5,000. Only the two ends are scanned.
test.each([
  [50n, "2021-01-04"],
  [1_000_000n, "2021-01-04"],
  [199n, "2023-06-05"],
  [200n, "2023-06-05"],
  [5_000n, "2023-09-04"],
  [5_001n, "2023-09-04"],
  [4_999n, TODAY],
  [1_000_000n, TODAY],
])("the band around %s on %s ends at the widest valid prices inside it", (reference, on) => {
  const [low, high] = rules().priceBand(BBCA, rp(reference), on);
  const band = shippedTables().bands.on(on);
  const [bottom, top] = bandLimits(band, reference);
  const ceiling = BigInt(bottom.ceil().toFixed());
  const first = ceiling > band.minPrice ? ceiling : band.minPrice;
  expect(validBetween(on, first, low.amount)).toEqual([low.amount]);
  expect(validBetween(on, high.amount, BigInt(top.floor().toFixed()))).toEqual([high.amount]);
});

test("costs use the chosen broker preset", () => {
  const ajaib = new IdxMarketRules(shippedTables(), "ajaib");
  expect(ajaib.costs(Side.BUY, rp(10_000_000n), TODAY).total.amount).toBe(15_130n);
  expect(rules().costs(Side.BUY, rp(10_000_000n), TODAY).total.amount).toBe(20_980n);
  expect(() => new IdxMarketRules(shippedTables(), "ipot")).toThrow(
    /^no broker fee preset named 'ipot'/u,
  );
});

test("daily costs are the stamp duty", () => {
  expect(rules().dailyCosts(rp(1n), "2021-01-04").amount).toBe(10_000n);
  expect(rules().dailyCosts(rp(10_000_000n), "2022-01-12").amount).toBe(0n);
});

// AC2: stamp duty is charged once for the day's orders, on their total, never per order.
test("an order's costs carry no stamp duty: its total is its fee, levy and tax", () => {
  const costs = rules().costs(Side.BUY, rp(6_000_000n), "2022-01-12");
  expect(costs.total.amount).toBe(costs.fee.amount + costs.levy.amount + costs.tax.amount);
});

test("two orders of 6 million on 2022-01-12 pay the duty once, on their 12 million total", () => {
  // Each order alone is under the 10 million exemption; the day's total is over it.
  expect(rules().dailyCosts(rp(6_000_000n), "2022-01-12").amount).toBe(0n);
  expect(rules().dailyCosts(rp(12_000_000n), "2022-01-12").amount).toBe(10_000n);
});

test("two orders on 2021-01-04 pay one duty of 10,000, not one each", () => {
  expect(rules().dailyCosts(rp(2n), "2021-01-04").amount).toBe(10_000n);
});

test.each([
  ["2026-09-24", "2026-09-28"], // Thursday: across the weekend
  ["2026-03-17", "2026-03-26"], // across Eid al-Fitr's five holidays
  ["2026-12-29", "2027-01-04"], // across the year-end holidays
  ["2021-01-04", "2021-01-06"], // the first verified trading day
])("a trade on %s settles two trading days later, on %s", (trade, settles) => {
  expect(rules().settlementDate(trade)).toBe(settles);
});

test("nothing settles from a non-trading day", () => {
  expect(() => rules().settlementDate("2026-09-26")).toThrow(
    new RangeError("2026-09-26 is not an IDX trading day, so nothing trades on it"),
  );
});

test("dividend tax and trading days", () => {
  expect(rules().dividendTax(rp(1_000n), TODAY).amount).toBe(100n);
  expect(rules().isTradingDay("2021-01-04")).toBe(true);
  expect(rules().isTradingDay("2026-12-31")).toBe(false);
});

test("trading days answer for every year of holiday data before the rules are verified", () => {
  // A pay date modelled for a 2020 dividend counts 2020's trading days (M6 spec §4.1).
  expect(rules().isTradingDay("2020-12-30")).toBe(true);
  expect(rules().isTradingDay("2020-12-31")).toBe(false);
  expect(rules().isTradingDay("2016-01-04")).toBe(true);
  expect(() => rules().isTradingDay("2015-12-31")).toThrow(
    /^holidays\.json has no IDX holidays for 2015/u,
  );
  expect(() => {
    rules().requireSupported("2020-12-30");
  }).toThrow(/primary-verified from 2021-01-01/u);
});

// AC4: Python's `IdxMarketRules` on seeded days, prices and trades (scripts/core_fixtures.py),
// which core must answer digit for digit.
test.each(parity)("parity with Python on %# ($day, $preset $side)", (expected) => {
  const market = new IdxMarketRules(shippedTables(), expected.preset);
  const side = expected.side === "buy" ? Side.BUY : Side.SELL;
  const on = expected.day;
  const [low, high] = market.priceBand(BBCA, rp(BigInt(expected.reference)), on);
  const gross = rp(BigInt(expected.gross));
  const costs = market.costs(side, gross, on);
  expect({
    ...expected,
    tick: String(market.roundToTick(BBCA, rp(BigInt(expected.price)), side, on).amount),
    low: String(low.amount),
    high: String(high.amount),
    fee: String(costs.fee.amount),
    levy: String(costs.levy.amount),
    tax: String(costs.tax.amount),
    stamp_duty: String(market.dailyCosts(gross, on).amount),
    dividend_tax: String(market.dividendTax(gross, on).amount),
    settles: market.settlementDate(on),
  }).toEqual(expected);
});

test("a day that is not an ISO date is refused before it is compared", () => {
  // "2021-1-5" sorts after "2021-01-01", so a string comparison alone would let it through.
  expect(() => {
    rules().requireSupported("2021-1-5");
  }).toThrow(new RulesFileError('day must be a date such as 2021-01-04, got "2021-1-5"'));
});
