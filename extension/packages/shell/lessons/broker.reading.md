+++
id = "broker.reading"
title = "Reading your broker"
summary = "Which of your broker's pages steadyhand reads, when a read counts, and what the panel asks for when one is missing."
explains = ["missing.page", "missing.history"]
module = "using-steadyhand"
position = 1
see_also = ["idx.sessions", "risk.returns"]
+++

steadyhand knows only what your broker's pages show it. With the side panel open beside your
broker's website, each page you open is read and recorded, and "Read this page" reads the one in
front of you again. Nothing is read or recorded while the panel is closed.

The pages it reads:

- **Portfolio**: your cash and your holdings, and, read after the close, each holding's close.
- **Watchlist**: the stocks you follow, and their closes.
- **Flags**: the exchange's notations on stocks, such as a suspension.
- **Dividends**, **cash movements** and **corporate actions**: the dividends a stock paid, your
  deposits and withdrawals, and share splits.
- **A stock's page**: its price chart.

**Fresh reads.** Advice needs the portfolio and the watchlist read for the same day, within
30 minutes of each other and outside a trading session. Otherwise the panel names the page to
read again.

**What is missing.** When the strategy needs something that has not been read, such as a stock's
dividends or its chart, or a chart that does not reach back far enough, the panel lists it under
Missing, and gives no orders until it is read.

**Pages you saved.** A broker page you saved can be pasted into the Advice tab, or opened from a
file. It is read in the panel, like any other, and goes nowhere else.
