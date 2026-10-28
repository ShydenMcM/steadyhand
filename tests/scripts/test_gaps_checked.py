"""Every commit carries its gap check (#378): the commit-msg git hook and the CI check reading
every commit a pull request holds or a push lands, by the global rule's section.

A unit test starts no process (#286): here every git call is stood in
(``tests/scripts/stood_in_commands.py``). Real git, through the installed hook of a fresh clone
and over real commits, is in ``tests/integration/scripts/test_gaps_checked_hook.py``."""

import runpy
import stat
import sys
from pathlib import Path

import pytest
from gaps_checked import TEMPLATE, RefusedError, Verdict, cleaned, commit_msg, landed, main
from gaps_checked import section_problem as problem_of
from script_imports import imported_modules
from stood_in_commands import Commands, stand_in
from stood_in_git import FakeGit
from stood_in_git import stand_in as stand_in_git

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/gaps_checked.py"
HOOK = ROOT / ".githooks/commit-msg"
README = ROOT / "README.md"

BEFORE = "- Before: listed four ways through and planted each one red first\n"
AFTER = "- After: attacked each new branch, verdicts identical, the change fully covered\n"
SECTION = f"Gaps checked:\n{BEFORE}{AFTER}- New passes: none\n"
MESSAGE = f"feat: a change\n\n{SECTION}"
BARE = "feat: a change\n\nNo check here.\n"
DIFF_CACHED = ("git", "diff", "--cached", "--name-only", "--no-renames", "-z")
COMMENT_CHAR = ("git", "config", "--get", "core.commentChar")
COMMENT_STRING = ("git", "config", "--get", "core.commentString")
UNSET = ("git", "config")
BASE = "b" * 40
HEAD = "c" * 40
FIRST = "1" * 40
SECOND = "2" * 40
PARENT = "3" * 40
OTHER_PARENT = "4" * 40
ZERO = "0" * 40


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> dict[str, Commands]:
    return stand_in(monkeypatch)


def staged(*files: str) -> dict[tuple[str, ...], bytes]:
    return {DIFF_CACHED: b"".join(f"{name}\0".encode() for name in files)}


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(text, encoding="utf-8")
    return path


# --- The section, by the rule the global Claude hook checks -------------------------------------


@pytest.mark.parametrize(
    ("message", "problem"),
    [
        pytest.param(MESSAGE, None, id="whole"),
        pytest.param(SECTION, None, id="the section alone"),
        pytest.param(
            f"feat: x\n\nGaps checked:\n- Before: listed four ways\n  through, each planted red\n"
            f"{AFTER}- New passes: none\n",
            None,
            id="an entry continued on an indented line",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:  \n{BEFORE}{AFTER}- New passes: #12 now passes, ruled\n",
            None,
            id="spaces after the header and a real new pass",
        ),
        pytest.param(BARE, 'it has no "Gaps checked:" section', id="no header"),
        pytest.param(
            f"feat: x\n\nGaps checked: see below\n{BEFORE}{AFTER}- New passes: none\n",
            'it has no "Gaps checked:" section',
            id="text after the header",
        ),
        pytest.param(
            f"feat: x\n\n  Gaps checked:\n{BEFORE}{AFTER}- New passes: none\n",
            'it has no "Gaps checked:" section',
            id="an indented header",
        ),
        pytest.param(
            f"feat: x\n\n{BEFORE}{AFTER}Gaps checked:\n- New passes: none\n",
            'its section has no "- Before:" line',
            id="entries above the header",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n{AFTER}- New passes: none\n",
            'its section has no "- Before:" line',
            id="Before missing",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n{BEFORE}- New passes: none\n",
            'its section has no "- After:" line',
            id="After missing",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n- Before: planted it\n{AFTER}- New passes: none\n",
            "its \"- Before:\" line says too little to be a check ('planted it')",
            id="a Before under 20 characters",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n{BEFORE}- After: n/a n/a n/a n/a n/a n/a\n"
            "- New passes: none\n",
            "its \"- After:\" line says too little to be a check ('n/a n/a n/a n/a n/a n/a')",
            id="an After of filler words",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n{BEFORE}- After: 1234567890 1234567890 ab\n"
            "- New passes: none\n",
            "its \"- After:\" line says too little to be a check ('1234567890 1234567890 ab')",
            id="an After of one real word",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n- Before: ran all the tests\n{AFTER}- New passes: none\n",
            "its \"- Before:\" line says too little to be a check ('ran all the tests')",
            id="a Before of four words under 20 characters",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n{BEFORE}- After: none none none none tbd\n"
            "- New passes: none\n",
            "its \"- After:\" line says too little to be a check ('none none none none tbd')",
            id="an After of filler words only",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n{BEFORE}{AFTER}- New passes:\n",
            'its section has no "- New passes:" entry (write "none" when there is none)',
            id="New passes empty",
        ),
        pytest.param(
            f"feat: x\n\nGaps checked:\n{BEFORE}{AFTER}",
            'its section has no "- New passes:" entry (write "none" when there is none)',
            id="New passes missing",
        ),
    ],
)
def test_the_section_is_judged_by_the_global_rule(message: str, problem: str | None) -> None:
    assert problem_of(message) == problem


def test_the_template_shows_every_entry_of_the_section() -> None:
    assert TEMPLATE == (
        "Gaps checked:\n"
        "- Before: <every way the change could let through what is refused today, each planted"
        " as a\n"
        "  failing test first>\n"
        "- After: <the attack on the diff, the old-vs-new verdicts, coverage of the changed code>\n"
        "- New passes: <each verdict the change turns into a pass and the ruling that allows it,"
        " or none>"
    )


# --- What git keeps of an edited message ---------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "kept"),
    [
        pytest.param("feat: x\n# a comment\nbody\n", "feat: x\nbody\n", id="a comment line"),
        pytest.param(
            "feat: x\n\nbody\n# ------------------------ >8 ------------------------\n"
            "Gaps checked:\n",
            "feat: x\n\nbody\n",
            id="everything from the scissors line",
        ),
        pytest.param("feat: x\n  # indented\n", "feat: x\n  # indented\n", id="an indented hash"),
        pytest.param(
            "feat: x\nno newline", "feat: x\nno newline", id="a last line without newline"
        ),
    ],
)
def test_comment_lines_and_the_scissors_are_dropped_as_git_drops_them(
    message: str, kept: str
) -> None:
    assert cleaned(message) == kept


# --- The commit-msg hook -------------------------------------------------------------------------


def test_a_commit_with_its_section_passes(tmp_path: Path, commands: dict[str, Commands]) -> None:
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    assert commit_msg(tmp_path, write(tmp_path, MESSAGE)) is None
    assert commands["c"].calls == [
        ["/stood-in/git", "config", "--get", "core.commentChar"],
        ["/stood-in/git", "config", "--get", "core.commentString"],
        ["/stood-in/git", *DIFF_CACHED[1:]],
    ]
    assert commands["c"].folders == [tmp_path, tmp_path, tmp_path]


@pytest.mark.parametrize(
    "files",
    [
        pytest.param(("scripts/a.py",), id="code"),
        pytest.param(("README.md", "scripts/a.py"), id="markdown beside code"),
        pytest.param(("notes.md.py",), id="a name holding .md"),
        pytest.param(("README.MD",), id="an upper-case suffix"),
        pytest.param((), id="nothing staged"),
    ],
)
def test_a_commit_without_its_section_is_refused_unless_it_holds_only_markdown(
    tmp_path: Path, commands: dict[str, Commands], files: tuple[str, ...]
) -> None:
    commands["c"] = Commands(answers=staged(*files), failing=UNSET)
    assert commit_msg(tmp_path, write(tmp_path, BARE)) == 'it has no "Gaps checked:" section'


@pytest.mark.parametrize(
    "files",
    [
        pytest.param(("README.md",), id="one file"),
        pytest.param(("docs/a.md", "docs/b c.md"), id="two, one with a space"),
    ],
)
def test_a_commit_of_only_markdown_needs_no_section(
    tmp_path: Path, commands: dict[str, Commands], files: tuple[str, ...]
) -> None:
    commands["c"] = Commands(answers=staged(*files), failing=UNSET)
    assert commit_msg(tmp_path, write(tmp_path, BARE)) is None


def test_a_section_only_in_comment_lines_is_refused(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commented = "feat: x\n\n" + "".join(f"# {line}\n" for line in SECTION.splitlines())
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    assert commit_msg(tmp_path, write(tmp_path, commented)) == 'it has no "Gaps checked:" section'


def test_a_section_below_the_scissors_is_refused(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    scissored = f"feat: x\n# ------------------------ >8 ------------------------\n{SECTION}"
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    assert commit_msg(tmp_path, write(tmp_path, scissored)) == 'it has no "Gaps checked:" section'


def test_a_hash_comment_character_set_by_hand_is_read_as_the_default(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commands["c"] = Commands(
        answers={COMMENT_CHAR: b"#\n", **staged("scripts/a.py")}, failing=COMMENT_STRING
    )
    assert commit_msg(tmp_path, write(tmp_path, MESSAGE)) is None


@pytest.mark.parametrize(
    ("answers", "failing", "named"),
    [
        pytest.param({COMMENT_CHAR: b";\n"}, COMMENT_STRING, "core.commentChar is ';'", id="char"),
        pytest.param(
            {COMMENT_CHAR: b"auto\n"}, COMMENT_STRING, "core.commentChar is 'auto'", id="auto"
        ),
        pytest.param(
            {COMMENT_STRING: b"//\n"}, COMMENT_CHAR, "core.commentString is '//'", id="string"
        ),
    ],
)
def test_another_comment_character_is_refused_by_name(
    tmp_path: Path,
    commands: dict[str, Commands],
    answers: dict[tuple[str, ...], bytes],
    failing: tuple[str, ...],
    named: str,
) -> None:
    """Git would drop lines starting with it, which this hook would still read as the message."""
    commands["c"] = Commands(answers={**answers, **staged("scripts/a.py")}, failing=failing)
    with pytest.raises(RefusedError) as refused:
        commit_msg(tmp_path, write(tmp_path, MESSAGE))
    assert str(refused.value) == (
        f"{named}: git drops lines starting with it, which this hook cannot tell from the"
        " message, so set it back to '#'"
    )


def test_a_message_file_that_cannot_be_read_is_refused(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    with pytest.raises(RefusedError) as refused:
        commit_msg(tmp_path, tmp_path / "missing")
    assert str(refused.value).startswith("cannot read the message file ")


def test_a_git_failure_is_refused_with_what_git_said(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake: FakeGit = stand_in_git(monkeypatch)
    fake.returncode, fake.stderr = 128, b"fatal: not a git repository\n"
    with pytest.raises(RefusedError) as refused:
        commit_msg(tmp_path, write(tmp_path, MESSAGE))
    assert str(refused.value) == "git config exited 128: fatal: not a git repository"


def test_git_off_the_path_is_refused_and_starts_nothing(
    tmp_path: Path, commands: dict[str, Commands], monkeypatch: pytest.MonkeyPatch
) -> None:
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(RefusedError) as refused:
        commit_msg(tmp_path, write(tmp_path, MESSAGE))
    assert str(refused.value) == "git is not on the path"
    assert commands["c"].calls == []


# --- Every commit a pull request holds or a push lands -------------------------------------------


DIFF_TREE = ("git", "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "-z")


def history(
    *commits: tuple[str, str, tuple[str, ...]],
    line: tuple[str, ...] = (),
    parents: tuple[str, ...] = (PARENT,),
) -> dict[tuple[str, ...], bytes]:
    """Git's answers for *commits*, each ``(name, message, files)`` with *parents*, oldest first,
    listed by ``rev-list`` with *line*'s options; the files are against the first parent."""
    answers = {
        ("git", "rev-list", "--reverse", *line, f"{BASE}..{HEAD}"): "".join(
            f"{name}\n" for name, _, _ in commits
        ).encode()
    }
    against = (parents[0],) if parents else ("--root",)
    for name, message, files in commits:
        answers["git", "log", "-1", "--format=%B", name] = message.encode()
        answers["git", "log", "-1", "--format=%P", name] = f"{' '.join(parents)}\n".encode()
        answers[(*DIFF_TREE, *against, name)] = b"".join(f"{f}\0".encode() for f in files)
    return answers


def test_every_commit_in_the_range_is_judged_oldest_first(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commands["c"] = Commands(
        answers=history((FIRST, BARE, ("scripts/a.py",)), (SECOND, MESSAGE, ("scripts/b.py",)))
    )
    assert landed(tmp_path, BASE, HEAD, first_parent=False) == [
        Verdict(FIRST, "feat: a change", 'it has no "Gaps checked:" section'),
        Verdict(SECOND, "feat: a change", None),
    ]
    assert commands["c"].calls == [
        ["/stood-in/git", "rev-list", "--reverse", f"{BASE}..{HEAD}"],
        ["/stood-in/git", "log", "-1", "--format=%B", FIRST],
        ["/stood-in/git", "log", "-1", "--format=%P", FIRST],
        ["/stood-in/git", *DIFF_TREE[1:], PARENT, FIRST],
        ["/stood-in/git", "log", "-1", "--format=%B", SECOND],
        ["/stood-in/git", "log", "-1", "--format=%P", SECOND],
        ["/stood-in/git", *DIFF_TREE[1:], PARENT, SECOND],
    ]


def test_a_merge_is_judged_by_its_files_against_its_first_parent_alone(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    """diff-tree ignores --first-parent, so the two trees are named: the merge's own change."""
    commands["c"] = Commands(
        answers=history((FIRST, BARE, ("README.md",)), parents=(PARENT, OTHER_PARENT))
    )
    assert landed(tmp_path, BASE, HEAD, first_parent=False) == [
        Verdict(FIRST, "feat: a change", None)
    ]
    assert commands["c"].calls[-1] == ["/stood-in/git", *DIFF_TREE[1:], PARENT, FIRST]


def test_a_root_commit_is_judged_by_every_file_it_holds(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    commands["c"] = Commands(answers=history((FIRST, BARE, ("scripts/a.py",)), parents=()))
    assert landed(tmp_path, BASE, HEAD, first_parent=False) == [
        Verdict(FIRST, "feat: a change", 'it has no "Gaps checked:" section')
    ]
    assert commands["c"].calls[-1] == ["/stood-in/git", *DIFF_TREE[1:], "--root", FIRST]


@pytest.mark.parametrize(
    ("files", "problem"),
    [
        pytest.param(("README.md",), None, id="only markdown"),
        pytest.param(
            ("README.md", "scripts/a.py"), 'it has no "Gaps checked:" section', id="code too"
        ),
        pytest.param((), 'it has no "Gaps checked:" section', id="an empty commit"),
    ],
)
def test_a_landed_commit_of_only_markdown_needs_no_section(
    tmp_path: Path, commands: dict[str, Commands], files: tuple[str, ...], problem: str | None
) -> None:
    commands["c"] = Commands(answers=history((FIRST, BARE, files)))
    assert landed(tmp_path, BASE, HEAD, first_parent=False) == [
        Verdict(FIRST, "feat: a change", problem)
    ]


def test_a_landed_message_is_judged_as_stored_with_its_hash_lines(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    """Git stored the message already cleaned, so a line starting with # is part of it."""
    hashed = "feat: x\n\n#12 is fixed here\n\n" + SECTION
    commands["c"] = Commands(answers=history((FIRST, hashed, ("scripts/a.py",))))
    assert landed(tmp_path, BASE, HEAD, first_parent=False) == [Verdict(FIRST, "feat: x", None)]


def test_a_push_judges_only_the_first_parent_line_it_landed(
    tmp_path: Path, commands: dict[str, Commands]
) -> None:
    """On ``main`` that is the release merge commit; ``develop``'s commits were judged as they
    landed there (Shyden, 2026-10-28, "First-parent on a push")."""
    commands["c"] = Commands(
        answers=history((FIRST, MESSAGE, ("scripts/a.py",)), line=("--first-parent",))
    )
    assert landed(tmp_path, BASE, HEAD, first_parent=True) == [
        Verdict(FIRST, "feat: a change", None)
    ]
    assert commands["c"].calls[0] == [
        "/stood-in/git",
        "rev-list",
        "--reverse",
        "--first-parent",
        f"{BASE}..{HEAD}",
    ]


@pytest.mark.parametrize(
    ("base", "head", "said"),
    [
        pytest.param(ZERO, HEAD, f"the range starts at {ZERO!r}", id="an all-zero base"),
        pytest.param("main", HEAD, "the range starts at 'main'", id="a branch name"),
        pytest.param(BASE, "c" * 39, f"the range ends at {'c' * 39!r}", id="a short head"),
        pytest.param(BASE, "C" * 40, f"the range ends at {'C' * 40!r}", id="upper case"),
    ],
)
def test_a_range_not_named_by_two_full_commits_is_refused(
    tmp_path: Path, commands: dict[str, Commands], base: str, head: str, said: str
) -> None:
    commands["c"] = Commands(answers={})
    with pytest.raises(RefusedError) as refused:
        landed(tmp_path, base, head, first_parent=False)
    assert said in str(refused.value)
    assert commands["c"].calls == []


# --- Run as a program ----------------------------------------------------------------------------


def test_the_hook_passes_a_message_with_its_section(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    assert main(tmp_path, ["commit-msg", str(write(tmp_path, MESSAGE))]) == 0
    assert capsys.readouterr() == ("", "")


def test_the_hook_refuses_with_the_reason_and_the_template(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    assert main(tmp_path, ["commit-msg", str(write(tmp_path, BARE))]) == 1
    assert capsys.readouterr().err == (
        'commit-msg: refused: the message: it has no "Gaps checked:" section.\n'
        "Every commit message carries this section (#378), unless the commit holds only .md"
        f" files:\n\n{TEMPLATE}\n"
    )


def test_the_hook_reports_a_refusal_it_cannot_judge(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    assert main(tmp_path, ["commit-msg", str(tmp_path / "missing")]) == 1
    assert capsys.readouterr().err.startswith("commit-msg: refused: cannot read the message file ")


def test_a_range_of_whole_sections_passes_with_its_count(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(
        answers=history((FIRST, MESSAGE, ("scripts/a.py",)), (SECOND, BARE, ("README.md",)))
    )
    assert main(tmp_path, ["range", BASE, HEAD]) == 0
    assert capsys.readouterr() == (
        "gaps-checked: 2 commits judged, 0 without a whole section\n",
        "",
    )


def test_a_range_names_every_commit_without_its_section(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(
        answers=history(
            (FIRST, BARE, ("scripts/a.py",)),
            (SECOND, "fix: y\n\nGaps checked:\n- Before: x\n", ("scripts/b.py",)),
        )
    )
    assert main(tmp_path, ["range", BASE, HEAD]) == 1
    out, err = capsys.readouterr()
    assert out == "gaps-checked: 2 commits judged, 2 without a whole section\n"
    assert err == (
        f'gaps-checked: {FIRST} feat: a change: it has no "Gaps checked:" section\n'
        f'gaps-checked: {SECOND} fix: y: its "- Before:" line says too little to be a check'
        " ('x')\n"
        f"Every commit carries this section (#378), unless it holds only .md files:\n\n{TEMPLATE}\n"
    )


def test_a_push_names_a_landed_commit_without_its_section(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(
        answers=history((FIRST, BARE, ("scripts/a.py",)), line=("--first-parent",))
    )
    assert main(tmp_path, ["landed", BASE, HEAD]) == 1
    out, err = capsys.readouterr()
    assert out == "gaps-checked: 1 commits judged, 1 without a whole section\n"
    assert err.startswith(f'gaps-checked: {FIRST} feat: a change: it has no "Gaps checked:"')


def test_a_range_of_no_commits_is_refused(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(answers=history())
    assert main(tmp_path, ["range", BASE, HEAD]) == 1
    assert capsys.readouterr() == (
        "",
        f"gaps-checked: refused: {BASE}..{HEAD} holds no commit, so nothing was judged\n",
    )


def test_a_range_git_cannot_read_is_refused(
    tmp_path: Path, commands: dict[str, Commands], capsys: pytest.CaptureFixture[str]
) -> None:
    commands["c"] = Commands(answers={}, failing=("git", "rev-list"))
    assert main(tmp_path, ["range", BASE, HEAD]) == 1
    assert capsys.readouterr().err == "gaps-checked: refused: git rev-list exited 1: HTTP 404\n"


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param([], id="nothing"),
        pytest.param(["commit-msg"], id="no message file"),
        pytest.param(["commit-msg", "a", "b"], id="two message files"),
        pytest.param(["range", BASE], id="no head"),
        pytest.param(["landed", BASE, HEAD, HEAD], id="a third commit"),
        pytest.param(["other", BASE, HEAD], id="another mode"),
    ],
)
def test_a_usage_error_exits_2(
    tmp_path: Path,
    commands: dict[str, Commands],
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    commands["c"] = Commands(answers={})
    assert main(tmp_path, argv) == 2
    assert capsys.readouterr().err == (
        "usage: gaps_checked.py commit-msg <message file>"
        " | range <base commit> <head commit> | landed <base commit> <head commit>\n"
    )
    assert commands["c"].calls == []


def test_it_imports_from_the_standard_library_alone() -> None:
    """The hook and CI run it outside the project, before anything is synced."""
    imported = imported_modules(SCRIPT)
    assert "subprocess" in imported
    assert sorted(imported - sys.stdlib_module_names) == []


def test_run_as_a_script_it_judges_from_the_repository_root(
    tmp_path: Path,
    commands: dict[str, Commands],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands["c"] = Commands(answers=staged("scripts/a.py"), failing=UNSET)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "commit-msg", str(write(tmp_path, BARE))])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exited.value.code == 1
    assert commands["c"].folders == [ROOT, ROOT, ROOT]
    assert capsys.readouterr().err.startswith("commit-msg: refused: the message: it has no")


def test_the_hook_is_tracked_executable_and_runs_the_script_outside_the_project() -> None:
    assert HOOK.read_text(encoding="utf-8") == (
        "#!/bin/sh\n"
        "# The gap check every commit message carries (#378). Installed by\n"
        "# `git config core.hooksPath .githooks` (README.md, Setting up a clone).\n"
        'exec uv run --no-project scripts/gaps_checked.py commit-msg "$@"\n'
    )
    assert HOOK.stat().st_mode & stat.S_IXUSR


def test_the_readme_names_the_commit_msg_hook_and_its_ci_check() -> None:
    text = README.read_text(encoding="utf-8")
    section = text.split("\n## Setting up a clone\n", 1)[1].split("\n## ", 1)[0]
    assert "Its `commit-msg` refuses a message without its `Gaps checked:` section" in section
    assert "`gaps-checked` job" in section
