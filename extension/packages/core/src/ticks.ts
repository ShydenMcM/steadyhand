/**
 * The IDX tick table, board lot and settlement cycle, from `rules/tick_sizes.json` (spec §4.2),
 * read and worked as Python's `steadyhand_idx.ticks` does. Prices are whole rupiah (`bigint`). A
 * tier's lower bound is inclusive and the tier is chosen by the price itself
 * (docs/research/t-rules.md §1).
 */
import {
  asDocument,
  dated,
  getInt,
  getStr,
  getTables,
  onlyKeys,
  pairwise,
  requireSchema,
  RulesFileError,
  Where,
  type Dated,
  type Row,
} from "./rules-file.ts";

export const TICKS_FILE = "tick_sizes.json";

/** Prices from `fromPrice` (inclusive) up to the next tier trade on multiples of `tick`. */
export interface TickTier {
  readonly fromPrice: bigint;
  readonly tick: bigint;
}

/** One period's tick tiers and board lot. */
export interface TickRow {
  readonly source: string;
  readonly lotSize: bigint;
  readonly tiers: readonly TickTier[];
}

const parseTier = (tier: Row, where: Where): TickTier => {
  onlyKeys(tier, new Set(["from_price", "tick"]), where);
  return {
    fromPrice: getInt(tier, "from_price", where, 1n),
    tick: getInt(tier, "tick", where, 1n),
  };
};

const parseRow = (row: Row, where: Where): TickRow => {
  const tiers = getTables(row, "tiers", where, "tier").map(([tier, place]) =>
    parseTier(tier, place),
  );
  if (tiers[0]?.fromPrice !== 1n) {
    throw new RulesFileError(`${where.toString()}: the first tier must start at a price of 1`);
  }
  for (const [lower, upper] of pairwise(tiers)) {
    if (upper.fromPrice <= lower.fromPrice) {
      throw new RulesFileError(
        `${where.toString()}: tiers must rise, got ${String(upper.fromPrice)} after ` +
          String(lower.fromPrice),
      );
    }
    if (upper.fromPrice % lower.tick !== 0n || upper.fromPrice % upper.tick !== 0n) {
      throw new RulesFileError(
        `${where.toString()}: the tier boundary ${String(upper.fromPrice)} must be a multiple ` +
          `of both ticks around it (${String(lower.tick)} and ${String(upper.tick)})`,
      );
    }
  }
  return {
    source: getStr(row, "source", where),
    lotSize: getInt(row, "lot_size", where, 1n),
    tiers,
  };
};

export const parseTicks = (value: unknown, file: string = TICKS_FILE): Dated<TickRow> => {
  const contents = asDocument(value, file);
  requireSchema(contents, file, 1n);
  onlyKeys(contents, new Set(["schema", "ticks", "settlement"]), new Where(file, "top level"));
  return dated(contents, "ticks", ["lot_size", "tiers"], parseRow, file);
};

/** Settlement, in trading days after the trade day, effective-dated. */
export const parseSettlement = (value: unknown, file: string = TICKS_FILE): Dated<bigint> =>
  dated(
    asDocument(value, file),
    "settlement",
    ["trading_days"],
    (row, where) => getInt(row, "trading_days", where, 1n),
    file,
  );

/** The tick of the tier `price` falls in. */
export const tickFor = (row: TickRow, price: bigint): bigint => {
  if (typeof price !== "bigint" || price < 1n) {
    throw new RangeError(
      `price must be a whole number of rupiah of at least 1, got ${String(price)}`,
    );
  }
  // The loader requires a first tier from 1, so a price of at least 1 always finds one.
  const tier = row.tiers.findLast((candidate) => candidate.fromPrice <= price) as TickTier;
  return tier.tick;
};

export const isValidPrice = (row: TickRow, price: bigint): boolean =>
  price % tickFor(row, price) === 0n;

/** The highest valid price at or below `price`. */
export const roundDown = (row: TickRow, price: bigint): bigint =>
  price - (price % tickFor(row, price));

/** The lowest valid price at or above `price`.
 *
 * Rounding up within a tier never passes the next tier's lower bound, because the loader requires
 * every lower bound to be a multiple of the tick below it. */
export const roundUp = (row: TickRow, price: bigint): bigint => {
  const tick = tickFor(row, price);
  const remainder = price % tick;
  return remainder === 0n ? price : price + tick - remainder;
};
