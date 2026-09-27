+++
id = "income.projection"
title = "Projection, not a promise"
summary = "How many years each scenario takes to reach your income target, under stated assumptions."
explains = ["term.contribution", "term.starting_income", "term.years_to_goal", "income.projection.costs_ignored"]
module = "income-goal"
position = 6
see_also = ["income.goal", "income.growth"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.3"]
+++

The projection asks how long it would take your portfolio to pay your income target, if you kept
reinvesting. It works month by month from today's holdings:

- each month's take-home dividends are reinvested, and your monthly **contribution** is added;
- the new money buys more of the same holdings, at today's yield;
- once a year, the dividends grow at the scenario's rate.

It runs three scenarios:

| Scenario | Starting income | Dividend growth |
|---|---|---|
| Pessimistic | the run-rate × 0.8 | the measured growth or 0%, whichever is lower |
| Base | the run-rate | the measured growth, at most 5% a year |
| Optimistic | the run-rate | the measured growth, at most 10% a year |

Each gives the **years to the goal**, rounded up to a tenth of a year, or says the target is not
reached within 50 years. Nothing is projected from an empty portfolio or a zero run-rate.

The assumptions are deliberately cautious: share prices never rise, and only take-home income is
reinvested. **The costs of buying are left out**, which errs the other way, and a note says so on
every projection. It is a way to compare plans, not a date to count on.
