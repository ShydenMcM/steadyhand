+++
id = "shares.prices"
title = "Prices, and what your portfolio is worth"
summary = "How a trade's price, a stock's last close and your holdings add up to the value of your portfolio."
explains = ["term.trade_price", "term.trade_value", "term.last_close", "term.holdings_value", "term.portfolio_value"]
module = "shares-and-dividends"
position = 2
see_also = ["shares.cost_basis", "costs.trading"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

A stock has many prices during a day. These lessons use a few of them.

- **Trade price.** The price one of your orders was filled at: what you actually paid, or
  received, for each share.
- **Trade value.** The number of shares traded times the trade price, before any costs. Buying
  100 shares of Stock A at 1,000 is a trade value of 100,000.
- **Last close.** The price a stock closed at on the most recent day it traded. steadyhand
  values what you hold at each stock's last close.

From those, steadyhand works out what your portfolio is worth each day:

- **Holdings value.** Every stock you hold, times its last close, added up.
- **Portfolio value.** Your cash plus your holdings value. The cash includes money from a sale
  that has not arrived in your account yet.

A portfolio's value is not money in your hand. It is what the shares would fetch at today's
closing prices, before the costs of selling them, and tomorrow's prices can be lower.
