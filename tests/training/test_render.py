"""The inline explanation for each level (T1 spec §6 item 4), with hand-written expected text.

The fixture catalogue has an engine lesson explaining two keys (a term and a note) and an IDX
lesson explaining one, so one run covers dedup, first-appearance order and both packages.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from steadyhand.training import Catalogue, LessonNotFoundError, Level, explain

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/training"
PROGRAM = "steadyhand-idx"
SHOWN = ["fixture.lot.size", "term.fixture_return", "fixture.note.gap", "fixture.lot.size"]


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load([FIXTURE / "engine/en", FIXTURE / "idx/en"], FIXTURE / "course.toml")


def test_new_gives_a_line_per_lesson_in_first_appearance_order(catalogue: Catalogue) -> None:
    assert explain(catalogue, SHOWN, Level.NEW, PROGRAM) == (
        "What this means\n"
        "• Lots: Shares are bought in lots of a fixed size. "
        "More: steadyhand-idx learn fixture.lots\n"
        "• Returns: How much a portfolio gained or lost. "
        "More: steadyhand-idx learn fixture.returns"
    )


def test_some_names_the_lessons_only(catalogue: Catalogue) -> None:
    assert explain(catalogue, SHOWN, Level.SOME, PROGRAM) == (
        "Learn more with steadyhand-idx learn: fixture.lots, fixture.returns"
    )


def test_two_keys_of_one_lesson_give_one_line(catalogue: Catalogue) -> None:
    shown = ["fixture.note.gap", "term.fixture_return"]
    assert explain(catalogue, shown, Level.NEW, PROGRAM) == (
        "What this means\n"
        "• Returns: How much a portfolio gained or lost. "
        "More: steadyhand-idx learn fixture.returns"
    )
    assert explain(catalogue, shown, Level.SOME, PROGRAM) == (
        "Learn more with steadyhand-idx learn: fixture.returns"
    )


@pytest.mark.parametrize("level", [Level.EXPERIENCED, Level.OFF])
def test_experienced_and_off_show_nothing(catalogue: Catalogue, level: Level) -> None:
    assert explain(catalogue, SHOWN, level, PROGRAM) == ""


@pytest.mark.parametrize("level", list(Level))
def test_no_keys_show_nothing_at_every_level(catalogue: Catalogue, level: Level) -> None:
    assert explain(catalogue, [], level, PROGRAM) == ""


@pytest.mark.parametrize("level", list(Level))
def test_an_unknown_key_is_a_bug_at_every_level(catalogue: Catalogue, level: Level) -> None:
    with pytest.raises(LessonNotFoundError, match=r"'fixture.lot.sise'"):
        explain(catalogue, ["fixture.note.gap", "fixture.lot.sise"], level, PROGRAM)


def test_the_program_name_is_the_callers(catalogue: Catalogue) -> None:
    assert explain(catalogue, ["fixture.lot.size"], Level.NEW, "sh") == (
        "What this means\n"
        "• Lots: Shares are bought in lots of a fixed size. More: sh learn fixture.lots"
    )


def test_keys_may_be_read_once(catalogue: Catalogue) -> None:
    def shown() -> Iterator[str]:
        yield from SHOWN

    assert explain(catalogue, shown(), Level.SOME, PROGRAM) == (
        "Learn more with steadyhand-idx learn: fixture.lots, fixture.returns"
    )


def test_the_levels_are_the_settings_values() -> None:
    assert [level.value for level in Level] == ["off", "new", "some", "experienced"]
    assert Level("some") is Level.SOME


def test_bad_arguments_are_refused(catalogue: Catalogue) -> None:
    with pytest.raises(TypeError, match=r"^level must be a Level, got str$"):
        explain(catalogue, SHOWN, "new", PROGRAM)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^keys is the keys the output showed, not one key$"):
        explain(catalogue, "fixture.lot.size", Level.NEW, PROGRAM)
    with pytest.raises(TypeError, match=r"^a key must be a str, got int$"):
        explain(catalogue, [3], Level.NEW, PROGRAM)  # type: ignore[list-item]
    with pytest.raises(
        ValueError, match=r"^program is the command the user types, and it is blank$"
    ):
        explain(catalogue, SHOWN, Level.NEW, " ")
    with pytest.raises(TypeError, match=r"^program must be a str, got NoneType$"):
        explain(catalogue, SHOWN, Level.NEW, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^catalogue must be a Catalogue, got dict$"):
        explain({}, SHOWN, Level.NEW, PROGRAM)  # type: ignore[arg-type]
