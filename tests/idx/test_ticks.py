"""The IDX tick table: tiers chosen by the price itself, lower bounds inclusive (t-rules.md §1)."""

import copy
from datetime import date
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, Dated, load_shipped
from steadyhand_idx.ticks import TickRow, parse_settlement, parse_ticks


@cache
def table() -> Dated[TickRow]:
    return parse_ticks(load_shipped("tick_sizes.toml"))


@cache
def row() -> TickRow:
    return table().on(date(2026, 9, 25))


def test_the_table_is_verified_from_13_march_2020() -> None:
    assert table().first == date(2020, 3, 13)
    assert table().on(date(2020, 3, 13)) is row()
    with pytest.raises(UnsupportedDateError, match=r"tick_sizes\.toml \[ticks\] has no verified"):
        table().on(date(2020, 3, 12))


def test_the_lot_is_100_shares() -> None:
    assert row().lot_size == 100


@pytest.mark.parametrize(
    ("price", "tick"),
    [
        (1, 1), (199, 1), (200, 2), (499, 2), (500, 5), (1_995, 5),
        (1_999, 5), (2_000, 10), (4_990, 10), (4_999, 10), (5_000, 25), (1_000_000, 25),
    ],
)  # fmt: skip
def test_every_tier_boundary_on_both_sides(price: int, tick: int) -> None:
    assert row().tick_for(price) == tick


@pytest.mark.parametrize(
    ("price", "valid"),
    [(199, True), (200, True), (201, False), (4_990, True), (4_995, False), (5_000, True),
     (5_010, False), (5_025, True)],
)  # fmt: skip
def test_validity_uses_the_tier_of_the_price_itself(price: int, valid: object) -> None:
    assert row().is_valid(price) is valid


@pytest.mark.parametrize(
    ("price", "down", "up"),
    [
        (200, 200, 200), (201, 200, 202), (499, 498, 500), (1_999, 1_995, 2_000),
        (4_999, 4_990, 5_000), (5_001, 5_000, 5_025), (5_024, 5_000, 5_025),
    ],
)  # fmt: skip
def test_rounding_lands_on_the_grid(price: int, down: int, up: int) -> None:
    assert row().round_down(price) == down
    assert row().round_up(price) == up


@given(st.integers(min_value=1, max_value=2_000_000))
def test_rounding_is_tight_and_valid(price: int) -> None:
    low, high = row().round_down(price), row().round_up(price)
    assert low <= price <= high
    assert row().is_valid(low)
    assert row().is_valid(high)
    assert not any(row().is_valid(p) for p in range(low + 1, price))
    assert not any(row().is_valid(p) for p in range(price + 1, high))


@pytest.mark.parametrize("price", [0, -5, True, "200"])
def test_a_price_must_be_a_positive_int(price: object) -> None:
    with pytest.raises(ValueError, match=r"price must be a whole number of rupiah of at least 1"):
        row().tick_for(price)  # type: ignore[arg-type]


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("tick_sizes.toml"))


def _row(document: dict[str, object]) -> dict[str, object]:
    found = document["ticks"]
    assert isinstance(found, list)
    row = found[0]
    assert isinstance(row, dict)
    return row


@pytest.mark.parametrize(
    ("tiers", "message"),
    [
        ([], r"row 1: the first tier must start at a price of 1$"),
        ([{"from_price": 2, "tick": 1}], "the first tier must start at a price of 1"),
        (
            [{"from_price": 1, "tick": 1}, {"from_price": 1, "tick": 2}],
            "tiers must rise, got 1 after 1",
        ),
        (
            [{"from_price": 1, "tick": 2}, {"from_price": 201, "tick": 1}],
            r"the tier boundary 201 must be a multiple of both ticks around it \(2 and 1\)",
        ),
        (
            [{"from_price": 1, "tick": 1}, {"from_price": 499, "tick": 5}],
            r"the tier boundary 499 must be a multiple of both ticks around it \(1 and 5\)",
        ),
        ([{"from_price": 1, "tick": 0}], r"row 1, tier 1: tick must be an integer of at least 1"),
        ([{"from_price": 1, "tick": 1, "x": 1}], r"row 1, tier 1: unknown key 'x'"),
        ([5], r"row 1, tier 1 must be an inline table"),
    ],
)
def test_bad_tiers_are_refused(tiers: list[object], message: str) -> None:
    document = _document()
    _row(document)["tiers"] = tiers
    with pytest.raises(DataFileError, match=message):
        parse_ticks(document)


def test_bad_rows_and_documents_are_refused() -> None:
    document = _document()
    _row(document)["lot_size"] = 0
    with pytest.raises(DataFileError, match="lot_size must be an integer of at least 1"):
        parse_ticks(document)
    document = _document()
    document["other"] = 1
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'other'"):
        parse_ticks(document)
    with pytest.raises(DataFileError, match="schema must be 1"):
        parse_ticks({})


def test_settlement_is_t_plus_2_from_26_november_2018() -> None:
    settlement = parse_settlement(load_shipped("tick_sizes.toml"))
    assert settlement.on(date(2018, 11, 26)) == 2
    assert settlement.on(date(2026, 9, 25)) == 2
    with pytest.raises(UnsupportedDateError, match=r"tick_sizes\.toml \[settlement\] has no"):
        settlement.on(date(2018, 11, 23))


def test_bad_settlement_rows_are_refused() -> None:
    document = _document()
    settlement = document["settlement"]
    assert isinstance(settlement, list)
    settlement[0]["trading_days"] = 0
    with pytest.raises(DataFileError, match="trading_days must be an integer of at least 1"):
        parse_settlement(document)
    settlement[0]["trading_days"] = 2
    settlement[0]["note"] = "x"
    with pytest.raises(DataFileError, match=r"\[\[settlement\]\] row 1: unknown key 'note'"):
        parse_settlement(document)
