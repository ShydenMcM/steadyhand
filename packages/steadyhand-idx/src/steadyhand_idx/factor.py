"""Recovering the price factor Yahoo applies without reporting it, from the IDX tick grid (#160).

Yahoo's "unadjusted" IDX history carries adjustments it does not report: a rights issue scales
every earlier price by a factor nobody publishes, so after the reported splits are reversed those
prices are not whole rupiah. Every real price sat on the tick grid of its day, so the one factor
that puts a whole run of them back on that grid is the factor Yahoo applied (spec §4).

This module is pure: no network, cache or calendar. Its input is the rows of one ticker's history
with a price that is not whole after the reported splits are reversed, in date order, and its
output is the runs those rows form, each proven or not.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal
from functools import cache
from itertools import pairwise

from steadyhand import IDR, Instrument, Money, Note
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.ticks import TICKS_FILE, TickRow, TickTier, parse_ticks

GRID_START = date(2014, 1, 6)
"""The first day with a known tick grid. A price before it is never provable (spec §4.2)."""

FIVE_TIERS_FROM = date(2016, 5, 2)
"""The first day of the five-tier grid in the inference-only history (t-hist.md §3)."""

FIT_TOLERANCE = Decimal("0.01")
"""A price times a factor fits when it is this close to its tier's tick, in rupiah (spec §4.3)."""

MIN_PRICES = 20
"""A run needs at least this many prices (five days) to be proven (spec §4.4, decision 1)."""

FACTOR_DIGITS = 7
"""A proven factor is refined over its run and kept to this many significant figures (§4.5)."""

NOISE_QUANTUM = Decimal("0.000001")
"""A proven factor that rounds to 1 here is a rounding error, not an adjustment (§4.5)."""

DIVIDEND_QUANTUM = Decimal("0.0001")
"""A restored dividend is quantised to this many rupiah per share (spec §4.5)."""

# Inference only (spec decision 2): these grids are never read by order validation, which uses
# tick_sizes.toml alone. docs/research/t-hist.md §3: five tiers from 2 May 2016 to 12 Mar 2020
# ("unverified but supported by data") and three tiers from 6 Jan 2014 to 1 May 2016 (values
# from the news, unverified). A wrong row can only leave a run unproven, never prove a wrong
# factor, because every candidate must fit every price of its run (spec §4.4).
_FIVE_TIERS = (
    TickTier(1, 1),
    TickTier(200, 2),
    TickTier(500, 5),
    TickTier(2000, 10),
    TickTier(5000, 25),
)
_THREE_TIERS = (TickTier(1, 1), TickTier(500, 5), TickTier(5000, 25))

_SIGNIFICANT = Context(prec=FACTOR_DIGITS, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class PriceRow:
    """One day's open, high, low and close after the reported splits are reversed."""

    day: date
    prices: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class Run:
    """Consecutive rows that one or more factors fit, oldest day first.

    ``factor`` is the refined factor when exactly one candidate fits every price and the run has at
    least ``MIN_PRICES`` prices, and ``None`` otherwise.
    """

    days: tuple[date, ...]
    prices: int
    factor: Decimal | None

    @property
    def first(self) -> date:
        return self.days[0]

    @property
    def last(self) -> date:
        return self.days[-1]


def is_noise(factor: Decimal) -> bool:
    """Whether a proven *factor* rounds to 1.000000: a rounding error, not an adjustment."""
    return factor.quantize(NOISE_QUANTUM) == 1


@dataclass(frozen=True, slots=True)
class Restoration:
    """A proven run of one stock's history, as a data source restored it (spec §5)."""

    instrument: Instrument
    first: date
    last: date
    factor: Decimal
    prices: int

    @property
    def noise(self) -> bool:
        """Whether the factor rounds to 1.000000: a split reversal's rounding error (§4.5)."""
        return is_noise(self.factor)

    @property
    def note(self) -> Note:
        """What a backtest's warnings say about this run (spec §7)."""
        span = f"{self.instrument.symbol}: Yahoo's prices from {self.first} to {self.last}"
        if self.noise:
            return Note(
                DATA_PRICES_RESTORED,
                f"{span} miss whole rupiah by a rounding error after its reported splits are "
                "reversed, so steadyhand put each one on the IDX tick grid, proven by "
                f"{self.prices:,} prices that fit it with no other factor.",
            )
        return Note(
            DATA_PRICES_RESTORED,
            f"{span} carry an adjustment Yahoo does not report, so steadyhand restored them: "
            f"every price and dividend in that span is multiplied by {self.factor}, proven by "
            f"{self.prices:,} prices that fit the IDX tick grid at that factor and at no other.",
        )


@dataclass(frozen=True, slots=True)
class DayGrid:
    """One day's tick grid: its tiers, and each tier's lower bound and tick for a lookup."""

    tiers: tuple[TickTier, ...]
    bounds: tuple[int, ...]
    ticks: tuple[int, ...]

    @classmethod
    def of(cls, tiers: tuple[TickTier, ...]) -> DayGrid:
        """*tiers* as a lookup. They must rise, so a bisect finds each value's own tier, and each
        boundary must be a multiple of the ticks on both sides, as ``tick_sizes.toml`` requires,
        so stepping a tick at a time from one multiple lands on every multiple of the next tier
        (``candidates``)."""
        for lower, upper in pairwise(tiers):
            if upper.from_price <= lower.from_price:
                msg = f"a day's tiers must rise, got {upper.from_price} after {lower.from_price}"
                raise ValueError(msg)
            if upper.from_price % lower.tick or upper.from_price % upper.tick:
                msg = (
                    f"a day's tier boundary {upper.from_price} must be a multiple of both ticks "
                    f"around it ({lower.tick} and {upper.tick})"
                )
                raise ValueError(msg)
        return cls(tiers, tuple(tier.from_price for tier in tiers), tuple(t.tick for t in tiers))

    def tick(self, value: Decimal | int) -> int:
        """The tick of the tier with the highest lower bound at or below *value*, or 1 below
        every tier."""
        below = bisect_right(self.bounds, value)
        return self.ticks[below - 1] if below else 1

    def nearest(self, value: Decimal) -> Decimal:
        """The multiple of *value*'s own tier's tick nearest *value*, half to even."""
        tick = self.tick(value)
        return (value / tick).to_integral_value(ROUND_HALF_EVEN) * tick

    def fits(self, prices: Sequence[Decimal], factor: Decimal) -> bool:
        """Whether every one of *prices* times *factor* is within ``FIT_TOLERANCE`` of the
        nearest multiple of its tier's tick."""
        for price in prices:
            value = price * factor
            if abs(value - self.nearest(value)) > FIT_TOLERANCE:
                return False
        return True


_FIVE_TIER_DAYS = DayGrid.of(_FIVE_TIERS)
_THREE_TIER_DAYS = DayGrid.of(_THREE_TIERS)


class Grid:
    """The tick grid of each day: ``tick_sizes.toml`` where it is verified, inference before.

    Each day's grid is looked up once per row of prices, never once per price (#296).
    """

    def __init__(self, verified: Dated[TickRow]) -> None:
        self._verified = Dated(
            verified.where, verified.starts, tuple(DayGrid.of(row.tiers) for row in verified.values)
        )

    @classmethod
    def shipped(cls) -> Grid:
        return _shipped()

    def on(self, day: date) -> DayGrid | None:
        """The day's grid, or ``None`` before ``GRID_START``."""
        if day >= self._verified.first:
            return self._verified.on(day)
        if day >= FIVE_TIERS_FROM:
            return _FIVE_TIER_DAYS
        if day >= GRID_START:
            return _THREE_TIER_DAYS
        return None

    def tiers_on(self, day: date) -> tuple[TickTier, ...] | None:
        """The day's tiers, or ``None`` before ``GRID_START``."""
        grid = self.on(day)
        return None if grid is None else grid.tiers

    def nearest(self, value: Decimal, day: date) -> Decimal | None:
        """The multiple of *value*'s own tier's tick nearest *value*; ``None`` with no grid."""
        grid = self.on(day)
        return None if grid is None else grid.nearest(value)

    def fits(self, price: Decimal, factor: Decimal, day: date) -> bool:
        grid = self.on(day)
        return grid is not None and grid.fits((price,), factor)


@cache
def _shipped() -> Grid:
    return Grid(parse_ticks(load_shipped(TICKS_FILE)))


def candidates(row: PriceRow, grid: Grid) -> list[Decimal]:
    """Every factor from about 1 to about 2 that puts all of *row*'s prices on its grid.

    The factors tried are g / p1 for every whole rupiah g from the one nearest the open p1 up to,
    not including, 2 * (p1 + FIT_TOLERANCE): every factor that puts p1 on a whole rupiah. Only
    the g on their own tier's tick are tried (#296): any other g / p1 puts p1 within 1e-20 of a
    whole rupiah that is at least a rupiah from every multiple of its tick, so it never fits. Both
    edges allow for float noise in p1, so the true factor is always tried. At the lower edge,
    starting at the nearest whole rupiah keeps f = 1 under upward noise (§3.5). At the upper
    edge, a recorded price may sit up to FIT_TOLERANCE off the true one, the slack every fit
    already allows, so a true factor just below 2 is still tried under downward noise. A factor
    tried past either edge can only make a second fit, which refuses the run (§4.4).
    """
    day = grid.on(row.day)
    if day is None:
        return []
    first = row.prices[0]
    start = max(int(first.to_integral_value(ROUND_HALF_UP)), 1)
    found: list[Decimal] = []
    whole = start + -start % day.tick(start)
    while whole < 2 * (first + FIT_TOLERANCE):
        factor = whole / first
        if day.fits(row.prices, factor):
            found.append(factor)
        whole += day.tick(whole)
    return found


def find_runs(rows: Sequence[PriceRow], grid: Grid | None = None) -> tuple[Run, ...]:
    """The runs *rows* form, oldest first (spec §4.1).

    The rows are walked newest first. The newest starts a run with its candidates; each older row
    joins while at least one of the run's candidates still fits all its prices, and the run keeps
    only those. A row that none fits ends the run and starts the next.
    """
    tiles = Grid.shipped() if grid is None else grid
    found: list[Run] = []
    members: list[PriceRow] = []
    passing: list[Decimal] = []
    for row in reversed(rows):
        if members:
            day = tiles.on(row.day)
            still = [] if day is None else [f for f in passing if day.fits(row.prices, f)]
            if still:
                members.append(row)
                passing = still
                continue
            found.append(_close(members, passing, tiles))
        members = [row]
        passing = candidates(row, tiles)
    if members:
        found.append(_close(members, passing, tiles))
    return tuple(reversed(found))


def _close(members: list[PriceRow], passing: list[Decimal], grid: Grid) -> Run:
    oldest_first = members[::-1]
    count = sum(len(row.prices) for row in oldest_first)
    days = tuple(row.day for row in oldest_first)
    if len(passing) != 1 or count < MIN_PRICES:
        return Run(days, count, None)
    return Run(days, count, _refine(oldest_first, passing[0], grid, count))


def _refine(rows: list[PriceRow], factor: Decimal, grid: Grid, count: int) -> Decimal:
    """The mean of (nearest tick / recorded price) over every price, to 7 significant figures."""
    total = Decimal(0)
    for row in rows:
        day = _grid_on(row.day, grid)
        for price in row.prices:
            total += day.nearest(price * factor) / price
    return _SIGNIFICANT.plus(total / count)


def _grid_on(day: date, grid: Grid) -> DayGrid:
    found = grid.on(day)
    if found is None:
        msg = f"there is no tick grid for {day.isoformat()}, before {GRID_START.isoformat()}"
        raise ValueError(msg)
    return found


def restore_price(recorded: Decimal, factor: Decimal, day: date, grid: Grid | None = None) -> Money:
    """The tick multiple nearest *recorded* times *factor*, as the price traded on *day*."""
    (amount,) = restore_prices((recorded,), factor, day, grid)
    return Money(amount, IDR)


def restore_prices(
    recorded: Sequence[Decimal], factor: Decimal, day: date, grid: Grid | None = None
) -> list[int]:
    """``restore_price`` of each of one day's *recorded* prices, in whole rupiah, looking the
    day's grid up once."""
    found = _grid_on(day, Grid.shipped() if grid is None else grid)
    return [int(found.nearest(price * factor)) for price in recorded]


def restore_dividend(recorded: Decimal, factor: Decimal) -> Decimal:
    """*recorded* (its reported splits already reversed) times *factor*, to Rp0.0001."""
    return (recorded * factor).quantize(DIVIDEND_QUANTUM, ROUND_HALF_EVEN)
