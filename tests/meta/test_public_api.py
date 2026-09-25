"""Everything public in the engine is importable from ``steadyhand`` itself.

The expected set is derived from the source, not listed, so a new public class cannot be
forgotten from ``__all__``.
"""

import ast
import importlib
import re
from pathlib import Path

import steadyhand

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "packages/steadyhand/src"
CONSTANT = re.compile(r"[A-Z][A-Z0-9_]*")


def public_modules() -> list[str]:
    modules: list[str] = []
    for path in sorted((SRC / "steadyhand").rglob("*.py")):
        parts = path.relative_to(SRC).with_suffix("").parts
        if any(part.startswith("_") for part in parts):
            continue  # private modules, and __init__ files, which only re-export
        modules.append(".".join(parts))
    return modules


def public_definitions(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.TypeAlias):
            name = node.name if not isinstance(node, ast.TypeAlias) else node.name.id
            if not name.startswith("_"):
                names.add(name)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(
                t.id for t in targets if isinstance(t, ast.Name) and CONSTANT.fullmatch(t.id)
            )
    return names


def definitions() -> dict[str, str]:
    """Every public name, mapped to the module that defines it."""
    found: dict[str, str] = {}
    for module in public_modules():
        path = SRC / (module.replace(".", "/") + ".py")
        for name in public_definitions(path.read_text(encoding="utf-8")):
            found[name] = module
    return found


def test_definition_detector() -> None:
    source = (
        "class A: ...\nclass _B: ...\ndef f() -> None: ...\ntype T = int\n"
        "LIMIT = 1\nTYPED: int = 2\n_PRIVATE = 3\nlower = 4\n"
    )
    assert public_definitions(source) == {"A", "f", "T", "LIMIT", "TYPED"}


def test_every_public_definition_is_exported_as_the_same_object() -> None:
    found = definitions()
    assert {"Money", "Portfolio", "MarketRules", "Broker", "DISCLAIMER"} <= set(found)
    missing = sorted(set(found) - set(steadyhand.__all__))
    assert missing == []
    wrong = sorted(
        name
        for name, module in found.items()
        if getattr(steadyhand, name) is not getattr(importlib.import_module(module), name)
    )
    assert wrong == []


def test_all_lists_only_defined_names() -> None:
    extra = sorted(set(steadyhand.__all__) - set(definitions()) - {"__version__"})
    assert extra == []
