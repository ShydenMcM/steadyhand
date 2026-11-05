"""The shipped stores keep SQLite's durable default, a full disk sync on every COMMIT (#506).

The unit run skips that sync (``tests/plugins/unsynced_sqlite.py``); this suite runs without it, so
here the stores open as a user's machine opens them.
"""

from pathlib import Path

from steadyhand_idx.cache import BarCache
from steadyhand_idx.state import StateStore

SYNCHRONOUS_FULL = 2


def test_the_state_store_syncs_every_commit_to_disk(tmp_path: Path) -> None:
    with StateStore(tmp_path / "state.db") as store:
        assert store._db.execute("PRAGMA synchronous").fetchone() == (SYNCHRONOUS_FULL,)


def test_the_bar_cache_syncs_every_commit_to_disk(tmp_path: Path) -> None:
    with BarCache(tmp_path / "cache.db") as cache:
        assert cache._db.execute("PRAGMA synchronous").fetchone() == (SYNCHRONOUS_FULL,)
