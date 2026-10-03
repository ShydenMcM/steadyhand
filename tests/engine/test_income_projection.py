"""dividend_growth and project: measured growth and the three-scenario projection (M4 §5.2, §5.3).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah. Growth is measured on Monday 7 July 2025: its year
window starts on 8 July 2024, and the window four years earlier runs from 8 July 2020 to
7 July 2021.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from steadyhand.income import (
    PROJECTION_LABEL,
    DividendGrowth,
    HoldingGrowth,
    IncomeGoal,
    IncomeSettings,
    Projection,
    ProjectionOutcome,
    RunRate,
    Scenario,
    ScenarioProjection,
    dividend_growth,
    project,
    run_rate,
    years_before,
)
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.portfolio import Portfolio
from steadyhand.types import (
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    Order,
    Side,
    Split,
)
from steadyhand_idx import IdxMarketRules

ASII = Instrument("ASII", "IDX", IDR)
BBCA = Instrument("BBCA", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
UNVR = Instrument("UNVR", "IDX", IDR)
USD = Currency("USD", 2)
AS_OF = date(2025, 7, 7)
BOUGHT = date(2020, 1, 2)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


class _TaxFree(IdxMarketRules):
    """IDX, but in a market that taxes no dividend, so a projection's arithmetic stays exact."""

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return Money.zero(gross.currency)


@cache
def tax_free() -> _TaxFree:
    return _TaxFree()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(**shares: int) -> Portfolio:
    book = Portfolio.empty(IDR)
    for symbol, quantity in shares.items():
        order = Order(Instrument(symbol, "IDX", IDR), Side.BUY, quantity, BOUGHT)
        fill = Fill(order, BOUGHT, quantity, rp(1), Costs.zero(IDR))
        book = book.deposit(rp(quantity), BOUGHT).apply_fill(fill, BOUGHT)
    return book


def dividend(stock: Instrument, ex_date: date, per_share: str) -> CashDividend:
    return CashDividend(stock, ex_date, Decimal(per_share))


def growth_of(
    portfolio: Portfolio, history: dict[Instrument, Sequence[CorporateAction]]
) -> DividendGrowth:
    return dividend_growth(run_rate(portfolio, history, rules(), AS_OF, 3), history)


def rate(gross: int) -> RunRate:
    return RunRate(AS_OF, (), rp(gross), rp(0))


def measured(growth: str) -> DividendGrowth:
    return DividendGrowth((), Decimal(growth), ())


def goal(target: int, contribution: int | None = None) -> IncomeSettings:
    added = None if contribution is None else rp(contribution)
    return IncomeSettings(IncomeGoal(rp(target)), added)


def years(projection: Projection) -> dict[Scenario, Decimal | None]:
    return {found.scenario: found.years for found in projection.scenarios}


def test_years_before_keeps_the_month_and_day() -> None:
    assert years_before(AS_OF, 4) == date(2021, 7, 7)
    assert years_before(date(2024, 2, 29), 4) == date(2020, 2, 29)
    assert years_before(date(2024, 2, 29), 1) == date(2023, 2, 28)


def test_growth_is_the_yearly_rate_between_year_windows_four_years_apart() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        # Earlier 200 a share, 100 on today's basis after the 1-for-2 split; recent
        # 46.41 + 100 = 146.41. 146.41 / 100 = 1.4641 = 1.1 ** 4: 10% a year. The 2023 dividend
        # is in neither window.
        BBCA: [
            dividend(BBCA, date(2020, 11, 16), "200"),
            Split(BBCA, date(2022, 6, 1), 1, 2),
            dividend(BBCA, date(2023, 5, 2), "999"),
            dividend(BBCA, date(2024, 11, 18), "46.41"),
            dividend(BBCA, date(2025, 4, 21), "100"),
        ],
        # 81 / 100 = 0.81, whose fourth root is 0.9486832980...: -5.131670...% a year.
        TLKM: [dividend(TLKM, date(2021, 4, 19), "100"), dividend(TLKM, date(2025, 4, 21), "81")],
        # Nothing four years ago: taken as 0%, with a note.
        UNVR: [dividend(UNVR, date(2025, 4, 21), "10")],
        # Nothing in the last year: no run-rate, so no weight and no entry.
        ASII: [dividend(ASII, date(2021, 4, 19), "50")],
    }
    growth = growth_of(holding(ASII=100, BBCA=100, TLKM=100, UNVR=100), history)
    assert growth.holdings == (
        HoldingGrowth(BBCA, Decimal("146.41"), Decimal(100), Decimal("0.10000000")),
        HoldingGrowth(TLKM, Decimal(81), Decimal(100), Decimal("-0.05131670")),
        HoldingGrowth(UNVR, Decimal(10), Decimal(0), Decimal(0)),
    )
    # Weighted by run-rate gross (14,641, 8,100 and 1,000 of 23,741):
    # (0.1 x 14,641 - 0.0513167 x 8,100 + 0 x 1,000) / 23,741 = 1,048.43473 / 23,741.
    assert growth.portfolio == Decimal("0.04416136")
    assert growth.notes == (
        Note(
            INCOME_GROWTH_SHORT_HISTORY,
            "UNVR: no dividend was found in the year ending 2021-07-07, so its dividend "
            "growth is taken as 0%",
        ),
    )


def test_the_earlier_window_holds_both_of_its_ends_and_nothing_outside_them() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [
            dividend(BBCA, date(2020, 7, 7), "1000"),
            dividend(BBCA, date(2020, 7, 8), "4"),
            dividend(BBCA, date(2021, 7, 7), "6"),
            dividend(BBCA, date(2021, 7, 8), "500"),
            dividend(BBCA, date(2025, 4, 21), "10"),
        ]
    }
    growth = growth_of(holding(BBCA=100), history)
    assert growth.holdings == (HoldingGrowth(BBCA, Decimal(10), Decimal(10), Decimal(0)),)


def test_a_portfolio_with_nothing_paying_has_no_growth() -> None:
    growth = growth_of(holding(TLKM=100), {TLKM: []})
    assert growth == DividendGrowth((), Decimal(0), ())


def test_an_income_goal_is_a_positive_amount_of_money() -> None:
    with pytest.raises(ValueError, match=r"^an income goal must be positive, got IDR 0$"):
        IncomeGoal(rp(0))
    with pytest.raises(TypeError, match=r"^monthly_target must be a Money, got int$"):
        IncomeGoal(5_000)  # type: ignore[arg-type]


def test_income_settings_default_to_no_contribution_and_the_engines_pay_lag() -> None:
    plain = IncomeSettings(IncomeGoal(rp(5_000)))
    assert plain.monthly_contribution is None
    assert plain.pay_lag_trading_days == 14


def test_income_settings_check_their_parts() -> None:
    target = IncomeGoal(rp(5_000))
    with pytest.raises(TypeError, match=r"^goal must be an IncomeGoal, got Money$"):
        IncomeSettings(rp(5_000))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^monthly_contribution must be a Money, got int$"):
        IncomeSettings(target, 1_000)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^a monthly contribution must be positive, got IDR 0$"):
        IncomeSettings(target, rp(0))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        IncomeSettings(target, Money(100, USD))
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        IncomeSettings(target, pay_lag_trading_days=0)


def test_a_goal_already_met_takes_no_time() -> None:
    # (120,000 - 12,000) / 12 = 9,000: met before the first month.
    projection = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_000), rules())
    assert years(projection)[Scenario.BASE] == Decimal("0.0")
    assert years(projection)[Scenario.OPTIMISTIC] == Decimal("0.0")


def test_a_short_run_simulated_by_hand() -> None:
    # Income 120,000 on a value of 1,200,000: a 10% yield, which reinvesting keeps.
    # Month 1: 10,000 a month less 1,000 tax reinvests 9,000, adding 9,000 x 10% = 900:
    #   income 120,900, whose take-home (120,900 - 12,090) / 12 = 9,067 misses 9,070.
    # Month 2: 10,075 a month less 1,008 (1,007.5 up) reinvests 9,067, adding 906.7 down to
    #   906: income 121,806, take-home (121,806 - 12,181) / 12 = 9,135. Met: 2 months, 0.2 years.
    # Reinvesting the tax too would add 1,000 in month 1, reach 9,075 and meet it a month early.
    projection = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_070), rules())
    assert years(projection)[Scenario.BASE] == Decimal("0.2")
    assert years(projection)[Scenario.OPTIMISTIC] == Decimal("0.2")


def test_the_contribution_is_reinvested_each_month() -> None:
    # Month 1 with 1,000 added: 9,000 + 1,000 reinvested adds 1,000, income 121,000, take-home
    # (121,000 - 12,100) / 12 = 9,075: met at once. Without it, month 1 gives 9,067 and
    # month 2 gives 9,135 (the test above).
    added = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_075, 1_000), rules())
    plain = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_075), rules())
    assert years(added)[Scenario.BASE] == Decimal("0.1")
    assert years(plain)[Scenario.BASE] == Decimal("0.2")


def test_dividends_grow_at_month_twelve_before_the_target_is_checked() -> None:
    # No tax, and a value so large that reinvesting adds nothing: income stays 240 (20 a
    # month) until month 12 grows it 5% to 252 (21 a month), which meets 21 in month 12.
    projection = project(rate(240), measured("0.05"), rp(10**12), goal(21), tax_free())
    assert years(projection)[Scenario.BASE] == Decimal("1.0")


def test_the_last_month_is_the_six_hundredth() -> None:
    # No tax, reinvesting adds nothing, and 5% growth multiplies income by 21/20 each year:
    # after k years 12 x 20**50 becomes 12 x 21**k x 20**(50 - k), exactly, which is
    # 21**k x 20**(50 - k) a month. That reaches 21**50 in month 600 and never 21**50 + 1.
    start, value = 12 * 20**50, rp(10**140)
    met = project(rate(start), measured("0.05"), value, goal(21**50), tax_free())
    missed = project(rate(start), measured("0.05"), value, goal(21**50 + 1), tax_free())
    assert years(met)[Scenario.BASE] == Decimal("50.0")
    base = missed.scenarios[1]
    assert (base.scenario, base.outcome, base.years) == (
        Scenario.BASE,
        ProjectionOutcome.NOT_WITHIN,
        None,
    )


@pytest.mark.parametrize(
    ("gross", "value"),
    [
        pytest.param(0, 1_200_000, id="silent"),
        # With no holdings' value, even a goal the income already meets cannot be projected.
        pytest.param(120_000, 0, id="unvalued"),
    ],
)
def test_nothing_to_project_from_cannot_be_projected(gross: int, value: int) -> None:
    projection = project(rate(gross), measured("0"), rp(value), goal(1), rules())
    assert [(s.outcome, s.years) for s in projection.scenarios] == [
        (ProjectionOutcome.CANNOT, None)
    ] * 3


@pytest.mark.parametrize(
    ("growth", "pessimistic", "base", "optimistic"),
    [
        ("-0.03", "-0.03", "-0.03", "-0.03"),
        ("0.07", "0", "0.05", "0.07"),
        ("0.12", "0", "0.05", "0.10"),
    ],
)
def test_each_scenario_starts_and_grows_as_the_spec_says(
    growth: str, pessimistic: str, base: str, optimistic: str
) -> None:
    projection = project(rate(1_001), measured(growth), rp(10_000), goal(1), rules())
    # The pessimistic start is 80% of 1,001 = 800.8, rounded down.
    assert [(s.scenario, s.starting_gross, s.growth) for s in projection.scenarios] == [
        (Scenario.PESSIMISTIC, rp(800), Decimal(pessimistic)),
        (Scenario.BASE, rp(1_001), Decimal(base)),
        (Scenario.OPTIMISTIC, rp(1_001), Decimal(optimistic)),
    ]


def test_a_projection_carries_its_label_the_goal_and_the_costs_note() -> None:
    projection = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_000, 500), rules())
    assert projection.label == PROJECTION_LABEL == "Projection, not a promise"
    assert (projection.target, projection.contribution) == (rp(9_000), rp(500))
    assert [note.key for note in projection.notes] == [INCOME_PROJECTION_COSTS_IGNORED]
    assert projection.scenarios[1] == ScenarioProjection(
        Scenario.BASE, rp(120_000), Decimal(0), ProjectionOutcome.REACHED, Decimal("0.0")
    )


def test_a_goal_in_another_currency_is_refused() -> None:
    dollars = IncomeSettings(IncomeGoal(Money(100, USD)))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        project(rate(120_000), measured("0"), rp(1_200_000), dollars, rules())


def rank(scenario: ScenarioProjection) -> Decimal:
    """Years, with ``NOT_WITHIN`` after every number."""
    return Decimal("Infinity") if scenario.years is None else scenario.years


grosses = st.integers(min_value=12, max_value=10**9)
values = st.integers(min_value=1, max_value=10**11)
targets = st.integers(min_value=1, max_value=10**7)
rates = st.decimals(min_value=Decimal("-0.2"), max_value=Decimal("0.2"), places=4, allow_nan=False)
added = st.integers(min_value=0, max_value=10**6)

# Each example simulates up to three times 600 months, so these run fewer examples than the
# profile's default.


@settings(max_examples=100)
@given(values, targets, added)
def test_a_zero_run_rate_cannot_be_projected(value: int, target: int, contribution: int) -> None:
    projection = project(
        rate(0), measured("0"), rp(value), goal(target, contribution or None), rules()
    )
    assert {s.outcome for s in projection.scenarios} == {ProjectionOutcome.CANNOT}


@settings(max_examples=100)
@given(grosses, values, targets, rates, added, added)
# Found by hypothesis (#97): rounding the income down every month made Rp6 a month take 1.7 years
# where Rp5 took 1.6.
@example(gross=12, value=14, target=6, growth=Decimal(0), smaller=5, extra=1)
def test_a_larger_contribution_never_takes_longer(
    gross: int, value: int, target: int, growth: Decimal, smaller: int, extra: int
) -> None:
    less = project(
        rate(gross), measured(str(growth)), rp(value), goal(target, smaller or None), rules()
    )
    more = project(
        rate(gross),
        measured(str(growth)),
        rp(value),
        goal(target, smaller + extra or None),
        rules(),
    )
    for fewer, larger in zip(  # runtime population: the scenarios of two drawn projections
        less.scenarios, more.scenarios, strict=True
    ):
        assert rank(larger) <= rank(fewer)


@settings(max_examples=100)
@given(grosses, values, targets, rates, added)
def test_pessimistic_never_beats_base_and_base_never_beats_optimistic(
    gross: int, value: int, target: int, growth: Decimal, contribution: int
) -> None:
    projection = project(
        rate(gross), measured(str(growth)), rp(value), goal(target, contribution or None), rules()
    )
    pessimistic, base, optimistic = (rank(s) for s in projection.scenarios)
    assert pessimistic >= base >= optimistic
