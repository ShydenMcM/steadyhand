+++
id = "idx.special_monitoring"
title = "The Special Monitoring Board"
summary = "Stocks the exchange watches closely trade differently, and steadyhand leaves them out by default."
explains = []
module = "how-idx-works"
position = 6
see_also = ["idx.universe"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §3", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.4", "docs/research/t-rules.md §3"]
+++

The exchange places some stocks it is watching closely on the **Special Monitoring Board**
(Papan Pemantauan Khusus). Stocks there trade in a call auction for the whole day: orders are
collected and matched at set times, not continuously.

steadyhand leaves these stocks out by default. It never buys one, and if you hold one, it
freezes the holding and flags it so that you decide what to do. It does not model the board's
auctions, and staying out keeps a strategy clear of the stocks the exchange itself is worried
about.

The data steadyhand uses cannot tell it which stocks are on the board, so you keep that list
yourself, in the exclusions file in your data folder, with the dates you added each one.
