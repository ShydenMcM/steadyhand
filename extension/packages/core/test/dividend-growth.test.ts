import { expect, test } from "vitest";
import type { Covered, DailyClose, Day, Dividend, Dividends, Split } from "../src/broker-view.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { DEFAULT_STRATEGY, DIVIDEND_GROWTH, dividendGrowth } from "../src/dividend-growth.ts";
import { IDR, Money } from "../src/money.ts";
import { missingPage, note, NOTE_CODES } from "../src/notes.ts";
import { ratioDown, RuleDecimal } from "../src/ratio.ts";
import { IdxMarketRules } from "../src/rules.ts";
import { lastUnknownAction } from "../src/series.ts";
import type { PortfolioView } from "../src/sizing.ts";
import type { MarketView, Memory } from "../src/strategy.ts";

// Ported from Python's tests/engine/test_dividend_growth.py, one test per case (M6 spec §6), with
// the extension's missing versus ineligible (spec §7.1, #230 AC2 to AC4).
//
// Most tests review on 2 January 2025 with `growth_years` 2, so a stock passes when it paid in
// 2022, 2023 and 2024 and its 2024 total is at least its 2022 total. Pay dates are the broker's
// own, so each is written beside its ex-date.

const STOCKS = ["ASII", "BBCA", "BBRI", "TLKM", "UNVR"] as const;
const REVIEW = "2025-01-02";

/** An ex-date's month and day, and the month and day it pays, in the same year unless `next`. */
interface PaidOn {
  readonly ex: string;
  readonly pay: string;
  readonly next?: true;
}

const MARCH: PaidOn = { ex: "03-04", pay: "03-26" };
const SEPTEMBER: PaidOn = { ex: "09-02", pay: "09-23" };
const DECEMBER: PaidOn = { ex: "12-02", pay: "12-20" };
/** An ex-date that pays in the next year. */
const LATE_DECEMBER: PaidOn = { ex: "12-20", pay: "01-15", next: true };
/** An ex-date that pays in January, and the first day inside a 2 January review's trailing year. */
const EARLY_JANUARY: PaidOn = { ex: "01-04", pay: "01-24" };

const rp = (amount: bigint): Money => new Money(amount, IDR);

const dividend = (symbol: string, exDate: Day, paymentDate: Day, gross: string): Dividend => ({
  symbol,
  exDate,
  paymentDate,
  grossPerShare: new RuleDecimal(gross),
});

/** One dividend a year in 2022, 2023 and 2024, on `on`'s days. */
const paid = (
  symbol: string,
  amounts: readonly [string, string, string] = ["100", "100", "100"],
  on: PaidOn = MARCH,
): Dividend[] => {
  const [first, second, third] = amounts;
  const byYear = [
    ["2022", first],
    ["2023", second],
    ["2024", third],
  ] as const;
  return byYear.map(([year, amount]) => {
    const payYear = on.next === true ? (BigInt(year) + 1n).toString() : year;
    return dividend(symbol, `${year}-${on.ex}`, `${payYear}-${on.pay}`, amount);
  });
};

/** `paid`'s dividends of 2022 and 2024, with none in 2023. */
const skipping2023 = (symbol: string): Dividend[] =>
  paid(symbol).filter((paidOut) => !paidOut.exDate.startsWith("2023"));

interface ViewOptions {
  /** The universe, beyond the buyable stocks. */
  readonly members?: readonly string[];
  readonly closes?: Readonly<Record<string, bigint>>;
  /** Each stock's dividend read period; `null` is no read. Unlisted stocks were read from 2015
   * to the advice day. */
  readonly covered?: Readonly<Record<string, Covered | null>>;
  readonly splits?: readonly Split[];
  /** Each stock's last corporate action found by price with no known ratio (spec §6.4, §6.6). */
  readonly actions?: Readonly<Record<string, Day>>;
}

const view = (
  day: Day,
  buyable: readonly string[],
  dividends: readonly Dividend[] = [],
  options: ViewOptions = {},
): MarketView => {
  const reads = new Map<string, Dividends>();
  for (const symbol of STOCKS) {
    const covered =
      options.covered === undefined || !(symbol in options.covered)
        ? { from: "2015-01-01", to: day }
        : options.covered[symbol];
    if (covered !== null && covered !== undefined) {
      const own = dividends.filter((paidOut) => paidOut.symbol === symbol);
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
    closes: new Map(
      Object.entries(options.closes ?? {}).map(([symbol, worth]) => [symbol, rp(worth)]),
    ),
    dividends: reads,
    splits: options.splits ?? [],
    unknownActions: new Map(Object.entries(options.actions ?? {})),
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

const growth = (minStocks = 1n, maxStocks = 45n, growthYears = 2n) =>
  dividendGrowth(minStocks, maxStocks, growthYears);

/** The weights as text, by symbol, for an exact comparison. */
const weighed = (weights: ReadonlyMap<string, { toString: () => string }>) =>
  Object.fromEntries([...weights].map(([symbol, weight]) => [symbol, weight.toString()]));

const NONE: Memory = new Map();

test("it is a strategy named dividend-growth with its settings, by default 15, 25 and 5", () => {
  const strategy = dividendGrowth();
  expect(strategy.name).toBe("dividend-growth");
  expect([strategy.minStocks, strategy.maxStocks, strategy.growthYears]).toEqual([15n, 25n, 5n]);
  expect(DIVIDEND_GROWTH).toEqual({ minStocks: 15n, maxStocks: 25n, growthYears: 5n });
});

test("dividend-growth stays the default strategy (core §8)", () => {
  expect(DEFAULT_STRATEGY).toBe("dividend-growth");
});

test.each([
  ["min_stocks must be at least 1, got 0", 0n, 25n, 5n],
  ["max_stocks must be at least 1, got 0", 15n, 0n, 5n],
  ["growth_years must be at least 1, got 0", 15n, 25n, 0n],
  ["max_stocks must be at least min_stocks (15), got 14", 15n, 14n, 5n],
] as const)("its settings are refused: %s", (message, minStocks, maxStocks, growthYears) => {
  expect(() => dividendGrowth(minStocks, maxStocks, growthYears)).toThrow(new RangeError(message));
});

const SPLIT_2024: Split = { symbol: "BBCA", exDate: "2024-01-10", from: 1n, to: 2n };

// The dividend test at its boundaries: BBCA alone is judged, with min_stocks 1, so it is picked
// with a weight of 1 when it passes and not at all when it fails.
test.each([
  ["grew", paid("BBCA", ["100", "105", "110"]), [], true],
  ["the last total equals the first", paid("BBCA", ["100", "90", "100"]), [], true],
  ["the last total is just below the first", paid("BBCA", ["100", "120", "99.99"]), [], false],
  ["a year with no dividend", skipping2023("BBCA"), [], false],
  [
    "the first year missing, a year before it paid",
    [dividend("BBCA", "2021-03-04", "2021-03-26", "100"), ...paid("BBCA").slice(1)],
    [],
    false,
  ],
  [
    "the last year missing, today's year paid",
    [...paid("BBCA").slice(0, 2), dividend("BBCA", REVIEW, "2025-01-20", "200")],
    [],
    false,
  ],
  [
    "several dividends in a year are added up",
    [...paid("BBCA", ["100", "100", "40"]), dividend("BBCA", "2024-09-02", "2024-09-23", "60")],
    [],
    true,
  ],
  [
    "several dividends in a year still fall short",
    [...paid("BBCA", ["100", "100", "40"]), dividend("BBCA", "2024-09-02", "2024-09-23", "59.99")],
    [],
    false,
  ],
  ["restated by a later split: 50, 50, 50", paid("BBCA", ["100", "100", "50"]), [SPLIT_2024], true],
  [
    "restated by a later split: 50, 50, 49",
    paid("BBCA", ["100", "100", "49"]),
    [SPLIT_2024],
    false,
  ],
  [
    "a larger dividend before the window does not count",
    [dividend("BBCA", "2021-03-04", "2021-03-26", "500"), ...paid("BBCA")],
    [],
    true,
  ],
  ["no dividend at all", [], [], false],
] as const)("the dividend test: %s", (_case, dividends, splits, passes) => {
  const decision = growth().decide(
    view(REVIEW, ["BBCA"], dividends, { splits }),
    portfolioOf(0n),
    NONE,
  );
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual(passes ? { BBCA: "1" } : {});
});

test("a stock outside the universe fails, even with a record that passes", () => {
  // TLKM holds its record but has left the universe: it is neither buyable nor a member.
  const decision = growth().decide(
    view(REVIEW, ["BBCA"], [...paid("BBCA"), ...paid("TLKM")]),
    portfolioOf(0n, { TLKM: 1_000n }),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
  expect(decision.reasons.get("TLKM")).toBe("dividend-growth: no longer passes the dividend test");
});

test("growth_years sets how many years must have paid", () => {
  const twoYears = paid("BBCA").slice(1);
  const of = (growthYears: bigint) =>
    weighed(
      growth(1n, 45n, growthYears).decide(view(REVIEW, ["BBCA"], twoYears), portfolioOf(0n), NONE)
        .weights,
    );
  expect(of(1n)).toEqual({ BBCA: "1" });
  expect(of(2n)).toEqual({});
});

test("an announced dividend whose ex-date is after the advice day does not count yet", () => {
  // Both pass and pay in March; one is picked by trailing yield. ASII's is 10%; BBCA's is 5%,
  // and would be 25% with its dividend announced for after the review.
  const dividends = [
    ...paid("ASII", ["100", "100", "100"], EARLY_JANUARY),
    ...paid("BBCA", ["50", "50", "50"], EARLY_JANUARY),
    dividend("BBCA", "2025-01-06", "2025-01-27", "200"),
  ];
  const decision = growth(1n, 1n).decide(
    view(REVIEW, ["ASII", "BBCA"], dividends, {
      closes: { ASII: 1_000n, BBCA: 1_000n },
      covered: { BBCA: { from: "2015-01-01", to: "2025-01-31" } },
    }),
    portfolioOf(1_000_000n),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "1" });
});

test("with at most max_stocks passing it holds them all in equal parts", () => {
  const dividends = [
    ...paid("ASII"),
    ...paid("BBCA"),
    ...paid("BBRI"),
    ...paid("TLKM", ["100", "100", "99"]),
  ];
  const decision = growth(2n, 3n).decide(
    view(REVIEW, ["ASII", "BBCA", "BBRI", "TLKM"], dividends),
    portfolioOf(9_000_000n),
    NONE,
  );
  const third = ratioDown(1n, 3n);
  expect(third.toString()).toBe("0.3333333333333333333333333333");
  expect(weighed(decision.weights)).toEqual({
    ASII: third.toString(),
    BBCA: third.toString(),
    BBRI: third.toString(),
  });
  expect(decision.reasons.get("ASII")).toBe(
    "dividend-growth: paid a dividend every year and grew it",
  );
  expect(Object.fromEntries(decision.memory)).toEqual({
    set: "IDX:ASII IDX:BBCA IDX:BBRI",
    year: "2025",
  });
  expect(decision.notes).toEqual([]);
  expect(decision.missing).toEqual([]);
});

test("exactly min_stocks passing holds them in equal parts with no note", () => {
  const decision = growth(2n, 3n).decide(
    view(REVIEW, ["ASII", "BBCA"], [...paid("ASII"), ...paid("BBCA")]),
    portfolioOf(9_000_000n),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBCA: "0.5" });
  expect(decision.notes).toEqual([]);
});

test.each([
  [[], "No stock passed the dividend test; everything is held as cash until one does."],
  [["ASII"], "Only 1 stock passed the dividend test; the rest is held as cash until more do."],
  [
    ["ASII", "BBCA", "BBRI"],
    "Only 3 stocks passed the dividend test; the rest is held as cash until more do.",
  ],
] as const)(
  "fewer than min_stocks passing (%j) leaves the rest in cash and says so",
  (passers, text) => {
    const dividends = passers.flatMap((symbol) => paid(symbol));
    const decision = growth(4n, 5n).decide(
      view(REVIEW, STOCKS, dividends),
      portfolioOf(8_000_000n),
      NONE,
    );
    // Each passer takes a quarter, 1 / min_stocks, and the rest stays in cash.
    expect(weighed(decision.weights)).toEqual(
      Object.fromEntries(passers.map((symbol) => [symbol, "0.25"])),
    );
    expect(decision.notes).toEqual([note(NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED, text)]);
    expect(decision.memory.get("year")).toBe("2025");
  },
);

test("a review sells what failed or left and keeps a suspended passer", () => {
  const dividends = [
    ...paid("ASII"),
    ...paid("BBRI"),
    ...paid("TLKM"),
    ...paid("UNVR"),
    ...paid("BBCA", ["100", "100", "1"]),
  ];
  // ASII (held) and UNVR (not held) pass but are suspended; TLKM passes but left.
  const today = view(REVIEW, ["BBCA", "BBRI"], dividends, { members: ["ASII", "UNVR"] });
  const held = { ASII: 1_000_000n, BBCA: 1_000_000n, TLKM: 1_000_000n };
  const decision = growth(1n, 5n).decide(today, portfolioOf(1_000_000n, held), NONE);
  // Candidates: BBRI (buyable) and ASII (held). BBCA failed and TLKM left, so both go to 0;
  // UNVR can neither be bought nor is held.
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBRI: "0.5" });
  expect(decision.memory.get("set")).toBe("IDX:ASII IDX:BBRI");
  expect(decision.reasons.get("BBCA")).toBe("dividend-growth: no longer passes the dividend test");
  expect(decision.reasons.get("TLKM")).toBe("dividend-growth: no longer passes the dividend test");
});

test("with more passers than max_stocks it spreads pay months before yield", () => {
  const dividends = [
    ...paid("ASII", ["100", "100", "100"], MARCH),
    ...paid("BBCA", ["120", "120", "120"], MARCH),
    ...paid("TLKM", ["20", "20", "20"], SEPTEMBER),
  ];
  const closes = { ASII: 2_000n, BBCA: 2_000n, TLKM: 2_000n };
  const decision = growth(1n, 2n).decide(
    view(REVIEW, ["ASII", "BBCA", "TLKM"], dividends, { closes }),
    portfolioOf(1_000_000n),
    NONE,
  );
  // Yields: BBCA 6%, ASII 5%, TLKM 1%. First pick, no month is crowded: BBCA. Second: ASII
  // would share March with BBCA, TLKM pays alone in September, so TLKM despite its yield.
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", TLKM: "0.5" });
  expect(decision.reasons.get("ASII")).toBe(
    "dividend-growth: not picked, to spread the months paid in",
  );
});

test("a stock paying in two months is as crowded as its least crowded month", () => {
  const dividends = [
    ...paid("BBCA", ["60", "60", "60"], MARCH),
    ...paid("BBCA", ["60", "60", "60"], SEPTEMBER),
    ...paid("ASII", ["100", "100", "100"], MARCH),
    ...paid("TLKM", ["40", "40", "40"], MARCH),
    ...paid("TLKM", ["40", "40", "40"], DECEMBER),
  ];
  const closes = { ASII: 1_000n, BBCA: 1_000n, TLKM: 1_000n };
  const decision = growth(1n, 2n).decide(
    view(REVIEW, ["ASII", "BBCA", "TLKM"], dividends, { closes }),
    portfolioOf(1_000_000n),
    NONE,
  );
  // Yields: BBCA 12%, ASII 10%, TLKM 8%. BBCA first, crowding March and September. ASII's one
  // month, March, has 1 picked; TLKM's least crowded, December, has 0: TLKM.
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", TLKM: "0.5" });
});

test("the pay months are last year's pay dates, as the broker shows them", () => {
  const dividends = [
    // BBCA's ex-dates are in December; they pay in January.
    ...paid("BBCA", ["300", "300", "300"], LATE_DECEMBER),
    ...paid("ASII", ["200", "200", "200"], EARLY_JANUARY),
    ...paid("TLKM", ["100", "100", "100"], DECEMBER),
    // BBRI paid in September before last year; last year it paid in January.
    ...paid("BBRI", ["250", "250", "250"], SEPTEMBER).slice(0, 2),
    dividend("BBRI", "2024-01-04", "2024-01-24", "250"),
  ];
  const closes = { ASII: 10_000n, BBCA: 10_000n, BBRI: 10_000n, TLKM: 10_000n };
  const decision = growth(1n, 2n).decide(
    view(REVIEW, ["ASII", "BBCA", "BBRI", "TLKM"], dividends, { closes }),
    portfolioOf(1_000_000n),
    NONE,
  );
  // Yields: BBCA 3%, BBRI 2.5%, ASII 2%, TLKM 1%. BBCA pays in January. ASII and BBRI pay in
  // January too (BBRI's September is not last year's), and TLKM in December: TLKM.
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", TLKM: "0.5" });
});

test("the trailing yield is the last 365 days of dividends over the last close", () => {
  const dividends = [
    // ASII's 2024 dividend is on 3 January, exactly 365 days back, so outside the window.
    ...paid("ASII", ["100", "100", "900"], { ex: "01-03", pay: "01-23" }),
    ...paid("BBCA", ["100", "100", "100"], EARLY_JANUARY),
    ...paid("BBRI", ["150", "150", "150"], EARLY_JANUARY),
    // TLKM's dividends are the largest, but it has no close to divide by.
    ...paid("TLKM", ["999", "999", "999"], EARLY_JANUARY),
  ];
  const closes = { ASII: 1_000n, BBCA: 1_000n, BBRI: 2_000n };
  const decision = growth(1n, 1n).decide(
    view(REVIEW, ["ASII", "BBCA", "BBRI", "TLKM"], dividends, { closes }),
    portfolioOf(1_000_000n),
    NONE,
  );
  // Yields: ASII 0, BBCA 10%, BBRI 7.5%, TLKM 0.
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});

test("a close of zero gives a yield of zero, not a division by it", () => {
  const dividends = [...paid("ASII"), ...paid("BBCA", ["1", "1", "1"])];
  const closes = { ASII: 0n, BBCA: 1_000n };
  const decision = growth(1n, 1n).decide(
    view(REVIEW, ["ASII", "BBCA"], dividends, { closes }),
    portfolioOf(1_000_000n),
    NONE,
  );
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});

test("equal crowding and yield go to the symbol", () => {
  const dividends = ["TLKM", "BBCA", "ASII"].flatMap((symbol) => paid(symbol));
  const decision = growth(1n, 2n).decide(
    view(REVIEW, ["TLKM", "BBCA", "ASII"], dividends),
    portfolioOf(1_000_000n),
    NONE,
  );
  // No closes, so every yield is 0 and every month is March.
  expect(weighed(decision.weights)).toEqual({ ASII: "0.5", BBCA: "0.5" });
});

/** Picked ASII and BBCA, and TLKM held from before: a 1,000 portfolio with 60 to spend. */
const HOLDING = { ASII: 400n, BBCA: 490n, TLKM: 50n };

const between = (buyable: readonly string[], chosen = "IDX:ASII IDX:BBCA", minStocks = 2n) => {
  const memory: Memory = new Map([
    ["set", chosen],
    ["year", "2025"],
  ]);
  // Between reviews it reads no dividends: none is read here, and none is missing.
  const covered = Object.fromEntries(STOCKS.map((symbol) => [symbol, null]));
  const decision = growth(minStocks, 5n).decide(
    view("2025-03-03", buyable, [], { covered }),
    portfolioOf(60n, HOLDING),
    memory,
  );
  expect(decision.memory).toEqual(memory);
  expect(decision.notes).toEqual([]);
  expect(decision.missing).toEqual([]);
  return decision;
};

test("between reviews it keeps every holding and tops up its picks to their target", () => {
  // 60 / 2 = 30 each, 3%. ASII 40% -> 43%. BBCA 49% takes only 1%, up to its target of 50%.
  const decision = between(["ASII", "BBCA", "TLKM"]);
  expect(weighed(decision.weights)).toEqual({ ASII: "0.43", BBCA: "0.5", TLKM: "0.05" });
  expect(decision.reasons.get("TLKM")).toBe("dividend-growth: held until the next review");
  expect(decision.reasons.get("ASII")).toBe(
    "dividend-growth: picked at the last review, topped up to its share",
  );
});

test("between reviews a pick it cannot buy today gets nothing", () => {
  // BBCA alone may be bought: 6% offered, 1% taken.
  expect(weighed(between(["BBCA", "TLKM"]).weights)).toEqual({
    ASII: "0.4",
    BBCA: "0.5",
    TLKM: "0.05",
  });
  expect(weighed(between([]).weights)).toEqual({ ASII: "0.4", BBCA: "0.49", TLKM: "0.05" });
});

test("between reviews the target is one over min_stocks when fewer were picked", () => {
  // One pick, min_stocks 4: ASII may reach 25%, which is below the 40% it holds.
  expect(between(["ASII"], "IDX:ASII", 4n).weights.get("ASII")?.toString()).toBe("0.4");
  // UNVR, picked but not held, is offered all 60 (6%) and takes it, under its 25% target.
  expect(between(["UNVR"], "IDX:UNVR", 4n).weights.get("UNVR")?.toString()).toBe("0.06");
});

test("it reviews on its first day and its first day in each year only", () => {
  const strategy = growth(1n, 5n);
  const dividends = [
    ...paid("ASII"),
    dividend("ASII", "2025-03-04", "2025-03-26", "100"),
    ...paid("BBCA"),
  ];
  const held = portfolioOf(0n, { ASII: 500n, TLKM: 500n });
  const decide = (day: Day, memory: Memory) =>
    weighed(strategy.decide(view(day, ["ASII", "BBCA", "TLKM"], dividends), held, memory).weights);
  // A first day in June reviews: TLKM fails, so it goes; ASII and BBCA pass.
  expect(decide("2025-06-10", NONE)).toEqual({ ASII: "0.5", BBCA: "0.5" });
  // Later that year it only keeps what it holds.
  const kept: Memory = new Map([
    ["set", "IDX:ASII IDX:BBCA"],
    ["year", "2025"],
  ]);
  // BBCA, picked but not held, is offered the spendable cash: none, so a weight of 0.
  expect(decide("2025-12-30", kept)).toEqual({ ASII: "0.5", BBCA: "0", TLKM: "0.5" });
  // The first day of 2026 reviews again: ASII paid in 2023 to 2025, BBCA stopped in 2024.
  expect(decide("2026-01-02", kept)).toEqual({ ASII: "1" });
});

// Missing versus ineligible (spec §7.1). Missing: the facts have not been read, so the stock is
// listed with the page to open and no orders are given. Ineligible: the facts were read and show
// it cannot pass, so it is not picked.

/** BBCA and BBRI both pass, with every dividend read; `covered` changes BBCA's read. */
const judged = (covered: Covered | null, buyable: readonly string[] = ["BBCA", "BBRI"]) =>
  growth().decide(
    view(REVIEW, buyable, [...paid("BBCA"), ...paid("BBRI")], { covered: { BBCA: covered } }),
    portfolioOf(1_000_000n, { ASII: 1_000n }),
    NONE,
  );

test("missing: a stock it must judge with no dividend read is listed, and nothing is ordered", () => {
  const decision = judged(null);
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
  expect(decision.missing[0]?.text).toBe("open the dividend page for BBCA");
  expect(decision.weights.size).toBe(0);
  expect(decision.notes).toEqual([]);
});

test("missing: the memory is kept as it was, so the next advice day reviews again", () => {
  const memory: Memory = new Map([
    ["set", "IDX:ASII"],
    ["year", "2024"],
  ]);
  const decision = growth().decide(
    view(REVIEW, ["BBCA"], paid("BBCA"), { covered: { BBCA: null } }),
    portfolioOf(0n),
    memory,
  );
  expect(decision.memory).toEqual(memory);
});

test("missing: a read starting a day after the look-back's first day", () => {
  // growth_years 2 on a 2025 review: 3 calendar years, from 1 January 2022.
  const decision = judged({ from: "2022-01-02", to: REVIEW });
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
});

test("missing: a read ending before the advice day", () => {
  const decision = judged({ from: "2015-01-01", to: "2025-01-01" });
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
});

test("a read covering exactly the look-back's first day to the advice day is judged", () => {
  const decision = judged({ from: "2022-01-01", to: REVIEW });
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", BBRI: "0.5" });
});

test("missing: every gap is listed, not only the first, held stocks included", () => {
  const decision = growth().decide(
    view(REVIEW, ["BBCA", "TLKM"], [], {
      members: ["ASII"],
      covered: { ASII: null, BBCA: null, TLKM: null },
    }),
    portfolioOf(1_000_000n, { ASII: 1_000n }),
    NONE,
  );
  expect(decision.missing).toEqual([
    missingPage("dividends", "ASII"),
    missingPage("dividends", "BBCA"),
    missingPage("dividends", "TLKM"),
  ]);
});

test("a stock it need not judge is not missing: a member neither buyable nor held", () => {
  // UNVR is in the universe but suspended and not held, so it can be neither bought nor sold.
  const decision = growth().decide(
    view(REVIEW, ["BBCA"], paid("BBCA"), { members: ["UNVR"], covered: { UNVR: null } }),
    portfolioOf(0n),
    NONE,
  );
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});

test("a stock it need not judge is not missing: a holding outside the universe", () => {
  const decision = growth().decide(
    view(REVIEW, ["BBCA"], paid("BBCA"), { covered: { TLKM: null } }),
    portfolioOf(0n, { TLKM: 1_000n }),
    NONE,
  );
  expect(decision.missing).toEqual([]);
});

test("ineligible: a read covering a year with no dividend is not picked, and is not missing", () => {
  // BBCA's read covers 2022 to the review, and lists nothing for 2023: it paid none then.
  const decision = growth().decide(
    view(REVIEW, ["BBCA", "BBRI"], [...skipping2023("BBCA"), ...paid("BBRI")], {
      covered: { BBCA: { from: "2022-01-01", to: REVIEW } },
    }),
    portfolioOf(1_000_000n),
    NONE,
  );
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBRI: "1" });
});

test("ineligible: a read listing no dividend at all is not picked, and is not missing", () => {
  const decision = growth().decide(
    view(REVIEW, ["BBCA", "BBRI"], paid("BBRI")),
    portfolioOf(1_000_000n),
    NONE,
  );
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBRI: "1" });
});

test("a memory naming a stock of another market is refused", () => {
  const memory: Memory = new Map([
    ["set", "JKT:AALI"],
    ["year", "2025"],
  ]);
  expect(() => growth().decide(view("2025-03-03", []), portfolioOf(0n), memory)).toThrow(
    new Error("dividend-growth's memory names JKT:AALI, not a stock of IDX"),
  );
});

test("a memory with a year but no set is refused", () => {
  const memory: Memory = new Map([["year", "2025"]]);
  expect(() => growth().decide(view("2025-03-03", []), portfolioOf(0n), memory)).toThrow(
    new Error("dividend-growth's memory has a year but no set"),
  );
});

// A dividend figure crossing a corporate action found by price with no known ratio (spec §6.4,
// §6.6, #480): the dividends before the action cannot be restated in today's shares, so the stock
// is missing until a corporate action read gives the ratio.

/** BBCA and BBRI both pass; `actions` gives the stocks' unknown actions. */
const acted = (
  actions: Readonly<Record<string, Day>>,
  covered: Covered | null = { from: "2015-01-01", to: REVIEW },
) =>
  growth().decide(
    view(REVIEW, ["BBCA", "BBRI"], [...paid("BBCA"), ...paid("BBRI")], {
      covered: { BBCA: covered },
      actions,
    }),
    portfolioOf(1_000_000n),
    NONE,
  );

test("missing: an unknown action inside the dividend window lists the corporate action page", () => {
  const decision = acted({ BBCA: "2023-06-19" });
  expect(decision.missing).toEqual([missingPage("corporate-actions", "BBCA")]);
  expect(decision.missing[0]?.text).toBe("open the corporate action page for BBCA");
  expect(decision.weights.size).toBe(0);
});

test("missing: an unknown action on the window's first trading day", () => {
  // The window opens on 1 January 2022; 3 January is its first trading day.
  expect(acted({ BBCA: "2022-01-03" }).missing).toEqual([missingPage("corporate-actions", "BBCA")]);
});

test("missing: an unknown action on the advice day", () => {
  expect(acted({ BBCA: REVIEW }).missing).toEqual([missingPage("corporate-actions", "BBCA")]);
});

test("judged: an unknown action before the dividend window does not cross it", () => {
  const decision = acted({ BBCA: "2021-12-30" });
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", BBRI: "0.5" });
});

test("judged: a known split on the action's day settles it", () => {
  // 9,000 to 3,000 is beyond any band, but a 1-for-3 split read for that day explains it.
  const at = (day: Day, amount: bigint): DailyClose => ({ day, close: rp(amount) });
  const recorded = [at("2023-06-16", 9_000n), at("2023-06-19", 3_000n)];
  const split: Split = { symbol: "BBCA", exDate: "2023-06-19", from: 1n, to: 3n };
  const rules = new IdxMarketRules();
  const calendar = IdxCalendar.shipped();
  expect(lastUnknownAction("BBCA", recorded, [], [], rules, calendar)).toBe("2023-06-19");
  const found = lastUnknownAction("BBCA", recorded, [split], [], rules, calendar);
  expect(found).toBeUndefined();
  const decision = acted(found === undefined ? {} : { BBCA: found });
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", BBRI: "0.5" });
});

test("judged: a corporate action read covering a false alarm settles it (#480 AC5)", () => {
  // 9,000 to 3,000 is beyond any band, but the corporate action page read for June 2023 lists no
  // split of BBCA, so its shares did not change and its dividends need no restating.
  const at = (day: Day, amount: bigint): DailyClose => ({ day, close: rp(amount) });
  const recorded = [at("2023-06-16", 9_000n), at("2023-06-19", 3_000n)];
  const read = { from: "2023-06-01", to: "2023-06-30" };
  const rules = new IdxMarketRules();
  const calendar = IdxCalendar.shipped();
  const found = lastUnknownAction("BBCA", recorded, [], [read], rules, calendar);
  expect(found).toBeUndefined();
  const decision = acted(found === undefined ? {} : { BBCA: found });
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", BBRI: "0.5" });
});

test("missing: a stock with no dividend read and an unknown action lists both pages", () => {
  expect(acted({ BBCA: "2023-06-19" }, null).missing).toEqual([
    missingPage("dividends", "BBCA"),
    missingPage("corporate-actions", "BBCA"),
  ]);
});

test("a stock it need not judge is not missing for an unknown action", () => {
  // UNVR is a member it can neither buy nor sell.
  const decision = growth().decide(
    view(REVIEW, ["BBCA"], paid("BBCA"), { members: ["UNVR"], actions: { UNVR: "2023-06-19" } }),
    portfolioOf(0n),
    NONE,
  );
  expect(decision.missing).toEqual([]);
});
