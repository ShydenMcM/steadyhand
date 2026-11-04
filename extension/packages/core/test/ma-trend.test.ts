import { expect, test } from "vitest";
import type { Covered, Day, Dividend, Dividends } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { MA_TREND, maTrend } from "../src/ma-trend.ts";
import { IDR, Money } from "../src/money.ts";
import { missingHistory, missingPage, type Note } from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import type { SeriesClose, StockSeries } from "../src/series.ts";
import type { PortfolioView } from "../src/sizing.ts";
import type { MarketView, Memory } from "../src/strategy.ts";

// Hand-computed examples, one test per case, written from spec §7.2 before the code: there is no
// Python reference for ma-trend (#234 AC1).
//
// Most tests use `fast_days` 2 and `slow_days` 4, so a stock is in an uptrend when the average of
// its last 2 total-return closes is strictly above the average of its last 4. Its closes fall on
// consecutive days from 1 January 2024, and the advice day is its last close's day.

const STOCKS = ["ASII", "BBCA", "BBRI", "TLKM", "UNVR"] as const;
const SMALL = maTrend(2n, 4n);
const CALENDAR = IdxCalendar.shipped();

const rp = (amount: bigint): Money => new Money(amount, IDR);

/** The `index`th day from 1 January 2024, in months of 28 days: ordered, and enough for 336. */
const dayOf = (index: bigint): Day => {
  const month = (1n + index / 28n).toString().padStart(2, "0");
  const date = (1n + (index % 28n)).toString().padStart(2, "0");
  return `2024-${month}-${date}`;
};

/** A series of `closes`, the first on 1 January 2024, unadjusted for dividends, from a chart
 * whose range starts on its first close. */
const seriesOf = (closes: readonly string[]): StockSeries => {
  const daily: SeriesClose[] = [];
  let index = 0n;
  for (const close of closes) {
    daily.push({ day: dayOf(index), close: new RuleDecimal(close) });
    index += 1n;
  }
  const first = daily[0];
  const covered = first === undefined ? null : { from: first.day, to: dayOf(index - 1n) };
  return { closes: daily, covered, dividendsAdjustedTo: null, missing: [] };
};

/** `count` closes of `close`. */
const flat = (count: bigint, close: string): string[] => {
  const closes: string[] = [];
  for (let made = 0n; made < count; made += 1n) {
    closes.push(close);
  }
  return closes;
};

/** 100, 100, 110, 110: the last 2 average 110, above the last 4's 105. */
const RISING = ["100", "100", "110", "110"] as const;
/** 110, 110, 100, 100: the last 2 average 100, below the last 4's 105. */
const FALLING = ["110", "110", "100", "100"] as const;
/** The advice day of a 4-close series. */
const DAY = dayOf(3n);

interface ViewOptions {
  /** The universe, beyond the buyable stocks. */
  readonly members?: readonly string[];
  /** Each stock's series; a stock unlisted has none. */
  readonly series?: Readonly<Record<string, StockSeries>>;
  readonly dividends?: readonly Dividend[];
  /** Each stock's dividend read period; `null` is no read. Unlisted stocks were read from 2015
   * to the advice day. */
  readonly covered?: Readonly<Record<string, Covered | null>>;
}

const view = (day: Day, buyable: readonly string[], options: ViewOptions = {}): MarketView => {
  const reads = new Map<string, Dividends>();
  for (const symbol of STOCKS) {
    const covered =
      options.covered === undefined || !(symbol in options.covered)
        ? { from: "2015-01-01", to: day }
        : options.covered[symbol];
    if (covered !== null && covered !== undefined) {
      const own = (options.dividends ?? []).filter((paidOut) => paidOut.symbol === symbol);
      reads.set(symbol, { symbol, covered, dividends: own });
    }
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

/** The weights `SMALL` gives BBCA alone, buyable, with all cash, on its series' last day. */
const alone = (closes: readonly string[]): Record<string, string> => {
  const series = seriesOf(closes);
  const day = series.closes.at(-1)?.day ?? DAY;
  return weighed(
    SMALL.decide(view(day, ["BBCA"], { series: { BBCA: series } }), CASH, NONE).weights,
  );
};

const decided = (day: Day, buyable: readonly string[], options: ViewOptions, portfolio = CASH) =>
  SMALL.decide(view(day, buyable, options), portfolio, NONE);

const UP = "ma-trend: in an uptrend, its 2-day average above its 4-day average";
const DOWN = "ma-trend: not in an uptrend, its 2-day average not above its 4-day average";
const LEFT = "ma-trend: no longer in the universe";

// Its settings (AC2).

test("it is a strategy named ma-trend with its settings, by default 50 and 200", () => {
  const strategy = maTrend();
  expect(strategy.name).toBe("ma-trend");
  expect([strategy.fastDays, strategy.slowDays]).toEqual([50n, 200n]);
  expect(MA_TREND).toEqual({ fastDays: 50n, slowDays: 200n });
});

test.each([
  ["fast_days must be at least 1, got 0", 0n, 4n],
  ["fast_days must be below slow_days, got 4 and 4", 4n, 4n],
  ["fast_days must be below slow_days, got 5 and 4", 5n, 4n],
] as const)("its settings are refused by name: %s", (message, fastDays, slowDays) => {
  expect(() => maTrend(fastDays, slowDays)).toThrow(new RangeError(message));
});

test("fast_days 1 and slow_days 2 are allowed", () => {
  expect([maTrend(1n, 2n).fastDays, maTrend(1n, 2n).slowDays]).toEqual([1n, 2n]);
});

// The trend (AC2, AC5): BBCA alone, so it is held at 1/1 in an uptrend and not at all otherwise.

test("uptrend: the last 2 closes average 110, above the last 4's 105", () => {
  expect(alone(RISING)).toEqual({ BBCA: "1" });
});

test("downtrend: the last 2 closes average 100, below the last 4's 105", () => {
  expect(alone(FALLING)).toEqual({});
});

test("equal averages are not an uptrend: four closes of 100", () => {
  expect(alone(flat(4n, "100"))).toEqual({});
});

test("only the last 4 closes count: an older close of 10 would lift the trend if it did", () => {
  expect(alone(["10", "100", "100", "100", "100"])).toEqual({});
});

test("only the last 2 closes are the fast average: 90 and 120 average 105, below 110", () => {
  // The last 3 would average 113.33, above the last 4's 110.
  expect(alone(["100", "130", "90", "120"])).toEqual({});
});

test("the defaults judge exactly 200 closes: 150 of 100 then 50 of 101 is an uptrend", () => {
  // The last 50 average 101, the last 200 average 100.25.
  const series = seriesOf([...flat(150n, "100"), ...flat(50n, "101")]);
  const day = dayOf(199n);
  const found = maTrend().decide(view(day, ["BBCA"], { series: { BBCA: series } }), CASH, NONE);
  expect([weighed(found.weights), found.missing]).toEqual([{ BBCA: "1" }, []]);
});

// Total return (AC2, spec §6.5): dividends are reinvested before the averages are taken.

test("a dividend reinvested turns a falling price into an uptrend", () => {
  // 100, 100, 96, 96 falls (96 against 98), but 5 paid on the third day scales the first two
  // closes by 1 - 5/100 to 95: 96 is above 95.5.
  const dividend: Dividend = {
    symbol: "BBCA",
    exDate: dayOf(2n),
    paymentDate: dayOf(3n),
    grossPerShare: new RuleDecimal("5"),
  };
  const options = { series: { BBCA: seriesOf(["100", "100", "96", "96"]) }, dividends: [dividend] };
  expect(weighed(decided(DAY, ["BBCA"], options).weights)).toEqual({ BBCA: "1" });
});

// Sizing (AC3): N is the number of universe members that day.

test("an uptrend stock not held is targeted at 1/N: BBCA at 1/4 among four members", () => {
  const series = { BBCA: seriesOf(RISING), BBRI: seriesOf(FALLING), TLKM: seriesOf(FALLING) };
  const found = decided(DAY, ["BBCA", "BBRI", "TLKM"], { members: ["UNVR"], series });
  expect(weighed(found.weights)).toEqual({ BBCA: "0.25" });
});

test("N counts every member, judged or not: UNVR, neither buyable nor held, needs no series", () => {
  const found = decided(DAY, ["BBCA"], {
    members: ["ASII", "BBRI", "TLKM", "UNVR"],
    series: { BBCA: seriesOf(RISING) },
  });
  expect([weighed(found.weights), found.missing]).toEqual([{ BBCA: "0.2" }, []]);
});

test("a held uptrend stock above 1/N keeps its weight", () => {
  const series = { BBCA: seriesOf(RISING), BBRI: seriesOf(FALLING) };
  const found = decided(
    DAY,
    ["BBCA", "BBRI"],
    { series },
    portfolioOf(400_000n, { BBCA: 600_000n }),
  );
  expect(weighed(found.weights)).toEqual({ BBCA: "0.6" });
});

test("a held uptrend stock below 1/N is topped up to 1/N with new cash", () => {
  const series = { BBCA: seriesOf(RISING), BBRI: seriesOf(FALLING) };
  const found = decided(
    DAY,
    ["BBCA", "BBRI"],
    { series },
    portfolioOf(900_000n, { BBCA: 100_000n }),
  );
  expect(weighed(found.weights)).toEqual({ BBCA: "0.5" });
});

test("new cash goes only to uptrend stocks below 1/N: all 0.2 to BBRI, none to BBCA at 0.8", () => {
  const series = { BBCA: seriesOf(RISING), BBRI: seriesOf(RISING) };
  const found = decided(
    DAY,
    ["BBCA", "BBRI"],
    { series },
    portfolioOf(200_000n, { BBCA: 800_000n }),
  );
  expect(weighed(found.weights)).toEqual({ BBCA: "0.8", BBRI: "0.2" });
});

test("new cash short of 1/N for all is shared equally: 0.15 each to BBCA and BBRI", () => {
  const series = { BBCA: seriesOf(RISING), BBRI: seriesOf(RISING), TLKM: seriesOf(RISING) };
  const portfolio = portfolioOf(300_000n, { TLKM: 700_000n });
  const found = decided(DAY, ["BBCA", "BBRI", "TLKM"], { members: ["ASII"], series }, portfolio);
  expect(weighed(found.weights)).toEqual({ BBCA: "0.15", BBRI: "0.15", TLKM: "0.7" });
});

test("a held uptrend member it cannot buy keeps its weight and gets no new cash", () => {
  const options = { members: ["BBCA"], series: { BBCA: seriesOf(RISING) } };
  const found = decided(DAY, [], options, portfolioOf(900_000n, { BBCA: 100_000n }));
  expect([weighed(found.weights), found.missing]).toEqual([{ BBCA: "0.1" }, []]);
});

test("an uptrend member it can neither buy nor holds gets no weight", () => {
  const found = decided(DAY, [], { members: ["BBCA"], series: { BBCA: seriesOf(RISING) } });
  expect(weighed(found.weights)).toEqual({});
});

test("a downtrend sells the whole holding, and says why", () => {
  const found = decided(
    DAY,
    ["BBCA"],
    { series: { BBCA: seriesOf(FALLING) } },
    portfolioOf(0n, { BBCA: 500_000n }),
  );
  expect([weighed(found.weights), Object.fromEntries(found.reasons)]).toEqual([{}, { BBCA: DOWN }]);
});

test("leaving the universe sells the whole holding unjudged, and says why", () => {
  // ASII has no series: a stock outside the universe is not judged, so none is needed.
  const found = decided(
    DAY,
    ["BBCA"],
    { series: { BBCA: seriesOf(RISING) } },
    portfolioOf(500_000n, { ASII: 500_000n }),
  );
  expect([weighed(found.weights), Object.fromEntries(found.reasons), found.missing]).toEqual([
    { BBCA: "0.5" },
    { ASII: LEFT, BBCA: UP },
    [],
  ]);
});

test("an empty universe sells every holding unjudged", () => {
  const found = decided(DAY, [], {}, portfolioOf(500_000n, { BBCA: 500_000n }));
  expect([weighed(found.weights), Object.fromEntries(found.reasons)]).toEqual([{}, { BBCA: LEFT }]);
});

test("every advice day is judged afresh: the memory is kept as given and nothing is noted", () => {
  const memory: Memory = new Map([["kept", "as given"]]);
  const found = SMALL.decide(
    view(DAY, ["BBCA"], { series: { BBCA: seriesOf(RISING) } }),
    CASH,
    memory,
  );
  expect([found.memory, found.notes, Object.fromEntries(found.reasons)]).toEqual([
    memory,
    [],
    { BBCA: UP },
  ]);
});

// Missing (AC4, AC5): nothing is ordered until every judged stock has its slow_days closes.

/** What `SMALL` says for BBCA, buyable, holding TLKM, with `options`: no orders and its gaps. */
const gaps = (options: ViewOptions, day: Day = DAY): readonly Note[] => {
  const found = decided(day, ["BBCA"], options, portfolioOf(500_000n, { TLKM: 500_000n }));
  expect([weighed(found.weights), found.memory]).toEqual([{}, NONE]);
  return found.missing;
};

test("missing: one close fewer than slow_days names the window and the closes held", () => {
  expect(gaps({ series: { BBCA: seriesOf(["100", "100", "110"]) } }, dayOf(2n))).toEqual([
    missingHistory("BBCA", { from: dayOf(0n), to: dayOf(2n) }, 3n),
  ]);
});

test("missing: the defaults with 199 closes", () => {
  const series = seriesOf(flat(199n, "100"));
  const day = dayOf(198n);
  const found = maTrend().decide(view(day, ["BBCA"], { series: { BBCA: series } }), CASH, NONE);
  expect([weighed(found.weights), found.missing]).toEqual([
    {},
    [missingHistory("BBCA", { from: dayOf(0n), to: day }, 199n)],
  ]);
});

test("missing: no series lists the price chart", () => {
  expect(gaps({})).toEqual([missingPage("stock-detail", "BBCA")]);
});

test("missing: a series of no closes lists the price chart", () => {
  expect(gaps({ series: { BBCA: seriesOf([]) } })).toEqual([missingPage("stock-detail", "BBCA")]);
});

test("missing: a series that asks for its chart again lists it", () => {
  const series = { ...seriesOf(RISING), missing: [missingPage("stock-detail", "BBCA")] };
  expect(gaps({ series: { BBCA: series } })).toEqual([missingPage("stock-detail", "BBCA")]);
});

test("missing: no dividend read for the series' window lists the dividend page", () => {
  const options = { series: { BBCA: seriesOf(RISING) }, covered: { BBCA: null } };
  expect(gaps(options)).toEqual([missingPage("dividends", "BBCA")]);
});

test("missing: every judged stock is listed, in symbol order, with the rest read", () => {
  const options = { members: ["TLKM"], series: { BBCA: seriesOf(RISING), UNVR: seriesOf(RISING) } };
  const found = decided(
    DAY,
    ["UNVR", "BBCA", "BBRI"],
    options,
    portfolioOf(0n, { TLKM: 500_000n }),
  );
  expect([weighed(found.weights), found.missing]).toEqual([
    {},
    [missingPage("stock-detail", "BBRI"), missingPage("stock-detail", "TLKM")],
  ]);
});

// Ineligible (#490 AC2, AC5, spec §7.1): a stock whose chart reaches back to the start of its
// slow_days window, but whose first close comes after it, was not trading then. It is not in an
// uptrend, and the other stocks still get orders. These use real trading days: the advice day is
// Monday 8 January 2024, so the 4-day window starts on Wednesday 3 January (1 January is a
// holiday, 6 and 7 a weekend).

const MONDAY = "2024-01-08";
/** A series of `closes`, each a day and its close, from a chart whose range starts on `from`. */
const listed = (from: Day, closes: readonly (readonly [Day, string])[]): StockSeries => ({
  closes: closes.map(([day, close]) => ({ day, close: new RuleDecimal(close) })),
  covered: { from, to: MONDAY },
  dividendsAdjustedTo: null,
  missing: [],
});
/** BBRI, in an uptrend over the whole window. */
const BBRI_UP = listed("2023-12-01", [
  ["2024-01-03", "100"],
  ["2024-01-04", "100"],
  ["2024-01-05", "110"],
  [MONDAY, "110"],
]);
/** BBCA, listed on 4 January, inside the window: its chart reaches back to December. */
const NEW_LISTING = listed("2023-12-01", [
  ["2024-01-04", "100"],
  ["2024-01-05", "110"],
  [MONDAY, "120"],
]);
const SHORT = "ma-trend: not in an uptrend, its history is shorter than 4 trading days";

test("ineligible: a listing inside the window is not bought, and the others still are", () => {
  const found = decided(MONDAY, ["BBCA", "BBRI"], { series: { BBCA: NEW_LISTING, BBRI: BBRI_UP } });
  expect([weighed(found.weights), Object.fromEntries(found.reasons), found.missing]).toEqual([
    { BBRI: "0.5" },
    { BBRI: UP },
    [],
  ]);
});

test("ineligible: a listing already held is sold, with a reason naming its short history", () => {
  const found = decided(
    MONDAY,
    ["BBCA", "BBRI"],
    { series: { BBCA: NEW_LISTING, BBRI: BBRI_UP } },
    portfolioOf(500_000n, { BBCA: 500_000n }),
  );
  expect([weighed(found.weights), Object.fromEntries(found.reasons), found.missing]).toEqual([
    { BBRI: "0.5" },
    { BBCA: SHORT, BBRI: UP },
    [],
  ]);
});

test("ineligible needs no dividend read: it is not judged by total return", () => {
  const options = { series: { BBCA: NEW_LISTING, BBRI: BBRI_UP }, covered: { BBCA: null } };
  const found = decided(MONDAY, ["BBCA", "BBRI"], options);
  expect([weighed(found.weights), found.missing]).toEqual([{ BBRI: "0.5" }, []]);
});

test("a listing on the window's first day is judged: 3 January opens its 4 closes", () => {
  const found = decided(MONDAY, ["BBRI"], { series: { BBRI: BBRI_UP } });
  expect([weighed(found.weights), found.missing]).toEqual([{ BBRI: "1" }, []]);
});

test("missing: a chart whose range ends short of the window's start is still missing history", () => {
  const series = listed("2024-01-04", [
    ["2024-01-04", "100"],
    ["2024-01-05", "110"],
    [MONDAY, "120"],
  ]);
  expect(gaps({ series: { BBCA: series } }, MONDAY)).toEqual([
    missingHistory("BBCA", { from: "2024-01-04", to: MONDAY }, 3n),
  ]);
});

test("missing: a chart covering the window with too few closes in it is still missing history", () => {
  // Trading from 2 January, but with no close on 3 or 5 January.
  const series = listed("2023-12-01", [
    ["2024-01-02", "100"],
    ["2024-01-04", "110"],
    [MONDAY, "120"],
  ]);
  expect(gaps({ series: { BBCA: series } }, MONDAY)).toEqual([
    missingHistory("BBCA", { from: "2024-01-02", to: MONDAY }, 3n),
  ]);
});
