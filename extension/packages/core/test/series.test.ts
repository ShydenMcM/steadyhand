import { expect, test } from "vitest";
import type { Covered, DailyClose, Day, Split } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { IDR, Money } from "../src/money.ts";
import { IdxMarketRules } from "../src/rules.ts";
import {
  chartReach,
  lastUnknownAction,
  stockSeries,
  type ChartRead,
  type SeriesInputs,
  type StockSeries,
} from "../src/series.ts";
import { RuleDecimal } from "../src/ratio.ts";

// A stock's series (spec §6.3, #232 AC1), in today's shares; actions found by price drop what
// came before (§6.4, AC2). The week of 16 June 2025 has no holiday.

const RULES = new IdxMarketRules();
const CALENDAR = IdxCalendar.shipped();
const at = (day: string, amount: bigint): DailyClose => ({ day, close: new Money(amount, IDR) });
/** The range every chart read below covers, unless a test says otherwise. */
const JUNE: Covered = { from: "2025-06-02", to: "2025-06-30" };
const chart = (
  closes: DailyClose[],
  adjustment: ChartRead["adjustment"] = "splits",
  covered: Covered = JUNE,
): ChartRead => ({
  adjustment,
  covered,
  closes,
});
const series = (inputs: Partial<SeriesInputs>) => {
  const found = stockSeries(
    { symbol: "BBCA", chart: undefined, recorded: [], splits: [], ...inputs },
    RULES,
    CALENDAR,
  );
  return {
    closes: found.closes.map((daily) => `${daily.day} ${daily.close.toString()}`),
    dividendsAdjustedTo: found.dividendsAdjustedTo,
    missing: found.missing,
  };
};
const AGAIN = [{ code: "missing.page", text: "open the price chart for BBCA" }];

test("with no chart, the series is the self-recorded closes", () => {
  expect(series({ recorded: [at("2025-06-16", 9_000n), at("2025-06-17", 9_100n)] })).toEqual({
    closes: ["2025-06-16 9000", "2025-06-17 9100"],
    dividendsAdjustedTo: null,
    missing: [],
  });
});

test("the chart wins on every day it holds, then the closes recorded after its last day", () => {
  const found = series({
    chart: chart([at("2025-06-16", 8_950n), at("2025-06-17", 9_000n)]),
    recorded: [at("2025-06-16", 9_999n), at("2025-06-17", 9_000n), at("2025-06-18", 9_050n)],
  });
  expect(found.closes).toEqual(["2025-06-16 8950", "2025-06-17 9000", "2025-06-18 9050"]);
  expect(found.missing).toEqual([]);
});

test("a chart whose last close disagrees with the recorded one drops the recorded part", () => {
  expect(
    series({
      chart: chart([at("2025-06-16", 8_950n), at("2025-06-17", 9_000n)]),
      recorded: [at("2025-06-17", 9_025n), at("2025-06-18", 9_050n)],
    }),
  ).toEqual({
    closes: ["2025-06-16 8950", "2025-06-17 9000"],
    dividendsAdjustedTo: null,
    missing: AGAIN,
  });
});

test("a chart with no recorded close on its last day is not compared", () => {
  expect(
    series({ chart: chart([at("2025-06-16", 8_950n)]), recorded: [at("2025-06-18", 9_050n)] })
      .closes,
  ).toEqual(["2025-06-16 8950", "2025-06-18 9050"]);
});

test("an action found by price drops everything before it and asks for the chart once", () => {
  expect(
    series({
      chart: chart([at("2025-06-16", 9_000n)]),
      recorded: [
        at("2025-06-16", 9_000n),
        at("2025-06-17", 9_000n),
        at("2025-06-18", 1_800n),
        at("2025-06-19", 1_810n),
      ],
    }),
  ).toEqual({
    closes: ["2025-06-18 1800", "2025-06-19 1810"],
    dividendsAdjustedTo: null,
    missing: AGAIN,
  });
});

test("with no chart, an action found by price drops the recorded closes before it", () => {
  expect(series({ recorded: [at("2025-06-16", 9_000n), at("2025-06-17", 1_800n)] })).toEqual({
    closes: ["2025-06-17 1800"],
    dividendsAdjustedTo: null,
    missing: AGAIN,
  });
});

const split: Split = { symbol: "BBCA", exDate: "2025-06-18", from: 1n, to: 3n };

test("recorded closes before a known split are restated in today's shares", () => {
  expect(
    series({ recorded: [at("2025-06-17", 9_000n), at("2025-06-18", 3_000n)], splits: [split] })
      .closes,
  ).toEqual(["2025-06-17 3000", "2025-06-18 3000"]);
});

test("a known split and a market move beyond the band on its day is still an action", () => {
  // 9,000 is 3,000 in the new shares; 2,500 is beyond its -15% band of 2,550.
  expect(
    series({ recorded: [at("2025-06-17", 9_000n), at("2025-06-18", 2_500n)], splits: [split] })
      .missing,
  ).toEqual(AGAIN);
});

test("a known split after both days of a pair restates neither for the band check", () => {
  // 16 to 17 June is flat in the old shares; restating 16 June alone would read 3,000 to 9,000.
  expect(
    series({
      recorded: [at("2025-06-16", 9_000n), at("2025-06-17", 9_000n), at("2025-06-18", 3_000n)],
      splits: [split],
    }),
  ).toEqual({
    closes: ["2025-06-16 3000", "2025-06-17 3000", "2025-06-18 3000"],
    dividendsAdjustedTo: null,
    missing: [],
  });
});

test("an unadjusted chart's closes before a known split are restated too", () => {
  expect(
    series({
      chart: chart([at("2025-06-17", 9_100n), at("2025-06-18", 3_000n)], "none"),
      splits: [split],
    }).closes,
  ).toEqual(["2025-06-17 3033.333333333333333333333333", "2025-06-18 3000"]);
});

test("a chart adjusted for splits is not restated again for a split it shows", () => {
  expect(
    series({ chart: chart([at("2025-06-17", 3_000n), at("2025-06-18", 3_000n)]), splits: [split] })
      .closes,
  ).toEqual(["2025-06-17 3000", "2025-06-18 3000"]);
});

test("a split after an adjusted chart's last day restates the chart's closes", () => {
  const later: Split = { ...split, exDate: "2025-06-19" };
  expect(
    series({
      chart: chart([at("2025-06-18", 9_000n)]),
      recorded: [at("2025-06-19", 3_000n)],
      splits: [later],
    }).closes,
  ).toEqual(["2025-06-18 3000", "2025-06-19 3000"]);
});

test("a chart adjusted for dividends says to which day", () => {
  expect(
    series({ chart: chart([at("2025-06-17", 9_000n)], "splits-and-dividends") })
      .dividendsAdjustedTo,
  ).toBe("2025-06-17");
});

test("an empty chart is no chart", () => {
  expect(series({ chart: chart([]), recorded: [at("2025-06-17", 9_000n)] }).closes).toEqual([
    "2025-06-17 9000",
  ]);
});

// #490 AC1: the series carries the range its chart read covers, for the windows strategies judge.
const covered = (inputs: Partial<SeriesInputs>) =>
  stockSeries(
    { symbol: "BBCA", chart: undefined, recorded: [], splits: [], ...inputs },
    RULES,
    CALENDAR,
  ).covered;

test("with no chart, the series covers no chart range", () => {
  expect(covered({ recorded: [at("2025-06-16", 9_000n)] })).toBeNull();
});

test("the series carries its chart read's range", () => {
  expect(covered({ chart: chart([at("2025-06-16", 9_000n)]) })).toEqual(JUNE);
});

test("a chart read with no close still carries its range", () => {
  expect(covered({ chart: chart([]) })).toEqual(JUNE);
});

test("a chart whose last close disagrees with the recorded one keeps its range", () => {
  expect(
    covered({
      chart: chart([at("2025-06-16", 9_000n)]),
      recorded: [at("2025-06-16", 9_100n)],
    }),
  ).toEqual(JUNE);
});

test("an action found by price after the chart drops the chart's range with the chart", () => {
  expect(
    covered({
      chart: chart([at("2025-06-16", 9_000n)]),
      recorded: [at("2025-06-16", 9_000n), at("2025-06-17", 9_000n), at("2025-06-18", 1_800n)],
    }),
  ).toBeNull();
});

// #230 AC2, #490 AC4, spec §7.1: a chart window is missing when no chart reaching its start was
// read, and ineligible when the chart reaches it but the stock had not started trading by then.
const reached = (from: Day | null, firstClose: Day | null): StockSeries => ({
  closes: firstClose === null ? [] : [{ day: firstClose, close: new RuleDecimal(9_000) }],
  covered: from === null ? null : { from, to: "2025-06-30" },
  dividendsAdjustedTo: null,
  missing: [],
});

test("missing: no series for the window", () => {
  expect(chartReach(undefined, "2025-01-02")).toBe("missing");
});

test("missing: a series of self-recorded closes alone, with no chart range", () => {
  expect(chartReach(reached(null, "2024-12-02"), "2025-01-02")).toBe("missing");
});

test("missing: a chart whose range starts after the window's start", () => {
  expect(chartReach(reached("2025-01-03", "2025-01-03"), "2025-01-02")).toBe("missing");
});

test("ineligible: a chart whose range starts before the window but whose first close is after it", () => {
  expect(chartReach(reached("2024-12-02", "2025-01-03"), "2025-01-02")).toBe("ineligible");
});

test("ineligible: a chart reaching the window's start with no close at all", () => {
  expect(chartReach(reached("2024-12-02", null), "2025-01-02")).toBe("ineligible");
});

test("a chart whose range and first close are on the window's start covers it", () => {
  expect(chartReach(reached("2025-01-02", "2025-01-02"), "2025-01-02")).toBe("covers");
});

// The last corporate action found by price with no known ratio (spec §6.4, §6.6, #480 AC2 and
// AC3), which the market view carries for the dividend figures.

const unknown = (
  recorded: readonly DailyClose[],
  splits: readonly Split[] = [],
  actionReads: readonly Covered[] = [],
) => lastUnknownAction("BBCA", recorded, splits, actionReads, RULES, CALENDAR);

test("no unknown action: closes the bands allow", () => {
  expect(unknown([at("2025-06-17", 9_000n), at("2025-06-18", 9_500n)])).toBeUndefined();
});

test("no unknown action: no closes at all", () => {
  expect(unknown([])).toBeUndefined();
});

test("an unknown action is dated by the first close after it", () => {
  expect(unknown([at("2025-06-17", 9_000n), at("2025-06-18", 3_000n)])).toBe("2025-06-18");
});

test("a known split on the action's day settles it", () => {
  expect(unknown([at("2025-06-17", 9_000n), at("2025-06-18", 3_000n)], [split])).toBeUndefined();
});

test("a known split and a move beyond the band on its day stays unknown", () => {
  expect(unknown([at("2025-06-17", 9_000n), at("2025-06-18", 2_500n)], [split])).toBe("2025-06-18");
});

test("with two unknown actions, the later one's day", () => {
  expect(
    unknown([at("2025-06-16", 9_000n), at("2025-06-17", 3_000n), at("2025-06-18", 1_000n)]),
  ).toBe("2025-06-18");
});

// A corporate action read whose period covers both closes settles the action whatever it shows
// (#480 AC5): the page lists every stock's splits, so no split there means no share change.

const jump = [at("2025-06-17", 9_000n), at("2025-06-18", 3_000n)];

test("a corporate action read covering both closes settles an action with no split", () => {
  expect(unknown(jump, [], [{ from: "2025-06-17", to: "2025-06-18" }])).toBeUndefined();
});

test("a corporate action read starting the day after the earlier close does not settle it", () => {
  expect(unknown(jump, [], [{ from: "2025-06-18", to: "2025-06-30" }])).toBe("2025-06-18");
});

test("a corporate action read ending the day before the later close does not settle it", () => {
  expect(unknown(jump, [], [{ from: "2025-06-01", to: "2025-06-17" }])).toBe("2025-06-18");
});

test("a corporate action read covering another stretch leaves the action unknown", () => {
  expect(unknown(jump, [], [{ from: "2025-07-01", to: "2025-07-31" }])).toBe("2025-06-18");
});

test("one of several corporate action reads covering both closes settles it", () => {
  const reads = [
    { from: "2025-07-01", to: "2025-07-31" },
    { from: "2025-01-01", to: "2025-06-30" },
  ];
  expect(unknown(jump, [], reads)).toBeUndefined();
});

test("a settled later action leaves an earlier unknown one standing", () => {
  const recorded = [at("2025-06-16", 9_000n), at("2025-06-17", 3_000n), at("2025-06-18", 1_000n)];
  expect(unknown(recorded, [], [{ from: "2025-06-17", to: "2025-06-18" }])).toBe("2025-06-17");
});
