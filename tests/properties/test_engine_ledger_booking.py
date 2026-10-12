"""The ledger booking property at its full count (#290). It calls its unit stand-in, in
tests/engine/test_ledger_booking.py, on every case it draws."""

import test_ledger_booking as unit
from hypothesis import given
from hypothesis import strategies as st

STEP = st.tuples(
    st.sampled_from(["deposit", "tax", "read"]),
    st.integers(min_value=0, max_value=50),
    st.integers(min_value=1, max_value=1_000),
)


@given(st.lists(STEP, max_size=40))
def test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger(
    steps: list[tuple[str, int, int]],
) -> None:
    unit.test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger(steps)
