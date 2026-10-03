"""Each published package carries the project's licence."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


PACKAGES = ["steadyhand", "steadyhand-idx"]


def test_the_packages_are_the_two_listed() -> None:
    packages = sorted(p for p in (ROOT / "packages").iterdir() if (p / "pyproject.toml").is_file())
    assert [p.name for p in packages] == PACKAGES


@pytest.mark.parametrize("package", PACKAGES)
def test_each_package_ships_the_root_licence(package: str) -> None:
    root_licence = (ROOT / "LICENSE").read_bytes()
    assert (ROOT / "packages" / package / "LICENSE").read_bytes() == root_licence
