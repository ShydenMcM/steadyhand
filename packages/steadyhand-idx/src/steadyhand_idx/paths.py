"""Where steadyhand-idx keeps its files, and how it writes them (M5 spec §4.1).

The data directory holds the operator's financial record, so it is created ``0700`` and every
file M5 writes in it is created ``0600``, whatever the process's umask.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Final

APP: Final = "steadyhand-idx"
"""The program's name: the command, and the data directory's name under ``XDG_DATA_HOME``."""

HOME_VARIABLE: Final = "STEADYHAND_HOME"
CONFIG_FILE: Final = "steadyhand.toml"
DIRECTORY_MODE: Final = 0o700
FILE_MODE: Final = 0o600


def data_dir(option: Path | None, env: Mapping[str, str]) -> Path:
    """The data directory: ``--data-dir``, then ``$STEADYHAND_HOME``, then
    ``$XDG_DATA_HOME/steadyhand-idx``, then ``~/.local/share/steadyhand-idx``.

    An empty variable counts as unset, and so does a relative ``XDG_DATA_HOME``, as the XDG base
    directory specification says.
    """
    if option is not None:
        return option
    if home := env.get(HOME_VARIABLE):
        return Path(home)
    xdg = env.get("XDG_DATA_HOME", "")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / APP
    user = env.get("HOME")
    return (Path(user) if user else Path.home()) / ".local" / "share" / APP


def make_private_dir(path: Path) -> None:
    """Create *path* and its parents, *path* itself ``0700``. An existing directory is kept as
    it is: the operator may have made it on purpose."""
    if path.is_dir():
        return
    path.mkdir(mode=DIRECTORY_MODE, parents=True)
    path.chmod(DIRECTORY_MODE)


def create_private(path: Path, text: str) -> None:
    """Write *text* to a new file ``0600``. An existing file raises ``FileExistsError``: this
    never overwrites."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    os.fchmod(descriptor, FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(text)


def private_file(path: Path) -> Path:
    """*path*, created empty and ``0600`` if it is missing, and made ``0600`` if it is not.

    For a file another library then opens and writes, such as an SQLite database, which would
    otherwise be created with the umask's mode.
    """
    try:
        create_private(path, "")
    except FileExistsError:
        path.chmod(FILE_MODE)
    return path


def replace_private(path: Path, text: str) -> None:
    """Write *text* to *path*, ``0600``, in one step: a reader sees the old file or the new one,
    never half of either."""
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        os.fchmod(descriptor, FILE_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(text)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
