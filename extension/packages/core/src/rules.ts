/**
 * `IdxMarketRules`: the Indonesia Stock Exchange's rules, read from `rules/*.json`, ported from
 * Python's `steadyhand_idx.rules`.
 *
 * Every value is looked up for the day it applies to (spec §4.2). The rules refuse any day before
 * `verifiedFrom`, the latest first date of any table in the tick, band, fee and holiday files, and
 * the refusal names the table that sets it. The date is derived from the files and never written
 * into code. `isTradingDay` alone answers for every year the holiday file covers: counting trading
 * days needs only the holidays.
 */
import bandsFile from "../rules/auto_reject.json" with { type: "json" };
import feesFile from "../rules/fees.json" with { type: "json" };
import ticksFile from "../rules/tick_sizes.json" with { type: "json" };
import { bandLimits, parseBands, type BandRow } from "./bands.ts";
import { HOLIDAYS_FILE, IdxCalendar } from "./calendar.ts";
import { Side, type Costs } from "./costs.ts";
import {
  dailyCosts,
  dividendTax,
  feePreset,
  feeTables,
  parseFees,
  protectionEnd,
  reinvestmentDeadline,
  tradeCosts,
  type BrokerPreset,
  type FeeSchedule,
} from "./fees.ts";
import { IDR, Money, type Currency } from "./money.ts";
import { UnsupportedDateError, type Dated } from "./rules-file.ts";
import { parseSettlement, parseTicks, roundDown, roundUp, type TickRow } from "./ticks.ts";

export const MARKET = "IDX";

/** A tradable stock: its exchange symbol (`BBRI`), market (`IDX`) and currency. */
export interface Instrument {
  readonly symbol: string;
  readonly market: string;
  readonly currency: Currency;
}

/** Every dated table the IDX rules read. */
export interface RuleTables {
  readonly calendar: IdxCalendar;
  readonly ticks: Dated<TickRow>;
  readonly settlement: Dated<bigint>;
  readonly bands: Dated<BandRow>;
  readonly fees: FeeSchedule;
}

/** The tables from the release's own rule files. */
export const shippedTables = (): RuleTables => ({
  calendar: IdxCalendar.shipped(),
  ticks: parseTicks(ticksFile),
  settlement: parseSettlement(ticksFile),
  bands: parseBands(bandsFile),
  fees: parseFees(feesFile),
});

/** Each table's first day, with the table's name, calendar first. */
const firstDates = (tables: RuleTables): (readonly [string, string])[] => [
  [tables.calendar.firstDay, `${HOLIDAYS_FILE} [year]`],
  ...[tables.ticks, tables.settlement, tables.bands, ...feeTables(tables.fees)].map(
    (table) => [table.first, table.where.toString()] as const,
  ),
];

const checkMoney = (amount: Money, what: string): void => {
  if (!amount.currency.equals(IDR)) {
    throw new RangeError(`${what} must be in IDR, got ${amount.toString()}`);
  }
};

/** IDX rules for one broker fee preset (`custom` by default). */
export class IdxMarketRules {
  readonly currency: Currency = IDR;
  readonly verifiedFrom: string;
  private readonly setBy: string;
  private readonly preset: BrokerPreset;

  constructor(
    private readonly tables: RuleTables = shippedTables(),
    brokerFees = "custom",
  ) {
    this.preset = feePreset(tables.fees, brokerFees);
    // The latest first date; on a tie, the first table listed names it, as Python's `max` does.
    const [verifiedFrom, setBy] = firstDates(tables).reduce((latest, next) =>
      next[0] > latest[0] ? next : latest,
    );
    this.verifiedFrom = verifiedFrom;
    this.setBy = setBy;
  }

  requireSupported(day: string): void {
    if (day < this.verifiedFrom) {
      throw new UnsupportedDateError(
        `steadyhand's IDX rules are primary-verified from ${this.verifiedFrom}, the first date ` +
          `of ${this.setBy}; ${day} is earlier`,
        day.slice(0, 4),
      );
    }
    this.tables.calendar.requireCovered(day);
  }

  lotSize(instrument: Instrument, on: string): bigint {
    this.check(instrument, on);
    return this.tables.ticks.on(on).lotSize;
  }

  /** A buy's price rounded up onto the tick grid, a sell's rounded down. */
  roundToTick(instrument: Instrument, price: Money, side: Side, on: string): Money {
    this.check(instrument, on);
    checkMoney(price, "price");
    const row = this.tables.ticks.on(on);
    const rounded = side === Side.BUY ? roundUp(row, price.amount) : roundDown(row, price.amount);
    return new Money(rounded, IDR);
  }

  /** The lowest and highest prices the exchange accepts around `reference`.
   *
   * II-A gives the band as a percentage (or, for the lowest prices, rupiah) and states no rounding.
   * A price must also sit on the tick grid, so the highest accepted price is the highest valid
   * price at or below the band's top, and the lowest is the lowest valid price at or above its
   * bottom and the minimum price (docs/research/t-rules.md §3). */
  priceBand(instrument: Instrument, reference: Money, on: string): readonly [Money, Money] {
    this.check(instrument, on);
    checkMoney(reference, "reference");
    const band = this.tables.bands.on(on);
    if (reference.amount < band.minPrice) {
      throw new RangeError(
        `reference ${reference.toString()} is below the minimum price, ` +
          `Rp${String(band.minPrice)}`,
      );
    }
    const ticks = this.tables.ticks.on(on);
    const [bottom, top] = bandLimits(band, reference.amount);
    const ceiling = BigInt(bottom.ceil().toFixed());
    const low = roundUp(ticks, ceiling > band.minPrice ? ceiling : band.minPrice);
    const high = roundDown(ticks, BigInt(top.floor().toFixed()));
    return [new Money(low, IDR), new Money(high, IDR)];
  }

  costs(side: Side, gross: Money, on: string): Costs {
    this.requireSupported(on);
    return tradeCosts(this.tables.fees, this.preset, side, gross, on);
  }

  dailyCosts(traded: Money, on: string): Money {
    this.requireSupported(on);
    return dailyCosts(this.tables.fees, traded, on);
  }

  /** The trading day, `settlement` trading days after `tradeDate`, when a trade settles. */
  settlementDate(tradeDate: string): string {
    this.requireSupported(tradeDate);
    if (!this.tables.calendar.isTradingDay(tradeDate)) {
      throw new RangeError(`${tradeDate} is not an IDX trading day, so nothing trades on it`);
    }
    const lag = this.tables.settlement.on(tradeDate);
    return this.tables.calendar.addTradingDays(tradeDate, lag);
  }

  dividendTax(gross: Money, on: string): Money {
    this.requireSupported(on);
    checkMoney(gross, "gross");
    return dividendTax(this.tables.fees, gross, on);
  }

  reinvestmentDeadline(exDate: string): string | null {
    this.requireSupported(exDate);
    return reinvestmentDeadline(this.tables.fees, exDate);
  }

  protectionEnd(purchaseDay: string): string {
    this.requireSupported(purchaseDay);
    return protectionEnd(this.tables.fees, purchaseDay);
  }

  isTradingDay(day: string): boolean {
    return this.tables.calendar.isTradingDay(day);
  }

  private check(instrument: Instrument, on: string): void {
    this.requireSupported(on);
    if (instrument.market !== MARKET || !instrument.currency.equals(IDR)) {
      throw new RangeError(
        `${instrument.symbol} is a ${instrument.market} ${instrument.currency.code} ` +
          "instrument; these rules are for IDX IDR",
      );
    }
  }
}
