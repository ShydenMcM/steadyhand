"""MarketView, PriceHistory and ActionHistory: prices and dividends up to the decision day, and
nothing later (M3 spec §6.1, M6 spec §4.1)."""

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from math import prod

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand._ratio import ratio_down
from steadyhand.market import PayDates, UnsupportedDateError, add_trading_days
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import (
    TRADE_FROZEN,
    TRADE_NO_BAR,
    TRADE_NOT_HELD,
    TRADE_NOT_IN_UNIVERSE,
    Note,
)
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Instrument,
    OtherAction,
    Side,
    Split,
)
from steadyhand.view import (
    ActionHistory,
    LookAheadError,
    MarketView,
    PastDividend,
    PortfolioView,
    PriceHistory,
    Tradable,
)
from steadyhand_idx import IdxMarketRules

RIGHTS = Note(TRADE_FROZEN, "frozen: rights issue")
NO_BAR = Note(TRADE_NO_BAR, "no bar on 2025-06-02")
D0 = date(2025, 6, 2)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def pay_dates(lag: int = 14) -> PayDates:
    return PayDates(rules(), lag)


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
    return Tradable(day, frozenset(), frozenset(), {}, frozenset())


def view_on(offset: int, actions: ActionHistory | None = None) -> MarketView:
    today = D0 + timedelta(days=offset)
    past = ActionHistory() if actions is None else actions
    return MarketView(history(), today, nothing_tradable(today), past, pay_dates())


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
    tradable = nothing_tradable(D0)
    with pytest.raises(TypeError, match=r"^history must be a PriceHistory, got list$"):
        MarketView([], D0, tradable, ActionHistory(), pay_dates())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^the tradable set is for 2025-06-03, not 2025-06-02$"):
        MarketView(
            history(), D0, nothing_tradable(D0 + timedelta(days=1)), ActionHistory(), pay_dates()
        )
    with pytest.raises(TypeError, match=r"^actions must be an ActionHistory, got tuple$"):
        MarketView(history(), D0, tradable, (), pay_dates())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^pay_dates must be a PayDates, got int$"):
        MarketView(history(), D0, tradable, ActionHistory(), 14)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^day must be a date, got str$"):
        view_on(1).bar(BBCA, "2025-06-02")  # type: ignore[arg-type]


def test_tradable_says_why_a_stock_cannot_be_traded() -> None:
    tradable = Tradable(
        D0, frozenset({BBCA}), frozenset({BBCA, BBRI}), {TLKM: RIGHTS}, frozenset({BBCA, TLKM})
    )
    assert tradable.why_not(BBCA, Side.BUY) is None
    assert tradable.why_not(BBRI, Side.SELL) is None
    assert tradable.why_not(BBRI, Side.BUY) == Note(
        TRADE_NOT_IN_UNIVERSE, "not in the universe on 2025-06-02"
    )
    assert tradable.why_not(TLKM, Side.BUY) == RIGHTS
    assert tradable.why_not(TLKM, Side.SELL) == RIGHTS
    assert tradable.why_not(Instrument("ASII", "IDX", IDR), Side.SELL) == Note(
        TRADE_NOT_HELD, "not held"
    )


def test_a_stock_cannot_be_both_tradable_and_kept_out() -> None:
    both = {BBRI: NO_BAR, BBCA: NO_BAR}
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be both tradable and kept out$"):
        Tradable(D0, frozenset({BBCA}), frozenset({BBRI}), both, frozenset({BBCA}))
    with pytest.raises(TypeError, match=r"^buyable must be a frozenset, got set$"):
        Tradable(D0, {BBCA}, frozenset(), {}, frozenset({BBCA}))  # type: ignore[arg-type]


def test_every_buyable_stock_is_a_member_and_a_member_may_be_kept_out() -> None:
    tradable = Tradable(D0, frozenset({BBCA}), frozenset(), {TLKM: RIGHTS}, frozenset({BBCA, TLKM}))
    assert tradable.members == frozenset({BBCA, TLKM})
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be buyable outside the universe$"):
        Tradable(D0, frozenset({BBRI, BBCA, TLKM}), frozenset(), {}, frozenset({TLKM}))
    with pytest.raises(TypeError, match=r"^members must be a frozenset, got set$"):
        Tradable(D0, frozenset(), frozenset(), {}, {TLKM})  # type: ignore[arg-type]


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


def test_the_view_shows_dividends_up_to_today_restated_in_todays_shares() -> None:
    actions = ActionHistory(
        [
            CashDividend(BBCA, D0 + timedelta(days=3), Decimal(170)),
            CashDividend(BBCA, date(2024, 4, 1), Decimal(100)),
            Split(BBCA, date(2024, 10, 1), 1, 5),
            CashDividend(BBCA, date(2024, 11, 1), Decimal(25)),
            OtherAction(BBCA, date(2024, 12, 2), "rights issue"),
        ]
    )
    view = view_on(2, actions)
    assert view.dividends(BBCA) == (
        PastDividend(date(2024, 4, 1), Decimal(20)),
        PastDividend(date(2024, 11, 1), Decimal(25)),
    )
    assert view.dividends(BBRI) == ()


def test_a_dividend_is_restated_by_each_split_from_its_own_ex_date_to_today() -> None:
    before, on, after = date(2021, 3, 1), date(2021, 6, 1), date(2022, 1, 3)
    history = ActionHistory(
        [
            CashDividend(BBCA, before, Decimal(100)),
            # Earned on the shares held before that day's split, as the engine pays it.
            CashDividend(BBCA, on, Decimal(100)),
            Split(BBCA, on, 1, 5),
            Split(BBCA, after, 5, 1),
        ]
    )
    assert history.dividends(BBCA, on - timedelta(days=1)) == (PastDividend(before, Decimal(100)),)
    assert history.dividends(BBCA, on) == (
        PastDividend(before, Decimal(20)),
        PastDividend(on, Decimal(20)),
    )
    assert history.dividends(BBCA, after) == (
        PastDividend(before, Decimal(100)),
        PastDividend(on, Decimal(100)),
    )
    # A 1-for-5 reverse split: five shares become one, so Rp 100 a share becomes Rp 500.
    reverse = ActionHistory([CashDividend(BBRI, before, Decimal(100)), Split(BBRI, on, 5, 1)])
    assert reverse.dividends(BBRI, on) == (PastDividend(before, Decimal(500)),)


def test_a_restatement_divides_once() -> None:
    # Two splits that cancel give the amount back exactly: 10 x 3 / 3, not 10 / 3 x 3.
    history = ActionHistory(
        [
            CashDividend(BBCA, date(2024, 4, 1), Decimal(10)),
            Split(BBCA, date(2024, 5, 2), 1, 3),
            Split(BBCA, date(2024, 6, 3), 3, 1),
        ]
    )
    assert history.dividends(BBCA, D0)[0].per_share == Decimal(10)
    thirds = ActionHistory(
        [CashDividend(BBCA, date(2024, 4, 1), Decimal(100)), Split(BBCA, D0, 1, 3)]
    )
    assert thirds.dividends(BBCA, D0)[0].per_share == Decimal("33.33333333333333333333333333")


def test_the_action_history_refuses_what_is_not_an_action_or_a_stock() -> None:
    with pytest.raises(TypeError, match=r"^action must be a CorporateAction, got str$"):
        ActionHistory(["BBCA"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match=r"^incomplete stock must be an Instrument, got str$"):
        ActionHistory((), ["BBCA"])  # type: ignore[list-item]


def test_a_stock_whose_look_back_was_refused_has_incomplete_history() -> None:
    history = ActionHistory((), [BBRI])
    assert history.incomplete == frozenset({BBRI})
    assert history.complete(BBCA)
    assert not history.complete(BBRI)
    view = view_on(0, history)
    assert view.history_complete(BBCA) is True
    assert view.history_complete(BBRI) is False
    assert ActionHistory().incomplete == frozenset()


def test_the_pay_date_is_the_engines_and_a_later_ex_date_is_look_ahead() -> None:
    view = view_on(2)
    assert view.today == date(2025, 6, 4)
    assert view.pay_date(date(2025, 5, 20)) == date(2025, 6, 13)
    assert view.pay_date(date(2025, 5, 20)) == add_trading_days(rules(), date(2025, 5, 20), 14)
    assert view.pay_date(view.today) == date(2025, 6, 26)
    one_day = MarketView(history(), D0, nothing_tradable(D0), ActionHistory(), pay_dates(1))
    assert one_day.pay_date(date(2025, 5, 20)) == date(2025, 5, 21)
    with pytest.raises(LookAheadError, match=r"^asked for 2025-06-05 while deciding on 2025-06-04"):
        view.pay_date(D0 + timedelta(days=3))


def test_an_ex_date_the_rules_cannot_place_raises_their_own_error() -> None:
    # The IDX holidays start in 2016; 2020's are there, before the rules' verified tables begin.
    assert view_on(0).pay_date(date(2020, 6, 10)) == date(2020, 6, 30)
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2015"):
        view_on(0).pay_date(date(2015, 12, 30))


_STOCKS = st.sampled_from([BBCA, BBRI])
_DAYS = st.dates(min_value=date(2019, 1, 1), max_value=date(2021, 12, 31))
_DIVIDEND = st.builds(CashDividend, _STOCKS, _DAYS, st.integers(1, 10_000).map(Decimal))
_SPLIT = st.builds(
    lambda stock, day, shares: Split(stock, day, *shares),
    _STOCKS,
    _DAYS,
    st.tuples(st.integers(1, 10), st.integers(1, 10)).filter(lambda pair: pair[0] != pair[1]),
)


@given(st.lists(st.one_of(_DIVIDEND, _SPLIT), max_size=12), _DAYS)
def test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits(
    actions: list[CorporateAction], today: date
) -> None:
    history = ActionHistory(actions)
    for stock in (BBCA, BBRI):
        paid = sorted(
            (
                action
                for action in actions
                if isinstance(action, CashDividend)
                and action.instrument == stock
                and action.ex_date <= today
            ),
            key=lambda action: action.ex_date,
        )
        found = history.dividends(stock, today)
        assert all(dividend.ex_date <= today for dividend in found)
        assert [dividend.ex_date for dividend in found] == [dividend.ex_date for dividend in paid]
        for dividend, source in zip(found, paid, strict=True):
            splits = [
                action
                for action in actions
                if isinstance(action, Split)
                and action.instrument == stock
                and source.ex_date <= action.ex_date <= today
            ]
            old = prod(split.old_shares for split in splits)
            new = prod(split.new_shares for split in splits)
            assert dividend.per_share == source.per_share * old / new
