"""What happened to an order that did not go through as it was placed.

The broker, the sizer and the risk manager all report the same two things, each with a reason
that the day's report prints (core spec §6.1: every dropped or cut order carries a reason). A
reason is a ``Note``: a sentence under a key that never changes, so a lesson can explain it
(M4 spec §7, M5 spec §7.4).
"""

from __future__ import annotations

from dataclasses import dataclass

from steadyhand._validate import require_int, require_type
from steadyhand.notes import Note
from steadyhand.types import Order


@dataclass(frozen=True, slots=True)
class Rejected:
    """An order that will not trade at all, and why."""

    order: Order
    reason: Note

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        require_type(self.reason, Note, "reason")


@dataclass(frozen=True, slots=True)
class Cut:
    """An order made smaller, to ``quantity`` shares, and why."""

    order: Order
    quantity: int
    reason: Note

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        require_int(self.quantity, "cut quantity", minimum=1)
        if self.quantity >= self.order.quantity:
            msg = f"a cut must leave fewer than {self.order.quantity} shares, got {self.quantity}"
            raise ValueError(msg)
        require_type(self.reason, Note, "reason")
