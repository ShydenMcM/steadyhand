"""Loading a unit test file is limited too (#285).

Shyden's rule (2026-10-11, every project): each test's own clocks start once it runs, so the
work a file does as it is imported and collected counted against no limit (measured
2026-10-12: ``tests/idx/test_yahoo.py`` took 0.50 s of CPU to load). This plugin times every test
module's import and collection, on the thread's own CPU clock and the wall clock; prints every
file, heaviest first; and fails a unit run with any file over the limit, naming it. A guards
run reports but is not judged: its step's one limit bounds it.

Compiling is timed apart (Shyden, 2026-10-24, #405, every project): pytest's assertion rewrite of a
test file and the import system's compile of source with no bytecode run only when a cache is
cold (every CI checkout, a fresh worktree, the first run on each Python, after an edit), and took
52 ms of ``tests/engine/test_backtest.py``'s cold load against 6 ms warm. Both are timed on the
same clock, printed beside each load and left out of the figure judged.
"""

import importlib._bootstrap_external
import sys
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

import _pytest.assertion.rewrite
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
    # Of cpu_microseconds, the part spent compiling source, which is not judged (#405).
    compile_microseconds: int = 0

    @property
    def judged_microseconds(self) -> int:
        """The CPU the limit judges: the load without its compiling."""
        return self.cpu_microseconds - self.compile_microseconds


LOADS: list[Load] = []

# This thread's CPU spent inside a timed compile so far, in nanoseconds, and how deep the calls
# into timed compiles now nest, so a compile that calls another is counted once.
_COMPILING = {"ns": 0, "depth": 0}


def compiling_ns() -> int:
    """This thread's CPU spent compiling source so far, in nanoseconds."""
    return _COMPILING["ns"]


def timed_apart[**P, R](compile_function: Callable[P, R]) -> Callable[P, R]:
    """*compile_function*, its thread CPU added to the compiling total, failed calls included."""

    @wraps(compile_function)
    def timed(*args: P.args, **kwargs: P.kwargs) -> R:
        outermost = _COMPILING["depth"] == 0
        _COMPILING["depth"] += 1
        start = time.thread_time_ns()
        try:
            return compile_function(*args, **kwargs)
        finally:
            _COMPILING["depth"] -= 1
            if outermost:
                _COMPILING["ns"] += time.thread_time_ns() - start

    return timed


def install(rewriter: object, loader: object) -> None:
    """Time *rewriter*'s ``_rewrite_test`` and *loader*'s ``source_to_code``. Either missing (a
    pytest or Python that renamed it) refuses the run before anything is patched: a clock that
    silently stopped finding its compiles would judge them again."""
    hooks = ((rewriter, "_rewrite_test"), (loader, "source_to_code"))
    missing = [name for owner, name in hooks if not callable(getattr(owner, name, None))]
    if missing:
        msg = f"load clock (#405): cannot time compiling, no {' or '.join(missing)} to wrap"
        raise RuntimeError(msg)
    for owner, name in hooks:
        setattr(owner, name, timed_apart(getattr(owner, name)))


# SourceFileLoader inherits source_to_code from SourceLoader, the class that defines it.
install(_pytest.assertion.rewrite, importlib._bootstrap_external.SourceLoader)


def over_limit(loads: list[Load]) -> list[Load]:
    """Every load in *loads* over the limit, in their order."""
    return [load for load in loads if load.judged_microseconds > LOAD_CPU_LIMIT_MICROSECONDS]


def judged(chosen: str, loads: list[Load]) -> list[str]:
    """Why a run of the *chosen* suite fails on *loads*, one line per file over the limit. Only a
    unit run's untraced loads are judged: a guards run's step limit bounds it, and a load timed
    under coverage timed its tracer too (the 1 s rule's terms). No file is let off: the one listed
    file went under the limit when #292 moved its pandas tests to integration.
    """
    if chosen != "unit":
        return []
    return [
        f"LOAD LIMIT: {load.path} took {load.judged_microseconds} us of CPU to load, "
        f"{load.compile_microseconds} us more compiling (timed apart, #405), over "
        f"{LOAD_CPU_LIMIT_MICROSECONDS}: cut its import-time work or move it out of unit"
        for load in over_limit(loads)
        if not load.traced
    ]


def report(loads: list[Load]) -> list[str]:
    """One line per file, heaviest judged CPU first, its compiling beside it, under a heading
    naming the limit."""
    heading = (
        "load CPU and wall per test file, compiling timed apart "
        f"(limit {LOAD_CPU_LIMIT_MICROSECONDS} us of CPU), {len(loads)} files:"
    )
    ranked = sorted(loads, key=lambda load: (-load.judged_microseconds, load.path))
    lines = [
        f"{load.judged_microseconds:>10} us CPU {load.compile_microseconds:>10} us compiling "
        f"{load.wall_microseconds:>10} us wall  {load.path}"
        for load in ranked
    ]
    return [heading, *lines]


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    if not isinstance(collector, pytest.Module):
        return (yield)
    cpu, wall, compiling = time.thread_time_ns(), time.perf_counter_ns(), compiling_ns()
    try:
        return (yield)
    finally:
        LOADS.append(
            Load(
                collector.path.resolve().relative_to(ROOT).as_posix(),
                (time.thread_time_ns() - cpu) // 1000,
                (time.perf_counter_ns() - wall) // 1000,
                traced=under_coverage(),
                compile_microseconds=(compiling_ns() - compiling) // 1000,
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
