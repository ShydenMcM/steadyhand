/**
 * Ratios as `decimal.js`, with Python's digits (spec §4.1), ported from Python's
 * `steadyhand._ratio.ratio_down` and the eight-place rounding in `steadyhand.metrics`.
 */
import Decimal from "decimal.js";

/** Python's default context: 28 significant digits. `ratio_down` divides in it, rounding down. */
const DOWN = Decimal.clone({ precision: 28, rounding: Decimal.ROUND_FLOOR });

/** Rates as the rule files give them, in Python's default context: 28 significant digits,
 * half-even. */
export const RuleDecimal = Decimal.clone({ precision: 28, rounding: Decimal.ROUND_HALF_EVEN });

/** The context the engine's ratios are worked out in: 50 significant digits, half-even. */
export const Ratio = Decimal.clone({ precision: 50, rounding: Decimal.ROUND_HALF_EVEN });

/** `part / whole`, rounded down at 28 significant digits. Zero when `whole` is zero.
 *
 * Rounding down means weights built from these ratios never sum above 1. */
export const ratioDown = (part: bigint | Decimal, whole: bigint | Decimal): Decimal => {
  const divisor = new DOWN(whole.toString());
  if (divisor.isZero()) {
    return new Ratio(0);
  }
  return new Ratio(new DOWN(part.toString()).div(divisor));
};

/** `value` to eight places, half-even, however large its whole part: Python's `RATIO_PLACES`
 * (0.00000001). */
export const roundRatio = (value: Decimal): Decimal =>
  new Ratio(value).toDecimalPlaces(8, Decimal.ROUND_HALF_EVEN);
