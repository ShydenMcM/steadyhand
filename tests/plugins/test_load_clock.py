"""Loading a unit test file is limited too (#285).

The clock is judged with planted loads; the last tests check that this very run timed its own
files, so a clock that stopped timing would be seen.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import load_clock
import pytest
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
        "load CPU and wall per test file (limit 100000 us of CPU), 2 files:",
        "     75000 us CPU      80000 us wall  tests/b.py",
        "      2000 us CPU       9000 us wall  tests/a.py",
    ]


HEAVY = Load("tests/test_heavy.py", 100_001, 100_001)
YAHOO = "tests/idx/test_yahoo.py"


def test_a_unit_run_refuses_a_load_over_the_limit_by_name() -> None:
    assert judged("unit", [HEAVY]) == [
        (
            "LOAD LIMIT: tests/test_heavy.py took 100001 us of CPU to load, over 100000: "
            "cut its import-time work or move it out of unit"
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
            "LOAD LIMIT: tests/idx/test_yahoo.py took 900000 us of CPU to load, over 100000: "
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
