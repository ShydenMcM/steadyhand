"""Dividend income: what a run received, what its holdings pay now, and where that leads (M4 spec).

Every function here is pure. The caller passes the run's day reports, its last state and, where a
figure needs it, each holding's dividend history; nothing here reads a file or the network.
Money stays integer minor units, income rounds down and tax rounds up. Every ratio is a
``Decimal`` worked out at 50 significant digits and rounded half-even to ``RATIO_PLACES``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, Money

_MONTHS = 12
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class IncomeFigures:
    """Dividends over a period (M4 spec §4).

    ``gross`` is what was paid, ``tax`` what the engine booked, and ``net`` what that left.
    ``take_home`` is what the full dividend tax leaves, whatever the engine booked (decision 2):
    the figure an investor living off dividends keeps. In a monthly average each of the four is
    divided and rounded down on its own, so ``net`` there can be a minor unit off
    ``gross - tax``.
    """

    gross: Money
    tax: Money
    net: Money
    take_home: Money

    @classmethod
    def zero(cls, currency: Currency) -> IncomeFigures:
        nothing = Money.zero(currency)
        return cls(nothing, nothing, nothing, nothing)

    def __add__(self, other: IncomeFigures) -> IncomeFigures:
        return IncomeFigures(
            self.gross + other.gross,
            self.tax + other.tax,
            self.net + other.net,
            self.take_home + other.take_home,
        )


@dataclass(frozen=True, slots=True)
class MonthlyIncome:
    """One calendar month's dividends. ``month`` is the month's first day."""

    month: date
    figures: IncomeFigures


@dataclass(frozen=True, slots=True)
class ReceivedIncome:
    """The dividends a run received, as of its last day (M4 spec §4).

    ``by_month`` holds every calendar month from the first day's to the last day's, including
    months with nothing paid. ``trailing`` covers the year window ending on ``as_of``, and
    ``monthly_average`` is each trailing figure divided by 12, rounded down. ``current_yield``
    divides the trailing gross by the last day's value, and ``yield_on_cost`` by what the final
    positions cost; each is ``None`` when its divisor is zero.
    """

    as_of: date
    by_month: tuple[MonthlyIncome, ...]
    trailing: IncomeFigures
    monthly_average: IncomeFigures
    current_yield: Decimal | None
    yield_on_cost: Decimal | None


def received_income(
    reports: Sequence[DayReport], final: EngineState, rules: MarketRules
) -> ReceivedIncome:
    """The income received by a run whose day reports, in order, are *reports*."""
    if not reports:
        msg = "a run with no days has no income report"
        raise ValueError(msg)
    as_of = reports[-1].day
    since = year_window_start(as_of)
    currency = final.holdings.portfolio.currency
    months: dict[date, IncomeFigures] = {}
    trailing = IncomeFigures.zero(currency)
    for report in reports:
        figures = _day_figures(report, rules, currency)
        month = report.day.replace(day=1)
        months[month] = months.get(month, IncomeFigures.zero(currency)) + figures
        if report.day >= since:
            trailing += figures
    by_month = tuple(
        MonthlyIncome(month, months.get(month, IncomeFigures.zero(currency)))
        for month in _months(reports[0].day, as_of)
    )
    average = IncomeFigures(
        _per_month(trailing.gross),
        _per_month(trailing.tax),
        _per_month(trailing.net),
        _per_month(trailing.take_home),
    )
    cost = sum(
        (position.cost_basis for position in final.holdings.portfolio.positions),
        Money.zero(currency),
    )
    return ReceivedIncome(
        as_of,
        by_month,
        trailing,
        average,
        _ratio(trailing.gross, reports[-1].value),
        _ratio(trailing.gross, cost),
    )


def _day_figures(report: DayReport, rules: MarketRules, currency: Currency) -> IncomeFigures:
    nothing = Money.zero(currency)
    gross = sum((entitlement.gross for entitlement in report.paid), nothing)
    take_home = sum(
        (_take_home(entitlement.gross, rules, report.day) for entitlement in report.paid), nothing
    )
    return IncomeFigures(gross, report.tax, gross - report.tax, take_home)


def _take_home(gross: Money, rules: MarketRules, on: date) -> Money:
    """What the full dividend tax on *on* leaves of *gross* (decision 2)."""
    return gross - rules.dividend_tax(gross, reinvested_by_deadline=False, on=on)


def _per_month(amount: Money) -> Money:
    """A year's *amount* as a monthly figure, rounded down."""
    return Money(amount.amount // _MONTHS, amount.currency)


def _ratio(numerator: Money, denominator: Money) -> Decimal | None:
    if denominator.amount == 0:
        return None
    quotient = _CONTEXT.divide(numerator.amount, denominator.amount)
    return quotient.quantize(RATIO_PLACES, context=_CONTEXT)


def _months(first: date, last: date) -> Iterator[date]:
    """The first day of every calendar month from *first*'s to *last*'s."""
    month = first.replace(day=1)
    while month <= last:
        yield month
        month = date(month.year + month.month // _MONTHS, month.month % _MONTHS + 1, 1)
