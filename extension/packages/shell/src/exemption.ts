/** What the panel keeps for the dividend reinvestment exemption (spec §9.2): the Settings switch,
 * the dividends the user received and the purchases that reinvest them, each kept in history's
 * settings store, so "forget everything" clears them. A kept value not as kept is refused naming
 * it; a typed entry is refused by the part that is wrong. */

import { asDay, IDR, Money, type DividendReceived, type Reinvestment } from "@steadyhand/core";
import { refusedSetting, STOCK_CODE, WHOLE_RUPIAH } from "./settings.ts";

/** The names the exemption is kept under. */
export const EXEMPTION = {
  /** Whether the user claims the exemption: true, false, or unset (not claimed). */
  claimed: "dividend-exemption",
  /** Each dividend received, as { received, symbol, gross } with gross in rupiah digits. */
  dividends: "dividends-received",
  /** Each reinvesting purchase, as { day, symbol, amount } with amount in rupiah digits. */
  purchases: "reinvesting-purchases",
} as const;

/** Whether the user claims the exemption; off until the switch is turned on. */
export const exemptionOf = (value: unknown): boolean => {
  if (value === undefined) {
    return false;
  }
  if (typeof value !== "boolean") {
    throw refusedSetting(EXEMPTION.claimed);
  }
  return value;
};

const POSITIVE_DIGITS = /^[1-9]\d*$/u;

const isRealDay = (value: unknown): value is string => {
  try {
    asDay(value, "the day");
    return true;
  } catch {
    return false;
  }
};

/** Each kept entry's day, stock and rupiah under `keys`, or `null` when one is not as kept. */
const keptEntries = (
  value: unknown,
  keys: readonly [string, string],
): { day: string; symbol: string; amount: Money }[] | null => {
  if (!Array.isArray(value)) {
    return null;
  }
  const entries: { day: string; symbol: string; amount: Money }[] = [];
  for (const kept of value as readonly unknown[]) {
    if (kept === null || kept === undefined) {
      return null; // any other primitive has no fields, so it is refused below
    }
    const record = kept as Readonly<Record<string, unknown>>;
    const [dayKey, amountKey] = keys;
    const day = record[dayKey];
    const symbol = record["symbol"];
    const amount = record[amountKey];
    if (
      !isRealDay(day) ||
      typeof symbol !== "string" ||
      !STOCK_CODE.test(symbol) ||
      typeof amount !== "string" ||
      !POSITIVE_DIGITS.test(amount)
    ) {
      return null;
    }
    entries.push({ day, symbol, amount: new Money(BigInt(amount), IDR) });
  }
  return entries;
};

/** The dividends kept, in the order kept; none before the first is entered. */
export const dividendsOf = (value: unknown): DividendReceived[] => {
  if (value === undefined) {
    return [];
  }
  const entries = keptEntries(value, ["received", "gross"]);
  if (entries === null) {
    throw refusedSetting(EXEMPTION.dividends);
  }
  return entries.map(({ day, symbol, amount }) => ({ received: day, symbol, gross: amount }));
};

/** The reinvesting purchases kept, in the order kept; none before the first is entered. */
export const purchasesOf = (value: unknown): Reinvestment[] => {
  if (value === undefined) {
    return [];
  }
  const entries = keptEntries(value, ["day", "amount"]);
  if (entries === null) {
    throw refusedSetting(EXEMPTION.purchases);
  }
  return entries;
};

/** `dividends` as kept. */
export const storedDividends = (dividends: readonly DividendReceived[]): unknown =>
  dividends.map(({ received, symbol, gross }) => ({
    received,
    symbol,
    gross: gross.amount.toString(),
  }));

/** `purchases` as kept. */
export const storedPurchases = (purchases: readonly Reinvestment[]): unknown =>
  purchases.map(({ day, symbol, amount }) => ({ day, symbol, amount: amount.amount.toString() }));

/** An entry as the user typed it in either form. */
export interface TypedEntry {
  readonly day: string;
  readonly symbol: string;
  readonly amount: string;
}

/** The part of a typed entry that is wrong: a day that is no day, a day after today, a day
 * before the rules' first, a stock that is no IDX code, or an amount not whole rupiah above 0. */
export type EntryRefusal = "day" | "future" | "early" | "stock" | "amount";

/** `typed` as a day, a stock in capitals and an amount in rupiah, or the part refused. An entry
 * dated after `today` is refused, as the claims are counted up to today, and so is one before
 * `first`, the first day the market rules are verified from. */
export const typedEntry = (
  typed: TypedEntry,
  today: string,
  first: string,
): { day: string; symbol: string; amount: Money } | EntryRefusal => {
  const day = typed.day.trim();
  if (!isRealDay(day)) {
    return "day";
  }
  if (day > today) {
    return "future";
  }
  if (day < first) {
    return "early";
  }
  const symbol = typed.symbol.trim().toUpperCase();
  if (!STOCK_CODE.test(symbol)) {
    return "stock";
  }
  const amount = typed.amount.trim();
  const rupiah = WHOLE_RUPIAH.test(amount) ? BigInt(amount.replaceAll(".", "")) : 0n;
  if (rupiah <= 0n) {
    return "amount";
  }
  return { day, symbol, amount: new Money(rupiah, IDR) };
};

/** WIB is seven hours ahead of UTC all year. */
const WIB_OFFSET_MS = 7 * 60 * 60 * 1000;

/** The day `instant` falls on in WIB, as an ISO day. */
export const wibDay = (instant: Date): string =>
  new Date(instant.getTime() + WIB_OFFSET_MS).toISOString().slice(0, 10);
