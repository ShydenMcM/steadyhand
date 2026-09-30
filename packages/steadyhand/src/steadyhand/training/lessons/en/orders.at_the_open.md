+++
id = "orders.at_the_open"
title = "What can happen to an order at the next open"
summary = "An order fills at the next day's opening price, unless something on that day stops it or makes it smaller."
explains = ["fill.frozen", "fill.no_bar", "fill.no_trades", "fill.no_reference", "fill.outside_band", "fill.volume.too_small", "fill.volume.cut", "fill.cash.short", "fill.cash.cut", "fill.charges_unpaid"]
module = "using-steadyhand"
position = 7
see_also = ["orders.not_tradable", "risk.limits"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md §5"]
+++

An order made after the close fills the next trading day at the opening price, as you would
place it at the open in your broker's app. steadyhand checks the order again at that moment:

- **Frozen, no bar or no trades.** If the stock was frozen, had no price that day, or did not
  trade at all, the order does not fill.
- **No previous close.** The day's allowed price range is set from the last close. Without one,
  the order does not fill.
- **Outside the price band.** The exchange rejects an order priced outside the day's allowed
  range, so a price at the open beyond it does not fill either.
- **Too much of the day's volume.** An order may take only a small share of the shares traded
  that day. A larger order is cut down to that share, and one whose share is less than a lot
  does not fill.
- **Not enough cash.** A buy is paid from settled cash at the open. If there is less than
  planned, the buy is cut to what can be spent, or does not fill at all.
- **Charges not covered.** A sale is refused if the day's charges would be more than the cash
  and the sale's proceeds could pay.

Each order that does not fill, or fills smaller, is listed in the day's report with its reason.
