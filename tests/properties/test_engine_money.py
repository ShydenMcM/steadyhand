"""The money property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_money.py, on every case it draws."""

from decimal import Decimal

import test_money as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    amount=st.integers(min_value=0, max_value=10**15),
    rate=st.decimals(min_value=0, max_value=1, places=6, allow_nan=False, allow_infinity=False),
)
def test_up_and_down_bracket_the_exact_value(amount: int, rate: Decimal) -> None:
    unit.TestTimes().test_up_and_down_bracket_the_exact_value(amount, rate)
