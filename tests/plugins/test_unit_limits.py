"""Each unit test is held to 1 s of wall time (#323, simplified by #446)."""

import sys
from types import SimpleNamespace

import pytest
import unit_limits
from unit_limits import WALL_LIMIT_SECONDS, held, under_coverage


def test_the_limit_is_one_second() -> None:
    assert WALL_LIMIT_SECONDS == 1


@pytest.mark.parametrize(
    ("markers", "expected"),
    [((), True), (("parametrize",), True), (("perf",), False), (("live",), False)],
    ids=["unmarked", "parametrized", "perf", "live"],
)
def test_perf_and_live_tests_are_other_suites_and_never_held(
    markers: tuple[str, ...], *, expected: bool
) -> None:
    assert held(frozenset(markers)) is expected


def test_no_coverage_module_means_no_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "coverage", raising=False)
    assert under_coverage() is False


def test_a_coverage_module_with_no_current_run_means_no_tracing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand_in = SimpleNamespace(Coverage=SimpleNamespace(current=lambda: None))
    monkeypatch.setitem(sys.modules, "coverage", stand_in)
    assert under_coverage() is False


def test_a_current_coverage_run_means_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    stand_in = SimpleNamespace(Coverage=SimpleNamespace(current=object))
    monkeypatch.setitem(sys.modules, "coverage", stand_in)
    assert under_coverage() is True


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
    monkeypatch.setattr(unit_limits, "under_coverage", lambda: False)
    unit, perf, live = _Item("slow"), _Item("perf"), _Item("live")
    unit_limits.pytest_collection_modifyitems([unit, perf, live])  # type: ignore[list-item]
    assert len(unit.added) == 1
    assert unit.added[0].name == "timeout"
    assert unit.added[0].args == (WALL_LIMIT_SECONDS,)
    assert (perf.added, live.added) == ([], [])


def test_a_traced_run_sets_no_wall_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(unit_limits, "under_coverage", lambda: True)
    unit = _Item()
    unit_limits.pytest_collection_modifyitems([unit])  # type: ignore[list-item]
    assert unit.added == []
