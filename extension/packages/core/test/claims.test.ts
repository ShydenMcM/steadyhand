import { expect, test } from "vitest";
import {
  claimsReport,
  coverClaims,
  DividendClaim,
  openClaim,
  Protection,
  settleBreaks,
  settleDeadlines,
  type BreakDay,
  type BreakRules,
  type ClaimRules,
  type DeadlineDay,
  type DividendReceived,
  type Reinvestment,
} from "../src/claims.ts";
import { Currency, CurrencyMismatchError, IDR, Money } from "../src/money.ts";
import { note, NOTE_CODES } from "../src/notes.ts";
import { IdxMarketRules } from "../src/rules.ts";

// #255 (spec §9.2): the dividend reinvestment exemption's claims, their covering by the
// purchases the user enters and the tax owed when a deadline is missed, ported from Python's
// `steadyhand.exemption` (`tests/engine/test_exemption.py`, one test per case). Python's claim
// has an ex-date and a pay date; the user enters only the date the dividend was received, so the
// ex-date cases are not ported and the pay date is the date received. Python's checks that each
// argument has the right type are TypeScript's compiler here. Breaks and protections falling
// away are #256.

const RULES = new IdxMarketRules();
const RECEIVED = "2025-06-24";
const DEADLINE = "2026-03-31";
const UNTIL = "2027-12-31"; // a 2025 purchase is held through 31 Dec 2027
const USD = new Currency("USD", 2n);

const rp = (amount: bigint): Money => new Money(amount, IDR);

/** IDX, but the dividend tax doubles to 20% from 2026. */
const RATE_RISES: ClaimRules = {
  dividendTax: (gross, on) => {
    const tax = RULES.dividendTax(gross, on);
    return on >= "2026-01-01" ? tax.plus(tax) : tax;
  },
  reinvestmentDeadline: (day) => RULES.reinvestmentDeadline(day),
  protectionEnd: (day) => RULES.protectionEnd(day),
};

/** IDX, but in a market that taxes no dividend. */
const TAX_FREE: ClaimRules = {
  dividendTax: (gross) => Money.zero(gross.currency),
  reinvestmentDeadline: (day) => RULES.reinvestmentDeadline(day),
  protectionEnd: (day) => RULES.protectionEnd(day),
};

const claim = (uncovered = 1_000n, ...protections: Protection[]): DividendClaim =>
  new DividendClaim("BBCA", RECEIVED, rp(1_000n), DEADLINE, rp(uncovered), protections);

const buy = (day: string, amount: bigint): Reinvestment => ({
  day,
  symbol: "BBRI",
  amount: rp(amount),
});

const settle = (
  claims: readonly DividendClaim[],
  day: string,
  purchases: readonly Reinvestment[] = [],
  rules: ClaimRules = RULES,
): DeadlineDay => settleDeadlines(coverClaims(claims, purchases, rules), day, rules);

const OLDER = new DividendClaim("BBCA", "2025-06-10", rp(1_000n), DEADLINE, rp(1_000n));

test("a claim may be split between uncovered and protected parts", () => {
  const split = claim(400n, new Protection(rp(250n), UNTIL), new Protection(rp(350n), UNTIL));
  expect(split.uncovered).toEqual(rp(400n));
  // 400 + 250 + 350 = the gross 1,000
  expect(split.protections.map((protection) => protection.amount)).toEqual([rp(250n), rp(350n)]);
});

test("a protection is a positive amount", () => {
  expect(() => new Protection(rp(0n), DEADLINE)).toThrow(
    new RangeError("a protection must be positive, got IDR 0"),
  );
});

test("a claim is received no later than its deadline", () => {
  expect(() => new DividendClaim("BBCA", RECEIVED, rp(1_000n), "2025-06-23", rp(1_000n))).toThrow(
    new RangeError("BBCA: a claim needs received <= deadline, got 2025-06-24 and 2025-06-23"),
  );
});

test("a claim on its deadline day is valid", () => {
  expect(new DividendClaim("BBCA", RECEIVED, rp(1_000n), RECEIVED, rp(1_000n)).deadline).toBe(
    RECEIVED,
  );
});

test("a claim's gross is in rupiah", () => {
  expect(
    () => new DividendClaim("BBCA", RECEIVED, new Money(1_000n, USD), DEADLINE, rp(1_000n)),
  ).toThrow(new CurrencyMismatchError(IDR, USD));
});

test("a claim's uncovered part is in rupiah", () => {
  expect(
    () => new DividendClaim("BBCA", RECEIVED, rp(1_000n), DEADLINE, new Money(1_000n, USD)),
  ).toThrow(new CurrencyMismatchError(IDR, USD));
});

test("a claim's protections are in rupiah", () => {
  expect(() => claim(0n, new Protection(new Money(1n, USD), DEADLINE))).toThrow(
    CurrencyMismatchError,
  );
});

const NOT_POSITIVE = "BBCA: a claim's gross must be positive and its uncovered part not negative";

test("a claim's gross is positive", () => {
  expect(() => new DividendClaim("BBCA", RECEIVED, rp(0n), DEADLINE, rp(0n))).toThrow(
    new RangeError(NOT_POSITIVE),
  );
});

test("a claim's uncovered part is not negative", () => {
  expect(() => new DividendClaim("BBCA", RECEIVED, rp(1_000n), DEADLINE, rp(-1n))).toThrow(
    new RangeError(NOT_POSITIVE),
  );
});

test("a claim's parts cannot exceed its gross", () => {
  expect(() => claim(401n, new Protection(rp(600n), UNTIL))).toThrow(
    new RangeError(
      "BBCA: uncovered IDR 401 and protected IDR 600 exceed the gross dividend IDR 1,000",
    ),
  );
});

test("a purchase covers a claim with its value, whatever stock it buys", () => {
  const after = settle([claim()], "2025-07-01", [buy("2025-07-01", 600n)]);
  // 1,000 - 600 = 400 still to reinvest.
  expect(after).toEqual({
    claims: [claim(400n, new Protection(rp(600n), UNTIL))],
    tax: rp(0n),
    notes: [],
  });
});

test("purchases cover the oldest receipt first and spill into the next", () => {
  const after = settle([claim(), OLDER], "2025-07-01", [
    buy("2025-07-01", 1_200n),
    buy("2025-07-01", 300n),
  ]);
  // The 1,200 purchase covers the older claim's 1,000 and 200 of the newer; the 300 covers 300.
  expect(after.claims).toEqual([
    claim(500n, new Protection(rp(200n), UNTIL), new Protection(rp(300n), UNTIL)),
    new DividendClaim("BBCA", "2025-06-10", rp(1_000n), DEADLINE, rp(0n), [
      new Protection(rp(1_000n), UNTIL),
    ]),
  ]);
});

test("claims received on the same day are covered in order of their stock", () => {
  const tlkm = new DividendClaim("TLKM", RECEIVED, rp(1_000n), DEADLINE, rp(1_000n));
  const after = coverClaims([tlkm, claim()], [buy("2025-07-01", 600n)], RULES);
  expect(after).toEqual([tlkm, claim(400n, new Protection(rp(600n), UNTIL))]);
});

test("a purchase larger than every claim leaves the rest unclaimed", () => {
  const after = settle([claim()], "2025-07-01", [buy("2025-07-01", 5_000n)]);
  expect(after.claims).toEqual([claim(0n, new Protection(rp(1_000n), UNTIL))]);
});

test("a purchase the day before the dividend was received covers nothing", () => {
  const after = settle([claim()], "2025-06-23", [buy("2025-06-23", 600n)]);
  expect(after.claims[0]?.uncovered).toEqual(rp(1_000n));
});

test("a purchase on the day the dividend was received covers", () => {
  const after = settle([claim()], RECEIVED, [buy(RECEIVED, 600n)]);
  expect(after.claims[0]?.uncovered).toEqual(rp(400n));
});

test("a purchase on the deadline itself covers", () => {
  const after = settle([claim()], DEADLINE, [buy(DEADLINE, 600n)]);
  expect(after.claims[0]?.uncovered).toEqual(rp(400n));
});

test("a purchase is protected from its own year, not the dividend's", () => {
  // Received in 2025, reinvested in 2026: held through 31 December 2028.
  const after = coverClaims([claim()], [buy("2026-02-02", 600n)], RULES);
  expect(after).toEqual([claim(400n, new Protection(rp(600n), "2028-12-31"))]);
});

test("what misses the deadline is taxed the next day and the claim keeps its protection", () => {
  const protectedPart = new Protection(rp(600n), UNTIL);
  const after = settle([claim(400n, protectedPart)], "2026-04-01");
  expect(after).toEqual({
    claims: [claim(0n, protectedPart)],
    tax: rp(40n), // 10% of the 400 not reinvested
    notes: [
      note(
        NOTE_CODES.EXEMPTION_DEADLINE_MISSED,
        "BBCA: IDR 400 of the dividend received on 2025-06-24 was not reinvested by " +
          "2026-03-31, so its tax of IDR 40 is owed, from 2025-06-24",
      ),
    ],
  });
});

test("nothing is taxed on the deadline itself", () => {
  expect(settle([claim()], DEADLINE)).toEqual({ claims: [claim()], tax: rp(0n), notes: [] });
});

test("a claim with nothing left after its deadline is closed", () => {
  const after = settle([claim(999n)], "2026-04-01");
  expect(after.tax).toEqual(rp(100n)); // 99.9 rounds up
  expect(after.claims).toEqual([]);
});

test("a claim fully reinvested by its deadline books nothing", () => {
  const protectedPart = new Protection(rp(1_000n), UNTIL);
  expect(settle([claim(0n, protectedPart)], "2026-04-01")).toEqual({
    claims: [claim(0n, protectedPart)],
    tax: rp(0n),
    notes: [],
  });
});

test("the deadline tax is at the rate in force on the day received", () => {
  const after = settle([claim(400n)], "2026-04-01", [], RATE_RISES);
  expect(after.tax).toEqual(rp(40n)); // 10% as on 24 June 2025, not 2026's 20%
});

test("an untaxed market books no zero tax and emits no note", () => {
  expect(settle([claim(400n)], "2026-04-01", [], TAX_FREE)).toEqual({
    claims: [],
    tax: rp(0n),
    notes: [],
  });
});

test("a purchase used up by an older claim leaves the newer one untouched", () => {
  const after = settle([claim(), OLDER], "2025-07-01", [buy("2025-07-01", 1_000n)]);
  expect(after.claims).toEqual([
    claim(),
    new DividendClaim("BBCA", "2025-06-10", rp(1_000n), DEADLINE, rp(0n), [
      new Protection(rp(1_000n), UNTIL),
    ]),
  ]);
});

const received = (day: string, symbol: string, gross: bigint): DividendReceived => ({
  received: day,
  symbol,
  gross: rp(gross),
});

test("a dividend received opens a claim for its gross", () => {
  expect(openClaim(RULES, received(RECEIVED, "BBCA", 1_000n))).toEqual(claim());
});

test("the deadline counts from the year received, not the ex-date's", () => {
  // Paid on 5 January 2026 for an ex-date in December 2025: Python counted from 2025 and gave
  // 31 March 2026.
  expect(openClaim(RULES, received("2026-01-05", "BBCA", 1_000n))?.deadline).toBe("2027-03-31");
});

test("a dividend received before PMK 18/2021 opens no claim", () => {
  expect(openClaim(RULES, received("2021-02-16", "BBCA", 1_000n))).toBeNull();
});

test("with no dividend entered the claims are missing and give no figure", () => {
  expect(claimsReport(RULES, [], [buy("2025-07-01", 600n)], "2026-04-01")).toEqual({
    report: null,
    missing: [
      note(
        NOTE_CODES.MISSING_DIVIDENDS,
        "no dividend received is entered: enter each one on the Tax tab",
      ),
    ],
  });
});

const DIVIDENDS = [
  received("2025-09-10", "TLKM", 2_000n),
  received(RECEIVED, "BBCA", 1_000n),
  received("2021-01-15", "BBRI", 1_000n),
];

// Entered out of order: 1 June 2025 comes before any claim; 1 July covers BBCA's 1,000 (TLKM is
// not received yet); 1 October covers 500 of TLKM's 2,000.
const PURCHASES = [buy("2025-10-01", 500n), buy("2025-06-01", 500n), buy("2025-07-01", 1_200n)];
const LATE = buy("2026-05-01", 100n); // after every deadline

test("each dividend received is a row, oldest first, with what is left and its deadline", () => {
  const read = claimsReport(RULES, DIVIDENDS, PURCHASES, "2026-03-31");
  expect(read.report?.rows).toEqual([
    {
      symbol: "BBCA",
      received: RECEIVED,
      gross: rp(1_000n),
      reinvested: rp(1_000n),
      toReinvest: rp(0n),
      deadline: DEADLINE,
      tax: rp(0n),
      missed: false,
    },
    {
      symbol: "TLKM",
      received: "2025-09-10",
      gross: rp(2_000n),
      reinvested: rp(500n),
      toReinvest: rp(1_500n),
      deadline: DEADLINE,
      tax: rp(150n), // owed if 31 March 2026 passes with 1,500 left
      missed: false,
    },
  ]);
  expect(read.report?.owed).toEqual(rp(0n));
  expect(read.report?.notes).toEqual([]);
});

test("a deadline passed shows its tax as owed, with the note", () => {
  const read = claimsReport(RULES, DIVIDENDS, PURCHASES, "2026-04-01");
  expect(read.report?.rows.map((row) => [row.symbol, row.missed, row.tax])).toEqual([
    ["BBCA", false, rp(0n)],
    ["TLKM", true, rp(150n)],
  ]);
  expect(read.report?.owed).toEqual(rp(150n));
  expect(read.report?.notes).toEqual([
    note(
      NOTE_CODES.EXEMPTION_DEADLINE_MISSED,
      "TLKM: IDR 1,500 of the dividend received on 2025-09-10 was not reinvested by " +
        "2026-03-31, so its tax of IDR 150 is owed, from 2025-09-10",
    ),
  ]);
});

test("a dividend received before the exemption is listed with the tax it owes", () => {
  const read = claimsReport(RULES, DIVIDENDS, PURCHASES, "2026-04-01");
  expect(read.report?.notExemptable).toEqual([
    { symbol: "BBRI", received: "2021-01-15", gross: rp(1_000n), tax: rp(100n) },
  ]);
});

test("a purchase that covers nothing is listed as such", () => {
  const read = claimsReport(RULES, DIVIDENDS, [LATE, ...PURCHASES], "2026-05-01");
  expect(read.report?.idle).toEqual([buy("2025-06-01", 500n), LATE]);
});

test("purchases cover in the order of their dates, whatever order they were entered in", () => {
  const entered = claimsReport(RULES, DIVIDENDS, PURCHASES, "2026-04-01");
  const sorted = claimsReport(RULES, DIVIDENDS, [...PURCHASES].reverse(), "2026-04-01");
  expect(sorted).toEqual(entered);
});

test("an entry dated after today is refused", () => {
  expect(() => claimsReport(RULES, DIVIDENDS, [LATE], "2026-02-01")).toThrow(
    new RangeError("an entry is dated 2026-05-01, after today, 2026-02-01"),
  );
  const early = [received("2025-09-10", "TLKM", 2_000n)];
  expect(() => claimsReport(RULES, early, [], "2025-09-09")).toThrow(
    new RangeError("an entry is dated 2025-09-10, after today, 2025-09-09"),
  );
});

// #256: protections falling away, the settlement grace and breaks, ported from the rest of
// Python's `settle_claims` (`test_exemption.py`, one test per case). Python judges every close
// and closes a claim with nothing left; here each portfolio read after a close is judged, and
// every claim stays, because the claims list shows one row per dividend received. The deadline
// step is #255's `settleDeadlines`.

const JUL1 = "2025-07-01"; // settles on 3 July
const JUL2 = "2025-07-02";
const JUL3 = "2025-07-03";

const BREAK_RULES: BreakRules = RULES;
const breakRules = (rules: ClaimRules): BreakRules => ({
  ...rules,
  settlementDate: (day) => RULES.settlementDate(day),
});

const close = (
  claims: readonly DividendClaim[],
  day: string,
  invested: bigint,
  since: string | null = null,
  rules: BreakRules = BREAK_RULES,
): BreakDay => settleBreaks(claims, rp(invested), since, day, rules);

test("protections past their date fall away and leave the claim with nothing protected", () => {
  const ending = new Protection(rp(600n), JUL1);
  const first = close([claim(0n, ending)], JUL1, 0n); // protected through 1 July, still counted
  expect([first.claims, first.since]).toEqual([[claim(0n, ending)], JUL1]);
  const after = close([claim(0n, ending)], JUL2, 0n, JUL1);
  expect([after.claims, after.since, after.tax]).toEqual([[claim(0n)], null, rp(0n)]);
});

test("a shortfall within the settlement grace keeps the claim", () => {
  const held = claim(0n, new Protection(rp(1_000n), UNTIL));
  const first = close([held], JUL1, 400n);
  expect([first.claims, first.since, first.tax]).toEqual([[held], JUL1, rp(0n)]);
  const second = close([held], JUL2, 400n, JUL1); // the shortfall's first day is kept
  expect([second.claims, second.since, second.tax]).toEqual([[held], JUL1, rp(0n)]);
});

test("a shortfall gone before the grace ends clears its day", () => {
  const held = claim(0n, new Protection(rp(1_000n), UNTIL));
  const after = close([held], JUL2, 1_000n, JUL1); // a rotation: bought back within the cycle
  expect([after.claims, after.since, after.tax]).toEqual([[held], null, rp(0n)]);
});

test("a shortfall still there at the settlement close breaks", () => {
  const held = claim(0n, new Protection(rp(1_000n), UNTIL));
  const after = close([held], JUL3, 400n, JUL1);
  // 1,000 protected against 400 invested: 600 breaks, and 10% of it is owed.
  expect(after).toEqual({
    claims: [claim(0n, new Protection(rp(400n), UNTIL))],
    since: null,
    tax: rp(60n),
    notes: [
      note(
        NOTE_CODES.EXEMPTION_CLAIM_BROKEN,
        "BBCA: IDR 600 reinvested from the dividend received on 2025-06-24 was no longer " +
          "invested when the settlement grace ended, so its tax of IDR 60 is owed, from " +
          "2025-06-24",
      ),
    ],
  });
});

test("breaks take the latest protection first", () => {
  const older = new DividendClaim("BBCA", "2025-06-10", rp(1_000n), DEADLINE, rp(500n), [
    new Protection(rp(500n), UNTIL),
  ]);
  const later = claim(500n, new Protection(rp(500n), "2028-12-31"));
  const after = close([older, later], JUL3, 300n, JUL1);
  // 1,000 protected against 300 invested: 700 breaks, the 2028 protection's 500 first, then
  // 200 of the 2027 one. Tax is 10% of each claim's part, 20 and 50, in the claims' order.
  expect(after.claims).toEqual([
    new DividendClaim("BBCA", "2025-06-10", rp(1_000n), DEADLINE, rp(500n), [
      new Protection(rp(300n), UNTIL),
    ]),
    claim(500n),
  ]);
  expect(after.tax).toEqual(rp(70n));
  expect(after.notes.map((found) => found.text.split(" reinvested")[0])).toEqual([
    "BBCA: IDR 200",
    "BBCA: IDR 500",
  ]);
});

test("equal dates break the newest claim and its last protection first", () => {
  const older = new DividendClaim("BBCA", "2025-06-10", rp(1_000n), DEADLINE, rp(0n), [
    new Protection(rp(1_000n), UNTIL),
  ]);
  const newer = claim(0n, new Protection(rp(600n), UNTIL), new Protection(rp(400n), UNTIL));
  const after = close([older, newer], JUL3, 1_700n, JUL1);
  // 2,000 protected against 1,700: 300 breaks from the newer claim's last protection.
  expect(after.claims).toEqual([
    older,
    claim(0n, new Protection(rp(600n), UNTIL), new Protection(rp(100n), UNTIL)),
  ]);
});

test("claims received on the same day break the later stock first", () => {
  const bbca = claim(0n, new Protection(rp(500n), UNTIL));
  const tlkm = new DividendClaim("TLKM", RECEIVED, rp(1_000n), DEADLINE, rp(500n), [
    new Protection(rp(500n), UNTIL),
  ]);
  const after = close([bbca, tlkm], JUL3, 700n, JUL1);
  expect(after.claims).toEqual([
    bbca,
    new DividendClaim("TLKM", RECEIVED, rp(1_000n), DEADLINE, rp(500n), [
      new Protection(rp(200n), UNTIL),
    ]),
  ]);
});

test("a broken claim is taxed at the rate of the day received", () => {
  const held = claim(0n, new Protection(rp(1_000n), UNTIL));
  const after = close([held], "2026-07-03", 400n, "2026-07-01", breakRules(RATE_RISES));
  expect(after.tax).toEqual(rp(60n)); // 10% as on 24 June 2025, not 2026's 20%
});

test("an untaxed market breaks the claim without a tax or a note", () => {
  const held = claim(0n, new Protection(rp(1_000n), UNTIL));
  const after = close([held], JUL3, 400n, JUL1, breakRules(TAX_FREE));
  expect([after.tax, after.notes]).toEqual([rp(0n), []]);
  expect(after.claims).toEqual([claim(0n, new Protection(rp(400n), UNTIL))]);
});

test("each break rounds its tax up on its own", () => {
  // Rp2 broken in two pieces of 1 owes 1 + 1 = 2, where the tax on Rp2 at once is 0.2, so 1.
  const split = new DividendClaim("BBCA", RECEIVED, rp(2n), DEADLINE, rp(0n), [
    new Protection(rp(1n), UNTIL),
  ]);
  const other = new DividendClaim("TLKM", RECEIVED, rp(2n), DEADLINE, rp(0n), [
    new Protection(rp(1n), UNTIL),
  ]);
  const after = close([split, other], JUL3, 0n, JUL1);
  expect([after.tax, after.notes.length]).toEqual([rp(2n), 2]);
  expect(RULES.dividendTax(rp(2n), RECEIVED)).toEqual(rp(1n));
});

test("with no shortfall nothing breaks and no grace starts", () => {
  const held = claim(0n, new Protection(rp(1_000n), UNTIL));
  expect(close([held], JUL1, 1_000n)).toEqual({
    claims: [held],
    since: null,
    tax: rp(0n),
    notes: [],
  });
});
