+++
id = "risk.drawdown"
title = "Drawdown: how far it fell"
summary = "A drawdown is how far the portfolio fell from its highest point before it recovered."
explains = ["term.drawdown", "term.high_water"]
module = "risk"
position = 1
see_also = ["risk.returns", "risk.limits"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.1"]
+++

You can lose money. A drawdown puts a number on how much.

The **high-water mark** is the highest value the portfolio has reached so far, measured per unit
so that new deposits do not count as gains (the returns lesson explains units). A **drawdown**
is a fall from that high point, as a share of it. If the high point was 1.20 a unit and the
portfolio later fell to 0.90, the drawdown is 0.30 / 1.20 = 25%.

A backtest reports its **deepest** drawdown, with the day of the peak and the day of the low.
It is the worst stretch you would have lived through if you had run the strategy then.

Two things make a drawdown matter more than it looks:

- Getting back takes more than the fall. After a 25% fall, the portfolio needs to rise by a
  third (33%) just to return to where it was.
- The worst drawdown in a backtest is not the worst that can happen. The future can hold a
  deeper fall than the past did.
