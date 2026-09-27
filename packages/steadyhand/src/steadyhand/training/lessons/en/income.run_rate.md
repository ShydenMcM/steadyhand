+++
id = "income.run_rate"
title = "Run-rate"
summary = "What the dividends you hold now would pay over a year if nothing changed."
explains = ["term.run_rate", "term.monthly_take_home"]
module = "income-goal"
position = 2
see_also = ["income.received", "tax.dividend"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5"]
+++

The run-rate takes each holding you have today, and each dividend that stock paid a share over
the last year, and multiplies the two. Added up, that is the yearly income your current
holdings would bring if every company paid the same again and you changed nothing.

It answers a different question from received income. Received income is what arrived over the
last year, from whatever you held at the time. The run-rate is what today's holdings point to.
If you bought a stock last month, its year of dividends counts in full in the run-rate, though
you received none of them.

steadyhand shows it two ways:

- the **annual run-rate**, before tax; and
- the **monthly take-home**: the annual figure less the full dividend tax, divided by 12. This
  is the figure the income goal compares with your target.

The run-rate is an estimate, not a forecast. Companies raise, cut and skip dividends, and a
share price says nothing about next year's payment.
