"""steadyhand_idx.training: the IDX distribution's lessons and its course (T1 spec §4.2, §4.3).

Like ``steadyhand.training``, only the output layer may import it, and it imports nothing that
decides what to trade (T1 spec §5).
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

COURSE: Traversable = files(__name__) / "course.toml"
"""The course's module list, shipped inside the wheel."""

__all__ = ["COURSE"]
