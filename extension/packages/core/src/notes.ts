/** Notes: every warning carries a dotted code, as Python's `steadyhand.notes` does (spec §4.5).
 *
 * Python's codes for simulated fills (`fill.*`) are not ported: the extension never fills an
 * order. The `missing.*` codes are new: each names what the user must read or enter. */

import type { Covered, Day, PageKind } from "./broker-view.ts";

export const NOTE_CODES = {
  CORPORATE_SPLIT_FRACTION_DROPPED: "corporate.split.fraction_dropped",
  CORPORATE_SPLIT_ORDER_CANCELLED: "corporate.split.order_cancelled",
  DATA_BAR_MISSING: "data.bar.missing",
  DATA_BAR_REFUSED: "data.bar.refused",
  DATA_DIVIDENDS_HISTORY_REFUSED: "data.dividends.history_refused",
  DATA_STOCK_UNAVAILABLE: "data.stock.unavailable",
  EXEMPTION_CLAIM_BROKEN: "exemption.claim_broken",
  EXEMPTION_DEADLINE_MISSED: "exemption.deadline_missed",
  INCOME_GROWTH_SHORT_HISTORY: "income.growth.short_history",
  INCOME_PROJECTION_COSTS_IGNORED: "income.projection.costs_ignored",
  LIMIT_CASH_CUT: "limit.cash.cut",
  LIMIT_CASH_SHORT: "limit.cash.short",
  LIMIT_MIN_LOTS: "limit.min_lots",
  LIMIT_WEIGHT_CUT: "limit.weight.cut",
  LIMIT_WEIGHT_FULL: "limit.weight.full",
  MISSING_DEPOSITS: "missing.deposits",
  MISSING_HISTORY: "missing.history",
  MISSING_PAGE: "missing.page",
  MISSING_RULES_YEAR: "missing.rules_year",
  RISK_HALT_DAILY_LOSS: "risk.halt.daily_loss",
  RISK_HALT_DRAWDOWN: "risk.halt.drawdown",
  STRATEGY_TOO_FEW_QUALIFIED: "strategy.too_few_qualified",
  TRADE_EXCLUDED: "trade.excluded",
  TRADE_FROZEN: "trade.frozen",
  TRADE_NO_BAR: "trade.no_bar",
  TRADE_NOT_HELD: "trade.not_held",
  TRADE_NOT_IN_UNIVERSE: "trade.not_in_universe",
  TRADE_REFUSED: "trade.refused",
} as const;

export type NoteCode = (typeof NOTE_CODES)[keyof typeof NOTE_CODES];

const KNOWN: ReadonlySet<string> = new Set(Object.values(NOTE_CODES));

/** A warning: its dotted code and the plain text the panel shows. */
export interface Note {
  readonly code: NoteCode;
  readonly text: string;
}

const isCode = (code: string): code is NoteCode => KNOWN.has(code);

export const note = (code: string, text: string): Note => {
  if (!isCode(code)) {
    throw new RangeError(`unknown note code '${code}'`);
  }
  if (text === "") {
    throw new RangeError(`note '${code}' has no text`);
  }
  return { code, text };
};

/** How each page is named in "open the ... page"; a stock's own pages also name the stock. */
const PAGE_NAMES: Readonly<Record<PageKind, string>> = {
  portfolio: "the portfolio page",
  watchlist: "the watchlist page",
  flags: "the page that flags suspended and monitored stocks",
  "cash-movements": "the cash movement page",
  "corporate-actions": "the corporate action page",
  dividends: "the dividend page",
  "stock-detail": "the price chart",
};

const PER_STOCK: ReadonlySet<PageKind> = new Set(["dividends", "stock-detail"]);

/** `missing.page`: the exact page to open, such as "open the dividend page for BBRI". */
export const missingPage = (page: PageKind, symbol?: string): Note => {
  if (PER_STOCK.has(page) && symbol === undefined) {
    throw new RangeError(`the ${page} page belongs to one stock: name it`);
  }
  const target = symbol === undefined ? "" : ` for ${symbol}`;
  return note(NOTE_CODES.MISSING_PAGE, `open ${PAGE_NAMES[page]}${target}`);
};

/** `missing.history`: the window a stock's history must cover and how many closes it has. */
export const missingHistory = (symbol: string, covered: Covered, closes: bigint): Note =>
  note(
    NOTE_CODES.MISSING_HISTORY,
    `${symbol}: the history from ${covered.from} to ${covered.to} has ${String(closes)} ` +
      (closes === 1n ? "close" : "closes"),
  );

/** `missing.deposits`: the cash-movement record does not cover the time since `since`. */
export const missingDeposits = (since: Day): Note =>
  note(
    NOTE_CODES.MISSING_DEPOSITS,
    `deposits and withdrawals since ${since} are not recorded: open the cash movement page, ` +
      "or enter each one (or none)",
  );

/** `missing.rules_year`: this release carries no IDX holiday data for `year`. */
export const missingRulesYear = (year: string): Note =>
  note(
    NOTE_CODES.MISSING_RULES_YEAR,
    `steadyhand has no IDX holiday data for ${year}; advice resumes when a release carries it`,
  );
