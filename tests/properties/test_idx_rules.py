"""The price band property at its full count (#290). It calls its unit stand-in, in
tests/idx/test_rules.py, on every case it draws."""

from datetime import date

import test_rules as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    reference=st.integers(min_value=50, max_value=1_000_000),
    on=st.sampled_from([date(2021, 1, 4), date(2023, 6, 5), date(2023, 9, 4), unit.TODAY]),
)
def test_band_edges_are_the_widest_valid_prices_inside_the_band(reference: int, on: date) -> None:
    unit.test_band_edges_are_the_widest_valid_prices_inside_the_band(reference, on)
