"""Every strategy steadyhand ships, by the name the configuration uses.

Each one has a one-line summary, how much it trades, and a complete plain-English guide in
``guides/<name>.md``, which ships inside the package (core spec §8, §10.1; M5 spec §5.5, §5.6).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from importlib.resources.abc import Traversable
from types import MappingProxyType
from typing import Final

from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy


class Turnover(StrEnum):
    """How much a strategy trades, as ``steadyhand-idx strategies`` shows it."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Registered:
    """One shipped strategy: what makes it, a one-line summary and how much it trades.

    Calling the entry makes the strategy, as calling the class did before. The registry is
    fixed data, so ``tests/engine/test_registry.py`` checks every summary and turnover.
    """

    make: Callable[[], Strategy]
    summary: str
    turnover: Turnover

    def __call__(self) -> Strategy:
        return self.make()


STRATEGIES: Final[Mapping[str, Registered]] = MappingProxyType(
    {
        "buy-and-hold": Registered(
            BuyAndHold,
            "Buys every stock it can on its first day in equal parts, then holds and reinvests.",
            Turnover.LOW,
        ),
    }
)

GUIDES: Final[Traversable] = files("steadyhand.strategies") / "guides"
"""The strategy guides, shipped inside the wheel."""


def guide(name: str) -> str:
    """The plain-English guide to the registered strategy *name*."""
    if name not in STRATEGIES:
        msg = f"no registered strategy is named {name!r}"
        raise KeyError(msg)
    return (GUIDES / f"{name}.md").read_text(encoding="utf-8")
