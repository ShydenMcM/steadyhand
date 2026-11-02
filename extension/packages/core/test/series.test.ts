import { expect, test } from "vitest";
import type { DailyClose, Split } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { IDR, Money } from "../src/money.ts";
import { IdxMarketRules } from "../src/rules.ts";
import { stockSeries, type ChartRead, type SeriesInputs } from "../src/series.ts";

// A stock's series (spec §6.3, #232 AC1), in today's shares; actions found by price drop what
// came before (§6.4, AC2). The week of 16 June 2025 has no holiday.

const RULES = new IdxMarketRules();
const CALENDAR = IdxCalendar.shipped();
const at = (day: string, amount: bigint): DailyClose => ({ day, close: new Money(amount, IDR) });
const chart = (
  closes: DailyClose[],
  adjustment: ChartRead["adjustment"] = "splits",
): ChartRead => ({
  adjustment,
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
