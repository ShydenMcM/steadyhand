import { expect, test } from "vitest";
import type { Portfolio, Watchlist } from "../src/broker-view.ts";
import { advise, closesFrom, type Decision } from "../src/advice.ts";
import { Side } from "../src/costs.ts";
import { IDR, Money } from "../src/money.ts";
import {
  missingDeposits,
  missingHistory,
  missingPage,
  NOTE_CODES,
  note,
  type Note,
} from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { RiskLimits } from "../src/risk.ts";
import { IdxMarketRules } from "../src/rules.ts";
import { tradableOn } from "../src/tradable.ts";

// Spec §4.4 and §4.5: sized and checked orders become advice, each with its limit price at the
// advice day's close, its estimated fees and the strategy's reason; a strategy missing data
// gives no orders and lists every gap. Fees are the `custom` preset's 0.2098% on a buy, rounded
// up to the rupiah (10,000,000 costs 20,980 in rules.test.ts).

const DAY = "2025-06-02";
const RULES = new IdxMarketRules();

const rp = (amount: bigint): Money => new Money(amount, IDR);

const PRICES: ReadonlyMap<string, Money> = new Map([
  ["BBCA", rp(9_000n)],
  ["BBRI", rp(4_000n)],
  ["TLKM", rp(2_500n)],
]);

const TRADABLE = tradableOn({
  day: DAY,
  members: new Set(["BBCA", "BBRI", "TLKM"]),
  held: new Set(["TLKM"]),
  flags: [{ symbol: "TLKM", flag: "suspended" }],
  excluded: new Map(),
});

const decision = (over: Partial<Decision> = {}): Decision => ({
  weights: new Map([
    ["BBCA", new RuleDecimal("0.1")],
    ["BBRI", new RuleDecimal("0.05")],
  ]),
  reasons: new Map([
    ["BBCA", "equal share of the set"],
    ["BBRI", "equal share of the set"],
    ["TLKM", "left the set"],
  ]),
  missing: [],
  ...over,
});

const run = (spendable: bigint, chosen: Decision = decision(), stops: readonly Note[] = []) =>
  advise({
    rules: RULES,
    limits: new RiskLimits(),
    stops,
    decision: chosen,
    portfolio: {
      value: rp(100_000_000n),
      spendable: rp(spendable),
      holdings: new Map([["TLKM", rp(5_000_000n)]]),
      held: new Map([["TLKM", 2_000n]]),
      invested: rp(4_000_000n),
    },
    tradable: TRADABLE,
    prices: PRICES,
    day: DAY,
  });

const summary = (advice: ReturnType<typeof run>) =>
  advice.orders.map((advised) => ({
    symbol: advised.order.symbol,
    side: advised.order.side,
    quantity: advised.order.quantity,
    limit: advised.limitPrice.amount,
    fees: advised.costs.total.amount,
    estimate: advised.costs.estimate,
    reason: advised.reason,
  }));

test("each order carries its limit at the close, its estimated fees and the strategy's reason", () => {
  expect(summary(run(50_000_000n))).toEqual([
    {
      symbol: "BBCA",
      side: Side.BUY,
      quantity: 1_100n,
      limit: 9_000n,
      fees: 20_771n,
      estimate: true,
      reason: "equal share of the set",
    },
    {
      symbol: "BBRI",
      side: Side.BUY,
      quantity: 1_200n,
      limit: 4_000n,
      fees: 10_071n,
      estimate: true,
      reason: "equal share of the set",
    },
  ]);
});

test("frozen beats a strategy's sell: the suspended holding is not sold", () => {
  const advice = run(50_000_000n);
  expect(advice.rejected).toEqual([
    {
      order: { symbol: "TLKM", side: Side.SELL, quantity: 2_000n, day: DAY },
      reason: { code: "trade.frozen", text: "frozen: suspended" },
    },
  ]);
});

test("the stamp duty is charged once, on the day's orders together", () => {
  // 9,900,000 and 4,800,000 are each under the 10 million exemption; together they are over it.
  expect(run(50_000_000n).stampDuty.amount).toBe(10_000n);
});

test("orders cut to the cash keep Python's notes and carry fees on what is left", () => {
  const advice = run(5_000_000n);
  expect(
    summary(advice).map((advised) => [advised.symbol, advised.quantity, advised.fees]),
  ).toEqual([
    ["BBCA", 500n, 9_441n],
    ["BBRI", 100n, 840n],
  ]);
  expect(advice.cuts.map((cut) => [cut.order.symbol, cut.quantity, cut.reason])).toEqual([
    ["BBCA", 500n, { code: "limit.cash.cut", text: "cut to the IDR 5,000,000 that can be spent" }],
    ["BBRI", 100n, { code: "limit.cash.cut", text: "cut to the IDR 490,559 that can be spent" }],
  ]);
  expect(advice.stampDuty.amount).toBe(0n);
});

test("a strategy missing data gives no orders and lists every gap", () => {
  const gaps = [
    missingPage("dividends", "BBRI"),
    missingHistory("BBCA", { from: "2024-06-03", to: "2025-06-02" }, 120n),
    missingDeposits("2025-05-01"),
  ];
  const advice = run(50_000_000n, decision({ missing: gaps }));
  expect(advice.orders).toEqual([]);
  expect(advice.rejected).toEqual([]);
  expect(advice.cuts).toEqual([]);
  expect(advice.stampDuty.amount).toBe(0n);
  expect(advice.missing).toEqual(gaps);
});

test("advice with nothing missing lists no gaps", () => {
  expect(run(50_000_000n).missing).toEqual([]);
});

test("advice is for its advice day", () => {
  expect(run(50_000_000n).day).toBe(DAY);
});

test("an order the strategy gave no reason for is a bug in the strategy, named", () => {
  const silent = decision({ reasons: new Map([["BBRI", "equal share of the set"]]) });
  expect(() => run(50_000_000n, silent)).toThrow(
    new Error("the strategy gave no reason for its order in BBCA"),
  );
});

// The advice day's closes come from the portfolio and the watchlist read on that day.

const portfolio = (last: bigint): Portfolio => ({
  cashAvailable: rp(0n),
  cashSettled: rp(0n),
  cashUnsettled: rp(0n),
  holdings: [{ symbol: "TLKM", lots: 20n, averagePrice: rp(2_000n), lastPrice: rp(last) }],
});

const watchlist: Watchlist = {
  stocks: [
    { symbol: "BBCA", lastPrice: rp(9_000n) },
    { symbol: "TLKM", lastPrice: rp(2_500n) },
  ],
};

test("the closes are each holding's and each watched stock's last price", () => {
  expect(
    [...closesFrom(portfolio(2_500n), watchlist)].map(([symbol, close]) => [symbol, close.amount]),
  ).toEqual([
    ["TLKM", 2_500n],
    ["BBCA", 9_000n],
  ]);
});

test("a stock whose two pages disagree on its close is refused by name", () => {
  expect(() => closesFrom(portfolio(2_490n), watchlist)).toThrow(
    new Error("TLKM's last price is IDR 2,490 on the portfolio and IDR 2,500 on the watchlist"),
  );
});

test("a day with no orders pays no stamp duty, even before the exemption existed", () => {
  // On 2021-01-04 the duty is 10,000 on any traded amount (rules.test.ts); nothing traded pays none.
  const advice = advise({
    rules: RULES,
    limits: new RiskLimits(),
    stops: [],
    decision: decision({ weights: new Map() }),
    portfolio: {
      value: rp(100_000_000n),
      spendable: rp(0n),
      holdings: new Map([["TLKM", rp(5_000_000n)]]),
      held: new Map([["TLKM", 2_000n]]),
      invested: rp(4_000_000n),
    },
    tradable: { ...TRADABLE, day: "2021-01-04" },
    prices: PRICES,
    day: "2021-01-04",
  });
  expect(advice.orders).toEqual([]);
  expect(advice.stampDuty.amount).toBe(0n);
});

// Python's `Decision` refuses weights that cannot be a portfolio (`InvalidWeightsError`).

test.each([
  ["-0.01", "BBCA: a weight must be finite and not negative, got -0.01"],
  ["NaN", "BBCA: a weight must be finite and not negative, got NaN"],
])("a weight that cannot be a portfolio is a bug in the strategy: %s", (weight, message) => {
  const bad = decision({ weights: new Map([["BBCA", new RuleDecimal(weight)]]) });
  expect(() => run(50_000_000n, bad)).toThrow(new RangeError(message));
});

test("weights summing to more than 1 are a bug in the strategy", () => {
  const bad = decision({
    weights: new Map([
      ["BBCA", new RuleDecimal("0.6")],
      ["BBRI", new RuleDecimal("0.41")],
    ]),
  });
  expect(() => run(50_000_000n, bad)).toThrow(new RangeError("weights sum to 1.01, more than 1"));
});

test("weights summing to exactly 1 are allowed", () => {
  const whole = decision({
    weights: new Map([
      ["BBCA", new RuleDecimal("0.6")],
      ["BBRI", new RuleDecimal("0.4")],
    ]),
  });
  expect(run(50_000_000n, whole).orders.length).toBe(2);
});

test("a watchlist listing a stock twice is refused by name", () => {
  const twice: Watchlist = {
    stocks: [
      { symbol: "BBCA", lastPrice: rp(9_000n) },
      { symbol: "BBCA", lastPrice: rp(9_000n) },
    ],
  };
  expect(() => closesFrom(portfolio(2_500n), twice)).toThrow(
    new Error("the watchlist lists BBCA twice"),
  );
});

// EXT S12 (#236, spec §8): a halt, or a fact a halt needs that is missing, stops every buy;
// sells are still given.

const HALT = note(
  NOTE_CODES.RISK_HALT_DAILY_LOSS,
  "daily loss limit: the unit value fell 6.00%, the limit is 5.00%",
);

const SELLING = decision({
  weights: new Map([["BBCA", new RuleDecimal("0.1")]]),
});

const sellable = (stops: readonly Note[]) =>
  advise({
    rules: RULES,
    limits: new RiskLimits(),
    stops,
    decision: SELLING,
    portfolio: {
      value: rp(100_000_000n),
      spendable: rp(50_000_000n),
      holdings: new Map([["TLKM", rp(5_000_000n)]]),
      held: new Map([["TLKM", 2_000n]]),
      invested: rp(4_000_000n),
    },
    tradable: {
      ...TRADABLE,
      reasons: new Map(),
      buyable: new Set(["BBCA", "BBRI", "TLKM"]),
      sellable: new Set(["TLKM"]),
    },
    prices: PRICES,
    day: DAY,
  });

test("with nothing stopping it, the same day buys BBCA and sells TLKM", () => {
  const advice = sellable([]);
  expect(advice.orders.map((advised) => [advised.order.symbol, advised.order.side])).toEqual([
    ["TLKM", Side.SELL],
    ["BBCA", Side.BUY],
  ]);
  expect(advice.stops).toEqual([]);
});

test("a halt stops every buy, each rejected with the halt's note, and still sells", () => {
  const advice = sellable([HALT]);
  expect(advice.orders.map((advised) => [advised.order.symbol, advised.order.side])).toEqual([
    ["TLKM", Side.SELL],
  ]);
  expect(advice.rejected.map((rejected) => [rejected.order.symbol, rejected.reason])).toEqual([
    ["BBCA", HALT],
  ]);
  expect(advice.stops).toEqual([HALT]);
});

test("missing deposits stop every buy the same way, the first stop given as the reason", () => {
  const gap = missingDeposits("2025-05-30");
  const advice = sellable([gap, HALT]);
  expect(advice.orders.map((advised) => advised.order.side)).toEqual([Side.SELL]);
  expect(advice.rejected.map((rejected) => rejected.reason)).toEqual([gap]);
  expect(advice.stops).toEqual([gap, HALT]);
});

test("a strategy missing data under a halt still lists the halt", () => {
  const gap = missingPage("watchlist");
  const advice = run(50_000_000n, decision({ missing: [gap] }), [HALT]);
  expect([advice.orders, advice.missing, advice.stops]).toEqual([[], [gap], [HALT]]);
});
