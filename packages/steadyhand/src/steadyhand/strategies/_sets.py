"""A set of stocks as a strategy remembers it: ``MARKET:SYMBOL`` entries separated by spaces,
in order, so the same set is always the same text."""

from __future__ import annotations

from collections.abc import Iterable

from steadyhand.money import Currency
from steadyhand.types import Instrument


def write_set(stocks: Iterable[Instrument]) -> str:
    return " ".join(sorted(f"{stock.market}:{stock.symbol}" for stock in stocks))


def read_set(text: str, currency: Currency) -> frozenset[Instrument]:
    entries = (entry.split(":") for entry in text.split())
    return frozenset(Instrument(symbol, market, currency) for market, symbol in entries)
