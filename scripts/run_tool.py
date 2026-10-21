"""One home for the CI scripts' calls to git and gh (#384, #381): the tool found on the path, run
in the repository with its output kept, and any failure raised naming the call."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class ToolError(Exception):
    """A tool missing from the path, or a call of it that failed."""


def run_tool(repo: Path, tool: str, *args: str) -> bytes:
    """*tool*'s standard output for *args*, run in *repo*; a missing tool or a failure raises."""
    path = shutil.which(tool)
    if path is None:
        msg = f"{tool} is not on the path"
        raise ToolError(msg)
    # git and gh, with arguments the calling script builds.
    done = subprocess.run([path, *args], cwd=repo, capture_output=True, check=False)  # noqa: S603
    if done.returncode != 0:
        msg = f"{tool} {' '.join(args[:3])} failed: {done.stderr.decode(errors='replace').strip()}"
        raise ToolError(msg)
    return done.stdout
