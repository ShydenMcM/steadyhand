+++
id = "orders.not_tradable"
title = "Why a stock is not traded on a day"
summary = "The reasons a stock is left out of a day's buying or selling, whatever the strategy wants."
explains = ["trade.not_in_universe", "trade.not_held", "trade.excluded", "trade.frozen"]
module = "using-steadyhand"
position = 2
see_also = ["idx.special_monitoring", "idx.universe"]
+++

Each advice day, steadyhand first works out which stocks can be bought and which can be sold. A
strategy may still ask for others, but those orders are not given, and the panel says why:

- **Not in the universe.** Only stocks in the universe you listed in Settings can be bought.
- **Not held.** You can only sell what you own: there is no short selling.
- **Excluded.** You listed the stock among the exclusions in Settings, so it is neither bought
  nor sold.
- **Frozen.** Your broker's flags page shows the stock suspended or on the Special Monitoring
  Board. It is neither bought nor sold until the flag is gone.

A stock left out on one day can be traded again on a later day once the reason has gone.
