"""``compare``: every refusal, and the whole command over a short made-up window (M5 spec §5.4).
The golden window's real runs are in ``tests/integration/cli/test_compare_command_golden.py``
(#292); each has its stand-in here, of the same name, over ``short_world``'s made-up days."""

import csv
from decimal import Decimal
from pathlib import Path

import pytest
from cli_world import Cli, market_cli
from short_world import GROWTH_CONFIG as SHORT_GROWTH_CONFIG
from short_world import RESTORED as SHORT_RESTORED
from short_world import WEEK, WEEK_END, library_run, short_cli
from short_world import WINDOW as SHORT_WINDOW

from steadyhand import DISCLAIMER

WINDOW = ("--from", "2021-02-01", "--to", "2022-01-31")
STEM = "compare-2021-02-01-2022-01-31"


@pytest.fixture
def market(tmp_path: Path) -> Cli:
    return market_cli(tmp_path / "home")


def test_a_strategy_named_twice_exits_2(market: Cli) -> None:
    assert market("compare", *WINDOW, "buy-and-hold", "buy-and-hold") == (
        2,
        "",
        "steadyhand-idx: buy-and-hold is named twice; name each strategy once\n",
    )


def test_an_unknown_strategy_exits_2_naming_the_closest(market: Cli) -> None:
    assert market("compare", *WINDOW, "buy-and-hold", "buy-hold") == (
        2,
        "",
        "steadyhand-idx: no strategy named 'buy-hold'; the closest: buy-and-hold\n",
    )


def test_compare_needs_a_strategy_and_the_configuration(market: Cli, tmp_path: Path) -> None:
    result = market("compare", *WINDOW)
    assert result.code == 2
    assert "the following arguments are required: strategy" in result.err
    unconfigured = Cli(tmp_path / "elsewhere")
    assert unconfigured("compare", *WINDOW, "buy-and-hold").code == 2
    assert not (market.home / "reports").exists()


# The stand-ins of the golden-window tests moved to tests/integration/cli/
# test_compare_command_golden.py (#292): each of the same name, over the made-up window.

SHORT_STEM = "compare-2021-02-01-2021-02-26"


@pytest.fixture
def short(tmp_path: Path) -> Cli:
    return short_cli(tmp_path / "home")


def test_each_strategy_ends_as_it_does_alone_with_the_longest_look_back(tmp_path: Path) -> None:
    short = short_cli(tmp_path / "home", SHORT_GROWTH_CONFIG)
    names = ("buy-and-hold", "dividend-growth")
    assert short("compare", *WEEK, *names).code == 0
    stem = "compare-2021-02-01-2021-02-05"
    with (short.home / "reports" / f"{stem}.csv").open(encoding="utf-8", newline="") as file:
        final = {row["strategy"]: int(row["final_value"]) for row in csv.DictReader(file)}
    # One fetch with dividend-growth's three-year look-back serves both; buy-and-hold alone takes
    # none, so any difference would show here.
    alone = {name: library_run(name, end=WEEK_END).run.metrics.final_value.amount for name in names}
    assert final == alone
    assert len(set(alone.values())) == 2


def test_the_csv_row_is_the_golden_runs_figures(short: Cli) -> None:
    assert short("compare", *SHORT_WINDOW, "buy-and-hold").code == 0
    with (short.home / "reports" / f"{SHORT_STEM}.csv").open(encoding="utf-8", newline="") as file:
        header, row, *rest = list(csv.reader(file))
    assert rest == []
    figures = dict(zip(header, row, strict=True))
    metrics = library_run().run.metrics
    assert figures["strategy"] == "buy-and-hold"
    assert int(figures["final_value"]) == metrics.final_value.amount == 103_981_291
    assert int(figures["deposited"]) == metrics.deposited.amount
    assert Decimal(figures["total_return"]) == metrics.total_return
    assert Decimal(figures["annual_return"]) == metrics.annual_return
    assert int(figures["costs"]) == metrics.costs.total.amount
    assert int(figures["dividends_gross"]) == metrics.dividends.gross.amount == 1_240_000
    assert int(figures["dividend_tax"]) == metrics.dividends.tax.amount
    assert header == [
        "strategy",
        "final_value",
        "deposited",
        "total_return",
        "annual_return",
        "drawdown",
        "costs",
        "turnover",
        "dividends_gross",
        "dividend_tax",
        "goal",
        "received",
        "received_share",
        "run_rate",
        "run_rate_share",
    ]
    assert figures["goal"] == "2000"


def test_the_table_is_a_row_per_strategy_then_the_warnings(short: Cli) -> None:
    result = short("compare", *SHORT_WINDOW, "buy-and-hold")
    assert result.err == ""
    header, row = result.out.split("\n\n")[1].splitlines()
    assert header.split("  ")[0] == "Strategy"
    assert header.endswith("Run-rate, of the goal")
    assert row.startswith("buy-and-hold")
    assert "IDR 103,981,291" in row
    assert row.endswith("13181.25%")
    assert result.out.startswith(
        "Comparison, 2021-02-01 to 2021-02-26, 19 trading days\n\nStrategy"
    )
    # XCCC's prices are restored: that is the one warning, and none is refused.
    assert f"\n\nWarnings:\n- {SHORT_RESTORED}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")


def test_the_markdown_file_is_the_same_table(short: Cli) -> None:
    short("compare", *SHORT_WINDOW, "buy-and-hold")
    lines = (short.home / "reports" / f"{SHORT_STEM}.md").read_text(encoding="utf-8").splitlines()
    assert lines[:4] == ["# Comparison, 2021-02-01 to 2021-02-26", "", "19 trading days.", ""]
    assert lines[4].startswith("| Strategy | Final value | Deposited | ")
    assert lines[5] == "|---|" + "---:|" * 14
    assert lines[6].startswith("| buy-and-hold | IDR 103,981,291 | IDR 100,000,000 | 3.98% | ")
    assert lines[-1] == DISCLAIMER
