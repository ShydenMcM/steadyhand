+++
id = "strategies.high_yield"
title = "high-yield, the biggest dividends now"
summary = "How high-yield chooses the stocks whose recent dividends are largest against their price, and why a high yield can be a warning."
explains = []
module = "strategies"
position = 5
see_also = ["dividends.basics", "strategies.holding_cash"]
+++

Every quarter, `high-yield` looks at the stocks that paid a cash dividend in each of the
`paid_years` (3 by default) calendar years before this one. For each, the **yield** is the
dividends per share with an ex-date in the last 365 days, restated for any split, divided by the
day's close. It holds the `yield_stocks` (10 by default) with the highest yields in equal parts,
and sells the rest. Between reviews it keeps its holdings and puts new cash into its picks.

A high yield is not always good news. When a company's price falls because the market expects
its dividend to be cut, its yield on last year's dividends rises. The yield looks back, and the
next dividend can be smaller. Open each stock's dividend page so the panel can read them.
