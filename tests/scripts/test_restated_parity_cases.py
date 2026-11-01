"""The restated-dividend parity harness's cases (#232 AC4, spec §6.6): seeded dividends that
Python's ``_restated_gross`` restates, for core's ``restatedGross`` to give identically
(``extension/packages/core/test/parity-restated.test.ts``). The committed file is checked against
a fresh run in ``tests/integration/scripts/test_core_fixtures.py``."""

import core_fixtures
import pytest


def test_the_same_seed_gives_the_same_cases() -> None:
    assert core_fixtures.restated_cases(7, 20) == core_fixtures.restated_cases(7, 20)


def test_another_seed_gives_other_cases() -> None:
    assert (
        core_fixtures.restated_cases(7, 20)["cases"] != core_fixtures.restated_cases(8, 20)["cases"]
    )


def test_the_committed_cases_restate_by_a_split_and_pass_over_others() -> None:
    cases = core_fixtures.restated_cases()["cases"]

    def counted(case: dict[str, object], symbol: str) -> bool:
        splits = case["splits"]
        assert isinstance(splits, list)
        return any(
            split["symbol"] == symbol and case["exDate"] <= split["exDate"] <= case["asOf"]  # type: ignore[operator]
            for split in splits
        )

    assert any(counted(case, "BBCA") for case in cases)
    assert any(counted(case, "TLKM") for case in cases)
    assert any(not case["splits"] for case in cases)


@pytest.mark.parametrize("count", [0, -1])
def test_a_harness_of_no_cases_is_refused(count: int) -> None:
    with pytest.raises(
        ValueError, match=rf"^the restated parity harness needs a case, got {count}$"
    ):
        core_fixtures.restated_cases(7, count)
