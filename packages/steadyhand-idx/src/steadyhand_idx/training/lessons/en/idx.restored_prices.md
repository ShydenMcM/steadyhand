+++
id = "idx.restored_prices"
title = "Restored prices: an adjustment Yahoo does not report"
summary = "Why some of Yahoo's old prices are not whole rupiah, and how steadyhand puts them back."
explains = ["data.prices.restored"]
module = "how-idx-works"
position = 8
see_also = ["backtest.data_gaps", "idx.ticks"]
sources = [
    "docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md §4",
    "docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md §7",
]
+++

steadyhand reads its prices from Yahoo. Yahoo **adjusts** old prices after some events, such as
a rights issue, so that a chart does not show a jump on the day of the event. It does this by
multiplying every earlier price by one number, the **factor**. For splits, Yahoo says which
splits it applied, and steadyhand undoes them. For some other events it applies a factor and
does not say so.

**How steadyhand notices.** Every real price on IDX sat on a tick: a whole number of rupiah, in
steps that depend on the price. After the reported splits are undone, a price that is not whole
rupiah cannot be what was traded. So it still carries an adjustment Yahoo did not report.

**How the tick grid proves the factor.** steadyhand tries every factor from 1 to just below 2
that puts the newest such price on a whole rupiah. It keeps only the factors that put *every*
price of the span back on that day's tick grid, within one hundredth of a rupiah. When exactly
one factor fits, and at least 20 prices (five days) agree on it, that factor is the one Yahoo
applied. steadyhand then restores each price to its tick, and each dividend in the span by the
same factor. When no factor fits, or more than one does, those days stay refused, as before.

**A rounding error.** Sometimes the factor is 1: nothing was adjusted, but undoing a reported
split left each price a tiny fraction away from a whole rupiah. steadyhand puts those prices on
the grid too, and its note says it was a rounding error.

**What you will see.** A backtest that uses restored prices warns you, naming the stock, the
span, the factor and how many prices proved it. For example, Stock A's prices over two years
might all be multiplied by 1.1. A restored figure can differ from the one Yahoo shows for that
day, because Yahoo's figure still carries the adjustment and steadyhand's does not.
