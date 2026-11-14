/** The risk halts as the panel judges them (spec §8, decision 18, EXT S12): the fund-style unit
 * value taken from after-close reads only, deposits and withdrawals from the broker's
 * cash-movement page or typed by the user, the daily loss and drawdown halts, and resume.
 *
 * The first after-close read opens the unit value: its value buys units at 1, as a run's first
 * day does in Python, and no halt is judged on it. Each later read is judged against the read
 * before it, once the cash-movement record covers every calendar day after that read up to its
 * own day. A deposit or withdrawal dated on a read's own day is in that read's value (Shyden,
 * 2026-11-04: a read after the close sees the day's whole cash balance), so it buys or sells
 * units at the price the read gives without it. The first span the record does not cover stops
 * the judging there: the panel lists `missing.deposits` and gives sell orders only.
 *
 * A same-day movement counts in its day's read only if it was recorded before that read (#499,
 * Shyden 2026-11-07): typed before the read, or listed by a cash-movement page read before it.
 * One recorded after the read may not be in it, so the judging stops before that read and the
 * panel lists `missing.reread` until a later read of the same day replaces it. */

import type { CashMovement, Covered, Day } from "./broker-view.ts";
import { dayAfter, type IdxCalendar } from "./calendar.ts";
import { Money } from "./money.ts";
import { missingDeposits, missingReread, type Note } from "./notes.ts";
import { Ratio } from "./ratio.ts";
import { haltOn, percent, UnitValue, type Halt, type RiskLimits } from "./risk.ts";

/** The portfolio's value on a read after `day`'s close: all cash plus every holding. */
export interface Valuation {
  readonly day: Day;
  readonly readAt: Date;
  readonly value: Money;
  /** The cost basis still invested on the read (#256); reads stored before it have none. */
  readonly invested?: Money;
}

/** The period a cash-movement page read covered, and when it was read; reads stored before
 * #499 have no `readAt`. */
export interface MovementRead extends Covered {
  readonly readAt?: Date;
}

/** A deposit or withdrawal the user typed, kept and shown as typed. */
export interface TypedMovement extends CashMovement {
  readonly typedAt: Date;
}

/** The user resumed the halt of `haltDay` at `at`, by typing `strategy`'s name. */
export interface Resumed {
  readonly haltDay: Day;
  readonly at: Date;
  readonly strategy: string;
}

/** Everything the halts are judged from, as the history store keeps it. */
export interface RiskRecord {
  readonly valuations: readonly Valuation[];
  /** The rows of every cash-movement page read. */
  readonly movements: readonly CashMovement[];
  /** The period each cash-movement page read covered, and when it was read. */
  readonly movementReads: readonly MovementRead[];
  readonly typed: readonly TypedMovement[];
  /** Each period the user said is complete: every entry in it typed, or none. */
  readonly answered: readonly Covered[];
  readonly resumes: readonly Resumed[];
}

export interface RiskState {
  /** The unit value at the last read judged; an empty fund before any read. */
  readonly unitValue: UnitValue;
  /** The last read judged, or `null` before any read. */
  readonly judgedTo: Day | null;
  /** The halt in force, or `null`. */
  readonly halt: Halt | null;
  /** `missing.deposits` while the cash-movement record leaves a span unjudged. */
  readonly missing: readonly Note[];
  /** The span the panel asks about: from the day after the last read judged to the latest
   * read, or `null` when every read is judged. */
  readonly unrecorded: Covered | null;
  /** Typed entries on days a cash-movement read covers: the read's rows count instead. */
  readonly superseded: readonly TypedMovement[];
}

export type ResumeAnswer = { readonly resumed: Resumed } | { readonly refused: string };

const inside = (spans: readonly Covered[], day: Day): boolean =>
  spans.some((span) => span.from <= day && day <= span.to);

/** Whether `spans` together cover every calendar day from `from` to `to`. */
const covers = (spans: readonly Covered[], from: Day, to: Day): boolean => {
  let reach = from;
  while (reach <= to) {
    const step = spans.find((span) => span.from <= reach && reach <= span.to);
    if (step === undefined) {
      return false;
    }
    reach = dayAfter(step.to);
  }
  return true;
};

/** Deposits less withdrawals dated from `from` to `to`: every row a page read listed, and each
 * typed entry on a day no page read covers. */
const netFlow = (record: RiskRecord, from: Day, to: Day, start: Money): Money => {
  const counted = [
    ...record.movements,
    ...record.typed.filter((entry) => !inside(record.movementReads, entry.day)),
  ];
  let net = start;
  for (const movement of counted) {
    if (from <= movement.day && movement.day <= to) {
      net = movement.kind === "deposit" ? net.plus(movement.amount) : net.minus(movement.amount);
    }
  }
  return net;
};

/** Whether a deposit or withdrawal dated `valuation`'s day was recorded after that read: a
 * counted typed entry typed later, or a row of that day with a page read covering it read later. */
const recordedAfter = (record: RiskRecord, valuation: Valuation): boolean => {
  const day = valuation.day;
  const typedLate = record.typed.some(
    (entry) =>
      entry.day === day && entry.typedAt > valuation.readAt && !inside(record.movementReads, day),
  );
  const pageLate =
    record.movements.some((movement) => movement.day === day) &&
    record.movementReads.some(
      (read) =>
        read.from <= day &&
        day <= read.to &&
        read.readAt !== undefined &&
        read.readAt > valuation.readAt,
    );
  return typedLate || pageLate;
};

interface Raised {
  readonly halt: Halt;
  readonly readAt: Date;
}

/** Whether a resume of `raised` was made after its read and before `before`; with `before`
 * `null`, at any time since. */
const resumedBefore = (record: RiskRecord, raised: Raised, before: Date | null): boolean =>
  record.resumes.some(
    (entry) =>
      entry.haltDay === raised.halt.day &&
      entry.at > raised.readAt &&
      (before === null || entry.at < before),
  );

const inOrder = (valuations: readonly Valuation[], calendar: IdxCalendar): Valuation[] => {
  const sorted = [...valuations].sort((first, second) => first.day.localeCompare(second.day));
  let last: Day | null = null;
  for (const valuation of sorted) {
    if (!calendar.isTradingDay(valuation.day)) {
      throw new RangeError(
        `${valuation.day} is not a trading day: an after-close read shows a trading day's close`,
      );
    }
    if (valuation.day === last) {
      throw new RangeError(`two after-close reads for ${valuation.day}`);
    }
    last = valuation.day;
  }
  return sorted;
};

/** The unit value, the halt in force and what is missing, from everything recorded. */
export const riskState = (
  limits: RiskLimits,
  calendar: IdxCalendar,
  record: RiskRecord,
): RiskState => {
  const superseded = record.typed.filter((entry) => inside(record.movementReads, entry.day));
  const sorted = inOrder(record.valuations, calendar);
  const [first, ...later] = sorted;
  if (first === undefined) {
    return {
      unitValue: new UnitValue(),
      judgedTo: null,
      halt: null,
      missing: [],
      unrecorded: null,
      superseded,
    };
  }
  const recorded = [...record.movementReads, ...record.answered];
  let fund = new UnitValue().deposit(first.value);
  let previous = first;
  let latest = first.day;
  for (const valuation of later) {
    latest = valuation.day;
  }
  let raised: Raised | null = null;
  const halted = (before: Date | null): Halt | null =>
    raised === null || resumedBefore(record, raised, before) ? null : raised.halt;
  for (const valuation of later) {
    const from = dayAfter(previous.day);
    if (!covers(recorded, from, valuation.day)) {
      return {
        unitValue: fund,
        judgedTo: previous.day,
        halt: halted(null),
        missing: [missingDeposits(previous.day)],
        unrecorded: { from, to: latest },
        superseded,
      };
    }
    if (recordedAfter(record, valuation)) {
      return {
        unitValue: fund,
        judgedTo: previous.day,
        halt: halted(null),
        missing: [missingReread(valuation.day)],
        unrecorded: null,
        superseded,
      };
    }
    const net = netFlow(record, from, valuation.day, Money.zero(valuation.value.currency));
    const market = valuation.value.minus(net);
    if (market.amount < 0n) {
      throw new RangeError(
        `the value read on ${valuation.day}, ${valuation.value.toString()}, is less than the ` +
          `deposits less withdrawals recorded after ${previous.day}, ${net.toString()}: is a ` +
          "deposit dated wrongly?",
      );
    }
    const revalued = fund.revalue(market);
    if (halted(valuation.readAt) === null) {
      const since =
        calendar.previousTradingDay(valuation.day) === previous.day ? undefined : previous.day;
      const halt = haltOn(limits, fund, revalued, valuation.day, since);
      raised = halt === null ? null : { halt, readAt: valuation.readAt };
    }
    fund =
      valuation.value.amount === 0n
        ? new UnitValue(new Ratio(0), revalued.price, revalued.highWater)
        : revalued.deposit(net);
    previous = valuation;
  }
  const done = { unitValue: fund, judgedTo: previous.day, halt: halted(null), missing: [] };
  return { ...done, unrecorded: null, superseded };
};

/** What stops buy advice: the halt in force, and every fact a halt needs that is missing. Sell
 * orders are still given. */
export const buyStops = (state: RiskState): readonly Note[] =>
  state.halt === null ? state.missing : [state.halt.cause, ...state.missing];

/** Resume the halt in force once the user types `strategy`'s name, as Python's `resume` does:
 * refused while a fact the halt needs is missing, or while the drawdown is still at or past its
 * limit, where ordering would only halt again. */
export const resume = (
  limits: RiskLimits,
  state: RiskState,
  strategy: string,
  typed: string,
  at: Date,
): ResumeAnswer => {
  if (state.halt === null) {
    return { refused: "nothing is halted; there is nothing to resume" };
  }
  if (typed !== strategy) {
    return { refused: `you typed '${typed}', not '${strategy}'; nothing was changed` };
  }
  const [gap] = state.missing;
  if (gap !== undefined) {
    return { refused: `the halt stays while a fact it needs is missing: ${gap.text}` };
  }
  const drawdown = state.unitValue.drawdown;
  if (drawdown.gte(limits.maxDrawdown)) {
    return {
      refused:
        `the unit value is still ${percent(drawdown)} below its high-water mark, at or past ` +
        `the ${percent(limits.maxDrawdown)} drawdown limit; the halt stays until it recovers`,
    };
  }
  return { resumed: { haltDay: state.halt.day, at, strategy } };
};
