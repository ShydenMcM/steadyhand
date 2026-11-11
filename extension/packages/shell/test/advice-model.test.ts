import {
  adviceDayAt,
  buyAndHold,
  buyStops,
  IDR,
  IdxCalendar,
  IdxMarketRules,
  incomeGrowth,
  missingPage,
  Money,
  NOTE_CODES,
  portfolioView,
  project,
  RiskLimits,
  riskState,
  runRate,
  RuleDecimal,
  shippedSessions,
  type Dividends,
  type Flags,
  type MarketView,
  type Memory,
  type Part,
  type Portfolio,
  type PortfolioView,
  type RiskRecord,
  type Source,
  type Strategy,
  type StrategyDecision,
  type Watchlist,
} from "@steadyhand/core";
import { expect, test } from "vitest";
import { adviceModel, type PanelReads, type Recorded } from "../src/advice-model.ts";

// The panel's advice (#238 AC3): the portfolio and watchlist reads, the flags read and the
// record turned into the day's orders, goal progress, warnings and the missing list. The week of
// Monday 16 June 2025 has no IDX holiday; 19:00 WIB is after the close.

const CALENDAR = IdxCalendar.shipped();
const SESSIONS = shippedSessions();
const RULES = new IdxMarketRules();
const LIMITS = new RiskLimits();
const rp = (amount: bigint): Money => new Money(amount, IDR);
const wib = (time: string): Date => new Date(`${time}+07:00`);
const AFTER_CLOSE = wib("2025-06-17T19:00:00");
const IN_SESSION = wib("2025-06-17T10:00:00");
const source = (pageKind: Source["pageKind"]): Source => ({
  broker: "fixture",
  pageKind,
  route: "page",
});

const portfolioAt = (readAt: Date): Part<Portfolio> => ({
  source: source("portfolio"),
  readAt,
  value: {
    cashAvailable: rp(10_000_000n),
    cashSettled: rp(10_000_000n),
    cashUnsettled: rp(0n),
    holdings: [{ symbol: "TLKM", lots: 10n, averagePrice: rp(2600n), lastPrice: rp(2750n) }],
  },
});

const watchlistAt = (readAt: Date): Part<Watchlist> => ({
  source: source("watchlist"),
  readAt,
  value: {
    stocks: [
      { symbol: "BBCA", lastPrice: rp(9100n) },
      { symbol: "TLKM", lastPrice: rp(2750n) },
    ],
  },
});

const flagsAt = (readAt: Date, flags: Flags["flags"] = []): Part<Flags> => ({
  source: source("flags"),
  readAt,
  value: { flags },
});

const UNFLAGGED: PanelReads = {
  portfolio: portfolioAt(AFTER_CLOSE),
  watchlist: watchlistAt(AFTER_CLOSE),
};

const FRESH: PanelReads = { ...UNFLAGGED, flags: flagsAt(AFTER_CLOSE) };

const NO_RISK: RiskRecord = {
  valuations: [],
  movements: [],
  movementReads: [],
  typed: [],
  answered: [],
  resumes: [],
};

const RECORDED: Recorded = {
  closes: new Map(),
  dividends: new Map(),
  splits: [],
  actionReads: [],
  risk: NO_RISK,
  stored: undefined,
  universe: ["BBCA", "TLKM"],
  excluded: new Map(),
  goal: undefined,
  contribution: rp(0n),
};

interface Seen {
  view?: MarketView;
  portfolio?: PortfolioView;
  memory?: Memory;
}

/** A strategy that puts a tenth in BBCA and nothing in TLKM, and keeps what it was given. */
const standIn = (seen: Seen = {}): Strategy => ({
  name: "stand-in",
  decide: (view, portfolio, memory): StrategyDecision => {
    seen.view = view;
    seen.portfolio = portfolio;
    seen.memory = memory;
    return {
      weights: new Map([["BBCA", new RuleDecimal("0.10")]]),
      reasons: new Map([
        ["BBCA", "BBCA passed the stand-in's test"],
        ["TLKM", "TLKM failed the stand-in's test"],
      ]),
      missing: [],
      memory: new Map([["set", "IDX:BBCA"]]),
      notes: [],
    };
  },
});

const model = (reads: PanelReads, recorded: Partial<Recorded> = {}, strategy = standIn()) =>
  adviceModel({
    reads,
    recorded: { ...RECORDED, ...recorded },
    strategy,
    rules: RULES,
    limits: LIMITS,
    calendar: CALENDAR,
    sessions: SESSIONS,
    now: AFTER_CLOSE,
  });

const sides = (advice: ReturnType<typeof model>) =>
  advice.state === "advice"
    ? advice.orders.map((line) => `${line.order.side} ${line.order.symbol}`)
    : [];

test("with nothing read, the panel asks for the portfolio and the watchlist", () => {
  expect(model({})).toEqual({
    state: "read again",
    reason: "not read",
    missing: [missingPage("portfolio"), missingPage("watchlist")],
    nextClose: adviceDayAt(AFTER_CLOSE, CALENDAR, SESSIONS).nextClose,
  });
});

test("reads made during a session ask for both again and give the next close", () => {
  const advice = adviceModel({
    reads: { ...FRESH, portfolio: portfolioAt(IN_SESSION), watchlist: watchlistAt(IN_SESSION) },
    recorded: RECORDED,
    strategy: standIn(),
    rules: RULES,
    limits: LIMITS,
    calendar: CALENDAR,
    sessions: SESSIONS,
    now: IN_SESSION,
  });
  expect(advice).toEqual({
    state: "read again",
    reason: "read during a trading session",
    missing: [missingPage("portfolio"), missingPage("watchlist")],
    nextClose: adviceDayAt(IN_SESSION, CALENDAR, SESSIONS).nextClose,
  });
});

test("with no universe listed in Settings, no advice is given: nothing is sold for it", () => {
  expect(model(FRESH, { universe: undefined })).toEqual({ state: "no universe" });
});

test("fresh reads give the day's orders: each side, stock, lots, limit price, costs and reason", () => {
  const advice = model(FRESH);
  if (advice.state !== "advice") {
    throw new Error(`expected advice, got ${advice.state}`);
  }
  expect(advice.day).toBe("2025-06-17");
  expect(sides(advice)).toEqual(["sell TLKM", "buy BBCA"]);
  const [sell, buy] = advice.orders;
  expect(sell?.order.quantity).toBe(1000n);
  expect(sell?.limitPrice).toEqual(rp(2750n));
  expect(sell?.reason).toBe("TLKM failed the stand-in's test");
  expect(buy?.limitPrice).toEqual(rp(9100n));
  expect(buy?.reason).toBe("BBCA passed the stand-in's test");
  if (buy === undefined) {
    throw new Error("expected a buy");
  }
  expect(buy.costs).toEqual(RULES.costs("buy", rp(9100n).times(buy.order.quantity), "2025-06-17"));
  expect(advice.missing).toEqual([]);
  expect(advice.stops).toEqual([]);
});

test("cash available to buy above the cash balance still gives advice, buying with the balance", () => {
  const portfolio = portfolioAt(AFTER_CLOSE);
  const credit = { ...portfolio, value: { ...portfolio.value, cashAvailable: rp(12_000_000n) } };
  const advice = model({ ...FRESH, portfolio: credit }, {}, buyAndHold);
  // TLKM, at 2,750,000 of 12,750,000, is already above the usual 10% limit per stock.
  expect(advice.state === "advice" ? sides(advice) : advice).toEqual(["buy BBCA"]);
});

test("with the flags page unread, buys stop naming it and sells are still given", () => {
  const advice = model(UNFLAGGED);
  expect(sides(advice)).toEqual(["sell TLKM"]);
  expect(advice.state === "advice" && advice.stops).toEqual([missingPage("flags")]);
  expect(advice.state === "advice" && advice.rejected.map((cut) => cut.reason)).toEqual([
    missingPage("flags"),
  ]);
});

test("a flags read for an earlier advice day counts as unread", () => {
  const advice = model({ ...FRESH, flags: flagsAt(wib("2025-06-16T19:00:00")) });
  expect(advice.state === "advice" && advice.stops).toEqual([missingPage("flags")]);
});

test("a stock the flags page marks is neither bought nor sold", () => {
  const advice = model({
    ...FRESH,
    flags: flagsAt(AFTER_CLOSE, [{ symbol: "TLKM", flag: "suspended" }]),
  });
  expect(sides(advice)).toEqual(["buy BBCA"]);
});

test("a stock Settings excludes is neither judged nor traded", () => {
  const seen: Seen = {};
  model(FRESH, { excluded: new Map([["TLKM", "my own reason"]]) }, standIn(seen));
  expect(seen.view?.tradable.sellable.has("TLKM")).toBe(false);
  expect(seen.view?.tradable.members.has("TLKM")).toBe(false);
});

test("a listed stock missing from the watchlist is named, and no orders are given", () => {
  const advice = model(FRESH, { universe: ["BBCA", "TLKM", "UNVR"] });
  expect(advice.state === "advice" && advice.missing).toEqual([missingPage("watchlist", "UNVR")]);
  expect(sides(advice)).toEqual([]);
});

test("a halt's stops from the risk record stop every buy", () => {
  const risk: RiskRecord = {
    ...NO_RISK,
    valuations: [
      { day: "2025-06-16", readAt: wib("2025-06-16T19:00:00"), value: rp(13_000_000n) },
      { day: "2025-06-17", readAt: AFTER_CLOSE, value: rp(12_750_000n) },
    ],
  };
  const expected = buyStops(riskState(LIMITS, CALENDAR, risk));
  expect(expected.length).toBeGreaterThan(0);
  const advice = model(FRESH, { risk });
  expect(advice.state === "advice" && advice.stops).toEqual(expected);
  expect(sides(advice)).toEqual(["sell TLKM"]);
});

test("the strategy sees the day's closes, tradable set, record and the memory the day began with", () => {
  const seen: Seen = {};
  const dividends: Dividends = {
    symbol: "BBCA",
    covered: { from: "2019-01-01", to: "2025-06-17" },
    dividends: [],
  };
  const began = new Map([["set", "IDX:TLKM"]]);
  model(
    FRESH,
    {
      dividends: new Map([["BBCA", dividends]]),
      splits: [{ symbol: "BBCA", exDate: "2021-10-13", from: 1n, to: 5n }],
      stored: { day: "2025-06-17", began, ended: new Map() },
      closes: new Map([
        [
          "BBCA",
          [
            { day: "2025-06-12", close: rp(9000n) },
            { day: "2025-06-13", close: rp(1800n) },
          ],
        ],
      ]),
    },
    standIn(seen),
  );
  expect(seen.view?.day).toBe("2025-06-17");
  expect(seen.view?.closes).toEqual(
    new Map([
      ["TLKM", rp(2750n)],
      ["BBCA", rp(9100n)],
    ]),
  );
  expect(seen.view?.tradable.buyable).toEqual(new Set(["BBCA", "TLKM"]));
  expect(seen.view?.dividends).toEqual(new Map([["BBCA", dividends]]));
  expect(seen.view?.splits).toEqual([{ symbol: "BBCA", exDate: "2021-10-13", from: 1n, to: 5n }]);
  expect(seen.view?.unknownActions).toEqual(new Map([["BBCA", "2025-06-13"]]));
  expect(seen.portfolio?.value).toEqual(rp(12_750_000n));
  expect(seen.memory).toEqual(began);
});

test("the advice carries the memory to keep: what the day began with and what it ended with", () => {
  const advice = model(FRESH);
  expect(advice.state === "advice" && advice.remember).toEqual({
    day: "2025-06-17",
    began: new Map(),
    ended: new Map([["set", "IDX:BBCA"]]),
  });
});

test("the strategy's notes are the advice's warnings", () => {
  const warning = { code: "strategy.too_few_qualified", text: "Only 1 stock passed." } as const;
  const strategy: Strategy = {
    name: "noted",
    decide: (view, portfolio, memory) => ({
      ...standIn().decide(view, portfolio, memory),
      notes: [warning],
    }),
  };
  const advice = model(FRESH, {}, strategy);
  expect(advice.state === "advice" && advice.warnings).toEqual([warning]);
});

test("with no income goal set, the goal says so", () => {
  const advice = model(FRESH);
  expect(advice.state === "advice" && advice.goal).toEqual({ state: "no goal set" });
});

test("a goal whose holdings lack a dividend read names what is missing", () => {
  const advice = model(FRESH, { goal: rp(1_000_000n) });
  expect(advice.state === "advice" && advice.goal).toEqual({
    state: "missing",
    missing: [missingPage("dividends", "TLKM")],
  });
});

test("a goal with every holding's dividends read gives the run rate against it", () => {
  const tlkm: Dividends = {
    symbol: "TLKM",
    covered: { from: "2024-01-01", to: "2025-06-17" },
    dividends: [
      {
        symbol: "TLKM",
        exDate: "2025-05-20",
        paymentDate: "2025-06-10",
        grossPerShare: new RuleDecimal("120"),
      },
    ],
  };
  const advice = model(FRESH, { goal: rp(1_000_000n), dividends: new Map([["TLKM", tlkm]]) });
  if (advice.state !== "advice" || advice.goal.state !== "progress") {
    throw new Error("expected goal progress");
  }
  expect(advice.goal.progress.target).toEqual(rp(1_000_000n));
  expect(advice.goal.progress.runRate.amount > 0n).toBe(true);
  // Read back to 2024 only: growth needs the five years to 17 June 2020 (spec §9.1, #254 AC2).
  expect(advice.goal.projection).toEqual({
    state: "missing",
    missing: [missingPage("dividends", "TLKM")],
  });
});

/** TLKM's dividends read back to 2020: `earlier` a share in the year to 17 June 2021. */
const tlkmSince2020 = (earlier: string | undefined): Dividends => ({
  symbol: "TLKM",
  covered: { from: "2020-06-01", to: "2025-06-17" },
  dividends: [
    ...(earlier === undefined
      ? []
      : [
          {
            symbol: "TLKM",
            exDate: "2021-05-20",
            paymentDate: "2021-06-10",
            grossPerShare: new RuleDecimal(earlier),
          },
        ]),
    {
      symbol: "TLKM",
      exDate: "2025-05-20",
      paymentDate: "2025-06-10",
      grossPerShare: new RuleDecimal("120"),
    },
  ],
});

/** The goal's projection as core makes it from the holdings alone, cash left out (spec §9.1). */
const projected = (tlkm: Dividends, contribution: Money) => {
  const dividends = new Map([["TLKM", tlkm]]);
  const held = portfolioView(RULES, portfolioAt(AFTER_CLOSE).value, "2025-06-17");
  const read = runRate({
    rules: RULES,
    held: held.held,
    dividends,
    splits: [],
    unknownActions: new Map(),
    asOf: "2025-06-17",
  });
  if (read.rate === null) {
    throw new Error("expected a run rate");
  }
  const growth = incomeGrowth(read.rate, dividends, []);
  if (growth.growth === null) {
    throw new Error("expected growth");
  }
  const projection = project({
    rate: read.rate,
    growth: growth.growth,
    holdingsValue: rp(2_750_000n),
    target: rp(1_000_000n),
    contribution,
    rules: RULES,
  });
  return {
    state: "projected",
    projection,
    notes: [...growth.growth.notes, ...projection.notes],
  };
};

test("a goal whose dividends reach back five years is projected from the holdings and the amount added", () => {
  const tlkm = tlkmSince2020("80");
  const advice = model(FRESH, {
    goal: rp(1_000_000n),
    contribution: rp(500_000n),
    dividends: new Map([["TLKM", tlkm]]),
  });
  if (advice.state !== "advice" || advice.goal.state !== "progress") {
    throw new Error("expected goal progress");
  }
  expect(advice.goal.projection).toEqual(projected(tlkm, rp(500_000n)));
  expect(
    advice.goal.projection.state === "projected" && advice.goal.projection.projection.contribution,
  ).toEqual(rp(500_000n));
});

test("a holding that paid nothing in the earlier year is projected at 0% growth, with its note", () => {
  const tlkm = tlkmSince2020(undefined);
  const advice = model(FRESH, { goal: rp(1_000_000n), dividends: new Map([["TLKM", tlkm]]) });
  if (advice.state !== "advice" || advice.goal.state !== "progress") {
    throw new Error("expected goal progress");
  }
  expect(advice.goal.projection).toEqual(projected(tlkm, rp(0n)));
  const codes = advice.goal.projection.state === "projected" ? advice.goal.projection.notes : [];
  expect(codes.map((each) => each.code)).toEqual([
    NOTE_CODES.INCOME_GROWTH_SHORT_HISTORY,
    NOTE_CODES.INCOME_PROJECTION_COSTS_IGNORED,
  ]);
});
