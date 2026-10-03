"""Every day of the golden backtests saved and read back (M5 spec §9.2 "Codec").

Both recorded runs go through the codec: the switch-off run (248 days, with rejected orders, a
cut and paid dividends) and the switch-on run (307 days, ending with five open claims).
"""

from pathlib import Path

import pytest
from record_golden import run, run_exempt

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
def golden(tmp_path_factory: pytest.TempPathFactory) -> tuple[BacktestResult, BacktestResult]:
    folder: Path = tmp_path_factory.mktemp("golden")
    return run(folder / "off"), run_exempt(folder / "on")


def test_every_day_report_of_both_golden_runs_reads_back_equal(
    golden: tuple[BacktestResult, BacktestResult],
) -> None:
    off, on = golden
    assert (len(off.run.reports), len(on.run.reports)) == (248, 307)
    for result in golden:
        for report in result.run.reports:
            assert decode_report(from_json(to_json(encode_report(report)))) == report


def test_the_final_state_of_both_golden_runs_reads_back_equal(
    golden: tuple[BacktestResult, BacktestResult],
) -> None:
    off, on = golden
    assert len(on.run.final.holdings.claims) == 6
    for result in (off, on):
        final = result.run.final
        assert decode_state(from_json(to_json(encode_state(final)))) == final
