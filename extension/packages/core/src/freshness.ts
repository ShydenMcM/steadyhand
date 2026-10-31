/**
 * Freshness (spec §5.4): advice needs the portfolio and the watchlist read on the same advice day
 * and within 30 minutes of each other. Otherwise the panel names the part to read again.
 */
import type { BrokerView, Day } from "./broker-view.ts";
import type { IdxCalendar } from "./calendar.ts";
import type { Dated } from "./rules-file.ts";
import { adviceDayAt, type SessionRow } from "./sessions.ts";

/** The most the two reads may be apart, in milliseconds: 30 minutes, inclusive. */
export const MOST_APART = 30n * 60n * 1000n;

/** The parts advice needs read together. */
export type FreshPart = "portfolio" | "watchlist";

export type Freshness =
  | { readonly fresh: true; readonly adviceDay: Day }
  | {
      readonly fresh: false;
      readonly readAgain: readonly FreshPart[];
      readonly reason:
        | "not read"
        | "read during a trading session"
        | "read for different advice days"
        | "read more than 30 minutes apart";
    };

/** Whether `view`'s portfolio and watchlist may be advised on together, and if not, which to read
 * again: each one missing, each one read during a session, or else the older of the two. */
export const freshness = (
  view: BrokerView,
  calendar: IdxCalendar,
  sessions: Dated<SessionRow>,
): Freshness => {
  const { portfolio, watchlist } = view;
  if (portfolio === undefined || watchlist === undefined) {
    const missing: FreshPart[] = [];
    if (portfolio === undefined) {
      missing.push("portfolio");
    }
    if (watchlist === undefined) {
      missing.push("watchlist");
    }
    return { fresh: false, readAgain: missing, reason: "not read" };
  }
  const portfolioDay = adviceDayAt(portfolio.readAt, calendar, sessions).adviceDay;
  const watchlistDay = adviceDayAt(watchlist.readAt, calendar, sessions).adviceDay;
  if (portfolioDay === null || watchlistDay === null) {
    const inSession: FreshPart[] = [];
    if (portfolioDay === null) {
      inSession.push("portfolio");
    }
    if (watchlistDay === null) {
      inSession.push("watchlist");
    }
    return { fresh: false, readAgain: inSession, reason: "read during a trading session" };
  }
  const older: FreshPart = portfolio.readAt <= watchlist.readAt ? "portfolio" : "watchlist";
  if (portfolioDay !== watchlistDay) {
    return { fresh: false, readAgain: [older], reason: "read for different advice days" };
  }
  const apart = BigInt(Math.abs(watchlist.readAt.getTime() - portfolio.readAt.getTime()));
  if (apart > MOST_APART) {
    return { fresh: false, readAgain: [older], reason: "read more than 30 minutes apart" };
  }
  return { fresh: true, adviceDay: portfolioDay };
};
