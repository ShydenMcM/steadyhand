+++
id = "risk.limits"
title = "The safety limits steadyhand applies"
summary = "The limits that cut or stop a strategy's orders, whatever the strategy wants to do."
explains = []
module = "risk"
position = 3
see_also = ["risk.drawdown"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.1"]
+++

Every strategy's orders pass through the same limits before they are placed. Each can be set in
your configuration. These are the defaults:

- **Cash only.** No borrowing and no short selling. A buy that needs more settled cash than you
  have is cut down or dropped.
- **At most 10% in one stock.** A buy that would take one stock above 10% of the portfolio's
  value is cut back to 10%.
- **Daily loss limit.** If the portfolio falls 5% in one day, the strategy **halts**: it places
  no new orders until you resume it.
- **Drawdown limit.** If the portfolio falls 25% below its high-water mark, the strategy halts
  in the same way.

A halt is not a sale. The holdings stay where they are; the strategy simply stops adding orders
until you have looked at what happened and chosen to resume.

These limits reduce some risks. They do not remove them: a portfolio can still lose a great deal
of its value, and the limits act on the day's closing prices, after the fall has happened.
