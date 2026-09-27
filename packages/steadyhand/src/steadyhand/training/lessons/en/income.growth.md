+++
id = "income.growth"
title = "Dividend growth"
summary = "How fast your holdings' dividends a share have grown over the last four years, as a yearly rate."
explains = ["term.dividend_growth", "income.growth.short_history"]
module = "income-goal"
position = 4
see_also = ["income.projection", "income.run_rate"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.2"]
+++

For each holding, steadyhand compares the dividends one share paid over the last year with what
it paid over the year that ended four years earlier. It turns the change into a yearly rate: a
dividend that went from 100 to 146 a share over four years grew about 10% a year.

It measures dividends **a share**, so buying more shares does not count as growth. A split is
allowed for, so it does not look like a cut.

The portfolio's **dividend growth** is each holding's growth, weighted by how much of the
run-rate that holding provides. The projection uses it for its scenarios, capped or trimmed so
that a single good stretch does not carry too far.

**When a holding's history is too short.** If a holding paid nothing in the earlier year, or the
data does not reach back four years, its growth cannot be measured. steadyhand counts it as 0%
and names the holding in a note, so its growth is never guessed upwards.
