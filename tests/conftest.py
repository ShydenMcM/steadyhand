"""Settings shared by every test suite in the workspace, and the ``cli`` fixture."""

import gc
import os
from pathlib import Path

import file_reads
import pytest
from cli_world import Cli
from hypothesis import settings

# Installed before any test module is collected, so every repository file the run opens is
# recorded for the docs-only fast-path guard, which runs last (tests/meta/test_fast_path_reads.py).
file_reads.install()

# No deadline in any profile: a per-example deadline times the machine as well as the code, and
# a busy laptop turned it into a red the next run could not reproduce (#30).
settings.register_profile("dev", max_examples=100, deadline=None)
settings.register_profile("ci", max_examples=500, deadline=None, print_blob=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


def pytest_collection_finish() -> None:
    """Put everything collection built out of the garbage collector's reach (#302).

    Otherwise each full collection walks the whole collected suite, 35-442 ms on CI, charged to
    whichever test happens to be running. Collecting first means no garbage is frozen.
    """
    gc.collect()
    gc.freeze()


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Move the tests marked ``last`` to the end, keeping every other test's order (#218)."""
    items.sort(key=lambda item: item.get_closest_marker("last") is not None)


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    """``steadyhand-idx`` with an empty data directory of its own (M5 spec §9.1)."""
    return Cli(tmp_path / "home")
