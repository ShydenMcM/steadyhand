/** The panel's advice (spec §10.3, #238 AC3): the latest portfolio, watchlist and flags reads and
 * everything recorded, turned into the day's orders, goal progress, warnings and the missing
 * list, or what to read before there can be any. Pure: the panel reads the record and keeps the
 * memory it returns. */

import {
  adviceDayAt,
  advise,
  buyStops,
  closesFrom,
  freshness,
  goalProgress,
  lastUnknownAction,
  memoryFor,
  missingPage,
  portfolioView,
  riskState,
  runRate,
  storedAfter,
  tradableOn,
  universeOf,
  type Advice,
  type BrokerView,
  type Covered,
  type DailyClose,
  type Dated,
  type Day,
  type Dividends,
  type GoalProgress,
  type HeldView,
  type IdxCalendar,
  type IdxMarketRules,
  type Money,
  type Note,
  type Part,
  type Portfolio,
  type RiskLimits,
  type RiskRecord,
  type SessionRow,
  type Split,
  type StoredMemory,
  type Strategy,
  type Watchlist,
} from "@steadyhand/core";

/** The reads the panel keeps while it is open: advice needs them made together (spec §5.4). */
export type PanelReads = Pick<BrokerView, "portfolio" | "watchlist" | "flags">;

/** What the history record and Settings hold. */
export interface Recorded {
  /** Each stock's self-recorded closes, in day order. */
  readonly closes: ReadonlyMap<string, readonly DailyClose[]>;
  readonly dividends: ReadonlyMap<string, Dividends>;
  readonly splits: readonly Split[];
  /** The period each corporate action read covered. */
  readonly actionReads: readonly Covered[];
  readonly risk: RiskRecord;
  /** The strategy's memory as stored, or `undefined` before its first advice. */
  readonly stored: StoredMemory | undefined;
  /** The universe Settings lists, or `undefined` before one is entered. */
  readonly universe: readonly string[] | undefined;
  /** Each stock Settings excludes, with the user's reason. */
  readonly excluded: ReadonlyMap<string, string>;
  /** The monthly income goal, or `undefined` when none is set. */
  readonly goal: Money | undefined;
}

export interface ModelInputs {
  readonly reads: PanelReads;
  readonly recorded: Recorded;
  readonly strategy: Strategy;
  readonly rules: IdxMarketRules;
  readonly limits: RiskLimits;
  readonly calendar: IdxCalendar;
  readonly sessions: Dated<SessionRow>;
  /** The instant the panel advises at, for the next close when there is no advice. */
  readonly now: Date;
}

export type Goal =
  | { readonly state: "no goal set" }
  | { readonly state: "missing"; readonly missing: readonly Note[] }
  | { readonly state: "progress"; readonly progress: GoalProgress };

export type AdviceModel =
  | {
      readonly state: "read again";
      readonly reason: string;
      /** Each page to read again, named as the panel says it. */
      readonly missing: readonly Note[];
      /** When the next close becomes final. */
      readonly nextClose: Date;
    }
  /** No universe is listed: advising would sell every holding as outside it. */
  | { readonly state: "no universe" }
  | (Advice & {
      readonly state: "advice";
      /** The strategy's notes about the day. */
      readonly warnings: readonly Note[];
      readonly goal: Goal;
      /** The memory to keep for the day (spec §4.3). */
      readonly remember: StoredMemory;
    });

/** The income goal's progress on `day`, from the holdings' dividend reads (spec §9). */
const goalOf = (
  target: Money | undefined,
  inputs: ModelInputs,
  held: HeldView,
  unknownActions: ReadonlyMap<string, Day>,
  day: Day,
): Goal => {
  if (target === undefined) {
    return { state: "no goal set" };
  }
  const read = runRate({
    rules: inputs.rules,
    held: held.held,
    dividends: inputs.recorded.dividends,
    splits: inputs.recorded.splits,
    unknownActions,
    asOf: day,
  });
  return read.rate === null
    ? { state: "missing", missing: read.missing }
    : { state: "progress", progress: goalProgress(target, read.rate) };
};

export const adviceModel = (inputs: ModelInputs): AdviceModel => {
  const { reads, recorded, rules, calendar, sessions } = inputs;
  const fresh = freshness(reads, calendar, sessions);
  if (!fresh.fresh) {
    return {
      state: "read again",
      reason: fresh.reason,
      missing: fresh.readAgain.map((page) => missingPage(page)),
      nextClose: adviceDayAt(inputs.now, calendar, sessions).nextClose,
    };
  }
  if (recorded.universe === undefined) {
    return { state: "no universe" };
  }
  const day = fresh.adviceDay;
  // Fresh means both were read.
  const portfolio = (reads.portfolio as Part<Portfolio>).value;
  const watchlist = (reads.watchlist as Part<Watchlist>).value;
  // A flags read for another day still freezes what it flags, but buys need today's (#238).
  const flagsDay =
    reads.flags === undefined
      ? null
      : adviceDayAt(reads.flags.readAt, calendar, sessions).adviceDay;
  const flagStops = flagsDay === day ? [] : [missingPage("flags")];

  const universe = universeOf(recorded.universe, new Set(recorded.excluded.keys()), watchlist);
  const held = portfolioView(rules, portfolio, day);
  const tradable = tradableOn({
    day,
    members: universe.members,
    held: new Set(held.held.keys()),
    flags: reads.flags?.value.flags ?? [],
    excluded: recorded.excluded,
  });
  const closes = closesFrom(portfolio, watchlist);
  const unknownActions = new Map<string, Day>();
  for (const symbol of new Set([...universe.members, ...held.held.keys()])) {
    const found = lastUnknownAction(
      symbol,
      recorded.closes.get(symbol) ?? [],
      recorded.splits,
      recorded.actionReads,
      rules,
      calendar,
    );
    if (found !== undefined) {
      unknownActions.set(symbol, found);
    }
  }
  const memory = memoryFor(recorded.stored, day);
  const decision = inputs.strategy.decide(
    {
      day,
      tradable,
      closes,
      dividends: recorded.dividends,
      splits: recorded.splits,
      unknownActions,
      // Dividend-growth, the panel's strategy until Settings offers others (EXT S14b), judges no
      // price series.
      series: new Map(),
      calendar,
    },
    held,
    memory,
  );
  const advice = advise({
    rules,
    limits: inputs.limits,
    stops: [...buyStops(riskState(inputs.limits, calendar, recorded.risk)), ...flagStops],
    decision: {
      weights: decision.weights,
      reasons: decision.reasons,
      missing: [...universe.missing, ...decision.missing],
    },
    portfolio: held,
    tradable,
    prices: closes,
    day,
  });
  return {
    ...advice,
    state: "advice",
    warnings: decision.notes,
    goal: goalOf(recorded.goal, inputs, held, unknownActions, day),
    remember: storedAfter(day, memory, decision.memory),
  };
};
