"""``paper run`` over the recorded golden window ends where the backtest does (M5 spec §6, §9.2),
moved out of unit by #292: each runs the paper account over the recorded year, or most of a month
of it day by day, through the real source, cache and state database, over the unit limit of
0.07 s of its own CPU in its heaviest measured run (develop, 2026-10-13: 1.2 s to 1.9 s).

The unit suite keeps a stand-in of each, of the same name, in ``tests/cli/test_paper_run.py``:
the same runs over nineteen trading days of three made-up stocks across the turn of 2021
(``tests/cli/short_world.py``), where ``dividend-growth`` reviews again on 3 January 2022.

#282 moved one more: thirty-one days run with ``--catch-up`` (0.066 s to 0.079 s of own CPU on
the laptop, 2026-10-14). The window is too short for 31 days, so its stand-in lowers the cap to 3.
"""

from datetime import date
from pathlib import Path

from cli_world import (
    GROWTH_CONFIG,
    golden_backtest,
    opened,
    paper,
    run_on,
    trading_days,
)
from record_golden import END, START

from steadyhand_idx.paper import CATCH_UP_CAP


def test_a_paper_account_run_day_by_day_ends_where_the_backtest_does(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    days = trading_days()[:12]
    for day in days:  # runtime population: one journey, each day on the state the last left
        assert run_on(cli, day).code == 0
    expected = golden_backtest(cli, days[-1]).run
    with opened(cli) as store:
        assert store.reports() == expected.reports
        account = store.account()
        assert account is not None
        assert account.state == expected.final


def test_a_year_caught_up_in_one_run_ends_where_the_backtest_does(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, END, "--catch-up")
    assert result.code == 0, result.err
    expected = golden_backtest(cli, END).run
    assert len(expected.reports) == len(trading_days()) == 248
    with opened(cli) as store:
        assert store.reports() == expected.reports
        account = store.account()
        assert account is not None
        assert account.state == expected.final


def test_dividend_growth_reviews_again_on_the_first_trading_day_of_2022(tmp_path: Path) -> None:
    cli = paper(tmp_path, GROWTH_CONFIG)
    run_on(cli, START)
    result = run_on(cli, END, "--catch-up")
    assert result.code == 0, result.err
    expected = golden_backtest(cli, END).run
    with opened(cli) as store:
        reports = store.reports()
        account = store.account()
    assert reports == expected.reports
    assert account is not None
    assert account.state == expected.final
    # 3 January 2022 tests 2019 to 2021: TLKM now passes and UNVR no longer does. The orders
    # it places that day fill on the 4th.
    filled = {
        (fill.order.instrument.symbol, fill.order.side.value)
        for report in reports
        if report.day == date(2022, 1, 4)
        for fill in report.fills
    }
    assert {("TLKM", "buy"), ("UNVR", "sell")} <= filled
    assert account.state.memory == {"set": "IDX:BBCA IDX:TLKM", "year": "2022"}


def test_thirty_one_days_to_run_proceed_with_catch_up(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, trading_days()[CATCH_UP_CAP + 1], "--catch-up")
    assert result.code == 0, result.err
    with opened(cli) as store:
        assert store.days() == trading_days()[: CATCH_UP_CAP + 2]
