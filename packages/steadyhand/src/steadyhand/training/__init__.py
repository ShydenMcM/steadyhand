"""steadyhand.training: lessons that explain what a report shows (T1 spec).

Only the output layer may import this package, and it imports nothing that decides what to
trade (T1 spec §5): the level a user picks changes how much is explained, never what the tool
suggests. It uses the standard library only.
"""

from steadyhand.training.catalogue import (
    Catalogue,
    Lesson,
    LessonError,
    LessonNotFoundError,
    Module,
)
from steadyhand.training.render import Level, explain

__all__ = [
    "Catalogue",
    "Lesson",
    "LessonError",
    "LessonNotFoundError",
    "Level",
    "Module",
    "explain",
]
