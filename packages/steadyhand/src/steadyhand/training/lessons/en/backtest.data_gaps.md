+++
id = "backtest.data_gaps"
title = "Days with missing prices"
summary = "What steadyhand does when a stock has no price for a day, and why the report warns you about it."
explains = ["data.bar.missing", "data.bar.refused"]
module = "using-steadyhand"
position = 3
see_also = ["risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

steadyhand needs each stock's prices for each trading day: the open, high, low and close,
together called a **bar**. Sometimes there is none.

- **A missing bar.** The data has no prices for a stock on a day. The stock may not have traded,
  or the data source may simply lack that day. steadyhand does not trade the stock that day, and
  if you hold it, values it at its last close. The report notes each such day.
- **Refused days.** In a backtest, the data source can refuse to give prices for some days
  altogether. steadyhand does not trade the stock on those days and values any holding at its
  last clean close. It lists the refused days in one warning per stock.

Both change the result. A stock that cannot be traded cannot be bought or sold when the
strategy wanted to, and a dividend whose ex-date falls on a refused day is unknown and is not
credited, so the backtest can show less income than the stock paid. If a report carries many of
these warnings, trust its figures less.
