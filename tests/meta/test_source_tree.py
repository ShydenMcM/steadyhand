"""Every guard reads Python source through ``source_tree.parse``, which names the file it cannot
parse (#190).

``ast.parse`` raises a ``SyntaxError`` naming ``<unknown>``. Nine readers called it directly, so a
module that did not parse failed its guard without saying which file it was. The shared reader
names the file; the walk below keeps a tenth direct call from appearing.
"""

import ast
from pathlib import Path

import pytest
from population import searched, tracked
from source_tree import UnreadableSourceError, parse

TESTS = Path(__file__).resolve().parents[1]
HOME = Path(__file__).with_name("source_tree.py")
AST_MODULE = "ast"
ONLY_AST = "PyCF_ONLY_AST"
# Measured on 2026-10-04 (#190): 97 Python files under tests/. Lower it only by a deliberate edit
# when the suite shrinks.
FILES_FLOOR = 96
DIRECT_FORMS = {
    "attribute": ("import ast\nast.parse(text)\n", "line 2: ast.parse"),
    "alias": ("import ast as syntax\nsyntax.parse(text)\n", "line 2: syntax.parse"),
    "one of several imports": ("import os, ast\nast.parse(text)\n", "line 2: ast.parse"),
    "inside a function": (
        "def f(text):\n    import ast\n    return ast.parse(text)\n",
        "line 3: ast.parse",
    ),
    "from-import": ("from ast import parse\n", "line 1: from ast import parse"),
    "from-import alias": ("from ast import parse as read\n", "line 1: from ast import parse"),
    "compile flag": (
        "import ast\ncompile(text, 'x', 'exec', ast.PyCF_ONLY_AST)\n",
        "line 2: ast.PyCF_ONLY_AST",
    ),
    "flag import": ("from ast import PyCF_ONLY_AST\n", "line 1: from ast import PyCF_ONLY_AST"),
}
"""Each way a module can parse Python itself, planted: (source, what the detector reports)."""


def direct_parses(source: str, name: str) -> list[str]:
    """Every way *source* parses Python itself rather than through ``source_tree.parse``:
    ``ast.parse`` under any name the module is imported as, ``parse`` imported from ``ast``, and
    ``compile`` asked for a tree by ``PyCF_ONLY_AST``. *name* names the file in errors."""
    tree = parse(source, name)
    aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == AST_MODULE
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == AST_MODULE:
            found += [
                f"line {node.lineno}: from ast import {alias.name}"
                for alias in node.names
                if alias.name in {"parse", ONLY_AST}
            ]
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.attr in {"parse", ONLY_AST}
        ):
            found.append(f"line {node.lineno}: {node.value.id}.{node.attr}")
    return found


def test_parse_returns_the_module_a_readable_source_holds() -> None:
    tree = parse("LIMIT = 1\n", "sample.py")
    assert isinstance(tree, ast.Module)
    assert [type(node) for node in tree.body] == [ast.Assign]


def test_parse_names_the_file_it_cannot_parse() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^broken\.py: ") as caught:
        parse("def (:\n", "broken.py")
    assert isinstance(caught.value.__cause__, SyntaxError)


@pytest.mark.parametrize("form", list(DIRECT_FORMS))
def test_the_detector_finds_each_way_of_parsing_directly(form: str) -> None:
    source, finding = DIRECT_FORMS[form]
    assert direct_parses(source, "sample.py") == [finding]


def test_the_detector_leaves_other_parses_and_mentions_alone() -> None:
    source = (
        '"""Mentions ast.parse in passing."""\n'
        "import json\n"
        "from ast import walk\n"
        "json.parse(text)\n"
        "parser.parse(text)\n"
        "'ast.parse(text)'\n"
        "# ast.parse(text)\n"
    )
    assert direct_parses(source, "sample.py") == []


def test_the_detector_names_the_file_it_cannot_parse() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^broken\.py: "):
        direct_parses("def (:\n", "broken.py")


def test_the_detector_finds_the_shared_reader_parsing() -> None:
    # Known positive on the real corpus: without it, a detector blind to the one form the
    # repository uses would pass the walk below by finding nothing.
    found = direct_parses(HOME.read_text(encoding="utf-8"), HOME.name)
    assert len(found) == 1
    assert found[0].endswith(": ast.parse")


def test_no_other_file_under_tests_parses_python_itself() -> None:
    files = sorted(TESTS.rglob("*.py"))
    # Independent of the walk: the Python files under tests/ as git lists them.
    assert files == tracked(TESTS, ".py")
    assert len(files) >= FILES_FLOOR, f"read {len(files)} files under {TESTS}"
    offenders = {
        str(path.relative_to(TESTS)): found
        for path in files
        if path != HOME and (found := direct_parses(path.read_text(encoding="utf-8"), path.name))
    }
    assert searched(offenders, of=len(files), what="Python files under tests/") == {}, (
        f"parse through source_tree.parse, which names the file: {offenders}"
    )
