"""Proving BBRI's unreported price factor over its whole recorded history finishes inside a
second (#160 spec §9.3).

The recording holds 3,135 days from 2014-01-06. 1,845 of them are the proof's evidence: a price
off whole rupiah on a day that is not a flat row with no volume (69 such flat days have one too).
Reading the evidence and finding the runs took 0.024 to 0.028 s five times in a row at a load of
12 on six cores; the budget leaves about thirty-five times that for a slower CI runner.
"""

import time
from pathlib import Path

import pytest

from steadyhand_idx.factor import find_runs
from steadyhand_idx.yahoo import evidence, history_from_json

BUDGET_SECONDS = 1
RECORDING = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "yahoo"
    / "BBRI.JK_2014-01-06_2026-10-01.json"
)


@pytest.mark.perf
def test_bbri_s_whole_history_is_proven_inside_the_budget() -> None:
    history = history_from_json(RECORDING)
    started = time.perf_counter()
    (run,) = find_runs(evidence(history))
    elapsed = time.perf_counter() - started
    assert run.factor is not None
    assert elapsed < BUDGET_SECONDS, f"{elapsed:.2f} s"
