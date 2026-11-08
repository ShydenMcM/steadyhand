import { chromium, expect, test, type BrowserContext, type Page } from "@playwright/test";
import { build as esbuild } from "esbuild";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { BROKER_ORIGINS, build } from "../../build.ts";
import { CHOICE_LINE, DISCLAIMER } from "../../packages/shell/src/advice-view.ts";
import { PANEL_DEBUGGING_PORT, openSidePanel } from "./side-panel.ts";

// The journeys against the fake broker (#238 AC5, #239, #241, spec §11, §14.3). The built
// extension loads in each browser the suite runs on (Chromium, Chrome and Edge, #501), installed
// as "Load unpacked" does, through Chrome's DevTools protocol: Chrome and Edge ignore the
// command-line flag that once did it (measured 2026-11-05 on Chrome 156 and Edge 156, #501). The
// panel is the browser's real side panel, opened by a real click on the extension's button
// (./side-panel.ts, #503), and every journey drives it with real clicks, key presses and wheel
// turns. The broker is served by the test at its reserved `.test` origin, so nothing is fetched.
//
// Every journey also proves two things (#241 AC2, AC3): the panel asks for nothing but the
// extension's own files, and the broker's pages ask for nothing but themselves; and the broker's
// page sees no event and no change to its document from the extension, which a planted change
// proves the recorder would see.
//
// These pages are the journey's, not the shared reader fixtures: dividend-growth needs a dividend
// in each of six years, growing, for every stock it may buy.

const [ORIGIN] = BROKER_ORIGINS;
const PAGES = new URL("fixtures/journey/", import.meta.url);
/** The pages in the order the orders journey opens them, with what the panel says once it has
 * read each. No two in a row say the same, so each read is seen before the next page opens. */
const JOURNEY = [
  ["portfolio", "Read the portfolio page."],
  ["dividends-BBCA", "Read the dividend page."],
  ["watchlist", "Read the watchlist page."],
  ["dividends-BBRI", "Read the dividend page."],
  ["flags", "Read the flags page."],
] as const;
/** A Monday and then a Tuesday evening after the close. */
const MONDAY_AFTER_CLOSE = new Date("2025-06-16T19:00:00+07:00");
const AFTER_CLOSE = new Date("2025-06-17T19:00:00+07:00");

/** The id Chrome gives an unpacked extension: the first 32 hex digits of its path's SHA-256, each
 * written as a letter from a to p. */
const unpackedId = (path: string): string =>
  Array.from(createHash("sha256").update(path).digest("hex").slice(0, 32), (digit) =>
    String.fromCharCode(97 + Number.parseInt(digit, 16)),
  ).join("");

/** Record, in a broker page's own world, every input event and every change to its document
 * from the moment its document is parsed (#241 AC3). Added to every page before its scripts run;
 * a page of another origin records nothing. */
const recordBrokerPage = (origin: string): void => {
  if (location.origin !== origin) {
    return;
  }
  const seen: string[] = [];
  Object.defineProperty(globalThis, "steadyhandSeen", { value: seen });
  const events = [
    "click",
    "dblclick",
    "auxclick",
    "contextmenu",
    "mousedown",
    "mouseup",
    "pointerdown",
    "pointerup",
    "keydown",
    "keyup",
    "keypress",
    "beforeinput",
    "input",
    "change",
    "submit",
    "reset",
    "select",
    "focusin",
    "focusout",
    "paste",
    "cut",
    "copy",
    "wheel",
  ];
  document.addEventListener("DOMContentLoaded", () => {
    for (const type of events) {
      globalThis.addEventListener(
        type,
        (event) => {
          seen.push(`event ${event.type}`);
        },
        true,
      );
    }
    new MutationObserver((records) => {
      for (const record of records) {
        seen.push(`mutation ${record.type}`);
      }
    }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  });
};

/** What the broker page's recorder has seen. */
const seenOn = (broker: Page): Promise<string[]> =>
  broker.evaluate(() => (globalThis as unknown as { steadyhandSeen: string[] }).steadyhandSeen);

interface Journey {
  readonly panel: Page;
  readonly context: BrowserContext;
  /** The broker's tab, opened on the first call. */
  readonly broker: () => Promise<Page>;
}

/** Build the extension, install it in this project's browser, serve the journey's broker pages,
 * open the real side panel with its clock at `time` and run `journey` on it; then check every
 * request it and the broker's pages made. The browser is closed after, pass or fail. */
const withPanel = async (
  journey: (opened: Journey) => Promise<void>,
  time: Date = AFTER_CLOSE,
): Promise<void> => {
  const info = test.info();
  const extension = info.outputPath("extension");
  await build(extension, esbuild);
  const { channel } = info.project.use;
  if (channel === undefined) {
    throw new Error(`project ${info.project.name} names no browser channel`);
  }
  // The extension is not pinned (#528): every browser opens it from its Extensions menu, one route.
  const profile = info.outputPath("profile");
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
    const own = `chrome-extension://${id}/`;
    await context.route(`${ORIGIN}/**`, async (route) => {
      const name = new URL(route.request().url()).pathname.slice(1);
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: await readFile(new URL(`${name}.html`, PAGES), "utf8"),
      });
    });
    await context.addInitScript(recordBrokerPage, ORIGIN);
    // Every request a broker page makes: only the pages the journey opens.
    const brokerRequests: string[] = [];
    context.on("request", (request) => {
      if (!request.url().startsWith(own)) {
        brokerRequests.push(`${request.resourceType()} ${request.url()}`);
      }
    });

    const opened = await openSidePanel(
      "/side-panel.html",
      time,
      info.outputPath("screen-at-failure.png"),
    );
    const { panel } = opened;
    expect(panel.url()).toBe(`${own}side-panel.html`);
    // The panel loaded again with request logging on: its own page and script must be seen.
    const panelRequests: string[] = [];
    panel.on("request", (request) => {
      panelRequests.push(request.url());
    });
    await panel.reload();
    await expect(panel.locator("#disclaimer")).toHaveText(DISCLAIMER);

    let broker: Page | undefined;
    await journey({
      panel,
      context,
      broker: async () => {
        broker ??= await context.newPage();
        return broker;
      },
    });

    expect(panelRequests).toContain(`${own}side-panel.js`);
    expect(panelRequests.filter((url) => !url.startsWith(own))).toEqual([]);
    expect(brokerRequests.filter((request) => !request.startsWith(`document ${ORIGIN}/`))).toEqual(
      [],
    );
    await opened.devtools.close();
  } finally {
    await context.close();
  }
};

/** Open the broker page `name` in the broker's tab and wait until the panel says `read`; the
 * page then has seen no event and no change from the extension. */
const readOnBroker = async (opened: Journey, name: string, read: string): Promise<void> => {
  const broker = await opened.broker();
  await broker.goto(`${ORIGIN}/${name}`);
  await expect(opened.panel.locator("#status")).toHaveText(read);
  expect(await seenOn(broker)).toEqual([]);
};

const saveUniverse = async (panel: Page, typed: string, saved: string): Promise<void> => {
  await panel.getByRole("tab", { name: "Settings" }).click();
  await expect(panel.locator("#pane-settings")).toBeVisible();
  await panel.getByLabel("Universe: the stocks to choose from").pressSequentially(typed);
  await panel.getByRole("button", { name: "Save universe" }).click();
  await expect(panel.locator("#status")).toHaveText(saved);
};

test("reading the portfolio and the watchlist gives the day's orders", async () => {
  await withPanel(async (opened) => {
    const { panel } = opened;
    await expect(panel.getByText(DISCLAIMER)).toBeVisible();
    await expect(panel.locator("#choice")).toHaveText(CHOICE_LINE);
    await expect(panel.locator("#pane-advice")).toBeVisible();
    await expect(panel.locator("#pane-settings")).toBeHidden();
    await saveUniverse(panel, "BBCA BBRI", "Universe saved: 2 stocks.");
    await expect(panel.locator("#pane-advice")).toBeHidden();

    for (const [name, read] of JOURNEY) {
      await readOnBroker(opened, name, read);
    }

    await panel.getByRole("tab", { name: "Advice" }).click();
    const advice = panel.locator("#advice");
    await expect(advice).toBeVisible();
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
    await expect(advice.locator("h2").last()).toHaveText("Income goal");
    const lines = await advice.locator("h2, p").all();
    expect(lines.length).toBeGreaterThan(3);
    // A block's box keeps the panel's width while its text spills past it (a 300-letter word
    // passed a box check on all three browsers, PR #509), so the text's own width is measured.
    for (const line of [...lines, panel.locator("#disclaimer"), panel.locator("#choice")]) {
      await expect(line).toBeVisible();
      const box = await line.boundingBox();
      expect(box === null ? Number.POSITIVE_INFINITY : box.x + box.width).toBeLessThanOrEqual(
        width,
      );
      expect(await line.evaluate((element) => element.scrollWidth - element.clientWidth)).toBe(0);
    }
    expect(await panel.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    );

    // The recorder's control: a change planted on the broker's page is seen.
    const broker = await opened.broker();
    await broker.evaluate(() => {
      document.body.setAttribute("data-planted", "yes");
    });
    expect(await seenOn(broker)).toEqual(["mutation attributes"]);
  });
});

test("a page the advice needs and has not read is named", async () => {
  await withPanel(async (opened) => {
    const { panel } = opened;
    await saveUniverse(panel, "BBCA BBRI", "Universe saved: 2 stocks.");
    await readOnBroker(opened, "portfolio", "Read the portfolio page.");
    await panel.getByRole("tab", { name: "Advice" }).click();
    await expect(panel.locator("#advice")).toContainText("Open the watchlist page.");
  });
});

test("a portfolio page pasted, and a watchlist page chosen from a file, are read", async () => {
  await withPanel(async ({ panel }) => {
    const status = panel.locator("#status");
    // A saved portfolio page, pasted by typing it into the box.
    const portfolio = await readFile(new URL("portfolio.html", PAGES), "utf8");
    await panel.getByLabel("Or paste a broker page you saved").pressSequentially(portfolio);
    await panel.getByRole("button", { name: "Read the pasted page" }).click();
    await expect(status).toHaveText("Read the portfolio page.");
    // A saved watchlist page, chosen in the file chooser the picker's real click opens.
    const chooser = panel.waitForEvent("filechooser");
    await panel.getByLabel("Or open a broker page you saved").click();
    await (await chooser).setFiles(fileURLToPath(new URL("watchlist.html", PAGES)));
    await expect(status).toHaveText("Read the watchlist page.");
  });
});

test("a deposit typed on Settings is kept and listed", async () => {
  await withPanel(async ({ panel }) => {
    await panel.getByRole("tab", { name: "Settings" }).click();
    await panel.getByLabel("Day, such as 2025-06-16").pressSequentially("2025-06-16");
    await panel.getByLabel("Amount, in rupiah").pressSequentially("1.000.000");
    await panel.getByRole("button", { name: "Keep this deposit or withdrawal" }).click();
    await expect(panel.locator("#status")).toHaveText(
      "Deposit of IDR 1,000,000 on 2025-06-16 kept.",
    );
    await expect(panel.locator("#typed-movements")).toHaveText(
      "2025-06-16: deposit of IDR 1,000,000",
    );
  });
});

test("a fall past the daily limit halts buying until the strategy's name is typed", async () => {
  await withPanel(async (opened) => {
    const { panel } = opened;
    const status = panel.locator("#status");
    await readOnBroker(opened, "portfolio", "Read the portfolio page.");
    // The next evening the portfolio is worth 6% less.
    await panel.clock.setSystemTime(AFTER_CLOSE);
    await readOnBroker(opened, "portfolio-after-a-fall", "Read the portfolio page.");
    await panel
      .getByRole("button", { name: "No deposits or withdrawals since 2025-06-16" })
      .click();
    await expect(status).toHaveText("Kept: no deposits or withdrawals since 2025-06-16.");
    await expect(panel.locator("#resume-box")).toBeVisible();
    await panel
      .getByLabel("Type the strategy's name to resume buying")
      .pressSequentially("ma-trend");
    await panel.getByRole("button", { name: "Resume" }).click();
    await expect(status).toHaveText(
      "Not resumed: you typed 'ma-trend', not 'dividend-growth'; nothing was changed",
    );
    const name = panel.getByLabel("Type the strategy's name to resume buying");
    await name.click({ clickCount: 3 });
    await name.press("Backspace");
    await name.pressSequentially("dividend-growth");
    await panel.getByRole("button", { name: "Resume" }).click();
    await expect(status).toHaveText("Buying resumed: dividend-growth.");
    await expect(panel.locator("#resume-box")).toBeHidden();
  }, MONDAY_AFTER_CLOSE);
});

test("Settings keeps the strategy, the goal and the exclusions, and Lessons shows the course", async () => {
  await withPanel(async ({ panel }) => {
    const status = panel.locator("#status");
    await panel.getByRole("tab", { name: "Settings" }).click();
    await panel.getByRole("button", { name: "Save strategy" }).click();
    await expect(status).toHaveText("Strategy saved: dividend-growth.");
    await panel.getByLabel("Monthly income goal, in rupiah").pressSequentially("5.000.000");
    await panel.getByRole("button", { name: "Save goal" }).click();
    await expect(status).toHaveText("Income goal saved.");
    // Settings runs past the panel's foot, so the wheel turned over it scrolls the panel, as a
    // person reaches the exclusions. (The advice did not scroll under the wheel on CI, PR #519.)
    const [tall, high] = await panel.evaluate(() => [
      document.documentElement.scrollHeight,
      innerHeight,
    ]);
    expect(
      tall,
      `Settings is ${String(tall)} px tall in a ${String(high)} px panel`,
    ).toBeGreaterThan(high);
    await panel.locator("#pane-settings").hover();
    await panel.mouse.wheel(0, 2_000);
    await expect.poll(() => panel.evaluate(() => scrollY)).toBeGreaterThan(0);
    await panel
      .getByLabel("Excluded stocks: one per line, the code and then your reason")
      .pressSequentially("UNVR too expensive");
    await panel.getByRole("button", { name: "Save exclusions" }).click();
    await expect(status).toHaveText("Exclusions saved: 1 stock.");
    await panel.getByRole("tab", { name: "Lessons" }).click();
    // The shipped course (#244): its modules in order, the first lesson first.
    const lessons = panel.locator("#pane-lessons");
    await expect(lessons).toBeVisible();
    await expect(lessons.locator("h2").first()).toHaveText("Start here");
    await expect(lessons.locator("h2").last()).toHaveText("Strategies");
    await expect(panel.locator("#lesson-start\\.welcome h3")).toHaveText("Start here");
  });
});

test("forgetting everything, once confirmed, leaves History empty", async () => {
  await withPanel(async (opened) => {
    const { panel } = opened;
    await readOnBroker(opened, "watchlist", "Read the watchlist page.");
    await panel.getByRole("tab", { name: "History" }).click();
    const history = panel.locator("#pane-history");
    await expect(history).toContainText(
      "steadyhand records a broker page only while this panel is open beside it.",
    );
    await expect(panel.locator("#stock-history p")).not.toHaveCount(0);
    await expect(panel.locator("#forget-confirm")).toBeHidden();
    await panel.getByRole("button", { name: "Forget everything" }).click();
    await expect(panel.locator("#forget-confirm")).toBeVisible();
    await panel.getByRole("button", { name: "Yes, forget everything" }).click();
    await expect(panel.locator("#status")).toHaveText("Everything is forgotten.");
    await expect(panel.locator("#stock-history")).toHaveText("Nothing is recorded yet.");
  });
});
