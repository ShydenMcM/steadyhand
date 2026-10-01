+++
id = "strategies.dividend_growth"
title = "dividend-growth, a test of past dividends"
summary = "How dividend-growth chooses stocks by the dividends they paid, and why a good record is not a promise."
explains = []
module = "strategies"
position = 3
see_also = ["dividends.basics", "strategies.holding_cash", "backtest.data_gaps"]
sources = ["packages/steadyhand/src/steadyhand/strategies/guides/dividend-growth.md", "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

Once a year, `dividend-growth` keeps the stocks that paid a dividend in every one of the last
six years and paid at least as much last year as five years before, with the amounts restated
for any split. It holds them in equal parts, spread so that their dividends arrive in different
months, and sells what no longer passes.

A long record of paying and raising dividends says something about a company's past, and
nothing certain about its future: a dividend can be cut in any year, and a company whose
dividends swing with its business can still pass. The test also needs years of history, so a
stock whose history the data source could not give is left out. Its guide, which the explain
command prints, gives the whole rule, its settings and the ways it tends to do badly.
