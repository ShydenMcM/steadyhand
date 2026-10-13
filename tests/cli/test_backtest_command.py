"""``backtest``: every refusal, and the whole command over a short made-up window (M5 spec §5.3,
§8.1). The golden window's real runs, a year of Yahoo's recorded answers read through the real
source and cache, are in ``tests/integration/cli/test_backtest_command_golden.py`` (#292); each
has its stand-in here, of the same name, over ``short_world``'s nineteen made-up days."""

import csv
import stat
from datetime import date
from pathlib import Path

import pytest
from cli_world import Cli, Result, golden_backtest, market_cli
from short_world import GROWTH_CONFIG as SHORT_GROWTH_CONFIG
from short_world import PLACEHOLDERS as SHORT_PLACEHOLDERS
from short_world import RESTORED as SHORT_RESTORED
from short_world import SHORT_CONFIG, WEEK, WEEK_END, library_run, short_cli
from short_world import WINDOW as SHORT_WINDOW

from steadyhand import DATA_BAR_REFUSED, DISCLAIMER, IDR, Money
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.training import catalogue

WINDOW = ("--from", "2021-02-01", "--to", "2022-01-31")
STEM = "backtest-buy-and-hold-2021-02-01-2022-01-31"


@pytest.fixture
def market(tmp_path: Path) -> Cli:
    return market_cli(tmp_path / "home")


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
    # The income report reads five years before the last day. Yahoo's BBRI rows before
    # 2017-11-10 have volumes that are not whole shares once its split is reversed, so those days
    # cannot be recovered (#162), but a dividend needs no price: the report is built, with BBRI's
    # 6 April 2021 dividend in its run-rate (M6 spec §4.3), at its restored Rp98.9057 a share on
    # 4,900 shares (#160). Before M6 the whole run stopped with exit 3.
    result = market("backtest", "--from", "2022-01-25", "--to", "2022-01-31")
    assert (result.code, result.err) == (0, "")
    assert "Run-rate a month           IDR 211,843\n" in result.out
    found = golden_backtest(market, date(2022, 1, 31), goal=True, start=date(2022, 1, 25))
    assert found.run.income is not None
    held = {h.instrument.symbol: h.dividends for h in found.run.income.run_rate.holdings}
    assert [(d.ex_date, d.gross) for d in held["BBRI"]] == [(date(2021, 4, 6), Money(484_637, IDR))]


# The stand-ins of the golden-window tests moved to tests/integration/cli/
# test_backtest_command_golden.py (#292): each of the same name, over the made-up window.

SHORT_STEM = "backtest-buy-and-hold-2021-12-15-2022-01-11"
WEEK_STEM = "backtest-buy-and-hold-2021-12-15-2021-12-21"


@pytest.fixture
def short(tmp_path: Path) -> Cli:
    return short_cli(tmp_path / "home")


def test_the_daily_csv_is_the_golden_run_day_by_day(short: Cli) -> None:
    assert short("backtest", *SHORT_WINDOW).code == 0
    with (short.home / "reports" / f"{SHORT_STEM}.csv").open(encoding="utf-8", newline="") as file:
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
        for report in library_run().run.reports
    ]
    assert rows[1:] == expected
    assert len(expected) == 19
    assert sum(int(row[5]) for row in rows[1:]) == 617_500


def test_the_summary_shows_the_golden_figures(short: Cli) -> None:
    result = short("backtest", *SHORT_WINDOW)
    assert result.out.split("\n\n")[1].splitlines() == [
        "                          buy-and-hold",
        "Final value            IDR 103,359,041",
        "Deposited              IDR 100,000,000",
        "Total return                     3.36%",
        "Annual return                   53.83%",
        "Largest drawdown                 0.33%",
        "Trading costs              IDR 174,709",
        "Turnover a year                477.96%",
        "Dividends before tax       IDR 617,500",
        "Dividend tax                IDR 61,750",
        "Income goal a month          IDR 2,000",
        "Received a month            IDR 46,312",
        "Received, of the goal         2315.60%",
        "Run-rate a month           IDR 167,100",
        "Run-rate, of the goal         8355.00%",
    ]
    metrics = library_run().run.metrics
    assert metrics.final_value == Money(103_359_041, IDR)
    assert metrics.costs.total == Money(174_709, IDR)


def test_the_summary_then_the_warnings_the_files_and_the_explanations(short: Cli) -> None:
    result = short("backtest", *WEEK)
    assert result.err == ""
    reports = short.home / "reports"
    assert result.out.startswith(
        "Backtest: buy-and-hold, 2021-12-15 to 2021-12-21, 5 trading days\n\n"
    )
    # XCCC's prices are restored: the one warning says so, and nothing is refused.
    assert f"\n\nWarnings:\n- {SHORT_RESTORED}\n\n" in result.out
    stems = (reports / f"{WEEK_STEM}.md", reports / f"{WEEK_STEM}.csv")
    assert f"\n\nWrote {stems[0]}\nWrote {stems[1]}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    refused = catalogue().for_key(DATA_BAR_REFUSED).id
    assert f"More: steadyhand-idx learn {refused}\n" not in result.out
    restored = catalogue().for_key(DATA_PRICES_RESTORED).id
    assert f"More: steadyhand-idx learn {restored}\n" in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")


def test_the_markdown_file_holds_the_summary_and_the_disclaimer(short: Cli) -> None:
    short("backtest", *SHORT_WINDOW)
    text = (short.home / "reports" / f"{SHORT_STEM}.md").read_text(encoding="utf-8")
    assert text.splitlines()[:7] == [
        "# Backtest: buy-and-hold, 2021-12-15 to 2022-01-11",
        "",
        "19 trading days.",
        "",
        "|  | buy-and-hold |",
        "|---|---:|",
        "| Final value | IDR 103,359,041 |",
    ]
    assert f"\n## Warnings\n\n- {SHORT_RESTORED}\n" in text
    assert "## Day warnings" not in text
    assert text.endswith(f"\n\n---\n\n{DISCLAIMER}\n")


def test_the_reports_are_private_and_a_second_run_replaces_them(short: Cli) -> None:
    short("backtest", *WEEK)
    reports = short.home / "reports"
    first = {path.name: path.read_bytes() for path in reports.iterdir()}
    assert short("backtest", *WEEK).code == 0
    assert {path.name: path.read_bytes() for path in reports.iterdir()} == first
    assert sorted(first) == [f"{WEEK_STEM}.csv", f"{WEEK_STEM}.md"]
    assert stat.S_IMODE(reports.stat().st_mode) == 0o700
    for path in reports.iterdir():  # runtime population: the files the run wrote
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_a_member_with_no_bars_gives_day_warnings_in_the_file(short: Cli) -> None:
    exclusions = short.home / "exclusions.csv"
    lines = exclusions.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith(SHORT_PLACEHOLDERS[0])]
    exclusions.write_text("".join(kept), encoding="utf-8")
    assert short("backtest", *WEEK).code == 0
    text = (short.home / "reports" / f"{WEEK_STEM}.md").read_text(encoding="utf-8")
    assert "\n## Day warnings\n\n- buy-and-hold, 2021-12-15: ZAAA has no bar on 2021-12-15" in text
    assert text.count(": ZAAA has no bar on ") == 5


def test_the_strategy_comes_from_the_configuration_or_the_option(short: Cli) -> None:
    named = short("backtest", *WEEK, "--strategy", "buy-and-hold")
    assert named.code == 0
    assert named.out == short("backtest", *WEEK).out


def test_the_starting_cash_and_goal_come_from_the_configuration(tmp_path: Path) -> None:
    short = short_cli(tmp_path / "home", SHORT_CONFIG.replace("100_000_000", "50_000_000"))
    result = short("backtest", *WEEK)
    (deposited,) = [line for line in result.out.splitlines() if line.startswith("Deposited ")]
    assert deposited.endswith(" IDR 50,000,000")


def test_the_broker_fee_preset_comes_from_the_configuration(tmp_path: Path) -> None:
    config = SHORT_CONFIG.replace("[account]\n", '[account]\nbroker_fees = "ajaib"\n')
    short = short_cli(tmp_path / "home", config)
    assert short("backtest", *WEEK).code == 0
    with (short.home / "reports" / f"{WEEK_STEM}.csv").open(encoding="utf-8", newline="") as file:
        last = list(csv.reader(file))[-1]
    expected = library_run(end=WEEK_END, broker_fees="ajaib").run.reports[-1].value.amount
    assert int(last[1]) == expected
    assert expected != library_run(end=WEEK_END).run.reports[-1].value.amount


def test_dividend_growth_reads_its_look_back_and_ends_as_the_library_run(tmp_path: Path) -> None:
    short = short_cli(tmp_path / "home", SHORT_GROWTH_CONFIG)
    result = short("backtest", *WEEK, "--strategy", "dividend-growth")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Backtest: dividend-growth, 2021-12-15 to 2021-12-21, 5 trading days\n\n"
    )
    daily = short.home / "reports" / "backtest-dividend-growth-2021-12-15-2021-12-21.csv"
    with daily.open(encoding="utf-8", newline="") as file:
        last = list(csv.reader(file))[-1]
    expected = library_run("dividend-growth", end=WEEK_END).run.reports[-1].value.amount
    assert int(last[1]) == expected
    # Blind to its three years of dividends, nothing would pass and it would hold only cash.
    assert expected != 100_000_000


SAVINGS_MONTHS = ("2021-12", "2022-01")


@pytest.fixture
def savings(tmp_path: Path) -> tuple[Result, dict[str, list[int]]]:
    """One monthly-savings run over two instalments, December's and January's, and the cash it
    held each day, by month."""
    config = SHORT_CONFIG.replace('name = "buy-and-hold"', 'name = "buy-and-hold"\ninstalments = 2')
    short = short_cli(tmp_path / "home", config)
    window = ("--from", "2021-12-27", "--to", "2022-01-07")
    result = short("backtest", *window, "--strategy", "monthly-savings")
    daily = short.home / "reports" / "backtest-monthly-savings-2021-12-27-2022-01-07.csv"
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
        "Backtest: monthly-savings, 2021-12-27 to 2022-01-07, 9 trading days\n\n"
    )
    assert result.out.split("\n\n")[1].splitlines()[:2] == [
        "                       monthly-savings     buy-and-hold",
        "Final value            IDR 101,042,022  IDR 101,228,538",
    ]


@pytest.mark.parametrize("month", SAVINGS_MONTHS)
def test_monthly_savings_keeps_back_the_instalments_still_due(
    savings: tuple[Result, dict[str, list[int]]], month: str
) -> None:
    # Each instalment of 50,000,000 fills the day after the month's first trading day, and the
    # instalment still due stays back as cash until its month.
    _, cash = savings
    reserve = (len(SAVINGS_MONTHS) - 1 - SAVINGS_MONTHS.index(month)) * 50_000_000
    assert reserve <= cash[month][1] < reserve + 50_000_000
