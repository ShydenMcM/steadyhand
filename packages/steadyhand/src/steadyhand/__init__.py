"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError
from steadyhand.disclaimer import DISCLAIMER
from steadyhand.market import MarketRules, UnsupportedDateError
from steadyhand.money import (
    IDR,
    MAX_MINOR_UNITS,
    Currency,
    CurrencyMismatchError,
    Money,
    Rounding,
)
from steadyhand.portfolio import (
    CashMovement,
    ChronologyError,
    InsufficientCashError,
    InsufficientSharesError,
    MissingPriceError,
    MovementKind,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    InvalidBarError,
    Order,
    OrderAck,
    OtherAction,
    Position,
    Side,
    Split,
)

__version__: str = version("steadyhand")

__all__ = [
    "DISCLAIMER",
    "IDR",
    "MAX_MINOR_UNITS",
    "Bar",
    "Broker",
    "CashDividend",
    "CashMovement",
    "ChronologyError",
    "CorporateAction",
    "Costs",
    "Currency",
    "CurrencyMismatchError",
    "DataSource",
    "DataUnavailableError",
    "Fill",
    "Instrument",
    "InsufficientCashError",
    "InsufficientSharesError",
    "InvalidBarError",
    "MarketRules",
    "MissingPriceError",
    "Money",
    "MovementKind",
    "NegativeProceedsError",
    "Order",
    "OrderAck",
    "OtherAction",
    "Portfolio",
    "Position",
    "Rounding",
    "Side",
    "Split",
    "UnsupportedDateError",
    "__version__",
]
