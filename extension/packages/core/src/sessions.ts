/**
 * The advice day (spec §4.2, §4.3, §6.2): which trading day's close a read shows, from the IDX
 * regular-market times in `rules/sessions.json` and the trading days in `rules/holidays.json`.
 * Times in the file are Jakarta time (WIB, UTC+7, with no daylight saving).
 */
import {
  asDay,
  asDocument,
  dated,
  getStr,
  getTime,
  onlyKeys,
  requireSchema,
  RulesFileError,
  Where,
} from "./rules-file.ts";
import type { Dated, Row } from "./rules-file.ts";
import type { IdxCalendar } from "./calendar.ts";

export const SESSIONS_FILE = "sessions.json";

/** When pre-opening starts and the last second of closing-price matching, as `HH:MM:SS` WIB. */
export interface SessionRow {
  readonly source: string;
  readonly preOpeningFrom: string;
  readonly closingMatchUntil: string;
}

const parseRow = (row: Row, where: Where): SessionRow => {
  const preOpeningFrom = getTime(row, "pre_opening_from", where);
  const closingMatchUntil = getTime(row, "closing_match_until", where);
  if (preOpeningFrom >= closingMatchUntil) {
    throw new RulesFileError(
      `${where.toString()}: pre-opening must start before the closing match ends, ` +
        `got ${preOpeningFrom} and ${closingMatchUntil}`,
    );
  }
  return { source: getStr(row, "source", where), preOpeningFrom, closingMatchUntil };
};

export const parseSessions = (value: unknown, file: string = SESSIONS_FILE): Dated<SessionRow> => {
  const contents = asDocument(value, file);
  requireSchema(contents, file, 1n);
  onlyKeys(contents, new Set(["schema", "sessions"]), new Where(file, "top level"));
  return dated(contents, "sessions", ["pre_opening_from", "closing_match_until"], parseRow, file);
};

const WIB_OFFSET_MS = 7 * 60 * 60 * 1000;

/** The Jakarta day and time of day (to the second, rounded down) of instant `at`. */
const inJakarta = (at: Date): { readonly day: string; readonly time: string } => {
  const local = new Date(at.getTime() + WIB_OFFSET_MS).toISOString();
  return { day: local.slice(0, 10), time: local.slice(11, 19) };
};

/** The instant `time` (`HH:MM:SS`) WIB on `day`. */
const atJakarta = (day: string, time: string): Date => new Date(`${day}T${time}+07:00`);

/** The first instant a read shows `day`'s close: the second after the closing match ends. */
const closeFinal = (day: string, sessions: Dated<SessionRow>): Date =>
  new Date(atJakarta(day, sessions.on(day).closingMatchUntil).getTime() + 1000);

/** What a read at one instant shows. */
export interface AdviceDayRead {
  /** The trading day whose close the read shows, or `null` during a trading day's session
   * (from its pre-opening until its close is final). */
  readonly adviceDay: string | null;
  /** When the next close not yet shown becomes final: the panel's "next close". */
  readonly nextClose: Date;
}

/** The advice day of a read at `at`, and the next close (spec §4.3, §6.2). A day outside the
 * holiday or session tables is refused with `UnsupportedDateError`. */
export const adviceDayAt = (
  at: Date,
  calendar: IdxCalendar,
  sessions: Dated<SessionRow>,
): AdviceDayRead => {
  const { day, time } = inJakarta(at);
  if (!calendar.isTradingDay(day)) {
    const next = calendar.nextTradingDay(day);
    return { adviceDay: calendar.previousTradingDay(day), nextClose: closeFinal(next, sessions) };
  }
  const row = sessions.on(day);
  if (time > row.closingMatchUntil) {
    const next = calendar.nextTradingDay(day);
    return { adviceDay: day, nextClose: closeFinal(next, sessions) };
  }
  const adviceDay = time < row.preOpeningFrom ? calendar.previousTradingDay(day) : null;
  return { adviceDay, nextClose: closeFinal(day, sessions) };
};

/** How often a strategy reviews: on the first trading day of each year, quarter or month. */
export type ReviewEvery = "year" | "quarter" | "month";

const periodOf = (day: string, every: ReviewEvery): string => {
  switch (every) {
    case "year":
      return day.slice(0, 4);
    case "quarter":
      return `${day.slice(0, 4)}-Q${String(Math.floor((Number(day.slice(5, 7)) - 1) / 3))}`;
    case "month":
      return day.slice(0, 7);
  }
};

/** Whether `adviceDay` is a review day: the first advice day on or after the rule's day (the
 * period's first trading day), or a strategy's first advice day (`previous` of `null`). Every
 * day before a period's first trading day lies in an earlier period, so an advice day reviews
 * exactly when the previous advice day is in an earlier period. */
export const isReviewDay = (
  adviceDay: string,
  previous: string | null,
  every: ReviewEvery,
): boolean => {
  asDay(adviceDay, "advice day");
  if (previous === null) {
    return true;
  }
  if (asDay(previous, "previous advice day") >= adviceDay) {
    throw new RangeError(`the previous advice day ${previous} must come before ${adviceDay}`);
  }
  return periodOf(previous, every) !== periodOf(adviceDay, every);
};
