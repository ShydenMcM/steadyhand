"""Coverage skips no shipped code (#374; Shyden 2026-10-22, "Count them as unrun").

Spec §10.5 asks for 100% branch coverage. The one function that talks to Yahoo, once excluded,
is tested with yfinance stood in, its real network run kept in the yahoo-shape workflow. A line
told to skip would count as unrun in the coverage gate anyway; this guard refuses the pragma and
any configured exclusion outright. It reads comments on purpose: the pragma is a comment.
"""

import tomllib
from pathlib import Path

from population import tracked

ROOT = Path(__file__).resolve().parents[2]
PRAGMA = "pragma: no cover"

# Measured on 2026-10-03 (#178): 57 Python files under packages/. Lower it only by a deliberate edit
# when the packages shrink.
FILES_FLOOR = 56


def python_files(root: Path) -> list[Path]:
    """Every Python file under *root*, found on disk."""
    return sorted(root.rglob("*.py"))


def pragma_lines(root: Path) -> list[str]:
    found: list[str] = []
    for path in python_files(root):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PRAGMA in line:
                found.append(f"{path.relative_to(root).as_posix()}:{number}: {line.strip()}")
    return found


def test_the_detector_sees_a_pragma(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\ny = 2  # pragma: no cover\n", encoding="utf-8")
    assert pragma_lines(tmp_path) == ["a.py:2: y = 2  # pragma: no cover"]


def test_no_shipped_line_is_excluded() -> None:
    """The Yahoo download, the last excluded function, is tested with yfinance stood in (#374)."""
    files = python_files(ROOT / "packages")
    # Independent of the walk: the packages' Python files as git lists them.
    assert files == tracked(ROOT / "packages", ".py")
    assert len(files) >= FILES_FLOOR, f"read {len(files)} files"
    assert pragma_lines(ROOT / "packages") == []


def test_the_configuration_excludes_nothing() -> None:
    """A Protocol method's body is its docstring, which coverage never counts, so no line is
    excluded by configuration (#374; Shyden 2026-10-22, "Count them as unrun")."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    report = pyproject["tool"]["coverage"]["report"]
    assert "exclude_also" not in report
    assert "exclude_lines" not in report
