"""Running ``steadyhand-idx`` in-process, as the console script does, with a fixed clock (M5 spec
§9.1). Nothing of steadyhand's is stubbed: the tests pass ``main`` the same kind of ``World`` the
console script builds, with text streams, an environment naming a temporary data directory, a
fixed clock and a data source."""

import io
import os
import stat
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import product
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import NamedTuple

from record_golden import RECORDED, START, STOCKS, recorded

from steadyhand import DataSource
from steadyhand_idx import BarCache, CachedDataSource, YahooDataSource
from steadyhand_idx.cli import SourceFactory, World, main
from steadyhand_idx.yahoo import YahooHistory

NOW = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)
"""18:00 UTC is 01:00 on 28 September in Jakarta, so 'today' is the Jakarta date."""


def mode(path: Path) -> int:
    """The permission bits of *path*."""
    return stat.S_IMODE(path.stat().st_mode)


@contextmanager
def umask(value: int) -> Iterator[None]:
    """The process's umask set to *value* while the block runs."""
    old = os.umask(value)
    try:
        yield
    finally:
        os.umask(old)


@contextmanager
def no_data(folder: Path) -> Iterator[DataSource]:
    """A source for commands that must not read market data: opening it fails the test."""
    msg = f"this command opened the data source in {folder}"
    raise AssertionError(msg)
    yield  # unreachable: it makes this a generator, as @contextmanager needs


class Result(NamedTuple):
    code: int
    out: str
    err: str


@dataclass(frozen=True, slots=True)
class Cli:
    """``steadyhand-idx`` with its data directory at ``home``."""

    home: Path
    source: SourceFactory = no_data
    now: datetime = NOW

    @property
    def config(self) -> Path:
        return self.home / "steadyhand.toml"

    def __call__(self, *argv: str, stdin: str = "") -> Result:
        out, err = io.StringIO(), io.StringIO()
        env = {"STEADYHAND_HOME": str(self.home)}
        world = World(io.StringIO(stdin), out, err, env, lambda: self.now, self.source)
        code = main(list(argv), world)
        return Result(code, out.getvalue(), err.getvalue())

    def init(self, *, training: str = "new", exemption: str = "off") -> Result:
        """``init`` answered by its flags, as a script runs it."""
        result = self(
            "init", "--training", training, "--exemption", exemption, stdin="I understand\n"
        )
        assert result.code == 0, result.err
        return result


PLACEHOLDERS = tuple("Z" + "".join(letters) for letters in product("ABCDEFGHIJ", repeat=3))[:40]
"""Made-up codes that fill the LQ45 file to 45. No real LQ45 list is ever written into this
repository (core spec §9.4); these are excluded, so no strategy ever holds one."""

GOLDEN_CONFIG = """[account]
starting_cash_idr = 100_000_000

[goal]
monthly_income_target_idr = 1_000_000

[risk]
max_weight = "0.25"

[consent]
disclaimer_accepted = 2026-09-27
"""
"""The golden run's settings (``record_golden.settings``), so a CLI backtest over its window must
reproduce its figures exactly."""


def recorded_or_empty(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer for the five golden stocks, and no rows for a placeholder."""
    if ticker.removesuffix(".JK") in STOCKS:
        return recorded(ticker, start, end)
    return YahooHistory(ticker, (), ())


def _no_wait(seconds: float) -> None:
    del seconds


@contextmanager
def recorded_source(folder: Path) -> Iterator[DataSource]:
    """The recorded answers through the real ``YahooDataSource`` and the bar cache in *folder*,
    on the day they were recorded, as the golden test reads them."""
    yahoo = YahooDataSource(download=recorded_or_empty, sleep=_no_wait)
    with BarCache(folder / "cache.sqlite") as cache:
        yield CachedDataSource(yahoo, cache, today=lambda: RECORDED)


def write_universe(home: Path) -> None:
    """The operator's files: an LQ45 list of the five golden stocks and 40 placeholders from the
    golden run's first day, and exclusions for every placeholder."""
    members = ", ".join(f'"{code}"' for code in (*STOCKS, *PLACEHOLDERS))
    (home / "lq45_members.toml").write_text(
        f"schema = 1\n\n[[record]]\neffective = {START}\nannounced = {START}\n"
        'source = "steadyhand CLI test: the golden stocks and made-up codes, not an LQ45 list"\n'
        f'kind = "review"\nmembers = [{members}]\n',
        encoding="utf-8",
    )
    rows = "".join(f"{code},{START},,a made-up code with no data\n" for code in PLACEHOLDERS)
    (home / "exclusions.csv").write_text(f"symbol,from,to,reason\n{rows}", encoding="utf-8")


def market_cli(home: Path, config: str = GOLDEN_CONFIG) -> Cli:
    """``steadyhand-idx`` over the recorded data, with *config* and the operator's files."""
    home.mkdir(parents=True)
    (home / "steadyhand.toml").write_text(config, encoding="utf-8")
    write_universe(home)
    return Cli(home, recorded_source)


def paper_process(home: str, now: str, start: Event) -> None:
    """One ``paper run --catch-up`` in a process of its own, for the concurrency test: it waits
    for *start*, runs over the recorded data at *now*, and exits with the command's code."""
    start.wait()
    cli = Cli(Path(home), recorded_source, datetime.fromisoformat(now))
    sys.exit(cli("paper", "run", "--catch-up").code)


SCRIPT = Path(sys.executable).with_name("steadyhand-idx")
"""The console script the package installs, beside this interpreter."""


def installed(home: Path, *argv: str, stdin: str = "") -> Result:
    """Run the installed ``steadyhand-idx`` in its own process, with *home* as its data
    directory and no network: only commands that read no market data are run this way."""
    env = {"PATH": os.environ["PATH"], "HOME": str(home.parent), "STEADYHAND_HOME": str(home)}
    done = subprocess.run(  # noqa: S603 - the installed console script, with the test's arguments
        [str(SCRIPT), *argv], input=stdin, capture_output=True, text=True, env=env, check=False
    )
    return Result(done.returncode, done.stdout, done.stderr)
