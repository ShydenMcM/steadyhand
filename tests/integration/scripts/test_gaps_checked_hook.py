"""The gap check through git, in a fresh clone of this commit (#378): the installed commit-msg
hook refuses a message without its section in every form git takes one (``-m``, ``-F``, a
heredoc on ``-F -``, an amend, a merge, a partial commit, an edited message), passes a commit of
only ``.md`` files, and the CI check (``gaps_checked.py range``) refuses, by name, every commit
the hook did not see: one made with ``--no-verify``, the amend the hook cannot tell (Shyden,
2026-10-28, "Name it, CI is the gate"), and a merge landing code. The logic, with git stood in,
is unit-tested in ``tests/scripts/test_gaps_checked.py``."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from ci_scope import FAST_PATH_DIRS, FAST_PATH_FILES

ROOT = Path(__file__).resolve().parents[3]
GIT = shutil.which("git")
UV = shutil.which("uv")
FAST_PATH_EXCLUDED = [
    *(f":(exclude){name}" for name in sorted(FAST_PATH_FILES)),
    *(f":(exclude){folder}" for folder in FAST_PATH_DIRS),
]
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")
SECTION = (
    "Gaps checked:\n"
    "- Before: listed four ways through and planted each one red first\n"
    "- After: attacked each new branch, verdicts identical, the change fully covered\n"
    "- New passes: none\n"
)
CHECKED = f"feat: checked\n\n{SECTION}"
BARE = "feat: bare\n\nNo check here.\n"
REFUSED = 'commit-msg: refused: the message: it has no "Gaps checked:" section.\n'


@dataclass(frozen=True)
class Clone:
    path: Path
    base: str


@dataclass(frozen=True)
class Ran:
    returncode: int
    output: str


@dataclass(frozen=True)
class Judged:
    """The CI check's run: its exit status, and each stream apart (the count line is printed on
    stdout, the commits it refuses on stderr)."""

    returncode: int
    out: str
    err: str


def environment() -> dict[str, str]:
    """This run's environment without what only the test process has: its virtual environment
    and coverage's settings, which a developer's commit never carries."""
    return {
        name: value
        for name, value in os.environ.items()
        if name != "VIRTUAL_ENV" and not name.startswith(("COVERAGE_", "COV_CORE_"))
    }


def run(repo: Path, *args: str, stdin: str | None = None) -> Ran:
    assert GIT is not None, "git is not on the path"
    done = subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, *IDENTITY, *args],
        cwd=repo,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=environment(),
    )
    return Ran(done.returncode, done.stdout + done.stderr)


def git(repo: Path, *args: str) -> str:
    ran = run(repo, *args)
    assert ran.returncode == 0, ran.output
    return ran.output


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def judge(repo: Path, mode: str, base: str, tip: str) -> Judged:
    """The CI check, run as CI's gaps-checked job runs it: ``range`` on a pull request,
    ``landed`` on a push."""
    assert UV is not None, "uv is not on the path"
    done = subprocess.run(  # noqa: S603 - uv, with arguments written in the tests
        [UV, "run", "--no-project", "scripts/gaps_checked.py", mode, base, tip],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=environment(),
    )
    return Judged(done.returncode, done.stdout, done.stderr)


@pytest.fixture(scope="module")
def clone(tmp_path_factory: pytest.TempPathFactory) -> Clone:
    path = tmp_path_factory.mktemp("gaps-checked") / "clone"
    git(ROOT, "clone", "--quiet", "--no-checkout", str(ROOT), str(path))
    git(path, "checkout", "--quiet", "--detach", head(ROOT))
    # The checkout's uncommitted changes to tracked files are committed in the clone, before the
    # hook is installed, so the hook judged is the one on disk here: a planted mutation
    # (mutations/378.toml) reaches it. The fast-path files are left out: a full run locks them
    # unreadable (lock_fast_path.py), and git cannot hash a file it cannot read.
    assert GIT is not None, "git is not on the path"
    diffed = subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "diff", "--binary", "HEAD", "--", ".", *FAST_PATH_EXCLUDED],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert diffed.returncode == 0, diffed.stderr.decode(errors="replace")
    subprocess.run(  # noqa: S603 - git, with arguments written in the tests
        [GIT, "apply", "--index", "--allow-empty"],
        cwd=path,
        input=diffed.stdout,
        capture_output=True,
        check=True,
    )
    git(path, "commit", "--quiet", "--allow-empty", "-m", "the checkout's uncommitted changes")
    git(path, "config", "core.hooksPath", ".githooks")
    return Clone(path, head(path))


@pytest.fixture
def branch(clone: Clone, request: pytest.FixtureRequest) -> Path:
    """The clone on a branch of its own for this test, at the clone's base commit, with nothing
    left in its work folder from an earlier test."""
    name = re.sub(r"[^A-Za-z0-9_-]", "-", request.node.name)[:60]
    git(clone.path, "checkout", "--quiet", "--force", "-B", name, clone.base)
    git(clone.path, "clean", "--quiet", "-fdx", "--", "work")
    return clone.path


def change(repo: Path, *names: str) -> None:
    """Change each of *names* under work/ and stage it."""
    for name in names:
        path = repo / "work" / name
        path.parent.mkdir(exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("a change\n")
        git(repo, "add", str(path))


def message_file(repo: Path, text: str) -> Path:
    path = repo.parent / "message.txt"
    path.write_text(text, encoding="utf-8")
    return path


# --- The hook, in every form a commit takes its message ------------------------------------------


def test_m_without_a_section_is_refused(branch: Path) -> None:
    before = head(branch)
    change(branch, "a.py")
    ran = run(branch, "commit", "-q", "-m", BARE)
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output
    assert head(branch) == before


def test_m_with_a_section_commits(branch: Path) -> None:
    before = head(branch)
    change(branch, "a.py")
    ran = run(branch, "commit", "-q", "-m", CHECKED)
    assert (ran.returncode, ran.output) == (0, "")
    assert git(branch, "rev-parse", "HEAD^").strip() == before


def test_a_message_file_without_a_section_is_refused(branch: Path) -> None:
    change(branch, "a.py")
    ran = run(branch, "commit", "-q", "-F", str(message_file(branch, BARE)))
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output


def test_a_message_file_with_a_section_commits(branch: Path) -> None:
    change(branch, "a.py")
    ran = run(branch, "commit", "-q", "-F", str(message_file(branch, CHECKED)))
    assert (ran.returncode, ran.output) == (0, "")


def test_a_heredoc_without_a_section_is_refused(branch: Path) -> None:
    change(branch, "a.py")
    ran = run(branch, "commit", "-q", "-F", "-", stdin=BARE)
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output


def test_a_heredoc_with_a_section_commits(branch: Path) -> None:
    change(branch, "a.py")
    ran = run(branch, "commit", "-q", "-F", "-", stdin=CHECKED)
    assert (ran.returncode, ran.output) == (0, "")


def test_an_amend_of_code_without_a_section_is_refused(branch: Path) -> None:
    change(branch, "a.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    amended = head(branch)
    change(branch, "a.py")
    ran = run(branch, "commit", "-q", "--amend", "-m", BARE)
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output
    assert head(branch) == amended


def test_a_merge_of_code_without_a_section_is_refused(branch: Path) -> None:
    git(branch, "checkout", "-q", "-b", f"{branch_name(branch)}-side")
    change(branch, "a.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    side = head(branch)
    git(branch, "checkout", "-q", "-")
    change(branch, "b.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    mine = head(branch)
    ran = run(branch, "merge", "-q", "--no-ff", "-m", BARE, side)
    git(branch, "merge", "--abort")
    assert (ran.returncode, REFUSED in ran.output) == (1, True), ran.output
    assert head(branch) == mine


def test_a_merge_with_a_section_commits(branch: Path) -> None:
    git(branch, "checkout", "-q", "-b", f"{branch_name(branch)}-side")
    change(branch, "a.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    side = head(branch)
    git(branch, "checkout", "-q", "-")
    change(branch, "b.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    ran = run(branch, "merge", "-q", "--no-ff", "-F", str(message_file(branch, CHECKED)), side)
    assert ran.returncode == 0, ran.output
    assert git(branch, "rev-parse", "HEAD^2").strip() == side


def test_only_markdown_commits_without_a_section(branch: Path) -> None:
    change(branch, "notes.md", "more.md")
    ran = run(branch, "commit", "-q", "-m", BARE)
    assert (ran.returncode, ran.output) == (0, "")


def test_markdown_beside_code_is_refused(branch: Path) -> None:
    change(branch, "notes.md", "a.py")
    ran = run(branch, "commit", "-q", "-m", BARE)
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output


def test_code_renamed_to_a_markdown_name_is_refused(branch: Path) -> None:
    change(branch, "a.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    git(branch, "mv", "work/a.py", "work/a.md")
    ran = run(branch, "commit", "-q", "-m", BARE)
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output


def test_a_partial_commit_of_only_markdown_needs_no_section(branch: Path) -> None:
    """``git commit -- <paths>`` commits through a temporary index git names to the hook."""
    change(branch, "a.py", "notes.md")
    ran = run(branch, "commit", "-q", "-m", BARE, "--", "work/notes.md")
    assert (ran.returncode, ran.output) == (0, "")
    assert git(branch, "show", "--name-only", "--format=", "HEAD") == "work/notes.md\n"


def test_a_partial_commit_of_code_is_refused(branch: Path) -> None:
    change(branch, "a.py", "notes.md")
    ran = run(branch, "commit", "-q", "-m", BARE, "--", "work/a.py")
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output


def test_a_section_below_the_scissors_line_git_cuts_is_refused(branch: Path) -> None:
    """``--cleanup=scissors`` keeps only what is above the line, so the section below it never
    lands, though the hook is handed the whole file."""
    change(branch, "a.py")
    cut = f"feat: x\n\n# ------------------------ >8 ------------------------\n{SECTION}"
    ran = run(branch, "commit", "-q", "--cleanup=scissors", "-F", str(message_file(branch, cut)))
    assert (ran.returncode, ran.output.startswith(REFUSED)) == (1, True), ran.output


def test_another_comment_character_is_refused(branch: Path) -> None:
    change(branch, "a.py")
    ran = run(branch, "-c", "core.commentChar=;", "commit", "-q", "-m", CHECKED)
    assert ran.returncode == 1, ran.output
    assert ran.output.startswith("commit-msg: refused: core.commentChar is ';'"), ran.output


# --- The CI check: every commit, the ones the hook did not see included --------------------------


def test_a_no_verify_commit_passes_git_and_is_refused_by_the_check_by_name(branch: Path) -> None:
    base = head(branch)
    change(branch, "a.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    change(branch, "b.py")
    git(branch, "commit", "-q", "--no-verify", "-m", BARE)
    skipped = head(branch)
    ran = judge(branch, "range", base, skipped)
    assert (ran.returncode, ran.out) == (
        1,
        "gaps-checked: 2 commits judged, 1 without a whole section\n",
    ), ran.err
    assert ran.err.startswith(
        f'gaps-checked: {skipped} feat: bare: it has no "Gaps checked:" section\n'
    ), ran.err


def test_the_amend_the_hook_cannot_tell_is_refused_by_the_check(branch: Path) -> None:
    """The named limit (AC7): git tells the hook nothing of --amend, so an amend adding only
    markdown passes the hook; the check judges the amended commit against its parent."""
    base = head(branch)
    change(branch, "a.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    change(branch, "notes.md")
    ran = run(branch, "commit", "-q", "--amend", "-m", BARE)
    assert (ran.returncode, ran.output) == (0, "")
    amended = head(branch)
    judged = judge(branch, "range", base, amended)
    assert (judged.returncode, judged.out) == (
        1,
        "gaps-checked: 1 commits judged, 1 without a whole section\n",
    ), judged.err
    assert judged.err.startswith(
        f'gaps-checked: {amended} feat: bare: it has no "Gaps checked:" section\n'
    ), judged.err


def test_a_landed_merge_of_code_without_a_section_is_refused_by_the_check(branch: Path) -> None:
    base = head(branch)
    git(branch, "checkout", "-q", "-b", f"{branch_name(branch)}-side")
    change(branch, "a.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    side = head(branch)
    git(branch, "checkout", "-q", "-")
    git(branch, "merge", "-q", "--no-ff", "--no-verify", "-m", BARE, side)
    merged = head(branch)
    ran = judge(branch, "landed", base, merged)
    assert (ran.returncode, ran.out) == (
        1,
        "gaps-checked: 1 commits judged, 1 without a whole section\n",
    ), ran.err
    assert ran.err.startswith(
        f'gaps-checked: {merged} feat: bare: it has no "Gaps checked:" section\n'
    ), ran.err


def test_a_landed_docs_only_merge_and_commit_pass_the_check(branch: Path) -> None:
    base = head(branch)
    git(branch, "checkout", "-q", "-b", f"{branch_name(branch)}-side")
    change(branch, "notes.md")
    git(branch, "commit", "-q", "-m", BARE)
    side = head(branch)
    git(branch, "checkout", "-q", "-")
    # Code on the branch since the side split: against its second parent the merge holds it.
    change(branch, "b.py")
    git(branch, "commit", "-q", "-m", CHECKED)
    git(branch, "merge", "-q", "--no-ff", "-m", BARE, side)
    ran = judge(branch, "range", base, head(branch))
    assert (ran.returncode, ran.out, ran.err) == (
        0,
        "gaps-checked: 3 commits judged, 0 without a whole section\n",
        "",
    )


def test_a_push_judges_the_merge_it_landed_and_not_the_branch_behind_it(branch: Path) -> None:
    """On main, the release merge carries the section; develop's commits behind it were judged
    as they landed on develop (Shyden, 2026-10-28, "First-parent on a push")."""
    base = head(branch)
    git(branch, "checkout", "-q", "-b", f"{branch_name(branch)}-side")
    change(branch, "a.py")
    git(branch, "commit", "-q", "--no-verify", "-m", BARE)
    side = head(branch)
    git(branch, "checkout", "-q", "-")
    git(branch, "merge", "-q", "--no-ff", "-F", str(message_file(branch, CHECKED)), side)
    landed = judge(branch, "landed", base, head(branch))
    every = judge(branch, "range", base, head(branch))
    assert (landed.returncode, landed.out, landed.err) == (
        0,
        "gaps-checked: 1 commits judged, 0 without a whole section\n",
        "",
    )
    assert (every.returncode, every.out) == (
        1,
        "gaps-checked: 2 commits judged, 1 without a whole section\n",
    ), every.err
    assert every.err.startswith(
        f'gaps-checked: {side} feat: bare: it has no "Gaps checked:" section\n'
    ), every.err


def branch_name(repo: Path) -> str:
    return git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
