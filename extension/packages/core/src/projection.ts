/** The income projection (spec §9.1, #254): each paying holding's dividend growth over four years
 * and how long the income goal takes in three scenarios, ported from Python's
 * `income.dividend_growth` and `income.project`.
 *
 * Growth is measured on the dividends a share, restated in today's shares (§6.6), not on the
 * income received, which also grows with every contribution and reinvested dividend that the
 * projection adds month by month. A paying holding whose dividends have not been read back five
 * years is missing, and there is no growth, so no projection, until none is. */

import type Decimal from "decimal.js";
import type { Day, Dividends, Split } from "./broker-view.ts";
import type { RunRate } from "./income.ts";
import { Money, Rounding } from "./money.ts";
import { monthsBefore } from "./months.ts";
import { missingPage, note, NOTE_CODES, type Note } from "./notes.ts";
import { Ratio, roundRatio } from "./ratio.ts";
import { splitRatio } from "./restated.ts";
import type { IdxMarketRules } from "./rules.ts";

export const PROJECTION_LABEL = "Projection, not a promise";

/** The years between the two year windows growth compares. */
export const GROWTH_YEARS = 4n;

/** How far back each paying holding's dividends must be read. */
export const HISTORY_YEARS = 5n;

/** A scenario stops after 50 years. */
export const PROJECTION_MONTHS = 600n;

const PESSIMISTIC_START = new Ratio("0.8");
const BASE_GROWTH_CAP = new Ratio("0.05");
const OPTIMISTIC_GROWTH_CAP = new Ratio("0.10");
const MONTHS = 12n;

export interface HoldingGrowth {
  readonly symbol: string;
  /** Dividends a share in the year to the run rate's day, in today's shares. */
  readonly recent: Decimal;
  /** The same for the year ending `GROWTH_YEARS` years earlier. */
  readonly earlier: Decimal;
  /** The yearly rate turning `earlier` into `recent`, or 0 when `earlier` is 0. */
  readonly growth: Decimal;
}

/** Each paying holding's growth, and the portfolio's: theirs weighted by run-rate gross. */
export interface IncomeGrowth {
  readonly holdings: readonly HoldingGrowth[];
  readonly portfolio: Decimal;
  readonly notes: readonly Note[];
}

export type IncomeGrowthRead =
  | { readonly growth: IncomeGrowth; readonly missing: readonly [] }
  | { readonly growth: null; readonly missing: readonly Note[] };

export type Scenario = "pessimistic" | "base" | "optimistic";

export type ProjectionOutcome = "reached" | "not-within" | "cannot";

export interface ScenarioProjection {
  readonly scenario: Scenario;
  readonly start: Money;
  readonly growth: Decimal;
  readonly outcome: ProjectionOutcome;
  /** Years until the goal is met, rounded up to a tenth; `null` unless it is reached. */
  readonly years: Decimal | null;
}

export interface Projection {
  readonly target: Money;
  readonly contribution: Money;
  readonly scenarios: readonly ScenarioProjection[];
  readonly notes: readonly Note[];
}

export interface ProjectionInputs {
  readonly rate: RunRate;
  readonly growth: IncomeGrowth;
  readonly holdingsValue: Money;
  /** The monthly take-home the goal asks for. */
  readonly target: Money;
  /** What the user adds each month; 0 when the Settings field is blank. */
  readonly contribution: Money;
  readonly rules: IdxMarketRules;
}

/** The same month and day `years` years before `day`; 29 February becomes 28 February. */
const yearsBefore = (day: Day, years: bigint): Day => monthsBefore(day, years * MONTHS);

/** The first day of the 365-day window ending on `end`, both ends included. */
const windowStart = (end: Day): Day => {
  const moved = new Date(`${end}T00:00:00Z`);
  moved.setUTCDate(moved.getUTCDate() - 364);
  return moved.toISOString().slice(0, 10);
};

/** The dividends a share with an ex-date in the year window ending on `end`, in `asOf`'s
 * shares, at 50 digits. */
const perShare = (read: Dividends, splits: readonly Split[], end: Day, asOf: Day): Decimal => {
  const since = windowStart(end);
  return read.dividends
    .filter((row) => since <= row.exDate && row.exDate <= end)
    .reduce((total, row) => {
      const [old, now] = splitRatio(row.symbol, row.exDate, splits, asOf);
      const restated = new Ratio(row.grossPerShare.toString())
        .times(old.toString())
        .div(now.toString());
      return total.plus(restated);
    }, new Ratio(0));
};

/** Each paying holding's dividend growth over `GROWTH_YEARS` years, or every holding whose
 * dividends do not reach back `HISTORY_YEARS` years. */
export const incomeGrowth = (
  rate: RunRate,
  dividends: ReadonlyMap<string, Dividends>,
  splits: readonly Split[],
): IncomeGrowthRead => {
  const earlierEnd = yearsBefore(rate.asOf, GROWTH_YEARS);
  const reach = yearsBefore(rate.asOf, HISTORY_YEARS);
  const paying = rate.holdings.filter((holding) => holding.annualGross.amount !== 0n);
  const missing: Note[] = [];
  const covered: { readonly symbol: string; readonly gross: bigint; readonly read: Dividends }[] =
    [];
  for (const holding of paying) {
    const read = dividends.get(holding.symbol);
    if (read === undefined || read.covered.from > reach) {
      missing.push(missingPage("dividends", holding.symbol));
    } else {
      covered.push({ symbol: holding.symbol, gross: holding.annualGross.amount, read });
    }
  }
  if (missing.length > 0) {
    return { growth: null, missing };
  }
  const notes: Note[] = [];
  const measured = covered.map(({ symbol, gross, read }) => {
    const recent = perShare(read, splits, rate.asOf, rate.asOf);
    const earlier = perShare(read, splits, earlierEnd, rate.asOf);
    if (earlier.isZero()) {
      notes.push(
        note(
          NOTE_CODES.INCOME_GROWTH_SHORT_HISTORY,
          `${symbol}: no dividend was found in the year ending ${earlierEnd}, so its dividend growth is taken as 0%`,
        ),
      );
      return { gross, holding: { symbol, recent, earlier, growth: new Ratio(0) } };
    }
    const yearly = recent.div(earlier).ln().div(GROWTH_YEARS.toString());
    const growth = roundRatio(yearly.exp().minus(1));
    return { gross, holding: { symbol, recent, earlier, growth } };
  });
  const holdings = measured.map(({ holding }): HoldingGrowth => holding);
  const weighted = measured.reduce(
    (total, { gross, holding }) => total.plus(holding.growth.times(gross.toString())),
    new Ratio(0),
  );
  const total = rate.annualGross.amount;
  const portfolio = total === 0n ? new Ratio(0) : roundRatio(weighted.div(total.toString()));
  return { growth: { holdings, portfolio, notes }, missing: [] };
};

/** `months` in years, rounded up to a tenth. */
const tenths = (months: bigint): Decimal =>
  new Ratio(((months * 10n + MONTHS - 1n) / MONTHS).toString()).div(10);

const perMonth = (amount: Money): Money => new Money(amount.amount / MONTHS, amount.currency);

/** `rate` as an exact fraction of whole numbers. */
const fraction = (rate: Decimal): readonly [bigint, bigint] => {
  const [whole = "", part = ""] = rate.toFixed().split(".");
  return [BigInt(`${whole}${part}`), 10n ** BigInt(part.length)];
};

const lesser = (first: Decimal, second: Decimal): Decimal => (first.lt(second) ? first : second);

/** Years until the target is met, or `null` after `PROJECTION_MONTHS`.
 *
 * Reinvesting at the holdings' own yield leaves the yield, income over value, unchanged, so the
 * yield is kept exactly, as a fraction only growth changes, and the income is rounded down only
 * where a month uses it, as Python does (#97). */
const yearsUntil = (inputs: ProjectionInputs, start: Money, growth: Decimal): Decimal | null => {
  const { target, contribution, rules } = inputs;
  const tax = (gross: Money): Money => rules.dividendTax(gross, inputs.rate.asOf);
  const met = (income: Money): boolean => perMonth(income.minus(tax(income))).ge(target);
  if (met(start)) {
    return tenths(0n);
  }
  let numerator = start.amount;
  let denominator = inputs.holdingsValue.amount;
  const [growBy, growOver] = fraction(new Ratio(1).plus(growth));
  let worth = inputs.holdingsValue.amount;
  let income = start;
  for (let month = 1n; month <= PROJECTION_MONTHS; month += 1n) {
    const monthly = perMonth(income);
    worth += monthly.minus(tax(monthly)).plus(contribution).amount;
    if (month % MONTHS === 0n) {
      numerator *= growBy;
      denominator *= growOver;
    }
    income = new Money((worth * numerator) / denominator, start.currency);
    if (met(income)) {
      return tenths(month);
    }
  }
  return null;
};

/** How long until the goal is met in each scenario. Each starts from the run rate's gross and
 * the holdings' value, idle cash not assumed invested; income rounds down, tax rounds up, and
 * trading costs are left out. */
export const project = (inputs: ProjectionInputs): Projection => {
  const { rate, growth, holdingsValue } = inputs;
  const measured = growth.portfolio;
  const plans: readonly (readonly [Scenario, Money, Decimal])[] = [
    [
      "pessimistic",
      rate.annualGross.timesRate(PESSIMISTIC_START, Rounding.DOWN),
      lesser(new Ratio(0), measured),
    ],
    ["base", rate.annualGross, lesser(measured, BASE_GROWTH_CAP)],
    ["optimistic", rate.annualGross, lesser(measured, OPTIMISTIC_GROWTH_CAP)],
  ];
  const cannot = rate.annualGross.amount === 0n || holdingsValue.amount === 0n;
  const scenarios = plans.map(([scenario, start, rateOfGrowth]): ScenarioProjection => {
    const years = cannot ? null : yearsUntil(inputs, start, rateOfGrowth);
    const outcome: ProjectionOutcome = cannot
      ? "cannot"
      : years === null
        ? "not-within"
        : "reached";
    return { scenario, start, growth: rateOfGrowth, outcome, years };
  });
  return {
    target: inputs.target,
    contribution: inputs.contribution,
    scenarios,
    notes: [
      note(
        NOTE_CODES.INCOME_PROJECTION_COSTS_IGNORED,
        "Reinvesting costs broker fees and levies, which this projection leaves out, so it reaches the target a little sooner than a real portfolio would",
      ),
    ],
  };
};
