"""The note and term keys of both packages, read from their source by walking the AST.

Shared by the key, term and training guards, so each derives the same key sets the same way
and none keeps a list. A comment or a docstring that mentions a key is never read as one.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
IDX = ROOT / "packages/steadyhand-idx/src/steadyhand_idx"
NOTE_MODULES = (ENGINE / "notes.py", IDX / "notes.py")
TERM_MODULE = ENGINE / "terms.py"
KEY_MODULES = (*NOTE_MODULES, TERM_MODULE)
TERM_PREFIX = "term."


def key_constants(source: str) -> list[tuple[str, str]]:
    """Every public module-level constant in *source* whose value is a string: (name, value)."""
    found: list[tuple[str, str]] = []
    for node in ast.parse(source).body:
        targets: list[ast.expr] = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        value = getattr(node, "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            found += [
                (t.id, value.value)
                for t in targets
                if isinstance(t, ast.Name) and not t.id.startswith("_")
            ]
    return found


def note_keys(source: str) -> list[str]:
    """How each ``Note(...)`` call in *source* names its key: a constant's name, or a finding."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or _called(node.func) != "Note":
            continue
        keywords = [keyword.value for keyword in node.keywords if keyword.arg == "key"]
        key = node.args[0] if node.args else next(iter(keywords), None)
        if isinstance(key, ast.Name):
            found.append(key.id)
        elif isinstance(key, ast.Attribute):
            found.append(key.attr)
        else:
            found.append(f"line {node.lineno}: key is not a constant")
    return found


def string_literals(source: str) -> list[str]:
    """Every string constant anywhere in *source*. A key matches only a string equal to it, so
    a docstring or a message that mentions a key among other words is not a finding."""
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _called(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def package_sources() -> dict[Path, str]:
    """Every Python file of both packages, by path."""
    paths = sorted([*ENGINE.rglob("*.py"), *IDX.rglob("*.py")])
    return {path: path.read_text(encoding="utf-8") for path in paths}


def constants_in(paths: tuple[Path, ...]) -> list[tuple[str, str]]:
    return [pair for path in paths for pair in key_constants(path.read_text(encoding="utf-8"))]


def note_key_values() -> set[str]:
    """Every note key both packages define."""
    return {value for _, value in constants_in(NOTE_MODULES)}


def term_key_values() -> set[str]:
    """Every term key the engine defines."""
    return {value for _, value in constants_in((TERM_MODULE,))}


def all_keys() -> set[str]:
    """Every note and term key: what the lesson catalogue must explain, each exactly once."""
    return note_key_values() | term_key_values()
