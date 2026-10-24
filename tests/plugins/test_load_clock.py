"""Loading a unit test file is limited too (#285).

The clock is judged with planted loads; the last tests check that this very run timed its own
files, so a clock that stopped timing would be seen.
"""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import load_clock
import pytest
from _pytest.assertion import rewrite
from load_clock import (
    LOAD_CPU_LIMIT_MICROSECONDS,
    LOADS,
    Load,
    judged,
    over_limit,
    report,
    under_coverage,
)
from population import searched

HERE = "tests/plugins/test_load_clock.py"


def test_the_limit_is_a_tenth_of_a_second() -> None:
    assert LOAD_CPU_LIMIT_MICROSECONDS == 100_000


@pytest.mark.parametrize(("cpu", "over"), [(0, False), (100_000, False), (100_001, True)])
def test_a_load_over_the_limit_is_named(cpu: int, *, over: bool) -> None:
    load = Load("tests/x/test_heavy.py", cpu_microseconds=cpu, wall_microseconds=cpu + 5)
    assert over_limit([load]) == ([load] if over else [])


def test_every_load_over_the_limit_is_named_not_only_the_first() -> None:
    heavy = [Load(f"tests/test_{n}.py", 200_000 + n, 300_000) for n in range(2)]
    light = Load("tests/test_light.py", 1_000, 2_000)
    assert over_limit([heavy[0], light, heavy[1]]) == heavy


def test_the_report_lists_every_file_heaviest_first() -> None:
    loads = [Load("tests/a.py", 2_000, 9_000), Load("tests/b.py", 75_000, 80_000)]
    assert report(loads) == [
        (
            "load CPU and wall per test file, compiling timed apart "
            "(limit 100000 us of CPU), 2 files:"
        ),
        "     75000 us CPU          0 us compiling      80000 us wall  tests/b.py",
        "      2000 us CPU          0 us compiling       9000 us wall  tests/a.py",
    ]


HEAVY = Load("tests/test_heavy.py", 100_001, 100_001)
YAHOO = "tests/idx/test_yahoo.py"


def test_a_unit_run_refuses_a_load_over_the_limit_by_name() -> None:
    assert judged("unit", [HEAVY]) == [
        (
            "LOAD LIMIT: tests/test_heavy.py took 100001 us of CPU to load, 0 us more compiling "
            "(timed apart, #405), over 100000: cut its import-time work or move it out of unit"
        )
    ]


TRACED = [Load(HEAVY.path, 100_001, 100_001, traced=True), Load(YAHOO, 1, 1, traced=True)]


def test_a_load_timed_under_coverage_is_not_judged_it_timed_the_tracer() -> None:
    assert judged("unit", TRACED) == []


def test_a_run_timed_under_coverage_fails_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(load_clock, "LOADS", TRACED)
    session = SimpleNamespace(
        config=SimpleNamespace(getoption=lambda name: {"suite": "unit"}[name]),
        exitstatus=pytest.ExitCode.OK,
    )
    load_clock.pytest_sessionfinish(session)  # type: ignore[arg-type]
    assert session.exitstatus == pytest.ExitCode.OK


def test_no_coverage_module_means_no_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "coverage", raising=False)
    assert under_coverage() is False


@pytest.mark.parametrize(("current", "covered"), [(None, False), (object(), True)])
def test_coverage_is_on_while_a_coverage_run_is_current(
    monkeypatch: pytest.MonkeyPatch, current: object, *, covered: bool
) -> None:
    fake = SimpleNamespace(Coverage=SimpleNamespace(current=lambda: current))
    monkeypatch.setitem(sys.modules, "coverage", fake)
    assert under_coverage() is covered


def test_a_guards_run_judges_no_load_its_step_limit_bounds_it() -> None:
    assert judged("guards", [HEAVY, Load(YAHOO, 1, 1)]) == []


def test_no_file_is_let_off_the_limit_any_more() -> None:
    """Shyden, 2026-10-12 (#285), "Burn-down list": it held only ``tests/idx/test_yahoo.py``, for
    its pandas import, until #292 moved the tests that build pandas frames to integration. Emptied,
    the list is gone, so that file over the limit is refused like any other."""
    assert not hasattr(load_clock, "LOAD_BURN_DOWN")
    assert judged("unit", [Load(YAHOO, 900_000, 3_000_000)]) == [
        (
            "LOAD LIMIT: tests/idx/test_yahoo.py took 900000 us of CPU to load, "
            "0 us more compiling (timed apart, #405), over 100000: "
            "cut its import-time work or move it out of unit"
        )
    ]


@pytest.mark.parametrize(
    "hook", ["pytest_make_collect_report", "pytest_terminal_summary", "pytest_sessionfinish"]
)
def test_this_run_calls_the_clocks_hooks(request: pytest.FixtureRequest, hook: str) -> None:
    caller = getattr(request.config.pluginmanager.hook, hook)
    assert getattr(load_clock, hook) in [impl.function for impl in caller.get_hookimpls()]


def test_this_run_timed_loading_this_file() -> None:
    mine = [load for load in LOADS if load.path == HERE]
    assert len(mine) == 1
    assert mine[0].cpu_microseconds > 0
    assert mine[0].wall_microseconds > 0
    assert mine[0].traced is under_coverage()
    assert 0 <= mine[0].compile_microseconds <= mine[0].cpu_microseconds


def test_each_timed_file_is_named_by_its_repo_path() -> None:
    root = Path(__file__).resolve().parents[2]
    unnamed = [load.path for load in LOADS if not (root / load.path).is_file()]
    assert searched(unnamed, of=len(LOADS), what="files this run loaded") == []


@pytest.mark.parametrize(
    ("chosen", "loads", "status"),
    [
        ("unit", [HEAVY], pytest.ExitCode.TESTS_FAILED),
        ("unit", [Load("tests/test_light.py", 1, 1)], pytest.ExitCode.OK),
        ("guards", [HEAVY], pytest.ExitCode.OK),
    ],
)
def test_a_judged_load_fails_a_passing_run(
    monkeypatch: pytest.MonkeyPatch, chosen: str, loads: list[Load], status: pytest.ExitCode
) -> None:
    monkeypatch.setattr(load_clock, "LOADS", loads)
    session = SimpleNamespace(
        config=SimpleNamespace(getoption=lambda name: {"suite": chosen}[name]),
        exitstatus=pytest.ExitCode.OK,
    )
    load_clock.pytest_sessionfinish(session)  # type: ignore[arg-type]
    assert session.exitstatus == status


def test_a_judged_load_keeps_a_failed_runs_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(load_clock, "LOADS", [HEAVY])
    session = SimpleNamespace(
        config=SimpleNamespace(getoption=lambda name: {"suite": "unit"}[name]),
        exitstatus=pytest.ExitCode.INTERRUPTED,
    )
    load_clock.pytest_sessionfinish(session)  # type: ignore[arg-type]
    assert session.exitstatus == pytest.ExitCode.INTERRUPTED


class _Reporter:
    """The terminal reporter as the summary hook writes to it: each line, and whether it is red."""

    def __init__(self) -> None:
        self.lines: list[tuple[str, bool]] = []

    def section(self, title: str) -> None:
        self.lines.append((f"== {title}", False))

    def write_line(self, line: str, *, red: bool = False) -> None:
        self.lines.append((line, red))


def _summary(monkeypatch: pytest.MonkeyPatch, loads: list[Load]) -> list[tuple[str, bool]]:
    """The summary hook called directly (#374): the real run calls it after coverage stopped."""
    monkeypatch.setattr(load_clock, "LOADS", loads)
    reporter = _Reporter()
    config = SimpleNamespace(getoption=lambda name: {"suite": "unit"}[name])
    load_clock.pytest_terminal_summary(reporter, config)  # type: ignore[arg-type]
    return reporter.lines


TRACED_NOTE = "coverage traced these loads, so none is judged: the limits step runs without it"


def test_the_summary_reports_every_load_then_names_each_refusal_in_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _summary(monkeypatch, [HEAVY]) == [
        ("== test file loads (#285)", False),
        *[(line, False) for line in report([HEAVY])],
        *[(refusal, True) for refusal in judged("unit", [HEAVY])],
    ]
    assert judged("unit", [HEAVY])


def test_the_summary_of_a_traced_run_says_so_and_refuses_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    traced = Load("tests/test_heavy.py", 100_001, 100_001, traced=True)
    assert _summary(monkeypatch, [traced]) == [
        ("== test file loads (#285)", False),
        *[(line, False) for line in report([traced])],
        (TRACED_NOTE, False),
    ]


def test_the_summary_of_an_untraced_run_inside_the_limit_carries_no_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    light = Load("tests/test_light.py", 5, 5)
    assert _summary(monkeypatch, [light]) == [
        ("== test file loads (#285)", False),
        *[(line, False) for line in report([light])],
    ]


# Compiling is timed apart (Shyden, 2026-10-24, #405: "Time it apart (Recommended)", then "Every
# project (Recommended)"): pytest's assertion rewrite took 52 ms of test_backtest.py's cold load
# and 0 of its warm one, so the judged figure leaves out the toolchain's one-off compile.


def test_compiling_is_left_out_of_the_judged_load() -> None:
    inside = Load("tests/test_c.py", 160_000, 170_000, compile_microseconds=60_000)
    over = Load("tests/test_d.py", 160_000, 170_000, compile_microseconds=59_999)
    assert over_limit([inside, over]) == [over]


def test_a_refusal_names_the_compiling_it_left_out() -> None:
    load = Load("tests/test_d.py", 160_000, 170_000, compile_microseconds=59_999)
    assert judged("unit", [load]) == [
        (
            "LOAD LIMIT: tests/test_d.py took 100001 us of CPU to load, 59999 us more compiling "
            "(timed apart, #405), over 100000: cut its import-time work or move it out of unit"
        )
    ]


def test_the_report_ranks_by_the_judged_load_and_shows_the_compiling() -> None:
    compiled = Load("tests/a.py", 90_000, 95_000, compile_microseconds=80_000)
    worked = Load("tests/b.py", 30_000, 31_000)
    assert report([compiled, worked]) == [
        (
            "load CPU and wall per test file, compiling timed apart "
            "(limit 100000 us of CPU), 2 files:"
        ),
        "     30000 us CPU          0 us compiling      31000 us wall  tests/b.py",
        "     10000 us CPU      80000 us compiling      95000 us wall  tests/a.py",
    ]


def _ticks(monkeypatch: pytest.MonkeyPatch, *ns: int) -> None:
    """The thread clock stood in: each read gives the next of *ns*; a read past them fails."""
    monkeypatch.setattr(load_clock, "thread_clock", iter(ns).__next__)


def _compiled() -> str:
    """A compile taking no time of its own: the clock stood in says how long it took."""
    return "compiled"


def test_time_inside_a_compile_is_added_to_the_compiling_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ticks(monkeypatch, 100, 350)
    before = load_clock.compiling_ns()
    assert load_clock.timed_apart(_compiled)() == "compiled"
    assert load_clock.compiling_ns() - before == 250


def test_a_compile_inside_a_compile_is_counted_once(monkeypatch: pytest.MonkeyPatch) -> None:
    # The outer compile's start, the inner one's start (an inner compile reads no end), the outer
    # one's end.
    _ticks(monkeypatch, 0, 10, 20)
    before = load_clock.compiling_ns()
    assert load_clock.timed_apart(load_clock.timed_apart(_compiled))() == "compiled"
    assert load_clock.compiling_ns() - before == 20


def test_a_failed_compile_is_counted_its_error_kept_and_the_next_one_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken() -> None:
        msg = "planted"
        raise SyntaxError(msg)

    _ticks(monkeypatch, 0, 400, 1_000, 1_100)
    before = load_clock.compiling_ns()
    with pytest.raises(SyntaxError, match="planted"):
        load_clock.timed_apart(broken)()
    assert load_clock.compiling_ns() - before == 400
    load_clock.timed_apart(_compiled)()
    assert load_clock.compiling_ns() - before == 500


def _compile(*_: object) -> None:
    """A compile hook to install over."""


@pytest.mark.parametrize(
    ("rewriter", "loader", "missing"),
    [
        (SimpleNamespace(), SimpleNamespace(source_to_code=_compile), "_rewrite_test"),
        (SimpleNamespace(_rewrite_test=_compile), SimpleNamespace(), "source_to_code"),
    ],
)
def test_the_clock_refuses_to_run_without_a_compile_it_times(
    rewriter: SimpleNamespace, loader: SimpleNamespace, missing: str
) -> None:
    with pytest.raises(RuntimeError, match=missing):
        load_clock.install(rewriter, loader)
    assert getattr(rewriter, "_rewrite_test", _compile) is _compile
    assert getattr(loader, "source_to_code", _compile) is _compile


def test_install_times_both_compiles(monkeypatch: pytest.MonkeyPatch) -> None:
    rewriter = SimpleNamespace(_rewrite_test=_compiled)
    loader = SimpleNamespace(source_to_code=_compiled)
    load_clock.install(rewriter, loader)
    _ticks(monkeypatch, 0, 5, 10, 17)
    before = load_clock.compiling_ns()
    assert rewriter._rewrite_test() == "compiled"
    assert load_clock.compiling_ns() - before == 5
    assert loader.source_to_code() == "compiled"
    assert load_clock.compiling_ns() - before == 12


def test_this_run_times_pytests_rewrite_of_a_test_file(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    source = tmp_path / "test_fresh.py"
    source.write_text("def test_one():\n    assert 1 == 1\n" * 20)
    before = load_clock.compiling_ns()
    _stat, code = rewrite._rewrite_test(source, request.config)
    assert code.co_filename == str(source)
    assert load_clock.compiling_ns() > before


def test_this_run_times_the_import_systems_compile_of_new_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "fresh_405.py").write_text("VALUE = 1\n")
    monkeypatch.syspath_prepend(tmp_path)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.delitem(sys.modules, "fresh_405", raising=False)
    before = load_clock.compiling_ns()
    assert importlib.import_module("fresh_405").VALUE == 1
    assert load_clock.compiling_ns() > before
    monkeypatch.delitem(sys.modules, "fresh_405")


def test_a_load_records_the_compiling_done_while_it_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hook driven by hand, with a compile planted inside its window: a warm run compiles
    nothing, so the run's own loads cannot show a clock that recorded no compiling."""
    monkeypatch.setattr(load_clock, "LOADS", [])
    # The hook's start, the compile's start and end, the hook's end.
    _ticks(monkeypatch, 0, 1_000_000, 3_000_000, 4_000_000)
    module = object.__new__(pytest.Module)
    module.path = Path(__file__)
    hook = load_clock.pytest_make_collect_report(module)
    next(hook)
    load_clock.timed_apart(_compiled)()
    collected = object()
    with pytest.raises(StopIteration) as finished:
        hook.send(collected)  # type: ignore[arg-type]
    assert finished.value.value is collected
    [load] = load_clock.LOADS
    assert load.path == HERE
    assert load.compile_microseconds == 2_000
    assert load.cpu_microseconds == 4_000
