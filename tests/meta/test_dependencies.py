"""The engine uses the standard library only, and the IDX package uses only its public API.

Spec §4.2. The pyproject check covers what is declared; the import walk covers what is used.
"""

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
IDX = ROOT / "packages/steadyhand-idx/src/steadyhand_idx"


def top_level_imports(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            names.add(node.module.split(".")[0])
    return names


def _is_private(part: str) -> bool:
    return part.startswith("_") and not (part.startswith("__") and part.endswith("__"))


def private_engine_imports(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "steadyhand" and any(_is_private(p) for p in parts[1:]):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            parts = node.module.split(".")
            if parts[0] != "steadyhand":
                continue
            if any(_is_private(p) for p in parts[1:]):
                found.append(node.module)
            found.extend(
                f"{node.module}.{alias.name}" for alias in node.names if _is_private(alias.name)
            )
    return found


def test_engine_pyproject_declares_no_runtime_dependencies() -> None:
    pyproject = (ROOT / "packages/steadyhand/pyproject.toml").read_text(encoding="utf-8")
    project = tomllib.loads(pyproject)["project"]
    assert project["dependencies"] == []
    assert "optional-dependencies" not in project


def test_import_detector_sees_absolute_imports_and_skips_relative_ones() -> None:
    source = "import os.path\nfrom decimal import Decimal\nfrom . import money\nimport yaml as y\n"
    assert top_level_imports(source) == {"os", "decimal", "yaml"}


def test_engine_imports_only_the_standard_library() -> None:
    files = sorted(ENGINE.rglob("*.py"))
    assert len(files) >= 8, files
    imported = {path: top_level_imports(path.read_text(encoding="utf-8")) for path in files}
    assert "decimal" in set().union(*imported.values())
    allowed = sys.stdlib_module_names | {"steadyhand"}
    foreign = {
        path.relative_to(ENGINE).as_posix(): sorted(names - allowed)
        for path, names in imported.items()
        if names - allowed
    }
    assert foreign == {}


def test_private_import_detector() -> None:
    source = (
        "from steadyhand._validate import require_date\n"
        "import steadyhand._validate\n"
        "from steadyhand import _hidden, Money, __version__\n"
        "from steadyhand_idx._x import y\n"
        "import os\n"
    )
    assert private_engine_imports(source) == [
        "steadyhand._validate",
        "steadyhand._validate",
        "steadyhand._hidden",
    ]


def test_idx_uses_only_the_engine_public_api() -> None:
    files = sorted(IDX.rglob("*.py"))
    assert files
    found = {
        path.relative_to(IDX).as_posix(): hits
        for path in files
        if (hits := private_engine_imports(path.read_text(encoding="utf-8")))
    }
    assert found == {}
