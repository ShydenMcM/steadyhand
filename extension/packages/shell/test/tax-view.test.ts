import { IDR, IdxMarketRules, Money, claimsReport, shippedTables } from "@steadyhand/core";
import { expect, test } from "vitest";
import { ESTIMATE_LINE, taxView } from "../src/tax-view.ts";

// The Tax tab's claims list as text (spec §9.2): what core's claims report says, in the lines the
// panel writes, under the line saying every figure is an estimate.

const RULES = new IdxMarketRules(shippedTables(), "custom");
const rupiah = (amount: bigint): Money => new Money(amount, IDR);

test("the estimate line names the yearly realisation reports", () => {
  expect(ESTIMATE_LINE).toBe(
    "Every figure here is an estimate: it assumes the yearly realisation reports are filed.",
  );
});

test("with no dividend entered the list says so and shows no figure", () => {
  expect(taxView(claimsReport(RULES, [], [], "2025-08-01", []))).toEqual([
    { heading: "Estimate", lines: [ESTIMATE_LINE] },
    {
      heading: "Claims",
      lines: ["No dividend received is entered: enter each one on the Tax tab."],
    },
  ]);
});

test("a claim still open shows what is left and the tax if its deadline is missed", () => {
  const read = claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [{ day: "2025-07-01", symbol: "BBRI", amount: rupiah(600_000n) }],
    "2025-08-01",
    [],
  );
  expect(taxView(read)[1]).toEqual({
    heading: "Claims",
    lines: [
      "BBCA, received 2025-06-10: gross IDR 1,000,000, reinvested IDR 600,000, still to reinvest " +
        "IDR 400,000 by 2026-03-31; if not, the tax owed is IDR 40,000.",
    ],
  });
});

test("a claim reinvested in full shows nothing left and no tax", () => {
  const read = claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [{ day: "2025-07-01", symbol: "BBRI", amount: rupiah(1_000_000n) }],
    "2025-08-01",
    [],
  );
  expect(taxView(read)[1]?.lines).toEqual([
    "BBCA, received 2025-06-10: gross IDR 1,000,000, reinvested IDR 1,000,000, nothing left to " +
      "reinvest.",
  ]);
});

test("a missed deadline shows the tax owed, with its note and the total", () => {
  const read = claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [],
    "2026-07-01",
    [],
  );
  expect(taxView(read).slice(1)).toEqual([
    {
      heading: "Claims",
      lines: [
        "BBCA, received 2025-06-10: gross IDR 1,000,000, reinvested IDR 0, IDR 1,000,000 not " +
          "reinvested by 2026-03-31, so the tax of IDR 100,000 is owed.",
      ],
    },
    {
      heading: "Tax owed",
      lines: [
        "IDR 100,000 in all.",
        "BBCA: IDR 1,000,000 of the dividend received on 2025-06-10 was not reinvested by " +
          "2026-03-31, so its tax of IDR 100,000 is owed, from 2025-06-10.",
      ],
    },
  ]);
});

test("a dividend from before the exemption is listed as not exemptable with its tax", () => {
  const read = claimsReport(
    RULES,
    [{ received: "2021-02-01", symbol: "TLKM", gross: rupiah(500_000n) }],
    [],
    "2025-08-01",
    [],
  );
  expect(taxView(read)[1]?.lines).toEqual([
    "TLKM, received 2021-02-01: no exemption on that day, so the tax of IDR 50,000 is owed.",
  ]);
});

test("a purchase that covers nothing is listed as such", () => {
  const read = claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [
      { day: "2025-05-01", symbol: "ASII", amount: rupiah(300_000n) },
      { day: "2025-07-01", symbol: "BBRI", amount: rupiah(1_000_000n) },
    ],
    "2025-08-01",
    [],
  );
  expect(taxView(read)[1]?.lines).toEqual([
    "BBCA, received 2025-06-10: gross IDR 1,000,000, reinvested IDR 1,000,000, nothing left to " +
      "reinvest.",
    "The purchase of ASII on 2025-05-01 for IDR 300,000 covered no claim: no dividend was open " +
      "before it, or every deadline had passed.",
  ]);
});
