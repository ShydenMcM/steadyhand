/** The side panel (spec §10.2, §10.3, #238): it records each broker page the content script
 * sends, asks the active tab for its page on "Read this page", keeps the universe typed into
 * Settings, and shows the day's advice, each on its tab (Advice, Settings, History, Lessons), with
 * the status line and the disclaimer outside the tabs. One thing is done
 * at a time, in the order asked; any failure is shown on the panel, never dropped.
 *
 * Chrome, the page and the clock come in as arguments so the unit run can stand them in. The
 * page is written with elements and their text only, never markup. */

import {
  asDay,
  IDR,
  IdxCalendar,
  Money,
  shippedSessions,
  STRATEGIES,
  type PageKind,
} from "@steadyhand/core";
import {
  forgetEverything,
  openHistory,
  putSetting,
  recordTyped,
  remember,
  riskRecord,
  settingOf,
  stockHistory,
  type ExtensionStorage,
} from "@steadyhand/history";
import { adviceModel, type PanelReads } from "./advice-model.ts";
import { adviceView, CHOICE_LINE, DISCLAIMER } from "./advice-view.ts";
import type { LessonModule } from "./lessons.ts";
import { isSnapshot, type Ask } from "./messages.ts";
import { excludedOf, keptUniverse, recordedFrom, recordRead, SETTINGS } from "./record-read.ts";
import {
  FEE_PRESETS,
  feePresetOf,
  KEPT,
  keptSettings,
  limitsOf,
  storedLimits,
  storedStrategy,
  strategyOf,
  typedLimits,
  typedStrategy,
  type ChosenStrategy,
  type TypedLimits,
} from "./settings.ts";

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
  addEventListener(type: "click" | "change", listener: () => void): void;
}

/** The panel's page as the panel uses it: the browser's `document` is one. */
export interface PanelDocument<E extends PanelElement<E>> {
  readonly body: E;
  createElement(tag: "textarea" | "select" | "input" | "option"): E & {
    value: string;
    /** A file input's files: the browser's `FileList` is one. */
    readonly files: ChosenFiles | null;
  };
  createElement(tag: "label"): E & { htmlFor: string };
  createElement(tag: "section" | "div" | "button" | "p" | "footer" | "h2" | "h3"): E;
}

/** The files a file input holds, as the panel reads them. */
export interface ChosenFiles {
  item(place: number): { text(): Promise<string> } | null;
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
  /** Where `db` was opened: "forget everything" deletes it there and opens it again, empty. */
  readonly factory: IDBFactory;
  /** The extension's own storage, which "forget everything" clears. */
  readonly storage: ExtensionStorage;
  /** The lesson catalogue the Lessons tab renders. */
  readonly lessons: readonly LessonModule[];
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

/** Whole rupiah as typed: plain digits, or digits in threes after Indonesian thousands dots. */
const WHOLE_RUPIAH = /^(?:\d+|\d{1,3}(?:\.\d{3})+)$/u;

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

/** The kinds of cash movement the user may type, each with its name. */
const MOVEMENT_KINDS = [
  ["deposit", "Deposit"],
  ["withdrawal", "Withdrawal"],
] as const;

/** How Settings names each risk limit, in order. */
const LIMIT_NAMES: Readonly<Record<keyof TypedLimits, string>> = {
  maxWeight: "The largest share of one stock, in percent",
  minLots: "The smallest buy, in lots",
  dailyLoss: "The one-day fall that halts ordering, in percent",
  maxDrawdown: "The fall from the high that halts ordering, in percent",
};

/** Why a typed setting was refused: every refusal of one is a RangeError naming what is wrong. */
const refusal = (failure: unknown): string => String(failure).replace(/^RangeError: /u, "");

/** What `read` makes of the setting `name` kept in `db`, or of nothing kept when it refuses
 * that: the advice redraw then names the refused setting on the status line. */
const keptOr = async <T>(
  db: IDBDatabase,
  name: string,
  read: (value: unknown) => T,
): Promise<T> => {
  const value: unknown = await settingOf(db, name);
  try {
    return read(value);
  } catch {
    return read(undefined);
  }
};

/** The panel's tabs, in order, each with its name. */
const TABS = [
  ["advice", "Advice"],
  ["settings", "Settings"],
  ["history", "History"],
  ["lessons", "Lessons"],
] as const;
type Tab = (typeof TABS)[number][0];

/** `count` with its noun, in the singular for 1. */
const counted = (count: bigint, one: string, many: string): string =>
  `${count.toString()} ${count === 1n ? one : many}`;

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
  const { page } = inputs;
  let { db } = inputs;
  const named = <T extends E>(made: T, id: string, text = ""): T => {
    made.id = id;
    made.textContent = text;
    return made;
  };
  const element = (
    tag: "section" | "div" | "button" | "p" | "footer" | "h2" | "h3",
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

  // Paste and import (#239 AC4): a saved page's text goes to the readers; the file is read here
  // and never leaves the panel.
  const pasteLabel = named(
    page.createElement("label"),
    "paste-label",
    "Or paste a broker page you saved",
  );
  const paste = named(page.createElement("textarea"), "paste");
  pasteLabel.htmlFor = paste.id;
  const readPaste = element("button", "read-paste", "Read the pasted page");
  const importLabel = named(
    page.createElement("label"),
    "import-label",
    "Or open a broker page you saved",
  );
  const importer = named(page.createElement("input"), "import");
  importer.setAttribute("type", "file");
  importer.setAttribute("accept", ".html,.htm");
  importLabel.htmlFor = importer.id;

  const goalLabel = named(
    page.createElement("label"),
    "goal-label",
    "Monthly income goal, in rupiah",
  );
  const goal = named(page.createElement("input"), "goal");
  goalLabel.htmlFor = goal.id;
  const saveGoal = element("button", "save-goal", "Save goal");

  // The risk limits, the rates as percentages (#239 AC1).
  const limitInput = (limit: keyof TypedLimits) => {
    const input = named(page.createElement("input"), `limit-${limit}`);
    const limitLabel = named(page.createElement("label"), `${input.id}-label`, LIMIT_NAMES[limit]);
    limitLabel.htmlFor = input.id;
    return { label: limitLabel, input };
  };
  const limitRows = {
    maxWeight: limitInput("maxWeight"),
    minLots: limitInput("minLots"),
    dailyLoss: limitInput("dailyLoss"),
    maxDrawdown: limitInput("maxDrawdown"),
  };
  const saveLimits = element("button", "save-limits", "Save risk limits");

  // The fee preset, from the shipped fees file's presets.
  const presetLabel = named(page.createElement("label"), "fee-preset-label", "Broker fee preset");
  const preset = named(page.createElement("select"), "fee-preset");
  presetLabel.htmlFor = preset.id;
  preset.append(
    ...FEE_PRESETS.map((name) => {
      const option = named(page.createElement("option"), "", name);
      option.value = name;
      return option;
    }),
  );
  const savePreset = element("button", "save-fee-preset", "Save fee preset");

  // Deposits and withdrawals the user types (spec §8), kept as typed and listed back.
  const movementKind = named(page.createElement("select"), "movement-kind");
  movementKind.append(
    ...MOVEMENT_KINDS.map(([kind, name]) => {
      const option = named(page.createElement("option"), "", name);
      option.value = kind;
      return option;
    }),
  );
  const movementDay = named(page.createElement("input"), "movement-day");
  const movementAmount = named(page.createElement("input"), "movement-amount");
  const movementLabels = (
    [
      [movementKind, "Deposit or withdrawal"],
      [movementDay, "Day, such as 2025-06-16"],
      [movementAmount, "Amount, in rupiah"],
    ] as const
  ).flatMap(([input, name]) => {
    const movementLabel = named(page.createElement("label"), `${input.id}-label`, name);
    movementLabel.htmlFor = input.id;
    return [movementLabel, input];
  });
  const addMovement = element("button", "add-movement", "Keep this deposit or withdrawal");
  const typedMovements = element("section", "typed-movements");
  const showTyped = async (): Promise<void> => {
    const typed = [...(await riskRecord(db)).typed].sort((one, other) =>
      one.day.localeCompare(other.day),
    );
    typedMovements.replaceChildren(
      ...(typed.length === 0
        ? [element("p", "", "No deposits or withdrawals typed.")]
        : typed.map((entry) =>
            element("p", "", `${entry.day}: ${entry.kind} of ${entry.amount.toString()}`),
          )),
    );
  };

  // The exclusions: a stock per line, its code and then the user's reason (spec §6.1).
  const exclusionsLabel = named(
    page.createElement("label"),
    "exclusions-label",
    "Excluded stocks: one per line, the code and then your reason",
  );
  const exclusions = named(page.createElement("textarea"), "exclusions");
  exclusionsLabel.htmlFor = exclusions.id;
  const saveExclusions = element("button", "save-exclusions", "Save exclusions");

  // The strategy and its settings (#239 AC1): a labelled input per setting, its help read with it.
  const strategyLabel = named(page.createElement("label"), "strategy-label", "Strategy");
  const picker = named(page.createElement("select"), "strategy");
  strategyLabel.htmlFor = picker.id;
  picker.append(
    ...[...STRATEGIES.keys()].map((name) => {
      const option = named(page.createElement("option"), "", name);
      option.value = name;
      return option;
    }),
  );
  const summary = element("p", "strategy-summary");
  const strategySettings = element("div", "strategy-settings");
  const saveStrategy = element("button", "save-strategy", "Save strategy");
  let settingInputs: ReadonlyMap<string, { value: string }> = new Map();
  /** Show `chosen` in the picker, with each of its settings at its value or its default. */
  const showStrategy = (chosen: ChosenStrategy): void => {
    picker.value = chosen.name;
    const entry = STRATEGIES.get(chosen.name);
    summary.textContent = entry?.summary ?? "";
    const rows = (entry?.settings ?? []).map((each) => {
      const id = `setting-${each.name}`;
      const label = named(page.createElement("label"), `${id}-label`, each.name);
      label.htmlFor = id;
      const input = named(page.createElement("input"), id);
      input.value = (chosen.values.get(each.name) ?? each.default).toString();
      input.setAttribute("aria-describedby", `${id}-help`);
      return { name: each.name, label, input, help: element("p", `${id}-help`, each.help) };
    });
    settingInputs = new Map(rows.map(({ name, input }) => [name, input]));
    strategySettings.replaceChildren(
      ...rows.flatMap(({ label, input, help }) => [label, input, help]),
    );
  };
  // History (#239 AC2): per stock what is recorded, and "forget everything", asked first.
  const recordingNote = element(
    "p",
    "recording-note",
    "steadyhand records a broker page only while this panel is open beside it.",
  );
  const stocksRecorded = element("section", "stock-history");
  const showHistory = async (): Promise<void> => {
    const stocks = await stockHistory(db);
    stocksRecorded.replaceChildren(
      ...(stocks.length === 0
        ? [element("p", "", "Nothing is recorded yet.")]
        : stocks.map((stock) =>
            element(
              "p",
              "",
              `${stock.symbol}: ${counted(stock.days, "day", "days")} recorded, ${counted(stock.chartReads, "chart read", "chart reads")}, ${counted(stock.dividends, "dividend", "dividends")}`,
            ),
          )),
    );
  };
  const forget = element("button", "forget", "Forget everything");
  const forgetConfirm = element("div", "forget-confirm");
  const forgetYes = element("button", "forget-yes", "Yes, forget everything");
  const forgetKeep = element("button", "forget-keep", "Keep everything");
  forgetConfirm.append(
    element(
      "p",
      "",
      "This deletes everything steadyhand has recorded and every setting. It cannot be undone.",
    ),
    forgetYes,
    forgetKeep,
  );
  forgetConfirm.hidden = true;

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
  panes.advice.append(read, pasteLabel, paste, readPaste, importLabel, importer, advice);
  panes.settings.append(
    strategyLabel,
    picker,
    summary,
    strategySettings,
    saveStrategy,
    goalLabel,
    goal,
    saveGoal,
    ...Object.values(limitRows).flatMap((row) => [row.label, row.input]),
    saveLimits,
    presetLabel,
    preset,
    savePreset,
    ...movementLabels,
    addMovement,
    typedMovements,
    label,
    universe,
    save,
    exclusionsLabel,
    exclusions,
    saveExclusions,
  );
  panes.history.append(recordingNote, stocksRecorded, forget, forgetConfirm);
  // Lessons (#239 AC3): each module's heading, then each of its lessons as a section.
  panes.lessons.append(
    ...(inputs.lessons.length === 0
      ? [element("p", "", "The lessons come in a later release.")]
      : inputs.lessons.flatMap((module) => [
          element("h2", "", module.title),
          ...module.lessons.map((lesson) => {
            const section = element("section", `lesson-${lesson.id}`);
            const title = element("h3", `${section.id}-title`, lesson.title);
            section.setAttribute("aria-labelledby", title.id);
            section.append(
              title,
              element("p", "", lesson.summary),
              ...lesson.paragraphs.map((paragraph) => element("p", "", paragraph)),
            );
            return section;
          }),
        ])),
  );
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
    await showHistory();
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

  const readPasted = async (): Promise<void> => {
    if (paste.value.trim() === "") {
      status.textContent = "Nothing is pasted.";
      return;
    }
    await recordPage(paste.value);
  };

  const readChosenFile = async (): Promise<void> => {
    const file = importer.files?.item(0) ?? null;
    if (file === null) {
      status.textContent = "No file was chosen.";
      return;
    }
    await recordPage(await file.text());
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

  const saveChosenStrategy = async (): Promise<void> => {
    const typed = new Map([...settingInputs].map(([name, input]) => [name, input.value]));
    let chosen: ChosenStrategy;
    try {
      chosen = typedStrategy(picker.value, typed);
    } catch (refused) {
      // Every refusal of a typed strategy is a RangeError naming what is wrong.
      status.textContent = `Strategy not saved: ${refusal(refused)}`;
      return;
    }
    await putSetting(db, KEPT.strategy, storedStrategy(chosen));
    status.textContent = `Strategy saved: ${chosen.name}.`;
    await redraw();
  };

  /** Keep the goal typed, or clear it when nothing is typed (spec §9). */
  const saveTypedGoal = async (): Promise<void> => {
    const typed = goal.value.trim();
    if (typed === "") {
      await putSetting(db, SETTINGS.goal, undefined);
      status.textContent = "Income goal cleared.";
    } else if (WHOLE_RUPIAH.test(typed)) {
      await putSetting(db, SETTINGS.goal, BigInt(typed.replaceAll(".", "")).toString());
      status.textContent = "Income goal saved.";
    } else {
      status.textContent = `Income goal not saved: type whole rupiah, such as 5.000.000, got "${goal.value}"`;
      return;
    }
    await redraw();
  };

  const saveTypedLimits = async (): Promise<void> => {
    let limits: ReturnType<typeof typedLimits>;
    try {
      limits = typedLimits({
        maxWeight: limitRows.maxWeight.input.value,
        minLots: limitRows.minLots.input.value,
        dailyLoss: limitRows.dailyLoss.input.value,
        maxDrawdown: limitRows.maxDrawdown.input.value,
      });
    } catch (refused) {
      status.textContent = `Risk limits not saved: ${refusal(refused)}`;
      return;
    }
    await putSetting(db, KEPT.limits, storedLimits(limits));
    status.textContent = "Risk limits saved.";
    await redraw();
  };

  const saveChosenPreset = async (): Promise<void> => {
    await putSetting(db, KEPT.feePreset, preset.value);
    status.textContent = `Fee preset saved: ${preset.value}.`;
    await redraw();
  };

  const keepTypedMovement = async (): Promise<void> => {
    const day = movementDay.value.trim();
    try {
      asDay(day, "the day");
    } catch {
      status.textContent = `Not kept: type the day as a date such as 2025-06-16, got "${movementDay.value}"`;
      return;
    }
    const amount = movementAmount.value.trim();
    const rupiah = WHOLE_RUPIAH.test(amount) ? BigInt(amount.replaceAll(".", "")) : 0n;
    if (rupiah <= 0n) {
      status.textContent = `Not kept: type whole rupiah above 0, such as 1.000.000, got "${movementAmount.value}"`;
      return;
    }
    const kind = movementKind.value === "withdrawal" ? "withdrawal" : "deposit";
    const [, name] = kind === "withdrawal" ? MOVEMENT_KINDS[1] : MOVEMENT_KINDS[0];
    const money = new Money(rupiah, IDR);
    await recordTyped(db, { day, kind, amount: money, typedAt: inputs.clock() });
    status.textContent = `${name} of ${money.toString()} on ${day} kept.`;
    await showTyped();
    await redraw();
  };

  const saveTypedExclusions = async (): Promise<void> => {
    const excluded = new Map<string, string>();
    for (const line of exclusions.value.split("\n")) {
      const words = line.trim();
      const space = words.search(/\s/u);
      const code = space === -1 ? words : words.slice(0, space);
      const reason = space === -1 ? "" : words.slice(space).trim();
      const symbol = code.toUpperCase();
      if (symbol === "") {
        continue;
      }
      if (!STOCK_CODE.test(symbol)) {
        status.textContent = `Exclusions not saved: "${code}" is not a four-letter IDX stock code.`;
        return;
      }
      if (excluded.has(symbol)) {
        status.textContent = `Exclusions not saved: ${symbol} is listed twice.`;
        return;
      }
      excluded.set(symbol, reason);
    }
    await putSetting(db, SETTINGS.excluded, [...excluded]);
    const stocks = excluded.size === 1 ? "stock" : "stocks";
    status.textContent = `Exclusions saved: ${excluded.size.toString()} ${stocks}.`;
    await redraw();
  };

  /** Show every setting as kept, the deposits and withdrawals typed, and the history. */
  const showKept = async (): Promise<void> => {
    universe.value = (await keptUniverse(db))?.join(" ") ?? "";
    const keptGoal: unknown = await settingOf(db, SETTINGS.goal);
    goal.value = typeof keptGoal === "string" ? keptGoal : "";
    showStrategy(await keptOr(db, KEPT.strategy, strategyOf));
    const limits = await keptOr(db, KEPT.limits, limitsOf);
    limitRows.maxWeight.input.value = limits.maxWeight.mul(100).toString();
    limitRows.minLots.input.value = limits.minLots.toString();
    limitRows.dailyLoss.input.value = limits.dailyLoss.mul(100).toString();
    limitRows.maxDrawdown.input.value = limits.maxDrawdown.mul(100).toString();
    preset.value = await keptOr(db, KEPT.feePreset, feePresetOf);
    await showTyped();
    exclusions.value = [...(await keptOr(db, SETTINGS.excluded, excludedOf))]
      .map(([symbol, reason]) => `${symbol} ${reason}`.trim())
      .join("\n");
    await showHistory();
  };

  /** Forget everything, then open the history again, empty, whether or not the forget left
   * anything: what it left is named on the status line. */
  const forgetAll = async (): Promise<void> => {
    try {
      await forgetEverything(inputs.factory, db, inputs.storage);
    } finally {
      db = await openHistory(inputs.factory);
      reads = {};
      await showKept();
    }
    status.textContent = "Everything is forgotten.";
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
  readPaste.addEventListener("click", () => {
    run(readPasted);
  });
  importer.addEventListener("change", () => {
    run(readChosenFile);
  });
  save.addEventListener("click", () => {
    run(saveUniverse);
  });
  picker.addEventListener("change", () => {
    showStrategy({ name: picker.value, values: new Map() });
  });
  saveLimits.addEventListener("click", () => {
    run(saveTypedLimits);
  });
  savePreset.addEventListener("click", () => {
    run(saveChosenPreset);
  });
  saveExclusions.addEventListener("click", () => {
    run(saveTypedExclusions);
  });
  addMovement.addEventListener("click", () => {
    run(keepTypedMovement);
  });
  saveGoal.addEventListener("click", () => {
    run(saveTypedGoal);
  });
  saveStrategy.addEventListener("click", () => {
    run(saveChosenStrategy);
  });
  forget.addEventListener("click", () => {
    forgetConfirm.hidden = false;
  });
  forgetKeep.addEventListener("click", () => {
    forgetConfirm.hidden = true;
  });
  forgetYes.addEventListener("click", () => {
    forgetConfirm.hidden = true;
    run(forgetAll);
  });

  await showKept();
  run(redraw);
  return { settled: () => queue };
};
