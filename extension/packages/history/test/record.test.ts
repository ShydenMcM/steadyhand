import {
  IDR,
  IdxCalendar,
  Money,
  RuleDecimal,
  shippedSessions,
  type CashMovements,
  type CorporateActions,
  type Dividends,
  type Part,
  type Portfolio,
  type Source,
  type StockDetail,
  type Watchlist,
} from "@steadyhand/core";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, expect, test } from "vitest";
import {
  recordCashMovements,
  recordCloses,
  recordCorporateActions,
  recordDividends,
  recordSeries,
  rowsOf,
} from "../src/record.ts";
import { openHistory, STORES } from "../src/schema.ts";

// What a read records (spec §6.2, #231 AC2-AC4), on an in-memory IndexedDB per test. The week of
// Monday 16 June 2025 has no IDX holiday; Saturday the 21st is not a trading day.

const RULES = { calendar: IdxCalendar.shipped(), sessions: shippedSessions() };
const rp = (amount: bigint): Money => new Money(amount, IDR);
const wib = (time: string): Date => new Date(`${time}+07:00`);
const source = (pageKind: Source["pageKind"]): Source => ({
  broker: "fixture",
  pageKind,
  route: "page",
});

const portfolioAt = (time: string): Part<Portfolio> => ({
  source: source("portfolio"),
  readAt: wib(time),
  value: {
    cashAvailable: rp(1_000_000n),
    cashSettled: rp(1_000_000n),
    cashUnsettled: rp(0n),
    holdings: [
      { symbol: "BBCA", lots: 2n, averagePrice: rp(8_500n), lastPrice: rp(9_025n) },
      { symbol: "TLKM", lots: 10n, averagePrice: rp(2_900n), lastPrice: rp(2_710n) },
    ],
  },
});

const watchlistAt = (time: string): Part<Watchlist> => ({
  source: source("watchlist"),
  readAt: wib(time),
  value: { stocks: [{ symbol: "BBRI", lastPrice: rp(4_120n) }] },
});

let db: IDBDatabase;

beforeEach(async () => {
  db = await openHistory(new IDBFactory());
  return () => {
    db.close();
  };
});

const closeRow = (symbol: string, day: string, close: bigint, pageKind: Source["pageKind"]) => ({
  symbol,
  day,
  close,
  currency: "IDR",
  source: source(pageKind),
});

test("a portfolio read at 16:02:00 WIB on a trading day records that day's close per holding", async () => {
  expect(await recordCloses(db, portfolioAt("2025-06-17T16:02:00"), RULES)).toBe("2025-06-17");
  expect(await rowsOf(db, STORES.closes)).toEqual([
    closeRow("BBCA", "2025-06-17", 9_025n, "portfolio"),
    closeRow("TLKM", "2025-06-17", 2_710n, "portfolio"),
  ]);
});

test("a watchlist read records that day's close per watched stock", async () => {
  await recordCloses(db, watchlistAt("2025-06-17T20:00:00"), RULES);
  expect(await rowsOf(db, STORES.closes)).toEqual([
    closeRow("BBRI", "2025-06-17", 4_120n, "watchlist"),
  ]);
});

test("a read one second before the close is final records no close", async () => {
  expect(await recordCloses(db, portfolioAt("2025-06-17T16:01:59"), RULES)).toBeNull();
  expect(await rowsOf(db, STORES.closes)).toEqual([]);
});

test("a read before the next pre-opening records the previous trading day's close", async () => {
  expect(await recordCloses(db, portfolioAt("2025-06-18T08:44:59"), RULES)).toBe("2025-06-17");
});

test("a read from the next pre-opening on, in the session, records no close", async () => {
  expect(await recordCloses(db, portfolioAt("2025-06-18T08:45:00"), RULES)).toBeNull();
  expect(await rowsOf(db, STORES.closes)).toEqual([]);
});

test("a read on a Saturday records Friday's close", async () => {
  expect(await recordCloses(db, watchlistAt("2025-06-21T11:00:00"), RULES)).toBe("2025-06-20");
});

test("a stock read twice for the same day is one close, the later read's", async () => {
  await recordCloses(db, watchlistAt("2025-06-17T16:30:00"), RULES);
  const later: Part<Watchlist> = {
    ...watchlistAt("2025-06-17T19:00:00"),
    value: { stocks: [{ symbol: "BBRI", lastPrice: rp(4_130n) }] },
  };
  await recordCloses(db, later, RULES);
  expect(await rowsOf(db, STORES.closes)).toEqual([
    closeRow("BBRI", "2025-06-17", 4_130n, "watchlist"),
  ]);
});

const detail: Part<StockDetail> = {
  source: source("stock-detail"),
  readAt: wib("2025-06-17T19:00:00"),
  value: {
    symbol: "BBCA",
    covered: { from: "2025-06-16", to: "2025-06-17" },
    closes: [
      { day: "2025-06-16", close: rp(9_000n) },
      { day: "2025-06-17", close: rp(9_025n) },
    ],
  },
};

test("a stock detail read records the chart series as shown, with the reader's adjustment", async () => {
  await recordSeries(db, detail, "splits");
  expect(await rowsOf(db, STORES.series)).toEqual([
    {
      symbol: "BBCA",
      readAt: "2025-06-17T12:00:00.000Z",
      adjustment: "splits",
      covered: { from: "2025-06-16", to: "2025-06-17" },
      closes: [
        { day: "2025-06-16", close: 9_000n, currency: "IDR" },
        { day: "2025-06-17", close: 9_025n, currency: "IDR" },
      ],
      source: source("stock-detail"),
    },
  ]);
});

test("each chart series read is kept, by its read instant", async () => {
  await recordSeries(db, detail, "none");
  await recordSeries(db, { ...detail, readAt: wib("2025-06-18T19:00:00") }, "none");
  expect((await rowsOf(db, STORES.series)).length).toBe(2);
});

const dividends: Part<Dividends> = {
  source: source("dividends"),
  readAt: wib("2025-06-17T19:00:00"),
  value: {
    symbol: "BBRI",
    covered: { from: "2025-01-01", to: "2025-06-17" },
    dividends: [
      {
        symbol: "BBRI",
        exDate: "2025-03-25",
        paymentDate: "2025-04-15",
        grossPerShare: new RuleDecimal("208.40"),
      },
      {
        symbol: "BBRI",
        exDate: "2025-05-27",
        paymentDate: "2025-06-13",
        grossPerShare: new RuleDecimal("210"),
      },
    ],
  },
};

test("dividend rows are recorded once each: reading the page twice changes nothing", async () => {
  await recordDividends(db, dividends);
  const once = await rowsOf(db, STORES.dividends);
  await recordDividends(db, { ...dividends, readAt: wib("2025-06-18T19:00:00") });
  expect(await rowsOf(db, STORES.dividends)).toEqual(once);
  expect(once).toEqual([
    {
      symbol: "BBRI",
      exDate: "2025-03-25",
      paymentDate: "2025-04-15",
      grossPerShare: "208.4",
      entry: "#1",
    },
    {
      symbol: "BBRI",
      exDate: "2025-05-27",
      paymentDate: "2025-06-13",
      grossPerShare: "210",
      entry: "#1",
    },
  ]);
});

// #230 AC3, spec §7.1: a dividend read records the period it covers for its stock, so a year
// inside it with no dividend is known to have none, and a year outside it is unread.
test("a dividend read records its stock's period once, however often the page is read", async () => {
  await recordDividends(db, dividends);
  await recordDividends(db, { ...dividends, readAt: wib("2025-06-18T19:00:00") });
  expect(await rowsOf(db, STORES.dividendReads)).toEqual([
    { symbol: "BBRI", from: "2025-01-01", to: "2025-06-17" },
  ]);
});

test("a dividend read listing no dividend still records the period it covers", async () => {
  await recordDividends(db, { ...dividends, value: { ...dividends.value, dividends: [] } });
  expect(await rowsOf(db, STORES.dividends)).toEqual([]);
  expect(await rowsOf(db, STORES.dividendReads)).toEqual([
    { symbol: "BBRI", from: "2025-01-01", to: "2025-06-17" },
  ]);
});

test("dividend reads of two periods are two periods", async () => {
  await recordDividends(db, dividends);
  const earlier = { from: "2019-01-01", to: "2024-12-31" };
  await recordDividends(db, { ...dividends, value: { ...dividends.value, covered: earlier } });
  expect(await rowsOf(db, STORES.dividendReads)).toEqual([
    { symbol: "BBRI", ...earlier },
    { symbol: "BBRI", from: "2025-01-01", to: "2025-06-17" },
  ]);
});

test("two identical dividend rows in one read are two dividends, read twice or not (#470)", async () => {
  const twice = dividends.value.dividends[0];
  if (twice === undefined) {
    throw new Error("the fixture lists no dividend");
  }
  const read = { ...dividends, value: { ...dividends.value, dividends: [twice, twice] } };
  await recordDividends(db, read);
  await recordDividends(db, read);
  expect(
    (await rowsOf(db, STORES.dividends)).map((row) => (row as { entry: string }).entry),
  ).toEqual(["#1", "#2"]);
});

test("a dividend the broker numbers is keyed by its number (#470)", async () => {
  const numbered = dividends.value.dividends.map((dividend) => ({
    ...dividend,
    reference: "DV-1",
  }));
  await recordDividends(db, { ...dividends, value: { ...dividends.value, dividends: numbered } });
  expect(
    (await rowsOf(db, STORES.dividends)).map((row) => (row as { entry: string }).entry),
  ).toEqual(["ref DV-1", "ref DV-1"]);
});

const movements: Part<CashMovements> = {
  source: source("cash-movements"),
  readAt: wib("2025-06-17T19:00:00"),
  value: {
    covered: { from: "2025-06-01", to: "2025-06-17" },
    movements: [
      { day: "2025-06-02", kind: "deposit", amount: rp(5_000_000n) },
      { day: "2025-06-10", kind: "withdrawal", amount: rp(250_000n) },
    ],
    totals: { deposits: rp(5_000_000n), withdrawals: rp(250_000n) },
  },
};

test("cash movements are recorded once each: reading the page twice changes nothing", async () => {
  await recordCashMovements(db, movements);
  await recordCashMovements(db, movements);
  expect(await rowsOf(db, STORES.cashMovements)).toEqual([
    { day: "2025-06-02", kind: "deposit", amount: "5000000", currency: "IDR", entry: "#1" },
    { day: "2025-06-10", kind: "withdrawal", amount: "250000", currency: "IDR", entry: "#1" },
  ]);
});

const deposit = { day: "2025-06-02", kind: "deposit" as const, amount: rp(1_000_000n) };
const twoDeposits = { deposits: rp(2_000_000n), withdrawals: rp(0n) };

test("two equal deposits on one day are both kept, and a second read adds neither (#470)", async () => {
  const read = {
    ...movements,
    value: { ...movements.value, movements: [deposit, deposit], totals: twoDeposits },
  };
  await recordCashMovements(db, read);
  await recordCashMovements(db, read);
  expect(await rowsOf(db, STORES.cashMovements)).toEqual([
    { day: "2025-06-02", kind: "deposit", amount: "1000000", currency: "IDR", entry: "#1" },
    { day: "2025-06-02", kind: "deposit", amount: "1000000", currency: "IDR", entry: "#2" },
  ]);
});

test("a movement the broker numbers is keyed by its number (#470)", async () => {
  const read = {
    ...movements,
    value: {
      ...movements.value,
      movements: [
        { ...deposit, reference: "TX-0042" },
        { ...deposit, reference: "TX-0043" },
      ],
      totals: twoDeposits,
    },
  };
  await recordCashMovements(db, read);
  await recordCashMovements(db, read);
  expect(await rowsOf(db, STORES.cashMovements)).toEqual([
    {
      day: "2025-06-02",
      kind: "deposit",
      amount: "1000000",
      currency: "IDR",
      reference: "TX-0042",
      entry: "ref TX-0042",
    },
    {
      day: "2025-06-02",
      kind: "deposit",
      amount: "1000000",
      currency: "IDR",
      reference: "TX-0043",
      entry: "ref TX-0043",
    },
  ]);
});

test("a cash read whose rows fall short of its totals is refused and nothing is written (#477)", async () => {
  const cut = {
    ...movements,
    value: { ...movements.value, movements: [deposit], totals: twoDeposits },
  };
  await expect(recordCashMovements(db, cut)).rejects.toThrow(
    "refusing a cash-movement read: deposits: the page shows 2000000, its rows add up to 1000000",
  );
  expect(await rowsOf(db, STORES.cashMovements)).toEqual([]);
});

const actions: Part<CorporateActions> = {
  source: source("corporate-actions"),
  readAt: wib("2025-06-17T19:00:00"),
  value: {
    covered: { from: "2025-01-01", to: "2025-06-17" },
    splits: [{ symbol: "BBCA", exDate: "2025-02-03", from: 1n, to: 5n }],
  },
};

test("corporate actions are recorded once each: reading the page twice changes nothing", async () => {
  await recordCorporateActions(db, actions);
  await recordCorporateActions(db, actions);
  expect(await rowsOf(db, STORES.corporateActions)).toEqual([
    { symbol: "BBCA", exDate: "2025-02-03", from: "1", to: "5", entry: "#1" },
  ]);
});

// #480: the page lists every stock's splits, so the period a read covers settles an action found
// by price inside it, split or none.
test("a corporate action read records its period once, however often the page is read", async () => {
  await recordCorporateActions(db, actions);
  await recordCorporateActions(db, { ...actions, readAt: wib("2025-06-18T19:00:00") });
  expect(await rowsOf(db, STORES.corporateActionReads)).toEqual([
    { from: "2025-01-01", to: "2025-06-17" },
  ]);
});

test("a corporate action read listing no split still records the period it covers", async () => {
  await recordCorporateActions(db, { ...actions, value: { ...actions.value, splits: [] } });
  expect(await rowsOf(db, STORES.corporateActions)).toEqual([]);
  expect(await rowsOf(db, STORES.corporateActionReads)).toEqual([
    { from: "2025-01-01", to: "2025-06-17" },
  ]);
});

test("corporate action reads of two periods are two periods", async () => {
  await recordCorporateActions(db, actions);
  const earlier = { from: "2019-01-01", to: "2024-12-31" };
  await recordCorporateActions(db, { ...actions, value: { ...actions.value, covered: earlier } });
  expect(await rowsOf(db, STORES.corporateActionReads)).toEqual([
    earlier,
    { from: "2025-01-01", to: "2025-06-17" },
  ]);
});

test("a split the broker numbers is keyed by its number, and an identical one apart (#470)", async () => {
  const split = { symbol: "BBCA", exDate: "2025-02-03", from: 1n, to: 5n };
  const read = {
    ...actions,
    value: { ...actions.value, splits: [split, split, { ...split, reference: "CA-7" }] },
  };
  await recordCorporateActions(db, read);
  await recordCorporateActions(db, read);
  expect(
    (await rowsOf(db, STORES.corporateActions)).map((row) => (row as { entry: string }).entry),
  ).toEqual(["#1", "#2", "ref CA-7"]);
});
