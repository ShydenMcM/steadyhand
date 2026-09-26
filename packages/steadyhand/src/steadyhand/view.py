"""What a strategy may see on a decision day: prices up to that day, and nothing later.

``PriceHistory`` holds every bar a run can use and is built once. Each day gets a cheap
``MarketView`` over it, which refuses any date after its own day with ``LookAheadError`` (core
spec §4.3). A backtest that peeks at tomorrow's price looks brilliant and means nothing.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Bar, Instrument, Side


class LookAheadError(LookupError):
    """A strategy asked for data dated after the day it is deciding on."""

    def __init__(self, asked: date, today: date) -> None:
        super().__init__(
            f"asked for {asked.isoformat()} while deciding on {today.isoformat()}: "
            "a decision may use nothing dated after its own day"
        )


class PriceHistory:
    """Every bar a run can use, indexed by instrument and day. It answers for any day."""

    def __init__(self, bars: Iterable[Bar]) -> None:
        grouped: dict[Instrument, list[Bar]] = {}
        for bar in bars:
            require_type(bar, Bar, "bar")
            grouped.setdefault(bar.instrument, []).append(bar)
        self._bars: dict[Instrument, tuple[Bar, ...]] = {}
        self._days: dict[Instrument, tuple[date, ...]] = {}
        for instrument, found in grouped.items():
            found.sort(key=lambda bar: bar.day)
            for earlier, later in pairwise(found):
                if earlier.day == later.day:
                    msg = f"two bars for {instrument.symbol} on {later.day.isoformat()}"
                    raise ValueError(msg)
            self._bars[instrument] = tuple(found)
            self._days[instrument] = tuple(bar.day for bar in found)

    @property
    def instruments(self) -> frozenset[Instrument]:
        return frozenset(self._bars)

    def between(self, instrument: Instrument, start: date | None, end: date) -> tuple[Bar, ...]:
        """The instrument's bars from *start* (or its first) to *end*, both inclusive."""
        days = self._days.get(instrument, ())
        first = 0 if start is None else bisect_left(days, start)
        return self._bars.get(instrument, ())[first : bisect_right(days, end)]

    def on(self, instrument: Instrument, day: date) -> Bar | None:
        found = self.between(instrument, day, day)
        return found[0] if found else None

    def before(self, instrument: Instrument, day: date) -> Bar | None:
        """The instrument's last bar dated strictly before *day*."""
        days = self._days.get(instrument, ())
        index = bisect_left(days, day)
        return self._bars[instrument][index - 1] if index else None


@dataclass(frozen=True, slots=True)
class Tradable:
    """Today's buyable and sellable stocks, and why a stock is neither (M3 spec §6.4).

    ``reasons`` explains stocks kept out for a cause (frozen, excluded, refused data, no bar).
    Any other stock is out because it is not in the universe (for a buy) or not held (a sell).
    """

    day: date
    buyable: frozenset[Instrument]
    sellable: frozenset[Instrument]
    reasons: Mapping[Instrument, str]

    def __post_init__(self) -> None:
        require_date(self.day, "tradable day")
        for name, group in (("buyable", self.buyable), ("sellable", self.sellable)):
            require_type(group, frozenset, name)
        clash = sorted(i.symbol for i in (self.buyable | self.sellable) if i in self.reasons)
        if clash:
            msg = f"{', '.join(clash)} cannot be both tradable and kept out"
            raise ValueError(msg)

    def why_not(self, instrument: Instrument, side: Side) -> str | None:
        """Why *instrument* cannot be traded on *side* today, or ``None`` when it can."""
        allowed = self.buyable if side is Side.BUY else self.sellable
        if instrument in allowed:
            return None
        if instrument in self.reasons:
            return self.reasons[instrument]
        if side is Side.BUY:
            return f"not in the universe on {self.day.isoformat()}"
        return "not held"


class MarketView:
    """The market as a strategy sees it on ``today``."""

    def __init__(self, history: PriceHistory, today: date, tradable: Tradable) -> None:
        require_type(history, PriceHistory, "history")
        require_date(today, "today")
        require_type(tradable, Tradable, "tradable")
        if tradable.day != today:
            msg = f"the tradable set is for {tradable.day.isoformat()}, not {today.isoformat()}"
            raise ValueError(msg)
        self._history = history
        self._today = today
        self._tradable = tradable

    @property
    def today(self) -> date:
        return self._today

    @property
    def tradable(self) -> Tradable:
        return self._tradable

    def bar(self, instrument: Instrument, day: date | None = None) -> Bar | None:
        """The bar for *day* (today by default), or ``None`` if the stock has none that day."""
        when = self._today if day is None else self._checked(day)
        return self._history.on(instrument, when)

    def history(
        self, instrument: Instrument, start: date | None = None, end: date | None = None
    ) -> tuple[Bar, ...]:
        """Bars from *start* (or the first) to *end* (today by default), both inclusive."""
        last = self._today if end is None else self._checked(end)
        return self._history.between(instrument, start, last)

    def last_close(self, instrument: Instrument) -> Money | None:
        """The most recent close on or before today."""
        found = self._history.between(instrument, None, self._today)
        return found[-1].close if found else None

    def _checked(self, day: date) -> date:
        require_date(day, "day")
        if day > self._today:
            raise LookAheadError(day, self._today)
        return day


@dataclass(frozen=True, slots=True)
class PortfolioView:
    """The portfolio as a strategy sees it: values at the last close, and what it may spend.

    ``value`` is all cash, settled and unsettled, plus ``holdings`` (core spec §6.2).
    ``spendable`` is what may be spent today, including every dividend already paid: the
    portfolio's ``spendable_cash``, or zero while a charge waits on unsettled sale proceeds.
    """

    value: Money
    spendable: Money
    holdings: Mapping[Instrument, Money]

    def __post_init__(self) -> None:
        require_type(self.value, Money, "value")
        require_type(self.spendable, Money, "spendable")
        for amount in (self.spendable, *self.holdings.values()):
            if amount.currency != self.value.currency:
                raise CurrencyMismatchError(self.value.currency, amount.currency)
        if self.spendable.amount < 0:
            msg = f"spendable cash cannot be negative, got {self.spendable}"
            raise ValueError(msg)
        held = sum((amount for amount in self.holdings.values()), Money.zero(self.value.currency))
        if held + self.spendable > self.value:
            msg = f"holdings {held} and spendable {self.spendable} exceed the value {self.value}"
            raise ValueError(msg)

    def weight(self, instrument: Instrument) -> Decimal:
        """The instrument's share of the value, rounded down so weights never sum above 1."""
        held = self.holdings.get(instrument)
        if held is None:
            return Decimal(0)
        return ratio_down(held.amount, self.value.amount)
