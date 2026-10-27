"""monthly-savings: the starting cash in monthly instalments, never selling (M6 spec §5)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

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


def check_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(
    instalments: int, start: int, months: list[tuple[int, int, int]]
) -> tuple[int, int, dict[str, str]]:
    """The monthly savings property's check on any journey, called by its unit stand-ins below
    and by tests/properties/test_engine_monthly_savings.py on every draw: each day the strategy
    lowers no holding's weight, its count of instalments due is the months not yet bought, and
    the cash sorts at or above their reserve (#365: equalities, no typed-in bound). Returns the
    cash, the amount invested and the strategy's memory at the end."""
    strategy = MonthlySavings(instalments)
    memory: dict[str, str] = {}
    cash, invested = start, 0
    # Counted here, not read from the strategy's memory: a month buys once, on its first day
    # with something to buy, so the instalments still due are the ones no month has bought yet.
    bought: set[int] = set()
    for number, (arrived, buyable, days) in enumerate(  # runtime population: a drawn journey
        months
    ):
        if buyable:
            bought.add(number)
        for day in range(1, days + 1):  # runtime population: the drawn days of this month
            held = portfolio(cash, {BBCA: invested} if invested else {})
            when = date(2025 + number // 12, number % 12 + 1, day)
            decision = strategy.decide(view(when, set(STOCKS[:buyable])), held, memory)
            memory = dict(decision.memory)
            added = sum(decision.weights.values()) - held.weight(BBCA)
            before_after = {s: [held.weight(s), decision.weights[s]] for s in held.holdings}
            assert {s: sorted(pair) for s, pair in before_after.items()} == before_after
            spent = int(added * held.value.amount)
            cash, invested = cash - spent, invested + spent
            due = max(instalments - len(bought), 0)
            assert int(memory["due"]) == due
            reserve = due * int(memory["instalment"])
            assert sorted([cash, reserve]) == [reserve, cash]
        cash += arrived
    return cash, invested, memory


ONE_INSTALMENT = (1, 1_000, [(0, 0, 1)])
THE_MOST = (24, 10**10, [(10**8, 4, 3)] * 30)
GAPS = (3, 50_000, [(0, 1, 2), (10_000, 0, 1), (0, 4, 3), (5, 2, 1), (0, 1, 1)])


# Unit stand-in of the property in tests/properties/test_engine_monthly_savings.py (#290):
# one instalment with nothing to buy; the most instalments, cash and months
# drawn; and months with nothing to buy between those that buy. Worked by hand: buying only
# moves cash into the holding, so cash and holding together are the start plus what arrived;
# the instalment is the start over the instalments, rounded down (10bn / 24 is 416,666,666,
# 50,000 / 3 is 16,666); the memory names the last month that bought, number 29 of the 30
# being June 2027, and no instalment is due once every one is bought.
@pytest.mark.parametrize(
    ("journey", "total", "memory"),
    [
        (ONE_INSTALMENT, 1_000, {"instalment": "1000", "due": "1"}),
        (
            THE_MOST,
            10**10 + 30 * 10**8,
            {"instalment": "416666666", "due": "0", "month": "2027-06"},
        ),
        (GAPS, 60_005, {"instalment": "16666", "due": "0", "month": "2025-05"}),
    ],
    ids=["one-instalment", "the-most", "gaps"],
)
def test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(
    journey: tuple[int, int, list[tuple[int, int, int]]], total: int, memory: dict[str, str]
) -> None:
    cash, invested, found = (
        check_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(*journey)
    )
    assert (cash + invested, found) == (total, memory)


# The two journeys whose every spend can be worked by hand. The most-drawn one cannot: its value
# changes every month, so each spend passes through 28-digit weights that do not terminate.
# One instalment buys nothing. In the gaps, the first month spends 16,668, what 33,332 of
# reserve leaves; the third month spends 4 x 6,666 of the 26,666 above one reserved
# instalment; the fourth spends 2 x 8,334, all the cash, as nothing is due after it; the fifth
# spends the Rp5 that arrived, whose weight of 5/60,005 and the holding's 60,000/60,005, each
# rounded down at 28 digits, sum back to 1 and leave the spend at exactly Rp5.
@pytest.mark.parametrize(
    ("journey", "cash", "invested"),
    [(ONE_INSTALMENT, 1_000, 0), (GAPS, 0, 60_005)],
    ids=["one-instalment", "gaps"],
)
def test_a_journey_s_cash_and_holding_are_worked_by_hand(
    journey: tuple[int, int, list[tuple[int, int, int]]], cash: int, invested: int
) -> None:
    found = check_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(
        *journey
    )
    assert found[:2] == (cash, invested)
