import { expect, test } from "vitest";
import type { Covered, Day, Dividend, Dividends } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { dailyVariance, LOW_VOLATILITY, lowVolatility } from "../src/low-volatility.ts";
import { IDR, Money } from "../src/money.ts";
import { missingHistory, missingPage, note, NOTE_CODES } from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import type { SeriesClose, StockSeries } from "../src/series.ts";
import type { PortfolioView } from "../src/sizing.ts";
import type { MarketView, Memory } from "../src/strategy.ts";

/** The shipped IDX trading days, read once. */
const CALENDAR = IdxCalendar.shipped();

// Hand-computed examples, one test per case, written from spec §7.3 before the code (#247 AC3).
//
// Most tests use `volatility_months` 2, and the advice day is Friday 31 May 2024. The look-back
// starts at the close on the last trading day on or before Sunday 31 March (Good Friday, 29 March,
// is a holiday, so Thursday 28 March). Every close is 100 unless a test sets it, so a stock with
// one close set to X has moves X/100 - 1 and 100/X - 1 and every other move 0: a higher X swings
// more.

const STOCKS = ["ASII", "BBCA", "BBRI", "TLKM", "UNVR"] as const;
/** Holds the 2 calmest. */
const SMALL = lowVolatility(2n, 2n);
/** Holds the single calmest. */
const ONE = lowVolatility(1n, 2n);
const DAY: Day = "2024-05-31";
const HOLIDAYS = new Set(["2024-03-29"]);

/** Each year's month lengths; 1 January 2023 is a Sunday. */
const YEARS = [
  ["2023", [31n, 28n, 31n, 30n, 31n, 30n, 31n, 31n, 30n, 31n, 30n, 31n]],
  ["2024", [31n, 29n, 31n, 30n, 31n, 30n, 31n, 31n, 30n, 31n, 30n, 31n]],
] as const;

/** The trading days of 2023 and 2024 up to `until`. */
const tradingDays = (until: Day): Day[] => {
  const days: Day[] = [];
  // Monday is 0, so Sunday 1 January 2023 is 6.
  let weekday = 6n;
  for (const [year, months] of YEARS) {
    let month = 1n;
    for (const monthDays of months) {
      for (let date = 1n; date <= monthDays; date += 1n) {
        const day = `${year}-${month.toString().padStart(2, "0")}-${date.toString().padStart(2, "0")}`;
        if (day <= until && weekday < 5n && !HOLIDAYS.has(day)) {
          days.push(day);
        }
        weekday = (weekday + 1n) % 7n;
      }
      month += 1n;
    }
  }
  return days;
};

/** A series closing at 100 on each of `days` except where `set` says, unadjusted for dividends,
 * from a chart whose range starts on `from`, by default its first close. */
const seriesOn = (
  days: readonly Day[],
  set: Readonly<Record<string, string>> = {},
  from: Day | undefined = days[0],
): StockSeries => {
  const closes: SeriesClose[] = days.map((day) => ({
    day,
    close: new RuleDecimal(set[day] ?? "100"),
  }));
  const covered = from === undefined ? null : { from, to: DAY };
  return { closes, covered, dividendsAdjustedTo: null, missing: [] };
};

/** A series on every trading day of 2023 and 2024 up to `until`. */
const seriesTo = (until: Day, set: Readonly<Record<string, string>> = {}): StockSeries =>
  seriesOn(tradingDays(until), set);

const rp = (amount: bigint): Money => new Money(amount, IDR);

interface ViewOptions {
  /** The universe, beyond the buyable stocks. */
  readonly members?: readonly string[];
  /** Each stock's series; a stock unlisted has none. */
  readonly series?: Readonly<Record<string, StockSeries>>;
  readonly dividends?: readonly Dividend[];
  /** Each stock's dividend read period. Unlisted stocks were read from 2015 to the advice day. */
  readonly covered?: Readonly<Record<string, Covered>>;
}

const view = (day: Day, buyable: readonly string[], options: ViewOptions = {}): MarketView => {
  const reads = new Map<string, Dividends>();
  for (const symbol of STOCKS) {
    const covered = options.covered?.[symbol] ?? { from: "2015-01-01", to: day };
    const own = (options.dividends ?? []).filter((paidOut) => paidOut.symbol === symbol);
    reads.set(symbol, { symbol, covered, dividends: own });
  }
  return {
    day,
    tradable: {
      day,
      buyable: new Set(buyable),
      sellable: new Set(),
      reasons: new Map(),
      members: new Set([...buyable, ...(options.members ?? [])]),
    },
    closes: new Map(STOCKS.map((symbol) => [symbol, rp(1000n)] as const)),
    dividends: reads,
    splits: [],
    unknownActions: new Map(),
    series: new Map(Object.entries(options.series ?? {})),
    calendar: CALENDAR,
  };
};

const portfolioOf = (
  spendable: bigint,
  held: Readonly<Record<string, bigint>> = {},
): PortfolioView => {
  const holdings = new Map(Object.entries(held).map(([symbol, worth]) => [symbol, rp(worth)]));
  const invested = [...holdings.values()].reduce((sum, worth) => sum + worth.amount, 0n);
  return { value: rp(spendable + invested), spendable: rp(spendable), holdings };
};

/** The weights as text, by symbol, for an exact comparison. */
const weighed = (weights: ReadonlyMap<string, { toString: () => string }>) =>
  Object.fromEntries([...weights].map(([symbol, weight]) => [symbol, weight.toString()]));

const NONE: Memory = new Map();
const CASH = portfolioOf(1_000_000n);

/** Each stock buyable, with its series to the advice day as `set` gives it. */
const allOf = (
  day: Day,
  sets: Readonly<Record<string, Readonly<Record<string, string>>>>,
): MarketView => {
  const series: Record<string, StockSeries> = {};
  for (const [symbol, set] of Object.entries(sets)) {
    series[symbol] = seriesTo(day, set);
  }
  return view(day, Object.keys(sets), { series });
};

/** The stocks `ONE` picks among `sets` on the advice day, with all cash. */
const pickedBy = (
  sets: Readonly<Record<string, Readonly<Record<string, string>>>>,
): Record<string, string> => weighed(ONE.decide(allOf(DAY, sets), CASH, NONE).weights);

const among = (count: bigint): string =>
  `low-volatility: among the ${count.toString()} calmest by daily moves`;
const notAmong = (count: bigint): string =>
  `low-volatility: not among the ${count.toString()} calmest by daily moves`;

const closesOf = (...closes: readonly string[]) => closes.map((close) => new RuleDecimal(close));

// The variance of a stock's daily moves (spec §7.3's examples).

test("closes 100, 110, 99, 99 move +0.10, -0.10 and 0, a variance of 0.02/3", () => {
  expect(dailyVariance(closesOf("100", "110", "99", "99")).toString()).toBe(
    "0.006666666666666666666666666667",
  );
});

test("closes 100, 120, 108 move +0.20 and -0.10 around a mean of 0.05, a variance of 0.0225", () => {
  expect(dailyVariance(closesOf("100", "120", "108")).toString()).toBe("0.0225");
});

test("a steady riser has no variance: closes 100, 101, 102.01 both move +0.01", () => {
  expect(dailyVariance(closesOf("100", "101", "102.01")).toString()).toBe("0");
});

test("a single move has no variance", () => {
  expect(dailyVariance(closesOf("100", "150")).toString()).toBe("0");
});

// Its settings (AC1).

test("it is a strategy named low-volatility with its settings, by default 10 and 12", () => {
  const strategy = lowVolatility();
  expect(strategy.name).toBe("low-volatility");
  expect([strategy.volatilityStocks, strategy.volatilityMonths]).toEqual([10n, 12n]);
  expect(LOW_VOLATILITY).toEqual({ volatilityStocks: 10n, volatilityMonths: 12n });
});

test("volatility_stocks below 1 is refused", () => {
  expect(() => lowVolatility(0n, 12n)).toThrow(
    new RangeError("volatility_stocks must be at least 1, got 0"),
  );
});

test("volatility_months below 1 is refused", () => {
  expect(() => lowVolatility(10n, 0n)).toThrow(
    new RangeError("volatility_months must be at least 1, got 0"),
  );
});

// A review.

test("a review holds the calmest at 1/volatility_stocks each and says why of every stock", () => {
  const decision = SMALL.decide(
    allOf(DAY, {
      ASII: { "2024-04-30": "130" },
      BBCA: { "2024-04-30": "120" },
      BBRI: { "2024-04-30": "110" },
      TLKM: {},
    }),
    CASH,
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ BBRI: "0.5", TLKM: "0.5" });
  expect(Object.fromEntries(decision.reasons)).toEqual({
    ASII: notAmong(2n),
    BBCA: notAmong(2n),
    BBRI: among(2n),
    TLKM: among(2n),
  });
  expect([decision.missing, decision.notes]).toEqual([[], []]);
  expect(Object.fromEntries(decision.memory)).toEqual({
    set: "IDX:BBRI IDX:TLKM",
    month: "2024-05",
  });
});

test("equal swings are ranked by symbol", () => {
  expect(pickedBy({ TLKM: {}, BBCA: {}, ASII: {} })).toEqual({ ASII: "1" });
});

test("a fall swings as a rise does: a stock falling to 50 is not calmer than one rising to 110", () => {
  expect(pickedBy({ ASII: { "2024-04-30": "50" }, BBCA: { "2024-04-30": "110" } })).toEqual({
    BBCA: "1",
  });
});

test("a steady riser is calmer than a flat stock with one swing", () => {
  // ASII rises 1% a day from its first close on 2 January 2023; its moves never vary.
  const days = tradingDays(DAY);
  let close = new RuleDecimal("100");
  const set: Record<string, string> = {};
  for (const day of days) {
    set[day] = close.toString();
    close = close.times("1.01");
  }
  expect(pickedBy({ ASII: set, BBCA: { "2024-04-30": "101" } })).toEqual({ ASII: "1" });
});

test("a swing before the look-back's first close does not count", () => {
  // 27 March's spike moves into 28 March, the first close: both moves are before the look-back.
  expect(pickedBy({ ASII: { "2024-03-27": "200" }, BBCA: { "2024-04-30": "101" } })).toEqual({
    ASII: "1",
  });
});

test("a swing from the look-back's first close counts", () => {
  // 28 March at 200 moves to 100 on 1 April, inside the look-back.
  expect(pickedBy({ ASII: { "2024-03-28": "200" }, BBCA: { "2024-04-30": "101" } })).toEqual({
    BBCA: "1",
  });
});

test("a swing on the advice day counts", () => {
  expect(pickedBy({ ASII: { "2024-05-31": "200" }, BBCA: { "2024-04-30": "101" } })).toEqual({
    BBCA: "1",
  });
});

test("a close after the advice day does not count", () => {
  // A review on 15 May of a series read later: ASII's spike on 20 May has not happened yet.
  const series = {
    ASII: seriesTo(DAY, { "2024-05-20": "200" }),
    BBCA: seriesTo(DAY, { "2024-05-02": "101" }),
  };
  const covered = { ASII: { from: "2015-01-01", to: DAY }, BBCA: { from: "2015-01-01", to: DAY } };
  const decision = ONE.decide(
    view("2024-05-15", ["ASII", "BBCA"], { series, covered }),
    CASH,
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "1" });
});

test("swings are of total-return closes: a dividend's fall on its ex-date is no swing", () => {
  // ASII closes 100 until its ex-date on 15 April, then 80, paying 20, so its total return is flat.
  // BBCA's 101 for a day is a real swing.
  const dividend: Dividend = {
    symbol: "ASII",
    exDate: "2024-04-15",
    paymentDate: "2024-05-15",
    grossPerShare: new RuleDecimal("20"),
  };
  const fallen: Record<string, string> = {};
  for (const day of tradingDays(DAY).filter((one) => one >= "2024-04-15")) {
    fallen[day] = "80";
  }
  const series = { ASII: seriesTo(DAY, fallen), BBCA: seriesTo(DAY, { "2024-04-30": "101" }) };
  const decision = ONE.decide(
    view(DAY, ["ASII", "BBCA"], { series, dividends: [dividend] }),
    CASH,
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "1" });
});

test("a held stock not among the calmest is sold, and one that left the universe too", () => {
  const decision = SMALL.decide(
    allOf(DAY, { ASII: {}, BBCA: {}, TLKM: { "2024-04-30": "130" } }),
    portfolioOf(500_000n, { TLKM: 300_000n, UNVR: 200_000n }),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBCA: "0.5" });
  expect(Object.fromEntries(decision.reasons)).toEqual({
    ASII: among(2n),
    BBCA: among(2n),
    TLKM: notAmong(2n),
    UNVR: "low-volatility: no longer in the universe",
  });
});

test("a held stock it cannot buy is still judged and kept when it is among the calmest", () => {
  const series = { ASII: seriesTo(DAY, { "2024-04-30": "130" }), BBCA: seriesTo(DAY) };
  const decision = ONE.decide(
    view(DAY, ["ASII"], { series, members: ["BBCA"] }),
    portfolioOf(500_000n, { BBCA: 500_000n }),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});

test("with fewer stocks to judge than volatility_stocks, the rest stays cash, with a note", () => {
  const decision = SMALL.decide(allOf(DAY, { BBCA: {} }), CASH, NONE);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5" });
  expect(decision.notes).toEqual([
    note(
      NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
      "Only 1 stock could be judged by its daily moves; the rest is held as cash until more can.",
    ),
  ]);
});

test("the note counts two stocks as stocks", () => {
  const decision = lowVolatility(3n, 2n).decide(allOf(DAY, { ASII: {}, BBCA: {} }), CASH, NONE);
  expect(decision.notes).toEqual([
    note(
      NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
      "Only 2 stocks could be judged by their daily moves; the rest is held as cash until more can.",
    ),
  ]);
});

test("with no stock to judge, everything is cash, with a note", () => {
  const decision = SMALL.decide(view(DAY, []), CASH, NONE);
  expect([weighed(decision.weights), decision.notes]).toEqual([
    {},
    [
      note(
        NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
        "No stock could be judged by its daily moves; everything is held as cash until one can.",
      ),
    ],
  ]);
});

// What it needs, and missing versus ineligible (spec §7.1, §7.3).

const LAST_MONTH: Memory = new Map([
  ["set", "IDX:TLKM"],
  ["month", "2024-04"],
]);

/** What `SMALL` decides with BBCA's series as given, ASII's in full, and last month's memory. */
const withBbca = (series: StockSeries, options: ViewOptions = {}) =>
  SMALL.decide(
    view(DAY, ["ASII", "BBCA"], { ...options, series: { ASII: seriesTo(DAY), BBCA: series } }),
    CASH,
    LAST_MONTH,
  );

test("a listing inside the look-back is ineligible, and the others are still judged", () => {
  // BBCA's chart reaches back to 1 March, but its first close is 1 April, after 31 March.
  const listing = seriesOn(
    tradingDays(DAY).filter((day) => day >= "2024-04-01"),
    {},
    "2024-03-01",
  );
  const decision = withBbca(listing);
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5" });
  expect(decision.reasons.get("BBCA")).toBe(
    "low-volatility: not judged, it had not started trading by 2024-03-31",
  );
  expect(decision.missing).toEqual([]);
});

test("30 closes in the look-back, 15 a month for 2 months, is enough to be judged", () => {
  // 28 March, then the 29 trading days from 23 April to 31 May.
  const days = tradingDays(DAY).filter((day) => day <= "2024-03-28" || day >= "2024-04-23");
  const decision = withBbca(seriesOn(days));
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBCA: "0.5" });
  expect(decision.reasons.get("BBCA")).toBe(among(2n));
});

test("29 closes in the look-back is ineligible: a stock that hardly traded would look calm", () => {
  // 28 March, then the 28 trading days from 24 April to 31 May.
  const days = tradingDays(DAY).filter((day) => day <= "2024-03-28" || day >= "2024-04-24");
  const decision = withBbca(seriesOn(days));
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5" });
  expect(decision.reasons.get("BBCA")).toBe(
    "low-volatility: not judged, it traded on too few days since 2024-03-31",
  );
  expect(decision.missing).toEqual([]);
});

test("closes before the look-back do not make up for too few inside it", () => {
  const days = tradingDays(DAY).filter((day) => day <= "2024-03-28" || day >= "2024-05-30");
  expect(withBbca(seriesOn(days)).reasons.get("BBCA")).toBe(
    "low-volatility: not judged, it traded on too few days since 2024-03-31",
  );
});

test("a stock with no series is missing: no orders, and the memory is kept", () => {
  const decision = SMALL.decide(view(DAY, ["BBCA"]), CASH, LAST_MONTH);
  expect(decision).toEqual({
    weights: new Map(),
    reasons: new Map(),
    missing: [missingPage("stock-detail", "BBCA")],
    memory: LAST_MONTH,
    notes: [],
  });
});

test("a stock with an empty series is missing", () => {
  expect(withBbca(seriesOn([], {}, "2024-03-01")).missing).toEqual([
    missingPage("stock-detail", "BBCA"),
  ]);
});

test("a stock whose dividends for the look-back are unread is missing", () => {
  const decision = withBbca(seriesTo(DAY), { covered: { BBCA: { from: "2024-01-01", to: DAY } } });
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
  expect(decision.memory).toBe(LAST_MONTH);
});

test("a chart not reaching the look-back's start is missing, with what it holds", () => {
  const days = tradingDays(DAY).filter((day) => day >= "2024-04-15");
  const decision = withBbca(seriesOn(days));
  expect(decision).toEqual({
    weights: new Map(),
    reasons: new Map(),
    missing: [missingHistory("BBCA", { from: "2024-04-15", to: DAY }, 35n)],
    memory: LAST_MONTH,
    notes: [],
  });
});

// Reviews.

test("its first advice day is a review", () => {
  const decision = SMALL.decide(allOf("2024-05-15", { BBCA: {} }), CASH, NONE);
  expect(Object.fromEntries(decision.memory)).toEqual({ set: "IDX:BBCA", month: "2024-05" });
});

test("the first advice day of a new month is a review", () => {
  const decision = SMALL.decide(allOf(DAY, { BBCA: {} }), CASH, LAST_MONTH);
  expect(Object.fromEntries(decision.memory)).toEqual({ set: "IDX:BBCA", month: "2024-05" });
});

test("the same month in another year is a review", () => {
  const lastYear: Memory = new Map([
    ["set", "IDX:TLKM"],
    ["month", "2023-05"],
  ]);
  const decision = SMALL.decide(allOf(DAY, { BBCA: {} }), CASH, lastYear);
  expect(Object.fromEntries(decision.memory)).toEqual({ set: "IDX:BBCA", month: "2024-05" });
});

const THIS_MONTH: Memory = new Map([
  ["set", "IDX:BBCA"],
  ["month", "2024-05"],
]);

test("between reviews it keeps its holdings and tops its picks up with new cash", () => {
  // TLKM is worth 0.6 and keeps it, above 1/2; the 400,000 cash takes BBCA to 0.4.
  const decision = SMALL.decide(
    view(DAY, ["BBCA", "ASII"]),
    portfolioOf(400_000n, { TLKM: 600_000n }),
    THIS_MONTH,
  );
  expect(weighed(decision.weights)).toEqual({ TLKM: "0.6", BBCA: "0.4" });
  expect(Object.fromEntries(decision.reasons)).toEqual({
    TLKM: "low-volatility: held until the next review",
    BBCA: "low-volatility: picked at the last review, topped up to its share",
  });
  expect([decision.memory, decision.missing, decision.notes]).toEqual([THIS_MONTH, [], []]);
});

test("between reviews no pick is topped up above 1/volatility_stocks", () => {
  const decision = SMALL.decide(view(DAY, ["BBCA"]), CASH, THIS_MONTH);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5" });
});

test("a memory with a month but no set is refused", () => {
  const broken: Memory = new Map([["month", "2024-05"]]);
  expect(() => SMALL.decide(view(DAY, []), CASH, broken)).toThrow(
    new Error("low-volatility's memory has a month but no set"),
  );
});
