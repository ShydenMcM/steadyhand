import { expect, test } from "vitest";
import type { Covered, Day, Dividend, Dividends, Split } from "../src/broker-view.ts";
import { HIGH_YIELD, highYield } from "../src/high-yield.ts";
import { IDR, Money } from "../src/money.ts";
import { missingPage, note, NOTE_CODES } from "../src/notes.ts";
import { ratioDown, RuleDecimal } from "../src/ratio.ts";
import type { PortfolioView } from "../src/sizing.ts";
import type { MarketView, Memory } from "../src/strategy.ts";

// Hand-computed examples, one test per case, written from spec §7.2 before the code: there is no
// Python reference for high-yield (#233 AC1).
//
// Most tests review on 2 January 2025 with `paid_years` 3, so a stock passes when it paid a cash
// dividend, by ex-date, in 2022, 2023 and 2024. Its yield is its dividends with an ex-date from
// 4 January 2024 to 2 January 2025 (the 365 days up to the advice day) over its close.

const STOCKS = ["ASII", "BBCA", "BBRI", "TLKM", "UNVR"] as const;
const REVIEW = "2025-01-02";

const rp = (amount: bigint): Money => new Money(amount, IDR);

const dividend = (symbol: string, exDate: Day, gross: string): Dividend => ({
  symbol,
  exDate,
  paymentDate: exDate,
  grossPerShare: new RuleDecimal(gross),
});

/** One dividend a year in 2022, 2023 and 2024, each on 4 March of its year, of `amounts`. */
const paid = (
  symbol: string,
  amounts: readonly [string, string, string] = ["100", "100", "100"],
): Dividend[] => {
  const [first, second, third] = amounts;
  return [
    dividend(symbol, "2022-03-04", first),
    dividend(symbol, "2023-03-04", second),
    dividend(symbol, "2024-03-04", third),
  ];
};

/** `paid`'s 2022 and 2023 dividends, and its 2024 one on `exDate` instead, of `gross`. */
const lastPaidOn = (symbol: string, exDate: Day, gross: string): Dividend[] => [
  ...paid(symbol).slice(0, 2),
  dividend(symbol, exDate, gross),
];

interface ViewOptions {
  /** The universe, beyond the buyable stocks. */
  readonly members?: readonly string[];
  /** Each stock's close on the advice day; unlisted stocks close at 1,000. */
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
      STOCKS.map((symbol) => [symbol, rp(options.closes?.[symbol] ?? 1000n)] as const),
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

/** The weights as text, by symbol, for an exact comparison. */
const weighed = (weights: ReadonlyMap<string, { toString: () => string }>) =>
  Object.fromEntries([...weights].map(([symbol, weight]) => [symbol, weight.toString()]));

const NONE: Memory = new Map();
const CASH = portfolioOf(1_000_000n);

/** The stocks a review on `REVIEW` picks with `yield_stocks` `yieldStocks`. */
const picked = (
  yieldStocks: bigint,
  buyable: readonly string[],
  dividends: readonly Dividend[],
  options: ViewOptions = {},
  paidYears: bigint = HIGH_YIELD.paidYears,
): Record<string, string> =>
  weighed(
    highYield(yieldStocks, paidYears).decide(view(REVIEW, buyable, dividends, options), CASH, NONE)
      .weights,
  );

test("it is a strategy named high-yield with its settings, by default 10 and 3", () => {
  const strategy = highYield();
  expect(strategy.name).toBe("high-yield");
  expect([strategy.yieldStocks, strategy.paidYears]).toEqual([10n, 3n]);
  expect(HIGH_YIELD).toEqual({ yieldStocks: 10n, paidYears: 3n });
});

test.each([
  ["yield_stocks must be at least 1, got 0", 0n, 3n],
  ["paid_years must be at least 1, got 0", 10n, 0n],
  ["yield_stocks must be at least 1, got -1", -1n, 3n],
] as const)("its settings are refused by name: %s", (message, yieldStocks, paidYears) => {
  expect(() => highYield(yieldStocks, paidYears)).toThrow(new RangeError(message));
});

test("settings of 1 are allowed", () => {
  expect([highYield(1n, 1n).yieldStocks, highYield(1n, 1n).paidYears]).toEqual([1n, 1n]);
});

// The dividend test (AC2): BBCA alone is judged, with yield_stocks 1, so it is picked with a
// weight of 1 when it passes and not at all when it fails.

test("passes: a cash dividend in each of the 3 years before this one", () => {
  expect(picked(1n, ["BBCA"], paid("BBCA"))).toEqual({ BBCA: "1" });
});

test("passes: falling dividends still pass, since only paying counts", () => {
  expect(picked(1n, ["BBCA"], paid("BBCA", ["300", "200", "100"]))).toEqual({ BBCA: "1" });
});

test("fails: a year with no dividend", () => {
  const without2023 = paid("BBCA").filter((paidOut) => !paidOut.exDate.startsWith("2023"));
  expect(picked(1n, ["BBCA"], without2023)).toEqual({});
});

test("fails: the first year missing, though the year before it paid", () => {
  const dividends = [dividend("BBCA", "2021-03-04", "100"), ...paid("BBCA").slice(1)];
  expect(picked(1n, ["BBCA"], dividends)).toEqual({});
});

test("fails: last year missing, though this year paid by the advice day", () => {
  const dividends = [...paid("BBCA").slice(0, 2), dividend("BBCA", REVIEW, "100")];
  expect(picked(1n, ["BBCA"], dividends)).toEqual({});
});

test("fails: no dividend at all", () => {
  expect(picked(1n, ["BBCA"], [])).toEqual({});
});

test("paid_years 1 asks only for last year's dividend", () => {
  const only2024 = paid("BBCA").slice(2);
  expect(picked(1n, ["BBCA"], only2024, {}, 1n)).toEqual({ BBCA: "1" });
  expect(picked(1n, ["BBCA"], only2024)).toEqual({});
});

// The yield (AC2) and the pick (AC3): the highest yields win, at 1/yield_stocks each.

test("the highest yields are picked: TLKM 100/500 and BBCA 100/1,000 over BBRI 100/2,000", () => {
  const dividends = [...paid("BBCA"), ...paid("BBRI"), ...paid("TLKM")];
  const closes = { BBCA: 1000n, BBRI: 2000n, TLKM: 500n };
  expect(picked(2n, ["BBCA", "BBRI", "TLKM"], dividends, { closes })).toEqual({
    BBCA: "0.5",
    TLKM: "0.5",
  });
});

test("several dividends in the trailing year add up: BBRI (100 + 150)/2,000 over BBCA 100/1,000", () => {
  const dividends = [...paid("BBCA"), ...paid("BBRI"), dividend("BBRI", "2024-09-02", "150")];
  const closes = { BBCA: 1000n, BBRI: 2000n };
  expect(picked(1n, ["BBCA", "BBRI"], dividends, { closes })).toEqual({ BBRI: "1" });
});

test("a dividend 366 days before the advice day is outside the yield: BBCA 100 beats BBRI 0", () => {
  const dividends = [...paid("BBCA"), ...lastPaidOn("BBRI", "2024-01-03", "300")];
  expect(picked(1n, ["BBCA", "BBRI"], dividends)).toEqual({ BBCA: "1" });
});

test("a dividend 365 days before the advice day is inside the yield: BBRI 300 beats BBCA 100", () => {
  const dividends = [...paid("BBCA"), ...lastPaidOn("BBRI", "2024-01-04", "300")];
  expect(picked(1n, ["BBCA", "BBRI"], dividends)).toEqual({ BBRI: "1" });
});

test("a dividend with its ex-date on the advice day counts toward the yield", () => {
  const dividends = [...paid("BBCA"), ...paid("BBRI"), dividend("BBRI", REVIEW, "1")];
  expect(picked(1n, ["BBCA", "BBRI"], dividends)).toEqual({ BBRI: "1" });
});

test("a dividend announced for after the advice day does not count toward the yield", () => {
  const dividends = [...paid("BBCA", ["100", "100", "101"]), ...paid("BBRI")];
  const announced = dividend("BBRI", "2025-01-03", "500");
  expect(picked(1n, ["BBCA", "BBRI"], [...dividends, announced])).toEqual({ BBCA: "1" });
});

test("a dividend is restated in today's shares: BBRI 300 before a 1:4 split is 75, below BBCA 100", () => {
  const dividends = [...paid("BBCA"), ...paid("BBRI", ["100", "100", "300"])];
  const splits: Split[] = [{ symbol: "BBRI", exDate: "2024-06-03", from: 1n, to: 4n }];
  expect(picked(1n, ["BBCA", "BBRI"], dividends, { splits })).toEqual({ BBCA: "1" });
  expect(picked(1n, ["BBCA", "BBRI"], dividends)).toEqual({ BBRI: "1" });
});

test("equal yields are broken by symbol: BBCA before BBRI", () => {
  const dividends = [...paid("BBRI"), ...paid("BBCA")];
  expect(picked(1n, ["BBRI", "BBCA"], dividends)).toEqual({ BBCA: "1" });
});

test("a review sells everything else and says why for each stock", () => {
  const dividends = [...paid("BBCA"), ...paid("BBRI"), ...paid("TLKM")];
  const closes = { BBCA: 1000n, BBRI: 2000n, TLKM: 500n };
  const buyable = ["ASII", "BBCA", "BBRI", "TLKM"];
  const held = portfolioOf(100_000n, { ASII: 50_000n, BBRI: 50_000n, UNVR: 50_000n });
  const decision = highYield(2n).decide(view(REVIEW, buyable, dividends, { closes }), held, NONE);
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.5", TLKM: "0.5" });
  expect(Object.fromEntries(decision.reasons)).toEqual({
    ASII: "high-yield: no longer paid a dividend in each of the last 3 years",
    BBCA: "high-yield: among the 2 highest dividend yields",
    BBRI: "high-yield: not among the 2 highest dividend yields",
    TLKM: "high-yield: among the 2 highest dividend yields",
    UNVR: "high-yield: no longer paid a dividend in each of the last 3 years",
  });
  expect(decision.missing).toEqual([]);
  expect(decision.notes).toEqual([]);
});

test("a review remembers its picks and its quarter", () => {
  const dividends = [...paid("BBCA"), ...paid("TLKM")];
  const decision = highYield(2n).decide(view(REVIEW, ["BBCA", "TLKM"], dividends), CASH, NONE);
  expect(Object.fromEntries(decision.memory)).toEqual({
    set: "IDX:BBCA IDX:TLKM",
    quarter: "2025-1",
  });
});

// Too few passers (AC3): each still gets 1/yield_stocks, and the rest stays cash.

test.each([
  [
    "two passers of three",
    ["BBCA", "TLKM"],
    "Only 2 stocks paid a dividend in each of the last 3 years; the rest is held as cash until more do.",
  ],
  [
    "one passer of three",
    ["BBCA"],
    "Only 1 stock paid a dividend in each of the last 3 years; the rest is held as cash until more do.",
  ],
] as const)("too few passers, %s: 1/3 each and a note", (_case, passers, text) => {
  const dividends = passers.flatMap((symbol) => paid(symbol));
  const decision = highYield(3n).decide(
    view(REVIEW, ["BBCA", "BBRI", "TLKM"], dividends),
    CASH,
    NONE,
  );
  const third = ratioDown(1n, 3n).toString();
  expect(weighed(decision.weights)).toEqual(
    Object.fromEntries(passers.map((symbol) => [symbol, third])),
  );
  expect(decision.notes).toEqual([note(NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED, text)]);
});

test("no passer at all: everything is cash, with a note", () => {
  const decision = highYield().decide(view(REVIEW, ["BBCA"], []), CASH, NONE);
  expect(decision.weights).toEqual(new Map());
  expect(decision.notes).toEqual([
    note(
      NOTE_CODES.STRATEGY_TOO_FEW_QUALIFIED,
      "No stock paid a dividend in each of the last 3 years; everything is held as cash until one does.",
    ),
  ]);
});

test("exactly yield_stocks passers leave no note", () => {
  const dividends = [...paid("BBCA"), ...paid("TLKM")];
  const decision = highYield(2n).decide(view(REVIEW, ["BBCA", "TLKM"], dividends), CASH, NONE);
  expect(decision.notes).toEqual([]);
});

// Reviews (AC5): the first advice day of each quarter, and its first advice day.

/** UNVR's dividends from 2022 to 2025, so it passes on any day of 2025 and 2026. */
const EVERY_YEAR = [...paid("UNVR"), dividend("UNVR", "2025-03-04", "100")];

const remembered = (quarter: string): Memory =>
  new Map([
    ["set", "IDX:BBCA IDX:TLKM"],
    ["quarter", quarter],
  ]);

test.each([
  ["its first advice day, in the middle of a quarter", "2025-02-03", NONE, "2025-1"],
  ["the first advice day of April", "2025-04-08", remembered("2025-1"), "2025-2"],
  ["the first advice day of July", "2025-07-01", remembered("2025-2"), "2025-3"],
  ["the first advice day of October", "2025-10-01", remembered("2025-3"), "2025-4"],
  ["the first advice day of January", "2026-01-02", remembered("2025-4"), "2026-1"],
  ["the same quarter of the next year", "2026-02-02", remembered("2025-1"), "2026-1"],
] as const)("reviews on %s", (_case, day, memory, quarter) => {
  const decision = highYield(1n).decide(view(day, ["UNVR"], EVERY_YEAR), CASH, memory);
  expect(Object.fromEntries(decision.memory)).toEqual({ set: "IDX:UNVR", quarter });
});

test.each([
  ["a later day of the same quarter", "2025-03-31", "2025-1"],
  ["the last day of the year, in its fourth quarter", "2025-12-31", "2025-4"],
] as const)("does not review on %s", (_case, day, quarter) => {
  const memory = remembered(quarter);
  const decision = highYield(1n).decide(view(day, ["UNVR"], EVERY_YEAR), CASH, memory);
  expect(decision.memory).toBe(memory);
});

// Between reviews (AC4): holdings are kept and new cash goes to the picks, up to 1/yield_stocks.

test("between reviews it keeps its holdings and tops its picks up to 1/yield_stocks", () => {
  // Worth 1,000: 400 cash, BBCA 450, ASII 150. Each pick may take 400 / 2 = 200 (0.2): BBCA has
  // room for 0.05 to reach 0.5, TLKM takes all 0.2. ASII is no pick and is kept.
  const held = portfolioOf(400n, { ASII: 150n, BBCA: 450n });
  const decision = highYield(2n).decide(
    view("2025-02-03", ["BBCA", "TLKM"]),
    held,
    remembered("2025-1"),
  );
  expect(weighed(decision.weights)).toEqual({ ASII: "0.15", BBCA: "0.5", TLKM: "0.2" });
  expect(Object.fromEntries(decision.reasons)).toEqual({
    ASII: "high-yield: held until the next review",
    BBCA: "high-yield: picked at the last review, topped up to its share",
    TLKM: "high-yield: picked at the last review, topped up to its share",
  });
  expect(decision.notes).toEqual([]);
});

test("between reviews a pick it cannot buy gets no cash; the rest goes to the others", () => {
  // TLKM cannot be bought, so BBCA may take all 400 (0.4), of which it has room for 0.05.
  const held = portfolioOf(400n, { ASII: 150n, BBCA: 450n });
  const decision = highYield(2n).decide(view("2025-02-03", ["BBCA"]), held, remembered("2025-1"));
  expect(weighed(decision.weights)).toEqual({ ASII: "0.15", BBCA: "0.5" });
});

test("between reviews no pick it can buy leaves the holdings as they are", () => {
  const held = portfolioOf(400n, { BBCA: 600n });
  const decision = highYield(2n).decide(view("2025-02-03", []), held, remembered("2025-1"));
  expect(weighed(decision.weights)).toEqual({ BBCA: "0.6" });
});

test("between reviews no dividend read is needed", () => {
  const covered = Object.fromEntries(STOCKS.map((symbol) => [symbol, null]));
  const decision = highYield(2n).decide(
    view("2025-02-03", ["BBCA", "TLKM"], [], { covered }),
    CASH,
    remembered("2025-1"),
  );
  expect(decision.missing).toEqual([]);
});

test("a memory with a quarter but no set is refused", () => {
  const memory = new Map([["quarter", "2025-1"]]);
  expect(() => highYield().decide(view("2025-02-03", []), CASH, memory)).toThrow(
    new Error("high-yield's memory has a quarter but no set"),
  );
});

// Missing versus ineligible (AC6, spec §7.1, §6.6): each stock a review judges needs a dividend
// read from 1 January of 2022 (3 calendar years before this one) to the advice day.

const reviewed = (options: ViewOptions, held: PortfolioView = CASH, buyable = ["BBCA"]) =>
  highYield(1n).decide(view(REVIEW, buyable, paid("BBCA"), options), held, remembered("2024-4"));

test("missing: no dividend read lists the dividend page, orders nothing and keeps the memory", () => {
  const decision = reviewed({ covered: { BBCA: null } });
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
  expect(decision.weights).toEqual(new Map());
  expect(decision.reasons).toEqual(new Map());
  expect(decision.notes).toEqual([]);
  expect(decision.memory).toEqual(remembered("2024-4"));
});

test("missing: a read starting the day after 1 January of the first year", () => {
  const decision = reviewed({ covered: { BBCA: { from: "2022-01-02", to: REVIEW } } });
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
});

test("judged: a read starting on 1 January of the first year", () => {
  const decision = reviewed({ covered: { BBCA: { from: "2022-01-01", to: REVIEW } } });
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});

test("missing: a read ending the day before the advice day", () => {
  const decision = reviewed({ covered: { BBCA: { from: "2015-01-01", to: "2025-01-01" } } });
  expect(decision.missing).toEqual([missingPage("dividends", "BBCA")]);
});

test("missing: an unknown corporate action after the window's first day lists its page", () => {
  const decision = reviewed({ actions: { BBCA: "2022-01-03" } });
  expect(decision.missing).toEqual([missingPage("corporate-actions", "BBCA")]);
  expect(decision.weights).toEqual(new Map());
});

test("judged: an unknown corporate action on the window's first day does not cross it", () => {
  const decision = reviewed({ actions: { BBCA: "2022-01-01" } });
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});

test("missing: no read and an unknown action list both pages", () => {
  const decision = reviewed({ covered: { BBCA: null }, actions: { BBCA: "2024-05-02" } });
  expect(decision.missing).toEqual([
    missingPage("dividends", "BBCA"),
    missingPage("corporate-actions", "BBCA"),
  ]);
});

test("missing: a held member it cannot buy is still judged", () => {
  const held = portfolioOf(100n, { ASII: 100n });
  const decision = reviewed({ members: ["ASII"], covered: { ASII: null } }, held);
  expect(decision.missing).toEqual([missingPage("dividends", "ASII")]);
});

test("not missing: a member it can neither buy nor holds is not judged", () => {
  const decision = reviewed({ members: ["ASII"], covered: { ASII: null } });
  expect(decision.missing).toEqual([]);
});

test("not missing: a holding outside the universe is not judged, and is sold", () => {
  const held = portfolioOf(100n, { ASII: 100n });
  const decision = reviewed({ covered: { ASII: null } }, held);
  expect(decision.missing).toEqual([]);
  expect(weighed(decision.weights)).toEqual({ BBCA: "1" });
});
