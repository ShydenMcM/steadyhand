"""A ten-year backtest over 45 stocks finishes in under 30 seconds (core spec §10.4, M3 §9).

The market is ``synthetic``'s, which also shows the engine running a market other than IDX.
The strategy rebalances to equal weights every day, so the strategy's run and the baseline's
both trade, value and size every day.
"""

import time
from datetime import timedelta

import pytest
from synthetic import END, START, All, EqualWeight, PlainRules, Synthetic

from steadyhand import (
    IDR,
    BacktestSettings,
    EngineSettings,
    IncomeGoal,
    Market,
    Money,
    backtest,
)

BUDGET_SECONDS = 30


@pytest.mark.perf
def test_ten_years_of_45_stocks_run_inside_the_budget() -> None:
    source = Synthetic()
    settings = BacktestSettings(
        Money(1_000_000_000, IDR),
        EngineSettings(monthly_contribution=Money(10_000_000, IDR)),
        IncomeGoal(Money(50_000_000, IDR)),
    )
    market = Market(All(source.stocks), source, PlainRules())
    began = time.perf_counter()
    result = backtest(EqualWeight(), market, START, END, settings)
    seconds = time.perf_counter() - began
    assert result.baseline is not None
    runs = (result.run, result.baseline)
    # The run did the work it is timed on: every weekday, trades and dividends in both runs.
    weekdays = sum((START + timedelta(days=n)).weekday() < 5 for n in range((END - START).days + 1))
    assert [len(run.reports) for run in runs] == [weekdays, weekdays]
    assert all(run.halt is None for run in runs)
    assert all(sum(len(r.fills) for r in run.reports) > 45 for run in runs)
    assert all(run.metrics.dividends.gross.amount > 0 for run in runs)
    # Each run's income report, from five years of history, is inside the same budget, and its
    # projection had a run-rate to simulate.
    assert all(
        run.income is not None and run.income.run_rate.annual_gross.amount > 0 for run in runs
    )
    assert result.income_impact is not None
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"
