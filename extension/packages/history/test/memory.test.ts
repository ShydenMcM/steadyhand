import { IDR, Money, monthlySavings, storedAfter } from "@steadyhand/core";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, expect, test } from "vitest";
import { remember, rememberedFor, rowsOf } from "../src/record.ts";
import { openHistory, STORES } from "../src/schema.ts";

// Strategy memory in the store (#229 AC1): kept with the advice day it was written for, so
// advising again that day starts from the memory the day began with.

let db: IDBDatabase;

beforeEach(async () => {
  db = await openHistory(new IDBFactory());
  return () => {
    db.close();
  };
});

const began = new Map([["set", "IDX:BBCA"]]);
const ended = new Map([["set", "IDX:BBCA IDX:TLKM"]]);

test("a strategy with nothing stored starts from no memory", async () => {
  expect(await rememberedFor(db, "buy-and-hold", "2025-06-17")).toEqual(new Map());
});

test("memory is kept with its advice day, what the day began with and ended with", async () => {
  await remember(db, "buy-and-hold", { day: "2025-06-17", began, ended });
  expect(await rowsOf(db, STORES.memory)).toEqual([
    { strategy: "buy-and-hold", day: "2025-06-17", began, ended },
  ]);
});

test("advising again on the same day starts from the memory that day began with", async () => {
  await remember(db, "buy-and-hold", { day: "2025-06-17", began, ended });
  expect(await rememberedFor(db, "buy-and-hold", "2025-06-17")).toEqual(began);
});

test("the next advice day starts from the memory the last one ended with", async () => {
  await remember(db, "buy-and-hold", { day: "2025-06-17", began, ended });
  expect(await rememberedFor(db, "buy-and-hold", "2025-06-18")).toEqual(ended);
});

test("each strategy keeps its own memory", async () => {
  await remember(db, "buy-and-hold", { day: "2025-06-17", began, ended });
  expect(await rememberedFor(db, "monthly-savings", "2025-06-17")).toEqual(new Map());
});

test("the advice for a day is the same however often it is asked for", async () => {
  const day = "2025-06-17";
  const view = {
    day,
    tradable: {
      day,
      buyable: new Set(["BBCA", "TLKM"]),
      sellable: new Set<string>(),
      reasons: new Map(),
      members: new Set(["BBCA", "TLKM"]),
    },
    closes: new Map(),
    dividends: new Map(),
    splits: [],
  };
  const portfolio = {
    value: new Money(1_000_000n, IDR),
    spendable: new Money(1_000_000n, IDR),
    holdings: new Map(),
  };
  const advise = async () => {
    const memory = await rememberedFor(db, monthlySavings().name, day);
    const decision = monthlySavings().decide(view, portfolio, memory);
    await remember(db, monthlySavings().name, storedAfter(day, memory, decision.memory));
    return decision;
  };
  const first = await advise();
  const again = await advise();
  expect([...again.weights].map(([symbol, weight]) => [symbol, weight.toString()])).toEqual(
    [...first.weights].map(([symbol, weight]) => [symbol, weight.toString()]),
  );
  expect(again.memory).toEqual(first.memory);
  expect(first.memory.get("due")).toBe("11");
});
