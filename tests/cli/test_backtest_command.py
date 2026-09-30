"""``backtest``: the recorded golden window through the whole command, and every refusal (M5 spec
§5.3, §8.1). The data is Yahoo's recorded answers read through the real source and cache."""

import csv
import json
import stat
from datetime import date
from pathlib import Path

import pytest
from cli_world import GOLDEN_CONFIG, PLACEHOLDERS, Cli, golden_backtest, market_cli
from record_golden import END, GOLDEN, RECORDED, START, recorded, run, settings, universe

from steadyhand import (
    DATA_BAR_REFUSED,
    DISCLAIMER,
    IDR,
    BacktestResult,
    BuyAndHold,
    Market,
    Money,
    backtest,
)
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules, YahooDataSource
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
    assert sum(int(row[5]) for row in rows[1:]) == 2_800_277


def test_the_summary_shows_the_golden_figures(market: Cli) -> None:
    result = market("backtest", *WINDOW)
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))["metrics"]
    assert stored["final_value"] == 97_889_490
    assert stored["dividends"] == {"gross": 2_800_277, "tax": 280_028}
    table = result.out.split("\n\n")[1].splitlines()
    assert table == [
        "                          buy-and-hold",
        "Final value             IDR 97,889,490",
        "Deposited              IDR 100,000,000",
        "Total return                    -2.11%",
        "Annual return                   -2.11%",
        "Largest drawdown                18.16%",
        "Trading costs              IDR 239,759",
        "Turnover a year                 54.42%",
        "Dividends before tax     IDR 2,800,277",
        "Dividend tax               IDR 280,028",
        "Income goal a month      IDR 1,000,000",
        "Received a month           IDR 210,020",
        "Received, of the goal           21.00%",
        "Run-rate a month           IDR 212,668",
        "Run-rate, of the goal           21.27%",
    ]
    costs = stored["costs"]
    assert costs["fee"] + costs["levy"] + costs["sale_tax"] + costs["daily"] == 239_759


def test_the_summary_then_the_warnings_the_files_and_the_explanations(market: Cli) -> None:
    result = market("backtest", *WINDOW)
    assert result.err == ""
    reports = market.home / "reports"
    assert result.out.startswith(
        "Backtest: buy-and-hold, 2021-02-01 to 2022-01-31, 248 trading days\n\n"
    )
    assert (
        "\n\nWarnings:\n- BBRI: the data source refused 146 day(s) (2021-02-01 to 2021-09-07)"
        in result.out
    )
    assert f"\n\nWrote {reports / f'{STEM}.md'}\nWrote {reports / f'{STEM}.csv'}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    refused = catalogue().for_key(DATA_BAR_REFUSED).id
    assert f"More: steadyhand-idx learn {refused}\n" in result.out
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
    assert lines[6] == "| Final value | IDR 97,889,490 |"
    assert "\n## Warnings\n\n- BBRI: the data source refused 146 day(s)" in text
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
    for path in reports.iterdir():
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


def test_an_unknown_strategy_names_the_closest(market: Cli) -> None:
    assert market("backtest", *WINDOW, "--strategy", "buy-and-hodl") == (
        2,
        "",
        "steadyhand-idx: no strategy named 'buy-and-hodl'; the closest: buy-and-hold\n",
    )


@pytest.mark.parametrize(
    ("window", "problem"),
    [
        (
            ("--from", "2022-01-31", "--to", "2021-02-01"),
            "--to 2021-02-01 is before --from 2022-01-31",
        ),
        (
            ("--from", "2021-02-13", "--to", "2021-02-14"),
            "there is no trading day from 2021-02-13 to 2021-02-14",
        ),
        (
            ("--from", "2021-01-15", "--to", "2021-03-01"),
            (
                "the backtest starts on 2021-01-15, but the universe's membership is only known "
                "from 2021-02-01; start on 2021-02-01 or later"
            ),
        ),
    ],
)
def test_a_window_it_cannot_run_exits_2(market: Cli, window: tuple[str, ...], problem: str) -> None:
    assert market("backtest", *window) == (2, "", f"steadyhand-idx: {problem}\n")
    assert not (market.home / "reports").exists()


def test_a_start_before_the_rules_are_verified_exits_2_naming_the_table(market: Cli) -> None:
    assert market("backtest", "--from", "2020-06-01", "--to", "2021-03-01") == (
        2,
        "",
        (
            "steadyhand-idx: steadyhand's IDX rules are primary-verified from 2021-01-01, the "
            "first date of fees.toml [stamp_duty]; 2020-06-01 is earlier\n"
        ),
    )


def test_a_date_it_cannot_read_is_a_usage_error(market: Cli) -> None:
    result = market("backtest", "--from", "1 Feb 2021", "--to", "2022-01-31")
    assert result.code == 2
    assert "argument --from: write a date as 2021-02-01, not '1 Feb 2021'" in result.err


def test_a_missing_lq45_file_names_the_key(market: Cli) -> None:
    (market.home / "lq45_members.toml").unlink()
    result = market("backtest", *WINDOW)
    assert result.code == 2
    assert result.err == (
        f"steadyhand-idx: [universe] lq45_members points to {market.home / 'lq45_members.toml'}, "
        "which does not exist. steadyhand does not ship LQ45 lists: docs/lq45-members.md says "
        "where IDX publishes each one\n"
    )


def test_backtest_needs_the_configuration(cli: Cli) -> None:
    assert cli("backtest", *WINDOW) == (
        2,
        "",
        (
            f"steadyhand-idx: there is no configuration at {cli.config}; "
            "run steadyhand-idx init first\n"
        ),
    )


def test_a_holding_whose_old_prices_cannot_be_recovered_keeps_its_dividend_history(
    market: Cli,
) -> None:
    # The income report reads five years before the last day. Yahoo's BBRI prices before
    # 2021-09-07 carry an event it does not report, so they cannot be recovered, but a dividend
    # needs no price: the report is built, with BBRI's 6 April 2021 dividend in its run-rate
    # (M6 spec §4.3). Before M6 the whole run stopped with exit 3.
    result = market("backtest", "--from", "2022-01-25", "--to", "2022-01-31")
    assert (result.code, result.err) == (0, "")
    assert "Run-rate a month           IDR 208,538\n" in result.out
    found = golden_backtest(market, date(2022, 1, 31), goal=True, start=date(2022, 1, 25))
    assert found.run.income is not None
    held = {h.instrument.symbol: h.dividends for h in found.run.income.run_rate.holdings}
    assert [(d.ex_date, d.gross) for d in held["BBRI"]] == [(date(2021, 4, 6), Money(440_572, IDR))]


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
    yahoo = YahooDataSource(download=recorded, sleep=no_wait)
    with BarCache(tmp_path / "bars.sqlite") as cache:
        source = CachedDataSource(yahoo, cache, today=lambda: RECORDED)
        rules = IdxMarketRules(broker_fees="ajaib")
        expected = backtest(BuyAndHold(), Market(universe(), source, rules), START, END, settings())
    assert int(last[1]) == expected.run.reports[-1].value.amount
    assert int(last[1]) != golden.run.reports[-1].value.amount


def no_wait(seconds: float) -> None:
    del seconds


def test_monthly_savings_spreads_the_starting_cash_over_its_instalments(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home", GOLDEN_CONFIG + "\n[strategy]\ninstalments = 4\n")
    result = market("backtest", *WINDOW, "--strategy", "monthly-savings")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Backtest: monthly-savings, 2021-02-01 to 2022-01-31, 248 trading days\n\n"
    )
    assert result.out.split("\n\n")[1].splitlines()[:2] == [
        "                       monthly-savings     buy-and-hold",
        "Final value            IDR 100,655,756   IDR 97,889,490",
    ]
    daily = market.home / "reports" / "backtest-monthly-savings-2021-02-01-2022-01-31.csv"
    cash: dict[str, list[int]] = {}
    with daily.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            held = int(row["settled_cash"]) + int(row["unsettled_cash"])
            cash.setdefault(row["day"][:7], []).append(held)
    # Each instalment of 25,000,000 fills the day after the month's first trading day, and the
    # instalments still due stay back as cash until their month.
    for bought, month in enumerate(["2021-02", "2021-03", "2021-04", "2021-05"], start=1):
        reserve = (4 - bought) * 25_000_000
        assert reserve <= cash[month][1] < reserve + 25_000_000, month
