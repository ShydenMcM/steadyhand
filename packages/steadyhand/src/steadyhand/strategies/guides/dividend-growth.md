# dividend-growth

> steadyhand is example software that you run yourself, on your own account, and you make your
> own decisions with it. It is not financial advice. You can lose money.

## What it does

It holds stocks from the universe (by default the LQ45, IDX's list of 45 large, easily traded
stocks) that have paid a dividend (a share of a company's profit paid to its shareholders) every
year, and paid at least as much last year as five years before.

Once a year, on the first day it runs in each calendar year and on its very first day, it
reviews its stocks. A stock passes when it paid a cash dividend in each of the last six calendar
years, each counted in the year of its ex-date (the first day the shares trade without that
dividend), and when its dividends last year added up to at least what they added up to five
years earlier. Amounts are compared per share, restated for any split in between, so a split
does not look like a cut.

It holds every stock that passes, up to 25 of them, in equal parts of the portfolio: one part
for each stock it holds, but never more than a fifteenth each. With more than 25 passing, it
picks them one at a time so that the months their dividends arrive in are spread across the
year: each time it takes the stock whose quietest pay month has the fewest stocks already picked,
then the one paying the most over the last year for its price. It sells what no longer passes.
Fewer than 15 passing means the rest of the portfolio waits as cash, and the report says how
many passed.

Between reviews it keeps what it holds and puts new cash, from dividends and monthly top-ups,
into the stocks it picked, never taking one above its share.

## Why people use it

A company that has paid a dividend every year, and pays more than it used to, has usually been
earning steadily. Owning several of them, paying in different months, gives an income that
arrives through the year and has tended to grow, which is what the income goal measures.

## When it tends to do badly

The test compares the totals of only two years, the last one and the one five years before it,
and asks of the years between only that each paid something. So it lets in companies whose
dividends swing with their profits, such as coal and metal miners, as long as last year was a
good one; those dividends can fall sharply the next year. A year in which many companies cut
their dividends can leave most of the portfolio in cash until the next review finds enough
stocks passing again, and cash earns nothing in steadyhand's model. Choosing by past dividends also misses companies that are only starting to
pay.

## Risks

- **You can lose money.** Share prices can fall a long way and stay down for years, whatever a
  company has paid before, and a dividend can be cut or stopped.
- **Fee drag:** every purchase and sale pays a broker commission, the exchange levy and, on some
  days, stamp duty, and a sale also pays tax. The yearly review sells stocks that no longer pass,
  so each review costs more than a year of buy-and-hold does.
- **The pay months are modelled.** The data source gives each dividend's ex-date, not the day
  it was paid, so steadyhand assumes each dividend is paid a set number of trading days after
  its ex-date (the pay lag, 14 by default). Real payments can come earlier or later.
- **Old data may not compare.** When a company changes its shares in a way the data source does
  not report as a split, such as a rights issue, its earlier dividends may be scaled, so a year
  before the change may not compare fairly with a year after it. A stock whose history the data
  source refuses does not pass, and the backtest warns about it.
- Every stock is bought in whole lots of 100 shares, so some cash can stay uninvested.

## How often it trades

Once a year it sells what no longer passes and evens out what it holds. In between it only buys,
when a dividend or a top-up arrives.

## Settings you can change

- `min_stocks`: below this many passing stocks, it holds the rest of the portfolio as cash
  instead of putting more into fewer stocks. From 1 to 45; the default is 15.
- `max_stocks`: the most stocks it holds. From 1 to 45, and at least `min_stocks`; the default is
  25.
- `growth_years`: how many years back the dividend test compares last year with. From 1 to 10;
  the default is 5, which asks for a dividend in each of the last six years. A longer test needs a
  longer history, which the data source must have.
- `monthly_contribution`: cash added on the first trading day of each month, which goes into the
  stocks it picked. The default is 0.
- The risk limits: the most any one stock may be of the portfolio (10% by default), which caps
  each purchase, and the daily loss and drawdown limits that stop all trading when they are
  reached.
