"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

__version__: str = version("steadyhand")

__all__ = ["__version__"]
