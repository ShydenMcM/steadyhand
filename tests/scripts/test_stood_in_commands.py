"""The stand-in for git and gh answers only what a test told it to (#381): a call it was not
told of fails the test, so a script cannot reach an unexpected command unseen."""

import subprocess
from pathlib import Path

import pytest
from stood_in_commands import Commands


def run(commands: Commands, *args: str) -> subprocess.CompletedProcess[bytes]:
    return commands.run(
        ["/stood-in/" + args[0], *args[1:]], cwd=Path(), capture_output=True, check=False
    )


def test_a_call_it_was_not_told_of_fails() -> None:
    with pytest.raises(AssertionError, match="unexpected call"):
        run(Commands(answers={("git", "diff"): b""}), "git", "log")


def test_the_last_word_is_matched_as_a_prefix_only() -> None:
    commands = Commands(answers={("gh", "api", "repos/o/r/runs"): b"listed"})
    assert run(commands, "gh", "api", "repos/o/r/runs?branch=x").stdout == b"listed"
    with pytest.raises(AssertionError, match="unexpected call"):
        run(commands, "gh", "api", "repos/o/r/jobs")


def test_a_shorter_call_does_not_match_a_longer_answer() -> None:
    with pytest.raises(AssertionError, match="unexpected call"):
        run(Commands(answers={("git", "diff", "-U0"): b""}), "git", "diff")


RUN_7 = {
    "workflow-trace-shape-0/shape/__run": "trace",
    "coverage-python-yahoo-shape/coverage.json": "{}",
}


def download(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    commands = Commands(answers={}, downloads={"7": RUN_7})
    return run(
        commands, "gh", "run", "download", "7", "--repo", "o/r", *args, "--dir", str(tmp_path)
    )


def written(tmp_path: Path) -> list[str]:
    return sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())


def test_a_download_by_pattern_keeps_each_matching_artifact_in_its_own_folder(
    tmp_path: Path,
) -> None:
    """As gh does: several artifacts may match a pattern, so each gets a folder of its name."""
    assert download(tmp_path, "--pattern", "workflow-trace-*").returncode == 0
    assert written(tmp_path) == ["workflow-trace-shape-0/shape/__run"]


def test_a_download_by_name_unpacks_that_artifact_alone_into_the_folder(tmp_path: Path) -> None:
    assert download(tmp_path, "--name", "coverage-python-yahoo-shape").returncode == 0
    assert written(tmp_path) == ["coverage.json"]


@pytest.mark.parametrize("asked", [("--name", "coverage-python-perf"), ("--pattern", "nothing-*")])
def test_a_download_matching_no_artifact_fails_as_gh_does(
    tmp_path: Path, asked: tuple[str, str]
) -> None:
    done = download(tmp_path, *asked)
    assert (done.returncode, done.stderr) == (
        1,
        b"no artifact matches any of the names or patterns provided",
    )
    assert written(tmp_path) == []


def test_a_download_naming_no_artifact_fails_the_test(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="names no artifact"):
        download(tmp_path)
