"""The restated-dividend parity harness's cases (#232 AC4, spec §6.6): seeded dividends that
Python's ``_restated_gross`` restates, for core's ``restatedGross`` to give identically
(``extension/packages/core/test/parity-restated.test.ts``). The committed file is checked against
a fresh run in ``tests/integration/scripts/test_core_fixtures.py``."""

from decimal import Decimal

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
            split["symbol"] == symbol and case["exDate"] <= split["exDate"] <= case["asOf"]
            for split in splits
        )

    assert any(counted(case, "BBCA") for case in cases)
    assert any(counted(case, "TLKM") for case in cases)
    assert any(not case["splits"] for case in cases)


def test_another_stock_s_split_leaves_the_gross_unrestated() -> None:
    # Python's `_split_ratio` takes one stock's actions, as its callers pass them: the cases give
    # it the dividend stock's splits only, so a TLKM split never restates a BBCA dividend.
    def in_window(case: dict[str, object], symbol: str) -> bool:
        splits = case["splits"]
        assert isinstance(splits, list)
        return any(
            split["symbol"] == symbol and case["exDate"] <= split["exDate"] <= case["asOf"]
            for split in splits
        )

    others_only = [
        case
        for case in core_fixtures.restated_cases()["cases"]
        if in_window(case, "TLKM") and not in_window(case, "BBCA")
    ]
    assert others_only
    for case in others_only:
        per_share = Decimal(str(case["grossPerShare"]))
        assert case["gross"] == str(int(per_share * int(str(case["shares"])))), case["name"]


@pytest.mark.parametrize("count", [0, -1])
def test_a_harness_of_no_cases_is_refused(count: int) -> None:
    with pytest.raises(
        ValueError, match=rf"^the restated parity harness needs a case, got {count}$"
    ):
        core_fixtures.restated_cases(7, count)
