"""Invariants that must hold after any sequence of deposits, buys and sells (spec §10.2)."""

from contextlib import suppress
from datetime import date, timedelta

from hypothesis import example, given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money
from steadyhand.portfolio import (
    InsufficientCashError,
    InsufficientSharesError,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.types import Costs, Fill, Instrument, Order, Side

D0 = date(2026, 1, 5)
STOCKS = (
    Instrument("ASII", "IDX", IDR),
    Instrument("BBRI", "IDX", IDR),
    Instrument("TLKM", "IDX", IDR),
)

type Step = tuple[str, int, int, int, int, int]  # kind, days forward, stock, shares, price, fee

STEP = st.tuples(
    st.sampled_from(["deposit", "buy", "sell"]),
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=0, max_value=len(STOCKS) - 1),
    st.integers(min_value=1, max_value=5_000),
    st.integers(min_value=50, max_value=20_000),
    st.integers(min_value=0, max_value=50_000),
)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def make_fill(side: Side, stock: Instrument, shares: int, price: int, fee: int, on: date) -> Fill:
    return Fill(Order(stock, side, shares, on), on, shares, rp(price), Costs(rp(fee), rp(0), rp(0)))


@given(st.lists(STEP, max_size=40))
@example(
    [
        ("deposit", 0, 0, 5_000, 0, 0),
        ("buy", 0, 1, 300, 4_000, 450),
        ("sell", 1, 1, 100, 4_100, 200),
        ("buy", 2, 2, 100, 3_000, 0),
    ]
)
def test_cash_and_share_invariants(steps: list[Step]) -> None:
    portfolio = Portfolio.empty(IDR)
    today = D0
    expected_cash = 0
    expected_shares = dict.fromkeys(STOCKS, 0)
    for kind, forward, stock_index, shares, price, fee in steps:
        today += timedelta(days=forward)
        stock = STOCKS[stock_index]
        with suppress(InsufficientCashError, InsufficientSharesError, NegativeProceedsError):
            # A refused step raises before `portfolio` is rebound, so the snapshot is unchanged.
            if kind == "deposit":
                portfolio = portfolio.deposit(rp(shares * 1_000), today)
                expected_cash += shares * 1_000
            elif kind == "buy":
                buy = make_fill(Side.BUY, stock, shares, price, fee, today)
                portfolio = portfolio.apply_fill(buy, today + timedelta(days=2))
                expected_cash -= shares * price + fee
                expected_shares[stock] += shares
            else:
                sell = make_fill(Side.SELL, stock, shares, price, fee, today)
                portfolio = portfolio.apply_fill(sell, today + timedelta(days=2))
                expected_cash += shares * price - fee
                expected_shares[stock] -= shares
        assert portfolio.cash_balance() == rp(expected_cash)
        for probe in (today, today + timedelta(days=1), today + timedelta(days=2)):
            assert portfolio.settled_cash(probe).amount >= 0
        balance = portfolio.settled_cash(today) + portfolio.unsettled_cash(today)
        assert balance == portfolio.cash_balance()
        held = {s: (p.quantity if (p := portfolio.position(s)) else 0) for s in STOCKS}
        assert held == expected_shares


@given(
    shares=st.integers(min_value=1, max_value=10_000),
    price=st.integers(min_value=50, max_value=50_000),
    buy_fee=st.integers(min_value=0, max_value=100_000),
    data=st.data(),
)
def test_a_round_trip_at_an_unchanged_price_loses_exactly_the_costs(
    shares: int, price: int, buy_fee: int, data: st.DataObject
) -> None:
    sell_fee = data.draw(st.integers(min_value=0, max_value=shares * price), label="sell_fee")
    start = shares * price + buy_fee
    stock = STOCKS[1]
    buy = make_fill(Side.BUY, stock, shares, price, buy_fee, D0)
    sell = make_fill(Side.SELL, stock, shares, price, sell_fee, D0 + timedelta(days=1))
    after = (
        Portfolio.empty(IDR)
        .deposit(rp(start), D0)
        .apply_fill(buy, D0 + timedelta(days=2))
        .apply_fill(sell, D0 + timedelta(days=3))
    )
    assert after.cash_balance() == rp(start - buy_fee - sell_fee)
    assert after.settled_cash(D0 + timedelta(days=3)) == after.cash_balance()
    assert after.position(stock) is None
