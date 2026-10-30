/**
 * IDX trading days, from the holiday calendars in `rules/holidays.json` (spec §4.2), ported from
 * Python's `steadyhand_idx.calendar`. Trading days come from IDX's own calendars, never from
 * which days a page shows prices for. A year with no holiday data is refused, naming the year,
 * rather than assumed to have no holidays. Days are ISO strings (`2026-09-28`).
 */
import shipped from "../../../rules/holidays.json" with { type: "json" };
import {
  asDay,
  asDocument,
  getInt,
  getList,
  getStr,
  onlyKeys,
  requireSchema,
  rows,
  RulesFileError,
  Where,
  type Row,
} from "./rules-file.ts";

export const HOLIDAYS_FILE = "holidays.json";

/** The note code for a day whose year no release carries yet (spec §4.5). */
export const MISSING_RULES_YEAR = "missing.rules_year";

/** A day in a year the calendar has no holiday data for: no advice is given until a release
 * carries it. */
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

/** One year's IDX non-trading weekdays, the document they come from, and IDX's stated total. */
export interface HolidayYear {
  readonly year: string;
  readonly source: string;
  readonly tradingDays: bigint;
  readonly holidays: ReadonlySet<string>;
}

const midnight = (day: string): Date => new Date(`${day}T00:00:00Z`);

const isWeekend = (day: string): boolean => [0, 6].includes(midnight(day).getUTCDay());

const dayAfter = (day: string): string => {
  const moved = midnight(day);
  moved.setUTCDate(moved.getUTCDate() + 1);
  return moved.toISOString().slice(0, 10);
};

const dayBefore = (day: string): string => {
  const moved = midnight(day);
  moved.setUTCDate(moved.getUTCDate() - 1);
  return moved.toISOString().slice(0, 10);
};

const yearOf = (day: string): string => day.slice(0, 4);

/** How many weekdays `year` has. */
const weekdays = (year: string): bigint => {
  let count = 0n;
  for (let day = `${year}-01-01`; yearOf(day) === year; day = dayAfter(day)) {
    if (!isWeekend(day)) {
      count += 1n;
    }
  }
  return count;
};

const YEAR_KEYS = new Set(["year", "source", "trading_days", "holidays"]);

const parseYear = (row: Row, where: Where): HolidayYear => {
  onlyKeys(row, YEAR_KEYS, where);
  const year = String(getInt(row, "year", where, 1n));
  const days: string[] = [];
  let position = 0n;
  for (const value of getList(row, "holidays", where)) {
    position += 1n;
    const day = asDay(value, `${where.toString()}: holiday ${String(position)}`);
    if (yearOf(day) !== year) {
      throw new RulesFileError(`${where.toString()}: ${day} is not in ${year}`);
    }
    if (isWeekend(day)) {
      throw new RulesFileError(
        `${where.toString()}: ${day} is a weekend, which is never a trading day anyway`,
      );
    }
    const last = days.at(-1);
    if (last !== undefined && day <= last) {
      throw new RulesFileError(
        `${where.toString()}: holidays must be listed once each, in order; ${day} is not`,
      );
    }
    days.push(day);
  }
  const stated = getInt(row, "trading_days", where, 0n);
  const counted = weekdays(year) - BigInt(days.length);
  if (counted !== stated) {
    throw new RulesFileError(
      `${where.toString()}: ${year} has ${String(counted)} weekdays that are not holidays, ` +
        `but the calendar states ${String(stated)} trading days`,
    );
  }
  return {
    year,
    source: getStr(row, "source", where),
    tradingDays: stated,
    holidays: new Set(days),
  };
};

const TOP_KEYS = new Set(["schema", "year"]);

/** Validate a holidays document: consecutive years, each one's arithmetic checked. */
export const parseHolidays = (value: unknown, file: string = HOLIDAYS_FILE): HolidayYear[] => {
  const document = asDocument(value, file);
  requireSchema(document, file, 1n);
  onlyKeys(document, TOP_KEYS, new Where(file, "top level"));
  const where = new Where(file, "year");
  const years: HolidayYear[] = [];
  let position = 0n;
  for (const row of rows(document, "year", where)) {
    position += 1n;
    const later = parseYear(row, where.at(position));
    const earlier = years.at(-1);
    if (earlier !== undefined && BigInt(later.year) !== BigInt(earlier.year) + 1n) {
      throw new RulesFileError(
        `${file}: years must be consecutive, got ${later.year} after ${earlier.year}`,
      );
    }
    years.push(later);
  }
  return years;
};

/** Which days the IDX regular market is open, for the years it has holiday data. */
export class IdxCalendar {
  private readonly years: ReadonlyMap<string, HolidayYear>;

  constructor(
    years: readonly HolidayYear[],
    private readonly file: string = HOLIDAYS_FILE,
  ) {
    if (years.length === 0) {
      throw new RulesFileError(`${file}: a calendar needs at least one year`);
    }
    this.years = new Map(years.map((year) => [year.year, year]));
  }

  /** The calendar from the release's own `rules/holidays.json`. */
  static shipped(): IdxCalendar {
    return new IdxCalendar(parseHolidays(shipped));
  }

  private get covered(): string[] {
    return [...this.years.keys()].sort();
  }

  get firstDay(): string {
    return `${String(this.covered[0])}-01-01`;
  }

  get lastDay(): string {
    return `${String(this.covered.at(-1))}-12-31`;
  }

  private year(year: string): HolidayYear {
    const found = this.years.get(year);
    if (found === undefined) {
      throw new UnsupportedDateError(
        `${this.file} has no IDX holidays for ${year}, so its trading days are unknown; ` +
          `it covers ${yearOf(this.firstDay)} to ${yearOf(this.lastDay)}`,
        year,
      );
    }
    return found;
  }

  /** The IDX document a year's holidays come from. */
  source(year: string): string {
    return this.year(year).source;
  }

  /** Refuse, with `UnsupportedDateError`, unless `day`'s year has holiday data. */
  requireCovered(day: string): void {
    this.year(yearOf(day));
  }

  isTradingDay(day: string): boolean {
    const { holidays } = this.year(yearOf(day));
    return !isWeekend(day) && !holidays.has(day);
  }

  /** The first trading day strictly after `day`. */
  nextTradingDay(day: string): string {
    return this.addTradingDays(day, 1n);
  }

  /** The last trading day strictly before `day`. */
  previousTradingDay(day: string): string {
    let found = dayBefore(day);
    while (!this.isTradingDay(found)) {
      found = dayBefore(found);
    }
    return found;
  }

  /** The `count`-th trading day after `day` (`count` of at least 1). `day` itself need not be a
   * trading day: the count starts on the day after it. */
  addTradingDays(day: string, count: bigint): string {
    if (typeof count !== "bigint" || count < 1n) {
      throw new RangeError(`count must be a bigint of at least 1, got ${String(count)}`);
    }
    let found = day;
    for (let left = count; left > 0n;) {
      found = dayAfter(found);
      if (this.isTradingDay(found)) {
        left -= 1n;
      }
    }
    return found;
  }

  /** Every trading day from `start` to `end`, inclusive. */
  tradingDays(start: string, end: string): string[] {
    if (end < start) {
      throw new RangeError(`end ${end} is before start ${start}`);
    }
    const found: string[] = [];
    for (let day = start; day <= end; day = dayAfter(day)) {
      if (this.isTradingDay(day)) {
        found.push(day);
      }
    }
    return found;
  }
}
