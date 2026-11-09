+++
id = "strategies.holding_cash"
title = "When a strategy holds cash"
summary = "Why a strategy keeps part of the portfolio in cash when too few stocks pass its test, and what that costs."
explains = ["strategy.too_few_qualified"]
module = "strategies"
position = 4
see_also = ["dividends.basics", "strategies.dividend_growth"]
+++

`dividend-growth` holds only stocks that passed its dividend test at its last yearly review, and
it gives each an equal share of the portfolio, never more than one part in `min_stocks` (15 by
default). When fewer stocks pass than that, it does not spread the money over the few it has:
the shares they would have taken stay in cash, and the panel's warnings say how many stocks
passed. `high-yield`, `momentum-rotation` and `low-volatility` do the same when fewer stocks qualify than
they hold.

This keeps the portfolio from resting on a handful of companies, which is a risk of its own. The
cost is that cash earns nothing in steadyhand's sums, so a year with many dividend cuts can leave
the portfolio holding a lot of it until the next review finds enough stocks passing again.
Lowering `min_stocks` in Settings puts more of the money to work in fewer stocks. Which way is
better is a choice about risk.
