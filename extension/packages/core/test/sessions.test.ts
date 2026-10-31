import { expect, test } from "vitest";
import shipped from "../rules/sessions.json" with { type: "json" };
import { IdxCalendar } from "../src/calendar.ts";
import { RulesFileError, UnsupportedDateError } from "../src/rules-file.ts";
import {
  adviceDayAt,
  isReviewDay,
  parseSessions,
  type AdviceDayRead,
  type ReviewEvery,
  type SessionRow,
} from "../src/sessions.ts";

// The advice day (#225, spec §4.2, §4.3, §6.2). Ported from Python's tests/idx/test_sessions.py
// for the reading cases. Times below are Jakarta time (WIB, UTC+7) written as UTC instants.

type Document = typeof shipped & Record<string, unknown>;

const documentCopy = (): Document => structuredClone(shipped);

const firstRow = (document: Document): Record<string, unknown> => {
  const [first] = document.sessions;
  if (first === undefined) {
    throw new Error("the shipped sessions table has no row");
  }
  return first;
};

const calendar = IdxCalendar.shipped();
const sessions = parseSessions(shipped);

/** The read at `wib`, a Jakarta wall-clock time such as `2026-10-29T16:02:00`. */
const readAt = (wib: string): AdviceDayRead =>
  adviceDayAt(new Date(`${wib}+07:00`), calendar, sessions);

const wib = (time: string): Date => new Date(`${time}+07:00`);

test("every row of the shipped sessions is read as the file states it", () => {
  expect(
    sessions.entries.map(([from, row]: readonly [string, SessionRow]) => ({
      from,
      source: row.source,
      pre_opening_from: row.preOpeningFrom,
      closing_match_until: row.closingMatchUntil,
    })),
  ).toEqual(shipped.sessions);
});

test("the table is verified from 8 April 2025", () => {
  expect(sessions.first).toBe("2025-04-08");
  expect(() => sessions.on("2025-04-07")).toThrow(UnsupportedDateError);
});

test("a row with an unknown key is refused", () => {
  const document = documentCopy();
  firstRow(document)["post_closing_until"] = "16:15:00";
  expect(() => parseSessions(document)).toThrow(
    "sessions.json [[sessions]] row 1: unknown key 'post_closing_until'",
  );
});

test.each([
  ["pre_opening_from", "8:45:00"],
  ["pre_opening_from", "24:00:00"],
  ["closing_match_until", "16:60:00"],
  ["closing_match_until", "16:01:60"],
  ["closing_match_until", 160159],
])("%s %j is refused as no time of day", (key, value) => {
  const document = documentCopy();
  firstRow(document)[key] = value;
  expect(() => parseSessions(document)).toThrow(
    `sessions.json [[sessions]] row 1: ${key} must be a time of day such as 08:45:00, ` +
      `got ${JSON.stringify(value)}`,
  );
});

test("pre-opening must start before the closing match ends", () => {
  const document = documentCopy();
  firstRow(document)["pre_opening_from"] = "16:01:59";
  expect(() => parseSessions(document)).toThrow(RulesFileError);
  expect(() => parseSessions(document)).toThrow(
    "sessions.json [[sessions]] row 1: pre-opening must start before the closing match ends, " +
      "got 16:01:59 and 16:01:59",
  );
});

test("a document with an unknown table is refused", () => {
  const document = documentCopy();
  document["breaks"] = [];
  expect(() => parseSessions(document)).toThrow("sessions.json [top level]: unknown key 'breaks'");
});

test("a read at 16:01:59 is still in the session: no advice day", () => {
  expect(readAt("2026-10-29T16:01:59")).toEqual({
    adviceDay: null,
    nextClose: wib("2026-10-29T16:02:00"),
  });
});

test("a read in the last second of the closing match is still in the session", () => {
  expect(readAt("2026-10-29T16:01:59.999").adviceDay).toBeNull();
});

test("a read at 16:02:00 shows that day's close", () => {
  expect(readAt("2026-10-29T16:02:00")).toEqual({
    adviceDay: "2026-10-29",
    nextClose: wib("2026-10-30T16:02:00"),
  });
});

test("a read the second before pre-opening still shows the previous close", () => {
  expect(readAt("2026-10-30T08:44:59")).toEqual({
    adviceDay: "2026-10-29",
    nextClose: wib("2026-10-30T16:02:00"),
  });
});

test("a read at the pre-opening instant has no advice day", () => {
  expect(readAt("2026-10-30T08:45:00")).toEqual({
    adviceDay: null,
    nextClose: wib("2026-10-30T16:02:00"),
  });
});

test("a read after midnight in Jakarta, still the previous day in UTC, shows the last close", () => {
  expect(readAt("2026-10-30T00:30:00")).toEqual({
    adviceDay: "2026-10-29",
    nextClose: wib("2026-10-30T16:02:00"),
  });
});

test("a weekend read shows Friday's close; the next close is Monday's", () => {
  expect(readAt("2026-10-31T12:00:00")).toEqual({
    adviceDay: "2026-10-30",
    nextClose: wib("2026-11-02T16:02:00"),
  });
});

test("Monday before pre-opening still shows Friday's close", () => {
  expect(readAt("2026-11-02T08:44:59").adviceDay).toBe("2026-10-30");
});

test("a holiday read shows the trading day before it", () => {
  expect(readAt("2026-08-17T12:00:00")).toEqual({
    adviceDay: "2026-08-14",
    nextClose: wib("2026-08-18T16:02:00"),
  });
});

test("a read in a year with no holiday data is refused", () => {
  expect(() => readAt("2028-01-04T17:00:00")).toThrow(UnsupportedDateError);
});

test("a read before the sessions table is verified is refused", () => {
  expect(() => readAt("2025-03-27T17:00:00")).toThrow(
    "sessions.json [sessions] has no verified row for 2025-03-27",
  );
});

test.each<[ReviewEvery]>([["year"], ["quarter"], ["month"]])(
  "a strategy's first advice day is a %s review day",
  (every) => {
    expect(isReviewDay("2026-10-29", null, every)).toBe(true);
  },
);

test.each<[string, string, ReviewEvery, boolean]>([
  ["2027-01-04", "2026-12-30", "year", true],
  ["2026-12-30", "2026-12-29", "year", false],
  ["2026-04-01", "2026-03-31", "quarter", true],
  ["2026-07-01", "2026-06-30", "quarter", true],
  ["2026-10-01", "2026-09-30", "quarter", true],
  ["2026-03-31", "2026-01-05", "quarter", false],
  ["2026-07-01", "2026-01-05", "quarter", true],
  ["2026-11-02", "2026-10-30", "month", true],
  ["2026-10-30", "2026-10-29", "month", false],
])("advice day %s after %s is a %s review day: %s", (day, previous, every, review) => {
  expect(isReviewDay(day, previous, every)).toBe(review);
});

test("a review day with no read moves to the next advice day, and only that one", () => {
  // 2 November 2026, the month's first trading day, had no read.
  expect(isReviewDay("2026-11-05", "2026-10-30", "month")).toBe(true);
  expect(isReviewDay("2026-11-06", "2026-11-05", "month")).toBe(false);
});

test.each([["2026-10-29"], ["2026-10-30"]])(
  "a previous advice day of %s, not before 2026-10-29, is refused",
  (previous) => {
    expect(() => isReviewDay("2026-10-29", previous, "month")).toThrow(
      `the previous advice day ${previous} must come before 2026-10-29`,
    );
  },
);

test("a day that is no date is refused", () => {
  expect(() => isReviewDay("2026-13-01", null, "month")).toThrow(RulesFileError);
});
