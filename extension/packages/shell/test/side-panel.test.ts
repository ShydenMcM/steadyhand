/**
 * The side panel's page, loaded in-process with the page's document stood in (#374 AC5): the unit
 * run has no browser, and the panel's only work today is to record on the page the packages its
 * bundle was built from. The built bundle loading in Chrome arrives with EXT S14a's browser tests.
 */
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("the page records each package the panel was built from, once each", async () => {
  const dataset: Record<string, string> = {};
  vi.stubGlobal("document", { documentElement: { dataset } });
  await import("../src/side-panel.ts");
  expect(dataset).toEqual({
    packages: "@steadyhand/core @steadyhand/readers @steadyhand/history",
  });
});
