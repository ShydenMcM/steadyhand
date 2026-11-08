"""``compare`` over the recorded golden window, the whole command (M5 spec §5.4), moved out of unit
by #292: each runs a year of five recorded stocks through the real source and cache, over the unit
limit of 0.07 s of its own CPU in its heaviest measured run (develop, 2026-10-13: 0.47 s to 2.2 s).
The first runs on a cold cache, as it must: it proves that one fetch with the longest look-back
serves every strategy as its own fetch would.

The unit suite keeps stand-ins of these checks, under their own names, in
``tests/cli/test_compare_command.py``: the same command and checks over nineteen trading days of
three made-up stocks (``tests/cli/short_world.py``).
"""

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


def test_a_comparison_prints_its_table_and_writes_its_files(market: Cli) -> None:
    result = market("compare", *WINDOW, "buy-and-hold")
    assert result.code == 0

    # The CSV row is the golden run's figures.
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

    # The table is a row per strategy, then the warnings.
    assert result.err == ""
    table_header, table_row = result.out.split("\n\n")[1].splitlines()
    assert table_header.split("  ")[0] == "Strategy"
    assert table_header.endswith("Run-rate, of the goal")
    assert table_row.startswith("buy-and-hold")
    assert "IDR 96,825,198" in table_row
    assert table_row.endswith("20.70%")
    assert result.out.startswith(
        "Comparison, 2021-02-01 to 2022-01-31, 248 trading days\n\nStrategy"
    )
    # BBRI's prices are restored (#160): that is the one warning, and none is refused.
    assert f"\n\nWarnings:\n- {RESTORED}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")

    # The Markdown file is the same table.
    lines = (market.home / "reports" / f"{STEM}.md").read_text(encoding="utf-8").splitlines()
    assert lines[:4] == ["# Comparison, 2021-02-01 to 2022-01-31", "", "248 trading days.", ""]
    assert lines[4].startswith("| Strategy | Final value | Deposited | ")
    assert lines[5] == "|---|" + "---:|" * 14
    assert lines[6].startswith("| buy-and-hold | IDR 96,825,198 | IDR 100,000,000 | -3.17% | ")
    assert lines[-1] == DISCLAIMER
