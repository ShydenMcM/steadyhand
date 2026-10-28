"""The journeys of M5 spec §9.1, in-process. A unit test starts no process (#286), so M5a's
journeys run through the console script's own entry point here, and as a user runs them, the
installed ``steadyhand-idx`` in its own process per command, in
``tests/integration/cli/test_journeys_installed.py``. The paper journey runs over the made-up
market of ``short_world``; the same journey over the recorded golden window is in
``tests/integration/cli/test_journeys_golden.py`` (#282)."""

import stat
from dataclasses import replace
from pathlib import Path

from cli_world import (
    Cli,
    at,
    opened,
)
from short_world import SHORT_CONFIG, WEEK, uncached
from short_world import START as SHORT_START
from short_world import trading_days as short_trading_days
from short_world import write_universe as write_short_universe

from steadyhand import DISCLAIMER, RISK_HALT_DAILY_LOSS
from steadyhand_idx import __version__
from steadyhand_idx.config import load
from steadyhand_idx.notes import PAPER_RESUMED


def test_a_first_time_users_journey(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cli = Cli(home)
    started = cli("init", stdin="I understand\ny\n1\nn\n")
    assert started.code == 0, started.err
    assert started.out.startswith(DISCLAIMER)
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert stat.S_IMODE((home / "steadyhand.toml").stat().st_mode) == 0o600
    written = load(home / "steadyhand.toml")
    assert written.strategy == "dividend-growth"
    assert written.strategy_settings == {
        "instalments": 12,
        "min_stocks": 15,
        "max_stocks": 25,
        "growth_years": 5,
    }

    listed = cli("strategies")
    assert listed.code == 0
    assert "buy-and-hold     low" in listed.out
    assert "monthly-savings  low" in listed.out
    assert "dividend-growth  low" in listed.out
    assert "What this means" in listed.out

    explained = cli("explain", "buy-and-hold")
    assert explained.code == 0
    assert explained.out.startswith("# buy-and-hold\n")
    assert cli("explain", "dividend-growth").out.startswith("# dividend-growth\n")

    course = cli("learn")
    assert course.code == 0
    assert course.out.startswith("Module 1: Start here\n")
    assert cli("learn", "start.welcome").code == 0

    assert cli("training", "experienced").code == 0
    quiet = cli("strategies")
    assert "What this means" not in quiet.out
    assert cli("training").out.startswith("Training level: experienced\n")


def test_the_exit_codes_and_their_messages(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cli = Cli(home)
    assert cli("--version") == (0, f"steadyhand-idx {__version__}\n", "")
    helped = cli("--help")
    assert (helped.code, helped.err) == (0, "")
    assert helped.out.startswith("usage: steadyhand-idx ")
    unknown = cli("nonsense")
    assert unknown.code == 2
    assert unknown.err.startswith("steadyhand-idx: argument command: invalid choice: 'nonsense'")
    assert cli("explain", "nothing") == (
        2,
        "",
        "steadyhand-idx: no strategy named 'nothing'\n",
    )
    assert cli("learn", "nothing") == (
        2,
        "",
        "steadyhand-idx: no lesson named 'nothing'\n",
    )
    assert cli("training") == (
        2,
        "",
        (
            f"steadyhand-idx: there is no configuration at {home / 'steadyhand.toml'}; "
            "run steadyhand-idx init first\n"
        ),
    )
    refused = cli("init", stdin="no\n")
    assert refused.code == 2
    assert (
        refused.err == "steadyhand-idx: the disclaimer was not accepted, so nothing was written\n"
    )
    assert not home.exists()


# The paper trader's journey over the recorded golden window moved to
# tests/integration/cli/test_journeys_golden.py (#282), one run from the backtest to the run after
# a resume. Its stand-in over the made-up window takes the same steps in three phases, each from a
# fresh home (#407: the stand-in in one piece took 111 ms of own CPU under load, over the limit).


def paper_trader(tmp_path: Path) -> tuple[Cli, str]:
    """A home on the made-up market with training off, and the settings written to it."""
    home = tmp_path / "home"
    cli = Cli(home, uncached, at(SHORT_START))
    cli.init(training="off")
    write_short_universe(home)
    settings = SHORT_CONFIG + '\n[training]\nlevel = "off"\n'
    cli.config.write_text(settings, encoding="utf-8")
    return cli, settings


def test_a_paper_trader_backtests_the_week_first(tmp_path: Path) -> None:
    cli, _ = paper_trader(tmp_path)
    tested = cli("backtest", *WEEK)
    assert tested.code == 0, tested.err
    assert tested.out.startswith("Backtest: buy-and-hold, 2021-12-15 to 2021-12-21")


def test_a_paper_trader_opens_the_account_and_reads_its_reports(tmp_path: Path) -> None:
    cli, _ = paper_trader(tmp_path)
    first = cli("paper", "run")
    assert first.code == 0, first.err
    assert first.out.startswith("2021-12-15: 0 fill(s), 3 order(s) queued, value IDR 100,000,000")
    again = cli("paper", "run")
    assert again.code == 0
    assert again.out.startswith("already up to date for 2021-12-15\n")
    status = cli("paper", "status")
    assert status.code == 0
    assert status.out.startswith("Paper account opened on 2021-12-15, running buy-and-hold")
    report = cli("report")
    assert report.code == 0
    assert report.out.startswith("Day report for 2021-12-15\n")
    income = cli("report", "--income")
    assert income.code == 0, income.err
    assert income.out.startswith("Income as of 2021-12-15\n")


def test_a_paper_trader_is_halted_resumes_and_runs_on(tmp_path: Path) -> None:
    cli, settings = paper_trader(tmp_path)
    first = cli("paper", "run")
    assert first.code == 0, first.err
    jumpy = settings.replace(
        'max_weight = "0.35"\n', 'max_weight = "0.35"\ndaily_loss_limit = "0.001"\n'
    )
    assert jumpy != settings
    cli.config.write_text(jumpy, encoding="utf-8")
    second = replace(cli, now=at(short_trading_days()[1]))
    halted = second("paper", "run")
    assert halted.code == 3
    assert "steadyhand-idx resume buy-and-hold" in halted.err
    resumed = second("resume", "buy-and-hold", stdin="resume\n")
    assert resumed.code == 0, resumed.err
    assert resumed.out.endswith(
        f"Resumed. From the next day run, the strategy's orders are placed again.\n\n{DISCLAIMER}\n"
    )
    later = replace(cli, now=at(short_trading_days()[2]))("paper", "run")
    assert later.code == 0, later.err
    with opened(cli) as store:
        assert store.days() == short_trading_days()[:3]
        keys = [line.note.key for line in store.audit()]
    assert keys.index(PAPER_RESUMED) == keys.index(RISK_HALT_DAILY_LOSS) + 1
