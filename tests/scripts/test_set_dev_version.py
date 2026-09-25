"""The dev-version script rewrites exactly what it should, and refuses anything else."""

import shutil
import tomllib
from pathlib import Path

import pytest

import set_dev_version
from set_dev_version import VersionError, main

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def copies(tmp_path: Path) -> tuple[Path, Path]:
    engine = tmp_path / "engine.toml"
    idx = tmp_path / "idx.toml"
    shutil.copyfile(ROOT / "packages/steadyhand/pyproject.toml", engine)
    shutil.copyfile(ROOT / "packages/steadyhand-idx/pyproject.toml", idx)
    return engine, idx


def project(path: Path) -> dict[str, object]:
    loaded = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    assert isinstance(loaded, dict)
    return loaded


def test_rewrites_both_versions_and_pins_the_engine(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    assert set_dev_version.set_dev_version(7, engine, idx) == "0.1.0.dev7"
    assert project(engine)["version"] == "0.1.0.dev7"
    assert project(idx)["version"] == "0.1.0.dev7"
    assert project(idx)["dependencies"] == ["steadyhand==0.1.0.dev7"]


def test_refuses_a_run_number_below_one(copies: tuple[Path, Path]) -> None:
    with pytest.raises(VersionError, match="run number must be positive, got 0"):
        set_dev_version.set_dev_version(0, *copies)


def test_refuses_mismatched_versions(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    idx.write_text(
        idx.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "0.2.0"')
    )
    with pytest.raises(
        VersionError, match=r"steadyhand-idx is at 0\.2\.0 but the engine is at 0\.1\.0"
    ):
        set_dev_version.set_dev_version(1, engine, idx)


def test_refuses_an_engine_without_a_plain_version(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    engine.write_text(
        engine.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "0.1"')
    )
    with pytest.raises(VersionError, match=r"engine\.toml: expected exactly one match"):
        set_dev_version.set_dev_version(1, engine, idx)


def test_refuses_an_idx_without_the_engine_dependency_line(copies: tuple[Path, Path]) -> None:
    engine, idx = copies
    idx.write_text(
        idx.read_text(encoding="utf-8").replace('    "steadyhand",\n', '    "steadyhand>=0.1",\n')
    )
    with pytest.raises(VersionError, match=r"idx\.toml: expected exactly one match"):
        set_dev_version.set_dev_version(1, engine, idx)
    assert project(engine)["version"] == "0.1.0"  # nothing is written unless both rewrite


@pytest.mark.parametrize(
    "argv",
    [
        ["set_dev_version.py"],
        ["set_dev_version.py", "x"],
        # Unicode digits: isdigit() accepts both; int() rejects one and silently reads the other.
        ["set_dev_version.py", "\u00b2"],
        ["set_dev_version.py", "\u0661"],
    ],
)
def test_main_refuses_bad_usage(
    argv: list[str],
    copies: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Point the script at copies: a regression here must never rewrite the real pyprojects.
    monkeypatch.setattr(set_dev_version, "ENGINE", copies[0])
    monkeypatch.setattr(set_dev_version, "IDX", copies[1])
    assert main(argv) == 2
    assert "usage: set_dev_version.py <run-number>" in capsys.readouterr().err
    assert project(copies[0])["version"] == "0.1.0"
    assert project(copies[1])["version"] == "0.1.0"


def test_main_prints_the_version(
    copies: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(set_dev_version, "ENGINE", copies[0])
    monkeypatch.setattr(set_dev_version, "IDX", copies[1])
    assert main(["set_dev_version.py", "42"]) == 0
    assert capsys.readouterr().out == "0.1.0.dev42\n"
