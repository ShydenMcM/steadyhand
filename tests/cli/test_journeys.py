"""The journeys of M5 spec §9.1, in-process. A unit test starts no process (#286), so M5a's
journeys run through the console script's own entry point here, and as a user runs them, the
installed ``steadyhand-idx`` in its own process per command, in
``tests/integration/cli/test_journeys_installed.py``. The paper journey reads market data, so it
runs over the recorded Yahoo answers, as every ``paper`` test does."""

import stat
from dataclasses import replace
from pathlib import Path

from cli_world import (
    GOLDEN_CONFIG,
    Cli,
    at,
    opened,
    recorded_source,
    trading_days,
    write_universe,
)
from record_golden import START

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


def test_a_paper_traders_journey(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cli = Cli(home, recorded_source, at(START))
    cli.init(training="off")
    write_universe(home)
    settings = GOLDEN_CONFIG + '\n[training]\nlevel = "off"\n'
    cli.config.write_text(settings, encoding="utf-8")

    # The golden window: an income report reads five years back, which the recordings cover
    # for this last day (M4 spec §8).
    tested = cli("backtest", "--from", "2021-02-01", "--to", "2022-01-31")
    assert tested.code == 0, tested.err
    assert tested.out.startswith("Backtest: buy-and-hold, 2021-02-01 to 2022-01-31")

    first = cli("paper", "run")
    assert first.code == 0, first.err
    assert first.out.startswith("2021-02-01: 0 fill(s), 5 order(s) queued, value IDR 100,000,000")
    again = cli("paper", "run")
    assert again.code == 0
    assert again.out.startswith("already up to date for 2021-02-01\n")
    status = cli("paper", "status")
    assert status.code == 0
    assert status.out.startswith("Paper account opened on 2021-02-01, running buy-and-hold")
    report = cli("report")
    assert report.code == 0
    assert report.out.startswith("Day report for 2021-02-01\n")
    income = cli("report", "--income")
    assert income.code == 0, income.err
    assert income.out.startswith("Income as of 2021-02-01\n")

    jumpy = settings.replace(
        'max_weight = "0.25"\n', 'max_weight = "0.25"\ndaily_loss_limit = "0.001"\n'
    )
    assert jumpy != settings
    cli.config.write_text(jumpy, encoding="utf-8")
    second = replace(cli, now=at(trading_days()[1]), env={"USER": "trader"})
    halted = second("paper", "run")
    assert halted.code == 3
    assert "steadyhand-idx resume buy-and-hold" in halted.err
    resumed = second("resume", "buy-and-hold", stdin="resume\n")
    assert resumed.code == 0, resumed.err
    assert resumed.out.endswith(
        f"Resumed. From the next day run, the strategy's orders are placed again.\n\n{DISCLAIMER}\n"
    )
    later = replace(cli, now=at(trading_days()[2]))("paper", "run")
    assert later.code == 0, later.err
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        keys = [line.note.key for line in store.audit()]
    assert keys.index(PAPER_RESUMED) == keys.index(RISK_HALT_DAILY_LOSS) + 1
