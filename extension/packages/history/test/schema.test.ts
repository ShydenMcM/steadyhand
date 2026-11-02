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
  expect(db.version).toBe(3);
  expect([...db.objectStoreNames].sort()).toEqual([
    "cash-movements",
    "chart-series",
    "closes",
    "corporate-actions",
    "dividend-reads",
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
    "cash-movements": ["day", "kind", "amount", "entry"],
    "chart-series": ["symbol", "readAt"],
    closes: ["symbol", "day"],
    "corporate-actions": ["symbol", "exDate", "from", "to", "entry"],
    "dividend-reads": ["symbol", "from", "to"],
    dividends: ["symbol", "exDate", "paymentDate", "grossPerShare", "entry"],
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
    new Error("steadyhand-history is at a newer version than this release reads (3)"),
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

test("a version 1 database keeps every row, each the first of its kind (#470)", async () => {
  const factory = new IDBFactory();
  const old = await openHistory(factory, MIGRATIONS.slice(0, 1));
  const write = old.transaction(
    [STORES.dividends, STORES.cashMovements, STORES.corporateActions],
    "readwrite",
  );
  write
    .objectStore(STORES.cashMovements)
    .put({ day: "2025-06-02", kind: "deposit", amount: "5000000" });
  write.objectStore(STORES.dividends).put({
    symbol: "BBRI",
    exDate: "2025-03-25",
    paymentDate: "2025-04-15",
    grossPerShare: "208.4",
  });
  write
    .objectStore(STORES.corporateActions)
    .put({ symbol: "BBCA", exDate: "2025-02-03", from: "1", to: "5" });
  await new Promise<void>((resolve) => {
    write.oncomplete = () => {
      resolve();
    };
  });
  old.close();
  const upgraded = await openHistory(factory);
  const read = upgraded.transaction(
    [STORES.dividends, STORES.cashMovements, STORES.corporateActions],
    "readonly",
  );
  expect(await requested(read.objectStore(STORES.cashMovements).getAll())).toEqual([
    { day: "2025-06-02", kind: "deposit", amount: "5000000", entry: "#1" },
  ]);
  expect(await requested(read.objectStore(STORES.dividends).getAll())).toEqual([
    {
      symbol: "BBRI",
      exDate: "2025-03-25",
      paymentDate: "2025-04-15",
      grossPerShare: "208.4",
      entry: "#1",
    },
  ]);
  expect(await requested(read.objectStore(STORES.corporateActions).getAll())).toEqual([
    { symbol: "BBCA", exDate: "2025-02-03", from: "1", to: "5", entry: "#1" },
  ]);
  upgraded.close();
});

// #230: dividends recorded before reads kept their period have no known period, so they count
// as unread until the page is read again: never a year "known" to have no dividend.
test("a version 2 database keeps its dividends and starts with no dividend period read", async () => {
  const factory = new IDBFactory();
  const old = await openHistory(factory, MIGRATIONS.slice(0, 2));
  const write = old.transaction(STORES.dividends, "readwrite");
  const dividend = {
    symbol: "BBRI",
    exDate: "2025-03-25",
    paymentDate: "2025-04-15",
    grossPerShare: "208.4",
    entry: "#1",
  };
  write.objectStore(STORES.dividends).put(dividend);
  await new Promise<void>((resolve) => {
    write.oncomplete = () => {
      resolve();
    };
  });
  old.close();
  const upgraded = await openHistory(factory);
  const read = upgraded.transaction([STORES.dividends, STORES.dividendReads], "readonly");
  expect(await requested(read.objectStore(STORES.dividends).getAll())).toEqual([dividend]);
  expect(await requested(read.objectStore(STORES.dividendReads).getAll())).toEqual([]);
  upgraded.close();
});
