import { expect, test } from "vitest";
import type { Dividends, Split } from "../src/broker-view.ts";
import { runRate } from "../src/income.ts";
import { IDR, Money } from "../src/money.ts";
import { incomeGrowth, project } from "../src/projection.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { IdxMarketRules } from "../src/rules.ts";
import fixture from "./parity-projection.json" with { type: "json" };

// The parity harness for the income projection (#254 AC1, spec §9.1): seeded holdings with five
// years of dividends, falling, steady and growing past the optimistic cap, some with nothing in
// the earlier year and some split between the years, that Python's `dividend_growth` and
// `project` answered (`scripts/core_fixtures.py`). Core must give the same growth, a holding at a
// time and for the portfolio, the same short-history notes, and the same years in every
// scenario.

interface Stock {
  readonly symbol: string;
  readonly shares: string;
  readonly dividends: readonly {
    readonly exDate: string;
    readonly paymentDate: string;
    readonly perShare: string;
  }[];
  readonly splits: readonly {
    readonly exDate: string;
    readonly from: string;
    readonly to: string;
  }[];
}

interface Scenario {
  readonly scenario: string;
  readonly start: string;
  readonly growth: string;
  readonly outcome: string;
  readonly years: string | null;
}

interface Case {
  readonly name: string;
  readonly asOf: string;
  readonly holdingsValue: string;
  readonly target: string;
  readonly contribution: string;
  readonly stocks: readonly Stock[];
  readonly growth: readonly (readonly string[])[];
  readonly portfolioGrowth: string;
  readonly shortHistory: readonly string[];
  readonly scenarios: readonly Scenario[];
}

const RULES = new IdxMarketRules();
const CASES: readonly Case[] = fixture.cases;

const rp = (amount: string): Money => new Money(BigInt(amount), IDR);

const readOf = (stock: Stock, asOf: string): Dividends => ({
  symbol: stock.symbol,
  covered: { from: "2000-01-01", to: asOf },
  dividends: stock.dividends.map((row) => ({
    symbol: stock.symbol,
    exDate: row.exDate,
    paymentDate: row.paymentDate,
    grossPerShare: new RuleDecimal(row.perShare),
  })),
});

const splitsOf = (stock: Stock): Split[] =>
  stock.splits.map((split) => ({
    symbol: stock.symbol,
    exDate: split.exDate,
    from: BigInt(split.from),
    to: BigInt(split.to),
  }));

test(`the harness compares ${CASES.length.toString()} portfolios from seed ${fixture.seed}`, () => {
  expect(CASES.length).toBeGreaterThan(0);
});

test.each(CASES)("core's growth and projection for $name are Python's", (parity) => {
  const dividends = new Map(
    parity.stocks.map((stock) => [stock.symbol, readOf(stock, parity.asOf)]),
  );
  const splits = parity.stocks.flatMap(splitsOf);
  const read = runRate({
    rules: RULES,
    held: new Map(parity.stocks.map((stock) => [stock.symbol, BigInt(stock.shares)])),
    dividends,
    splits,
    unknownActions: new Map(),
    asOf: parity.asOf,
  });
  if (read.rate === null) {
    throw new Error(`${parity.name}: no run rate`);
  }
  const grown = incomeGrowth(read.rate, dividends, splits);
  if (grown.growth === null) {
    throw new Error(`${parity.name}: no growth`);
  }
  const growth = grown.growth;
  expect(
    growth.holdings.map((holding) => [
      holding.symbol,
      holding.recent.toString(),
      holding.earlier.toString(),
      holding.growth.toString(),
    ]),
  ).toEqual(
    parity.growth.map(([symbol = "", recent = "", earlier = "", rate = ""]) => [
      symbol,
      new RuleDecimal(recent).toString(),
      new RuleDecimal(earlier).toString(),
      new RuleDecimal(rate).toString(),
    ]),
  );
  expect(growth.portfolio.toString()).toBe(new RuleDecimal(parity.portfolioGrowth).toString());
  expect(growth.notes.map((found) => found.text.split(":")[0])).toEqual(parity.shortHistory);
  const projection = project({
    rate: read.rate,
    growth,
    holdingsValue: rp(parity.holdingsValue),
    target: rp(parity.target),
    contribution: rp(parity.contribution),
    rules: RULES,
  });
  expect(
    projection.scenarios.map((found) => ({
      scenario: found.scenario,
      start: found.start.amount.toString(),
      growth: found.growth.toString(),
      outcome: found.outcome,
      years: found.years === null ? null : found.years.toFixed(1),
    })),
  ).toEqual(
    parity.scenarios.map((found) => ({
      ...found,
      growth: new RuleDecimal(found.growth).toString(),
    })),
  );
});
