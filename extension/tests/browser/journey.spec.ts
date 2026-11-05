import { chromium, expect, test } from "@playwright/test";
import { build as esbuild } from "esbuild";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { BROKER_ORIGINS, build } from "../../build.ts";
import { CHOICE_LINE, DISCLAIMER } from "../../packages/shell/src/advice-view.ts";
import { PANEL_DEBUGGING_PORT, openSidePanel } from "./side-panel.ts";

// The first journey (#238 AC5): the built extension loads in each browser the suite runs on
// (Chromium, Chrome and Edge, #501), which proves each accepts its manifest and content security
// policy, and the fixture broker's pages become advice. Each browser installs it as "Load
// unpacked" does, through Chrome's DevTools protocol: Chrome and Edge ignore the command-line flag
// that once did it (measured 2026-11-05 on Chrome 156 and Edge 156, #501). The
// panel is the browser's real side panel, opened by a real click on the extension's button
// (./side-panel.ts, #503), and checked at the side panel's own width. The broker is served by the test at its reserved `.test`
// origin, so nothing is fetched. The panel's clock is set to a Tuesday evening after the close.
//
// These pages are the journey's, not the shared reader fixtures: dividend-growth needs a dividend
// in each of six years, growing, for every stock it may buy.

const [ORIGIN] = BROKER_ORIGINS;
const PAGES = new URL("fixtures/journey/", import.meta.url);
/** The pages in the order the journey opens them, with what the panel says once it has read each.
 * No two in a row say the same, so each read is seen before the next page opens. */
const JOURNEY = [
  ["portfolio", "Read the portfolio page."],
  ["dividends-BBCA", "Read the dividend page."],
  ["watchlist", "Read the watchlist page."],
  ["dividends-BBRI", "Read the dividend page."],
  ["flags", "Read the flags page."],
] as const;
const AFTER_CLOSE = new Date("2025-06-17T19:00:00+07:00");

/** The id Chrome gives an unpacked extension: the first 32 hex digits of its path's SHA-256, each
 * written as a letter from a to p. */
const unpackedId = (path: string): string =>
  Array.from(createHash("sha256").update(path).digest("hex").slice(0, 32), (digit) =>
    String.fromCharCode(97 + Number.parseInt(digit, 16)),
  ).join("");

test("the built extension turns the broker's pages into the day's buy orders", async () => {
  const info = test.info();
  const extension = info.outputPath("extension");
  await build(extension, esbuild);
  const { channel } = info.project.use;
  if (channel === undefined) {
    throw new Error(`project ${info.project.name} names no browser channel`);
  }
  // The extension's tile is pinned to the toolbar in the profile, as "Pin" in the extensions
  // menu does; the id is loadUnpacked's, which is checked below.
  const profile = info.outputPath("profile");
  await mkdir(`${profile}/Default`, { recursive: true });
  await writeFile(
    `${profile}/Default/Preferences`,
    JSON.stringify({ extensions: { pinned_extensions: [unpackedId(extension)] } }),
  );
  // A window on the display the CI step gives it: the side panel is browser UI, which has no
  // headless form a person could click.
  const context = await chromium.launchPersistentContext(profile, {
    channel,
    headless: false,
    viewport: null,
    args: [
      "--enable-unsafe-extension-debugging",
      `--remote-debugging-port=${String(PANEL_DEBUGGING_PORT)}`,
      "--window-position=0,0",
      "--window-size=1280,800",
    ],
    ignoreDefaultArgs: ["--disable-extensions"],
  });
  try {
    const browser = context.browser();
    if (browser === null) {
      throw new Error("the browser gave no handle to install the extension with");
    }
    const devtools = await browser.newBrowserCDPSession();
    const { id } = await devtools.send("Extensions.loadUnpacked", { path: extension });
    expect(id).toBe(unpackedId(extension));
    await context.route(`${ORIGIN}/**`, async (route) => {
      const name = new URL(route.request().url()).pathname.slice(1);
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: await readFile(new URL(`${name}.html`, PAGES), "utf8"),
      });
    });

    const opened = await openSidePanel("/side-panel.html", AFTER_CLOSE);
    const { panel } = opened;
    expect(panel.url()).toBe(`chrome-extension://${id}/side-panel.html`);
    await expect(panel.getByText(DISCLAIMER)).toBeVisible();
    await expect(panel.locator("#disclaimer")).toHaveText(DISCLAIMER);
    await expect(panel.locator("#choice")).toHaveText(CHOICE_LINE);

    await panel.getByLabel("Universe: the stocks to choose from").pressSequentially("BBCA BBRI");
    await panel.getByRole("button", { name: "Save universe" }).click();
    await expect(panel.locator("#status")).toHaveText("Universe saved: 2 stocks.");

    const broker = await context.newPage();
    for (const [name, read] of JOURNEY) {
      await broker.goto(`${ORIGIN}/${name}`);
      await expect(panel.locator("#status")).toHaveText(read);
    }

    const advice = panel.locator("#advice");
    await expect(advice.locator("h2").first()).toHaveText("Advice for 2025-06-17");
    await expect(advice.locator("p").first()).toHaveText(
      "Buy 7 lots of BBCA at a limit of IDR 9,100, estimated fees IDR 13,365: " +
        "dividend-growth: paid a dividend every year and grew it.",
    );
    await expect(advice.locator("p").nth(1)).toHaveText(
      "Buy 14 lots of BBRI at a limit of IDR 4,560, estimated fees IDR 13,394: " +
        "dividend-growth: paid a dividend every year and grew it.",
    );
    // At the side panel's own width (#503 AC2): every line shows, and none runs past the edge.
    const width = await panel.evaluate(() => innerWidth);
    expect(width).toBeLessThan(500);
    for (const line of [
      advice.locator("h2").first(),
      advice.locator("p").first(),
      advice.locator("p").nth(1),
      panel.locator("#disclaimer"),
      panel.locator("#choice"),
    ]) {
      await expect(line).toBeVisible();
      const box = await line.boundingBox();
      expect(box === null ? Number.POSITIVE_INFINITY : box.x + box.width).toBeLessThanOrEqual(
        width,
      );
    }
    await opened.devtools.close();
  } finally {
    await context.close();
  }
});
