import { readFileSync } from "node:fs";
import {
  IdxCalendar,
  IdxMarketRules,
  IDR,
  Money,
  shippedSessions,
  type PageKind,
  type PartValues,
  type Part,
} from "@steadyhand/core";
import {
  corporateActionRecord,
  dividendRecord,
  openHistory,
  putSetting,
  recordedCloses,
  remember,
  riskRecord,
  rowsOf,
  STORES,
} from "@steadyhand/history";
import { FIXTURE_READERS } from "@steadyhand/readers";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, expect, test } from "vitest";
import type { PanelReads } from "../src/advice-model.ts";
import { recordedFrom, recordRead, SETTINGS } from "../src/record-read.ts";

// The panel records each broker page it is sent and reads the record back to advise (spec §7.1,
// §10.2, #238): the page names its kind, the broker's reader of that kind reads it, history
// records what it shows, and the portfolio, watchlist and flags stay in the panel's reads.

const RULES = {
  calendar: IdxCalendar.shipped(),
  sessions: shippedSessions(),
  market: new IdxMarketRules(),
};

/** A Tuesday evening after the close, and the same Tuesday mid-session. */
const AFTER_CLOSE = new Date("2025-06-17T19:00:00+07:00");
const IN_SESSION = new Date("2025-06-17T10:00:00+07:00");
const NO_READS: PanelReads = {};

const PAGES = new URL("../../readers/fixtures/fixture-broker/", import.meta.url);
const page = (kind: PageKind): string => readFileSync(new URL(`${kind}.html`, PAGES), "utf8");

/** What the fixture broker's reader makes of its own page of `kind`. */
const partOf = <K extends PageKind>(kind: K, readAt: Date): Part<PartValues[K]> => {
  const read = FIXTURE_READERS[kind]({ route: "page", text: page(kind) }, readAt);
  if ("refused" in read) {
    throw new Error(read.refused);
  }
  return read.part;
};

let db: IDBDatabase;

beforeEach(async () => {
  db = await openHistory(new IDBFactory());
  return () => {
    db.close();
  };
});

/** Every store a read can write to. */
const READ_STORES = [
  STORES.closes,
  STORES.series,
  STORES.dividends,
  STORES.dividendReads,
  STORES.cashMovements,
  STORES.cashMovementReads,
  STORES.corporateActions,
  STORES.corporateActionReads,
  STORES.valuations,
];

const everyStoreEmpty = async (): Promise<void> => {
  for (const store of READ_STORES) {
    expect(await rowsOf(db, store)).toEqual([]);
  }
};

test("a page naming no page kind is refused and nothing is recorded", async () => {
  expect(await recordRead(db, "<main>hello</main>", AFTER_CLOSE, NO_READS, RULES)).toEqual({
    refused: "the page names no page kind",
  });
  await everyStoreEmpty();
});

test("a page its reader refuses is refused with the reader's reason and nothing is recorded", async () => {
  const broken = page("portfolio").replace(/<table[\s\S]*<\/table>/u, "");
  const outcome = await recordRead(db, broken, AFTER_CLOSE, NO_READS, RULES);
  expect(outcome).toHaveProperty("refused");
  expect(outcome).not.toHaveProperty("reads");
  await everyStoreEmpty();
});

test("a portfolio read after the close records its closes and the portfolio's value", async () => {
  const outcome = await recordRead(db, page("portfolio"), AFTER_CLOSE, NO_READS, RULES);
  const part = partOf("portfolio", AFTER_CLOSE);
  expect(outcome).toEqual({ kind: "portfolio", reads: { portfolio: part } });
  const closes = await recordedCloses(db);
  expect([...closes.keys()].sort()).toEqual(part.value.holdings.map((held) => held.symbol).sort());
  for (const held of part.value.holdings) {
    expect(closes.get(held.symbol)).toEqual([{ day: "2025-06-17", close: held.lastPrice }]);
  }
  expect(await rowsOf(db, STORES.valuations)).toHaveLength(1);
});

test("a portfolio read mid-session is kept but records nothing: it shows no close", async () => {
  const outcome = await recordRead(db, page("portfolio"), IN_SESSION, NO_READS, RULES);
  expect(outcome).toEqual({
    kind: "portfolio",
    reads: { portfolio: partOf("portfolio", IN_SESSION) },
  });
  await everyStoreEmpty();
});

test("a watchlist read records its closes and keeps the portfolio already read", async () => {
  const portfolio = partOf("portfolio", AFTER_CLOSE);
  const outcome = await recordRead(db, page("watchlist"), AFTER_CLOSE, { portfolio }, RULES);
  const part = partOf("watchlist", AFTER_CLOSE);
  expect(outcome).toEqual({ kind: "watchlist", reads: { portfolio, watchlist: part } });
  const closes = await recordedCloses(db);
  for (const stock of part.value.stocks) {
    expect(closes.get(stock.symbol)).toEqual([{ day: "2025-06-17", close: stock.lastPrice }]);
  }
  expect(await rowsOf(db, STORES.valuations)).toEqual([]);
});

test("a stock detail read records its chart as shown, unadjusted: the fixture broker's chart is raw", async () => {
  const outcome = await recordRead(db, page("stock-detail"), AFTER_CLOSE, NO_READS, RULES);
  expect(outcome).toEqual({ kind: "stock-detail", reads: NO_READS });
  const part = partOf("stock-detail", AFTER_CLOSE);
  expect(await rowsOf(db, STORES.series)).toEqual([
    expect.objectContaining({
      symbol: part.value.symbol,
      readAt: AFTER_CLOSE.toISOString(),
      adjustment: "none",
    }),
  ]);
});

test("a dividends read records the stock's dividends and the period read", async () => {
  const outcome = await recordRead(db, page("dividends"), AFTER_CLOSE, NO_READS, RULES);
  expect(outcome).toEqual({ kind: "dividends", reads: NO_READS });
  const part = partOf("dividends", AFTER_CLOSE);
  const recorded = await dividendRecord(db);
  expect([...recorded.keys()]).toEqual([part.value.symbol]);
  expect(recorded.get(part.value.symbol)?.covered).toEqual(part.value.covered);
  expect(recorded.get(part.value.symbol)?.dividends).toHaveLength(part.value.dividends.length);
});

test("a cash movements read records every movement", async () => {
  const outcome = await recordRead(db, page("cash-movements"), AFTER_CLOSE, NO_READS, RULES);
  expect(outcome).toEqual({ kind: "cash-movements", reads: NO_READS });
  const part = partOf("cash-movements", AFTER_CLOSE);
  expect(await rowsOf(db, STORES.cashMovements)).toHaveLength(part.value.movements.length);
  expect(await rowsOf(db, STORES.cashMovementReads)).toEqual([
    { ...part.value.covered, readAt: part.readAt },
  ]);
});

test("a corporate actions read records every split and the period read", async () => {
  const outcome = await recordRead(db, page("corporate-actions"), AFTER_CLOSE, NO_READS, RULES);
  expect(outcome).toEqual({ kind: "corporate-actions", reads: NO_READS });
  const part = partOf("corporate-actions", AFTER_CLOSE);
  expect(await corporateActionRecord(db)).toEqual({
    splits: part.value.splits,
    reads: [part.value.covered],
  });
});

test("a flags read is kept in the panel's reads alone", async () => {
  const outcome = await recordRead(db, page("flags"), AFTER_CLOSE, NO_READS, RULES);
  expect(outcome).toEqual({ kind: "flags", reads: { flags: partOf("flags", AFTER_CLOSE) } });
  await everyStoreEmpty();
});

test("an empty record reads back as nothing recorded and nothing set", async () => {
  expect(await recordedFrom(db, "dividend-growth")).toEqual({
    closes: new Map(),
    dividends: new Map(),
    splits: [],
    actionReads: [],
    risk: await riskRecord(db),
    stored: undefined,
    universe: undefined,
    excluded: new Map(),
    goal: undefined,
  });
});

test("the record reads back with the strategy's memory and the settings kept", async () => {
  await recordRead(db, page("portfolio"), AFTER_CLOSE, NO_READS, RULES);
  await recordRead(db, page("dividends"), AFTER_CLOSE, NO_READS, RULES);
  await recordRead(db, page("corporate-actions"), AFTER_CLOSE, NO_READS, RULES);
  const stored = { day: "2025-06-17", began: new Map(), ended: new Map([["a", "b"]]) };
  await remember(db, "dividend-growth", stored);
  await remember(db, "buy-and-hold", { ...stored, day: "2025-06-16" });
  await putSetting(db, SETTINGS.universe, ["BBCA", "TLKM"]);
  await putSetting(db, SETTINGS.excluded, [["TLKM", "sold the business"]]);
  await putSetting(db, SETTINGS.goal, "1500000");
  const actions = await corporateActionRecord(db);
  expect(await recordedFrom(db, "dividend-growth")).toEqual({
    closes: await recordedCloses(db),
    dividends: await dividendRecord(db),
    splits: actions.splits,
    actionReads: actions.reads,
    risk: await riskRecord(db),
    stored,
    universe: ["BBCA", "TLKM"],
    excluded: new Map([["TLKM", "sold the business"]]),
    goal: new Money(1500000n, IDR),
  });
});

test.each([
  [SETTINGS.universe, "BBCA"],
  [SETTINGS.universe, ["BBCA", 7n]],
  [SETTINGS.excluded, "TLKM"],
  [SETTINGS.excluded, [["TLKM"]]],
  [SETTINGS.excluded, [["TLKM", 7n]]],
  [SETTINGS.goal, 1500000n],
  [SETTINGS.goal, "1.5 million"],
])("the setting %s kept as %s is refused, naming it", async (name, value) => {
  await putSetting(db, name, value);
  await expect(recordedFrom(db, "dividend-growth")).rejects.toThrow(`the setting ${name}`);
});
