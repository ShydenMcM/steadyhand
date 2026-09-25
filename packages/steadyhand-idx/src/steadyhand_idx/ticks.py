"""The IDX tick table, board lot and settlement cycle, from ``data/tick_sizes.toml`` (spec §9.1).

Prices here are whole rupiah (``int``). A tier's lower bound is inclusive and the tier is chosen
by the price itself (docs/research/t-rules.md §1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_int,
    get_str,
    get_tables,
    only_keys,
    require_schema,
    rows,
)

TICKS_FILE = "tick_sizes.toml"


@dataclass(frozen=True, slots=True)
class TickTier:
    """Prices from ``from_price`` (inclusive) up to the next tier trade on multiples of ``tick``."""

    from_price: int
    tick: int


@dataclass(frozen=True, slots=True)
class TickRow:
    """One period's tick tiers and board lot."""

    source: str
    lot_size: int
    tiers: tuple[TickTier, ...]

    def tick_for(self, price: int) -> int:
        """The tick of the tier *price* falls in."""
        if type(price) is not int or price < 1:
            msg = f"price must be a whole number of rupiah of at least 1, got {price!r}"
            raise ValueError(msg)
        return next(tier.tick for tier in reversed(self.tiers) if tier.from_price <= price)

    def is_valid(self, price: int) -> bool:
        return price % self.tick_for(price) == 0

    def round_down(self, price: int) -> int:
        """The highest valid price at or below *price*."""
        return price - price % self.tick_for(price)

    def round_up(self, price: int) -> int:
        """The lowest valid price at or above *price*.

        Rounding up within a tier never passes the next tier's lower bound, because the loader
        requires every lower bound to be a multiple of the tick below it.
        """
        remainder = price % self.tick_for(price)
        return price if remainder == 0 else price + self.tick_for(price) - remainder


def _parse_tier(tier: Row, where: Where) -> TickTier:
    only_keys(tier, {"from_price", "tick"}, where)
    return TickTier(
        get_int(tier, "from_price", where, minimum=1), get_int(tier, "tick", where, minimum=1)
    )


def _parse_row(row: Row, where: Where) -> TickRow:
    only_keys(row, {"from", "source", "lot_size", "tiers"}, where)
    tiers = tuple(
        _parse_tier(tier, place) for tier, place in get_tables(row, "tiers", where, label="tier")
    )
    if not tiers or tiers[0].from_price != 1:
        msg = f"{where}: the first tier must start at a price of 1"
        raise DataFileError(msg)
    for lower, upper in pairwise(tiers):
        if upper.from_price <= lower.from_price:
            msg = f"{where}: tiers must rise, got {upper.from_price} after {lower.from_price}"
            raise DataFileError(msg)
        if upper.from_price % lower.tick or upper.from_price % upper.tick:
            msg = (
                f"{where}: the tier boundary {upper.from_price} must be a multiple of both "
                f"ticks around it ({lower.tick} and {upper.tick})"
            )
            raise DataFileError(msg)
    return TickRow(get_str(row, "source", where), get_int(row, "lot_size", where, minimum=1), tiers)


def parse_ticks(document: Row, file: str = TICKS_FILE) -> Dated[TickRow]:
    require_schema(document, file, 1)
    only_keys(document, {"schema", "ticks", "settlement"}, Where(file, "top level"))
    where = Where(file, "ticks")
    found = rows(document, "ticks", where)
    return Dated(
        where,
        tuple(get_date(row, "from", where.at(i)) for i, row in enumerate(found, start=1)),
        tuple(_parse_row(row, where.at(i)) for i, row in enumerate(found, start=1)),
    )


def parse_settlement(document: Row, file: str = TICKS_FILE) -> Dated[int]:
    """Settlement, in trading days after the trade day, effective-dated."""
    where = Where(file, "settlement")
    starts: list[date] = []
    days: list[int] = []
    for index, row in enumerate(rows(document, "settlement", where), start=1):
        place = where.at(index)
        only_keys(row, {"from", "source", "trading_days"}, place)
        get_str(row, "source", place)
        starts.append(get_date(row, "from", place))
        days.append(get_int(row, "trading_days", place, minimum=1))
    return Dated(where, tuple(starts), tuple(days))
