"""What happened to an order that did not go through as it was placed.

The broker, the sizer and the risk manager all report the same two things, each with a reason
that the day's report prints (core spec §6.1: every dropped or cut order carries a reason).
"""

from __future__ import annotations

from dataclasses import dataclass

from steadyhand._validate import require_int, require_type
from steadyhand.types import Order


def _require_reason(reason: object, order: Order) -> None:
    require_type(reason, str, "reason")
    if not str(reason).strip():
        msg = f"a {order.side.value} order for {order.instrument.symbol} needs a reason"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Rejected:
    """An order that will not trade at all, and why."""

    order: Order
    reason: str

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        _require_reason(self.reason, self.order)


@dataclass(frozen=True, slots=True)
class Cut:
    """An order made smaller, to ``quantity`` shares, and why."""

    order: Order
    quantity: int
    reason: str

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        require_int(self.quantity, "cut quantity", minimum=1)
        if self.quantity >= self.order.quantity:
            msg = f"a cut must leave fewer than {self.order.quantity} shares, got {self.quantity}"
            raise ValueError(msg)
        _require_reason(self.reason, self.order)
