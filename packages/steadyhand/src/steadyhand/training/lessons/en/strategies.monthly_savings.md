+++
id = "strategies.monthly_savings"
title = "monthly-savings, investing in instalments"
summary = "Why a strategy might invest its starting cash a little each month instead of all at once, and what waiting costs."
explains = []
module = "strategies"
position = 2
see_also = ["strategies.buy_and_hold", "risk.backtests_mislead"]
sources = ["packages/steadyhand/src/steadyhand/strategies/guides/monthly-savings.md", "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

`monthly-savings` splits its starting cash into equal monthly instalments (12 by default) and
invests one each month across every stock it can buy. It never sells.

Spreading the buying out means no single day's prices decide the whole portfolio. The cost is
that money waiting for its month earns nothing in the model, and in a market that mostly rises,
investing later tends to trail investing everything at once. Neither is a mistake; they are
different answers to how much a bad first day should matter to you. Its guide, which the explain
command prints, gives the whole rule and when a change to its instalments takes effect.
