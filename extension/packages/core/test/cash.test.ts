import { expect, test } from "vitest";
import type { CashMovement, CashMovements } from "../src/broker-view.ts";
import { totalsMismatch } from "../src/cash.ts";
import { IDR, Money } from "../src/money.ts";

// A cash read counts only when its rows add up to the totals its page shows (#474, #477): a page
// cut short to one of two equal deposits must never pass as the whole period.

const rp = (amount: bigint): Money => new Money(amount, IDR);
const deposit: CashMovement = { day: "2026-10-05", kind: "deposit", amount: rp(5_000_000n) };
const withdrawal: CashMovement = { day: "2026-10-20", kind: "withdrawal", amount: rp(750_000n) };
const read = (
  movements: readonly CashMovement[],
  deposits: bigint,
  withdrawals: bigint,
): CashMovements => ({
  covered: { from: "2026-10-01", to: "2026-10-31" },
  movements,
  totals: { deposits: rp(deposits), withdrawals: rp(withdrawals) },
});

test("rows that add up to both totals pass", () => {
  expect(totalsMismatch(read([deposit, withdrawal], 5_000_000n, 750_000n))).toBeUndefined();
});

test("two equal deposits, both in the rows and the total, pass", () => {
  expect(totalsMismatch(read([deposit, deposit], 10_000_000n, 0n))).toBeUndefined();
});

test("no movements and totals of nothing pass", () => {
  expect(totalsMismatch(read([], 0n, 0n))).toBeUndefined();
});

test("a page cut short to one of two equal deposits is named", () => {
  expect(totalsMismatch(read([deposit], 10_000_000n, 0n))).toBe(
    "deposits: the page shows 10000000, its rows add up to 5000000",
  );
});

test.each([
  [5_000_001n, 750_000n, "deposits: the page shows 5000001, its rows add up to 5000000"],
  [4_999_999n, 750_000n, "deposits: the page shows 4999999, its rows add up to 5000000"],
  [5_000_000n, 750_001n, "withdrawals: the page shows 750001, its rows add up to 750000"],
  [5_000_000n, 749_999n, "withdrawals: the page shows 749999, its rows add up to 750000"],
] as const)(
  "totals of %s and %s one rupiah off the rows are named: %s",
  (deposits, withdrawals, named) => {
    expect(totalsMismatch(read([deposit, withdrawal], deposits, withdrawals))).toBe(named);
  },
);
