"""The portfolio properties at their full count (#290). Each calls its unit stand-in, in
tests/engine/test_portfolio_properties.py, on every case it draws."""

import test_portfolio_properties as unit
from hypothesis import example, given
from hypothesis import strategies as st

STEP = st.tuples(
    st.sampled_from(["deposit", "buy", "sell"]),
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=0, max_value=len(unit.STOCKS) - 1),
    st.integers(min_value=1, max_value=5_000),
    st.integers(min_value=50, max_value=20_000),
    st.integers(min_value=0, max_value=50_000),
)
LATER_STEP = st.tuples(
    st.sampled_from(["deposit", "buy", "sell", "dividend", "duty-later"]),
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=0, max_value=len(unit.STOCKS) - 1),
    st.integers(min_value=1, max_value=5_000),
    st.integers(min_value=50, max_value=20_000),
    st.integers(min_value=0, max_value=50_000),
)


@given(st.lists(STEP, max_size=40))
@example(
    [
        ("deposit", 0, 0, 5_000, 0, 0),
        ("buy", 0, 1, 300, 4_000, 450),
        ("sell", 1, 1, 100, 4_100, 200),
        ("buy", 2, 2, 100, 3_000, 0),
    ]
)
def test_cash_and_share_invariants(steps: list[unit.Step]) -> None:
    unit.test_cash_and_share_invariants(steps)


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
    unit.test_a_round_trip_at_an_unchanged_price_loses_exactly_the_costs(
        shares, price, buy_fee, sell_fee
    )


@given(st.lists(LATER_STEP, max_size=40))
def test_the_kept_totals_agree_with_the_whole_ledger_on_every_day(steps: list[unit.Step]) -> None:
    unit.test_the_kept_totals_agree_with_the_whole_ledger_on_every_day(steps)
