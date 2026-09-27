# buy-and-hold

> steadyhand is example software that you run yourself, on your own account, and you make your
> own decisions with it. It is not financial advice. You can lose money.

## What it does

On the first day it runs, it takes every stock in the universe that can be bought that day (by
default the LQ45, IDX's list of 45 large, easily traded stocks) and buys them in equal amounts
of money. After that it never sells. Whenever new cash arrives, from a dividend (a share of a
company's profit paid to its shareholders) or from a monthly top-up, it spreads that cash
equally across the same stocks again.

It keeps the stocks it chose on the first day. A stock that later leaves the LQ45 stays in the
portfolio, and a stock that joins later is never bought.

## Why people use it

It is the simplest way to own a slice of a whole market, and it costs very little in fees
because it hardly ever trades. steadyhand runs it next to every other strategy as the
**baseline**: if a cleverer strategy cannot beat plain buying and holding after its costs, the
cleverness is not worth paying for.

## When it tends to do badly

When the market as a whole falls, this strategy falls with it, because it never moves to cash.
It also keeps holding a company whose business is getting worse, since it never sells, and
because it only reinvests new cash equally it never trims a stock that has grown to a large part
of the portfolio.

## Risks

- **You can lose money.** Share prices can fall a long way and stay down for years.
- **Fee drag:** every purchase pays a broker commission, the exchange levy and, on some days,
  stamp duty. Buying small amounts often, for example reinvesting small dividends, pays these
  costs many times over.
- Every stock is bought in whole lots of 100 shares, so some cash can stay uninvested when a lot
  of a stock costs more than an equal share of the cash.
- A stock can be suspended, or its prices can be missing. steadyhand then does not trade it and
  values it at its last known price, which may turn out to be wrong.

## How often it trades

Very rarely. It buys on its first day, then only when a dividend or a top-up arrives, and it
never sells.

## Settings you can change

This strategy has no settings of its own. These engine settings change what it does:

- `monthly_contribution`: cash added on the first trading day of each month and spread across
  the stocks. The default is 0.
- The risk limits: the most any one stock may be of the portfolio (10% by default), which caps
  each purchase, and the daily loss and drawdown limits that stop all trading when they are
  reached.
