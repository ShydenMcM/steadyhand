"""How much explanation goes under a command's output, by the user's level (T1 spec §6).

``explain`` returns the text and the caller prints it. The level changes only how much is
explained; nothing here can see, or change, what a command suggests (T1 spec §5).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from steadyhand._validate import require_type
from steadyhand.training.catalogue import Catalogue, Lesson

_HEADING = "What this means"
_BULLET = "•"


class Level(StrEnum):
    """How much a user wants explained. The values are what ``steadyhand.toml`` stores."""

    OFF = "off"
    NEW = "new"
    SOME = "some"
    EXPERIENCED = "experienced"


def explain(catalogue: Catalogue, keys: Iterable[str], level: Level, program: str) -> str:
    """The explanation for the keys a command's output showed, or ``""`` (T1 spec §6 item 4).

    *keys* come in the order the output first showed them. Each lesson appears once, however
    many of its keys were shown. Every key is looked up whatever the level, so a key with no
    lesson raises ``LessonNotFoundError`` at every level: it is a bug, not a setting.
    """
    require_type(catalogue, Catalogue, "catalogue")
    require_type(level, Level, "level")
    require_type(program, str, "program")
    if isinstance(keys, str):
        msg = "keys is the keys the output showed, not one key"
        raise TypeError(msg)
    if not program.strip():
        msg = "program is the command the user types, and it is blank"
        raise ValueError(msg)
    lessons: dict[str, Lesson] = {}
    for key in keys:
        require_type(key, str, "a key")
        lesson = catalogue.for_key(key)
        lessons.setdefault(lesson.id, lesson)
    if not lessons or level in (Level.OFF, Level.EXPERIENCED):
        return ""
    if level is Level.SOME:
        return f"Learn more with {program} learn: {', '.join(lessons)}"
    lines = [
        f"{_BULLET} {lesson.title}: {lesson.summary} More: {program} learn {lesson.id}"
        for lesson in lessons.values()
    ]
    return "\n".join([_HEADING, *lines])
