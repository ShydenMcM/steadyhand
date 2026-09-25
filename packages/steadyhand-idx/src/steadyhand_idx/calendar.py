"""IDX trading days, from the holiday calendars in ``data/holidays.toml`` (spec §9.1).

Trading days come from IDX's own calendars and never from which days have price bars: Yahoo's
index series has no bar for 22 Sep 2026, which was a trading day (docs/research/t-pay.md §2).
A year with no holiday data is refused rather than assumed to have no holidays.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from itertools import pairwise

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import (
    DataFileError,
    Row,
    Where,
    as_date,
    get_int,
    get_list,
    get_str,
    load_shipped,
    only_keys,
    require_schema,
    rows,
)

HOLIDAYS_FILE = "holidays.toml"
_SATURDAY = 5
_ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class HolidayYear:
    """One year's IDX non-trading weekdays, the document they come from, and IDX's stated total."""

    year: int
    source: str
    trading_days: int
    holidays: frozenset[date]


def _weekdays(year: int) -> int:
    first = date(year, 1, 1)
    length = (date(year + 1, 1, 1) - first).days
    return sum(1 for offset in range(length) if (first + timedelta(offset)).weekday() < _SATURDAY)


def _parse_year(row: Row, where: Where) -> HolidayYear:
    only_keys(row, {"year", "source", "trading_days", "holidays"}, where)
    year = get_int(row, "year", where, minimum=1)
    listed = get_list(row, "holidays", where)
    days: list[date] = []
    for position, value in enumerate(listed, start=1):
        day = as_date(value, f"{where}: holiday {position}")
        if day.year != year:
            msg = f"{where}: {day.isoformat()} is not in {year}"
            raise DataFileError(msg)
        if day.weekday() >= _SATURDAY:
            msg = f"{where}: {day.isoformat()} is a weekend, which is never a trading day anyway"
            raise DataFileError(msg)
        if days and day <= days[-1]:
            msg = f"{where}: holidays must be listed once each, in order; {day.isoformat()} is not"
            raise DataFileError(msg)
        days.append(day)
    stated = get_int(row, "trading_days", where, minimum=0)
    counted = _weekdays(year) - len(days)
    if counted != stated:
        msg = (
            f"{where}: {year} has {counted} weekdays that are not holidays, "
            f"but the calendar states {stated} trading days"
        )
        raise DataFileError(msg)
    return HolidayYear(year, get_str(row, "source", where), stated, frozenset(days))


def parse_holidays(document: Row, file: str = HOLIDAYS_FILE) -> tuple[HolidayYear, ...]:
    """Validate a holidays document: consecutive years, each one's arithmetic checked."""
    require_schema(document, file, 1)
    only_keys(document, {"schema", "year"}, Where(file, "top level"))
    where = Where(file, "year")
    years = tuple(
        _parse_year(row, where.at(i)) for i, row in enumerate(rows(document, "year", where), 1)
    )
    for earlier, later in pairwise(years):
        if later.year != earlier.year + 1:
            msg = f"{file}: years must be consecutive, got {later.year} after {earlier.year}"
            raise DataFileError(msg)
    return years


class IdxCalendar:
    """Which days the IDX regular market is open, for the years it has holiday data."""

    def __init__(self, years: Iterable[HolidayYear], *, file: str = HOLIDAYS_FILE) -> None:
        self._years = {year.year: year for year in years}
        if not self._years:
            msg = f"{file}: a calendar needs at least one year"
            raise DataFileError(msg)
        self._file = file

    @classmethod
    def shipped(cls) -> IdxCalendar:
        """The calendar from the package's own ``data/holidays.toml``."""
        return _shipped_calendar()

    @property
    def first_day(self) -> date:
        return date(min(self._years), 1, 1)

    @property
    def last_day(self) -> date:
        return date(max(self._years), 12, 31)

    def source(self, year: int) -> str:
        """The IDX document a year's holidays come from."""
        return self._year(year).source

    def _year(self, year: int) -> HolidayYear:
        found = self._years.get(year)
        if found is None:
            msg = (
                f"{self._file} has no IDX holidays for {year}, so its trading days are unknown; "
                f"it covers {self.first_day.year} to {self.last_day.year}"
            )
            raise UnsupportedDateError(msg)
        return found

    def require_covered(self, day: date) -> None:
        """Raise ``UnsupportedDateError`` unless *day*'s year has holiday data."""
        self._year(day.year)

    def is_trading_day(self, day: date) -> bool:
        holidays = self._year(day.year).holidays
        return day.weekday() < _SATURDAY and day not in holidays

    def next_trading_day(self, day: date) -> date:
        """The first trading day strictly after *day*."""
        return self.add_trading_days(day, 1)

    def previous_trading_day(self, day: date) -> date:
        """The last trading day strictly before *day*."""
        day -= _ONE_DAY
        while not self.is_trading_day(day):
            day -= _ONE_DAY
        return day

    def add_trading_days(self, day: date, count: int) -> date:
        """The *count*-th trading day after *day* (``count`` of at least 1).

        *day* itself need not be a trading day: the count starts on the day after it.
        """
        if type(count) is not int or count < 1:
            msg = f"count must be an int of at least 1, got {count!r}"
            raise ValueError(msg)
        while count:
            day += _ONE_DAY
            if self.is_trading_day(day):
                count -= 1
        return day

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        """Every trading day from *start* to *end*, inclusive."""
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        found: list[date] = []
        day = start
        while day <= end:
            if self.is_trading_day(day):
                found.append(day)
            day += _ONE_DAY
        return tuple(found)


@cache
def _shipped_calendar() -> IdxCalendar:
    return IdxCalendar(parse_holidays(load_shipped(HOLIDAYS_FILE)))
