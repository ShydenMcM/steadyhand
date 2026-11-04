/** The income goal (spec §9, decision 19, EXT S13): the holdings' run rate after the final
 * dividend tax, the goal against it, and the payment calendar, ported from Python's
 * `income.run_rate`, `goal_progress` and `payment_calendar`.
 *
 * A holding's run rate is its dividends with an ex-date in the 365 days up to the day, both ends
 * included, each restated in today's shares (§6.6) and multiplied by the shares held, rounded
 * down, a dividend that rounds to nothing left out. The calendar puts each dividend in the month
 * of the payment date its broker read gives, where Python models one. The goal compares the run
 * rate alone: income received is a later story. A holding whose dividends for the window have
 * not been read, or whose dividend figure crosses a corporate action found by price, is missing,
 * and there is no run rate until none is. */

import type Decimal from "decimal.js";
import type { Day, Dividends, Split } from "./broker-view.ts";
import { IDR, Money } from "./money.ts";
import { missingPage, type Note } from "./notes.ts";
import { Ratio, roundRatio } from "./ratio.ts";
import { restatedGross } from "./restated.ts";
import type { IdxMarketRules } from "./rules.ts";

/** One dividend a holding counts: its gross on the shares held now. */
export interface Entitlement {
  readonly exDate: Day;
  readonly paymentDate: Day;
  readonly gross: Money;
}

export interface HoldingRunRate {
  readonly symbol: string;
  readonly shares: bigint;
  readonly dividends: readonly Entitlement[];
  readonly annualGross: Money;
  readonly monthlyTakeHome: Money;
}

/** What the holdings would pay in a year at their trailing dividends. The portfolio's monthly
 * take-home is worked from its own annual gross, so it can be a rupiah or two more than the
 * holdings' monthly figures added up. */
export interface RunRate {
  readonly asOf: Day;
  readonly holdings: readonly HoldingRunRate[];
  readonly annualGross: Money;
  readonly monthlyTakeHome: Money;
}

export type RunRateRead =
  | { readonly rate: RunRate; readonly missing: readonly [] }
  | { readonly rate: null; readonly missing: readonly Note[] };

export interface IncomeInputs {
  readonly rules: IdxMarketRules;
  /** The shares of each holding. */
  readonly held: ReadonlyMap<string, bigint>;
  /** Each stock's dividend read, by symbol, with the period it covers. */
  readonly dividends: ReadonlyMap<string, Dividends>;
  readonly splits: readonly Split[];
  /** Each stock's last corporate action found by price with no known ratio (§6.4). */
  readonly unknownActions: ReadonlyMap<string, Day>;
  readonly asOf: Day;
}

/** The run rate's monthly take-home against the target, not capped at 1. */
export interface GoalProgress {
  readonly target: Money;
  readonly runRate: Money;
  readonly runRateShare: Decimal;
}

export interface HoldingCalendar {
  readonly symbol: string;
  /** Take-home by month of the year, January first. */
  readonly months: readonly Money[];
}

/** Expected take-home by month of the year, January first. `evenness` is the largest month's
 * share of the year: 1/12 when every month is equal, 1 when one month has it all, `null` with
 * nothing to share. */
export interface PaymentCalendar {
  readonly months: readonly Money[];
  readonly holdings: readonly HoldingCalendar[];
  readonly emptyMonths: bigint;
  readonly evenness: Decimal | null;
}

const MONTHS = 12n;

/** The first day of the 365-day window ending on `day`, both ends included. */
const windowStart = (day: Day): Day => {
  const moved = new Date(`${day}T00:00:00Z`);
  moved.setUTCDate(moved.getUTCDate() - 364);
  return moved.toISOString().slice(0, 10);
};

/** What the full dividend tax on `on` leaves of `gross`. */
const takeHome = (rules: IdxMarketRules, gross: Money, on: Day): Money =>
  gross.minus(rules.dividendTax(gross, on));

const perMonth = (amount: Money): Money => new Money(amount.amount / MONTHS, amount.currency);

const sum = (amounts: readonly Money[]): Money =>
  amounts.reduce((total, amount) => total.plus(amount), Money.zero(IDR));

interface Covered {
  readonly symbol: string;
  readonly shares: bigint;
  readonly read: Dividends;
}

/** The run rate of the holdings on `asOf`, or every gap that stops it. */
export const runRate = (inputs: IncomeInputs): RunRateRead => {
  const { rules, asOf } = inputs;
  const since = windowStart(asOf);
  const held = [...inputs.held].sort(([first], [second]) => first.localeCompare(second));
  const missing: Note[] = [];
  const covered: Covered[] = [];
  for (const [symbol, shares] of held) {
    const read = inputs.dividends.get(symbol);
    const action = inputs.unknownActions.get(symbol);
    const crossed = action !== undefined && action > since;
    if (read === undefined || read.covered.from > since || read.covered.to < asOf) {
      missing.push(missingPage("dividends", symbol));
    } else if (!crossed) {
      covered.push({ symbol, shares, read });
    }
    if (crossed) {
      missing.push(missingPage("corporate-actions", symbol));
    }
  }
  if (missing.length > 0) {
    return { rate: null, missing };
  }
  const holdings = covered.map(({ symbol, shares, read }): HoldingRunRate => {
    const dividends = read.dividends
      .filter((row) => since <= row.exDate && row.exDate <= asOf)
      .sort((first, second) => first.exDate.localeCompare(second.exDate))
      .map((row): Entitlement => ({
        exDate: row.exDate,
        paymentDate: row.paymentDate,
        gross: restatedGross(row, shares, inputs.splits, asOf),
      }))
      .filter((entitlement) => entitlement.gross.amount > 0n);
    const annualGross = sum(dividends.map((entitlement) => entitlement.gross));
    const monthlyTakeHome = perMonth(takeHome(rules, annualGross, asOf));
    return { symbol, shares, dividends, annualGross, monthlyTakeHome };
  });
  const annualGross = sum(holdings.map((holding) => holding.annualGross));
  const monthlyTakeHome = perMonth(takeHome(rules, annualGross, asOf));
  return { rate: { asOf, holdings, annualGross, monthlyTakeHome }, missing: [] };
};

/** `part` over `whole` at 50 digits, to eight places. */
const share = (part: Money, whole: Money): Decimal =>
  roundRatio(new Ratio(part.amount.toString()).div(whole.amount.toString()));

/** The goal tracker: the run rate's monthly take-home against `target` (spec §9). */
export const goalProgress = (target: Money, rate: RunRate): GoalProgress => {
  if (target.amount <= 0n) {
    throw new RangeError(`an income goal must be positive, got ${target.toString()}`);
  }
  const runRate = rate.monthlyTakeHome;
  return { target, runRate, runRateShare: share(runRate, target) };
};

/** The months of the year, January first, as the month a payment date names less one. */
const MONTH_KEYS: readonly bigint[] = [0n, 1n, 2n, 3n, 4n, 5n, 6n, 7n, 8n, 9n, 10n, 11n];

const monthOf = (day: Day): bigint => BigInt(day.slice(5, 7)) - 1n;

/** Each month's take-home from `entitlements`, each less the full tax on `on`. */
const byMonth = (rules: IdxMarketRules, entitlements: readonly Entitlement[], on: Day): Money[] =>
  MONTH_KEYS.map((month) =>
    sum(
      entitlements
        .filter((entitlement) => monthOf(entitlement.paymentDate) === month)
        .map((entitlement) => takeHome(rules, entitlement.gross, on)),
    ),
  );

/** Where in the year the run rate's dividends would arrive, as take-home, each less the full tax
 * on the run rate's day. */
export const paymentCalendar = (rate: RunRate, rules: IdxMarketRules): PaymentCalendar => {
  const holdings = rate.holdings.map((holding): HoldingCalendar => ({
    symbol: holding.symbol,
    months: byMonth(rules, holding.dividends, rate.asOf),
  }));
  const all = rate.holdings.flatMap((holding) => holding.dividends);
  const months = byMonth(rules, all, rate.asOf);
  const year = sum(months);
  const largest = months.reduce((most, month) => (month.gt(most) ? month : most), Money.zero(IDR));
  return {
    months,
    holdings,
    emptyMonths: BigInt(months.filter((month) => month.amount === 0n).length),
    evenness: year.amount === 0n ? null : share(largest, year),
  };
};
