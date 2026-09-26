"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

from steadyhand.backtest import (
    BacktestResult,
    BacktestSettings,
    Market,
    NoTradingDaysError,
    RunResult,
    UniverseCoverageError,
    backtest,
)
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
from steadyhand.engine import (
    DataValidationError,
    DayInputs,
    DayOrderError,
    DayReport,
    EngineSettings,
    EngineState,
    run_day,
)
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
    "BacktestResult",
    "BacktestSettings",
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
    "DataValidationError",
    "DayInputs",
    "DayOrderError",
    "DayReport",
    "Decision",
    "EngineSettings",
    "EngineState",
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
    "Market",
    "MarketRules",
    "MarketView",
    "Memory",
    "MissingPriceError",
    "Money",
    "MovementKind",
    "NegativeProceedsError",
    "NoTradingDaysError",
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
    "RunResult",
    "Side",
    "SimulatedBroker",
    "Sizer",
    "Split",
    "Strategy",
    "Tradable",
    "UnavailableDaysError",
    "UnitValue",
    "Universe",
    "UniverseCoverageError",
    "UnsupportedDateError",
    "__version__",
    "apply_actions",
    "backtest",
    "run_day",
]
