"""No ``float`` in money, weight or ledger code (spec §4.4, §10.1).

The check walks the AST, so a comment or an ordinary string that mentions float is not a
finding, while ``float(...)``, a ``1.5`` literal and a ``"float"`` string annotation are.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"


def guarded_files() -> list[Path]:
    """Every module of the engine, found on disk: money, weights and ledgers run through it all."""
    return sorted(ENGINE.rglob("*.py"))


def _annotations(tree: ast.AST) -> Iterator[ast.expr]:
    for node in ast.walk(tree):
        if isinstance(node, ast.arg | ast.AnnAssign) and node.annotation is not None:
            yield node.annotation
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.returns is not None:
            yield node.returns


def float_uses(source: str) -> list[str]:
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "float":
            found.append(f"line {node.lineno}: float")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float | complex):
            kind = type(node.value).__name__
            found.append(f"line {node.lineno}: {kind} literal {node.value!r}")
    for annotation in _annotations(tree):
        for node in ast.walk(annotation):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and float_uses(node.value)
            ):
                found.append(f"line {node.lineno}: float in string annotation")
    return found


@pytest.mark.parametrize(
    ("source", "finding"),
    [
        ("x: float = 0", "line 1: float"),
        ("y = 1.5", "line 1: float literal 1.5"),
        ("z = float(1)", "line 1: float"),
        ("w = 2j", "line 1: complex literal 2j"),
        ('def f() -> "float": ...', "line 1: float in string annotation"),
        ('def g(a: "list[float]") -> None: ...', "line 1: float in string annotation"),
    ],
)
def test_detector_finds_float(source: str, finding: str) -> None:
    assert finding in float_uses(source)


def test_detector_ignores_comments_and_plain_strings() -> None:
    source = '# x: float = 1.5\nlabel = "float 1.5"\ncount: int = 2\n'
    assert float_uses(source) == []


def test_guarded_engine_modules_contain_no_float() -> None:
    files = guarded_files()
    names = {path.relative_to(ENGINE).as_posix() for path in files}
    assert {"money.py", "portfolio.py", "view.py", "strategies/buy_and_hold.py"} <= names
    findings = {
        path.relative_to(ENGINE).as_posix(): uses
        for path in files
        if (uses := float_uses(path.read_text(encoding="utf-8")))
    }
    assert findings == {}
