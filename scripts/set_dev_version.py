"""Give both packages a unique development version before a TestPyPI upload.

Usage: python scripts/set_dev_version.py <run-number>

``0.1.0`` becomes ``0.1.0.dev<run-number>`` in both pyproject files, and steadyhand-idx is
pinned to exactly that engine version, so a dev install never mixes two builds. Nothing is
written unless every rewrite applies.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "packages/steadyhand/pyproject.toml"
IDX = ROOT / "packages/steadyhand-idx/pyproject.toml"
VERSION_LINE = re.compile(r'^version = "(?P<base>\d+\.\d+\.\d+)"$', re.MULTILINE)
ENGINE_DEPENDENCY = re.compile(r'^    "steadyhand",$', re.MULTILINE)
USAGE = "usage: set_dev_version.py <run-number>"


class VersionError(RuntimeError):
    """A pyproject file is not in the shape this script rewrites."""


def _replace_once(pattern: re.Pattern[str], text: str, replacement: str, path: Path) -> str:
    rewritten, count = pattern.subn(replacement, text)
    if count != 1:
        msg = f"{path.name}: expected exactly one match for {pattern.pattern!r}, found {count}"
        raise VersionError(msg)
    return rewritten


def _base_version(text: str, path: Path) -> str:
    matches = VERSION_LINE.findall(text)
    if len(matches) != 1:
        msg = (
            f"{path.name}: expected exactly one match for {VERSION_LINE.pattern!r}, "
            f"found {len(matches)}"
        )
        raise VersionError(msg)
    return str(matches[0])


def set_dev_version(run_number: int, engine: Path | None = None, idx: Path | None = None) -> str:
    engine = engine or ENGINE
    idx = idx or IDX
    if run_number < 1:
        msg = f"run number must be positive, got {run_number}"
        raise VersionError(msg)
    engine_text = engine.read_text(encoding="utf-8")
    idx_text = idx.read_text(encoding="utf-8")
    base = _base_version(engine_text, engine)
    idx_base = _base_version(idx_text, idx)
    if idx_base != base:
        msg = f"steadyhand-idx is at {idx_base} but the engine is at {base}"
        raise VersionError(msg)
    version = f"{base}.dev{run_number}"
    new_engine = _replace_once(VERSION_LINE, engine_text, f'version = "{version}"', engine)
    new_idx = _replace_once(VERSION_LINE, idx_text, f'version = "{version}"', idx)
    new_idx = _replace_once(ENGINE_DEPENDENCY, new_idx, f'    "steadyhand=={version}",', idx)
    for text in (new_engine, new_idx):
        tomllib.loads(text)  # never write a file that no longer parses
    engine.write_text(new_engine, encoding="utf-8")
    idx.write_text(new_idx, encoding="utf-8")
    return version


def main(argv: list[str]) -> int:
    # isdigit() alone accepts non-ASCII digits: int() rejects some and silently reads others.
    usable = len(argv) == 2 and argv[1].isascii() and argv[1].isdigit()  # noqa: PLR2004 - program name plus one argument
    if not usable:
        print(USAGE, file=sys.stderr)
        return 2
    print(set_dev_version(int(argv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
