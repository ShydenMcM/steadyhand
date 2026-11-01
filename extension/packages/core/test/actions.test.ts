import { expect, test } from "vitest";
import { actionBetween } from "../src/actions.ts";
import { IdxCalendar } from "../src/calendar.ts";
import { IDR, Money } from "../src/money.ts";
import { IdxMarketRules } from "../src/rules.ts";

// Corporate actions found by price (spec §6.4, #232 AC2), on the shipped band and tick rows,
// each edge worked by hand. In the tier up to Rp5,000 the band is +25% / -15% from 2025-04-08,
// on a tick grid of 5 from Rp500 and 2 from Rp200; up to Rp200 it is +35%.

const RULES = new IdxMarketRules();
const CALENDAR = IdxCalendar.shipped();
const close = (day: string, amount: bigint) => ({ day, close: new Money(amount, IDR) });
const moved = (from: ReturnType<typeof close>, to: ReturnType<typeof close>) =>
  actionBetween("BBCA", from, to, RULES, CALENDAR);

test("a rise to the band's top exactly is a market move", () => {
  expect(moved(close("2025-06-16", 1_000n), close("2025-06-17", 1_250n))).toBe(false);
});

test("a rise one tick beyond the band's top marks an action", () => {
  expect(moved(close("2025-06-16", 1_000n), close("2025-06-17", 1_255n))).toBe(true);
});

test("a fall to the band's bottom exactly is a market move", () => {
  expect(moved(close("2025-06-16", 1_000n), close("2025-06-17", 850n))).toBe(false);
});

test("a fall one tick beyond the band's bottom marks an action", () => {
  expect(moved(close("2025-06-16", 1_000n), close("2025-06-17", 845n))).toBe(true);
});

test("an unchanged close is a market move", () => {
  expect(moved(close("2025-06-16", 1_000n), close("2025-06-17", 1_000n))).toBe(false);
});

test("across a gap the band is stepped once a trading day, each from the last step's price", () => {
  // Two trading days: 1,000 to 1,250, then 1,250 to 1,562.5, down to the tick, 1,560.
  expect(moved(close("2025-06-16", 1_000n), close("2025-06-18", 1_560n))).toBe(false);
  expect(moved(close("2025-06-16", 1_000n), close("2025-06-18", 1_565n))).toBe(true);
});

test("a gap crossing a tier edge steps each tier's own band", () => {
  // 180 is in the 35% tier: 243, down to the tick of 2, 242; then 25%: 302.5, down to 302.
  expect(moved(close("2025-06-16", 180n), close("2025-06-18", 302n))).toBe(false);
  expect(moved(close("2025-06-16", 180n), close("2025-06-18", 304n))).toBe(true);
});

test("a step reads the band rows effective on its own day", () => {
  // 2025-03-27 to 2025-04-08 is one trading day (the Lebaran holidays), stepped with the row
  // from 2025-04-08: -15%, so 850, where the earlier row's -25% would allow 750.
  expect(CALENDAR.nextTradingDay("2025-03-27")).toBe("2025-04-08");
  expect(moved(close("2025-03-27", 1_000n), close("2025-04-08", 850n))).toBe(false);
  expect(moved(close("2025-03-27", 1_000n), close("2025-04-08", 800n))).toBe(true);
});

test("a fixed-rupiah tier steps by rupiah", () => {
  // From 2026-09-28 a price up to Rp10 moves at most Rp1 a day.
  expect(CALENDAR.nextTradingDay("2026-10-01")).toBe("2026-10-02");
  expect(moved(close("2026-10-01", 5n), close("2026-10-02", 6n))).toBe(false);
  expect(moved(close("2026-10-01", 5n), close("2026-10-02", 7n))).toBe(true);
});
