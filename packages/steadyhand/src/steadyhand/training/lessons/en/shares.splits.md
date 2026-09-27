+++
id = "shares.splits"
title = "Stock splits"
summary = "A split changes how many shares you hold and the price of each, without changing what the holding is worth."
explains = ["corporate.split.fraction_dropped"]
module = "shares-and-dividends"
position = 5
see_also = ["shares.cost_basis"]
+++

A company can **split** its shares. In a 5-for-1 split, every share you held becomes five, and
the price of each falls to about a fifth. You own the same part of the company as before.

A **reverse split** goes the other way: in a 1-for-5 reverse split, every five shares become one.

**When a fraction of a share is dropped.** A reverse split can leave a fraction: 1,203 shares in
a 1-for-5 reverse split make 240.6 shares. A share cannot be held in parts, so you keep 240 and
the 0.6 share is left over. In a real account that part may be paid out to you in cash,
called cash in lieu. steadyhand does not model that payment: it drops the fraction and says so
in a note, so a report shows slightly less than a real account would.
