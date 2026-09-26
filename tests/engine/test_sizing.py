"""CompoundingSizer: target weights to whole lots, rounded towards zero (M3 spec §6.2)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money, Rounding
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView
from steadyhand_idx import IdxMarketRules

DAY = date(2025, 6, 2)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
PRICES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR), TLKM: Money(2_500, IDR)}


@cache
def sizer() -> CompoundingSizer:
    return CompoundingSizer(IdxMarketRules())


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def view(value: int, held: dict[Instrument, int]) -> PortfolioView:
    holdings = {stock: PRICES[stock] * shares for stock, shares in held.items()}
    return PortfolioView(rp(value), rp(0), holdings)


def size(weights: dict[Instrument, str], value: int, held: dict[Instrument, int]) -> list[Order]:
    decimals = {stock: Decimal(weight) for stock, weight in weights.items()}
    return list(sizer().size(decimals, view(value, held), held, PRICES, DAY))


def test_it_is_a_sizer() -> None:
    assert isinstance(sizer(), Sizer)


def test_a_weight_becomes_whole_lots_at_the_last_close_rounded_down() -> None:
    assert size({BBCA: "0.5"}, 10_000_000, {}) == [Order(BBCA, Side.BUY, 500, DAY)]
    assert size({BBCA: "0.54"}, 10_000_000, {}) == [Order(BBCA, Side.BUY, 600, DAY)]
    assert size({BBCA: "0.53999"}, 10_000_000, {}) == [Order(BBCA, Side.BUY, 500, DAY)]


def test_sizes_grow_with_the_portfolio() -> None:
    assert size({BBCA: "0.5"}, 20_000_000, {}) == [Order(BBCA, Side.BUY, 1_100, DAY)]


def test_a_stock_missing_from_the_weights_is_sold() -> None:
    assert size({}, 10_000_000, {BBCA: 200}) == [Order(BBCA, Side.SELL, 200, DAY)]


def test_a_target_within_a_lot_of_the_holding_places_no_order() -> None:
    assert size({BBCA: "0.18"}, 10_000_000, {BBCA: 200}) == []
    assert size({BBCA: "0.26999"}, 10_000_000, {BBCA: 200}) == []
    assert size({BBCA: "0.27"}, 10_000_000, {BBCA: 200}) == [Order(BBCA, Side.BUY, 100, DAY)]
    assert size({BBCA: "0.09"}, 10_000_000, {BBCA: 200}) == [Order(BBCA, Side.SELL, 100, DAY)]


def test_a_sale_is_whole_lots_of_what_is_held() -> None:
    assert size({}, 10_000_000, {BBCA: 150}) == [Order(BBCA, Side.SELL, 100, DAY)]
    assert size({}, 10_000_000, {BBCA: 50}) == []


def test_sells_come_first_then_buys_each_by_symbol() -> None:
    orders = size({TLKM: "0.1", BBCA: "0.2"}, 10_000_000, {BBRI: 500})
    assert [(o.side, o.instrument.symbol) for o in orders] == [
        (Side.SELL, "BBRI"),
        (Side.BUY, "BBCA"),
        (Side.BUY, "TLKM"),
    ]


def test_a_stock_with_no_price_cannot_be_sized() -> None:
    stock = Instrument("GOTO", "IDX", IDR)
    with pytest.raises(LookupError, match=r"^no price for GOTO on 2025-06-02 to size it with$"):
        sizer().size({stock: Decimal("0.1")}, view(10_000_000, {}), {}, PRICES, DAY)


@given(
    value=st.integers(0, 10**10),
    weights=st.lists(st.integers(0, 1_000), min_size=3, max_size=3),
    held=st.lists(st.integers(0, 5_000), min_size=3, max_size=3),
)
def test_orders_are_whole_lots_that_never_overshoot_the_target(
    value: int, weights: list[int], held: list[int]
) -> None:
    stocks = (BBCA, BBRI, TLKM)
    total = sum(weights) or 1
    decimals = {s: Decimal(w) / total / 2 for s, w in zip(stocks, weights, strict=True)}
    shares = {s: h for s, h in zip(stocks, held, strict=True) if h}
    worth = sum(PRICES[s].amount * n for s, n in shares.items())
    portfolio = view(worth + value, shares)
    orders = sizer().size(decimals, portfolio, shares, PRICES, DAY)
    for order in orders:
        stock = order.instrument
        assert order.quantity % 100 == 0
        target = portfolio.value.times(decimals[stock], rounding=Rounding.DOWN).amount
        current = PRICES[stock].amount * shares.get(stock, 0)
        traded = PRICES[stock].amount * order.quantity
        if order.side is Side.BUY:
            assert current + traded <= target
        else:
            assert order.quantity <= shares[stock]
            assert current - traded >= target
