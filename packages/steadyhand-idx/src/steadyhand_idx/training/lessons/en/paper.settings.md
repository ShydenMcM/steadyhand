+++
id = "paper.settings"
title = "Changing your settings while paper trading"
summary = "A changed setting applies from the next day run and is written in the audit log; the starting cash never changes after opening."
explains = ["paper.setting.changed", "paper.setting.starting_cash_ignored"]
module = "using-steadyhand"
position = 5
see_also = ["paper.daily_run"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §6.5"]
+++

You can change most settings in `steadyhand.toml` while a paper account is running: the monthly
contribution, the safety limits, your broker's fee preset, the dividend settings and your income
goal. The next day that `paper run` plays uses the new value, and the audit log records which
setting changed, from what to what, and from which day.

Two settings behave differently:

- **The starting cash** is used only on the day the account opens. Changing it later does not
  add or remove money. The audit log says once that the change was seen and has no effect. To
  add money, set a monthly contribution instead.
- **The strategy** does not change just because the file changes. `paper run` refuses to run
  and tells you the `paper switch` command that makes the change on purpose.

A paper account run with its settings unchanged ends exactly where a backtest over the same
days ends. Once you change a setting, its record is no longer comparable with such a backtest,
which is why each change is written down.
