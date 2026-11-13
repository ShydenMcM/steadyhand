/** The dividend reinvestment exemption's claims (spec §9.2, #255), ported from Python's
 * `steadyhand.exemption`.
 *
 * A dividend received while `fees.json` has an exemption row opens a claim: its tax is not owed
 * if it is reinvested by the deadline and the investment is held. The extension cannot see past
 * dividends or purchases, so the user enters both. Python counts the deadline from the ex-date
 * because its engine never knew the receipt date; here it counts from the date received
 * (PMK 18/2021). Every figure is an estimate that assumes the yearly realisation reports are filed
 * (docs/research/t-tax.md §7). Breaks against the cost basis still invested are #256. */

import type { Day } from "./broker-view.ts";
import { CurrencyMismatchError, IDR, Money } from "./money.ts";
import { missingDividends, note, NOTE_CODES, type Note } from "./notes.ts";
import type { IdxMarketRules } from "./rules.ts";

/** The three rules the claims read. */
export type ClaimRules = Pick<
  IdxMarketRules,
  "dividendTax" | "reinvestmentDeadline" | "protectionEnd"
>;

/** A dividend the user received: the day it was paid to them, its stock and its gross. */
export interface DividendReceived {
  readonly received: Day;
  readonly symbol: string;
  readonly gross: Money;
}

/** A purchase the user made to reinvest dividends: its value, not its costs. */
export interface Reinvestment {
  readonly day: Day;
  readonly symbol: string;
  readonly amount: Money;
}

const requireRupiah = (amount: Money): void => {
  if (!amount.currency.equals(IDR)) {
    throw new CurrencyMismatchError(IDR, amount.currency);
  }
};

/** Part of a claim reinvested by one purchase, which must stay invested through `until`. */
export class Protection {
  readonly amount: Money;
  readonly until: Day;

  constructor(amount: Money, until: Day) {
    if (amount.amount <= 0n) {
      throw new RangeError(`a protection must be positive, got ${amount.toString()}`);
    }
    this.amount = amount;
    this.until = until;
  }
}

/** A dividend received whose tax waits on its reinvestment.
 *
 * `uncovered` is the part of `gross` not yet reinvested; `protections` are the reinvested parts,
 * each held through its own date. Together they never exceed `gross`. */
export class DividendClaim {
  readonly symbol: string;
  readonly received: Day;
  readonly gross: Money;
  readonly deadline: Day;
  readonly uncovered: Money;
  readonly protections: readonly Protection[];

  constructor(
    symbol: string,
    received: Day,
    gross: Money,
    deadline: Day,
    uncovered: Money,
    protections: readonly Protection[] = [],
  ) {
    if (received > deadline) {
      throw new RangeError(
        `${symbol}: a claim needs received <= deadline, got ${received} and ${deadline}`,
      );
    }
    requireRupiah(gross);
    requireRupiah(uncovered);
    let covered = Money.zero(IDR);
    for (const protection of protections) {
      requireRupiah(protection.amount);
      covered = covered.plus(protection.amount);
    }
    if (gross.amount <= 0n || uncovered.amount < 0n) {
      throw new RangeError(
        `${symbol}: a claim's gross must be positive and its uncovered part not negative`,
      );
    }
    if (uncovered.plus(covered).gt(gross)) {
      throw new RangeError(
        `${symbol}: uncovered ${uncovered.toString()} and protected ${covered.toString()} ` +
          `exceed the gross dividend ${gross.toString()}`,
      );
    }
    this.symbol = symbol;
    this.received = received;
    this.gross = gross;
    this.deadline = deadline;
    this.uncovered = uncovered;
    this.protections = protections;
  }
}

/** The order claims are covered in: oldest receipt first, then the stock. */
const byAge = (first: DividendClaim, second: DividendClaim): ReturnType<string["localeCompare"]> =>
  first.received.localeCompare(second.received) || first.symbol.localeCompare(second.symbol);

/** The claim `dividend` opens, or `null` when no exemption applies on the day it was received. */
export const openClaim = (rules: ClaimRules, dividend: DividendReceived): DividendClaim | null => {
  const deadline = rules.reinvestmentDeadline(dividend.received);
  return deadline === null
    ? null
    : new DividendClaim(
        dividend.symbol,
        dividend.received,
        dividend.gross,
        deadline,
        dividend.gross,
      );
};

/** Cover open claims with `purchases`, in the order given (Python's `cover_claims`).
 *
 * Each purchase covers the claims received on or before its day whose deadline it meets, oldest
 * receipt first, whatever stock it buys (t-tax.md §4). Each amount covered is protected until
 * the rules' `protectionEnd` of the purchase's day. The claims keep their order. */
export const coverClaims = (
  claims: readonly DividendClaim[],
  purchases: readonly Reinvestment[],
  rules: ClaimRules,
): DividendClaim[] => {
  const slots = claims.map((claim) => ({ claim }));
  const oldestFirst = [...slots].sort((first, second) => byAge(first.claim, second.claim));
  for (const purchase of purchases) {
    let left = purchase.amount;
    for (const slot of oldestFirst) {
      if (left.amount === 0n) {
        break;
      }
      const claim = slot.claim;
      const inTime = claim.received <= purchase.day && purchase.day <= claim.deadline;
      if (!inTime || claim.uncovered.amount === 0n) {
        continue;
      }
      const taken = left.lt(claim.uncovered) ? left : claim.uncovered;
      const protection = new Protection(taken, rules.protectionEnd(purchase.day));
      slot.claim = new DividendClaim(
        claim.symbol,
        claim.received,
        claim.gross,
        claim.deadline,
        claim.uncovered.minus(taken),
        [...claim.protections, protection],
      );
      left = left.minus(taken);
    }
  }
  return slots.map((slot) => slot.claim);
};

/** The claims at the end of `day`, with the tax their missed deadlines owe. */
export interface DeadlineDay {
  readonly claims: readonly DividendClaim[];
  readonly tax: Money;
  readonly notes: readonly Note[];
}

const deadlineMissed = (claim: DividendClaim, tax: Money): Note =>
  note(
    NOTE_CODES.EXEMPTION_DEADLINE_MISSED,
    `${claim.symbol}: ${claim.uncovered.toString()} of the dividend received on ` +
      `${claim.received} was not reinvested by ${claim.deadline}, so its tax of ` +
      `${tax.toString()} is owed, from ${claim.received}`,
  );

/** Python's `settle_claims`, its deadline step: what is still uncovered after its deadline owes
 * the tax at the rate of the day received, rounded up. A claim with nothing left to reinvest and
 * nothing protected is closed. */
export const settleDeadlines = (
  claims: readonly DividendClaim[],
  day: Day,
  rules: ClaimRules,
): DeadlineDay => {
  let tax = Money.zero(IDR);
  const notes: Note[] = [];
  const kept: DividendClaim[] = [];
  for (const claim of claims) {
    let current = claim;
    if (day > claim.deadline && claim.uncovered.amount > 0n) {
      const owed = rules.dividendTax(claim.uncovered, claim.received);
      if (owed.amount > 0n) {
        tax = tax.plus(owed);
        notes.push(deadlineMissed(claim, owed));
      }
      current = new DividendClaim(
        claim.symbol,
        claim.received,
        claim.gross,
        claim.deadline,
        Money.zero(IDR),
        claim.protections,
      );
    }
    if (current.uncovered.amount > 0n || current.protections.length > 0) {
      kept.push(current);
    }
  }
  return { claims: kept, tax, notes };
};

/** One dividend received, as the claims list shows it. */
export interface ClaimRow {
  readonly symbol: string;
  readonly received: Day;
  readonly gross: Money;
  readonly reinvested: Money;
  readonly toReinvest: Money;
  readonly deadline: Day;
  /** The tax on what is left to reinvest: owed when `missed`, else owed if the deadline passes. */
  readonly tax: Money;
  readonly missed: boolean;
}

/** A dividend received on a day with no exemption: its tax is owed. */
export interface NotExemptable {
  readonly symbol: string;
  readonly received: Day;
  readonly gross: Money;
  readonly tax: Money;
}

export interface ClaimsReport {
  readonly rows: readonly ClaimRow[];
  readonly notExemptable: readonly NotExemptable[];
  /** Purchases that covered nothing: no open claim before them, or every deadline passed. */
  readonly idle: readonly Reinvestment[];
  /** The tax the missed deadlines owe. */
  readonly owed: Money;
  readonly notes: readonly Note[];
}

export type ClaimsRead =
  | { readonly report: ClaimsReport; readonly missing: readonly [] }
  | { readonly report: null; readonly missing: readonly Note[] };

const uncoveredOf = (claims: readonly DividendClaim[]): Money =>
  claims.reduce((sum, claim) => sum.plus(claim.uncovered), Money.zero(IDR));

/** The claims list on `today` from the dividends and purchases the user entered. */
export const claimsReport = (
  rules: ClaimRules,
  dividends: readonly DividendReceived[],
  purchases: readonly Reinvestment[],
  today: Day,
): ClaimsRead => {
  if (dividends.length === 0) {
    return { report: null, missing: [missingDividends()] };
  }
  for (const day of [...dividends.map((entry) => entry.received), ...purchases.map((p) => p.day)]) {
    if (day > today) {
      throw new RangeError(`an entry is dated ${day}, after today, ${today}`);
    }
  }
  let claims: DividendClaim[] = [];
  const notExemptable: NotExemptable[] = [];
  for (const dividend of dividends) {
    const claim = openClaim(rules, dividend);
    if (claim === null) {
      const tax = rules.dividendTax(dividend.gross, dividend.received);
      notExemptable.push({ ...dividend, tax });
    } else {
      claims.push(claim);
    }
  }
  claims.sort(byAge);
  const idle: Reinvestment[] = [];
  const byDay = [...purchases].sort((first, second) => first.day.localeCompare(second.day));
  for (const purchase of byDay) {
    const after = coverClaims(claims, [purchase], rules);
    if (uncoveredOf(after).equals(uncoveredOf(claims))) {
      idle.push(purchase);
    }
    claims = after;
  }
  const rows = claims.map((claim) => ({
    symbol: claim.symbol,
    received: claim.received,
    gross: claim.gross,
    reinvested: claim.gross.minus(claim.uncovered),
    toReinvest: claim.uncovered,
    deadline: claim.deadline,
    tax: rules.dividendTax(claim.uncovered, claim.received),
    missed: today > claim.deadline && claim.uncovered.amount > 0n,
  }));
  const settled = settleDeadlines(claims, today, rules);
  return {
    report: { rows, notExemptable, idle, owed: settled.tax, notes: settled.notes },
    missing: [],
  };
};
