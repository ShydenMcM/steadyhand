"""Terms: a stable key for each figure a report can show (T1 spec §3.2).

A term key follows the note rules in ``steadyhand.notes``: a dotted lowercase identifier that is
never reworded, in a constant named after its value, here always under ``term.``. A lesson
attaches to a term, so a report's labels can be explained as well as its notes.

``FIGURES`` maps every figure field, as ``"Class.field"``, to its term. Several fields share a
term when they show the same quantity. ``tests/meta/test_terms.py`` derives the figure fields
itself, by walking the report types, and fails when one is missing here or when an entry here
names a field that does not exist. This module imports nothing from the rest of the engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

TERM_ANNUAL_RETURN = "term.annual_return"
"""The total return compounded to a yearly rate over the run's calendar days."""

TERM_BROKER_FEE = "term.broker_fee"
"""What the broker charges on a trade."""

TERM_CASH_MOVEMENT = "term.cash_movement"
"""One change to cash: positive when money comes in, negative when it goes out."""

TERM_CLAIM_PROTECTED = "term.claim_protected"
"""Part of a dividend claim reinvested by a purchase, which must stay invested until a date."""

TERM_CLAIM_TO_REINVEST = "term.claim_to_reinvest"
"""The part of a dividend claim not yet reinvested, which is taxed if its deadline passes."""

TERM_CONTRIBUTION = "term.contribution"
"""The money added each month in a projection."""

TERM_COST_BASIS = "term.cost_basis"
"""What a holding cost to buy, costs included."""

TERM_CURRENT_YIELD = "term.current_yield"
"""A year's dividends as a share of what the holdings are worth today."""

TERM_DAILY_COST = "term.daily_cost"
"""A cost charged by the day rather than by the trade."""

TERM_DEPOSIT = "term.deposit"
"""Money paid into the portfolio."""

TERM_DIVIDEND_GROSS = "term.dividend_gross"
"""A dividend before tax."""

TERM_DIVIDEND_GROWTH = "term.dividend_growth"
"""The yearly rate at which dividends a share have grown, or are assumed to grow."""

TERM_DIVIDEND_NET = "term.dividend_net"
"""A dividend after tax."""

TERM_DIVIDEND_PER_SHARE = "term.dividend_per_share"
"""The dividends one share paid over a year."""

TERM_DIVIDEND_TAX = "term.dividend_tax"
"""The tax taken from a dividend before it is paid."""

TERM_DRAWDOWN = "term.drawdown"
"""The largest fall from a high point to a later low point."""

TERM_EVENNESS = "term.evenness"
"""The largest month's share of a year's dividend income."""

TERM_GOAL_SHARE = "term.goal_share"
"""How much of the income target an amount covers."""

TERM_HIGH_WATER = "term.high_water"
"""The highest unit price the portfolio has reached."""

TERM_HOLDINGS_VALUE = "term.holdings_value"
"""What the shares held are worth at the day's closing prices."""

TERM_INCOME_TARGET = "term.income_target"
"""The yearly dividend income the goal asks for."""

TERM_LAST_CLOSE = "term.last_close"
"""A stock's most recent closing price."""

TERM_LEVY = "term.levy"
"""The exchange's charges on a trade, collected by the broker."""

TERM_MONTHLY_TAKE_HOME = "term.monthly_take_home"
"""The run-rate after tax, spread over twelve months."""

TERM_PAYMENT_CALENDAR = "term.payment_calendar"
"""The expected dividend income in each month of the year."""

TERM_PORTFOLIO_VALUE = "term.portfolio_value"
"""Cash plus holdings: what the whole portfolio is worth."""

TERM_RECEIVED_INCOME = "term.received_income"
"""The dividends actually paid over the last year."""

TERM_RUN_RATE = "term.run_rate"
"""What the dividends held now would pay over a year if nothing changed."""

TERM_SALE_TAX = "term.sale_tax"
"""The tax charged on the value of every sale."""

TERM_SETTLED_CASH = "term.settled_cash"
"""Cash that has arrived and can be spent."""

TERM_STARTING_INCOME = "term.starting_income"
"""The yearly dividend income a projection starts from."""

TERM_TAKE_HOME = "term.take_home"
"""What dividends leave after the full dividend tax, whatever tax the engine booked."""

TERM_TOTAL_RETURN = "term.total_return"
"""The portfolio's gain or loss over the run, with deposits not counted as gains."""

TERM_TRADE_PRICE = "term.trade_price"
"""The price a trade was filled at."""

TERM_TRADE_VALUE = "term.trade_value"
"""The number of shares traded times the price, before costs."""

TERM_TRADING_COSTS = "term.trading_costs"
"""Everything a trade costs on top of its value."""

TERM_TRAILING_INCOME = "term.trailing_income"
"""The dividend income after tax paid in the last year of a run."""

TERM_TURNOVER = "term.turnover"
"""How much of the portfolio is traded in a year."""

TERM_UNIT_PRICE = "term.unit_price"
"""The price of one unit when the portfolio is counted as a fund."""

TERM_UNITS = "term.units"
"""How many units of the portfolio exist when it is counted as a fund."""

TERM_UNSETTLED_CASH = "term.unsettled_cash"
"""Cash from a sale that has not arrived yet."""

TERM_YEARS_TO_GOAL = "term.years_to_goal"
"""How many years a projection takes to reach the income target."""

TERM_YIELD_ON_COST = "term.yield_on_cost"
"""A year's dividends as a share of what the holdings cost to buy."""

FIGURES: Mapping[str, str] = MappingProxyType(
    {
        "CashMovement.amount": TERM_CASH_MOVEMENT,
        "CostBreakdown.daily": TERM_DAILY_COST,
        "CostBreakdown.fee": TERM_BROKER_FEE,
        "CostBreakdown.levy": TERM_LEVY,
        "CostBreakdown.sale_tax": TERM_SALE_TAX,
        "CostBreakdown.total": TERM_TRADING_COSTS,
        "Costs.fee": TERM_BROKER_FEE,
        "Costs.levy": TERM_LEVY,
        "Costs.tax": TERM_SALE_TAX,
        "Costs.total": TERM_TRADING_COSTS,
        "DayReport.daily_cost": TERM_DAILY_COST,
        "DayReport.deposit": TERM_DEPOSIT,
        "DayReport.holdings_value": TERM_HOLDINGS_VALUE,
        "DayReport.settled": TERM_SETTLED_CASH,
        "DayReport.tax": TERM_DIVIDEND_TAX,
        "DayReport.unit_price": TERM_UNIT_PRICE,
        "DayReport.unsettled": TERM_UNSETTLED_CASH,
        "DayReport.value": TERM_PORTFOLIO_VALUE,
        "DividendClaim.gross": TERM_DIVIDEND_GROSS,
        "DividendClaim.uncovered": TERM_CLAIM_TO_REINVEST,
        "DividendGrowth.portfolio": TERM_DIVIDEND_GROWTH,
        "DividendTotals.gross": TERM_DIVIDEND_GROSS,
        "DividendTotals.net": TERM_DIVIDEND_NET,
        "DividendTotals.tax": TERM_DIVIDEND_TAX,
        "Drawdown.depth": TERM_DRAWDOWN,
        "Entitlement.gross": TERM_DIVIDEND_GROSS,
        "Fill.gross": TERM_TRADE_VALUE,
        "Fill.price": TERM_TRADE_PRICE,
        "GoalProgress.received": TERM_RECEIVED_INCOME,
        "GoalProgress.received_share": TERM_GOAL_SHARE,
        "GoalProgress.run_rate": TERM_RUN_RATE,
        "GoalProgress.run_rate_share": TERM_GOAL_SHARE,
        "GoalProgress.target": TERM_INCOME_TARGET,
        "HoldingCalendar.months": TERM_PAYMENT_CALENDAR,
        "HoldingGrowth.earlier": TERM_DIVIDEND_PER_SHARE,
        "HoldingGrowth.growth": TERM_DIVIDEND_GROWTH,
        "HoldingGrowth.recent": TERM_DIVIDEND_PER_SHARE,
        "HoldingRunRate.annual_gross": TERM_RUN_RATE,
        "HoldingRunRate.monthly_take_home": TERM_MONTHLY_TAKE_HOME,
        "Holdings.last_closes": TERM_LAST_CLOSE,
        "IncomeFigures.gross": TERM_DIVIDEND_GROSS,
        "IncomeFigures.net": TERM_DIVIDEND_NET,
        "IncomeFigures.take_home": TERM_TAKE_HOME,
        "IncomeFigures.tax": TERM_DIVIDEND_TAX,
        "IncomeImpact.received": TERM_RECEIVED_INCOME,
        "IncomeImpact.run_rate": TERM_RUN_RATE,
        "Metrics.annual_return": TERM_ANNUAL_RETURN,
        "Metrics.deposited": TERM_DEPOSIT,
        "Metrics.final_value": TERM_PORTFOLIO_VALUE,
        "Metrics.total_return": TERM_TOTAL_RETURN,
        "Metrics.trailing_income": TERM_TRAILING_INCOME,
        "Metrics.turnover": TERM_TURNOVER,
        "PaymentCalendar.evenness": TERM_EVENNESS,
        "PaymentCalendar.months": TERM_PAYMENT_CALENDAR,
        "Position.cost_basis": TERM_COST_BASIS,
        "Projection.contribution": TERM_CONTRIBUTION,
        "Projection.target": TERM_INCOME_TARGET,
        "Protection.amount": TERM_CLAIM_PROTECTED,
        "ReceivedIncome.current_yield": TERM_CURRENT_YIELD,
        "ReceivedIncome.yield_on_cost": TERM_YIELD_ON_COST,
        "RunRate.annual_gross": TERM_RUN_RATE,
        "RunRate.monthly_take_home": TERM_MONTHLY_TAKE_HOME,
        "ScenarioProjection.growth": TERM_DIVIDEND_GROWTH,
        "ScenarioProjection.starting_gross": TERM_STARTING_INCOME,
        "ScenarioProjection.years": TERM_YEARS_TO_GOAL,
        "UnitValue.high_water": TERM_HIGH_WATER,
        "UnitValue.price": TERM_UNIT_PRICE,
        "UnitValue.units": TERM_UNITS,
    }
)
"""Every figure field a report can show, as ``"Class.field"``, and the term that explains it."""
