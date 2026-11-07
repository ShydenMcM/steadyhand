+++
id = "strategies.dividend_growth"
title = "dividend-growth, a test of past dividends"
summary = "How dividend-growth chooses stocks by the dividends they paid, and why a good record is not a promise."
explains = []
module = "strategies"
position = 3
see_also = ["dividends.basics", "strategies.holding_cash", "broker.reading"]
+++

Once a year, `dividend-growth` keeps the stocks that paid a dividend in every one of the last six
years and paid at least as much last year as `growth_years` (5 by default) years before, with the
amounts restated for any split. It holds up to `max_stocks` (25 by default) of them in equal
parts, spread so that their dividends arrive in different months, and sells what no longer
passes.

A long record of paying and raising dividends says something about a company's past, and
nothing certain about its future: a dividend can be cut in any year, and a company whose
dividends swing with its business can still pass. The test also needs years of dividends: open
each stock's dividend page so the panel can read them. A stock whose dividends have not been
read is listed under Missing.
