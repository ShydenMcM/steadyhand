"""``backtest`` over the recorded golden window, the whole command (M5 spec §5.3), moved out of
unit by #292: each runs a year of five recorded stocks through the real source and cache, over the
unit limit of 0.07 s of its own CPU in its heaviest measured run (develop, 2026-10-13: 0.29 s to
1.34 s). The monthly-savings tests share one module-scoped run, so they move together: left in unit,
the run's cost would land on whichever of them ran first.

The unit suite keeps a stand-in of each, of the same name, in
``tests/cli/test_backtest_command.py``: the same command and checks over nineteen trading days of
three made-up stocks (``tests/cli/short_world.py``), which meet a dividend, a split and a restored
adjustment as the golden window does.
"""

import csv
import json
import stat
from pathlib import Path

import pytest
from cli_world import (
    GOLDEN_CONFIG,
    GROWTH_CONFIG,
    RESTORED,
    Cli,
    Result,
    market_cli,
)
from record_cli_seed import PLACEHOLDERS
from record_golden import END, GOLDEN, RECORDED, START, replay, run, settings, universe

from steadyhand import (
    DATA_BAR_REFUSED,
    DISCLAIMER,
    BacktestResult,
    BuyAndHold,
    Market,
    backtest,
)
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.training import catalogue

WINDOW = ("--from", "2021-02-01", "--to", "2022-01-31")
STEM = "backtest-buy-and-hold-2021-02-01-2022-01-31"


@pytest.fixture
def market(tmp_path: Path) -> Cli:
    return market_cli(tmp_path / "home")


@pytest.fixture(scope="module")
def golden(tmp_path_factory: pytest.TempPathFactory) -> BacktestResult:
    return run(tmp_path_factory.mktemp("golden"))


def test_the_daily_csv_is_the_golden_run_day_by_day(market: Cli, golden: BacktestResult) -> None:
    assert market("backtest", *WINDOW).code == 0
    with (market.home / "reports" / f"{STEM}.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == [
        "day",
        "value",
        "settled_cash",
        "unsettled_cash",
        "holdings_value",
        "dividends_gross",
        "dividend_tax",
    ]
    expected = [
        [
            report.day.isoformat(),
            *(
                str(amount)
                for amount in (
                    report.value.amount,
                    report.settled.amount,
                    report.unsettled.amount,
                    report.holdings_value.amount,
                    sum(paid.gross.amount for paid in report.paid),
                    report.tax.amount,
                )
            ),
        ]
        for report in golden.run.reports
    ]
    assert rows[1:] == expected
    assert len(expected) == 248
    assert sum(int(row[5]) for row in rows[1:]) == 2_699_239


def test_the_summary_shows_the_golden_figures(market: Cli) -> None:
    result = market("backtest", *WINDOW)
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))["metrics"]
    assert stored["final_value"] == 96_825_198
    assert stored["dividends"] == {"gross": 2_699_239, "tax": 269_925}
    table = result.out.split("\n\n")[1].splitlines()
    assert table == [
        "                          buy-and-hold",
        "Final value             IDR 96,825,198",
        "Deposited              IDR 100,000,000",
        "Total return                    -3.17%",
        "Annual return                   -3.17%",
        "Largest drawdown                17.65%",
        "Trading costs              IDR 279,116",
        "Turnover a year                 54.14%",
        "Dividends before tax     IDR 2,699,239",
        "Dividend tax               IDR 269,925",
        "Income goal a month      IDR 1,000,000",
        "Received a month           IDR 202,442",
        "Received, of the goal           20.24%",
        "Run-rate a month           IDR 206,964",
        "Run-rate, of the goal           20.70%",
    ]
    costs = stored["costs"]
    assert costs["fee"] + costs["levy"] + costs["sale_tax"] + costs["daily"] == 279_116


def test_the_summary_then_the_warnings_the_files_and_the_explanations(market: Cli) -> None:
    result = market("backtest", *WINDOW)
    assert result.err == ""
    reports = market.home / "reports"
    assert result.out.startswith(
        "Backtest: buy-and-hold, 2021-02-01 to 2022-01-31, 248 trading days\n\n"
    )
    # BBRI's prices up to 2021-09-07 are restored (#160): the one warning says so, and nothing
    # in the window is refused.
    assert f"\n\nWarnings:\n- {RESTORED}\n\n" in result.out
    assert f"\n\nWrote {reports / f'{STEM}.md'}\nWrote {reports / f'{STEM}.csv'}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    refused = catalogue().for_key(DATA_BAR_REFUSED).id
    assert f"More: steadyhand-idx learn {refused}\n" not in result.out
    restored = catalogue().for_key(DATA_PRICES_RESTORED).id
    assert restored == "idx.restored_prices"
    assert f"More: steadyhand-idx learn {restored}\n" in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")


def test_the_markdown_file_holds_the_summary_and_the_disclaimer(market: Cli) -> None:
    market("backtest", *WINDOW)
    text = (market.home / "reports" / f"{STEM}.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[:6] == [
        "# Backtest: buy-and-hold, 2021-02-01 to 2022-01-31",
        "",
        "248 trading days.",
        "",
        "|  | buy-and-hold |",
        "|---|---:|",
    ]
    assert lines[6] == "| Final value | IDR 96,825,198 |"
    assert f"\n## Warnings\n\n- {RESTORED}\n" in text
    assert "## Day warnings" not in text
    assert text.endswith(f"\n\n---\n\n{DISCLAIMER}\n")


def test_the_reports_are_private_and_a_second_run_replaces_them(market: Cli) -> None:
    market("backtest", *WINDOW)
    reports = market.home / "reports"
    first = {path.name: path.read_bytes() for path in reports.iterdir()}
    assert market("backtest", *WINDOW).code == 0
    assert {path.name: path.read_bytes() for path in reports.iterdir()} == first
    assert sorted(first) == [f"{STEM}.csv", f"{STEM}.md"]
    assert stat.S_IMODE(reports.stat().st_mode) == 0o700
    for path in reports.iterdir():  # runtime population: the files the run wrote
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_a_member_with_no_bars_gives_day_warnings_in_the_file(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home")
    exclusions = market.home / "exclusions.csv"
    lines = exclusions.read_text(encoding="utf-8").splitlines(keepends=True)
    exclusions.write_text("".join(line for line in lines if not line.startswith(PLACEHOLDERS[0])))
    assert market("backtest", *WINDOW).code == 0
    text = (market.home / "reports" / f"{STEM}.md").read_text(encoding="utf-8")
    assert "\n## Day warnings\n\n- buy-and-hold, 2021-02-01: ZAAA has no bar on 2021-02-01" in text
    assert text.count(": ZAAA has no bar on ") == 248


def test_the_strategy_comes_from_the_configuration_or_the_option(market: Cli) -> None:
    named = market("backtest", *WINDOW, "--strategy", "buy-and-hold")
    assert named.code == 0
    assert named.out == market("backtest", *WINDOW).out


def test_the_starting_cash_and_goal_come_from_the_configuration(tmp_path: Path) -> None:
    config = GOLDEN_CONFIG.replace("100_000_000", "50_000_000")
    market = market_cli(tmp_path / "home", config)
    result = market("backtest", *WINDOW)
    (deposited,) = [line for line in result.out.splitlines() if line.startswith("Deposited ")]
    assert deposited.endswith(" IDR 50,000,000")


def test_the_broker_fee_preset_comes_from_the_configuration(
    tmp_path: Path, golden: BacktestResult
) -> None:
    config = GOLDEN_CONFIG.replace("[account]\n", '[account]\nbroker_fees = "ajaib"\n')
    market = market_cli(tmp_path / "home", config)
    assert market("backtest", *WINDOW).code == 0
    with (market.home / "reports" / f"{STEM}.csv").open(encoding="utf-8", newline="") as file:
        last = list(csv.reader(file))[-1]
    with BarCache(tmp_path / "bars.sqlite") as cache:
        source = CachedDataSource(replay(), cache, today=lambda: RECORDED)
        rules = IdxMarketRules(broker_fees="ajaib")
        expected = backtest(BuyAndHold(), Market(universe(), source, rules), START, END, settings())
    assert int(last[1]) == expected.run.reports[-1].value.amount
    assert int(last[1]) != golden.run.reports[-1].value.amount


def test_dividend_growth_reads_its_look_back_and_ends_as_the_library_run(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home", GROWTH_CONFIG)
    result = market("backtest", *WINDOW, "--strategy", "dividend-growth")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Backtest: dividend-growth, 2021-02-01 to 2022-01-31, 248 trading days\n\n"
    )
    daily = market.home / "reports" / "backtest-dividend-growth-2021-02-01-2022-01-31.csv"
    with daily.open(encoding="utf-8", newline="") as file:
        last = list(csv.reader(file))[-1]
    expected = run(tmp_path / "library", "dividend-growth").run.reports[-1].value.amount
    assert int(last[1]) == expected
    # Blind to its three years of dividends, nothing would pass and it would hold only cash.
    assert expected != 100_000_000


SAVINGS_MONTHS = ("2021-02", "2021-03", "2021-04", "2021-05")


@pytest.fixture(scope="module")
def savings(tmp_path_factory: pytest.TempPathFactory) -> tuple[Result, dict[str, list[int]]]:
    """One monthly-savings run over four instalments, and the cash it held each day, by month."""
    config = GOLDEN_CONFIG.replace(
        'name = "buy-and-hold"', 'name = "buy-and-hold"\ninstalments = 4'
    )
    market = market_cli(tmp_path_factory.mktemp("savings") / "home", config)
    result = market("backtest", *WINDOW, "--strategy", "monthly-savings")
    daily = market.home / "reports" / "backtest-monthly-savings-2021-02-01-2022-01-31.csv"
    cash: dict[str, list[int]] = {}
    with daily.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            held = int(row["settled_cash"]) + int(row["unsettled_cash"])
            cash.setdefault(row["day"][:7], []).append(held)
    return result, cash


def test_monthly_savings_runs_against_buy_and_hold(
    savings: tuple[Result, dict[str, list[int]]],
) -> None:
    result, _ = savings
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Backtest: monthly-savings, 2021-02-01 to 2022-01-31, 248 trading days\n\n"
    )
    assert result.out.split("\n\n")[1].splitlines()[:2] == [
        "                       monthly-savings     buy-and-hold",
        "Final value             IDR 98,752,838   IDR 96,825,198",
    ]


@pytest.mark.parametrize("month", SAVINGS_MONTHS)
def test_monthly_savings_keeps_back_the_instalments_still_due(
    savings: tuple[Result, dict[str, list[int]]], month: str
) -> None:
    # Each instalment of 25,000,000 fills the day after the month's first trading day, and the
    # instalments still due stay back as cash until their month.
    _, cash = savings
    reserve = (len(SAVINGS_MONTHS) - 1 - SAVINGS_MONTHS.index(month)) * 25_000_000
    assert reserve <= cash[month][1] < reserve + 25_000_000
