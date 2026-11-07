import { IDBFactory } from "fake-indexeddb";
import { beforeEach, expect, test } from "vitest";
import { putAll } from "../src/record.ts";
import { openHistory, STORES } from "../src/schema.ts";
import { stockHistory } from "../src/summary.ts";

// The History tab (#239 AC2): per stock, the days recorded, the chart reads and the dividends.

let db: IDBDatabase;

beforeEach(async () => {
  db = await openHistory(new IDBFactory());
  return () => {
    db.close();
  };
});

const close = (symbol: string, day: string) => ({ symbol, day, close: "9000" });
const chartRead = (symbol: string, readAt: string) => ({ symbol, readAt, points: [] });
const dividend = (symbol: string, exDate: string) => ({
  symbol,
  exDate,
  paymentDate: exDate,
  grossPerShare: "100",
  entry: "#1",
});

test("nothing recorded is no stock", async () => {
  expect(await stockHistory(db)).toEqual([]);
});

test("each stock has its days, chart reads and dividends counted, by symbol", async () => {
  await putAll(db, STORES.closes, [
    close("TLKM", "2025-06-16"),
    close("BBCA", "2025-06-16"),
    close("BBCA", "2025-06-17"),
  ]);
  await putAll(db, STORES.series, [
    chartRead("BBCA", "2025-06-17T12:00:00.000Z"),
    chartRead("BBCA", "2025-06-18T12:00:00.000Z"),
    chartRead("ASII", "2025-06-18T12:00:00.000Z"),
  ]);
  await putAll(db, STORES.dividends, [
    dividend("BBCA", "2024-05-02"),
    dividend("TLKM", "2024-05-20"),
    dividend("TLKM", "2025-05-21"),
  ]);
  expect(await stockHistory(db)).toEqual([
    { symbol: "ASII", days: 0n, chartReads: 1n, dividends: 0n },
    { symbol: "BBCA", days: 2n, chartReads: 2n, dividends: 1n },
    { symbol: "TLKM", days: 1n, chartReads: 0n, dividends: 2n },
  ]);
});

test("a row with no stock code is refused, naming its store", async () => {
  await putAll(db, STORES.closes, [{ symbol: 7, day: "2025-06-16" }]);
  await expect(stockHistory(db)).rejects.toThrow("closes holds a row with no stock code");
});
