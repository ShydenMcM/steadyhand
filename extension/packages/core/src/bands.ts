/**
 * The IDX auto-reject bands and minimum price, from `rules/auto_reject.json` (spec §4.2), read as
 * Python's `steadyhand_idx.bands` reads them. Working out a band's limits is EXT S4b's (#224).
 */
import type Decimal from "decimal.js";
import {
  asDocument,
  dated,
  getDecimal,
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
import { RuleDecimal } from "./ratio.ts";

export const BANDS_FILE = "auto_reject.json";

const HUNDRED = new RuleDecimal("100");

/** How far a price may move from a reference in this tier, by percentage or in rupiah.
 *
 * `upTo` is the highest reference price in the tier (inclusive), or `null` for the top tier. */
export interface BandTier {
  readonly upTo: bigint | null;
  readonly up: Decimal;
  readonly down: Decimal;
  readonly inRupiah: boolean;
}

/** One period's minimum price and band tiers. */
export interface BandRow {
  readonly source: string;
  readonly minPrice: bigint;
  readonly tiers: readonly BandTier[];
}

const TIER_KEYS = new Set(["up_to", "up_percent", "down_percent", "up_rupiah", "down_rupiah"]);

const parseTier = (tier: Row, where: Where, last: boolean): BandTier => {
  onlyKeys(tier, TIER_KEYS, where);
  if (last && "up_to" in tier) {
    throw new RulesFileError(`${where.toString()}: the top tier has no up_to`);
  }
  const upTo = last ? null : getInt(tier, "up_to", where, 1n);
  const inRupiah = "up_rupiah" in tier || "down_rupiah" in tier;
  if (inRupiah && ("up_percent" in tier || "down_percent" in tier)) {
    throw new RulesFileError(
      `${where.toString()}: give the band in percent or in rupiah, not both`,
    );
  }
  if (inRupiah) {
    return {
      upTo,
      up: new RuleDecimal(String(getInt(tier, "up_rupiah", where, 1n))),
      down: new RuleDecimal(String(getInt(tier, "down_rupiah", where, 1n))),
      inRupiah,
    };
  }
  const up = getDecimal(tier, "up_percent", where);
  const down = getDecimal(tier, "down_percent", where);
  if (!(
    up.isPositive() &&
    !up.isZero() &&
    down.isPositive() &&
    !down.isZero() &&
    down.lt(HUNDRED)
  )) {
    throw new RulesFileError(
      `${where.toString()}: percentages must be above 0, and down below 100`,
    );
  }
  return { upTo, up, down, inRupiah };
};

const parseRow = (row: Row, where: Where): BandRow => {
  const listed = getTables(row, "tiers", where, "tier");
  const lastListed = listed.at(-1);
  if (lastListed === undefined) {
    throw new RulesFileError(`${where.toString()}: needs at least one tier`);
  }
  const tiers = listed.map(([tier, place]) => parseTier(tier, place, tier === lastListed[0]));
  const minPrice = getInt(row, "min_price", where, 1n);
  const bounds = tiers.flatMap((tier) => (tier.upTo === null ? [] : [tier.upTo]));
  const [firstBound] = bounds;
  if (firstBound !== undefined && firstBound < minPrice) {
    throw new RulesFileError(
      `${where.toString()}: the first tier ends at ${String(firstBound)}, below the minimum ` +
        `price ${String(minPrice)}`,
    );
  }
  for (const [lower, upper] of pairwise(bounds)) {
    if (upper <= lower) {
      throw new RulesFileError(
        `${where.toString()}: tier bounds must rise, got ${String(upper)} after ${String(lower)}`,
      );
    }
  }
  return { source: getStr(row, "source", where), minPrice, tiers };
};

export const parseBands = (value: unknown, file: string = BANDS_FILE): Dated<BandRow> => {
  const contents = asDocument(value, file);
  requireSchema(contents, file, 1n);
  onlyKeys(contents, new Set(["schema", "bands"]), new Where(file, "top level"));
  return dated(contents, "bands", ["min_price", "tiers"], parseRow, file);
};
