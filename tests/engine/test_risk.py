"""RiskManager, RiskLimits and the unit value: every limit at its threshold and one step past."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView, Tradable
from steadyhand_idx import IdxMarketRules

DAY = date(2025, 6, 2)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
PRICES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR)}
OPEN = Tradable(DAY, frozenset({BBCA, BBRI}), frozenset({BBCA, BBRI}), {TLKM: "frozen: merger"})


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def buy(quantity: int, stock: Instrument = BBCA) -> Order:
    return Order(stock, Side.BUY, quantity, DAY)


def check(
    *orders: Order,
    value: int = 100_000_000,
    spendable: int | None = None,
    held: dict[Instrument, int] | None = None,
    limits: RiskLimits | None = None,
) -> tuple[list[Order], list[tuple[Order, str]], list[tuple[int, str]]]:
    """Check *orders* for a portfolio worth *value*, spending all of it not *held* by default."""
    holdings = {stock: rp(amount) for stock, amount in (held or {}).items()}
    cash = value - sum((held or {}).values()) if spendable is None else spendable
    portfolio = PortfolioView(rp(value), rp(cash), holdings)
    result = RiskManager(rules(), limits).check(orders, portfolio, OPEN, PRICES)
    rejected = [(r.order, r.reason) for r in result.rejected]
    return list(result.orders), rejected, [(c.quantity, c.reason) for c in result.cuts]


def test_the_defaults_are_the_core_specs() -> None:
    limits = RiskManager(rules()).limits
    assert limits == RiskLimits(Decimal("0.10"), 1, Decimal("0.05"), Decimal("0.25"))


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"max_weight": 0.1}, TypeError, r"^max_weight must be a finite Decimal, got 0\.1$"),
        ({"daily_loss": Decimal("NaN")}, TypeError, r"^daily_loss must be a finite Decimal"),
        ({"min_lots": 0}, ValueError, r"^min_lots must be at least 1, got 0$"),
        ({"max_weight": Decimal(0)}, ValueError, r"^max_weight must be above 0 and at most 1"),
        ({"max_weight": Decimal("1.01")}, ValueError, r"^max_weight must be above 0 and at most"),
        (
            {"daily_loss": Decimal(1)},
            ValueError,
            r"^daily_loss must be above 0 and below 1, got 1$",
        ),
        ({"max_drawdown": Decimal(0)}, ValueError, r"^max_drawdown must be above 0 and below 1"),
    ],
)
def test_limits_are_checked(
    kwargs: dict[str, object], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        RiskLimits(**kwargs)  # type: ignore[arg-type]


def test_a_stock_outside_the_tradable_set_is_dropped_with_its_reason() -> None:
    sell = Order(TLKM, Side.SELL, 100, DAY)
    stranger = buy(100, Instrument("ASII", "IDX", IDR))
    passed, rejected, _ = check(buy(100, TLKM), sell, stranger)
    assert passed == []
    assert rejected == [
        (buy(100, TLKM), "frozen: merger"),
        (sell, "frozen: merger"),
        (stranger, "not in the universe on 2025-06-02"),
    ]


def test_sales_pass_and_their_proceeds_fund_nothing() -> None:
    sell = Order(BBCA, Side.SELL, 1_000, DAY)
    passed, rejected, _ = check(sell, buy(100), spendable=0)
    assert passed == [sell]
    assert rejected == [(buy(100), "not enough cash: IDR 0 can be spent")]


def test_a_buy_is_cut_to_the_limit_per_stock_exactly_at_its_edge() -> None:
    passed, _, cuts = check(buy(300), value=18_000_000)
    assert passed == [buy(200)]
    assert cuts == [(200, "cut to the 10.00% limit per stock")]
    passed, _, cuts = check(buy(300), value=17_999_990)
    assert passed == [buy(100)]


def test_a_buy_for_a_stock_already_at_the_limit_is_dropped() -> None:
    _, rejected, _ = check(buy(100), value=10_000_000, held={BBCA: 900_001})
    assert rejected == [(buy(100), "already at the 10.00% limit per stock")]


def test_a_buy_below_the_minimum_lots_is_dropped() -> None:
    limits = RiskLimits(min_lots=2)
    passed, rejected, _ = check(buy(100), buy(200, BBRI), limits=limits)
    assert rejected == [(buy(100), "below the minimum buy of 2 lot(s)")]
    assert passed == [buy(200, BBRI)]


def test_buys_together_spend_no_more_than_the_cash_costs_included() -> None:
    limits = RiskLimits(max_weight=Decimal(1))
    passed, rejected, _ = check(buy(100), buy(100, BBRI), spendable=1_000_000, limits=limits)
    assert passed == [buy(100)]
    assert rejected == [(buy(100, BBRI), "not enough cash: IDR 98,111 can be spent")]
    passed, _, cuts = check(buy(300), spendable=1_803_777, limits=limits)
    assert passed == [buy(200)]
    assert cuts == [(200, "cut to the IDR 1,803,777 that can be spent")]
    passed, _, _ = check(buy(300), spendable=1_803_776, limits=limits)
    assert passed == [buy(100)]


def test_the_first_deposit_buys_units_at_one() -> None:
    funded = UnitValue().deposit(rp(10_000_000))
    assert funded == UnitValue(Decimal(10_000_000), Decimal(1), Decimal(1))


def test_a_deposit_leaves_the_unit_value_unchanged() -> None:
    fund = UnitValue().deposit(rp(10_000_000)).revalue(rp(12_000_000))
    topped = fund.deposit(rp(1_200_000))
    assert (topped.units, topped.price) == (Decimal(11_000_000), Decimal("1.2"))
    assert topped.revalue(rp(13_200_000)).price == Decimal("1.2")


def test_revaluing_moves_the_price_and_the_high_water_mark() -> None:
    fund = UnitValue().deposit(rp(1_000)).revalue(rp(1_500)).revalue(rp(1_200))
    assert (fund.price, fund.high_water) == (Decimal("1.2"), Decimal("1.5"))
    assert UnitValue().revalue(rp(5)) == UnitValue()


def test_units_cannot_be_bought_at_nothing_and_are_never_negative() -> None:
    worthless = UnitValue(Decimal(10), Decimal(0), Decimal(1))
    with pytest.raises(ValueError, match=r"^no units can be bought at a price of 0$"):
        worthless.deposit(rp(1))
    with pytest.raises(ValueError, match=r"^units cannot be negative, got -1$"):
        UnitValue(Decimal(-1))
    with pytest.raises(TypeError, match=r"^price must be a finite Decimal, got 1$"):
        UnitValue(Decimal(1), 1)  # type: ignore[arg-type]


@given(
    units=st.integers(1, 10**12),
    value=st.integers(1, 10**13),
    deposit=st.integers(1, 10**12),
)
def test_a_deposit_never_moves_the_price(units: int, value: int, deposit: int) -> None:
    fund = UnitValue(Decimal(units)).revalue(rp(value))
    topped = fund.deposit(rp(deposit))
    assert topped.price == fund.price
    # Valued again with the deposit in it, the fund is worth what it was per unit: a deposit
    # is neither a gain nor a loss. Decimal rounding at 28 digits may move it either way, by
    # far less than any limit could notice.
    after = topped.revalue(rp(value + deposit)).price
    assert abs(after - fund.price) <= fund.price * Decimal("1e-20")


def fund(price: str, high_water: str = "1") -> UnitValue:
    return UnitValue(Decimal(100), Decimal(price), Decimal(high_water))


def test_a_daily_loss_at_the_limit_halts() -> None:
    halt = RiskManager(rules()).halt(fund("1"), fund("0.95"), DAY)
    assert halt == Halt(DAY, "daily loss limit: the unit value fell 5.00%, the limit is 5.00%")
    assert RiskManager(rules()).halt(fund("1"), fund("0.9501"), DAY) is None


def test_a_drawdown_at_the_kill_switch_halts() -> None:
    manager = RiskManager(rules())
    halt = manager.halt(fund("0.76", "1"), fund("0.75", "1"), DAY)
    assert halt == Halt(
        DAY,
        "drawdown kill switch: the unit value is 25.00% below its high-water mark, "
        "the limit is 25.00%",
    )
    assert manager.halt(fund("0.76", "1"), fund("0.7501", "1"), DAY) is None


def test_no_halt_before_there_are_units() -> None:
    empty = UnitValue()
    assert RiskManager(rules()).halt(empty, UnitValue(Decimal(0), Decimal("0.1")), DAY) is None
    assert RiskManager(rules()).halt(empty, fund("0.96"), DAY) is None


def test_a_halt_needs_a_day_and_a_cause() -> None:
    with pytest.raises(ValueError, match=r"^a halt needs a cause$"):
        Halt(DAY, " ")
    with pytest.raises(TypeError, match=r"^halt day must be a date, got str$"):
        Halt("2025-06-02", "x")  # type: ignore[arg-type]
