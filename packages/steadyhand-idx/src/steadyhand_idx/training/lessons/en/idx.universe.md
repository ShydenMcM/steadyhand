+++
id = "idx.universe"
title = "The LQ45"
summary = "The LQ45 is the exchange's list of 45 large, easily traded stocks, and steadyhand's default choice of stocks."
explains = []
module = "how-idx-works"
position = 7
see_also = ["idx.survivorship"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.4"]
+++

The **LQ45** is a list the exchange keeps of 45 large stocks that trade a lot every day. Its
members change at regular reviews: every six months until January 2024, and every three months
from May 2024. A member can also be replaced between reviews.

steadyhand's strategies choose from the LQ45 by default. Large, busy stocks are easier to buy
and sell at a fair price, even in small amounts.

The exchange's terms do not allow its data to be passed on for commercial use without its
permission, so steadyhand does not ship the lists. You supply the file yourself, in your data folder, with each list and the date it
took effect. A backtest uses whichever list was in effect on each day it replays.
