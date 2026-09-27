+++
id = "costs.sale_tax"
title = "The 0.1% sale tax"
summary = "Every sale of shares on IDX pays a final tax of 0.1% of its value, and buying pays none."
explains = ["term.sale_tax"]
module = "costs-and-tax"
position = 2
see_also = ["costs.trading"]
sources = ["docs/research/t-fees.md §2"]
+++

When you sell shares on IDX, 0.1% of the sale's value is taken as tax. Selling Rp10,000,000 of
shares pays Rp10,000 of tax. Buying pays no tax.

It is charged on the sale's **value**, not on any profit, so a sale at a loss pays it just the
same. The exchange collects it through your broker, who takes it from the
money the sale brings in, so you never pay it separately.

The rate has been 0.1% throughout the years steadyhand's data covers.
