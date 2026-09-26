"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

from steadyhand.broker import Broker, FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import (
    PAY_LAG_TRADING_DAYS,
    CorporateOutcome,
    Entitlement,
    Holdings,
    apply_actions,
)
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
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
from steadyhand.outcomes import Cut, Rejected
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
from steadyhand.risk import Checked, Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.strategies import (
    STRATEGIES,
    BuyAndHold,
    Decision,
    InvalidWeightsError,
    Memory,
    Strategy,
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
from steadyhand.universe import Universe
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

__version__: str = version("steadyhand")

__all__ = [
    "DISCLAIMER",
    "IDR",
    "MAX_MINOR_UNITS",
    "PAY_LAG_TRADING_DAYS",
    "STRATEGIES",
    "Bar",
    "Broker",
    "BuyAndHold",
    "CashDividend",
    "CashMovement",
    "Checked",
    "ChronologyError",
    "CompoundingSizer",
    "CorporateAction",
    "CorporateOutcome",
    "Costs",
    "Currency",
    "CurrencyMismatchError",
    "Cut",
    "DataSource",
    "DataUnavailableError",
    "Decision",
    "Entitlement",
    "Fill",
    "FillResult",
    "FillSettings",
    "Halt",
    "Holdings",
    "Instrument",
    "InsufficientCashError",
    "InsufficientSharesError",
    "InvalidBarError",
    "InvalidWeightsError",
    "LookAheadError",
    "MarketRules",
    "MarketView",
    "Memory",
    "MissingPriceError",
    "Money",
    "MovementKind",
    "NegativeProceedsError",
    "Opening",
    "Order",
    "OrderAck",
    "OtherAction",
    "Portfolio",
    "PortfolioView",
    "Position",
    "PriceHistory",
    "Rejected",
    "RiskLimits",
    "RiskManager",
    "Rounding",
    "Side",
    "SimulatedBroker",
    "Sizer",
    "Split",
    "Strategy",
    "Tradable",
    "UnavailableDaysError",
    "UnitValue",
    "Universe",
    "UnsupportedDateError",
    "__version__",
    "apply_actions",
]
