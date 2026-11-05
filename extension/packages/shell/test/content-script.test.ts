/**
 * The content script's entry point, loaded in-process with the page and `chrome` stood in: it
 * sends the page as it is and parses, changes and keeps nothing (spec §10.2).
 */
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

test("on load the content script sends the page's address and whole text to the panel", async () => {
  const sent: unknown[] = [];
  const listeners: unknown[] = [];
  vi.stubGlobal("location", { href: "https://broker.steadyhand.test/portfolio" });
  vi.stubGlobal("document", { documentElement: { outerHTML: "<html><body>p</body></html>" } });
  vi.stubGlobal("chrome", {
    runtime: {
      sendMessage: (message: unknown) => {
        sent.push(message);
        return Promise.resolve(undefined);
      },
      onMessage: { addListener: (listener: unknown) => listeners.push(listener) },
    },
  });
  await import("../src/content-script.ts");
  await vi.waitFor(() => {
    expect(sent).toEqual([
      {
        kind: "snapshot",
        url: "https://broker.steadyhand.test/portfolio",
        html: "<html><body>p</body></html>",
      },
    ]);
  });
  expect(listeners).toHaveLength(1);
});
