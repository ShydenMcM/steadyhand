import { IDBFactory } from "fake-indexeddb";
import { expect, test } from "vitest";
import { DATABASE, MIGRATIONS, openHistory, requested, STORES, VERSION } from "../src/schema.ts";

// The store (spec §6.1, #231 AC1) on an in-memory IndexedDB, a fresh one per test.

test("the database is the extension's own, at the newest version its migrations reach", () => {
  expect(DATABASE).toBe("steadyhand-history");
  expect(VERSION).toBe(MIGRATIONS.length);
});

test("a new database has one store per kind, each keyed by its own fields", async () => {
  const db = await openHistory(new IDBFactory());
  expect(db.version).toBe(1);
  expect([...db.objectStoreNames].sort()).toEqual([
    "cash-movements",
    "chart-series",
    "closes",
    "corporate-actions",
    "dividends",
    "memory",
    "settings",
  ]);
  const read = db.transaction([...db.objectStoreNames], "readonly");
  expect(
    Object.fromEntries(
      [...db.objectStoreNames].map((name) => [name, read.objectStore(name).keyPath]),
    ),
  ).toEqual({
    "cash-movements": ["day", "kind", "amount"],
    "chart-series": ["symbol", "readAt"],
    closes: ["symbol", "day"],
    "corporate-actions": ["symbol", "exDate", "from", "to"],
    dividends: ["symbol", "exDate", "paymentDate", "grossPerShare"],
    memory: "strategy",
    settings: "name",
  });
  expect(Object.values(STORES).sort()).toEqual([...db.objectStoreNames].sort());
  db.close();
});

test("reopening the database keeps what was written", async () => {
  const factory = new IDBFactory();
  const first = await openHistory(factory);
  const write = first.transaction(STORES.settings, "readwrite");
  await requested(write.objectStore(STORES.settings).put({ name: "fees", value: "custom" }));
  first.close();
  const again = await openHistory(factory);
  const read = again.transaction(STORES.settings, "readonly");
  expect(await requested(read.objectStore(STORES.settings).get("fees"))).toEqual({
    name: "fees",
    value: "custom",
  });
  again.close();
});

test("an upgrade runs each migration after the version the database is at, in order", async () => {
  const factory = new IDBFactory();
  const ran: string[] = [];
  const steps = [
    (db: IDBDatabase) => {
      ran.push("first");
      db.createObjectStore("a");
    },
    (db: IDBDatabase) => {
      ran.push("second");
      db.createObjectStore("b");
    },
  ];
  (await openHistory(factory, steps.slice(0, 1))).close();
  expect(ran).toEqual(["first"]);
  const upgraded = await openHistory(factory, steps);
  expect(ran).toEqual(["first", "second"]);
  expect([...upgraded.objectStoreNames].sort()).toEqual(["a", "b"]);
  upgraded.close();
});

test("a database a newer release wrote is refused by name, not read", async () => {
  const factory = new IDBFactory();
  const newer = await requested(factory.open(DATABASE, VERSION + 1));
  newer.close();
  await expect(openHistory(factory)).rejects.toThrow(
    new Error("steadyhand-history is at a newer version than this release reads (1)"),
  );
});

test("a database held open by another tab is refused by name, not waited on", async () => {
  const factory = new IDBFactory();
  const held = await openHistory(factory, MIGRATIONS);
  held.onversionchange = null;
  const store = (name: string) => (db: IDBDatabase) => db.createObjectStore(name);
  const upgrade = openHistory(factory, [...MIGRATIONS, store("c")]);
  await expect(upgrade).rejects.toThrow(
    new Error("steadyhand-history is open in another tab of an older release: close it first"),
  );
  held.close();
  // Once the other tab closes, the refused upgrade completes and its connection is closed at
  // once: a connection left open would block the next upgrade, which is refused when blocked.
  const next = await openHistory(factory, [...MIGRATIONS, store("c"), store("d")]);
  expect([...next.objectStoreNames]).toContain("d");
  next.close();
});
