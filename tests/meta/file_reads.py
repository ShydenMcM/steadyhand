"""Every repository file the test run opens, recorded as it happens (#218).

The docs-only fast path in CI skips the tests, so it may only hold files no test reads. Shyden
chose to learn that from what the tests do rather than from their source text (2026-10-06):
``tests/conftest.py`` installs one ``Recorder`` as an audit hook before any test module is
collected, and ``test_fast_path_reads.py`` runs last and judges what it saw.

An audit hook cannot be removed and runs inside every audited call, so the recorder does as
little as it can and never raises: anything it cannot place is kept by type name in
``unread``, which the guard requires to be empty (fail closed, never skipped).
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(eq=False)
class Recorder:
    """An audit hook recording each ``open`` of a file under *root*, by its repo path.

    *root* is absolute with its symlinks resolved, as ``Path.resolve`` gives it, because the
    paths it is compared with are. A dataclass, so building one runs no code of this module.
    """

    root: Path
    installed: bool = False
    _opened: set[str] = field(default_factory=set)
    _unread: list[str] = field(default_factory=list)

    def __call__(self, event: str, args: tuple[object, ...]) -> None:
        if event != "open":
            return
        target = args[0]
        if isinstance(target, int):
            return  # a descriptor: os.open already reported the path it was opened from
        if isinstance(target, bytes):
            target = os.fsdecode(target)
        if not isinstance(target, str):
            self._unread.append(type(target).__name__)
            return
        full = _real(target)
        prefix = f"{self.root}{os.sep}"
        if full.startswith(prefix):
            self._opened.add(full.removeprefix(prefix).replace(os.sep, "/"))

    @property
    def opened(self) -> frozenset[str]:
        return frozenset(self._opened)

    @property
    def unread(self) -> tuple[str, ...]:
        return tuple(self._unread)


def _real(path: str) -> str:
    """*path* with its symlinks followed. A loop makes 3.12 raise and 3.13 return the path
    unchanged; the open then fails, so the absolute spelling is all there is to place."""
    try:
        return str(Path(path).resolve())
    except RuntimeError:
        return os.path.abspath(path)  # noqa: PTH100 - the spelling, without following links


RECORDER = Recorder(Path(__file__).resolve().parents[2])


def install() -> Recorder:
    """Install the shared recorder once for this process, and return it."""
    if not RECORDER.installed:
        sys.addaudithook(RECORDER)
        RECORDER.installed = True
    return RECORDER
