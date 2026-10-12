"""Three suites under ``tests/``: unit, the whole-repo guards (#285) and integration (#286).

Shyden's rules (2026-10-08, every project): a test that reads or parses the whole tracked tree to
check a rule across the code is a guard, run in its own CI job with one limit at its step; a test
whose real case needs a process (real git, the installed console script, a second process racing
for a lock) is an integration test, also in its own job with one limit; every other test is unit,
bound by the unit rules. The guards live in ``tests/guards``, integration in ``tests/integration``.

``pytest`` runs unit; ``pytest --suite guards`` and ``pytest --suite integration`` run the others.
A run skips the other suites' folders before importing them, and refuses by name any test it
collected from another suite anyway: a file named on the command line is collected whatever
``pytest_ignore_collect`` says (measured on 2026-10-12).
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import pytest

TESTS = Path(__file__).resolve().parents[1]
GUARDS = TESTS / "guards"
INTEGRATION = TESTS / "integration"
SUITES = ("unit", "guards", "integration")
FOLDERS = {"guards": GUARDS, "integration": INTEGRATION}


class Located(Protocol):
    @property
    def path(self) -> Path: ...


def suite_of(path: Path) -> str:
    """The suite *path* belongs to: ``guards`` for ``tests/guards`` and everything in it,
    ``integration`` for ``tests/integration`` likewise, and ``unit`` for the rest."""
    for suite, folder in FOLDERS.items():
        if path == folder or folder in path.parents:
            return suite
    return "unit"


def skips(chosen: str, path: Path) -> bool:
    """Whether a run of the *chosen* suite leaves *path* uncollected. The folders above
    ``tests/guards`` and ``tests/integration`` are walked by every run, or no run but unit would
    ever reach them."""
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
        help=(
            "the suite to run: unit (the default), guards, the whole-repo guards (#285), or "
            "integration, the tests whose real case needs a process (#286)"
        ),
    )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    # None, never False: False would collect a path some other rule (norecursedirs) leaves out.
    return True if skips(config.getoption("suite"), collection_path.resolve()) else None


def pytest_itemcollected(item: pytest.Item) -> None:
    refuse_strays(item.config.getoption("suite"), [item])
