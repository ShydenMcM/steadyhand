+++
id = "idx.settlement"
title = "Settlement: when money and shares change hands"
summary = "A trade on IDX settles two trading days after it is made, so a sale's cash cannot be spent until then."
explains = ["term.settled_cash", "term.unsettled_cash"]
module = "how-idx-works"
position = 5
see_also = ["idx.lots"]
sources = ["docs/research/t-rules.md §7", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.2"]
+++

When your order fills, the trade is agreed at once, but the money and the shares move later. On
IDX that happens on the second trading day after the trade, called **T+2**. A sale on Monday
settles on Wednesday, and a sale on Friday settles on Tuesday, if no holiday falls between.

So steadyhand tracks cash in two parts:

- **Settled cash** has arrived and can be spent.
- **Unsettled cash** is money from a sale that has not arrived yet.

Only settled cash is spent on new purchases. If a strategy sells one stock to buy another, the
purchase may have to wait until the sale's cash settles.

The portfolio's value counts both, because the unsettled money is yours: it is only on its way.
