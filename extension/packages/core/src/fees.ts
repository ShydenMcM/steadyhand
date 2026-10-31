/**
 * IDX trading costs and taxes, from `rules/fees.json` (spec §4.2), read and worked as Python's
 * `steadyhand_idx.fees` does. Every component is worked out exactly as a percentage of the gross
 * value, the components are summed, and the total is rounded once to the rupiah, against the
 * trader (spec §4.1). The levy and tax lines of `Costs` are rounded down and the broker line takes
 * the rest, so the three lines always add up to the rounded total and none of them is negative.
 * Each sum is worked in Python's default context (`RuleDecimal`), in Python's order, so the digits
 * match.
 */
import type Decimal from "decimal.js";
import { Costs, Side } from "./costs.ts";
import { IDR, Money, Rounding } from "./money.ts";
import { RuleDecimal } from "./ratio.ts";
import {
  asDay,
  asDocument,
  dated,
  getDecimal,
  getInt,
  getList,
  getStr,
  isRow,
  onlyKeys,
  requireSchema,
  RulesFileError,
  Where,
  type Dated,
  type Row,
} from "./rules-file.ts";

export const FEES_FILE = "fees.json";

/** What a broker's quote may already contain. */
export const INCLUDABLE: ReadonlySet<string> = new Set(["levy", "commission_vat", "sale_tax"]);

const MONTHS = 12n;

const HUNDRED = new RuleDecimal("100");

/** The exchange-side charges per side, in percent of the gross value. */
export interface Levy {
  readonly exchange: Decimal;
  readonly clearing: Decimal;
  readonly settlement: Decimal;
  readonly guaranteeFund: Decimal;
}

/** `amount` rupiah on a day's trade confirmation worth more than `exemptUpTo`. */
export interface StampDuty {
  readonly amount: bigint;
  readonly exemptUpTo: bigint;
}

/** A broker's quoted rate per side, in percent, and what that quote already contains. */
export interface BrokerPreset {
  readonly name: string;
  readonly source: string;
  /** The day the quote was last read from the broker's page, if the file says. */
  readonly checked: string | null;
  readonly buy: Decimal;
  readonly sell: Decimal;
  readonly includes: ReadonlySet<string>;
}

/** The reinvestment exemption's two counts (docs/research/t-tax.md §3). */
export interface Exemption {
  readonly reinvestByMonth: bigint;
  readonly holdTaxYears: bigint;
}

/** The dated cost tables and the broker presets from one fees file. */
export interface FeeSchedule {
  readonly levy: Dated<Levy>;
  readonly vat: Dated<Decimal>;
  readonly saleTax: Dated<Decimal>;
  readonly stampDuty: Dated<StampDuty>;
  readonly dividendTaxRate: Dated<Decimal>;
  readonly dividendExemption: Dated<Exemption | null>;
  readonly presets: ReadonlyMap<string, BrokerPreset>;
}

const levy = (row: Row, where: Where): Levy => ({
  exchange: getDecimal(row, "exchange_percent", where),
  clearing: getDecimal(row, "clearing_percent", where),
  settlement: getDecimal(row, "settlement_percent", where),
  guaranteeFund: getDecimal(row, "guarantee_fund_percent", where),
});

const rate = (row: Row, where: Where): Decimal => getDecimal(row, "rate_percent", where);

const stampDuty = (row: Row, where: Where): StampDuty => ({
  amount: getInt(row, "amount_rupiah", where, 1n),
  exemptUpTo: getInt(row, "exempt_up_to_rupiah", where, 0n),
});

const COUNTS = ["reinvest_by_month", "hold_tax_years"];

const exemption = (row: Row, where: Where): Exemption | null => {
  const missing = COUNTS.filter((key) => !(key in row));
  if (missing.length === COUNTS.length) {
    return null;
  }
  const [lacks] = missing;
  if (lacks !== undefined) {
    throw new RulesFileError(
      `${where.toString()}: an exemption row gives both counts or neither, and lacks '${lacks}'`,
    );
  }
  const month = getInt(row, "reinvest_by_month", where, 1n);
  if (month > MONTHS) {
    throw new RulesFileError(
      `${where.toString()}: reinvest_by_month must be a month from 1 to 12, got ${String(month)}`,
    );
  }
  return { reinvestByMonth: month, holdTaxYears: getInt(row, "hold_tax_years", where, 1n) };
};

const PRESET_KEYS = new Set(["source", "checked", "buy_percent", "sell_percent", "includes"]);

const preset = (name: string, row: unknown, file: string): BrokerPreset => {
  const where = new Where(file, `presets.${name}`);
  if (!isRow(row)) {
    throw new RulesFileError(`${where.toString()} must be a table`);
  }
  onlyKeys(row, PRESET_KEYS, where);
  const checked = "checked" in row ? asDay(row.checked, `${where.toString()}: checked`) : null;
  const includes = new Set<string>();
  for (const item of getList(row, "includes", where)) {
    if (typeof item !== "string" || !INCLUDABLE.has(item) || includes.has(item)) {
      throw new RulesFileError(
        `${where.toString()}: includes may list each of ${[...INCLUDABLE].sort().join(", ")} ` +
          `once, got ${JSON.stringify(item)}`,
      );
    }
    includes.add(item);
  }
  return {
    name,
    source: getStr(row, "source", where),
    checked,
    buy: getDecimal(row, "buy_percent", where),
    sell: getDecimal(row, "sell_percent", where),
    includes,
  };
};

const TABLES = [
  "levy",
  "vat",
  "sale_tax",
  "stamp_duty",
  "dividend_tax",
  "dividend_exemption",
  "presets",
];

export const parseFees = (value: unknown, file: string = FEES_FILE): FeeSchedule => {
  const contents = asDocument(value, file);
  requireSchema(contents, file, 1n);
  onlyKeys(contents, new Set(["schema", ...TABLES]), new Where(file, "top level"));
  const { presets } = contents;
  if (!isRow(presets) || Object.keys(presets).length === 0) {
    throw new RulesFileError(`${file} [presets] must be a table with at least one preset`);
  }
  const levyKeys = ["exchange_percent", "clearing_percent", "settlement_percent"];
  const schedule: FeeSchedule = {
    levy: dated(contents, "levy", [...levyKeys, "guarantee_fund_percent"], levy, file),
    vat: dated(contents, "vat", ["rate_percent"], rate, file),
    saleTax: dated(contents, "sale_tax", ["rate_percent"], rate, file),
    stampDuty: dated(
      contents,
      "stamp_duty",
      ["amount_rupiah", "exempt_up_to_rupiah"],
      stampDuty,
      file,
    ),
    dividendTaxRate: dated(contents, "dividend_tax", ["rate_percent"], rate, file),
    dividendExemption: dated(contents, "dividend_exemption", COUNTS, exemption, file),
    presets: new Map(Object.entries(presets).map(([name, row]) => [name, preset(name, row, file)])),
  };
  for (const found of schedule.presets.values()) {
    checkQuoteCoversWhatItIncludes(schedule, found, file);
  }
  return schedule;
};

/** Every dated table, for working out the first day all of them are verified. */
export const feeTables = (schedule: FeeSchedule): readonly Dated<unknown>[] => [
  schedule.levy,
  schedule.vat,
  schedule.saleTax,
  schedule.stampDuty,
  schedule.dividendTaxRate,
  schedule.dividendExemption,
];

/** The levy in percent, VAT included on every part except the guarantee fund. */
export const levyWithVat = (levy: Levy, vat: Decimal): Decimal => {
  const taxed = levy.exchange.plus(levy.clearing).plus(levy.settlement);
  return taxed.plus(taxed.times(vat).div(HUNDRED)).plus(levy.guaranteeFund);
};

export const feePreset = (schedule: FeeSchedule, name: string): BrokerPreset => {
  const found = schedule.presets.get(name);
  if (found === undefined) {
    const known = [...schedule.presets.keys()].toSorted().join(", ");
    throw new RangeError(`no broker fee preset named '${name}'; ${FEES_FILE} has ${known}`);
  }
  return found;
};

/** One trade's costs in percent of its gross value, before any rounding. */
export interface Percentages {
  readonly fee: Decimal;
  readonly levy: Decimal;
  readonly tax: Decimal;
}

/** The fee, levy and tax on one trade, in percent of its gross value. */
export const feePercentages = (
  schedule: FeeSchedule,
  quote: BrokerPreset,
  side: Side,
  on: string,
): Percentages => {
  const vat = schedule.vat.on(on);
  const levy = levyWithVat(schedule.levy.on(on), vat);
  const tax = side === Side.SELL ? schedule.saleTax.on(on) : new RuleDecimal("0");
  let commission = side === Side.BUY ? quote.buy : quote.sell;
  if (quote.includes.has("levy")) {
    commission = commission.minus(levy);
  }
  if (quote.includes.has("sale_tax")) {
    commission = commission.minus(tax);
  }
  if (!quote.includes.has("commission_vat")) {
    commission = commission.plus(commission.times(vat).div(HUNDRED));
  }
  return { fee: commission, levy, tax };
};

const requireRupiah = (money: Money, name: string): void => {
  if (!money.currency.equals(IDR) || money.amount < 0n) {
    throw new RangeError(`${name} must be a non-negative IDR amount, got ${money.toString()}`);
  }
};

/** The costs of one trade worth `gross`, rounded once, against the trader. The fee comes from a
 * broker preset, so it is marked an estimate. */
export const tradeCosts = (
  schedule: FeeSchedule,
  quote: BrokerPreset,
  side: Side,
  gross: Money,
  on: string,
): Costs => {
  requireRupiah(gross, "gross");
  const rates = feePercentages(schedule, quote, side, on);
  const total = gross.timesRate(
    rates.fee.plus(rates.levy).plus(rates.tax).div(HUNDRED),
    Rounding.UP,
  );
  const levy = gross.timesRate(rates.levy.div(HUNDRED), Rounding.DOWN);
  const tax = gross.timesRate(rates.tax.div(HUNDRED), Rounding.DOWN);
  return new Costs(total.minus(levy).minus(tax), levy, tax, true);
};

/** Stamp duty on the day's trade confirmation, given the day's buys plus sells. */
export const dailyCosts = (schedule: FeeSchedule, traded: Money, on: string): Money => {
  requireRupiah(traded, "traded");
  const duty = schedule.stampDuty.on(on);
  return traded.amount <= duty.exemptUpTo ? Money.zero(IDR) : new Money(duty.amount, IDR);
};

/** The full tax on a gross dividend paid on `on`, rounded up to the rupiah.
 *
 * The reinvestment exemption is the engine's claim bookkeeping, not a discount here. */
export const dividendTax = (schedule: FeeSchedule, gross: Money, on: string): Money => {
  requireRupiah(gross, "gross");
  return gross.timesRate(schedule.dividendTaxRate.on(on).div(HUNDRED), Rounding.UP);
};

const isLeap = (year: bigint): boolean =>
  year % 4n === 0n && (year % 100n !== 0n || year % 400n === 0n);

/** `year-month-last day`, as an ISO day. */
const endOfMonth = (year: bigint, month: bigint): string => {
  const thirty = month === 4n || month === 6n || month === 9n || month === 11n;
  const february = isLeap(year) ? 29n : 28n;
  const last = month === 2n ? february : thirty ? 30n : 31n;
  const two = (value: bigint): string => String(value).padStart(2, "0");
  return `${String(year).padStart(4, "0")}-${two(month)}-${two(last)}`;
};

const yearOf = (day: string): bigint => BigInt(day.slice(0, 4));

/** The last day to reinvest a dividend with `exDate`, or `null` if it cannot be exempt.
 *
 * The deadline counts from the ex-date's year, which is never later than the year the dividend is
 * really paid (docs/research/t-pay.md §4), so it errs early. */
export const reinvestmentDeadline = (schedule: FeeSchedule, exDate: string): string | null => {
  const exemption = schedule.dividendExemption.on(exDate);
  return exemption === null ? null : endOfMonth(yearOf(exDate) + 1n, exemption.reinvestByMonth);
};

/** The last day an investment made on `purchaseDay` must stay held to keep its claim. */
export const protectionEnd = (schedule: FeeSchedule, purchaseDay: string): string => {
  const exemption = schedule.dividendExemption.on(purchaseDay);
  if (exemption === null) {
    throw new RangeError(`no reinvestment exemption applies to a purchase on ${purchaseDay}`);
  }
  return endOfMonth(yearOf(purchaseDay) + exemption.holdTaxYears - 1n, MONTHS);
};

/** An all-in quote smaller than the levy and tax it claims to contain is a data error, checked on
 * the first day all three tables answer and on every day one of them changes after it. */
const checkQuoteCoversWhatItIncludes = (
  schedule: FeeSchedule,
  quote: BrokerPreset,
  file: string,
): void => {
  const tables: readonly Dated<unknown>[] = [schedule.levy, schedule.vat, schedule.saleTax];
  const first = tables.map((table) => table.first).reduce((a, b) => (b > a ? b : a));
  const days = new Set([first]);
  for (const table of tables) {
    for (const [start] of table.entries) {
      if (start >= first) {
        days.add(start);
      }
    }
  }
  for (const day of [...days].toSorted()) {
    for (const side of [Side.BUY, Side.SELL]) {
      if (feePercentages(schedule, quote, side, day).fee.isNegative()) {
        throw new RulesFileError(
          `${file} preset '${quote.name}': its ${side} quote is smaller than the costs it says ` +
            `it includes on ${day}`,
        );
      }
    }
  }
};
