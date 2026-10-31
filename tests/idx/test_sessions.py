"""The IDX regular-market times core needs, from ``data/sessions.toml`` (t-rules.md §5, #225)."""

import copy
from datetime import date, time
from functools import cache

import pytest

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, Dated, load_shipped
from steadyhand_idx.sessions import SESSIONS_FILE, SessionRow, parse_sessions


@cache
def table() -> Dated[SessionRow]:
    return parse_sessions(load_shipped(SESSIONS_FILE))


def shipped() -> dict[str, object]:
    return copy.deepcopy(load_shipped(SESSIONS_FILE))


def test_the_table_is_verified_from_8_april_2025() -> None:
    assert table().first == date(2025, 4, 8)
    with pytest.raises(UnsupportedDateError, match=r"sessions\.toml \[sessions\] has no verified"):
        table().on(date(2025, 4, 7))


def test_the_current_row_is_ii_a_2026() -> None:
    row = table().on(date(2026, 10, 30))
    assert row.pre_opening_from == time(8, 45, 0)
    assert row.closing_match_until == time(16, 1, 59)
    assert "Kep-00136/BEI/09-2026" in row.source


def test_a_row_with_an_unknown_key_is_refused() -> None:
    document = shipped()
    document["sessions"][0]["post_closing_until"] = time(16, 15)  # type: ignore[index]
    with pytest.raises(DataFileError, match="post_closing_until"):
        parse_sessions(document)


@pytest.mark.parametrize("key", ["pre_opening_from", "closing_match_until"])
def test_a_time_that_is_not_a_time_is_refused(key: str) -> None:
    document = shipped()
    document["sessions"][0][key] = "08:45:00"  # type: ignore[index]
    with pytest.raises(DataFileError, match=f"{key} must be a time of day"):
        parse_sessions(document)


def test_pre_opening_must_start_before_the_closing_match_ends() -> None:
    document = shipped()
    document["sessions"][0]["pre_opening_from"] = time(16, 1, 59)  # type: ignore[index]
    with pytest.raises(DataFileError, match="pre-opening must start before"):
        parse_sessions(document)


def test_a_document_with_an_unknown_table_is_refused() -> None:
    document = shipped()
    document["breaks"] = []
    with pytest.raises(DataFileError, match="breaks"):
        parse_sessions(document)
