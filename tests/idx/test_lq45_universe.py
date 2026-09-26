"""Lq45Universe: the user's LQ45 lists and exclusions, as the engine's Universe (M3 spec §7.2)."""

from datetime import date
from itertools import product

import pytest

from steadyhand import IDR, Instrument, Universe
from steadyhand_idx.universe import (
    Exclusion,
    Exclusions,
    Lq45Membership,
    Lq45Record,
    Lq45Universe,
    MembershipUnknownError,
)

CODES = ["Z" + "".join(letters) for letters in product("ABCDEFGHIJ", repeat=3)][:46]
FIRST = date(2021, 2, 1)
SECOND = date(2021, 8, 2)


def membership() -> Lq45Membership:
    return Lq45Membership(
        [
            Lq45Record(FIRST, date(2021, 1, 25), "Peng-1", "review", frozenset(CODES[:45])),
            Lq45Record(SECOND, date(2021, 7, 26), "Peng-2", "review", frozenset(CODES[1:])),
        ]
    )


def stock(code: str) -> Instrument:
    return Instrument(code, "IDX", IDR)


def test_it_is_the_engines_universe() -> None:
    universe: Universe = Lq45Universe(membership())
    assert isinstance(universe, Universe)


def test_members_are_idx_instruments_from_the_list_in_force() -> None:
    universe = Lq45Universe(membership())
    assert universe.members_on(FIRST) == frozenset(stock(code) for code in CODES[:45])
    assert universe.members_on(SECOND) == frozenset(stock(code) for code in CODES[1:])
    assert stock(CODES[0]) in universe.members_on(date(2021, 8, 1))


def test_the_first_day_is_the_first_list_and_nothing_before_it_is_guessed() -> None:
    universe = Lq45Universe(membership())
    assert universe.first_day() == FIRST
    with pytest.raises(MembershipUnknownError, match=r"no LQ45 list in force on 2021-01-29"):
        universe.members_on(date(2021, 1, 29))


def test_exclusions_are_instruments_with_their_reasons() -> None:
    kept_out = Exclusions([Exclusion(CODES[3], FIRST, date(2021, 3, 31), "Special Monitoring")])
    universe = Lq45Universe(membership(), kept_out)
    assert universe.excluded_on(date(2021, 3, 31)) == {stock(CODES[3]): "Special Monitoring"}
    assert universe.excluded_on(date(2021, 4, 1)) == {}


def test_no_exclusions_by_default() -> None:
    assert Lq45Universe(membership()).excluded_on(FIRST) == {}
