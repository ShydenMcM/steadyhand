"""The paper account's state database, ``state.sqlite`` in the data directory (M5 spec §6.3).

One ``account`` row holds the encoded ``EngineState``, the opening day, the strategy, the last
day run and the settings that day ran with. Three tables are append-only, and triggers refuse
any change to them: ``day_reports`` (one encoded report per trading day), ``audit`` (a key and
a line per event, core spec §9.7) and ``runs`` (one row per ``paper run``).

``StateStore.save`` writes a day in one ``BEGIN IMMEDIATE`` transaction: the account, the day's
report and its audit lines, or nothing. Inside it the store reads ``last_day`` again and writes
only if it is still the day the caller started from, so a day run by two processes at once is
saved exactly once (§6.4). The file is created ``0600`` (§4.1), and its schema is upgraded in
place on ``BarCache``'s pattern (core spec §9.3).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Final

from steadyhand import (
    DayReport,
    EngineState,
    Note,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
)
from steadyhand_idx.paths import private_file

STATE_FILE: Final = "state.sqlite"
BUSY_TIMEOUT_SECONDS: Final = 30.0
"""How long a second ``paper run`` waits for the first one's write lock before failing."""

# Applied in order; PRAGMA user_version records how many have run. Never edit a shipped entry:
# add a new one, so a database made by an older release upgrades in place.
MIGRATIONS: Final[tuple[str, ...]] = (
    """
    CREATE TABLE account (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        opened_on TEXT NOT NULL,
        strategy TEXT NOT NULL,
        state TEXT NOT NULL,
        last_day TEXT NOT NULL,
        settings TEXT NOT NULL
    ) STRICT;
    CREATE TABLE day_reports (
        day TEXT PRIMARY KEY,
        report TEXT NOT NULL
    ) STRICT;
    CREATE TABLE audit (
        id INTEGER PRIMARY KEY,
        day TEXT NOT NULL,
        key TEXT NOT NULL,
        line TEXT NOT NULL
    ) STRICT;
    CREATE TABLE runs (
        id INTEGER PRIMARY KEY,
        at TEXT NOT NULL,
        target TEXT NOT NULL,
        days TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK (outcome IN ('ran', 'up to date', 'stopped', 'halted')),
        detail TEXT NOT NULL
    ) STRICT;
    CREATE TRIGGER day_reports_are_kept BEFORE UPDATE ON day_reports
        BEGIN SELECT RAISE(ABORT, 'day_reports is append-only'); END;
    CREATE TRIGGER day_reports_are_never_removed BEFORE DELETE ON day_reports
        BEGIN SELECT RAISE(ABORT, 'day_reports is append-only'); END;
    CREATE TRIGGER audit_is_kept BEFORE UPDATE ON audit
        BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    CREATE TRIGGER audit_is_never_removed BEFORE DELETE ON audit
        BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    CREATE TRIGGER runs_are_kept BEFORE UPDATE ON runs
        BEGIN SELECT RAISE(ABORT, 'runs is append-only'); END;
    CREATE TRIGGER runs_are_never_removed BEFORE DELETE ON runs
        BEGIN SELECT RAISE(ABORT, 'runs is append-only'); END;
    """,
)


class StateSchemaError(RuntimeError):
    """The state database was written by a newer steadyhand-idx than this one. M5 exits 2."""


class Outcome(Enum):
    """How a ``paper run`` ended (M5 spec §6.3)."""

    RAN = "ran"
    UP_TO_DATE = "up to date"
    STOPPED = "stopped"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class Account:
    """The paper account: opened on ``opened_on`` with ``strategy``, its state after the last
    day run, and the settings that day ran with, by configuration key."""

    opened_on: date
    strategy: str
    state: EngineState
    settings: Mapping[str, str] = field(default_factory=dict)
    last_day: date = field(init=False)
    """The last day run: the state's, which an account always has."""

    def __post_init__(self) -> None:
        if self.state.last_day is None:
            msg = "an account is saved only with a day run"
            raise ValueError(msg)
        object.__setattr__(self, "last_day", self.state.last_day)
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))


@dataclass(frozen=True, slots=True)
class AuditLine:
    """One line of the audit log: what happened on ``day``, under its note's key (core §9.7)."""

    day: date
    note: Note


@dataclass(frozen=True, slots=True)
class Run:
    """One ``paper run``: when it ran (UTC), its target day, the days it ran, how it ended."""

    at: datetime
    target: date
    days: tuple[date, ...]
    outcome: Outcome
    detail: str = ""

    def __post_init__(self) -> None:
        if self.at.tzinfo is not UTC:
            msg = f"a run's time is in UTC, got {self.at.isoformat()}"
            raise ValueError(msg)


class StateStore:
    """The state database. Use it as a context manager, or call ``close()``."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db = sqlite3.connect(
            private_file(path), timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None
        )
        try:
            self._migrate()
        except BaseException:
            self._db.close()
            raise

    def __enter__(self) -> StateStore:
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

    def account(self) -> Account | None:
        """The account, or ``None`` before the first day is run."""
        row = self._db.execute(
            "SELECT opened_on, strategy, state, settings FROM account"
        ).fetchone()
        if row is None:
            return None
        opened_on, strategy, state, settings = row
        return Account(
            date.fromisoformat(opened_on),
            strategy,
            decode_state(from_json(state)),
            _settings(settings),
        )

    def save(
        self,
        account: Account,
        *,
        after: date | None,
        report: DayReport | None = None,
        audit: Sequence[AuditLine] = (),
    ) -> bool:
        """Write *account*, *report* and *audit* in one transaction, if the last day saved is
        still *after* (``None``: no account yet). Otherwise write nothing and return ``False``:
        another run got there first."""
        with self._write():
            if self._last_day() != after:
                return False
            self._db.execute(
                "INSERT INTO account (id, opened_on, strategy, state, last_day, settings) "
                "VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET "
                "opened_on = excluded.opened_on, strategy = excluded.strategy, "
                "state = excluded.state, last_day = excluded.last_day, "
                "settings = excluded.settings",
                (
                    account.opened_on.isoformat(),
                    account.strategy,
                    to_json(encode_state(account.state)),
                    account.last_day.isoformat(),
                    to_json(dict(account.settings)),
                ),
            )
            if report is not None:
                self._db.execute(
                    "INSERT INTO day_reports (day, report) VALUES (?, ?)",
                    (report.day.isoformat(), to_json(encode_report(report))),
                )
            self._insert_audit(audit)
            return True

    def finish(self, run: Run, audit: Sequence[AuditLine] = ()) -> None:
        """Record *run*, and any *audit* lines that belong to no saved day, in one transaction."""
        with self._write():
            self._insert_audit(audit)
            self._db.execute(
                "INSERT INTO runs (at, target, days, outcome, detail) VALUES (?, ?, ?, ?, ?)",
                (
                    run.at.isoformat(),
                    run.target.isoformat(),
                    to_json({"days": [day.isoformat() for day in run.days]}),
                    run.outcome.value,
                    run.detail,
                ),
            )

    def report(self, day: date) -> DayReport | None:
        """The report saved for *day*, or ``None``."""
        row = self._db.execute(
            "SELECT report FROM day_reports WHERE day = ?", (day.isoformat(),)
        ).fetchone()
        return None if row is None else decode_report(from_json(row[0]))

    def reports(self) -> tuple[DayReport, ...]:
        """Every saved report, oldest first."""
        rows = self._db.execute("SELECT report FROM day_reports ORDER BY day").fetchall()
        return tuple(decode_report(from_json(text)) for (text,) in rows)

    def days(self) -> tuple[date, ...]:
        """Every day with a saved report, oldest first."""
        rows = self._db.execute("SELECT day FROM day_reports ORDER BY day").fetchall()
        return tuple(date.fromisoformat(day) for (day,) in rows)

    def audit(self) -> tuple[AuditLine, ...]:
        """The audit log, in the order it was written."""
        rows = self._db.execute("SELECT day, key, line FROM audit ORDER BY id").fetchall()
        return tuple(_audit_line(day, key, line) for day, key, line in rows)

    def runs(self) -> tuple[Run, ...]:
        """Every recorded run, in the order they ended."""
        rows = self._db.execute(
            "SELECT at, target, days, outcome, detail FROM runs ORDER BY id"
        ).fetchall()
        return tuple(
            Run(
                datetime.fromisoformat(at).astimezone(UTC),
                date.fromisoformat(target),
                tuple(date.fromisoformat(day) for day in _days(days)),
                Outcome(outcome),
                detail,
            )
            for at, target, days, outcome, detail in rows
        )

    def _last_day(self) -> date | None:
        row = self._db.execute("SELECT last_day FROM account").fetchone()
        return None if row is None else date.fromisoformat(row[0])

    def _insert_audit(self, audit: Sequence[AuditLine]) -> None:
        self._db.executemany(
            "INSERT INTO audit (day, key, line) VALUES (?, ?, ?)",
            [(line.day.isoformat(), line.note.key, line.note.text) for line in audit],
        )

    def _migrate(self) -> None:
        with self._write():
            version = self.schema_version
            if version > len(MIGRATIONS):
                msg = (
                    f"{self._path} is at state schema {version}, newer than this "
                    f"steadyhand-idx knows ({len(MIGRATIONS)}); upgrade steadyhand-idx"
                )
                raise StateSchemaError(msg)
            for number in range(version, len(MIGRATIONS)):
                # One statement at a time: executescript() would commit this transaction first.
                # A trigger's body holds its own semicolons, so statements split at "END;".
                for statement in _statements(MIGRATIONS[number]):
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


def _statements(script: str) -> Iterator[str]:
    """The statements of *script*, each whole: ``sqlite3.complete_statement`` decides where one
    ends, so the semicolons inside a trigger's body do not split it."""
    pending = ""
    for piece in script.split(";"):
        pending += piece + ";"
        if sqlite3.complete_statement(pending):
            if pending.strip(" \n;"):
                yield pending.strip()
            pending = ""


def _settings(text: str) -> dict[str, str]:
    settings = from_json(text)
    if not isinstance(settings, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in settings.items()
    ):
        msg = f"the saved settings are not a table of text values: {text}"
        raise ValueError(msg)
    return settings


def _days(text: str) -> list[str]:
    document = from_json(text)
    days = document.get("days") if isinstance(document, dict) else None
    if not isinstance(days, list) or not all(isinstance(day, str) for day in days):
        msg = f"a run's days are not a list of dates: {text}"
        raise ValueError(msg)
    return days


def _audit_line(day: str, key: str, line: str) -> AuditLine:
    return AuditLine(date.fromisoformat(day), Note(key, line))
