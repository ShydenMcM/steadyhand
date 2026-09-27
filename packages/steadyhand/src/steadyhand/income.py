"""Dividend income: what a run received, what its holdings pay now, and where that leads (M4 spec).

Every function here is pure. The caller passes the run's day reports, its last state and, where a
figure needs it, each holding's dividend history; nothing here reads a file or the network.
Money stays integer minor units, income rounds down and tax rounds up. Every ratio is a
``Decimal`` worked out at 50 significant digits and rounded half-even to ``RATIO_PLACES``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand._validate import require_int
from steadyhand.corporate import Entitlement
from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules, add_trading_days
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Split

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


@dataclass(frozen=True, slots=True)
class HoldingRunRate:
    """What one holding would pay in a year at its trailing dividends (M4 spec §5.1).

    ``dividends`` are the holding's cash dividends with an ex-date in the year window ending on
    the run-rate's day, each restated onto today's share basis (§3.3), multiplied by the shares
    held now and rounded down, and paid on its modelled pay date. A dividend that rounds to
    nothing is left out, as the engine leaves out a zero entitlement.
    """

    instrument: Instrument
    shares: int
    dividends: tuple[Entitlement, ...]
    annual_gross: Money
    monthly_take_home: Money


@dataclass(frozen=True, slots=True)
class RunRate:
    """What the final portfolio would pay in a year at its holdings' trailing dividends.

    A monthly take-home is the annual gross less the full dividend tax on ``as_of``, divided by
    12 and rounded down. The portfolio's is worked out from its own annual gross, so it can be a
    minor unit or two more than the holdings' monthly figures added up.
    """

    as_of: date
    holdings: tuple[HoldingRunRate, ...]
    annual_gross: Money
    monthly_take_home: Money


@dataclass(frozen=True, slots=True)
class HoldingCalendar:
    """One holding's expected take-home by month of the year, January first."""

    instrument: Instrument
    months: tuple[Money, ...]


@dataclass(frozen=True, slots=True)
class PaymentCalendar:
    """Expected take-home by month of the year, January first, from the run-rate (M4 §5.1).

    Each dividend counts in the month of its modelled pay date, less the full tax on the
    run-rate's day. ``empty_months`` counts the months with nothing, and ``evenness`` is the
    largest month's share of the year: 1/12 when every month is equal, 1 when one month has it
    all, and ``None`` when there is nothing to share.
    """

    months: tuple[Money, ...]
    holdings: tuple[HoldingCalendar, ...]
    empty_months: int
    evenness: Decimal | None


def run_rate(
    portfolio: Portfolio,
    history: Mapping[Instrument, Sequence[CorporateAction]],
    rules: MarketRules,
    as_of: date,
    pay_lag_trading_days: int,
) -> RunRate:
    """The run-rate of *portfolio*'s holdings on *as_of* (M4 spec §5.1).

    *history* holds each held stock's corporate actions; a stock the portfolio holds and
    *history* lacks is an error, never read as a stock that pays nothing.
    """
    require_int(pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
    since = year_window_start(as_of)
    nothing = Money.zero(portfolio.currency)
    holdings: list[HoldingRunRate] = []
    for position in portfolio.positions:
        stock = position.instrument
        actions = _history_of(stock, history)
        dividends = [
            action
            for action in actions
            if isinstance(action, CashDividend) and since <= action.ex_date <= as_of
        ]
        paid: list[Entitlement] = []
        for dividend in sorted(dividends, key=lambda found: found.ex_date):
            gross = _restated_gross(dividend, position.quantity, actions, as_of)
            if gross.amount > 0:
                pay = add_trading_days(rules, dividend.ex_date, pay_lag_trading_days)
                paid.append(Entitlement(stock, dividend.ex_date, pay, gross))
        annual = sum((entitlement.gross for entitlement in paid), nothing)
        monthly = _per_month(_take_home(annual, rules, as_of))
        holdings.append(HoldingRunRate(stock, position.quantity, tuple(paid), annual, monthly))
    total = sum((holding.annual_gross for holding in holdings), nothing)
    return RunRate(as_of, tuple(holdings), total, _per_month(_take_home(total, rules, as_of)))


def payment_calendar(rate: RunRate, rules: MarketRules) -> PaymentCalendar:
    """Where in the year *rate*'s dividends would arrive, as take-home (M4 spec §5.1)."""
    nothing = Money.zero(rate.annual_gross.currency)
    totals = [nothing] * _MONTHS
    holdings: list[HoldingCalendar] = []
    for holding in rate.holdings:
        months = [nothing] * _MONTHS
        for dividend in holding.dividends:
            months[dividend.pay_date.month - 1] += _take_home(dividend.gross, rules, rate.as_of)
        totals = [total + month for total, month in zip(totals, months, strict=True)]
        holdings.append(HoldingCalendar(holding.instrument, tuple(months)))
    year = sum(totals, nothing)
    return PaymentCalendar(
        tuple(totals),
        tuple(holdings),
        sum(1 for month in totals if month.amount == 0),
        _ratio(max(totals), year),
    )


def _history_of(
    stock: Instrument, history: Mapping[Instrument, Sequence[CorporateAction]]
) -> Sequence[CorporateAction]:
    actions = history.get(stock)
    if actions is None:
        msg = f"{stock.symbol}: no dividend history was passed for a stock the portfolio holds"
        raise ValueError(msg)
    for action in actions:
        if action.instrument != stock:
            msg = f"{stock.symbol}: its history holds an action for {action.instrument.symbol}"
            raise ValueError(msg)
    return actions


def _split_ratio(ex_date: date, actions: Sequence[CorporateAction], as_of: date) -> tuple[int, int]:
    """The (old, new) share counts of every split from *ex_date* to *as_of*, multiplied together.

    A split on the dividend's own ex-date counts: the engine pays that dividend on the shares
    held before the split (``corporate.apply_actions``), so it is on the old basis.
    """
    old = new = 1
    for action in actions:
        if isinstance(action, Split) and ex_date <= action.ex_date <= as_of:
            old *= action.old_shares
            new *= action.new_shares
    return old, new


def _restated_gross(
    dividend: CashDividend, shares: int, actions: Sequence[CorporateAction], as_of: date
) -> Money:
    """*dividend* on *shares* of today's basis, rounded down once (M4 spec §3.3).

    Worked in integers from the exact ratio of ``per_share``, so a 1-for-3 split, whose ratio
    no ``Decimal`` can hold, still gives the exact amount before the one rounding.
    """
    old, new = _split_ratio(dividend.ex_date, actions, as_of)
    numerator, denominator = dividend.per_share.as_integer_ratio()
    currency = dividend.instrument.currency
    scale = 10**currency.minor_units
    return Money(numerator * shares * old * scale // (denominator * new), currency)


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
