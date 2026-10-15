"""Each unit test is held to 1 s of wall and 0.1 s of its own thread CPU (#323).

The global rule (Shyden, 2026-10-07 to 2026-10-12, every project): a unit test runs in under 1 s
and at or under 0.1 s of its own thread CPU, and no limit is ever raised. This is the one place
that applies both, to a unit run only, and only when coverage is not tracing it: its tracer would
be timed with the code, so CI judges in its own step without coverage ("Unit limits, judged
without coverage"). A guards, integration or properties run is not a unit run, and a test marked
``perf`` or ``live`` is another suite: each of those has one limit at its own CI step.

The wall limit is pytest-timeout's, set on each held test here. The CPU clock times each test's
whole protocol (setup, call and teardown) on the thread's own clock, as #282 measured it, prints
the heaviest, and fails the run naming every test over the limit, as the load clock does (#285).
Whether coverage traced a test is recorded while that test runs: pytest-cov stops coverage before
the session ends, so a run asked at its end said "not traced" and judged a traced one (PR #327).
"""

import time
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from load_clock import under_coverage

# The most own CPU one unit test may take, in microseconds. An integer, so the edit hook that
# refuses a raised limit (~/.claude/hooks/unit-limit-never-raised.py, CPU_LIMITS) reads it.
CPU_LIMIT_MICROSECONDS = 100_000
# The most wall-clock time one unit test may take, in seconds: pytest-timeout's limit.
WALL_LIMIT_SECONDS = 1
HEAVIEST_SHOWN = 10
OTHER_SUITES = frozenset({"perf", "live"})


@dataclass(frozen=True)
class Spent:
    """One test's whole protocol, named by its node id, and whether coverage traced it."""

    nodeid: str
    cpu_microseconds: int
    wall_microseconds: int
    traced: bool


SPENT: list[Spent] = []
REGISTERED: list[bool] = []


def held(markers: frozenset[str]) -> bool:
    """Whether a test with *markers* is a unit test: ``perf`` and ``live`` are other suites."""
    return not markers & OTHER_SUITES


def judged(spent: list[Spent]) -> list[str]:
    """Why the run fails, one line per test over the CPU limit; a test coverage traced is not
    judged, its tracer timed with the code."""
    return [
        f"CPU LIMIT: {one.nodeid} took {one.cpu_microseconds} us of its own CPU, over "
        f"{CPU_LIMIT_MICROSECONDS}: cut its work or move its real case out of unit"
        for one in spent
        if not one.traced and one.cpu_microseconds > CPU_LIMIT_MICROSECONDS
    ]


def report(spent: list[Spent]) -> list[str]:
    """The heaviest tests first, under a heading naming both limits."""
    heading = (
        f"own CPU and wall per unit test (limits {CPU_LIMIT_MICROSECONDS} us of CPU, "
        f"{WALL_LIMIT_SECONDS} s of wall), {len(spent)} tests, the heaviest {HEAVIEST_SHOWN}:"
    )
    ranked = sorted(spent, key=lambda one: (-one.cpu_microseconds, one.nodeid))
    lines = [
        f"{one.cpu_microseconds:>10} us CPU {one.wall_microseconds:>10} us wall  {one.nodeid}"
        for one in ranked[:HEAVIEST_SHOWN]
    ]
    note = (
        ["coverage traced this run, so no test is judged: the limits step runs without it"]
        if any(one.traced for one in spent)
        else []
    )
    return [heading, *lines, *note]


def _markers(item: pytest.Item) -> frozenset[str]:
    return frozenset(mark.name for mark in item.iter_markers())


def pytest_configure(config: pytest.Config) -> None:
    del config
    REGISTERED.append(True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Set the wall limit on every held test of a run coverage is not tracing."""
    if under_coverage():
        return
    for item in items:
        if held(_markers(item)):
            item.add_marker(pytest.mark.timeout(WALL_LIMIT_SECONDS))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None) -> Generator[None]:
    del nextitem
    cpu, wall = time.thread_time_ns(), time.perf_counter_ns()
    try:
        return (yield)
    finally:
        if held(_markers(item)):
            SPENT.append(
                Spent(
                    item.nodeid,
                    (time.thread_time_ns() - cpu) // 1000,
                    (time.perf_counter_ns() - wall) // 1000,
                    under_coverage(),
                )
            )


def pytest_sessionfinish(session: pytest.Session) -> None:
    if judged(SPENT) and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    terminalreporter.section("unit test limits (#323)")
    for line in report(SPENT):
        terminalreporter.write_line(line)
    for refusal in judged(SPENT):
        terminalreporter.write_line(refusal, red=True)
