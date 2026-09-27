+++
id = "costs.trading"
title = "What a trade costs"
summary = "Every trade pays the broker's fee and the exchange's levy on top of its value, and a sale also pays tax."
explains = ["term.broker_fee", "term.levy", "term.trading_costs"]
module = "costs-and-tax"
position = 1
see_also = ["costs.sale_tax", "costs.stamp_duty", "backtest.report"]
sources = ["docs/research/t-fees.md §1", "docs/research/t-fees.md §4"]
+++

Buying or selling shares costs money on top of the trade's value. On IDX there are three parts:

- **The broker's fee**, also called commission: what your broker charges for placing the order.
  Each broker sets its own rate, as a percentage of the trade's value, and charges VAT on it.
- **The levy**: the exchange's charges, which the broker collects and passes on. Since
  1 April 2022 it is 0.0433% of the trade's value on each side, buying or selling. It is made up
  of the exchange's fee (0.018%), the clearing house's fee (0.009%), the settlement fee (0.003%),
  VAT on those three, and a guarantee fund contribution (0.010%).
- **The sale tax**: 0.1% of the value of every sale. Its own lesson explains it.

The **trading costs** of a trade are all three added up.

Retail brokers usually quote one all-in rate for each side. One broker's quote checked in 2026
was 0.1513% to buy and 0.2513% to sell, including the levy, the VAT and the sale tax. steadyhand
records what each broker preset's rate already includes, so nothing is charged twice. Check the
preset you use against your own broker's fee page.

Costs look small, but they are paid on every trade. A strategy that trades often can lose more to
costs than it gains.
