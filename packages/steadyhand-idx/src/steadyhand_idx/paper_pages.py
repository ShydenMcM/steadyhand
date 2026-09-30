"""What the paper commands print (M5 spec §6, §7), built as ``Page``s for ``output.render``."""

from __future__ import annotations

from steadyhand import FIGURES
from steadyhand_idx.output import Page
from steadyhand_idx.paper import PaperRun
from steadyhand_idx.paths import APP


def paper_run_page(done: PaperRun) -> Page:
    """One line per day run, with the portfolio's value that evening, or that nothing was left to
    run."""
    page = Page()
    if not done.reports:
        page.add(f"already up to date for {done.target.isoformat()}")
        return page
    for report in done.reports:
        page.add(
            f"{report.day.isoformat()}: {len(report.fills)} fill(s), "
            f"{len(report.queued)} order(s) queued, value {report.value}",
            FIGURES["DayReport.value"],
        )
    first, last = done.reports[0].day, done.reports[-1].day
    days = first.isoformat() if first == last else f"{first.isoformat()} to {last.isoformat()}"
    page.add()
    page.add(f"Ran {len(done.reports)} day(s): {days}. Read a day's report with: {APP} report")
    return page
