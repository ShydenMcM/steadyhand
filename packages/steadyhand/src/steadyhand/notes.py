"""Notes: a stable key and a sentence, for anything a report says beyond its figures (M4 spec §7).

A key is a dotted lowercase identifier that is never reworded, so the training sub-project can
attach a lesson to it; the text is free to change. Every key is a constant below, named after its
value, and every ``Note`` in the engine is built from one of them, never from a literal
(``tests/meta/test_note_keys.py``). This module imports nothing from the rest of the engine, so
any engine module can use it without an import cycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from steadyhand._validate import require_type

INCOME_GROWTH_SHORT_HISTORY = "income.growth.short_history"
"""A holding whose dividend growth could not be measured, which therefore counts as 0%."""

INCOME_PROJECTION_COSTS_IGNORED = "income.projection.costs_ignored"
"""On every projection: the trading costs of reinvesting are left out."""

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")


@dataclass(frozen=True, slots=True)
class Note:
    """Something a report says in words, under a key that never changes."""

    key: str
    text: str

    def __post_init__(self) -> None:
        require_type(self.key, str, "key")
        require_type(self.text, str, "text")
        if _KEY.fullmatch(self.key) is None:
            msg = f"a note key is a dotted lowercase identifier, got {self.key!r}"
            raise ValueError(msg)
        if not self.text.strip():
            msg = f"the note {self.key} has no text"
            raise ValueError(msg)
