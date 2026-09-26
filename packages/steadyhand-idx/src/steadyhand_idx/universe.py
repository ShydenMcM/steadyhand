"""Which stocks a strategy may hold: dated LQ45 membership and the exclusions (spec §9.4).

Both files are supplied by the user, and steadyhand ships neither. IDX's Terms of Use bar
redistributing its data for commercial use without written permission, and Apache-2.0 would pass
on rights we do not hold (docs/research/t-lq45.md §5). docs/lq45-members.md tells a user where IDX
publishes each list; nothing here downloads anything.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path

from steadyhand import IDR, Instrument
from steadyhand_idx._datafile import (
    DataFileError,
    Row,
    Where,
    get_date,
    get_list,
    get_str,
    load_path,
    only_keys,
    require_schema,
    rows,
)

LQ45_SIZE = 45
REVIEW_KINDS = frozenset({"review", "replacement"})
# LQ45 reviews were semi-annual until January 2024 and quarterly from May 2024 (t-lq45.md §3).
QUARTERLY_FROM = date(2024, 5, 1)
_CODE = re.compile(r"[A-Z]{4}")
_EXCLUSION_HEADER = ["symbol", "from", "to", "reason"]


class MembershipUnknownError(LookupError):
    """No LQ45 list in the user's file covers the day asked about."""


@dataclass(frozen=True, slots=True)
class Lq45Record:
    """One IDX document's full list of 45, in force from ``effective`` until the next record."""

    effective: date
    announced: date
    source: str
    kind: str
    members: frozenset[str]


def _months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def _parse_record(row: Row, where: Where) -> Lq45Record:
    only_keys(row, {"effective", "announced", "source", "kind", "members"}, where)
    effective = get_date(row, "effective", where)
    announced = get_date(row, "announced", where)
    if announced > effective:
        msg = f"{where}: announced {announced} is after effective {effective}"
        raise DataFileError(msg)
    kind = get_str(row, "kind", where)
    if kind not in REVIEW_KINDS:
        msg = f"{where}: kind must be 'review' or 'replacement', got {kind!r}"
        raise DataFileError(msg)
    codes = get_list(row, "members", where)
    bad = [code for code in codes if not (isinstance(code, str) and _CODE.fullmatch(code))]
    if bad:
        msg = f"{where}: members must be four-letter IDX codes, got {bad[0]!r}"
        raise DataFileError(msg)
    members = frozenset(str(code) for code in codes)
    if len(codes) != LQ45_SIZE or len(members) != LQ45_SIZE:
        msg = (
            f"{where}: members must list {LQ45_SIZE} different codes, "
            f"got {len(members)} of {len(codes)}"
        )
        raise DataFileError(msg)
    return Lq45Record(effective, announced, get_str(row, "source", where), kind, members)


class Lq45Membership:
    """LQ45 membership on each date: the latest record in force on or before it."""

    def __init__(self, records: Sequence[Lq45Record], *, file: str = "lq45_members.toml") -> None:
        if not records:
            msg = f"{file}: needs at least one record"
            raise DataFileError(msg)
        for earlier, later in pairwise(records):
            if later.effective <= earlier.effective:
                msg = (
                    f"{file}: records must be in effective-date order, "
                    f"got {later.effective} after {earlier.effective}"
                )
                raise DataFileError(msg)
        self._records = tuple(records)
        self._file = file

    @classmethod
    def load(cls, path: Path) -> Lq45Membership:
        """Read the user's file. A missing file names the config key that points to it."""
        if not path.exists():
            msg = (
                f"[universe] lq45_members points to {path}, which does not exist. steadyhand does "
                "not ship LQ45 lists: docs/lq45-members.md says where IDX publishes each one"
            )
            raise FileNotFoundError(msg)
        document = load_path(path)
        require_schema(document, path.name, 1)
        only_keys(document, {"schema", "record"}, Where(path.name, "top level"))
        where = Where(path.name, "record")
        records = [
            _parse_record(row, where.at(index))
            for index, row in enumerate(rows(document, "record", where), start=1)
        ]
        return cls(records, file=path.name)

    @property
    def records(self) -> tuple[Lq45Record, ...]:
        return self._records

    def members_on(self, day: date) -> frozenset[str]:
        found = [record for record in self._records if record.effective <= day]
        if not found:
            msg = (
                f"{self._file} has no LQ45 list in force on {day.isoformat()}; "
                f"its first takes effect on {self._records[0].effective.isoformat()}"
            )
            raise MembershipUnknownError(msg)
        return found[-1].members

    def gaps(self) -> list[tuple[Lq45Record, Lq45Record]]:
        """Consecutive records more than one review apart: at least one list is missing."""
        found: list[tuple[Lq45Record, Lq45Record]] = []
        for earlier, later in pairwise(self._records):
            allowed = 3 if later.effective >= QUARTERLY_FROM else 6
            if _months_between(earlier.effective, later.effective) > allowed:
                found.append((earlier, later))
        return found

    def survivorship_warnings(self, start: date, end: date) -> list[str]:
        """What a backtest from *start* to *end* must print about missing lists (spec §9.4).

        A start before the first list needs no warning: the backtest refuses it (M3 spec §7.2).
        """
        warnings: list[str] = []
        for earlier, later in self.gaps():
            if start < later.effective and earlier.effective <= end:
                warnings.append(
                    f"Survivorship bias: {self._file} has no LQ45 list between "
                    f"{earlier.effective.isoformat()} ({earlier.source}) and "
                    f"{later.effective.isoformat()} ({later.source}), more than one review apart. "
                    "The backtest uses the earlier list until the later one."
                )
        return warnings


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A stock the operator keeps out of the portfolio, from ``start`` to ``end`` inclusive."""

    symbol: str
    start: date
    end: date | None
    reason: str

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)


class Exclusions:
    """The operator's ``exclusions.csv``: stocks never bought, and frozen if held (spec §6.1).

    Yahoo cannot tell which stocks are on the Special Monitoring Board, so the user lists them
    here by hand, with the dates they were on it. No file means no exclusions.
    """

    def __init__(self, entries: Sequence[Exclusion] = ()) -> None:
        self._entries = tuple(entries)

    @classmethod
    def load(cls, path: Path) -> Exclusions:
        if not path.exists():
            return cls()
        with path.open(encoding="utf-8", newline="") as handle:
            lines = list(csv.reader(handle))
        if not lines or lines[0] != _EXCLUSION_HEADER:
            msg = f"{path.name}: the first line must be {','.join(_EXCLUSION_HEADER)}"
            raise DataFileError(msg)
        return cls(
            [_exclusion(line, f"{path.name} line {n}") for n, line in enumerate(lines[1:], 2)]
        )

    def excluded_on(self, day: date) -> dict[str, str]:
        """Each symbol excluded on *day*, with the reason given for it."""
        return {entry.symbol: entry.reason for entry in self._entries if entry.covers(day)}


def _exclusion(line: list[str], where: str) -> Exclusion:
    if len(line) != len(_EXCLUSION_HEADER):
        msg = f"{where}: needs {len(_EXCLUSION_HEADER)} fields, got {len(line)}"
        raise DataFileError(msg)
    symbol, first, last, reason = (field.strip() for field in line)
    try:
        Instrument(symbol, "IDX", IDR)
    except ValueError:
        msg = f"{where}: {symbol!r} is not an IDX symbol"
        raise DataFileError(msg) from None
    try:
        start = date.fromisoformat(first)
        end = date.fromisoformat(last) if last else None
    except ValueError:
        msg = f"{where}: dates must be written 2026-09-25, got {first!r} and {last!r}"
        raise DataFileError(msg) from None
    if end is not None and end < start:
        msg = f"{where}: to {end} is before from {start}"
        raise DataFileError(msg)
    if not reason:
        msg = f"{where}: give a reason, so the report can say why {symbol} was skipped"
        raise DataFileError(msg)
    return Exclusion(symbol, start, end, reason)


class Lq45Universe:
    """The engine's ``Universe`` for IDX: the LQ45 on each day, and the operator's exclusions."""

    def __init__(self, membership: Lq45Membership, exclusions: Exclusions | None = None) -> None:
        self._membership = membership
        self._exclusions = Exclusions() if exclusions is None else exclusions

    def members_on(self, day: date) -> frozenset[Instrument]:
        return frozenset(Instrument(code, "IDX", IDR) for code in self._membership.members_on(day))

    def excluded_on(self, day: date) -> dict[Instrument, str]:
        excluded = self._exclusions.excluded_on(day)
        return {Instrument(symbol, "IDX", IDR): reason for symbol, reason in excluded.items()}

    def first_day(self) -> date:
        return self._membership.records[0].effective

    def survivorship_warnings(self, start: date, end: date) -> tuple[str, ...]:
        return tuple(self._membership.survivorship_warnings(start, end))
