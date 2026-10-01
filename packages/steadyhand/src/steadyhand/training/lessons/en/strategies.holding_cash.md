+++
id = "strategies.holding_cash"
title = "When a strategy holds cash"
summary = "Why dividend-growth keeps part of the portfolio in cash when too few stocks pass its test, and what that costs."
explains = ["strategy.too_few_qualified"]
module = "strategies"
position = 4
see_also = ["dividends.basics", "risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

`dividend-growth` holds only stocks that passed its dividend test at its last yearly review, and
it gives each an equal share of the portfolio, never more than one part in `min_stocks` (15 by
default). When fewer stocks pass than that, it does not spread the money over the few it has:
the shares they would have taken stay in cash, and the report says how many stocks passed.

This keeps the portfolio from resting on a handful of companies, which is a risk of its own. The
cost is that cash earns nothing in steadyhand's model, so a year with many dividend cuts can
leave the portfolio holding a lot of it until the next review finds enough stocks passing again.
Lowering `min_stocks` puts more of the money to work in fewer stocks. Which way is better is a
choice about risk, and a backtest over past years only shows what it would have done then.
