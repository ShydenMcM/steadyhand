"""A local SQLite cache of bars and corporate actions, keyed by (ticker, date) (spec §9.3).

``BarCache`` stores what a data source returned, one range at a time, in one transaction: the
bars, the actions and the fact that the range was fetched. A stored row is never overwritten.
A different value for a row already stored is a ``CacheConflictError`` and nothing is written,
so good cached data survives a bad fetch (spec §5 step 1).

``CachedDataSource`` puts the cache in front of another ``DataSource`` and fetches only the
ranges it is missing (spec §9.2). A day counts as fetched only once it is over in Jakarta, so
today's bar is always fetched afresh and never stored here; it is stored by the first read
after the day is over.

Corporate actions can also be fetched alone (M6 spec §4.3): a strategy's look-back reads the
years before a run, whose prices it never needs. Such a range is recorded as fetched for
actions only, so its bars still count as missing.

Each fetched range also stores the upstream's restorations overlapping it (#160 spec §6): the
runs of a stock's history whose prices and dividends were restored, so a report can say so
from a cache read alone.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from typing import Protocol
from zoneinfo import ZoneInfo

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    DataSource,
    Instrument,
    Money,
    Note,
    OtherAction,
    Split,
    UnsupportedDateError,
)
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import Restoration

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
    """
    CREATE TABLE fetched_actions (
        symbol TEXT NOT NULL,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        PRIMARY KEY (symbol, start, end)
    ) STRICT;
    """,
    # #160 spec §6: every proven run is recorded, and every range is read again under the new
    # rules. That corrects a cached dividend Yahoo scaled by an unreported factor (BBRI's 2021
    # dividend was cached as 89.91268, not 98.9057). Bars from refused days were never stored,
    # so no stored bar is wrong; clearing ``fetched`` fetches the days that can now be restored.
    """
    CREATE TABLE restorations (
        symbol TEXT NOT NULL,
        first TEXT NOT NULL,
        last TEXT NOT NULL,
        factor TEXT NOT NULL,
        prices INTEGER NOT NULL,
        PRIMARY KEY (symbol, first)
    ) STRICT;
    DELETE FROM actions;
    DELETE FROM fetched_actions;
    DELETE FROM fetched;
    """,
)


class CacheConflictError(RuntimeError):
    """A fetched value differs from the one already cached. Nothing from that fetch is stored."""


class CacheSchemaError(RuntimeError):
    """The cache file was written by a newer steadyhand-idx than this one."""


class RestoringSource(DataSource, Protocol):
    """A data source that also says which runs of a stock's history it restored."""

    def restorations(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[Restoration]: ...


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
        restorations: Sequence[Restoration] = (),
    ) -> None:
        """Store one fetched range, all of it or none of it, and mark the range as fetched."""
        start, end = span
        symbol = self._symbol(instrument)
        located = [(b.instrument, b.day) for b in bars] + [
            (a.instrument, a.ex_date) for a in actions
        ]
        self._require_within(instrument, span, located)
        self._require_overlapping(instrument, span, restorations)
        with self._write():
            self._insert_restorations(symbol, restorations)
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

    def store_actions(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        actions: Sequence[CorporateAction],
        restorations: Sequence[Restoration] = (),
    ) -> None:
        """Store one range's actions, fetched without its bars, all of them or none, and mark the
        range as fetched for actions only (M6 spec §4.3)."""
        start, end = span
        symbol = self._symbol(instrument)
        self._require_within(instrument, span, [(a.instrument, a.ex_date) for a in actions])
        self._require_overlapping(instrument, span, restorations)
        with self._write():
            self._insert_restorations(symbol, restorations)
            for action in actions:
                kind, values = _action_row(action)
                self._insert_action(symbol, action.ex_date, kind, values)
            self._db.execute(
                "INSERT OR IGNORE INTO fetched_actions VALUES (?, ?, ?)",
                (symbol, start.isoformat(), end.isoformat()),
            )

    def _require_within(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        located: Sequence[tuple[Instrument, date]],
    ) -> None:
        start, end = span
        for owner, day in located:
            if owner != instrument or not start <= day <= end:
                symbol = instrument.symbol
                msg = f"{owner.symbol} {day.isoformat()} is not {symbol} in {start} to {end}"
                raise ValueError(msg)

    def _require_overlapping(
        self, instrument: Instrument, span: tuple[date, date], restorations: Sequence[Restoration]
    ) -> None:
        start, end = span
        for run in restorations:
            if run.instrument != instrument or run.first > end or run.last < start:
                msg = (
                    f"{run.instrument.symbol}'s restoration {run.first} to {run.last} does not "
                    f"overlap {instrument.symbol} in {start} to {end}"
                )
                raise ValueError(msg)

    def _insert_restorations(self, symbol: str, restorations: Sequence[Restoration]) -> None:
        for run in restorations:
            values = (run.last.isoformat(), str(run.factor), run.prices)
            found = self._db.execute(
                "SELECT last, factor, prices FROM restorations WHERE symbol = ? AND first = ?",
                (symbol, run.first.isoformat()),
            ).fetchone()
            if found is None:
                self._db.execute(
                    "INSERT INTO restorations VALUES (?, ?, ?, ?, ?)",
                    (symbol, run.first.isoformat(), *values),
                )
            elif tuple(found) != values:
                msg = (
                    f"{symbol} {run.first.isoformat()}: cached restoration {tuple(found)} "
                    f"differs from fetched {values}"
                )
                raise CacheConflictError(msg)

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

    def restorations(self, instrument: Instrument, start: date, end: date) -> list[Restoration]:
        """The stored restorations overlapping *start* to *end*, oldest first."""
        rows = self._db.execute(
            "SELECT first, last, factor, prices FROM restorations "
            "WHERE symbol = ? AND first <= ? AND last >= ? ORDER BY first",
            (self._symbol(instrument), end.isoformat(), start.isoformat()),
        ).fetchall()
        return [
            Restoration(
                instrument, date.fromisoformat(first), date.fromisoformat(last), Decimal(f), prices
            )
            for first, last, f, prices in rows
        ]

    def fetched(self, instrument: Instrument) -> list[tuple[date, date]]:
        """Every range stored for *instrument*, merged where they touch or overlap."""
        rows = self._db.execute(
            "SELECT start, end FROM fetched WHERE symbol = ? ORDER BY start, end",
            (self._symbol(instrument),),
        ).fetchall()
        return _merged(rows)

    def fetched_actions(self, instrument: Instrument) -> list[tuple[date, date]]:
        """Every range whose actions are stored for *instrument*, with or without its bars,
        merged where they touch or overlap."""
        rows = self._db.execute(
            "SELECT start, end FROM fetched WHERE symbol = ? "
            "UNION SELECT start, end FROM fetched_actions WHERE symbol = ? ORDER BY start, end",
            (self._symbol(instrument), self._symbol(instrument)),
        ).fetchall()
        return _merged(rows)

    @staticmethod
    def _symbol(instrument: Instrument) -> str:
        if instrument.market != "IDX" or instrument.currency != IDR:
            msg = f"this cache holds IDX IDR stocks, not {instrument.symbol} on {instrument.market}"
            raise ValueError(msg)
        return instrument.symbol


def _merged(rows: Sequence[tuple[str, str]]) -> list[tuple[date, date]]:
    """Stored ``(start, end)`` rows, in start order, merged where they touch or overlap."""
    merged: list[tuple[date, date]] = []
    for first, last in rows:
        start, end = date.fromisoformat(first), date.fromisoformat(last)
        if merged and start <= merged[-1][1] + _ONE_DAY:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def jakarta_today() -> date:
    """Today's date in Jakarta, where the IDX trading day is counted."""
    return datetime.now(JAKARTA).date()


class CachedDataSource:
    """A ``DataSource`` that answers from ``BarCache`` and fetches only what it is missing."""

    def __init__(
        self,
        upstream: RestoringSource,
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
        """The range's actions. A part not yet stored is fetched without its bars and stored
        as fetched for actions only, so a look-back never reads a price (M6 spec §4.3)."""
        today = self._today_for(start, end)
        complete = min(end, today - _ONE_DAY)
        if start <= complete:
            for first, last in self.missing_actions(instrument, start, complete):
                actions = self._upstream.corporate_actions(instrument, first, last)
                restored = self._upstream.restorations(instrument, first, last)
                self._cache.store_actions(instrument, (first, last), actions, restored)
        cached = self._cache.actions(instrument, start, complete)
        if end < today:
            return cached
        return [*cached, *self._upstream.corporate_actions(instrument, today, today)]

    def restorations(self, instrument: Instrument, start: date, end: date) -> list[Restoration]:
        """The restorations stored with the ranges read so far that overlap *start* to *end*:
        a cache read, never a fetch (#160 spec §6)."""
        return self._cache.restorations(instrument, start, end)

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> tuple[Note, ...]:
        """One note per restoration stored for *instruments* overlapping the range, and per run
        the upstream inferred for today's bar, which is never stored; each note once."""
        stored = (
            restoration.note
            for instrument in instruments
            for restoration in self._cache.restorations(instrument, start, end)
        )
        return tuple(dict.fromkeys((*stored, *self._upstream.data_notes(instruments, start, end))))

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
        """The parts of *start* to *end* not yet stored, trimmed to trading days.

        A gap holding no trading day (a weekend, a holiday) is not missing: there is nothing
        there to fetch, and asking Yahoo for it would fail.
        """
        gaps = _gaps(self._cache.fetched(instrument), start, end)
        return [span for first, last in gaps if (span := self._trading(first, last)) is not None]

    def missing_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> list[tuple[date, date]]:
        """The parts of *start* to *end* whose actions are not yet stored, with or without bars.

        A gap in years the holiday calendar covers is trimmed to its trading days, as in
        ``missing``. A gap reaching into a year it does not cover is asked for whole: actions
        need no calendar, and such a gap is the start of a look-back, years long.
        """
        found: list[tuple[date, date]] = []
        for first, last in _gaps(self._cache.fetched_actions(instrument), start, end):
            try:
                span = self._trading(first, last)
            except UnsupportedDateError:
                span = (first, last)
            if span is not None:
                found.append(span)
        return found

    def _trading(self, first: date, last: date) -> tuple[date, date] | None:
        """*first* to *last* narrowed to its first and last trading day, or ``None`` if it has
        none."""
        days = self._calendar.trading_days(first, last)
        return (days[0], days[-1]) if days else None

    def _today_for(self, start: date, end: date) -> date:
        """Today, once *start* to *end* is a range that can be read today."""
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        today = self._today()
        if end > today:
            msg = (
                f"no bars exist yet after today ({today.isoformat()}); asked for {end.isoformat()}"
            )
            raise ValueError(msg)
        return today

    def _fill(self, instrument: Instrument, start: date, end: date) -> date:
        """Fetch and store every missing range that is over, and return today."""
        today = self._today_for(start, end)
        complete = min(end, today - _ONE_DAY)
        if start <= complete:
            for first, last in self.missing(instrument, start, complete):
                bars = self._upstream.bars(instrument, first, last)
                actions = self._upstream.corporate_actions(instrument, first, last)
                restored = self._upstream.restorations(instrument, first, last)
                self._cache.store(instrument, (first, last), bars, actions, restored)
        return today


def _gaps(covered: Sequence[tuple[date, date]], start: date, end: date) -> list[tuple[date, date]]:
    """The parts of *start* to *end* outside *covered*, merged ranges in start order."""
    gaps: list[tuple[date, date]] = []
    cursor = start
    for first, last in covered:
        if last < cursor:
            continue
        if first > end:
            break
        if first > cursor:
            gaps.append((cursor, first - _ONE_DAY))
        cursor = last + _ONE_DAY
    if cursor <= end:
        gaps.append((cursor, end))
    return gaps
