"""The split property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_portfolio_actions.py, on every case it draws."""

import test_portfolio_actions as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    quantity=st.integers(min_value=1, max_value=10**6),
    cost=st.integers(min_value=10**6, max_value=10**9),
    ratio=st.tuples(st.integers(1, 20), st.integers(1, 20)).filter(lambda r: r[0] != r[1]),
)
def test_splits_keep_the_total_cost_basis(quantity: int, cost: int, ratio: tuple[int, int]) -> None:
    unit.test_splits_keep_the_total_cost_basis(quantity, cost, ratio)
