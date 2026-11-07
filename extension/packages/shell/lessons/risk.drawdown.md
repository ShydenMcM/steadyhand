+++
id = "risk.drawdown"
title = "Drawdown: how far it fell"
summary = "A drawdown is how far the portfolio fell from its highest point before it recovered."
explains = ["risk.halt.drawdown"]
module = "risk"
position = 1
see_also = ["risk.returns", "risk.limits"]
+++

You can lose money. A drawdown puts a number on how much.

The **high-water mark** is the highest value the portfolio has reached so far, measured per unit
so that new deposits do not count as gains (the returns lesson explains units). A **drawdown**
is a fall from that high point, as a share of it. If the high point was 1.20 a unit and the
portfolio later fell to 0.90, the drawdown is 0.30 / 1.20 = 25%.

steadyhand follows the unit value from each portfolio page read after the close. If it falls 25%
below its high-water mark, buying stops until you resume it; the safety limits lesson explains
how.

Two things make a drawdown matter more than it looks:

- Getting back takes more than the fall. After a 25% fall, the portfolio needs to rise by a
  third (33%) just to return to where it was.
- The worst fall so far is not the worst that can happen. The future can hold a deeper fall
  than the past did.
