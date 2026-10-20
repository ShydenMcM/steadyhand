"""mypy's types for the literal-floor reader (#272), from a real mypy run over a planted project:
each kind of object the reader asks about, one test each. mypy takes seconds, so these are guards,
not unit tests; the reader's own plants (tests/guard_helpers) use a hand-written stand-in."""

import ast
from pathlib import Path

import pytest
from literal_floor_types import MypyTypes
from literal_floors import LIBRARY, UNKNOWN, UnreadableSourceError

SHAPES = """\
from typing import Protocol


class Box:
    least: int = 5


class Crate(Box):
    pass


class Shape(Protocol):
    least: int


class Other:
    least: int = 1
"""

PLANTED = """\
import json
from pathlib import Path

from shapes import Box, Crate, Other


def test_reads(either: Box | Other, crate: Crate) -> None:
    box = Box()
    assert box.least
    assert Box.least
    assert Path("x").name
    assert json.loads("{}").least
    assert either.least
    assert crate.least
"""

PYPROJECT = '[tool.mypy]\nstrict = true\npython_version = "3.12"\n'


def _plant(root: Path, planted: str) -> None:
    for folder, name, text in (
        ("packages", "shapes.py", SHAPES),
        ("tests", "test_planted.py", planted),
        ("scripts", "tool.py", "TOOL = 1\n"),
    ):
        (root / folder).mkdir()
        (root / folder / name).write_text(text, encoding="utf-8")
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")


@pytest.fixture(scope="module")
def types(tmp_path_factory: pytest.TempPathFactory) -> MypyTypes:
    root = tmp_path_factory.mktemp("planted")
    _plant(root, PLANTED)
    return MypyTypes(root)


def _read(source: str, index: int) -> ast.Attribute:
    """The attribute read in the *index*-th assert of *source*."""
    asserts = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Assert)]
    found = asserts[index].test
    assert isinstance(found, ast.Attribute)
    return found


def _class(source: str, name: str) -> ast.ClassDef:
    return next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def test_an_object_of_our_class_is_owned_by_it(types: MypyTypes) -> None:
    assert types.owners("tests/test_planted.py", _read(PLANTED, 0)) == frozenset({"shapes.Box"})


def test_a_class_object_is_owned_by_its_class(types: MypyTypes) -> None:
    assert types.owners("tests/test_planted.py", _read(PLANTED, 1)) == frozenset({"shapes.Box"})


def test_an_outside_librarys_object_is_the_librarys(types: MypyTypes) -> None:
    assert types.owners("tests/test_planted.py", _read(PLANTED, 2)) == LIBRARY


def test_an_untyped_value_is_a_type_the_check_cannot_work_out(types: MypyTypes) -> None:
    assert types.owners("tests/test_planted.py", _read(PLANTED, 3)) == UNKNOWN


def test_a_union_is_owned_by_each_of_its_classes(types: MypyTypes) -> None:
    owners = types.owners("tests/test_planted.py", _read(PLANTED, 4))
    assert owners == frozenset({"shapes.Box", "shapes.Other"})


def test_a_place_mypy_did_not_type_is_a_type_the_check_cannot_work_out(
    types: MypyTypes,
) -> None:
    assert types.owners("tests/test_planted.py", _read("assert elsewhere.least\n", 0)) == UNKNOWN


def test_a_class_is_named_by_where_it_is_defined(types: MypyTypes) -> None:
    assert types.class_name("packages/shapes.py", _class(SHAPES, "Crate")) == "shapes.Crate"


def test_a_class_mypy_does_not_know_is_unnamed(types: MypyTypes) -> None:
    unknown = _class("class Nowhere:\n    pass\n", "Nowhere")
    assert types.class_name("packages/shapes.py", unknown) == UNKNOWN


def test_a_class_is_related_to_its_subclasses(types: MypyTypes) -> None:
    assert types.related("shapes.Box") == frozenset({"shapes.Box", "shapes.Crate"})


def test_a_subclass_is_related_to_its_base(types: MypyTypes) -> None:
    assert types.related("shapes.Crate") == frozenset({"shapes.Box", "shapes.Crate"})


def test_a_protocol_may_be_met_by_any_class(types: MypyTypes) -> None:
    assert types.related("shapes.Shape") is None


def test_a_tree_mypy_rejects_is_refused_by_name(tmp_path: Path) -> None:
    _plant(tmp_path, "def broken() -> int:\n    return 'text'\n")
    with pytest.raises(UnreadableSourceError, match="mypy found 1 errors"):
        MypyTypes(tmp_path)
