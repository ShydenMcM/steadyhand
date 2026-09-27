+++
id = "backtest.report"
title = "Reading a backtest's trading figures"
summary = "What turnover and the cash movements in a backtest report tell you about how much a strategy trades."
explains = ["term.turnover", "term.cash_movement"]
module = "using-steadyhand"
position = 2
see_also = ["backtest.basics", "costs.trading"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

A backtest report shows how the portfolio's value, returns and drawdown moved. Two figures in it
describe how much the strategy traded.

- **Turnover** is how much of the portfolio the strategy traded in a year: the value bought and
  the value sold, averaged, as a share of the average portfolio value, scaled to a year. A
  turnover of 100% means the strategy bought and sold about the whole portfolio once a year.
  Every trade costs money, so a high turnover needs a better result just to break even.
- **Cash movements** are every change to the portfolio's cash, one line each: a deposit, a
  purchase, a sale, a dividend, a tax, or a daily cost. Money coming in is positive and money going out
  is negative. Together they explain how the cash balance got to where it is.

Buy-and-hold has a very low turnover, because it hardly ever sells. That is part of why it is the
baseline every other strategy is compared with.
