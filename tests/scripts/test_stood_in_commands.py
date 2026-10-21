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
