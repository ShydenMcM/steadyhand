"""The default test run leaves nothing out but the perf suite (global rule 2026-11-05, #502).

``perf`` times the engine and runs in its own CI step, without coverage; every other test runs in
the default run. A second deselecting marker would be a suite that never runs on a pull request,
as the hand-started Yahoo live check was until #502 removed it.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def pytest_options() -> dict[str, list[str]]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    options: dict[str, list[str]] = pyproject["tool"]["pytest"]["ini_options"]
    return options


def test_the_default_run_deselects_the_perf_marker_alone() -> None:
    addopts = pytest_options()["addopts"]
    expression = addopts[addopts.index("-m") + 1]
    assert expression == "not perf"


def test_the_declared_markers_are_perf_and_last() -> None:
    names = sorted(marker.split(":", maxsplit=1)[0] for marker in pytest_options()["markers"])
    assert names == ["last", "perf"]
