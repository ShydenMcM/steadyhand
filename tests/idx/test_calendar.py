"""The IDX trading calendar: IDX's own holiday lists, each year's arithmetic checked on load."""

import copy
from datetime import date
from functools import cache

import pytest

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, load_shipped
from steadyhand_idx.calendar import HolidayYear, IdxCalendar, parse_holidays


@cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


# Holidays and IDX's stated trading-day total per year, copied from the research docs
# (t-hist.md §1, t-pay.md §2, t-rules.md §4). A literal pin: the loader's own arithmetic check
# derives from the file, so it cannot notice a year that went missing with its total.
RESEARCH = {
    2016: (15, 246), 2017: (22, 238), 2018: (21, 240), 2019: (16, 245),
    2020: (20, 242), 2021: (14, 247), 2022: (14, 246), 2023: (21, 239),
    2024: (25, 237), 2025: (25, 236), 2026: (22, 239), 2027: (20, 241),
}  # fmt: skip


def weekdays(year: int) -> int:
    days = range(date(year, 1, 1).toordinal(), date(year + 1, 1, 1).toordinal())
    return sum(1 for day in days if date.fromordinal(day).weekday() < 5)


def test_the_shipped_calendar_covers_2016_to_2027() -> None:
    assert calendar().first_day == date(2016, 1, 1)
    assert calendar().last_day == date(2027, 12, 31)


@pytest.mark.parametrize(("year", "expected"), sorted(RESEARCH.items()))
def test_each_year_matches_the_research(year: int, expected: tuple[int, int]) -> None:
    holidays, trading_days = expected
    days = calendar().trading_days(date(year, 1, 1), date(year, 12, 31))
    assert len(days) == trading_days
    assert weekdays(year) - len(days) == holidays


def test_the_2021_to_2025_window_has_the_1205_days_yahoo_has_bars_for() -> None:
    # Measured on 2026-09-25: 25 large IDX stocks each had exactly 1,205 Yahoo bars in this window.
    assert len(calendar().trading_days(date(2021, 1, 1), date(2025, 12, 31))) == 1205


@pytest.mark.parametrize(
    ("day", "status", "why"),
    [
        (date(2026, 9, 22), "open", "Yahoo's ^JKSE has no bar, but IDX traded (t-pay.md §2)"),
        (date(2018, 6, 27), "open", "election-day holiday, but Peng-00504 kept IDX open"),
        (date(2022, 5, 4), "closed", "Eid leave added by the 2022 calendar's version 2"),
        (date(2025, 8, 18), "closed", "added to 2025 by Peng-00149/BEI.POP/08-2025"),
        (date(2026, 12, 31), "closed", "the exchange's year-end holiday"),
        (date(2026, 9, 26), "closed", "a Saturday"),
        (date(2026, 9, 27), "closed", "a Sunday"),
        (date(2026, 9, 28), "open", "an ordinary Monday"),
    ],
)
def test_known_days(day: date, status: str, why: str) -> None:
    assert calendar().is_trading_day(day) is (status == "open"), why


@pytest.mark.parametrize("day", [date(2015, 12, 31), date(2028, 1, 3)])
def test_a_year_without_holiday_data_is_refused(day: date) -> None:
    with pytest.raises(
        UnsupportedDateError,
        match=(
            rf"^holidays\.toml has no IDX holidays for {day.year}, so its trading days are "
            r"unknown; it covers 2016 to 2027$"
        ),
    ):
        calendar().is_trading_day(day)


def test_next_and_previous_cross_holidays_weekends_and_the_year_end() -> None:
    assert calendar().next_trading_day(date(2026, 12, 30)) == date(2027, 1, 4)
    assert calendar().previous_trading_day(date(2027, 1, 4)) == date(2026, 12, 30)
    assert calendar().next_trading_day(date(2026, 9, 25)) == date(2026, 9, 28)
    assert calendar().previous_trading_day(date(2026, 9, 28)) == date(2026, 9, 25)


def test_add_trading_days_counts_from_the_day_after() -> None:
    # Eid 2026: 18-20 and 23-24 March are holidays, 21-22 a weekend.
    assert calendar().add_trading_days(date(2026, 3, 17), 1) == date(2026, 3, 25)
    assert calendar().add_trading_days(date(2026, 3, 17), 2) == date(2026, 3, 26)
    # A non-trading start day is allowed: the count starts on the day after it.
    assert calendar().add_trading_days(date(2026, 3, 21), 1) == date(2026, 3, 25)


def test_counting_past_the_last_year_is_refused() -> None:
    with pytest.raises(UnsupportedDateError, match="no IDX holidays for 2028"):
        calendar().add_trading_days(date(2027, 12, 30), 2)


@pytest.mark.parametrize("count", [0, -1, True])
def test_add_trading_days_needs_a_positive_int(count: int) -> None:
    with pytest.raises(ValueError, match=rf"^count must be an int of at least 1, got {count!r}$"):
        calendar().add_trading_days(date(2026, 3, 17), count)


def test_trading_days_is_inclusive_and_refuses_a_reversed_range() -> None:
    assert calendar().trading_days(date(2026, 9, 25), date(2026, 9, 28)) == (
        date(2026, 9, 25),
        date(2026, 9, 28),
    )
    with pytest.raises(ValueError, match=r"^end 2026-09-24 is before start 2026-09-25$"):
        calendar().trading_days(date(2026, 9, 25), date(2026, 9, 24))


def test_each_year_names_its_source() -> None:
    assert calendar().source(2026) == "Peng-00171/BEI.POP/09-2025"
    with pytest.raises(UnsupportedDateError, match="no IDX holidays for 2030"):
        calendar().source(2030)


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("holidays.toml"))


def _years(document: dict[str, object]) -> list[dict[str, object]]:
    found = document["year"]
    assert isinstance(found, list)
    return found


def test_a_dropped_holiday_fails_the_arithmetic_check() -> None:
    document = _document()
    first = _years(document)[0]
    holidays = first["holidays"]
    assert isinstance(holidays, list)
    first["holidays"] = holidays[1:]
    with pytest.raises(
        DataFileError,
        match=(
            r"^holidays\.toml \[\[year\]\] row 1: 2016 has 247 weekdays that are not holidays, "
            r"but the calendar states 246 trading days$"
        ),
    ):
        parse_holidays(document)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"holidays": [date(2017, 1, 2)]}, r"2017-01-02 is not in 2016"),
        ({"holidays": [date(2016, 1, 2)]}, r"2016-01-02 is a weekend"),
        (
            {"holidays": [date(2016, 1, 4), date(2016, 1, 4)]},
            r"holidays must be listed once each, in order; 2016-01-04 is not",
        ),
        ({"holidays": ["2016-01-04"]}, r"holiday 1 must be a TOML date"),
        ({"source": ""}, r"source must be a non-empty string"),
        ({"note": "x"}, r"unknown key 'note'"),
    ],
)
def test_bad_year_rows_are_refused(change: dict[str, object], message: str) -> None:
    document = _document()
    _years(document)[0].update(change)
    with pytest.raises(DataFileError, match=message):
        parse_holidays(document)


def test_years_must_be_consecutive() -> None:
    document = _document()
    del _years(document)[1]
    with pytest.raises(DataFileError, match="years must be consecutive, got 2018 after 2016"):
        parse_holidays(document)


def test_the_top_level_is_checked() -> None:
    document = _document()
    document["extra"] = 1
    with pytest.raises(DataFileError, match=r"holidays\.toml \[top level\]: unknown key 'extra'"):
        parse_holidays(document)
    with pytest.raises(DataFileError, match="schema must be 1"):
        parse_holidays({"schema": 2})


def test_a_calendar_needs_a_year() -> None:
    with pytest.raises(DataFileError, match="a calendar needs at least one year"):
        IdxCalendar([])


def test_a_calendar_built_by_hand_uses_its_own_years() -> None:
    year = HolidayYear(2030, "test", 261, frozenset())
    calendar = IdxCalendar([year], file="mine.toml")
    assert calendar.is_trading_day(date(2030, 1, 1))
    with pytest.raises(UnsupportedDateError, match=r"^mine\.toml has no IDX holidays for 2031"):
        calendar.is_trading_day(date(2031, 1, 1))


def test_require_covered_refuses_a_year_without_data() -> None:
    calendar().require_covered(date(2027, 12, 31))
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2028"):
        calendar().require_covered(date(2028, 1, 3))
