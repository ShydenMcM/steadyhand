"""The halt parity harness's cases (#236 AC6, spec §8): seeded runs of after-close reads with
deposits and withdrawals, that Python's ``UnitValue`` and ``RiskManager.halt`` answer, for core's
``riskState`` to give identically (``extension/packages/core/test/parity-halts.test.ts``). The
committed file is checked against a fresh run in
``tests/integration/scripts/test_core_fixtures.py``."""

from datetime import date
from typing import Any

import core_fixtures
import pytest


def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = core_fixtures.halt_cases()["cases"]
    return cases


def test_the_same_seed_gives_the_same_cases() -> None:
    assert core_fixtures.halt_cases(7, 5) == core_fixtures.halt_cases(7, 5)


def test_another_seed_gives_other_cases() -> None:
    assert core_fixtures.halt_cases(7, 5)["cases"] != core_fixtures.halt_cases(8, 5)["cases"]


def _codes() -> set[str | None]:
    return {case["halt"]["code"] if case["halt"] else None for case in _cases()}


def test_the_committed_cases_reach_each_halt_and_none() -> None:
    assert _codes() == {None, "risk.halt.daily_loss", "risk.halt.drawdown"}


def test_some_halts_come_after_a_skipped_trading_day_and_carry_no_text() -> None:
    halts = [case["halt"] for case in _cases() if case["halt"]]
    assert any("text" in halt for halt in halts)
    assert any("text" not in halt for halt in halts)


def test_moves_fall_on_a_read_s_own_day_and_on_days_with_no_read() -> None:
    on_read = 0
    between = 0
    for case in _cases():
        days = {read["day"] for read in case["reads"]}
        for movement in case["movements"]:
            if movement["day"] in days:
                on_read += 1
            else:
                between += 1
    assert on_read > 0
    assert between > 0


def test_moves_include_deposits_withdrawals_and_weekend_days() -> None:
    movements = [movement for case in _cases() for movement in case["movements"]]
    assert {movement["kind"] for movement in movements} == {"deposit", "withdrawal"}
    assert any(date.fromisoformat(movement["day"]).weekday() >= 5 for movement in movements)


@pytest.mark.parametrize("journeys", [0, -1])
def test_a_harness_of_no_journeys_is_refused(journeys: int) -> None:
    with pytest.raises(
        ValueError, match=rf"^the halt parity harness needs a journey, got {journeys}$"
    ):
        core_fixtures.halt_cases(1, journeys)
