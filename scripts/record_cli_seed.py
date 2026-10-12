"""Record the bar cache every recorded CLI test starts from (#282).

    uv run python scripts/record_cli_seed.py

fills a new bar cache through the real ``CachedDataSource`` from the recorded Yahoo answers, for
the five golden stocks and the 40 made-up codes that fill the CLI tests' LQ45 file: each code's
bars over the golden run's window, and its corporate actions over the income report's look-back
before it, as the CLI tests read them. It writes the cache's rows to
``tests/fixtures/cache/cli-seed.sql``.

A CLI test's data directory starts from a cache built from that file (``cli_world.seed``) instead
of filling one: the fill was about 78% of a paper test's CPU, and about 0.12 s for all 45 codes,
more than one unit test may spend (0.07 s). ``test_cli_seed.py`` fills each code afresh and
compares, so a seed that no longer matches what a first run stores is red.

Run it after a change to the recordings or to what the cache stores, and review the diff: the
file is never edited by hand.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import date, timedelta
from itertools import product
from pathlib import Path

from record_golden import END, HISTORY_START, RECORDED, START, STOCKS, TESTS, recorded, replay

from steadyhand import IDR, Instrument
from steadyhand_idx.cache import BarCache, CachedDataSource
from steadyhand_idx.yahoo import YahooHistory

SEED = TESTS / "fixtures" / "cache" / "cli-seed.sql"

PLACEHOLDERS = tuple("Z" + "".join(letters) for letters in product("ABCDEFGHIJ", repeat=3))[:40]
"""Made-up codes that fill the LQ45 file to 45. No real LQ45 list is ever written into this
repository (core spec §9.4); these are excluded, so no strategy ever holds one."""

CODES = (*STOCKS, *PLACEHOLDERS)
"""Every code the CLI tests' LQ45 file names, in the order the seed stores them."""


def recorded_or_empty(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer for the five golden stocks, and no rows for a placeholder."""
    if ticker.removesuffix(".JK") in STOCKS:
        return recorded(ticker, start, end)
    return YahooHistory(ticker, (), ())


def fill(cache: BarCache, code: str) -> None:
    """Store in *cache* what the CLI tests read of *code*: its bars over the golden window and
    its actions over the look-back before it, fetched as a first run fetches them."""
    source = CachedDataSource(replay(recorded_or_empty), cache, today=lambda: RECORDED)
    instrument = Instrument(code, "IDX", IDR)
    source.bars(instrument, START, END)
    source.corporate_actions(instrument, HISTORY_START, START - timedelta(days=1))


def statements(path: Path) -> list[str]:
    """The cache at *path* as SQL: its rows, in one transaction, without its schema, which the
    cache's own migrations make (a dump would lose the schema version they record)."""
    with closing(sqlite3.connect(path)) as db:
        rows = [line for line in db.iterdump() if line.startswith("INSERT INTO ")]
    return ["BEGIN;", *rows, "COMMIT;"]


def record(seed: Path = SEED) -> Path:
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "cache.sqlite"
        with BarCache(path) as cache:
            for code in CODES:
                fill(cache, code)
        text = "\n".join(statements(path)) + "\n"
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(text, encoding="utf-8")
    return seed


def main(argv: list[str]) -> int:
    if argv:
        print(__doc__)
        return 2
    print(record())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
