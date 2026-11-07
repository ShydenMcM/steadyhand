+++
id = "idx.sessions"
title = "Trading hours"
summary = "When the Indonesia Stock Exchange is open, and which of the day's prices steadyhand uses."
explains = ["missing.rules_year"]
module = "how-idx-works"
position = 4
see_also = ["orders.limit_prices", "broker.reading"]
+++

The regular market's hours, in Western Indonesia Time:

|                                                         | Monday to Thursday | Friday            |
| ------------------------------------------------------- | ------------------ | ----------------- |
| Pre-opening: orders gathered, then matched at one price | 08:45 to 08:59:59  | same              |
| Session I                                               | 09:00 to 12:00     | 09:00 to 11:30    |
| Session II                                              | 13:30 to 15:49:59  | 14:00 to 15:49:59 |
| Pre-closing: orders gathered for the closing price      | 15:50 to 15:59:59  | same              |
| Post-closing: trading at the closing price              | 16:02 to 16:15     | same              |

The **opening price** comes from the pre-opening auction, and the **closing price** from the
pre-closing one. In each, orders are collected for a few minutes and then matched at a single
price.

steadyhand works with each day's closing price, not with the minutes in between. A portfolio or
watchlist page read from 16:02 on a trading day until the next trading day's pre-opening
records that day's close. A page read during a session records no close, and the panel asks
for it again after the close.

The exchange is closed at weekends and on its published holidays. Each release of steadyhand
carries the holidays year by year; for a year it has none for, advice waits for a release that
does.
