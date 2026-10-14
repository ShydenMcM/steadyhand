"""The received income property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_income_received.py, on every case it draws."""

import test_income_received as unit
from hypothesis import given
from hypothesis import strategies as st


@given(st.lists(st.integers(min_value=1, max_value=10**12), min_size=1, max_size=5))
def test_take_home_is_never_more_than_gross(amounts: list[int]) -> None:
    unit.test_take_home_is_never_more_than_gross(amounts)
