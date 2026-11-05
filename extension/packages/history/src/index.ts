import { PACKAGE as CORE } from "@steadyhand/core";

/** The package's own name. */
export const PACKAGE = "@steadyhand/history";

/** The workspace packages this one is built on: history sits on core (spec §3). */
export const BUILT_ON: readonly string[] = [CORE];

export { corporateActionRecord, dividendRecord, recordedCloses, settingOf } from "./market.ts";
export {
  putSetting,
  recordCashMovements,
  recordCloses,
  recordCorporateActions,
  recordDividends,
  recordSeries,
  remember,
  rowsOf,
  storedMemory,
  type Adjustment,
  type ReadRules,
} from "./record.ts";
export { amountOf, recordValuation, riskRecord, type ValuationRules } from "./risk.ts";
export { openHistory, STORES } from "./schema.ts";
