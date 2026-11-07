+++
id = "shares.prices"
title = "Prices, and what your portfolio is worth"
summary = "How a stock's close and your holdings add up to the value of your portfolio."
explains = []
module = "shares-and-dividends"
position = 2
see_also = ["shares.cost_basis", "costs.trading"]
+++

A stock has many prices during a day. These lessons use a few of them.

- **Close.** The price a stock closed at on the most recent trading day. The panel records each
  stock's close from a portfolio or watchlist page read after the close, and values what you
  hold at it.
- **Trade value.** The number of shares traded times their price, before any costs. Buying
  2 lots, 200 shares, of Stock A at 1,000 is a trade value of 200,000.

From those, steadyhand works out what your portfolio is worth each day:

- **Holdings value.** Every stock you hold, times its close, added up.
- **Portfolio value.** Your cash plus your holdings value. The cash includes money from a sale
  that has not arrived in your account yet.

Your broker may show a larger figure as cash available to buy. steadyhand spends no more than
the cash itself, so the orders it gives never add up to more than the portfolio holds.

A portfolio's value is not money in your hand. It is what the shares would fetch at the day's
closing prices, before the costs of selling them, and tomorrow's prices can be lower.
