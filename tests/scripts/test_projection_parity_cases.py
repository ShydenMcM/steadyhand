"""The income projection's parity harness cases (#254 AC1, spec §9.1): seeded holdings with five
years of dividends, whose dividend growth and projection Python's ``dividend_growth`` and
``project`` give, for core's ``incomeGrowth`` and ``project`` to give identically
(``extension/packages/core/test/parity-projection.test.ts``). The committed file is checked
against a fresh run in ``tests/integration/scripts/test_core_fixtures.py``."""

from functools import cache
from typing import Any

import core_fixtures
import pytest

from steadyhand.income import OPTIMISTIC_GROWTH_CAP


@cache
def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = core_fixtures.projection_cases()["cases"]
    return cases


def _outcomes() -> set[str]:
    return {scenario["outcome"] for case in _cases() for scenario in case["scenarios"]}


def test_the_same_seed_gives_the_same_cases() -> None:
    assert core_fixtures.projection_cases(7, 5) == core_fixtures.projection_cases(7, 5)


def test_another_seed_gives_other_cases() -> None:
    first = core_fixtures.projection_cases(7, 5)["cases"]
    assert first != core_fixtures.projection_cases(8, 5)["cases"]


def test_every_outcome_is_reached_somewhere() -> None:
    assert _outcomes() == {"reached", "not-within", "cannot"}


def test_a_goal_is_met_at_once_somewhere() -> None:
    years = [
        scenario["years"]
        for case in _cases()
        for scenario in case["scenarios"]
        if scenario["outcome"] == "reached"
    ]
    assert "0.0" in years
    assert any(year != "0.0" for year in years)


def test_growth_falls_rises_past_both_caps_and_meets_a_short_history() -> None:
    growths = [float(case["portfolioGrowth"]) for case in _cases()]
    assert any(growth < 0 for growth in growths)
    assert any(growth > float(OPTIMISTIC_GROWTH_CAP) for growth in growths)
    assert any(case["shortHistory"] for case in _cases())


def test_some_cases_add_a_contribution_and_some_add_none() -> None:
    contributions = {case["contribution"] == "0" for case in _cases()}
    assert contributions == {True, False}


def test_some_holdings_split_between_the_two_years() -> None:
    assert any(stock["splits"] for case in _cases() for stock in case["stocks"])


@pytest.mark.parametrize("count", [0, -1])
def test_a_harness_of_no_cases_is_refused(count: int) -> None:
    with pytest.raises(
        ValueError, match=rf"^the projection parity harness needs a case, got {count}$"
    ):
        core_fixtures.projection_cases(1, count)
