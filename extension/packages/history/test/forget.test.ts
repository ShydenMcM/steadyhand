import { IDBFactory } from "fake-indexeddb";
import { expect, test } from "vitest";
import { forgetEverything, type ExtensionStorage } from "../src/forget.ts";
import { putMemory, putSetting, rowsOf } from "../src/record.ts";
import { DATABASE, openHistory, STORES } from "../src/schema.ts";

// "Forget everything" (spec §6.1, §11, #231 AC5): the database and the extension's storage are
// deleted, and both are read back empty, after every store was written.

/** The extension's storage (`chrome.storage.local`'s shape), stood in by a map. */
const storageOf = (items: Record<string, unknown>, clears = true): ExtensionStorage => {
  const held = new Map(Object.entries(items));
  return {
    get: () => Promise.resolve(Object.fromEntries(held)),
    clear: () => {
      if (clears) {
        held.clear();
      }
      return Promise.resolve();
    },
  };
};

/** One row in every store. */
const fill = async (db: IDBDatabase): Promise<void> => {
  const write = db.transaction(Object.values(STORES), "readwrite");
  const rows: Record<string, unknown> = {
    [STORES.closes]: { symbol: "BBCA", day: "2025-06-17" },
    [STORES.series]: { symbol: "BBCA", readAt: "2025-06-17T12:00:00.000Z" },
    [STORES.dividends]: {
      symbol: "BBRI",
      exDate: "2025-03-25",
      paymentDate: "2025-04-15",
      grossPerShare: "208.4",
    },
    [STORES.cashMovements]: { day: "2025-06-02", kind: "deposit", amount: "5000000" },
    [STORES.corporateActions]: { symbol: "BBCA", exDate: "2025-02-03", from: "1", to: "5" },
  };
  for (const [store, row] of Object.entries(rows)) {
    write.objectStore(store).put(row);
  }
  await new Promise<void>((resolve) => {
    write.oncomplete = () => {
      resolve();
    };
  });
  await putMemory(db, "buy-and-hold", "2025-06-17", { held: ["BBCA"] });
  await putSetting(db, "fees", "custom");
};

test("forgetting deletes the database and the storage, and reads both back empty", async () => {
  const factory = new IDBFactory();
  const db = await openHistory(factory);
  await fill(db);
  for (const store of Object.values(STORES)) {
    expect((await rowsOf(db, store)).length, store).toBe(1);
  }
  const storage = storageOf({ panel: "advice" });
  await forgetEverything(factory, db, storage);
  expect((await factory.databases()).map((found) => found.name)).toEqual([]);
  expect(await storage.get(null)).toEqual({});
  const reopened = await openHistory(factory);
  for (const store of Object.values(STORES)) {
    expect(await rowsOf(reopened, store), store).toEqual([]);
  }
  reopened.close();
});

test("storage that is not empty after clearing is named, not passed over", async () => {
  const factory = new IDBFactory();
  const db = await openHistory(factory);
  await expect(
    forgetEverything(factory, db, storageOf({ panel: "advice" }, false)),
  ).rejects.toThrow(new Error("forget everything left the extension's storage holding: panel"));
});

test("a database still listed after deleting it is named, not passed over", async () => {
  const factory = new IDBFactory();
  const db = await openHistory(factory);
  const listed: IDBFactory = Object.assign(Object.create(factory) as IDBFactory, {
    deleteDatabase: (name: string) => factory.deleteDatabase(name),
    databases: () => Promise.resolve([{ name: DATABASE, version: 1 }]),
  });
  await expect(forgetEverything(listed, db, storageOf({}))).rejects.toThrow(
    new Error("forget everything left the database steadyhand-history in place"),
  );
});
