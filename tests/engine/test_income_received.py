"""received_income: dividends by month and over the trailing year, take-home and yields (M4 §4).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.income import IncomeFigures, MonthlyIncome, received_income
from steadyhand.money import IDR, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

BBCA = Instrument("BBCA", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
BOUGHT = date(2024, 1, 2)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def paid(day: date, gross: int, stock: Instrument = BBCA) -> Entitlement:
    return Entitlement(stock, day - timedelta(days=20), day, rp(gross))


def report(
    day: date, *, paid: Sequence[Entitlement] = (), tax: int = 0, value: int = 1_000_000
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
        settled=rp(value),
        unsettled=rp(0),
        holdings_value=rp(0),
        value=rp(value),
        unit_price=Decimal(1),
        warnings=(),
    )


def final(**cost: int) -> EngineState:
    """The last state: 100 shares of each named stock, bought for the given total cost."""
    book = Portfolio.empty(IDR)
    for symbol, total in cost.items():
        order = Order(Instrument(symbol, "IDX", IDR), Side.BUY, 100, BOUGHT)
        fill = Fill(order, BOUGHT, 100, rp(total // 100), Costs.zero(IDR))
        book = book.deposit(rp(total), BOUGHT).apply_fill(fill, BOUGHT)
    return EngineState(Holdings(book))


def figures(gross: int, tax: int, net: int, take_home: int) -> IncomeFigures:
    return IncomeFigures(rp(gross), rp(tax), rp(net), rp(take_home))


def test_each_month_sums_what_was_paid_and_booked_and_empty_months_are_kept() -> None:
    run = [
        report(
            date(2025, 1, 30),
            paid=[paid(date(2025, 1, 30), 1_000), paid(date(2025, 1, 30), 555, TLKM)],
            tax=156,
        ),
        report(date(2025, 3, 3)),
        report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 2_000)], tax=200),
    ]
    income = received_income(run, final(), rules())
    assert income.as_of == date(2025, 3, 10)
    assert income.by_month == (
        # Take-home: 1,000 - 100 = 900, and 555 - 56 (55.5 rounded up) = 499.
        MonthlyIncome(date(2025, 1, 1), figures(1_555, 156, 1_399, 1_399)),
        MonthlyIncome(date(2025, 2, 1), figures(0, 0, 0, 0)),
        MonthlyIncome(date(2025, 3, 1), figures(2_000, 200, 1_800, 1_800)),
    )


def test_take_home_is_after_the_full_tax_whatever_was_booked() -> None:
    # Decision 2: nothing was booked (as if exempt), but living off it means paying the 10%.
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], tax=0)]
    income = received_income(run, final(), rules())
    assert income.by_month[0].figures == figures(1_000, 0, 1_000, 900)
    assert income.trailing == figures(1_000, 0, 1_000, 900)


def test_the_trailing_year_is_the_365_days_ending_on_the_last_day() -> None:
    # The window ending on Monday 7 July 2025 starts on Monday 8 July 2024.
    run = [
        report(date(2024, 7, 5), paid=[paid(date(2024, 7, 5), 5_000)], tax=500),
        report(date(2024, 7, 8), paid=[paid(date(2024, 7, 8), 1_200)], tax=120),
        report(date(2025, 7, 7), paid=[paid(date(2025, 7, 7), 2_400)], tax=240),
    ]
    income = received_income(run, final(), rules())
    assert income.trailing == figures(3_600, 360, 3_240, 3_240)
    # Each figure / 12: 3,600 -> 300, 360 -> 30, 3,240 -> 270.
    assert income.monthly_average == figures(300, 30, 270, 270)
    # By month is not trimmed: July 2024 keeps both of its payments, and there are 13 months.
    assert len(income.by_month) == 13
    assert income.by_month[0] == MonthlyIncome(date(2024, 7, 1), figures(6_200, 620, 5_580, 5_580))


def test_each_monthly_average_is_rounded_down_on_its_own() -> None:
    # Paid 12 with 2 booked, take-home 12 - 2 (1.2 rounded up) = 10. Each / 12 rounds down:
    # gross 1, tax 0, net 10 -> 0 and take-home 0, so net is not gross - tax here.
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 12)], tax=2)]
    income = received_income(run, final(), rules())
    assert income.trailing == figures(12, 2, 10, 10)
    assert income.monthly_average == figures(1, 0, 0, 0)


def test_the_current_yield_and_the_yield_on_cost() -> None:
    run = [
        report(date(2025, 3, 3), value=10),
        report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], tax=100, value=40_000),
    ]
    income = received_income(run, final(BBCA=15_000, TLKM=10_000), rules())
    # 1,000 / 40,000 on the last day's value; 1,000 / (15,000 + 10,000) on cost.
    assert income.current_yield == Decimal("0.02500000")
    assert income.yield_on_cost == Decimal("0.04000000")


def test_a_yield_is_rounded_half_even_to_eight_places() -> None:
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], value=3_000)]
    income = received_income(run, final(BBCA=6_000), rules())
    # 1,000 / 3,000 = 0.333333333...; 1,000 / 6,000 = 0.1666666666... rounds up to ...67.
    assert income.current_yield == Decimal("0.33333333")
    assert income.yield_on_cost == Decimal("0.16666667")


def test_a_yield_is_none_when_its_divisor_is_zero() -> None:
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], value=0)]
    income = received_income(run, final(), rules())
    assert income.current_yield is None
    assert income.yield_on_cost is None


def test_months_run_across_a_year_end() -> None:
    run = [report(date(2024, 12, 30)), report(date(2025, 2, 3))]
    income = received_income(run, final(), rules())
    months = [month.month for month in income.by_month]
    assert months == [date(2024, 12, 1), date(2025, 1, 1), date(2025, 2, 1)]


def test_a_run_with_no_days_has_no_income_report() -> None:
    with pytest.raises(ValueError, match=r"^a run with no days has no income report$"):
        received_income([], final(), rules())


@given(st.lists(st.integers(min_value=1, max_value=10**12), min_size=1, max_size=5))
def test_take_home_is_never_more_than_gross(amounts: list[int]) -> None:
    day = date(2025, 3, 10)
    run = [report(day, paid=[paid(day, amount) for amount in amounts])]
    trailing = received_income(run, final(), rules()).trailing
    assert Money.zero(IDR) <= trailing.take_home <= trailing.gross
