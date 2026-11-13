import { IDR, Money } from "@steadyhand/core";
import { expect, test } from "vitest";
import {
  EXEMPTION,
  dividendsOf,
  exemptionOf,
  purchasesOf,
  storedDividends,
  storedPurchases,
  typedEntry,
  wibDay,
} from "../src/exemption.ts";

// What the panel keeps for the dividend reinvestment exemption (spec §9.2): the switch, the
// dividends received and the reinvesting purchases, each refused by name when not as kept, and
// how it reads an entry the user typed.

const refused = (name: string): Error =>
  new Error(`the setting ${name} is not as Settings keeps it`);

const rupiah = (amount: bigint): Money => new Money(amount, IDR);

test("the exemption is kept under its own names", () => {
  expect(EXEMPTION).toEqual({
    claimed: "dividend-exemption",
    dividends: "dividends-received",
    purchases: "reinvesting-purchases",
  });
});

test("before the switch is touched the exemption is not claimed", () => {
  expect(exemptionOf(undefined)).toBe(false);
});

test("a kept switch that is on is read as claimed", () => {
  expect(exemptionOf(true)).toBe(true);
});

test("a kept switch that is off is read as not claimed", () => {
  expect(exemptionOf(false)).toBe(false);
});

test("a kept switch that is not true or false is refused", () => {
  expect(() => exemptionOf("yes")).toThrow(refused("dividend-exemption"));
});

test("before any dividend is entered there are none", () => {
  expect(dividendsOf(undefined)).toEqual([]);
});

test("kept dividends are read back in the order kept", () => {
  const kept = [
    { received: "2025-06-10", symbol: "BBCA", gross: "1000000" },
    { received: "2025-03-02", symbol: "TLKM", gross: "250000" },
  ];
  expect(dividendsOf(kept)).toEqual([
    { received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) },
    { received: "2025-03-02", symbol: "TLKM", gross: rupiah(250_000n) },
  ]);
});

test("a dividend stored and read again is the same dividend", () => {
  const entered = [{ received: "2025-06-10", symbol: "BBCA", gross: rupiah(1_000_000n) }];
  expect(dividendsOf(storedDividends(entered))).toEqual(entered);
});

test("kept dividends that are not a list are refused", () => {
  expect(() => dividendsOf({ received: "2025-06-10" })).toThrow(refused("dividends-received"));
});

test("a kept dividend with a day that is not a day is refused", () => {
  const kept = [{ received: "2025-13-10", symbol: "BBCA", gross: "1000" }];
  expect(() => dividendsOf(kept)).toThrow(refused("dividends-received"));
});

test("a kept dividend with a stock that is not a code is refused", () => {
  const kept = [{ received: "2025-06-10", symbol: "bbca", gross: "1000" }];
  expect(() => dividendsOf(kept)).toThrow(refused("dividends-received"));
});

test("a kept dividend with a gross that is not whole rupiah is refused", () => {
  const kept = [{ received: "2025-06-10", symbol: "BBCA", gross: "10.5" }];
  expect(() => dividendsOf(kept)).toThrow(refused("dividends-received"));
});

test("a kept dividend of nothing is refused", () => {
  const kept = [{ received: "2025-06-10", symbol: "BBCA", gross: "0" }];
  expect(() => dividendsOf(kept)).toThrow(refused("dividends-received"));
});

test("a kept dividend that is not a record is refused", () => {
  expect(() => dividendsOf(["BBCA"])).toThrow(refused("dividends-received"));
});

test("before any purchase is entered there are none", () => {
  expect(purchasesOf(undefined)).toEqual([]);
});

test("kept purchases are read back in the order kept", () => {
  const kept = [
    { day: "2025-07-01", symbol: "BBRI", amount: "600000" },
    { day: "2025-05-01", symbol: "ASII", amount: "1" },
  ];
  expect(purchasesOf(kept)).toEqual([
    { day: "2025-07-01", symbol: "BBRI", amount: rupiah(600_000n) },
    { day: "2025-05-01", symbol: "ASII", amount: rupiah(1n) },
  ]);
});

test("a purchase stored and read again is the same purchase", () => {
  const entered = [{ day: "2025-07-01", symbol: "BBRI", amount: rupiah(600_000n) }];
  expect(purchasesOf(storedPurchases(entered))).toEqual(entered);
});

test("kept purchases that are not a list are refused", () => {
  expect(() => purchasesOf("BBRI")).toThrow(refused("reinvesting-purchases"));
});

test("a kept purchase with a missing amount is refused", () => {
  const kept = [{ day: "2025-07-01", symbol: "BBRI" }];
  expect(() => purchasesOf(kept)).toThrow(refused("reinvesting-purchases"));
});

test("a kept dividend with its stock in a list is refused", () => {
  const kept = [{ received: "2025-06-10", symbol: ["BBCA"], gross: "1000" }];
  expect(() => dividendsOf(kept)).toThrow(refused("dividends-received"));
});

test("a kept purchase with its amount as a number is refused", () => {
  const kept = [{ day: "2025-07-01", symbol: "BBRI", amount: 1000 }];
  expect(() => purchasesOf(kept)).toThrow(refused("reinvesting-purchases"));
});

test("a kept purchase that is a word is refused", () => {
  expect(() => purchasesOf(["BBRI"])).toThrow(refused("reinvesting-purchases"));
});

test("a kept purchase that is null is refused", () => {
  expect(() => purchasesOf([null])).toThrow(refused("reinvesting-purchases"));
});

test("a kept purchase that is missing is refused", () => {
  expect(() => purchasesOf([undefined])).toThrow(refused("reinvesting-purchases"));
});

const TODAY = "2025-08-01";
const FIRST = "2021-01-01";

test("a typed entry is read as its day, its stock in capitals and its rupiah", () => {
  expect(
    typedEntry({ day: " 2025-07-01 ", symbol: " bbri ", amount: "1.250.000" }, TODAY, FIRST),
  ).toEqual({ day: "2025-07-01", symbol: "BBRI", amount: rupiah(1_250_000n) });
});

test("a typed entry dated today is kept", () => {
  expect(typedEntry({ day: TODAY, symbol: "BBRI", amount: "1" }, TODAY, FIRST)).toEqual({
    day: TODAY,
    symbol: "BBRI",
    amount: rupiah(1n),
  });
});

test("a typed entry with a day that is not a day is refused by its day", () => {
  expect(typedEntry({ day: "1 July", symbol: "BBRI", amount: "1000" }, TODAY, FIRST)).toBe("day");
});

test("a typed entry dated after today is refused by its day", () => {
  expect(typedEntry({ day: "2025-08-02", symbol: "BBRI", amount: "1000" }, TODAY, FIRST)).toBe(
    "future",
  );
});

test("a typed entry with a stock that is not a code is refused by its stock", () => {
  expect(typedEntry({ day: "2025-07-01", symbol: "BBRI4", amount: "1000" }, TODAY, FIRST)).toBe(
    "stock",
  );
});

test("a typed entry with an amount that is not whole rupiah is refused by its amount", () => {
  expect(typedEntry({ day: "2025-07-01", symbol: "BBRI", amount: "1,5" }, TODAY, FIRST)).toBe(
    "amount",
  );
});

test("a typed entry of nothing is refused by its amount", () => {
  expect(typedEntry({ day: "2025-07-01", symbol: "BBRI", amount: "0" }, TODAY, FIRST)).toBe(
    "amount",
  );
});

test("a typed entry dated the rules' first day is kept", () => {
  expect(typedEntry({ day: FIRST, symbol: "BBRI", amount: "1" }, TODAY, FIRST)).toEqual({
    day: FIRST,
    symbol: "BBRI",
    amount: rupiah(1n),
  });
});

test("a typed entry dated before the rules' first day is refused by its day", () => {
  expect(typedEntry({ day: "2020-12-31", symbol: "BBRI", amount: "1" }, TODAY, FIRST)).toBe(
    "early",
  );
});

test("today is the day in WIB, seven hours ahead of UTC", () => {
  expect(wibDay(new Date("2025-06-17T16:59:59Z"))).toBe("2025-06-17");
  expect(wibDay(new Date("2025-06-17T17:00:00Z"))).toBe("2025-06-18");
});
