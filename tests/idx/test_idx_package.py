"""The IDX package is installed from this workspace and reports its own version."""

import tomllib
from pathlib import Path

import steadyhand_idx

ROOT = Path(__file__).resolve().parents[2]


def test_version_matches_the_package_pyproject() -> None:
    pyproject = tomllib.loads(
        (ROOT / "packages/steadyhand-idx/pyproject.toml").read_text(encoding="utf-8")
    )
    assert steadyhand_idx.__version__ == pyproject["project"]["version"]


def test_every_exported_name_resolves() -> None:
    assert "__version__" in steadyhand_idx.__all__
    missing = [name for name in steadyhand_idx.__all__ if not hasattr(steadyhand_idx, name)]
    assert missing == []
