"""The sizing property at its full count (#290). It calls its unit stand-in's check, in
tests/engine/test_sizing.py, on every case it draws."""

import test_sizing as unit
from hypothesis import given
from hypothesis import strategies as st


@given(
    value=st.integers(0, 10**10),
    weights=st.lists(st.integers(0, 1_000), min_size=3, max_size=3),
    held=st.lists(st.integers(0, 5_000), min_size=3, max_size=3),
)
def test_orders_are_whole_lots_that_never_overshoot_the_target(
    value: int, weights: list[int], held: list[int]
) -> None:
    unit.check_orders_are_whole_lots_that_never_overshoot_the_target(value, weights, held)
