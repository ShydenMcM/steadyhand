import { expect, test } from "vitest";
import type { Dividend, Dividends } from "../src/broker-view.ts";
import { RuleDecimal } from "../src/ratio.ts";
import type { StockSeries } from "../src/series.ts";
import { totalReturn } from "../src/total-return.ts";

// Total return (spec §6.5, #232 AC3): each dividend in the window reinvested on its ex-date.

const close = (day: string, amount: string) => ({ day, close: new RuleDecimal(amount) });
const SERIES: StockSeries = {
  closes: [close("2025-06-16", "1000"), close("2025-06-17", "1000"), close("2025-06-18", "950")],
  dividendsAdjustedTo: null,
  missing: [],
};
const dividend = (exDate: string, gross: string, symbol = "BBCA"): Dividend => ({
  symbol,
  exDate,
  paymentDate: "2025-07-01",
  grossPerShare: new RuleDecimal(gross),
});
const read = (dividends: Dividend[], from = "2025-01-01", to = "2025-06-30"): Dividends => ({
  covered: { from, to },
  dividends,
});
const run = (series: StockSeries, dividends: Dividends | undefined) => {
  const found = totalReturn("BBCA", series, dividends, [], "2025-06-30");
  return { closes: found.closes.map((daily) => daily.close.toString()), missing: found.missing };
};
const UNREAD = [{ code: "missing.page", text: "open the dividend page for BBCA" }];

test("a dividend scales every close before its ex-date by 1 - dividend / the close before", () => {
  // 50 on a close of 1,000: every earlier close times 0.95.
  expect(run(SERIES, read([dividend("2025-06-18", "50")]))).toEqual({
    closes: ["950", "950", "950"],
    missing: [],
  });
});

test("two dividends each use the close before their own ex-date as the series gives it", () => {
  // 10 on the 16th's 1,000 (0.99) before the 17th; 95 on the 17th's 1,000 (0.905) before the
  // 18th: the close the series gives, not the one the first dividend adjusted.
  expect(
    run(SERIES, read([dividend("2025-06-17", "10"), dividend("2025-06-18", "95")])).closes,
  ).toEqual(["895.95", "905", "950"]);
});

test("a dividend outside the window, on its first day, or of another stock changes nothing", () => {
  const outside = [
    dividend("2025-06-20", "50"),
    dividend("2025-06-16", "50"),
    dividend("2025-06-18", "50", "TLKM"),
  ];
  expect(run(SERIES, read(outside)).closes).toEqual(["1000", "1000", "950"]);
});

test("a stock whose dividends for the window are unread is listed missing", () => {
  expect(run(SERIES, undefined)).toEqual({ closes: ["1000", "1000", "950"], missing: UNREAD });
  expect(run(SERIES, read([], "2025-06-17")).missing).toEqual(UNREAD);
  expect(run(SERIES, read([], "2025-01-01", "2025-06-17")).missing).toEqual(UNREAD);
});

test("a chart already adjusted for dividends is not adjusted again", () => {
  const adjusted = { ...SERIES, dividendsAdjustedTo: "2025-06-18" };
  expect(run(adjusted, undefined)).toEqual({ closes: ["1000", "1000", "950"], missing: [] });
});

test("dividends after a dividend-adjusted chart's last day still apply", () => {
  const adjusted = { ...SERIES, dividendsAdjustedTo: "2025-06-17" };
  expect(
    run(adjusted, read([dividend("2025-06-17", "10"), dividend("2025-06-18", "50")], "2025-06-17"))
      .closes,
  ).toEqual(["950", "950", "950"]);
});

test("a series that asks for its chart again passes that on and is not adjusted", () => {
  const asks = {
    ...SERIES,
    missing: [{ code: "missing.page" as const, text: "open the price chart for BBCA" }],
  };
  expect(run(asks, read([dividend("2025-06-18", "50")]))).toEqual({
    closes: ["1000", "1000", "950"],
    missing: asks.missing,
  });
});

test("an empty series is returned as it is", () => {
  expect(run({ ...SERIES, closes: [] }, undefined)).toEqual({ closes: [], missing: [] });
});
