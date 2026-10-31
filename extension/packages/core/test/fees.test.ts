import Decimal from "decimal.js";
import { expect, test } from "vitest";
import shipped from "../rules/fees.json" with { type: "json" };
import { Side } from "../src/costs.ts";
import {
  dailyCosts,
  dividendTax,
  feePreset,
  feeTables,
  levyWithVat,
  parseFees,
  protectionEnd,
  reinvestmentDeadline,
  tradeCosts,
  type FeeSchedule,
} from "../src/fees.ts";
import { Currency, IDR, Money } from "../src/money.ts";
import { RulesFileError, type Dated } from "../src/rules-file.ts";

// Ported from Python's tests/idx/test_fees.py, one test per case: the reading cases (#223), and
// the cost arithmetic with its check that an all-in quote covers what it includes (#224).

type Document = Record<string, unknown> & {
  levy: Record<string, unknown>[];
  vat: Record<string, unknown>[];
  dividend_exemption: Record<string, unknown>[];
  presets: Record<string, Record<string, unknown>>;
};

/** A fresh copy of the shipped document, to change one value of. */
const documentCopy = (): Document => structuredClone(shipped);

const rowOf = (rows: Record<string, unknown>[], position: number): Record<string, unknown> => {
  const row = rows.at(position);
  if (row === undefined) {
    throw new Error("the shipped fee table is shorter than the test expects");
  }
  return row;
};

const presetOf = (document: Document, name: string): Record<string, unknown> => {
  const preset = document.presets[name];
  if (preset === undefined) {
    throw new Error(`the shipped fees have no preset ${name}`);
  }
  return preset;
};

/** The rows of a dated table as the file writes them, `write` giving each row's own keys. */
const asWritten = <T>(
  table: Dated<T>,
  rows: readonly { source: string }[],
  write: (value: T) => Record<string, string>,
): Record<string, string>[] =>
  table.entries.map(([from, value], position) => ({
    from,
    source: rows.at(position)?.source ?? "",
    ...write(value),
  }));

const rate = (value: { toString: () => string }): Record<string, string> => ({
  rate_percent: value.toString(),
});

/** `rows` with each of `keys` written as decimal.js writes the decimal, which drops trailing zeros
 * (`0.010` reads back as `0.01`), so values are compared, not spellings. */
const normalised = <R extends Record<string, unknown>>(rows: readonly R[], keys: string[]): R[] =>
  rows.map((row) => ({
    ...row,
    ...Object.fromEntries(
      keys
        .filter((key) => key in row)
        .map((key) => [key, new Decimal(String(row[key])).toString()]),
    ),
  }));

const LEVY_KEYS = [
  "exchange_percent",
  "clearing_percent",
  "settlement_percent",
  "guarantee_fund_percent",
];

const schedule: FeeSchedule = parseFees(shipped);

test("every levy row of the shipped file is read as the file states it", () => {
  expect(
    asWritten(schedule.levy, shipped.levy, (levy) => ({
      exchange_percent: levy.exchange.toString(),
      clearing_percent: levy.clearing.toString(),
      settlement_percent: levy.settlement.toString(),
      guarantee_fund_percent: levy.guaranteeFund.toString(),
    })),
  ).toEqual(normalised(shipped.levy, LEVY_KEYS));
});

test("every rate row of the shipped file is read as the file states it", () => {
  const rates = ["rate_percent"];
  expect(asWritten(schedule.vat, shipped.vat, rate)).toEqual(normalised(shipped.vat, rates));
  expect(asWritten(schedule.saleTax, shipped.sale_tax, rate)).toEqual(
    normalised(shipped.sale_tax, rates),
  );
  expect(asWritten(schedule.dividendTaxRate, shipped.dividend_tax, rate)).toEqual(
    normalised(shipped.dividend_tax, rates),
  );
});

test("every stamp duty row of the shipped file is read as the file states it", () => {
  expect(
    asWritten(schedule.stampDuty, shipped.stamp_duty, (duty) => ({
      amount_rupiah: String(duty.amount),
      exempt_up_to_rupiah: String(duty.exemptUpTo),
    })),
  ).toEqual(shipped.stamp_duty);
});

test("every exemption row of the shipped file is read as the file states it", () => {
  expect(
    asWritten(schedule.dividendExemption, shipped.dividend_exemption, (exemption) =>
      exemption === null
        ? {}
        : {
            reinvest_by_month: String(exemption.reinvestByMonth),
            hold_tax_years: String(exemption.holdTaxYears),
          },
    ),
  ).toEqual(shipped.dividend_exemption);
});

test("every preset of the shipped file is read as the file states it", () => {
  expect(
    Object.fromEntries(
      [...schedule.presets].map(([name, preset]) => [
        name,
        {
          source: preset.source,
          ...(preset.checked === null ? {} : { checked: preset.checked }),
          buy_percent: preset.buy.toString(),
          sell_percent: preset.sell.toString(),
          includes: [...preset.includes],
        },
      ]),
    ),
  ).toEqual(
    Object.fromEntries(
      Object.entries(shipped.presets).map(([name, preset]) => [
        name,
        normalised([preset], ["buy_percent", "sell_percent"])[0],
      ]),
    ),
  );
});

test("the tables start where their rows are verified", () => {
  expect(schedule.levy.first).toBe("2020-03-13");
  expect(schedule.stampDuty.first).toBe("2021-01-01");
  expect(schedule.dividendExemption.on("2021-02-16")).toBeNull();
  expect(schedule.dividendExemption.on("2021-02-17")).toEqual({
    reinvestByMonth: 3n,
    holdTaxYears: 3n,
  });
});

test("a planted changed row goes red: a levy rate that is no decimal", () => {
  const document = documentCopy();
  rowOf(document.levy, 0).exchange_percent = "0.0l8";
  expect(() => parseFees(document)).toThrow(
    new RulesFileError(
      'fees.json [[levy]] row 1: exchange_percent must be a decimal of at least 0, such as 0.018, got "0.0l8"',
    ),
  );
});

test.each([
  [["levy", "levy"], 'includes may list each of commission_vat, levy, sale_tax once, got "levy"'],
  [["broker"], 'includes may list each of commission_vat, levy, sale_tax once, got "broker"'],
])("includes %j is checked", (includes, message) => {
  const document = documentCopy();
  presetOf(document, "custom").includes = includes;
  expect(() => parseFees(document)).toThrow(
    new RulesFileError(`fees.json [presets.custom]: ${message}`),
  );
});

test("a preset that is not a table is refused", () => {
  const document = documentCopy();
  document.presets.broken = 5 as unknown as Record<string, unknown>;
  expect(() => parseFees(document)).toThrow(
    new RulesFileError("fees.json [presets.broken] must be a table"),
  );
});

test.each([{}, [], "x"])("presets %j are refused", (presets) => {
  expect(() => parseFees({ ...shipped, presets })).toThrow(
    new RulesFileError("fees.json [presets] must be a table with at least one preset"),
  );
});

test("a levy row with an unknown key is refused", () => {
  const document = documentCopy();
  rowOf(document.levy, 0).exchange = "0.018";
  expect(() => parseFees(document)).toThrow(
    new RulesFileError("fees.json [[levy]] row 1: unknown key 'exchange'"),
  );
});

test("a row without its source is refused", () => {
  const document = documentCopy();
  delete rowOf(document.vat, 0).source;
  expect(() => parseFees(document)).toThrow(
    new RulesFileError("fees.json [[vat]] row 1: missing key 'source'"),
  );
});

test("a checked day that is no date is refused", () => {
  const document = documentCopy();
  presetOf(document, "ajaib").checked = "2026-02-30";
  expect(() => parseFees(document)).toThrow(
    /fees\.json \[presets\.ajaib\]: checked must be a date such as 2021-01-04/u,
  );
});

test("an unknown top-level table is refused", () => {
  expect(() => parseFees({ ...shipped, levies: [] })).toThrow(
    new RulesFileError("fees.json [top level]: unknown key 'levies'"),
  );
});

test.each([
  [
    { hold_tax_years: null },
    "an exemption row gives both counts or neither, and lacks 'hold_tax_years'",
  ],
  [
    { reinvest_by_month: null },
    "an exemption row gives both counts or neither, and lacks 'reinvest_by_month'",
  ],
  [{ reinvest_by_month: "13" }, "reinvest_by_month must be a month from 1 to 12, got 13"],
  [{ reinvest_by_month: "0" }, 'reinvest_by_month must be an integer of at least 1, got "0"'],
  [{ hold_tax_years: "0" }, 'hold_tax_years must be an integer of at least 1, got "0"'],
  [{ months: "3" }, "unknown key 'months'"],
])("a bad exemption row %j is refused", (change, message) => {
  const document = documentCopy();
  const row = rowOf(document.dividend_exemption, 1);
  for (const [key, value] of Object.entries(change)) {
    if (value === null) {
      Reflect.deleteProperty(row, key);
    } else {
      row[key] = value;
    }
  }
  expect(() => parseFees(document)).toThrow(
    new RulesFileError(`fees.json [[dividend_exemption]] row 2: ${message}`),
  );
});

test("a file read by hand uses its own name", () => {
  expect(() => parseFees({ schema: "1" }, "mine.json")).toThrow(
    new RulesFileError("mine.json [presets] must be a table with at least one preset"),
  );
});

const fees = (): FeeSchedule => parseFees(shipped);

const TODAY = "2026-09-25";

const rp = (amount: bigint): Money => new Money(amount, IDR);

const USD = new Currency("USD", 2n);

test.each([
  // t-fees.md §1.5 and t-verify.md §2: the levy per side, VAT included.
  ["2020-03-13", "0.0430"],
  ["2020-06-17", "0.0430"],
  ["2020-06-18", "0.0380"],
  ["2020-12-17", "0.0380"],
  ["2020-12-18", "0.0430"],
  ["2022-03-31", "0.0430"],
  ["2022-04-01", "0.0433"],
  ["2025-01-01", "0.0433"],
])("the levy on %s is %s%%, as the research says", (on, levy) => {
  const schedule = fees();
  expect(levyWithVat(schedule.levy.on(on), schedule.vat.on(on)).eq(new Decimal(levy))).toBe(true);
});

test("every dated table starts where its rows are verified", () => {
  expect(feeTables(fees()).map((table) => table.first)).toEqual([
    "2020-03-13", // levy
    "2016-01-01", // VAT
    "2016-01-01", // sale tax
    "2021-01-01", // stamp duty
    "2009-01-01", // dividend tax
    "2009-01-01", // dividend exemption: none until PMK 18/2021
  ]);
});

test.each([
  ["custom", Side.BUY, 20_980n], // 0.15% x 1.11 + 0.0433% = 0.2098%
  ["custom", Side.SELL, 30_980n], // plus the 0.1% sale tax
  ["ajaib", Side.BUY, 15_130n], // all-in 0.1513%
  ["ajaib", Side.SELL, 25_130n], // all-in 0.2513%
])("worked example on ten million: %s %s costs %s", (preset, side, total) => {
  const schedule = fees();
  const costs = tradeCosts(schedule, feePreset(schedule, preset), side, rp(10_000_000n), TODAY);
  expect(costs.total.amount).toBe(total);
  expect(costs.levy.amount).toBe(4_330n);
  expect(costs.tax.amount).toBe(side === Side.SELL ? 10_000n : 0n);
});

test("every trade's fee is marked an estimate", () => {
  const schedule = fees();
  expect(tradeCosts(schedule, feePreset(schedule, "custom"), Side.BUY, rp(1n), TODAY).estimate).toBe(
    true,
  );
});

test("an all-in quote keeps its total when the levy was lower", () => {
  // 18 Jun - 17 Dec 2020 the levy was 0.038%, so more of Ajaib's 0.1513% is commission.
  const schedule = fees();
  const costs = tradeCosts(
    schedule,
    feePreset(schedule, "ajaib"),
    Side.BUY,
    rp(10_000_000n),
    "2020-07-01",
  );
  expect([costs.total.amount, costs.levy.amount]).toEqual([15_130n, 3_800n]);
});

test("a small trade rounds the total up once", () => {
  // 1,001 x 0.2098% = 2.100098: the total rounds up to 3; the levy line (0.433) rounds down.
  const schedule = fees();
  const costs = tradeCosts(schedule, feePreset(schedule, "custom"), Side.BUY, rp(1_001n), TODAY);
  expect([costs.fee.amount, costs.levy.amount, costs.tax.amount]).toEqual([3n, 0n, 0n]);
});

// Each preset's all-in rate today, in percent, worked out by hand above: a literal pin, as a
// numerator over 10,000 so the exact cost is a whole-number ceiling.
const TOTAL_PER_10000: Record<string, bigint> = {
  "custom buy": 2_098n,
  "custom sell": 3_098n,
  "ajaib buy": 1_513n,
  "ajaib sell": 2_513n,
};

// Python's unit stand-in (#290): each preset and side once, at the ends of the gross drawn and
// where the 0.1% sale tax rounds down to nothing and to one.
test.each([
  [0n, "custom", Side.BUY],
  [10n ** 12n, "custom", Side.SELL],
  [999n, "ajaib", Side.SELL],
  [1_001n, "ajaib", Side.SELL],
  [12_345_679n, "ajaib", Side.BUY],
])("costs on %s (%s %s) round once against the trader", (gross, preset, side) => {
  const schedule = fees();
  const costs = tradeCosts(schedule, feePreset(schedule, preset), side, rp(gross), TODAY);
  const numerator = gross * (TOTAL_PER_10000[`${preset} ${side}`] ?? 0n);
  const denominator = 1_000_000n; // percent over 10,000, then over 100
  const ceiling = (numerator + denominator - 1n) / denominator;
  expect(costs.total.amount).toBe(ceiling);
  // every sale pays 0.1%, rounded down
  expect(costs.tax.amount).toBe(side === Side.SELL ? gross / 1_000n : 0n);
});

test("gross must be a non-negative rupiah amount", () => {
  const schedule = fees();
  const custom = feePreset(schedule, "custom");
  expect(() => tradeCosts(schedule, custom, Side.BUY, rp(-1n), TODAY)).toThrow(
    new RangeError("gross must be a non-negative IDR amount, got IDR -1"),
  );
  expect(() => tradeCosts(schedule, custom, Side.BUY, new Money(100n, USD), TODAY)).toThrow(
    new RangeError("gross must be a non-negative IDR amount, got USD 1.00"),
  );
  expect(() => dividendTax(schedule, rp(-1n), TODAY)).toThrow(
    new RangeError("gross must be a non-negative IDR amount, got IDR -1"),
  );
  expect(() => dividendTax(schedule, new Money(100n, USD), TODAY)).toThrow(
    new RangeError("gross must be a non-negative IDR amount, got USD 1.00"),
  );
});

test("costs before the levy is verified are refused", () => {
  const schedule = fees();
  expect(() =>
    tradeCosts(schedule, feePreset(schedule, "custom"), Side.BUY, rp(1_000n), "2020-03-12"),
  ).toThrow(/^fees\.json \[levy\] has no verified row/u);
});

test.each([
  ["2021-01-04", 0n, 0n], // nothing traded, no confirmation
  ["2021-01-04", 1n, 10_000n], // every confirmation, however small, until 11 Jan 2022
  ["2022-01-11", 1n, 10_000n],
  ["2022-01-12", 1n, 0n], // PP 3/2022's exemption from 12 Jan 2022
  ["2022-01-12", 10_000_000n, 0n], // "paling banyak Rp10.000.000" is exempt
  ["2022-01-12", 10_000_001n, 10_000n],
])("stamp duty on %s for %s traded is %s, as the law imposed it", (on, traded, duty) => {
  expect(dailyCosts(fees(), rp(traded), on).amount).toBe(duty);
});

test("stamp duty before 2021 is refused, and so is a negative day's trading", () => {
  expect(() => dailyCosts(fees(), rp(1n), "2020-12-31")).toThrow(
    /^fees\.json \[stamp_duty\] has no verified row for 2020-12-31/u,
  );
  expect(() => dailyCosts(fees(), rp(-1n), TODAY)).toThrow(
    new RangeError("traded must be a non-negative IDR amount, got IDR -1"),
  );
});

test.each([
  [1_000_000n, 100_000n],
  [999n, 100n], // 99.9 rounds up to 100
  [0n, 0n],
])("dividend tax on %s is the full ten percent rounded up: %s", (gross, tax) => {
  expect(dividendTax(fees(), rp(gross), TODAY).amount).toBe(tax);
});

test.each([
  ["2021-02-16", null], // the day before PMK 18/2021
  ["2021-02-17", "2022-03-31"],
  ["2026-05-20", "2027-03-31"], // t-tax.md §4's worked example
  ["2026-12-31", "2027-03-31"],
  ["2027-01-04", "2028-03-31"],
])("a dividend with ex-date %s is reinvested by %s: the end of March after its year", (exDate, deadline) => {
  expect(reinvestmentDeadline(fees(), exDate)).toBe(deadline);
});

test.each([
  ["2023-06-01", "2024-02-29"], // a leap year
  ["2024-06-01", "2025-02-28"],
  ["2399-06-01", "2400-02-29"], // divisible by 400
])("the deadline is the last day of its month: ex-date %s gives %s", (exDate, deadline) => {
  const document = documentCopy();
  rowOf(document.dividend_exemption, 1).reinvest_by_month = "2";
  const february = parseFees(document);
  expect(reinvestmentDeadline(february, exDate)).toBe(deadline);
});

test.each([
  ["2099-06-01", "2100-02-28"], // divisible by 100, not by 400
  ["2026-03-01", "2027-04-30"],
  ["2026-03-01", "2027-12-31"],
])("a month's last day follows the calendar: ex-date %s gives %s", (exDate, deadline) => {
  const document = documentCopy();
  rowOf(document.dividend_exemption, 1).reinvest_by_month = deadline.slice(5, 7).replace(/^0/u, "");
  expect(reinvestmentDeadline(parseFees(document), exDate)).toBe(deadline);
});

test.each([
  ["2021-02-17", "2023-12-31"],
  ["2027-03-10", "2029-12-31"], // M4 spec §2's correction: 2027, 2028 and 2029
  ["2026-12-31", "2028-12-31"],
])("protection for a purchase on %s lasts to %s: three tax years with its own", (purchase, until) => {
  expect(protectionEnd(fees(), purchase)).toBe(until);
});

test("no protection ends for a purchase the exemption does not cover", () => {
  expect(() => protectionEnd(fees(), "2021-02-16")).toThrow(
    new RangeError("no reinvestment exemption applies to a purchase on 2021-02-16"),
  );
  expect(() => reinvestmentDeadline(fees(), "2008-12-31")).toThrow(
    /^fees\.json \[dividend_exemption\] has no verified row/u,
  );
});

test("only presets that state what they include are shipped", () => {
  const schedule = fees();
  expect([...schedule.presets.keys()].toSorted()).toEqual(["ajaib", "custom"]);
  expect([...feePreset(schedule, "ajaib").includes].toSorted()).toEqual([
    "commission_vat",
    "levy",
    "sale_tax",
  ]);
  expect(feePreset(schedule, "custom").includes.size).toBe(0);
  expect(() => feePreset(schedule, "stockbit")).toThrow(
    new RangeError("no broker fee preset named 'stockbit'; fees.json has ajaib, custom"),
  );
});

test("an all-in quote smaller than what it includes is refused", () => {
  const document = documentCopy();
  presetOf(document, "ajaib").buy_percent = "0.04";
  expect(() => parseFees(document)).toThrow(
    new RulesFileError(
      "fees.json preset 'ajaib': its buy quote is smaller than the costs it says it includes " +
        "on 2020-03-13",
    ),
  );
});

test("an all-in sell quote is checked on every day a covered table changes", () => {
  // The levy rose to 0.0433% on 1 April 2022; a sell quote of 0.1431% covers the 0.043% levy and
  // the 0.1% sale tax before it, but not after.
  const document = documentCopy();
  presetOf(document, "ajaib").sell_percent = "0.1431";
  expect(() => parseFees(document)).toThrow(
    new RulesFileError(
      "fees.json preset 'ajaib': its sell quote is smaller than the costs it says it includes " +
        "on 2022-04-01",
    ),
  );
});
