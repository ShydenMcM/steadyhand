+++
id = "income.received"
title = "Income received, and yield"
summary = "The dividends your portfolio was actually paid over the last year, and what they are as a share of its value and cost."
explains = ["term.received_income", "term.trailing_income", "term.current_yield", "term.yield_on_cost"]
module = "income-goal"
position = 1
see_also = ["income.run_rate", "tax.dividend", "shares.cost_basis"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §4"]
+++

**Received income** is the dividend money that actually arrived, as opposed to what the
portfolio might pay later. steadyhand shows it by month, and over the **trailing twelve months**:
the year that ends on the report's day. The income goal compares your target with the monthly
average of that year's take-home income (its total divided by 12).

A backtest also reports its **trailing income**: the dividends, after the tax booked on them,
paid in the last year of the run. It is how steadyhand compares one strategy's income with
another's.

Two ratios put the year's dividends, before tax, next to the portfolio:

- **Current yield**: the year's dividends as a share of what the portfolio is worth today. A
  portfolio worth 10,000,000 that was paid 500,000 has a current yield of 5%.
- **Yield on cost**: the same dividends as a share of what the holdings cost you. If those
  holdings cost 8,000,000, the yield on cost is 6.25%. Holdings that have risen in price show a
  yield on cost above their current yield.

Either is left out when there is nothing to divide by, such as a portfolio with no holdings.
