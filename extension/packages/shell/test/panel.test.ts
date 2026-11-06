import { readFileSync } from "node:fs";
import { STRATEGIES, type PageKind } from "@steadyhand/core";
import { openHistory, putSetting, settingOf, storedMemory } from "@steadyhand/history";
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
import { KEPT } from "../src/settings.ts";

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
  hidden = false;
  readonly attributes = new Map<string, string>();
  children: StandIn[] = [];
  readonly listeners = new Map<string, () => void>();

  constructor(readonly tagName: string) {}

  get clicked(): (() => void) | undefined {
    return this.listeners.get("click");
  }

  get changed(): (() => void) | undefined {
    return this.listeners.get("change");
  }

  append(...children: StandIn[]): void {
    this.children.push(...children);
  }

  replaceChildren(...children: StandIn[]): void {
    this.children = children;
  }

  addEventListener(type: "click" | "change", listener: () => void): void {
    this.listeners.set(type, listener);
  }

  setAttribute(name: string, value: string): void {
    this.attributes.set(name, value);
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

const TABS = ["advice", "settings", "history", "lessons"] as const;
/** The tabs whose panes are showing. */
const shown = (root: StandIn): string[] => TABS.filter((tab) => !byId(root, `pane-${tab}`).hidden);
/** Each tab's aria-selected, in tab order. */
const selected = (root: StandIn): (string | undefined)[] =>
  TABS.map((tab) => byId(root, `tab-${tab}`).attributes.get("aria-selected"));

test("the panel has the tabs Advice, Settings, History and Lessons, and opens on Advice", async () => {
  const { page } = await open();
  expect(TABS.map((tab) => byId(page, `tab-${tab}`).textContent)).toEqual([
    "Advice",
    "Settings",
    "History",
    "Lessons",
  ]);
  expect(shown(page)).toEqual(["advice"]);
  expect(selected(page)).toEqual(["true", "false", "false", "false"]);
});

test("clicking a tab shows its pane alone and marks that tab selected", async () => {
  const { page } = await open();
  byId(page, "tab-history").clicked?.();
  expect(shown(page)).toEqual(["history"]);
  expect(selected(page)).toEqual(["false", "false", "true", "false"]);
  byId(page, "tab-advice").clicked?.();
  expect(shown(page)).toEqual(["advice"]);
  expect(selected(page)).toEqual(["true", "false", "false", "false"]);
});

test("each tab controls its pane and each pane is labelled by its tab", async () => {
  const { page } = await open();
  expect(byId(page, "tabs").attributes.get("role")).toBe("tablist");
  for (const tab of TABS) {
    const button = byId(page, `tab-${tab}`).attributes;
    const pane = byId(page, `pane-${tab}`).attributes;
    expect([button.get("role"), button.get("aria-controls")]).toEqual(["tab", `pane-${tab}`]);
    expect([pane.get("role"), pane.get("aria-labelledby")]).toEqual(["tabpanel", `tab-${tab}`]);
  }
});

test("the advice and the read button are on the Advice tab, the universe on Settings", async () => {
  const { page } = await open();
  expect(byId(byId(page, "pane-advice"), "advice").tagName).toBe("section");
  expect(byId(byId(page, "pane-advice"), "read").textContent).toBe("Read this page");
  expect(byId(byId(page, "pane-settings"), "universe").tagName).toBe("textarea");
  expect(byId(byId(page, "pane-settings"), "save-universe").textContent).toBe("Save universe");
});

test("the status line and the disclaimer stay outside the tabs, shown on every one", async () => {
  const { page } = await open();
  for (const tab of TABS) {
    const pane = byId(page, `pane-${tab}`);
    expect(all(pane).some((element) => ["status", "notice"].includes(element.id))).toBe(false);
  }
  expect(byId(page, "status").tagName).toBe("p");
  expect(byId(page, "notice").tagName).toBe("footer");
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

/** The advice once the portfolio and watchlist are read, with the universe and `kept` saved
 * first, and the status line beside it. */
const adviceWith = async (kept: Readonly<Record<string, unknown>>) => {
  await putSetting(db, SETTINGS.universe, ["BBCA", "TLKM", "UNVR"]);
  for (const [name, value] of Object.entries(kept)) {
    await putSetting(db, name, value);
  }
  const { page, panel, chrome } = await open();
  chrome.send(snapshot("portfolio"));
  chrome.send(snapshot("watchlist"));
  await panel.settled();
  return { advice: textOf(byId(page, "advice")), status: byId(page, "status").textContent };
};

test("advice is given and remembered under the strategy kept in Settings", async () => {
  const { advice } = await adviceWith({ [KEPT.strategy]: { name: "buy-and-hold", values: [] } });
  expect(advice[0]).toBe("Advice for 2025-06-17");
  expect((await storedMemory(db, "buy-and-hold"))?.day).toBe("2025-06-17");
  expect(await storedMemory(db, "dividend-growth")).toBeUndefined();
});

test("a kept strategy no strategy has is refused, naming the setting", async () => {
  const { status } = await adviceWith({ [KEPT.strategy]: { name: "no-such", values: [] } });
  expect(status).toBe(
    "Something went wrong: Error: the setting strategy is not as Settings keeps it",
  );
});

test("a kept strategy value out of its bounds is refused, naming the setting", async () => {
  const kept = { name: "ma-trend", values: [["fast_days", "0"]] };
  const { status } = await adviceWith({ [KEPT.strategy]: kept });
  expect(status).toBe(
    "Something went wrong: Error: the setting strategy is not as Settings keeps it",
  );
});

/** The advice of buy-and-hold over BBRI and UNVR, with `kept` saved too, once the portfolio,
 * watchlist and flags are read. The page's cash available to buy is above its cash balance,
 * so the cash balance is what is spent (#511). */
const ordersWith = async (kept: Readonly<Record<string, unknown>>) => {
  await putSetting(db, SETTINGS.universe, ["BBRI", "UNVR"]);
  await putSetting(db, KEPT.strategy, { name: "buy-and-hold", values: [] });
  for (const [name, value] of Object.entries(kept)) {
    await putSetting(db, name, value);
  }
  const { page: body, panel, chrome } = await open();
  chrome.send(snapshot("portfolio"));
  chrome.send(snapshot("watchlist"));
  chrome.send(snapshot("flags"));
  await panel.settled();
  return textOf(byId(body, "advice"));
};

test("advice follows the risk limits kept in Settings", async () => {
  const limits = { maxWeight: "0.01", minLots: "1", dailyLoss: "0.05", maxDrawdown: "0.2" };
  const advice = await ordersWith({ [KEPT.limits]: limits });
  expect(advice).toContain("Buy BBRI cut to 6 lots: cut to the 1.00% limit per stock.");
  expect(advice).toContain("Buy UNVR cut to 16 lots: cut to the 1.00% limit per stock.");
});

test("kept risk limits not as Settings keeps them are refused, naming the setting", async () => {
  const { status } = await adviceWith({ [KEPT.limits]: { maxWeight: "lots" } });
  expect(status).toBe(
    "Something went wrong: Error: the setting risk-limits is not as Settings keeps it",
  );
});

test("advice follows the fee preset kept in Settings", async () => {
  const advice = await ordersWith({ [KEPT.feePreset]: "ajaib" });
  expect(advice[1]).toBe(
    "Buy 9 lots of BBRI at a limit of IDR 4,560, estimated fees IDR 6,210: buy-and-hold: part of its day-one set, bought with an equal share of the cash.",
  );
});

test("a kept fee preset no broker has is refused, naming the setting", async () => {
  const { status } = await adviceWith({ [KEPT.feePreset]: "no-such" });
  expect(status).toBe(
    "Something went wrong: Error: the setting fee-preset is not as Settings keeps it",
  );
});

// Settings: the strategy and its settings (#239 AC1), each bounded as the registry says and
// refused out of range by name.

/** The input of each setting shown for the chosen strategy, by setting name. */
const settingInputs = (root: StandIn): Map<string, StandIn> =>
  new Map(
    all(byId(root, "strategy-settings"))
      .filter((element) => element.tagName === "input")
      .map((input) => [input.id.replace(/^setting-/u, ""), input]),
  );

const choose = (root: StandIn, name: string): void => {
  byId(root, "strategy").value = name;
  byId(root, "strategy").changed?.();
};

test("Settings offers every strategy by name, with dividend-growth chosen before any is kept", async () => {
  const { page } = await open();
  const settings = byId(page, "pane-settings");
  const picker = byId(settings, "strategy");
  expect(picker.tagName).toBe("select");
  expect(byId(settings, "strategy-label").htmlFor).toBe("strategy");
  expect(byId(settings, "strategy-label").textContent).toBe("Strategy");
  expect(
    picker.children.map((option) => [option.tagName, option.value, option.textContent]),
  ).toEqual([...STRATEGIES.keys()].map((name) => ["option", name, name]));
  expect(picker.value).toBe("dividend-growth");
  expect(byId(settings, "strategy-summary").textContent).toBe(
    STRATEGIES.get("dividend-growth")?.summary,
  );
});

test("each setting of the kept strategy has a labelled input holding its kept value, with its help", async () => {
  await putSetting(db, KEPT.strategy, { name: "ma-trend", values: [["fast_days", "20"]] });
  const { page } = await open();
  expect(byId(page, "strategy").value).toBe("ma-trend");
  const inputs = settingInputs(page);
  expect([...inputs.keys()]).toEqual(["fast_days", "slow_days"]);
  expect(inputs.get("fast_days")?.value).toBe("20");
  const slow = STRATEGIES.get("ma-trend")?.settings.find((each) => each.name === "slow_days");
  expect(inputs.get("slow_days")?.value).toBe(slow?.default.toString());
  for (const each of STRATEGIES.get("ma-trend")?.settings ?? []) {
    const label = byId(page, `setting-${each.name}-label`);
    expect([label.tagName, label.htmlFor, label.textContent]).toEqual([
      "label",
      `setting-${each.name}`,
      each.name,
    ]);
    const input = byId(page, `setting-${each.name}`);
    expect(input.attributes.get("aria-describedby")).toBe(`setting-${each.name}-help`);
    expect(byId(page, `setting-${each.name}-help`).textContent).toBe(each.help);
  }
});

test("choosing another strategy shows its summary and its settings at their defaults", async () => {
  const { page } = await open();
  choose(page, "buy-and-hold");
  expect(settingInputs(page).size).toBe(0);
  expect(byId(page, "strategy-summary").textContent).toBe(STRATEGIES.get("buy-and-hold")?.summary);
  choose(page, "ma-trend");
  expect([...settingInputs(page)].map(([name, input]) => [name, input.value])).toEqual(
    STRATEGIES.get("ma-trend")?.settings.map((each) => [each.name, each.default.toString()]),
  );
});

test("the strategy saved is kept with the values typed, and advice follows it", async () => {
  await putSetting(db, SETTINGS.universe, ["BBRI", "UNVR"]);
  const { page, panel, chrome } = await open();
  chrome.send(snapshot("portfolio"));
  chrome.send(snapshot("watchlist"));
  await panel.settled();
  choose(page, "ma-trend");
  const fast = settingInputs(page).get("fast_days");
  if (fast === undefined) {
    throw new Error("no fast_days input");
  }
  fast.value = " 10 ";
  byId(page, "save-strategy").clicked?.();
  await panel.settled();
  const slow = STRATEGIES.get("ma-trend")?.settings.find((each) => each.name === "slow_days");
  expect(await settingOf(db, KEPT.strategy)).toEqual({
    name: "ma-trend",
    values: [
      ["fast_days", "10"],
      ["slow_days", slow?.default.toString()],
    ],
  });
  expect(byId(page, "status").textContent).toBe("Strategy saved: ma-trend.");
  expect((await storedMemory(db, "ma-trend"))?.day).toBe("2025-06-17");
});

test("a typed setting out of its bounds is refused by name, and nothing is kept", async () => {
  const { page, panel } = await open();
  choose(page, "ma-trend");
  const fast = settingInputs(page).get("fast_days");
  if (fast === undefined) {
    throw new Error("no fast_days input");
  }
  fast.value = "0";
  byId(page, "save-strategy").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe(
    "Strategy not saved: fast_days must be from 1 to 499, got 0",
  );
  expect(await settingOf(db, KEPT.strategy)).toBeUndefined();
});

test("a typed setting that is not a whole number is refused by name, and nothing is kept", async () => {
  const { page, panel } = await open();
  choose(page, "ma-trend");
  const slow = settingInputs(page).get("slow_days");
  if (slow === undefined) {
    throw new Error("no slow_days input");
  }
  slow.value = "ten";
  byId(page, "save-strategy").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe(
    'Strategy not saved: slow_days must be a whole number, got "ten"',
  );
  expect(await settingOf(db, KEPT.strategy)).toBeUndefined();
});

test("a kept strategy not as Settings keeps it still opens the panel, and says so", async () => {
  await putSetting(db, KEPT.strategy, "dividend-growth");
  const { page, panel } = await open();
  await panel.settled();
  expect(byId(page, "strategy").value).toBe("dividend-growth");
  expect(byId(page, "status").textContent).toBe(
    "Something went wrong: Error: the setting strategy is not as Settings keeps it",
  );
});
