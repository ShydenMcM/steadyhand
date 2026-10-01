"""Record the golden backtests' results (M3 spec §9, M4 spec §9).

    uv run python scripts/record_golden.py

runs ``buy-and-hold`` over the recorded Yahoo fixtures for ASII, BBCA, BBRI, TLKM and UNVR from
1 February 2021 to 31 January 2022, with an income goal, and writes everything the golden test pins,
its income report included, to
``tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json``. The window holds BBCA's
1-for-5 split, seven cash dividends, and 146 days of BBRI prices that Yahoo cannot unadjust (its
rights issue). The recordings reach back to 31 January 2017, five years before the run ends, for
the income report's dividend growth (M4 spec §9).

It then runs ``ExemptionScript`` with the dividend reinvestment exemption on, from 1 February 2021
to 29 April 2022, over longer recordings of the same stocks, and writes
``tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json``. That window passes the
31 March 2022 deadline of the 2021 dividends, so the run holds a claim of each kind.

Last it runs ``dividend-growth`` over the first run's window with ``VALUES``, a two-year test
whose three-year look-back (from 1 January 2018) fits in the recordings, and with TLKM's
look-back refused by script, and writes
``tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json``. The look-back holds UNVR's
2020 split, and the window crosses into 2022, where the strategy reviews again.

Run it only after a change that moves the numbers on purpose, and review the diff: the files are
never edited by hand.
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestResult,
    BacktestSettings,
    DataUnavailableError,
    Decision,
    DividendClaim,
    EngineSettings,
    IncomeFigures,
    IncomeGoal,
    IncomeReport,
    Market,
    MarketView,
    Memory,
    Money,
    PortfolioView,
    RiskLimits,
    Strategy,
    backtest,
)
from steadyhand_idx import IdxMarketRules
from steadyhand_idx.cache import BarCache, CachedDataSource
from steadyhand_idx.universe import Lq45Membership, Lq45Record, Lq45Universe
from steadyhand_idx.yahoo import YahooDataSource, YahooHistory, history_from_json

TESTS = Path(__file__).resolve().parents[1] / "tests"
FIXTURES = TESTS / "fixtures" / "yahoo"
GOLDEN = TESTS / "fixtures" / "golden" / "buy-and-hold_2021-02-01_2022-01-31.json"
START, END = date(2021, 2, 1), date(2022, 1, 31)
EXEMPT_GOLDEN = TESTS / "fixtures" / "golden" / "exemption-script_2021-02-01_2022-04-29.json"
EXEMPT_END = date(2022, 4, 29)
"""The switch-on run's last day, past the 31 March 2022 deadline of every 2021 dividend."""
TOP_UP, SELL_DOWN = date(2021, 7, 1), date(2021, 11, 1)
HISTORY_START = date(2017, 1, 31)
"""Where the recordings start: five years before the run ends (M4 spec §9)."""
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
GROWTH_GOLDEN = TESTS / "fixtures" / "golden" / "dividend-growth_2021-02-01_2022-01-31.json"
VALUES = {"instalments": 12, "min_stocks": 2, "max_stocks": 2, "growth_years": 2}
"""Every registered strategy's settings in the golden runs. ``dividend-growth`` tests two years
of growth, so its look-back of three years, from 1 January 2018, fits in the recordings."""
REFUSED_HISTORY = "TLKM.JK"
"""The stock whose look-back the ``dividend-growth`` golden run is refused."""
RECORDED = date(2026, 9, 27)
"""The day the fixtures were recorded; the cache treats it as today."""


def settings(*, income: bool = True, exemption: bool = False) -> BacktestSettings:
    """Rp100,000,000, 25% a stock so that five stocks can be fully invested (M3 spec §9), and a
    goal of Rp1,000,000 a month, so that the run carries an income report (M4 spec §9)."""
    limits = RiskLimits(max_weight=Decimal("0.25"))
    goal = IncomeGoal(Money(1_000_000, IDR)) if income else None
    engine = EngineSettings(limits=limits, dividend_reinvestment_exemption=exemption)
    return BacktestSettings(Money(100_000_000, IDR), engine, goal)


def recorded(ticker: str, start: date, end: date, *, last: date = END) -> YahooHistory:
    """Yahoo's recorded answer from the recordings ending on *last*. A range outside the
    recording is refused, never invented."""
    if start < HISTORY_START or end > last:
        msg = f"{ticker}: the fixture covers {HISTORY_START} to {last}, not {start} to {end}"
        raise ValueError(msg)
    name = f"{ticker}_{HISTORY_START.isoformat()}_{last.isoformat()}.json"
    return history_from_json(FIXTURES / name)


def recorded_refusing_history(ticker: str, start: date, end: date) -> YahooHistory:
    """The recordings, except that TLKM's look-back is refused, as Yahoo refuses a stock it
    has nothing for: a range that ends before the run and starts after ``HISTORY_START``, where
    the income report's history starts."""
    if ticker == REFUSED_HISTORY and start > HISTORY_START and end < START:
        msg = f"{ticker}: refused by the golden test's script"
        raise DataUnavailableError(msg)
    return recorded(ticker, start, end)


def recorded_to_exempt_end(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer from the longer recordings the switch-on run reads."""
    return recorded(ticker, start, end, last=EXEMPT_END)


class ExemptionScript:
    """The switch-on golden run's trader: it trades on three set days only (M4 spec §9).

    On its first day it buys what it can at 10% each. On ``TOP_UP`` it raises that to 19% each,
    which reinvests the dividends paid since. On ``SELL_DOWN`` it keeps half a percent in BBCA and
    sells the rest, so less is invested than is protected and part of a claim breaks. The
    dividends paid after that are never reinvested, so they are taxed at their deadline. On any
    other day it keeps what it holds. It is a test fixture, not a strategy anyone should run.
    """

    @property
    def name(self) -> str:
        return "exemption-script"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        del memory
        day, buyable = view.today, view.tradable.buyable
        if not portfolio.holdings and day < TOP_UP:
            return Decision(dict.fromkeys(buyable, Decimal("0.10")))
        if day == TOP_UP:
            return Decision(dict.fromkeys(buyable, Decimal("0.19")))
        if day == SELL_DOWN:
            return Decision(
                {stock: Decimal("0.005") for stock in buyable if stock.symbol == "BBCA"}
            )
        return Decision({stock: portfolio.weight(stock) for stock in portfolio.holdings})


def universe() -> Lq45Universe:
    """The five stocks as the whole universe. It is a test selection, not an LQ45 list: the
    loader takes only full lists of 45, and steadyhand ships none (t-lq45.md §5)."""
    record = Lq45Record(
        START,
        START,
        "steadyhand golden test: five stocks chosen for their events, not an LQ45 list",
        "review",
        frozenset(STOCKS),
    )
    return Lq45Universe(Lq45Membership([record]))


def run(
    folder: Path,
    strategy: str = "buy-and-hold",
    end: date = END,
    *,
    income: bool = True,
    download: Callable[[str, date, date], YahooHistory] = recorded,
) -> BacktestResult:
    """Back-test *strategy*, made from ``VALUES`` with its look-back, from ``START`` to *end*
    through the real source, cache and rules.

    Without *income* there is no goal, so no history is fetched before ``START``: an earlier
    *end* would need recordings from before ``HISTORY_START``.
    """
    entry = STRATEGIES[strategy]
    chosen = replace(settings(income=income), lookback_years=entry.lookback_years(VALUES))
    return _backtest(folder, entry(VALUES), end, chosen, download)


def run_growth(folder: Path) -> BacktestResult:
    """Back-test ``dividend-growth`` over the first run's window, TLKM's look-back refused."""
    return run(folder, "dividend-growth", download=recorded_refusing_history)


def run_exempt(folder: Path) -> BacktestResult:
    """Back-test ``ExemptionScript`` from ``START`` to ``EXEMPT_END`` with the exemption on."""
    exempt = settings(exemption=True)
    return _backtest(folder, ExemptionScript(), EXEMPT_END, exempt, recorded_to_exempt_end)


def _backtest(
    folder: Path,
    strategy: Strategy,
    end: date,
    backtest_settings: BacktestSettings,
    download: Callable[[str, date, date], YahooHistory],
) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules."""
    folder.mkdir(parents=True, exist_ok=True)
    yahoo = YahooDataSource(download=download, sleep=_no_wait)
    with BarCache(folder / "bars.sqlite") as store:
        source = CachedDataSource(yahoo, store, today=lambda: RECORDED)
        market = Market(universe(), source, IdxMarketRules())
        return backtest(strategy, market, START, end, backtest_settings)


def _no_wait(seconds: float) -> None:
    del seconds


def summary(result: BacktestResult) -> dict[str, object]:
    """Everything the golden file pins, as JSON values."""
    outcome, metrics = result.run, result.run.metrics
    portfolio = outcome.final.holdings.portfolio
    return {
        "window": [result.start.isoformat(), result.end.isoformat()],
        "strategy": outcome.strategy,
        "days": [[r.day.isoformat(), r.value.amount, str(r.unit_price)] for r in outcome.reports],
        "fills": [
            [
                f.day.isoformat(),
                f.order.instrument.symbol,
                f.order.side.value,
                f.quantity,
                f.price.amount,
                f.costs.fee.amount,
                f.costs.levy.amount,
                f.costs.tax.amount,
            ]
            for r in outcome.reports
            for f in r.fills
        ],
        "dividends": [
            [r.day.isoformat(), e.instrument.symbol, e.ex_date.isoformat(), e.gross.amount]
            for r in outcome.reports
            for e in r.paid
        ],
        "taxes": [[r.day.isoformat(), r.tax.amount] for r in outcome.reports if r.tax.amount],
        "notes": [
            [r.day.isoformat(), note.key, note.text] for r in outcome.reports for note in r.notes
        ],
        "claims": [_claim(claim) for claim in outcome.final.holdings.claims],
        "positions": {p.instrument.symbol: p.quantity for p in portfolio.positions},
        "cash": portfolio.cash_balance().amount,
        "halt": None
        if outcome.halt is None
        else [outcome.halt.day.isoformat(), outcome.halt.cause.text],
        "warnings": [[note.key, note.text] for note in (*result.warnings, *outcome.warnings)],
        "metrics": {
            "final_value": metrics.final_value.amount,
            "deposited": metrics.deposited.amount,
            "total_return": str(metrics.total_return),
            "annual_return": str(metrics.annual_return),
            "drawdown": [
                str(metrics.drawdown.depth),
                metrics.drawdown.peak.isoformat(),
                metrics.drawdown.trough.isoformat(),
            ],
            "costs": {
                "fee": metrics.costs.fee.amount,
                "levy": metrics.costs.levy.amount,
                "sale_tax": metrics.costs.sale_tax.amount,
                "daily": metrics.costs.daily.amount,
            },
            "turnover": str(metrics.turnover),
            "dividends": {
                "gross": metrics.dividends.gross.amount,
                "tax": metrics.dividends.tax.amount,
            },
            "trailing_income": metrics.trailing_income.amount,
        },
        "income": _income(outcome.income),
    }


def _income(report: IncomeReport | None) -> object:
    """Every figure of an income report, as JSON values."""
    if report is None:
        return None
    received, rate, growth = report.received, report.run_rate, report.growth
    goal = report.goal
    return {
        "as_of": report.as_of.isoformat(),
        "received": {
            "by_month": [[m.month.isoformat(), *_figures(m.figures)] for m in received.by_month],
            "trailing": _figures(received.trailing),
            "monthly_average": _figures(received.monthly_average),
            "yields": [str(received.current_yield), str(received.yield_on_cost)],
        },
        "run_rate": {
            "holdings": [
                [
                    h.instrument.symbol,
                    h.shares,
                    h.annual_gross.amount,
                    h.monthly_take_home.amount,
                    [
                        [e.ex_date.isoformat(), e.pay_date.isoformat(), e.gross.amount]
                        for e in h.dividends
                    ],
                ]
                for h in rate.holdings
            ],
            "annual_gross": rate.annual_gross.amount,
            "monthly_take_home": rate.monthly_take_home.amount,
        },
        "calendar": {
            "months": [month.amount for month in report.calendar.months],
            "empty_months": report.calendar.empty_months,
            "evenness": str(report.calendar.evenness),
        },
        "growth": {
            "holdings": [
                [g.instrument.symbol, str(g.recent), str(g.earlier), str(g.growth)]
                for g in growth.holdings
            ],
            "portfolio": str(growth.portfolio),
            "notes": [[note.key, note.text] for note in growth.notes],
        },
        "projection": [
            [
                s.scenario.value,
                s.starting_gross.amount,
                str(s.growth),
                s.outcome.value,
                None if s.years is None else str(s.years),
            ]
            for s in report.projection.scenarios
        ],
        "goal": [
            goal.target.amount,
            goal.received.amount,
            str(goal.received_share),
            goal.run_rate.amount,
            str(goal.run_rate_share),
        ],
        "claims": [report.claims_label, [_claim(claim) for claim in report.claims]],
    }


def _claim(claim: DividendClaim) -> list[object]:
    return [
        claim.instrument.symbol,
        claim.ex_date.isoformat(),
        claim.pay_date.isoformat(),
        claim.gross.amount,
        claim.deadline.isoformat(),
        claim.uncovered.amount,
        [[p.amount.amount, p.until.isoformat()] for p in claim.protections],
    ]


def _figures(figures: IncomeFigures) -> list[int]:
    return [
        figures.gross.amount,
        figures.tax.amount,
        figures.net.amount,
        figures.take_home.amount,
    ]


def record(folder: Path, golden: Path = GOLDEN) -> Path:
    """Run the golden backtest with its cache in *folder*, and write its summary to *golden*."""
    return _write(summary(run(folder)), golden)


def record_exempt(folder: Path, golden: Path = EXEMPT_GOLDEN) -> Path:
    """Run the switch-on golden backtest with its cache in *folder*, and write its summary."""
    return _write(summary(run_exempt(folder)), golden)


def record_growth(folder: Path, golden: Path = GROWTH_GOLDEN) -> Path:
    """Run the ``dividend-growth`` golden backtest with its cache in *folder*, and write its
    summary to *golden*."""
    return _write(summary(run_growth(folder)), golden)


def _write(pinned: dict[str, object], golden: Path) -> Path:
    text = json.dumps(pinned, indent=1, sort_keys=True) + "\n"
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(text, encoding="utf-8")
    return golden


def main(argv: list[str]) -> int:
    if argv:
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as scratch:
        print(record(Path(scratch) / "buy-and-hold"))
        print(record_exempt(Path(scratch) / "exemption"))
        print(record_growth(Path(scratch) / "dividend-growth"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
