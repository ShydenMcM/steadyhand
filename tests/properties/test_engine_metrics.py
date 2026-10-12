"""The drawdown property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_metrics.py, on every case it draws."""

from decimal import Decimal

import test_metrics as unit
from hypothesis import given
from hypothesis import strategies as st


@given(st.lists(st.decimals(min_value=0, max_value=5, places=3), min_size=1, max_size=30))
def test_the_drawdown_matches_every_pair_checked(prices: list[Decimal]) -> None:
    unit.test_the_drawdown_matches_every_pair_checked(prices)
