"""Every day of the made-up window's backtests saved and read back (M5 spec §9.2 "Codec").

The stand-ins of the golden runs' codec checks, which run in the integration suite
(``tests/integration/golden/test_golden_snapshot_recorded.py``, #292): the made-up window's
switch-off run at a 30% limit per stock (19 days, with cuts, skipped orders, a split and a paid
dividend) and its switch-on run (19 days,
ending with its one claim reinvested in part).
"""

import pytest
from short_world import RUNS, library_run

from steadyhand import (
    BacktestResult,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
)


@pytest.fixture(scope="module")
def golden() -> tuple[BacktestResult, BacktestResult]:
    return library_run(max_weight="0.30"), RUNS["exemption-on"]()


@pytest.mark.parametrize(("which", "days"), [(0, 19), (1, 19)], ids=["off", "on"])
def test_every_day_report_of_both_golden_runs_reads_back_equal(
    golden: tuple[BacktestResult, BacktestResult], which: int, days: int
) -> None:
    result = golden[which]
    assert len(result.run.reports) == days
    for report in result.run.reports:  # runtime population: the reports the run produced
        assert decode_report(from_json(to_json(encode_report(report)))) == report


def test_the_switch_on_run_ends_holding_its_claim(
    golden: tuple[BacktestResult, BacktestResult],
) -> None:
    _, on = golden
    assert len(on.run.final.holdings.claims) == 1


@pytest.mark.parametrize("which", [0, 1], ids=["off", "on"])
def test_the_final_state_of_both_golden_runs_reads_back_equal(
    golden: tuple[BacktestResult, BacktestResult], which: int
) -> None:
    final = golden[which].run.final
    assert decode_state(from_json(to_json(encode_state(final)))) == final
