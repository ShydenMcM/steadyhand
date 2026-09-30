"""What a strategy may see on a decision day: prices and dividends up to that day, and nothing
later.

``PriceHistory`` holds every bar a run can use, and ``ActionHistory`` every corporate action,
the look-back's included (M6 spec §4.1). Both are built once. Each day gets a cheap
``MarketView`` over them, which refuses any date after its own day with ``LookAheadError`` (core
spec §4.3). A backtest that peeks at tomorrow's price looks brilliant and means nothing.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from math import prod

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_type
from steadyhand.market import PayDates
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import TRADE_NOT_HELD, TRADE_NOT_IN_UNIVERSE, Note
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Instrument,
    OtherAction,
    Side,
    Split,
)


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
class PastDividend:
    """A cash dividend as a strategy sees it (M6 spec §4.1): its ex-date, and its amount per
    share restated in today's shares, so that one year's dividends compare with another's."""

    ex_date: date
    per_share: Decimal


class ActionHistory:
    """Every corporate action a run loaded, the look-back's included, and the stocks whose history
    is incomplete: the data source refused their look-back, or their actions on days whose prices
    it refused (M6 spec §4.1, §4.3). It answers for any day."""

    def __init__(
        self, actions: Iterable[CorporateAction] = (), incomplete: Iterable[Instrument] = ()
    ) -> None:
        dividends: dict[Instrument, list[CashDividend]] = {}
        splits: dict[Instrument, list[Split]] = {}
        for action in actions:
            if isinstance(action, CashDividend):
                dividends.setdefault(action.instrument, []).append(action)
            elif isinstance(action, Split):
                splits.setdefault(action.instrument, []).append(action)
            elif not isinstance(action, OtherAction):
                msg = f"action must be a CorporateAction, got {type(action).__name__}"
                raise TypeError(msg)
        self._dividends = {
            stock: tuple(sorted(found, key=lambda dividend: dividend.ex_date))
            for stock, found in dividends.items()
        }
        self._days = {
            stock: tuple(dividend.ex_date for dividend in found)
            for stock, found in self._dividends.items()
        }
        self._splits = {
            stock: tuple(sorted(found, key=lambda split: split.ex_date))
            for stock, found in splits.items()
        }
        refused = frozenset(incomplete)
        for stock in refused:
            require_type(stock, Instrument, "incomplete stock")
        self._incomplete = refused

    @property
    def incomplete(self) -> frozenset[Instrument]:
        """The stocks whose history the data source did not give in full."""
        return self._incomplete

    def dividends(self, instrument: Instrument, today: date) -> tuple[PastDividend, ...]:
        """The stock's cash dividends with an ex-date on or before *today*, oldest first.

        Each is restated by every split from its own ex-date to *today*: a dividend is earned on
        the shares held before that day's split (``corporate._Actions``), so a split on the same
        day restates it too. After a 1-for-5 reverse split, a Rp 100 dividend is Rp 500 a share.
        """
        known = self._dividends.get(instrument, ())
        found = known[: bisect_right(self._days.get(instrument, ()), today)]
        splits = [split for split in self._splits.get(instrument, ()) if split.ex_date <= today]
        return tuple(
            PastDividend(
                dividend.ex_date,
                _restated(
                    dividend.per_share,
                    [split for split in splits if split.ex_date >= dividend.ex_date],
                ),
            )
            for dividend in found
        )

    def complete(self, instrument: Instrument) -> bool:
        """Whether the data source gave the stock's whole history."""
        return instrument not in self._incomplete


def _restated(per_share: Decimal, splits: list[Split]) -> Decimal:
    """*per_share* in the shares left after *splits*: one division, so it rounds once."""
    if not splits:
        return per_share
    old = prod(split.old_shares for split in splits)
    new = prod(split.new_shares for split in splits)
    return per_share * old / new


@dataclass(frozen=True, slots=True)
class Tradable:
    """Today's buyable and sellable stocks, and why a stock is neither (M3 spec §6.4).

    ``reasons`` explains stocks kept out for a cause (frozen, excluded, refused data, no bar).
    Any other stock is out because it is not in the universe (for a buy) or not held (a sell).
    ``members`` is the universe on ``day`` (M6 spec §4.2), so a strategy can tell a stock that
    left it from one kept out today; every buyable stock is a member.
    """

    day: date
    buyable: frozenset[Instrument]
    sellable: frozenset[Instrument]
    reasons: Mapping[Instrument, Note]
    members: frozenset[Instrument]

    def __post_init__(self) -> None:
        require_date(self.day, "tradable day")
        for name, group in (
            ("buyable", self.buyable),
            ("sellable", self.sellable),
            ("members", self.members),
        ):
            require_type(group, frozenset, name)
        clash = sorted(i.symbol for i in (self.buyable | self.sellable) if i in self.reasons)
        if clash:
            msg = f"{', '.join(clash)} cannot be both tradable and kept out"
            raise ValueError(msg)
        outside = sorted(i.symbol for i in self.buyable - self.members)
        if outside:
            msg = f"{', '.join(outside)} cannot be buyable outside the universe"
            raise ValueError(msg)

    def why_not(self, instrument: Instrument, side: Side) -> Note | None:
        """Why *instrument* cannot be traded on *side* today, or ``None`` when it can."""
        allowed = self.buyable if side is Side.BUY else self.sellable
        if instrument in allowed:
            return None
        if instrument in self.reasons:
            return self.reasons[instrument]
        if side is Side.BUY:
            return Note(TRADE_NOT_IN_UNIVERSE, f"not in the universe on {self.day.isoformat()}")
        return Note(TRADE_NOT_HELD, "not held")


class MarketView:
    """The market as a strategy sees it on ``today``.

    *actions* hold the dividend history and *pay_dates* model a dividend's pay date as the
    engine pays it (M6 spec §4.1).
    """

    def __init__(
        self,
        history: PriceHistory,
        today: date,
        tradable: Tradable,
        actions: ActionHistory,
        pay_dates: PayDates,
    ) -> None:
        require_type(history, PriceHistory, "history")
        require_date(today, "today")
        require_type(tradable, Tradable, "tradable")
        require_type(actions, ActionHistory, "actions")
        require_type(pay_dates, PayDates, "pay_dates")
        if tradable.day != today:
            msg = f"the tradable set is for {tradable.day.isoformat()}, not {today.isoformat()}"
            raise ValueError(msg)
        self._history = history
        self._today = today
        self._tradable = tradable
        self._actions = actions
        self._pay_dates = pay_dates

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

    def dividends(self, instrument: Instrument) -> tuple[PastDividend, ...]:
        """The stock's cash dividends with an ex-date on or before today, oldest first, each
        restated in today's shares."""
        return self._actions.dividends(instrument, self._today)

    def pay_date(self, ex_date: date) -> date:
        """The modelled pay date of a dividend with *ex_date*, on or before today: the engine's
        and the income calendar's, from ``add_trading_days`` (M4 spec §3.1)."""
        return self._pay_dates.of(self._checked(ex_date))

    def history_complete(self, instrument: Instrument) -> bool:
        """False when the data source refused any part of the stock's corporate actions: its
        look-back, or those of the days whose prices it refused (M6 §4.3)."""
        return self._actions.complete(instrument)

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
