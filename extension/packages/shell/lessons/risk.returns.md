+++
id = "risk.returns"
title = "Returns, counted fairly"
summary = "How steadyhand measures gain or loss so that money you pay in is never counted as profit."
explains = ["missing.deposits", "missing.reread"]
module = "risk"
position = 2
see_also = ["risk.drawdown", "risk.limits"]
+++

If you pay 1,000,000 into a portfolio and it is later worth 1,100,000, it looks like a 10% gain.
But if you paid in another 100,000 along the way, the portfolio gained nothing: the extra value
is your own money.

steadyhand avoids that mistake by counting the portfolio like a fund.

- A **deposit** is money you pay in, and a **withdrawal** is money you take out.
- Each deposit buys **units** at the current **unit value**, and each withdrawal sells them, so
  neither moves the unit value.
- After that the unit value moves only with the investments: price changes, dividends and
  costs.

The unit value is taken only from portfolio pages read after the close, and the first such read
starts it at 1.

So steadyhand needs every deposit and withdrawal. It reads them from your broker's cash movement
page, or you type each one in Settings. Until the record covers the time since the last read,
buying stops, and the panel asks you to open the cash movement page, type each one in, or answer
that there were none.
