import { expect, test } from "vitest";
import shipped from "../rules/sessions.json" with { type: "json" };
import type { BrokerView, PageKind, Part, Portfolio, Watchlist } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { freshness, MOST_APART, type Freshness } from "../src/freshness.ts";
import { IDR, Money } from "../src/money.ts";
import { parseSessions } from "../src/sessions.ts";

// Freshness (#226 AC4, spec §5.4). Times are Jakarta time (WIB, UTC+7). 2026-10-29 and
// 2026-10-30 are trading days whose closing match ends at 16:01:59, so the close is final at 16:02:00.

const calendar = IdxCalendar.shipped();
const sessions = parseSessions(shipped);

const part = <T>(pageKind: PageKind, wib: string, value: T): Part<T> => ({
  source: { broker: "fixture", pageKind, route: "page" },
  readAt: new Date(`${wib}+07:00`),
  value,
});

const portfolio = (wib: string): Part<Portfolio> =>
  part("portfolio", wib, {
    cashAvailable: new Money(0n, IDR),
    cashSettled: new Money(0n, IDR),
    cashUnsettled: new Money(0n, IDR),
    holdings: [],
  });

const watchlist = (wib: string): Part<Watchlist> => part("watchlist", wib, { stocks: [] });

const check = (view: BrokerView): Freshness => freshness(view, calendar, sessions);

test("the most two reads may be apart is 30 minutes", () => {
  expect(MOST_APART).toBe(30n * 60n * 1000n);
});

test("reads 30:00 apart on the same advice day are fresh", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-29T16:10:00"),
      watchlist: watchlist("2026-10-29T16:40:00"),
    }),
  ).toEqual({ fresh: true, adviceDay: "2026-10-29" });
});

test("reads 30:01 apart name the older one, the portfolio, to read again", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-29T16:10:00"),
      watchlist: watchlist("2026-10-29T16:40:01"),
    }),
  ).toEqual({ fresh: false, readAgain: ["portfolio"], reason: "read more than 30 minutes apart" });
});

test("reads 30:01 apart name the older one, the watchlist, to read again", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-29T16:40:01"),
      watchlist: watchlist("2026-10-29T16:10:00"),
    }),
  ).toEqual({ fresh: false, readAgain: ["watchlist"], reason: "read more than 30 minutes apart" });
});

test("reads at the same instant are fresh", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-30T07:00:00"),
      watchlist: watchlist("2026-10-30T07:00:00"),
    }),
  ).toEqual({ fresh: true, adviceDay: "2026-10-29" });
});

test("reads on different advice days name the older one", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-30T20:00:00"),
      watchlist: watchlist("2026-10-29T20:00:00"),
    }),
  ).toEqual({ fresh: false, readAgain: ["watchlist"], reason: "read for different advice days" });
});

test("a read in the session's last second makes no advice day and is named", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-29T16:01:59"),
      watchlist: watchlist("2026-10-29T16:20:00"),
    }),
  ).toEqual({ fresh: false, readAgain: ["portfolio"], reason: "read during a trading session" });
});

test("both read during a session are both named", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-29T10:00:00"),
      watchlist: watchlist("2026-10-29T10:05:00"),
    }),
  ).toEqual({
    fresh: false,
    readAgain: ["portfolio", "watchlist"],
    reason: "read during a trading session",
  });
});

test.each([
  [{ watchlist: watchlist("2026-10-29T17:00:00") }, ["portfolio"]],
  [{ portfolio: portfolio("2026-10-29T17:00:00") }, ["watchlist"]],
  [{}, ["portfolio", "watchlist"]],
] as const)("a part not read is named: %#", (view, readAgain) => {
  expect(check(view)).toEqual({ fresh: false, readAgain, reason: "not read" });
});

test("a read the second the close is final makes that day the advice day", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-29T16:02:00"),
      watchlist: watchlist("2026-10-29T16:20:00"),
    }),
  ).toEqual({ fresh: true, adviceDay: "2026-10-29" });
});

test("a watchlist read during a session is named alone", () => {
  expect(
    check({
      portfolio: portfolio("2026-10-29T17:00:00"),
      watchlist: watchlist("2026-10-29T15:00:00"),
    }),
  ).toEqual({ fresh: false, readAgain: ["watchlist"], reason: "read during a trading session" });
});
