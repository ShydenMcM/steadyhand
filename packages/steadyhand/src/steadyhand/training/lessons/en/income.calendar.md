+++
id = "income.calendar"
title = "The payment calendar"
summary = "Which months of the year your current holdings' dividends would arrive in, and how evenly."
explains = ["term.payment_calendar", "term.evenness"]
module = "income-goal"
position = 3
see_also = ["income.run_rate", "dividends.basics"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.1"]
+++

The **payment calendar** spreads the run-rate across the twelve months of the year. Each
dividend a holding paid over the last year is placed in the month its payment would arrive,
after tax, using the same pay date steadyhand uses everywhere else. The calendar shows the
result per holding and in total, and how many months would have nothing.

If you plan to live on dividends, when they arrive matters as much as how much they are. Many
companies pay once a year, often in the same few months, which can leave long gaps.

**Evenness** is the largest month's share of the year's total:

- 1/12, about 8%, means every month pays the same;
- 1, or 100%, means the whole year's income arrives in a single month.

A lower number is a steadier income. It is left out when the run-rate is zero.
