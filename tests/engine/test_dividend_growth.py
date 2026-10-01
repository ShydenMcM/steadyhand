"""dividend-growth: the stocks that paid a dividend every year and grew it, spread across the
months they pay in (M6 spec §6).

Most tests review on 2 January 2025 with ``growth_years`` 2, so a stock passes when it paid in
2022, 2023 and 2024 and its 2024 total is at least its 2022 total. Every pay date below was read
from the calendar (``PayDates(IdxMarketRules(), 14)``), never counted by hand.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand._ratio import ratio_down
from steadyhand.market import PayDates
from steadyhand.money import IDR, Money
from steadyhand.notes import STRATEGY_TOO_FEW_QUALIFIED, Note
from steadyhand.strategies import DividendGrowthStrategy, Strategy
from steadyhand.types import Bar, CashDividend, CorporateAction, Instrument, Split
from steadyhand.view import ActionHistory, MarketView, PortfolioView, PriceHistory, Tradable
from steadyhand_idx import IdxMarketRules

STOCKS = [Instrument(code, "IDX", IDR) for code in ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")]
ASII, BBCA, BBRI, TLKM, UNVR = STOCKS
REVIEW = date(2025, 1, 2)
"""The first trading day of 2025."""

YEARS = (2022, 2023, 2024)
"""Y - growth_years - 1 to Y - 1 for a 2025 review with growth_years 2."""

MARCH, SEPTEMBER, DECEMBER = date(2024, 3, 4), date(2024, 9, 2), date(2024, 12, 2)
"""Ex-dates that pay in their own month: 26 March, 23 September and 20 December 2024."""

LATE_DECEMBER = date(2024, 12, 20)
"""An ex-date that pays in the next year: 15 January 2025."""

EARLY_JANUARY = date(2024, 1, 4)
"""An ex-date that pays on 24 January 2024, and the first day inside the trailing year."""


@cache
def pay_dates() -> PayDates:
    return PayDates(IdxMarketRules(), 14)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def paid(
    stock: Instrument, amounts: tuple[int | str, ...] = (100, 100, 100), on: date = MARCH
) -> list[CashDividend]:
    """One dividend a year in 2022, 2023 and 2024, on *on*'s month and day."""
    return [
        CashDividend(stock, date(year, on.month, on.day), Decimal(amount))
        for year, amount in zip(YEARS, amounts, strict=True)
    ]


def view(
    day: date,
    buyable: set[Instrument],
    actions: Sequence[CorporateAction] | ActionHistory | None = None,
    *,
    members: set[Instrument] | None = None,
    closes: dict[Instrument, int] | None = None,
) -> MarketView:
    universe = frozenset(buyable if members is None else members | buyable)
    tradable = Tradable(day, frozenset(buyable), frozenset(), {}, universe)
    bars = [
        Bar(stock, day, rp(close), rp(close), rp(close), rp(close), 1_000)
        for stock, close in (closes or {}).items()
    ]
    history = actions if isinstance(actions, ActionHistory) else ActionHistory(actions or [])
    return MarketView(PriceHistory(bars), day, tradable, history, pay_dates())


def portfolio(spendable: int, held: dict[Instrument, int] | None = None) -> PortfolioView:
    holdings = {stock: rp(value) for stock, value in (held or {}).items()}
    return PortfolioView(rp(spendable + sum((held or {}).values())), rp(spendable), holdings)


def growth(min_stocks: int = 1, max_stocks: int = 45, growth_years: int = 2) -> Strategy:
    return DividendGrowthStrategy(min_stocks, max_stocks, growth_years)


def test_the_dates_above_pay_where_the_tests_say() -> None:
    of = pay_dates().of
    assert [of(day) for day in (MARCH, SEPTEMBER, DECEMBER)] == [
        date(2024, 3, 26),
        date(2024, 9, 23),
        date(2024, 12, 20),
    ]
    assert of(LATE_DECEMBER) == date(2025, 1, 15)
    assert of(EARLY_JANUARY) == date(2024, 1, 24)
    assert REVIEW - timedelta(days=365) == date(2024, 1, 3)


def test_it_is_a_strategy_named_dividend_growth_with_its_settings() -> None:
    strategy: Strategy = DividendGrowthStrategy(15, 25, 5)
    assert isinstance(strategy, Strategy)
    assert strategy.name == "dividend-growth"
    made = DividendGrowthStrategy(15, 25, 5)
    assert (made.min_stocks, made.max_stocks, made.growth_years) == (15, 25, 5)
    assert DividendGrowthStrategy(3, 3, 1).max_stocks == 3


@pytest.mark.parametrize(
    ("settings", "error", "message"),
    [
        ((0, 25, 5), ValueError, "min_stocks must be at least 1, got 0"),
        ((15, 0, 5), ValueError, "max_stocks must be at least 1, got 0"),
        ((15, 25, 0), ValueError, "growth_years must be at least 1, got 0"),
        ((15, 14, 5), ValueError, "max_stocks must be at least min_stocks (15), got 14"),
        ((True, 25, 5), TypeError, "min_stocks must be an int, got bool"),
    ],
)
def test_its_settings_are_checked_when_it_is_made(
    settings: tuple[int, int, int], error: type[Exception], message: str
) -> None:
    with pytest.raises(error) as caught:
        DividendGrowthStrategy(*settings)
    assert str(caught.value) == message


SPLIT_2024 = Split(BBCA, date(2024, 1, 10), 1, 2)
"""A 1-into-2 split between the 2023 and 2024 dividends: earlier dividends halve."""

TESTED = [
    ("grew", paid(BBCA, (100, 105, 110)), True),
    ("the last total equals the first", paid(BBCA, (100, 90, 100)), True),
    ("the last total is just below the first", paid(BBCA, (100, 120, "99.99")), False),
    ("a year with no dividend", [paid(BBCA)[0], paid(BBCA)[2]], False),
    (
        "the first year missing, a year before it paid",
        [CashDividend(BBCA, date(2021, 3, 4), Decimal(100)), *paid(BBCA)[1:]],
        False,
    ),
    (
        "the last year missing, today's year paid",
        [*paid(BBCA)[:2], CashDividend(BBCA, REVIEW, Decimal(200))],
        False,
    ),
    (
        "several dividends in a year are added up",
        [*paid(BBCA, (100, 100, 40)), CashDividend(BBCA, SEPTEMBER, Decimal(60))],
        True,
    ),
    (
        "several dividends in a year still fall short",
        [*paid(BBCA, (100, 100, 40)), CashDividend(BBCA, SEPTEMBER, Decimal("59.99"))],
        False,
    ),
    ("restated by a later split: 50, 50, 50", [*paid(BBCA, (100, 100, 50)), SPLIT_2024], True),
    ("restated by a later split: 50, 50, 49", [*paid(BBCA, (100, 100, 49)), SPLIT_2024], False),
    (
        "a larger dividend before the window does not count",
        [CashDividend(BBCA, date(2021, 3, 4), Decimal(500)), *paid(BBCA)],
        True,
    ),
    ("no dividend at all", [], False),
]


@pytest.mark.parametrize(
    ("actions", "passes"), [(a, p) for _, a, p in TESTED], ids=[name for name, _, _ in TESTED]
)
def test_the_dividend_test_at_its_boundaries(
    actions: list[CorporateAction], *, passes: bool
) -> None:
    strategy = DividendGrowthStrategy(1, 45, 2)
    assert strategy.passes(view(REVIEW, {BBCA}, actions), BBCA) is passes


def test_a_stock_with_an_incomplete_history_or_outside_the_universe_fails() -> None:
    strategy = DividendGrowthStrategy(1, 45, 2)
    actions: list[CorporateAction] = [*paid(BBCA), *paid(TLKM)]
    assert strategy.passes(view(REVIEW, {BBCA, TLKM}, actions), BBCA) is True
    refused = ActionHistory(actions, {BBCA})
    assert strategy.passes(view(REVIEW, {BBCA, TLKM}, refused), BBCA) is False
    # TLKM holds its record but has left the universe: it is neither buyable nor a member.
    assert strategy.passes(view(REVIEW, {BBCA}, actions), TLKM) is False


def test_growth_years_sets_how_many_years_must_have_paid() -> None:
    two_years = paid(BBCA)[1:]
    assert DividendGrowthStrategy(1, 45, 1).passes(view(REVIEW, {BBCA}, two_years), BBCA)
    assert not DividendGrowthStrategy(1, 45, 2).passes(view(REVIEW, {BBCA}, two_years), BBCA)


def test_with_at_most_max_stocks_passing_it_holds_them_all_in_equal_parts() -> None:
    actions = [*paid(ASII), *paid(BBCA), *paid(BBRI), *paid(TLKM, (100, 100, 99))]
    decision = growth(min_stocks=2, max_stocks=3).decide(
        view(REVIEW, {ASII, BBCA, BBRI, TLKM}, actions), portfolio(9_000_000), {}
    )
    third = ratio_down(1, 3)
    assert third == Decimal("0.3333333333333333333333333333")
    assert decision.weights == {ASII: third, BBCA: third, BBRI: third}
    assert decision.memory == {"set": "IDX:ASII IDX:BBCA IDX:BBRI", "year": "2025"}
    assert decision.notes == ()


def test_exactly_min_stocks_passing_holds_them_in_equal_parts_with_no_note() -> None:
    decision = growth(min_stocks=2, max_stocks=3).decide(
        view(REVIEW, {ASII, BBCA}, [*paid(ASII), *paid(BBCA)]), portfolio(9_000_000), {}
    )
    assert decision.weights == {ASII: Decimal("0.5"), BBCA: Decimal("0.5")}
    assert decision.notes == ()


@pytest.mark.parametrize(
    ("passers", "text"),
    [
        (
            [],
            "No stock passed the dividend test; everything is held as cash until one does.",
        ),
        (
            [ASII],
            "Only 1 stock passed the dividend test; the rest is held as cash until more do.",
        ),
        (
            [ASII, BBCA, BBRI],
            "Only 3 stocks passed the dividend test; the rest is held as cash until more do.",
        ),
    ],
)
def test_fewer_than_min_stocks_passing_leaves_the_rest_in_cash_and_says_so(
    passers: list[Instrument], text: str
) -> None:
    actions = [dividend for stock in passers for dividend in paid(stock)]
    decision = growth(min_stocks=4, max_stocks=5).decide(
        view(REVIEW, set(STOCKS), actions), portfolio(8_000_000), {}
    )
    # Each passer takes a quarter, 1 / min_stocks, and the rest stays in cash.
    assert decision.weights == dict.fromkeys(passers, Decimal("0.25"))
    assert decision.notes == (Note(STRATEGY_TOO_FEW_QUALIFIED, text),)
    assert decision.memory["year"] == "2025"


def test_a_review_sells_what_failed_or_left_and_keeps_a_suspended_passer() -> None:
    actions = [*paid(ASII), *paid(BBRI), *paid(TLKM), *paid(UNVR), *paid(BBCA, (100, 100, 1))]
    held = {ASII: 1_000_000, BBCA: 1_000_000, TLKM: 1_000_000}
    today = view(
        REVIEW,
        {BBCA, BBRI},
        actions,
        # ASII (held) and UNVR (not held) pass but are suspended; TLKM passes but left.
        members={ASII, BBCA, BBRI, UNVR},
    )
    decision = growth(min_stocks=1, max_stocks=5).decide(today, portfolio(1_000_000, held), {})
    # Candidates: BBRI (buyable) and ASII (held). BBCA failed and TLKM left, so both go to 0;
    # UNVR can neither be bought nor is held.
    assert decision.weights == {ASII: Decimal("0.5"), BBRI: Decimal("0.5")}
    assert decision.memory["set"] == "IDX:ASII IDX:BBRI"


def test_with_more_passers_than_max_stocks_it_spreads_pay_months_before_yield() -> None:
    actions = [
        *paid(ASII, (100, 100, 100), MARCH),
        *paid(BBCA, (120, 120, 120), MARCH),
        *paid(TLKM, (20, 20, 20), SEPTEMBER),
    ]
    closes = dict.fromkeys((ASII, BBCA, TLKM), 2_000)
    decision = growth(max_stocks=2).decide(
        view(REVIEW, {ASII, BBCA, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: BBCA 6%, ASII 5%, TLKM 1%. First pick, no month is crowded: BBCA. Second: ASII
    # would share March with BBCA, TLKM pays alone in September, so TLKM despite its yield.
    assert decision.weights == {BBCA: Decimal("0.5"), TLKM: Decimal("0.5")}


def test_a_stock_paying_in_two_months_is_as_crowded_as_its_least_crowded_month() -> None:
    actions = [
        *paid(BBCA, (60, 60, 60), MARCH),
        *paid(BBCA, (60, 60, 60), SEPTEMBER),
        *paid(ASII, (100, 100, 100), MARCH),
        *paid(TLKM, (40, 40, 40), MARCH),
        *paid(TLKM, (40, 40, 40), DECEMBER),
    ]
    closes = dict.fromkeys((ASII, BBCA, TLKM), 1_000)
    decision = growth(max_stocks=2).decide(
        view(REVIEW, {ASII, BBCA, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: BBCA 12%, ASII 10%, TLKM 8%. BBCA first, crowding March and September. ASII's one
    # month, March, has 1 picked; TLKM's least crowded, December, has 0: TLKM.
    assert decision.weights == {BBCA: Decimal("0.5"), TLKM: Decimal("0.5")}


def test_the_pay_months_are_last_years_modelled_pay_dates() -> None:
    actions = [
        # BBCA's ex-dates are in December; they pay in January.
        *paid(BBCA, (300, 300, 300), LATE_DECEMBER),
        *paid(ASII, (200, 200, 200), EARLY_JANUARY),
        *paid(TLKM, (100, 100, 100), DECEMBER),
        # BBRI paid in September before last year; last year it paid in January.
        *paid(BBRI, (250, 250, 250), SEPTEMBER)[:2],
        CashDividend(BBRI, EARLY_JANUARY, Decimal(250)),
    ]
    closes = dict.fromkeys((ASII, BBCA, BBRI, TLKM), 10_000)
    decision = growth(max_stocks=2).decide(
        view(REVIEW, {ASII, BBCA, BBRI, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: BBCA 3%, BBRI 2.5%, ASII 2%, TLKM 1%. BBCA pays in January. ASII and BBRI pay in
    # January too (BBRI's September is not last year's), and TLKM in December: TLKM.
    assert decision.weights == {BBCA: Decimal("0.5"), TLKM: Decimal("0.5")}


def test_the_trailing_yield_is_the_last_365_days_of_dividends_over_the_last_close() -> None:
    actions = [
        # ASII's 2024 dividend is on 3 January, exactly 365 days back, so outside the window.
        *paid(ASII, (100, 100, 900), date(2024, 1, 3)),
        *paid(BBCA, (100, 100, 100), EARLY_JANUARY),
        *paid(BBRI, (150, 150, 150), EARLY_JANUARY),
        # TLKM's dividends are the largest, but it has no close to divide by.
        *paid(TLKM, (999, 999, 999), EARLY_JANUARY),
    ]
    closes = {ASII: 1_000, BBCA: 1_000, BBRI: 2_000}
    decision = growth(max_stocks=1).decide(
        view(REVIEW, {ASII, BBCA, BBRI, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: ASII 0, BBCA 10%, BBRI 7.5%, TLKM 0.
    assert decision.weights == {BBCA: Decimal(1)}


def test_equal_coverage_and_yield_go_to_market_then_symbol() -> None:
    other = Instrument("AALI", "JKT", IDR)
    stocks = [TLKM, BBCA, ASII, other]
    actions = [dividend for stock in stocks for dividend in paid(stock)]
    decision = growth(max_stocks=2).decide(
        view(REVIEW, set(stocks), actions), portfolio(1_000_000), {}
    )
    # No closes, so every yield is 0 and every month is March. IDX sorts before JKT.
    assert decision.weights == {ASII: Decimal("0.5"), BBCA: Decimal("0.5")}


HOLDING = {ASII: 400, BBCA: 490, TLKM: 50}
"""Picked ASII and BBCA, and TLKM held from before: a 1,000 portfolio with 60 to spend."""


def between(
    buyable: set[Instrument], chosen: str = "IDX:ASII IDX:BBCA", min_stocks: int = 2
) -> dict[Instrument, Decimal]:
    memory = {"set": chosen, "year": "2025"}
    decision = growth(min_stocks=min_stocks, max_stocks=5).decide(
        view(date(2025, 3, 3), buyable), portfolio(60, HOLDING), memory
    )
    assert decision.memory == memory
    assert decision.notes == ()
    return dict(decision.weights)


def test_between_reviews_it_keeps_every_holding_and_tops_up_its_picks_to_their_target() -> None:
    # 60 // 2 = 30 each, 3%. ASII 40% -> 43%. BBCA 49% takes only 1%, up to its target of 50%.
    assert between({ASII, BBCA, TLKM}) == {
        ASII: Decimal("0.43"),
        BBCA: Decimal("0.5"),
        TLKM: Decimal("0.05"),
    }


def test_between_reviews_a_pick_it_cannot_buy_today_gets_nothing() -> None:
    # BBCA alone may be bought: 6% offered, 1% taken.
    assert between({BBCA, TLKM}) == {
        ASII: Decimal("0.4"),
        BBCA: Decimal("0.5"),
        TLKM: Decimal("0.05"),
    }
    assert between(set()) == {ASII: Decimal("0.4"), BBCA: Decimal("0.49"), TLKM: Decimal("0.05")}


def test_between_reviews_the_target_is_one_over_min_stocks_when_fewer_were_picked() -> None:
    # One pick, min_stocks 4: ASII may reach 25%, which is below the 40% it holds.
    assert between({ASII}, "IDX:ASII", min_stocks=4)[ASII] == Decimal("0.4")
    # UNVR, picked but not held, is offered all 60 (6%) and takes it, under its 25% target.
    assert between({UNVR}, "IDX:UNVR", min_stocks=4)[UNVR] == Decimal("0.06")


def test_it_reviews_on_its_first_day_and_its_first_day_in_each_year_only() -> None:
    strategy = growth(min_stocks=1, max_stocks=5)
    actions = [*paid(ASII), CashDividend(ASII, date(2025, 3, 4), Decimal(100)), *paid(BBCA)]
    held = portfolio(0, {ASII: 500, TLKM: 500})

    def decide(day: date, memory: dict[str, str]) -> dict[Instrument, Decimal]:
        decision = strategy.decide(view(day, {ASII, BBCA, TLKM}, actions), held, memory)
        return dict(decision.weights)

    # A first day in June reviews: TLKM fails, so it goes; ASII and BBCA pass.
    assert decide(date(2025, 6, 10), {}) == {ASII: Decimal("0.5"), BBCA: Decimal("0.5")}
    # Later that year it only keeps what it holds.
    kept = {"set": "IDX:ASII IDX:BBCA", "year": "2025"}
    # BBCA, picked but not held, is offered the spendable cash: none, so a weight of 0.
    assert decide(date(2025, 12, 30), kept) == {
        ASII: Decimal("0.5"),
        BBCA: Decimal(0),
        TLKM: Decimal("0.5"),
    }
    # The first day of 2026 reviews again: ASII paid in 2023 to 2025, BBCA stopped in 2024.
    assert decide(date(2026, 1, 2), kept) == {ASII: Decimal(1)}


@given(
    st.lists(
        st.dates(min_value=date(2025, 1, 1), max_value=date(2027, 12, 31)),
        min_size=1,
        max_size=12,
        unique=True,
    ).map(sorted)
)
def test_it_reviews_on_no_day_but_the_first_and_each_new_years_first(days: list[date]) -> None:
    """A review sells TLKM, which never passes; any other day keeps it."""
    strategy = growth()
    actions: list[CorporateAction] = [
        CashDividend(ASII, date(year, 3, 4), Decimal(100)) for year in range(2020, 2028)
    ]
    held = portfolio(0, {ASII: 500, TLKM: 500})
    memory: dict[str, str] = {}
    last_year = None
    for day in days:
        decision = strategy.decide(view(day, {ASII, TLKM}, actions), held, memory)
        reviewed = TLKM not in decision.weights
        assert reviewed is (day.year != last_year)
        memory, last_year = dict(decision.memory), day.year
