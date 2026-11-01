import { expect, test } from "vitest";
import { Side } from "../src/costs.ts";
import { IDR, Money } from "../src/money.ts";
import { note, type Note } from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { checkOrders, RiskLimits } from "../src/risk.ts";
import { IdxMarketRules } from "../src/rules.ts";
import { sizeOrders, type Order, type PortfolioView } from "../src/sizing.ts";
import type { Tradable } from "../src/tradable.ts";
import fixture from "./parity.json" with { type: "json" };

// The parity harness (#228, spec §14.4): seeded cases that Python's `CompoundingSizer` and
// `RiskManager` answered (`scripts/core_fixtures.py`), each of which core's sizing and risk must
// answer identically, notes included. Strategies and the income run rate join it in their own
// stories (EXT S7a, S7b, S13). It is removed only when the port is finished, with Shyden's
// agreement.

interface WrittenOrder {
  readonly symbol: string;
  readonly side: string;
  readonly quantity: string;
  readonly day: string;
}

interface Case {
  readonly name: string;
  readonly day: string;
  readonly prices: Readonly<Record<string, string>>;
  readonly held: Readonly<Record<string, string>>;
  readonly weights: Readonly<Record<string, string>>;
  readonly value: string;
  readonly spendable: string;
  readonly holdings: Readonly<Record<string, string>>;
  readonly limits: { readonly max_weight: string; readonly min_lots: string };
  readonly extra: readonly WrittenOrder[];
  readonly members: readonly string[];
  readonly reasons: Readonly<Record<string, { readonly code: string; readonly text: string }>>;
  readonly expected: unknown;
}

const RULES = new IdxMarketRules();
const CASES: readonly Case[] = fixture.cases;

const rp = (amount: string): Money => new Money(BigInt(amount), IDR);

const sideOf = (text: string): Side => {
  if (text === Side.BUY || text === Side.SELL) {
    return text;
  }
  throw new Error(`the parity fixture has an order on side ${text}`);
};

const read = (order: WrittenOrder): Order => ({
  symbol: order.symbol,
  side: sideOf(order.side),
  quantity: BigInt(order.quantity),
  day: order.day,
});

const written = (order: Order): WrittenOrder => ({
  symbol: order.symbol,
  side: order.side,
  quantity: order.quantity.toString(),
  day: order.day,
});

const coded = (reason: Note) => ({ code: reason.code, text: reason.text });

/** Core's answer to `parity`, written as Python's is. */
const answer = (parity: Case) => {
  const prices = new Map(
    Object.entries(parity.prices).map(([symbol, price]) => [symbol, rp(price)]),
  );
  const held = new Map(
    Object.entries(parity.held).map(([symbol, shares]) => [symbol, BigInt(shares)]),
  );
  const weights = new Map(
    Object.entries(parity.weights).map(([symbol, weight]) => [symbol, new RuleDecimal(weight)]),
  );
  const portfolio: PortfolioView = {
    value: rp(parity.value),
    spendable: rp(parity.spendable),
    holdings: new Map(
      Object.entries(parity.holdings).map(([symbol, worth]) => [symbol, rp(worth)]),
    ),
  };
  const reasons = new Map(
    Object.entries(parity.reasons).map(([symbol, reason]) => [
      symbol,
      note(reason.code, reason.text),
    ]),
  );
  const free = (symbol: string): boolean => !reasons.has(symbol);
  const tradable: Tradable = {
    day: parity.day,
    buyable: new Set(parity.members.filter(free)),
    sellable: new Set([...held.keys()].filter(free)),
    reasons,
    members: new Set(parity.members),
  };
  const limits = new RiskLimits({
    maxWeight: new RuleDecimal(parity.limits.max_weight),
    minLots: BigInt(parity.limits.min_lots),
  });
  const sized = sizeOrders(RULES, weights, portfolio, held, prices, parity.day);
  const checked = checkOrders(
    RULES,
    limits,
    [...sized, ...parity.extra.map(read)],
    portfolio,
    tradable,
    prices,
  );
  return {
    sized: sized.map(written),
    orders: checked.orders.map(written),
    rejected: checked.rejected.map((dropped) => ({
      order: written(dropped.order),
      ...coded(dropped.reason),
    })),
    cuts: checked.cuts.map((cut) => ({
      order: written(cut.order),
      quantity: cut.quantity.toString(),
      ...coded(cut.reason),
    })),
  };
};

test(`the harness compares ${CASES.length.toString()} cases from seed ${fixture.seed}`, () => {
  expect(CASES.length).toBeGreaterThan(0);
});

test.each(CASES)("core sizes and checks $name as Python does", (parity) => {
  expect(
    answer(parity),
    `seed ${fixture.seed}, ${parity.name}: ${JSON.stringify({ ...parity, expected: undefined })}`,
  ).toEqual(parity.expected);
});
