+++
id = "tax.dividend"
title = "Tax on dividends"
summary = "Dividends from Indonesian companies carry a 10% final tax for resident individuals, which the investor pays."
explains = ["term.dividend_tax", "term.dividend_net", "term.take_home"]
module = "costs-and-tax"
position = 4
see_also = ["tax.exemption", "dividends.basics", "income.goal"]
sources = ["docs/research/t-tax.md §1", "docs/research/t-tax.md §2", "docs/superpowers/specs/2026-09-26-m4-income-design.md §2", "docs/research/t-tax.md §5"]
+++

For a resident individual, a dividend from an Indonesian company is taxed at **10%**, and the tax
is final.

Nothing is taken off before the money reaches you: the company pays the dividend in full, and
your account receives the gross amount. If the tax is due, you pay it yourself, by the 15th of
the following month. It is not due if you reinvest the dividend in Indonesia under the rules in
the next lesson.

steadyhand's figures:

- **Dividend tax** is the tax steadyhand books. By default it books the full 10% of every
  dividend on its pay date, as if you had paid it.
- **Net dividend** is the gross dividend less the tax booked.
- **Take-home** is the gross dividend less the full 10%, whatever was booked. The income goal
  uses it, because money you live on is money you are not reinvesting, so it cannot be exempt.

A dividend of Rp1,000,000 therefore shows a take-home of Rp900,000.
