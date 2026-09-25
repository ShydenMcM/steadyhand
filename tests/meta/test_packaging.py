"""Each published package carries the project's licence."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_each_package_ships_the_root_licence() -> None:
    root_licence = (ROOT / "LICENSE").read_bytes()
    packages = sorted(p for p in (ROOT / "packages").iterdir() if (p / "pyproject.toml").is_file())
    assert [p.name for p in packages] == ["steadyhand", "steadyhand-idx"]
    for package in packages:
        assert (package / "LICENSE").read_bytes() == root_licence, package.name
