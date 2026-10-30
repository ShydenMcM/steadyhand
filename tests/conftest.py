"""Settings shared by every test suite in the workspace, and the ``cli`` fixture."""

from pathlib import Path

import file_reads
import hypothesis_profile
import no_process
import pytest
import suites
import unit_limits
from cli_world import Cli
from stood_in_git import FakeGit, stand_in
from suites import pytest_ignore_collect, pytest_itemcollected

__all__ = [
    "pytest_ignore_collect",
    "pytest_itemcollected",
]


def pytest_addoption(parser: pytest.Parser) -> None:
    """The suite to run (#285)."""
    suites.pytest_addoption(parser)


def pytest_configure(config: pytest.Config) -> None:
    """In a guards run, record every repository file it opens, before any test module is
    collected, for the docs-only read guard that runs last (tests/guards/test_fast_path_reads.py).

    A unit run records nothing: CI's lock makes those files unreadable before every job, which
    covers it from outside the process (Shyden, 2026-10-12, #285). A unit run instead refuses every
    process and outside connection, from before the first test module is imported (#286), and holds
    each test to 1 s of wall when coverage is not tracing it (#323). A
    properties run loads the one Hypothesis profile, which draws every property's full count (#290).
    """
    suite = config.getoption("suite")
    if suite == "guards":
        file_reads.install()
    if suite == "unit":
        no_process.install()
        config.pluginmanager.register(no_process, "no-process")
        config.pluginmanager.register(unit_limits, "unit-limits")
    if suite == "properties":
        hypothesis_profile.load()


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Move the tests marked ``last`` to the end, keeping every other test's order (#218)."""
    items.sort(key=lambda item: item.get_closest_marker("last") is not None)


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    """``steadyhand-idx`` with an empty data directory of its own (M5 spec §9.1)."""
    return Cli(tmp_path / "home")


@pytest.fixture
def fake_git(monkeypatch: pytest.MonkeyPatch) -> FakeGit:
    """Git stood in for the CI scripts' unit tests, which start no process (#286)."""
    return stand_in(monkeypatch)
