"""A local SQLite cache of bars and corporate actions, keyed by (ticker, date) (spec §9.3).

``BarCache`` stores what a data source returned, one range at a time, in one transaction: the
bars, the actions and the fact that the range was fetched. A stored row is never overwritten.
A different value for a row already stored is a ``CacheConflictError`` and nothing is written,
so good cached data survives a bad fetch (spec §5 step 1).

``CachedDataSource`` puts the cache in front of another ``DataSource`` and fetches only the
ranges it is missing (spec §9.2). A day counts as fetched only once it is over in Jakarta, so
today's bar is always fetched afresh and never stored here: M5's daily run stores it after it
passes validation.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from zoneinfo import ZoneInfo

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    DataSource,
    Instrument,
    Money,
    OtherAction,
    Split,
)
from steadyhand_idx.calendar import IdxCalendar

JAKARTA = ZoneInfo("Asia/Jakarta")
_ONE_DAY = timedelta(days=1)
_BUSY_TIMEOUT_SECONDS = 30.0

# Applied in order; PRAGMA user_version records how many have run. Never edit a shipped entry:
# add a new one, so a cache made by an older release upgrades in place.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE bars (
        symbol TEXT NOT NULL,
        day TEXT NOT NULL,
        open INTEGER NOT NULL,
        high INTEGER NOT NULL,
        low INTEGER NOT NULL,
        close INTEGER NOT NULL,
        volume INTEGER NOT NULL,
        PRIMARY KEY (symbol, day)
    ) STRICT;
    CREATE TABLE actions (
        symbol TEXT NOT NULL,
        ex_date TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('split', 'dividend', 'other')),
        old_shares INTEGER,
        new_shares INTEGER,
        per_share TEXT,
        description TEXT,
        PRIMARY KEY (symbol, ex_date, kind)
    ) STRICT;
    CREATE TABLE fetched (
        symbol TEXT NOT NULL,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        PRIMARY KEY (symbol, start, end)
    ) STRICT;
    """,
)


class CacheConflictError(RuntimeError):
    """A fetched value differs from the one already cached. Nothing from that fetch is stored."""


class CacheSchemaError(RuntimeError):
    """The cache file was written by a newer steadyhand-idx than this one."""


type _BarRow = tuple[int, int, int, int, int]
type _ActionRow = tuple[int | None, int | None, str | None, str | None]


def _action_row(action: CorporateAction) -> tuple[str, _ActionRow]:
    if isinstance(action, Split):
        return "split", (action.old_shares, action.new_shares, None, None)
    if isinstance(action, CashDividend):
        return "dividend", (None, None, str(action.per_share), None)
    return "other", (None, None, None, action.description)


class BarCache:
    """The cache file. Use it as a context manager, or call ``close()``."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_SECONDS, isolation_level=None)
        try:
            self._migrate()
        except BaseException:
            self._db.close()
            raise

    def __enter__(self) -> BarCache:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    @property
    def schema_version(self) -> int:
        return int(self._db.execute("PRAGMA user_version").fetchone()[0])

    def _migrate(self) -> None:
        with self._write():
            version = self.schema_version
            if version > len(MIGRATIONS):
                msg = (
                    f"{self._path} is at cache schema {version}, newer than this "
                    f"steadyhand-idx knows ({len(MIGRATIONS)}); upgrade steadyhand-idx"
                )
                raise CacheSchemaError(msg)
            for number in range(version, len(MIGRATIONS)):
                # One statement at a time: executescript() would commit this transaction first.
                for statement in MIGRATIONS[number].split(";"):
                    if statement.strip():
                        self._db.execute(statement)
                self._db.execute(f"PRAGMA user_version = {number + 1}")

    @contextmanager
    def _write(self) -> Iterator[None]:
        """One transaction, taking the write lock at once, rolled back on any error."""
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        self._db.execute("COMMIT")

    def store(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        bars: Sequence[Bar],
        actions: Sequence[CorporateAction],
    ) -> None:
        """Store one fetched range, all of it or none of it, and mark the range as fetched."""
        start, end = span
        symbol = self._symbol(instrument)
        located = [(b.instrument, b.day) for b in bars] + [
            (a.instrument, a.ex_date) for a in actions
        ]
        for owner, day in located:
            if owner != instrument or not start <= day <= end:
                msg = f"{owner.symbol} {day.isoformat()} is not {symbol} in {start} to {end}"
                raise ValueError(msg)
        with self._write():
            for bar in bars:
                row: _BarRow = (
                    bar.open.amount,
                    bar.high.amount,
                    bar.low.amount,
                    bar.close.amount,
                    bar.volume,
                )
                self._insert_bar(symbol, bar.day, row)
            for action in actions:
                kind, values = _action_row(action)
                self._insert_action(symbol, action.ex_date, kind, values)
            self._db.execute(
                "INSERT OR IGNORE INTO fetched VALUES (?, ?, ?)",
                (symbol, start.isoformat(), end.isoformat()),
            )

    def _insert_bar(self, symbol: str, day: date, row: _BarRow) -> None:
        found = self._db.execute(
            "SELECT open, high, low, close, volume FROM bars WHERE symbol = ? AND day = ?",
            (symbol, day.isoformat()),
        ).fetchone()
        if found is None:
            self._db.execute(
                "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?)", (symbol, day.isoformat(), *row)
            )
        elif tuple(found) != row:
            msg = (
                f"{symbol} {day.isoformat()}: cached bar {tuple(found)} differs from fetched {row}"
            )
            raise CacheConflictError(msg)

    def _insert_action(self, symbol: str, day: date, kind: str, values: _ActionRow) -> None:
        found = self._db.execute(
            "SELECT old_shares, new_shares, per_share, description FROM actions "
            "WHERE symbol = ? AND ex_date = ? AND kind = ?",
            (symbol, day.isoformat(), kind),
        ).fetchone()
        if found is None:
            self._db.execute(
                "INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (symbol, day.isoformat(), kind, *values),
            )
        elif tuple(found) != values:
            msg = (
                f"{symbol} {day.isoformat()}: cached {kind} {tuple(found)} "
                f"differs from fetched {values}"
            )
            raise CacheConflictError(msg)

    def bars(self, instrument: Instrument, start: date, end: date) -> list[Bar]:
        symbol = self._symbol(instrument)
        rows = self._db.execute(
            "SELECT day, open, high, low, close, volume FROM bars "
            "WHERE symbol = ? AND day BETWEEN ? AND ? ORDER BY day",
            (symbol, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [
            Bar(
                instrument,
                date.fromisoformat(day),
                Money(opening, IDR),
                Money(high, IDR),
                Money(low, IDR),
                Money(closing, IDR),
                volume,
            )
            for day, opening, high, low, closing, volume in rows
        ]

    def actions(self, instrument: Instrument, start: date, end: date) -> list[CorporateAction]:
        symbol = self._symbol(instrument)
        rows = self._db.execute(
            "SELECT ex_date, kind, old_shares, new_shares, per_share, description FROM actions "
            "WHERE symbol = ? AND ex_date BETWEEN ? AND ? ORDER BY ex_date, kind",
            (symbol, start.isoformat(), end.isoformat()),
        ).fetchall()
        found: list[CorporateAction] = []
        for day, kind, old, new, per_share, description in rows:
            ex_date = date.fromisoformat(day)
            if kind == "split":
                found.append(Split(instrument, ex_date, old, new))
            elif kind == "dividend":
                found.append(CashDividend(instrument, ex_date, Decimal(per_share)))
            else:
                found.append(OtherAction(instrument, ex_date, description))
        return found

    def fetched(self, instrument: Instrument) -> list[tuple[date, date]]:
        """Every range stored for *instrument*, merged where they touch or overlap."""
        rows = self._db.execute(
            "SELECT start, end FROM fetched WHERE symbol = ? ORDER BY start, end",
            (self._symbol(instrument),),
        ).fetchall()
        merged: list[tuple[date, date]] = []
        for first, last in rows:
            start, end = date.fromisoformat(first), date.fromisoformat(last)
            if merged and start <= merged[-1][1] + _ONE_DAY:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    @staticmethod
    def _symbol(instrument: Instrument) -> str:
        if instrument.market != "IDX" or instrument.currency != IDR:
            msg = f"this cache holds IDX IDR stocks, not {instrument.symbol} on {instrument.market}"
            raise ValueError(msg)
        return instrument.symbol


def jakarta_today() -> date:
    """Today's date in Jakarta, where the IDX trading day is counted."""
    return datetime.now(JAKARTA).date()


class CachedDataSource:
    """A ``DataSource`` that answers from ``BarCache`` and fetches only what it is missing."""

    def __init__(
        self,
        upstream: DataSource,
        cache: BarCache,
        calendar: IdxCalendar | None = None,
        *,
        today: Callable[[], date] = jakarta_today,
    ) -> None:
        self._upstream = upstream
        self._cache = cache
        self._calendar = IdxCalendar.shipped() if calendar is None else calendar
        self._today = today

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        today = self._fill(instrument, start, end)
        cached = self._cache.bars(instrument, start, min(end, today - _ONE_DAY))
        if end < today:
            return cached
        return [*cached, *self._upstream.bars(instrument, today, today)]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        today = self._fill(instrument, start, end)
        cached = self._cache.actions(instrument, start, min(end, today - _ONE_DAY))
        if end < today:
            return cached
        return [*cached, *self._upstream.corporate_actions(instrument, today, today)]

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
        """The parts of *start* to *end* not yet stored, trimmed to trading days.

        A gap holding no trading day (a weekend, a holiday) is not missing: there is nothing
        there to fetch, and asking Yahoo for it would fail.
        """
        gaps: list[tuple[date, date]] = []
        cursor = start
        for first, last in self._cache.fetched(instrument):
            if last < cursor:
                continue
            if first > end:
                break
            if first > cursor:
                gaps.append((cursor, first - _ONE_DAY))
            cursor = last + _ONE_DAY
        if cursor <= end:
            gaps.append((cursor, end))
        trimmed: list[tuple[date, date]] = []
        for first, last in gaps:
            days = self._calendar.trading_days(first, last)
            if days:
                trimmed.append((days[0], days[-1]))
        return trimmed

    def _fill(self, instrument: Instrument, start: date, end: date) -> date:
        """Fetch and store every missing range that is over, and return today."""
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        today = self._today()
        if end > today:
            msg = (
                f"no bars exist yet after today ({today.isoformat()}); asked for {end.isoformat()}"
            )
            raise ValueError(msg)
        complete = min(end, today - _ONE_DAY)
        if start <= complete:
            for first, last in self.missing(instrument, start, complete):
                bars = self._upstream.bars(instrument, first, last)
                actions = self._upstream.corporate_actions(instrument, first, last)
                self._cache.store(instrument, (first, last), bars, actions)
        return today
