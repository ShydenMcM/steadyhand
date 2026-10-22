"""A perf test's time verdict, judged only in the run that means it (#374 AC9).

Shyden, 2026-10-22, global ("Two runs, one judges time"): CI runs the perf suite twice. The judged
run, without coverage, holds each timing to its budget ("Performance, a ten-year backtest in under
30 seconds"); the measured run, under coverage with ``--perf-measured``, feeds the coverage record
and judges no time, since the tracer would be timed with the code. Neither run can stand in for the
other: a judged run coverage traces is refused, and so is a measured run coverage does not trace,
so no step drops the verdict and still passes. The choice is made here, where every arm is unit
tested; each perf test calls ``within_budget`` once, a line with no branch of its own.
"""

from functools import partial

import pytest
from load_clock import under_coverage

MEASURED = "--perf-measured"
Check = partial[None]


def verdict(seconds: float, budget: float, *, measured: bool, traced: bool) -> str | None:
    """Why this timing fails its run, or None when it passes."""
    if measured and not traced:
        return f"{MEASURED} judges no time, so it runs only under coverage"
    if traced and not measured:
        return (
            "coverage traced this run, so its times include the tracer: judge them in a run "
            f"without --cov, and measure coverage with {MEASURED}"
        )
    if measured or seconds < budget:
        return None
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
            "the perf run coverage measures: it judges no time and runs only under coverage, "
            "while a perf run without it judges every budget and refuses coverage (#374)"
        ),
    )


@pytest.fixture
def within_budget(request: pytest.FixtureRequest) -> Check:
    """``within_budget(seconds, budget)``: a perf test's one time check, judged by this run."""
    return partial(judge, measured=bool(request.config.getoption("perf_measured")))
