+++
id = "backtest.data_gaps"
title = "Days with missing prices"
summary = "What steadyhand does when a stock has no price for a day, and why the report warns you about it."
explains = [
    "data.bar.missing",
    "data.bar.refused",
    "data.dividends.history_refused",
    "data.stock.unavailable",
]
module = "using-steadyhand"
position = 3
see_also = ["risk.backtests_mislead"]
sources = [
    "docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md",
    "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md",
]
+++

steadyhand needs each stock's prices for each trading day: the open, high, low and close,
together called a **bar**. Sometimes there is none.

- **A missing bar.** The data has no prices for a stock on a day. The stock may not have traded,
  or the data source may simply lack that day. steadyhand does not trade the stock that day, and
  if you hold it, values it at its last close. The report notes each such day.
- **Refused days.** In a backtest, the data source can refuse to give prices for some days
  altogether. steadyhand does not trade the stock on those days and values any holding at its
  last clean close. It lists the refused days in one warning per stock.
- **Refused dividend history.** A strategy that judges a stock by the dividends it paid reads
  the years before the run as well. If the data source refuses a stock's history for those
  years, the run goes on, and one warning names the stock and the years refused. The stock's
  dividend history counts as incomplete, so such a strategy treats it as not qualifying.
- **A stock the data source cannot serve at all.** Sometimes the source has nothing usable for a
  stock: it no longer knows a stock that was delisted, or its record of the stock's share splits
  cannot be read. steadyhand treats every day the stock was in the universe as refused, so the
  stock is never bought or sold, and the run goes on. One warning names the stock and what the
  source said.

Each of these changes the result. A stock that cannot be traded cannot be bought or sold when the
strategy wanted to, and a dividend whose ex-date falls on a refused day is unknown and is not
credited, so the backtest can show less income than the stock paid. If a report carries many of
these warnings, trust its figures less.
