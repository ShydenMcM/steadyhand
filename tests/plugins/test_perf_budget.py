"""A perf or live test's time is judged only in the run that means it (#374 AC9).

The verdict is judged with planted timings and a planted coverage state; the fixture the perf
tests call and the setup hook are taken from this very run, so an option that was never
registered, or a hook never called, would be seen.
"""

from dataclasses import dataclass, field

import perf_budget
import pytest
from perf_budget import MEASURED, judge, pytest_runtest_setup, verdict

JUDGED_TRACED = (
    "coverage traced this run, so its times include the tracer: judge them in a run without "
    "--cov, and measure coverage with --measured"
)
MEASURED_UNTRACED = "--measured judges no time, so it runs only under coverage"


@dataclass(frozen=True)
class _Config:
    measured: bool

    def getoption(self, name: str) -> bool:
        assert name == "measured"
        return self.measured


@dataclass(frozen=True)
class _Item:
    """A collected test as the setup hook reads it: its markers and its run's option."""

    config: _Config
    markers: tuple[str, ...] = field(default=())

    def get_closest_marker(self, name: str) -> str | None:
        return name if name in self.markers else None


def _set_up(
    monkeypatch: pytest.MonkeyPatch, markers: tuple[str, ...], *, measured: bool, traced: bool
) -> None:
    monkeypatch.setattr(perf_budget, "under_coverage", lambda: traced)
    pytest_runtest_setup(_Item(_Config(measured), markers))  # type: ignore[arg-type]


def test_the_measured_run_is_asked_for_by_name() -> None:
    assert MEASURED == "--measured"


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
    assert request.config.getoption("measured") is False
    assert (within_budget.func, within_budget.keywords) == (judge, {"measured": False})


@pytest.mark.parametrize("marker", ["live", "perf"])
def test_a_judged_run_coverage_traces_is_refused_before_the_test_runs(
    monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    """The live check has no time call of its own: its step's limit is its verdict (G1, G3)."""
    with pytest.raises(pytest.fail.Exception, match=f"^{JUDGED_TRACED}$"):
        _set_up(monkeypatch, (marker,), measured=False, traced=True)


@pytest.mark.parametrize("marker", ["live", "perf"])
def test_a_measured_run_coverage_does_not_trace_is_refused_before_the_test_runs(
    monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    with pytest.raises(pytest.fail.Exception, match=f"^{MEASURED_UNTRACED}$"):
        _set_up(monkeypatch, (marker,), measured=True, traced=False)


@pytest.mark.parametrize("marker", ["live", "perf"])
@pytest.mark.parametrize("measured", [False, True])
def test_a_run_of_the_kind_it_says_sets_the_test_up(
    monkeypatch: pytest.MonkeyPatch, marker: str, *, measured: bool
) -> None:
    _set_up(monkeypatch, (marker,), measured=measured, traced=measured)


@pytest.mark.parametrize(("measured", "traced"), [(False, True), (True, False)])
def test_a_test_marked_neither_live_nor_perf_is_never_refused(
    monkeypatch: pytest.MonkeyPatch, *, measured: bool, traced: bool
) -> None:
    """A unit test runs under coverage without --measured, and must stay untouched (G4)."""
    _set_up(monkeypatch, ("slow",), measured=measured, traced=traced)


def test_this_run_calls_the_setup_hook(request: pytest.FixtureRequest) -> None:
    caller = request.config.pluginmanager.hook.pytest_runtest_setup
    assert perf_budget.pytest_runtest_setup in [impl.function for impl in caller.get_hookimpls()]
