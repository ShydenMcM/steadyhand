+++
id = "idx.special_monitoring"
title = "The Special Monitoring Board"
summary = "Stocks the exchange watches closely trade differently, and steadyhand leaves them out by default."
explains = []
module = "how-idx-works"
position = 6
see_also = ["idx.universe"]

+++

The exchange places some stocks it is watching closely on the **Special Monitoring Board**
(Papan Pemantauan Khusus). Stocks there trade in a call auction for the whole day: orders are
collected and matched at set times, not continuously.

steadyhand leaves these stocks out by default. It never buys one, and if you hold one, it
freezes the holding and flags it so that you decide what to do. It does not model the board's
auctions, and staying out keeps a strategy clear of the stocks the exchange itself is worried
about.

steadyhand learns which stocks are on the board from your broker's flags page, the page that
marks them, so read that page with the others to keep the list current. A stock you want kept out
for a reason of your own can be excluded on Settings, with its code and your reason.
