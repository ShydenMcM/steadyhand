+++
id = "orders.limit_prices"
title = "Limit prices"
summary = "Why each order's limit is the day's close, and when the broker may still refuse it."
explains = []
module = "using-steadyhand"
position = 3
see_also = ["idx.ticks", "idx.auto_reject"]
+++

Every order the panel gives is a limit order at the advice day's close. A close is always a
price the exchange accepts: it sits on a valid tick, and on an ordinary day it is the reference
the next day's auto-rejection band is set from, so it is inside that band.

A limit at the close may not fill. If the price stays above your buy limit, or below your sell
limit, nothing is bought or sold, and the next day's advice starts from what you then hold.

On some days the reference is not the previous close, such as the ex-date of a rights issue,
when the exchange sets a new one. steadyhand does not know about rights issues, so on such a day
your broker may refuse an order at the close. Nothing fills, and nothing else changes.
