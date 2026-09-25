"""The Broker protocol: where orders go and fills come from."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.types import Fill, Order, OrderAck


@runtime_checkable
class Broker(Protocol):
    """Accepts orders and reports what filled. The simulated broker arrives in M3."""

    def submit(self, orders: Sequence[Order], on: date) -> Sequence[OrderAck]:
        """Queue *orders* placed on *on*. Returns one acknowledgement per order, in order."""
        ...

    def fills(self, on: date) -> Sequence[Fill]:
        """Everything that filled on *on*."""
        ...
