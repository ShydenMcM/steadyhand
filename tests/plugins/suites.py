"""Four suites under ``tests/``: unit, the whole-repo guards (#285), integration (#286) and the
properties (#290).

Shyden's rules (2026-10-08, every project): a test that reads or parses the whole tracked tree to
check a rule across the code is a guard, run in its own CI job with one limit at its step; a test
whose real case needs a process (real git, the installed console script, a second process racing
for a lock) is an integration test, also in its own job with one limit; so is a long real run
over the recorded golden window, too heavy for the unit limits, with a short stand-in of it in
unit (#292, under the rule that a cut never drops a real run). Shyden's ruling on #290
(2026-10-12): every Hypothesis property runs at its full count in a properties suite, with a fast
stand-in of it in unit. Every other test is unit, bound by the unit rules. The guards live in
``tests/guards``, integration in ``tests/integration``, the properties in ``tests/properties``.

``pytest`` runs unit; ``pytest --suite guards``, ``--suite integration`` and ``--suite properties``
run the others.
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
PROPERTIES = TESTS / "properties"
SUITES = ("unit", "guards", "integration", "properties")
FOLDERS = {"guards": GUARDS, "integration": INTEGRATION, "properties": PROPERTIES}


class Located(Protocol):
    @property
    def path(self) -> Path: ...


class Collected(Protocol):
    @property
    def nodeid(self) -> str: ...


def suite_of(path: Path) -> str:
    """The suite *path* belongs to: ``guards`` for ``tests/guards`` and everything in it,
    ``integration`` and ``properties`` likewise for their folders, and ``unit`` for the rest."""
    for suite, folder in FOLDERS.items():
        if path == folder or folder in path.parents:
            return suite
    return "unit"


def skips(chosen: str, path: Path) -> bool:
    """Whether a run of the *chosen* suite leaves *path* uncollected. The folders above the
    suites' own folders are walked by every run, or no run but unit would ever reach them."""
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


def is_property(test: object) -> bool:
    """Whether *test* is a Hypothesis property: ``@given`` marks every function it wraps with
    ``is_hypothesis_test = True``, so a property is found whatever name it was imported as."""
    return getattr(test, "is_hypothesis_test", False) is True


def refuse_properties(chosen: str, items: Iterable[Collected]) -> None:
    """Refuse, by name, every Hypothesis property in *items* unless the *chosen* run is the
    properties suite (#290): elsewhere a property would draw its cases inside the unit limits."""
    if chosen == "properties":
        return
    found = [item.nodeid for item in items if is_property(getattr(item, "obj", None))]
    if found:
        msg = (
            f"a {chosen} run collected Hypothesis properties, which run in tests/properties at "
            f"their full count with a unit stand-in each (#290): {', '.join(found)}"
        )
        raise pytest.UsageError(msg)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--suite",
        choices=SUITES,
        default="unit",
        help=(
            "the suite to run: unit (the default), guards, the whole-repo guards (#285), or "
            "integration, the tests whose real case needs a process (#286) or runs the recorded "
            "golden window (#292), or properties, the "
            "Hypothesis properties at their full count (#290)"
        ),
    )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    # None, never False: False would collect a path some other rule (norecursedirs) leaves out.
    return True if skips(config.getoption("suite"), collection_path.resolve()) else None


def pytest_itemcollected(item: pytest.Item) -> None:
    refuse_strays(item.config.getoption("suite"), [item])
    refuse_properties(item.config.getoption("suite"), [item])
