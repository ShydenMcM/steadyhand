import { expect, test } from "vitest";
import {
  claimsReport,
  coverClaims,
  DividendClaim,
  openClaim,
  type DividendReceived,
  type Reinvestment,
} from "../src/claims.ts";
import { IDR, Money } from "../src/money.ts";
import { IdxMarketRules } from "../src/rules.ts";
import fixture from "./parity-claims.json" with { type: "json" };

// The parity harness for the exemption claims (#255 AC1, spec §9.2): seeded dividends received,
// some before PMK 18/2021, and purchases on any day, some before every dividend and some after
// every deadline, that Python's `cover_claims` (a day at a time, in date order) and the deadline
// step of `settle_claims` answered (`scripts/core_fixtures.py`). Core must leave each claim the
// same part to reinvest and the same protections, owe the same tax and say the same notes.
// Python's claims carry the deadline counted from the day received, as core's do: the case where
// Python's own engine counts from the ex-date is named in `claims.test.ts`.

interface Claim {
  readonly symbol: string;
  readonly received: string;
  readonly gross: string;
  readonly deadline: string;
  readonly uncovered: string;
  readonly tax: string;
  readonly protections: readonly (readonly string[])[];
}

interface Case {
  readonly name: string;
  readonly today: string;
  readonly dividends: readonly { received: string; symbol: string; gross: string }[];
  readonly purchases: readonly { day: string; amount: string }[];
  readonly claims: readonly Claim[];
  readonly notExemptable: readonly { symbol: string; received: string; tax: string }[];
  readonly owed: string;
  readonly notes: readonly string[];
}

const RULES = new IdxMarketRules();
const CASES: readonly Case[] = fixture.cases;

const rp = (amount: string): Money => new Money(BigInt(amount), IDR);

const dividendsOf = (parity: Case): DividendReceived[] =>
  parity.dividends.map((entry) => ({
    received: entry.received,
    symbol: entry.symbol,
    gross: rp(entry.gross),
  }));

const purchasesOf = (parity: Case): Reinvestment[] =>
  parity.purchases.map((entry) => ({ day: entry.day, symbol: "BBRI", amount: rp(entry.amount) }));

test(`the harness compares ${CASES.length.toString()} sets of entries from seed ${fixture.seed}`, () => {
  expect(CASES.length).toBeGreaterThan(0);
});

test.each(CASES)("core's claims report for $name is Python's", (parity) => {
  const read = claimsReport(RULES, dividendsOf(parity), purchasesOf(parity), parity.today);
  if (read.report === null) {
    throw new Error(`${parity.name}: no report`);
  }
  expect(
    read.report.rows.map((row) => [
      row.symbol,
      row.received,
      row.gross.amount.toString(),
      row.deadline,
      row.toReinvest.amount.toString(),
      row.tax.amount.toString(),
    ]),
  ).toEqual(
    parity.claims.map((claim) => [
      claim.symbol,
      claim.received,
      claim.gross,
      claim.deadline,
      claim.uncovered,
      claim.tax,
    ]),
  );
  expect(
    read.report.notExemptable.map((entry) => [
      entry.symbol,
      entry.received,
      entry.tax.amount.toString(),
    ]),
  ).toEqual(parity.notExemptable.map((entry) => [entry.symbol, entry.received, entry.tax]));
  expect(read.report.owed.amount.toString()).toBe(parity.owed);
  expect(read.report.notes.map((found) => found.code)).toEqual(parity.notes);
});

test.each(CASES)("core's protections for $name are Python's", (parity) => {
  const claims = dividendsOf(parity)
    .map((dividend) => openClaim(RULES, dividend))
    .filter((claim): claim is DividendClaim => claim !== null)
    .sort(
      (first, second) =>
        first.received.localeCompare(second.received) || first.symbol.localeCompare(second.symbol),
    );
  const byDay = purchasesOf(parity).sort((first, second) => first.day.localeCompare(second.day));
  const covered = coverClaims(claims, byDay, RULES);
  expect(
    covered.map((claim) =>
      claim.protections.map((protection) => [
        protection.amount.amount.toString(),
        protection.until,
      ]),
    ),
  ).toEqual(parity.claims.map((claim) => claim.protections));
});
