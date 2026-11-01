import { expect, test } from "@playwright/test";
import { build } from "esbuild";
import { fileURLToPath } from "node:url";

// The history store in Chromium's own IndexedDB (#231 AC6): the unit tests' in-memory stand-in
// is not the browser's. The store is bundled as the extension bundles it and run on a page of
// its own origin (IndexedDB refuses an opaque one), served by the test so nothing is fetched.

const ORIGIN = "https://history.steadyhand.test";

const bundled = async (): Promise<string> => {
  const result = await build({
    entryPoints: [fileURLToPath(new URL("history-bundle.ts", import.meta.url))],
    bundle: true,
    write: false,
    format: "iife",
    globalName: "steadyhandHistory",
    platform: "browser",
  });
  const [output] = result.outputFiles;
  if (output === undefined) {
    throw new Error("esbuild wrote no bundle of the history store");
  }
  return output.text;
};

test("the store records, keeps across a reopen and forgets, in Chromium's IndexedDB", async ({
  page,
}) => {
  await page.route(`${ORIGIN}/**`, (route) =>
    route.fulfill({ contentType: "text/html", body: "<!doctype html><title>history</title>" }),
  );
  await page.goto(`${ORIGIN}/`);
  await page.addScriptTag({ content: await bundled() });
  const seen = await page.evaluate(async () => {
    const store = (
      globalThis as unknown as { steadyhandHistory: typeof import("./history-bundle.ts") }
    ).steadyhandHistory;
    const rules = { calendar: store.IdxCalendar.shipped(), sessions: store.shippedSessions() };
    const read = {
      source: { broker: "fixture", pageKind: "watchlist" as const, route: "page" as const },
      readAt: new Date("2025-06-17T16:02:00+07:00"),
      value: { stocks: [{ symbol: "BBRI", lastPrice: new store.Money(4_120n, store.IDR) }] },
    };
    const first = await store.openHistory(indexedDB);
    const day = await store.recordCloses(first, read, rules);
    first.close();
    const again = await store.openHistory(indexedDB);
    const kept = (await store.rowsOf(again, store.STORES.closes)) as {
      symbol: string;
      close: bigint;
    }[];
    const items = new Map<string, unknown>([["panel", "advice"]]);
    await store.forgetEverything(indexedDB, again, {
      get: () => Promise.resolve(Object.fromEntries(items)),
      clear: () => {
        items.clear();
        return Promise.resolve();
      },
    });
    return {
      day,
      kept: kept.map((row) => `${row.symbol} ${row.close.toString()}`),
      left: (await indexedDB.databases()).map((found) => found.name),
    };
  });
  expect(seen).toEqual({ day: "2025-06-17", kept: ["BBRI 4120"], left: [] });
});
