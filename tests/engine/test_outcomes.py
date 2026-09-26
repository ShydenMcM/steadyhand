"""Rejected and Cut: every order that does not go through as placed says why."""

from datetime import date

import pytest

from steadyhand.money import IDR
from steadyhand.outcomes import Cut, Rejected
from steadyhand.types import Instrument, Order, Side

ORDER = Order(Instrument("BBCA", "IDX", IDR), Side.BUY, 500, date(2025, 6, 2))


def test_outcomes_keep_the_order_and_the_reason() -> None:
    assert Rejected(ORDER, "frozen: rights issue").reason == "frozen: rights issue"
    cut = Cut(ORDER, 100, "cut to 10% of the day's volume")
    assert (cut.order, cut.quantity) == (ORDER, 100)


@pytest.mark.parametrize("reason", ["", "   "])
def test_every_outcome_needs_a_reason(reason: str) -> None:
    with pytest.raises(ValueError, match=r"^a buy order for BBCA needs a reason$"):
        Rejected(ORDER, reason)
    with pytest.raises(ValueError, match=r"^a buy order for BBCA needs a reason$"):
        Cut(ORDER, 100, reason)


def test_a_cut_leaves_fewer_shares_than_the_order() -> None:
    with pytest.raises(ValueError, match=r"^a cut must leave fewer than 500 shares, got 500$"):
        Cut(ORDER, 500, "no change")
    with pytest.raises(ValueError, match=r"^cut quantity must be at least 1, got 0$"):
        Cut(ORDER, 0, "nothing left")


def test_outcomes_check_their_types() -> None:
    with pytest.raises(TypeError, match=r"^order must be an Order, got str$"):
        Rejected("BBCA", "no bar")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^reason must be a str, got int$"):
        Rejected(ORDER, 3)  # type: ignore[arg-type]
