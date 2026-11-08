import { type Browser, type Page, chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { findImage, type Picture, type Point } from "../lib/find-image.ts";

// The real side panel, opened as a person opens it (#503; Shyden 2026-11-05: an operating-system
// click on CI's virtual screen is real input). Automation cannot open it: Chrome refuses
// `sidePanel.open()` from DevTools even with a user gesture, and Playwright cannot click browser
// UI (measured 2026-11-05). So the suite runs each browser in a window on an X display, with a
// window manager, finds the extension's button in a screenshot and clicks it with xdotool.
//
// The button is the extension's tile: the browser draws its name's first letter, the same pixels
// in every browser's extensions menu (measured on CI 2026-11-06). Every browser takes one route
// (#528, Shyden 2026-11-08): its Extensions (puzzle) button opens the menu, and the tile below the
// toolbar row, the menu's entry, is the extension's action button. Choosing by which picture was
// drawn first raced a toolbar tile (PR #526), and Chrome pins the extension on its own, so a tile
// on the toolbar is never clicked. The pictures were cut from CI screenshots
// (Xvfb 1280x800) with the pointer away from them: a hovered or pressed button is drawn on grey,
// not the toolbar's white (Edge's first cut was hovered and never matched, PR #509). When a
// browser redraws them, the test fails naming the picture it cannot find.

const TOOLBAR = new URL("fixtures/toolbar/", import.meta.url);
/** The extension's tile, 16x16, as the browser draws it for an extension with no icon. */
const TILE = new URL("extension-tile.png", TOOLBAR);
/** The Extensions (puzzle) button at rest, 18x20, as each browser draws it: one shows. */
const EXTENSIONS_BUTTONS = [
  { name: "Chromium's Extensions button", file: "chromium-extensions-button.png" },
  { name: "Edge's Extensions button", file: "edge-extensions-button.png" },
] as const;

/** How long the screen may take to show what the next click needs. */
const SCREEN_CEILING_MS = 10_000;
/** How far below the Extensions button's centre its menu's entries start: past the toolbar row. */
const MENU_BELOW_BUTTON_PX = 24;
const LOOK_EVERY_MS = 250;
/** The port the panel's page is reached on; one browser runs at a time in CI. */
export const PANEL_DEBUGGING_PORT = 9333;

const run = (command: string, args: readonly string[]): Buffer =>
  execFileSync(command, args, { maxBuffer: 64 * 1024 * 1024 });

const pictureOf = (file: URL): Picture => {
  const path = fileURLToPath(file);
  const [width, height] = run("identify", ["-format", "%w %h", path])
    .toString()
    .split(" ")
    .map((side) => Number.parseInt(side, 10));
  return {
    width: width ?? 0,
    height: height ?? 0,
    rgb: new Uint8Array(run("stream", ["-map", "rgb", "-storage-type", "char", path, "-"])),
  };
};

const screen = (): Picture => {
  const [width, height] = run("xdotool", ["getdisplaygeometry"])
    .toString()
    .trim()
    .split(" ")
    .map((side) => Number.parseInt(side, 10));
  return {
    width: width ?? 0,
    height: height ?? 0,
    rgb: new Uint8Array(run("import", ["-window", "root", "-depth", "8", "rgb:-"])),
  };
};

/** The screen as a PNG at *file*, so a failed run can be judged by what it looked at. */
const saveScreen = (file: string): void => {
  const now = screen();
  execFileSync(
    "convert",
    ["-size", `${String(now.width)}x${String(now.height)}`, "-depth", "8", "rgb:-", file],
    { input: now.rgb },
  );
};

const click = ({ x, y }: Point): void => {
  run("xdotool", ["mousemove", String(x), String(y), "click", "1"]);
};

const pause = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

/** The one place each picture shows below *top* (pixels from the screen's top), looked for until
 * one of them shows or the ceiling passes. */
const lookFor = async (
  wanted: readonly { name: string; picture: Picture }[],
  top = 0,
): Promise<{ name: string; at: Point }> => {
  const seen: string[] = [];
  for (let waited = 0; waited <= SCREEN_CEILING_MS; waited += LOOK_EVERY_MS) {
    const now = screen();
    seen.length = 0;
    for (const { name, picture } of wanted) {
      const places = findImage(now, picture).filter((place) => place.y > top);
      seen.push(`${name}: ${String(places.length)}`);
      const [at] = places;
      if (places.length === 1 && at !== undefined) {
        return { name, at };
      }
    }
    await pause(LOOK_EVERY_MS);
  }
  throw new Error(
    `after ${String(SCREEN_CEILING_MS)} ms the screen shows none of these exactly once (${seen.join(", ")}): the browser drew its toolbar differently, so the pictures in tests/browser/fixtures/toolbar need cutting again`,
  );
};

/** The panel's page as the browser opened it, reached over DevTools within the ceiling. */
const panelIn = async (browser: Browser, path: string): Promise<Page> => {
  for (let waited = 0; waited <= SCREEN_CEILING_MS; waited += LOOK_EVERY_MS) {
    for (const context of browser.contexts()) {
      const panel = context.pages().find((page) => page.url().endsWith(path));
      if (panel !== undefined) {
        return panel;
      }
    }
    await pause(LOOK_EVERY_MS);
  }
  throw new Error(
    `the click on the extension's button opened no page ending ${path} within ${String(SCREEN_CEILING_MS)} ms`,
  );
};

/** Open the extension's side panel with a real click, as a person does, and return its page with
 * *time* as its clock. The panel is reached over DevTools after the click: a connection made
 * before it never hears of the page the browser opens (measured on CI 2026-11-06, PR #509), so
 * the clock is set on the open panel and the panel reloaded under it. If it cannot, the screen
 * it looked at is saved at *screenOnFailure* (CI keeps it) and the error stands. */
export const openSidePanel = async (
  path: string,
  time: Date,
  screenOnFailure: string,
): Promise<{ panel: Page; devtools: Browser }> => {
  try {
    return await clickOpen(path, time);
  } catch (error) {
    saveScreen(screenOnFailure);
    throw error;
  }
};

const clickOpen = async (path: string, time: Date): Promise<{ panel: Page; devtools: Browser }> => {
  const tile = pictureOf(TILE);
  const menu = await lookFor(
    EXTENSIONS_BUTTONS.map(({ name, file }) => ({
      name,
      picture: pictureOf(new URL(file, TOOLBAR)),
    })),
  );
  click(menu.at);
  // The menu opens below its button; a tile on the toolbar beside the button is not the menu's
  // (Chrome pins the extension on its own, run 42461808760), so only one below that row counts.
  const belowToolbar = menu.at.y + MENU_BELOW_BUTTON_PX;
  click(
    (await lookFor([{ name: "the extension's tile in its menu", picture: tile }], belowToolbar)).at,
  );
  const devtools = await chromium.connectOverCDP(
    `http://127.0.0.1:${String(PANEL_DEBUGGING_PORT)}`,
  );
  const panel = await panelIn(devtools, path);
  await panel.clock.install({ time });
  await panel.reload();
  return { panel, devtools };
};
