+++
id = "orders.not_tradable"
title = "Why a stock is not traded on a day"
summary = "The reasons a stock is left out of a day's buying or selling, whatever the strategy wants."
explains = ["trade.not_in_universe", "trade.not_held", "trade.excluded", "trade.frozen", "trade.no_bar", "trade.refused"]
module = "using-steadyhand"
position = 6
see_also = ["orders.at_the_open"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md §6.4", "docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md §7.3"]
+++

Each trading day, steadyhand first works out which stocks can be bought and which can be sold.
A strategy may still ask for others, but those orders are skipped, and the report says why:

- **Not in the universe.** Only stocks in the day's universe, the index list your
  configuration names, can be bought.
- **Not held.** You can only sell what you own: there is no short selling.
- **Excluded.** You listed the stock in your exclusions file, so it is never bought, and a
  holding in it is frozen.
- **Frozen.** A stock you hold is frozen when it is excluded or when a corporate action cannot
  be modelled. It is neither bought nor sold until you deal with it yourself.
- **No bar.** The data source has no price for the stock that day, often because it was
  suspended. With no price there is nothing safe to trade on.
- **Refused.** The data source refused to give that day's prices, so the stock is left alone
  until its data is clean again.

A stock left out on one day can be traded again on a later day once the reason has gone.
