"""Record the golden backtest's results (M3 spec §9).

    uv run python scripts/record_golden.py

runs ``buy-and-hold`` over the recorded Yahoo fixtures for ASII, BBCA, BBRI, TLKM and UNVR from
1 February 2021 to 31 January 2022, with an income goal, and writes everything the golden test pins,
its income report included, to
``tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json``. The window holds BBCA's
1-for-5 split, seven cash dividends, and 146 days of BBRI prices that Yahoo cannot unadjust (its
rights issue). The recordings reach back to 31 January 2017, five years before the run ends, for
the income report's dividend growth (M4 spec §9). Run it only after a change that moves the
numbers on purpose, and review the diff: the file is never edited by hand.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestResult,
    BacktestSettings,
    EngineSettings,
    IncomeFigures,
    IncomeGoal,
    IncomeReport,
    Market,
    Money,
    RiskLimits,
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
HISTORY_START = date(2017, 1, 31)
"""Where the recordings start: five years before the run ends (M4 spec §9)."""
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
RECORDED = date(2026, 9, 27)
"""The day the fixtures were recorded; the cache treats it as today."""


def settings(*, income: bool = True) -> BacktestSettings:
    """Rp100,000,000, 25% a stock so that five stocks can be fully invested (M3 spec §9), and a
    goal of Rp1,000,000 a month, so that the run carries an income report (M4 spec §9)."""
    limits = RiskLimits(max_weight=Decimal("0.25"))
    goal = IncomeGoal(Money(1_000_000, IDR)) if income else None
    return BacktestSettings(Money(100_000_000, IDR), EngineSettings(limits=limits), goal)


def recorded(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer. A range outside the recording is refused, never invented."""
    if start < HISTORY_START or end > END:
        msg = f"{ticker}: the fixture covers {HISTORY_START} to {END}, not {start} to {end}"
        raise ValueError(msg)
    name = f"{ticker}_{HISTORY_START.isoformat()}_{END.isoformat()}.json"
    return history_from_json(FIXTURES / name)


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
    folder: Path, strategy: str = "buy-and-hold", end: date = END, *, income: bool = True
) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules.

    Without *income* there is no goal, so no history is fetched before ``START``: an earlier
    *end* would need recordings from before ``HISTORY_START``.
    """
    folder.mkdir(parents=True, exist_ok=True)
    yahoo = YahooDataSource(download=recorded, sleep=_no_wait)
    with BarCache(folder / "bars.sqlite") as store:
        source = CachedDataSource(yahoo, store, today=lambda: RECORDED)
        market = Market(universe(), source, IdxMarketRules())
        return backtest(STRATEGIES[strategy](), market, START, end, settings(income=income))


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
        "positions": {p.instrument.symbol: p.quantity for p in portfolio.positions},
        "cash": portfolio.cash_balance().amount,
        "halt": None
        if outcome.halt is None
        else [outcome.halt.day.isoformat(), outcome.halt.cause],
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
    }


def _figures(figures: IncomeFigures) -> list[int]:
    return [
        figures.gross.amount,
        figures.tax.amount,
        figures.net.amount,
        figures.take_home.amount,
    ]


def record(folder: Path, golden: Path = GOLDEN) -> Path:
    """Run the golden backtest with its cache in *folder*, and write its summary to *golden*."""
    text = json.dumps(summary(run(folder)), indent=1, sort_keys=True) + "\n"
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(text, encoding="utf-8")
    return golden


def main(argv: list[str]) -> int:
    if argv:
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as scratch:
        print(record(Path(scratch)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
