+++
id = "idx.survivorship"
title = "Survivorship bias"
summary = "Testing on today's stock list, or a list with gaps, makes the past look better than it was."
explains = ["universe.survivorship.gap"]
module = "risk"
position = 5
see_also = ["idx.universe", "risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.4"]
+++

The companies on a list today are the ones that did well enough to be there. The ones that
shrank, failed or were taken off are missing. Run a backtest on today's list and those losers
never appear, so the past looks kinder than it was. This is **survivorship bias**.

steadyhand avoids most of it by using the LQ45 list that was in effect on each day of a backtest,
not today's. That only works if your file holds every list.

**When the lists have a gap.** If two lists in your file are more than one review apart,
steadyhand does not know who joined and left in between. It keeps using the earlier list until
the later one takes effect, and the backtest warns you, naming the gap. A stock that joined and
left inside the gap never appears, so the result may look better than a real investor's would
have. Filling the gap in your file removes the warning.
