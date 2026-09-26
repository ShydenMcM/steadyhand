"""MarketView and PriceHistory: prices up to the decision day, and nothing later (M3 spec §6.1)."""

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest

from steadyhand._ratio import ratio_down
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import Bar, Instrument, Side
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

D0 = date(2025, 6, 2)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bar(stock: Instrument, day: date, close: int) -> Bar:
    return Bar(stock, day, rp(close), rp(close), rp(close), rp(close), 1_000)


def history() -> PriceHistory:
    days = [D0 + timedelta(days=n) for n in range(4)]
    return PriceHistory(
        [bar(BBCA, day, 9_000 + 25 * n) for n, day in reversed(list(enumerate(days)))]
        + [bar(BBRI, days[1], 4_000), bar(BBRI, days[3], 4_010)]
    )


def nothing_tradable(day: date) -> Tradable:
    return Tradable(day, frozenset(), frozenset(), {})


def view_on(offset: int) -> MarketView:
    today = D0 + timedelta(days=offset)
    return MarketView(history(), today, nothing_tradable(today))


def test_history_sorts_each_stock_by_day_and_answers_for_any_day() -> None:
    prices = history()
    assert prices.instruments == frozenset({BBCA, BBRI})
    assert [b.close.amount for b in prices.between(BBCA, None, D0 + timedelta(days=3))] == [
        9_000,
        9_025,
        9_050,
        9_075,
    ]
    assert [
        b.day.day for b in prices.between(BBCA, D0 + timedelta(days=1), D0 + timedelta(days=2))
    ] == [3, 4]
    assert prices.on(BBRI, D0 + timedelta(days=1)) == bar(BBRI, D0 + timedelta(days=1), 4_000)
    assert prices.on(BBRI, D0 + timedelta(days=2)) is None


def test_before_is_the_last_bar_strictly_earlier() -> None:
    prices = history()
    assert prices.before(BBRI, D0 + timedelta(days=3)) == bar(BBRI, D0 + timedelta(days=1), 4_000)
    assert prices.before(BBRI, D0 + timedelta(days=1)) is None
    assert prices.before(TLKM, D0) is None


def test_an_unknown_stock_has_no_bars() -> None:
    assert history().between(TLKM, None, D0) == ()
    assert history().on(TLKM, D0) is None


def test_history_refuses_two_bars_on_one_day_and_anything_but_bars() -> None:
    with pytest.raises(ValueError, match=r"^two bars for BBCA on 2025-06-02$"):
        PriceHistory([bar(BBCA, D0, 9_000), bar(BBCA, D0, 9_025)])
    with pytest.raises(TypeError, match=r"^bar must be a Bar, got str$"):
        PriceHistory(["BBCA"])  # type: ignore[list-item]


def test_the_view_shows_today_and_earlier() -> None:
    view = view_on(2)
    assert view.today == D0 + timedelta(days=2)
    assert view.bar(BBCA) == bar(BBCA, D0 + timedelta(days=2), 9_050)
    assert view.bar(BBCA, D0) == bar(BBCA, D0, 9_000)
    assert [b.day for b in view.history(BBCA)] == [D0 + timedelta(days=n) for n in range(3)]
    assert [b.day for b in view.history(BBCA, start=D0 + timedelta(days=1))] == [
        D0 + timedelta(days=1),
        D0 + timedelta(days=2),
    ]
    assert view.last_close(BBRI) == rp(4_000)
    assert view.last_close(TLKM) is None


@pytest.mark.parametrize(
    "ask",
    [
        lambda view, later: view.bar(BBCA, later),
        lambda view, later: view.history(BBCA, end=later),
    ],
    ids=["bar", "history"],
)
def test_asking_about_a_later_day_is_look_ahead(ask: Callable[[MarketView, date], object]) -> None:
    view = view_on(2)
    message = r"^asked for 2025-06-05 while deciding on 2025-06-04: a decision may use nothing"
    with pytest.raises(LookAheadError, match=message):
        ask(view, D0 + timedelta(days=3))


def test_the_view_checks_its_arguments() -> None:
    with pytest.raises(TypeError, match=r"^history must be a PriceHistory, got list$"):
        MarketView([], D0, nothing_tradable(D0))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^the tradable set is for 2025-06-03, not 2025-06-02$"):
        MarketView(history(), D0, nothing_tradable(D0 + timedelta(days=1)))
    with pytest.raises(TypeError, match=r"^day must be a date, got str$"):
        view_on(1).bar(BBCA, "2025-06-02")  # type: ignore[arg-type]


def test_tradable_says_why_a_stock_cannot_be_traded() -> None:
    tradable = Tradable(
        D0, frozenset({BBCA}), frozenset({BBCA, BBRI}), {TLKM: "frozen: rights issue"}
    )
    assert tradable.why_not(BBCA, Side.BUY) is None
    assert tradable.why_not(BBRI, Side.SELL) is None
    assert tradable.why_not(BBRI, Side.BUY) == "not in the universe on 2025-06-02"
    assert tradable.why_not(TLKM, Side.BUY) == "frozen: rights issue"
    assert tradable.why_not(TLKM, Side.SELL) == "frozen: rights issue"
    assert tradable.why_not(Instrument("ASII", "IDX", IDR), Side.SELL) == "not held"


def test_a_stock_cannot_be_both_tradable_and_kept_out() -> None:
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be both tradable and kept out$"):
        Tradable(D0, frozenset({BBCA}), frozenset({BBRI}), {BBRI: "no bar", BBCA: "no bar"})
    with pytest.raises(TypeError, match=r"^buyable must be a frozenset, got set$"):
        Tradable(D0, {BBCA}, frozenset(), {})  # type: ignore[arg-type]


def test_a_weight_is_the_share_of_value_rounded_down() -> None:
    portfolio = PortfolioView(rp(3_000_000), rp(1_000_000), {BBCA: rp(1_000_000)})
    assert portfolio.weight(BBCA) == Decimal("0.3333333333333333333333333333")
    assert portfolio.weight(BBRI) == 0
    assert PortfolioView(rp(0), rp(0), {}).weight(BBCA) == 0


def test_the_portfolio_view_must_add_up() -> None:
    with pytest.raises(ValueError, match=r"^spendable cash cannot be negative, got IDR -1$"):
        PortfolioView(rp(0), rp(-1), {})
    with pytest.raises(
        ValueError, match=r"^holdings IDR 2 and spendable IDR 1 exceed the value IDR 2$"
    ):
        PortfolioView(rp(2), rp(1), {BBCA: rp(2)})
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        PortfolioView(rp(5), rp(0), {BBCA: Money(1, Currency("USD", 2))})
    with pytest.raises(TypeError, match=r"^value must be a Money, got int$"):
        PortfolioView(5, rp(0), {})  # type: ignore[arg-type]


def test_ratios_round_down_and_a_zero_whole_is_zero() -> None:
    assert ratio_down(2, 3) == Decimal("0.6666666666666666666666666666")
    assert ratio_down(Decimal("1.5"), 1) == Decimal("1.5")
    assert ratio_down(7, 0) == 0
