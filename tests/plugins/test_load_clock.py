"""Loading a unit test file is limited too (#285).

The clock is judged with planted loads; the last tests check that this very run timed its own
files, so a clock that stopped timing would be seen.
"""

from pathlib import Path
from types import SimpleNamespace

import load_clock
import pytest
from load_clock import (
    LOAD_BURN_DOWN,
    LOAD_CPU_LIMIT_MICROSECONDS,
    LOADS,
    Load,
    judged,
    over_limit,
    report,
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
LISTED = "tests/idx/test_yahoo.py"


def test_a_unit_run_refuses_a_load_over_the_limit_by_name() -> None:
    assert judged("unit", [HEAVY]) == [
        (
            "LOAD LIMIT: tests/test_heavy.py took 100001 us of CPU to load, over 100000: "
            "cut its import-time work or move it out of unit"
        )
    ]


def test_a_guards_run_judges_no_load_its_step_limit_bounds_it() -> None:
    assert judged("guards", [HEAVY, Load(LISTED, 1, 1)]) == []


def test_the_burn_down_list_holds_only_test_yahoo_and_why() -> None:
    """Shyden, 2026-10-12 (#285), "Burn-down list": #292 moves its pandas tests out and empties
    it. The list only shrinks: an entry is never added."""
    assert list(LOAD_BURN_DOWN) == [LISTED]
    assert "pandas" in LOAD_BURN_DOWN[LISTED]
    assert "#292" in LOAD_BURN_DOWN[LISTED]


def test_a_listed_file_over_the_limit_is_reported_not_refused() -> None:
    assert judged("unit", [Load(LISTED, 900_000, 3_000_000)]) == []


@pytest.mark.parametrize("cpu", [0, 100_000])
def test_a_listed_file_within_the_limit_must_come_off_the_list(cpu: int) -> None:
    assert judged("unit", [Load(LISTED, cpu, cpu)]) == [
        (
            f"LOAD BURN-DOWN: {LISTED} now loads within the limit ({cpu} us of CPU): take it off "
            "LOAD_BURN_DOWN in tests/plugins/load_clock.py"
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
