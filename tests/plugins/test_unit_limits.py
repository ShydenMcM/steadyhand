"""Each unit test is held to 1 s of wall and 0.1 s of its own thread CPU (#323).

The check is judged with planted records; the last test checks that this very run timed the tests
before it, so a clock that stopped timing would be seen. The planted runs of real slow tests,
which start pytest in its own process, are in tests/integration/plugins.
"""

from types import SimpleNamespace

import pytest
import unit_limits
from unit_limits import (
    CPU_LIMIT_MICROSECONDS,
    SPENT,
    WALL_LIMIT_SECONDS,
    Spent,
    held,
    judged,
    report,
)

HERE = "tests/plugins/test_unit_limits.py"


def test_the_limits_are_one_second_and_a_tenth_of_a_second_of_cpu() -> None:
    assert (WALL_LIMIT_SECONDS, CPU_LIMIT_MICROSECONDS) == (1, 100_000)


@pytest.mark.parametrize(("cpu", "over"), [(0, False), (100_000, False), (100_001, True)])
def test_a_test_over_the_cpu_limit_is_named_with_its_figure(cpu: int, *, over: bool) -> None:
    spent = Spent(
        "tests/x/test_heavy.py::test_loop", cpu_microseconds=cpu, wall_microseconds=1, traced=False
    )
    expected = (
        [
            (
                "CPU LIMIT: tests/x/test_heavy.py::test_loop took 100001 us of its own CPU, over "
                "100000: cut its work or move its real case out of unit"
            )
        ]
        if over
        else []
    )
    assert judged([spent]) == expected


def test_every_test_over_the_limit_is_named_not_only_the_first() -> None:
    first = Spent("tests/test_x.py::test_0", 200_000, 300_000, traced=False)
    light = Spent("tests/test_x.py::test_light", 1_000, 2_000, traced=False)
    second = Spent("tests/test_x.py::test_1", 200_001, 300_000, traced=False)
    names = [line.split(" ")[2] for line in judged([first, light, second])]
    assert names == [first.nodeid, second.nodeid]


def test_a_test_coverage_traced_is_not_judged_and_one_it_did_not_trace_is() -> None:
    # Coverage's tracer would be timed with the code (the 1 s rule's terms). Whether it traced a
    # test is recorded while that test runs: pytest-cov stops coverage before the session ends,
    # so asking at the end said "not traced" and judged a traced run (#323, PR #327's CI).
    traced = Spent("tests/test_x.py::test_traced", 900_000, 900_000, traced=True)
    untraced = Spent("tests/test_x.py::test_untraced", 900_000, 900_000, traced=False)
    assert [line.split(" ")[2] for line in judged([traced, untraced])] == [untraced.nodeid]


class Item:
    """The two things the clock reads from a pytest item."""

    nodeid = "tests/test_x.py::test_planted"

    def iter_markers(self) -> list[pytest.Mark]:
        return []


@pytest.mark.parametrize("tracing", [True, False], ids=["under coverage", "without coverage"])
def test_each_record_says_whether_coverage_traced_its_test_while_it_ran(
    monkeypatch: pytest.MonkeyPatch, *, tracing: bool
) -> None:
    monkeypatch.setattr(unit_limits, "under_coverage", lambda: tracing)
    before = len(SPENT)
    protocol = unit_limits.pytest_runtest_protocol(Item(), None)  # type: ignore[arg-type]
    next(protocol)
    with pytest.raises(StopIteration):
        protocol.send(None)
    try:
        assert len(SPENT) == before + 1
        assert (SPENT[-1].nodeid, SPENT[-1].traced) == (Item.nodeid, tracing)
    finally:
        del SPENT[before:]


@pytest.mark.parametrize(
    ("markers", "expected"),
    [((), True), (("parametrize",), True), (("perf",), False), (("live",), False)],
    ids=["unmarked", "parametrized", "perf", "live"],
)
def test_perf_and_live_tests_are_other_suites_and_never_held(
    markers: tuple[str, ...], *, expected: bool
) -> None:
    assert held(frozenset(markers)) is expected


def test_the_report_lists_the_heaviest_ten_first_under_a_heading_naming_both_limits() -> None:
    spent = [
        Spent(f"tests/test_x.py::test_{n:02}", n * 1_000, n * 2_000, traced=False)
        for n in range(12)
    ]
    lines = report(spent)
    assert lines[0] == (
        "own CPU and wall per unit test (limits 100000 us of CPU, 1 s of wall), "
        "12 tests, the heaviest 10:"
    )
    assert [line.split()[-1] for line in lines[1:]] == [
        f"tests/test_x.py::test_{n:02}" for n in range(11, 1, -1)
    ]
    assert lines[1] == "     11000 us CPU      22000 us wall  tests/test_x.py::test_11"


def test_the_report_says_when_coverage_traced_the_run() -> None:
    lines = report([Spent("tests/test_x.py::test_a", 5, 6, traced=True)])
    assert lines[-1] == (
        "coverage traced this run, so no test is judged: the limits step runs without it"
    )


def test_the_report_of_an_untraced_run_carries_no_such_note() -> None:
    lines = report([Spent("tests/test_x.py::test_a", 5, 6, traced=False)])
    assert len(lines) == 2
    assert not lines[-1].startswith("coverage traced")


def test_this_run_timed_the_tests_before_this_one() -> None:
    # Liveness: the clock recorded this file's earlier tests, with CPU and wall of their own. This
    # file is unit, and tests/conftest.py registers the clock for every unit run.
    assert unit_limits.REGISTERED == [True]
    mine = [spent for spent in SPENT if spent.nodeid.startswith(f"{HERE}::")]
    assert len(mine) >= 10
    assert all(spent.wall_microseconds > 0 for spent in mine)  # runtime population: this run's


class _Item:
    """A collected test as the collection hook reads it: its markers, and those it is given."""

    def __init__(self, *names: str) -> None:
        self.names = names
        self.added: list[pytest.MarkDecorator] = []

    def iter_markers(self) -> list[SimpleNamespace]:
        """Each marker as the hook reads it, by name alone (``pytest.Mark`` is pytest's own)."""
        return [SimpleNamespace(name=name) for name in self.names]

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.added.append(marker)


def test_an_untraced_run_sets_the_wall_limit_on_every_unit_test_and_no_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Called directly (#374): the real run marks its tests only when coverage is not tracing."""
    monkeypatch.setattr(unit_limits, "under_coverage", lambda: False)
    unit, perf, live = _Item("slow"), _Item("perf"), _Item("live")
    unit_limits.pytest_collection_modifyitems([unit, perf, live])  # type: ignore[list-item]
    assert [(mark.name, mark.args) for mark in unit.added] == [("timeout", (WALL_LIMIT_SECONDS,))]
    assert (perf.added, live.added) == ([], [])


def test_a_traced_run_sets_no_wall_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(unit_limits, "under_coverage", lambda: True)
    unit = _Item()
    unit_limits.pytest_collection_modifyitems([unit])  # type: ignore[list-item]
    assert unit.added == []


OVER = Spent("tests/a.py::over", CPU_LIMIT_MICROSECONDS + 1, 1, traced=False)
UNDER = Spent("tests/a.py::under", CPU_LIMIT_MICROSECONDS, 1, traced=False)


@pytest.mark.parametrize(
    ("spent", "before", "after"),
    [
        ([OVER], pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED),
        ([OVER], pytest.ExitCode.INTERRUPTED, pytest.ExitCode.INTERRUPTED),
        ([UNDER], pytest.ExitCode.OK, pytest.ExitCode.OK),
    ],
)
def test_a_test_over_its_limit_fails_a_passing_run_and_keeps_a_failed_runs_status(
    monkeypatch: pytest.MonkeyPatch,
    spent: list[Spent],
    before: pytest.ExitCode,
    after: pytest.ExitCode,
) -> None:
    """Called directly (#374): the real run calls it after coverage stopped."""
    monkeypatch.setattr(unit_limits, "SPENT", spent)
    session = SimpleNamespace(exitstatus=before)
    unit_limits.pytest_sessionfinish(session)  # type: ignore[arg-type]
    assert session.exitstatus == after


class _Reporter:
    def __init__(self) -> None:
        self.lines: list[tuple[str, bool]] = []

    def section(self, title: str) -> None:
        self.lines.append((f"== {title}", False))

    def write_line(self, line: str, *, red: bool = False) -> None:
        self.lines.append((line, red))


@pytest.mark.parametrize("spent", [[OVER], [UNDER]])
def test_the_summary_reports_the_heaviest_then_names_each_refusal_in_red(
    monkeypatch: pytest.MonkeyPatch, spent: list[Spent]
) -> None:
    monkeypatch.setattr(unit_limits, "SPENT", spent)
    reporter = _Reporter()
    unit_limits.pytest_terminal_summary(reporter)  # type: ignore[arg-type]
    assert reporter.lines == [
        ("== unit test limits (#323)", False),
        *[(line, False) for line in report(spent)],
        *[(refusal, True) for refusal in judged(spent)],
    ]
    assert bool(judged(spent)) is (spent == [OVER])
