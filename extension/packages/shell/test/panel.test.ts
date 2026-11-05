import { readFileSync } from "node:fs";
import type { PageKind } from "@steadyhand/core";
import { openHistory, settingOf, storedMemory } from "@steadyhand/history";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, expect, test } from "vitest";
import { CHOICE_LINE, DISCLAIMER } from "../src/advice-view.ts";
import type { Snapshot } from "../src/messages.ts";
import {
  startPanel,
  type PanelDocument,
  type PanelElement,
  type PanelRuntime,
  type PanelTabs,
} from "../src/panel.ts";
import { SETTINGS } from "../src/record-read.ts";

// The side panel (spec §10.2, §10.3, #238 AC3-AC4): it records each page the content script sends,
// asks the active tab for its page on "Read this page", keeps the universe typed into Settings,
// and shows the day's advice with the disclaimer always beneath it. The page, Chrome and the
// clock are stood in; history is fake-indexeddb.

/** A Tuesday evening after the close: the fixture pages read then are fresh for 2025-06-17. */
const AFTER_CLOSE = new Date("2025-06-17T19:00:00+07:00");
const PAGES = new URL("../../readers/fixtures/fixture-broker/", import.meta.url);
const page = (kind: PageKind): string => readFileSync(new URL(`${kind}.html`, PAGES), "utf8");
const snapshot = (kind: PageKind): Snapshot => ({
  kind: "snapshot",
  url: `https://broker.steadyhand.test/${kind}`,
  html: page(kind),
});

/** An element as the panel uses one: its text, children, value and click listener. */
class StandIn implements PanelElement<StandIn> {
  id = "";
  htmlFor = "";
  value = "";
  textContent = "";
  children: StandIn[] = [];
  clicked: (() => void) | undefined;

  constructor(readonly tagName: string) {}

  append(...children: StandIn[]): void {
    this.children.push(...children);
  }

  replaceChildren(...children: StandIn[]): void {
    this.children = children;
  }

  addEventListener(_type: "click", listener: () => void): void {
    this.clicked = listener;
  }
}

const standInDocument = (): PanelDocument<StandIn> => ({
  body: new StandIn("body"),
  // One stand-in serves every tag: it has a value and a label's target too.
  createElement: (tag: string) => new StandIn(tag),
});

const all = (root: StandIn): StandIn[] => [root, ...root.children.flatMap(all)];
const byId = (root: StandIn, id: string): StandIn => {
  const found = all(root).find((element) => element.id === id);
  if (found === undefined) {
    throw new Error(`no element #${id}`);
  }
  return found;
};
/** Every line of text under `root`, in page order. */
const textOf = (root: StandIn): string[] =>
  all(root)
    .map((element) => element.textContent)
    .filter((text) => text !== "");

interface Chrome {
  runtime: PanelRuntime;
  tabs: PanelTabs;
  /** The content script's listener, once the panel adds it. */
  send: (message: unknown) => void;
  asked: number[];
}

const standInChrome = (
  answer: () => Promise<unknown>,
  tabs: readonly { id?: number }[] = [{ id: 7 }],
): Chrome => {
  const chrome: Chrome = {
    send: () => {
      throw new Error("the panel added no listener");
    },
    asked: [],
    runtime: {
      onMessage: {
        addListener: (listener) => {
          chrome.send = (message) => listener(message);
        },
      },
    },
    tabs: {
      query: (query) => {
        expect(query).toEqual({ active: true, currentWindow: true });
        return Promise.resolve(tabs);
      },
      sendMessage: (tabId, message) => {
        expect(message).toEqual({ kind: "ask" });
        chrome.asked.push(tabId);
        return answer();
      },
    },
  };
  return chrome;
};

let db: IDBDatabase;

beforeEach(async () => {
  db = await openHistory(new IDBFactory());
  return () => {
    db.close();
  };
});

const open = async (chrome = standInChrome(() => Promise.resolve(undefined))) => {
  const page = standInDocument();
  const panel = await startPanel({
    page,
    db,
    runtime: chrome.runtime,
    tabs: chrome.tabs,
    clock: () => AFTER_CLOSE,
  });
  return { page: page.body, panel, chrome };
};

test("the disclaimer and the choice line are on the panel from the start", async () => {
  const { page } = await open();
  expect(byId(page, "disclaimer").textContent).toBe(DISCLAIMER);
  expect(byId(page, "choice").textContent).toBe(CHOICE_LINE);
});

test("before any read the panel says which pages to open", async () => {
  const { page, panel } = await open();
  await panel.settled();
  expect(textOf(byId(page, "advice"))).toEqual([
    "Read again",
    "The pages below were not read.",
    "Open the portfolio page.",
    "Open the watchlist page.",
    "The next close is final at 2025-06-18 16:02 WIB.",
  ]);
});

test("the universe typed into Settings is saved as symbols and advice follows", async () => {
  const { page, panel, chrome } = await open();
  chrome.send(snapshot("portfolio"));
  chrome.send(snapshot("watchlist"));
  await panel.settled();
  expect(textOf(byId(page, "advice"))).toEqual([
    "Universe",
    "List the universe's stocks in Settings to get advice.",
  ]);

  byId(page, "universe").value = " bbca, TLKM\nbbca  UNVR ";
  byId(page, "save-universe").clicked?.();
  await panel.settled();

  expect(await settingOf(db, SETTINGS.universe)).toEqual(["BBCA", "TLKM", "UNVR"]);
  expect(byId(page, "status").textContent).toBe("Universe saved: 3 stocks.");
  expect(textOf(byId(page, "advice"))[0]).toBe("Advice for 2025-06-17");
  // The day's memory is kept, so asking again gives the same advice.
  expect((await storedMemory(db, "dividend-growth"))?.day).toBe("2025-06-17");
});

test("a universe entry that is not an IDX stock code is refused, naming it", async () => {
  const { page, panel } = await open();
  byId(page, "universe").value = "BBCA BBC4 TLKM";
  byId(page, "save-universe").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe(
    'Universe not saved: "BBC4" is not a four-letter IDX stock code.',
  );
  expect(await settingOf(db, SETTINGS.universe)).toBeUndefined();
});

test("the saved universe is in the text box when the panel opens", async () => {
  const first = await open();
  byId(first.page, "universe").value = "BBCA TLKM";
  byId(first.page, "save-universe").clicked?.();
  await first.panel.settled();
  const { page } = await open();
  expect(byId(page, "universe").value).toBe("BBCA TLKM");
});

test("each page sent is recorded in turn and the advice redrawn", async () => {
  const { page, panel, chrome } = await open();
  chrome.send(snapshot("portfolio"));
  await panel.settled();
  expect(byId(page, "status").textContent).toBe("Read the portfolio page.");
  expect(textOf(byId(page, "advice"))).toContain("Open the watchlist page.");
  expect(textOf(byId(page, "advice"))).not.toContain("Open the portfolio page.");
});

test("a page that is not a broker page steadyhand reads is said so, and nothing changes", async () => {
  const { page, panel, chrome } = await open();
  chrome.send({
    kind: "snapshot",
    url: "https://broker.steadyhand.test/",
    html: "<main>hi</main>",
  });
  await panel.settled();
  expect(byId(page, "status").textContent).toMatch(/^This page was not read: /u);
});

test("a message that is not a snapshot is left alone", async () => {
  const { page, panel, chrome } = await open();
  chrome.send({ kind: "ask" });
  await panel.settled();
  expect(byId(page, "status").textContent).toBe("");
});

test('"Read this page" asks the active tab for its page and records it', async () => {
  const chrome = standInChrome(() => Promise.resolve(snapshot("portfolio")));
  const { page, panel } = await open(chrome);
  expect(byId(page, "read").textContent).toBe("Read this page");
  byId(page, "read").clicked?.();
  await panel.settled();
  expect(chrome.asked).toEqual([7]);
  expect(byId(page, "status").textContent).toBe("Read the portfolio page.");
});

test('"Read this page" on a tab with no broker page says so', async () => {
  const chrome = standInChrome(() =>
    Promise.reject(new Error("Could not establish connection. Receiving end does not exist.")),
  );
  const { page, panel } = await open(chrome);
  byId(page, "read").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe("This tab shows no broker page steadyhand reads.");
});

test('"Read this page" with no active tab says so', async () => {
  const chrome = standInChrome(() => Promise.resolve(undefined), []);
  const { page, panel } = await open(chrome);
  byId(page, "read").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe("This tab shows no broker page steadyhand reads.");
  expect(chrome.asked).toEqual([]);
});

test("any other failure is shown, never dropped", async () => {
  const chrome = standInChrome(() => Promise.reject(new Error("the extension was reloaded")));
  const { page, panel } = await open(chrome);
  byId(page, "read").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe(
    "Something went wrong: Error: the extension was reloaded",
  );
});

test('"Read this page" on a tab Chrome gives no id says so', async () => {
  const chrome = standInChrome(() => Promise.resolve(undefined), [{}]);
  const { page, panel } = await open(chrome);
  byId(page, "read").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe("This tab shows no broker page steadyhand reads.");
  expect(chrome.asked).toEqual([]);
});
