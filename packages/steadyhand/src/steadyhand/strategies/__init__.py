"""Strategies: the Strategy protocol, the shipped strategies and their registry."""

from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Decision, InvalidWeightsError, Memory, Strategy
from steadyhand.strategies.registry import (
    GUIDES,
    STRATEGIES,
    Registered,
    Setting,
    Turnover,
    guide,
)

__all__ = [
    "GUIDES",
    "STRATEGIES",
    "BuyAndHold",
    "Decision",
    "InvalidWeightsError",
    "Memory",
    "Registered",
    "Setting",
    "Strategy",
    "Turnover",
    "guide",
]
