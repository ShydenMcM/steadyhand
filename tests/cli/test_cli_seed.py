"""The bar cache the recorded CLI tests start from is the one a first run fills (#282): each code's
rows in the recorded seed are the rows a fresh cache stores for it, and ``recorded_source`` copies
the seed into a folder with no cache, never over one."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from cli_world import recorded_source, seed
from record_cli_seed import CODES, fill

from steadyhand_idx import BarCache

Rows = dict[str, list[tuple[object, ...]]]


def rows(path: Path, code: str | None = None) -> Rows:
    """Every table's rows in the cache at *path*, or only *code*'s, in key order."""
    with closing(sqlite3.connect(path)) as db:
        tables = [
            name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        ]
        found: Rows = {}
        for table in sorted(tables):
            where, args = ("WHERE symbol = ?", (code,)) if code else ("", ())
            query = f"SELECT * FROM {table} {where} ORDER BY 1, 2, 3"  # noqa: S608 - names from the cache
            found[table] = db.execute(query, args).fetchall()
    return found


def seeded(folder: Path) -> Path:
    path = folder / "seed.sqlite"
    path.write_bytes(seed())
    return path


@pytest.mark.parametrize("code", CODES)
def test_the_seed_holds_what_a_first_run_stores(code: str, tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.sqlite"
    with BarCache(fresh) as cache:
        fill(cache, code)
    stored = rows(fresh, code)
    assert stored["fetched"], f"the fill stored no fetched range for {code}"
    assert stored["fetched_actions"], f"the fill stored no action range for {code}"
    assert rows(seeded(tmp_path), code) == stored


def test_the_seed_holds_no_other_code(tmp_path: Path) -> None:
    found = rows(seeded(tmp_path))
    assert len(found) == 5, sorted(found)
    symbols = {row[0] for table in found.values() for row in table}
    assert symbols == set(CODES)
    assert len(CODES) == 45


def test_a_folder_with_no_bar_cache_starts_from_the_seed(tmp_path: Path) -> None:
    with recorded_source(tmp_path):
        pass
    assert rows(tmp_path / "cache.sqlite") == rows(seeded(tmp_path))


def test_a_bar_cache_already_in_the_folder_is_kept(tmp_path: Path) -> None:
    BarCache(tmp_path / "cache.sqlite").close()
    with recorded_source(tmp_path):
        pass
    assert not any(rows(tmp_path / "cache.sqlite").values())
