import { expect, test } from "vitest";
import type { Covered, Day, Dividend, Dividends } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { MOMENTUM_ROTATION, momentumRotation } from "../src/momentum-rotation.ts";
import { IDR, Money } from "../src/money.ts";
import { missingHistory, missingPage, note, NOTE_CODES } from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import type { SeriesClose, StockSeries } from "../src/series.ts";
import type { PortfolioView } from "../src/sizing.ts";
import type { MarketView, Memory } from "../src/strategy.ts";

/** The shipped IDX trading days, read once. */
const CALENDAR = IdxCalendar.shipped();

// Hand-computed examples, one test per case, written from spec §7.2 before the code: there is no
// Python reference for momentum-rotation (#235 AC1).
//
// Most tests use `momentum_months` 2 and `skip_months` 1, and the advice day is Friday 31 May 2024.
// Its momentum runs from the close
// on the last trading day on or before Sunday 31 March (Good Friday, 29 March, is a holiday, so
// Thursday 28 March) to the close on the last trading day on or before 30 April (April has no
// 31st). Every close is 100 unless a test sets it, so a stock's momentum is its 30 April close over
// its 28 March close.

const STOCKS = ["ASII", "BBCA", "BBRI", "TLKM", "UNVR"] as const;
/** Holds the 2 strongest. */
const SMALL = momentumRotation(2n, 2n, 1n);
/** Holds the single strongest. */
const ONE = momentumRotation(1n, 2n, 1n);
const DAY: Day = "2024-05-31";
const HOLIDAYS = new Set(["2024-03-29"]);

/** Each year's month lengths; 1 January 2023 is a Sunday. */
const YEARS = [
  ["2023", [31n, 28n, 31n, 30n, 31n, 30n, 31n, 31n, 30n, 31n, 30n, 31n]],
  ["2024", [31n, 29n, 31n, 30n, 31n, 30n, 31n, 31n, 30n, 31n, 30n, 31n]],
] as const;

/** Every day of 2023 and 2024 up to `until`, with whether it is a trading day. */
const calendar = (until: Day): { readonly day: Day; readonly trading: boolean }[] => {
  const days: { readonly day: Day; readonly trading: boolean }[] = [];
  // Monday is 0, so Sunday 1 January 2023 is 6.
  let weekday = 6n;
  for (const [year, months] of YEARS) {
    let month = 1n;
    for (const monthDays of months) {
      for (let date = 1n; date <= monthDays; date += 1n) {
        const day = `${year}-${month.toString().padStart(2, "0")}-${date.toString().padStart(2, "0")}`;
        if (day <= until) {
          days.push({ day, trading: weekday < 5n && !HOLIDAYS.has(day) });
        }
        weekday = (weekday + 1n) % 7n;
      }
      month += 1n;
    }
  }
  return days;
};

/** The trading days of 2023 and 2024 up to `until`. */
const tradingDays = (until: Day): Day[] =>
  calendar(until)
    .filter((entry) => entry.trading)
    .map((entry) => entry.day);

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

/** The stocks `ONE` picks among `sets` on `day`, with all cash. */
const pickedBy = (
  day: Day,
  sets: Readonly<Record<string, Readonly<Record<string, string>>>>,
): Record<string, string> => weighed(ONE.decide(allOf(day, sets), CASH, NONE).weights);

const among = (count: bigint): string =>
  `momentum-rotation: among the ${count.toString()} strongest by momentum`;
const notAmong = (count: bigint): string =>
  `momentum-rotation: not among the ${count.toString()} strongest by momentum`;

// Its settings (AC2, AC3).

test("it is a strategy named momentum-rotation with its settings, by default 10, 12 and 1", () => {
  const strategy = momentumRotation();
  expect(strategy.name).toBe("momentum-rotation");
  expect([strategy.momentumStocks, strategy.momentumMonths, strategy.skipMonths]).toEqual([
    10n,
    12n,
    1n,
  ]);
  expect(MOMENTUM_ROTATION).toEqual({ momentumStocks: 10n, momentumMonths: 12n, skipMonths: 1n });
});

test.each([
  ["momentum_stocks must be at least 1, got 0", 0n, 12n, 1n],
  ["skip_months must be at least 0, got -1", 10n, 12n, -1n],
  ["skip_months must be below momentum_months, got 12 and 12", 10n, 12n, 12n],
  ["skip_months must be below momentum_months, got 3 and 2", 10n, 2n, 3n],
] as const)("%s", (message, stocks, months, skip) => {
  expect(() => momentumRotation(stocks, months, skip)).toThrow(new RangeError(message));
});

// A review (AC3).

test("a review holds the strongest at 1/momentum_stocks each and says why of every stock", () => {
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
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBCA: "0.5" });
  expect(Object.fromEntries(decision.reasons)).toEqual({
    ASII: among(2n),
    BBCA: among(2n),
    BBRI: notAmong(2n),
    TLKM: notAmong(2n),
  });
  expect([decision.missing, decision.notes]).toEqual([[], []]);
  expect(Object.fromEntries(decision.memory)).toEqual({
    set: "IDX:ASII IDX:BBCA",
    month: "2024-05",
  });
});

test("a fall is weaker than no change, and the strongest fall is the weakest", () => {
  const decision = SMALL.decide(
    allOf(DAY, {
      ASII: { "2024-04-30": "50" },
      BBCA: { "2024-04-30": "90" },
      BBRI: {},
    }),
    CASH,
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", BBRI: "0.5" });
});

test("equal momentums are ranked by symbol", () => {
  const decision = SMALL.decide(allOf(DAY, { TLKM: {}, BBRI: {}, BBCA: {}, ASII: {} }), CASH, NONE);
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBCA: "0.5" });
});

test("momentums are compared exactly: 1/3 up beats 33.333333% up", () => {
  // BBCA's 300 → 400 is 1/3 up; ASII's 30000000 → 39999999.99 is a hair less:
  // 400 × 30000000 = 12,000,000,000 against 39999999.99 × 300 = 11,999,999,997.
  const decision = ONE.decide(
    allOf(DAY, {
      ASII: { "2024-03-28": "30000000", "2024-04-30": "39999999.99" },
      BBCA: { "2024-03-28": "300", "2024-04-30": "400" },
    }),
    CASH,
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});

test("a held stock not among the strongest is sold, and one that left the universe too", () => {
  const decision = SMALL.decide(
    allOf(DAY, { ASII: { "2024-04-30": "130" }, BBCA: { "2024-04-30": "120" }, TLKM: {} }),
    portfolioOf(500_000n, { TLKM: 300_000n, UNVR: 200_000n }),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBCA: "0.5" });
  expect(Object.fromEntries(decision.reasons)).toEqual({
    ASII: among(2n),
    BBCA: among(2n),
    TLKM: notAmong(2n),
    UNVR: "momentum-rotation: no longer in the universe",
  });
});

test("a held stock it cannot buy is still ranked and kept when it is among the strongest", () => {
  const series = { ASII: seriesTo(DAY, { "2024-04-30": "130" }), BBCA: seriesTo(DAY) };
  const decision = ONE.decide(
    view(DAY, ["BBCA"], { members: ["ASII"], series }),
    portfolioOf(500_000n, { ASII: 500_000n }),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "1" });
  expect(Object.fromEntries(decision.reasons)).toEqual({ ASII: among(1n), BBCA: notAmong(1n) });
});

test("with fewer stocks to rank than momentum_stocks, the rest stays cash, with a note", () => {
  const decision = SMALL.decide(allOf(DAY, { BBCA: {} }), CASH, NONE);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5" });
  expect(decision.notes).toEqual([
    note(
      NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
      "Only 1 stock could be ranked by momentum; the rest is held as cash until more can.",
    ),
  ]);
});

test("the note counts two stocks as stocks", () => {
  const decision = momentumRotation(3n, 2n, 1n).decide(
    allOf(DAY, { ASII: {}, BBCA: {} }),
    CASH,
    NONE,
  );
  expect(decision.notes).toEqual([
    note(
      NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
      "Only 2 stocks could be ranked by momentum; the rest is held as cash until more can.",
    ),
  ]);
});

test("with no stock to rank, everything is cash, with a note", () => {
  const decision = SMALL.decide(view(DAY, []), CASH, NONE);
  expect([weighed(decision.weights), decision.notes]).toEqual([
    {},
    [
      note(
        NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
        "No stock could be ranked by momentum; everything is held as cash until one can.",
      ),
    ],
  ]);
});

// Its window's ends (AC2, AC7).

test("a window starting on a weekend before a holiday takes the close of the day before both", () => {
  // Start: Sunday 31 March; Saturday 30 and Good Friday 29 have no close, so Thursday 28 March.
  // TLKM would win on 27 March, BBRI on Monday 1 April.
  const picked = pickedBy(DAY, {
    BBCA: { "2024-03-28": "50" },
    BBRI: { "2024-04-01": "40" },
    TLKM: { "2024-03-27": "40" },
  });
  expect(picked).toEqual({ BBCA: "1" });
});

test("a window ending on a 31st that a 30-day month lacks ends on its 30th", () => {
  // End: 31 May less a month is 30 April. ASII would win on 1 May, BBCA on 29 April.
  const picked = pickedBy(DAY, {
    ASII: { "2024-05-01": "300" },
    BBCA: { "2024-04-29": "300" },
    BBRI: { "2024-04-30": "200" },
  });
  expect(picked).toEqual({ BBRI: "1" });
});

test("in 31-day months a window runs from a trading 31st to the Friday before a Sunday 30th", () => {
  // Advice day Wednesday 31 July: the start is Friday 31 May itself, the end Sunday 30 June, so
  // Friday 28 June. BBCA would win on 30 May, BBRI on 3 June, TLKM on Monday 1 July.
  const picked = pickedBy("2024-07-31", {
    ASII: { "2024-05-31": "50" },
    BBCA: { "2024-05-30": "40" },
    BBRI: { "2024-06-03": "40" },
    TLKM: { "2024-07-01": "300" },
  });
  expect(picked).toEqual({ ASII: "1" });
});

test("a window starting on a 30th that February lacks starts on the leap day", () => {
  // Advice day 30 April: the start is 29 February, the end Saturday 30 March, so (Good Friday)
  // Thursday 28 March. ASII would win on 1 March, BBCA on 28 February, TLKM on 27 March.
  const picked = pickedBy("2024-04-30", {
    ASII: { "2024-03-01": "40" },
    BBCA: { "2024-02-28": "40" },
    TLKM: { "2024-03-27": "300" },
    UNVR: { "2024-02-29": "50" },
  });
  expect(picked).toEqual({ UNVR: "1" });
});

test("momentum is of total-return closes: a dividend counts as a gain", () => {
  // ASII stays at 100 but pays 20 on 15 April, so its closes before then are 80: 100/80 = 1.25
  // beats BBCA's 120/100 = 1.2.
  const dividend: Dividend = {
    symbol: "ASII",
    exDate: "2024-04-15",
    paymentDate: "2024-05-15",
    grossPerShare: new RuleDecimal("20"),
  };
  const series = { ASII: seriesTo(DAY), BBCA: seriesTo(DAY, { "2024-04-30": "120" }) };
  const decision = ONE.decide(
    view(DAY, ["ASII", "BBCA"], { series, dividends: [dividend] }),
    CASH,
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "1" });
});

// What it needs (AC6), and missing versus ineligible (spec §7.1).

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

// Ranked once its chart proves it traded at the window's start, 31 March (#490 AC3, AC5, ruled
// 2026-11-04): no count of closes is needed.

const NOT_TRADING = "momentum-rotation: not ranked, it had not started trading by 2024-03-31";
/** BBCA, listed on 1 April, inside the window: its chart reaches back to 1 March. */
const NEW_LISTING = seriesOn(
  tradingDays(DAY).filter((day) => day >= "2024-04-01"),
  {},
  "2024-03-01",
);

test("a listing on the window's first trading day is ranked, with that day's close", () => {
  // 28 March, the last trading day on or before 31 March, to 30 April: 100 to 150.
  const days = tradingDays(DAY).filter((day) => day >= "2024-03-28");
  const decision = ONE.decide(
    view(DAY, ["ASII", "BBCA"], {
      series: { ASII: seriesTo(DAY), BBCA: seriesOn(days, { "2024-04-30": "150" }, "2024-03-01") },
    }),
    CASH,
    NONE,
  );
  expect([weighed(decision.weights), decision.missing]).toEqual([{ BBCA: "1" }, []]);
});

test("ineligible: a listing inside the window is not ranked, and the others still are", () => {
  const decision = withBbca(NEW_LISTING);
  expect([
    weighed(decision.weights),
    Object.fromEntries(decision.reasons),
    decision.missing,
    decision.memory,
    decision.notes,
  ]).toEqual([
    { ASII: "0.5" },
    { ASII: among(2n), BBCA: NOT_TRADING },
    [],
    new Map([
      ["set", "IDX:ASII"],
      ["month", "2024-05"],
    ]),
    [
      note(
        NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
        "Only 1 stock could be ranked by momentum; the rest is held as cash until more can.",
      ),
    ],
  ]);
});

test("ineligible: a listing already held is sold, with a reason naming the window's start", () => {
  const decision = SMALL.decide(
    view(DAY, ["ASII", "BBCA"], { series: { ASII: seriesTo(DAY), BBCA: NEW_LISTING } }),
    portfolioOf(500_000n, { BBCA: 500_000n }),
    LAST_MONTH,
  );
  expect([weighed(decision.weights), Object.fromEntries(decision.reasons)]).toEqual([
    { ASII: "0.5" },
    { ASII: among(2n), BBCA: NOT_TRADING },
  ]);
});

test("ineligible needs no dividend read: it is not judged by total return", () => {
  const decision = withBbca(NEW_LISTING, { covered: { BBCA: { from: "2024-05-01", to: DAY } } });
  expect([weighed(decision.weights), decision.missing]).toEqual([{ ASII: "0.5" }, []]);
});

test("a chart whose range starts after the window's start is missing history, however long", () => {
  // 15 April to 31 May, every calendar day: 47 closes, none on or before 31 March.
  const days = calendar(DAY)
    .map((entry) => entry.day)
    .filter((day) => day >= "2024-04-15");
  expect(BigInt(days.length)).toBe(47n);
  const decision = withBbca(seriesOn(days));
  expect(decision).toEqual({
    weights: new Map(),
    reasons: new Map(),
    missing: [missingHistory("BBCA", { from: "2024-04-15", to: DAY }, 47n)],
    memory: LAST_MONTH,
    notes: [],
  });
});

test("self-recorded closes with no chart range are missing history, however long", () => {
  const days = tradingDays(DAY);
  const decision = withBbca({ ...seriesOn(days), covered: null });
  expect(decision.missing).toEqual([
    missingHistory("BBCA", { from: "2023-01-02", to: DAY }, BigInt(days.length)),
  ]);
});

test("a stock with no series is missing its chart", () => {
  const decision = SMALL.decide(
    view(DAY, ["ASII", "BBCA"], { series: { ASII: seriesTo(DAY) } }),
    CASH,
    LAST_MONTH,
  );
  expect([decision.missing, decision.memory]).toEqual([
    [missingPage("stock-detail", "BBCA")],
    LAST_MONTH,
  ]);
});

test("a series with no closes is missing its chart", () => {
  const decision = withBbca(seriesOn([]));
  expect(decision.missing).toEqual([missingPage("stock-detail", "BBCA")]);
});

test("a series asking for its chart again is missing what it asks", () => {
  const asking = { ...seriesTo(DAY), missing: [missingPage("stock-detail", "BBCA")] };
  const decision = withBbca(asking);
  expect(decision.missing).toEqual([missingPage("stock-detail", "BBCA")]);
});

test("a dividend read short of the series is missing its dividends", () => {
  const decision = withBbca(seriesTo(DAY), {
    covered: { BBCA: { from: "2024-03-01", to: DAY } },
  });
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
});

test("a stock that left the universe needs no series", () => {
  const decision = SMALL.decide(
    view(DAY, ["ASII"], { series: { ASII: seriesTo(DAY) } }),
    portfolioOf(0n, { UNVR: 1_000_000n }),
    NONE,
  );
  expect([weighed(decision.weights), decision.missing]).toEqual([{ ASII: "0.5" }, []]);
});

// Reviews (AC5) and between them (AC4).

test("its first advice day is a review", () => {
  const decision = SMALL.decide(allOf("2024-05-15", { BBCA: {} }), CASH, NONE);
  expect(Object.fromEntries(decision.memory)).toEqual({ set: "IDX:BBCA", month: "2024-05" });
});

test("the first advice day of a new month is a review", () => {
  const decision = SMALL.decide(allOf(DAY, { BBCA: {} }), CASH, LAST_MONTH);
  expect(Object.fromEntries(decision.memory)).toEqual({ set: "IDX:BBCA", month: "2024-05" });
});

test("the same month's month in another year is a review", () => {
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
    TLKM: "momentum-rotation: held until the next review",
    BBCA: "momentum-rotation: picked at the last review, topped up to its share",
  });
  expect([decision.memory, decision.missing, decision.notes]).toEqual([THIS_MONTH, [], []]);
});

test("between reviews no pick is topped up above 1/momentum_stocks", () => {
  const decision = SMALL.decide(view(DAY, ["BBCA"]), CASH, THIS_MONTH);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5" });
});

test("a memory with a month but no set is refused", () => {
  const broken: Memory = new Map([["month", "2024-05"]]);
  expect(() => SMALL.decide(view(DAY, []), CASH, broken)).toThrow(
    new Error("momentum-rotation's memory has a month but no set"),
  );
});
