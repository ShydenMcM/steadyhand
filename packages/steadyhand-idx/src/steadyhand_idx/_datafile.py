"""Reading the TOML data files: the ones shipped in ``data/`` and the ones a user supplies.

Every value is read through a typed getter that names the file, the table, the row and the key
in its error, so a bad file says exactly where it is bad. Unknown keys are refused, because a
misspelt key would otherwise be silently ignored and its default used instead.
"""

from __future__ import annotations

import tomllib
from bisect import bisect_right
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import resources
from itertools import pairwise
from pathlib import Path
from typing import cast

from steadyhand import UnsupportedDateError

type Row = Mapping[str, object]


class DataFileError(ValueError):
    """A data file is malformed. The message names the file, the row and the key."""


@dataclass(frozen=True, slots=True)
class Where:
    """A position in a data file, for error messages: ``fees.toml [[levy]] row 2``."""

    file: str
    table: str
    row: int | None = None
    part: str | None = None

    def __str__(self) -> str:
        if self.row is None:
            place = f"{self.file} [{self.table}]"
        else:
            place = f"{self.file} [[{self.table}]] row {self.row}"
        return place if self.part is None else f"{place}, {self.part}"

    def at(self, row: int) -> Where:
        """The same table, at *row* (counted from 1)."""
        return Where(self.file, self.table, row)

    def within(self, part: str) -> Where:
        """A named part of this row, such as ``tier 2``."""
        return Where(self.file, self.table, self.row, part)


def load_shipped(name: str) -> dict[str, object]:
    """Parse ``steadyhand_idx/data/<name>``."""
    text = resources.files("steadyhand_idx").joinpath("data", name).read_text(encoding="utf-8")
    return _parse(text, name)


def load_path(path: Path) -> dict[str, object]:
    """Parse a user-supplied file. A missing file is a ``FileNotFoundError`` naming the path."""
    return _parse(path.read_text(encoding="utf-8"), path.name)


def _parse(text: str, name: str) -> dict[str, object]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        msg = f"{name} is not valid TOML: {error}"
        raise DataFileError(msg) from error


def require_schema(document: Row, file: str, version: int) -> None:
    found = document.get("schema")
    if found != version:
        msg = f"{file}: schema must be {version}, got {found!r}"
        raise DataFileError(msg)


def rows(document: Row, table: str, where: Where) -> list[Row]:
    """The rows of an array of tables, at least one of them, each a mapping."""
    found = document.get(table)
    if not isinstance(found, list) or not found:
        msg = f"{where} must be a non-empty array of tables"
        raise DataFileError(msg)
    for index, row in enumerate(found, start=1):
        if not isinstance(row, dict):
            msg = f"{where.at(index)} must be a table"
            raise DataFileError(msg)
    return cast("list[Row]", found)


def only_keys(row: Row, allowed: Collection[str], where: Where) -> None:
    unknown = sorted(set(row) - set(allowed))
    if unknown:
        msg = f"{where}: unknown key {unknown[0]!r}"
        raise DataFileError(msg)


def _get(row: Row, key: str, where: Where) -> object:
    if key not in row:
        msg = f"{where}: missing key {key!r}"
        raise DataFileError(msg)
    return row[key]


def _wrong(where: Where, key: str, expected: str, value: object) -> DataFileError:
    return DataFileError(f"{where}: {key} must be {expected}, got {value!r}")


def as_date(value: object, what: str) -> date:
    """*value* as a plain ``date``; TOML gives a ``datetime`` for a value with a time, refused."""
    if isinstance(value, datetime) or not isinstance(value, date):
        msg = f"{what} must be a TOML date such as 2021-01-04, got {value!r}"
        raise DataFileError(msg)
    return value


def get_date(row: Row, key: str, where: Where) -> date:
    return as_date(_get(row, key, where), f"{where}: {key}")


def get_int(row: Row, key: str, where: Where, *, minimum: int) -> int:
    value = _get(row, key, where)
    if type(value) is not int or value < minimum:
        raise _wrong(where, key, f"an integer of at least {minimum}", value)
    return value


def get_str(row: Row, key: str, where: Where) -> str:
    value = _get(row, key, where)
    if not isinstance(value, str) or not value.strip():
        raise _wrong(where, key, "a non-empty string", value)
    return value


def get_decimal(row: Row, key: str, where: Where) -> Decimal:
    """A rate written as a string (``"0.018"``), so no float is ever involved (spec §9.5)."""
    value = _get(row, key, where)
    if not isinstance(value, str):
        raise _wrong(where, key, 'a decimal written as a string, such as "0.018"', value)
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise _wrong(where, key, "a decimal number", value) from None
    if not number.is_finite() or number < 0:
        raise _wrong(where, key, "a finite decimal of at least 0", value)
    return number


def get_list(row: Row, key: str, where: Where) -> Sequence[object]:
    value = _get(row, key, where)
    if not isinstance(value, list):
        raise _wrong(where, key, "an array", value)
    return cast("list[object]", value)


def get_tables(row: Row, key: str, where: Where, *, label: str) -> list[tuple[Row, Where]]:
    """An array of inline tables, each paired with its place (``..., tier 2``) for errors."""
    found: list[tuple[Row, Where]] = []
    for index, value in enumerate(get_list(row, key, where), start=1):
        place = where.within(f"{label} {index}")
        if not isinstance(value, dict):
            msg = f"{place} must be an inline table"
            raise DataFileError(msg)
        found.append((cast("Row", value), place))
    return found


@dataclass(frozen=True, slots=True)
class Dated[T]:
    """Rows that each apply from their ``from`` date until the next row's.

    The first row's date is the first day the table can answer for. An earlier day raises
    ``UnsupportedDateError`` naming the table: a rule is never assumed for a date nobody verified.
    """

    where: Where
    starts: tuple[date, ...]
    values: tuple[T, ...]

    def __post_init__(self) -> None:
        if not self.starts or len(self.starts) != len(self.values):
            msg = f"{self.where}: needs one value per start date, and at least one"
            raise DataFileError(msg)
        for earlier, later in pairwise(self.starts):
            if later <= earlier:
                msg = f"{self.where}: from dates must increase, got {later} after {earlier}"
                raise DataFileError(msg)

    @property
    def first(self) -> date:
        return self.starts[0]

    def on(self, day: date) -> T:
        if day < self.first:
            msg = (
                f"{self.where} has no verified row for {day.isoformat()}: "
                f"its first row applies from {self.first.isoformat()}"
            )
            raise UnsupportedDateError(msg)
        return self.values[bisect_right(self.starts, day) - 1]
