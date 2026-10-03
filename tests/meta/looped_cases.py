"""Find cases looped inside one test, for ``test_one_test_per_case.py`` (#173).

A population known before the run is one test per case (``@pytest.mark.parametrize``): a loop
inside one test stops at its first failing case, hides the rest, and its title names no case.
A *judging loop* is a ``for`` or ``while`` whose body asserts or expects a raise, or a
comprehension handed to ``all()`` or ``any()`` inside an ``assert``. The only one allowed loops
over a population that exists only at runtime, and says so with ``# runtime population: <why>``
on the line where it starts.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

ALLOW = "# runtime population:"


class UnreadableTestFileError(Exception):
    """A test file the reader cannot parse: refused by name, never skipped."""


@dataclass(frozen=True, slots=True)
class LoopedCase:
    """One judging loop: the test it sits in, its line, and its form."""

    test: str
    line: int
    kind: str


@dataclass(frozen=True, slots=True)
class Reading:
    """What one file's reading saw: every test it read, and the looped cases among them."""

    tests: tuple[str, ...]
    looped: tuple[LoopedCase, ...]


def _judges(statements: list[ast.stmt]) -> bool:
    """Whether *statements* assert anything or expect a raise, at any depth."""
    for statement in statements:
        for node in ast.walk(statement):
            if isinstance(node, ast.Assert):
                return True
            if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == "raises")
                or (isinstance(node.func, ast.Name) and node.func.id == "raises")
            ):
                return True
    return False


def _loops(test: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[int, str]]:
    """The judging loops anywhere inside *test*, as ``(line, kind)``."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(test):
        if isinstance(node, ast.For | ast.AsyncFor | ast.While) and _judges(
            node.body + node.orelse
        ):
            found.append((node.lineno, "while" if isinstance(node, ast.While) else "for"))
        elif isinstance(node, ast.Assert):
            found.extend(
                (call.lineno, call.func.id)
                for call in ast.walk(node.test)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id in ("all", "any")
                and call.args
                and isinstance(call.args[0], ast.GeneratorExp | ast.ListComp | ast.SetComp)
            )
    return sorted(found)


def _tests(
    body: list[ast.stmt], prefix: str
) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """The tests pytest collects from *body*: ``test*`` functions, and those of ``Test*``
    classes, nested classes included, in source order."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            found.append((f"{prefix}{node.name}", node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            found.extend(_tests(node.body, f"{prefix}{node.name}::"))
    return found


def read_tests(source: str, name: str) -> Reading:
    """The tests pytest collects from *source* (module level and ``Test*`` classes), and the
    judging loops inside them that carry no ``ALLOW`` comment. *name* names the file in errors."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        msg = f"{name}: {error}"
        raise UnreadableTestFileError(msg) from error
    lines = source.splitlines()
    tests = _tests(tree.body, "")
    looped = tuple(
        LoopedCase(test, line, kind)
        for test, node in tests
        for line, kind in _loops(node)
        if ALLOW not in lines[line - 1]
    )
    return Reading(tuple(test for test, _ in tests), looped)


def read_file(path: Path) -> Reading:
    """``read_tests`` on the file at *path*."""
    return read_tests(path.read_text(encoding="utf-8"), path.as_posix())
