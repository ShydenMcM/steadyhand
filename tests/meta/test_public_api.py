"""Everything public in the engine is importable from ``steadyhand`` itself.

The expected set is derived from the source, not listed, so a new public class cannot be
forgotten from ``__all__``. The one exception is ``steadyhand.training``: only the output layer
may import it (T1 spec §5), so ``steadyhand`` must not re-export it, and its public names are
importable from ``steadyhand.training`` instead.
"""

import ast
import importlib
import re
from pathlib import Path

import steadyhand
import steadyhand.training

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "packages/steadyhand/src"
CONSTANT = re.compile(r"[A-Z][A-Z0-9_]*")
TRAINING = "steadyhand.training"


def public_modules(package: str = "steadyhand") -> list[str]:
    """The public modules under *package*. For ``steadyhand`` that leaves out training."""
    modules: list[str] = []
    for path in sorted((SRC / package.replace(".", "/")).rglob("*.py")):
        parts = path.relative_to(SRC).with_suffix("").parts
        if any(part.startswith("_") for part in parts):
            continue  # private modules, and __init__ files, which only re-export
        name = ".".join(parts)
        if package != TRAINING and (name == TRAINING or name.startswith(f"{TRAINING}.")):
            continue
        modules.append(name)
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


def definitions(package: str = "steadyhand") -> dict[str, str]:
    """Every public name under *package*, mapped to the module that defines it."""
    found: dict[str, str] = {}
    for module in public_modules(package):
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


def test_training_is_left_out_of_the_engine_and_exports_its_own_names() -> None:
    assert not any(  # runtime population: the public modules the walk found
        module.startswith(TRAINING) for module in public_modules()
    )
    # The training package defines its lesson root in its own __init__, as well as re-exporting.
    own = SRC / "steadyhand/training/__init__.py"
    found = {
        **definitions(TRAINING),
        **dict.fromkeys(public_definitions(own.read_text(encoding="utf-8")), TRAINING),
    }
    assert {"Catalogue", "Lesson", "LessonError", "LESSONS"} <= set(found)
    assert sorted(set(found) ^ set(steadyhand.training.__all__)) == []
    wrong = sorted(
        name
        for name, module in found.items()
        if getattr(steadyhand.training, name) is not getattr(importlib.import_module(module), name)
    )
    assert wrong == []
    assert not set(found) & set(steadyhand.__all__)
