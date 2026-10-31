/**
 * Reading the rule files in `extension/packages/core/rules/` (spec §4.2), ported from Python's
 * `steadyhand_idx._datafile`. `scripts/core_fixtures.py` writes them only after Python's readers
 * accept each file, with every whole number and date written as a string; core checks them again,
 * so a file changed by hand is refused here too, naming where.
 */
import type Decimal from "decimal.js";
import { RuleDecimal } from "./ratio.ts";

/** A rule file that does not say what core needs. */
export class RulesFileError extends Error {
  override name = "RulesFileError";
}

/** The note code for a day whose year no release carries yet (spec §4.5). */
export const MISSING_RULES_YEAR = "missing.rules_year";

/** A day no release carries a rule for yet: no advice is given until one does. */
export class UnsupportedDateError extends Error {
  override name = "UnsupportedDateError";
  readonly code = MISSING_RULES_YEAR;

  constructor(
    message: string,
    readonly year: string,
  ) {
    super(message);
  }
}

/** One table of a rule file, its values as the JSON holds them. */
export type Row = Readonly<Record<string, unknown>>;

/** Where in a rule file a value was read, for the messages. */
export class Where {
  constructor(
    readonly file: string,
    readonly table: string,
    readonly row?: bigint,
    readonly part?: string,
  ) {}

  /** The same table, at `row` (counted from 1). */
  at(row: bigint): Where {
    return new Where(this.file, this.table, row);
  }

  /** A named part of this row, such as `tier 2`. */
  within(part: string): Where {
    return new Where(this.file, this.table, this.row, part);
  }

  toString(): string {
    const place =
      this.row === undefined
        ? `${this.file} [${this.table}]`
        : `${this.file} [[${this.table}]] row ${String(this.row)}`;
    return this.part === undefined ? place : `${place}, ${this.part}`;
  }
}

export const isRow = (value: unknown): value is Row =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** The contents itself, refused unless it is a table. */
export const asDocument = (value: unknown, file: string): Row => {
  if (!isRow(value)) {
    throw new RulesFileError(`${file}: the document must be a table`);
  }
  return value;
};

export const requireSchema = (contents: Row, file: string, version: bigint): void => {
  if (contents.schema !== String(version)) {
    throw new RulesFileError(
      `${file}: schema must be ${String(version)}, got ${JSON.stringify(contents.schema)}`,
    );
  }
};

/** The rows of `table`, which must be a non-empty array of tables. */
export const rows = (contents: Row, table: string, where: Where): Row[] => {
  const found = contents[table];
  if (!Array.isArray(found) || found.length === 0 || !found.every(isRow)) {
    throw new RulesFileError(`${where.toString()} must be a non-empty array of tables`);
  }
  return found;
};

export const onlyKeys = (row: Row, allowed: ReadonlySet<string>, where: Where): void => {
  const unknown = Object.keys(row).filter((key) => !allowed.has(key));
  if (unknown.length > 0) {
    throw new RulesFileError(`${where.toString()}: unknown key '${String(unknown[0])}'`);
  }
};

const wrong = (where: Where, key: string, expected: string, value: unknown): RulesFileError =>
  new RulesFileError(
    `${where.toString()}: ${key} must be ${expected}, got ${JSON.stringify(value)}`,
  );

const get = (row: Row, key: string, where: Where): unknown => {
  if (!(key in row)) {
    throw new RulesFileError(`${where.toString()}: missing key '${key}'`);
  }
  return row[key];
};

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/u;

/** `value` as an ISO day (`2021-01-04`), refused unless it is a real calendar day. */
export const asDay = (value: unknown, what: string): string => {
  if (typeof value !== "string" || !ISO_DAY.test(value) || !isRealDay(value)) {
    throw new RulesFileError(
      `${what} must be a date such as 2021-01-04, got ${JSON.stringify(value)}`,
    );
  }
  return value;
};

/** Whether `day` names a day the calendar has: month 13 is no date, and 2021-02-30 reads as
 * 2021-03-02, so neither is. */
const isRealDay = (day: string): boolean => {
  const parsed = new Date(`${day}T00:00:00Z`);
  return parsed.toString() !== "Invalid Date" && parsed.toISOString().startsWith(day);
};

export const getInt = (row: Row, key: string, where: Where, minimum: bigint): bigint => {
  const value = get(row, key, where);
  if (typeof value !== "string" || !/^-?\d+$/u.test(value) || BigInt(value) < minimum) {
    throw wrong(where, key, `an integer of at least ${String(minimum)}`, value);
  }
  return BigInt(value);
};

export const getStr = (row: Row, key: string, where: Where): string => {
  const value = get(row, key, where);
  if (typeof value !== "string" || value === "") {
    throw wrong(where, key, "a non-empty string", value);
  }
  return value;
};

export const getList = (row: Row, key: string, where: Where): readonly unknown[] => {
  const value = get(row, key, where);
  if (!Array.isArray(value)) {
    throw wrong(where, key, "an array", value);
  }
  return value;
};

/** `value` as an ISO day, read from `key`. */
export const getDate = (row: Row, key: string, where: Where): string =>
  asDay(get(row, key, where), `${where.toString()}: ${key}`);

const PLAIN_DECIMAL = /^\d+(?:\.\d+)?$/u;

/** A rate written as a string (`"0.018"`), so no `number` is ever involved (spec §4.1). */
export const getDecimal = (row: Row, key: string, where: Where): Decimal => {
  const value = get(row, key, where);
  if (typeof value !== "string") {
    throw wrong(where, key, 'a decimal written as a string, such as "0.018"', value);
  }
  if (!PLAIN_DECIMAL.test(value)) {
    throw wrong(where, key, "a decimal of at least 0, such as 0.018", value);
  }
  return new RuleDecimal(value);
};

/** An array of inline tables, each paired with its place (`..., tier 2`) for the messages. */
export const getTables = (
  row: Row,
  key: string,
  where: Where,
  label: string,
): (readonly [Row, Where])[] => {
  const found: (readonly [Row, Where])[] = [];
  let position = 0n;
  for (const value of getList(row, key, where)) {
    position += 1n;
    const place = where.within(`${label} ${String(position)}`);
    if (!isRow(value)) {
      throw new RulesFileError(`${place.toString()} must be an inline table`);
    }
    found.push([value, place]);
  }
  return found;
};

/** Each item with the one after it, as Python's `itertools.pairwise`. */
export const pairwise = <T>(items: readonly T[]): (readonly [T, T])[] => {
  const pairs: (readonly [T, T])[] = [];
  let before: readonly [T] | undefined;
  for (const item of items) {
    if (before !== undefined) {
      pairs.push([before[0], item]);
    }
    before = [item];
  }
  return pairs;
};

/** Rows that each apply from their `from` day until the next row's.
 *
 * The first row's day is the first the table can answer for. An earlier day is refused with
 * `UnsupportedDateError` naming the table: a rule is never assumed for a day nobody verified. */
export class Dated<T> {
  readonly entries: readonly (readonly [string, T])[];
  /** The first day the table answers for. */
  readonly first: string;

  constructor(
    readonly where: Where,
    entries: readonly (readonly [string, T])[],
  ) {
    const [first] = entries;
    if (first === undefined) {
      throw new RulesFileError(`${where.toString()}: needs at least one row`);
    }
    for (const [[earlier], [later]] of pairwise(entries)) {
      if (later <= earlier) {
        throw new RulesFileError(
          `${where.toString()}: from dates must increase, got ${later} after ${earlier}`,
        );
      }
    }
    this.entries = entries;
    this.first = first[0];
  }

  on(day: string): T {
    asDay(day, "day");
    const found = this.entries.findLast(([start]) => start <= day);
    if (found === undefined) {
      throw new UnsupportedDateError(
        `${this.where.toString()} has no verified row for ${day}: ` +
          `its first row applies from ${this.first}`,
        day.slice(0, 4),
      );
    }
    return found[1];
  }
}

/** A dated table: an array of rows, each with `from`, `source` and the table's own `keys`. */
export const dated = <T>(
  contents: Row,
  table: string,
  keys: readonly string[],
  parse: (row: Row, where: Where) => T,
  file: string,
): Dated<T> => {
  const where = new Where(file, table);
  const entries: (readonly [string, T])[] = [];
  let position = 0n;
  for (const row of rows(contents, table, where)) {
    position += 1n;
    const place = where.at(position);
    onlyKeys(row, new Set(["from", "source", ...keys]), place);
    getStr(row, "source", place);
    entries.push([getDate(row, "from", place), parse(row, place)]);
  }
  return new Dated(where, entries);
};
