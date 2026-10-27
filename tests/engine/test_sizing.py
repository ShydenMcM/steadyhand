"""CompoundingSizer: target weights to whole lots, rounded towards zero (M3 spec §6.2)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

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


def check_orders_are_whole_lots_that_never_overshoot_the_target(
    value: int, weights: list[int], held: list[int]
) -> list[Order]:
    """The sizing property's check on any cash, weights and holdings, called by its unit
    stand-in below and by tests/properties/test_engine_sizing.py on every draw: every order is
    whole lots, a buy's holding sorts at or below its target, and a sale sorts at or below what
    is held and leaves the holding at or above its target (#365: equalities, no typed-in
    bound). Returns the orders."""
    stocks = (BBCA, BBRI, TLKM)
    total = sum(weights) or 1
    decimals = {s: Decimal(w) / total / 2 for s, w in zip(stocks, weights, strict=True)}
    shares = {s: h for s, h in zip(stocks, held, strict=True) if h}
    worth = sum(PRICES[s].amount * n for s, n in shares.items())
    portfolio = view(worth + value, shares)
    orders = sizer().size(decimals, portfolio, shares, PRICES, DAY)
    for order in orders:  # runtime population: the orders the sizer returned
        stock = order.instrument
        assert order.quantity % 100 == 0
        target = portfolio.value.times(decimals[stock], rounding=Rounding.DOWN).amount
        current = PRICES[stock].amount * shares.get(stock, 0)
        traded = PRICES[stock].amount * order.quantity
        if order.side is Side.BUY:
            assert sorted([target, current + traded]) == [current + traded, target]
        else:
            assert sorted([shares[stock], order.quantity]) == [order.quantity, shares[stock]]
            assert sorted([current - traded, target]) == [target, current - traded]
    return list(orders)


# Unit stand-in of the property in tests/properties/test_engine_sizing.py (#290):
# nothing at all, all cash at the largest value, all held with no weights
# (everything sold), and a mix of both sides. Worked by hand, each weight half its share of the
# drawn ones, each target the weight times the value rounded down, and each order the whole lots
# between holding and target, rounded towards zero. All cash: a sixth of Rp10bn is 1,666,666,666,
# which is 1,851 lots of BBCA at Rp900,000, 4,166 of BBRI at Rp400,000 and 6,666 of TLKM at
# Rp250,000. All held: each target is 0, so all 5,000 of each are sold. The mix is worth
# Rp14,632,067: BBCA's 1/3,002 of it, 4,874, is within a lot of its Rp900,000 held; BBRI's
# 250/1,501, 2,437,053, buys 6 lots; TLKM's 500/1,501, 4,874,106, sells 30 of the Rp12,497,500 held.
@pytest.mark.parametrize(
    ("value", "weights", "held", "expected"),
    [
        (0, [0, 0, 0], [0, 0, 0], []),
        (
            10**10,
            [1_000, 1_000, 1_000],
            [0, 0, 0],
            [
                Order(BBCA, Side.BUY, 185_100, DAY),
                Order(BBRI, Side.BUY, 416_600, DAY),
                Order(TLKM, Side.BUY, 666_600, DAY),
            ],
        ),
        (
            0,
            [0, 0, 0],
            [5_000, 5_000, 5_000],
            [
                Order(BBCA, Side.SELL, 5_000, DAY),
                Order(BBRI, Side.SELL, 5_000, DAY),
                Order(TLKM, Side.SELL, 5_000, DAY),
            ],
        ),
        (
            1_234_567,
            [1, 500, 1_000],
            [100, 0, 4_999],
            [Order(TLKM, Side.SELL, 3_000, DAY), Order(BBRI, Side.BUY, 600, DAY)],
        ),
    ],
    ids=["nothing", "all-cash", "all-held", "mix"],
)
def test_orders_are_whole_lots_that_never_overshoot_the_target(
    value: int, weights: list[int], held: list[int], expected: list[Order]
) -> None:
    assert check_orders_are_whole_lots_that_never_overshoot_the_target(value, weights, held) == (
        expected
    )
