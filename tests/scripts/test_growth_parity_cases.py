"""The dividend-growth parity harness's cases (#230 AC5, spec §14.4): journeys of advice days
that Python's dividend-growth decides, for core's to decide identically
(``extension/packages/core/test/parity-dividend-growth.test.ts``). The committed file is checked
against a fresh run in ``tests/integration/scripts/test_core_fixtures.py``."""

import core_fixtures
import pytest

from steadyhand.strategies import DividendGrowthStrategy


def test_the_same_seed_gives_the_same_journeys() -> None:
    assert core_fixtures.growth_cases(7, 3) == core_fixtures.growth_cases(7, 3)


def test_another_seed_gives_other_journeys() -> None:
    assert core_fixtures.growth_cases(7, 3)["cases"] != core_fixtures.growth_cases(8, 3)["cases"]


def test_the_committed_journeys_review_and_keep_between_reviews() -> None:
    cases = core_fixtures.growth_cases()["cases"]
    first = [case for case in cases if not case["memory"]]
    new_year = [case for case in cases if case["memory"] and case["read"]]
    kept = [case for case in cases if not case["read"]]
    assert [bool(group) for group in (first, new_year, kept)] == [True] * 3


def test_only_a_review_day_carries_the_dividend_record() -> None:
    for case in core_fixtures.growth_cases()["cases"]:
        assert case["read"] is (case["memory"].get("year") != case["day"][:4])
        assert bool(case["dividends"]) is case["read"]


def test_the_committed_journeys_reach_too_few_passers_and_no_passer() -> None:
    reviews = [case for case in core_fixtures.growth_cases()["cases"] if case["read"]]
    too_few = [case for case in reviews if case["expected"]["notes"]]
    none = [case for case in reviews if not case["expected"]["weights"]]
    assert too_few
    assert none


def test_the_committed_journeys_reach_the_spread_of_pay_months(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spread = DividendGrowthStrategy._spread
    calls: list[int] = []

    def counted(self: DividendGrowthStrategy, *args: object) -> object:
        calls.append(1)
        return spread(self, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(DividendGrowthStrategy, "_spread", counted)
    core_fixtures.growth_cases()
    assert len(calls) >= 10


def test_the_committed_journeys_restate_by_splits_and_hold_announced_dividends() -> None:
    reviews = [case for case in core_fixtures.growth_cases()["cases"] if case["read"]]
    assert any(case["splits"] for case in reviews)
    assert any(
        dividend["exDate"] > case["day"] for case in reviews for dividend in case["dividends"]
    )


@pytest.mark.parametrize("journeys", [0, -1])
def test_a_harness_of_no_journeys_is_refused(journeys: int) -> None:
    with pytest.raises(
        ValueError, match=rf"^the dividend-growth parity harness needs a journey, got {journeys}$"
    ):
        core_fixtures.growth_cases(journeys=journeys)
