"""The simulated broker properties at their full count (#290). Each calls its unit stand-in, in
tests/engine/test_simulated_broker.py, on every case it draws."""

from datetime import date

import pytest
import test_simulated_broker as unit
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import Instrument, Side

# A cash balance, a number of lots of each stock held, the orders placed, and each stock's open
# and volume: one draw serves both tests below.
DRAW = {
    "cash": st.integers(0, 30_000_000),
    "held": st.integers(0, 40),
    "orders": st.lists(
        st.tuples(
            st.sampled_from([Side.BUY, Side.SELL]),
            st.sampled_from([unit.BBCA, unit.BBRI]),
            st.integers(1, 30),
        ),
        max_size=6,
    ),
    "opens": st.tuples(st.integers(7_700, 10_700), st.integers(3_450, 4_950)),
    "volumes": st.tuples(st.integers(0, 50_000), st.integers(0, 50_000)),
}


@pytest.mark.parametrize("probe", [unit.TODAY, date(2025, 6, 4), unit.SETTLES], ids=str)
@given(**DRAW)
def test_the_settled_cash_is_never_negative_from_the_trade_to_its_settlement(
    probe: date,
    cash: int,
    held: int,
    orders: list[tuple[Side, Instrument, int]],
    opens: tuple[int, int],
    volumes: tuple[int, int],
) -> None:
    unit.test_the_settled_cash_is_never_negative_from_the_trade_to_its_settlement(
        probe, cash, held, orders, opens, volumes
    )


@given(**DRAW)
def test_fills_keep_cash_whole_lots_ticks_and_bands(
    cash: int,
    held: int,
    orders: list[tuple[Side, Instrument, int]],
    opens: tuple[int, int],
    volumes: tuple[int, int],
) -> None:
    unit.test_fills_keep_cash_whole_lots_ticks_and_bands(cash, held, orders, opens, volumes)
