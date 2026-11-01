import { expect, test } from "vitest";
import type { Dividend, Split } from "../src/broker-view.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { restatedGross, restatedPerShare, splitRatio } from "../src/restated.ts";

// Dividends restated in today's shares (spec §6.6, #232 AC4), as Python's `_restated_gross`; the
// seeded parity cases are in parity-restated.test.ts.

const split = (exDate: string, from: bigint, to: bigint, symbol = "BBCA"): Split => ({
  symbol,
  exDate,
  from,
  to,
});
const dividend: Dividend = {
  symbol: "BBCA",
  exDate: "2025-03-25",
  paymentDate: "2025-04-15",
  grossPerShare: new RuleDecimal("270.5"),
};

test("no split since the ex-date leaves the basis as it was", () => {
  expect(splitRatio("BBCA", "2025-03-25", [], "2025-12-31")).toEqual([1n, 1n]);
});

test("every split from the ex-date to the day read is multiplied in, the ex-date included", () => {
  const splits = [
    split("2025-03-25", 1n, 5n),
    split("2025-06-02", 1n, 2n),
    split("2026-01-02", 1n, 3n),
  ];
  expect(splitRatio("BBCA", "2025-03-25", splits, "2025-12-31")).toEqual([1n, 10n]);
});

test("a split before the ex-date, or of another stock, is not counted", () => {
  const splits = [split("2025-03-24", 1n, 5n), split("2025-06-02", 1n, 2n, "TLKM")];
  expect(splitRatio("BBCA", "2025-03-25", splits, "2025-12-31")).toEqual([1n, 1n]);
});

test("a dividend on today's shares is worked exactly and rounded down once", () => {
  // 270.5 per old share is 270.5 / 3 per new share; on 1,000 new shares 90,166.66..., so 90,166.
  expect(restatedGross(dividend, 1_000n, [split("2025-06-02", 1n, 3n)], "2025-12-31").amount).toBe(
    90_166n,
  );
});

test("a reverse split raises the dividend per share", () => {
  expect(restatedGross(dividend, 10n, [split("2025-06-02", 4n, 1n)], "2025-12-31").amount).toBe(
    10_820n,
  );
});

test("the restated dividend per share is the gross times the ratio, at 28 digits", () => {
  expect(restatedPerShare(dividend, [split("2025-06-02", 1n, 3n)], "2025-12-31").toString()).toBe(
    "90.16666666666666666666666667",
  );
});
