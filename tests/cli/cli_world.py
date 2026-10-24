"""Running ``steadyhand-idx`` in-process, as the console script does, with a fixed clock (M5 spec
§9.1). Nothing of steadyhand's is stubbed: the tests pass ``main`` the same kind of ``World`` the
console script builds, with text streams, an environment naming a temporary data directory, a
fixed clock and a data source."""

import io
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta, timezone
from functools import cache
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import NamedTuple

from record_cli_seed import PLACEHOLDERS, SEED, recorded_or_empty
from record_golden import END, RECORDED, START, STOCKS, replay

from steadyhand import DISCLAIMER, STRATEGIES, BacktestResult, DataSource, Market, backtest
from steadyhand_idx import BarCache, CachedDataSource
from steadyhand_idx.cli import SourceFactory, World, main
from steadyhand_idx.config import load
from steadyhand_idx.paper import days_to_run
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.state import STATE_FILE, StateStore
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe

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
    """``steadyhand-idx`` with its data directory at ``home``, and *env* besides."""

    home: Path
    source: SourceFactory = no_data
    now: datetime = NOW
    env: Mapping[str, str] = field(default_factory=dict)

    @property
    def config(self) -> Path:
        return self.home / "steadyhand.toml"

    def __call__(self, *argv: str, stdin: str = "") -> Result:
        out, err = io.StringIO(), io.StringIO()
        env = {**self.env, "STEADYHAND_HOME": str(self.home)}
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


GOLDEN_CONFIG = """[account]
starting_cash_idr = 100_000_000

[goal]
monthly_income_target_idr = 1_000_000

[strategy]
name = "buy-and-hold"

[risk]
max_weight = "0.25"

[consent]
disclaimer_accepted = 2026-09-27
"""
"""The golden run's settings (``record_golden.settings``), so a CLI backtest over its window must
reproduce its figures exactly. It names ``buy-and-hold``, the golden run's strategy, since the
default is ``dividend-growth`` (M6 spec §7)."""

GROWTH_CONFIG = GOLDEN_CONFIG.replace(
    'name = "buy-and-hold"',
    'name = "dividend-growth"\nmin_stocks = 2\nmax_stocks = 2\ngrowth_years = 2',
)
"""The golden settings running ``dividend-growth`` with the golden run's values
(``record_golden.VALUES``): a two-year test, whose look-back fits in the recordings."""

RESTORED = (
    "BBRI: Yahoo's prices from 2014-01-06 to 2021-09-07 carry an adjustment Yahoo does not "
    "report, so steadyhand restored them: every price and dividend in that span is multiplied "
    "by 1.100019, proven by 7,380 prices that fit the IDX tick grid at that factor and at no "
    "other."
)
"""The golden window's one warning: BBRI's restoration in its whole recording (#160)."""


@cache
def seed() -> bytes:
    """The bytes of a bar cache holding the recorded seed (``record_cli_seed``), built once per
    process: the cache's own migrations make the schema, and the seed's rows go in."""
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "cache.sqlite"
        BarCache(path).close()
        with closing(sqlite3.connect(path)) as db:
            db.executescript(SEED.read_text(encoding="utf-8"))
        return path.read_bytes()


@contextmanager
def recorded_source(folder: Path) -> Iterator[DataSource]:
    """The recorded answers through the real ``YahooDataSource`` and the bar cache in *folder*,
    on the day they were recorded, as the golden test reads them. A folder with no bar cache
    starts from the seed, as if a first run had filled it; a cache already there is kept."""
    path = folder / "cache.sqlite"
    if not path.exists():
        path.write_bytes(seed())
    with BarCache(path) as cache:
        yield CachedDataSource(replay(recorded_or_empty), cache, today=lambda: RECORDED)


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


WIB = timezone(timedelta(hours=7))


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


@cache
def trading_days() -> tuple[date, ...]:
    """The golden window's trading days, from the IDX calendar."""
    return days_to_run(START - timedelta(days=1), END, rules())


def at(day: date, hour: int = 17, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=WIB)


def paper(tmp_path: Path, config: str = GOLDEN_CONFIG) -> Cli:
    return market_cli(tmp_path / "home", config)


def run_on(cli: Cli, day: date, *extra: str) -> Result:
    return replace(cli, now=at(day))("paper", "run", *extra)


# The golden window's accounts for ``paper status``, ``report`` and ``resume``: one home for the
# unit tests (tests/cli/test_paper_commands.py) and the runs moved out of unit by #292
# (tests/integration/cli/test_paper_commands_golden.py), so the two cannot drift apart (#374).

QUIET = '\n[training]\nlevel = "off"\n'
"""Training off: a page is then its lines and the disclaimer, nothing else."""

EXEMPT = "\n[tax]\ndividend_reinvestment_exemption = true\n"

JUMPY = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\ndaily_loss_limit = "0.001"\n'
)
"""A daily-loss limit the golden run's second day breaches (as ``paper run``'s halt test)."""

TIGHT = GOLDEN_CONFIG.replace('[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.19"\n')
"""A 19% limit per stock, under buy-and-hold's 20% of each of the five: its first orders are cut to
the limit and its later top-ups skipped. With BBRI's prices restored (#160), the golden settings
spread the money five ways and never block an order."""


def quiet(config: str = GOLDEN_CONFIG) -> str:
    assert "[training]" not in config
    return config + QUIET


def page(text: str) -> str:
    """The page as a command prints it with training off."""
    return f"{text}\n\n{DISCLAIMER}\n"


def run_from(cli: Cli, start: date, day: date) -> Cli:
    """*cli*'s account opened on *start* and run up to *day*, and *cli* set at *day*."""
    assert run_on(cli, start).code == 0
    if day != start:
        done = run_on(cli, day, "--catch-up")
        assert done.code in (0, 3), done.err
    return replace(cli, now=at(day))


def ran_to(tmp_path: Path, day: date, config: str = GOLDEN_CONFIG) -> Cli:
    """An account opened on the golden window's first day and run up to *day*."""
    return run_from(paper(tmp_path, config), START, day)


def halted(tmp_path: Path) -> Cli:
    """An account halted by the daily-loss limit on 2021-02-02, the day it is left on."""
    cli = paper(tmp_path, quiet(JUMPY))
    assert run_on(cli, START).code == 0
    assert run_on(cli, trading_days()[1]).code == 3
    return replace(cli, now=at(trading_days()[1]), env={"USER": "tester"})


@contextmanager
def opened(cli: Cli) -> Iterator[StateStore]:
    with StateStore(cli.home / STATE_FILE) as store:
        yield store


def tables(cli: Cli) -> dict[str, list[tuple[object, ...]]]:
    """Every row of the account, the day reports and the audit log, as SQLite holds them."""
    database = sqlite3.connect(cli.home / STATE_FILE)
    try:
        return {
            table: database.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608
            for table in ("account", "day_reports", "audit")
        }
    finally:
        database.close()


def golden_backtest(
    cli: Cli, end: date, *, goal: bool = False, start: date = START
) -> BacktestResult:
    """The configured strategy, with its look-back, from *start*, the golden window's first day
    by default, to *end*, as ``backtest`` runs it over the same configuration, universe files and
    recorded data. Without
    the income goal unless *goal*: its report reads five years before *end* (M4 spec §8), which
    the recordings do not cover for an early *end*, and it changes neither the states nor the
    day reports."""
    config = load(cli.config)
    universe = Lq45Universe(
        Lq45Membership.load(config.lq45_members), Exclusions.load(config.exclusions)
    )
    entry = STRATEGIES[config.strategy]
    lookback = entry.lookback_years(config.strategy_settings)
    chosen = replace(config.settings, lookback_years=lookback)
    with recorded_source(cli.home) as source:
        market = Market(universe, source, IdxMarketRules(broker_fees=config.broker_fees))
        return backtest(
            entry(config.strategy_settings),
            market,
            start,
            end,
            chosen if goal else replace(chosen, goal=None),
        )
