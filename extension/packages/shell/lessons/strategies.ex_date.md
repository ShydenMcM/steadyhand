+++
id = "strategies.ex_date"
title = "What happens around an ex-date"
summary = "Why buying a stock just before its ex-date to collect the dividend is not free money."
explains = []
module = "strategies"
position = 10
see_also = ["dividends.basics", "tax.dividend"]
+++

A stock's ex-date is the first day a buyer no longer gets the coming dividend. The price usually
falls that morning, because the shares are now worth less by about the cash leaving the company.
Buying the day before and selling on the ex-date can look like collecting a dividend for nothing.
The dividend is real, but so are the fall, the fees and the tax.

This was measured on the LQ45 as it stood at the time, from July 2020 to December 2025: 258 trades,
each buying at the close before an ex-date and selling at the ex-date's close. On average a trade
made +0.25%, and the true average could plausibly be anywhere from -0.08% to +0.57%. Only 52% of
trades gained. The worst lost 8.3% in that one day, and the best made 12.0%.

That is close to a coin flip, with large swings either way and about 47 trades a year to place by
hand. One stretch of years does not say what the next will do. The figures assume fees of 0.15% a
buy and 0.25% a sell and 10% tax on the dividend, and they use dividend figures from
a public data source.
