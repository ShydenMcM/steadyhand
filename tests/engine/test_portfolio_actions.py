"""Portfolio: dividends, tax and daily costs as cash movements, and splits (M3 spec §3.3)."""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import ChronologyError, InsufficientCashError, MovementKind, Portfolio
from steadyhand.types import Costs, Fill, Instrument, Order, Side, Split

D0 = date(2026, 1, 5)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
USD = Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(quantity: int, cost: int, stock: Instrument = BBRI) -> Portfolio:
    """A portfolio that bought *quantity* shares for exactly *cost*, with nothing left over."""
    order = Order(stock, Side.BUY, quantity, D0)
    price, remainder = divmod(cost, quantity)
    fill = Fill(order, D0, quantity, rp(price), Costs(rp(remainder), rp(0), rp(0)))
    return Portfolio.empty(IDR).deposit(rp(cost), D0).apply_fill(fill, D0)


def test_the_new_movement_kinds() -> None:
    kinds = {kind.name: kind.value for kind in MovementKind}
    assert kinds == {
        "DEPOSIT": "deposit",
        "BUY": "buy",
        "SELL": "sell",
        "DIVIDEND": "dividend",
        "TAX": "tax",
        "DAILY_COST": "daily cost",
    }


def test_a_dividend_is_settled_cash_on_the_day_it_is_paid() -> None:
    paid = holding(100, 400_000).credit_dividend(rp(12_345), D0 + timedelta(days=1))
    movement = paid.ledger[-1]
    assert (movement.kind, movement.amount, movement.settles_on) == (
        MovementKind.DIVIDEND,
        rp(12_345),
        D0 + timedelta(days=1),
    )
    assert paid.settled_cash(D0 + timedelta(days=1)) == rp(12_345)
    assert paid.positions == holding(100, 400_000).positions


@pytest.mark.parametrize("kind", [MovementKind.TAX, MovementKind.DAILY_COST])
def test_a_charge_is_debited_on_its_day(kind: MovementKind) -> None:
    charged = Portfolio.empty(IDR).deposit(rp(50_000), D0).charge(kind, rp(10_000), D0)
    movement = charged.ledger[-1]
    assert (movement.kind, movement.amount, movement.settles_on) == (kind, rp(-10_000), D0)
    assert charged.settled_cash(D0) == rp(40_000)
    assert charged.cash_balance() == rp(40_000)


def test_a_deferred_charge_is_held_back_from_spending_at_once() -> None:
    later = D0 + timedelta(days=2)
    charged = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    charged = charged.charge(MovementKind.DAILY_COST, rp(10_000), D0, settles_on=later)
    assert (charged.settled_cash(D0), charged.spendable_cash(D0)) == (rp(50_000), rp(40_000))
    assert (charged.settled_cash(later), charged.spendable_cash(later)) == (rp(40_000), rp(40_000))
    order = Order(BBRI, Side.BUY, 45, D0)
    buy = Fill(order, D0, 45, rp(1_000), Costs.zero(IDR))
    with pytest.raises(
        InsufficientCashError,
        match=r"^2026-01-05: needs IDR 45,000 but only IDR 40,000 can be spent$",
    ):
        charged.apply_fill(buy, later)


def test_sale_proceeds_are_spendable_once_settled() -> None:
    later = D0 + timedelta(days=2)
    order = Order(BBRI, Side.SELL, 100, D0)
    sold = holding(100, 100_000).apply_fill(Fill(order, D0, 100, rp(1_000), Costs.zero(IDR)), later)
    assert (sold.spendable_cash(D0), sold.spendable_cash(later)) == (rp(0), rp(100_000))


def test_a_charge_cannot_settle_before_it_is_made() -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(
        ValueError, match=r"^settles on 2026-01-04, before the trade on 2026-01-05$"
    ):
        funded.charge(MovementKind.TAX, rp(1), D0, settles_on=D0 - timedelta(days=1))


@pytest.mark.parametrize("kind", [MovementKind.DEPOSIT, MovementKind.DIVIDEND, MovementKind.BUY])
def test_only_tax_and_daily_costs_are_charges(kind: MovementKind) -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(
        ValueError, match=rf"^charge books tax or a daily cost, not a {kind.value}$"
    ):
        funded.charge(kind, rp(1), D0)


def test_a_charge_kind_must_be_a_movement_kind() -> None:
    with pytest.raises(TypeError, match=r"^kind must be a MovementKind, got str$"):
        Portfolio.empty(IDR).charge("tax", rp(1), D0)  # type: ignore[arg-type]


@pytest.mark.parametrize("amount", [0, -1])
def test_dividends_and_charges_must_be_positive(amount: int) -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(ValueError, match=rf"^a dividend must be positive, got IDR {amount}$"):
        funded.credit_dividend(rp(amount), D0)
    with pytest.raises(ValueError, match=rf"^a tax must be positive, got IDR {amount}$"):
        funded.charge(MovementKind.TAX, rp(amount), D0)


def test_dividends_and_charges_check_currency_type_and_date() -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        funded.credit_dividend(Money(100, USD), D0)
    with pytest.raises(TypeError, match=r"^amount must be a Money, got int$"):
        funded.charge(MovementKind.DAILY_COST, 10_000, D0)  # type: ignore[arg-type]
    with pytest.raises(ChronologyError, match=r"^2026-01-04 is before the last recorded"):
        funded.credit_dividend(rp(1), D0 - timedelta(days=1))


def test_a_split_scales_the_quantity_and_keeps_the_basis() -> None:
    split = holding(300, 1_200_000).apply_split(Split(BBRI, D0, 1, 5))
    only = split.positions[0]
    assert (only.quantity, only.cost_basis) == (1_500, rp(1_200_000))
    assert split.ledger == holding(300, 1_200_000).ledger


def test_a_reverse_split_drops_the_fraction_of_a_share() -> None:
    split = holding(1_203, 1_203_000).apply_split(Split(BBRI, D0, 5, 1))
    only = split.positions[0]
    assert (only.quantity, only.cost_basis) == (240, rp(1_203_000))


def test_a_holding_that_rounds_to_nothing_is_removed() -> None:
    split = holding(4, 4_000).apply_split(Split(BBRI, D0, 5, 1))
    assert split.positions == ()
    assert split.cash_balance() == rp(0)


def test_a_split_leaves_other_holdings_alone() -> None:
    both = holding(100, 100_000).deposit(rp(200_000), D0)
    order = Order(TLKM, Side.BUY, 200, D0)
    both = both.apply_fill(Fill(order, D0, 200, rp(1_000), Costs.zero(IDR)), D0)
    split = both.apply_split(Split(TLKM, D0, 1, 2))
    assert [(p.instrument.symbol, p.quantity) for p in split.positions] == [
        ("BBRI", 100),
        ("TLKM", 400),
    ]


def test_a_split_needs_a_holding_a_split_and_a_date_in_order() -> None:
    with pytest.raises(ValueError, match=r"^2026-01-05: no TLKM is held to split$"):
        holding(100, 100_000).apply_split(Split(TLKM, D0, 1, 5))
    with pytest.raises(TypeError, match=r"^split must be a Split, got tuple$"):
        holding(100, 100_000).apply_split((BBRI, D0, 1, 5))  # type: ignore[arg-type]
    with pytest.raises(ChronologyError, match=r"^2026-01-04 is before the last recorded"):
        holding(100, 100_000).apply_split(Split(BBRI, D0 - timedelta(days=1), 1, 5))


@given(
    quantity=st.integers(min_value=1, max_value=10**6),
    cost=st.integers(min_value=10**6, max_value=10**9),
    ratio=st.tuples(st.integers(1, 20), st.integers(1, 20)).filter(lambda r: r[0] != r[1]),
)
def test_splits_keep_the_total_cost_basis(quantity: int, cost: int, ratio: tuple[int, int]) -> None:
    before = holding(quantity, cost)
    after = before.apply_split(Split(BBRI, D0, *ratio))
    expected = quantity * ratio[1] // ratio[0]
    if expected == 0:
        assert after.positions == ()
    else:
        assert (after.positions[0].quantity, after.positions[0].cost_basis) == (expected, rp(cost))
    assert after.cash_balance() == before.cash_balance()
