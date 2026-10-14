"""The buy-and-hold property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_buy_and_hold.py, on every case it draws."""

import test_buy_and_hold as unit
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import Instrument


@given(
    held=st.dictionaries(st.sampled_from(unit.STOCKS), st.integers(1, 10**10), max_size=5),
    spendable=st.integers(0, 10**10),
    unsettled=st.integers(0, 10**10),
    chosen=st.sets(st.sampled_from(unit.STOCKS)),
    buyable=st.sets(st.sampled_from(unit.STOCKS)),
)
def test_it_never_sells_and_buys_only_its_set(
    held: dict[Instrument, int],
    spendable: int,
    unsettled: int,
    chosen: set[Instrument],
    buyable: set[Instrument],
) -> None:
    unit.test_it_never_sells_and_buys_only_its_set(held, spendable, unsettled, chosen, buyable)
