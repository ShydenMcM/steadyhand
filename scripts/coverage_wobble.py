"""Two measured runs of one suite compared (#374).

Shyden's ruling of 2026-10-22: run-to-run wobble (for example fresh random property cases) is
measured, and a line whose coverage wobbles gets a fixed test. The properties suite draws fresh
cases each run, so its CI step measures it twice and this fails, naming each line and arm only
one run took, before either report reaches the coverage gate.

Usage: coverage_wobble.py FIRST.json SECOND.json
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _taken(data: Mapping[str, Any]) -> tuple[set[int], set[str]]:
    lines = set(data["executed_lines"])
    arms = {f"{start}>{end}" for start, end in data["executed_branches"]}
    return lines, arms


def wobble(first: Mapping[str, Any], second: Mapping[str, Any]) -> list[str]:
    """Each file, line and arm one coverage.py report ran and the other did not."""
    said: list[str] = []
    files_one, files_two = first["files"], second["files"]
    for path in sorted(set(files_one) | set(files_two)):
        if path not in files_one or path not in files_two:
            said.append(f"{path}: measured in one run only")
            continue
        lines_one, arms_one = _taken(files_one[path])
        lines_two, arms_two = _taken(files_two[path])
        said += [
            f"{path}: line {line} ran in one run only" for line in sorted(lines_one ^ lines_two)
        ]
        said += [f"{path}: arm {arm} ran in one run only" for arm in sorted(arms_one ^ arms_two)]
    return said


def main(argv: Sequence[str]) -> int:
    try:
        first, second = (json.loads(Path(path).read_text(encoding="utf-8")) for path in argv)
    except (OSError, json.JSONDecodeError) as error:
        print(f"coverage wobble: cannot read a run: {error}", file=sys.stderr)
        return 1
    found = wobble(first, second)
    for line in found:
        print(f"coverage wobble: {line}", file=sys.stderr)
    if found:
        return 1
    print("the two runs measured the same")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
