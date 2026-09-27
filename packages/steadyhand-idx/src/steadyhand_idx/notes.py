"""The IDX distribution's note keys (M4 spec §7, T1 spec §3.1).

Each key follows the engine's rules in ``steadyhand.notes``: a dotted lowercase identifier that is
never reworded, held in a constant named after its value, so a lesson can attach to it. The
engine's key meta-test (``tests/meta/test_note_keys.py``) reads this module as well as the
engine's, so a key is never defined twice across the two packages.
"""

from __future__ import annotations

UNIVERSE_SURVIVORSHIP_GAP = "universe.survivorship.gap"
"""The LQ45 record has no list between two dates more than one review apart."""
