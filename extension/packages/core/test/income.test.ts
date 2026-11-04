import { expect, test } from "vitest";
import type { Dividend, Dividends, Split } from "../src/broker-view.ts";
import { goalProgress, paymentCalendar, runRate, type IncomeInputs } from "../src/income.ts";
import { IDR, Money } from "../src/money.ts";
import { missingPage } from "../src/notes.ts";
import { RuleDecimal } from "../src/ratio.ts";
import { IdxMarketRules } from "../src/rules.ts";

// EXT S13 (#237, spec §9): the holdings' run rate after the 10% final dividend tax, the goal
// against it, and the payment calendar, as Python's `run_rate`, `goal_progress` and
// `payment_calendar` give them. The window is the 365 days up to the day, both ends included:
// 2024-06-18 to 2025-06-17.

const RULES = new IdxMarketRules();
const DAY = "2025-06-17";

const rp = (amount: bigint): Money => new Money(amount, IDR);

const dividend = (
  symbol: string,
  exDate: string,
  paymentDate: string,
  perShare: string,
): Dividend => ({ symbol, exDate, paymentDate, grossPerShare: new RuleDecimal(perShare) });

const read = (symbol: string, rows: readonly Dividend[], from = "2024-01-01"): Dividends => ({
  symbol,
  covered: { from, to: DAY },
  dividends: rows,
});

const BBRI = read("BBRI", [
  dividend("BBRI", "2024-03-20", "2024-04-10", "200"),
  dividend("BBRI", "2024-12-20", "2025-01-15", "135"),
  dividend("BBRI", "2025-03-25", "2025-04-15", "208.4"),
]);
const TLKM = read("TLKM", [dividend("TLKM", "2025-05-30", "2025-06-27", "250")]);

const inputs = (over: Partial<IncomeInputs> = {}): IncomeInputs => ({
  rules: RULES,
  held: new Map([
    ["BBRI", 1_000n],
    ["TLKM", 500n],
  ]),
  dividends: new Map([
    ["BBRI", BBRI],
    ["TLKM", TLKM],
  ]),
  splits: [],
  unknownActions: new Map(),
  asOf: DAY,
  ...over,
});

const rated = (over: Partial<IncomeInputs> = {}) => {
  const found = runRate(inputs(over));
  if (found.rate === null) {
    throw new Error(`no run rate: ${JSON.stringify(found.missing)}`);
  }
  return found.rate;
};

test("each holding's window dividends times its shares, less the 10% tax, by the month", () => {
  // BBRI: 135 + 208.4 a share on 1,000 shares is 343,400; the tax rounded up is 34,340, which
  // leaves 309,060, or 25,755 a month. TLKM: 250 on 500 is 125,000, 112,500 after tax, 9,375 a
  // month. The March 2024 dividend is before the window.
  const rate = rated();
  expect(
    rate.holdings.map((holding) => [
      holding.symbol,
      holding.shares,
      holding.annualGross.amount,
      holding.monthlyTakeHome.amount,
    ]),
  ).toEqual([
    ["BBRI", 1_000n, 343_400n, 25_755n],
    ["TLKM", 500n, 125_000n, 9_375n],
  ]);
  expect([rate.asOf, rate.annualGross.amount, rate.monthlyTakeHome.amount]).toEqual([
    DAY,
    468_400n,
    35_130n,
  ]);
});

test("each holding lists the dividends it counts, with their gross on the shares held", () => {
  expect(rated().holdings[0]?.dividends).toEqual([
    { exDate: "2024-12-20", paymentDate: "2025-01-15", gross: rp(135_000n) },
    { exDate: "2025-03-25", paymentDate: "2025-04-15", gross: rp(208_400n) },
  ]);
});

test("the portfolio's monthly figure is worked from its own annual gross, rounded down", () => {
  // 1 share of each at 7 a share: 7 a year each, 6 after the tax rounded up to 1, so 0 a month
  // each; together 14 less 2 is 12, so 1 a month.
  const tiny = read("BBRI", [dividend("BBRI", "2025-01-02", "2025-01-20", "7")]);
  const tinier = read("TLKM", [dividend("TLKM", "2025-01-02", "2025-01-20", "7")]);
  const rate = rated({
    held: new Map([
      ["BBRI", 1n],
      ["TLKM", 1n],
    ]),
    dividends: new Map([
      ["BBRI", tiny],
      ["TLKM", tinier],
    ]),
  });
  expect(rate.holdings.map((holding) => holding.monthlyTakeHome.amount)).toEqual([0n, 0n]);
  expect(rate.monthlyTakeHome.amount).toBe(1n);
});

test("a dividend on both ends of the window counts", () => {
  const ends = read("BBRI", [
    dividend("BBRI", "2024-06-18", "2024-07-10", "10"),
    dividend("BBRI", "2025-06-17", "2025-07-10", "20"),
    dividend("BBRI", "2024-06-17", "2024-07-09", "1000"),
  ]);
  const rate = rated({ held: new Map([["BBRI", 1n]]), dividends: new Map([["BBRI", ends]]) });
  expect(rate.annualGross.amount).toBe(30n);
});

test("a dividend announced after the day is not counted", () => {
  const later = read("BBRI", [dividend("BBRI", "2025-06-18", "2025-07-10", "10")]);
  const rate = rated({ held: new Map([["BBRI", 1n]]), dividends: new Map([["BBRI", later]]) });
  expect(rate.annualGross.amount).toBe(0n);
});

test("dividends are restated in today's shares: a 1-to-5 split after the ex-date", () => {
  const split: Split = { symbol: "BBRI", exDate: "2025-01-10", from: 1n, to: 5n };
  const rate = rated({
    held: new Map([["BBRI", 1_000n]]),
    dividends: new Map([["BBRI", read("BBRI", [BBRI.dividends[1] as Dividend])]]),
    splits: [split],
  });
  expect(rate.annualGross.amount).toBe(27_000n);
});

test("a dividend that rounds to nothing on the shares held is left out", () => {
  const small = read("BBRI", [dividend("BBRI", "2025-01-02", "2025-01-20", "0.4")]);
  const rate = rated({ held: new Map([["BBRI", 1n]]), dividends: new Map([["BBRI", small]]) });
  expect(rate.holdings[0]?.dividends).toEqual([]);
});

test("holdings are listed by symbol, whatever order they are held in", () => {
  const rate = rated({
    held: new Map([
      ["TLKM", 500n],
      ["BBRI", 1_000n],
    ]),
  });
  expect(rate.holdings.map((holding) => holding.symbol)).toEqual(["BBRI", "TLKM"]);
});

test("no holdings: a run rate of nothing", () => {
  const rate = rated({ held: new Map(), dividends: new Map() });
  expect([rate.holdings, rate.annualGross.amount, rate.monthlyTakeHome.amount]).toEqual([
    [],
    0n,
    0n,
  ]);
});

test("a holding with no dividend read is missing, and there is no run rate", () => {
  expect(runRate(inputs({ dividends: new Map([["BBRI", BBRI]]) }))).toEqual({
    rate: null,
    missing: [missingPage("dividends", "TLKM")],
  });
});

test("a read that starts after the window's first day is missing", () => {
  const short = read("TLKM", TLKM.dividends, "2024-06-19");
  expect(
    runRate(
      inputs({
        dividends: new Map([
          ["BBRI", BBRI],
          ["TLKM", short],
        ]),
      }),
    ),
  ).toEqual({
    rate: null,
    missing: [missingPage("dividends", "TLKM")],
  });
});

test("a read that starts on the window's first day covers it", () => {
  const exact = read("TLKM", TLKM.dividends, "2024-06-18");
  expect(
    runRate(
      inputs({
        dividends: new Map([
          ["BBRI", BBRI],
          ["TLKM", exact],
        ]),
      }),
    ).missing,
  ).toEqual([]);
});

test("a read that ends before the day is missing", () => {
  const stale = { ...TLKM, covered: { from: "2024-01-01", to: "2025-06-16" } };
  expect(
    runRate(
      inputs({
        dividends: new Map([
          ["BBRI", BBRI],
          ["TLKM", stale],
        ]),
      }),
    ),
  ).toEqual({
    rate: null,
    missing: [missingPage("dividends", "TLKM")],
  });
});

test("a corporate action found by price inside the window is missing its ratio", () => {
  expect(runRate(inputs({ unknownActions: new Map([["BBRI", "2025-02-03"]]) }))).toEqual({
    rate: null,
    missing: [missingPage("corporate-actions", "BBRI")],
  });
});

test("one found on the window's first day or before it does not cross the window", () => {
  expect(runRate(inputs({ unknownActions: new Map([["BBRI", "2024-06-18"]]) })).missing).toEqual(
    [],
  );
});

test("every holding missing anything is listed, in symbol order", () => {
  expect(
    runRate(inputs({ dividends: new Map(), unknownActions: new Map([["TLKM", "2025-01-02"]]) }))
      .missing,
  ).toEqual([
    missingPage("dividends", "BBRI"),
    missingPage("dividends", "TLKM"),
    missingPage("corporate-actions", "TLKM"),
  ]);
});

test("the goal: the run rate's monthly take-home over the target, to eight places", () => {
  const goal = goalProgress(rp(1_000_000n), rated());
  expect([goal.target, goal.runRate, goal.runRateShare.toString()]).toEqual([
    rp(1_000_000n),
    rp(35_130n),
    "0.03513",
  ]);
});

test("a run rate past the target is a share above 1, not capped", () => {
  expect(goalProgress(rp(10_000n), rated()).runRateShare.toString()).toBe("3.513");
});

test.each([0n, -1n])("a target of %s is refused", (target) => {
  expect(() => goalProgress(rp(target), rated())).toThrow(
    `an income goal must be positive, got IDR ${target.toString()}`,
  );
});

test("the payment calendar: each dividend's take-home in its payment month", () => {
  // January 135,000 less 13,500; April 208,400 less 20,840; June 125,000 less 12,500.
  const months = paymentCalendar(rated(), RULES);
  expect(months.months.map((month) => month.amount)).toEqual([
    121_500n,
    0n,
    0n,
    187_560n,
    0n,
    112_500n,
    0n,
    0n,
    0n,
    0n,
    0n,
    0n,
  ]);
  expect(months.holdings.map((holding) => [holding.symbol, holding.months[3]?.amount])).toEqual([
    ["BBRI", 187_560n],
    ["TLKM", 0n],
  ]);
  expect([months.emptyMonths, months.evenness?.toString()]).toEqual([9n, "0.44491887"]);
});

test("a calendar of nothing has twelve empty months and no evenness", () => {
  const months = paymentCalendar(rated({ held: new Map(), dividends: new Map() }), RULES);
  expect([months.emptyMonths, months.evenness]).toEqual([12n, null]);
});
