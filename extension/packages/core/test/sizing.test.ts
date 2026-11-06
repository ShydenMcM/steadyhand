import type Decimal from "decimal.js";
import { expect, test } from "vitest";
import type { Holding, Portfolio } from "../src/broker-view.ts";
import { Side } from "../src/costs.ts";
import { IDR, Money, Rounding } from "../src/money.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { IdxMarketRules } from "../src/rules.ts";
import { portfolioView, sizeOrders, type Order, type PortfolioView } from "../src/sizing.ts";

// Ported from Python's tests/engine/test_sizing.py, one test per case.

const DAY = "2025-06-02";
const PRICES: ReadonlyMap<string, Money> = new Map([
  ["BBCA", new Money(9_000n, IDR)],
  ["BBRI", new Money(4_000n, IDR)],
  ["TLKM", new Money(2_500n, IDR)],
]);

const RULES = new IdxMarketRules();

const rp = (amount: bigint): Money => new Money(amount, IDR);

const price = (symbol: string): Money => {
  const found = PRICES.get(symbol);
  if (found === undefined) {
    throw new Error(`no test price for ${symbol}`);
  }
  return found;
};

const view = (value: bigint, held: ReadonlyMap<string, bigint>): PortfolioView => ({
  value: rp(value),
  spendable: rp(0n),
  holdings: new Map([...held].map(([symbol, shares]) => [symbol, price(symbol).times(shares)])),
});

const order = (symbol: string, side: Side, quantity: bigint): Order => ({
  symbol,
  side,
  quantity,
  day: DAY,
});

const size = (
  weights: Readonly<Record<string, string>>,
  value: bigint,
  held: Readonly<Record<string, bigint>> = {},
): readonly Order[] => {
  const shares = new Map(Object.entries(held));
  const decimals = new Map(
    Object.entries(weights).map(([symbol, weight]) => [symbol, new RuleDecimal(weight)]),
  );
  return sizeOrders(RULES, decimals, view(value, shares), shares, PRICES, DAY);
};

test("a weight becomes whole lots at the last close rounded down: 0.5", () => {
  expect(size({ BBCA: "0.5" }, 10_000_000n)).toEqual([order("BBCA", Side.BUY, 500n)]);
});

test("a weight becomes whole lots at the last close rounded down: 0.54", () => {
  expect(size({ BBCA: "0.54" }, 10_000_000n)).toEqual([order("BBCA", Side.BUY, 600n)]);
});

test("a weight becomes whole lots at the last close rounded down: 0.53999", () => {
  expect(size({ BBCA: "0.53999" }, 10_000_000n)).toEqual([order("BBCA", Side.BUY, 500n)]);
});

test("sizes grow with the portfolio", () => {
  expect(size({ BBCA: "0.5" }, 20_000_000n)).toEqual([order("BBCA", Side.BUY, 1_100n)]);
});

test("a stock missing from the weights is sold", () => {
  expect(size({}, 10_000_000n, { BBCA: 200n })).toEqual([order("BBCA", Side.SELL, 200n)]);
});

test("a target within a lot of the holding places no order: 0.18", () => {
  expect(size({ BBCA: "0.18" }, 10_000_000n, { BBCA: 200n })).toEqual([]);
});

test("a target within a lot of the holding places no order: 0.26999", () => {
  expect(size({ BBCA: "0.26999" }, 10_000_000n, { BBCA: 200n })).toEqual([]);
});

test("a target a full lot above the holding buys it: 0.27", () => {
  expect(size({ BBCA: "0.27" }, 10_000_000n, { BBCA: 200n })).toEqual([
    order("BBCA", Side.BUY, 100n),
  ]);
});

test("a target a full lot below the holding sells it: 0.09", () => {
  expect(size({ BBCA: "0.09" }, 10_000_000n, { BBCA: 200n })).toEqual([
    order("BBCA", Side.SELL, 100n),
  ]);
});

test("a sale is whole lots of what is held: 150 shares sell 100", () => {
  expect(size({}, 10_000_000n, { BBCA: 150n })).toEqual([order("BBCA", Side.SELL, 100n)]);
});

test("a sale is whole lots of what is held: 50 shares sell nothing", () => {
  expect(size({}, 10_000_000n, { BBCA: 50n })).toEqual([]);
});

test("sells come first, then buys, each by symbol", () => {
  const orders = size({ TLKM: "0.1", BBCA: "0.2" }, 10_000_000n, { BBRI: 500n });
  expect(orders.map((placed) => [placed.side, placed.symbol])).toEqual([
    [Side.SELL, "BBRI"],
    [Side.BUY, "BBCA"],
    [Side.BUY, "TLKM"],
  ]);
});

test("a stock with no price cannot be sized", () => {
  expect(() => size({ GOTO: "0.1" }, 10_000_000n)).toThrow(
    new Error("no price for GOTO on 2025-06-02 to size it with"),
  );
});

// The stand-in cases of Python's sizing property (#290), worked by hand there: nothing at all,
// all cash at the largest value, all held with no weights, and a mix of both sides.
interface SizingCase {
  readonly name: string;
  readonly value: bigint;
  readonly weights: Readonly<Record<Stock, bigint>>;
  readonly held: Readonly<Record<Stock, bigint>>;
  readonly expected: readonly Order[];
}

const STOCKS: readonly Stock[] = ["BBCA", "BBRI", "TLKM"];
type Stock = "BBCA" | "BBRI" | "TLKM";

const SIZING_CASES: readonly SizingCase[] = [
  {
    name: "nothing",
    value: 0n,
    weights: { BBCA: 0n, BBRI: 0n, TLKM: 0n },
    held: { BBCA: 0n, BBRI: 0n, TLKM: 0n },
    expected: [],
  },
  {
    name: "all-cash",
    value: 10n ** 10n,
    weights: { BBCA: 1_000n, BBRI: 1_000n, TLKM: 1_000n },
    held: { BBCA: 0n, BBRI: 0n, TLKM: 0n },
    expected: [
      order("BBCA", Side.BUY, 185_100n),
      order("BBRI", Side.BUY, 416_600n),
      order("TLKM", Side.BUY, 666_600n),
    ],
  },
  {
    name: "all-held",
    value: 0n,
    weights: { BBCA: 0n, BBRI: 0n, TLKM: 0n },
    held: { BBCA: 5_000n, BBRI: 5_000n, TLKM: 5_000n },
    expected: [
      order("BBCA", Side.SELL, 5_000n),
      order("BBRI", Side.SELL, 5_000n),
      order("TLKM", Side.SELL, 5_000n),
    ],
  },
  {
    name: "mix",
    value: 1_234_567n,
    weights: { BBCA: 1n, BBRI: 500n, TLKM: 1_000n },
    held: { BBCA: 100n, BBRI: 0n, TLKM: 4_999n },
    expected: [order("TLKM", Side.SELL, 3_000n), order("BBRI", Side.BUY, 600n)],
  },
];

interface Sized {
  readonly decimals: ReadonlyMap<string, Decimal>;
  readonly shares: ReadonlyMap<string, bigint>;
  readonly portfolio: PortfolioView;
  readonly orders: readonly Order[];
}

/** Each stock weighted half its share of `weights`, the shares `held`, the portfolio worth them and
 * `value` more, and the sizer's orders on them. */
const sized = (sizing: SizingCase): Sized => {
  const total = STOCKS.reduce((sum, symbol) => sum + sizing.weights[symbol], 0n) || 1n;
  const decimals = new Map(
    STOCKS.map((symbol) => [
      symbol,
      new RuleDecimal(String(sizing.weights[symbol])).div(String(total)).div(2),
    ]),
  );
  const shares = new Map(
    STOCKS.filter((symbol) => sizing.held[symbol] > 0n).map((symbol) => [
      symbol,
      sizing.held[symbol],
    ]),
  );
  const worth = [...shares].reduce((sum, [symbol, held]) => sum + price(symbol).amount * held, 0n);
  const portfolio = view(worth + sizing.value, shares);
  return {
    decimals,
    shares,
    portfolio,
    orders: sizeOrders(RULES, decimals, portfolio, shares, PRICES, DAY),
  };
};

test.each(SIZING_CASES)(
  "orders are whole lots that never overshoot the target: $name",
  (sizing) => {
    const { decimals, shares, portfolio, orders } = sized(sizing);
    for (const placed of orders) {
      const weight = decimals.get(placed.symbol);
      expect(weight).toBeDefined();
      expect(placed.quantity % 100n).toBe(0n);
      const target = portfolio.value.timesRate(weight ?? new RuleDecimal(0), Rounding.DOWN).amount;
      const held = shares.get(placed.symbol) ?? 0n;
      const current = price(placed.symbol).amount * held;
      const traded = price(placed.symbol).amount * placed.quantity;
      if (placed.side === Side.BUY) {
        expect(current + traded <= target).toBe(true);
      } else {
        expect(placed.quantity <= held).toBe(true);
        expect(target <= current - traded).toBe(true);
      }
    }
  },
);

test.each(SIZING_CASES)("each stand-in case's orders are worked by hand: $name", (sizing) => {
  expect(sized(sizing).orders).toEqual(sizing.expected);
});

// The broker's portfolio as the sizer sees it (spec §4.4): value is all cash plus holdings at
// the advice day's close; the unsettled balance is signed, so a buy not yet settled lowers it.

const holding = (symbol: string, lots: bigint, last: bigint): Holding => ({
  symbol,
  lots,
  averagePrice: rp(1n),
  lastPrice: rp(last),
});

const brokerPortfolio = (holdings: readonly Holding[]): Portfolio => ({
  cashAvailable: rp(3_000_000n),
  cashSettled: rp(5_000_000n),
  cashUnsettled: rp(-1_250_000n),
  holdings,
});

test("the value is settled and unsettled cash plus each holding at its last price", () => {
  const seen = portfolioView(RULES, brokerPortfolio([holding("BBCA", 2n, 9_000n)]), DAY);
  expect(seen.value.equals(rp(5_000_000n - 1_250_000n + 1_800_000n))).toBe(true);
});

test("what may be spent is the cash the broker says is available to buy", () => {
  expect(portfolioView(RULES, brokerPortfolio([]), DAY).spendable.equals(rp(3_000_000n))).toBe(
    true,
  );
});

test("cash available to buy above the cash balance is spent only up to the balance", () => {
  const credit = { ...brokerPortfolio([]), cashAvailable: rp(4_000_000n) };
  expect(portfolioView(RULES, credit, DAY).spendable.amount).toBe(5_000_000n - 1_250_000n);
});

test("with a cash balance below nothing, nothing is spent", () => {
  const owing = { ...brokerPortfolio([]), cashSettled: rp(1_000_000n) };
  expect(portfolioView(RULES, owing, DAY).spendable.amount).toBe(0n);
});

test("each holding is worth its lots, in shares, at its last price", () => {
  const seen = portfolioView(RULES, brokerPortfolio([holding("BBCA", 2n, 9_000n)]), DAY);
  expect([...seen.holdings].map(([symbol, worth]) => [symbol, worth.amount])).toEqual([
    ["BBCA", 1_800_000n],
  ]);
});

test("the shares held are each holding's lots times the lot size", () => {
  const seen = portfolioView(RULES, brokerPortfolio([holding("BBCA", 3n, 9_000n)]), DAY);
  expect([...seen.held]).toEqual([["BBCA", 300n]]);
});

test("a stock listed twice in the portfolio is refused by name", () => {
  const twice = brokerPortfolio([holding("BBCA", 1n, 9_000n), holding("BBCA", 2n, 9_000n)]);
  expect(() => portfolioView(RULES, twice, DAY)).toThrow(
    new Error("the portfolio lists BBCA twice"),
  );
});

test("a weighted stock valued above its target but with no shares given sells nothing", () => {
  // Python's `held.get(instrument, 0)`: only shares given as held are ever sold.
  const portfolio = view(10_000_000n, new Map([["BBCA", 200n]]));
  const weights = new Map([["BBCA", new RuleDecimal("0.05")]]);
  expect(sizeOrders(RULES, weights, portfolio, new Map(), PRICES, DAY)).toEqual([]);
});
