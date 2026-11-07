+++
id = "strategies.total_return"
title = "Total return"
summary = "Why ma-trend and momentum-rotation judge a stock by its price with its dividends added back."
explains = []
module = "strategies"
position = 8
see_also = ["dividends.basics", "strategies.ma_trend", "strategies.momentum_rotation"]
+++

On a dividend's ex-date a stock's price usually falls by about the dividend, because a buyer from
that day on will not receive it. A price chart alone then shows a fall that the holder did not
lose: the money arrived as the dividend.

**Total return** puts the dividend back. Each cash dividend is treated as reinvested in the stock
on its ex-date, so every close before the ex-date is scaled by one minus the dividend divided by
the close on the day before. A chart that already includes the adjustment is not adjusted twice.

`ma-trend` and `momentum-rotation` judge every stock by its total return, so a high payer is not
mistaken for a falling one. That needs the stock's dividends for the whole window, read from its
dividend page, and a stock whose dividends have not been read is listed under Missing.
