+++
id = "strategies.buy_and_hold"
title = "buy-and-hold, the yardstick"
summary = "The simplest strategy, and the one every backtest is measured against: buy once, in equal parts, then hold."
explains = []
module = "strategies"
position = 1
see_also = ["backtest.basics", "strategies.monthly_savings", "strategies.dividend_growth"]
sources = ["packages/steadyhand/src/steadyhand/strategies/guides/buy-and-hold.md", "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

`buy-and-hold` spends its starting cash on its first day, in equal parts, on every stock it can
buy. After that it never sells: dividends and new cash buy more of the same stocks.

Every backtest runs it beside the strategy you chose, over the same days and with the same
costs. A strategy that trades more has to do better than this to be worth its extra costs and
its extra decisions, and often does not. Its guide, which the explain command prints, gives the
whole rule, its settings and its risks.
