import Decimal from "decimal.js";
import { expect, test } from "vitest";
import { IDR, Money } from "../src/money.ts";
import { ratioDown, rupiahUp } from "../src/ratio.ts";
import type { PortfolioView } from "../src/sizing.ts";
import { topUp } from "../src/strategy.ts";

// New cash shared by water-filling (#486): hand-computed, one test per case, the same cases as
// Python's tests/engine/test_top_up.py. A 1,000 portfolio unless said; TLKM is held but never
// bought, so the cash and the stocks bought add up to the portfolio with the room each case needs.

const QUARTER = new Decimal("0.25");

const portfolioOf = (spendable: bigint, held: Readonly<Record<string, bigint>>): PortfolioView => {
  const holdings = new Map(
    Object.entries(held).map(([symbol, worth]) => [symbol, new Money(worth, IDR)]),
  );
  const invested = [...holdings.values()].reduce((sum, worth) => sum + worth.amount, 0n);
  return {
    value: new Money(spendable + invested, IDR),
    spendable: new Money(spendable, IDR),
    holdings,
  };
};

const filled = (found: ReadonlyMap<string, Decimal>) =>
  Object.fromEntries([...found].map(([symbol, weight]) => [symbol, weight.toString()]));

test("a stock with little room leaves the rest of its share to the others", () => {
  // BBRI at 24%, with least room, is filled first though BBCA comes first by symbol: it takes
  // 1% (10), and the other 290 go to BBCA, which takes its 25%. 50 stay cash.
  const found = topUp(portfolioOf(300n, { BBRI: 240n, TLKM: 460n }), ["BBCA", "BBRI"], QUARTER);
  expect(filled(found)).toEqual({ BBCA: "0.25", BBRI: "0.25" });
});

test("cash short of every cap is shared equally", () => {
  const found = topUp(portfolioOf(300n, { TLKM: 700n }), ["BBCA", "BBRI"], QUARTER);
  expect(filled(found)).toEqual({ BBCA: "0.15", BBRI: "0.15" });
});

test("ample cash fills every stock to its cap", () => {
  const found = topUp(portfolioOf(1000n, {}), ["BBCA", "BBRI"], QUARTER);
  expect(filled(found)).toEqual({ BBCA: "0.25", BBRI: "0.25" });
});

test("a stock at or above its cap gets nothing and the others get its share", () => {
  const portfolio = portfolioOf(200n, { BBCA: 300n, BBRI: 250n, TLKM: 250n });
  const found = topUp(portfolio, ["BBCA", "BBRI", "UNVR"], QUARTER);
  expect(filled(found)).toEqual({ BBCA: "0.3", BBRI: "0.25", UNVR: "0.2" });
});

test("equal room is filled by symbol, so the odd rupiah goes last", () => {
  // 301 / 2 = 150 to BBCA first; the 151 left go to BBRI.
  const found = topUp(portfolioOf(301n, { TLKM: 699n }), ["BBRI", "BBCA"], QUARTER);
  expect(filled(found)).toEqual({ BBCA: "0.15", BBRI: "0.151" });
});

test("a stock capped mid-way counts its part rupiah as a whole one", () => {
  // A 3,000 portfolio and a cap of 1/3 (999.99... rupiah). BBCA at 999 has room for 0.99...,
  // which uses a whole rupiah of the 501, so BBRI, uncapped, is offered 500, not 501.
  const third = ratioDown(1n, 3n);
  const found = topUp(portfolioOf(501n, { BBCA: 999n, TLKM: 1500n }), ["BBCA", "BBRI"], third);
  expect(filled(found)).toEqual({
    BBCA: third.toString(),
    BBRI: ratioDown(500n, 3000n).toString(),
  });
});

test("nothing to buy gives nothing", () => {
  expect(topUp(portfolioOf(500n, { TLKM: 500n }), [], QUARTER).size).toBe(0);
});

test("a weight's rupiah are rounded up, and a whole one is kept", () => {
  expect([rupiahUp(new Decimal("0.0001"), 3000n), rupiahUp(new Decimal("0.25"), 1000n)]).toEqual([
    1n,
    250n,
  ]);
});
