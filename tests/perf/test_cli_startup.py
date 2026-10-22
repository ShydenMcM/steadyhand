"""The command starts quickly (M5 spec §9.3): each command that reads no market data answers in
under half a second, the best of five runs. Measured in the M5a scratch build at about 0.07 s;
the budget leaves room for a slower CI runner."""

import time
from pathlib import Path

import pytest
from cli_world import installed
from perf_budget import Check

BUDGET_SECONDS = 0.5


@pytest.mark.perf
@pytest.mark.parametrize(
    "argv", [("--version",), ("strategies",), ("learn",), ("explain", "buy-and-hold")]
)
def test_a_command_that_reads_no_market_data_starts_within_budget(
    tmp_path: Path, argv: tuple[str, ...], within_budget: Check
) -> None:
    best = float("inf")
    for _ in range(5):  # runtime population: five timing samples of one command, the best judged
        started = time.perf_counter()
        result = installed(tmp_path / "home", *argv)
        best = min(best, time.perf_counter() - started)
        assert result.code == 0, result.err
    within_budget(best, BUDGET_SECONDS)
