"""Every strategy steadyhand ships, by the name the configuration uses.

Each one must have a complete guide at ``docs/strategies/<name>.md`` (core spec §8, §10.1).
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Final

from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy

STRATEGIES: Final[Mapping[str, Callable[[], Strategy]]] = MappingProxyType(
    {"buy-and-hold": BuyAndHold}
)
