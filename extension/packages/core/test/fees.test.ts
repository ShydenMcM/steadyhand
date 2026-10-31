import Decimal from "decimal.js";
import { expect, test } from "vitest";
import shipped from "../rules/fees.json" with { type: "json" };
import { parseFees, type FeeSchedule } from "../src/fees.ts";
import { RulesFileError, type Dated } from "../src/rules-file.ts";

// Ported from the reading cases of Python's tests/idx/test_fees.py, one test per case. The cost
// arithmetic, and its check that an all-in quote covers what it includes, are EXT S4b's (#224).

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
