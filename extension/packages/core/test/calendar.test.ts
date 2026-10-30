import { expect, test } from "vitest";
import shipped from "../../../rules/holidays.json" with { type: "json" };
import {
  IdxCalendar,
  MISSING_RULES_YEAR,
  parseHolidays,
  UnsupportedDateError,
  type HolidayYear,
} from "../src/calendar.ts";
import { RulesFileError } from "../src/rules-file.ts";

// Ported from Python's tests/idx/test_calendar.py, one test per case.

const calendar = IdxCalendar.shipped();

/** A fresh copy of the shipped document, to change one value of. */
const documentCopy = (): { schema: string; year: Record<string, unknown>[] } =>
  structuredClone(shipped);

const firstYear = (document: { year: Record<string, unknown>[] }): Record<string, unknown> => {
  const [first] = document.year;
  if (first === undefined) {
    throw new Error("the shipped calendar has no year");
  }
  return first;
};

// Holidays and IDX's stated trading-day total per year, copied from the research docs
// (t-hist.md §1, t-pay.md §2, t-rules.md §4). A literal pin: the reader's own arithmetic check
// derives from the file, so it cannot notice a year that went missing with its total.
const RESEARCH: [string, bigint, bigint][] = [
  ["2016", 15n, 246n],
  ["2017", 22n, 238n],
  ["2018", 21n, 240n],
  ["2019", 16n, 245n],
  ["2020", 20n, 242n],
  ["2021", 14n, 247n],
  ["2022", 14n, 246n],
  ["2023", 21n, 239n],
  ["2024", 25n, 237n],
  ["2025", 25n, 236n],
  ["2026", 22n, 239n],
  ["2027", 20n, 241n],
];

test("the shipped calendar covers 2016 to 2027", () => {
  expect([calendar.firstDay, calendar.lastDay]).toEqual(["2016-01-01", "2027-12-31"]);
});

test.each(RESEARCH)("%s has %s holidays and %s trading days", (year, holidays, trading) => {
  const days = calendar.tradingDays(`${year}-01-01`, `${year}-12-31`);
  expect(BigInt(days.length)).toBe(trading);
  const year0 = parseHolidays(shipped).find((each) => each.year === year);
  expect(BigInt(year0?.holidays.size ?? -1)).toBe(holidays);
});

test("the 2021 to 2025 window has the 1,205 days Yahoo has bars for", () => {
  expect(BigInt(calendar.tradingDays("2021-01-01", "2025-12-31").length)).toBe(1205n);
});

test.each([
  ["2026-09-22", true, "Yahoo's ^JKSE has no bar, but IDX traded (t-pay.md §2)"],
  ["2018-06-27", true, "election-day holiday, but Peng-00504 kept IDX open"],
  ["2022-05-04", false, "Eid leave added by the 2022 calendar's version 2"],
  ["2025-08-18", false, "added to 2025 by Peng-00149/BEI.POP/08-2025"],
  ["2026-12-31", false, "the exchange's year-end holiday"],
  ["2026-09-26", false, "a Saturday"],
  ["2026-09-27", false, "a Sunday"],
  ["2026-09-28", true, "an ordinary Monday"],
])("%s is a trading day: %s (%s)", (day, open) => {
  expect(calendar.isTradingDay(day)).toBe(open);
});

test.each(["2015-12-31", "2028-01-03"])("%s, in a year without holiday data, is refused", (day) => {
  const year = day.slice(0, 4);
  expect(() => calendar.isTradingDay(day)).toThrow(
    new UnsupportedDateError(
      `holidays.json has no IDX holidays for ${year}, so its trading days are unknown; ` +
        "it covers 2016 to 2027",
      year,
    ),
  );
});

test("the refusal carries the missing year and its note code", () => {
  const caught = (() => {
    try {
      calendar.isTradingDay("2028-01-03");
    } catch (error) {
      return error;
    }
    return undefined;
  })();
  expect(caught).toBeInstanceOf(UnsupportedDateError);
  expect(caught).toMatchObject({ year: "2028", code: "missing.rules_year" });
  expect(MISSING_RULES_YEAR).toBe("missing.rules_year");
});

test("next and previous cross holidays, weekends and the year end", () => {
  expect(calendar.nextTradingDay("2026-12-30")).toBe("2027-01-04");
  expect(calendar.previousTradingDay("2027-01-04")).toBe("2026-12-30");
  expect(calendar.nextTradingDay("2026-09-25")).toBe("2026-09-28");
  expect(calendar.previousTradingDay("2026-09-28")).toBe("2026-09-25");
});

test("addTradingDays counts from the day after", () => {
  // Eid 2026: 18-20 and 23-24 March are holidays, 21-22 a weekend.
  expect(calendar.addTradingDays("2026-03-17", 1n)).toBe("2026-03-25");
  expect(calendar.addTradingDays("2026-03-17", 2n)).toBe("2026-03-26");
  // A non-trading start day is allowed: the count starts on the day after it.
  expect(calendar.addTradingDays("2026-03-21", 1n)).toBe("2026-03-25");
});

test("counting past the last year is refused", () => {
  expect(() => calendar.addTradingDays("2027-12-30", 2n)).toThrow(/no IDX holidays for 2028/u);
});

test.each([[0n], [-1n], [true as unknown as bigint]])("a count of %s is refused", (count) => {
  expect(() => calendar.addTradingDays("2026-03-17", count)).toThrow(
    new RangeError(`count must be a bigint of at least 1, got ${String(count)}`),
  );
});

test("tradingDays is inclusive", () => {
  expect(calendar.tradingDays("2026-09-25", "2026-09-28")).toEqual(["2026-09-25", "2026-09-28"]);
});

test("tradingDays refuses a reversed range", () => {
  expect(() => calendar.tradingDays("2026-09-25", "2026-09-24")).toThrow(
    new RangeError("end 2026-09-24 is before start 2026-09-25"),
  );
});

test("each year names its source", () => {
  expect(calendar.source("2026")).toBe("Peng-00171/BEI.POP/09-2025");
  expect(() => calendar.source("2030")).toThrow(/no IDX holidays for 2030/u);
});

test("every row of the shipped file is read as the file states it", () => {
  const read = parseHolidays(shipped);
  expect(
    read.map((year: HolidayYear) => ({
      year: year.year,
      source: year.source,
      trading_days: String(year.tradingDays),
      holidays: [...year.holidays],
    })),
  ).toEqual(shipped.year);
});

test("a planted changed row goes red: a trading-day total one off", () => {
  const document = documentCopy();
  firstYear(document).trading_days = "245";
  expect(() => parseHolidays(document)).toThrow(
    new RulesFileError(
      "holidays.json [[year]] row 1: 2016 has 246 weekdays that are not holidays, " +
        "but the calendar states 245 trading days",
    ),
  );
});

test("a dropped holiday fails the arithmetic check", () => {
  const document = documentCopy();
  const first = firstYear(document);
  first.holidays = (first.holidays as string[]).slice(1);
  expect(() => parseHolidays(document)).toThrow(
    new RulesFileError(
      "holidays.json [[year]] row 1: 2016 has 247 weekdays that are not holidays, " +
        "but the calendar states 246 trading days",
    ),
  );
});

test.each([
  [{ holidays: ["2017-01-02"] }, "2017-01-02 is not in 2016"],
  [{ holidays: ["2016-01-02"] }, "2016-01-02 is a weekend"],
  [
    { holidays: ["2016-01-04", "2016-01-04"] },
    "holidays must be listed once each, in order; 2016-01-04 is not",
  ],
  [{ holidays: [20160104] }, "holiday 1 must be a date such as 2021-01-04, got 20160104"],
  [{ holidays: ["2016-02-30"] }, 'holiday 1 must be a date such as 2021-01-04, got "2016-02-30"'],
  [{ holidays: ["2016-13-01"] }, 'holiday 1 must be a date such as 2021-01-04, got "2016-13-01"'],
  [{ holidays: "2016-01-04" }, 'holidays must be an array, got "2016-01-04"'],
  [{ source: "" }, 'source must be a non-empty string, got ""'],
  [{ year: "0" }, 'year must be an integer of at least 1, got "0"'],
  [{ year: 2016 }, "year must be an integer of at least 1, got 2016"],
  [{ trading_days: "x" }, 'trading_days must be an integer of at least 0, got "x"'],
  [{ note: "x" }, "unknown key 'note'"],
])("a year row changed to %j is refused: %s", (change, message) => {
  const document = documentCopy();
  Object.assign(firstYear(document), change);
  expect(() => parseHolidays(document)).toThrow(`holidays.json [[year]] row 1: ${message}`);
});

test("a missing key is refused by name", () => {
  const document = documentCopy();
  delete firstYear(document).source;
  expect(() => parseHolidays(document)).toThrow(
    new RulesFileError("holidays.json [[year]] row 1: missing key 'source'"),
  );
});

test("years must be consecutive", () => {
  const document = documentCopy();
  document.year.splice(1, 1);
  expect(() => parseHolidays(document)).toThrow(
    new RulesFileError("holidays.json: years must be consecutive, got 2018 after 2016"),
  );
});

test("the top level is checked", () => {
  const document = { ...documentCopy(), extra: "1" };
  expect(() => parseHolidays(document)).toThrow(
    new RulesFileError("holidays.json [top level]: unknown key 'extra'"),
  );
});

test.each([
  [{ schema: "2" }, 'holidays.json: schema must be 1, got "2"'],
  [{ schema: "1" }, "holidays.json [year] must be a non-empty array of tables"],
  [{ schema: "1", year: [] }, "holidays.json [year] must be a non-empty array of tables"],
  [{ schema: "1", year: ["2016"] }, "holidays.json [year] must be a non-empty array of tables"],
  [[], "holidays.json: the document must be a table"],
  [null, "holidays.json: the document must be a table"],
])("the document %j is refused", (document, message) => {
  expect(() => parseHolidays(document)).toThrow(new RulesFileError(message));
});

test("a calendar needs a year", () => {
  expect(() => new IdxCalendar([])).toThrow(
    new RulesFileError("holidays.json: a calendar needs at least one year"),
  );
});

test("a calendar built by hand uses its own years and file name", () => {
  const year: HolidayYear = {
    year: "2030",
    source: "test",
    tradingDays: 261n,
    holidays: new Set(),
  };
  const mine = new IdxCalendar([year], "mine.json");
  expect(mine.isTradingDay("2030-01-01")).toBe(true);
  expect(() => mine.isTradingDay("2031-01-01")).toThrow(
    /^mine\.json has no IDX holidays for 2031/u,
  );
});

test("requireCovered refuses a year without data", () => {
  expect(() => {
    calendar.requireCovered("2027-12-31");
  }).not.toThrow();
  expect(() => {
    calendar.requireCovered("2028-01-03");
  }).toThrow(/^holidays\.json has no IDX holidays for 2028/u);
});
