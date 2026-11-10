/** The panel's record (spec §7.1, §10.2, #238): each broker page it is sent is read by the
 * broker's reader of the kind the page names and recorded in history, and the record is read
 * back for advice. The portfolio, watchlist and flags reads stay in the panel's memory: advice
 * needs the latest of each, read together (spec §5.4). */

import { IDR, Money, type PageKind, type Part, type PartValues } from "@steadyhand/core";
import {
  corporateActionRecord,
  dividendRecord,
  recordCashMovements,
  recordCloses,
  recordCorporateActions,
  recordDividends,
  recordedCloses,
  recordSeries,
  recordValuation,
  riskRecord,
  settingOf,
  storedMemory,
  type Adjustment,
  type ValuationRules,
} from "@steadyhand/history";
import { FIXTURE_READERS, pageKindOf, type Refused } from "@steadyhand/readers";
import type { PanelReads, Recorded } from "./advice-model.ts";
import { refusedSetting } from "./settings.ts";

/** The names Settings keeps its values under. */
export const SETTINGS = {
  /** The stocks the user lists as the universe, as symbols. */
  universe: "universe",
  /** Each excluded stock and the user's reason, as [symbol, reason] pairs. */
  excluded: "excluded",
  /** The monthly income goal in whole rupiah, as decimal digits. */
  goal: "income-goal",
  /** The monthly amount the user adds, in whole rupiah, as decimal digits (spec §9.1). */
  contribution: "monthly-contribution",
} as const;

/** The fixture broker's chart is made from its own closes, unadjusted (spec §5.3, §6.5). */
const FIXTURE_CHART: Adjustment = "none";

/** A page read and recorded, with the panel's reads as they now stand, or why it was not. */
export type Recording<K extends PageKind = PageKind> =
  { readonly kind: K; readonly reads: PanelReads } | Refused;

type Recorder<K extends PageKind> = (
  db: IDBDatabase,
  part: Part<PartValues[K]>,
  reads: PanelReads,
  rules: ValuationRules,
) => Promise<PanelReads>;

const RECORDERS: { readonly [K in PageKind]: Recorder<K> } = {
  portfolio: async (db, part, reads, rules) => {
    await recordCloses(db, part, rules);
    await recordValuation(db, part, rules);
    return { ...reads, portfolio: part };
  },
  watchlist: async (db, part, reads, rules) => {
    await recordCloses(db, part, rules);
    return { ...reads, watchlist: part };
  },
  "stock-detail": async (db, part, reads) => {
    await recordSeries(db, part, FIXTURE_CHART);
    return reads;
  },
  dividends: async (db, part, reads) => {
    await recordDividends(db, part);
    return reads;
  },
  "cash-movements": async (db, part, reads) => {
    await recordCashMovements(db, part);
    return reads;
  },
  "corporate-actions": async (db, part, reads) => {
    await recordCorporateActions(db, part);
    return reads;
  },
  flags: (_db, part, reads) => Promise.resolve({ ...reads, flags: part }),
};

const recordAs = async <K extends PageKind>(
  kind: K,
  db: IDBDatabase,
  html: string,
  readAt: Date,
  reads: PanelReads,
  rules: ValuationRules,
): Promise<Recording<K>> => {
  const read = FIXTURE_READERS[kind]({ route: "page", text: html }, readAt);
  if ("refused" in read) {
    return read;
  }
  const record: Recorder<K> = RECORDERS[kind];
  return { kind, reads: await record(db, read.part, reads, rules) };
};

/** Read the broker page `html`, taken at `readAt`, by the reader of the kind it names; record
 * what it shows and return the panel's reads with it. A page with no known kind, or one its
 * reader refuses, records nothing. A cash-movement read history refuses rejects (#477). */
export const recordRead = async (
  db: IDBDatabase,
  html: string,
  readAt: Date,
  reads: PanelReads,
  rules: ValuationRules,
): Promise<Recording> => {
  const named = pageKindOf(html);
  return "refused" in named ? named : recordAs(named.kind, db, html, readAt, reads, rules);
};

const isText = (value: unknown): value is string => typeof value === "string";

const universeOf = (value: unknown): readonly string[] | undefined => {
  if (value === undefined) {
    return undefined;
  }
  if (!Array.isArray(value) || !value.every(isText)) {
    throw refusedSetting(SETTINGS.universe);
  }
  return value;
};

const isExclusion = (value: unknown): value is readonly [string, string] =>
  Array.isArray(value) && value.length === 2 && value.every(isText);

/** The exclusions Settings keeps, each stock with the user's reason; none before any are kept. */
export const excludedOf = (value: unknown): ReadonlyMap<string, string> => {
  if (value === undefined) {
    return new Map();
  }
  if (!Array.isArray(value) || !value.every(isExclusion)) {
    throw refusedSetting(SETTINGS.excluded);
  }
  return new Map(value);
};

/** Whole rupiah kept under `name` as decimal digits, or `undefined` when none is kept. */
const rupiahOf = (name: string, value: unknown): Money | undefined => {
  if (value === undefined) {
    return undefined;
  }
  if (!isText(value) || !/^\d+$/u.test(value)) {
    throw refusedSetting(name);
  }
  return new Money(BigInt(value), IDR);
};

/** The universe Settings keeps, if one is saved. */
export const keptUniverse = async (db: IDBDatabase): Promise<readonly string[] | undefined> =>
  universeOf(await settingOf(db, SETTINGS.universe));

/** Everything history and Settings hold that `strategy` advises with. A setting not in the
 * shape Settings keeps it is refused, naming it. */
export const recordedFrom = async (db: IDBDatabase, strategy: string): Promise<Recorded> => {
  const actions = await corporateActionRecord(db);
  return {
    closes: await recordedCloses(db),
    dividends: await dividendRecord(db),
    splits: actions.splits,
    actionReads: actions.reads,
    risk: await riskRecord(db),
    stored: await storedMemory(db, strategy),
    universe: await keptUniverse(db),
    excluded: excludedOf(await settingOf(db, SETTINGS.excluded)),
    goal: rupiahOf(SETTINGS.goal, await settingOf(db, SETTINGS.goal)),
    contribution:
      rupiahOf(SETTINGS.contribution, await settingOf(db, SETTINGS.contribution)) ??
      new Money(0n, IDR),
  };
};
