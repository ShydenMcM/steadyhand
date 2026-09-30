"""The reports ``backtest`` and ``compare`` print and write: a terminal summary, a Markdown file and
a CSV (M5 spec §5.3, §5.4).

Every figure a report shows is a ``Figure``: its CSV column, its label on screen, and the report
field it shows, whose term key T1 explains it with (read from ``steadyhand.terms.FIGURES``, never
retyped). The terminal, the Markdown and the CSV all read the same lists, so they cannot disagree.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

from steadyhand import (
    DISCLAIMER,
    FIGURES,
    BacktestResult,
    Comparison,
    GoalProgress,
    Metrics,
    Money,
    Note,
    RunResult,
)
from steadyhand_idx.output import Page
from steadyhand_idx.paths import make_private_dir, replace_private

type Value = Money | Decimal


@dataclass(frozen=True, slots=True)
class Figure:
    """One figure: ``name`` heads its CSV column, ``label`` its row on screen, and ``field`` is
    the report field it shows, as ``steadyhand.terms.FIGURES`` names it."""

    name: str
    label: str
    field: str

    @property
    def key(self) -> str:
        """The term that explains this figure (T1 spec §3.2)."""
        return FIGURES[self.field]


RUN_FIGURES: Final[tuple[tuple[Figure, Callable[[Metrics], Value]], ...]] = (
    (Figure("final_value", "Final value", "Metrics.final_value"), lambda m: m.final_value),
    (Figure("deposited", "Deposited", "Metrics.deposited"), lambda m: m.deposited),
    (Figure("total_return", "Total return", "Metrics.total_return"), lambda m: m.total_return),
    (Figure("annual_return", "Annual return", "Metrics.annual_return"), lambda m: m.annual_return),
    (Figure("drawdown", "Largest drawdown", "Drawdown.depth"), lambda m: m.drawdown.depth),
    (Figure("costs", "Trading costs", "CostBreakdown.total"), lambda m: m.costs.total),
    (Figure("turnover", "Turnover a year", "Metrics.turnover"), lambda m: m.turnover),
    (
        Figure("dividends_gross", "Dividends before tax", "DividendTotals.gross"),
        lambda m: m.dividends.gross,
    ),
    (Figure("dividend_tax", "Dividend tax", "DividendTotals.tax"), lambda m: m.dividends.tax),
)
"""The figures every run has (M3 spec §8)."""

GOAL_FIGURES: Final[tuple[tuple[Figure, Callable[[GoalProgress], Value]], ...]] = (
    (Figure("goal", "Income goal a month", "GoalProgress.target"), lambda g: g.target),
    (Figure("received", "Received a month", "GoalProgress.received"), lambda g: g.received),
    (
        Figure("received_share", "Received, of the goal", "GoalProgress.received_share"),
        lambda g: g.received_share,
    ),
    (Figure("run_rate", "Run-rate a month", "GoalProgress.run_rate"), lambda g: g.run_rate),
    (
        Figure("run_rate_share", "Run-rate, of the goal", "GoalProgress.run_rate_share"),
        lambda g: g.run_rate_share,
    ),
)
"""The income-goal figures, which a run has when its settings set a goal (M4 spec §8)."""

DAY_COLUMNS: Final = (
    "day",
    "value",
    "settled_cash",
    "unsettled_cash",
    "holdings_value",
    "dividends_gross",
    "dividend_tax",
)
"""The daily CSV's columns. Amounts are whole rupiah; ``dividend_tax`` is all the dividend tax
booked that day, which with the exemption on includes tax on earlier dividends (M4 spec §6)."""


def figures(runs: Sequence[RunResult]) -> list[Figure]:
    """The figures every one of *runs* has: the income figures only when each has a goal."""
    shown = [figure for figure, _ in RUN_FIGURES]
    if all(run.income is not None for run in runs):
        shown += [figure for figure, _ in GOAL_FIGURES]
    return shown


def values(run: RunResult) -> dict[str, Value]:
    """Each figure *run* has, by name."""
    found = {figure.name: read(run.metrics) for figure, read in RUN_FIGURES}
    if run.income is not None:
        found |= {figure.name: read(run.income.goal) for figure, read in GOAL_FIGURES}
    return found


def show(value: Value) -> str:
    """*value* as a person reads it: money with its currency, a rate as a percentage."""
    if isinstance(value, Money):
        return str(value)
    return f"{value * 100:.2f}%"


def raw(value: Value) -> str:
    """*value* as a spreadsheet reads it: money in whole rupiah, a rate as a decimal."""
    return str(value.amount) if isinstance(value, Money) else str(value)


def backtest_files(result: BacktestResult, folder: Path) -> tuple[Path, Path]:
    """Write the backtest's Markdown summary and its daily CSV into *folder*, replacing any
    earlier run over the same range (M5 spec §5.3)."""
    stem = f"backtest-{result.run.strategy}-{result.start}-{result.end}"
    runs = _runs(result)
    markdown = [
        f"# Backtest: {result.run.strategy}, {result.start} to {result.end}",
        "",
        f"{len(result.run.reports)} trading days.",
        "",
        *_markdown_table(["", *(run.strategy for run in runs)], _by_figure(runs)),
        *_markdown_notes(runs, result.warnings),
    ]
    days = [
        [
            report.day.isoformat(),
            *(
                str(amount.amount)
                for amount in (
                    report.value,
                    report.settled,
                    report.unsettled,
                    report.holdings_value,
                    sum((paid.gross for paid in report.paid), Money.zero(report.value.currency)),
                    report.tax,
                )
            ),
        ]
        for report in result.run.reports
    ]
    return _write(folder, stem, markdown, [list(DAY_COLUMNS), *days])


def backtest_page(result: BacktestResult, written: Sequence[Path]) -> Page:
    """The terminal summary: the strategy beside ``buy-and-hold``, then warnings (§5.3)."""
    runs = _runs(result)
    page = Page()
    page.add(
        f"Backtest: {result.run.strategy}, {result.start} to {result.end}, "
        f"{len(result.run.reports)} trading days"
    )
    page.add()
    header = ["", *(run.strategy for run in runs)]
    for line, figure in zip(
        text_table([header, *_by_figure(runs)]), [None, *figures(runs)], strict=True
    ):
        page.add(line, *([] if figure is None else [figure.key]))
    _page_notes(page, runs, result.warnings, written)
    return page


def comparison_files(comparison: Comparison, folder: Path) -> tuple[Path, Path]:
    """Write the comparison's Markdown table and its CSV, a row per strategy (M5 spec §5.4)."""
    stem = f"compare-{comparison.start}-{comparison.end}"
    runs = comparison.runs
    shown = figures(runs)
    markdown = [
        f"# Comparison, {comparison.start} to {comparison.end}",
        "",
        f"{_days(comparison)} trading days.",
        "",
        *_markdown_table(
            ["Strategy", *(figure.label for figure in shown)], _by_run(runs, shown, show)
        ),
        *_markdown_notes(runs, comparison.warnings),
    ]
    table = [["strategy", *(figure.name for figure in shown)], *_by_run(runs, shown, raw)]
    return _write(folder, stem, markdown, table)


def comparison_page(comparison: Comparison, written: Sequence[Path]) -> Page:
    """The terminal table: a row per strategy, with the same figures as ``backtest``."""
    runs = comparison.runs
    shown = figures(runs)
    page = Page()
    page.add(
        f"Comparison, {comparison.start} to {comparison.end}, {_days(comparison)} trading days"
    )
    page.add()
    header = ["Strategy", *(figure.label for figure in shown)]
    lines = text_table([header, *_by_run(runs, shown, show)])
    page.add(lines[0], *(figure.key for figure in shown))
    for line in lines[1:]:
        page.add(line)
    _page_notes(page, runs, comparison.warnings, written)
    return page


def _runs(result: BacktestResult) -> tuple[RunResult, ...]:
    return (result.run,) if result.baseline is None else (result.run, result.baseline)


def _days(comparison: Comparison) -> int:
    return len(comparison.runs[0].reports)


def _by_figure(runs: Sequence[RunResult]) -> list[list[str]]:
    """A row per figure, a column per run."""
    found = [values(run) for run in runs]
    return [
        [figure.label, *(show(each[figure.name]) for each in found)] for figure in figures(runs)
    ]


def _by_run(
    runs: Sequence[RunResult], shown: Sequence[Figure], form: Callable[[Value], str]
) -> list[list[str]]:
    """A row per run, a column per figure."""
    return [[run.strategy, *(form(values(run)[figure.name]) for figure in shown)] for run in runs]


def _halts(runs: Sequence[RunResult]) -> list[tuple[str, str]]:
    """Each halt's line, and the key of the limit it reached."""
    return [
        (
            f"{run.strategy} stopped ordering on {run.halt.day}: {run.halt.cause.text}",
            run.halt.cause.key,
        )
        for run in runs
        if run.halt is not None
    ]


def _page_notes(
    page: Page, runs: Sequence[RunResult], warnings: Sequence[Note], written: Sequence[Path]
) -> None:
    for halt, key in _halts(runs):
        page.add()
        page.add(halt, key)
    if warnings:
        page.add()
        page.add("Warnings:")
        for warning in warnings:
            page.add(f"- {warning.text}", warning.key)
    page.add()
    for path in written:
        page.add(f"Wrote {path}")


def _markdown_notes(runs: Sequence[RunResult], warnings: Sequence[Note]) -> list[str]:
    lines = [line for halt, _key in _halts(runs) for line in ("", halt)]
    if warnings:
        lines += ["", "## Warnings", "", *(f"- {warning.text}" for warning in warnings)]
    day_warnings = [
        f"- {run.strategy}, {report.day}: {warning.text}"
        for run in runs
        for report in run.reports
        for warning in report.warnings
    ]
    if day_warnings:
        lines += ["", "## Day warnings", "", *day_warnings]
    return [*lines, "", "---", "", DISCLAIMER]


def text_table(rows: Sequence[Sequence[str]]) -> list[str]:
    """*rows* in columns: the first left-aligned, the rest right-aligned, two spaces apart."""
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(
            cell.ljust(width) if column == 0 else cell.rjust(width)
            for column, (cell, width) in enumerate(zip(row, widths, strict=True))
        ).rstrip()
        for row in rows
    ]


def _markdown_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        f"| {' | '.join(header)} |",
        f"|---|{'---:|' * (len(header) - 1)}",
        *(f"| {' | '.join(row)} |" for row in rows),
    ]


def _write(
    folder: Path, stem: str, markdown: Sequence[str], table: Sequence[Sequence[str]]
) -> tuple[Path, Path]:
    make_private_dir(folder)
    text = io.StringIO()
    csv.writer(text, lineterminator="\n").writerows(table)
    summary, daily = folder / f"{stem}.md", folder / f"{stem}.csv"
    replace_private(summary, "\n".join(markdown) + "\n")
    replace_private(daily, text.getvalue())
    return summary, daily
