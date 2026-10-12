"""Git stood in for the CI scripts' unit tests (#286): a unit test starts no process, so these
tests answer each script's one ``git`` call themselves and check the call it made."""

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

FAKE_GIT = "/stood-in/bin/git"


@dataclass
class FakeGit:
    """``subprocess.run`` for a script that runs git: answers every call with *stdout*, *stderr*
    and *returncode*, and keeps each call's arguments."""

    stdout: bytes = b""
    stderr: bytes = b""
    returncode: int = 0
    calls: list[tuple[list[str], dict[str, object]]] = field(default_factory=list)

    def run(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((list(args), kwargs))
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, self.stderr)

    def called_in(self, repo: Path, *args: str) -> bool:
        """Whether the one call was git with exactly *args*, in *repo*, its output captured."""
        expected = ([FAKE_GIT, *args], {"cwd": repo, "capture_output": True, "check": False})
        return self.calls == [expected]


def stand_in(monkeypatch: pytest.MonkeyPatch) -> FakeGit:
    """Answer the scripts' git calls with a ``FakeGit`` for the rest of the test."""
    git = FakeGit()
    monkeypatch.setattr(subprocess, "run", git.run)
    monkeypatch.setattr(shutil, "which", lambda name: FAKE_GIT if name == "git" else None)
    return git
