"""A perf test's time verdict is judged only in the run that means it (#374 AC9).

The verdict is judged with planted timings and a planted coverage state; the fixture the perf
tests call is taken from this very run, so an option that was never registered would be seen.
"""

import perf_budget
import pytest
from perf_budget import MEASURED, judge, verdict

JUDGED_TRACED = (
    "coverage traced this run, so its times include the tracer: judge them in a run without "
    "--cov, and measure coverage with --perf-measured"
)
MEASURED_UNTRACED = "--perf-measured judges no time, so it runs only under coverage"


def test_the_measured_run_is_asked_for_by_name() -> None:
    assert MEASURED == "--perf-measured"


def test_a_judged_timing_under_its_budget_passes() -> None:
    assert verdict(0.99, 1.0, measured=False, traced=False) is None


def test_a_judged_timing_at_its_budget_fails_it_must_be_under() -> None:
    assert verdict(1.0, 1.0, measured=False, traced=False) == "took 1.00 s, over the 1.0 s budget"


def test_a_judged_timing_over_its_budget_fails_with_its_figure() -> None:
    assert verdict(31.4, 30, measured=False, traced=False) == "took 31.40 s, over the 30 s budget"


def test_a_judged_run_coverage_traces_is_refused_even_inside_the_budget() -> None:
    assert verdict(0.0, 1.0, measured=False, traced=True) == JUDGED_TRACED


def test_a_measured_run_coverage_does_not_trace_is_refused() -> None:
    assert verdict(0.0, 1.0, measured=True, traced=False) == MEASURED_UNTRACED


def test_a_measured_run_under_coverage_judges_no_time() -> None:
    assert verdict(99.0, 1.0, measured=True, traced=True) is None


def test_judging_a_timing_over_budget_fails_the_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(perf_budget, "under_coverage", lambda: False)
    with pytest.raises(pytest.fail.Exception, match=r"^took 2\.00 s, over the 1 s budget$"):
        judge(2.0, 1, measured=False)


def test_judging_a_timing_inside_budget_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(perf_budget, "under_coverage", lambda: False)
    judge(0.5, 1, measured=False)


def test_judging_reads_whether_coverage_traces_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(perf_budget, "under_coverage", lambda: True)
    with pytest.raises(pytest.fail.Exception, match=r"^coverage traced this run"):
        judge(0.5, 1, measured=False)


def test_the_fixture_judges_by_this_runs_option(
    within_budget: perf_budget.Check, request: pytest.FixtureRequest
) -> None:
    assert request.config.getoption("perf_measured") is False
    assert (within_budget.func, within_budget.keywords) == (judge, {"measured": False})
