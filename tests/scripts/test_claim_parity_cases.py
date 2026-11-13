"""The exemption claims' parity harness cases (#255 AC1, spec §9.2): seeded dividends received and
purchases, which Python's ``cover_claims`` and ``settle_claims`` answer, for core's
``coverClaims`` and ``claimsReport`` to answer identically
(``extension/packages/core/test/parity-claims.test.ts``). The committed file is checked against a
fresh run in ``tests/integration/scripts/test_core_fixtures.py``."""

from functools import cache
from typing import Any

import core_fixtures
import pytest


@cache
def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = core_fixtures.claim_cases()["cases"]
    return cases


def test_the_same_seed_gives_the_same_cases() -> None:
    assert core_fixtures.claim_cases(7, 5) == core_fixtures.claim_cases(7, 5)


def test_another_seed_gives_other_cases() -> None:
    assert core_fixtures.claim_cases(7, 5)["cases"] != core_fixtures.claim_cases(8, 5)["cases"]


def test_some_dividends_are_not_exemptable() -> None:
    assert any(case["notExemptable"] for case in _cases())


def test_some_deadlines_are_missed_and_some_are_not() -> None:
    owed = {case["owed"] != "0" for case in _cases()}
    assert owed == {True, False}


def test_claims_are_left_whole_part_covered_and_fully_covered() -> None:
    claims = [claim for case in _cases() for claim in case["claims"]]
    assert any(claim["uncovered"] == claim["gross"] for claim in claims)
    assert any(claim["uncovered"] == "0" for claim in claims)
    assert any(claim["gross"] != claim["uncovered"] != "0" for claim in claims)


def test_some_claims_are_covered_by_more_than_one_purchase() -> None:
    assert any(len(claim["protections"]) > 1 for case in _cases() for claim in case["claims"])


def test_some_purchases_are_protected_past_the_dividends_own_year() -> None:
    assert any(
        int(until[:4]) > int(claim["received"][:4]) + 2
        for case in _cases()
        for claim in case["claims"]
        for _, until in claim["protections"]
    )


def test_some_cases_enter_no_purchase() -> None:
    assert any(not case["purchases"] for case in _cases())


@pytest.mark.parametrize("count", [0, -1])
def test_a_harness_of_no_cases_is_refused(count: int) -> None:
    with pytest.raises(ValueError, match=rf"^the claim parity harness needs a case, got {count}$"):
        core_fixtures.claim_cases(1, count)
