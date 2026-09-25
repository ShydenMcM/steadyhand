"""IDX auto-rejection bands: tier by reference price, upper bounds inclusive (t-rules.md §3)."""

import copy
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, Dated, load_shipped
from steadyhand_idx.bands import BandRow, parse_bands


@cache
def table() -> Dated[BandRow]:
    return parse_bands(load_shipped("auto_reject.toml"))


type Tier = tuple[int | None, str, str, bool]


def pct(up_to: int | None, up: str, down: str) -> Tier:
    return (up_to, up, down, False)


RUPIAH_1: Tier = (10, "1", "1", True)

# Every period, copied from t-hist.md §4 and t-rules.md §3: (from, minimum price, tiers), each tier
# (inclusive upper reference, up, down, in rupiah). A literal pin against the research.
RESEARCH = [
    (date(2020, 3, 13), 50, [pct(200, "35", "7"), pct(5000, "25", "7"), pct(None, "20", "7")]),
    (date(2023, 6, 5), 50, [pct(200, "35", "15"), pct(5000, "25", "15"), pct(None, "20", "15")]),
    (date(2023, 9, 4), 50, [pct(200, "35", "35"), pct(5000, "25", "25"), pct(None, "20", "20")]),
    (date(2025, 4, 8), 50, [pct(200, "35", "15"), pct(5000, "25", "15"), pct(None, "20", "15")]),
    (
        date(2026, 9, 28),
        1,
        [RUPIAH_1, pct(200, "35", "15"), pct(5000, "25", "15"), pct(None, "20", "15")],
    ),
    (
        date(2027, 1, 1),
        1,
        [RUPIAH_1, pct(200, "35", "35"), pct(5000, "25", "25"), pct(None, "20", "20")],
    ),
]


def test_every_period_matches_the_research() -> None:
    assert table().starts == tuple(start for start, _, _ in RESEARCH)
    for start, min_price, tiers in RESEARCH:
        row = table().on(start)
        assert row.min_price == min_price, start
        found = [(t.up_to, str(t.up), str(t.down), t.in_rupiah) for t in row.tiers]
        assert found == tiers, start


def test_the_table_is_verified_from_13_march_2020() -> None:
    with pytest.raises(UnsupportedDateError, match=r"auto_reject\.toml \[bands\] has no verified"):
        table().on(date(2020, 3, 12))


@pytest.mark.parametrize(
    ("on", "reference", "up"),
    [
        (date(2025, 4, 8), 200, "35"),  # 200 is in the LOWER tier here, unlike the tick table
        (date(2025, 4, 8), 201, "25"),
        (date(2025, 4, 8), 5_000, "25"),
        (date(2025, 4, 8), 5_001, "20"),
        (date(2026, 9, 28), 10, "1"),
        (date(2026, 9, 28), 11, "35"),
    ],
)
def test_the_tier_edges_are_inclusive_of_the_upper_bound(on: date, reference: int, up: str) -> None:
    assert table().on(on).tier_for(reference).up == Decimal(up)


def test_percentage_limits_are_exact() -> None:
    assert table().on(date(2025, 4, 8)).limits(1_000) == (Decimal(850), Decimal(1_250))
    assert table().on(date(2020, 3, 13)).limits(155) == (Decimal("144.15"), Decimal("209.25"))


def test_rupiah_limits_are_one_either_way() -> None:
    assert table().on(date(2026, 9, 28)).limits(7) == (Decimal(6), Decimal(8))


@pytest.mark.parametrize("reference", [0, -1, True])
def test_a_reference_must_be_a_positive_int(reference: int) -> None:
    with pytest.raises(
        ValueError, match="reference must be a whole number of rupiah of at least 1"
    ):
        table().on(date(2025, 4, 8)).tier_for(reference)


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("auto_reject.toml"))


def _first_row(document: dict[str, object]) -> dict[str, object]:
    found = document["bands"]
    assert isinstance(found, list)
    row = found[0]
    assert isinstance(row, dict)
    return row


TOP = {"up_percent": "20", "down_percent": "7"}


@pytest.mark.parametrize(
    ("tiers", "message"),
    [
        ([{"up_to": 200, **TOP}], r"row 1, tier 1: the top tier has no up_to"),
        ([{"up_percent": "20"}, TOP], r"row 1, tier 1: missing key 'up_to'"),
        (
            [{"up_to": 200, "up_percent": "35", "down_rupiah": 1}, TOP],
            "give the band in percent or in rupiah, not both",
        ),
        ([{"up_to": 10, "down_rupiah": 1}, TOP], "missing key 'up_rupiah'"),
        (
            [{"up_percent": "0", "down_percent": "7"}],
            "percentages must be above 0, and down below 100",
        ),
        ([{"up_percent": "20", "down_percent": "100"}], "percentages must be above 0"),
        ([{"up_to": 20, **TOP}, TOP], "the first tier ends at 20, below the minimum price 50"),
        (
            [{"up_to": 200, **TOP}, {"up_to": 200, **TOP}, TOP],
            "tier bounds must rise, got 200 after 200",
        ),
        ([{**TOP, "note": "x"}], "unknown key 'note'"),
    ],
)
def test_bad_tiers_are_refused(tiers: list[dict[str, object]], message: str) -> None:
    document = _document()
    _first_row(document)["tiers"] = tiers
    with pytest.raises(DataFileError, match=message):
        parse_bands(document)


def test_bad_documents_are_refused() -> None:
    document = _document()
    document["x"] = 1
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'x'"):
        parse_bands(document)
    document = _document()
    _first_row(document)["min_price"] = 0
    with pytest.raises(DataFileError, match="min_price must be an integer of at least 1"):
        parse_bands(document)
