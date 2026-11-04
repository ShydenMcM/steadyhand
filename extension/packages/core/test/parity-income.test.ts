import { expect, test } from "vitest";
import type { Dividends, Split } from "../src/broker-view.ts";
import { goalProgress, paymentCalendar, runRate } from "../src/income.ts";
import { IDR, Money } from "../src/money.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { IdxMarketRules } from "../src/rules.ts";
import fixture from "./parity-income.json" with { type: "json" };

// The parity harness for the income goal (#237 AC4, spec §9, §14.4): seeded holdings with
// dividends around the trailing year and splits after some of them, that Python's `run_rate`,
// `_share` and `payment_calendar` answered (`scripts/core_fixtures.py`). Each dividend's
// payment date is the one Python models; core reads it from the broker. Core must give the same
// rupiah, share and months.

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

interface Case {
  readonly name: string;
  readonly asOf: string;
  readonly target: string;
  readonly stocks: readonly Stock[];
  readonly holdings: readonly (readonly string[])[];
  readonly annualGross: string;
  readonly monthlyTakeHome: string;
  readonly share: string;
  readonly months: readonly string[];
  readonly emptyMonths: string;
  readonly evenness: string | null;
}

const RULES = new IdxMarketRules();
const CASES: readonly Case[] = fixture.cases;

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

test.each(CASES)("core's income for $name is Python's", (parity) => {
  const found = runRate({
    rules: RULES,
    held: new Map(parity.stocks.map((stock) => [stock.symbol, BigInt(stock.shares)])),
    dividends: new Map(parity.stocks.map((stock) => [stock.symbol, readOf(stock, parity.asOf)])),
    splits: parity.stocks.flatMap(splitsOf),
    unknownActions: new Map(),
    asOf: parity.asOf,
  });
  if (found.rate === null) {
    throw new Error(`${parity.name} has no run rate: ${JSON.stringify(found.missing)}`);
  }
  const rate = found.rate;
  const months = paymentCalendar(rate, RULES);
  const share = goalProgress(new Money(BigInt(parity.target), IDR), rate).runRateShare;
  expect(
    {
      holdings: rate.holdings.map((holding) => [
        holding.annualGross.amount.toString(),
        holding.monthlyTakeHome.amount.toString(),
      ]),
      annualGross: rate.annualGross.amount.toString(),
      monthlyTakeHome: rate.monthlyTakeHome.amount.toString(),
      share: share.toString(),
      months: months.months.map((month) => month.amount.toString()),
      emptyMonths: months.emptyMonths.toString(),
      evenness: months.evenness === null ? null : months.evenness.toString(),
    },
    `seed ${fixture.seed}, ${parity.name}`,
  ).toEqual({
    holdings: parity.holdings,
    annualGross: parity.annualGross,
    monthlyTakeHome: parity.monthlyTakeHome,
    share: new RuleDecimal(parity.share).toString(),
    months: parity.months,
    emptyMonths: parity.emptyMonths,
    evenness: parity.evenness === null ? null : new RuleDecimal(parity.evenness).toString(),
  });
});
