"""The pre-push checks (#377): format, lint and types for the Python and the extension, and no
test suite; a check that fails stops the push, named, with what it printed.

A unit test starts no process (#286): here every command is stood in
(``tests/scripts/stood_in_commands.py``). The real tools refusing a planted defect, through the
installed hook of a fresh clone, are in ``tests/integration/scripts/test_pre_push_hook.py``."""

import io
import runpy
import stat
import sys
from pathlib import Path

import pytest
from script_imports import imported_modules
from stood_in_commands import Commands, stand_in

import pre_push
from pre_push import CHECKS, Check, Outcome, main, report, run

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/pre_push.py"
HOOK = ROOT / ".githooks/pre-push"
README = ROOT / "README.md"

EVERY_COMMAND = {
    ("uv", "run", "--locked", "ruff", "check"): b"",
    ("uv", "run", "--locked", "ruff", "format", "--check"): b"",
    ("uv", "run", "--locked", "mypy"): b"",
    ("npm", "run", "lint"): b"",
    ("npm", "run", "format:check"): b"",
    ("npm", "run", "typecheck"): b"",
}
HEAD = "a" * 40
OTHER = "b" * 40
ZERO = "0" * 40
PUSHING_HEAD = f"refs/heads/377 {HEAD} refs/heads/377 {ZERO}\n"
CLEAN = {("git", "status"): b"", ("git", "rev-parse"): f"{HEAD}\n".encode(), **EVERY_COMMAND}


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> dict[str, Commands]:
    return stand_in(monkeypatch)


def test_the_checks_are_format_lint_and_types_for_both_halves_and_no_test_suite() -> None:
    assert [(c.name, c.folder, c.command) for c in CHECKS] == [
        ("ruff check", ".", ("uv", "run", "--locked", "ruff", "check")),
        ("ruff format", ".", ("uv", "run", "--locked", "ruff", "format", "--check")),
        ("mypy", ".", ("uv", "run", "--locked", "mypy")),
        ("extension lint", "extension", ("npm", "run", "lint")),
        ("extension format", "extension", ("npm", "run", "format:check")),
        ("extension typecheck", "extension", ("npm", "run", "typecheck")),
    ]


def test_a_check_runs_its_tool_from_the_path_in_its_folder_and_keeps_both_streams(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commands["c"] = Commands(answers={("npm", "run", "lint"): b"out \xff\n"})
    check = Check("extension lint", "extension", ("npm", "run", "lint"))
    assert run(tmp_path, check) == Outcome(check, 0, "out �\n")
    assert commands["c"].calls == [["/stood-in/npm", "run", "lint"]]
    assert commands["c"].folders == [tmp_path / "extension"]


def test_a_failing_check_keeps_its_exit_code_and_what_it_printed(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commands["c"] = Commands(answers={}, failing=("uv", "run", "--locked", "mypy"))
    check = Check("mypy", ".", ("uv", "run", "--locked", "mypy"))
    assert run(tmp_path, check) == Outcome(check, 1, "HTTP 404")
    assert commands["c"].folders == [tmp_path / "."]


def test_a_tool_not_on_the_path_fails_its_check_named_and_starts_nothing(
    tmp_path: Path, commands: dict[str, Commands], monkeypatch: pytest.MonkeyPatch
) -> None:
    commands["c"] = Commands(answers={})
    monkeypatch.setattr("shutil.which", lambda _name: None)
    check = Check("mypy", ".", ("uv", "run", "--locked", "mypy"))
    assert run(tmp_path, check) == Outcome(check, 127, "uv is not on the path\n")
    assert commands["c"].calls == []


def test_a_failure_is_reported_by_name_command_folder_and_output() -> None:
    check = Check("extension format", "extension", ("npm", "run", "format:check"))
    assert report(Outcome(check, 2, "[warn] a.ts\n")) == (
        "pre-push: extension format failed (exit 2): npm run format:check, in extension/\n"
        "[warn] a.ts\n"
    )


def test_a_failure_report_ends_its_output_on_a_new_line() -> None:
    check = Check("mypy", ".", ("uv", "run", "--locked", "mypy"))
    assert report(Outcome(check, 1, "no newline")) == (
        "pre-push: mypy failed (exit 1): uv run --locked mypy, in ./\nno newline\n"
    )


def test_a_clean_tree_runs_every_check_in_order_and_allows_the_push(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    assert main(tmp_path, PUSHING_HEAD) == 0
    assert commands["c"].calls == [
        ["/stood-in/git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        ["/stood-in/git", "rev-parse", "HEAD"],
        *(["/stood-in/" + c.command[0], *c.command[1:]] for c in CHECKS),
    ]
    assert commands["c"].folders == [tmp_path, tmp_path] + [tmp_path / c.folder for c in CHECKS]
    assert capsys.readouterr().err == "pre-push: 6 checks passed\n"


def test_a_failing_check_refuses_the_push_and_every_later_check_still_runs(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(
        answers=dict(CLEAN), failing=("uv", "run", "--locked", "ruff", "check")
    )
    assert main(tmp_path, PUSHING_HEAD) == 1
    assert [call[1:] for call in commands["c"].calls[2:]] == [list(c.command[1:]) for c in CHECKS]
    assert capsys.readouterr().err == (
        "pre-push: ruff check failed (exit 1): uv run --locked ruff check, in ./\nHTTP 404\n"
    )


def test_every_failing_check_is_reported_in_order(
    tmp_path: Path,
    commands: dict[str, Commands],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    ran: list[str] = []

    def outcome(_root: Path, check: Check) -> Outcome:
        ran.append(check.name)
        failing = check.name in {"mypy", "extension typecheck"}
        return Outcome(check, 2 if failing else 0, f"{check.name} said\n")

    monkeypatch.setattr(pre_push, "run", outcome)
    assert main(tmp_path, PUSHING_HEAD) == 1
    assert ran == [c.name for c in CHECKS]
    assert capsys.readouterr().err == (
        "pre-push: mypy failed (exit 2): uv run --locked mypy, in ./\nmypy said\n"
        "pre-push: extension typecheck failed (exit 2): npm run typecheck, in extension/\n"
        "extension typecheck said\n"
    )


@pytest.mark.parametrize(
    ("status", "first"),
    [
        pytest.param(b" M scripts/a.py\0", "scripts/a.py", id="modified"),
        pytest.param(b"?? scripts/new.py\0", "scripts/new.py", id="untracked"),
        pytest.param(b"R  scripts/a.py\0scripts/old.py\0", "scripts/a.py", id="renamed"),
        pytest.param(b" D scripts/a.py\0?? b.ts\0", "scripts/a.py", id="deleted-then-more"),
    ],
)
def test_a_tree_with_anything_uncommitted_is_refused_before_any_check(
    tmp_path: Path,
    commands: dict[str, Commands],
    capsys: pytest.CaptureFixture[str],
    status: bytes,
    first: str,
) -> None:
    commands["c"] = Commands(answers={**CLEAN, ("git", "status"): status})
    assert main(tmp_path, PUSHING_HEAD) == 1
    assert len(commands["c"].calls) == 1
    assert capsys.readouterr().err == (
        f"pre-push: refused: the tree has uncommitted changes, the first {first}: the checks "
        "read the files on disk, so commit or stash every change before pushing\n"
    )


def test_a_pushed_branch_that_is_not_the_checked_out_commit_is_refused_before_any_check(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    pushing = PUSHING_HEAD + f"refs/heads/other {OTHER} refs/heads/other {ZERO}\n"
    assert main(tmp_path, pushing) == 1
    assert len(commands["c"].calls) == 2
    assert capsys.readouterr().err == (
        f"pre-push: refused: refs/heads/other is at {OTHER}, not the checked-out commit {HEAD}: "
        "the checks read the checked-out files, so check out each branch you push\n"
    )


def test_a_deleted_branch_pushes_no_commit_and_is_passed_over(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    assert main(tmp_path, f"(delete) {ZERO} refs/heads/gone {OTHER}\n" + PUSHING_HEAD) == 0
    assert main(tmp_path, f"(delete) {'0' * 64} refs/heads/gone {OTHER}\n") == 0


@pytest.mark.parametrize(
    ("line", "ref", "commit"),
    [
        pytest.param(
            f"refs/heads/a {ZERO} refs/heads/a {OTHER}", "refs/heads/a", ZERO, id="zero-not-deleted"
        ),
        pytest.param(
            f"(delete) {OTHER} refs/heads/a {OTHER}", "(delete)", OTHER, id="delete-a-commit"
        ),
    ],
)
def test_only_a_deleted_branch_with_no_commit_is_passed_over(
    tmp_path: Path,
    commands: dict[str, Commands],
    capsys: pytest.CaptureFixture[str],
    line: str,
    ref: str,
    commit: str,
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    assert main(tmp_path, line + "\n") == 1
    assert capsys.readouterr().err == (
        f"pre-push: refused: {ref} is at {commit}, not the checked-out commit {HEAD}: "
        "the checks read the checked-out files, so check out each branch you push\n"
    )


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("refs/heads/a 1234 refs/heads/a", id="three-fields"),
        pytest.param("refs/heads/a 1234 refs/heads/a 0000 extra", id="five-fields"),
        pytest.param("", id="blank"),
    ],
)
def test_a_line_from_git_it_cannot_read_is_refused_before_any_check(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str], line: str
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    assert main(tmp_path, PUSHING_HEAD + line + "\n") == 1
    assert commands["c"].calls == []
    assert capsys.readouterr().err == (
        f"pre-push: refused: cannot read what git is pushing: {line!r}\n"
    )


@pytest.mark.parametrize(
    ("answers", "failing", "refusal"),
    [
        pytest.param({}, ("git", "status"), "git status exited 1: HTTP 404", id="status-fails"),
        pytest.param(
            {("git", "status"): b""},
            ("git", "rev-parse"),
            "git rev-parse exited 1: HTTP 404",
            id="rev-parse-fails",
        ),
        pytest.param(
            {("git", "status"): b"?\0"}, (), "cannot read git status: b'?\\x00'", id="short-entry"
        ),
        pytest.param(
            {("git", "status"): b" M a.py"},
            (),
            "cannot read git status: b' M a.py'",
            id="no-final-nul",
        ),
    ],
)
def test_a_git_answer_it_cannot_use_is_refused_before_any_check(
    tmp_path: Path,
    commands: dict[str, Commands],
    capsys: pytest.CaptureFixture[str],
    answers: dict[tuple[str, ...], bytes],
    failing: tuple[str, ...],
    refusal: str,
) -> None:
    commands["c"] = Commands(answers=answers, failing=failing)
    assert main(tmp_path, PUSHING_HEAD) == 1
    assert all(Path(call[0]).name == "git" for call in commands["c"].calls)
    assert capsys.readouterr().err == f"pre-push: refused: {refusal}\n"


def test_git_not_on_the_path_is_refused_before_any_check(
    tmp_path: Path,
    commands: dict[str, Commands],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert main(tmp_path, PUSHING_HEAD) == 1
    assert commands["c"].calls == []
    assert capsys.readouterr().err == "pre-push: refused: git is not on the path\n"


def test_it_imports_from_the_standard_library_alone() -> None:
    """The hook runs it outside the project, before anything is synced."""
    imported = imported_modules(SCRIPT)
    assert "subprocess" in imported
    assert sorted(imported - sys.stdlib_module_names) == []


def test_run_as_a_script_it_reads_what_git_pushes_from_standard_input(
    commands: dict[str, Commands],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands["c"] = Commands(answers=dict(CLEAN))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "origin", "git@example.com:o/r.git"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"refs/heads/b {OTHER} refs/heads/b {ZERO}\n"))
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 1
    assert commands["c"].folders == [ROOT, ROOT]
    assert capsys.readouterr().err.startswith(f"pre-push: refused: refs/heads/b is at {OTHER}")


def test_the_hook_is_tracked_executable_and_runs_the_script_outside_the_project() -> None:
    assert HOOK.read_text(encoding="utf-8") == (
        "#!/bin/sh\n"
        "# The pre-push checks (#377): format, lint and types, no test suite. Installed by\n"
        "# `git config core.hooksPath .githooks` (README.md, Setting up a clone).\n"
        'exec uv run --no-project scripts/pre_push.py "$@"\n'
    )
    assert HOOK.stat().st_mode & stat.S_IXUSR


def test_the_readme_documents_the_install_step_every_clone_runs() -> None:
    text = README.read_text(encoding="utf-8")
    section = text.split("\n## Setting up a clone\n", 1)[1].split("\n## ", 1)[0]
    assert "\ngit config core.hooksPath .githooks\n" in section
