"""steadyhand_idx.training: the IDX distribution's lessons and its course (T1 spec §4.2, §4.3).

Like ``steadyhand.training``, only the output layer may import it, and it imports nothing that
decides what to trade (T1 spec §5).
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

from steadyhand.training import LESSONS as ENGINE_LESSONS
from steadyhand.training import Catalogue

COURSE: Traversable = files(__name__) / "course.toml"
"""The course's module list, shipped inside the wheel."""

LESSONS: Traversable = files(__name__) / "lessons" / "en"
"""The IDX lessons, shipped inside the wheel."""


def catalogue() -> Catalogue:
    """Both packages' lessons and the course, loaded and checked (T1 spec §7)."""
    return Catalogue.load([ENGINE_LESSONS, LESSONS], COURSE)


__all__ = ["COURSE", "LESSONS", "catalogue"]
