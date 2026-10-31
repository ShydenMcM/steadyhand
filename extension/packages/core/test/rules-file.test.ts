import { expect, test } from "vitest";
import {
  Dated,
  getDecimal,
  getTables,
  MISSING_RULES_YEAR,
  RulesFileError,
  UnsupportedDateError,
  Where,
} from "../src/rules-file.ts";

// Ported from Python's tests/idx/test_datafile.py, one test per case.

const where = new Where("t.json", "rows");

const dated = new Dated(where, [
  ["2020-01-01", "a"],
  ["2021-06-01", "b"],
]);

test("a dated table answers from each row's start until the next", () => {
  expect([
    dated.on("2020-01-01"),
    dated.on("2021-05-31"),
    dated.on("2021-06-01"),
    dated.on("2030-01-01"),
  ]).toEqual(["a", "a", "b", "b"]);
  expect(dated.first).toBe("2020-01-01");
});

test("a day before the first row is refused, naming the table and the missing year", () => {
  const refused = (): string => dated.on("2019-12-31");
  expect(refused).toThrow(
    new UnsupportedDateError(
      "t.json [rows] has no verified row for 2019-12-31: its first row applies from 2020-01-01",
      "2019",
    ),
  );
  try {
    refused();
  } catch (error) {
    expect(error).toMatchObject({ code: MISSING_RULES_YEAR, year: "2019" });
  }
});

test("a dated table refuses a day that is no date", () => {
  expect(() => dated.on("2021-02-30")).toThrow(/day must be a date such as 2021-01-04/u);
});

test("a dated table needs a row", () => {
  expect(() => new Dated(where, [])).toThrow(
    new RulesFileError("t.json [rows]: needs at least one row"),
  );
});

test("from dates must increase", () => {
  expect(
    () =>
      new Dated(where, [
        ["2021-01-01", 1n],
        ["2021-01-01", 2n],
      ]),
  ).toThrow(
    new RulesFileError("t.json [rows]: from dates must increase, got 2021-01-01 after 2021-01-01"),
  );
});

test("a decimal is read exactly from its string", () => {
  expect(getDecimal({ rate: "0.018" }, "rate", where).toString()).toBe("0.018");
  expect(getDecimal({ rate: "10" }, "rate", where).toString()).toBe("10");
});

test.each([
  [0.018, 'a decimal written as a string, such as "0.018"'],
  ["-1", "a decimal of at least 0, such as 0.018"],
  ["1e3", "a decimal of at least 0, such as 0.018"],
  ["Infinity", "a decimal of at least 0, such as 0.018"],
  ["", "a decimal of at least 0, such as 0.018"],
])("a decimal %j is refused", (value, expected) => {
  expect(() => getDecimal({ rate: value }, "rate", where.at(2n))).toThrow(
    new RulesFileError(
      `t.json [[rows]] row 2: rate must be ${expected}, got ${JSON.stringify(value)}`,
    ),
  );
});

test("each inline table is paired with its place", () => {
  const found = getTables({ tiers: [{ a: "1" }, { a: "2" }] }, "tiers", where.at(1n), "tier");
  expect(found.map(([row, place]) => [row, place.toString()])).toEqual([
    [{ a: "1" }, "t.json [[rows]] row 1, tier 1"],
    [{ a: "2" }, "t.json [[rows]] row 1, tier 2"],
  ]);
});

test("a tier that is not a table is refused", () => {
  expect(() => getTables({ tiers: [{}, "x"] }, "tiers", where.at(1n), "tier")).toThrow(
    new RulesFileError("t.json [[rows]] row 1, tier 2 must be an inline table"),
  );
});

test("a part is dropped when the place moves to another row", () => {
  expect(where.at(1n).within("tier 1").at(2n).toString()).toBe("t.json [[rows]] row 2");
});
