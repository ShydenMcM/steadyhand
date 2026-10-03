"""``compare``: the recorded golden window through the whole command (M5 spec §5.4)."""

import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest
from cli_world import GROWTH_CONFIG, RESTORED, Cli, market_cli
from record_golden import GOLDEN, run

from steadyhand import DISCLAIMER

WINDOW = ("--from", "2021-02-01", "--to", "2022-01-31")
STEM = "compare-2021-02-01-2022-01-31"


@pytest.fixture
def market(tmp_path: Path) -> Cli:
    return market_cli(tmp_path / "home")


def test_each_strategy_ends_as_it_does_alone_with_the_longest_look_back(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home", GROWTH_CONFIG)
    names = ("buy-and-hold", "monthly-savings", "dividend-growth")
    assert market("compare", *WINDOW, *names).code == 0
    with (market.home / "reports" / f"{STEM}.csv").open(encoding="utf-8", newline="") as file:
        final = {row["strategy"]: int(row["final_value"]) for row in csv.DictReader(file)}
    # One fetch with dividend-growth's three-year look-back serves all three; each run alone
    # takes its own (none for the other two), so any difference would show here.
    alone = {name: run(tmp_path / name, name).run.metrics.final_value.amount for name in names}
    assert final == alone
    assert len(set(alone.values())) == 3


def test_the_csv_row_is_the_golden_runs_figures(market: Cli) -> None:
    assert market("compare", *WINDOW, "buy-and-hold").code == 0
    with (market.home / "reports" / f"{STEM}.csv").open(encoding="utf-8", newline="") as file:
        header, row, *rest = list(csv.reader(file))
    assert rest == []
    figures = dict(zip(header, row, strict=True))
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))["metrics"]
    costs = stored["costs"]
    assert figures["strategy"] == "buy-and-hold"
    assert int(figures["final_value"]) == stored["final_value"]
    assert int(figures["deposited"]) == stored["deposited"]
    assert Decimal(figures["total_return"]) == Decimal(stored["total_return"])
    assert Decimal(figures["annual_return"]) == Decimal(stored["annual_return"])
    assert Decimal(figures["drawdown"]) == Decimal(stored["drawdown"][0])
    assert int(figures["costs"]) == sum(costs.values())
    assert Decimal(figures["turnover"]) == Decimal(stored["turnover"])
    assert int(figures["dividends_gross"]) == stored["dividends"]["gross"]
    assert int(figures["dividend_tax"]) == stored["dividends"]["tax"]
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
    assert figures["goal"] == "1000000"


def test_the_table_is_a_row_per_strategy_then_the_warnings(market: Cli) -> None:
    result = market("compare", *WINDOW, "buy-and-hold")
    assert result.err == ""
    header, row = result.out.split("\n\n")[1].splitlines()
    assert header.split("  ")[0] == "Strategy"
    assert header.endswith("Run-rate, of the goal")
    assert row.startswith("buy-and-hold")
    assert "IDR 96,825,198" in row
    assert row.endswith("20.70%")
    assert result.out.startswith(
        "Comparison, 2021-02-01 to 2022-01-31, 248 trading days\n\nStrategy"
    )
    # BBRI's prices are restored (#160): that is the one warning, and none is refused.
    assert f"\n\nWarnings:\n- {RESTORED}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")


def test_the_markdown_file_is_the_same_table(market: Cli) -> None:
    market("compare", *WINDOW, "buy-and-hold")
    lines = (market.home / "reports" / f"{STEM}.md").read_text(encoding="utf-8").splitlines()
    assert lines[:4] == ["# Comparison, 2021-02-01 to 2022-01-31", "", "248 trading days.", ""]
    assert lines[4].startswith("| Strategy | Final value | Deposited | ")
    assert lines[5] == "|---|" + "---:|" * 14
    assert lines[6].startswith("| buy-and-hold | IDR 96,825,198 | IDR 100,000,000 | -3.17% | ")
    assert lines[-1] == DISCLAIMER


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
