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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal
from functools import cache

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


class Grid:
    """The tick grid of each day: ``tick_sizes.toml`` where it is verified, inference before."""

    def __init__(self, verified: Dated[TickRow]) -> None:
        self._verified = verified

    @classmethod
    def shipped(cls) -> Grid:
        return _shipped()

    def tiers_on(self, day: date) -> tuple[TickTier, ...] | None:
        """The day's tiers, or ``None`` before ``GRID_START``."""
        if day >= self._verified.first:
            return self._verified.on(day).tiers
        if day >= FIVE_TIERS_FROM:
            return _FIVE_TIERS
        if day >= GRID_START:
            return _THREE_TIERS
        return None

    def nearest(self, value: Decimal, day: date) -> Decimal | None:
        """The multiple of *value*'s own tier's tick nearest *value*; ``None`` with no grid."""
        tiers = self.tiers_on(day)
        if tiers is None:
            return None
        tick = next((tier.tick for tier in reversed(tiers) if tier.from_price <= value), 1)
        return (value / tick).to_integral_value(ROUND_HALF_EVEN) * tick

    def fits(self, price: Decimal, factor: Decimal, day: date) -> bool:
        value = price * factor
        nearest = self.nearest(value, day)
        return nearest is not None and abs(value - nearest) <= FIT_TOLERANCE


@cache
def _shipped() -> Grid:
    return Grid(parse_ticks(load_shipped(TICKS_FILE)))


def candidates(row: PriceRow, grid: Grid) -> list[Decimal]:
    """Every factor from about 1 to about 2 that puts all of *row*'s prices on its grid.

    The factors tried are g / p1 for every whole rupiah g from the one nearest the open p1 up to,
    not including, 2 * (p1 + FIT_TOLERANCE): every factor that puts p1 on a whole rupiah. Both
    edges allow for float noise in p1, so the true factor is always tried. At the lower edge,
    starting at the nearest whole rupiah keeps f = 1 under upward noise (§3.5). At the upper
    edge, a recorded price may sit up to FIT_TOLERANCE off the true one, the slack every fit
    already allows, so a true factor just below 2 is still tried under downward noise. A factor
    tried past either edge can only make a second fit, which refuses the run (§4.4).
    """
    first = row.prices[0]
    start = max(int(first.to_integral_value(ROUND_HALF_UP)), 1)
    found: list[Decimal] = []
    whole = start
    while whole < 2 * (first + FIT_TOLERANCE):
        factor = whole / first
        if all(grid.fits(price, factor, row.day) for price in row.prices):
            found.append(factor)
        whole += 1
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
            still = [f for f in passing if all(tiles.fits(p, f, row.day) for p in row.prices)]
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
        for price in row.prices:
            total += _on_grid(price * factor, row.day, grid) / price
    return _SIGNIFICANT.plus(total / count)


def _on_grid(value: Decimal, day: date, grid: Grid) -> Decimal:
    nearest = grid.nearest(value, day)
    if nearest is None:
        msg = f"there is no tick grid for {day.isoformat()}, before {GRID_START.isoformat()}"
        raise ValueError(msg)
    return nearest


def restore_price(recorded: Decimal, factor: Decimal, day: date, grid: Grid | None = None) -> Money:
    """The tick multiple nearest *recorded* times *factor*, as the price traded on *day*."""
    tiles = Grid.shipped() if grid is None else grid
    return Money(int(_on_grid(recorded * factor, day, tiles)), IDR)


def restore_dividend(recorded: Decimal, factor: Decimal) -> Decimal:
    """*recorded* (its reported splits already reversed) times *factor*, to Rp0.0001."""
    return (recorded * factor).quantize(DIVIDEND_QUANTUM, ROUND_HALF_EVEN)
