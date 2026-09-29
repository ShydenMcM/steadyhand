+++
id = "paper.daily_run"
title = "Paper trading, one day at a time"
summary = "What paper run does each trading day, what it writes down, and why it sometimes stops."
explains = ["paper.account.opened", "paper.order.queued", "paper.order.skipped", "paper.order.cut", "paper.run.stopped"]
module = "using-steadyhand"
position = 4
see_also = ["paper.settings", "risk.limits"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §6", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.7"]
+++

Paper trading runs your strategy on real prices with pretend money. No order reaches a broker.
You run `paper run` once each trading day, after 16:30 in Jakarta, when the day's trading is
over.

The first run **opens** the paper account with your starting cash and your strategy. Each run
after that plays every trading day since the last one, oldest first, exactly as a backtest over
the same days would. If you miss a few days, the next run catches them up.

Each day, the strategy looks at the closing prices and decides what it wants to own. The orders
it makes are **queued**: they fill at the next day's open, as they would for you in your
broker's app. Some orders change on the way. An order is **cut** when a safety limit allows only
part of it, and **skipped** when it cannot be placed at all, for example because there is not
enough settled cash. Each one is written in the audit log with its reason.

A run **stops** when a day's prices cannot be trusted: a price is impossible, or the data source
has not published the day yet. Nothing trades on that day and it is not saved. Days caught up
before it stay saved, and the next run tries the day again.
