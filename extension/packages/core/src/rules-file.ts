/**
 * Reading the rule files in `extension/rules/` (spec §4.2), ported from Python's
 * `steadyhand_idx._datafile`. `scripts/core_fixtures.py` writes them only after Python's readers
 * accept each file, with every whole number and date written as a string; core checks them again,
 * so a file changed by hand is refused here too, naming where.
 */

/** A rule file that does not say what core needs. */
export class RulesFileError extends Error {
  override name = "RulesFileError";
}

/** One table of a rule file, its values as the JSON holds them. */
export type Row = Readonly<Record<string, unknown>>;

/** Where in a rule file a value was read, for the messages. */
export class Where {
  constructor(
    readonly file: string,
    readonly table: string,
    readonly row?: bigint,
  ) {}

  at(row: bigint): Where {
    return new Where(this.file, this.table, row);
  }

  toString(): string {
    if (this.row === undefined) {
      return `${this.file} [${this.table}]`;
    }
    return `${this.file} [[${this.table}]] row ${String(this.row)}`;
  }
}

const isRow = (value: unknown): value is Row =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** The document itself, refused unless it is a table. */
export const asDocument = (value: unknown, file: string): Row => {
  if (!isRow(value)) {
    throw new RulesFileError(`${file}: the document must be a table`);
  }
  return value;
};

export const requireSchema = (document: Row, file: string, version: bigint): void => {
  if (document.schema !== String(version)) {
    throw new RulesFileError(
      `${file}: schema must be ${String(version)}, got ${JSON.stringify(document.schema)}`,
    );
  }
};

/** The rows of `table`, which must be a non-empty array of tables. */
export const rows = (document: Row, table: string, where: Where): Row[] => {
  const found = document[table];
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
