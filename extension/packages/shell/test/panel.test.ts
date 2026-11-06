import { readFileSync } from "node:fs";
import { STRATEGIES, type PageKind } from "@steadyhand/core";
import {
  openHistory,
  putSetting,
  riskRecord,
  rowsOf,
  settingOf,
  storedMemory,
  STORES,
} from "@steadyhand/history";
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
import { FEE_PRESETS, KEPT } from "../src/settings.ts";

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

let factory: IDBFactory;
let db: IDBDatabase;

beforeEach(async () => {
  factory = new IDBFactory();
  db = await openHistory(factory);
  return () => {
    db.close();
  };
});

/** The extension's storage (`chrome.storage.local`'s shape), stood in by a map; `clears` false
 * stands in a clear that leaves its items. */
const standInStorage = (items: Record<string, unknown> = {}, clears = true) => {
  const held = new Map(Object.entries(items));
  return {
    held,
    get: () => Promise.resolve(Object.fromEntries(held)),
    clear: () => {
      if (clears) {
        held.clear();
      }
      return Promise.resolve();
    },
  };
};

const open = async (
  chrome = standInChrome(() => Promise.resolve(undefined)),
  clock = () => AFTER_CLOSE,
  storage = standInStorage(),
) => {
  const page = standInDocument();
  const panel = await startPanel({
    page,
    db,
    factory,
    storage,
    runtime: chrome.runtime,
    tabs: chrome.tabs,
    clock,
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

// Settings: the monthly income goal (#239 AC1), in whole rupiah.

const saveGoal = async (page: StandIn, panel: { settled(): Promise<void> }, typed: string) => {
  byId(page, "goal").value = typed;
  byId(page, "save-goal").clicked?.();
  await panel.settled();
  return byId(page, "status").textContent;
};

test("the income goal has a labelled input on Settings holding the kept goal", async () => {
  await putSetting(db, SETTINGS.goal, "5000000");
  const { page } = await open();
  const settings = byId(page, "pane-settings");
  expect(byId(settings, "goal").tagName).toBe("input");
  expect(byId(settings, "goal").value).toBe("5000000");
  const label = byId(settings, "goal-label");
  expect([label.tagName, label.htmlFor, label.textContent]).toEqual([
    "label",
    "goal",
    "Monthly income goal, in rupiah",
  ]);
  expect(byId(settings, "save-goal").textContent).toBe("Save goal");
});

test("the goal input is empty before any goal is kept", async () => {
  const { page } = await open();
  expect(byId(page, "goal").value).toBe("");
});

test("a goal typed with thousands dots is kept as whole rupiah", async () => {
  const { page, panel } = await open();
  expect(await saveGoal(page, panel, " 5.000.000 ")).toBe("Income goal saved.");
  expect(await settingOf(db, SETTINGS.goal)).toBe("5000000");
});

test("a goal typed as plain digits is kept as typed", async () => {
  const { page, panel } = await open();
  expect(await saveGoal(page, panel, "2500000")).toBe("Income goal saved.");
  expect(await settingOf(db, SETTINGS.goal)).toBe("2500000");
});

test("an empty goal clears the kept goal", async () => {
  await putSetting(db, SETTINGS.goal, "5000000");
  const { page, panel } = await open();
  expect(await saveGoal(page, panel, "  ")).toBe("Income goal cleared.");
  expect(await settingOf(db, SETTINGS.goal)).toBeUndefined();
});

test("a goal that is not whole rupiah is refused, naming what was typed, and nothing changes", async () => {
  await putSetting(db, SETTINGS.goal, "5000000");
  const { page, panel } = await open();
  for (const typed of ["5jt", "5.00.000", "5,000,000", "-5000"]) {
    expect(await saveGoal(page, panel, typed)).toBe(
      `Income goal not saved: type whole rupiah, such as 5.000.000, got "${typed}"`,
    );
  }
  expect(await settingOf(db, SETTINGS.goal)).toBe("5000000");
});

// Settings: the risk limits, the rates as percentages and the smallest buy in lots, and the fee
// preset (#239 AC1).

const LIMITS = [
  ["maxWeight", "The largest share of one stock, in percent"],
  ["minLots", "The smallest buy, in lots"],
  ["dailyLoss", "The one-day fall that halts ordering, in percent"],
  ["maxDrawdown", "The fall from the high that halts ordering, in percent"],
] as const;

const typeLimits = (page: StandIn, typed: Readonly<Record<string, string>>): void => {
  for (const [limit, text] of Object.entries(typed)) {
    byId(page, `limit-${limit}`).value = text;
  }
};

test("each risk limit has a labelled input on Settings, at its default before any is kept", async () => {
  const { page } = await open();
  const settings = byId(page, "pane-settings");
  for (const [limit, name] of LIMITS) {
    const label = byId(settings, `limit-${limit}-label`);
    expect([label.tagName, label.htmlFor, label.textContent]).toEqual([
      "label",
      `limit-${limit}`,
      name,
    ]);
    expect(byId(settings, `limit-${limit}`).tagName).toBe("input");
  }
  expect(LIMITS.map(([limit]) => byId(page, `limit-${limit}`).value)).toEqual([
    "10",
    "1",
    "5",
    "25",
  ]);
  expect(byId(settings, "save-limits").textContent).toBe("Save risk limits");
});

test("the kept risk limits are shown as percentages", async () => {
  const kept = { maxWeight: "0.2", minLots: "2", dailyLoss: "0.04", maxDrawdown: "0.305" };
  await putSetting(db, KEPT.limits, kept);
  const { page } = await open();
  expect(LIMITS.map(([limit]) => byId(page, `limit-${limit}`).value)).toEqual([
    "20",
    "2",
    "4",
    "30.5",
  ]);
});

test("the risk limits typed are kept, and advice follows them", async () => {
  await putSetting(db, SETTINGS.universe, ["BBRI", "UNVR"]);
  await putSetting(db, KEPT.strategy, { name: "buy-and-hold", values: [] });
  const { page, panel, chrome } = await open();
  chrome.send(snapshot("portfolio"));
  chrome.send(snapshot("watchlist"));
  chrome.send(snapshot("flags"));
  typeLimits(page, { maxWeight: " 1 ", minLots: "1", dailyLoss: "5", maxDrawdown: "20" });
  byId(page, "save-limits").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe("Risk limits saved.");
  expect(await settingOf(db, KEPT.limits)).toEqual({
    maxWeight: "0.01",
    minLots: "1",
    dailyLoss: "0.05",
    maxDrawdown: "0.2",
  });
  expect(textOf(byId(page, "advice"))).toContain(
    "Buy BBRI cut to 6 lots: cut to the 1.00% limit per stock.",
  );
});

test("a risk limit typed wrong is refused by name, and nothing is kept", async () => {
  const { page, panel } = await open();
  typeLimits(page, { maxWeight: "ten" });
  byId(page, "save-limits").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe(
    'Risk limits not saved: the largest share of one stock must be a percentage, got "ten"',
  );
  typeLimits(page, { maxWeight: "120" });
  byId(page, "save-limits").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe(
    "Risk limits not saved: maxWeight must be above 0 and at most 1, got 1.2",
  );
  expect(await settingOf(db, KEPT.limits)).toBeUndefined();
});

test("the fee preset is chosen on Settings from every broker preset, custom before any is kept", async () => {
  const { page } = await open();
  const settings = byId(page, "pane-settings");
  const picker = byId(settings, "fee-preset");
  expect(picker.tagName).toBe("select");
  const label = byId(settings, "fee-preset-label");
  expect([label.tagName, label.htmlFor, label.textContent]).toEqual([
    "label",
    "fee-preset",
    "Broker fee preset",
  ]);
  expect(
    picker.children.map((option) => [option.tagName, option.value, option.textContent]),
  ).toEqual(FEE_PRESETS.map((name) => ["option", name, name]));
  expect(picker.value).toBe("custom");
  expect(byId(settings, "save-fee-preset").textContent).toBe("Save fee preset");
});

test("the fee preset chosen is kept and shown when the panel opens again", async () => {
  const first = await open();
  byId(first.page, "fee-preset").value = "ajaib";
  byId(first.page, "save-fee-preset").clicked?.();
  await first.panel.settled();
  expect(byId(first.page, "status").textContent).toBe("Fee preset saved: ajaib.");
  expect(await settingOf(db, KEPT.feePreset)).toBe("ajaib");
  const { page } = await open();
  expect(byId(page, "fee-preset").value).toBe("ajaib");
});

test("kept risk limits and fee preset not as Settings keeps them still open the panel at the defaults", async () => {
  await putSetting(db, KEPT.limits, { maxWeight: "lots" });
  await putSetting(db, KEPT.feePreset, "no-such-broker");
  const { page, panel } = await open();
  await panel.settled();
  expect(byId(page, "limit-maxWeight").value).toBe("10");
  expect(byId(page, "fee-preset").value).toBe("custom");
  expect(byId(page, "status").textContent).toBe(
    "Something went wrong: Error: the setting risk-limits is not as Settings keeps it",
  );
});

// Settings: deposits and withdrawals the user types (#239 AC1), kept as typed and listed back.

const typeMovement = async (
  page: StandIn,
  panel: { settled(): Promise<void> },
  typed: { kind: string; day: string; amount: string },
) => {
  byId(page, "movement-kind").value = typed.kind;
  byId(page, "movement-day").value = typed.day;
  byId(page, "movement-amount").value = typed.amount;
  byId(page, "add-movement").clicked?.();
  await panel.settled();
  return byId(page, "status").textContent;
};

const typedKept = async () =>
  (await riskRecord(db)).typed.map((entry) => [
    entry.day,
    entry.kind,
    entry.amount.toString(),
    entry.typedAt.toISOString(),
  ]);

test("Settings has a labelled kind, day and amount for a typed deposit or withdrawal", async () => {
  const { page } = await open();
  const settings = byId(page, "pane-settings");
  const kind = byId(settings, "movement-kind");
  expect(kind.tagName).toBe("select");
  expect(kind.children.map((option) => [option.value, option.textContent])).toEqual([
    ["deposit", "Deposit"],
    ["withdrawal", "Withdrawal"],
  ]);
  for (const [id, tag, name] of [
    ["movement-kind", "select", "Deposit or withdrawal"],
    ["movement-day", "input", "Day, such as 2025-06-16"],
    ["movement-amount", "input", "Amount, in rupiah"],
  ] as const) {
    const label = byId(settings, `${id}-label`);
    expect([label.tagName, label.htmlFor, label.textContent]).toEqual(["label", id, name]);
    expect(byId(settings, id).tagName).toBe(tag);
  }
  expect(byId(settings, "add-movement").textContent).toBe("Keep this deposit or withdrawal");
  expect(textOf(byId(settings, "typed-movements"))).toEqual(["No deposits or withdrawals typed."]);
});

test("a deposit typed is kept as typed, at the instant it was typed, and listed", async () => {
  const { page, panel } = await open();
  const typed = { kind: "deposit", day: " 2025-06-16 ", amount: "1.000.000" };
  expect(await typeMovement(page, panel, typed)).toBe(
    "Deposit of IDR 1,000,000 on 2025-06-16 kept.",
  );
  expect(await typedKept()).toEqual([
    ["2025-06-16", "deposit", "IDR 1,000,000", AFTER_CLOSE.toISOString()],
  ]);
  expect(textOf(byId(page, "typed-movements"))).toEqual(["2025-06-16: deposit of IDR 1,000,000"]);
});

test("the deposits and withdrawals typed are listed by day when the panel opens", async () => {
  // Each entry is kept under the instant it was typed, so the clock moves on a second each time.
  let ticks = 0;
  const first = await open(undefined, () => new Date(AFTER_CLOSE.getTime() + 1000 * ++ticks));
  await typeMovement(first.page, first.panel, {
    kind: "withdrawal",
    day: "2025-06-13",
    amount: "250000",
  });
  await typeMovement(first.page, first.panel, {
    kind: "deposit",
    day: "2025-06-02",
    amount: "500.000",
  });
  const { page } = await open();
  expect(textOf(byId(page, "typed-movements"))).toEqual([
    "2025-06-02: deposit of IDR 500,000",
    "2025-06-13: withdrawal of IDR 250,000",
  ]);
});

test("a typed day that is not a real date is refused, naming what was typed, and nothing is kept", async () => {
  const { page, panel } = await open();
  for (const day of ["2025-02-30", "16/06/2025", ""]) {
    expect(await typeMovement(page, panel, { kind: "deposit", day, amount: "1000" })).toBe(
      `Not kept: type the day as a date such as 2025-06-16, got "${day}"`,
    );
  }
  expect(await typedKept()).toEqual([]);
});

test("a typed amount that is not whole rupiah above 0 is refused, naming what was typed", async () => {
  const { page, panel } = await open();
  for (const amount of ["1jt", "0", "-500", ""]) {
    expect(await typeMovement(page, panel, { kind: "withdrawal", day: "2025-06-16", amount })).toBe(
      `Not kept: type whole rupiah above 0, such as 1.000.000, got "${amount}"`,
    );
  }
  expect(await typedKept()).toEqual([]);
});

// Settings: the exclusions (#239 AC1), each stock with the user's reason, one per line.

const saveExclusions = async (
  page: StandIn,
  panel: { settled(): Promise<void> },
  typed: string,
) => {
  byId(page, "exclusions").value = typed;
  byId(page, "save-exclusions").clicked?.();
  await panel.settled();
  return byId(page, "status").textContent;
};

test("the exclusions have a labelled text box on Settings holding those kept, one per line", async () => {
  await putSetting(db, SETTINGS.excluded, [
    ["BBRI", "Too much debt"],
    ["UNVR", ""],
  ]);
  const { page } = await open();
  const settings = byId(page, "pane-settings");
  expect(byId(settings, "exclusions").tagName).toBe("textarea");
  expect(byId(settings, "exclusions").value).toBe("BBRI Too much debt\nUNVR");
  const label = byId(settings, "exclusions-label");
  expect([label.tagName, label.htmlFor, label.textContent]).toEqual([
    "label",
    "exclusions",
    "Excluded stocks: one per line, the code and then your reason",
  ]);
  expect(byId(settings, "save-exclusions").textContent).toBe("Save exclusions");
});

test("the exclusions box is empty before any is kept", async () => {
  const { page } = await open();
  expect(byId(page, "exclusions").value).toBe("");
});

test("the exclusions typed are kept with their reasons, and advice leaves them out", async () => {
  await putSetting(db, SETTINGS.universe, ["BBRI", "UNVR"]);
  await putSetting(db, KEPT.strategy, { name: "buy-and-hold", values: [] });
  const { page, panel, chrome } = await open();
  chrome.send(snapshot("portfolio"));
  chrome.send(snapshot("watchlist"));
  chrome.send(snapshot("flags"));
  await panel.settled();
  expect(textOf(byId(page, "advice")).join("\n")).toContain("of UNVR");
  expect(await saveExclusions(page, panel, " unvr   Too  much debt \n\n")).toBe(
    "Exclusions saved: 1 stock.",
  );
  expect(await settingOf(db, SETTINGS.excluded)).toEqual([["UNVR", "Too  much debt"]]);
  const advice = textOf(byId(page, "advice")).join("\n");
  expect(advice).toContain("of BBRI");
  expect(advice).not.toContain("of UNVR");
});

test("exclusions with no reason are kept with an empty one", async () => {
  const { page, panel } = await open();
  expect(await saveExclusions(page, panel, "BBRI\nUNVR")).toBe("Exclusions saved: 2 stocks.");
  expect(await settingOf(db, SETTINGS.excluded)).toEqual([
    ["BBRI", ""],
    ["UNVR", ""],
  ]);
});

test("emptying the exclusions box keeps no exclusions", async () => {
  await putSetting(db, SETTINGS.excluded, [["BBRI", ""]]);
  const { page, panel } = await open();
  expect(await saveExclusions(page, panel, " \n")).toBe("Exclusions saved: 0 stocks.");
  expect(await settingOf(db, SETTINGS.excluded)).toEqual([]);
});

test("an exclusion that is not an IDX stock code is refused, naming it, and nothing changes", async () => {
  const { page, panel } = await open();
  expect(await saveExclusions(page, panel, "BBRI debt\nBBC4 why")).toBe(
    'Exclusions not saved: "BBC4" is not a four-letter IDX stock code.',
  );
  expect(await settingOf(db, SETTINGS.excluded)).toBeUndefined();
});

test("a stock excluded twice is refused, naming it, and nothing changes", async () => {
  const { page, panel } = await open();
  expect(await saveExclusions(page, panel, "BBRI debt\nbbri again")).toBe(
    "Exclusions not saved: BBRI is listed twice.",
  );
  expect(await settingOf(db, SETTINGS.excluded)).toBeUndefined();
});

test("kept exclusions not as Settings keeps them still open the panel with the box empty", async () => {
  await putSetting(db, SETTINGS.excluded, "BBRI");
  const { page, panel } = await open();
  await panel.settled();
  expect(byId(page, "exclusions").value).toBe("");
  expect(byId(page, "status").textContent).toBe(
    "Something went wrong: Error: the setting excluded is not as Settings keeps it",
  );
});

// History (#239 AC2, spec §10.3): per stock the days recorded, chart reads and dividends; the note
// that recording happens only while the panel is open; "forget everything", confirmed first.

/** The lines the History tab lists, one per stock. */
const historyLines = (root: StandIn): string[] => textOf(byId(root, "stock-history"));

/** Send each fixture page of `kinds`, in turn, and wait for each to be recorded. */
const readPages = async (
  opened: Awaited<ReturnType<typeof open>>,
  kinds: readonly PageKind[],
): Promise<void> => {
  for (const kind of kinds) {
    opened.chrome.send(snapshot(kind));
    await opened.panel.settled();
  }
};

test("the History tab says recording happens only while the panel is open", async () => {
  const { page } = await open();
  expect(textOf(byId(page, "pane-history"))).toContain(
    "steadyhand records a broker page only while this panel is open beside it.",
  );
});

test("History says nothing is recorded before any page is read", async () => {
  const { page } = await open();
  expect(historyLines(page)).toEqual(["Nothing is recorded yet."]);
});

test("History lists each stock read with its days, chart reads and dividends, by symbol", async () => {
  const opened = await open();
  await readPages(opened, ["portfolio", "watchlist", "stock-detail", "dividends"]);
  expect(historyLines(opened.page)).toEqual([
    "BBCA: 1 day recorded, 1 chart read, 2 dividends",
    "BBRI: 1 day recorded, 0 chart reads, 0 dividends",
    "TLKM: 1 day recorded, 0 chart reads, 0 dividends",
    "UNVR: 1 day recorded, 0 chart reads, 0 dividends",
  ]);
});

test("History lists what was recorded before the panel opened", async () => {
  await readPages(await open(), ["portfolio"]);
  const { page } = await open();
  expect(historyLines(page)).toEqual([
    "BBCA: 1 day recorded, 0 chart reads, 0 dividends",
    "TLKM: 1 day recorded, 0 chart reads, 0 dividends",
  ]);
});

test('"Forget everything" asks first, and nothing is forgotten until it is confirmed', async () => {
  const opened = await open();
  await readPages(opened, ["portfolio"]);
  const { page } = opened;
  expect(byId(page, "forget-confirm").hidden).toBe(true);
  expect(byId(page, "forget").textContent).toBe("Forget everything");
  byId(page, "forget").clicked?.();
  expect(byId(page, "forget-confirm").hidden).toBe(false);
  expect(textOf(byId(page, "forget-confirm"))).toEqual([
    "This deletes everything steadyhand has recorded and every setting. It cannot be undone.",
    "Yes, forget everything",
    "Keep everything",
  ]);
  await opened.panel.settled();
  expect(await rowsOf(db, STORES.closes)).toHaveLength(2);
});

test('"Keep everything" closes the question and forgets nothing', async () => {
  const opened = await open();
  await readPages(opened, ["portfolio"]);
  byId(opened.page, "forget").clicked?.();
  byId(opened.page, "forget-keep").clicked?.();
  await opened.panel.settled();
  expect(byId(opened.page, "forget-confirm").hidden).toBe(true);
  expect(await rowsOf(db, STORES.closes)).toHaveLength(2);
});

test("forgetting everything deletes every store and the storage, and reads back empty", async () => {
  const storage = standInStorage({ "kept-by-the-shell": true });
  const opened = await open(undefined, undefined, storage);
  await readPages(opened, ["portfolio", "watchlist", "stock-detail", "dividends"]);
  await putSetting(db, SETTINGS.universe, ["BBCA", "TLKM"]);
  const { page, panel } = opened;
  byId(page, "forget").clicked?.();
  byId(page, "forget-yes").clicked?.();
  await panel.settled();
  expect(byId(page, "status").textContent).toBe("Everything is forgotten.");
  expect(byId(page, "forget-confirm").hidden).toBe(true);
  expect(historyLines(page)).toEqual(["Nothing is recorded yet."]);
  expect(byId(page, "universe").value).toBe("");
  expect(storage.held.size).toBe(0);
  const reopened = await openHistory(factory);
  for (const store of Object.values(STORES)) {
    expect(await rowsOf(reopened, store)).toEqual([]);
  }
  reopened.close();
});

test("after forgetting everything the panel records the next page again", async () => {
  const opened = await open();
  await readPages(opened, ["watchlist"]);
  byId(opened.page, "forget").clicked?.();
  byId(opened.page, "forget-yes").clicked?.();
  await opened.panel.settled();
  await readPages(opened, ["portfolio"]);
  expect(historyLines(opened.page)).toEqual([
    "BBCA: 1 day recorded, 0 chart reads, 0 dividends",
    "TLKM: 1 day recorded, 0 chart reads, 0 dividends",
  ]);
});

test("a forget that leaves anything behind is shown, naming what is left", async () => {
  const storage = standInStorage({ "kept-by-the-shell": true }, false);
  const opened = await open(undefined, undefined, storage);
  byId(opened.page, "forget").clicked?.();
  byId(opened.page, "forget-yes").clicked?.();
  await opened.panel.settled();
  expect(byId(opened.page, "status").textContent).toBe(
    "Something went wrong: Error: forget everything left the extension's storage holding: kept-by-the-shell",
  );
  await readPages(opened, ["portfolio"]);
  expect(historyLines(opened.page)).toHaveLength(2);
});

test("after forgetting everything the advice asks for the pages again", async () => {
  const opened = await open();
  await readPages(opened, ["portfolio", "watchlist"]);
  expect(textOf(byId(opened.page, "advice"))).not.toContain("Open the portfolio page.");
  byId(opened.page, "forget").clicked?.();
  byId(opened.page, "forget-yes").clicked?.();
  await opened.panel.settled();
  expect(textOf(byId(opened.page, "advice"))).toContain("Open the portfolio page.");
});
