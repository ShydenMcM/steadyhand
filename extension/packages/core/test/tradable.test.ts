import { expect, test } from "vitest";
import type { Flag } from "../src/broker-view.ts";
import { Side } from "../src/costs.ts";
import { tradableOn, whyNot, type TradableInputs } from "../src/tradable.ts";

// Ported from how Python's engine builds the tradable set (`engine._tradable`) and from
// `view.Tradable.why_not`; flags come from the broker's page (spec §4.4).

const DAY = "2026-10-30";

const inputs = (over: Partial<TradableInputs> = {}): TradableInputs => ({
  day: DAY,
  members: new Set(["BBCA", "BBRI", "TLKM"]),
  held: new Set(["BBCA", "ASII"]),
  flags: [],
  excluded: new Map(),
  ...over,
});

const suspended = (symbol: string): Flag => ({ symbol, flag: "suspended" });

test("an unflagged member is buyable and a held stock sellable", () => {
  const tradable = tradableOn(inputs());
  expect([...tradable.buyable].sort()).toEqual(["BBCA", "BBRI", "TLKM"]);
  expect([...tradable.sellable].sort()).toEqual(["ASII", "BBCA"]);
  expect(whyNot(tradable, "BBRI", Side.BUY)).toBeNull();
  expect(whyNot(tradable, "ASII", Side.SELL)).toBeNull();
});

test("a stock outside the universe is not bought, with Python's note", () => {
  expect(whyNot(tradableOn(inputs()), "ASII", Side.BUY)).toEqual({
    code: "trade.not_in_universe",
    text: "not in the universe on 2026-10-30",
  });
});

test("a stock not held is not sold, with Python's note", () => {
  expect(whyNot(tradableOn(inputs()), "BBRI", Side.SELL)).toEqual({
    code: "trade.not_held",
    text: "not held",
  });
});

test("a held stock the broker marks suspended is neither bought nor sold", () => {
  const tradable = tradableOn(inputs({ flags: [suspended("BBCA")] }));
  const frozen = { code: "trade.frozen", text: "frozen: suspended" };
  expect(whyNot(tradable, "BBCA", Side.BUY)).toEqual(frozen);
  expect(whyNot(tradable, "BBCA", Side.SELL)).toEqual(frozen);
});

test("a held stock on the Special Monitoring Board is neither bought nor sold", () => {
  const tradable = tradableOn(inputs({ flags: [{ symbol: "BBCA", flag: "special-monitoring" }] }));
  const frozen = { code: "trade.frozen", text: "frozen: on the Special Monitoring Board" };
  expect(whyNot(tradable, "BBCA", Side.BUY)).toEqual(frozen);
  expect(whyNot(tradable, "BBCA", Side.SELL)).toEqual(frozen);
});

test("a flagged stock not held is not bought", () => {
  expect(whyNot(tradableOn(inputs({ flags: [suspended("TLKM")] })), "TLKM", Side.BUY)).toEqual({
    code: "trade.frozen",
    text: "frozen: suspended",
  });
});

test("a held stock Settings excludes is neither bought nor sold", () => {
  const tradable = tradableOn(inputs({ excluded: new Map([["BBCA", "my employer"]]) }));
  const excluded = { code: "trade.excluded", text: "excluded: my employer" };
  expect(whyNot(tradable, "BBCA", Side.BUY)).toEqual(excluded);
  expect(whyNot(tradable, "BBCA", Side.SELL)).toEqual(excluded);
});

test("frozen beats excluded, as Python sets the frozen reason first", () => {
  const tradable = tradableOn(
    inputs({ flags: [suspended("BBCA")], excluded: new Map([["BBCA", "my employer"]]) }),
  );
  expect(whyNot(tradable, "BBCA", Side.SELL)?.code).toBe("trade.frozen");
});

test("a stock both suspended and monitored keeps the first flag the page lists", () => {
  const tradable = tradableOn(
    inputs({ flags: [{ symbol: "BBCA", flag: "special-monitoring" }, suspended("BBCA")] }),
  );
  expect(whyNot(tradable, "BBCA", Side.SELL)?.text).toBe("frozen: on the Special Monitoring Board");
});

test("a held stock that left the universe may be sold but not bought", () => {
  const tradable = tradableOn(inputs());
  expect(tradable.sellable.has("ASII")).toBe(true);
  expect(tradable.buyable.has("ASII")).toBe(false);
});

test("the tradable set is for its day", () => {
  expect(tradableOn(inputs()).day).toBe(DAY);
});
