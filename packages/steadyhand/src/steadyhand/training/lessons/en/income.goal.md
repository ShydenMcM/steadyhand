+++
id = "income.goal"
title = "Your income goal"
summary = "The monthly take-home income you are aiming for, and how much of it your portfolio covers today."
explains = ["term.income_target", "term.goal_share"]
module = "income-goal"
position = 5
see_also = ["income.received", "income.run_rate", "income.projection"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.4"]
+++

The **income target** is the monthly income you would like your portfolio to pay you: an amount
you choose, such as what you need to live on. steadyhand measures it on **take-home** income,
after the full dividend tax, because money you live on is money you are not reinvesting.

The goal tracker shows two ways of measuring progress, each as a share of the target:

- **Received**: the monthly average take-home of the dividends actually paid over the last year.
- **Run-rate**: the monthly take-home your current holdings would pay over a year.

With a target of 5,000,000 a month, a run-rate take-home of 1,250,000 covers 25% of it. A share
above 100% means the target is covered.

The two often differ. The run-rate moves as soon as you buy or sell; received income catches up
over the following year.
