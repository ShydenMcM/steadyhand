"""A perf or live test's time, judged only in the run that means it (#374 AC9).

Shyden, 2026-10-22, global ("Two runs, one judges time"): CI runs the perf suite twice. The judged
run, without coverage, holds each timing to its budget ("Performance, a ten-year backtest in under
30 seconds"); the measured run, under coverage with ``--measured``, feeds the coverage record
and judges no time, since the tracer would be timed with the code. Neither run can stand in for the
other: a judged run coverage traces is refused, and so is a measured run coverage does not trace,
so no step drops the verdict and still passes. The choice is made here, where every arm is unit
tested; each perf test calls ``within_budget`` once, a line with no branch of its own. The live
Yahoo check runs twice the same way in yahoo-shape: its verdict is its step's limit, with no time
call of its own, so every test marked live or perf is refused at setup in a run of the wrong kind.
"""

from functools import partial

import pytest
from load_clock import under_coverage

MEASURED = "--measured"
# The markers of the tests whose time is judged: by a budget (perf) or by their step's limit (live).
TIMED = ("live", "perf")
Check = partial[None]


def wrong_run(*, measured: bool, traced: bool) -> str | None:
    """Why this run is not the kind it says it is, or None when it is."""
    if measured and not traced:
        return f"{MEASURED} judges no time, so it runs only under coverage"
    if traced and not measured:
        return (
            "coverage traced this run, so its times include the tracer: judge them in a run "
            f"without --cov, and measure coverage with {MEASURED}"
        )
    return None


def verdict(seconds: float, budget: float, *, measured: bool, traced: bool) -> str | None:
    """Why this timing fails its run, or None when it passes."""
    wrong = wrong_run(measured=measured, traced=traced)
    if wrong is not None or measured or seconds < budget:
        return wrong
    return f"took {seconds:.2f} s, over the {budget} s budget"


def judge(seconds: float, budget: float, *, measured: bool) -> None:
    """Fail the calling test when its timing fails this run."""
    failure = verdict(seconds, budget, measured=measured, traced=under_coverage())
    if failure is not None:
        pytest.fail(failure, pytrace=False)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        MEASURED,
        action="store_true",
        help=(
            "the perf or live run coverage measures: it judges no time and runs only under "
            "coverage, while a run without it judges every time and refuses coverage (#374)"
        ),
    )


@pytest.fixture
def within_budget(request: pytest.FixtureRequest) -> Check:
    """``within_budget(seconds, budget)``: a perf test's one time check, judged by this run."""
    return partial(judge, measured=bool(request.config.getoption("measured")))


def pytest_runtest_setup(item: pytest.Item) -> None:
    """A live or perf test in a run of the wrong kind fails before it runs."""
    if any(item.get_closest_marker(name) for name in TIMED):
        failure = wrong_run(
            measured=bool(item.config.getoption("measured")), traced=under_coverage()
        )
        if failure is not None:
            pytest.fail(failure, pytrace=False)
