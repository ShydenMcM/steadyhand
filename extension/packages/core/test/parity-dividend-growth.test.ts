import { expect, test } from "vitest";
import type { Dividends } from "../src/broker-view.ts";
import { dividendGrowth } from "../src/dividend-growth.ts";
import { IDR, Money } from "../src/money.ts";
import { RuleDecimal } from "../src/ratio.ts";
import type { PortfolioView } from "../src/sizing.ts";
import type { MarketView } from "../src/strategy.ts";
import fixture from "./parity-dividend-growth.json" with { type: "json" };

// The parity harness for dividend-growth (#230 AC5, spec §14.4): journeys of advice days that
// Python's dividend-growth decided (`scripts/core_fixtures.py`), each day from the memory the
// last one ended with. Core must give the same weights, memory and notes on every day. On a
// review day every stock's whole record is read, from long before the look-back to the advice
// day; between reviews nothing is read, as the strategy reads no dividends then. Pay dates are
// Python's modelled ones, standing in for the broker's.

interface Case {
  readonly name: string;
  readonly minStocks: string;
  readonly maxStocks: string;
  readonly growthYears: string;
  readonly day: string;
  readonly members: readonly string[];
  readonly buyable: readonly string[];
  readonly holdings: Readonly<Record<string, string>>;
  readonly value: string;
  readonly spendable: string;
  readonly closes: Readonly<Record<string, string>>;
  readonly dividends: readonly {
    readonly symbol: string;
    readonly exDate: string;
    readonly paymentDate: string;
    readonly grossPerShare: string;
  }[];
  readonly splits: readonly {
    readonly symbol: string;
    readonly exDate: string;
    readonly from: string;
    readonly to: string;
  }[];
  readonly read: boolean;
  readonly memory: Readonly<Record<string, string>>;
  readonly expected: {
    readonly weights: Readonly<Record<string, string>>;
    readonly memory: Readonly<Record<string, string>>;
    readonly notes: readonly unknown[];
  };
}

const CASES: readonly Case[] = fixture.cases;

const rp = (amount: string): Money => new Money(BigInt(amount), IDR);

/** A weight as a value: Python's `Decimal` keeps a trailing zero (`0.0550`) that decimal.js
 * drops (`0.055`), the same number. Read without rounding, so no other digit can differ. */
const valued = (weights: Readonly<Record<string, string>>) =>
  Object.fromEntries(
    Object.entries(weights).map(([symbol, weight]) => [symbol, new RuleDecimal(weight).toString()]),
  );

/** Each member's dividend read on a review day: its whole record, to the advice day. */
const readsOf = (parity: Case): Map<string, Dividends> =>
  new Map(
    parity.read
      ? parity.members.map((symbol) => [
          symbol,
          {
            symbol,
            covered: { from: "2000-01-01", to: parity.day },
            dividends: parity.dividends
              .filter((row) => row.symbol === symbol)
              .map((row) => ({
                symbol,
                exDate: row.exDate,
                paymentDate: row.paymentDate,
                grossPerShare: new RuleDecimal(row.grossPerShare),
              })),
          },
        ])
      : [],
  );

const answer = (parity: Case) => {
  const view: MarketView = {
    day: parity.day,
    tradable: {
      day: parity.day,
      buyable: new Set(parity.buyable),
      sellable: new Set(),
      reasons: new Map(),
      members: new Set(parity.members),
    },
    closes: new Map(Object.entries(parity.closes).map(([symbol, price]) => [symbol, rp(price)])),
    dividends: readsOf(parity),
    splits: parity.splits.map((split) => ({
      symbol: split.symbol,
      exDate: split.exDate,
      from: BigInt(split.from),
      to: BigInt(split.to),
    })),
  };
  const portfolio: PortfolioView = {
    value: rp(parity.value),
    spendable: rp(parity.spendable),
    holdings: new Map(
      Object.entries(parity.holdings).map(([symbol, worth]) => [symbol, rp(worth)]),
    ),
  };
  const strategy = dividendGrowth(
    BigInt(parity.minStocks),
    BigInt(parity.maxStocks),
    BigInt(parity.growthYears),
  );
  const decision = strategy.decide(view, portfolio, new Map(Object.entries(parity.memory)));
  return {
    missing: decision.missing,
    weights: Object.fromEntries(
      [...decision.weights]
        .sort(([first], [second]) => (first < second ? -1 : 1))
        .map(([symbol, weight]) => [symbol, weight.toString()]),
    ),
    memory: Object.fromEntries(decision.memory),
    notes: decision.notes.map((said) => ({ code: said.code, text: said.text })),
  };
};

test(`the harness compares ${CASES.length.toString()} dividend-growth days from seed ${fixture.seed}`, () => {
  expect(CASES.length).toBeGreaterThan(0);
});

test.each(CASES)("core's dividend-growth decides $name as Python does", (parity) => {
  expect(answer(parity), `seed ${fixture.seed} ${parity.name}: ${JSON.stringify(parity)}`).toEqual({
    missing: [],
    weights: valued(parity.expected.weights),
    memory: parity.expected.memory,
    notes: parity.expected.notes,
  });
});
