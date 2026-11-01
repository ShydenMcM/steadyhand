import { expect, test } from "vitest";
import { forgetEverything } from "../src/forget.ts";
import { putSetting } from "../src/record.ts";
import { failure, openHistory, requested } from "../src/schema.ts";

// The failures a working IndexedDB never gives on demand (a full disk, a broken profile), each
// with a stand-in request that fails as IndexedDB's do: its `onerror` called, its `error` set.

const broken = new DOMException("the disk is full", "QuotaExceededError");

/** A request that fails with `error` once its handler is set. */
const failing = (error: DOMException | null, extra: object = {}): unknown => {
  const request = { error, ...extra } as { error: DOMException | null; onerror?: () => void };
  return new Proxy(request, {
    set(target, key, value: unknown) {
      Reflect.set(target, key, value);
      if (key === "onerror") {
        queueMicrotask(() => {
          target.onerror?.();
        });
      }
      return true;
    },
  });
};

test("IndexedDB's own error is passed on as it is", () => {
  expect(failure(broken, "writing")).toBe(broken);
});

test("a failure IndexedDB gives no error for is named", () => {
  expect(failure(null, "writing settings")).toEqual(
    new Error("writing settings failed with no error"),
  );
});

test("a request that fails rejects with its error", async () => {
  await expect(requested(failing(broken) as IDBRequest)).rejects.toBe(broken);
});

test("a write that fails rejects with its error", async () => {
  const write = failing(broken, {
    objectStore: () => ({ put: () => undefined }),
  }) as IDBTransaction;
  const db = { transaction: () => write } as unknown as IDBDatabase;
  await expect(putSetting(db, "fees", "custom")).rejects.toBe(broken);
});

test("an open that fails for any cause but a newer version rejects with its error", async () => {
  const factory = { open: () => failing(broken) as IDBOpenDBRequest } as unknown as IDBFactory;
  await expect(openHistory(factory)).rejects.toBe(broken);
});

test("a delete that fails rejects with its error, and nothing is read back as gone", async () => {
  const factory = {
    deleteDatabase: () => failing(broken) as IDBOpenDBRequest,
  } as unknown as IDBFactory;
  const db = { close: () => undefined } as unknown as IDBDatabase;
  const storage = { get: () => Promise.resolve({}), clear: () => Promise.resolve() };
  await expect(forgetEverything(factory, db, storage)).rejects.toBe(broken);
});
