"""income_report and goal_progress: the report assembled, and the goal tracker (M4 §3.2, §5.4).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah. Each part of the report has its own tests; these
check that the report puts the right inputs into each part.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.income import (
    CLAIMS_LABEL,
    GROWTH_YEARS,
    HISTORY_YEARS,
    GoalProgress,
    IncomeFigures,
    IncomeGoal,
    IncomeSettings,
    ProjectionOutcome,
    ReceivedIncome,
    RunRate,
    dividend_growth,
    goal_progress,
    income_report,
    payment_calendar,
    project,
    received_income,
    run_rate,
    years_before,
)
from steadyhand.market import UnsupportedDateError
from steadyhand.metrics import year_window_start
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

BBCA = Instrument("BBCA", "IDX", IDR)
USD = Currency("USD", 2)
AS_OF = date(2025, 7, 7)
BOUGHT = date(2024, 1, 2)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def report(
    day: date, *, paid: Sequence[Entitlement] = (), tax: int = 0, holdings: int = 900_000
) -> DayReport:
    return DayReport(
        day=day,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=tuple(paid),
        tax=rp(tax),
        daily_cost=rp(0),
        deposit=rp(0),
        frozen=(),
        halt=None,
        settled=rp(100_000),
        unsettled=rp(0),
        holdings_value=rp(holdings),
        value=rp(holdings + 100_000),
        unit_price=Decimal(1),
        warnings=(),
    )


def final(shares: int = 1_000) -> EngineState:
    order = Order(BBCA, Side.BUY, shares, BOUGHT)
    fill = Fill(order, BOUGHT, shares, rp(900), Costs.zero(IDR))
    book = Portfolio.empty(IDR).deposit(rp(shares * 900), BOUGHT).apply_fill(fill, BOUGHT)
    return EngineState(Holdings(book))


def history() -> dict[Instrument, Sequence[CorporateAction]]:
    return {
        BBCA: [
            CashDividend(BBCA, date(2021, 4, 19), Decimal(40)),
            CashDividend(BBCA, date(2025, 4, 21), Decimal(50)),
        ]
    }


def run() -> list[DayReport]:
    pay = date(2025, 5, 14)
    paid = Entitlement(BBCA, date(2025, 4, 21), pay, rp(50_000))
    return [report(pay, paid=[paid], tax=5_000), report(AS_OF)]


def test_the_report_gathers_every_part_as_of_the_last_day() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)), rp(1_000), pay_lag_trading_days=3)
    got = income_report(run(), final(), history(), rules(), settings)
    rate = run_rate(final().holdings.portfolio, history(), rules(), AS_OF, 3)
    growth = dividend_growth(rate, history())
    received = received_income(run(), final(), rules())
    assert got.as_of == AS_OF
    assert got.received == received
    assert got.run_rate == rate
    assert got.calendar == payment_calendar(rate, rules())
    assert got.growth == growth
    assert got.projection == project(rate, growth, rp(900_000), settings, rules())
    assert got.goal == goal_progress(settings.goal, received, rate)
    # By hand: 50 x 1,000 = 50,000 a year, (50,000 - 5,000) / 12 = 3,750 a month; received
    # the same 45,000 of take-home, 3,750 a month; 3,750 / 10,000 = 0.375 of the goal.
    assert got.goal == GoalProgress(
        rp(10_000), rp(3_750), Decimal("0.375"), rp(3_750), Decimal("0.375")
    )


def test_the_report_shows_the_open_claims_as_an_estimate() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)), rp(1_000))
    assert income_report(run(), final(), history(), rules(), settings).claims == ()
    protected = (Protection(rp(30_000), date(2027, 12, 31)),)
    claim = DividendClaim(
        BBCA,
        date(2025, 4, 21),
        date(2025, 5, 14),
        rp(50_000),
        date(2026, 3, 31),
        rp(20_000),
        protected,
    )
    state = final()
    claimed = EngineState(Holdings(state.holdings.portfolio, claims=(claim,)))
    got = income_report(run(), claimed, history(), rules(), settings)
    assert got.claims == (claim,)
    assert (
        got.claims_label
        == CLAIMS_LABEL
        == ("Estimate: assumes the yearly realisation reports are filed")
    )


def test_the_projection_starts_from_the_holdings_not_the_idle_cash() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    idle = [*run()[:-1], report(AS_OF, holdings=0)]
    got = income_report(idle, final(), history(), rules(), settings)
    assert {s.outcome for s in got.projection.scenarios} == {ProjectionOutcome.CANNOT}


def test_the_calendar_pays_after_the_settings_pay_lag() -> None:
    # 21 April 2025 plus 3 trading days is 24 April; plus 14 is 14 May.
    goal = IncomeGoal(rp(10_000))
    short = income_report(run(), final(), history(), rules(), IncomeSettings(goal))
    quick = IncomeSettings(goal, pay_lag_trading_days=3)
    shorter = income_report(run(), final(), history(), rules(), quick)
    assert short.calendar.months.index(max(short.calendar.months)) == 4
    assert shorter.calendar.months.index(max(shorter.calendar.months)) == 3


def test_a_goal_in_another_currency_than_the_portfolio_is_refused() -> None:
    dollars = IncomeSettings(IncomeGoal(Money(100, USD)))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        income_report(run(), final(), history(), rules(), dollars)


def test_a_run_with_no_days_has_no_income_report() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    with pytest.raises(ValueError, match=r"^a run with no days has no income report$"):
        income_report([], final(), history(), rules(), settings)


def test_a_year_window_before_the_rules_first_day_is_refused_not_guessed() -> None:
    # A report on 30 June 2021 reads the dividends back to 1 July 2020, and IDX's rules start on
    # 1 January 2021: the pay month of a dividend on 8 December 2020 is not known.
    early: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [CashDividend(BBCA, date(2020, 12, 8), Decimal(50))]
    }
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    with pytest.raises(
        UnsupportedDateError, match=r"^steadyhand's IDX rules are primary-verified from 2021-01-01"
    ):
        income_report([report(date(2021, 6, 30))], final(), early, rules(), settings)


def test_a_holding_without_history_stops_the_report() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    with pytest.raises(ValueError, match=r"^BBCA: no dividend history was passed for a stock"):
        income_report(run(), final(), {}, rules(), settings)


def figures(take_home: int) -> IncomeFigures:
    return IncomeFigures(rp(0), rp(0), rp(0), rp(take_home))


def test_goal_shares_are_not_capped_at_one() -> None:
    received = ReceivedIncome(AS_OF, (), figures(3_000), figures(250), None, None)
    rate = RunRate(AS_OF, (), rp(16_667), rp(1_250))
    progress = goal_progress(IncomeGoal(rp(1_000)), received, rate)
    # 250 / 1,000 received; 1,250 / 1,000 at the run-rate: past the goal, and reported as such.
    assert progress == GoalProgress(rp(1_000), rp(250), Decimal("0.25"), rp(1_250), Decimal("1.25"))


def test_goal_progress_refuses_a_goal_in_another_currency() -> None:
    received = ReceivedIncome(AS_OF, (), figures(3_000), figures(250), None, None)
    rate = RunRate(AS_OF, (), rp(16_667), rp(1_250))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine USD with IDR$"):
        goal_progress(IncomeGoal(Money(100, USD)), received, rate)


def test_five_years_of_history_hold_every_window_the_report_reads() -> None:
    assert (HISTORY_YEARS, GROWTH_YEARS) == (5, 4)
    # The oldest window read is growth's earlier one: from 8 July 2020 to 7 July 2021. Five
    # years of history start on 7 July 2020, a day before it.
    assert year_window_start(years_before(AS_OF, GROWTH_YEARS)) == date(2020, 7, 8)
    assert years_before(AS_OF, HISTORY_YEARS) == date(2020, 7, 7)
