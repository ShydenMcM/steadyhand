"""The note and term keys of both packages, read from their source by walking the AST.

Shared by the key, term and training guards, so each derives the same key sets the same way
and none keeps a list. A comment or a docstring that mentions a key is never read as one.
"""

import ast
from pathlib import Path

from source_tree import parse

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
IDX = ROOT / "packages/steadyhand-idx/src/steadyhand_idx"
NOTE_MODULES = (ENGINE / "notes.py", IDX / "notes.py")
TERM_MODULE = ENGINE / "terms.py"
KEY_MODULES = (*NOTE_MODULES, TERM_MODULE)
TERM_PREFIX = "term."
SAVED_NOTE_READERS = {ENGINE / "snapshot.py": "_read_note", IDX / "state.py": "_audit_line"}
"""The functions allowed to build a ``Note`` from a key that is not a constant, one per module:
each reads a saved note back exactly as it was written (M5 spec §6.3). The note was built from a
constant when it was made; read back, its key is data, and it cannot drift."""


def key_constants(source: str, name: str) -> list[tuple[str, str]]:
    """Every public module-level constant in *source* whose value is a string: (name, value).
    *name* names the file in errors."""
    found: list[tuple[str, str]] = []
    for node in parse(source, name).body:
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


def note_keys(source: str, name: str, *, reader: str | None = None) -> list[str]:
    """How each ``Note(...)`` call in *source* names its key: a constant's name, or a finding.
    *name* names the file in errors.

    Calls inside the function named *reader* are left out: pass it only for the snapshot module.
    """
    tree = parse(source, name)
    skipped = {
        id(inner)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == reader
        for inner in ast.walk(node)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _called(node.func) != "Note" or id(node) in skipped:
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


def string_literals(source: str, name: str) -> list[str]:
    """Every string constant anywhere in *source*. A key matches only a string equal to it, so
    a docstring or a message that mentions a key among other words is not a finding. *name*
    names the file in errors."""
    return [
        node.value
        for node in ast.walk(parse(source, name))
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
    return [
        pair
        for path in paths
        for pair in key_constants(path.read_text(encoding="utf-8"), path.name)
    ]


def note_key_values() -> set[str]:
    """Every note key both packages define."""
    return {value for _, value in constants_in(NOTE_MODULES)}


def term_key_values() -> set[str]:
    """Every term key the engine defines."""
    return {value for _, value in constants_in((TERM_MODULE,))}


def all_keys() -> set[str]:
    """Every note and term key: what the lesson catalogue must explain, each exactly once."""
    return note_key_values() | term_key_values()
