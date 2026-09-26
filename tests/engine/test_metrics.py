"""measure: one run's returns, drawdown, costs, turnover and dividends (M3 spec §8).

Every expected number is worked out by hand in the test, never by the code under test.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.metrics import RATIO_PLACES, CostBreakdown, DividendTotals, Drawdown, measure
from steadyhand.money import IDR, Money
from steadyhand.portfolio import Portfolio
from steadyhand.risk import UnitValue
from steadyhand.types import Costs, Fill, Instrument, Order, Side

BBCA = Instrument("BBCA", "IDX", IDR)
MONDAY = date(2025, 7, 7)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def report(
    day: date,
    *,
    value: int = 1_000_000,
    price: str = "1",
    fills: Sequence[Fill] = (),
    paid: Sequence[Entitlement] = (),
    tax: int = 0,
    daily: int = 0,
) -> DayReport:
    return DayReport(
        day=day,
        fills=tuple(fills),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=tuple(paid),
        tax=rp(tax),
        daily_cost=rp(daily),
        deposit=rp(0),
        frozen=(),
        halt=None,
        settled=rp(value),
        unsettled=rp(0),
        holdings_value=rp(0),
        value=rp(value),
        unit_price=Decimal(price),
        warnings=(),
    )


def final(price: str = "1", deposits: Sequence[int] = (1_000_000,)) -> EngineState:
    portfolio = Portfolio.empty(IDR)
    for amount in deposits:
        portfolio = portfolio.deposit(rp(amount), MONDAY)
    units = UnitValue(Decimal(sum(deposits)), Decimal(price), max(Decimal(1), Decimal(price)))
    return EngineState(Holdings(portfolio), units)


def fill(side: Side, quantity: int, price: int, fee: int = 0, levy: int = 0, tax: int = 0) -> Fill:
    order = Order(BBCA, side, quantity, MONDAY)
    return Fill(order, MONDAY, quantity, rp(price), Costs(rp(fee), rp(levy), rp(tax)))


def paid(day: date, gross: int) -> Entitlement:
    return Entitlement(BBCA, day - timedelta(days=20), day, rp(gross))


def days(count: int, start: date = MONDAY) -> list[date]:
    return [start + timedelta(days=n) for n in range(count)]


def test_returns_are_time_weighted_and_compounded_over_calendar_days() -> None:
    # 2021 and 2022 hold 730 calendar days. Growth of 1.21 over two years is 10% a year.
    run = [report(date(2021, 1, 1)), report(date(2022, 12, 31), value=1_815_000, price="1.21")]
    metrics = measure(run, final("1.21", deposits=(1_000_000, 500_000)))
    assert metrics.total_return == Decimal("0.21000000")
    assert metrics.annual_return == Decimal("0.10000000")
    assert metrics.final_value == rp(1_815_000)
    assert metrics.deposited == rp(1_500_000)


def test_only_deposits_count_as_deposited() -> None:
    # A dividend is cash coming in too, but it is a return, not money put in.
    portfolio = Portfolio.empty(IDR).deposit(rp(1_000_000), MONDAY)
    portfolio = portfolio.credit_dividend(rp(50_000), MONDAY)
    state = EngineState(Holdings(portfolio), UnitValue(Decimal(1_000_000)))
    assert measure([report(MONDAY, value=1_050_000)], state).deposited == rp(1_000_000)


def test_a_deposit_is_not_a_gain() -> None:
    # Half as much again was deposited, but the unit value never moved: no return at all.
    run = [report(day, value=1_500_000) for day in days(3)]
    metrics = measure(run, final("1", deposits=(1_000_000, 500_000)))
    assert (metrics.total_return, metrics.annual_return) == (Decimal(0), Decimal(0))


def test_a_total_loss_compounds_to_minus_one() -> None:
    run = [report(MONDAY), report(MONDAY + timedelta(days=9), value=0, price="0")]
    metrics = measure(run, final("0"))
    assert metrics.total_return == Decimal("-1.00000000")
    assert metrics.annual_return == Decimal("-1.00000000")


def test_a_one_day_run_scales_its_day_to_a_year() -> None:
    # 0.1% on one day, compounded over 365: 1.001 ** 365 = 1.44025131...
    metrics = measure([report(MONDAY, price="1.001")], final("1.001"))
    assert metrics.total_return == Decimal("0.00100000")
    assert metrics.annual_return == Decimal("0.44025131")


def test_a_huge_annualised_return_from_a_short_run_is_reported_whole() -> None:
    # 13.5% in one day compounds to 1.135 ** 365 - 1 = 118437561766240817509.438579149... a
    # year (worked out at 60 digits). Its eight places are still exact, and not refused.
    metrics = measure([report(MONDAY, price="1.135")], final("1.135"))
    assert metrics.annual_return == Decimal("118437561766240817509.43857915")


def test_the_drawdown_is_the_deepest_fall_from_a_running_peak() -> None:
    # 1.1 -> 0.99 is a 10% fall; 1.2 -> 1.05 is 12.5%, the deeper one.
    prices = ["1", "1.1", "0.99", "1.2", "1.05"]
    run = [report(day, price=p) for day, p in zip(days(5), prices, strict=True)]
    drawdown = measure(run, final("1.05")).drawdown
    assert drawdown == Drawdown(Decimal("0.12500000"), days(5)[3], days(5)[4])


def test_equal_falls_report_the_first_and_the_peak_starts_at_one() -> None:
    # The run opens at a unit value of 1, so a first day at 0.9 is already a 10% fall.
    prices = ["0.9", "1", "0.9"]
    run = [report(day, price=p) for day, p in zip(days(3), prices, strict=True)]
    drawdown = measure(run, final("0.9")).drawdown
    assert drawdown == Drawdown(Decimal("0.10000000"), MONDAY, MONDAY)


def test_a_run_that_never_falls_has_no_drawdown() -> None:
    run = [report(day, price=p) for day, p in zip(days(3), ["1", "1.01", "1.02"], strict=True)]
    assert measure(run, final("1.02")).drawdown == Drawdown(Decimal(0), MONDAY, MONDAY)


def test_costs_are_split_by_kind() -> None:
    fills = [
        fill(Side.BUY, 100, 9_000, fee=1_350, levy=270),
        fill(Side.SELL, 100, 9_100, 1_365, 273, 910),
    ]
    run = [report(MONDAY, fills=fills[:1]), report(days(2)[1], fills=fills[1:], daily=10_000)]
    costs = measure(run, final()).costs
    assert costs == CostBreakdown(rp(2_715), rp(543), rp(910), rp(10_000))
    assert costs.total == rp(14_168)


def test_turnover_is_half_the_traded_value_over_the_average_value_per_year() -> None:
    # Rp400,000 bought and Rp200,000 sold over two days, against an average value of
    # Rp1,000,000: 600,000 / 2 / 1,000,000 = 0.3 of the portfolio in 2 days, or 54.75 a year.
    fills = [fill(Side.BUY, 100, 4_000), fill(Side.SELL, 100, 2_000)]
    run = [report(MONDAY, fills=fills[:1]), report(days(2)[1], fills=fills[1:])]
    assert measure(run, final()).turnover == Decimal("54.75000000")


def test_the_average_value_uses_every_day() -> None:
    # Values of 1,000,000 and 3,000,000 average 2,000,000: 600,000 / 2 / 2,000,000 over 2 days.
    fills = [fill(Side.BUY, 100, 6_000)]
    run = [report(MONDAY, fills=fills), report(days(2)[1], value=3_000_000)]
    assert measure(run, final()).turnover == Decimal("27.37500000")


def test_turnover_of_a_worthless_portfolio_is_zero() -> None:
    run = [report(day, value=0, price="0") for day in days(2)]
    assert measure(run, final("0")).turnover == Decimal("0E-8")


def test_dividends_and_the_income_of_the_last_365_days() -> None:
    last = date(2022, 1, 10)
    # 365 days ending on 10 January 2022 start on 11 January 2021.
    run = [
        report(date(2021, 1, 10), paid=[paid(date(2021, 1, 10), 1_000)], tax=100),
        report(date(2021, 1, 11), paid=[paid(date(2021, 1, 11), 2_000)], tax=200),
        report(last, paid=[paid(last, 4_000)], tax=400),
    ]
    metrics = measure(run, final())
    assert metrics.dividends == DividendTotals(rp(7_000), rp(700))
    assert metrics.dividends.net == rp(6_300)
    assert metrics.trailing_income == rp(5_400)


def test_a_run_with_no_days_has_no_metrics() -> None:
    with pytest.raises(ValueError, match=r"^a run with no days has no metrics$"):
        measure([], final())


def _deepest_fall(prices: Sequence[Decimal]) -> Decimal:
    """Every (peak, later day) pair checked: an oracle with no running state."""
    worst = Decimal(0)
    for later, price in enumerate(prices):
        for peak in [Decimal(1), *prices[: later + 1]]:
            if peak > 0:
                worst = max(worst, (peak - price) / peak)
    return worst.quantize(RATIO_PLACES)


@given(st.lists(st.decimals(min_value=0, max_value=5, places=3), min_size=1, max_size=30))
def test_the_drawdown_matches_every_pair_checked(prices: list[Decimal]) -> None:
    run = [report(day, price=str(p)) for day, p in zip(days(len(prices)), prices, strict=True)]
    drawdown = measure(run, final(str(prices[-1]))).drawdown
    assert drawdown.depth == _deepest_fall(prices)
    assert Decimal(0) <= drawdown.depth <= Decimal(1)
    assert drawdown.peak <= drawdown.trough
