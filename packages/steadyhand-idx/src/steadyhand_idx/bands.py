"""IDX auto-rejection bands and the minimum price, from ``data/auto_reject.toml`` (spec §9.1).

The tier is chosen by the reference price, and each tier's ``up_to`` is inclusive: 200 and 5,000
fall in the lower tier, unlike the tick table (docs/research/t-rules.md §3). This module gives
the band's exact limits. Turning them into prices an order can carry, on the tick grid and not
below the minimum price, is ``IdxMarketRules.price_band``'s job, because it needs both tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_decimal,
    get_int,
    get_str,
    get_tables,
    only_keys,
    require_schema,
    rows,
)

BANDS_FILE = "auto_reject.toml"
_HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class BandTier:
    """How far a price may move from a reference in this tier, by percentage or in rupiah.

    ``up_to`` is the highest reference price in the tier (inclusive), or ``None`` for the top tier.
    """

    up_to: int | None
    up: Decimal
    down: Decimal
    in_rupiah: bool

    def limits(self, reference: int) -> tuple[Decimal, Decimal]:
        """The exact (lowest, highest) accepted prices, before tick rounding."""
        if self.in_rupiah:
            return reference - self.down, reference + self.up
        return (
            reference * (_HUNDRED - self.down) / _HUNDRED,
            reference * (_HUNDRED + self.up) / _HUNDRED,
        )


@dataclass(frozen=True, slots=True)
class BandRow:
    """One period's minimum price and band tiers."""

    source: str
    min_price: int
    tiers: tuple[BandTier, ...]

    def tier_for(self, reference: int) -> BandTier:
        if type(reference) is not int or reference < 1:
            msg = f"reference must be a whole number of rupiah of at least 1, got {reference!r}"
            raise ValueError(msg)
        return next(t for t in self.tiers if t.up_to is None or reference <= t.up_to)

    def limits(self, reference: int) -> tuple[Decimal, Decimal]:
        """The exact (lowest, highest) prices the band accepts around *reference*."""
        return self.tier_for(reference).limits(reference)


def _parse_tier(tier: Row, where: Where, *, last: bool) -> BandTier:
    only_keys(tier, {"up_to", "up_percent", "down_percent", "up_rupiah", "down_rupiah"}, where)
    up_to = None if last else get_int(tier, "up_to", where, minimum=1)
    if last and "up_to" in tier:
        msg = f"{where}: the top tier has no up_to"
        raise DataFileError(msg)
    in_rupiah = "up_rupiah" in tier or "down_rupiah" in tier
    if in_rupiah and ("up_percent" in tier or "down_percent" in tier):
        msg = f"{where}: give the band in percent or in rupiah, not both"
        raise DataFileError(msg)
    if in_rupiah:
        up = Decimal(get_int(tier, "up_rupiah", where, minimum=1))
        down = Decimal(get_int(tier, "down_rupiah", where, minimum=1))
    else:
        up = get_decimal(tier, "up_percent", where)
        down = get_decimal(tier, "down_percent", where)
        if not (up > 0 and 0 < down < _HUNDRED):
            msg = f"{where}: percentages must be above 0, and down below 100"
            raise DataFileError(msg)
    return BandTier(up_to, up, down, in_rupiah)


def _parse_row(row: Row, where: Where) -> BandRow:
    only_keys(row, {"from", "source", "min_price", "tiers"}, where)
    listed = get_tables(row, "tiers", where, label="tier")
    tiers = tuple(
        _parse_tier(tier, place, last=index == len(listed))
        for index, (tier, place) in enumerate(listed, start=1)
    )
    min_price = get_int(row, "min_price", where, minimum=1)
    bounds = [tier.up_to for tier in tiers if tier.up_to is not None]
    if bounds and bounds[0] < min_price:
        msg = f"{where}: the first tier ends at {bounds[0]}, below the minimum price {min_price}"
        raise DataFileError(msg)
    for lower, upper in pairwise(bounds):
        if upper <= lower:
            msg = f"{where}: tier bounds must rise, got {upper} after {lower}"
            raise DataFileError(msg)
    return BandRow(get_str(row, "source", where), min_price, tiers)


def parse_bands(document: Row, file: str = BANDS_FILE) -> Dated[BandRow]:
    require_schema(document, file, 1)
    only_keys(document, {"schema", "bands"}, Where(file, "top level"))
    where = Where(file, "bands")
    found = rows(document, "bands", where)
    return Dated(
        where,
        tuple(get_date(row, "from", where.at(i)) for i, row in enumerate(found, start=1)),
        tuple(_parse_row(row, where.at(i)) for i, row in enumerate(found, start=1)),
    )
