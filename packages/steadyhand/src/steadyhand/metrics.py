"""What one backtest run achieved: returns, drawdown, costs, turnover and dividends (M3 spec §8).

Money stays integer minor units. Every ratio is a ``Decimal`` worked out at 50 significant
digits and then rounded half-even to eight decimal places, so the same run always reports the
same digits, and they are exact while the whole part has fewer than 40 digits. A power is taken
with ``Decimal.ln`` and ``Decimal.exp``, never with ``float``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand.engine import DayReport, EngineState
from steadyhand.money import Money
from steadyhand.portfolio import MovementKind
from steadyhand.types import Fill

RATIO_PLACES = Decimal("0.00000001")
"""Every ratio is reported to eight decimal places."""
YEAR_DAYS = 365
"""Calendar days in the year that annual figures are scaled to, and in the trailing year."""
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class Drawdown:
    """The run's deepest fall in the unit value, from ``peak`` to ``trough``, as a fraction.

    A run whose unit value never fell has a depth of 0, with both dates on its first day.
    """

    depth: Decimal
    peak: date
    trough: date


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Trading costs by kind: broker fees, exchange levies, sale tax and the daily stamp duty."""

    fee: Money
    levy: Money
    sale_tax: Money
    daily: Money

    @property
    def total(self) -> Money:
        return self.fee + self.levy + self.sale_tax + self.daily


@dataclass(frozen=True, slots=True)
class DividendTotals:
    """Cash dividends paid during the run, and the tax booked on them."""

    gross: Money
    tax: Money

    @property
    def net(self) -> Money:
        return self.gross - self.tax


@dataclass(frozen=True, slots=True)
class Metrics:
    """One run's results (M3 spec §8).

    ``total_return`` is time-weighted: the unit value's change, so deposits are not gains.
    ``annual_return`` compounds it over the run's calendar days. ``turnover`` is the share of
    the average portfolio traded in a year. ``trailing_income`` is the net dividend income paid
    in the last ``YEAR_DAYS`` calendar days of the run.
    """

    final_value: Money
    deposited: Money
    total_return: Decimal
    annual_return: Decimal
    drawdown: Drawdown
    costs: CostBreakdown
    turnover: Decimal
    dividends: DividendTotals
    trailing_income: Money


def measure(reports: Sequence[DayReport], final: EngineState) -> Metrics:
    """The metrics of a run whose day reports, in order, are *reports* and last state *final*."""
    if not reports:
        msg = "a run with no days has no metrics"
        raise ValueError(msg)
    first, last = reports[0].day, reports[-1].day
    days = (last - first).days + 1
    currency = final.holdings.portfolio.currency
    nothing = Money.zero(currency)
    deposited = sum(
        (m.amount for m in final.holdings.portfolio.ledger if m.kind is MovementKind.DEPOSIT),
        nothing,
    )
    fills = [fill for report in reports for fill in report.fills]
    costs = CostBreakdown(
        sum((fill.costs.fee for fill in fills), nothing),
        sum((fill.costs.levy for fill in fills), nothing),
        sum((fill.costs.tax for fill in fills), nothing),
        sum((report.daily_cost for report in reports), nothing),
    )
    dividends = DividendTotals(
        sum((e.gross for report in reports for e in report.paid), nothing),
        sum((report.tax for report in reports), nothing),
    )
    since = last - timedelta(days=YEAR_DAYS - 1)
    trailing = [report for report in reports if report.day >= since]
    trailing_income = sum((e.gross for report in trailing for e in report.paid), nothing) - sum(
        (report.tax for report in trailing), nothing
    )
    return Metrics(
        final_value=reports[-1].value,
        deposited=deposited,
        total_return=_rounded(_CONTEXT.subtract(final.units.price, Decimal(1))),
        annual_return=_annual(final.units.price, days),
        drawdown=_drawdown(reports),
        costs=costs,
        turnover=_turnover(reports, fills, days),
        dividends=dividends,
        trailing_income=trailing_income,
    )


def _rounded(value: Decimal) -> Decimal:
    """*value* to eight places, in a context wide enough for its whole part, so that a huge
    annualised return from a short run is reported rather than refused."""
    wide = Context(prec=max(_CONTEXT.prec, value.adjusted() + 1 + 8), rounding=ROUND_HALF_EVEN)
    return value.quantize(RATIO_PLACES, context=wide)


def _annual(growth: Decimal, days: int) -> Decimal:
    """Compound annual return: ``growth`` over ``days`` calendar days, scaled to a year."""
    if growth == 0:
        return _rounded(Decimal(-1))
    exponent = _CONTEXT.divide(_CONTEXT.multiply(growth.ln(_CONTEXT), YEAR_DAYS), days)
    return _rounded(_CONTEXT.subtract(exponent.exp(_CONTEXT), Decimal(1)))


def _drawdown(reports: Sequence[DayReport]) -> Drawdown:
    """The deepest fall from a running peak of the unit value, which starts at 1."""
    peak, peak_day = Decimal(1), reports[0].day
    deepest = Drawdown(Decimal(0), peak_day, peak_day)
    for report in reports:
        if report.unit_price > peak:
            peak, peak_day = report.unit_price, report.day
            continue
        depth = _CONTEXT.divide(_CONTEXT.subtract(peak, report.unit_price), peak)
        if depth > deepest.depth:
            deepest = Drawdown(depth, peak_day, report.day)
    return Drawdown(_rounded(deepest.depth), deepest.peak, deepest.trough)


def _turnover(reports: Sequence[DayReport], fills: Sequence[Fill], days: int) -> Decimal:
    """(Gross bought + gross sold) / 2 / the average daily value, scaled to a year."""
    traded = sum(fill.gross.amount for fill in fills)
    average = _CONTEXT.divide(sum(report.value.amount for report in reports), len(reports))
    if average == 0:
        return _rounded(Decimal(0))
    yearly = _CONTEXT.divide(_CONTEXT.multiply(traded, YEAR_DAYS), _CONTEXT.multiply(2, days))
    return _rounded(_CONTEXT.divide(yearly, average))
