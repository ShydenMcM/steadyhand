"""The income parity harness's cases (#237 AC4, spec §9): seeded holdings whose run rate, goal
share and payment calendar Python's ``run_rate``, ``_share`` and ``payment_calendar`` give, for
core's ``runRate``, ``goalProgress`` and ``paymentCalendar`` to give identically
(``extension/packages/core/test/parity-income.test.ts``). The committed file is checked against
a fresh run in ``tests/integration/scripts/test_core_fixtures.py``."""

from typing import Any

import core_fixtures
import pytest


def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = core_fixtures.income_cases()["cases"]
    return cases


def test_the_same_seed_gives_the_same_cases() -> None:
    assert core_fixtures.income_cases(7, 5) == core_fixtures.income_cases(7, 5)


def test_another_seed_gives_other_cases() -> None:
    assert core_fixtures.income_cases(7, 5)["cases"] != core_fixtures.income_cases(8, 5)["cases"]


def test_the_committed_cases_hold_nothing_pay_nothing_and_pay() -> None:
    cases = _cases()
    assert any(not case["stocks"] for case in cases)
    assert any(case["stocks"] and case["annualGross"] == "0" for case in cases)
    assert any(case["annualGross"] != "0" for case in cases)


def test_some_holdings_split_and_some_dividends_fall_outside_the_window() -> None:
    stocks = [stock for case in _cases() for stock in case["stocks"]]
    assert any(stock["splits"] for stock in stocks)
    windows = [
        (case["asOf"], dividend["exDate"])
        for case in _cases()
        for stock in case["stocks"]
        for dividend in stock["dividends"]
    ]
    assert any(ex_date > as_of for as_of, ex_date in windows)


def test_the_goal_share_runs_past_1_somewhere() -> None:
    assert any(float(case["share"]) > 1 for case in _cases())


@pytest.mark.parametrize("count", [0, -1])
def test_a_harness_of_no_cases_is_refused(count: int) -> None:
    with pytest.raises(ValueError, match=rf"^the income parity harness needs a case, got {count}$"):
        core_fixtures.income_cases(1, count)
