+++
id = "idx.ticks"
title = "Tick sizes: the steps a price moves in"
summary = "A price on IDX moves in fixed steps, and the step is larger for dearer shares."
explains = []
module = "how-idx-works"
position = 2
see_also = ["idx.lots", "idx.auto_reject"]
sources = ["docs/research/t-rules.md §1", "docs/research/t-hist.md §6"]
+++

A share price cannot be any number. It moves in fixed steps called **ticks**, and the size of
the step depends on the price:

| Price | Tick |
|---|---|
| below Rp200 | Rp1 |
| Rp200 to below Rp500 | Rp2 |
| Rp500 to below Rp2,000 | Rp5 |
| Rp2,000 to below Rp5,000 | Rp10 |
| Rp5,000 and above | Rp25 |

So a stock at Rp4,990 can be offered at Rp4,990 or Rp5,000, but not at Rp4,995, and a stock at
Rp5,000 moves to Rp5,025 next, not Rp5,010. The step is set by the price of the order itself.

These steps have been the same since at least March 2020. steadyhand keeps them, with their
dates, in a data file rather than in its code, so a change to the rules is a change to the data.
