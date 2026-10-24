"""``gh`` and ``git`` stood in for the CI scripts' unit tests (#384, #381): a unit test starts no
process, so each call is answered here by its leading arguments, and every call is kept."""

import fnmatch
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass
class Commands:
    """``subprocess.run`` stood in: answers each call by its leading arguments."""

    answers: dict[tuple[str, ...], bytes]
    downloads: dict[str, dict[str, str]] = field(default_factory=dict)
    failing: tuple[str, ...] = ()
    calls: list[list[str]] = field(default_factory=list)

    def run(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(list(args))
        assert kwargs == {"cwd": kwargs["cwd"], "capture_output": True, "check": False}
        words = (Path(args[0]).name, *args[1:])
        if self.failing and words[: len(self.failing)] == self.failing:
            return subprocess.CompletedProcess(args, 1, b"", b"HTTP 404")
        if words[:3] == ("gh", "run", "download"):
            return self._download(args)
        for prefix, answer in self.answers.items():
            # The last word is matched as a prefix, so a URL's query need not be spelled out.
            head, last = prefix[:-1], prefix[-1]
            matched = len(words) >= len(prefix) and words[: len(head)] == head
            if matched and words[len(head)].startswith(last):
                return subprocess.CompletedProcess(args, 0, answer, b"")
        msg = f"unexpected call {args}"
        raise AssertionError(msg)

    def _download(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
        """As gh does: ``--name`` unpacks that one artifact into the folder, ``--pattern`` keeps
        each artifact it matches in a folder of its name, and matching none fails."""
        target = Path(args[args.index("--dir") + 1])
        if "--name" in args:
            wanted, nested = args[args.index("--name") + 1], False
        elif "--pattern" in args:
            wanted, nested = args[args.index("--pattern") + 1], True
        else:
            msg = f"the download names no artifact: {args}"
            raise AssertionError(msg)
        files = {
            (relative if nested else relative.split("/", 1)[1]): text
            for relative, text in self.downloads.get(args[3], {}).items()
            if fnmatch.fnmatchcase(relative.split("/", 1)[0], wanted)
        }
        if not files:
            stderr = b"no artifact matches any of the names or patterns provided"
            return subprocess.CompletedProcess(args, 1, b"", stderr)
        for relative, text in files.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, b"", b"")


def stand_in(monkeypatch: pytest.MonkeyPatch) -> dict[str, Commands]:
    """Answer every ``subprocess.run`` with the ``Commands`` put in the returned holder under
    ``"c"``, and every tool lookup with a stood-in path, for the rest of the test."""
    holder: dict[str, Commands] = {}

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return holder["c"].run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr("shutil.which", lambda name: f"/stood-in/{name}")
    return holder
