"""Which suite a test file belongs to, and a run that collects across the line (#285, #286, #290).

Planted paths, never the tree: each misfiling a run could make is written out here by hand.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
import suites
from suites import (
    GUARDS,
    INTEGRATION,
    PROPERTIES,
    SUITES,
    TESTS,
    is_property,
    refuse_properties,
    refuse_strays,
    skips,
    suite_of,
)


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
        ("properties", "properties"),
        ("properties/test_engine_money.py", "properties"),
        ("properties/hypothesis_profile.py", "properties"),
        ("propertiesx/test_prefix_only.py", "unit"),
        ("engine/test_money.py", "unit"),
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


def test_the_properties_folder_is_tests_properties() -> None:
    expected = Path(__file__).resolve().parents[1] / "properties"
    assert expected == PROPERTIES


def test_there_are_four_suites_and_unit_comes_first() -> None:
    assert SUITES == ("unit", "guards", "integration", "properties")


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
        ("unit", "properties", True),
        ("unit", "properties/test_engine_money.py", True),
        ("guards", "properties", True),
        ("integration", "properties", True),
        ("properties", "engine", True),
        ("properties", "engine/test_money.py", True),
        ("properties", "conftest.py", True),
        ("properties", "properties", False),
        ("properties", "properties/test_engine_money.py", False),
    ],
)
def test_a_run_skips_the_other_suites_files(chosen: str, path: str, *, skipped: bool) -> None:
    assert skips(chosen, TESTS / path) is skipped


@pytest.mark.parametrize("chosen", ["unit", "guards", "integration", "properties"])
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
        ("unit", "properties/test_engine_money.py"),
        ("properties", "engine/test_money.py"),
        ("properties", "guards/test_no_float.py"),
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
        ("properties", "properties/test_engine_money.py"),
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
        ("unit", "properties", True),
        ("properties", "engine", True),
        ("properties", "properties", None),
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


# Hypothesis marks every function @given wraps with is_hypothesis_test = True: planted here as
# that mark alone, since a unit test imports no Hypothesis. tests/properties/test_profile.py
# checks the mark on a real @given.
def collected(nodeid: str, obj: object) -> SimpleNamespace:
    return SimpleNamespace(nodeid=nodeid, obj=obj)


PROPERTY = SimpleNamespace(is_hypothesis_test=True)


@pytest.mark.parametrize(
    ("test", "found"),
    [
        (PROPERTY, True),
        (SimpleNamespace(is_hypothesis_test=False), False),
        (SimpleNamespace(is_hypothesis_test=1), False),
        (SimpleNamespace(), False),
        (None, False),
    ],
    ids=["marked", "marked-false", "marked-not-a-bool", "unmarked", "no-function"],
)
def test_a_property_is_a_test_hypothesis_marked(test: object, *, found: bool) -> None:
    assert is_property(test) is found


@pytest.mark.parametrize("chosen", ["unit", "guards", "integration"])
def test_a_property_outside_the_properties_suite_is_refused_by_name(chosen: str) -> None:
    mixed = [
        collected("tests/engine/test_money.py::test_plain", SimpleNamespace()),
        collected("tests/engine/test_money.py::TestTimes::test_drawn", PROPERTY),
        collected("tests/idx/test_ticks.py::test_drawn[1]", PROPERTY),
    ]
    with pytest.raises(pytest.UsageError) as refused:
        refuse_properties(chosen, mixed)
    assert str(refused.value) == (
        f"a {chosen} run collected Hypothesis properties, which run in tests/properties at their "
        "full count with a unit stand-in each (#290): "
        "tests/engine/test_money.py::TestTimes::test_drawn, tests/idx/test_ticks.py::test_drawn[1]"
    )


@pytest.mark.parametrize("chosen", ["unit", "guards", "integration", "properties"])
def test_a_run_of_plain_tests_passes(chosen: str) -> None:
    refuse_properties(chosen, [collected("tests/x.py::test_plain", SimpleNamespace())])


def test_a_properties_run_passes_its_properties() -> None:
    refuse_properties("properties", [collected("tests/properties/x.py::test_drawn", PROPERTY)])


def test_the_item_hook_refuses_a_property_as_it_is_collected() -> None:
    drawn = SimpleNamespace(
        path=TESTS / "engine/test_money.py",
        config=config("unit"),
        nodeid="tests/engine/test_money.py::test_drawn",
        obj=PROPERTY,
    )
    with pytest.raises(pytest.UsageError, match=r"tests/engine/test_money\.py::test_drawn$"):
        suites.pytest_itemcollected(drawn)  # type: ignore[arg-type]
