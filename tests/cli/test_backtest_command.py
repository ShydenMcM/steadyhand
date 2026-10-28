"""``backtest``: every refusal, and the whole command over a short made-up window (M5 spec §5.3,
§8.1). The golden window's real runs, a year of Yahoo's recorded answers read through the real
source and cache, are in ``tests/integration/cli/test_backtest_command_golden.py`` (#292); each
has its stand-in here, of the same name, over ``short_world``'s nineteen made-up days."""

import csv
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from cli_world import Cli, Result, market_cli
from short_world import GROWTH_CONFIG as SHORT_GROWTH_CONFIG
from short_world import PLACEHOLDERS as SHORT_PLACEHOLDERS
from short_world import RECORDED as SHORT_RECORDED
from short_world import RESTORED as SHORT_RESTORED
from short_world import SHORT_CONFIG, WEEK, WEEK_END, library_run, short_cli
from short_world import WINDOW as SHORT_WINDOW
from short_world import download as short_download

from steadyhand import DATA_BAR_REFUSED, DISCLAIMER, IDR, DataSource, Instrument, Money
from steadyhand_idx import IdxCalendar
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.training import catalogue
from steadyhand_idx.yahoo import (
    UnrecoverablePricesError,
    YahooDataSource,
    YahooHistory,
    unadjust,
)

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


# The real case, BBRI's rows before 2017-11-10 in the golden window, moved to
# tests/integration/cli/test_backtest_command_golden.py (#282). Its stand-in gives a made-up stock
# the same fault: an old row whose volume is not whole shares once its split is reversed.

OLD_ROW = date(2018, 12, 17)


def odd_volume(ticker: str, start: date, end: date) -> YahooHistory:
    """The made-up answer, but XBBB's first look-back row trades one share more than Yahoo's
    split-adjusted volumes allow: half a share once its 1-for-2 split is reversed (#162)."""
    answer = short_download(ticker, start, end)
    if ticker != "XBBB.JK":
        return answer
    rows = tuple(
        replace(row, volume=row.volume + 1) if row.day == OLD_ROW else row for row in answer.rows
    )
    return YahooHistory(ticker, rows, answer.splits)


@contextmanager
def odd_source(folder: Path) -> Iterator[DataSource]:
    del folder
    yield YahooDataSource(download=odd_volume, sleep=lambda _: None, today=lambda: SHORT_RECORDED)


def run_rate(page: str) -> str:
    found = [line for line in page.splitlines() if line.startswith("Run-rate a month")]
    assert len(found) == 1, page
    return found[0]


def test_a_holding_whose_old_prices_cannot_be_recovered_keeps_its_dividend_history(
    tmp_path: Path,
) -> None:
    xbbb = Instrument("XBBB", "IDX", IDR)
    old = odd_volume("XBBB.JK", OLD_ROW, OLD_ROW)
    with pytest.raises(UnrecoverablePricesError) as caught:
        unadjust(old, xbbb, IdxCalendar.shipped(), (OLD_ROW, OLD_ROW))
    assert caught.value.days == (OLD_ROW,)

    result = short_cli(tmp_path / "odd", source=odd_source)("backtest", *WEEK)
    assert (result.code, result.err) == (0, "")
    whole = short_cli(tmp_path / "whole")("backtest", *WEEK)
    assert whole.code == 0, whole.err
    assert run_rate(result.out) == run_rate(whole.out)


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
    assert sum(int(row[5]) for row in rows[1:]) == 825_000


def test_the_summary_shows_the_golden_figures(short: Cli) -> None:
    result = short("backtest", *SHORT_WINDOW)
    assert result.out.split("\n\n")[1].splitlines() == [
        "                          buy-and-hold",
        "Final value            IDR 104,467,795",
        "Deposited              IDR 100,000,000",
        "Total return                     4.47%",
        "Annual return                   76.79%",
        "Largest drawdown                 0.45%",
        "Trading costs              IDR 268,205",
        "Turnover a year                640.23%",
        "Dividends before tax       IDR 825,000",
        "Dividend tax                IDR 82,500",
        "Income goal a month          IDR 2,000",
        "Received a month            IDR 61,875",
        "Received, of the goal         3093.75%",
        "Run-rate a month           IDR 224,415",
        "Run-rate, of the goal        11220.75%",
    ]
    metrics = library_run().run.metrics
    assert metrics.final_value == Money(104_467_795, IDR)
    assert metrics.costs.total == Money(268_205, IDR)


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
        "| Final value | IDR 104,467,795 |",
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
        "Final value            IDR 101,282,692  IDR 101,629,434",
    ]


@pytest.mark.parametrize("month", SAVINGS_MONTHS)
def test_monthly_savings_keeps_back_the_instalments_still_due(
    savings: tuple[Result, dict[str, list[int]]], month: str
) -> None:
    # Each instalment of 50,000,000 fills the day after the month's first trading day, and the
    # instalment still due stays back as cash until its month. Worked by hand: a third of what it
    # may spend in each stock, as whole lots at the decision day's close, bought at the next open
    # plus 0.1% rounded up to the tick, paying 0.208% of each buy rounded up (0.15% commission
    # with 10% VAT, the levy 0.03% with VAT and the guarantee fund 0.01%) and 10,000 stamp duty.
    # 27 December keeps January's 50,000,000 back and buys 161 lots of XAAA at 1,025, 81 of XBBB
    # at 2,040 and 23 of XCCC at 7,125: 49,414,000 and 102,782 in fees, so 50,473,218 is left,
    # the 50,000,000 still due and 473,218 the lots could not use. 3 January spends it all: 161
    # lots of XAAA at 1,035, 81 of XBBB at 2,050 and 23 of XCCC at 7,175, 49,771,000 and 103,526
    # in fees, leaving 588,692.
    _, cash = savings
    assert cash[month][1] == {"2021-12": 50_473_218, "2022-01": 588_692}[month]
