/** The service worker's entry point, loaded in-process with `chrome` stood in. */
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

test("clicking the toolbar button opens the side panel", async () => {
  const asked: unknown[] = [];
  vi.stubGlobal("chrome", {
    sidePanel: {
      setPanelBehavior: (behavior: unknown) => {
        asked.push(behavior);
        return Promise.resolve();
      },
    },
  });
  await import("../src/service-worker.ts");
  expect(asked).toEqual([{ openPanelOnActionClick: true }]);
});
