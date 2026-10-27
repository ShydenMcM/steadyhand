"""The tick property at its full count (#290). It calls its unit stand-in's check, in
tests/idx/test_ticks.py, on every case it draws."""

import test_ticks as unit
from hypothesis import given
from hypothesis import strategies as st


@given(st.integers(min_value=1, max_value=2_000_000))
def test_rounding_is_tight_and_valid(price: int) -> None:
    unit.check_rounding_is_tight_and_valid(price)
