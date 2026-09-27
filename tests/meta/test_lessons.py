"""The catalogue guards, switched on over the real lessons of both packages (T1 spec §8).

``catalogue()`` loading at all proves every rule ``Catalogue.load`` checks: ids unique across
both packages and equal to their file names, each key explained at most once, every
``see_also`` resolved, every course position in place. The tests below add what needs the repo.
After T1, a story that adds a note or a term key cannot merge until its lesson exists.
"""

from pathlib import Path

import pytest
from key_walk import ENGINE, IDX, all_keys
from lesson_rules import (
    advice_findings,
    missing_sources,
    start_here_problems,
    unexplained,
    unknown,
)

from steadyhand import DISCLAIMER
from steadyhand.training import Catalogue, Level, explain
from steadyhand_idx.training import catalogue

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = (ENGINE / "training/lessons/en", IDX / "training/lessons/en")
NOT_NEUTRAL = ("Rp", "IDX", "Indonesia", "steadyhand-idx")


@pytest.fixture(scope="module")
def real() -> Catalogue:
    return catalogue()


def test_every_lesson_file_is_loaded(real: Catalogue) -> None:
    files = sorted(path for folder in FOLDERS for path in folder.rglob("*.md"))
    assert len(files) >= 30
    assert len(real.lessons()) == len(files)
    assert all(any(path.is_relative_to(folder) for folder in FOLDERS) for path in files)


def test_every_key_has_a_lesson(real: Catalogue) -> None:
    keys = all_keys()
    assert len(keys) >= 40
    assert unexplained(real, keys) == []


def test_no_lesson_explains_a_key_that_does_not_exist(real: Catalogue) -> None:
    assert sum(len(lesson.explains) for lesson in real.lessons()) >= 40
    assert unknown(real, all_keys()) == []


def test_every_source_is_a_repo_file(real: Catalogue) -> None:
    assert sum(len(lesson.sources) for lesson in real.lessons()) >= 20
    assert missing_sources(real, ROOT) == []


def test_the_course_opens_with_the_disclaimer(real: Catalogue) -> None:
    assert start_here_problems(real, DISCLAIMER) == []


def test_no_lesson_carries_advice_phrasing(real: Catalogue) -> None:
    assert advice_findings(real) == []


def test_the_engine_lessons_are_market_neutral(real: Catalogue) -> None:
    engine = [lesson for lesson in real.lessons() if Path(lesson.origin).is_relative_to(FOLDERS[0])]
    assert len(engine) >= 10
    found = [
        f"{lesson.id}: {word}"
        for lesson in engine
        for word in NOT_NEUTRAL
        if word in f"{lesson.title} {lesson.summary} {lesson.body}"
    ]
    assert found == []


def test_the_modules_written_in_t1_have_lessons(real: Catalogue) -> None:
    counts = {module.slug: len(module.lessons) for module in real.course()}
    written = [slug for slug in counts if slug != "strategies"]
    assert len(written) == 7
    assert [slug for slug in written if counts[slug] == 0] == []
    assert counts["strategies"] == 0


def test_the_spec_example_renders_as_written(real: Catalogue) -> None:
    assert explain(real, ["term.run_rate"], Level.NEW, "steadyhand-idx") == (
        "What this means\n"
        "• Run-rate: What the dividends you hold now would pay over a year if nothing changed. "
        "More: steadyhand-idx learn income.run_rate"
    )
