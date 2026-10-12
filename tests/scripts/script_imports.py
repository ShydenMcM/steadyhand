"""What a CI script imports, read from its source (#286): CI runs the scripts with the runner's
system python3 before uv installs anything, so they may import the standard library alone."""

import ast
from pathlib import Path

from source_tree import parse

DYNAMIC = frozenset({"__import__", "import_module"})


def imported_modules(path: Path) -> set[str]:
    """The top-level name of every module *path* imports, in either import statement. A dynamic
    import (``__import__``, ``importlib.import_module``) cannot be read, so it is refused."""
    tree = parse(path.read_text(encoding="utf-8"), path.name)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"a relative import in {path.name}"
            assert node.module is not None
            found.add(node.module.partition(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
            assert name not in DYNAMIC, f"a dynamic import in {path.name}, line {node.lineno}"
    return found
