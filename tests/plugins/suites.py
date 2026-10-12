"""Two suites under ``tests/``: the whole-repo guards, and unit (#285).

Shyden's rule (2026-10-08, every project): a test that reads or parses the whole tracked tree to
check a rule across the code is a guard, run in its own CI job with one limit at its step; every
other test is unit, bound by the unit rules. The guards live in ``tests/guards``.

``pytest`` runs unit; ``pytest --suite guards`` runs the guards. A run skips the other suite's
folders before importing them, and refuses by name any test it collected from the other suite
anyway: a file named on the command line is collected whatever ``pytest_ignore_collect`` says
(measured on 2026-10-12).
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import pytest

TESTS = Path(__file__).resolve().parents[1]
GUARDS = TESTS / "guards"
SUITES = ("unit", "guards")


class Located(Protocol):
    @property
    def path(self) -> Path: ...


def suite_of(path: Path) -> str:
    """The suite *path* belongs to: ``guards`` for ``tests/guards`` and everything in it."""
    return "guards" if path == GUARDS or GUARDS in path.parents else "unit"


def skips(chosen: str, path: Path) -> bool:
    """Whether a run of the *chosen* suite leaves *path* uncollected. The folders above
    ``tests/guards`` are walked by both, or a guards run would never reach it."""
    return suite_of(path) != chosen and path not in GUARDS.parents


def refuse_strays(chosen: str, items: Iterable[Located]) -> None:
    """Refuse, by name, every test in *items* from a suite other than *chosen*."""
    paths = {item.path.resolve() for item in items}
    strays = sorted(
        path.relative_to(TESTS.parent).as_posix() for path in paths if suite_of(path) != chosen
    )
    if strays:
        msg = f"a {chosen} run collected tests from another suite: {', '.join(strays)}"
        raise pytest.UsageError(msg)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--suite",
        choices=SUITES,
        default="unit",
        help="the suite to run: unit (the default) or guards, the whole-repo guards (#285)",
    )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    # None, never False: False would collect a path some other rule (norecursedirs) leaves out.
    return True if skips(config.getoption("suite"), collection_path.resolve()) else None


def pytest_itemcollected(item: pytest.Item) -> None:
    refuse_strays(item.config.getoption("suite"), [item])
