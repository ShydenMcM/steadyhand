+++
id = "risk.returns"
title = "Returns, counted fairly"
summary = "How steadyhand measures gain or loss so that money you pay in is never counted as profit."
explains = ["term.total_return", "term.annual_return", "term.unit_price", "term.units", "term.deposit"]
module = "risk"
position = 2
see_also = ["risk.drawdown"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

If you pay 1,000,000 into a portfolio and it is later worth 1,100,000, it looks like a 10% gain.
But if you paid in another 100,000 along the way, the portfolio gained nothing: the extra value
is your own money.

steadyhand avoids that mistake by counting the portfolio like a fund.

- A **deposit** is money you pay in: the starting capital, and any monthly top-up.
- Each deposit buys **units** at the current **unit price**. The first deposit buys units at a
  price of 1. A deposit leaves the unit price unchanged, because the money it adds is matched
  by the units it buys.
- After that the unit price moves only with the investments: price changes, dividends and
  costs.

The **total return** is how much the unit price changed over the run. A unit price that went
from 1.00 to 1.25 is a total return of 25%, however much you paid in along the way.

The **annual return** turns the total return into a yearly rate, compounded over the run's
calendar days. A 25% total return over two years is about 11.8% a year, not 12.5%, because each
year's gain builds on the one before.
