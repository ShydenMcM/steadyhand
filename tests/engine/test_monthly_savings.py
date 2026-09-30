"""monthly-savings: the starting cash in monthly instalments, never selling (M6 spec §5)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand._ratio import ratio_down
from steadyhand.market import PayDates
from steadyhand.money import IDR, Money
from steadyhand.strategies import MonthlySavings, Strategy
from steadyhand.types import Instrument
from steadyhand.view import ActionHistory, MarketView, PortfolioView, PriceHistory, Tradable
from steadyhand_idx import IdxMarketRules

STOCKS = [Instrument(code, "IDX", IDR) for code in ("ASII", "BBCA", "BBRI", "TLKM")]
ASII, BBCA, BBRI, TLKM = STOCKS
JUNE, LATER_IN_JUNE, JULY, AUGUST = (
    date(2025, 6, 2),
    date(2025, 6, 3),
    date(2025, 7, 1),
    date(2025, 8, 1),
)


@cache
def pay_dates() -> PayDates:
    return PayDates(IdxMarketRules(), 14)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def view(day: date, buyable: set[Instrument]) -> MarketView:
    tradable = Tradable(day, frozenset(buyable), frozenset(), {}, frozenset(buyable))
    return MarketView(PriceHistory([]), day, tradable, ActionHistory(), pay_dates())


def portfolio(spendable: int, held: dict[Instrument, int] | None = None) -> PortfolioView:
    holdings = {stock: rp(value) for stock, value in (held or {}).items()}
    return PortfolioView(rp(spendable + sum((held or {}).values())), rp(spendable), holdings)


def test_it_is_a_strategy_named_monthly_savings() -> None:
    strategy: Strategy = MonthlySavings(12)
    assert isinstance(strategy, Strategy)
    assert strategy.name == "monthly-savings"
    assert MonthlySavings(12).instalments == 12
    with pytest.raises(ValueError, match=r"^instalments must be at least 1, got 0$"):
        MonthlySavings(0)


def test_its_first_day_fixes_the_instalment_and_buys_one_split_equally() -> None:
    decision = MonthlySavings(12).decide(view(JUNE, {BBCA, BBRI}), portfolio(12_000_000), {})
    # The instalment is 12,000,000 // 12 = 1,000,000; eleven stay back, so 500,000 a stock.
    each = ratio_down(500_000, 12_000_000)
    assert each == Decimal("0.04166666666666666666666666666")
    assert decision.weights == {BBCA: each, BBRI: each}
    assert decision.memory == {"instalment": "1000000", "due": "11", "month": "2025-06"}
    assert decision.notes == ()


def test_the_instalment_is_whole_and_rounded_down() -> None:
    decision = MonthlySavings(7).decide(view(JUNE, {BBCA}), portfolio(1_000_000), {})
    # 1,000,000 // 7 = 142,857 a month; six of them, 857,142, stay back.
    assert decision.memory["instalment"] == "142857"
    assert decision.weights == {BBCA: ratio_down(1_000_000 - 6 * 142_857, 1_000_000)}


def test_later_days_in_the_month_keep_every_holding_and_buy_nothing() -> None:
    memory = {"instalment": "1000000", "due": "11", "month": "2025-06"}
    held = portfolio(11_300_000, {BBCA: 600_000, ASII: 400_000})
    decision = MonthlySavings(12).decide(view(LATER_IN_JUNE, {BBCA, BBRI}), held, memory)
    assert decision.weights == {BBCA: held.weight(BBCA), ASII: held.weight(ASII)}
    assert decision.memory == memory


def test_the_next_month_buys_its_instalment_with_the_cash_that_arrived_since() -> None:
    memory = {"instalment": "1000000", "due": "11", "month": "2025-06"}
    # 11,000,000 of reserve and 300,000 of dividends: ten instalments stay back, 1,300,000 goes.
    held = portfolio(11_300_000, {BBCA: 1_000_000})
    decision = MonthlySavings(12).decide(view(JULY, {BBCA, BBRI}), held, memory)
    each = ratio_down(650_000, 12_300_000)
    assert decision.weights == {BBCA: held.weight(BBCA) + each, BBRI: each}
    assert decision.memory == {"instalment": "1000000", "due": "10", "month": "2025-07"}


def test_the_last_instalment_spends_everything_and_so_does_every_month_after() -> None:
    last = {"instalment": "1000000", "due": "1", "month": "2025-06"}
    decision = MonthlySavings(12).decide(view(JULY, {BBCA}), portfolio(1_250_000), last)
    assert decision.weights == {BBCA: ratio_down(1_250_000, 1_250_000)}
    assert decision.memory == {"instalment": "1000000", "due": "0", "month": "2025-07"}
    after = MonthlySavings(12).decide(view(AUGUST, {BBCA}), portfolio(80_000), decision.memory)
    assert after.weights == {BBCA: Decimal(1)}
    assert after.memory == {"instalment": "1000000", "due": "0", "month": "2025-08"}


def test_one_instalment_is_a_lump_sum_then_monthly_reinvestment() -> None:
    decision = MonthlySavings(1).decide(view(JUNE, {BBCA, BBRI}), portfolio(9_000_000), {})
    assert decision.weights == {BBCA: Decimal("0.5"), BBRI: Decimal("0.5")}
    assert decision.memory == {"instalment": "9000000", "due": "0", "month": "2025-06"}


def test_a_month_with_nothing_buyable_waits_for_a_day_that_has_something() -> None:
    first = MonthlySavings(12).decide(view(JUNE, set()), portfolio(12_000_000), {})
    assert first.weights == {}
    assert first.memory == {"instalment": "1000000", "due": "12"}
    retry = MonthlySavings(12).decide(
        view(LATER_IN_JUNE, {BBCA}), portfolio(12_000_000), first.memory
    )
    assert retry.weights == {BBCA: ratio_down(1_000_000, 12_000_000)}
    assert retry.memory == {"instalment": "1000000", "due": "11", "month": "2025-06"}


def test_it_never_sells_and_keeps_a_stock_that_left_the_universe() -> None:
    memory = {"instalment": "1000000", "due": "5", "month": "2025-06"}
    held = portfolio(5_000_000, {TLKM: 2_000_000})
    decision = MonthlySavings(12).decide(view(JULY, {BBCA}), held, memory)
    assert decision.weights == {TLKM: held.weight(TLKM), BBCA: ratio_down(1_000_000, 7_000_000)}


def test_a_first_day_on_a_portfolio_that_holds_stocks_sizes_the_instalment_from_cash() -> None:
    held = portfolio(4_000_000, {TLKM: 6_000_000})
    decision = MonthlySavings(4).decide(view(JUNE, {BBCA}), held, {})
    # The portfolio is worth 10,000,000 but only 4,000,000 is cash: 1,000,000 a month.
    assert decision.memory == {"instalment": "1000000", "due": "3", "month": "2025-06"}
    assert decision.weights == {TLKM: held.weight(TLKM), BBCA: ratio_down(1_000_000, 10_000_000)}


@given(
    instalments=st.integers(1, 24),
    start=st.integers(1_000, 10**10),
    months=st.lists(
        st.tuples(st.integers(0, 10**8), st.integers(0, 4), st.integers(1, 3)),
        min_size=1,
        max_size=30,
    ),
)
def test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(
    instalments: int, start: int, months: list[tuple[int, int, int]]
) -> None:
    strategy = MonthlySavings(instalments)
    memory: dict[str, str] = {}
    cash, invested = start, 0
    # Counted here, not read from the strategy's memory: a month buys once, on its first day
    # with something to buy, so the instalments still due are the ones no month has bought yet.
    bought: set[int] = set()
    for number, (arrived, buyable, days) in enumerate(months):
        if buyable:
            bought.add(number)
        for day in range(1, days + 1):
            held = portfolio(cash, {BBCA: invested} if invested else {})
            when = date(2025 + number // 12, number % 12 + 1, day)
            decision = strategy.decide(view(when, set(STOCKS[:buyable])), held, memory)
            memory = dict(decision.memory)
            added = sum(decision.weights.values()) - held.weight(BBCA)
            assert all(decision.weights[stock] >= held.weight(stock) for stock in held.holdings)
            spent = int(added * held.value.amount)
            cash, invested = cash - spent, invested + spent
            due = max(instalments - len(bought), 0)
            assert int(memory["due"]) == due
            assert cash >= due * int(memory["instalment"])
        cash += arrived
