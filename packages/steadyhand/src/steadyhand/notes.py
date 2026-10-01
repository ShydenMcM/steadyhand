"""Notes: a stable key and a sentence, for anything a report says beyond its figures (M4 spec §7).

A key is a dotted lowercase identifier that is never reworded, so the training sub-project can
attach a lesson to it; the text is free to change. Every key is a constant below (or, for the
IDX distribution, in ``steadyhand_idx.notes``), named after its value, and every ``Note`` in
either package is built from one of them, never from a literal
(``tests/meta/test_note_keys.py``). Figures have keys too, in ``steadyhand.terms``. This module
imports nothing from the rest of the engine, so any engine module can use it without an import
cycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from steadyhand._validate import require_type

CORPORATE_SPLIT_FRACTION_DROPPED = "corporate.split.fraction_dropped"
"""A split left a fraction of a share, which is dropped: cash in lieu is not modelled."""

DATA_BAR_MISSING = "data.bar.missing"
"""A member or a holding has no bar on a day, so it is not traded that day."""

DATA_BAR_REFUSED = "data.bar.refused"
"""The data source refused a stock's days in a backtest, so it was not traded on them."""

DATA_DIVIDENDS_HISTORY_REFUSED = "data.dividends.history_refused"
"""The data source refused a stock's corporate actions before the run, so its dividend history
is incomplete (M6 spec §4.3)."""

EXEMPTION_CLAIM_BROKEN = "exemption.claim_broken"
"""Protected dividend money left the portfolio past the settlement grace, so its tax is booked."""

EXEMPTION_DEADLINE_MISSED = "exemption.deadline_missed"
"""Part of a dividend claim was not reinvested by its deadline, so its tax is booked now."""

INCOME_GROWTH_SHORT_HISTORY = "income.growth.short_history"
"""A holding whose dividend growth could not be measured, which therefore counts as 0%."""

INCOME_PROJECTION_COSTS_IGNORED = "income.projection.costs_ignored"
"""On every projection: the trading costs of reinvesting are left out."""

RISK_HALT_DAILY_LOSS = "risk.halt.daily_loss"
"""The unit value fell by the daily loss limit or more in one day, so ordering stopped."""

RISK_HALT_DRAWDOWN = "risk.halt.drawdown"
"""The unit value fell by the drawdown limit or more below its high-water mark: ordering stopped."""

CORPORATE_SPLIT_ORDER_CANCELLED = "corporate.split.order_cancelled"
"""An order for a stock that splits that day is cancelled: its quantity no longer fits."""

FILL_CASH_CUT = "fill.cash.cut"
"""A buy at the open was made smaller to the cash that could be spent."""

FILL_CASH_SHORT = "fill.cash.short"
"""A buy at the open found no cash to spend, so it was not filled."""

FILL_CHARGES_UNPAID = "fill.charges_unpaid"
"""A sale was refused: the day's charges would exceed the cash and proceeds to pay them."""

FILL_FROZEN = "fill.frozen"
"""An order for a frozen stock was not filled at the open."""

FILL_NO_BAR = "fill.no_bar"
"""An order was not filled: its stock has no bar that day."""

FILL_NO_REFERENCE = "fill.no_reference"
"""An order was not filled: there is no previous close to set its price band."""

FILL_NO_TRADES = "fill.no_trades"
"""An order was not filled: its stock did not trade that day."""

FILL_OUTSIDE_BAND = "fill.outside_band"
"""An order was not filled: its price at the open was outside the day's price band."""

FILL_VOLUME_CUT = "fill.volume.cut"
"""An order was made smaller to its share of the day's traded volume."""

FILL_VOLUME_TOO_SMALL = "fill.volume.too_small"
"""An order was not filled: its share of the day's volume is less than a lot."""

LIMIT_CASH_CUT = "limit.cash.cut"
"""A buy was made smaller to the cash that can be spent."""

LIMIT_CASH_SHORT = "limit.cash.short"
"""A buy was not placed: there is no cash to spend."""

LIMIT_MIN_LOTS = "limit.min_lots"
"""A buy was not placed: it is below the smallest buy allowed."""

LIMIT_WEIGHT_CUT = "limit.weight.cut"
"""A buy was made smaller to the most one stock may be of the portfolio."""

LIMIT_WEIGHT_FULL = "limit.weight.full"
"""A buy was not placed: the stock is already at its weight limit."""

STRATEGY_TOO_FEW_QUALIFIED = "strategy.too_few_qualified"
"""``dividend-growth`` found fewer stocks passing its test than its ``min_stocks``, so the rest
of the portfolio is held as cash (M6 spec §6)."""

TRADE_EXCLUDED = "trade.excluded"
"""A stock you excluded is not traded."""

TRADE_FROZEN = "trade.frozen"
"""A frozen stock is not traded."""

TRADE_NO_BAR = "trade.no_bar"
"""A stock with no bar today is not traded."""

TRADE_NOT_HELD = "trade.not_held"
"""A stock that is not held cannot be sold."""

TRADE_NOT_IN_UNIVERSE = "trade.not_in_universe"
"""A stock outside the universe on the day cannot be bought."""

TRADE_REFUSED = "trade.refused"
"""A stock whose data the source refused today is not traded."""

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")


@dataclass(frozen=True, slots=True)
class Note:
    """Something a report says in words, under a key that never changes."""

    key: str
    text: str

    def __post_init__(self) -> None:
        require_type(self.key, str, "key")
        require_type(self.text, str, "text")
        if _KEY.fullmatch(self.key) is None:
            msg = f"a note key is a dotted lowercase identifier, got {self.key!r}"
            raise ValueError(msg)
        if not self.text.strip():
            msg = f"the note {self.key} has no text"
            raise ValueError(msg)
