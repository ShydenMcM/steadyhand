"""The catalogue guards, proven on a fixture catalogue (T1 spec §8).

The fixture passes every guard, and each broken copy fails exactly the guard it breaks. The
guards run over the real lesson folders in ``test_lessons.py``.
"""

import shutil
from pathlib import Path

import pytest
from lesson_rules import missing_sources, start_here_problems, unexplained, unknown

from steadyhand import DISCLAIMER
from steadyhand.training import Catalogue

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/training"
KEYS = frozenset({"term.fixture_return", "fixture.note.gap", "fixture.lot.size"})


def load(folder: Path) -> Catalogue:
    return Catalogue.load([folder / "engine/en", folder / "idx/en"], folder / "course.toml")


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    return Path(shutil.copytree(FIXTURE, tmp_path / "training"))


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} is not in {path.name} exactly once"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_the_fixture_passes_every_guard() -> None:
    catalogue = load(FIXTURE)
    assert len(catalogue.lessons()) == 3
    assert unexplained(catalogue, KEYS) == []
    assert unknown(catalogue, KEYS) == []
    assert missing_sources(catalogue, ROOT) == []
    assert start_here_problems(catalogue, DISCLAIMER) == []


def test_a_key_with_no_lesson_is_found() -> None:
    assert unexplained(load(FIXTURE), KEYS | {"fixture.new.key"}) == ["fixture.new.key"]


def test_a_lesson_explaining_a_key_that_does_not_exist_is_found() -> None:
    assert unknown(load(FIXTURE), KEYS - {"fixture.lot.size"}) == ["fixture.lots: fixture.lot.size"]


@pytest.mark.parametrize(
    "source",
    ["docs/nowhere.md", "docs/nowhere.md §3", "docs", "/etc/hosts", "../steadyhand/README.md"],
)
def test_a_source_that_is_not_a_repo_file_is_found(copy: Path, source: str) -> None:
    edit(copy / "engine/en/fixture.returns.md", '"README.md"', f'"{source}"')
    assert missing_sources(load(copy), ROOT) == [f"fixture.returns: {source}"]


def test_a_source_with_a_section_is_checked_by_its_path() -> None:
    lesson = load(FIXTURE).lesson("fixture.returns")
    assert "docs/lq45-members.md §2" in lesson.sources
    assert missing_sources(load(FIXTURE), ROOT) == []


def test_a_start_lesson_without_the_disclaimer_is_found(copy: Path) -> None:
    edit(copy / "engine/en/start.welcome.md", "You can lose money.", "You can lose.")
    assert start_here_problems(load(copy), DISCLAIMER) == [
        "start.welcome does not carry the disclaimer"
    ]


def test_a_disclaimer_hidden_in_a_comment_does_not_count(copy: Path) -> None:
    edit(copy / "engine/en/start.welcome.md", "> steadyhand is", "<!--\n> steadyhand is")
    edit(copy / "engine/en/start.welcome.md", "You can lose money.", "You can lose money. -->")
    assert start_here_problems(load(copy), DISCLAIMER) == [
        "start.welcome does not carry the disclaimer"
    ]


def test_a_course_that_does_not_open_with_start_here_is_found(copy: Path) -> None:
    edit(copy / "course.toml", 'slug = "start-here"', 'slug = "begin"')
    edit(copy / "engine/en/start.welcome.md", '"start-here"', '"begin"')
    assert start_here_problems(load(copy), DISCLAIMER) == [
        "the course does not start with start-here"
    ]


def test_a_start_module_with_no_lesson_is_found(copy: Path) -> None:
    edit(copy / "engine/en/start.welcome.md", 'module = "start-here"\nposition = 1\n', "")
    assert start_here_problems(load(copy), DISCLAIMER) == ["start-here has no lesson"]
