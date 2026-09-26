"""The Strategy protocol: a strategy says what share of the portfolio each stock should be.

Strategies return target weights, not orders (core spec §4.3). The sizer and the risk manager
turn weights into legal orders, so every rule about lots, ticks, cash and caps lives in one
tested place.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

from steadyhand._validate import require_type
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

type Memory = Mapping[str, str]
"""What a strategy keeps from one day to the next, as text, so M5 can save it with the state."""


class InvalidWeightsError(ValueError):
    """A strategy returned weights that cannot be a portfolio. It is a bug in the strategy."""


@dataclass(frozen=True, slots=True)
class Decision:
    """A strategy's answer for one day: target weights, and what to remember until tomorrow.

    A stock missing from ``weights`` is targeted at zero. Weights are ``Decimal``, none is
    negative, and together they are at most 1; the rest is held as cash.
    """

    weights: Mapping[Instrument, Decimal]
    memory: Memory = field(default_factory=dict)

    def __post_init__(self) -> None:
        total = Decimal(0)
        for instrument, weight in self.weights.items():
            require_type(instrument, Instrument, "weighted stock")
            if not isinstance(weight, Decimal):
                msg = (
                    f"{instrument.symbol}: a weight must be a Decimal, got {type(weight).__name__}"
                )
                raise InvalidWeightsError(msg)
            if not weight.is_finite() or weight < 0:
                msg = f"{instrument.symbol}: a weight must be finite and not negative, got {weight}"
                raise InvalidWeightsError(msg)
            total += weight
        if total > 1:
            msg = f"weights sum to {total}, more than 1"
            raise InvalidWeightsError(msg)
        for key, value in self.memory.items():
            require_type(key, str, "memory key")
            require_type(value, str, "memory value")


@runtime_checkable
class Strategy(Protocol):
    """A way of choosing stocks. Each registered strategy has a plain-English guide (core §8)."""

    @property
    def name(self) -> str:
        """The name the configuration and the guide use, such as ``buy-and-hold``."""
        ...

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        """Today's target weights, given the market up to today and yesterday's memory."""
        ...
