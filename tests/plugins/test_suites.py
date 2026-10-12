"""Which suite a test file belongs to, and a run that collects across the line (#285, #286).

Planted paths, never the tree: each misfiling a run could make is written out here by hand.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
import suites
from suites import GUARDS, INTEGRATION, SUITES, TESTS, refuse_strays, skips, suite_of


@pytest.mark.parametrize(
    ("path", "suite"),
    [
        ("guards", "guards"),
        ("guards/test_no_float.py", "guards"),
        ("guards/nested/test_deeper.py", "guards"),
        ("guardsx/test_prefix_only.py", "unit"),
        ("integration", "integration"),
        ("integration/scripts/test_ci_scope_git.py", "integration"),
        ("integrationx/test_prefix_only.py", "unit"),
        ("test_integration.py", "unit"),
        ("test_guards.py", "unit"),
        ("cli/test_cli.py", "unit"),
        ("repo/test_deploy_dev.py", "unit"),
        ("conftest.py", "unit"),
    ],
)
def test_each_path_belongs_to_one_suite(path: str, suite: str) -> None:
    assert suite_of(TESTS / path) == suite


def test_the_guards_folder_is_tests_guards() -> None:
    expected = Path(__file__).resolve().parents[1] / "guards"
    assert expected == GUARDS


def test_the_integration_folder_is_tests_integration() -> None:
    expected = Path(__file__).resolve().parents[1] / "integration"
    assert expected == INTEGRATION


def test_there_are_three_suites_and_unit_comes_first() -> None:
    assert SUITES == ("unit", "guards", "integration")


@pytest.mark.parametrize(
    ("chosen", "path", "skipped"),
    [
        ("unit", "guards", True),
        ("unit", "guards/test_no_float.py", True),
        ("unit", "cli", False),
        ("unit", "cli/test_cli.py", False),
        ("guards", "cli", True),
        ("guards", "cli/test_cli.py", True),
        ("guards", "conftest.py", True),
        ("guards", "guards/test_no_float.py", False),
        ("guards", "integration", True),
        ("unit", "integration", True),
        ("unit", "integration/cli/test_journeys_installed.py", True),
        ("integration", "cli", True),
        ("integration", "guards", True),
        ("integration", "conftest.py", True),
        ("integration", "integration/cli/test_journeys_installed.py", False),
    ],
)
def test_a_run_skips_the_other_suites_files(chosen: str, path: str, *, skipped: bool) -> None:
    assert skips(chosen, TESTS / path) is skipped


@pytest.mark.parametrize("chosen", ["unit", "guards", "integration"])
def test_a_run_walks_down_through_the_folders_above_the_guards(chosen: str) -> None:
    assert skips(chosen, TESTS) is False
    assert skips(chosen, TESTS.parent) is False


def items(*paths: str) -> list[SimpleNamespace]:
    return [SimpleNamespace(path=TESTS / path) for path in paths]


@pytest.mark.parametrize(
    ("chosen", "stray"),
    [
        ("unit", "guards/test_no_float.py"),
        ("unit", "integration/scripts/test_ci_scope_git.py"),
        ("guards", "cli/test_cli.py"),
        ("guards", "integration/scripts/test_ci_scope_git.py"),
        ("integration", "cli/test_cli.py"),
        ("integration", "guards/test_no_float.py"),
    ],
)
def test_a_test_from_the_other_suite_is_refused_by_name(chosen: str, stray: str) -> None:
    mixed = items("guards/test_lessons.py", "cli/test_init.py", stray)
    with pytest.raises(pytest.UsageError, match=f"tests/{stray}"):
        refuse_strays(chosen, mixed)


@pytest.mark.parametrize(
    ("chosen", "own"),
    [
        ("unit", "cli/test_init.py"),
        ("guards", "guards/test_lessons.py"),
        ("integration", "integration/cli/test_journeys_installed.py"),
    ],
)
def test_a_run_of_its_own_suite_alone_passes(chosen: str, own: str) -> None:
    refuse_strays(chosen, items(own, own))


@pytest.mark.parametrize(
    "hook", ["pytest_addoption", "pytest_ignore_collect", "pytest_itemcollected"]
)
def test_this_run_calls_the_suite_hooks(request: pytest.FixtureRequest, hook: str) -> None:
    caller = getattr(request.config.pluginmanager.hook, hook)
    assert getattr(suites, hook) in [impl.function for impl in caller.get_hookimpls()]


def test_this_run_is_a_unit_run_by_default(request: pytest.FixtureRequest) -> None:
    assert request.config.getoption("suite") == "unit"


def config(chosen: str) -> SimpleNamespace:
    return SimpleNamespace(getoption=lambda name: {"suite": chosen}[name])


@pytest.mark.parametrize(
    ("chosen", "path", "answer"),
    [
        ("unit", "guards", True),
        ("unit", "integration", True),
        ("unit", "cli", None),
        ("guards", "cli", True),
        ("integration", "cli", True),
        ("integration", "integration", None),
    ],
)
def test_the_collect_hook_skips_with_true_and_otherwise_leaves_it_to_others(
    chosen: str, path: str, *, answer: bool | None
) -> None:
    assert suites.pytest_ignore_collect(TESTS / path, config(chosen)) is answer  # type: ignore[arg-type]


def test_the_item_hook_refuses_a_stray_as_it_is_collected() -> None:
    stray = SimpleNamespace(path=TESTS / "guards/test_lessons.py", config=config("unit"))
    with pytest.raises(pytest.UsageError, match=r"tests/guards/test_lessons\.py"):
        suites.pytest_itemcollected(stray)  # type: ignore[arg-type]
