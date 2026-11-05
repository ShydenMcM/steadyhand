import { readFileSync } from "node:fs";
import {
  Costs,
  IDR,
  IdxMarketRules,
  missingPage,
  Money,
  note,
  NOTE_CODES,
  RuleDecimal,
  Side,
  type StoredMemory,
} from "@steadyhand/core";
import { expect, test } from "vitest";
import type { AdviceModel } from "../src/advice-model.ts";
import { adviceView, CHOICE_LINE, DISCLAIMER } from "../src/advice-view.ts";

// The panel's advice as text (spec §10.3, #238 AC3): each order with its lots, limit, estimated
// fees and reason, what was not given and why, the stops, the missing list with the page to open,
// warnings and income-goal progress; the advice day; or what to read first and when the next
// close is final. The panel writes these lines as they are.

const RULES = new IdxMarketRules();
const rp = (amount: bigint): Money => new Money(amount, IDR);
const DAY = "2025-06-17";
const KEPT: StoredMemory = { day: DAY, began: new Map(), ended: new Map() };

const advice = (parts: Partial<Extract<AdviceModel, { state: "advice" }>> = {}): AdviceModel => ({
  state: "advice",
  day: DAY,
  orders: [],
  rejected: [],
  cuts: [],
  stampDuty: rp(0n),
  missing: [],
  stops: [],
  warnings: [],
  goal: { state: "no goal set" },
  remember: KEPT,
  ...parts,
});

const buyBbca = {
  order: { symbol: "BBCA", side: Side.BUY, quantity: 300n, day: DAY },
  limitPrice: rp(9100n),
  costs: new Costs(rp(4095n), rp(1180n), rp(0n), true),
  reason: "BBCA raised its dividend six years running",
};

test("the disclaimer is core §9.8's text, word for word as Python writes it", () => {
  const python = readFileSync(
    new URL("../../../../packages/steadyhand/src/steadyhand/disclaimer.py", import.meta.url),
    "utf8",
  );
  const constant = python.slice(python.indexOf("DISCLAIMER: Final"));
  const quoted = [...constant.matchAll(/"([^"]*)"/gu)].map((match) => match[1]).join("");
  expect(DISCLAIMER).toBe(quoted);
  expect(DISCLAIMER).toBe(
    "steadyhand is example software that you run yourself, on your own account, and you make " +
      "your own decisions with it. It is not financial advice. You can lose money.",
  );
});

test("the choice line is spec §10.3's", () => {
  expect(CHOICE_LINE).toBe(
    "steadyhand computes what the strategy you chose implies; the choice and the orders are yours",
  );
});

test("a day with no orders says so, under its advice day, with no goal set", () => {
  expect(adviceView(advice(), RULES)).toEqual([
    { heading: "Advice for 2025-06-17", lines: ["No orders for this day."] },
    { heading: "Income goal", lines: ["No income goal set."] },
  ]);
});

test("each order gives its side, lots, stock, limit, estimated fees and reason", () => {
  const sell = {
    order: { symbol: "TLKM", side: Side.SELL, quantity: 1000n, day: DAY },
    limitPrice: rp(2750n),
    costs: new Costs(rp(6875n), rp(1100n), rp(2750n)),
    reason: "TLKM is outside the universe",
  };
  expect(adviceView(advice({ orders: [buyBbca, sell] }), RULES)[0]).toEqual({
    heading: "Advice for 2025-06-17",
    lines: [
      "Buy 3 lots of BBCA at a limit of IDR 9,100, estimated fees IDR 5,275: " +
        "BBCA raised its dividend six years running.",
      "Sell 10 lots of TLKM at a limit of IDR 2,750, estimated fees IDR 10,725: " +
        "TLKM is outside the universe.",
    ],
  });
});

test("a stamp duty on the day's orders is its own line", () => {
  expect(adviceView(advice({ orders: [buyBbca], stampDuty: rp(10_000n) }), RULES)[0]).toEqual({
    heading: "Advice for 2025-06-17",
    lines: [
      "Buy 3 lots of BBCA at a limit of IDR 9,100, estimated fees IDR 5,275: " +
        "BBCA raised its dividend six years running.",
      "Stamp duty on the day's orders: IDR 10,000.",
    ],
  });
});

test("orders not given and orders cut each say why", () => {
  const short = note(NOTE_CODES.LIMIT_CASH_SHORT, "settled cash is short");
  const cut = note(NOTE_CODES.LIMIT_CASH_CUT, "cut to the settled cash");
  const view = adviceView(
    advice({
      rejected: [{ order: buyBbca.order, reason: short }],
      cuts: [{ order: { ...buyBbca.order, symbol: "TLKM" }, quantity: 200n, reason: cut }],
    }),
    RULES,
  );
  expect(view[1]).toEqual({
    heading: "Not given as the strategy asked",
    lines: [
      "Buy 3 lots of BBCA not given: settled cash is short.",
      "Buy TLKM cut to 2 lots: cut to the settled cash.",
    ],
  });
});

test("stops, missing pages and warnings each have their own list", () => {
  const view = adviceView(
    advice({
      stops: [missingPage("flags")],
      missing: [missingPage("dividends", "BBCA")],
      warnings: [note(NOTE_CODES.INCOME_GROWTH_SHORT_HISTORY, "UNVR has five years of dividends")],
    }),
    RULES,
  );
  expect(view.slice(1, 4)).toEqual([
    {
      heading: "Buys stopped",
      lines: ["Open the page that flags suspended and monitored stocks."],
    },
    { heading: "Missing", lines: ["Open the dividend page for BBCA."] },
    { heading: "Warnings", lines: ["UNVR has five years of dividends."] },
  ]);
});

test("income-goal progress gives the run rate against the goal, and its share", () => {
  const goal = {
    state: "progress" as const,
    progress: {
      target: rp(4_000_000n),
      runRate: rp(1_000_000n),
      runRateShare: new RuleDecimal("0.25"),
    },
  };
  expect(adviceView(advice({ goal }), RULES).at(-1)).toEqual({
    heading: "Income goal",
    lines: ["IDR 1,000,000 a month of the IDR 4,000,000 goal (25.00%)."],
  });
});

test("an income goal that cannot be measured names what is missing", () => {
  const goal = { state: "missing" as const, missing: [missingPage("dividends", "TLKM")] };
  expect(adviceView(advice({ goal }), RULES).at(-1)).toEqual({
    heading: "Income goal",
    lines: ["Open the dividend page for TLKM."],
  });
});

test("reads that are not fresh say why, what to open and when the next close is final", () => {
  const model: AdviceModel = {
    state: "read again",
    reason: "read during a trading session",
    missing: [missingPage("portfolio"), missingPage("watchlist")],
    nextClose: new Date("2025-06-17T16:15:00+07:00"),
  };
  expect(adviceView(model, RULES)).toEqual([
    {
      heading: "Read again",
      lines: [
        "The pages below were read during a trading session.",
        "Open the portfolio page.",
        "Open the watchlist page.",
        "The next close is final at 2025-06-17 16:15 WIB.",
      ],
    },
  ]);
});

test("with no universe listed, the panel asks for one", () => {
  expect(adviceView({ state: "no universe" }, RULES)).toEqual([
    { heading: "Universe", lines: ["List the universe's stocks in Settings to get advice."] },
  ]);
});
