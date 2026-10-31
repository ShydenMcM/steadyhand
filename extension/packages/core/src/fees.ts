/**
 * IDX trading costs and taxes, from `rules/fees.json` (spec §4.2), read as Python's
 * `steadyhand_idx.fees` reads them. Working out a trade's costs, and refusing an all-in quote
 * smaller than the costs it says it includes, are EXT S4b's (#224).
 */
import type Decimal from "decimal.js";
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
  return {
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
};
