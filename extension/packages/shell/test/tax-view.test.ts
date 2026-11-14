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

// #256 (Shyden 2026-11-13: the report on the Tax tab, below the claims list): what is still held,
// until when, and the cost basis named as missing until a portfolio read after a close gives it.

const MISSING_COST_BASIS =
  "No portfolio page read after a close gives the cost basis still invested: read it, so a " +
  "reinvested dividend no longer invested can be found.";

const heldReport = (invested: bigint | null): ReturnType<typeof claimsReport> =>
  claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [{ day: "2025-07-01", symbol: "BBRI", amount: rupiah(600_000n) }],
    "2025-08-01",
    invested === null ? [] : [{ day: "2025-07-01", invested: rupiah(invested) }],
  );

test("what is held is listed below the claims, with the day it may be sold", () => {
  expect(taxView(heldReport(5_000_000n))[2]).toEqual({
    heading: "Held",
    lines: [
      "BBCA, received 2025-06-10: IDR 600,000 reinvested must stay invested until 2027-12-31.",
    ],
  });
});

test("with something held and no portfolio read, the cost basis is named as missing", () => {
  expect(taxView(heldReport(null))[2]?.lines).toEqual([
    "BBCA, received 2025-06-10: IDR 600,000 reinvested must stay invested until 2027-12-31.",
    MISSING_COST_BASIS,
  ]);
});

test("with nothing held there is no held section", () => {
  const read = claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [],
    "2025-08-01",
    [],
  );
  expect(taxView(read).map((section) => section.heading)).toEqual(["Estimate", "Claims"]);
});

test("a break's tax is owed with its note, and the missing cost basis is not repeated there", () => {
  // 600,000 held against 100,000 invested on Tuesday 1 July, still so on Thursday 3 July, when
  // 1 July's trades settle: 500,000 breaks and 50,000 is owed.
  const read = claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [{ day: "2025-07-01", symbol: "BBRI", amount: rupiah(600_000n) }],
    "2025-08-01",
    [
      { day: "2025-07-01", invested: rupiah(100_000n) },
      { day: "2025-07-03", invested: rupiah(100_000n) },
    ],
  );
  expect(taxView(read).slice(2)).toEqual([
    {
      heading: "Held",
      lines: [
        "BBCA, received 2025-06-10: IDR 100,000 reinvested must stay invested until 2027-12-31.",
      ],
    },
    {
      heading: "Tax owed",
      lines: [
        "IDR 50,000 in all.",
        "BBCA: IDR 500,000 reinvested from the dividend received on 2025-06-10 was no longer " +
          "invested when the settlement grace ended, so its tax of IDR 50,000 is owed, from " +
          "2025-06-10.",
      ],
    },
  ]);
});

test("with tax owed and the cost basis missing, the missing note stays with what is held", () => {
  const read = claimsReport(
    RULES,
    [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }],
    [{ day: "2025-07-01", symbol: "BBRI", amount: rupiah(600_000n) }],
    "2026-04-01",
    [],
  );
  expect(taxView(read).slice(2)).toEqual([
    {
      heading: "Held",
      lines: [
        "BBCA, received 2025-06-10: IDR 600,000 reinvested must stay invested until 2027-12-31.",
        MISSING_COST_BASIS,
      ],
    },
    {
      heading: "Tax owed",
      lines: [
        "IDR 40,000 in all.",
        "BBCA: IDR 400,000 of the dividend received on 2025-06-10 was not reinvested by " +
          "2026-03-31, so its tax of IDR 40,000 is owed, from 2025-06-10.",
      ],
    },
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
