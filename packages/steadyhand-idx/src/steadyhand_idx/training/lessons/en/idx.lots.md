+++
id = "idx.lots"
title = "Lots: shares come in hundreds"
summary = "On the Indonesia Stock Exchange you buy and sell shares in lots of 100."
explains = []
module = "how-idx-works"
position = 1
see_also = ["idx.ticks"]
sources = ["docs/research/t-rules.md §1"]
+++

On the Indonesia Stock Exchange (IDX), shares trade in **lots**. One lot is 100 shares, and an
order on the regular market must be for whole lots: 100, 200 or 1,000 shares, never 150.

So the smallest purchase of a stock is one lot. At a price of Rp4,000 a share, one lot costs
Rp400,000 before costs.

This matters most when a portfolio is small. If a strategy wants Rp300,000 of that stock, it
cannot buy it: the nearest amounts are nothing or Rp400,000. steadyhand always rounds a planned
purchase **down** to whole lots, and drops any order smaller than one lot, so some cash can be
left unspent.
