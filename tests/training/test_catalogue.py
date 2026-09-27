"""The lesson loader: every rule of T1 spec §4.1, and the course file (§4.3).

Each malformed case writes a good catalogue with exactly one file changed, and asserts that the
``LessonError`` names that file and the field, not only that something was raised.
"""

from pathlib import Path

import pytest

from steadyhand.training import Catalogue, Lesson, LessonError, LessonNotFoundError, Module

GOOD = {
    "engine/start.welcome.md": (
        'id = "start.welcome"\ntitle = "Welcome"\nsummary = "What this software is."\n'
        'explains = []\nmodule = "start-here"\nposition = 1'
    ),
    "engine/income.run_rate.md": (
        'id = "income.run_rate"\ntitle = "Run-rate"\nsummary = "What holdings pay in a year."\n'
        'explains = ["term.run_rate"]\nmodule = "income-goal"\nposition = 1\n'
        'see_also = ["idx.lots"]\nsources = ["README.md"]'
    ),
    "engine/data.gaps.md": (
        'id = "data.gaps"\ntitle = "Gaps in the data"\nsummary = "Why a day can be missing."\n'
        'explains = ["data.bar.missing", "data.bar.refused"]'
    ),
    "idx/idx.lots.md": (
        'id = "idx.lots"\ntitle = "Lots"\nsummary = "Shares trade in lots of 100."\n'
        'explains = ["idx.lot.size"]\nmodule = "how-idx-works"\nposition = 1'
    ),
    "idx/idx.ticks.md": (
        'id = "idx.ticks"\ntitle = "Tick sizes"\nsummary = "Prices move in fixed steps."\n'
        'explains = ["idx.tick.size"]\nmodule = "how-idx-works"\nposition = 2'
    ),
}
COURSE = (
    '[[module]]\nnumber = 1\nslug = "start-here"\ntitle = "Start here"\n\n'
    '[[module]]\nnumber = 2\nslug = "how-idx-works"\ntitle = "How IDX works"\n\n'
    '[[module]]\nnumber = 3\nslug = "income-goal"\ntitle = "The income goal"\n\n'
    '[[module]]\nnumber = 4\nslug = "strategies"\ntitle = "Strategies"\n'
)


def lesson_text(header: str, body: str = "Some words about it.") -> str:
    return f"+++\n{header}\n+++\n\n{body}\n"


def changed(path: str, old: str, new: str) -> str:
    """The good header of *path* with *old* replaced once by *new*: the case's one defect."""
    assert GOOD[path].count(old) == 1, f"{old!r} is not in {path} exactly once"
    return lesson_text(GOOD[path].replace(old, new))


def build(
    tmp_path: Path, files: dict[str, str | None] | None = None, course: str = COURSE
) -> Catalogue:
    texts: dict[str, str | None] = {name: lesson_text(header) for name, header in GOOD.items()}
    texts.update(files or {})
    for name, text in texts.items():
        if text is not None:
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "course.toml").write_text(course, encoding="utf-8")
    return Catalogue.load([tmp_path / "engine", tmp_path / "idx"], tmp_path / "course.toml")


def test_a_good_catalogue_loads(tmp_path: Path) -> None:
    catalogue = build(tmp_path)
    assert [lesson.id for lesson in catalogue.lessons()] == [
        "data.gaps",
        "idx.lots",
        "idx.ticks",
        "income.run_rate",
        "start.welcome",
    ]
    run_rate = catalogue.lesson("income.run_rate")
    assert run_rate == Lesson(
        id="income.run_rate",
        title="Run-rate",
        summary="What holdings pay in a year.",
        explains=("term.run_rate",),
        module="income-goal",
        position=1,
        see_also=("idx.lots",),
        sources=("README.md",),
        body="Some words about it.",
        origin=str(tmp_path / "engine/income.run_rate.md"),
    )
    assert catalogue.for_key("data.bar.refused") is catalogue.lesson("data.gaps")
    assert catalogue.for_key("idx.lot.size") is catalogue.lesson("idx.lots")
    assert [(m.number, m.slug, m.title) for m in catalogue.course()] == [
        (1, "start-here", "Start here"),
        (2, "how-idx-works", "How IDX works"),
        (3, "income-goal", "The income goal"),
        (4, "strategies", "Strategies"),
    ]
    how = catalogue.course()[1]
    assert how == Module(
        2,
        "how-idx-works",
        "How IDX works",
        (catalogue.lesson("idx.lots"), catalogue.lesson("idx.ticks")),
    )
    assert catalogue.course()[3].lessons == ()


def test_lessons_are_found_in_subfolders_and_other_files_are_ignored(tmp_path: Path) -> None:
    catalogue = build(
        tmp_path,
        {
            "engine/start.welcome.md": None,
            "engine/deeper/start.welcome.md": lesson_text(GOOD["engine/start.welcome.md"]),
            "engine/notes.txt": "not a lesson",
        },
    )
    assert catalogue.lesson("start.welcome").origin.endswith("deeper/start.welcome.md")
    assert len(catalogue.lessons()) == len(GOOD)


def test_a_file_with_windows_line_endings_reads_the_same(tmp_path: Path) -> None:
    text = lesson_text(GOOD["idx/idx.lots.md"], "First line.\n\nSecond line.")
    catalogue = build(tmp_path, {"idx/idx.lots.md": text.replace("\n", "\r\n")})
    assert catalogue.lesson("idx.lots").body == "First line.\n\nSecond line."
    assert catalogue.lesson("idx.lots").summary == "Shares trade in lots of 100."


def test_a_byte_order_mark_is_not_part_of_the_header(tmp_path: Path) -> None:
    text = "\ufeff" + lesson_text(GOOD["idx/idx.lots.md"])
    catalogue = build(tmp_path, {"idx/idx.lots.md": text}, course="\ufeff" + COURSE)
    assert catalogue.lesson("idx.lots").title == "Lots"
    assert len(catalogue.course()) == 4


def test_titles_and_summaries_at_their_limits_load(tmp_path: Path) -> None:
    title, summary = "T" * 60, "S" * 159 + "."
    catalogue = build(
        tmp_path,
        {
            "idx/idx.lots.md": changed("idx/idx.lots.md", '"Lots"', f'"{title}"'),
            "idx/idx.ticks.md": changed(
                "idx/idx.ticks.md", '"Prices move in fixed steps."', f'"{summary}"'
            ),
        },
    )
    assert catalogue.lesson("idx.lots").title == title
    assert catalogue.lesson("idx.ticks").summary == summary


def test_text_outside_ascii_loads(tmp_path: Path) -> None:
    text = changed("idx/idx.lots.md", '"Lots"', '"Lot — 100 lembar"')
    assert build(tmp_path, {"idx/idx.lots.md": text}).lesson("idx.lots").title == "Lot — 100 lembar"


LOTS = "idx/idx.lots.md"
TICKS = "idx/idx.ticks.md"
RUN = "engine/income.run_rate.md"

LESSON_CASES = [
    ("no opening fence", LOTS, GOOD[LOTS] + "\n+++\n\nBody.\n", "header"),
    ("no closing fence", LOTS, f"+++\n{GOOD[LOTS]}\n\nBody.\n", "header"),
    ("not TOML", LOTS, lesson_text(GOOD[LOTS] + "\nthis is not toml"), "header"),
    ("no body", LOTS, f"+++\n{GOOD[LOTS]}\n+++\n\n  \n", "body"),
    ("unknown field", LOTS, changed(LOTS, "position = 1", 'position = 1\nlevel = "new"'), "level"),
    ("no id", LOTS, changed(LOTS, 'id = "idx.lots"\n', ""), "id"),
    ("no title", LOTS, changed(LOTS, 'title = "Lots"\n', ""), "title"),
    (
        "no summary",
        LOTS,
        changed(LOTS, 'summary = "Shares trade in lots of 100."\n', ""),
        "summary",
    ),
    ("no explains", LOTS, changed(LOTS, 'explains = ["idx.lot.size"]\n', ""), "explains"),
    ("id not a key", LOTS, changed(LOTS, '"idx.lots"', '"Idx.Lots"'), "id"),
    ("id not a string", LOTS, changed(LOTS, '"idx.lots"', "3"), "id"),
    ("id not the file name", LOTS, changed(LOTS, '"idx.lots"', '"idx.lot"'), "id"),
    ("empty title", LOTS, changed(LOTS, '"Lots"', '"  "'), "title"),
    ("long title", LOTS, changed(LOTS, '"Lots"', '"' + "T" * 61 + '"'), "title"),
    ("title on two lines", LOTS, changed(LOTS, '"Lots"', '"Lots\\nof them"'), "title"),
    ("title not text", LOTS, changed(LOTS, '"Lots"', "7"), "title"),
    ("summary without a stop", LOTS, changed(LOTS, 'of 100."', 'of 100"'), "summary"),
    (
        "summary of two sentences",
        LOTS,
        changed(LOTS, "Shares trade", "Yes. Shares trade"),
        "summary",
    ),
    (
        "long summary",
        LOTS,
        changed(LOTS, '"Shares trade in lots of 100."', '"' + "S" * 160 + '."'),
        "summary",
    ),
    ("explains not a list", LOTS, changed(LOTS, '["idx.lot.size"]', '"idx.lot.size"'), "explains"),
    ("explains a bad key", LOTS, changed(LOTS, '["idx.lot.size"]', '["lot size"]'), "explains"),
    (
        "explains a key twice",
        LOTS,
        changed(LOTS, '["idx.lot.size"]', '["idx.lot.size", "idx.lot.size"]'),
        "explains",
    ),
    ("explains an empty entry", LOTS, changed(LOTS, '["idx.lot.size"]', '[""]'), "explains"),
    ("module without position", LOTS, changed(LOTS, "\nposition = 1", ""), "position"),
    ("position without module", LOTS, changed(LOTS, 'module = "how-idx-works"\n', ""), "module"),
    ("module not a slug", LOTS, changed(LOTS, '"how-idx-works"', '"How IDX"'), "module"),
    ("module not in the course", LOTS, changed(LOTS, '"how-idx-works"', '"costs"'), "module"),
    ("position zero", LOTS, changed(LOTS, "position = 1", "position = 0"), "position"),
    ("position true", LOTS, changed(LOTS, "position = 1", "position = true"), "position"),
    ("position as text", LOTS, changed(LOTS, "position = 1", 'position = "1"'), "position"),
    ("position repeated", TICKS, changed(TICKS, "position = 2", "position = 1"), "position"),
    ("position gap", TICKS, changed(TICKS, "position = 2", "position = 3"), "position"),
    ("see_also unresolved", RUN, changed(RUN, '["idx.lots"]', '["idx.lot"]'), "see_also"),
    ("see_also itself", RUN, changed(RUN, '["idx.lots"]', '["income.run_rate"]'), "see_also"),
    ("see_also not a list", RUN, changed(RUN, '["idx.lots"]', '"idx.lots"'), "see_also"),
    ("sources empty entry", RUN, changed(RUN, '["README.md"]', '[" "]'), "sources"),
    ("sources not a list", RUN, changed(RUN, '["README.md"]', '"README.md"'), "sources"),
    ("sources not text", RUN, changed(RUN, '["README.md"]', "[1]"), "sources"),
]


@pytest.mark.parametrize(
    ("path", "text", "field"),
    [case[1:] for case in LESSON_CASES],
    ids=[case[0] for case in LESSON_CASES],
)
def test_a_broken_lesson_names_its_file_and_field(
    tmp_path: Path, path: str, text: str, field: str
) -> None:
    with pytest.raises(LessonError) as raised:
        build(tmp_path, {path: text})
    assert (raised.value.origin, raised.value.field) == (str(tmp_path / path), field)
    assert str(raised.value).startswith(f"{tmp_path / path}: {field}: ")


def test_an_id_used_in_both_packages_names_the_second_file(tmp_path: Path) -> None:
    copy = lesson_text(GOOD[LOTS].replace('["idx.lot.size"]', "[]"))
    with pytest.raises(LessonError) as raised:
        build(tmp_path, {"idx/deeper/idx.lots.md": copy})
    first, second = sorted([str(tmp_path / LOTS), str(tmp_path / "idx/deeper/idx.lots.md")])
    assert (raised.value.origin, raised.value.field) == (second, "id")
    assert raised.value.problem == f"idx.lots is also {first}"


def test_a_key_explained_by_two_lessons_names_the_second(tmp_path: Path) -> None:
    text = changed(TICKS, '["idx.tick.size"]', '["idx.tick.size", "idx.lot.size"]')
    with pytest.raises(LessonError) as raised:
        build(tmp_path, {TICKS: text})
    assert (raised.value.origin, raised.value.field) == (str(tmp_path / TICKS), "explains")
    assert raised.value.problem == "idx.lot.size is already explained by idx.lots"


def test_a_missing_root_is_named(tmp_path: Path) -> None:
    build(tmp_path)
    missing = tmp_path / "nowhere"
    with pytest.raises(LessonError) as raised:
        Catalogue.load([tmp_path / "engine", missing], tmp_path / "course.toml")
    assert (raised.value.origin, raised.value.field) == (str(missing), "root")


COURSE_CASES = [
    ("not TOML", COURSE + "\nnot toml", "course"),
    ("unknown table", COURSE + "\n[extra]\nx = 1\n", "extra"),
    ("no modules", 'title = "x"\n', "title"),
    ("empty", "", "module"),
    ("module not a table list", "module = [1]\n", "module[1]"),
    ("number out of order", COURSE.replace("number = 2", "number = 3"), "module[2].number"),
    ("number true", COURSE.replace("number = 1", "number = true"), "module[1].number"),
    ("slug not a slug", COURSE.replace('"start-here"', '"Start here"'), "module[1].slug"),
    ("slug twice", COURSE.replace('"how-idx-works"', '"start-here"'), "module[2].slug"),
    ("no title", COURSE.replace('title = "Start here"\n', ""), "module[1].title"),
    ("long title", COURSE.replace('"Start here"', '"' + "T" * 61 + '"'), "module[1].title"),
    (
        "extra field",
        COURSE.replace('title = "Start here"', 'title = "Start here"\ncolour = 1'),
        "module[1].colour",
    ),
]


@pytest.mark.parametrize(
    ("course", "field"), [case[1:] for case in COURSE_CASES], ids=[case[0] for case in COURSE_CASES]
)
def test_a_broken_course_names_the_field(tmp_path: Path, course: str, field: str) -> None:
    with pytest.raises(LessonError) as raised:
        build(tmp_path, course=course)
    assert (raised.value.origin, raised.value.field) == (str(tmp_path / "course.toml"), field)


def test_an_unknown_id_names_the_closest(tmp_path: Path) -> None:
    catalogue = build(tmp_path)
    with pytest.raises(LessonNotFoundError) as raised:
        catalogue.lesson("idx.lot")
    assert raised.value.wanted == "idx.lot"
    assert raised.value.closest == ("idx.lots", "idx.ticks")
    assert str(raised.value) == "no lesson for 'idx.lot'; the closest: idx.lots, idx.ticks"


def test_an_id_like_nothing_names_no_closest(tmp_path: Path) -> None:
    with pytest.raises(LessonNotFoundError) as raised:
        build(tmp_path).lesson("zzzz")
    assert raised.value.closest == ()
    assert str(raised.value) == "no lesson for 'zzzz'"


def test_a_key_with_no_lesson_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(LessonNotFoundError) as raised:
        build(tmp_path).for_key("data.bar.missed")
    assert raised.value.closest[0] == "data.bar.missing"
