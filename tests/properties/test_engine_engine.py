"""The engine day property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_engine.py, on every case it draws."""

import test_engine as unit
from hypothesis import given, settings
from hypothesis import strategies as st


# Each example runs the engine for four days: the count it was written with (#74).
@settings(max_examples=40)
@given(
    moves=st.lists(st.tuples(st.integers(-12, 12), st.integers(-12, 12)), min_size=3, max_size=3),
    capital=st.integers(1_000_000, 50_000_000),
)
def test_every_day_keeps_cash_whole_and_the_value_adding_up(
    moves: list[tuple[int, int]], capital: int
) -> None:
    unit.test_every_day_keeps_cash_whole_and_the_value_adding_up(moves, capital)
