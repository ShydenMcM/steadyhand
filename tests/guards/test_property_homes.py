"""Every Hypothesis property runs in tests/properties and calls a unit stand-in of its name (#290).

Shyden's ruling on #290 (2026-10-12): a property that cannot meet the unit limits moves to a
properties suite at its full count, and unit keeps a fast stand-in of it. The stand-in is the
unit test the property calls, with the same name, in the unit file the property file's name
points to (``tests/properties/test_engine_money.py`` to ``tests/engine/test_money.py``),
parametrized over chosen cases. The suites plugin refuses a property that any other run collects;
this guard checks the rest from the source: no unit test file imports Hypothesis, so no strategy
is left behind in one, and every property has its stand-in and calls it.
"""

import ast
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from floors import floor_breach
from population import searched, tracked
from source_tree import UnreadableSourceError, parse
from suites import PROPERTIES, suite_of

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
RAW_GIVEN = re.compile(r"^[ \t]*@(?:hypothesis\.)?given\b", re.MULTILINE)
FUNCTION = ast.FunctionDef | ast.AsyncFunctionDef


def _names(node: ast.expr) -> bool:
    """Whether *node* names Hypothesis's ``given``, bare or through its module."""
    return (isinstance(node, ast.Name) and node.id == "given") or (
        isinstance(node, ast.Attribute) and node.attr == "given"
    )


def _is_property(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        _names(decorator.func if isinstance(decorator, ast.Call) else decorator)
        for decorator in function.decorator_list
    )


def _imported(node: ast.Import | ast.ImportFrom | ast.Call) -> str | None:
    """The module *node* imports, when it is an import or a call importing a named module."""
    if isinstance(node, ast.Import):
        return next((alias.name for alias in node.names if _hypothesis(alias.name)), None)
    if isinstance(node, ast.ImportFrom):
        return node.module
    if (
        isinstance(node.func, ast.Name | ast.Attribute)
        and (node.func.id if isinstance(node.func, ast.Name) else node.func.attr)
        in {"__import__", "import_module"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _hypothesis(module: str | None) -> bool:
    return module is not None and (module == "hypothesis" or module.startswith("hypothesis."))


def hypothesis_imports(source: str, name: str) -> list[int]:
    """Line numbers of every import of Hypothesis in *source*, in any form the code writes one.
    *name* names the file in errors."""
    return sorted(
        node.lineno
        for node in ast.walk(parse(source, name))
        if isinstance(node, ast.Import | ast.ImportFrom | ast.Call) and _hypothesis(_imported(node))
    )


def properties(source: str, name: str) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function in *source* that ``@given`` wraps, in classes too."""
    return [
        node
        for node in ast.walk(parse(source, name))
        if isinstance(node, FUNCTION) and _is_property(node)
    ]


def stand_ins(source: str, name: str) -> set[str]:
    """The name of every function in *source* that ``@given`` does not wrap, in classes too."""
    return {
        node.name
        for node in ast.walk(parse(source, name))
        if isinstance(node, FUNCTION) and not _is_property(node)
    }


def calls_its_stand_in(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether *function* calls a function of its own name from another module or class: the
    unit stand-in, as ``unit.test_x(...)`` or ``unit.TestX().test_x(...)``."""
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == function.name
        for node in ast.walk(function)
    )


def unit_home(path: Path) -> Path:
    """The unit file a properties file's name points to: ``test_<folder>_<rest>.py`` in
    tests/properties holds the properties of ``tests/<folder>/test_<rest>.py``."""
    folder, _, rest = path.name.removeprefix("test_").partition("_")
    return TESTS / folder / f"test_{rest}"


PLANTED_IMPORTS = {
    "from hypothesis import given": "from hypothesis import given\n",
    "import hypothesis": "import hypothesis\n",
    "import its strategies under a name": "import hypothesis.strategies as st\n",
    "from its strategies": "from hypothesis.strategies import integers\n",
    "inside a function": "def f():\n    from hypothesis import given\n",
    "among other modules": "import os, hypothesis\n",
    "by __import__": "def f():\n    return __import__('hypothesis')\n",
    "by import_module": "def f():\n    return importlib.import_module('hypothesis.strategies')\n",
}


@pytest.mark.parametrize("form", PLANTED_IMPORTS)
def test_each_form_of_hypothesis_import_is_found(form: str) -> None:
    source = PLANTED_IMPORTS[form]
    assert hypothesis_imports(source, "planted.py") == [source.count("\n")]


@pytest.mark.parametrize(
    "source",
    [
        "import os\n",
        "from hypothesis_profile import load\n",
        "import hypothesisx\n",
        "from . import hypothesis\n",
        "def f():\n    return __import__(name)\n",
    ],
    ids=["another module", "a name that starts the same", "a longer name", "relative", "unnamed"],
)
def test_other_imports_are_not_found(source: str) -> None:
    assert hypothesis_imports(source, "planted.py") == []


PLANTED_PROPERTIES = {
    "given with strategies": "@given(st.integers())\ndef test_x(n): ...\n",
    "given through its module": "@hypothesis.given(st.integers())\ndef test_x(n): ...\n",
    "given bare": "@given\ndef test_x(n): ...\n",
    "under other decorators": (
        "@settings(max_examples=5)\n@given(st.integers())\n@example(1)\ndef test_x(n): ...\n"
    ),
    "a method": "class TestX:\n    @given(st.integers())\n    def test_x(self, n): ...\n",
    "async": "@given(st.integers())\nasync def test_x(n): ...\n",
}


@pytest.mark.parametrize("form", PLANTED_PROPERTIES)
def test_each_form_of_property_is_found_and_is_no_stand_in(form: str) -> None:
    source = PLANTED_PROPERTIES[form]
    assert [found.name for found in properties(source, "planted.py")] == ["test_x"]
    assert "test_x" not in stand_ins(source, "planted.py")


def test_a_plain_or_parametrized_test_is_a_stand_in() -> None:
    source = (
        "@pytest.mark.parametrize('n', [1])\ndef test_x(n): ...\n"
        "class TestY:\n    def test_y(self): ...\n"
        "@settings(max_examples=5)\ndef test_z(): ...\n"
    )
    assert properties(source, "planted.py") == []
    assert stand_ins(source, "planted.py") == {"test_x", "test_y", "test_z"}


@pytest.mark.parametrize(
    ("body", "calls"),
    [
        ("unit.test_x(n)", True),
        ("unit.TestX().test_x(n)", True),
        ("unit.test_y(n)", False),
        ("test_x(n)", False),
        ("unit.test_x", False),
        ("pass", False),
    ],
    ids=["module", "class", "another name", "itself", "no call", "nothing"],
)
def test_a_property_calls_its_stand_in_only_by_its_own_name(body: str, *, calls: bool) -> None:
    (found,) = properties(f"@given(st.integers())\ndef test_x(n):\n    {body}\n", "planted.py")
    assert calls_its_stand_in(found) is calls


@pytest.mark.parametrize(
    ("name", "home"),
    [
        ("test_engine_money.py", "engine/test_money.py"),
        ("test_idx_ticks.py", "idx/test_ticks.py"),
        ("test_engine_portfolio_properties.py", "engine/test_portfolio_properties.py"),
    ],
)
def test_a_properties_file_names_its_unit_home(name: str, home: str) -> None:
    assert unit_home(PROPERTIES / name) == TESTS / home


@pytest.mark.parametrize("reader", [hypothesis_imports, properties, stand_ins])
def test_each_reader_names_the_file_it_cannot_parse(reader: Callable[[str, str], object]) -> None:
    with pytest.raises(UnreadableSourceError, match=r"^broken\.py: "):
        reader("def (:\n", "broken.py")


def test_the_import_reader_finds_the_properties_profiles_import() -> None:
    # Known positive: a reader that matched nothing would pass the test below it.
    profile = PROPERTIES / "hypothesis_profile.py"
    assert len(hypothesis_imports(profile.read_text(), profile.name)) == 1


def test_no_unit_test_file_imports_hypothesis() -> None:
    walked = sorted(p for p in TESTS.rglob("*.py") if suite_of(p) == "unit")
    # Independent of the walk: the files as git lists them.
    assert walked == [p for p in tracked(TESTS, ".py") if suite_of(p) == "unit"]
    offenders = {
        str(p.relative_to(TESTS)): lines
        for p in walked
        if (lines := hypothesis_imports(p.read_text(), str(p.relative_to(TESTS))))
    }
    assert searched(offenders, of=len(walked), what="unit test files") == {}, (
        f"a property and its strategies belong in tests/properties (#290): {offenders}"
    )
    assert floor_breach("python.property-homes.unit-files", len(walked)) is None


def test_every_property_calls_a_unit_stand_in_of_its_name() -> None:
    files = tracked(PROPERTIES, ".py")
    assert files == sorted(PROPERTIES.rglob("*.py"))
    found = [
        (path, prop)
        for path in files
        for prop in properties(path.read_text(), str(path.relative_to(TESTS)))
    ]
    # Independent of the parse: the @given lines as the text holds them.
    assert len(found) == sum(len(RAW_GIVEN.findall(path.read_text())) for path in files)
    missing = []
    for path, prop in found:  # runtime population: the properties found in tests/properties
        home = unit_home(path)
        where = f"{path.relative_to(TESTS)}::{prop.name}"
        if not home.is_file():
            missing.append(f"{where}: no unit file {home.relative_to(TESTS)}")
        elif prop.name not in stand_ins(home.read_text(), str(home.relative_to(TESTS))):
            missing.append(f"{where}: no stand-in of its name in {home.relative_to(TESTS)}")
        elif not calls_its_stand_in(prop):
            missing.append(f"{where}: never calls its stand-in")
    assert searched(missing, of=len(found), what="properties") == []
    assert floor_breach("python.property-homes.properties", len(found)) is None
