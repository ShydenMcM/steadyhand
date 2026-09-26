"""The shared checks refuse the look-alike types that Python's subclassing lets through."""

import re
from datetime import UTC, date, datetime

import pytest

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.risk import UnitValue


def test_require_date_accepts_a_date() -> None:
    require_date(date(2026, 1, 5), "day")


def test_require_date_refuses_a_datetime() -> None:
    with pytest.raises(TypeError, match="day must be a date, got datetime"):
        require_date(datetime(2026, 1, 5, tzinfo=UTC), "day")


def test_require_date_refuses_a_string() -> None:
    with pytest.raises(TypeError, match="day must be a date, got str"):
        require_date("2026-01-05", "day")


def test_require_int_accepts_the_minimum() -> None:
    require_int(1, "quantity", minimum=1)


def test_require_int_refuses_one_below_the_minimum() -> None:
    with pytest.raises(ValueError, match="quantity must be at least 1, got 0"):
        require_int(0, "quantity", minimum=1)


@pytest.mark.parametrize(("value", "name"), [(True, "bool"), ("1", "str"), (None, "NoneType")])
def test_require_int_refuses_non_ints(value: object, name: str) -> None:
    with pytest.raises(TypeError, match=f"quantity must be an int, got {name}"):
        require_int(value, "quantity", minimum=1)


def test_require_type_accepts_an_instance() -> None:
    require_type("BBRI", str, "symbol")
    require_type(True, bool, "accepted")


@pytest.mark.parametrize(
    ("value", "expected", "message"),
    [
        (None, str, "symbol must be a str, got NoneType"),
        (1, bool, "symbol must be a bool, got int"),
        ("x", date, "symbol must be a date, got str"),
    ],
)
def test_require_type_names_the_field_and_the_type(
    value: object, expected: type, message: str
) -> None:
    with pytest.raises(TypeError, match=f"^{re.escape(message)}$"):
        require_type(value, expected, "symbol")


def test_require_type_uses_an_before_a_vowel() -> None:
    with pytest.raises(TypeError, match=r"^order must be an int, got str$"):
        require_type("1", int, "order")


def test_require_type_uses_a_before_a_u_that_sounds_like_you() -> None:
    with pytest.raises(TypeError, match=r"^units must be a UnitValue, got int$"):
        require_type(1, UnitValue, "units")
