"""A ten-year backtest over 45 stocks finishes in under 30 seconds (core spec §10.4, M3 §9), and
a year of ``dividend-growth`` over them in under 3 (M6 spec §9.4).

The market is ``synthetic``'s, which also shows the engine running a market other than IDX.
The strategy rebalances to equal weights every day, so the strategy's run and the baseline's
both trade, value and size every day. The ``dividend-growth`` year took 0.37 to 0.40 s at a
load of 10 on six cores (0.67 to 0.74 s at 30); its budget leaves about eight times that for a
slower CI runner.
"""

import time
from datetime import date, timedelta

import pytest
from synthetic import END, START, All, EqualWeight, PlainRules, Synthetic

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestResult,
    BacktestSettings,
    EngineSettings,
    IncomeGoal,
    Market,
    Money,
    backtest,
)

BUDGET_SECONDS = 30
GROWTH_BUDGET_SECONDS = 3


@pytest.fixture(scope="module")
def timed() -> tuple[BacktestResult, float]:
    """Ten years of 45 stocks with a goal, and the seconds the backtest took."""
    source = Synthetic()
    settings = BacktestSettings(
        Money(1_000_000_000, IDR),
        EngineSettings(monthly_contribution=Money(10_000_000, IDR)),
        IncomeGoal(Money(50_000_000, IDR)),
    )
    market = Market(All(source.stocks), source, PlainRules())
    began = time.perf_counter()
    result = backtest(EqualWeight(), market, START, END, settings)
    return result, time.perf_counter() - began


@pytest.mark.perf
def test_ten_years_of_45_stocks_run_inside_the_budget(timed: tuple[BacktestResult, float]) -> None:
    result, seconds = timed
    assert result.income_impact is not None
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"


@pytest.mark.perf
@pytest.mark.parametrize("which", ["run", "baseline"])
def test_each_timed_run_did_the_work_it_is_timed_on(
    timed: tuple[BacktestResult, float], which: str
) -> None:
    run = getattr(timed[0], which)
    assert run is not None
    # Every weekday, trades and dividends.
    weekdays = sum((START + timedelta(days=n)).weekday() < 5 for n in range((END - START).days + 1))
    assert len(run.reports) == weekdays
    assert run.halt is None
    assert sum(len(r.fills) for r in run.reports) > 45
    assert run.metrics.dividends.gross.amount > 0
    # Its income report, from five years of history, is inside the same budget, and its
    # projection had a run-rate to simulate.
    assert run.income is not None
    assert run.income.run_rate.annual_gross.amount > 0


@pytest.mark.perf
def test_a_year_of_dividend_growth_over_45_stocks_runs_inside_its_budget() -> None:
    source = Synthetic()
    entry = STRATEGIES["dividend-growth"]
    # The default six years of look-back, from 1 January 2017: the synthetic data starts in 2016.
    settings = BacktestSettings(Money(1_000_000_000, IDR), lookback_years=entry.lookback_years())
    market = Market(All(source.stocks), source, PlainRules())
    began = time.perf_counter()
    result = backtest(entry(), market, date(2023, 1, 2), date(2023, 12, 29), settings)
    seconds = time.perf_counter() - began
    # It did the work it is timed on: more stocks passed than max_stocks, so the review picked
    # 25 by their pay months, reading six years of dividends for each of the 45.
    assert len(result.run.reports) == 260
    assert len(result.run.final.holdings.portfolio.positions) == 25
    assert seconds < GROWTH_BUDGET_SECONDS, f"took {seconds:.1f} s"
