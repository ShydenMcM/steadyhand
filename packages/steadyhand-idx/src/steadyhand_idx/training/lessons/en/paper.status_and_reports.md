+++
id = "paper.status_and_reports"
title = "Following your paper account"
summary = "What paper status and report show, and why the income report fetches data when the others do not."
explains = []
module = "using-steadyhand"
position = 8
see_also = ["paper.daily_run", "income.goal"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §7.1", "docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §7.2"]
+++

Three commands read the paper account without changing it.

- **`paper status`** shows the account as it stands after the last day run: its cash, settled
  and not yet settled, each holding with its last close, value and share of the whole, the
  orders waiting for the next open, dividends you are entitled to but have not been paid yet,
  and any stock that is frozen. If the account is halted, it says so and prints the exact
  command that resumes it.
- **`report`** shows one saved day: what was bought and sold, what was queued, which orders
  were blocked and why, the cash and value that evening, and the dividends paid and earned.
  It shows the latest day unless you name one with `--day`. Holdings are listed for the latest
  day only, because the account keeps today's positions, not every day's.
- **`report --income`** shows the income view: what the account has received, the run-rate,
  the payment calendar, how far you are from your income goal, and three projections. The
  projections are estimates, never promises. This is the one report that fetches data: it
  reads five years of each holding's dividends through the data source, as a backtest does.

None of these place an order or change a saved day.
