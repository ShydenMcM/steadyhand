/** The panel's advice as text (spec §10.3, #238 AC3): what the advice model says, in the lines
 * the panel writes. Pure: the panel only puts each line on the page. */

import {
  instrument,
  percent,
  Side,
  type AdvisedOrder,
  type Cut,
  type IdxMarketRules,
  type Note,
  type Order,
  type Rejected,
  type Scenario,
  type ScenarioProjection,
} from "@steadyhand/core";
import type { AdviceModel, Goal, GoalProjection } from "./advice-model.ts";

/** Core §9.8's disclaimer, word for word as Python's `steadyhand.DISCLAIMER`. */
export const DISCLAIMER =
  "steadyhand is example software that you run yourself, on your own account, and you make " +
  "your own decisions with it. It is not financial advice. You can lose money.";

/** The line the panel shows beside the disclaimer (spec §10.3, §12.3). */
export const CHOICE_LINE =
  "steadyhand computes what the strategy you chose implies; the choice and the orders are yours";

/** A heading and the lines under it. */
export interface Section {
  readonly heading: string;
  readonly lines: readonly string[];
}

const SIDE_NAMES: Readonly<Record<Side, string>> = { [Side.BUY]: "Buy", [Side.SELL]: "Sell" };

/** WIB is seven hours ahead of UTC all year. */
const WIB_OFFSET_MS = 7 * 60 * 60 * 1000;

/** `text` with its full stop: a note written as a whole sentence already has one. */
const stopped = (text: string): string => (text.endsWith(".") ? text : `${text}.`);

/** `text` as a sentence: capitalised, with its full stop. */
export const sentence = (text: string): string =>
  stopped(`${text.charAt(0).toUpperCase()}${text.slice(1)}`);

/** `text` after a colon: as written, with its full stop. */
const clause = stopped;

const noteLines = (notes: readonly Note[]): readonly string[] =>
  notes.map((each) => sentence(each.text));

const lotsOf = (order: Order, quantity: bigint, rules: IdxMarketRules): bigint =>
  quantity / rules.lotSize(instrument(order.symbol, rules), order.day);

const orderLine = (advised: AdvisedOrder, rules: IdxMarketRules): string => {
  const { order } = advised;
  return (
    `${SIDE_NAMES[order.side]} ${lotsOf(order, order.quantity, rules).toString()} lots of ` +
    `${order.symbol} at a limit of ${advised.limitPrice.toString()}, estimated fees ` +
    `${advised.costs.total.toString()}: ${clause(advised.reason)}`
  );
};

const rejectedLine = (rejected: Rejected, rules: IdxMarketRules): string => {
  const { order } = rejected;
  const lots = lotsOf(order, order.quantity, rules).toString();
  return `${SIDE_NAMES[order.side]} ${lots} lots of ${order.symbol} not given: ${clause(rejected.reason.text)}`;
};

const cutLine = (cut: Cut, rules: IdxMarketRules): string => {
  const { order } = cut;
  const lots = lotsOf(order, cut.quantity, rules).toString();
  return `${SIDE_NAMES[order.side]} ${order.symbol} cut to ${lots} lots: ${clause(cut.reason.text)}`;
};

/** `instant` as WIB wall-clock time, to the minute. */
const wibTime = (instant: Date): string => {
  const shifted = new Date(instant.getTime() + WIB_OFFSET_MS);
  return `${shifted.toISOString().slice(0, 10)} ${shifted.toISOString().slice(11, 16)} WIB`;
};

/** The label every projection carries (spec §9.1): years, never a date. */
const PROJECTION = "Projection, not a promise";

const SCENARIO_NAMES: Readonly<Record<Scenario, string>> = {
  pessimistic: "Pessimistic",
  base: "Base",
  optimistic: "Optimistic",
};

const scenarioLine = (each: ScenarioProjection): string =>
  each.years === null
    ? `${SCENARIO_NAMES[each.scenario]}: not within 50 years.`
    : `${SCENARIO_NAMES[each.scenario]}: about ${each.years.toFixed(1)} years.`;

const projectionLines = (read: GoalProjection): readonly string[] => {
  if (read.state === "missing") {
    return [
      `${PROJECTION}: it needs five years of each holding's dividends.`,
      ...noteLines(read.missing),
    ];
  }
  const { projection } = read;
  // A zero run-rate or no holdings leaves every scenario with nothing to grow from.
  const scenarios = projection.scenarios.every((each) => each.outcome === "cannot")
    ? [`${PROJECTION}: nothing to project from a zero run-rate or no holdings.`]
    : [
        `${PROJECTION}, adding ${projection.contribution.toString()} a month:`,
        ...projection.scenarios.map(scenarioLine),
      ];
  return [...scenarios, ...noteLines(read.notes)];
};

const goalLines = (goal: Goal): readonly string[] => {
  switch (goal.state) {
    case "no goal set":
      return ["No income goal set."];
    case "missing":
      return noteLines(goal.missing);
    case "progress": {
      const { progress } = goal;
      return [
        `${progress.runRate.toString()} a month of the ${progress.target.toString()} goal ` +
          `(${percent(progress.runRateShare)}).`,
        ...projectionLines(goal.projection),
      ];
    }
  }
};

/** A section for each list that has lines; an empty list is left out. */
const listed = (heading: string, lines: readonly string[]): readonly Section[] =>
  lines.length === 0 ? [] : [{ heading, lines }];

export const adviceView = (model: AdviceModel, rules: IdxMarketRules): readonly Section[] => {
  switch (model.state) {
    case "read again":
      return [
        {
          heading: "Read again",
          lines: [
            `The pages below were ${model.reason}.`,
            ...noteLines(model.missing),
            `The next close is final at ${wibTime(model.nextClose)}.`,
          ],
        },
      ];
    case "no universe":
      return [
        { heading: "Universe", lines: ["List the universe's stocks in Settings to get advice."] },
      ];
    case "advice": {
      const orders = model.orders.map((each) => orderLine(each, rules));
      const duty =
        model.stampDuty.amount === 0n
          ? []
          : [`Stamp duty on the day's orders: ${model.stampDuty.toString()}.`];
      return [
        {
          heading: `Advice for ${model.day}`,
          lines: orders.length === 0 ? ["No orders for this day."] : [...orders, ...duty],
        },
        ...listed("Not given as the strategy asked", [
          ...model.rejected.map((each) => rejectedLine(each, rules)),
          ...model.cuts.map((each) => cutLine(each, rules)),
        ]),
        ...listed("Buys stopped", noteLines(model.stops)),
        ...listed("Missing", noteLines(model.missing)),
        ...listed("Warnings", noteLines(model.warnings)),
        { heading: "Income goal", lines: goalLines(model.goal) },
      ];
    }
  }
};
