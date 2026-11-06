/** The side panel (spec §10.2, §10.3, #238): it records each broker page the content script
 * sends, asks the active tab for its page on "Read this page", keeps the universe typed into
 * Settings, and shows the day's advice, each on its tab (Advice, Settings, History, Lessons), with
 * the status line and the disclaimer outside the tabs. One thing is done
 * at a time, in the order asked; any failure is shown on the panel, never dropped.
 *
 * Chrome, the page and the clock come in as arguments so the unit run can stand them in. The
 * page is written with elements and their text only, never markup. */

import { IdxCalendar, shippedSessions, type PageKind } from "@steadyhand/core";
import { putSetting, remember } from "@steadyhand/history";
import { adviceModel, type PanelReads } from "./advice-model.ts";
import { adviceView, CHOICE_LINE, DISCLAIMER } from "./advice-view.ts";
import { isSnapshot, type Ask } from "./messages.ts";
import { keptUniverse, recordedFrom, recordRead, SETTINGS } from "./record-read.ts";
import { keptSettings } from "./settings.ts";

/** An element as the panel uses one, whose children are elements `E` (the browser's
 * `HTMLElement` is one, with `E` = `HTMLElement`). */
export interface PanelElement<E> {
  id: string;
  textContent: string | null;
  /** As the browser types it: `"until-found"` is a kind of hidden the panel never uses. */
  hidden: boolean | "until-found";
  setAttribute(name: string, value: string): void;
  append(...children: E[]): void;
  replaceChildren(...children: E[]): void;
  addEventListener(type: "click", listener: () => void): void;
}

/** The panel's page as the panel uses it: the browser's `document` is one. */
export interface PanelDocument<E extends PanelElement<E>> {
  readonly body: E;
  createElement(tag: "textarea"): E & { value: string };
  createElement(tag: "label"): E & { htmlFor: string };
  createElement(tag: "section" | "div" | "button" | "p" | "footer" | "h2"): E;
}

/** The part of `chrome.runtime` the panel uses: the content script's snapshots arrive here. */
export interface PanelRuntime {
  readonly onMessage: { addListener(listener: (message: unknown) => boolean): void };
}

/** The part of `chrome.tabs` the panel uses. Asking the active tab needs no `tabs` permission. */
export interface PanelTabs {
  query(query: {
    active: true;
    currentWindow: true;
  }): Promise<readonly { id?: number | undefined }[]>;
  sendMessage(tabId: number, message: Ask): Promise<unknown>;
}

export interface PanelInputs<E extends PanelElement<E>> {
  readonly page: PanelDocument<E>;
  readonly db: IDBDatabase;
  readonly runtime: PanelRuntime;
  readonly tabs: PanelTabs;
  readonly clock: () => Date;
}

export interface Panel {
  /** Resolves once everything asked so far is done. */
  settled(): Promise<void>;
}

const CALENDAR = IdxCalendar.shipped();
const SESSIONS = shippedSessions();

/** What Chrome says when a tab has no content script of the extension to answer. */
const NO_RECEIVER = "Receiving end does not exist";
const NOT_A_BROKER_TAB = "This tab shows no broker page steadyhand reads.";

/** An IDX stock code: four capital letters. */
const STOCK_CODE = /^[A-Z]{4}$/u;

/** The symbols typed into the universe box: split on spaces, commas and new lines, in capitals,
 * each once, in the order first typed. */
const symbolsIn = (typed: string): readonly string[] => [
  ...new Set(
    typed
      .split(/[\s,]+/u)
      .filter((word) => word !== "")
      .map((word) => word.toUpperCase()),
  ),
];

/** The panel's tabs, in order, each with its name. */
const TABS = [
  ["advice", "Advice"],
  ["settings", "Settings"],
  ["history", "History"],
  ["lessons", "Lessons"],
] as const;
type Tab = (typeof TABS)[number][0];

/** How the status line names each page read. */
const PAGE_NAMES: Readonly<Record<PageKind, string>> = {
  portfolio: "the portfolio page",
  watchlist: "the watchlist page",
  flags: "the flags page",
  "cash-movements": "the cash movement page",
  "corporate-actions": "the corporate action page",
  dividends: "the dividend page",
  "stock-detail": "the stock's page",
};

export const startPanel = async <E extends PanelElement<E>>(
  inputs: PanelInputs<E>,
): Promise<Panel> => {
  const { page, db } = inputs;
  const named = <T extends E>(made: T, id: string, text = ""): T => {
    made.id = id;
    made.textContent = text;
    return made;
  };
  const element = (
    tag: "section" | "div" | "button" | "p" | "footer" | "h2",
    id: string,
    text = "",
  ) => named(page.createElement(tag), id, text);

  const advice = element("section", "advice");
  const read = element("button", "read", "Read this page");
  const label = named(
    page.createElement("label"),
    "universe-label",
    "Universe: the stocks to choose from",
  );
  const universe = named(page.createElement("textarea"), "universe");
  label.htmlFor = universe.id;
  const save = element("button", "save-universe", "Save universe");
  const status = element("p", "status");
  const footer = element("footer", "notice");
  footer.append(element("p", "disclaimer", DISCLAIMER), element("p", "choice", CHOICE_LINE));

  // The tabs (spec §10.2): one pane shows at a time; the status line and the notice stay outside
  // them, so they show on every tab.
  const tabList = element("div", "tabs");
  tabList.setAttribute("role", "tablist");
  const panes: Readonly<Record<Tab, E>> = {
    advice: element("section", "pane-advice"),
    settings: element("section", "pane-settings"),
    history: element("section", "pane-history"),
    lessons: element("section", "pane-lessons"),
  };
  const tabs = TABS.map(([tab, name]) => {
    const button = element("button", `tab-${tab}`, name);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", `pane-${tab}`);
    const pane = panes[tab];
    pane.setAttribute("role", "tabpanel");
    pane.setAttribute("aria-labelledby", button.id);
    return { tab, button, pane };
  });
  const show = (chosen: Tab): void => {
    for (const { tab, button, pane } of tabs) {
      pane.hidden = tab !== chosen;
      button.setAttribute("aria-selected", String(tab === chosen));
    }
  };
  for (const { tab, button } of tabs) {
    button.addEventListener("click", () => {
      show(tab);
    });
    tabList.append(button);
  }
  panes.advice.append(read, advice);
  panes.settings.append(label, universe, save);
  show("advice");
  page.body.append(status, tabList, ...tabs.map(({ pane }) => pane), footer);

  let reads: PanelReads = {};

  const redraw = async (): Promise<void> => {
    const { strategy, limits, market } = await keptSettings(db);
    const recorded = await recordedFrom(db, strategy.name);
    const model = adviceModel({
      reads,
      recorded,
      strategy,
      rules: market,
      limits,
      calendar: CALENDAR,
      sessions: SESSIONS,
      now: inputs.clock(),
    });
    if (model.state === "advice") {
      await remember(db, strategy.name, model.remember);
    }
    const lines = adviceView(model, market).flatMap((section) => [
      element("h2", "", section.heading),
      ...section.lines.map((line) => element("p", "", line)),
    ]);
    advice.replaceChildren(...lines);
  };

  const recordPage = async (html: string): Promise<void> => {
    const { market } = await keptSettings(db);
    const rules = { calendar: CALENDAR, sessions: SESSIONS, market };
    const recording = await recordRead(db, html, inputs.clock(), reads, rules);
    if ("refused" in recording) {
      status.textContent = `This page was not read: ${recording.refused}`;
      return;
    }
    reads = recording.reads;
    status.textContent = `Read ${PAGE_NAMES[recording.kind]}.`;
    await redraw();
  };

  const askActiveTab = async (): Promise<void> => {
    const [tab] = await inputs.tabs.query({ active: true, currentWindow: true });
    if (tab?.id === undefined) {
      status.textContent = NOT_A_BROKER_TAB;
      return;
    }
    let answer: unknown;
    try {
      answer = await inputs.tabs.sendMessage(tab.id, { kind: "ask" });
    } catch (failure) {
      if (!String(failure).includes(NO_RECEIVER)) {
        throw failure;
      }
    }
    if (!isSnapshot(answer)) {
      status.textContent = NOT_A_BROKER_TAB;
      return;
    }
    await recordPage(answer.html);
  };

  const saveUniverse = async (): Promise<void> => {
    const symbols = symbolsIn(universe.value);
    const wrong = symbols.find((symbol) => !STOCK_CODE.test(symbol));
    if (wrong !== undefined) {
      status.textContent = `Universe not saved: "${wrong}" is not a four-letter IDX stock code.`;
      return;
    }
    await putSetting(db, SETTINGS.universe, symbols);
    status.textContent = `Universe saved: ${symbols.length.toString()} stocks.`;
    await redraw();
  };

  let queue = Promise.resolve();
  /** Run `job` after everything asked before it; a failure is shown, and the queue goes on. */
  const run = (job: () => Promise<void>): void => {
    queue = queue.then(job).catch((failure: unknown) => {
      status.textContent = `Something went wrong: ${String(failure)}`;
    });
  };

  inputs.runtime.onMessage.addListener((message) => {
    if (isSnapshot(message)) {
      run(() => recordPage(message.html));
    }
    return false;
  });
  read.addEventListener("click", () => {
    run(askActiveTab);
  });
  save.addEventListener("click", () => {
    run(saveUniverse);
  });

  universe.value = (await keptUniverse(db))?.join(" ") ?? "";
  run(redraw);
  return { settled: () => queue };
};
