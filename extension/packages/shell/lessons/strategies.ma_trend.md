+++
id = "strategies.ma_trend"
title = "ma-trend, following the trend"
summary = "How ma-trend holds the stocks whose prices are rising, by comparing two averages, and why trends turn."
explains = []
module = "strategies"
position = 6
see_also = ["strategies.total_return", "costs.trading"]
+++

Every advice day, `ma-trend` compares two averages of each stock's closes: the average of the
last `fast_days` (50 by default) and the average of the last `slow_days` (200 by default), both
counted as total return. A stock whose short average is above its long one is in an
**uptrend**.

It keeps a holding while its uptrend lasts, and sells all of it when the trend turns or the stock
leaves the universe. New cash goes to the stocks in an uptrend, each up to an equal share of the
universe.

Averages are slow by design. They move only after the price has, so the strategy buys after a
rise has started and sells after a fall has begun, and in a market that goes sideways it can buy
and sell again and again, paying costs each time. It needs each stock's chart, read from the
stock's own page, reaching back `slow_days` trading days.
