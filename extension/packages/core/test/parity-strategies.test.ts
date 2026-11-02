import { expect, test } from "vitest";
import { buyAndHold } from "../src/buy-and-hold.ts";
import { IDR, Money } from "../src/money.ts";
import { monthlySavings } from "../src/monthly-savings.ts";
import { RuleDecimal } from "../src/ratio.ts";
import type { PortfolioView } from "../src/sizing.ts";
import type { MarketView, Strategy } from "../src/strategy.ts";
import fixture from "./parity-strategies.json" with { type: "json" };

// The parity harness for strategies (#229 AC6, spec §14.4): journeys of advice days that
// Python's buy-and-hold and monthly-savings decided (`scripts/core_fixtures.py`), each day from
// the memory the last one ended with. Core's strategies must give the same weights, memory and
// notes on every day.

interface Case {
  readonly name: string;
  readonly strategy: string;
  readonly instalments: string;
  readonly day: string;
  readonly buyable: readonly string[];
  readonly holdings: Readonly<Record<string, string>>;
  readonly value: string;
  readonly spendable: string;
  readonly memory: Readonly<Record<string, string>>;
  readonly expected: {
    readonly weights: Readonly<Record<string, string>>;
    readonly memory: Readonly<Record<string, string>>;
    readonly notes: readonly unknown[];
  };
}

/** A weight as a value: Python's `Decimal` keeps a trailing zero (`0.0550`) that decimal.js
 * drops (`0.055`), the same number. Read without rounding, so no other digit can differ. */
const valued = (weights: Readonly<Record<string, string>>) =>
  Object.fromEntries(
    Object.entries(weights).map(([symbol, weight]) => [symbol, new RuleDecimal(weight).toString()]),
  );

const CASES: readonly Case[] = fixture.cases;

const rp = (amount: string): Money => new Money(BigInt(amount), IDR);

const strategyOf = (parity: Case): Strategy => {
  if (parity.strategy === buyAndHold.name) {
    return buyAndHold;
  }
  if (parity.strategy === "monthly-savings") {
    return monthlySavings(BigInt(parity.instalments));
  }
  throw new Error(`the strategy parity fixture names ${parity.strategy}`);
};

const answer = (parity: Case) => {
  const view: MarketView = {
    day: parity.day,
    tradable: {
      day: parity.day,
      buyable: new Set(parity.buyable),
      sellable: new Set(),
      reasons: new Map(),
      members: new Set(parity.buyable),
    },
    closes: new Map(),
    dividends: new Map(),
    splits: [],
    unknownActions: new Map(),
    series: new Map(),
  };
  const portfolio: PortfolioView = {
    value: rp(parity.value),
    spendable: rp(parity.spendable),
    holdings: new Map(
      Object.entries(parity.holdings).map(([symbol, worth]) => [symbol, rp(worth)]),
    ),
  };
  const decision = strategyOf(parity).decide(
    view,
    portfolio,
    new Map(Object.entries(parity.memory)),
  );
  return {
    weights: Object.fromEntries(
      [...decision.weights]
        .sort(([first], [second]) => (first < second ? -1 : 1))
        .map(([symbol, weight]) => [symbol, weight.toString()]),
    ),
    memory: Object.fromEntries(decision.memory),
    notes: decision.notes.map((said) => ({ code: said.code, text: said.text })),
  };
};

test(`the harness compares ${CASES.length.toString()} strategy days from seed ${fixture.seed}`, () => {
  expect(CASES.length).toBeGreaterThan(0);
});

test.each(CASES)("core's $strategy decides $name as Python does", (parity) => {
  expect(
    answer(parity),
    `seed ${fixture.seed}, ${parity.name}: ${JSON.stringify({ ...parity, expected: undefined })}`,
  ).toEqual({ ...parity.expected, weights: valued(parity.expected.weights) });
});
