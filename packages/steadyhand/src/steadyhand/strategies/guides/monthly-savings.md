# monthly-savings

> steadyhand is example software that you run yourself, on your own account, and you make your
> own decisions with it. It is not financial advice. You can lose money.

## What it does

It spreads your starting cash over a number of monthly instalments, 12 by default, instead of
investing it all on the first day. On the first day it runs, it divides the cash it can spend by
the number of instalments, and that amount is the instalment. On the first day it runs in each
calendar month, it invests one instalment, split equally across every stock in the universe (by
default the LQ45, IDX's list of 45 large, easily traded stocks) that can be bought that day, and
keeps the rest of the starting cash back for the instalments still to come.

Cash that arrives in between, from a dividend (a share of a company's profit paid to its
shareholders) or from a monthly top-up, goes in with the next instalment. After the last
instalment it invests all its cash each month. It never sells: a stock that joins the LQ45 is
bought from the next instalment on, and a stock that leaves it stays in the portfolio. If no
stock can be bought on its first day in a month, that month's instalment waits for the next day
one can.

## Why people use it

Investing a large sum all at once means buying at whatever the prices are on that one day.
Spreading it over months, often called dollar-cost averaging, buys at many different prices
instead, so a fall soon after you start costs less. Many people also find it an easier way to
begin. Run it beside `buy-and-hold` with `steadyhand-idx compare` to see what spreading the
purchases out cost or saved over the same days.

## When it tends to do badly

When prices rise through the months it is still investing, it buys later and higher than a lump
sum would have, so in a rising market it is expected to trail `buy-and-hold`. The cash waiting
for its instalment earns nothing in steadyhand's model, although a real account might pay some
interest on it. Once every instalment is invested it behaves much like `buy-and-hold`, and falls
with the market as that does.

## Risks

- **You can lose money.** Share prices can fall a long way and stay down for years, and
  spreading the purchases out does not stop that.
- **Fee drag:** every monthly purchase pays a broker commission, the exchange levy and, on some
  days, stamp duty. Small instalments split across many stocks pay these costs many times over.
- Every stock is bought in whole lots of 100 shares, so a small instalment split across many
  stocks may leave cash unspent, which waits for the next month.
- A stock can be suspended, or its prices can be missing. steadyhand then does not trade it and
  values it at its last known price, which may turn out to be wrong.

## How often it trades

Once a month: it buys on its first day in each calendar month, and it never sells.

## Settings you can change

- `instalments`: how many monthly instalments the starting cash is spread over, from 1 to 120.
  The default is 12. With 1 it invests everything on its first day, then reinvests each month.
  It is fixed when the strategy starts, from the cash it holds then: changing it later does not
  change a run or a paper account already under way.
- `monthly_contribution`: cash added on the first trading day of each month, which goes in with
  that month's instalment. The default is 0.
- The risk limits: the most any one stock may be of the portfolio (10% by default), which caps
  each purchase, and the daily loss and drawdown limits that stop all trading when they are
  reached.
