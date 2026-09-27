"""The output layer: the ``[training]`` level, the inline block and the footer (M5 spec §5.7,
T1 spec §6 item 4), and the lesson and course pages ``learn`` prints (T1 §6 item 3)."""

import re

import pytest

from steadyhand import DISCLAIMER
from steadyhand.training import Lesson, Level, Module
from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.output import (
    LEVELS,
    Page,
    UnknownNameError,
    render,
    show_course,
    show_lesson,
    training_level,
)
from steadyhand_idx.training import catalogue

RUN_RATE = "term.run_rate"
DIVIDEND_TAX = "term.dividend_tax"


def page_showing(*keys: str) -> Page:
    page = Page()
    page.add("Run-rate: IDR 1,200,000", *keys)
    return page


def test_the_levels_are_t1s() -> None:
    assert LEVELS == ("off", "new", "some", "experienced")


@pytest.mark.parametrize(
    ("table", "level"),
    [({}, Level.NEW), ({"level": "off"}, Level.OFF), ({"level": "experienced"}, Level.EXPERIENCED)],
)
def test_the_training_level(table: dict[str, object], level: Level) -> None:
    assert training_level(table) is level


@pytest.mark.parametrize(
    ("table", "problem"),
    [
        ({"level": "NEW"}, "level must be one of off, new, some, experienced, got 'NEW'"),
        ({"level": 1}, "level must be one of off, new, some, experienced, got 1"),
        ({"level": "new", "colour": True}, "unknown key 'colour'"),
    ],
)
def test_a_bad_training_table_names_its_key(table: dict[str, object], problem: str) -> None:
    message = f"steadyhand.toml [training]: {problem}"
    with pytest.raises(DataFileError, match=f"^{re.escape(message)}$"):
        training_level(table)


def test_a_page_keeps_each_key_once_in_first_shown_order() -> None:
    page = Page()
    page.add("a", DIVIDEND_TAX, RUN_RATE)
    page.add()
    page.add("b", RUN_RATE, DIVIDEND_TAX)
    assert page.lines == ["a", "", "b"]
    assert page.keys == [DIVIDEND_TAX, RUN_RATE]


def test_at_new_the_block_explains_each_lesson_before_the_footer() -> None:
    run_rate = catalogue().for_key(RUN_RATE)
    assert render(page_showing(RUN_RATE), {"level": "new"}) == (
        "Run-rate: IDR 1,200,000\n\nWhat this means\n"
        f"• {run_rate.title}: {run_rate.summary} More: steadyhand-idx learn {run_rate.id}\n\n"
        f"{DISCLAIMER}\n"
    )


def test_at_some_the_block_names_the_lessons() -> None:
    lessons = catalogue()
    ids = f"{lessons.for_key(RUN_RATE).id}, {lessons.for_key(DIVIDEND_TAX).id}"
    assert render(page_showing(RUN_RATE, DIVIDEND_TAX), {"level": "some"}) == (
        f"Run-rate: IDR 1,200,000\n\nLearn more with steadyhand-idx learn: {ids}\n\n{DISCLAIMER}\n"
    )


@pytest.mark.parametrize("level", ["experienced", "off"])
def test_at_experienced_and_off_there_is_no_block_and_the_same_footer(level: str) -> None:
    assert render(page_showing(RUN_RATE), {"level": level}) == (
        f"Run-rate: IDR 1,200,000\n\n{DISCLAIMER}\n"
    )


def test_with_no_keys_there_is_no_block_at_any_level() -> None:
    for level in LEVELS:
        assert render(page_showing(), {"level": level}) == (
            f"Run-rate: IDR 1,200,000\n\n{DISCLAIMER}\n"
        )


def test_a_page_that_shows_a_key_with_no_lesson_is_a_bug_at_every_level() -> None:
    for level in LEVELS:
        with pytest.raises(LookupError, match=r"no lesson for 'term\.nothing'"):
            render(page_showing("term.nothing"), {"level": level})


def lesson(see_also: tuple[str, ...]) -> Lesson:
    return Lesson(
        id="a.b",
        title="A title",
        summary="A summary.",
        explains=(),
        module=None,
        position=None,
        see_also=see_also,
        sources=(),
        body="\nFirst line.\n\nSecond paragraph.\n\n",
        origin="a.b.md",
    )


def test_a_lesson_is_its_title_its_body_then_its_see_also() -> None:
    assert show_lesson(lesson(("c.d", "e.f"))).lines == [
        "A title",
        "",
        "First line.\n\nSecond paragraph.",
        "",
        "See also: c.d, e.f",
    ]


def test_a_lesson_with_nothing_to_see_also_ends_with_its_body() -> None:
    assert show_lesson(lesson(())).lines == ["A title", "", "First line.\n\nSecond paragraph."]


def test_the_course_lists_each_module_and_says_when_one_is_empty() -> None:
    modules = [
        Module(1, "one", "The first", (lesson(()),)),
        Module(2, "two", "The second", ()),
    ]
    assert show_course(modules).lines == [
        "Module 1: The first",
        "  a.b: A title",
        "",
        "Module 2: The second",
        "  (no lessons yet)",
        "",
        "Read one with: steadyhand-idx learn <id>",
    ]


def test_an_unknown_name_carries_up_to_three_close_names() -> None:
    error = UnknownNameError.among("strategy", "buy-and-hodl", ["buy-and-hold", "x", "y"])
    assert str(error) == "no strategy named 'buy-and-hodl'; the closest: buy-and-hold"
    assert (error.kind, error.wanted, error.closest) == (
        "strategy",
        "buy-and-hodl",
        ("buy-and-hold",),
    )
    assert str(UnknownNameError.among("lesson", "zzz", ["a.b"])) == "no lesson named 'zzz'"
    many = UnknownNameError.among("lesson", "abcd", ["abce", "abcf", "abcg", "abch"])
    assert len(many.closest) == 3
