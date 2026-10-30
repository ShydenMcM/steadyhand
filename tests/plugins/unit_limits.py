"""Each unit test is held to 1 s of wall time, pytest-timeout's limit (#323, simplified by #446).

The global rule (Shyden, every project): a unit test runs in under 1 s, the runner's timeout, and
no limit is ever raised. This is the one place that sets it, on a unit run only, and only when
coverage is not tracing it, since its tracer would be timed with the code. A test marked ``perf``
or ``live`` is another suite, with one limit at its own CI step.
"""

import sys

import pytest

# The most wall-clock time one unit test may take, in seconds: pytest-timeout's limit.
WALL_LIMIT_SECONDS = 1
OTHER_SUITES = frozenset({"perf", "live"})


def held(markers: frozenset[str]) -> bool:
    """Whether a test with *markers* is a unit test: ``perf`` and ``live`` are other suites."""
    return not markers & OTHER_SUITES


def under_coverage() -> bool:
    """Whether coverage is measuring this run: its tracer would be timed with the code."""
    module = sys.modules.get("coverage")
    return module is not None and module.Coverage.current() is not None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Set the wall limit on every held test of a run coverage is not tracing."""
    if under_coverage():
        return
    for item in items:
        if held(frozenset(mark.name for mark in item.iter_markers())):
            item.add_marker(pytest.mark.timeout(WALL_LIMIT_SECONDS))
