"""The catalogue guards that need the repo (T1 spec §8), as functions over a loaded catalogue.

``Catalogue.load`` checks every rule a lesson file can break on its own. What is left needs the
repo: the key sets (derived from the key modules' source by ``key_walk``), the paths ``sources``
cites, and the disclaimer. Each function returns its findings, so a test asserts ``[]`` and a
failure names what is wrong. Until the real lessons land they run against the fixture
catalogue; then against both packages' lesson folders.
"""

from collections.abc import Set
from pathlib import Path, PurePosixPath

from markdown_text import normalised

from steadyhand.training import Catalogue

SECTION = " §"
FIRST_MODULE = "start-here"


def unexplained(catalogue: Catalogue, keys: Set[str]) -> list[str]:
    """Every key that no lesson explains."""
    explained = {key for lesson in catalogue.lessons() for key in lesson.explains}
    return sorted(keys - explained)


def unknown(catalogue: Catalogue, keys: Set[str]) -> list[str]:
    """Every key a lesson explains that is not a note or term key, as ``id: key``."""
    return [
        f"{lesson.id}: {key}"
        for lesson in catalogue.lessons()
        for key in lesson.explains
        if key not in keys
    ]


def missing_sources(catalogue: Catalogue, root: Path) -> list[str]:
    """Every ``sources`` entry whose path is not a file in the repo, as ``id: entry``."""
    found: list[str] = []
    for lesson in catalogue.lessons():
        for source in lesson.sources:
            path = PurePosixPath(source.split(SECTION, 1)[0])
            if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                found.append(f"{lesson.id}: {source}")
    return found


def start_here_problems(catalogue: Catalogue, disclaimer: str) -> list[str]:
    """Why the course does not open with a lesson carrying the disclaimer verbatim, if it
    does not. The text is compared as a reader sees it, however the Markdown wraps it."""
    modules = catalogue.course()
    if not modules or modules[0].slug != FIRST_MODULE:
        return [f"the course does not start with {FIRST_MODULE}"]
    if not modules[0].lessons:
        return [f"{FIRST_MODULE} has no lesson"]
    first = modules[0].lessons[0]
    if disclaimer not in normalised(first.body):
        return [f"{first.id} does not carry the disclaimer"]
    return []
