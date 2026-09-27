+++
id = "risk.backtests_mislead"
title = "Why backtests mislead"
summary = "A backtest shows what a strategy would have done in the past, which is not what it will do next."
explains = []
module = "risk"
position = 4
see_also = ["idx.survivorship", "backtest.basics", "backtest.data_gaps"]
+++

A backtest replays a strategy over past prices. It is a useful check and an easy one to
over-trust. Its results tend to look better than real life, for several reasons:

- **The past does not repeat.** A strategy that did well in one stretch of years can do badly in
  the next, when the market behaves differently.
- **Fitting to the past.** Try enough settings and one of them will look excellent on the
  history you tried them on, by chance. The more a strategy was tuned, the less its backtest
  says.
- **Survivorship bias.** A list of stocks chosen today leaves out the companies that failed or
  shrank. Testing on it makes the past look kinder than it was.
- **Missing or wrong data.** Prices can be missing on some days, or wrong, and a dividend on a
  missing day is never counted.
- **Perfect execution.** A backtest assumes you placed every order on time, at the modelled
  price. Real orders can fill at worse prices, or not at all.

steadyhand tries to be honest about these: it charges realistic costs, it warns when data or
the stock list has gaps, and it compares every strategy with plain buy-and-hold. Treat any
backtest as a rough guide to how a strategy behaves, never as a forecast.
