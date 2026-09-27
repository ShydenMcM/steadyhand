"""run_rate and payment_calendar: what the holdings pay now, and in which months (M4 §3.3, §5.1).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah. The run-rate is taken on Monday 7 July 2025, whose
year window starts on Monday 8 July 2024, with a pay lag of three trading days unless a test says
otherwise.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.income import (
    HoldingCalendar,
    HoldingRunRate,
    RunRate,
    payment_calendar,
    run_rate,
)
from steadyhand.money import IDR, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import (
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    Order,
    OtherAction,
    Side,
    Split,
)
from steadyhand_idx import IdxMarketRules

ASII = Instrument("ASII", "IDX", IDR)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
UNVR = Instrument("UNVR", "IDX", IDR)
AS_OF = date(2025, 7, 7)
BOUGHT = date(2024, 1, 2)
LAG = 3


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(**shares: int) -> Portfolio:
    """A portfolio holding the given shares, bought at Rp1 each before any dividend here."""
    book = Portfolio.empty(IDR)
    for symbol, quantity in shares.items():
        order = Order(Instrument(symbol, "IDX", IDR), Side.BUY, quantity, BOUGHT)
        fill = Fill(order, BOUGHT, quantity, rp(1), Costs.zero(IDR))
        book = book.deposit(rp(quantity), BOUGHT).apply_fill(fill, BOUGHT)
    return book


def dividend(stock: Instrument, ex_date: date, per_share: str) -> CashDividend:
    return CashDividend(stock, ex_date, Decimal(per_share))


def rate_of(
    portfolio: Portfolio, history: dict[Instrument, Sequence[CorporateAction]], lag: int = LAG
) -> RunRate:
    return run_rate(portfolio, history, rules(), AS_OF, lag)


def months(**amounts: int) -> tuple[Money, ...]:
    """Twelve monthly amounts, January first, from keyword arguments such as ``jan=900``."""
    names = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    return tuple(rp(amounts.get(name, 0)) for name in names)


def test_the_run_rate_restates_each_trailing_dividend_and_rounds_it_down() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [
            dividend(BBCA, date(2024, 7, 8), "12.5"),
            Split(BBCA, date(2025, 1, 6), 1, 5),
            OtherAction(BBCA, date(2025, 2, 3), "rights issue"),
            dividend(BBCA, date(2025, 4, 21), "55.5"),
        ],
        TLKM: [],
    }
    rate = rate_of(holding(BBCA=1_501, TLKM=100), history)
    # 12.5 a share before the 1-for-5 split is 2.5 now: 2.5 x 1,501 = 3,752.5, down to 3,752.
    # 55.5 x 1,501 = 83,305.5, down to 83,305. Paid three trading days after each ex-date.
    bbca = HoldingRunRate(
        BBCA,
        1_501,
        (
            Entitlement(BBCA, date(2024, 7, 8), date(2024, 7, 11), rp(3_752)),
            Entitlement(BBCA, date(2025, 4, 21), date(2025, 4, 24), rp(83_305)),
        ),
        # 3,752 + 83,305 = 87,057; tax 8,705.7 up to 8,706; (87,057 - 8,706) / 12 = 6,529.25.
        rp(87_057),
        rp(6_529),
    )
    assert rate == RunRate(
        AS_OF, (bbca, HoldingRunRate(TLKM, 100, (), rp(0), rp(0))), rp(87_057), rp(6_529)
    )


def test_the_year_window_holds_both_of_its_ends_and_nothing_outside_them() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [
            dividend(BBCA, date(2024, 7, 7), "1"),
            dividend(BBCA, date(2024, 7, 8), "2"),
            dividend(BBCA, AS_OF, "3"),
            dividend(BBCA, date(2025, 7, 8), "4"),
        ]
    }
    rate = rate_of(holding(BBCA=100), history)
    assert [entitled.ex_date for entitled in rate.holdings[0].dividends] == [
        date(2024, 7, 8),
        AS_OF,
    ]
    assert rate.annual_gross == rp(500)


def test_only_a_split_from_the_ex_date_to_the_run_rate_day_restates_a_dividend() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        # Before the dividend: it is already on today's basis.
        ASII: [Split(ASII, date(2024, 8, 1), 1, 2), dividend(ASII, date(2024, 9, 2), "10")],
        # After the run-rate's day: the shares held now are still on the old basis.
        BBRI: [dividend(BBRI, date(2025, 4, 21), "10"), Split(BBRI, date(2025, 7, 8), 1, 2)],
        # On the dividend's own ex-date: the engine pays it on the shares held before the split.
        UNVR: [dividend(UNVR, date(2025, 4, 21), "10"), Split(UNVR, date(2025, 4, 21), 1, 2)],
    }
    rate = rate_of(holding(ASII=100, BBRI=100, UNVR=100), history)
    assert [held.annual_gross for held in rate.holdings] == [rp(1_000), rp(1_000), rp(500)]


def test_a_split_no_decimal_can_hold_is_still_restated_exactly() -> None:
    # 100 a share before a 1-for-3 split, on 3,000 shares now: exactly 100,000. A Decimal third
    # (33.333...) times 3,000 would round down to 99,999.
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, date(2024, 9, 2), "100"), Split(BBCA, date(2025, 1, 6), 1, 3)]
    }
    assert rate_of(holding(BBCA=3_000), history).annual_gross == rp(100_000)


def test_the_portfolio_monthly_take_home_is_worked_out_from_its_own_annual_gross() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, date(2025, 4, 21), "0.65")],
        TLKM: [dividend(TLKM, date(2025, 4, 21), "0.65")],
    }
    rate = rate_of(holding(BBCA=100, TLKM=100), history)
    # Each holding: 65 - 7 (6.5 up) = 58, / 12 = 4. The portfolio: 130 - 13 = 117, / 12 = 9.
    assert [held.monthly_take_home for held in rate.holdings] == [rp(4), rp(4)]
    assert rate.monthly_take_home == rp(9)


def test_the_pay_date_is_the_engines_for_the_same_lag() -> None:
    # 14 trading days after Monday 21 April 2025, skipping 1, 12 and 13 May: Wednesday 14 May.
    ex = date(2025, 4, 21)
    history: dict[Instrument, Sequence[CorporateAction]] = {BBCA: [dividend(BBCA, ex, "10")]}
    rate = rate_of(holding(BBCA=100), history, PAY_LAG_TRADING_DAYS)
    engine = apply_actions(Holdings(holding(BBCA=100)), history[BBCA], ex, rules())
    assert rate.holdings[0].dividends[0].pay_date == date(2025, 5, 14)
    assert engine.entitled[0].pay_date == date(2025, 5, 14)


def test_a_held_stock_missing_from_the_history_is_an_error() -> None:
    with pytest.raises(
        ValueError,
        match=r"^TLKM: no dividend history was passed for a stock the portfolio holds$",
    ):
        rate_of(holding(BBCA=100, TLKM=100), {BBCA: []})


def test_a_history_holding_another_stocks_action_is_an_error() -> None:
    wrong: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(TLKM, date(2025, 4, 21), "10")]
    }
    with pytest.raises(ValueError, match=r"^BBCA: its history holds an action for TLKM$"):
        rate_of(holding(BBCA=100), wrong)


def test_the_pay_lag_is_at_least_one_trading_day() -> None:
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        rate_of(holding(BBCA=100), {BBCA: []}, 0)


prices = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal(10_000),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
ratios = st.tuples(st.integers(1, 10), st.integers(1, 10)).filter(lambda pair: pair[0] != pair[1])


@given(prices, st.integers(min_value=1, max_value=10**7))
def test_without_a_later_split_a_dividend_is_priced_as_the_engine_credits_it(
    per_share: Decimal, shares: int
) -> None:
    ex = date(2025, 4, 21)
    paid = CashDividend(BBCA, ex, per_share)
    engine = apply_actions(Holdings(holding(BBCA=shares)), [paid], ex, rules())
    rate = run_rate(holding(BBCA=shares), {BBCA: [paid]}, rules(), ex, PAY_LAG_TRADING_DAYS)
    assert rate.holdings[0].dividends == engine.entitled


@given(prices, st.integers(min_value=1, max_value=10**6), ratios, ratios)
def test_restating_across_two_splits_equals_restating_across_their_combined_ratio(
    per_share: Decimal, shares: int, first: tuple[int, int], second: tuple[int, int]
) -> None:
    combined = (first[0] * second[0], first[1] * second[1])
    assume(combined[0] != combined[1])
    paid = CashDividend(BBCA, date(2024, 9, 2), per_share)
    two: list[CorporateAction] = [
        paid,
        Split(BBCA, date(2024, 10, 1), *first),
        Split(BBCA, date(2025, 1, 6), *second),
    ]
    one: list[CorporateAction] = [paid, Split(BBCA, date(2024, 10, 1), *combined)]
    assert rate_of(holding(BBCA=shares), {BBCA: two}) == rate_of(holding(BBCA=shares), {BBCA: one})


def test_the_calendar_puts_each_dividend_in_its_pay_month_as_take_home() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        # Friday 27 December 2024: three trading days on is Friday 3 January 2025.
        # Thursday 27 March 2025: the market reopened after Idul Fitri on 8 April, so 10 April.
        BBCA: [dividend(BBCA, date(2024, 12, 27), "10"), dividend(BBCA, date(2025, 3, 27), "5")],
        TLKM: [dividend(TLKM, date(2025, 4, 21), "3")],
    }
    rate = rate_of(holding(BBCA=100, TLKM=200), history)
    assert [paid.pay_date for paid in rate.holdings[0].dividends] == [
        date(2025, 1, 3),
        date(2025, 4, 10),
    ]
    calendar = payment_calendar(rate, rules())
    # BBCA 1,000 - 100 in January and 500 - 50 in April; TLKM 600 - 60 in April.
    assert calendar.holdings == (
        HoldingCalendar(BBCA, months(jan=900, apr=450)),
        HoldingCalendar(TLKM, months(apr=540)),
    )
    assert calendar.months == months(jan=900, apr=990)
    assert calendar.empty_months == 10
    # 990 / (900 + 990) = 0.5238095238...
    assert calendar.evenness == Decimal("0.52380952")


def test_a_calendar_paying_the_same_every_month_scores_one_twelfth() -> None:
    ex_dates = [
        date(2024, 7, 15),
        date(2024, 8, 12),
        date(2024, 9, 9),
        date(2024, 10, 14),
        date(2024, 11, 11),
        date(2024, 12, 9),
        date(2025, 1, 13),
        date(2025, 2, 10),
        date(2025, 3, 10),
        date(2025, 4, 14),
        date(2025, 5, 19),
        date(2025, 6, 16),
    ]
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, ex, "10") for ex in ex_dates]
    }
    calendar = payment_calendar(rate_of(holding(BBCA=100), history), rules())
    assert calendar.months == (rp(900),) * 12
    assert calendar.empty_months == 0
    assert calendar.evenness == Decimal("0.08333333")


def test_a_calendar_paying_in_one_month_scores_one() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, date(2025, 4, 21), "10")]
    }
    calendar = payment_calendar(rate_of(holding(BBCA=100), history), rules())
    assert calendar.empty_months == 11
    assert calendar.evenness == Decimal("1.00000000")


def test_a_calendar_with_nothing_to_share_has_no_evenness() -> None:
    silent = payment_calendar(rate_of(holding(TLKM=100), {TLKM: []}), rules())
    assert silent.months == months()
    assert silent.empty_months == 12
    assert silent.evenness is None
    # A Rp1 dividend is a run-rate, but its tax (0.1 up to 1) leaves nothing to take home.
    tiny = rate_of(holding(BBCA=1), {BBCA: [dividend(BBCA, date(2025, 4, 21), "1")]})
    assert tiny.annual_gross == rp(1)
    calendar = payment_calendar(tiny, rules())
    assert calendar.empty_months == 12
    assert calendar.evenness is None
