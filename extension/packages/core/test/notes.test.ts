import { expect, test } from "vitest";
import {
  NOTE_CODES,
  missingDeposits,
  missingHistory,
  missingPage,
  missingReread,
  missingRulesYear,
  note,
} from "../src/notes.ts";

// Python's steadyhand/notes.py codes, without the simulated-fill codes (spec §4.5), plus the
// five codes that name what is missing.
const PYTHON_CODES_KEPT = [
  "corporate.split.fraction_dropped",
  "corporate.split.order_cancelled",
  "data.bar.missing",
  "data.bar.refused",
  "data.dividends.history_refused",
  "data.stock.unavailable",
  "exemption.claim_broken",
  "exemption.deadline_missed",
  "income.growth.short_history",
  "income.projection.costs_ignored",
  "limit.cash.cut",
  "limit.cash.short",
  "limit.min_lots",
  "limit.weight.cut",
  "limit.weight.full",
  "risk.halt.daily_loss",
  "risk.halt.drawdown",
  "strategy.too_few_qualified",
  "trade.excluded",
  "trade.frozen",
  "trade.no_bar",
  "trade.not_held",
  "trade.not_in_universe",
  "trade.refused",
];
const NEW_CODES = [
  "missing.deposits",
  "missing.history",
  "missing.page",
  "missing.reread",
  "missing.rules_year",
];

test("the codes are Python's dotted codes and the four missing ones", () => {
  expect([...Object.values(NOTE_CODES)].sort()).toEqual(
    [...PYTHON_CODES_KEPT, ...NEW_CODES].sort(),
  );
});

test("no simulated-fill code is ported", () => {
  expect(Object.values(NOTE_CODES).filter((code) => code.startsWith("fill."))).toEqual([]);
});

test("a note is its code and its text", () => {
  expect(note(NOTE_CODES.TRADE_FROZEN, "frozen: suspended")).toEqual({
    code: "trade.frozen",
    text: "frozen: suspended",
  });
});

test("a note refuses a code that is not one of the codes", () => {
  expect(() => note("fill.cash.cut", "x")).toThrow(
    new RangeError("unknown note code 'fill.cash.cut'"),
  );
});

test("a note refuses empty text", () => {
  expect(() => note(NOTE_CODES.TRADE_FROZEN, "")).toThrow(
    new RangeError("note 'trade.frozen' has no text"),
  );
});

test.each([
  ["portfolio", undefined, "open the portfolio page"],
  ["watchlist", undefined, "open the watchlist page"],
  ["flags", undefined, "open the page that flags suspended and monitored stocks"],
  ["cash-movements", undefined, "open the cash movement page"],
  ["corporate-actions", undefined, "open the corporate action page"],
  ["dividends", "BBRI", "open the dividend page for BBRI"],
  ["stock-detail", "BBRI", "open the price chart for BBRI"],
] as const)("missing.page names the page to open: %s %s", (page, symbol, text) => {
  expect(missingPage(page, symbol)).toEqual({ code: "missing.page", text });
});

test("missing.page for a stock's own page needs the stock", () => {
  expect(() => missingPage("stock-detail")).toThrow(
    new RangeError("the stock-detail page belongs to one stock: name it"),
  );
});

test("missing.history gives the window and how many closes it has", () => {
  expect(missingHistory("BBRI", { from: "2025-10-31", to: "2026-10-30" }, 150n)).toEqual({
    code: "missing.history",
    text: "BBRI: the history from 2025-10-31 to 2026-10-30 has 150 closes",
  });
});

test("missing.history says one close in the singular", () => {
  expect(missingHistory("BBRI", { from: "2026-10-30", to: "2026-10-30" }, 1n).text).toBe(
    "BBRI: the history from 2026-10-30 to 2026-10-30 has 1 close",
  );
});

test("missing.deposits names the day the record must cover from", () => {
  expect(missingDeposits("2026-10-01")).toEqual({
    code: "missing.deposits",
    text:
      "deposits and withdrawals since 2026-10-01 are not recorded: open the cash movement page, " +
      "or enter each one (or none)",
  });
});

test("missing.reread names the day whose read came before a deposit or withdrawal", () => {
  expect(missingReread("2025-07-02")).toEqual({
    code: "missing.reread",
    text:
      "a deposit or withdrawal on 2025-07-02 was recorded after that day's portfolio read: " +
      "read the portfolio again",
  });
});

test("missing.rules_year names the year with no IDX rules", () => {
  expect(missingRulesYear("2027")).toEqual({
    code: "missing.rules_year",
    text: "steadyhand has no IDX holiday data for 2027; advice resumes when a release carries it",
  });
});
