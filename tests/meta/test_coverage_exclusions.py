"""Coverage may skip exactly one piece of shipped code: the one function that talks to Yahoo.

Spec §10.5 asks for 100% branch coverage. The network call cannot run on a pull request, so it is
excluded and run instead by the daily yahoo-shape workflow. Any second exclusion is a hole in
the 100%, so this guard fails on it. It reads comments on purpose: the pragma is a comment.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRAGMA = "pragma: no cover"


def pragma_lines(root: Path) -> list[str]:
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PRAGMA in line:
                found.append(f"{path.relative_to(root).as_posix()}:{number}: {line.strip()}")
    return found


def test_the_detector_sees_a_pragma(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\ny = 2  # pragma: no cover\n", encoding="utf-8")
    assert pragma_lines(tmp_path) == ["a.py:2: y = 2  # pragma: no cover"]


def test_only_the_yahoo_download_is_excluded() -> None:
    found = pragma_lines(ROOT / "packages")
    assert len(found) == 1, found
    assert found[0].startswith("steadyhand-idx/src/steadyhand_idx/yahoo.py:")
    assert "def download_history(" in found[0]


def test_the_only_other_exclusion_is_a_protocol_body() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    report = pyproject["tool"]["coverage"]["report"]
    assert report["exclude_also"] == [r"^\s*\.\.\.$"]
    assert "exclude_lines" not in report
