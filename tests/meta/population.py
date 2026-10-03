"""What a guard proves it saw, for the guards that can pass by finding nothing (#178).

Shyden's rule (2026-10-02): such a guard proves what it inspected, counted at the level it
judges. ``searched`` puts that count inside the verdict, so an empty finding never stands alone.
``tracked`` lists files as git sees them, independent of the walk a guard makes, so a walk that
narrows (a glob for an rglob, a folder left out) no longer matches it.
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BlindGuardError(AssertionError):
    """A verdict over a population of none: it says nothing, so it is refused."""


def searched[T](findings: T, *, of: int, what: str) -> T:
    """*findings*, once *of* members of the population (*what*) were judged."""
    if of < 1:
        msg = f"judged no {what}: an empty finding over nothing proves nothing"
        raise BlindGuardError(msg)
    return findings


def git(*arguments: str | Path, cwd: Path = ROOT) -> str:
    """What ``git`` prints for *arguments*, run in *cwd*. No git on the path is refused by name."""
    found = shutil.which("git")
    if found is None:
        msg = "git is not on the path: a walk cannot be checked against what git lists"
        raise BlindGuardError(msg)
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
