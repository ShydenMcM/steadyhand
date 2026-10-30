"""Files as git lists them, for the guards that walk the tree.

``tracked`` lists files as git sees them, independent of the walk a guard makes, so a walk that
narrows (a glob for an rglob, a folder left out) no longer matches it.
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class GitMissingError(AssertionError):
    """No git on the path, so a walk cannot be checked against what git lists."""


def git(*arguments: str | Path, cwd: Path = ROOT) -> str:
    """What ``git`` prints for *arguments*, run in *cwd*. No git on the path is refused by name."""
    found = shutil.which("git")
    if found is None:
        msg = "git is not on the path: a walk cannot be checked against what git lists"
        raise GitMissingError(msg)
    return subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [found, *arguments], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def tracked(directory: Path, suffix: str, *, root: Path = ROOT) -> list[Path]:
    """Every file under *directory* whose name ends in *suffix*, as git lists it in the
    repository at *root* (tracked, or new and not ignored), that is on disk."""
    listed = git(
        "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", directory, cwd=root
    )
    names = [name for name in listed.split("\0") if name.endswith(suffix)]
    return sorted(root / name for name in names if (root / name).is_file())
