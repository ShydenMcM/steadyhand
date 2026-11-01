"""The parity harness's cases (#228, spec §14.4): seeded inputs that Python's sizer and risk
manager answer, written for core's sizing and risk to answer identically
(``extension/packages/core/test/parity.test.ts``). The committed file is checked against a fresh
run in ``tests/integration/scripts/test_core_fixtures.py``."""

from decimal import Decimal

import core_fixtures
import pytest

# Every reason the risk manager can give an order on the advice day (``RiskManager.check`` and
# ``Tradable.why_not``): the cases are only a check of the port if each one comes up.
RISK_CODES = {
    "limit.cash.cut",
    "limit.cash.short",
    "limit.min_lots",
    "limit.weight.cut",
    "limit.weight.full",
    "trade.excluded",
    "trade.frozen",
    "trade.not_held",
    "trade.not_in_universe",
}


def _codes(document: core_fixtures.ParityCases) -> set[str]:
    found: set[str] = set()
    for case in document["cases"]:
        expected = case["expected"]
        found |= {entry["code"] for entry in expected["rejected"] + expected["cuts"]}
    return found


def test_the_same_seed_gives_the_same_cases() -> None:
    assert core_fixtures.parity_cases(7, 25) == core_fixtures.parity_cases(7, 25)


def test_another_seed_gives_other_cases() -> None:
    assert core_fixtures.parity_cases(7, 25)["cases"] != core_fixtures.parity_cases(8, 25)["cases"]


def test_the_seed_is_written_with_its_cases() -> None:
    assert core_fixtures.parity_cases(7, 3)["seed"] == "7"


def test_the_committed_seed_writes_every_case() -> None:
    document = core_fixtures.parity_cases()
    assert document["seed"] == str(core_fixtures.PARITY_SEED)
    assert len(document["cases"]) == core_fixtures.PARITY_CASES


def test_the_committed_cases_reach_every_reason_the_risk_manager_gives() -> None:
    assert _codes(core_fixtures.parity_cases()) == RISK_CODES


def test_the_committed_cases_have_orders_the_risk_manager_passes() -> None:
    cases = core_fixtures.parity_cases()["cases"]
    sides = {order["side"] for case in cases for order in case["expected"]["orders"]}
    assert sides == {"buy", "sell"}


def test_the_committed_cases_put_targets_on_a_whole_lot_edge() -> None:
    # A target within a rupiah of a whole number of lots, where rounding it down or up decides
    # the lots: the harness missed a sizer rounding up until these were drawn (2026-11-02).
    edges = 0
    for case in core_fixtures.parity_cases()["cases"]:
        value = int(case["value"])
        for symbol, weight in case["weights"].items():
            lot_value = int(case["prices"][symbol]) * 100
            exact = Decimal(weight) * value
            edges += exact != int(exact) and (int(exact) + 1) % lot_value == 0
    assert edges > 0


@pytest.mark.parametrize("count", [0, -1])
def test_a_harness_of_no_cases_is_refused(count: int) -> None:
    with pytest.raises(ValueError, match=rf"^the parity harness needs a case, got {count}$"):
        core_fixtures.parity_cases(7, count)
