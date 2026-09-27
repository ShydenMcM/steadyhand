+++
id = "costs.stamp_duty"
title = "Stamp duty"
summary = "A fixed Rp10,000 charge on a day's trade confirmation when that day's trades are worth more than Rp10,000,000."
explains = ["term.daily_cost"]
module = "costs-and-tax"
position = 3
see_also = ["costs.trading"]
sources = ["docs/research/t-fees.md §3"]
+++

Each day you trade, your broker sends a **trade confirmation**, a document listing that day's
trades. Indonesian law charges a stamp duty of Rp10,000 on it. Since 12 January 2022, a
confirmation worth Rp10,000,000 or less is exempt.

steadyhand books it as a **daily cost**: one charge per day, not per trade, and only on days
whose trades pass the threshold.

On small trades it is the largest cost there is. A Rp11,000,000 trade pays about 0.09% in stamp
duty alone, while a Rp100,000,000 trade pays 0.01%. A small portfolio that trades often can lose
a noticeable part of its value this way.
