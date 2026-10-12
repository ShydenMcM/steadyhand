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

import pytest
from source_tree import UnreadableSourceError, parse

import steadyhand
import steadyhand.training

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "packages/steadyhand/src"
CONSTANT = re.compile(r"[A-Z][A-Z0-9_]*")
TRAINING = "steadyhand.training"
DEFINITION = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef | ast.TypeAlias
UNREAD_FORMS = {
    "If": "if VERSION:\n    class A: ...\n",
    "Try": "try:\n    LIMIT = 1\nexcept ImportError:\n    LIMIT = 2\n",
    "With": "with lock:\n    def f() -> None: ...\n",
    "For": "for item in ():\n    LIMIT = item\n",
    "While": "while False:\n    LIMIT = 1\n",
    "Match": "match VERSION:\n    case 1:\n        LIMIT = 1\n",
    "AugAssign": "LIMIT += 1\n",
    "Expr": "(LIMIT := 1)\n",
    "Assign": "A, B = 1, 2\n",
    "AnnAssign": "holder.LIMIT: int = 1\n",
}
"""A module-level statement of each kind ``public_definitions`` refuses, each binding a name
the export check would otherwise miss."""


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


def _assigns_names(node: ast.Assign | ast.AnnAssign) -> bool:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return all(isinstance(target, ast.Name) for target in targets)


def _binds_nothing(node: ast.stmt) -> bool:
    """An import (a re-export, not a definition) or a bare expression binding no name, such
    as a docstring."""
    if isinstance(node, ast.Import | ast.ImportFrom):
        return True
    return isinstance(node, ast.Expr) and not any(
        isinstance(inner, ast.NamedExpr) for inner in ast.walk(node)
    )


def public_definitions(source: str, name: str) -> set[str]:
    """Every public name *source* defines at the top level; *name* names the file in errors."""
    names: set[str] = set()
    for node in parse(source, name).body:
        if isinstance(node, DEFINITION):
            defined = node.name.id if isinstance(node, ast.TypeAlias) else node.name
            if not defined.startswith("_"):
                names.add(defined)
        elif isinstance(node, ast.Assign | ast.AnnAssign) and _assigns_names(node):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(
                t.id for t in targets if isinstance(t, ast.Name) and CONSTANT.fullmatch(t.id)
            )
        elif not _binds_nothing(node):
            msg = (
                f"{name}: line {node.lineno}: a module-level {type(node).__name__} is not read: "
                "it could define a public name, so define public names at the top level"
            )
            raise UnreadableSourceError(msg)
    return names


def definitions(package: str = "steadyhand") -> dict[str, str]:
    """Every public name under *package*, mapped to the module that defines it."""
    found: dict[str, str] = {}
    for module in public_modules(package):
        path = SRC / (module.replace(".", "/") + ".py")
        for name in public_definitions(
            path.read_text(encoding="utf-8"), path.relative_to(SRC).as_posix()
        ):
            found[name] = module
    return found


def test_definition_detector() -> None:
    source = (
        "class A: ...\nclass _B: ...\ndef f() -> None: ...\ntype T = int\n"
        "LIMIT = 1\nTYPED: int = 2\n_PRIVATE = 3\nlower = 4\n"
    )
    assert public_definitions(source, "sample.py") == {"A", "f", "T", "LIMIT", "TYPED"}


def test_definition_detector_reads_an_async_function() -> None:
    assert public_definitions("async def fetch() -> None: ...\n", "sample.py") == {"fetch"}


def test_definition_detector_names_the_file_it_cannot_parse() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^broken\.py: "):
        public_definitions("def (:\n", "broken.py")


@pytest.mark.parametrize("kind", list(UNREAD_FORMS))
def test_definition_detector_refuses_a_statement_it_does_not_read(kind: str) -> None:
    with pytest.raises(
        UnreadableSourceError, match=rf"^broken\.py: line 1: a module-level {kind} "
    ):
        public_definitions(UNREAD_FORMS[kind], "broken.py")


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
        **dict.fromkeys(
            public_definitions(own.read_text(encoding="utf-8"), own.relative_to(SRC).as_posix()),
            TRAINING,
        ),
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
