"""Ratios as ``Decimal``, rounded down, for weights and fund-style unit values."""

from decimal import ROUND_FLOOR, Decimal, localcontext


def ratio_down(part: int | Decimal, whole: int | Decimal) -> Decimal:
    """*part* / *whole*, rounded down at the context's precision. Zero when *whole* is zero.

    Rounding down means weights built from these ratios never sum above 1.
    """
    if whole == 0:
        return Decimal(0)
    with localcontext() as context:
        context.rounding = ROUND_FLOOR
        return Decimal(part) / Decimal(whole)
