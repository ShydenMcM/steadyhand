"""The IDX distribution's note keys (M4 spec §7, T1 spec §3.1).

Each key follows the engine's rules in ``steadyhand.notes``: a dotted lowercase identifier that is
never reworded, held in a constant named after its value, so a lesson can attach to it. The
engine's key meta-test (``tests/meta/test_note_keys.py``) reads this module as well as the
engine's, so a key is never defined twice across the two packages.
"""

from __future__ import annotations

UNIVERSE_SURVIVORSHIP_GAP = "universe.survivorship.gap"
"""The LQ45 record has no list between two dates more than one review apart."""

PAPER_ACCOUNT_OPENED = "paper.account.opened"
"""The first ``paper run`` opened the paper account with the starting cash and a strategy."""

PAPER_ORDER_CUT = "paper.order.cut"
"""An order the strategy wanted was made smaller, and why."""

PAPER_ORDER_QUEUED = "paper.order.queued"
"""An order was queued for the next trading day's open."""

PAPER_ORDER_SKIPPED = "paper.order.skipped"
"""An order the strategy wanted was not placed at all, and why."""

PAPER_RUN_STOPPED = "paper.run.stopped"
"""A ``paper run`` stopped on a day whose data could not be trusted; that day was not saved."""

PAPER_SETTING_CHANGED = "paper.setting.changed"
"""A setting changed in ``steadyhand.toml``; it applies from the next day run."""

PAPER_SETTING_STARTING_CASH_IGNORED = "paper.setting.starting_cash_ignored"
"""The starting cash changed after the account opened, so the change has no effect."""
