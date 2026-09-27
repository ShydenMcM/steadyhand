"""The lesson catalogue: the lesson files, the course, and the rules they keep (T1 spec §4, §7).

A lesson is a Markdown file ``<id>.md`` whose TOML header sits between two ``+++`` lines.
``Catalogue.load`` reads every lesson under the roots it is given and the course file, checks
every rule of §4.1, and raises ``LessonError`` naming the file and the field of the first rule
broken. It reads only what it is given, as UTF-8 with or without a byte-order mark. Whether a
key a lesson explains exists, and whether a ``sources`` path exists, is for the catalogue guards
to check against the repo: an installed copy has neither the key modules' source nor the
repo's paths.
"""

from __future__ import annotations

import difflib
import re
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import cast

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
_SLUG = re.compile(r"[a-z]+(-[a-z]+)*")
_FENCE = "+++"
_TITLE_LIMIT = 60
_SUMMARY_LIMIT = 160
_CLOSEST = 3
_FIELDS = ("id", "title", "summary", "explains", "module", "position", "see_also", "sources")
_REQUIRED = ("id", "title", "summary", "explains")
_MODULE_FIELDS = ("number", "slug", "title")


class LessonError(ValueError):
    """A lesson file or the course file breaks a rule (T1 spec §4.1)."""

    def __init__(self, origin: str, field: str, problem: str) -> None:
        super().__init__(f"{origin}: {field}: {problem}")
        self.origin = origin
        self.field = field
        self.problem = problem


class LessonNotFoundError(LookupError):
    """No lesson has the id, or explains the key, that was asked for."""

    def __init__(self, wanted: str, closest: tuple[str, ...]) -> None:
        hint = f"; the closest: {', '.join(closest)}" if closest else ""
        super().__init__(f"no lesson for {wanted!r}{hint}")
        self.wanted = wanted
        self.closest = closest


@dataclass(frozen=True, slots=True)
class Lesson:
    """One lesson: its header fields, its Markdown body, and the file it came from."""

    id: str
    title: str
    summary: str
    explains: tuple[str, ...]
    module: str | None
    position: int | None
    see_also: tuple[str, ...]
    sources: tuple[str, ...]
    body: str
    origin: str


@dataclass(frozen=True, slots=True)
class Module:
    """One course module, and its lessons in course order. A module may be empty for now."""

    number: int
    slug: str
    title: str
    lessons: tuple[Lesson, ...]


class Catalogue:
    """Every lesson and the course, checked against each other. Build one with ``load``."""

    __slots__ = ("_by_id", "_by_key", "_modules")

    def __init__(self, lessons: Mapping[str, Lesson], modules: tuple[Module, ...]) -> None:
        self._by_id = dict(lessons)
        self._by_key = {key: lesson for lesson in lessons.values() for key in lesson.explains}
        self._modules = modules

    @classmethod
    def load(cls, roots: Iterable[Traversable], course: Traversable) -> Catalogue:
        """Read every ``*.md`` under each root and the course file, and check every rule."""
        slugs = _read_course(course)
        by_id: dict[str, Lesson] = {}
        by_key: dict[str, Lesson] = {}
        for root in roots:
            if not root.is_dir():
                raise LessonError(str(root), "root", "is not a folder")
            for file in _markdown_files(root):
                lesson = _read_lesson(file)
                first = by_id.setdefault(lesson.id, lesson)
                if first is not lesson:
                    raise LessonError(lesson.origin, "id", f"{lesson.id} is also {first.origin}")
                for key in lesson.explains:
                    owner = by_key.setdefault(key, lesson)
                    if owner is not lesson:
                        msg = f"{key} is already explained by {owner.id}"
                        raise LessonError(lesson.origin, "explains", msg)
        for lesson in by_id.values():
            for other in lesson.see_also:
                if other not in by_id:
                    raise LessonError(lesson.origin, "see_also", f"no lesson {other!r}")
        return cls(by_id, _modules(slugs, by_id.values()))

    def lessons(self) -> tuple[Lesson, ...]:
        """Every lesson, by id."""
        return tuple(self._by_id[name] for name in sorted(self._by_id))

    def lesson(self, lesson_id: str) -> Lesson:
        """The lesson with *lesson_id*, or ``LessonNotFoundError`` naming the closest ids."""
        found = self._by_id.get(lesson_id)
        if found is None:
            raise LessonNotFoundError(lesson_id, _closest(lesson_id, self._by_id))
        return found

    def for_key(self, key: str) -> Lesson:
        """The lesson that explains *key*. A key with no lesson is a bug (T1 spec §7)."""
        found = self._by_key.get(key)
        if found is None:
            raise LessonNotFoundError(key, _closest(key, self._by_key))
        return found

    def course(self) -> tuple[Module, ...]:
        """The course's modules, in order."""
        return self._modules


def _closest(wanted: str, names: Iterable[str]) -> tuple[str, ...]:
    return tuple(difflib.get_close_matches(wanted, sorted(names), n=_CLOSEST))


def _markdown_files(root: Traversable) -> Iterator[Traversable]:
    for entry in sorted(root.iterdir(), key=lambda found: found.name):
        if entry.is_dir():
            yield from _markdown_files(entry)
        elif entry.name.endswith(".md"):
            yield entry


def _read_lesson(file: Traversable) -> Lesson:
    origin = str(file)
    header, body = _split(file.read_text(encoding="utf-8-sig"), origin)
    for name in sorted(header):
        if name not in _FIELDS:
            raise LessonError(origin, name, "is not a lesson field")
    for name in _REQUIRED:
        if name not in header:
            raise LessonError(origin, name, "is required")
    lesson_id = _key(header["id"], origin, "id")
    if lesson_id != file.name.removesuffix(".md"):
        raise LessonError(origin, "id", f"{lesson_id} is not the file's name")
    module = header.get("module")
    position = header.get("position")
    if (module is None) != (position is None):
        missing = "position" if position is None else "module"
        raise LessonError(origin, missing, "module and position are given together or not at all")
    if module is not None and (not isinstance(module, str) or not _SLUG.fullmatch(module)):
        raise LessonError(origin, "module", f"{module!r} is not a module slug")
    if position is not None and (type(position) is not int or position < 1):
        raise LessonError(origin, "position", f"{position!r} is not a whole number from 1")
    see_also = _keys(header.get("see_also", []), origin, "see_also")
    if lesson_id in see_also:
        raise LessonError(origin, "see_also", "a lesson does not list itself")
    return Lesson(
        id=lesson_id,
        title=_line(header["title"], origin, "title", _TITLE_LIMIT),
        summary=_summary(header["summary"], origin),
        explains=_keys(header["explains"], origin, "explains"),
        module=module,
        position=position,
        see_also=see_also,
        sources=_strings(header.get("sources", []), origin, "sources"),
        body=body,
        origin=origin,
    )


def _split(text: str, origin: str) -> tuple[dict[str, object], str]:
    """The TOML header and the body of a lesson file."""
    lines = text.splitlines()
    if not lines or lines[0] != _FENCE:
        raise LessonError(origin, "header", f"the file does not start with a {_FENCE} line")
    try:
        end = lines.index(_FENCE, 1)
    except ValueError:
        raise LessonError(origin, "header", f"the header has no closing {_FENCE} line") from None
    try:
        header = tomllib.loads("\n".join(lines[1:end]))
    except tomllib.TOMLDecodeError as error:
        raise LessonError(origin, "header", f"is not valid TOML ({error})") from None
    body = "\n".join(lines[end + 1 :]).strip()
    if not body:
        raise LessonError(origin, "body", "the lesson has no text")
    return header, body


def _line(value: object, origin: str, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise LessonError(origin, field, "is not text")
    if not value.strip() or len(value) > limit or "\n" in value:
        raise LessonError(origin, field, f"is not one line of 1 to {limit} characters")
    return value


def _summary(value: object, origin: str) -> str:
    summary = _line(value, origin, "summary", _SUMMARY_LIMIT)
    if not summary.endswith(".") or ". " in summary:
        raise LessonError(origin, "summary", "is not one sentence ending in a full stop")
    return summary


def _key(value: object, origin: str, field: str) -> str:
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise LessonError(origin, field, f"{value!r} is not a dotted lowercase identifier")
    return value


def _strings(value: object, origin: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise LessonError(origin, field, "is not a list")
    items = tuple(cast("list[object]", value))
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise LessonError(origin, field, f"{item!r} is not text")
    if len(set(items)) != len(items):
        raise LessonError(origin, field, "lists an entry twice")
    return cast("tuple[str, ...]", items)


def _keys(value: object, origin: str, field: str) -> tuple[str, ...]:
    return tuple(_key(item, origin, field) for item in _strings(value, origin, field))


def _read_course(course: Traversable) -> tuple[tuple[int, str, str], ...]:
    """The course file's modules as (number, slug, title), numbered 1, 2, 3 … in file order."""
    origin = str(course)
    try:
        data = tomllib.loads(course.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as error:
        raise LessonError(origin, "course", f"is not valid TOML ({error})") from None
    extra = sorted(set(data) - {"module"})
    if extra:
        raise LessonError(origin, extra[0], "is not a course field")
    entries = data.get("module")
    if not isinstance(entries, list) or not entries:
        raise LessonError(origin, "module", "the course lists no modules")
    modules: list[tuple[int, str, str]] = []
    for number, entry in enumerate(cast("list[object]", entries), start=1):
        where = f"module[{number}]"
        if not isinstance(entry, dict):
            raise LessonError(origin, where, "is not a table")
        fields = cast("dict[str, object]", entry)
        for name in sorted(set(fields) ^ set(_MODULE_FIELDS)):
            problem = "is not a module field" if name in fields else "is required"
            raise LessonError(origin, f"{where}.{name}", problem)
        if type(fields["number"]) is not int or fields["number"] != number:
            raise LessonError(origin, f"{where}.number", f"is not {number}")
        slug = fields["slug"]
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
            raise LessonError(origin, f"{where}.slug", f"{slug!r} is not a module slug")
        if any(slug == seen for _, seen, _ in modules):
            raise LessonError(origin, f"{where}.slug", f"{slug} is listed twice")
        title = _line(fields["title"], origin, f"{where}.title", _TITLE_LIMIT)
        modules.append((number, slug, title))
    return tuple(modules)


def _modules(
    course: tuple[tuple[int, str, str], ...], lessons: Iterable[Lesson]
) -> tuple[Module, ...]:
    """Each course module with its lessons, positions running 1, 2, 3 … with no gap or repeat."""
    placed: dict[str, dict[int, Lesson]] = {slug: {} for _, slug, _ in course}
    for lesson in sorted(lessons, key=lambda found: found.origin):
        if lesson.module is None or lesson.position is None:
            continue
        if lesson.module not in placed:
            raise LessonError(lesson.origin, "module", f"{lesson.module} is not in the course")
        slots = placed[lesson.module]
        other = slots.setdefault(lesson.position, lesson)
        if other is not lesson:
            msg = f"{lesson.module} already has {other.id} at {lesson.position}"
            raise LessonError(lesson.origin, "position", msg)
    for slug, slots in placed.items():
        for expected, position in enumerate(sorted(slots), start=1):
            if position != expected:
                msg = f"{slug} has no lesson at {expected}, so {position} leaves a gap"
                raise LessonError(slots[position].origin, "position", msg)
    return tuple(
        Module(number, slug, title, tuple(placed[slug][p] for p in sorted(placed[slug])))
        for number, slug, title in course
    )
