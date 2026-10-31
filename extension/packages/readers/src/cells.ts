/**
 * A table cell's text read as one value of the broker view, or refused naming where it is and why
 * (spec §5.2). Refusals are thrown as `Refusal` inside a reader and returned at its edge.
 */
import Decimal from "decimal.js";
import {
  IDR,
  Money,
  parseIndonesianNumber,
  parseIndonesianWhole,
  UnreadableNumberError,
  type Covered,
  type Day,
} from "@steadyhand/core";
import type { Refused } from "./html-table.ts";

/** A reader's refusal, thrown from deep inside it and turned into `Refused` at its edge. */
export class Refusal extends Error {
  constructor(message: string) {
    super(message);
    this.name = "Refusal";
  }
}

/** `result`'s value, or its refusal thrown. */
export const orRefuse = <T extends object>(result: T | Refused): T => {
  if ("refused" in result) {
    throw new Refusal(result.refused);
  }
  return result;
};

/** What `read` returns, or the refusal it threw. Any other error is not a refusal and goes on up. */
export const refusing = <T>(read: () => T): T | Refused => {
  try {
    return read();
  } catch (error) {
    if (error instanceof Refusal) {
      return { refused: error.message };
    }
    throw error;
  }
};

/** What `parse` returns, or its `UnreadableNumberError` refused at `where`. */
export const numberAt = <T>(where: string, parse: () => T): T => {
  try {
    return parse();
  } catch (error) {
    if (error instanceof UnreadableNumberError) {
      throw new Refusal(`${where}: ${error.message}`);
    }
    throw error;
  }
};

/** A whole number of rupiah, of either sign (an unsettled balance may be negative). */
export const rupiah = (text: string, where: string): Money =>
  new Money(
    numberAt(where, () => parseIndonesianWhole(text)),
    IDR,
  );

const positive = (text: string, where: string, what: string): bigint => {
  const value = numberAt(where, () => parseIndonesianWhole(text));
  if (value <= 0n) {
    throw new Refusal(`${where}: ${JSON.stringify(text)} is not a positive ${what}`);
  }
  return value;
};

/** A price per share in whole rupiah, above zero. */
export const price = (text: string, where: string): Money =>
  new Money(positive(text, where, "price"), IDR);

/** An amount of whole rupiah above zero. */
export const amount = (text: string, where: string): Money =>
  new Money(positive(text, where, "amount"), IDR);

/** A number of lots above zero. */
export const lots = (text: string, where: string): bigint =>
  positive(text, where, "number of lots");

/** An exact amount per share above zero, which may be a fraction of a rupiah. */
export const perShare = (text: string, where: string): Decimal => {
  const value = numberAt(where, () => parseIndonesianNumber(text));
  if (value.lte(0)) {
    throw new Refusal(`${where}: ${JSON.stringify(text)} is not a positive amount`);
  }
  return value;
};

/** An IDX stock code: four capital letters. */
export const symbol = (text: string, where: string): string => {
  if (!/^[A-Z]{4}$/u.test(text)) {
    throw new Refusal(`${where}: ${JSON.stringify(text)} is not a stock code`);
  }
  return text;
};

/** A calendar date written `DD/MM/YYYY`, as `YYYY-MM-DD`. */
export const day = (text: string, where: string): Day => {
  const [, dd = "", mm = "", yyyy = ""] = /^(\d{2})\/(\d{2})\/(\d{4})$/u.exec(text) ?? [];
  const iso = `${yyyy}-${mm}-${dd}`;
  const parsed = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== iso) {
    throw new Refusal(`${where}: ${JSON.stringify(text)} is not a date DD/MM/YYYY`);
  }
  return iso;
};

/** A ratio written `N:M`, both whole and above zero. */
export const ratio = (
  text: string,
  where: string,
): { readonly from: bigint; readonly to: bigint } => {
  const match = /^([1-9]\d*):([1-9]\d*)$/u.exec(text);
  if (match === null) {
    throw new Refusal(`${where}: ${JSON.stringify(text)} is not a ratio N:M`);
  }
  const [, from = "", to = ""] = match;
  return { from: BigInt(from), to: BigInt(to) };
};

/** The period a page covers, from its `from` and `to` texts. */
export const covered = (from: string, to: string, where: string): Covered => {
  const period = { from: day(from, `${where} "Dari"`), to: day(to, `${where} "Sampai"`) };
  if (period.to < period.from) {
    throw new Refusal(`${where}: the period ends before it starts`);
  }
  return period;
};
