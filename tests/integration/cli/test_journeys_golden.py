"""The paper trader's journey of M5 spec §9.1 over the recorded golden window, moved out of unit by
#282: it backtests a recorded year and runs the paper account, its reports, a halt and a resume
through the real source, cache and state database, over the unit limit of 0.07 s of its own CPU
in its heaviest measured run (laptop, 2026-10-14: 0.23 s to 0.41 s).

The unit suite keeps a stand-in of the same name in ``tests/cli/test_journeys.py``: the same
journey over nineteen trading days of three made-up stocks (``tests/cli/short_world.py``).
"""

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
from steadyhand_idx.notes import PAPER_RESUMED


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
    second = replace(cli, now=at(trading_days()[1]))
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
