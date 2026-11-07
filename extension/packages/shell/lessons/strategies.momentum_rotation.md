+++
id = "strategies.momentum_rotation"
title = "momentum-rotation, last year's leaders"
summary = "How momentum-rotation holds the stocks that rose most over the last year, and why leaders can stop leading."
explains = []
module = "strategies"
position = 7
see_also = ["strategies.total_return", "strategies.holding_cash"]
+++

On the first advice day of each month, `momentum-rotation` measures each stock's rise: its total
return from about `momentum_months` (12 by default) months ago to about `skip_months` (1 by
default) months ago. The latest month is left out because a stock's very latest moves often
reverse. It holds the `momentum_stocks` (10 by default) that rose most, in equal parts, and sells
the rest. Between reviews it keeps its holdings and puts new cash into its picks.

Stocks that rose most over a year have often kept rising for a while. Often is not always: when
the market turns, last year's leaders can fall fastest, and a monthly review sells them only
after the fall. It needs each stock's chart, read from the stock's own page, reaching back over
the whole window, and the stock's dividends for that time.
