"""The user-supplied LQ45 file and exclusions. Every list here is synthetic (t-lq45.md §5)."""

from datetime import date
from itertools import product
from pathlib import Path

import pytest

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.universe import (
    Exclusions,
    Lq45Membership,
    Lq45Record,
    MembershipUnknownError,
)

# 45 made-up four-letter codes. No real LQ45 list is ever written into this repository.
CODES = ["Z" + "".join(letters) for letters in product("ABCDEFGHIJ", repeat=3)][:60]


def record_toml(effective: str, announced: str, members: list[str], kind: str = "review") -> str:
    quoted = ", ".join(f'"{code}"' for code in members)
    return (
        f"[[record]]\neffective = {effective}\nannounced = {announced}\n"
        f'source = "Peng-test/{effective}"\nkind = "{kind}"\nmembers = [{quoted}]\n'
    )


def write(tmp_path: Path, *records: str) -> Path:
    path = tmp_path / "lq45_members.toml"
    path.write_text("schema = 1\n\n" + "\n".join(records), encoding="utf-8")
    return path


# Semi-annual until January 2024, quarterly from May 2024; Feb 2023 is missing on purpose.
DATES = [
    ("2022-08-01", "2022-07-25"),
    ("2023-08-01", "2023-07-25"),
    ("2024-02-01", "2024-01-25"),
    ("2024-05-02", "2024-04-24"),
    ("2024-08-01", "2024-07-25"),
    ("2025-02-03", "2025-01-22"),
]


@pytest.fixture
def membership(tmp_path: Path) -> Lq45Membership:
    records = [record_toml(e, a, CODES[i : i + 45]) for i, (e, a) in enumerate(DATES)]
    return Lq45Membership.load(write(tmp_path, *records))


def test_membership_is_the_latest_list_in_force(membership: Lq45Membership) -> None:
    assert membership.members_on(date(2022, 8, 1)) == frozenset(CODES[0:45])
    assert membership.members_on(date(2024, 1, 31)) == frozenset(CODES[1:46])
    assert membership.members_on(date(2024, 2, 1)) == frozenset(CODES[2:47])
    with pytest.raises(
        MembershipUnknownError,
        match=r"^lq45_members\.toml has no LQ45 list in force on 2022-07-29; its first takes",
    ):
        membership.members_on(date(2022, 7, 29))


def test_gaps_are_records_more_than_one_review_apart(membership: Lq45Membership) -> None:
    # Aug 2022 -> Aug 2023 skips Feb 2023 (12 months > 6); Aug 2024 -> Feb 2025 skips Nov 2024
    # (6 months > 3 once reviews are quarterly). Jan 2024 -> May 2024 is 3 months: no gap.
    assert [(a.effective, b.effective) for a, b in membership.gaps()] == [
        (date(2022, 8, 1), date(2023, 8, 1)),
        (date(2024, 8, 1), date(2025, 2, 3)),
    ]


def test_warnings_for_an_early_start_and_each_gap_spanned(membership: Lq45Membership) -> None:
    warnings = membership.survivorship_warnings(date(2021, 1, 4), date(2023, 12, 29))
    assert len(warnings) == 2
    assert warnings[0].startswith(
        "Survivorship bias: the backtest starts on 2021-01-04, before the first LQ45 list in "
        "lq45_members.toml (2022-08-01, Peng-test/2022-08-01)."
    )
    assert "no LQ45 list between 2022-08-01" in warnings[1]
    assert "and 2023-08-01 (Peng-test/2023-08-01), more than one review apart" in warnings[1]
    assert membership.survivorship_warnings(date(2024, 2, 1), date(2024, 7, 31)) == []
    later = membership.survivorship_warnings(date(2024, 9, 2), date(2025, 3, 3))
    assert [w.split(" between ")[1][:10] for w in later] == ["2024-08-01"]


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (
            record_toml("2024-02-01", "2024-02-02", CODES[:45]),
            "announced 2024-02-02 is after effective",
        ),
        (record_toml("2024-02-01", "2024-01-25", CODES[:45], "annual"), "kind must be 'review' or"),
        (
            record_toml("2024-02-01", "2024-01-25", CODES[:44]),
            "members must list 45 different codes, got 44 of 44",
        ),
        (
            record_toml("2024-02-01", "2024-01-25", [*CODES[:44], CODES[0]]),
            "members must list 45 different codes, got 44 of 45",
        ),
        (
            record_toml("2024-02-01", "2024-01-25", [*CODES[:44], "BBCA.JK"]),
            r"members must be four-letter IDX codes, got 'BBCA\.JK'",
        ),
    ],
    ids=["announced-late", "kind", "44-codes", "duplicate", "not-a-code"],
)
def test_bad_records_are_refused(tmp_path: Path, record: str, message: str) -> None:
    with pytest.raises(
        DataFileError, match=rf"^lq45_members\.toml \[\[record\]\] row 1: {message}"
    ):
        Lq45Membership.load(write(tmp_path, record))


def test_records_must_be_in_order(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        record_toml("2024-05-02", "2024-04-24", CODES[:45]),
        record_toml("2024-02-01", "2024-01-25", CODES[:45]),
    )
    with pytest.raises(
        DataFileError, match="must be in effective-date order, got 2024-02-01 after"
    ):
        Lq45Membership.load(path)
    with pytest.raises(DataFileError, match=r"^mine\.toml: needs at least one record$"):
        Lq45Membership([], file="mine.toml")


def test_a_missing_file_names_the_config_key(tmp_path: Path) -> None:
    with pytest.raises(
        FileNotFoundError,
        match=r"^\[universe\] lq45_members points to .*nothing\.toml, which does not exist\. "
        r"steadyhand does not ship LQ45 lists",
    ):
        Lq45Membership.load(tmp_path / "nothing.toml")


def test_the_records_are_kept(membership: Lq45Membership) -> None:
    first = membership.records[0]
    assert first == Lq45Record(
        date(2022, 8, 1), date(2022, 7, 25), "Peng-test/2022-08-01", "review", frozenset(CODES[:45])
    )


def exclusions(tmp_path: Path, text: str) -> Exclusions:
    path = tmp_path / "exclusions.csv"
    path.write_text(text, encoding="utf-8")
    return Exclusions.load(path)


def test_exclusions_apply_between_their_dates(tmp_path: Path) -> None:
    found = exclusions(
        tmp_path,
        "symbol,from,to,reason\n"
        "ZAAA,2024-01-02,2024-06-28,Special Monitoring Board\n"
        "ZAAB,2025-01-02,,I do not want to own it\n",
    )
    assert found.excluded_on(date(2024, 1, 1)) == {}
    assert found.excluded_on(date(2024, 6, 28)) == {"ZAAA": "Special Monitoring Board"}
    assert found.excluded_on(date(2026, 9, 25)) == {"ZAAB": "I do not want to own it"}


def test_no_exclusions_file_means_no_exclusions(tmp_path: Path) -> None:
    assert Exclusions.load(tmp_path / "absent.csv").excluded_on(date(2026, 9, 25)) == {}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", r"the first line must be symbol,from,to,reason"),
        ("sym,from,to,reason\n", r"the first line must be symbol,from,to,reason"),
        ("symbol,from,to,reason\nZAAA,2024-01-02\n", r"line 2: needs 4 fields, got 2"),
        ("symbol,from,to,reason\nzaaa,2024-01-02,,x\n", r"line 2: 'zaaa' is not an IDX symbol"),
        (
            "symbol,from,to,reason\nZAAA,02/01/2024,,x\n",
            r"line 2: dates must be written 2026-09-25",
        ),
        (
            "symbol,from,to,reason\nZAAA,2024-01-02,2023-01-02,x\n",
            r"line 2: to 2023-01-02 is before",
        ),
        ("symbol,from,to,reason\nZAAA,2024-01-02,, \n", r"line 2: give a reason"),
    ],
)
def test_bad_exclusions_are_refused(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(DataFileError, match=rf"^exclusions\.csv.*{message}"):
        exclusions(tmp_path, text)
