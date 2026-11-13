/** The dividend reinvestment exemption's claims (spec §9.2, #255), ported from Python's
 * `steadyhand.exemption`.
 *
 * A dividend received while `fees.json` has an exemption row opens a claim: its tax is not owed
 * if it is reinvested by the deadline and the investment is held. The extension cannot see past
 * dividends or purchases, so the user enters both. Python counts the deadline from the ex-date
 * because its engine never knew the receipt date; here it counts from the date received
 * (PMK 18/2021). Every figure is an estimate that assumes the yearly realisation reports are filed
 * (docs/research/t-tax.md §7). Breaks against the cost basis still invested are `settleBreaks`
 * (#256). */

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

/** The order claims are covered in: oldest receipt first, then the stock. Days are all ten
 * characters, so the day then the stock sorts as the two in turn. */
const ageOf = (claim: DividendClaim): string => `${claim.received} ${claim.symbol}`;

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
  const oldestFirst = [...slots].sort((first, second) =>
    ageOf(first.claim).localeCompare(ageOf(second.claim)),
  );
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

/** The rules a break reads: the claims' three and the settlement date that ends the grace. */
export type BreakRules = ClaimRules & Pick<IdxMarketRules, "settlementDate">;

/** The claims after a portfolio read is judged, with the tax their breaks owe. */
export interface BreakDay {
  readonly claims: readonly DividendClaim[];
  /** The read a shortfall still inside its settlement grace was first seen on, or `null`. */
  readonly since: Day | null;
  readonly tax: Money;
  readonly notes: readonly Note[];
}

const claimBroken = (claim: DividendClaim, amount: Money, tax: Money): Note =>
  note(
    NOTE_CODES.EXEMPTION_CLAIM_BROKEN,
    `${claim.symbol}: ${amount.toString()} reinvested from the dividend received on ` +
      `${claim.received} was no longer invested when the settlement grace ended, so its tax of ` +
      `${tax.toString()} is owed, from ${claim.received}`,
  );

const withProtections = (claim: DividendClaim, protections: readonly Protection[]): DividendClaim =>
  new DividendClaim(
    claim.symbol,
    claim.received,
    claim.gross,
    claim.deadline,
    claim.uncovered,
    protections,
  );

/** One protection while a break takes from it. */
interface Piece {
  readonly slot: BreakSlot;
  readonly until: Day;
  left: Money;
}

/** One claim while a break takes from its protections. */
interface BreakSlot {
  readonly claim: DividendClaim;
  readonly pieces: Piece[];
  readonly queue: Piece[];
  removed: Money;
}

/** Python's `_Close.breaks`: remove protections, latest `until` first, until `shortfall` is
 * covered; ties go to the newest claim, then to its protection added last. The pieces are listed
 * a protection place at a time and reversed, so a stable sort on the date and the claim's age
 * leaves Python's order on the place, then the claim. */
const breakProtections = (
  claims: readonly DividendClaim[],
  shortfall: Money,
  rules: BreakRules,
): Omit<BreakDay, "since"> => {
  const slots = claims.map((claim) => {
    const slot: BreakSlot = { claim, pieces: [], queue: [], removed: Money.zero(IDR) };
    for (const protection of claim.protections) {
      slot.pieces.push({ slot, until: protection.until, left: protection.amount });
    }
    slot.queue.push(...slot.pieces);
    return slot;
  });
  const ordered: Piece[] = [];
  while (slots.some((slot) => slot.queue.length > 0)) {
    for (const slot of slots) {
      const next = slot.queue.shift();
      if (next !== undefined) {
        ordered.push(next);
      }
    }
  }
  const keyOf = (piece: Piece): string => `${piece.until} ${ageOf(piece.slot.claim)}`;
  ordered.reverse();
  ordered.sort((first, second) => keyOf(second).localeCompare(keyOf(first)));
  let left = shortfall;
  for (const piece of ordered) {
    if (left.amount === 0n) {
      break;
    }
    const taken = piece.left.lt(left) ? piece.left : left;
    piece.left = piece.left.minus(taken);
    piece.slot.removed = piece.slot.removed.plus(taken);
    left = left.minus(taken);
  }
  let tax = Money.zero(IDR);
  const notes: Note[] = [];
  const kept = slots.map((slot) => {
    if (slot.removed.amount > 0n) {
      const owed = rules.dividendTax(slot.removed, slot.claim.received);
      if (owed.amount > 0n) {
        tax = tax.plus(owed);
        notes.push(claimBroken(slot.claim, slot.removed, owed));
      }
    }
    const rest = slot.pieces.filter((piece) => piece.left.amount > 0n);
    return withProtections(
      slot.claim,
      rest.map((piece) => new Protection(piece.left, piece.until)),
    );
  });
  return { claims: kept, tax, notes };
};

/** The rest of Python's `settle_claims`, judged on a portfolio read after `day`'s close:
 * protections past their date fall away, then the protected amount is compared with the cost
 * basis still `invested`. A shortfall still there on a read on or after the settlement date of
 * the read it was first seen on breaks protections, at the rate of the day each claim was
 * received. Every claim stays, so the claims list keeps a row for each dividend. */
export const settleBreaks = (
  claims: readonly DividendClaim[],
  invested: Money,
  since: Day | null,
  day: Day,
  rules: BreakRules,
): BreakDay => {
  const current = claims.map((claim) =>
    withProtections(
      claim,
      claim.protections.filter((protection) => protection.until >= day),
    ),
  );
  const held = current.reduce(
    (sum, claim) =>
      claim.protections.reduce((total, protection) => total.plus(protection.amount), sum),
    Money.zero(IDR),
  );
  if (!held.gt(invested)) {
    return { claims: current, since: null, tax: Money.zero(IDR), notes: [] };
  }
  const first = since ?? day;
  if (day < rules.settlementDate(first)) {
    return { claims: current, since: first, tax: Money.zero(IDR), notes: [] };
  }
  return { ...breakProtections(current, held.minus(invested), rules), since: null };
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
  claims.sort((first, second) => ageOf(first).localeCompare(ageOf(second)));
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
