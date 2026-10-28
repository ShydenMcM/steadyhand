"""The pre-push hook through git, in a fresh clone of this commit (#377): no hook until the
README's install step runs; then the real tools pass the clean commit, refuse a commit planting
one defect for each check, each named with its own plant, and the hook refuses an uncommitted
file or a branch that is not checked out before any check runs. The hook's logic, with every
command stood in, is unit-tested in ``tests/scripts/test_pre_push.py``.

The clone links this checkout's ``extension/node_modules`` (CI's integration job installs it),
and its own first ``uv run`` syncs its environment from uv's cache."""

import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from ci_scope import FAST_PATH_DIRS, FAST_PATH_FILES

ROOT = Path(__file__).resolve().parents[3]
GIT = shutil.which("git")
ZERO = "0" * 40
FAST_PATH_EXCLUDED = [
    *(f":(exclude){name}" for name in sorted(FAST_PATH_FILES)),
    *(f":(exclude){folder}" for folder in FAST_PATH_DIRS),
]
# Each check's plant: a defect only that check refuses (seen so by hand, 2026-10-28).
PLANTS = {
    "ruff check": ("scripts/planted_lint.py", "import os\n"),
    "ruff format": ("scripts/planted_format.py", "x=1\n"),
    "mypy": ("scripts/planted_type.py", 'x: int = "a"\n'),
    "extension lint": ("extension/planted_lint.ts", "debugger;\nexport {};\n"),
    "extension format": ("extension/planted_format.ts", "export const spaced  =  1;\n"),
    "extension typecheck": ("extension/planted_type.ts", 'export const typed: number = "a";\n'),
}


def git(repo: Path, *args: str) -> str:
    assert GIT is not None, "git is not on the path"
    done = subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


@dataclass(frozen=True)
class Clone:
    path: Path
    head: str
    hooks_path_before: str


@dataclass(frozen=True)
class Pushed:
    returncode: int
    output: str


def a_push_environment() -> dict[str, str]:
    """This run's environment without what only the test process has: its virtual environment
    and coverage's settings, which a developer's push never carries."""
    return {
        name: value
        for name, value in os.environ.items()
        if name != "VIRTUAL_ENV" and not name.startswith(("COVERAGE_", "COV_CORE_"))
    }


def push(clone: Clone, commit: str) -> Pushed:
    """Run the installed pre-push hook through git, as a push of *commit* to a new branch."""
    stdin = clone.path.parent / "stdin"
    stdin.write_text(f"refs/heads/x {commit} refs/heads/x {ZERO}\n", encoding="utf-8")
    assert GIT is not None, "git is not on the path"
    done = subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "hook", "run", f"--to-stdin={stdin}", "pre-push", "--", "origin", str(ROOT)],
        cwd=clone.path,
        capture_output=True,
        text=True,
        check=False,
        env=a_push_environment(),
    )
    return Pushed(done.returncode, done.stdout + done.stderr)


@pytest.fixture(scope="module")
def clone(tmp_path_factory: pytest.TempPathFactory) -> Clone:
    modules = ROOT / "extension/node_modules"
    assert modules.is_dir(), "the extension's packages are not installed: npm ci in extension/"
    path = tmp_path_factory.mktemp("pre-push") / "clone"
    git(ROOT, "clone", "--quiet", "--no-checkout", str(ROOT), str(path))
    git(path, "checkout", "--quiet", "--detach", git(ROOT, "rev-parse", "HEAD").strip())
    # The checkout's uncommitted changes to tracked files are committed in the clone, so the
    # hook judged is the one on disk here: a planted mutation (mutations/377.toml) reaches it.
    assert GIT is not None, "git is not on the path"
    # The fast-path files are left out: a full run locks them unreadable (lock_fast_path.py), and
    # git cannot hash a file it cannot read. No check reads them, so the clone needs no change.
    diffed = subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "diff", "--binary", "HEAD", "--", ".", *FAST_PATH_EXCLUDED],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert diffed.returncode == 0, diffed.stderr.decode(errors="replace")
    changes = diffed.stdout
    # Always one commit, empty when the checkout has no changes, so every run takes one path.
    subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "apply", "--index", "--allow-empty"],
        cwd=path,
        input=changes,
        capture_output=True,
        check=True,
    )
    git(path, "commit", "--quiet", "--allow-empty", "-m", "the checkout's uncommitted changes")
    head = git(path, "rev-parse", "HEAD").strip()
    (path / "extension/node_modules").symlink_to(modules)
    # A link is not a folder, so .gitignore's `node_modules/` passes it over; a real clone's is.
    with (path / ".git/info/exclude").open("a", encoding="utf-8") as exclude:
        exclude.write("extension/node_modules\n")
    hooks_path = subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [str(GIT), "config", "--get", "core.hooksPath"], cwd=path, capture_output=True, check=False
    )
    git(path, "config", "core.hooksPath", ".githooks")
    return Clone(path, head, hooks_path.stdout.decode() + f"exit {hooks_path.returncode}")


@pytest.fixture(scope="module")
def planted(clone: Clone) -> Iterator[Pushed]:
    git(clone.path, "checkout", "--quiet", "-b", "planted", clone.head)
    for relative, text in PLANTS.values():
        (clone.path / relative).write_text(text, encoding="utf-8")
    git(clone.path, "add", "-A")
    git(clone.path, "commit", "--quiet", "-m", "planted")
    yield push(clone, git(clone.path, "rev-parse", "HEAD").strip())
    git(clone.path, "checkout", "--quiet", "--detach", clone.head)


def reports(output: str) -> dict[str, str]:
    """Each failed check's report in the hook's output, by the check's name."""
    found: dict[str, str] = {}
    for part in re.split(r"(?m)^(?=pre-push: )", output):
        named = re.match(r"pre-push: (.+?) failed \(exit \d+\)", part)
        if named:
            found[named.group(1)] = part
    return found


def test_a_fresh_clone_has_no_hook_until_the_install_step_runs(clone: Clone) -> None:
    assert clone.hooks_path_before == "exit 1"
    assert git(clone.path, "config", "--get", "core.hooksPath") == ".githooks\n"


def test_the_clean_commit_passes_every_check(clone: Clone) -> None:
    git(clone.path, "checkout", "--quiet", "--detach", clone.head)
    pushed = push(clone, clone.head)
    assert (pushed.returncode, pushed.output.splitlines()[-1:]) == (
        0,
        ["pre-push: 6 checks passed"],
    ), pushed.output


def test_the_planted_commit_is_refused_with_every_check_named(planted: Pushed) -> None:
    assert planted.returncode == 1, planted.output
    assert sorted(reports(planted.output)) == sorted(PLANTS)


@pytest.mark.parametrize("name", PLANTS)
def test_each_check_is_refused_for_its_own_plant_alone(planted: Pushed, name: str) -> None:
    report = reports(planted.output)[name]
    named = {
        Path(relative).name for relative, _ in PLANTS.values() if Path(relative).name in report
    }
    assert named == {Path(PLANTS[name][0]).name}, report


def test_an_untracked_file_is_refused_before_any_check(clone: Clone) -> None:
    git(clone.path, "checkout", "--quiet", "--detach", clone.head)
    stray = clone.path / "stray.txt"
    stray.write_text("x\n", encoding="utf-8")
    try:
        pushed = push(clone, clone.head)
    finally:
        stray.unlink()
    assert (pushed.returncode, pushed.output) == (
        1,
        (
            "pre-push: refused: the tree has uncommitted changes, the first stray.txt: the "
            "checks read the files on disk, so commit or stash every change before pushing\n"
        ),
    )


def test_a_branch_that_is_not_checked_out_is_refused_before_any_check(clone: Clone) -> None:
    git(clone.path, "checkout", "--quiet", "--detach", clone.head)
    other = "b" * 40
    pushed = push(clone, other)
    assert (pushed.returncode, pushed.output) == (
        1,
        (
            f"pre-push: refused: refs/heads/x is at {other}, not the checked-out commit "
            f"{clone.head}: the checks read the checked-out files, so check out each branch "
            "you push\n"
        ),
    )
