"""A unit run's SQLite files skip the disk sync (#506): a COMMIT on a CI runner once took more than
the 1 s unit limit waiting on the disk."""

import sqlite3
from contextlib import closing
from pathlib import Path

import unsynced_sqlite

SYNCHRONOUS_OFF = 0


def test_a_unit_runs_database_file_skips_the_disk_sync(tmp_path: Path) -> None:
    with closing(sqlite3.connect(tmp_path / "a.db")) as db:
        assert db.execute("PRAGMA synchronous").fetchone() == (SYNCHRONOUS_OFF,)


def test_the_connection_keeps_what_the_caller_asked_for(tmp_path: Path) -> None:
    with closing(sqlite3.connect(tmp_path / "a.db", timeout=2.5, isolation_level=None)) as db:
        assert db.execute("PRAGMA busy_timeout").fetchone() == (2_500,)
        assert db.isolation_level is None


def test_installing_twice_wraps_once() -> None:
    unsynced_sqlite.install()
    unsynced_sqlite.install()
    assert sqlite3.connect.__wrapped__ is unsynced_sqlite.REAL_CONNECT  # type: ignore[attr-defined]
