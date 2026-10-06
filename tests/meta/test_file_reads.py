"""The recorder behind the docs-only read guard, driven with the audit events it receives (#218).

Measured on 3.12 and 3.13 before writing it: ``open``'s first argument is a ``str`` for
``Path.read_text``, ``open(str)``, ``io.open_code`` (imports) and ``os.open``; ``bytes`` for
``open(bytes)``; an ``int`` for ``open(fd)``, whose path ``os.open`` already reported.
``is_file()`` and ``exists()`` raise no event at all, which is why a path that goes away is
never docs-only (``scripts/ci_scope.py``).
"""

import os
from pathlib import Path

import pytest
from file_reads import Recorder


@pytest.fixture
def root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo.resolve()


def test_a_file_opened_inside_the_repo_is_recorded_by_its_repo_path(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (str(root / "docs/a.md"), "r", 0))
    assert recorder.opened == frozenset({"docs/a.md"})


def test_a_bytes_path_is_recorded_like_a_str_path(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (os.fsencode(root / "HANDOVER.md"), "r", 0))
    assert recorder.opened == frozenset({"HANDOVER.md"})


def test_a_relative_path_is_resolved_against_the_working_directory(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(root / "..")
    recorder = Recorder(root)
    recorder("open", ("repo/docs/b.md", "r", 0))
    assert recorder.opened == frozenset({"docs/b.md"})


def test_a_dotted_path_is_normalised_before_it_is_placed(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (f"{root}/packages/../HANDOVER.md", "r", 0))
    assert recorder.opened == frozenset({"HANDOVER.md"})


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/elsewhere/HANDOVER.md", id="outside"),
        pytest.param("{root}-sibling/HANDOVER.md", id="a-sibling-sharing-the-prefix"),
        pytest.param("{root}", id="the-root-itself"),
    ],
)
def test_a_path_outside_the_repo_is_not_recorded(root: Path, path: str) -> None:
    recorder = Recorder(root)
    recorder("open", (path.format(root=root), "r", 0))
    assert recorder.opened == frozenset()
    assert recorder.unread == ()


def test_an_open_by_descriptor_is_skipped_because_its_path_was_reported(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (7, "r", 0))
    assert (recorder.opened, recorder.unread) == (frozenset(), ())


def test_any_other_event_is_ignored(root: Path) -> None:
    recorder = Recorder(root)
    recorder("os.listdir", (str(root / "docs"),))
    assert (recorder.opened, recorder.unread) == (frozenset(), ())


def test_an_argument_of_a_type_it_cannot_place_is_kept_by_name(root: Path) -> None:
    recorder = Recorder(root)
    recorder("open", (root / "HANDOVER.md", "r", 0))
    assert recorder.unread == ("PosixPath",)
    assert recorder.opened == frozenset()


def test_opened_is_a_snapshot_not_a_live_view(root: Path) -> None:
    recorder = Recorder(root)
    before = recorder.opened
    recorder("open", (str(root / "a.md"), "r", 0))
    assert before == frozenset()


def test_a_file_opened_through_a_symlink_is_recorded_by_its_real_path(
    root: Path, tmp_path: Path
) -> None:
    (root / "HANDOVER.md").write_text("x", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(root / "HANDOVER.md")
    recorder = Recorder(root)
    recorder("open", (str(link), "r", 0))
    assert recorder.opened == frozenset({"HANDOVER.md"})


def test_a_symlink_loop_is_placed_by_its_spelling_on_every_python(root: Path) -> None:
    """3.12's resolve raises on a loop and 3.13's returns the path unchanged (measured); the
    open itself then fails, so the spelling is all there is to place, on both."""
    (root / "a").symlink_to(root / "b")
    (root / "b").symlink_to(root / "a")
    recorder = Recorder(root)
    recorder("open", (str(root / "a/x.md"), "r", 0))
    assert (recorder.opened, recorder.unread) == (frozenset({"a/x.md"}), ())
