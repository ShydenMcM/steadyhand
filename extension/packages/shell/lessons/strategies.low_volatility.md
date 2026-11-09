+++
id = "strategies.low_volatility"
title = "low-volatility, the calmest stocks"
summary = "How low-volatility holds the stocks that moved most evenly over the last year, and what that gives up."
explains = []
module = "strategies"
position = 9
see_also = ["strategies.total_return", "strategies.holding_cash"]
+++

On the first advice day of each month, `low-volatility` measures how unevenly each stock moved: the
standard deviation of its daily total-return moves over about `volatility_months` (12 by default)
months. It holds the `volatility_stocks` (10 by default) with the lowest figure, in equal parts, and
sells the rest. Between reviews it keeps its holdings and puts new cash into its picks.

Calm is not the same as safe, and it says nothing about direction: a stock falling by the same small
amount every day scores as calm too. Calm stocks have often fallen less in a bad market, and often
risen less in a good one. Measured on the LQ45 from 2020 to 2025, with no costs counted, it dropped
less than holding every member equally, 21.5% against 33.5% at worst, and earned less, 7.1% a year
against 9.6%. One stretch of years does not say what the next will do.

A stock that hardly traded would look calm, so one with fewer than 15 closes for each month looked
back is not judged. It needs each stock's chart, read from the stock's own page, reaching back over
the whole look-back, and the stock's dividends for that time.
