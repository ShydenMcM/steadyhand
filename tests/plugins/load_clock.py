"""Loading a unit test file is limited too (#285).

Shyden's rule (2026-10-11, every project): each test's own clocks start once it runs, so the
work a file does as it is imported and collected counted against no limit (measured
2026-10-12: ``tests/idx/test_yahoo.py`` took 0.50 s of CPU to load). This plugin times every test
module's import and collection, on the thread's own CPU clock and the wall clock; prints every
file, heaviest first; and fails a unit run with any file over the limit, naming it. A guards
run reports but is not judged: its step's one limit bounds it.
"""

import sys
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest

# The most CPU one unit file may take to load, in microseconds. An integer, so the edit hook
# that refuses a raised limit (~/.claude/hooks/unit-limit-never-raised.py, CPU_LIMITS) reads it.
LOAD_CPU_LIMIT_MICROSECONDS = 100_000

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Load:
    """One test file's import and collection, named by its repo path."""

    path: str
    cpu_microseconds: int
    wall_microseconds: int
    # Timed while coverage traced the run: its tracer was timed with the file, so it is not judged.
    traced: bool = False


LOADS: list[Load] = []


def over_limit(loads: list[Load]) -> list[Load]:
    """Every load in *loads* over the limit, in their order."""
    return [load for load in loads if load.cpu_microseconds > LOAD_CPU_LIMIT_MICROSECONDS]


def judged(chosen: str, loads: list[Load]) -> list[str]:
    """Why a run of the *chosen* suite fails on *loads*, one line per file over the limit. Only a
    unit run's untraced loads are judged: a guards run's step limit bounds it, and a load timed
    under coverage timed its tracer too (the 1 s rule's terms). No file is let off: the one listed
    file went under the limit when #292 moved its pandas tests to integration.
    """
    if chosen != "unit":
        return []
    return [
        f"LOAD LIMIT: {load.path} took {load.cpu_microseconds} us of CPU to load, over "
        f"{LOAD_CPU_LIMIT_MICROSECONDS}: cut its import-time work or move it out of unit"
        for load in over_limit(loads)
        if not load.traced
    ]


def report(loads: list[Load]) -> list[str]:
    """One line per file, heaviest CPU first, under a heading naming the limit."""
    heading = (
        f"load CPU and wall per test file (limit {LOAD_CPU_LIMIT_MICROSECONDS} us of CPU), "
        f"{len(loads)} files:"
    )
    ranked = sorted(loads, key=lambda load: (-load.cpu_microseconds, load.path))
    lines = [
        f"{load.cpu_microseconds:>10} us CPU {load.wall_microseconds:>10} us wall  {load.path}"
        for load in ranked
    ]
    return [heading, *lines]


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    if not isinstance(collector, pytest.Module):
        return (yield)
    cpu, wall = time.thread_time_ns(), time.perf_counter_ns()
    try:
        return (yield)
    finally:
        LOADS.append(
            Load(
                collector.path.resolve().relative_to(ROOT).as_posix(),
                (time.thread_time_ns() - cpu) // 1000,
                (time.perf_counter_ns() - wall) // 1000,
                traced=under_coverage(),
            )
        )


def under_coverage() -> bool:
    """Whether coverage is measuring this run: its tracer, not the file, would be timed."""
    module = sys.modules.get("coverage")
    return module is not None and module.Coverage.current() is not None


def pytest_sessionfinish(session: pytest.Session) -> None:
    refusals = judged(session.config.getoption("suite"), LOADS)
    if refusals and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    terminalreporter.section("test file loads (#285)")
    for line in report(LOADS):
        terminalreporter.write_line(line)
    if any(load.traced for load in LOADS):
        terminalreporter.write_line(
            "coverage traced these loads, so none is judged: the limits step runs without it"
        )
    for refusal in judged(config.getoption("suite"), LOADS):
        terminalreporter.write_line(refusal, red=True)
