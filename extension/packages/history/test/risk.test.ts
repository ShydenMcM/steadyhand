import {
  IDR,
  IdxCalendar,
  IdxMarketRules,
  Money,
  shippedSessions,
  type CashMovements,
  type Part,
  type Portfolio,
  type Source,
} from "@steadyhand/core";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, expect, test } from "vitest";
import { putAll, recordCashMovements, rowsOf } from "../src/record.ts";
import {
  recordAnswered,
  recordResume,
  recordTyped,
  recordValuation,
  riskRecord,
} from "../src/risk.ts";
import { openHistory, STORES } from "../src/schema.ts";

// What the risk halts are judged from (spec §8, EXT S12, #236): after-close valuations, the
// period each cash-movement read covers, typed entries, answered periods and resumes. The week of
// Monday 16 June 2025 has no IDX holiday.

const RULES = {
  calendar: IdxCalendar.shipped(),
  sessions: shippedSessions(),
  market: new IdxMarketRules(),
};
const rp = (amount: bigint): Money => new Money(amount, IDR);
const wib = (time: string): Date => new Date(`${time}+07:00`);
const source = (pageKind: Source["pageKind"]): Source => ({
  broker: "fixture",
  pageKind,
  route: "page",
});

/** Worth 5,415,000: 1,000,000 settled less 100,000 unsettled, 2 lots of 100 BBCA at 9,025
 * (1,805,000) and 10 lots of TLKM at 2,710 (2,710,000). */
const portfolioAt = (time: string): Part<Portfolio> => ({
  source: source("portfolio"),
  readAt: wib(time),
  value: {
    cashAvailable: rp(1_000_000n),
    cashSettled: rp(1_000_000n),
    cashUnsettled: rp(-100_000n),
    holdings: [
      { symbol: "BBCA", lots: 2n, averagePrice: rp(8_500n), lastPrice: rp(9_025n) },
      { symbol: "TLKM", lots: 10n, averagePrice: rp(2_900n), lastPrice: rp(2_710n) },
    ],
  },
});

let db: IDBDatabase;

beforeEach(async () => {
  db = await openHistory(new IDBFactory());
  return () => {
    db.close();
  };
});

test("an after-close portfolio read records the portfolio's value for its day", async () => {
  expect(await recordValuation(db, portfolioAt("2025-06-17T16:02:00"), RULES)).toBe("2025-06-17");
  expect(await rowsOf(db, STORES.valuations)).toEqual([
    {
      day: "2025-06-17",
      readAt: wib("2025-06-17T16:02:00"),
      value: 5_415_000n,
      currency: "IDR",
      // #256: the cost basis, 200 BBCA at 8,500 and 1,000 TLKM at 2,900.
      invested: 4_600_000n,
    },
  ]);
});

test("a valuation stored before #256 reads back with no cost basis", async () => {
  const row = { day: "2025-06-17", readAt: wib("2025-06-17T16:02:00"), value: 5_415_000n };
  await putAll(db, STORES.valuations, [{ ...row, currency: "IDR" }]);
  expect((await riskRecord(db)).valuations).toEqual([{ ...row, value: rp(5_415_000n) }]);
});

test("a read during a session records no valuation", async () => {
  expect(await recordValuation(db, portfolioAt("2025-06-17T11:00:00"), RULES)).toBeNull();
  expect(await rowsOf(db, STORES.valuations)).toEqual([]);
});

test("a read before the pre-opening values the trading day before", async () => {
  expect(await recordValuation(db, portfolioAt("2025-06-17T07:00:00"), RULES)).toBe("2025-06-16");
});

test("a day read twice keeps the later read", async () => {
  await recordValuation(db, portfolioAt("2025-06-17T16:02:00"), RULES);
  await recordValuation(db, portfolioAt("2025-06-17T20:00:00"), RULES);
  expect(
    (await rowsOf(db, STORES.valuations)).map((row) => (row as { readAt: Date }).readAt),
  ).toEqual([wib("2025-06-17T20:00:00")]);
});

const movements: Part<CashMovements> = {
  source: source("cash-movements"),
  readAt: wib("2025-06-17T19:00:00"),
  value: {
    covered: { from: "2025-06-01", to: "2025-06-17" },
    movements: [
      { day: "2025-06-02", kind: "deposit", amount: rp(5_000_000n) },
      { day: "2025-06-10", kind: "withdrawal", amount: rp(250_000n), reference: "TX-9" },
    ],
    totals: { deposits: rp(5_000_000n), withdrawals: rp(250_000n) },
  },
};

test("a cash-movement read records the period it covers and when it was read", async () => {
  await recordCashMovements(db, movements);
  expect(await rowsOf(db, STORES.cashMovementReads)).toEqual([
    { from: "2025-06-01", to: "2025-06-17", readAt: wib("2025-06-17T19:00:00") },
  ]);
});

test("a cash-movement read stored before #499 reads back with no read time", async () => {
  await putAll(db, STORES.cashMovementReads, [{ from: "2025-06-01", to: "2025-06-17" }]);
  expect((await riskRecord(db)).movementReads).toEqual([{ from: "2025-06-01", to: "2025-06-17" }]);
});

test("a cash-movement read refused for its totals records no period either", async () => {
  const cut = {
    ...movements,
    value: { ...movements.value, movements: movements.value.movements.slice(1) },
  };
  await expect(recordCashMovements(db, cut)).rejects.toThrow(/^refusing a cash-movement read/);
  expect(await rowsOf(db, STORES.cashMovementReads)).toEqual([]);
});

const typedAt = wib("2025-06-18T09:00:00");
const resumedAt = wib("2025-06-18T09:30:00");

test("everything recorded reads back as the record the halts are judged from", async () => {
  await recordValuation(db, portfolioAt("2025-06-17T16:02:00"), RULES);
  await recordValuation(db, portfolioAt("2025-06-16T16:02:00"), RULES);
  await recordCashMovements(db, movements);
  await recordTyped(db, { day: "2025-06-18", kind: "deposit", amount: rp(700_000n), typedAt });
  await recordTyped(db, {
    day: "2025-06-18",
    kind: "deposit",
    amount: rp(700_000n),
    typedAt: wib("2025-06-18T09:01:00"),
  });
  await recordAnswered(db, { from: "2025-06-18", to: "2025-06-18" }, typedAt);
  await recordResume(db, { haltDay: "2025-06-17", at: resumedAt, strategy: "buy-and-hold" });
  expect(await riskRecord(db)).toEqual({
    valuations: [
      {
        day: "2025-06-16",
        readAt: wib("2025-06-16T16:02:00"),
        value: rp(5_415_000n),
        invested: rp(4_600_000n),
      },
      {
        day: "2025-06-17",
        readAt: wib("2025-06-17T16:02:00"),
        value: rp(5_415_000n),
        invested: rp(4_600_000n),
      },
    ],
    movements: [
      { day: "2025-06-02", kind: "deposit", amount: rp(5_000_000n) },
      { day: "2025-06-10", kind: "withdrawal", amount: rp(250_000n), reference: "TX-9" },
    ],
    movementReads: [{ from: "2025-06-01", to: "2025-06-17", readAt: wib("2025-06-17T19:00:00") }],
    typed: [
      { day: "2025-06-18", kind: "deposit", amount: rp(700_000n), typedAt },
      {
        day: "2025-06-18",
        kind: "deposit",
        amount: rp(700_000n),
        typedAt: wib("2025-06-18T09:01:00"),
      },
    ],
    answered: [{ from: "2025-06-18", to: "2025-06-18" }],
    resumes: [{ haltDay: "2025-06-17", at: resumedAt, strategy: "buy-and-hold" }],
  });
});

test("an empty history reads back as an empty record", async () => {
  expect(await riskRecord(db)).toEqual({
    valuations: [],
    movements: [],
    movementReads: [],
    typed: [],
    answered: [],
    resumes: [],
  });
});

test("a row in a currency steadyhand does not know is refused by name", async () => {
  await recordTyped(db, {
    day: "2025-06-18",
    kind: "deposit",
    amount: new Money(1n, IDR),
    typedAt,
  });
  const write = db.transaction(STORES.typedMovements, "readwrite");
  write.objectStore(STORES.typedMovements).put({
    day: "2025-06-18",
    kind: "deposit",
    amount: "1",
    currency: "USD",
    typedAt: wib("2025-06-18T10:00:00"),
  });
  await new Promise((resolve) => {
    write.oncomplete = resolve;
  });
  await expect(riskRecord(db)).rejects.toThrow(/^a recorded amount is in USD, not IDR$/);
});
