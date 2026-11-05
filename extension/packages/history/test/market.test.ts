import {
  IDR,
  Money,
  RuleDecimal,
  type CorporateActions,
  type Dividends,
  type Part,
  type Source,
} from "@steadyhand/core";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, expect, test } from "vitest";
import { recordedCloses, dividendRecord, corporateActionRecord, settingOf } from "../src/market.ts";
import { putAll, putSetting, recordCorporateActions, recordDividends } from "../src/record.ts";
import { openHistory, STORES } from "../src/schema.ts";

// What the panel reads back to advise (#238): each stock's recorded closes, its dividend read and
// the period it covers, every split and corporate action read, and the settings.

let db: IDBDatabase;

beforeEach(async () => {
  db = await openHistory(new IDBFactory());
  return () => {
    db.close();
  };
});

const rp = (amount: bigint): Money => new Money(amount, IDR);
const at = new Date("2025-06-17T19:00:00+07:00");
const source = (pageKind: Source["pageKind"]): Source => ({
  broker: "fixture",
  pageKind,
  route: "page",
});

const closeRow = (symbol: string, day: string, close: bigint, currency = "IDR") => ({
  symbol,
  day,
  close,
  currency,
  source: source("portfolio"),
});

test("nothing recorded reads back as no closes", async () => {
  expect(await recordedCloses(db)).toEqual(new Map());
});

test("each stock's recorded closes read back in day order, as rupiah", async () => {
  await putAll(db, STORES.closes, [
    closeRow("TLKM", "2025-06-17", 2750n),
    closeRow("BBCA", "2025-06-17", 9100n),
    closeRow("BBCA", "2025-06-16", 9050n),
  ]);
  expect(await recordedCloses(db)).toEqual(
    new Map([
      [
        "BBCA",
        [
          { day: "2025-06-16", close: rp(9050n) },
          { day: "2025-06-17", close: rp(9100n) },
        ],
      ],
      ["TLKM", [{ day: "2025-06-17", close: rp(2750n) }]],
    ]),
  );
});

test("a close recorded in another currency is refused, naming it", async () => {
  await putAll(db, STORES.closes, [closeRow("BBCA", "2025-06-17", 9100n, "USD")]);
  await expect(recordedCloses(db)).rejects.toThrow("a recorded amount is in USD, not IDR");
});

const dividendRead = (
  symbol: string,
  from: string,
  to: string,
  rows: Dividends["dividends"] = [],
): Part<Dividends> => ({
  source: source("dividends"),
  readAt: at,
  value: { symbol, covered: { from, to }, dividends: rows },
});

const bbri = [
  {
    symbol: "BBRI",
    exDate: "2025-03-25",
    paymentDate: "2025-04-15",
    grossPerShare: new RuleDecimal("208.40"),
    reference: "DV-1",
  },
  {
    symbol: "BBRI",
    exDate: "2025-05-27",
    paymentDate: "2025-06-13",
    grossPerShare: new RuleDecimal("210"),
  },
];

/** A dividend record with each amount as text, so equal amounts compare equal however written. */
const asText = (record: ReadonlyMap<string, Dividends>) =>
  new Map(
    [...record].map(([symbol, read]) => [
      symbol,
      {
        ...read,
        dividends: read.dividends.map((row) => ({
          ...row,
          grossPerShare: row.grossPerShare.toString(),
        })),
      },
    ]),
  );

test("nothing read reads back as no dividend record", async () => {
  expect(await dividendRecord(db)).toEqual(new Map());
});

test("a stock's dividends read back with the period its read covers, references kept", async () => {
  await recordDividends(db, dividendRead("BBRI", "2025-01-01", "2025-06-17", bbri));
  expect(asText(await dividendRecord(db))).toEqual(
    new Map([
      [
        "BBRI",
        {
          symbol: "BBRI",
          covered: { from: "2025-01-01", to: "2025-06-17" },
          dividends: [
            {
              symbol: "BBRI",
              exDate: "2025-03-25",
              paymentDate: "2025-04-15",
              grossPerShare: "208.4",
              reference: "DV-1",
            },
            {
              symbol: "BBRI",
              exDate: "2025-05-27",
              paymentDate: "2025-06-13",
              grossPerShare: "210",
            },
          ],
        },
      ],
    ]),
  );
});

test("a read that lists no dividend still covers its period", async () => {
  await recordDividends(db, dividendRead("UNVR", "2020-01-01", "2025-06-17"));
  expect(await dividendRecord(db)).toEqual(
    new Map([
      [
        "UNVR",
        { symbol: "UNVR", covered: { from: "2020-01-01", to: "2025-06-17" }, dividends: [] },
      ],
    ]),
  );
});

test("dividends recorded with no read of their period are not known: the stock is absent", async () => {
  await putAll(db, STORES.dividends, [
    {
      symbol: "BBRI",
      exDate: "2025-03-25",
      paymentDate: "2025-04-15",
      grossPerShare: "208.4",
      entry: "#1",
    },
  ]);
  expect(await dividendRecord(db)).toEqual(new Map());
});

const coveredOf = async (symbol: string) => (await dividendRecord(db)).get(symbol)?.covered;

test("overlapping reads of one stock cover their joined period", async () => {
  await recordDividends(db, dividendRead("BBRI", "2019-01-01", "2023-06-30"));
  await recordDividends(db, dividendRead("BBRI", "2023-01-01", "2025-06-17"));
  expect(await coveredOf("BBRI")).toEqual({ from: "2019-01-01", to: "2025-06-17" });
});

test("a read starting the day after another ends joins it", async () => {
  await recordDividends(db, dividendRead("BBRI", "2019-01-01", "2022-12-31"));
  await recordDividends(db, dividendRead("BBRI", "2023-01-01", "2025-06-17"));
  expect(await coveredOf("BBRI")).toEqual({ from: "2019-01-01", to: "2025-06-17" });
});

test("reads with a gap between them cover the latest joined period alone", async () => {
  await recordDividends(db, dividendRead("BBRI", "2019-01-01", "2022-12-30"));
  await recordDividends(db, dividendRead("BBRI", "2023-01-01", "2025-06-17"));
  expect(await coveredOf("BBRI")).toEqual({ from: "2023-01-01", to: "2025-06-17" });
});

test("a read inside a wider one leaves the wider period", async () => {
  await recordDividends(db, dividendRead("BBRI", "2015-01-01", "2025-06-17"));
  await recordDividends(db, dividendRead("BBRI", "2020-01-01", "2021-12-31"));
  expect(await coveredOf("BBRI")).toEqual({ from: "2015-01-01", to: "2025-06-17" });
});

test("each stock's period is its own reads' alone", async () => {
  await recordDividends(db, dividendRead("BBRI", "2019-01-01", "2025-06-17"));
  await recordDividends(db, dividendRead("TLKM", "2024-01-01", "2025-06-17"));
  expect(await coveredOf("TLKM")).toEqual({ from: "2024-01-01", to: "2025-06-17" });
});

test("nothing read reads back as no splits and no corporate action reads", async () => {
  expect(await corporateActionRecord(db)).toEqual({ splits: [], reads: [] });
});

test("every split and each corporate action read's period read back", async () => {
  const read: Part<CorporateActions> = {
    source: source("corporate-actions"),
    readAt: at,
    value: {
      covered: { from: "2020-01-01", to: "2025-06-17" },
      splits: [
        { symbol: "BBCA", exDate: "2021-10-13", from: 1n, to: 5n, reference: "CA-9" },
        { symbol: "TLKM", exDate: "2024-03-01", from: 10n, to: 1n },
      ],
    },
  };
  await recordCorporateActions(db, read);
  expect(await corporateActionRecord(db)).toEqual({
    splits: [
      { symbol: "BBCA", exDate: "2021-10-13", from: 1n, to: 5n, reference: "CA-9" },
      { symbol: "TLKM", exDate: "2024-03-01", from: 10n, to: 1n },
    ],
    reads: [{ from: "2020-01-01", to: "2025-06-17" }],
  });
});

test("a setting never kept reads back as undefined", async () => {
  expect(await settingOf(db, "universe")).toBeUndefined();
});

test("a setting reads back as last kept", async () => {
  await putSetting(db, "universe", ["BBCA", "TLKM"]);
  await putSetting(db, "universe", ["BBRI"]);
  expect(await settingOf(db, "universe")).toEqual(["BBRI"]);
});
