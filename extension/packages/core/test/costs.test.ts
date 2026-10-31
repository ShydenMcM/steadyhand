import { expect, test } from "vitest";
import { Costs, Side } from "../src/costs.ts";
import { Currency, CurrencyMismatchError, IDR, Money } from "../src/money.ts";

// Ported from Python's tests/engine/test_types.py `TestCosts`, one test per case.

const rp = (amount: bigint): Money => new Money(amount, IDR);

const costs = (fee = 0n, levy = 0n, tax = 0n): Costs => new Costs(rp(fee), rp(levy), rp(tax));

test("the two sides are buy and sell, as Python names them", () => {
  expect(Object.values(Side)).toEqual(["buy", "sell"]);
});

test("total adds the three parts", () => {
  expect(costs(450n, 30n, 100n).total.equals(rp(580n))).toBe(true);
});

test("zero is nothing on every part", () => {
  const zero = Costs.zero(IDR);
  expect([zero.fee, zero.levy, zero.tax].map(String)).toEqual(["IDR 0", "IDR 0", "IDR 0"]);
});

test("costs are exact unless a fee is marked an estimate", () => {
  expect(costs().estimate).toBe(false);
  expect(new Costs(rp(1n), rp(0n), rp(0n), true).estimate).toBe(true);
});

test.each(["fee", "levy", "tax"])("no part may be negative: %s", (part) => {
  const parts = { fee: 0n, levy: 0n, tax: 0n, [part]: -1n };
  expect(() => costs(parts.fee, parts.levy, parts.tax)).toThrow(
    new RangeError(`${part} cannot be negative, got IDR -1`),
  );
});

test("parts must share a currency", () => {
  expect(() => new Costs(rp(1n), rp(1n), new Money(1n, new Currency("USD", 2n)))).toThrow(
    CurrencyMismatchError,
  );
});
