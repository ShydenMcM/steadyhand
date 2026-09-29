"""Rejected and Cut: every order that does not go through as placed says why."""

from datetime import date

import pytest

from steadyhand.money import IDR
from steadyhand.notes import FILL_FROZEN, FILL_VOLUME_CUT, Note
from steadyhand.outcomes import Cut, Rejected
from steadyhand.types import Instrument, Order, Side

ORDER = Order(Instrument("BBCA", "IDX", IDR), Side.BUY, 500, date(2025, 6, 2))


def test_outcomes_keep_the_order_and_the_keyed_reason() -> None:
    frozen = Note(FILL_FROZEN, "frozen: rights issue")
    assert Rejected(ORDER, frozen).reason == frozen
    volume = Note(FILL_VOLUME_CUT, "cut to 10% of the day's volume")
    cut = Cut(ORDER, 100, volume)
    assert (cut.order, cut.quantity, cut.reason) == (ORDER, 100, volume)


def test_every_reason_is_a_note_under_a_key() -> None:
    with pytest.raises(TypeError, match=r"^reason must be a Note, got str$"):
        Rejected(ORDER, "frozen: rights issue")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^reason must be a Note, got str$"):
        Cut(ORDER, 100, "cut to 10% of the day's volume")  # type: ignore[arg-type]


def test_a_cut_leaves_fewer_shares_than_the_order() -> None:
    with pytest.raises(ValueError, match=r"^a cut must leave fewer than 500 shares, got 500$"):
        Cut(ORDER, 500, Note(FILL_VOLUME_CUT, "no change"))
    with pytest.raises(ValueError, match=r"^cut quantity must be at least 1, got 0$"):
        Cut(ORDER, 0, Note(FILL_VOLUME_CUT, "nothing left"))


def test_outcomes_check_their_types() -> None:
    with pytest.raises(TypeError, match=r"^order must be an Order, got str$"):
        Rejected("BBCA", "no bar")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^reason must be a Note, got int$"):
        Rejected(ORDER, 3)  # type: ignore[arg-type]
