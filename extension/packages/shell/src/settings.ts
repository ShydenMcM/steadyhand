/** What Settings keeps for the strategy, the risk limits and the fee preset, and how it reads
 * what the user typed (#239 AC1). A kept value not in the shape Settings writes is refused,
 * naming the setting; a typed value is refused by the name of what is wrong. */

import {
  IdxMarketRules,
  RiskLimits,
  RuleDecimal,
  shippedTables,
  strategyFrom,
  type Strategy,
} from "@steadyhand/core";
import { settingOf } from "@steadyhand/history";
import { LANGUAGES, type Language } from "./words.ts";

/** The strategy chosen in Settings, with the values typed for its settings; a setting with no
 * value takes its default. */
export interface ChosenStrategy {
  readonly name: string;
  readonly values: ReadonlyMap<string, bigint>;
}

/** The risk limits as typed: the rates as percentages, the smallest buy in lots. */
export interface TypedLimits {
  readonly maxWeight: string;
  readonly minLots: string;
  readonly dailyLoss: string;
  readonly maxDrawdown: string;
}

/** The names Settings keeps these under in history's settings store. */
export const KEPT = {
  strategy: "strategy",
  limits: "risk-limits",
  feePreset: "fee-preset",
  language: "language",
} as const;

/** The default strategy (core §8) and fee preset (core spec §4.2's own commission). */
const DEFAULT_STRATEGY = "dividend-growth";
const DEFAULT_PRESET = "custom";

/** The broker fee presets the shipped fees file names, in its order. */
export const FEE_PRESETS: readonly string[] = [...shippedTables().fees.presets.keys()];

export const refusedSetting = (name: string): Error =>
  new Error(`the setting ${name} is not as Settings keeps it`);

const DIGITS = /^\d+$/u;
const PERCENTAGE = /^\d+(?:\.\d+)?$/u;

const isRecord = (value: unknown): value is Readonly<Record<string, unknown>> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isDigits = (value: unknown): value is string =>
  typeof value === "string" && DIGITS.test(value);

const isKeptValue = (value: unknown): value is readonly [string, string] =>
  Array.isArray(value) && value.length === 2 && typeof value[0] === "string" && isDigits(value[1]);

/** The strategy Settings keeps, or dividend-growth with its defaults before one is chosen. */
export const strategyOf = (value: unknown): ChosenStrategy => {
  if (value === undefined) {
    return { name: DEFAULT_STRATEGY, values: new Map() };
  }
  if (!isRecord(value) || typeof value["name"] !== "string") {
    throw refusedSetting(KEPT.strategy);
  }
  const values: unknown = value["values"];
  if (!Array.isArray(values) || !values.every(isKeptValue)) {
    throw refusedSetting(KEPT.strategy);
  }
  return {
    name: value["name"],
    values: new Map(values.map(([name, digits]) => [name, BigInt(digits)])),
  };
};

/** `chosen` as Settings keeps it: its name, and each value as decimal digits. */
export const storedStrategy = (chosen: ChosenStrategy): unknown => ({
  name: chosen.name,
  values: [...chosen.values].map(([name, value]) => [name, value.toString()]),
});

/** The strategy `name` with the values typed for its settings, once the strategy accepts them. */
export const typedStrategy = (name: string, typed: ReadonlyMap<string, string>): ChosenStrategy => {
  const values = new Map<string, bigint>();
  for (const [setting, text] of typed) {
    const trimmed = text.trim();
    if (!DIGITS.test(trimmed)) {
      throw new RangeError(`${setting} must be a whole number, got "${text}"`);
    }
    values.set(setting, BigInt(trimmed));
  }
  strategyFrom(name, values);
  return { name, values };
};

/** The risk limits Settings keeps, or the defaults before any are set. */
export const limitsOf = (value: unknown): RiskLimits => {
  if (value === undefined) {
    return new RiskLimits();
  }
  if (!isRecord(value)) {
    throw refusedSetting(KEPT.limits);
  }
  const { maxWeight, minLots, dailyLoss, maxDrawdown } = value;
  const rates = [maxWeight, dailyLoss, maxDrawdown];
  if (!rates.every((rate) => typeof rate === "string" && PERCENTAGE.test(rate))) {
    throw refusedSetting(KEPT.limits);
  }
  if (!isDigits(minLots)) {
    throw refusedSetting(KEPT.limits);
  }
  return new RiskLimits({
    maxWeight: new RuleDecimal(String(maxWeight)),
    minLots: BigInt(minLots),
    dailyLoss: new RuleDecimal(String(dailyLoss)),
    maxDrawdown: new RuleDecimal(String(maxDrawdown)),
  });
};

/** `limits` as Settings keeps them: each as decimal text. */
export const storedLimits = (limits: RiskLimits): unknown => ({
  maxWeight: limits.maxWeight.toString(),
  minLots: limits.minLots.toString(),
  dailyLoss: limits.dailyLoss.toString(),
  maxDrawdown: limits.maxDrawdown.toString(),
});

/** How Settings names each typed rate. */
const RATE_NAMES = {
  maxWeight: "the largest share of one stock",
  dailyLoss: "the one-day fall that halts ordering",
  maxDrawdown: "the fall from the high that halts ordering",
} as const;

const typedRate = (
  limit: keyof typeof RATE_NAMES,
  text: string,
): InstanceType<typeof RuleDecimal> => {
  const trimmed = text.trim();
  if (!PERCENTAGE.test(trimmed)) {
    throw new RangeError(`${RATE_NAMES[limit]} must be a percentage, got "${text}"`);
  }
  return new RuleDecimal(trimmed).div(100);
};

/** The risk limits typed: each rate a percentage, the smallest buy whole lots, then checked by
 * the limits' own rules. */
export const typedLimits = (typed: TypedLimits): RiskLimits => {
  const maxWeight = typedRate("maxWeight", typed.maxWeight);
  const lots = typed.minLots.trim();
  if (!DIGITS.test(lots)) {
    throw new RangeError(`the smallest buy in lots must be a whole number, got "${typed.minLots}"`);
  }
  return new RiskLimits({
    maxWeight,
    minLots: BigInt(lots),
    dailyLoss: typedRate("dailyLoss", typed.dailyLoss),
    maxDrawdown: typedRate("maxDrawdown", typed.maxDrawdown),
  });
};

/** The fee preset Settings keeps, or `custom` before one is chosen. */
export const feePresetOf = (value: unknown): string => {
  if (value === undefined) {
    return DEFAULT_PRESET;
  }
  if (typeof value !== "string" || !FEE_PRESETS.includes(value)) {
    throw refusedSetting(KEPT.feePreset);
  }
  return value;
};

/** The language Settings keeps (#251 AC1), or English before one is chosen. */
export const languageOf = (value: unknown): Language => {
  if (value === undefined) {
    return "en";
  }
  const found = LANGUAGES.find(([language]) => language === value);
  if (found === undefined) {
    throw refusedSetting(KEPT.language);
  }
  return found[0];
};

/** What the panel advises and records under: the strategy, risk limits and fee preset Settings
 * keeps (#239 AC1). A kept value not as Settings keeps it, or a strategy that refuses its kept
 * values, is refused naming the setting. */
export interface KeptSettings {
  readonly strategy: Strategy;
  readonly limits: RiskLimits;
  readonly market: IdxMarketRules;
}

const keptStrategy = (value: unknown): Strategy => {
  const chosen = strategyOf(value);
  try {
    return strategyFrom(chosen.name, chosen.values);
  } catch {
    throw refusedSetting(KEPT.strategy);
  }
};

/** The strategy, risk limits and market rules under the settings kept in `db`. */
export const keptSettings = async (db: IDBDatabase): Promise<KeptSettings> => ({
  strategy: keptStrategy(await settingOf(db, KEPT.strategy)),
  limits: limitsOf(await settingOf(db, KEPT.limits)),
  market: new IdxMarketRules(shippedTables(), feePresetOf(await settingOf(db, KEPT.feePreset))),
});
