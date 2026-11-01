"""The strategy parity harness's cases (#229 AC6, spec §14.4): journeys of advice days that
Python's buy-and-hold and monthly-savings decide, for core's strategies to decide identically
(``extension/packages/core/test/parity-strategies.test.ts``). The committed file is checked
against a fresh run in ``tests/integration/scripts/test_core_fixtures.py``."""

import core_fixtures
import pytest


def test_the_same_seed_gives_the_same_journeys() -> None:
    assert core_fixtures.strategy_cases(7, 5) == core_fixtures.strategy_cases(7, 5)


def test_another_seed_gives_other_journeys() -> None:
    assert (
        core_fixtures.strategy_cases(7, 5)["cases"] != core_fixtures.strategy_cases(8, 5)["cases"]
    )


def test_the_committed_journeys_judge_both_strategies_at_every_instalment_choice() -> None:
    cases = core_fixtures.strategy_cases()["cases"]
    assert {case["strategy"] for case in cases} == {"buy-and-hold", "monthly-savings"}
    drawn = {int(case["instalments"]) for case in cases if case["strategy"] == "monthly-savings"}
    assert drawn == set(core_fixtures.INSTALMENT_CHOICES)


def test_the_committed_journeys_reach_each_turn_of_monthly_savings() -> None:
    # A first day, a day later in a month that bought, a new month, the last instalment and the
    # months after it, and a month with nothing to buy: each where the strategy branches.
    days = [
        case
        for case in core_fixtures.strategy_cases()["cases"]
        if case["strategy"] == "monthly-savings"
    ]
    first = [case for case in days if not case["memory"]]
    same_month = [case for case in days if case["memory"].get("month") == case["day"][:7]]
    new_month = [
        case
        for case in days
        if case["memory"].get("month") not in (None, case["day"][:7]) and case["buyable"]
    ]
    spent_out = [case for case in days if case["memory"].get("due") == "0"]
    nothing = [case for case in days if not case["buyable"]]
    assert [bool(group) for group in (first, same_month, new_month, spent_out, nothing)] == [
        True
    ] * 5


def test_the_committed_journeys_carry_a_set_from_one_day_to_the_next() -> None:
    days = [
        case
        for case in core_fixtures.strategy_cases()["cases"]
        if case["strategy"] == "buy-and-hold"
    ]
    assert any("set" in case["memory"] for case in days)


@pytest.mark.parametrize("journeys", [0, -1])
def test_a_harness_of_no_journeys_is_refused(journeys: int) -> None:
    with pytest.raises(
        ValueError, match=rf"^the strategy parity harness needs a journey, got {journeys}$"
    ):
        core_fixtures.strategy_cases(7, journeys)
