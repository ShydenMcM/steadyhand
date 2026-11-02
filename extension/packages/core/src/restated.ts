/** Dividends restated in today's shares (spec §6.6), ported from Python's `income._split_ratio`
 * and `_restated_gross`: a dividend per share is restated by every split from its ex-date to the
 * day it is read for, and an amount is worked in whole numbers and rounded down once. */

import type Decimal from "decimal.js";
import type { Day, Dividend, Split } from "./broker-view.ts";
import { IDR, Money } from "./money.ts";
import { RuleDecimal } from "./ratio.ts";

/** The (old, new) share counts of every split of `symbol` from `exDate` to `asOf`, multiplied
 * together. A split on the dividend's own ex-date counts: that dividend is paid on the shares
 * held before the split, so it is on the old basis. */
export const splitRatio = (
  symbol: string,
  exDate: Day,
  splits: readonly Split[],
  asOf: Day,
): readonly [bigint, bigint] => {
  let old = 1n;
  let now = 1n;
  for (const split of splits) {
    if (split.symbol === symbol && exDate <= split.exDate && split.exDate <= asOf) {
      old *= split.from;
      now *= split.to;
    }
  }
  return [old, now];
};

/** `rate` as an exact fraction of whole numbers. */
const fraction = (rate: Decimal): readonly [bigint, bigint] => {
  const [whole = "", part = ""] = rate.toFixed().split(".");
  return [BigInt(`${whole}${part}`), 10n ** BigInt(part.length)];
};

/** `dividend` on `shares` of the basis on `asOf`, in rupiah, rounded down once. */
export const restatedGross = (
  dividend: Dividend,
  shares: bigint,
  splits: readonly Split[],
  asOf: Day,
): Money => {
  const [old, now] = splitRatio(dividend.symbol, dividend.exDate, splits, asOf);
  const [numerator, denominator] = fraction(dividend.grossPerShare);
  return new Money((numerator * shares * old) / (denominator * now), IDR);
};

/** `dividend` per share in the basis on `asOf`, at 28 digits: for a ratio, not an amount. */
export const restatedPerShare = (
  dividend: Dividend,
  splits: readonly Split[],
  asOf: Day,
): Decimal => {
  const [old, now] = splitRatio(dividend.symbol, dividend.exDate, splits, asOf);
  return new RuleDecimal(dividend.grossPerShare).times(old.toString()).div(now.toString());
};
