"""Every note key is a stable constant, defined once and used (M4 spec §7).

The training sub-project attaches lessons to keys, so a key must never be reworded or reused,
and no note may be built from a literal that could drift from its constant. The keys are read
from ``notes.py`` and the ``Note(...)`` calls from every engine module, both by walking the AST,
so a comment or a docstring that mentions a key is never a finding.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
NOTES = ENGINE / "notes.py"
KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
KNOWN = {"income.growth.short_history", "income.projection.costs_ignored"}


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


def engine_sources() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in sorted(ENGINE.rglob("*.py"))}


def test_the_constant_detector() -> None:
    source = "A = 'x.y'\n_B = 'z.w'\nC: str = 'c.d'\nD = 2\nE = F = 'e.f'\n"
    assert key_constants(source) == [("A", "x.y"), ("C", "c.d"), ("E", "e.f"), ("F", "e.f")]


def test_the_note_detector() -> None:
    source = (
        "Note(KEY, 't')\n"
        "notes.Note(notes.OTHER, 't')\n"
        "Note(key=NAMED, text='t')\n"
        "Note('income.x', 't')\n"
        "Note(f'{a}.b', 't')\n"
        "Note(make(), 't')\n"
        "Note()\n"
        "Other('income.y', 't')\n"
    )
    assert note_keys(source) == [
        "KEY",
        "OTHER",
        "NAMED",
        "line 4: key is not a constant",
        "line 5: key is not a constant",
        "line 6: key is not a constant",
        "line 7: key is not a constant",
    ]


def test_the_literal_detector() -> None:
    source = '"""Mentions income.x in passing."""\nK = "income.x"\nNote("income.y", "t")\n'
    assert {"income.x", "income.y"} <= set(string_literals(source))
    assert "income.x" not in string_literals('"""Mentions income.x in passing."""\n')


def test_every_key_is_a_dotted_lowercase_identifier_named_after_itself() -> None:
    keys = key_constants(NOTES.read_text(encoding="utf-8"))
    assert {value for _, value in keys} >= KNOWN
    for name, value in keys:
        assert KEY.fullmatch(value), f"{name} = {value!r} is not a dotted lowercase identifier"
        assert name == value.upper().replace(".", "_"), f"{name} is not named after {value!r}"


def test_no_key_is_defined_twice() -> None:
    keys = key_constants(NOTES.read_text(encoding="utf-8"))
    values = [value for _, value in keys]
    assert len(set(values)) == len(values) >= len(KNOWN)
    elsewhere = {
        path.name: sorted(set(values) & set(string_literals(source)))
        for path, source in engine_sources().items()
        if path != NOTES
    }
    assert len(elsewhere) >= 10, "the engine's modules were not found"
    assert {name: found for name, found in elsewhere.items() if found} == {}


def test_every_note_is_built_from_a_key_constant_and_every_key_is_used() -> None:
    names = {name for name, _ in key_constants(NOTES.read_text(encoding="utf-8"))}
    used = [key for source in engine_sources().values() for key in note_keys(source)]
    assert len(used) >= len(KNOWN), "no Note(...) call was found in the engine"
    assert sorted(set(used) - names) == []
    assert sorted(names - set(used)) == []
