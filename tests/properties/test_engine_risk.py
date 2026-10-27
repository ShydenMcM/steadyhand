"""The unit value property at its full count (#290). It calls its unit stand-in's check, in
tests/engine/test_risk.py, on every case it draws."""

import test_risk as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    units=st.integers(1, 10**12),
    value=st.integers(1, 10**13),
    deposit=st.integers(1, 10**12),
)
def test_a_deposit_never_moves_the_price(units: int, value: int, deposit: int) -> None:
    unit.check_a_deposit_never_moves_the_price(units, value, deposit)
