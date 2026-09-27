+++
id = "backtest.basics"
title = "What a backtest does"
summary = "A backtest runs a strategy day by day over past prices, with the same rules and costs as paper trading."
explains = []
module = "using-steadyhand"
position = 1
see_also = ["backtest.report", "risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §5"]
+++

A **backtest** asks: if I had run this strategy over these past years, what would have happened?

steadyhand answers it by stepping through the trading days one at a time. On each day it:

1. applies the day's corporate actions: splits, dividend entitlements, and dividends paid;
2. fills the orders it queued the day before, at today's opening price, charging the market's
   costs;
3. asks the strategy what it wants to hold, showing it prices up to today and no further;
4. turns that into orders in whole lots, and passes them through the safety limits;
5. queues those orders for tomorrow's open; and
6. values the portfolio at today's closing prices.

Deciding after today's close and filling at tomorrow's open is how a real investor would trade
on the same information, so the backtest never uses a price it could not have known. Paper
trading runs the same daily steps, so a strategy behaves the same in both.

Every backtest also runs plain buy-and-hold over the same days, so you can see whether the
strategy's extra trading added anything after its costs.
