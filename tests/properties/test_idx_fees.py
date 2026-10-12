"""The fees property at its full count (#290). It calls its unit stand-in, in
tests/idx/test_fees.py, on every case it draws."""

import test_fees as unit
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.types import Side


@given(
    gross=st.integers(min_value=0, max_value=10**12),
    key=st.sampled_from(sorted(unit.TOTAL_PERCENT, key=str)),
)
def test_costs_round_once_against_the_trader(gross: int, key: tuple[str, Side]) -> None:
    unit.test_costs_round_once_against_the_trader(gross, key)
