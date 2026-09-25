"""The data-file reader: typed getters whose errors name the file, row and key."""

import tomllib
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Where,
    as_date,
    get_date,
    get_decimal,
    get_int,
    get_list,
    get_str,
    get_tables,
    load_path,
    load_shipped,
    only_keys,
    require_schema,
    rows,
)

HERE = Where("fees.toml", "levy", 2)


def test_where_names_the_file_table_and_row() -> None:
    assert str(HERE) == "fees.toml [[levy]] row 2"
    assert str(Where("fees.toml", "presets")) == "fees.toml [presets]"
    assert str(Where("fees.toml", "levy").at(3)) == "fees.toml [[levy]] row 3"


def test_shipped_files_are_read_from_the_package() -> None:
    assert load_shipped("holidays.toml")["schema"] == 1


def test_invalid_toml_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "lq45_members.toml"
    path.write_text("schema = \n", encoding="utf-8")
    with pytest.raises(DataFileError, match=r"^lq45_members\.toml is not valid TOML"):
        load_path(path)


def test_a_missing_user_file_names_its_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"nothing\.toml"):
        load_path(tmp_path / "nothing.toml")


def test_user_files_parse(tmp_path: Path) -> None:
    path = tmp_path / "x.toml"
    path.write_text("schema = 1\n", encoding="utf-8")
    assert load_path(path) == {"schema": 1}


def test_schema_must_match() -> None:
    require_schema({"schema": 1}, "x.toml", 1)
    with pytest.raises(DataFileError, match=r"^x\.toml: schema must be 1, got 2$"):
        require_schema({"schema": 2}, "x.toml", 1)
    with pytest.raises(DataFileError, match="got None"):
        require_schema({}, "x.toml", 1)


def test_rows_must_be_a_non_empty_array_of_tables() -> None:
    where = Where("x.toml", "levy")
    assert rows({"levy": [{"a": 1}]}, "levy", where) == [{"a": 1}]
    bad_documents: list[dict[str, object]] = [{}, {"levy": []}, {"levy": {"a": 1}}]
    for bad in bad_documents:
        with pytest.raises(DataFileError, match=r"x\.toml \[levy\] must be a non-empty array"):
            rows(bad, "levy", where)
    with pytest.raises(DataFileError, match=r"x\.toml \[\[levy\]\] row 2 must be a table"):
        rows({"levy": [{"a": 1}, 5]}, "levy", where)


def test_unknown_keys_are_refused() -> None:
    only_keys({"from": 1}, {"from", "rate"}, HERE)
    with pytest.raises(DataFileError, match=r"row 2: unknown key 'rat'$"):
        only_keys({"from": 1, "rat": 2}, {"from", "rate"}, HERE)


def test_missing_keys_are_named() -> None:
    with pytest.raises(DataFileError, match=r"row 2: missing key 'rate'$"):
        get_decimal({}, "rate", HERE)


def test_dates_must_be_plain_toml_dates() -> None:
    document = tomllib.loads("a = 2021-01-04\nb = 2021-01-04T09:00:00\nc = '2021-01-04'")
    assert get_date(document, "a", HERE) == date(2021, 1, 4)
    for key in ("b", "c"):
        with pytest.raises(DataFileError, match=rf"row 2: {key} must be a TOML date"):
            get_date(document, key, HERE)
    assert as_date(date(2021, 1, 4), "x") == date(2021, 1, 4)
    with pytest.raises(DataFileError, match=r"^holiday 3 must be a TOML date"):
        as_date(datetime(2021, 1, 4, 9, 0), "holiday 3")  # noqa: DTZ001 - naive on purpose


def test_ints_must_be_ints_at_or_above_the_minimum() -> None:
    assert get_int({"n": 100}, "n", HERE, minimum=1) == 100
    for bad in (0, True, "100", 1.0):
        with pytest.raises(DataFileError, match="n must be an integer of at least 1"):
            get_int({"n": bad}, "n", HERE, minimum=1)


def test_strings_must_be_non_empty() -> None:
    assert get_str({"s": "IDX"}, "s", HERE) == "IDX"
    for bad in ("", "  ", 5):
        with pytest.raises(DataFileError, match="s must be a non-empty string"):
            get_str({"s": bad}, "s", HERE)


def test_decimals_are_written_as_strings_and_never_negative() -> None:
    assert get_decimal({"r": "0.018"}, "r", HERE) == Decimal("0.018")
    assert get_decimal({"r": "0"}, "r", HERE) == 0
    with pytest.raises(DataFileError, match="r must be a decimal written as a string"):
        get_decimal({"r": 0.018}, "r", HERE)
    with pytest.raises(DataFileError, match="r must be a decimal number, got 'abc'"):
        get_decimal({"r": "abc"}, "r", HERE)
    for bad in ("NaN", "Infinity", "-0.1"):
        with pytest.raises(DataFileError, match="r must be a finite decimal of at least 0"):
            get_decimal({"r": bad}, "r", HERE)


def test_lists_must_be_arrays() -> None:
    assert get_list({"l": [1]}, "l", HERE) == [1]
    with pytest.raises(DataFileError, match="l must be an array"):
        get_list({"l": "a"}, "l", HERE)


def test_a_dated_table_answers_from_each_row_until_the_next() -> None:
    table = Dated(Where("t.toml", "t"), (date(2020, 3, 13), date(2023, 6, 5)), ("a", "b"))
    assert table.first == date(2020, 3, 13)
    assert table.on(date(2020, 3, 13)) == "a"
    assert table.on(date(2023, 6, 4)) == "a"
    assert table.on(date(2023, 6, 5)) == "b"
    assert table.on(date(2040, 1, 1)) == "b"


def test_a_dated_table_refuses_a_day_before_its_first_row() -> None:
    table = Dated(Where("tick_sizes.toml", "ticks"), (date(2020, 3, 13),), ("a",))
    with pytest.raises(
        UnsupportedDateError,
        match=(
            r"^tick_sizes\.toml \[ticks\] has no verified row for 2020-03-12: "
            r"its first row applies from 2020-03-13$"
        ),
    ):
        table.on(date(2020, 3, 12))


def test_a_dated_table_needs_increasing_dates_and_one_value_each() -> None:
    where = Where("t.toml", "t")
    with pytest.raises(DataFileError, match="from dates must increase, got 2020-01-01 after"):
        Dated(where, (date(2020, 1, 1), date(2020, 1, 1)), ("a", "b"))
    with pytest.raises(DataFileError, match="needs one value per start date, and at least one"):
        Dated(where, (), ())
    with pytest.raises(DataFileError, match="needs one value per start date"):
        Dated(where, (date(2020, 1, 1),), ("a", "b"))


def test_a_part_of_a_row_is_named_after_the_row() -> None:
    assert str(HERE.within("tier 2")) == "fees.toml [[levy]] row 2, tier 2"


def test_inline_tables_come_with_their_place() -> None:
    row = {"tiers": [{"tick": 1}, {"tick": 2}]}
    found = get_tables(row, "tiers", HERE, label="tier")
    assert [(table, str(place)) for table, place in found] == [
        ({"tick": 1}, "fees.toml [[levy]] row 2, tier 1"),
        ({"tick": 2}, "fees.toml [[levy]] row 2, tier 2"),
    ]
    with pytest.raises(
        DataFileError, match=r"^fees\.toml \[\[levy\]\] row 2, tier 1 must be an inline table$"
    ):
        get_tables({"tiers": [5]}, "tiers", HERE, label="tier")
