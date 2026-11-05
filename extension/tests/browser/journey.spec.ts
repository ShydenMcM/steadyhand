import { chromium, expect, test } from "@playwright/test";
import { build as esbuild } from "esbuild";
import { readFile } from "node:fs/promises";
import { BROKER_ORIGINS, build } from "../../build.ts";
import { CHOICE_LINE, DISCLAIMER } from "../../packages/shell/src/advice-view.ts";

// The first journey (#238 AC5): the built extension loads in Chromium, which proves Chrome accepts
// its manifest and content security policy, and the fixture broker's pages become advice. The
// panel opens in a tab of its own (automation cannot open Chrome's side panel), where it hears the
// content script as the side panel does. The broker is served by the test at its reserved `.test`
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

test("the built extension turns the broker's pages into the day's buy orders", async () => {
  const extension = test.info().outputPath("extension");
  await build(extension, esbuild);
  const context = await chromium.launchPersistentContext("", {
    channel: "chromium",
    args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
  });
  try {
    await context.route(`${ORIGIN}/**`, async (route) => {
      const name = new URL(route.request().url()).pathname.slice(1);
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: await readFile(new URL(`${name}.html`, PAGES), "utf8"),
      });
    });
    // Chrome starts the extension's service worker when it loads the extension; its address
    // names the extension.
    const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent("serviceworker"));
    const id = new URL(worker.url()).host;

    const panel = await context.newPage();
    await panel.clock.install({ time: AFTER_CLOSE });
    await panel.goto(`chrome-extension://${id}/side-panel.html`);
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
    await expect(panel.locator("#disclaimer")).toBeVisible();
  } finally {
    await context.close();
  }
});
