"""What every command prints: its body, T1's inline training block and the disclaimer footer
(M5 spec §5.7).

This is the one module outside the training packages allowed to import training (T1 spec §5
item 1), and the one that parses the ``[training]`` table (item 3), so the setting that decides
how much is explained never reaches a module that decides anything else. The output is plain
text with no colour.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Final

from steadyhand import DISCLAIMER
from steadyhand.training import Lesson, LessonNotFoundError, Level, Module, explain
from steadyhand_idx._datafile import DataFileError, Where
from steadyhand_idx.paths import APP, CONFIG_FILE
from steadyhand_idx.training import catalogue

LEVELS: Final = tuple(level.value for level in Level)
"""The values ``[training] level`` may take, as ``init --training`` and ``training`` accept them."""

_HEADER: Final = re.compile(r"^[ \t]*\[[ \t]*training[ \t]*\][ \t]*(?:#.*)?$", re.MULTILINE)
_NEXT_HEADER: Final = re.compile(r"^[ \t]*\[", re.MULTILINE)
_LEVEL_LINE: Final = re.compile(
    r"""^([ \t]*level[ \t]*=[ \t]*)("(?:[^"\\\n]|\\.)*"|'[^'\n]*')""", re.MULTILINE
)


class UnknownNameError(LookupError):
    """No strategy or lesson has the name given. It carries up to three close names."""

    def __init__(self, wanted: str, closest: tuple[str, ...], *, kind: str) -> None:
        hint = f"; the closest: {', '.join(closest)}" if closest else ""
        super().__init__(f"no {kind} named {wanted!r}{hint}")
        self.kind = kind
        self.wanted = wanted
        self.closest = closest

    @classmethod
    def among(cls, kind: str, wanted: str, names: Iterable[str]) -> UnknownNameError:
        """The error for *wanted*, with the names closest to it (``difflib``)."""
        return cls(wanted, tuple(get_close_matches(wanted, sorted(names), n=3)), kind=kind)


@dataclass(slots=True)
class Page:
    """A command's output as it is built: its lines, and the keys of what they showed, in the
    order they first appeared (T1 spec §6 item 4)."""

    lines: list[str] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)

    def add(self, line: str = "", *keys: str) -> None:
        """Add *line*, which shows the figures or notes that *keys* name."""
        self.lines.append(line)
        self.keys.extend(key for key in keys if key not in self.keys)


def training_level(table: Mapping[str, object]) -> Level:
    """The ``[training]`` table, checked with the configuration's rules: only ``level``, one of
    ``LEVELS``. With no level, it is ``new`` (M5 spec §4.2)."""
    where = Where(CONFIG_FILE, "training")
    unknown = sorted(set(table) - {"level"})
    if unknown:
        msg = f"{where}: unknown key {unknown[0]!r}"
        raise DataFileError(msg)
    value = table.get("level", Level.NEW.value)
    if not isinstance(value, str) or value not in LEVELS:
        msg = f"{where}: level must be one of {', '.join(LEVELS)}, got {value!r}"
        raise DataFileError(msg)
    return Level(value)


def render(page: Page, training: Mapping[str, object]) -> str:
    """*page*, then the explanation of its keys at the level *training* sets, then the
    disclaimer footer, which is the same at every level."""
    parts = ["\n".join(page.lines)]
    explanation = explain(catalogue(), page.keys, training_level(training), APP)
    if explanation:
        parts.append(explanation)
    parts.append(DISCLAIMER)
    return "\n\n".join(parts) + "\n"


def course_page() -> Page:
    """``learn``: every module and its lessons, in course order (T1 spec §6 item 3)."""
    return show_course(catalogue().course())


def show_course(modules: Iterable[Module]) -> Page:
    """Each of *modules* and its lessons; a module with none says so."""
    page = Page()
    for index, module in enumerate(modules):
        if index:
            page.add()
        page.add(f"Module {module.number}: {module.title}")
        for lesson in module.lessons:
            page.add(f"  {lesson.id}: {lesson.title}")
        if not module.lessons:
            page.add("  (no lessons yet)")
    page.add()
    page.add(f"Read one with: {APP} learn <id>")
    return page


def lesson_page(lesson_id: str) -> Page:
    """``learn <id>``: the lesson's title, its body, then its "see also" ids."""
    lessons = catalogue()
    try:
        lesson = lessons.lesson(lesson_id)
    except LessonNotFoundError as error:
        raise UnknownNameError(lesson_id, error.closest, kind="lesson") from None
    return show_lesson(lesson)


def show_lesson(lesson: Lesson) -> Page:
    """*lesson*'s title, its body, then its "see also" ids when it has any."""
    page = Page()
    page.add(lesson.title)
    page.add()
    page.add(lesson.body.strip("\n"))
    if lesson.see_also:
        page.add()
        page.add(f"See also: {', '.join(lesson.see_also)}")
    return page


def with_training_level(text: str, level: str) -> str:
    """*text*, a configuration, with its ``[training] level`` set to *level* and every other
    byte unchanged (M5 spec §5.2). The table or the line is added when it is absent."""
    value = f'"{Level(level).value}"'
    header = _HEADER.search(text)
    if header is None:
        ending = "" if text.endswith("\n") or not text else "\n"
        return f"{text}{ending}\n[training]\nlevel = {value}\n"
    start = header.end()
    following = _NEXT_HEADER.search(text, start + 1)
    end = len(text) if following is None else following.start()
    line = _LEVEL_LINE.search(text, start, end)
    if line is None:
        return f"{text[:start]}\nlevel = {value}{text[start:]}"
    return f"{text[: line.start(2)]}{value}{text[line.end(2) :]}"
