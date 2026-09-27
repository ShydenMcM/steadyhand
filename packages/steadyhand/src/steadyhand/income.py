"""Dividend income: what a run received, what its holdings pay now, and where that leads (M4 spec).

Every function here is pure. The caller passes the run's day reports, its last state and, where a
figure needs it, each holding's dividend history; nothing here reads a file or the network.
Money stays integer minor units, income rounds down and tax rounds up. Every ratio is a
``Decimal`` worked out at 50 significant digits and rounded half-even to ``RATIO_PLACES``.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal
from enum import Enum

from steadyhand._validate import require_int, require_type
from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement
from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules, add_trading_days
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, CurrencyMismatchError, Money, Rounding
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Split

PROJECTION_LABEL = "Projection, not a promise"
"""Carried by every projection: it reports years, never a date (core spec §7)."""

PROJECTION_MONTHS = 600
"""A projection stops after 50 years: a target not met by then is ``NOT_WITHIN``."""

GROWTH_YEARS = 4
"""Dividend growth compares the trailing year with the year ending this many years earlier."""

HISTORY_YEARS = 5
"""An income report needs each holding's corporate actions from this many years before its day,
which holds every window it reads (M4 spec §3.2)."""

PESSIMISTIC_START = Decimal("0.8")
"""The pessimistic scenario starts from this share of the run-rate (core spec §7)."""

BASE_GROWTH_CAP = Decimal("0.05")
OPTIMISTIC_GROWTH_CAP = Decimal("0.10")
"""The base and optimistic scenarios grow dividends at the measured rate, up to these caps."""

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


@dataclass(frozen=True, slots=True)
class HoldingGrowth:
    """One holding's measured dividend growth (M4 spec §5.2).

    ``recent`` and ``earlier`` are its dividends a share, restated onto today's basis, over the
    year windows ending on the run-rate's day and ``GROWTH_YEARS`` years before it. ``growth``
    is the yearly rate that turns one into the other over those years, or 0 when ``earlier`` is
    0: it paid nothing then, or its history does not reach back that far.
    """

    instrument: Instrument
    recent: Decimal
    earlier: Decimal
    growth: Decimal


@dataclass(frozen=True, slots=True)
class DividendGrowth:
    """Each paying holding's growth, and the portfolio's: theirs weighted by run-rate gross.

    A holding whose run-rate is zero carries no weight and is left out. ``notes`` name each
    holding whose growth could not be measured.
    """

    holdings: tuple[HoldingGrowth, ...]
    portfolio: Decimal
    notes: tuple[Note, ...]


@dataclass(frozen=True, slots=True)
class IncomeGoal:
    """The monthly take-home income an investor wants their dividends to reach."""

    monthly_target: Money

    def __post_init__(self) -> None:
        require_type(self.monthly_target, Money, "monthly_target")
        if self.monthly_target.amount <= 0:
            msg = f"an income goal must be positive, got {self.monthly_target}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class IncomeSettings:
    """What an income report needs beyond the run itself.

    The contribution and the pay lag are the engine's (``EngineSettings``), so that the
    projection adds what the run added and the calendar pays when the engine paid.
    """

    goal: IncomeGoal
    monthly_contribution: Money | None = None
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS

    def __post_init__(self) -> None:
        require_type(self.goal, IncomeGoal, "goal")
        if self.monthly_contribution is not None:
            require_type(self.monthly_contribution, Money, "monthly_contribution")
            if self.monthly_contribution.amount <= 0:
                msg = f"a monthly contribution must be positive, got {self.monthly_contribution}"
                raise ValueError(msg)
            target = self.goal.monthly_target
            if self.monthly_contribution.currency != target.currency:
                raise CurrencyMismatchError(target.currency, self.monthly_contribution.currency)
        require_int(self.pay_lag_trading_days, "pay_lag_trading_days", minimum=1)


class Scenario(Enum):
    """The three projections of core spec §7, as amended by decision 5."""

    PESSIMISTIC = "pessimistic"
    BASE = "base"
    OPTIMISTIC = "optimistic"


class ProjectionOutcome(Enum):
    """``REACHED`` in some years, ``NOT_WITHIN`` 50 years, or ``CANNOT``: nothing to project."""

    REACHED = "reached"
    NOT_WITHIN = "not within 50 years"
    CANNOT = "cannot project"


@dataclass(frozen=True, slots=True)
class ScenarioProjection:
    """One scenario: where it starts, how its dividends grow, and when it meets the target.

    ``years`` is rounded up to a tenth, and is ``None`` unless the outcome is ``REACHED``.
    """

    scenario: Scenario
    starting_gross: Money
    growth: Decimal
    outcome: ProjectionOutcome
    years: Decimal | None


@dataclass(frozen=True, slots=True)
class Projection:
    """How long until the goal is met, in three scenarios (M4 spec §5.3). Never a promise."""

    target: Money
    contribution: Money
    scenarios: tuple[ScenarioProjection, ...]
    notes: tuple[Note, ...]

    @property
    def label(self) -> str:
        return PROJECTION_LABEL


@dataclass(frozen=True, slots=True)
class GoalProgress:
    """How far the income is from the goal (M4 spec §5.4).

    ``received`` is the monthly average take-home over the trailing year and ``run_rate`` the
    run-rate's monthly take-home; each share is that figure over the target, not capped at 1.
    """

    target: Money
    received: Money
    received_share: Decimal
    run_rate: Money
    run_rate_share: Decimal


@dataclass(frozen=True, slots=True)
class IncomeReport:
    """A run's dividend income, as of its last day: everything M5's ``report --income`` shows."""

    as_of: date
    received: ReceivedIncome
    run_rate: RunRate
    calendar: PaymentCalendar
    growth: DividendGrowth
    projection: Projection
    goal: GoalProgress


def income_report(
    reports: Sequence[DayReport],
    final: EngineState,
    history: Mapping[Instrument, Sequence[CorporateAction]],
    rules: MarketRules,
    settings: IncomeSettings,
) -> IncomeReport:
    """The income report of a run whose day reports, in order, are *reports* (M4 spec §3.2).

    *history* holds, for every stock in the final portfolio, its corporate actions with an
    ex-date from ``HISTORY_YEARS`` years before the last day to the last day. The caller fetches
    it; nothing here reads a file or the network.
    """
    received = received_income(reports, final, rules)
    portfolio = final.holdings.portfolio
    target = settings.goal.monthly_target
    if target.currency != portfolio.currency:
        raise CurrencyMismatchError(portfolio.currency, target.currency)
    rate = run_rate(portfolio, history, rules, received.as_of, settings.pay_lag_trading_days)
    growth = dividend_growth(rate, history)
    return IncomeReport(
        received.as_of,
        received,
        rate,
        payment_calendar(rate, rules),
        growth,
        project(rate, growth, reports[-1].holdings_value, settings, rules),
        goal_progress(settings.goal, received, rate),
    )


def goal_progress(goal: IncomeGoal, received: ReceivedIncome, rate: RunRate) -> GoalProgress:
    """The goal tracker: received and run-rate monthly take-home against the target (§5.4)."""
    target = goal.monthly_target
    got, expected = received.monthly_average.take_home, rate.monthly_take_home
    return GoalProgress(target, got, _share(got, target), expected, _share(expected, target))


def years_before(day: date, years: int) -> date:
    """The same month and day *years* years before *day*; 29 February becomes 28 February."""
    year = day.year - years
    if (day.month, day.day) == (2, 29) and not calendar.isleap(year):
        return date(year, 2, 28)
    return day.replace(year=year)


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


def dividend_growth(
    rate: RunRate, history: Mapping[Instrument, Sequence[CorporateAction]]
) -> DividendGrowth:
    """Each paying holding's dividend growth over ``GROWTH_YEARS`` years (M4 spec §5.2).

    This is the growth of what the portfolio holds, a share at a time, not of the income it
    received: received income also grows with every contribution and reinvested dividend,
    which the projection adds month by month, so measuring from it would count them twice.
    """
    earlier_end = years_before(rate.as_of, GROWTH_YEARS)
    found: list[HoldingGrowth] = []
    notes: list[Note] = []
    weighted = Decimal(0)
    for holding in rate.holdings:
        if holding.annual_gross.amount == 0:
            continue
        actions = _history_of(holding.instrument, history)
        recent = _per_share(actions, rate.as_of, rate.as_of)
        earlier = _per_share(actions, earlier_end, rate.as_of)
        if earlier == 0:
            growth = Decimal(0)
            notes.append(
                Note(
                    INCOME_GROWTH_SHORT_HISTORY,
                    f"{holding.instrument.symbol}: no dividend was found in the year ending "
                    f"{earlier_end.isoformat()}, so its dividend growth is taken as 0%",
                )
            )
        else:
            yearly = _CONTEXT.divide(_CONTEXT.divide(recent, earlier).ln(_CONTEXT), GROWTH_YEARS)
            growth = _rounded(_CONTEXT.subtract(yearly.exp(_CONTEXT), Decimal(1)))
        found.append(HoldingGrowth(holding.instrument, recent, earlier, growth))
        weighted = _CONTEXT.add(weighted, _CONTEXT.multiply(growth, holding.annual_gross.amount))
    total = rate.annual_gross.amount
    portfolio = _rounded(_CONTEXT.divide(weighted, total)) if total else Decimal(0)
    return DividendGrowth(tuple(found), portfolio, tuple(notes))


def project(
    rate: RunRate,
    growth: DividendGrowth,
    holdings_value: Money,
    settings: IncomeSettings,
    rules: MarketRules,
) -> Projection:
    """How long until the goal is met, in each scenario (M4 spec §5.3).

    Each scenario starts from the run-rate's gross and the holdings' value; idle cash is not
    assumed invested. Month by month it reinvests the take-home part of the income plus the
    contribution at the portfolio's current yield, grows dividends once a year, and checks the
    monthly take-home against the target. Income rounds down, tax rounds up, and trading costs
    are left out.
    """
    target = settings.goal.monthly_target
    if target.currency != rate.annual_gross.currency:
        raise CurrencyMismatchError(rate.annual_gross.currency, target.currency)
    given = settings.monthly_contribution
    contribution = Money.zero(target.currency) if given is None else given
    measured = growth.portfolio
    plans = (
        (
            Scenario.PESSIMISTIC,
            rate.annual_gross.times(PESSIMISTIC_START, Rounding.DOWN),
            min(Decimal(0), measured),
        ),
        (Scenario.BASE, rate.annual_gross, min(measured, BASE_GROWTH_CAP)),
        (Scenario.OPTIMISTIC, rate.annual_gross, min(measured, OPTIMISTIC_GROWTH_CAP)),
    )
    projector = _Projector(target, contribution, rules, rate.as_of)
    scenarios: list[ScenarioProjection] = []
    for scenario, start, rate_of_growth in plans:
        if rate.annual_gross.amount == 0 or holdings_value.amount == 0:
            outcome, years = ProjectionOutcome.CANNOT, None
        else:
            years = projector.years(start, holdings_value, rate_of_growth)
            outcome = ProjectionOutcome.NOT_WITHIN if years is None else ProjectionOutcome.REACHED
        scenarios.append(ScenarioProjection(scenario, start, rate_of_growth, outcome, years))
    note = Note(
        INCOME_PROJECTION_COSTS_IGNORED,
        "Reinvesting costs broker fees and levies, which this projection leaves out, so it "
        "reaches the target a little sooner than a real portfolio would",
    )
    return Projection(target, contribution, tuple(scenarios), (note,))


@dataclass(frozen=True, slots=True)
class _Projector:
    """One goal's month-by-month simulation, shared by the three scenarios."""

    target: Money
    contribution: Money
    rules: MarketRules
    as_of: date

    def years(self, income: Money, value: Money, growth: Decimal) -> Decimal | None:
        """Years until the target is met, rounded up to a tenth, or ``None`` after 600 months.

        Reinvesting at the holdings' own yield leaves the yield, income over value, unchanged:
        ``(I + n·I/V) / (V + n) = I/V``. So the yield is kept exactly, as a ratio of integers that
        only growth changes, and the income is rounded down only where a month uses it. Rounding
        it down every month instead lost an amount that depended on the month's figures, and a
        larger contribution could then take longer (#97).
        """
        if self._met(income):
            return _tenths(0)
        numerator, denominator = income.amount, value.amount
        grow_by, grow_over = (1 + growth).as_integer_ratio()
        worth = value.amount
        for month in range(1, PROJECTION_MONTHS + 1):
            monthly = _per_month(income)
            worth += (monthly - self._tax(monthly) + self.contribution).amount
            if month % _MONTHS == 0:
                numerator, denominator = numerator * grow_by, denominator * grow_over
            income = Money(worth * numerator // denominator, income.currency)
            if self._met(income):
                return _tenths(month)
        return None

    def _met(self, income: Money) -> bool:
        return _per_month(income - self._tax(income)) >= self.target

    def _tax(self, gross: Money) -> Money:
        return self.rules.dividend_tax(gross, reinvested_by_deadline=False, on=self.as_of)


def _tenths(months: int) -> Decimal:
    """*months* in years, rounded up to one decimal place."""
    return Decimal(-(-months * 10 // _MONTHS)).scaleb(-1)


def _per_share(actions: Sequence[CorporateAction], end: date, as_of: date) -> Decimal:
    """The cash dividends a share in the year window ending on *end*, on *as_of*'s basis."""
    since = year_window_start(end)
    total = Decimal(0)
    for action in actions:
        if isinstance(action, CashDividend) and since <= action.ex_date <= end:
            old, new = _split_ratio(action.ex_date, actions, as_of)
            restated = _CONTEXT.divide(_CONTEXT.multiply(action.per_share, old), new)
            total = _CONTEXT.add(total, restated)
    return total


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
    return _rounded(_CONTEXT.divide(numerator.amount, denominator.amount))


def _share(part: Money, target: Money) -> Decimal:
    if part.currency != target.currency:
        raise CurrencyMismatchError(target.currency, part.currency)
    return _rounded(_CONTEXT.divide(part.amount, target.amount))


def _rounded(value: Decimal) -> Decimal:
    return value.quantize(RATIO_PLACES, context=_CONTEXT)


def _months(first: date, last: date) -> Iterator[date]:
    """The first day of every calendar month from *first*'s to *last*'s."""
    month = first.replace(day=1)
    while month <= last:
        yield month
        month = date(month.year + month.month // _MONTHS, month.month % _MONTHS + 1, 1)
