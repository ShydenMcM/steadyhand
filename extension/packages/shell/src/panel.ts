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
  claimsReport,
  IDR,
  IdxCalendar,
  IdxMarketRules,
  Money,
  resume,
  riskState,
  shippedSessions,
  shippedTables,
  STRATEGIES,
  type Covered,
  type Day,
  type PageKind,
} from "@steadyhand/core";
import {
  forgetEverything,
  openHistory,
  putSetting,
  recordAnswered,
  recordResume,
  recordTyped,
  remember,
  riskRecord,
  settingOf,
  stockHistory,
  type ExtensionStorage,
} from "@steadyhand/history";
import { adviceModel, type PanelReads } from "./advice-model.ts";
import { adviceView } from "./advice-view.ts";
import {
  dividendsOf,
  EXEMPTION,
  exemptionOf,
  purchasesOf,
  storedDividends,
  storedPurchases,
  typedEntry,
  wibDay,
} from "./exemption.ts";
import { taxView } from "./tax-view.ts";
import type { Block, Spans } from "./lesson-text.ts";
import type { LessonModule } from "./lessons.ts";
import { isSnapshot, type Ask } from "./messages.ts";
import { excludedOf, keptUniverse, recordedFrom, recordRead, SETTINGS } from "./record-read.ts";
import {
  FEE_PRESETS,
  feePresetOf,
  KEPT,
  keptSettings,
  languageOf,
  limitsOf,
  STOCK_CODE,
  storedLimits,
  storedStrategy,
  strategyOf,
  typedLimits,
  typedStrategy,
  WHOLE_RUPIAH,
  type ChosenStrategy,
  type TypedLimits,
} from "./settings.ts";
import { fill, LANGUAGES, WORDS, type Language, type Words } from "./words.ts";

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
  createElement(tag: "textarea" | "select" | "option"): E & {
    value: string;
    /** A file input's files: the browser's `FileList` is one. */
    readonly files: ChosenFiles | null;
  };
  createElement(tag: "input"): E & {
    value: string;
    readonly files: ChosenFiles | null;
    /** A checkbox's tick. */
    checked: boolean;
  };
  createElement(tag: "label"): E & { htmlFor: string };
  createElement(tag: ContainerTag): E;
}

/** The files a file input holds, as the panel reads them. */
export interface ChosenFiles {
  item(place: number): { text(): Promise<string> } | null;
}

/** The tags the panel makes elements of that hold text or other elements. */
type ContainerTag =
  | "section"
  | "div"
  | "button"
  | "p"
  | "footer"
  | "h2"
  | "h3"
  | "span"
  | "strong"
  | "code"
  | "ul"
  | "ol"
  | "li"
  | "table"
  | "tr"
  | "th"
  | "td";

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
/** The rules the claims are counted by: they read no fee, so the default preset serves. */
const CLAIM_RULES = new IdxMarketRules(shippedTables(), feePresetOf(undefined));

/** What Chrome says when a tab has no content script of the extension to answer. */
const NO_RECEIVER = "Receiving end does not exist";

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

/** A key of the panel's words (#251). */
type Said = keyof Words;

/** The kinds of cash movement the user may type, each with its name. */
const MOVEMENT_KINDS = [
  ["deposit", "deposit"],
  ["withdrawal", "withdrawal"],
] as const satisfies readonly (readonly [string, Said])[];

/** How Settings names each risk limit, in order. */
const LIMIT_NAMES: Readonly<Record<keyof TypedLimits, Said>> = {
  maxWeight: "limitMaxWeight",
  minLots: "limitMinLots",
  dailyLoss: "limitDailyLoss",
  maxDrawdown: "limitMaxDrawdown",
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
  ["advice", "tabAdvice"],
  ["settings", "tabSettings"],
  ["history", "tabHistory"],
  ["lessons", "tabLessons"],
  ["tax", "tabTax"],
] as const satisfies readonly (readonly [string, Said])[];
type Tab = (typeof TABS)[number][0];

/** `count` with its noun, as `one` says it for 1 and `many` for any other count. */
const counted = (count: bigint, one: string, many: string): string =>
  fill(count === 1n ? one : many, { count: count.toString() });

/** How the status line names each page read. */
const PAGE_NAMES: Readonly<Record<PageKind, Said>> = {
  portfolio: "pagePortfolio",
  watchlist: "pageWatchlist",
  flags: "pageFlags",
  "cash-movements": "pageCashMovements",
  "corporate-actions": "pageCorporateActions",
  dividends: "pageDividends",
  "stock-detail": "pageStockDetail",
};

export const startPanel = async <E extends PanelElement<E>>(
  inputs: PanelInputs<E>,
): Promise<Panel> => {
  const { page } = inputs;
  let { db } = inputs;
  // The language (#251): every element given a key keeps it, and `speak` rewrites each one's
  // text in the language chosen.
  let language: Language = "en";
  let words: Words = WORDS[language];
  const said: (readonly [E, Said])[] = [];
  /** `made` with its id and its text: the words under `key`, or `text` as given. */
  const named = <T extends E>(made: T, id: string, key?: Said, text = ""): T => {
    made.id = id;
    if (key === undefined) {
      made.textContent = text;
    } else {
      said.push([made, key]);
      made.textContent = words[key];
    }
    return made;
  };
  const element = (tag: ContainerTag, id: string, key?: Said) =>
    named(page.createElement(tag), id, key);
  /** A container holding `text` as given, in no language of the panel's. */
  const holding = (tag: ContainerTag, text: string) =>
    named(page.createElement(tag), "", undefined, text);

  /** `tag` holding `spans`, each its own element: plain text, bold or code. */
  const spanned = (tag: ContainerTag, spans: Spans): E => {
    const holder = element(tag, "");
    holder.append(
      ...spans.map((span) => holding(span.style === "plain" ? "span" : span.style, span.text)),
    );
    return holder;
  };
  const blockElement = (block: Block): E => {
    if (block.kind === "paragraph") {
      return spanned("p", block.spans);
    }
    if (block.kind === "list") {
      const listed = element(block.ordered ? "ol" : "ul", "");
      listed.append(...block.items.map((item) => spanned("li", item)));
      return listed;
    }
    const table = element("table", "");
    const row = (cells: readonly Spans[], tag: "th" | "td"): E => {
      const tr = element("tr", "");
      tr.append(...cells.map((cell) => spanned(tag, cell)));
      return tr;
    };
    table.append(row(block.heading, "th"), ...block.rows.map((cells) => row(cells, "td")));
    return table;
  };

  const advice = element("section", "advice");
  const read = element("button", "read", "read");

  // The deposits question and the resume after a halt (#517, spec §8): each shows only while
  // the risk record asks for it.
  const answerNone = element("button", "answer-none");
  /** The span the deposits question asks about, and the last read it runs from. */
  let asked: { readonly span: Covered; readonly since: Day } | null = null;
  const resumeBox = element("div", "resume-box");
  const resumeLabel = named(page.createElement("label"), "resume-label", "resumeLabel");
  const resumeName = named(page.createElement("input"), "resume");
  resumeLabel.htmlFor = resumeName.id;
  const resumeGo = element("button", "resume-go", "resume");
  resumeBox.append(resumeLabel, resumeName, resumeGo);
  const label = named(page.createElement("label"), "universe-label", "universeLabel");
  const universe = named(page.createElement("textarea"), "universe");
  label.htmlFor = universe.id;
  const save = element("button", "save-universe", "saveUniverse");

  // Paste and import (#239 AC4): a saved page's text goes to the readers; the file is read here
  // and never leaves the panel.
  const pasteLabel = named(page.createElement("label"), "paste-label", "pasteLabel");
  const paste = named(page.createElement("textarea"), "paste");
  pasteLabel.htmlFor = paste.id;
  const readPaste = element("button", "read-paste", "readPaste");
  const importLabel = named(page.createElement("label"), "import-label", "importLabel");
  const importer = named(page.createElement("input"), "import");
  importer.setAttribute("type", "file");
  importer.setAttribute("accept", ".html,.htm");
  importLabel.htmlFor = importer.id;

  const goalLabel = named(page.createElement("label"), "goal-label", "goalLabel");
  const goal = named(page.createElement("input"), "goal");
  goalLabel.htmlFor = goal.id;
  const saveGoal = element("button", "save-goal", "saveGoal");
  const contributionLabel = named(
    page.createElement("label"),
    "contribution-label",
    "contributionLabel",
  );
  const contribution = named(page.createElement("input"), "contribution");
  contributionLabel.htmlFor = contribution.id;
  const saveContribution = element("button", "save-contribution", "saveContribution");

  // The dividend reinvestment exemption (#255, spec §9.2): off until ticked; the Tax tab shows
  // only while it is on.
  const exemptionLabel = named(page.createElement("label"), "exemption-label", "exemptionLabel");
  const exemption = named(page.createElement("input"), "exemption");
  exemption.setAttribute("type", "checkbox");
  exemptionLabel.htmlFor = exemption.id;

  // The Tax tab's forms (#255 AC1): each an input per part, labelled, and its button.
  const entryForm = (
    form: "dividend" | "purchase",
    [day, stock, amount]: readonly [Said, Said, Said],
    amountPart: string,
    add: Said,
  ) => {
    const part = (id: string, name: Said) => {
      const input = named(page.createElement("input"), `${form}-${id}`);
      const partLabel = named(page.createElement("label"), `${input.id}-label`, name);
      partLabel.htmlFor = input.id;
      return { input, label: partLabel };
    };
    const parts = [part("day", day), part("stock", stock), part(amountPart, amount)] as const;
    const button = element("button", `add-${form}`, add);
    return { parts, button, list: element("section", `typed-${form}s`) };
  };
  const dividendForm = entryForm(
    "dividend",
    ["dividendDayLabel", "entryStockLabel", "dividendGrossLabel"],
    "gross",
    "addDividend",
  );
  const purchaseForm = entryForm(
    "purchase",
    ["purchaseDayLabel", "entryStockLabel", "purchaseAmountLabel"],
    "amount",
    "addPurchase",
  );
  const taxClaims = element("section", "tax-claims");

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
  const saveLimits = element("button", "save-limits", "saveLimits");

  // The fee preset, from the shipped fees file's presets.
  const presetLabel = named(page.createElement("label"), "fee-preset-label", "presetLabel");
  const preset = named(page.createElement("select"), "fee-preset");
  presetLabel.htmlFor = preset.id;
  preset.append(
    ...FEE_PRESETS.map((name) => {
      const option = named(page.createElement("option"), "", undefined, name);
      option.value = name;
      return option;
    }),
  );
  const savePreset = element("button", "save-fee-preset", "savePreset");

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
      [movementKind, "movementKindLabel"],
      [movementDay, "movementDayLabel"],
      [movementAmount, "movementAmountLabel"],
    ] as const
  ).flatMap(([input, name]) => {
    const movementLabel = named(page.createElement("label"), `${input.id}-label`, name);
    movementLabel.htmlFor = input.id;
    return [movementLabel, input];
  });
  const addMovement = element("button", "add-movement", "addMovement");
  const typedMovements = element("section", "typed-movements");
  const showTyped = async (): Promise<void> => {
    const typed = [...(await riskRecord(db)).typed].sort((one, other) =>
      one.day.localeCompare(other.day),
    );
    typedMovements.replaceChildren(
      ...(typed.length === 0
        ? [holding("p", words.noMovements)]
        : typed.map((entry) =>
            holding(
              "p",
              fill(entry.kind === "withdrawal" ? words.withdrawalLine : words.depositLine, {
                day: entry.day,
                amount: entry.amount.toString(),
              }),
            ),
          )),
    );
  };

  // The exclusions: a stock per line, its code and then the user's reason (spec §6.1).
  const exclusionsLabel = named(page.createElement("label"), "exclusions-label", "exclusionsLabel");
  const exclusions = named(page.createElement("textarea"), "exclusions");
  exclusionsLabel.htmlFor = exclusions.id;
  const saveExclusions = element("button", "save-exclusions", "saveExclusions");

  // The language (#251 AC1): each named in its own language.
  const languageLabel = named(page.createElement("label"), "language-label", "languageLabel");
  const languagePicker = named(page.createElement("select"), "language");
  languageLabel.htmlFor = languagePicker.id;
  languagePicker.append(
    ...LANGUAGES.map(([code, name]) => {
      const option = named(page.createElement("option"), "", undefined, name);
      option.value = code;
      return option;
    }),
  );
  const saveLanguage = element("button", "save-language", "saveLanguage");
  /** Speak `chosen`: every element with a key says its words in it, and the page says which. */
  const speak = (chosen: Language): void => {
    language = chosen;
    words = WORDS[chosen];
    languagePicker.value = chosen;
    page.body.setAttribute("lang", chosen);
    for (const [made, key] of said) {
      made.textContent = words[key];
    }
  };

  // The strategy and its settings (#239 AC1): a labelled input per setting, its help read with it.
  const strategyLabel = named(page.createElement("label"), "strategy-label", "strategyLabel");
  const picker = named(page.createElement("select"), "strategy");
  strategyLabel.htmlFor = picker.id;
  picker.append(
    ...[...STRATEGIES.keys()].map((name) => {
      const option = named(page.createElement("option"), "", undefined, name);
      option.value = name;
      return option;
    }),
  );
  const summary = element("p", "strategy-summary");
  const strategySettings = element("div", "strategy-settings");
  const saveStrategy = element("button", "save-strategy", "saveStrategy");
  let settingInputs: ReadonlyMap<string, { value: string }> = new Map();
  /** Show `chosen` in the picker, with each of its settings at its value or its default. */
  const showStrategy = (chosen: ChosenStrategy): void => {
    picker.value = chosen.name;
    const entry = STRATEGIES.get(chosen.name);
    summary.textContent = entry?.summary ?? "";
    const rows = (entry?.settings ?? []).map((each) => {
      const id = `setting-${each.name}`;
      const label = named(page.createElement("label"), `${id}-label`, undefined, each.name);
      label.htmlFor = id;
      const input = named(page.createElement("input"), id);
      input.value = (chosen.values.get(each.name) ?? each.default).toString();
      input.setAttribute("aria-describedby", `${id}-help`);
      const help = named(page.createElement("p"), `${id}-help`, undefined, each.help);
      return { name: each.name, label, input, help };
    });
    settingInputs = new Map(rows.map(({ name, input }) => [name, input]));
    strategySettings.replaceChildren(
      ...rows.flatMap(({ label, input, help }) => [label, input, help]),
    );
  };
  // History (#239 AC2): per stock what is recorded, and "forget everything", asked first.
  const recordingNote = element("p", "recording-note", "recordingNote");
  const stocksRecorded = element("section", "stock-history");
  const showHistory = async (): Promise<void> => {
    const stocks = await stockHistory(db);
    stocksRecorded.replaceChildren(
      ...(stocks.length === 0
        ? [holding("p", words.nothingRecorded)]
        : stocks.map((stock) =>
            holding(
              "p",
              fill(words.stockLine, {
                symbol: stock.symbol,
                days: counted(stock.days, words.dayOne, words.dayMany),
                chartReads: counted(stock.chartReads, words.chartReadOne, words.chartReadMany),
                dividends: counted(stock.dividends, words.dividendOne, words.dividendMany),
              }),
            ),
          )),
    );
  };
  const forget = element("button", "forget", "forget");
  const forgetConfirm = element("div", "forget-confirm");
  const forgetYes = element("button", "forget-yes", "forgetYes");
  const forgetKeep = element("button", "forget-keep", "forgetKeep");
  forgetConfirm.append(element("p", "", "forgetWarning"), forgetYes, forgetKeep);
  forgetConfirm.hidden = true;

  const status = element("p", "status");
  const footer = element("footer", "notice");
  footer.append(element("p", "disclaimer", "disclaimer"), element("p", "choice", "choiceLine"));

  // The tabs (spec §10.2): one pane shows at a time; the status line and the notice stay outside
  // them, so they show on every tab.
  const tabList = element("div", "tabs");
  tabList.setAttribute("role", "tablist");
  const panes: Readonly<Record<Tab, E>> = {
    advice: element("section", "pane-advice"),
    settings: element("section", "pane-settings"),
    history: element("section", "pane-history"),
    lessons: element("section", "pane-lessons"),
    tax: element("section", "pane-tax"),
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
  /** Tick the switch as `claimed` and show the Tax tab only while it is. The switch is on
   * Settings, so the Tax pane is never showing when it is unticked. */
  const showExemption = (claimed: boolean): void => {
    exemption.checked = claimed;
    for (const { tab, button } of tabs) {
      if (tab === "tax") {
        button.hidden = !claimed;
      }
    }
  };
  for (const { tab, button } of tabs) {
    button.addEventListener("click", () => {
      show(tab);
    });
    tabList.append(button);
  }
  panes.advice.append(
    read,
    answerNone,
    resumeBox,
    pasteLabel,
    paste,
    readPaste,
    importLabel,
    importer,
    advice,
  );
  panes.settings.append(
    languageLabel,
    languagePicker,
    saveLanguage,
    strategyLabel,
    picker,
    summary,
    strategySettings,
    saveStrategy,
    goalLabel,
    goal,
    saveGoal,
    contributionLabel,
    contribution,
    saveContribution,
    exemptionLabel,
    exemption,
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
  panes.tax.append(
    ...[dividendForm, purchaseForm].flatMap((form) => [
      ...form.parts.flatMap(({ label: partLabel, input }) => [partLabel, input]),
      form.button,
      form.list,
    ]),
    taxClaims,
  );
  panes.history.append(recordingNote, stocksRecorded, forget, forgetConfirm);
  // Lessons (#239 AC3): each module's heading, then each of its lessons as a section.
  panes.lessons.append(
    ...(inputs.lessons.length === 0
      ? [element("p", "", "noLessons")]
      : inputs.lessons.flatMap((module) => [
          holding("h2", module.title),
          ...module.lessons.map((lesson) => {
            const section = element("section", `lesson-${lesson.id}`);
            const title = named(
              page.createElement("h3"),
              `${section.id}-title`,
              undefined,
              lesson.title,
            );
            section.setAttribute("aria-labelledby", title.id);
            section.append(title, holding("p", lesson.summary), ...lesson.blocks.map(blockElement));
            return section;
          }),
        ])),
  );
  show("advice");
  page.body.append(status, tabList, ...tabs.map(({ pane }) => pane), footer);

  let reads: PanelReads = {};

  /** Show the deposits question and the resume box only while the risk record asks for them. */
  const showRisk = async (): Promise<void> => {
    // Limits kept wrong are named by the advice; until then the question uses the defaults.
    const limits = await keptOr(db, KEPT.limits, limitsOf);
    const state = riskState(limits, CALENDAR, await riskRecord(db));
    resumeBox.hidden = state.halt === null;
    asked =
      state.unrecorded !== null && state.judgedTo !== null
        ? { span: state.unrecorded, since: state.judgedTo }
        : null;
    answerNone.hidden = asked === null;
    answerNone.textContent = asked === null ? "" : fill(words.answerNone, { day: asked.since });
  };

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
      holding("h2", section.heading),
      ...section.lines.map((line) => holding("p", line)),
    ]);
    advice.replaceChildren(...lines);
    await showHistory();
    await showRisk();
  };

  const recordPage = async (html: string): Promise<void> => {
    const { market } = await keptSettings(db);
    const rules = { calendar: CALENDAR, sessions: SESSIONS, market };
    const recording = await recordRead(db, html, inputs.clock(), reads, rules);
    if ("refused" in recording) {
      status.textContent = fill(words.pageNotRead, { reason: recording.refused });
      return;
    }
    reads = recording.reads;
    status.textContent = fill(words.pageRead, { page: words[PAGE_NAMES[recording.kind]] });
    await redraw();
  };

  const askActiveTab = async (): Promise<void> => {
    const [tab] = await inputs.tabs.query({ active: true, currentWindow: true });
    if (tab?.id === undefined) {
      status.textContent = words.notABrokerTab;
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
      status.textContent = words.notABrokerTab;
      return;
    }
    await recordPage(answer.html);
  };

  const readPasted = async (): Promise<void> => {
    if (paste.value.trim() === "") {
      status.textContent = words.nothingPasted;
      return;
    }
    await recordPage(paste.value);
  };

  const readChosenFile = async (): Promise<void> => {
    const file = importer.files?.item(0) ?? null;
    if (file === null) {
      status.textContent = words.noFileChosen;
      return;
    }
    await recordPage(await file.text());
  };

  /** Keep the answer that the span asked about had no deposit or withdrawal. */
  const answerNoneAsked = async (): Promise<void> => {
    if (asked === null) {
      return;
    }
    await recordAnswered(db, asked.span, inputs.clock());
    status.textContent = fill(words.answeredNone, { day: asked.since });
    await redraw();
  };

  /** Resume buying when the name typed is the kept strategy's, as `resume` judges it. */
  const resumeHalt = async (): Promise<void> => {
    const { strategy, limits } = await keptSettings(db);
    const state = riskState(limits, CALENDAR, await riskRecord(db));
    const answer = resume(limits, state, strategy.name, resumeName.value.trim(), inputs.clock());
    if ("refused" in answer) {
      status.textContent = fill(words.notResumed, { reason: answer.refused });
      return;
    }
    await recordResume(db, answer.resumed);
    status.textContent = fill(words.resumed, { strategy: strategy.name });
    await redraw();
  };

  const saveUniverse = async (): Promise<void> => {
    const symbols = symbolsIn(universe.value);
    const wrong = symbols.find((symbol) => !STOCK_CODE.test(symbol));
    if (wrong !== undefined) {
      status.textContent = fill(words.universeNotSaved, { code: wrong });
      return;
    }
    await putSetting(db, SETTINGS.universe, symbols);
    status.textContent = fill(words.universeSaved, { count: symbols.length.toString() });
    await redraw();
  };

  const saveChosenStrategy = async (): Promise<void> => {
    const typed = new Map([...settingInputs].map(([name, input]) => [name, input.value]));
    let chosen: ChosenStrategy;
    try {
      chosen = typedStrategy(picker.value, typed);
    } catch (refused) {
      // Every refusal of a typed strategy is a RangeError naming what is wrong.
      status.textContent = fill(words.strategyNotSaved, { reason: refusal(refused) });
      return;
    }
    await putSetting(db, KEPT.strategy, storedStrategy(chosen));
    status.textContent = fill(words.strategySaved, { strategy: chosen.name });
    await redraw();
  };

  /** Keep the whole rupiah typed in `input` under `setting`, or clear it when nothing is typed,
   * saying which with the words named. */
  const saveTypedRupiah = async (
    input: { readonly value: string },
    setting: string,
    said: {
      readonly cleared: keyof Words;
      readonly saved: keyof Words;
      readonly notSaved: keyof Words;
    },
  ): Promise<void> => {
    const typed = input.value.trim();
    if (typed === "") {
      await putSetting(db, setting, undefined);
      status.textContent = words[said.cleared];
    } else if (WHOLE_RUPIAH.test(typed)) {
      await putSetting(db, setting, BigInt(typed.replaceAll(".", "")).toString());
      status.textContent = words[said.saved];
    } else {
      status.textContent = fill(words[said.notSaved], { typed: input.value });
      return;
    }
    await redraw();
  };

  /** Keep the goal typed, or clear it when nothing is typed (spec §9). */
  const saveTypedGoal = (): Promise<void> =>
    saveTypedRupiah(goal, SETTINGS.goal, {
      cleared: "goalCleared",
      saved: "goalSaved",
      notSaved: "goalNotSaved",
    });

  /** Keep the monthly amount added, or clear it so the projection adds 0 (spec §9.1). */
  const saveTypedContribution = (): Promise<void> =>
    saveTypedRupiah(contribution, SETTINGS.contribution, {
      cleared: "contributionCleared",
      saved: "contributionSaved",
      notSaved: "contributionNotSaved",
    });

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
      status.textContent = fill(words.limitsNotSaved, { reason: refusal(refused) });
      return;
    }
    await putSetting(db, KEPT.limits, storedLimits(limits));
    status.textContent = words.limitsSaved;
    await redraw();
  };

  const saveChosenPreset = async (): Promise<void> => {
    await putSetting(db, KEPT.feePreset, preset.value);
    status.textContent = fill(words.presetSaved, { preset: preset.value });
    await redraw();
  };

  const keepTypedMovement = async (): Promise<void> => {
    const day = movementDay.value.trim();
    try {
      asDay(day, "the day");
    } catch {
      status.textContent = fill(words.dayNotKept, { typed: movementDay.value });
      return;
    }
    const amount = movementAmount.value.trim();
    const rupiah = WHOLE_RUPIAH.test(amount) ? BigInt(amount.replaceAll(".", "")) : 0n;
    if (rupiah <= 0n) {
      status.textContent = fill(words.amountNotKept, { typed: movementAmount.value });
      return;
    }
    const kind = movementKind.value === "withdrawal" ? "withdrawal" : "deposit";
    const money = new Money(rupiah, IDR);
    await recordTyped(db, { day, kind, amount: money, typedAt: inputs.clock() });
    status.textContent = fill(kind === "withdrawal" ? words.withdrawalKept : words.depositKept, {
      amount: money.toString(),
      day,
    });
    await showTyped();
    await redraw();
  };

  const saveTypedExclusions = async (): Promise<void> => {
    const excluded = new Map<string, string>();
    for (const line of exclusions.value.split("\n")) {
      const entry = line.trim();
      const space = entry.search(/\s/u);
      const code = space === -1 ? entry : entry.slice(0, space);
      const reason = space === -1 ? "" : entry.slice(space).trim();
      const symbol = code.toUpperCase();
      if (symbol === "") {
        continue;
      }
      if (!STOCK_CODE.test(symbol)) {
        status.textContent = fill(words.exclusionsNotCode, { code });
        return;
      }
      if (excluded.has(symbol)) {
        status.textContent = fill(words.exclusionsTwice, { symbol });
        return;
      }
      excluded.set(symbol, reason);
    }
    await putSetting(db, SETTINGS.excluded, [...excluded]);
    status.textContent = fill(
      excluded.size === 1 ? words.exclusionsSavedOne : words.exclusionsSavedMany,
      { count: excluded.size.toString() },
    );
    await redraw();
  };

  /** Show every setting as kept, the deposits and withdrawals typed, and the history. */
  const showKept = async (): Promise<void> => {
    try {
      speak(languageOf(await settingOf(db, KEPT.language)));
    } catch {
      speak("en");
      status.textContent = words.languageRefused;
    }
    universe.value = (await keptUniverse(db))?.join(" ") ?? "";
    const keptGoal: unknown = await settingOf(db, SETTINGS.goal);
    goal.value = typeof keptGoal === "string" ? keptGoal : "";
    const keptContribution: unknown = await settingOf(db, SETTINGS.contribution);
    contribution.value = typeof keptContribution === "string" ? keptContribution : "";
    showStrategy(await keptOr(db, KEPT.strategy, strategyOf));
    const limits = await keptOr(db, KEPT.limits, limitsOf);
    limitRows.maxWeight.input.value = limits.maxWeight.mul(100).toString();
    limitRows.minLots.input.value = limits.minLots.toString();
    limitRows.dailyLoss.input.value = limits.dailyLoss.mul(100).toString();
    limitRows.maxDrawdown.input.value = limits.maxDrawdown.mul(100).toString();
    preset.value = await keptOr(db, KEPT.feePreset, feePresetOf);
    showExemption(await keptOr(db, EXEMPTION.claimed, exemptionOf));
    await showTax();
    await showTyped();
    exclusions.value = [...(await keptOr(db, SETTINGS.excluded, excludedOf))]
      .map(([symbol, reason]) => `${symbol} ${reason}`.trim())
      .join("\n");
    await showHistory();
    await showRisk();
  };

  /** The kept dividends and purchases, each listed with its Remove button, and the claims on
   * today in WIB. */
  const showTax = async (): Promise<void> => {
    const dividends = await keptOr(db, EXEMPTION.dividends, dividendsOf);
    const purchases = await keptOr(db, EXEMPTION.purchases, purchasesOf);
    const entryRow = (form: "dividend" | "purchase", text: string, place: number): E => {
      const row = element("div", "");
      const remove = element("button", `remove-${form}-${place.toString()}`, "remove");
      remove.addEventListener("click", () => {
        run(() => removeEntry(form, place));
      });
      row.append(holding("p", text), remove);
      return row;
    };
    dividendForm.list.replaceChildren(
      ...dividends.map((entry, place) =>
        entryRow(
          "dividend",
          fill(words.dividendLine, {
            day: entry.received,
            symbol: entry.symbol,
            amount: entry.gross.toString(),
          }),
          place,
        ),
      ),
    );
    purchaseForm.list.replaceChildren(
      ...purchases.map((entry, place) =>
        entryRow(
          "purchase",
          fill(words.purchaseLine, {
            day: entry.day,
            symbol: entry.symbol,
            amount: entry.amount.toString(),
          }),
          place,
        ),
      ),
    );
    const market = CLAIM_RULES;
    const today = wibDay(inputs.clock());
    taxClaims.replaceChildren(
      ...taxView(claimsReport(market, dividends, purchases, today)).flatMap((section) => [
        holding("h2", section.heading),
        ...section.lines.map((line) => holding("p", line)),
      ]),
    );
  };

  /** Keep the entry typed in `form`, or name the part refused. */
  const keepEntry = async (form: "dividend" | "purchase"): Promise<void> => {
    const [day, stock, amount] = (form === "dividend" ? dividendForm : purchaseForm).parts;
    const typed = { day: day.input.value, symbol: stock.input.value, amount: amount.input.value };
    const today = wibDay(inputs.clock());
    const market = CLAIM_RULES;
    const entry = typedEntry(typed, today, market.verifiedFrom);
    if (typeof entry === "string") {
      const trimmed = typed.day.trim();
      const refused: Readonly<Record<typeof entry, string>> = {
        day: fill(words.dayNotKept, { typed: typed.day }),
        future: fill(words.entryFuture, { day: trimmed, today }),
        early: fill(words.entryEarly, { day: trimmed, first: market.verifiedFrom }),
        stock: fill(words.stockNotKept, { typed: typed.symbol }),
        amount: fill(words.amountNotKept, { typed: typed.amount }),
      };
      status.textContent = refused[entry];
      return;
    }
    const said = { amount: entry.amount.toString(), symbol: entry.symbol, day: entry.day };
    if (form === "dividend") {
      const kept = await keptOr(db, EXEMPTION.dividends, dividendsOf);
      const received = { received: entry.day, symbol: entry.symbol, gross: entry.amount };
      await putSetting(db, EXEMPTION.dividends, storedDividends([...kept, received]));
      status.textContent = fill(words.dividendKept, said);
    } else {
      const kept = await keptOr(db, EXEMPTION.purchases, purchasesOf);
      await putSetting(db, EXEMPTION.purchases, storedPurchases([...kept, entry]));
      status.textContent = fill(words.purchaseKept, said);
    }
    await showTax();
  };

  /** Take the entry at `place` off `form`'s list. */
  const removeEntry = async (form: "dividend" | "purchase", place: number): Promise<void> => {
    if (form === "dividend") {
      const kept = await keptOr(db, EXEMPTION.dividends, dividendsOf);
      await putSetting(
        db,
        EXEMPTION.dividends,
        storedDividends(kept.filter((_, at) => at !== place)),
      );
    } else {
      const kept = await keptOr(db, EXEMPTION.purchases, purchasesOf);
      await putSetting(
        db,
        EXEMPTION.purchases,
        storedPurchases(kept.filter((_, at) => at !== place)),
      );
    }
    status.textContent = words.entryRemoved;
    await showTax();
  };

  const saveExemption = async (): Promise<void> => {
    await putSetting(db, EXEMPTION.claimed, exemption.checked);
    showExemption(exemption.checked);
  };

  const saveChosenLanguage = async (): Promise<void> => {
    const chosen = languageOf(languagePicker.value);
    await putSetting(db, KEPT.language, chosen);
    speak(chosen);
    status.textContent = words.languageSaved;
    await showTyped();
    await showTax();
    await redraw();
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
    status.textContent = words.forgotten;
    await redraw();
  };

  let queue = Promise.resolve();
  /** Run `job` after everything asked before it; a failure is shown, and the queue goes on. */
  const run = (job: () => Promise<void>): void => {
    queue = queue.then(job).catch((failure: unknown) => {
      status.textContent = fill(words.wentWrong, { failure: String(failure) });
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
  answerNone.addEventListener("click", () => {
    run(answerNoneAsked);
  });
  resumeGo.addEventListener("click", () => {
    run(resumeHalt);
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
  saveContribution.addEventListener("click", () => {
    run(saveTypedContribution);
  });
  dividendForm.button.addEventListener("click", () => {
    run(() => keepEntry("dividend"));
  });
  purchaseForm.button.addEventListener("click", () => {
    run(() => keepEntry("purchase"));
  });
  exemption.addEventListener("change", () => {
    run(saveExemption);
  });
  saveLanguage.addEventListener("click", () => {
    run(saveChosenLanguage);
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
