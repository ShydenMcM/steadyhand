+++
id = "paper.halts_and_switching"
title = "Resuming after a halt, and switching strategy"
summary = "How to resume ordering after a safety limit halts the account, and how to move it to another strategy."
explains = ["paper.resumed", "paper.strategy.switched"]
module = "using-steadyhand"
position = 9
see_also = ["risk.limits", "paper.settings"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §7.3", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.1"]
+++

**Resuming.** When a safety limit halts the account, `paper run` keeps running the days (prices,
settlement and dividends carry on) but places no orders. Ordering starts again only when you
say so, with `resume` and the name of the account's strategy. It shows the halt's day and
cause and asks you to type `resume`. The audit log records that you resumed, who you are and
when.

`resume` refuses while the halt's cause is still there: if the unit value is still at or past
the drawdown limit below its high-water mark, resuming would only halt again. Wait for it to
recover, or raise `risk.max_drawdown` in `steadyhand.toml` if you have decided to accept more.

**Switching.** The account keeps the strategy it was opened with until you change it on purpose.
Edit `[strategy] name` in `steadyhand.toml`; `paper run` then refuses and prints the command to
run: `paper switch` with the new name. It asks you to type the name again. The holdings and the
cash stay as they are, and what the old strategy remembered is cleared, because it means nothing
to another one. From the next day run, the new strategy trades from the holdings it finds.
Switching is refused while the account is halted: resume first.

A switched account's record is no longer comparable with a backtest of either strategy, which is
why the switch is written in the audit log.
