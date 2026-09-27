+++
id = "dividends.basics"
title = "Dividends"
summary = "A dividend is cash a company pays to the people who hold its shares on a given day."
explains = ["term.dividend_gross", "term.dividend_per_share"]
module = "shares-and-dividends"
position = 4
see_also = ["tax.dividend", "income.received"]
sources = ["docs/research/t-pay.md §4"]
+++

A company that makes a profit may pay part of it to its shareholders as a **dividend**. It is
announced as an amount per share: the **dividend per share**. If Stock A pays 50 a share and you
hold 400 shares, your dividend is 20,000.

Two dates matter:

- The **ex-date.** You must have bought the shares before this day. Buy on the ex-date or later
  and the dividend goes to the seller instead.
- The **pay date.** The day the cash arrives, usually some weeks after the ex-date. Price data
  gives the ex-date but not the pay date, so steadyhand models the pay date as a set number of
  trading days after the ex-date, measured from real payment schedules.

The **gross dividend** is the full amount before tax. The tax lesson explains what is taken
from it.

A dividend is paid out of the company's cash, so on the ex-date the share price usually drops by
about the dividend. A dividend is not free money on top of the price: it is part of your return,
paid to you in cash.
