/**
 * Numbers as an Indonesian broker writes them (spec §5.2): a dot groups thousands and a comma
 * starts the fraction, so `1.234.567` is one million and more and `1.234,50` is one thousand and
 * more. Read exactly, as a `Decimal`, never a `number`. A form that is not Indonesian, or that a
 * page written the English way would also produce with another meaning, is refused by name.
 */
import Decimal from "decimal.js";

/** Optional minus; a whole part either grouped in threes by dots or not grouped; an optional fraction. */
const INDONESIAN = /^(-?)(0|[1-9]\d{0,2}(?:\.\d{3})*|[1-9]\d*)(?:,(\d+))?$/u;
const THREE_DIGITS = /^\d{3}$/u;
const THOUSANDS = /\B(?=(?:\d{3})+$)/gu;

const NOT_INDONESIAN = "is not a number in Indonesian format";
const AMBIGUOUS =
  "is ambiguous: a comma before exactly three digits could be a thousands separator";

/** A broker's text that is not exactly one number in Indonesian format. */
export class UnreadableNumberError extends Error {
  readonly text: string;
  readonly reason: string;

  constructor(text: string, reason: string) {
    super(`${JSON.stringify(text)} ${reason}`);
    this.name = "UnreadableNumberError";
    this.text = text;
    this.reason = reason;
  }
}

/** The exact value of `text`, or `UnreadableNumberError` naming why it cannot be read. */
export const parseIndonesianNumber = (text: string): Decimal => {
  if (text === "") {
    throw new UnreadableNumberError(text, "is empty");
  }
  const match = INDONESIAN.exec(text);
  if (match === null) {
    throw new UnreadableNumberError(text, NOT_INDONESIAN);
  }
  const [, sign = "", whole = "", fraction] = match;
  // "1,234" with no dot is one and a fraction here, but one thousand and more written the English way.
  if (fraction !== undefined && !whole.includes(".") && THREE_DIGITS.test(fraction)) {
    throw new UnreadableNumberError(text, AMBIGUOUS);
  }
  const digits = whole.replaceAll(".", "");
  return new Decimal(fraction === undefined ? `${sign}${digits}` : `${sign}${digits}.${fraction}`);
};

/** The exact whole number `text` shows (lots, rupiah): a fraction other than zeros is refused. */
export const parseIndonesianWhole = (text: string): bigint => {
  const value = parseIndonesianNumber(text);
  if (!value.isInteger()) {
    throw new UnreadableNumberError(text, "has a fraction where a whole number is needed");
  }
  return BigInt(value.toFixed());
};

/** `value` written the Indonesian way, in a form `parseIndonesianNumber` reads back exactly. A
 * fraction of exactly three digits with no thousands dot gains a trailing zero (`1,2340`), as
 * `1,234` would be refused as ambiguous. */
export const formatIndonesianNumber = (value: Decimal): string => {
  const sign = value.isNegative() && !value.isZero() ? "-" : "";
  const [whole = "", fraction] = value.abs().toFixed().split(".");
  const grouped = whole.replace(THOUSANDS, ".");
  if (fraction === undefined) {
    return `${sign}${grouped}`;
  }
  const unambiguous =
    !grouped.includes(".") && THREE_DIGITS.test(fraction) ? `${fraction}0` : fraction;
  return `${sign}${grouped},${unambiguous}`;
};
