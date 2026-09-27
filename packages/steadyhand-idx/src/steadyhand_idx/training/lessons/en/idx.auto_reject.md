+++
id = "idx.auto_reject"
title = "Auto-rejection: how far a price may move in a day"
summary = "The exchange refuses any order priced too far above or below the previous close."
explains = []
module = "how-idx-works"
position = 3
see_also = ["idx.ticks"]
sources = ["docs/research/t-rules.md §3"]
+++

To stop wild swings, the exchange refuses an order priced **more than** a set percentage above or
below a reference price, normally the previous day's close. A price exactly on the limit is
accepted. The limits are called **auto-rejection** bands.

The upper limit depends on the price:

| Previous close | Highest accepted rise |
|---|---|
| up to Rp200 | 35% |
| over Rp200 to Rp5,000 | 25% |
| over Rp5,000 | 20% |

The lower limit has changed several times. It has been 15% at every price since 8 April 2025,
and from 1 January 2027 it becomes the same as the upper limit in each price range. From
28 September 2026 the lowest price a share may trade at is Rp1 instead of Rp50, and a share
priced Rp1 to Rp10 may move by Rp1 either way instead of by a percentage.

So until the end of 2026 a stock can fall at most about 15% in a day, however bad the news.
If sellers want lower prices, the stock stops at the limit and the selling carries on the next
day. steadyhand also uses the bands to spot impossible price data.
