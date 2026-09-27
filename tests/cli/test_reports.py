"""The report layouts, from real runs over the recorded golden window: a strategy beside the
baseline, a comparison, a halt, a run with no goal, and the value formats (M5 spec §5.3, §5.4)."""

from collections.abc import Iterator
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from record_golden import END, RECORDED, START, recorded, settings, universe

from steadyhand import (
    IDR,
    BacktestResult,
    BacktestSettings,
    Decision,
    EngineSettings,
    Market,
    MarketView,
    Memory,
    Money,
    PortfolioView,
    RiskLimits,
    backtest,
    compare,
)
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules, YahooDataSource
from steadyhand_idx.reports import (
    GOAL_FIGURES,
    RUN_FIGURES,
    backtest_files,
    backtest_page,
    comparison_files,
    comparison_page,
    figures,
    raw,
    show,
    values,
)


class Cash:
    """A strategy that never buys, so its run is the starting cash and nothing else."""

    @property
    def name(self) -> str:
        return "cash"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        return Decision({})


def no_wait(seconds: float) -> None:
    del seconds


@pytest.fixture(scope="module")
def market(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Market]:
    yahoo = YahooDataSource(download=recorded, sleep=no_wait)
    with BarCache(tmp_path_factory.mktemp("bars") / "bars.sqlite") as cache:
        source = CachedDataSource(yahoo, cache, today=lambda: RECORDED)
        yield Market(universe(), source, IdxMarketRules())


@pytest.fixture(scope="module")
def beside(market: Market) -> BacktestResult:
    return backtest(Cash(), market, START, END, settings())


def test_a_strategy_is_shown_beside_the_baseline(beside: BacktestResult) -> None:
    lines = backtest_page(beside, ()).lines
    assert lines[0] == "Backtest: cash, 2021-02-01 to 2022-01-31, 248 trading days"
    assert lines[2].split() == ["cash", "buy-and-hold"]
    assert lines[3].split("  ")[0] == "Final value"
    assert lines[3].endswith("IDR 100,000,000   IDR 97,889,490")


def test_each_figure_row_carries_its_term_key(beside: BacktestResult) -> None:
    page = backtest_page(beside, ())
    expected = list(dict.fromkeys(figure.key for figure, _ in (*RUN_FIGURES, *GOAL_FIGURES)))
    assert page.keys[: len(expected)] == expected
    assert "term.portfolio_value" in page.keys


def test_the_backtest_files_hold_the_strategys_days_and_both_columns(
    beside: BacktestResult, tmp_path: Path
) -> None:
    summary, daily = backtest_files(beside, tmp_path / "reports")
    assert summary.name == "backtest-cash-2021-02-01-2022-01-31.md"
    assert "\n|  | cash | buy-and-hold |\n" in summary.read_text(encoding="utf-8")
    rows = daily.read_text(encoding="utf-8").splitlines()
    assert rows[1] == "2021-02-01,100000000,100000000,0,0,0,0"
    assert len(rows) == 249


def test_a_comparison_is_a_row_per_run(market: Market, tmp_path: Path) -> None:
    comparison = compare([Cash()], market, START, END, settings())
    page = comparison_page(comparison, [tmp_path / "a.md"])
    assert [line.split("  ")[0] for line in page.lines[2:5]] == ["Strategy", "cash", "buy-and-hold"]
    assert page.lines[-1] == f"Wrote {tmp_path / 'a.md'}"
    summary, table = comparison_files(comparison, tmp_path)
    first = table.read_text(encoding="utf-8").splitlines()[1]
    assert first.startswith("cash,100000000,100000000,0")
    assert "\n| cash | IDR 100,000,000 | " in summary.read_text(encoding="utf-8")


def test_a_halt_is_reported_on_screen_and_in_the_file(market: Market, tmp_path: Path) -> None:
    jumpy = BacktestSettings(
        Money(100_000_000, IDR),
        EngineSettings(limits=RiskLimits(max_weight=Decimal("0.25"), daily_loss=Decimal("0.001"))),
    )
    result = backtest(Cash(), market, START, END, jumpy)
    assert result.baseline is not None
    halt = result.baseline.halt
    assert halt is not None
    line = f"buy-and-hold stopped ordering on {halt.day}: {halt.cause}"
    assert line in backtest_page(result, ()).lines
    summary, _ = backtest_files(result, tmp_path)
    assert f"\n\n{line}\n" in summary.read_text(encoding="utf-8")


def test_a_run_with_no_goal_shows_no_income_figures(market: Market, tmp_path: Path) -> None:
    result = backtest(Cash(), market, START, END, settings(income=False))
    shown = figures((result.run,))
    assert [figure.name for figure in shown] == [figure.name for figure, _ in RUN_FIGURES]
    assert set(values(result.run)) == {figure.name for figure, _ in RUN_FIGURES}
    assert not any("goal" in line for line in backtest_page(result, ()).lines)
    quiet = replace(result, warnings=())
    assert "Warnings:" in backtest_page(result, ()).lines
    assert "Warnings:" not in backtest_page(quiet, ()).lines
    summary, _ = backtest_files(quiet, tmp_path)
    assert "## Warnings" not in summary.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("value", "shown", "raw_form"),
    [
        (Money(1_234_567, IDR), "IDR 1,234,567", "1234567"),
        (Money(-5, IDR), "IDR -5", "-5"),
        (Decimal("0.2111"), "21.11%", "0.2111"),
        (Decimal("-0.02110510"), "-2.11%", "-0.02110510"),
        (Decimal(0), "0.00%", "0"),
    ],
)
def test_values_are_shown_to_people_and_written_raw_for_spreadsheets(
    value: Money | Decimal, shown: str, raw_form: str
) -> None:
    assert show(value) == shown
    assert raw(value) == raw_form


def test_each_figure_reads_the_report_field_it_names(beside: BacktestResult) -> None:
    # The baseline's run, whose figures differ from one another: the cash run's are mostly 0,
    # so a figure reading the wrong field could still match it.
    run = beside.baseline
    assert run is not None
    assert run.income is not None
    assert run.metrics.total_return != run.metrics.drawdown.depth
    metrics = run.metrics
    owners: dict[str, object] = {
        "Metrics": metrics,
        "Drawdown": metrics.drawdown,
        "CostBreakdown": metrics.costs,
        "DividendTotals": metrics.dividends,
        "GoalProgress": run.income.goal,
    }
    shown = values(run)
    for figure, _ in (*RUN_FIGURES, *GOAL_FIGURES):
        owner, attribute = figure.field.split(".")
        assert shown[figure.name] == getattr(owners[owner], attribute), figure.name


def test_each_figures_term_is_pinned() -> None:
    assert [figure.key for figure, _ in (*RUN_FIGURES, *GOAL_FIGURES)] == [
        "term.portfolio_value",
        "term.deposit",
        "term.total_return",
        "term.annual_return",
        "term.drawdown",
        "term.trading_costs",
        "term.turnover",
        "term.dividend_gross",
        "term.dividend_tax",
        "term.income_target",
        "term.received_income",
        "term.goal_share",
        "term.run_rate",
        "term.goal_share",
    ]
