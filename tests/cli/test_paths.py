"""The data directory and the private files in it (M5 spec §4.1)."""

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from steadyhand_idx.paths import create_private, data_dir, make_private_dir, replace_private


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@contextmanager
def strict_umask() -> Iterator[None]:
    """A umask that strips the owner's write bit, so a mode that is only inherited shows."""
    old = os.umask(0o277)
    try:
        yield
    finally:
        os.umask(old)


def test_the_option_comes_first() -> None:
    env = {"STEADYHAND_HOME": "/b", "XDG_DATA_HOME": "/c", "HOME": "/d"}
    assert data_dir(Path("/a"), env) == Path("/a")


def test_then_steadyhand_home() -> None:
    env = {"STEADYHAND_HOME": "/b", "XDG_DATA_HOME": "/c", "HOME": "/d"}
    assert data_dir(None, env) == Path("/b")


def test_then_xdg_data_home() -> None:
    env = {"XDG_DATA_HOME": "/c", "HOME": "/d"}
    assert data_dir(None, env) == Path("/c/steadyhand-idx")


def test_then_the_home_directory() -> None:
    assert data_dir(None, {"HOME": "/d"}) == Path("/d/.local/share/steadyhand-idx")


def test_an_empty_variable_counts_as_unset() -> None:
    env = {"STEADYHAND_HOME": "", "XDG_DATA_HOME": "", "HOME": "/d"}
    assert data_dir(None, env) == Path("/d/.local/share/steadyhand-idx")


def test_a_relative_xdg_data_home_is_ignored_as_the_xdg_specification_says() -> None:
    env = {"XDG_DATA_HOME": "relative/share", "HOME": "/d"}
    assert data_dir(None, env) == Path("/d/.local/share/steadyhand-idx")


def test_with_no_home_variable_the_users_home_is_asked_for() -> None:
    assert data_dir(None, {}) == Path.home() / ".local" / "share" / "steadyhand-idx"


def test_a_new_data_directory_is_0700_whatever_the_umask(tmp_path: Path) -> None:
    target = tmp_path / "steadyhand-idx"
    with strict_umask():
        make_private_dir(target)
    assert target.is_dir()
    assert mode(target) == 0o700


def test_a_new_data_directory_gets_its_parents(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "steadyhand-idx"
    make_private_dir(target)
    assert target.is_dir()
    assert mode(target) == 0o700


def test_an_existing_directory_is_left_as_it_is(tmp_path: Path) -> None:
    target = tmp_path / "mine"
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    make_private_dir(target)
    assert mode(target) == 0o755


def test_a_created_file_is_0600_whatever_the_umask(tmp_path: Path) -> None:
    target = tmp_path / "steadyhand.toml"
    with strict_umask():
        create_private(target, "a = 1\n")
    assert target.read_text(encoding="utf-8") == "a = 1\n"
    assert mode(target) == 0o600


def test_creating_never_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "steadyhand.toml"
    target.write_text("mine\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        create_private(target, "a = 1\n")
    assert target.read_text(encoding="utf-8") == "mine\n"


def test_a_replaced_file_is_0600_and_leaves_nothing_behind(tmp_path: Path) -> None:
    target = tmp_path / "report.md"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o644)
    with strict_umask():
        replace_private(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert mode(target) == 0o600
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.md"]


def test_a_new_file_can_be_written_by_replacing(tmp_path: Path) -> None:
    target = tmp_path / "report.md"
    replace_private(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert mode(target) == 0o600


def test_a_failed_replace_keeps_the_old_file_and_leaves_nothing_behind(tmp_path: Path) -> None:
    target = tmp_path / "report.md"
    target.write_text("old\n", encoding="utf-8")
    unencodable = chr(0xD800)  # a lone surrogate: UTF-8 cannot write it
    with pytest.raises(UnicodeEncodeError):
        replace_private(target, f"new {unencodable}\n")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.md"]
