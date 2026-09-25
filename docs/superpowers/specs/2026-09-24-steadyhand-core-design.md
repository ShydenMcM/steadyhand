# steadyhand — Sub-project A: Core Engine, IDX Rules, Backtester and Paper Trading

- **Status:** Approved by the operator on 2026-09-24
- **Date:** 2026-09-24
- **Owner:** Shyden (personal project, github.com/ShydenMcM/steadyhand)
- **Licence:** Apache-2.0
- **Language:** English only. The app is written for English speakers; Indonesia matters only because the operator lives there and the software must be legal to use there.

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

---

## 1. Purpose

### 1.1 The operator's goal

Build towards **living off dividend income**, so that work becomes optional. Start with a small amount of capital, reinvest every dividend and profit, and keep adding top-ups until the portfolio's dividend income reaches a "liveable wage" that the operator sets.

### 1.2 What the project is

A public, open-source, **self-hosted** toolkit made of two Python packages in one repository:

| Package | Role |
|---|---|
| `steadyhand` | A market-neutral engine library: core types, the strategy interface, a simulated broker, risk controls, position sizing, a backtester, metrics, income tracking and a strategy library. Other people can build their own bots on it, which saves them writing an engine. |
| `steadyhand-idx` | The first distribution built on the engine. It covers Indonesia Stock Exchange (IDX) rules, a Yahoo Finance `.JK` data source, the LQ45 universe, saved paper-trading state, configuration and a CLI. |

Future market distributions (`steadyhand-asx`, `steadyhand-us`, …) follow the same `-<market>` pattern.

### 1.3 What the project is not (hard boundaries)

- **Not a hosted service.** Nobody but the person running it ever touches their money, keys or data. A hosted service would move the project into OJK-licensed investment-advisory activity (§3.3).
- **Not a signal seller**, leaderboard or strategy marketplace. Any of these would need its own legal review before it could be designed.
- **Not "robot trading".** That phrase is associated in Indonesia with Bappebti-regulated futures/forex Ponzi schemes (§3.1). It is never used in names, docs or marketing.
- **No unofficial broker access.** The project never reverse-engineers or UI-automates a broker's app. The operator decided this on 2026-09-24 (§3.4).

## 2. The roadmap, and where this spec sits

| Sub-project | Scope | Spec |
|---|---|---|
| **A (this spec)** | Engine, IDX rules, Yahoo data, backtester, paper trading, strategy library, income goal tracker, CLI | this document |
| B+C | Scheduler plus a self-hosted web dashboard: positions, P&L, income goal, strategy switcher, and the **Confirm Fill** flow for manual real orders, with phone push via a **self-hosted ntfy** server. Playwright end-to-end tests are mandatory. No Telegram or other third-party chat service (operator decision 2026-09-24). | separate |
| D | Always-on intraday mode. It is blocked until a realtime IDX data source exists, because free Yahoo data is delayed. | separate |
| E | Interactive Brokers adapter for global markets, with a tax review for foreign-regulated accounts first | separate |
| later | An optional HTTP service wrapper around the engine library | separate |

Real IDX orders will **always be placed by the operator by hand** in their broker app. The bot proposes the order and the operator confirms what was actually filled. Automatic IDX orders are only considered if an OJK-licensed broker publishes an official API.

## 3. Legal and regulatory findings (Indonesia)

This is based on web research carried out on 2026-09-24. Sources and unverified items are listed in Appendix A. **This is engineering research, not legal advice.**

1. **Automated trading on your own account is not prohibited.** No IDX or OJK regulation names retail algorithmic trading for equities. Placing your own orders, through your own licensed broker's sanctioned channel, into your own KSEI-registered account (SID + RDN) is ordinary retail trading. Bappebti Regulation 12/2022 on "robot trading" covers third parties *selling* robot-trading services in commodity futures and forex. It does not cover IDX shares or software you run for yourself.
2. **Market manipulation is a crime no matter who places the orders.** Spoofing, wash trades, pre-arranged trades and pump-and-dump are prohibited under UU 4/2023 (P2SK), which carries over UU 8/1995 Art. 104. For the design this means: no order cancel/replace loops, no trading between related accounts, low turnover by default, and stocks on the Special Monitoring Board (Papan Pemantauan Khusus) excluded by default.
3. **Investment-advice licensing.** OJK licenses "penasihat investasi" (investment advisers), and Bareksa's robo-advisor holds licence KEP-17/D.04/2021. Self-hosted software that a person runs and decides with is outside that licence, provided the strategies are presented as example code, not recommendations. That framing is required everywhere (§9.8).
4. **Broker APIs.** No OJK-licensed broker researched (Stockbit, IPOT, Mandiri MOST, BNI, Ajaib, Mirae, Phillip, Trimegah, Valbury, RHB, MNC, Sinarmas) offers a public, documented retail order API. Their "robo" features are closed rules engines inside their own apps. Unofficial access would likely breach the broker's terms of service, which is a civil matter (the account can be frozen). Hence the manual-execution decision.
5. **Tax.**
   - A **0.1% final tax on the gross value of every sale**, on top of broker fees (PP 41/1994 as amended by PP 14/1997, collected by the exchange through the broker; `docs/research/t-fees.md` §2).
   - Domestic dividends to resident individuals are taxed at **10% final** (UU PPh Pasal 17(2c) as restated by UU HPP; PP 19/2009). **Nothing is withheld:** the issuer pays the dividend gross (PP 55/2022 Pasal 9(2)(l)). The dividend is **exempt if it is invested in Indonesia by the end of the third month after the tax year of receipt** (for example, a 2026 dividend by 31 March 2027) and **held in qualifying forms for at least 3 tax years counted from that year**. IDX shares qualify, and switching between qualifying forms is allowed (PMK 18/2021 Pasal 35–36). The investor must also file a yearly investment-realisation report (PMK 81/2024 Pasal 370 and 374). If the condition is missed, the 10% is owed as of the day of receipt and the investor pays it themselves by the 15th of the next month (PMK 81/2024 Pasal 372–373). Partial reinvestment exempts the invested part only. *Verified from the regulation text by T-TAX (§12); the details, quotes and unverified points are in `docs/research/t-tax.md`. The tax treatment stays a config switch, and the default is the conservative 10%.*
6. **Market mechanics.**
   - A lot is 100 shares, and regular-market orders must be in whole lots.
   - Settlement is T+2.
   - Regular-market sessions (IDX Rule II-A, Kep-00003/BEI/04-2025, in force 8 Apr 2025, and unchanged in Kep-00136/BEI/09-2026): Session I 09:00–12:00 WIB Monday to Thursday (09:00–11:30 on Friday); Session II 13:30–15:49:59 (14:00–15:49:59 on Friday); pre-closing auction 15:50–15:59:59. The continuous-session hours were the same in the 2023 rule. *Corrected by T-RULES: an earlier draft dated this change to 15 Dec 2025, from a news source.*
   - The auto-rejection revision is **adopted** (Kep-00136/BEI/09-2026, issued 21 Sep 2026). From 28 Sep 2026 the minimum price falls from Rp50 to Rp1, stocks at Rp1–10 get a fixed ±Rp1 band, and ARB stays at 15%. From 1 Jan 2027 the bands are symmetric: 35% for Rp11–200, 25% for over Rp200–5,000, and 20% above Rp5,000. The full dated history is in `docs/research/t-rules.md`.
   - For these reasons, every one of these values is **dated data in a file**, never a constant in code.
7. **Data licensing.** Yahoo Finance `.JK` is reached through the community library `yfinance`, which is Apache-2.0 licensed. Yahoo's terms make anything beyond personal, non-commercial use a grey area. Each self-hoster fetches their own data for their own use, and the project never redistributes data. `DataSource` is a plugin, so a licensed feed such as EODHD or Twelve Data can replace Yahoo.

## 4. Architecture

### 4.1 Repository layout

```
steadyhand/                      # uv workspace, public monorepo
├── packages/
│   ├── steadyhand/              # engine library (PyPI: steadyhand)
│   │   └── src/steadyhand/
│   │       ├── money.py         # Money, Currency: integer minor units, never float
│   │       ├── types.py         # Instrument, Bar, CorporateAction, Order, Fill, Position
│   │       ├── portfolio.py     # Portfolio: settled/unsettled cash, positions, entitlements
│   │       ├── market.py        # MarketRules protocol
│   │       ├── data.py          # DataSource protocol
│   │       ├── broker/          # Broker protocol, SimulatedBroker, ManualBroker (stub)
│   │       ├── risk.py          # RiskManager + RiskLimits
│   │       ├── sizing.py        # Sizer protocol; CompoundingSizer (default)
│   │       ├── engine.py        # the daily loop shared by backtest and paper modes
│   │       ├── backtest.py      # historical driver over engine.py
│   │       ├── metrics.py       # return, risk, cost and income metrics
│   │       ├── income.py        # dividend ledger, income goal tracker, projection
│   │       ├── audit.py         # plain-English decision log
│   │       └── strategies/      # Strategy protocol + library + docs/<name>.md
│   └── steadyhand-idx/          # IDX distribution (PyPI: steadyhand-idx)
│       └── src/steadyhand_idx/
│           ├── rules.py         # IdxMarketRules (reads data/*.toml)
│           ├── calendar.py      # IDX trading days and holidays
│           ├── yahoo.py         # YahooDataSource (.JK)
│           ├── cache.py         # local price/action cache (SQLite)
│           ├── universe.py      # dated LQ45 membership + exclusions
│           ├── state.py         # paper-trading state (SQLite)
│           ├── config.py        # TOML config loading + validation
│           ├── cli.py           # `steadyhand-idx` entry point
│           └── data/            # tick_sizes.toml, auto_reject.toml, fees.toml,
│                                # holidays.toml, exclusions.csv (no LQ45 lists: §9.4)
├── docs/                        # strategy guide, getting started, specs, plans
└── tests/                       # per-package test suites + cross-package golden tests
```

### 4.2 Engine dependency rule

The `steadyhand` engine **depends on the Python standard library only at runtime** (test and dev tools such as pytest and hypothesis are dev dependencies). That keeps its supply-chain surface small and means contributors never have to install a data stack just to write a strategy. `steadyhand-idx` depends on `steadyhand` and `yfinance`. A test checks the engine's declared dependencies (§10.1). Neither package imports anything from the other's private modules. `steadyhand-idx` uses only the engine's public API, which proves that API is enough for a real distribution.

### 4.3 Core interfaces

These signatures are illustrative. Their final form is fixed in the implementation plan.

```python
class MarketRules(Protocol):
    currency: Currency
    def lot_size(self, instrument: Instrument, on: date) -> int: ...
    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money: ...
    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]: ...
    def costs(self, side: Side, gross: Money, on: date) -> Costs: ...        # fee, levy, sell tax
    def settlement_date(self, trade_date: date) -> date: ...                   # T+2 on trading days
    def dividend_tax(self, gross: Money, reinvested_by_deadline: bool, on: date) -> Money: ...  # reshaped in M4 (§6.2)
    def is_trading_day(self, day: date) -> bool: ...

class DataSource(Protocol):
    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]: ...        # UNADJUSTED OHLCV
    def corporate_actions(self, instrument: Instrument, start: date, end: date) -> Sequence[CorporateAction]: ...

class Strategy(Protocol):
    name: str
    def target_weights(self, view: MarketView, portfolio: PortfolioView) -> Mapping[Instrument, Decimal]: ...

class Broker(Protocol):
    def submit(self, orders: Sequence[Order], on: date) -> Sequence[OrderAck]: ...
    def fills(self, on: date) -> Sequence[Fill]: ...
```

- **Strategies return target weights, not orders.** A strategy says what share of the portfolio each stock should be, and the Sizer and RiskManager turn that into legal orders. This keeps strategies short and readable for non-experts, and puts every rule about lots, ticks, cash and caps in one tested place.
- **`MarketView` enforces no look-ahead.** It only exposes bars dated on or before the decision date. Asking for a later bar raises `LookAheadError`, and a test proves this for every strategy (§10.3).
- **Prices are stored unadjusted, and corporate actions are applied by the engine.** Pre-adjusted closes already fold dividends into the price, so booking dividends as cash on top of them would count those dividends twice. Splits change the share count; dividends create entitlements.

### 4.4 Money

`Money` holds an **integer amount in minor units** plus a `Currency`. IDR has no minor unit in practical use, so for IDR one unit is one rupiah. Rates and weights such as fee percentages, yields and target weights are `Decimal`. `float` is not allowed in money or weight code, and a test enforces that (§10.1). Rounding is explicit: a buy's cost rounds up, and sale proceeds and dividends round down, so the simulation never overstates what you have.

## 5. The daily run (data flow)

`engine.run_day(day)` is the single loop that both modes use. The backtester calls it for each historical trading day. Paper mode calls it once per trading day, after the market closes (at about 16:30 WIB) and after the post-closing session ends at 16:15 WIB.

1. **Fetch and validate.** Get today's bars and corporate actions for the universe and held stocks, and write them to the cache. The run **stops without trading** in any of these cases:
   - the newest bar is not dated to the most recent IDX trading day (stale data);
   - any held stock is missing a bar;
   - a close-to-close move lies outside that day's auto-reject band and no split explains it (impossible data);
   - a price is non-positive, or a price or volume is malformed or negative. A zero volume is valid data (the stock did not trade), and §5.1 rejects orders on that day.

   Good cached data is never overwritten by data that fails validation.
2. **Corporate actions.**
   - A **split** or **reverse split** adjusts the share count and the average cost of the position.
   - Holding a stock on the day before its **ex-date** creates a dividend **entitlement**.
   - On the **pay date**, the dividend is credited as *dividend cash*, tagged with its reinvestment deadline. The broker pays it gross (§3.5). With `dividend_reinvestment_exemption` off (the default), the engine books 10% as tax on the pay date, which models an investor who self-pays it, so the spendable dividend cash is the net amount.
   - Yahoo gives ex-dates, not pay dates, so the pay date is `ex_date + pay_lag_trading_days`, counted on the IDX holiday calendar. The default lag is **14**, the 90th percentile of 47 KSEI-scheduled dividends from 2025–2026 (`docs/research/t-pay.md` §4); it is a config value (§9.5), and a per-stock override file (`dividend_pay_dates.csv`) wins when a row exists for that stock. At 14, 43 of the 47 are credited on or after their real pay date and none is more than 2 trading days early, so the model errs towards understating income. The reinvestment deadline is **not** taken from this modelled date (§6.2).
   - Any **other** action on a held stock, such as a rights issue or a merger, **freezes** that stock (no orders in or out) and raises a flag for the operator to resolve.
3. **Fill yesterday's orders.** Orders queued on the previous trading day fill at **today's open** (§5.1).
4. **Decide.** The active strategy receives a `MarketView` up to and including today, and returns target weights.
5. **Size and check.** The Sizer turns target weights into share quantities using settled cash plus reinvestable dividend cash. Quantities are rounded **down** to whole lots. The RiskManager then applies its limits (§6). Each order that is dropped or cut back is written to the audit log with a reason.
6. **Queue.** The approved orders are queued for tomorrow's open.
7. **Save and report.** The whole day runs as **one SQLite transaction**. The day's report lists fills, orders queued, blocked orders with their reasons, cash (settled and unsettled), holdings, dividends received and upcoming, and income goal progress.

### 5.1 Simulated fills

- The fill price is the next session's **open**, adjusted by slippage (default 0.10%: buys pay more, sells receive less) and then rounded to a valid tick **against the trader** (buys round up, sells round down).
- An order is **rejected** if the fill price falls outside that day's auto-reject band, if the stock did not trade that day (zero volume), or if the stock is frozen.
- An order larger than **10% of that day's traded volume** (configurable) is cut down to 10% of volume, rounded down to whole lots, and the cut is logged. This stops a backtest assuming it could trade unlimited size in a thinly traded stock.
- Costs, all from `fees.toml` with effective dates (`docs/research/t-fees.md`): the broker commission (per preset, different for buys and sells, with VAT on it); the exchange levy on both sides (IDX 0.018%, KPEI 0.009% and KSEI 0.003%, VAT on those three, and KPEI's 0.01% guarantee fund, which carries no VAT: 0.0433% today); the 0.1% sale tax on sales; and, from 2021, the Rp10,000 stamp duty on each trade confirmation, which brokers issue once per trading day: every confirmation until 11 Jan 2022, and from 12 Jan 2022 only one over Rp10,000,000 (PP 3/2022; `t-verify.md` §3.2). How M2 charges it is a plan decision (`t-fees.md` §6, `t-verify.md` §5). A preset whose quoted rate is all-in says what it includes, so nothing is charged twice. The costs of a trade are summed and rounded once, against the trader.
- Sale proceeds are **unsettled** until T+2 trading days. Only settled cash plus dividend cash can be spent.

## 6. Risk controls and sizing

### 6.1 RiskManager (defaults; every value configurable)

| Control | Default | On breach |
|---|---|---|
| Cash only | always on | No shorting, no margin; a buy with insufficient settled cash is cut or dropped |
| Max weight per stock | 10% of portfolio value | Buy is cut back to the cap |
| Min position size | 1 lot | Anything smaller is dropped |
| Daily loss limit | 5% portfolio drop in one day | Strategy **halts**: no new orders until `steadyhand-idx resume` |
| Max drawdown kill switch | 25% below the high-water mark | Strategy **halts** until `resume` |
| Special Monitoring Board / exclusions | excluded | Never bought; held ones are frozen and flagged |
| Idempotency | always on | A second run for the same trading date is a no-op that reports it already ran |

A halt is recorded in state and survives a restart. `resume` requires the operator to type the strategy name, logs who resumed it and when, and refuses to run while the cause (for example, stale data) is still present.

### 6.2 Sizing

- **`CompoundingSizer` (default):** position sizes are computed from **current** portfolio value, meaning all cash (settled and unsettled) plus holdings at the last close, times the target weights. Only settled cash can be spent, so a buy is still cut to the settled cash available. The same value is used for the daily loss limit and drawdown, so selling a stock never looks like a loss while its proceeds settle. Gains and reinvested dividends increase future sizes automatically. This is the "start small, reinvest profits" behaviour.
- **Top-ups:** `monthly_contribution` in config adds cash on the first trading day of each month, in backtest and paper modes. It is optional and defaults to 0.
- **Reinvestment:** dividend cash is spent on the next day's targets. Its deadline tag means income reports can show how much dividend cash still needs reinvesting for the tax exemption. With the exemption switch on, each dividend also carries an exemption claim: the amount reinvested by the deadline, and a protection end date (31 December of the third tax year counted from the year of the qualifying purchase, the stricter reading). If share holdings at cost fall below the amount still protected, the claim breaks, and 10% of the shortfall is booked as tax dated to the original pay date (`docs/research/t-tax.md` §7). The deadline's tax year is the year of the **ex date** unless `dividend_pay_dates.csv` gives the real pay date: a modelled pay date can push a December payment into January and make the deadline a year late, while the ex date's year is never later than the real one (`docs/research/t-pay.md` §4). The M4 plan replaces `dividend_tax`'s `reinvested_by_deadline: bool` with a read of that claim. The yearly reports and any self-payment are the investor's own paperwork, so exemption figures are labelled as estimates.

## 7. Income goal (the primary objective)

`income.py` owns the dividend ledger and everything reported about income. Metrics:

- **Dividend income:** gross, tax and net, shown by month, as a trailing 12-month total, and as a monthly average (trailing 12 months ÷ 12).
- **Current yield:** trailing 12-month dividends ÷ current value. **Yield on cost:** trailing 12-month dividends ÷ what was paid for the holdings.
- **Payment calendar:** expected pay months per holding, based on each stock's own dividend history, and how evenly income is spread across the year.
- **Income goal tracker:** the operator sets `monthly_income_target` (in IDR). The report shows the current monthly average against the target, the percentage reached, and a **projection** of years to reach the target under three scenarios:

| Scenario | Dividend growth | Price growth | Yield |
|---|---|---|---|
| Pessimistic | 0% | 0% | trailing yield × 0.8 |
| Base | portfolio's own trailing 5-year dividend growth, capped at 5%/yr | 0% | trailing yield |
| Optimistic | trailing 5-year dividend growth, capped at 10%/yr | 0% | trailing yield |

  Every scenario reinvests all dividends and adds `monthly_contribution`. Price growth is 0% in all three on purpose, so the projection never relies on the market rising. Every output is labelled **"Projection, not a promise"**, and the figure is the number of years to the target in each scenario, never a date.
- **Strategy income impact:** every backtest report compares the strategy's final trailing 12-month dividend income against the buy-and-hold baseline over the same period, so the operator can see whether trading added to future income or took away from it.

## 8. Strategy library

Every strategy ships with `docs/strategies/<name>.md` in **plain English**. Each guide has the same sections: *What it does* (no jargon, or jargon explained where it first appears), *Why people use it*, *When it tends to do badly*, *Risks* (always including "you can lose money", fee drag, and anything specific to the strategy), *How often it trades*, and *Settings you can change*. `steadyhand-idx explain <name>` prints the guide. A test fails if any registered strategy is missing a guide or any of its sections (§10.1).

The universe is the **LQ45** (IDX's list of 45 large, liquid stocks) as it stood on each date (§9.4), unless the operator configures otherwise.

| # | Strategy | In one line | Turnover | Wave |
|---|---|---|---|---|
| 1 | `buy-and-hold` | Buy the whole universe equally and hold. It is **the baseline every other strategy is measured against**. | very low | 1 |
| 2 | `monthly-savings` | Put the same amount in every month, split equally, and never sell (dollar-cost averaging) | very low | 1 |
| 3 | `dividend-growth` (**default**) | Hold 15–25 stocks whose total dividend per share has not fallen in any of the last 5 calendar years (adjusted for splits), weighted towards spreading pay months across the year, and reinvest everything | low | 1 |
| 4 | `high-yield` | Hold the top 10 stocks by trailing 12-month dividend yield that have paid for at least 3 years, rebalanced quarterly | low | 2 |
| 5 | `ma-trend` | Hold a stock while its 50-day average price is above its 200-day average; sell when that reverses | low–medium | 2 |
| 6 | `momentum-rotation` | Each month, hold the top 10 stocks by 12-month return, skipping the most recent month | medium | 2 |
| 7 | `dual-momentum` | Momentum rotation, but move to cash when even the best performers have fallen over 12 months | medium | 3 |
| 8 | `low-volatility` | Hold the 10 stocks whose prices have swung least over the past year | low | 3 |
| 9 | `breakout` | Buy when a stock closes at a 55-day high; sell at a 20-day low | medium | 3 |
| 10 | `rsi-reversion` | Buy stocks that have fallen sharply over a short period (RSI below 30); sell when they recover (RSI above 55) or after 20 days | high | 4 |
| 11 | `dividend-capture` | Buy just before ex-date and sell just after. **Shipped for learning:** on IDX the price usually drops by about the dividend on ex-date, so fees and the sell tax are expected to make this lose. The guide says so plainly. | high | 4 |

- **Waves** set the build order. Each wave is fully tested and documented before the next begins. All four waves are in scope for sub-project A.
- **Deferred:** a true P/E or book-value "value" strategy. Free sources give today's fundamentals, not the figures as they stood on past dates (point-in-time), so backtesting such a strategy would use numbers nobody had at the time (look-ahead bias). It returns when a point-in-time fundamentals source exists. `high-yield` covers value-style investing using only price and dividend history, which is valid on past dates.
- Parameters shown (stock counts, windows, thresholds) are defaults, and each can be changed in config.

## 9. IDX distribution details

### 9.1 Market rules data (`data/*.toml`, all effective-dated)

- `tick_sizes.toml`: the IDX price-tier tick table, as sourced by T-RULES (`docs/research/t-rules.md` §1), with its history in `docs/research/t-hist.md` §3 (primary-verified from 13 Mar 2020). The tier is chosen by the order price, and each tier's lower bound is inclusive. Boundary tests are written against that source, not against memory.
- `auto_reject.toml`: ARA/ARB bands by price tier, with **effective-from dates**, as sourced by T-RULES (`docs/research/t-rules.md` §3), including the 28 Sep 2026 and 1 Jan 2027 changes, with the 2020 changes in `docs/research/t-hist.md` §4. The reference price is in `docs/research/t-verify.md` §4: the opening price from 13 Mar to 6 Sep 2020, and the previous close from 7 Sep 2020. The tier edges differ from the tick table (200 and 5,000 fall in the lower auto-reject tier), so the two tables never share a tier function.
- `fees.toml`: effective-dated levy rows (each component and the VAT rate), the sale tax, the stamp duty, and broker presets (`ajaib`, `stockbit`, `ipot`) plus `custom`, in the shape `docs/research/t-fees.md` §5 recommends. Every row is primary-verified (see below the list). The defaults are marked "check against your broker's fee schedule".
- `holidays.toml`: IDX non-trading days by year. `calendar.py` refuses to run for a year that has no holiday data, instead of assuming no holidays. Every year from 2016 to 2027 is verified from an IDX calendar: 2016–2024 (`docs/research/t-hist.md` §1), 2025 (`docs/research/t-pay.md` §2) and 2026–2027 (`docs/research/t-rules.md` §4).
- `sessions.toml`: trading sessions with effective dates, used for scheduling and reports.

When a rule changes, the change is a data-file edit with a new effective date. Backtests over past dates keep using the rules that applied on those dates.

**Only primary-verified rows ship** (Shyden, 2026-09-25). A backtest refuses a start date earlier than the latest first date of any table in the rule and fee files (`tick_sizes.toml`, `auto_reject.toml`, `fees.toml`, `holidays.toml`), and the error names the table that sets it. The date is derived from the files, never hard-coded. With the rows researched so far it is **2021-01-01**, set by stamp duty, since whether a trade confirmation was dutiable before 2021 is unverified (`docs/research/t-verify.md` §5).

### 9.2 Yahoo data source

- `yfinance` is pinned to an exact version, and Dependabot proposes upgrades.
- It fetches unadjusted OHLCV plus dividends and splits.
- Yahoo's dividends carry the **ex date only**, with no pay or recording date (`docs/research/t-pay.md` §5). Trading days come from `holidays.toml`, never from which days have bars: `^JKSE` has no bar for 22 Sep 2026, which was a trading day (`t-pay.md` §2).
- Retries use exponential backoff: 3 attempts, then `DataUnavailableError` (fail closed).
- It is rate-limited and polite, and fetches only what the cache is missing.
- A scheduled CI workflow (daily, and not a PR gate) fetches a small fixed set of tickers and checks the response shape. On failure it opens a GitHub issue, so a Yahoo format change is noticed before it can break a user's run.

### 9.3 Cache and state

- `cache.py`: SQLite holding bars and actions, keyed by (ticker, date). Validated rows only (§5 step 1).
- `state.py`: SQLite holding paper portfolio, queued orders, fills, entitlements, dividend ledger, halts, run log (unique per trading date), and the audit log.
- Schema migrations are versioned, applied in order and tested. Both files sit in the user's data directory, outside the repo, and are git-ignored.

### 9.4 Universe and survivorship bias

- `lq45_members.toml` holds dated LQ45 membership: one record per IDX document (a review, or a mid-period replacement), each with `effective`, `announced`, `source`, `kind` and the full list of 45 `members`. Membership on a date is the latest record whose `effective` is on or before it. The format and the loader's checks are in `docs/research/t-lq45.md` §4.
- **The file is supplied by the user, never shipped.** IDX's Terms of Use bar redistributing its data for commercial use without written permission, and bar scraping. Apache-2.0 would pass on commercial rights we do not hold (`docs/research/t-lq45.md` §5). So the file lives in the user's data directory, at the path in `[universe] lq45_members` (§9.5). The package ships only the loader and a guide to where IDX publishes each list. Tests use a synthetic file. A missing file is an error that names the key. Nothing downloads from idx.co.id.
- Historical coverage is best-effort. **A backtest that starts before the file's first record, or spans a gap between records, prints a survivorship-bias warning** in its report and output. A gap is two consecutive records more than one review apart: reviews were semi-annual until January 2024 and quarterly from May 2024. Primary lists exist for 19 of the 24 reviews taking effect in 2016–2025 (`t-lq45.md` §3).
- `exclusions.csv` lists stocks excluded by the operator or known to be on the Special Monitoring Board. Yahoo cannot tell us board status, so this file is maintained by hand and dated.

### 9.5 Configuration (`steadyhand.toml`)

```toml
[account]
starting_cash_idr = 10_000_000
monthly_contribution_idr = 0
broker_fees = "custom"          # or a preset name from fees.toml

[goal]
monthly_income_target_idr = 10_000_000

[strategy]
name = "dividend-growth"        # any registered strategy
# per-strategy parameters override defaults here

[risk]
max_weight = "0.10"
daily_loss_limit = "0.05"
max_drawdown = "0.25"
max_volume_participation = "0.10"

[universe]
lq45_members = "lq45_members.toml"   # T-LQ45 (docs/research/t-lq45.md): user-supplied, relative to the data directory

[dividends]
pay_lag_trading_days = 14            # T-PAY (docs/research/t-pay.md): 90th percentile, IDX trading days after the ex date

[tax]
dividend_reinvestment_exemption = false   # rule confirmed by T-TAX (docs/research/t-tax.md); on = estimated exemption
```

Config is validated on load. An unknown key, wrong type or out-of-range value is an error that names the key. Numbers used as rates are strings parsed to `Decimal`, so no floats are involved.

### 9.6 CLI (`steadyhand-idx`)

| Command | Does |
|---|---|
| `init` | Writes a starter config, shows the disclaimer and requires the user to type `I understand`, then creates the data directory |
| `backtest --from --to [--strategy]` | Runs a backtest and writes a report (terminal summary plus a Markdown/CSV file) |
| `compare --from --to s1 s2 …` | Runs several strategies over the same period and shows them in one table against the baseline |
| `paper run` | Runs today's daily cycle, and is safe to run twice |
| `paper status` | Shows holdings, cash, queued orders and halts |
| `report [--income]` | Shows the latest daily report, or the full income goal view |
| `explain <strategy>` | Prints the plain-English guide |
| `resume <strategy>` | Clears a halt after confirmation |
| `strategies` | Lists strategies with their one-line descriptions and turnover |

Exit codes: 0 means success, 2 means a usage or config error, 3 means the run was halted or stopped safely (stale data, a kill switch), and 1 means an unexpected error. Scheduling (cron and similar) is documented in sub-project A's docs. The in-app scheduler belongs to B+C.

### 9.7 Audit log

Every decision writes one plain-English line, stored in the state DB and shown in reports. Examples:

- `2026-10-01 BUY 3 lots BBRI queued: target weight 8.0%, current 5.1% (dividend-growth)`
- `2026-10-01 SKIP TLKM: max weight 10% reached`
- `2026-10-02 HALT: portfolio down 5.4% today, over the 5% daily loss limit. Run 'steadyhand-idx resume dividend-growth' after reviewing.`

### 9.8 Disclaimers

The README, every package README, every strategy guide, `init` and every report footer carry the disclaimer, verbatim: *steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.* It is written once, in the constant `steadyhand.DISCLAIMER`, and tested for presence (§10.1).

## 10. Testing

TDD throughout: a test is written, and shown failing, before any production code. New tests are first run against stubs that throw `NotImplementedError("<name>")`, and any test that passes against a stub is a finding. A bare `raises(Exception)` is not accepted; the test must match on what the error says.

### 10.1 Meta-guards (tests about the codebase)

- No `float` in `money.py`, `portfolio.py`, `sizing.py`, `risk.py`, `income.py`, `metrics.py`, `broker/`. This is checked by AST walk over annotations and literals, and comments do not count, because the check works on the AST, not the text.
- The engine declares no third-party runtime dependencies. This is checked in `pyproject.toml` and by walking every engine module's imports.
- Every registered strategy has a guide with all required sections.
- The disclaimer is present in the README, every guide, and the `init` and report outputs.
- Supply chain: every `uses:` in `.github/workflows/*` is a full 40-hex SHA followed by a `# vX.Y.Z` comment. `dependabot.yml` covers `uv` and `github-actions`, each with `target-branch: develop`, and has a same-repo sub-path actions group above any patch group. The file is parsed as YAML, so comments cannot satisfy the check.
- Each meta-guard is **mutation-verified**: break the real thing, leave any comment naming it, and confirm the guard goes red.

### 10.2 Unit and property-based tests (pytest + hypothesis)

- Properties that must always hold:
  - order quantities are whole lots;
  - settled cash is never negative;
  - costs are never negative, and every sell pays the 0.1% tax;
  - a round trip at an unchanged price always loses exactly the modelled costs;
  - rounding always goes against the trader;
  - splits conserve position value;
  - the total of every cash movement equals the cash balance.
- Boundary values: every tick-table boundary on both sides, every auto-reject band edge, T+2 across weekends, holidays and year-end, lot rounding at exactly 1 lot and 1 lot minus 1 share, and each risk limit at exactly its threshold and one step past it.
- Error paths: every `*Error` type is raised by a test that asserts its message.

### 10.3 Integration and golden tests (real data, no mocks)

- **Recorded real Yahoo responses** for a fixed set of tickers and dates are committed as fixtures (small, with the source and date noted). The data source, cache, rules and engine run end-to-end on them. This is real data replayed, not a hand-made mock.
- **Golden backtests:** `buy-and-hold` and `dividend-growth` over a fixed fixture period must reproduce the stored results **exactly** (integer rupiah). Any change to those results must come with a reviewed update of the stored numbers.
- **No look-ahead:** every registered strategy runs under a `MarketView` that raises on any future access. It also runs a truncation check: running up to day D and running up to D+k must give identical decisions up to D.
- **Idempotency and atomicity:** `paper run` twice on the same date equals `paper run` once. A crash injected at each step of `run_day` leaves state equal to the previous day's.
- **CLI journeys:** `init` → `backtest` → `compare` → `paper run` (×2, same day) → `report --income` → a forced halt → `resume`, run as subprocesses against a temporary data directory with the fixtures, checking exit codes and output.

### 10.4 Non-functional

- **Performance:** a 10-year daily backtest over 45 stocks, run on a deterministic synthetic price series (fixed seed, generated in the test, because 10 years of real fixtures would bloat the repo), finishes in **under 30 seconds** on a GitHub-hosted runner. This is a CI test with a recorded baseline.
- **Concurrency:** two `paper run` processes started together result in exactly one run for that date. This is enforced through an SQLite lock plus the unique run key, and tested with real processes.
- **Security:** `pip-audit` in CI, with any vulnerability failing the build. GitHub secret scanning and push protection are on. No credentials exist in sub-project A. Config and state paths are validated against path traversal.

### 10.5 Quality gates (CI, all required status checks on `develop` and `main`)

- `ruff check` and `ruff format --check`, `mypy --strict`, and `pytest -W error` with **100% branch coverage** for both packages.
- The meta-guards, pip-audit, and a build of both wheels.
- Branch protection: required contexts are listed explicitly and re-read after each is added, with `strict: true`.

## 11. Repository and delivery

- **GitHub:** `ShydenMcM/steadyhand`, public, Apache-2.0, with `main` and `develop`. Each ticket gets its own branch, merged into `develop` by PR. `main` changes only by a release PR from `develop`. Nothing is ever merged straight into `main`.
- **Tooling:** uv workspace, hatchling build backend, Python ≥ 3.12, with a CI matrix of 3.12 and 3.13.
- **Dependabot:** `uv` and `github-actions`, weekly, targeting `develop`, with grouping as in §10.1. Alerts and security updates are enabled explicitly on the repo and read back (an org default does not apply to a personal repo).
- **Release:**
  - A merge into `develop` publishes both packages to **TestPyPI** as `X.Y.Z.devN`. This is the library's dev environment.
  - A GitHub release from `main` publishes to **PyPI**.
  - Both use **trusted publishing (OIDC)**, so no tokens are stored. Setting up the pending publishers on PyPI and TestPyPI is an operator step (§12).
- **Board:** a GitHub Projects board on the `ShydenMcM` account. Every piece of work is a story with full acceptance criteria before it starts.
- **Docs:** README (what it is, what it is not, the disclaimer, quick start), CONTRIBUTING, SECURITY.md (private vulnerability reporting enabled), CODE_OF_CONDUCT, the strategy guide index, and "Getting started for complete beginners".

## 12. Open items and operator steps

| ID | Item | Blocks |
|---|---|---|
| T-TAX | **Done (#25):** `docs/research/t-tax.md`. The exemption now rests on UU HPP, PP 55/2022, PMK 18/2021 Pasal 15–16 and 33–36, and PMK 81/2024 Pasal 370–374 (PP 9/2021's provision was revoked). Deadline, 3-tax-year holding, qualifying forms (IDX shares count) and reporting are verified. No withholding for resident individuals | `dividend_reinvestment_exemption` may be enabled; default stays 10% |
| T-RULES | **Done (#24):** `docs/research/t-rules.md`. The tick table, ARA/ARB bands and minimum price are verified from 2020-12-07, the holidays for 2026–2027, and the sessions from 2023-04-03. Earlier years were listed there as open for M2, and T-HIST (#37) has since researched them | `rules.py` data files and their boundary tests |
| T-LQ45 | **Done (#26):** `docs/research/t-lq45.md`. IDX publishes each review's full list of 45; the earliest found is Feb–Jul 2004. For 2016–2025, 19 of 24 reviews have a primary list (announcements, or IDX's fact-sheet booklets in the Internet Archive). Feb 2019, Feb and Aug 2021, Aug 2022 and Feb 2023 have none. The lists are not ours to ship under Apache-2.0, so the file is user-supplied (§9.4) | survivorship coverage of backtests |
| T-PAY | **Done (#27):** `docs/research/t-pay.md`. 47 cash dividends from 18 issuers (2025–2026), dated from KSEI's schedule letters and counted on the IDX calendar: ex to pay is 6–16 trading days, median 12, 90th percentile 14. The default is 14. No IDX or KSEI rule fixes recording to payment; POJK 15/2020 Pasal 58 caps payment at 30 days after the RUPS minutes are announced. Yahoo gives ex dates only | pay-date modelling default |
| T-HIST | **Done (#37):** `docs/research/t-hist.md`. Holidays for 2016–2024 from IDX's own calendars, each year's trading-day total recomputed and matched, and every holiday cross-checked against Yahoo. Ticks, auto-rejection bands and the reference price are primary-verified from 13 Mar 2020 (Kep-00025/BEI/03-2020); the five-tier tick table from 2 May 2016 is supported by Yahoo prices but no IDX text was found; bands before 9 Mar 2020 are unverified. The reference-price history was completed by T-VERIFY (#41). Yahoo has zero-volume placeholder bars on trading days, and its prices are adjusted even with `auto_adjust=False` | M2 data files; how far back a backtest may run on verified rules |
| T-FEES | **Done (#38):** `docs/research/t-fees.md`. The levy is IDX 0.018% (verified FY2016–2017 and from 13 Mar 2020), KPEI 0.009% (from FY2019), KSEI 0.003% (Rule VI-A, 2021; probable but unverified before, when the 2009 list said 0.006%; T-VERIFY verified 0.003% from FY2019), VAT on those three (10%, then 11% from 1 Apr 2022, and 12% × 11/12 from 2025), and KPEI's 0.01% guarantee fund with no VAT (SEOJK 23/2015; 0.005% from 18 Jun to 17 Dec 2020, verified by T-VERIFY): 0.043%, then 0.0433%. The 0.1% sale tax is PP 41/1994 as amended by PP 14/1997, on gross sale value, collected by the exchange. Stamp duty is Rp10,000 per trade confirmation from 2021 (UU 10/2020); the Rp10 million threshold is PP 3/2022's exemption, from 12 Jan 2022 (found by T-VERIFY). Ajaib, Stockbit and IPOT publish no minimum fee; only Ajaib states that its quote includes levy and sale tax | `fees.toml` and M2's fees task |
| T-VERIFY | **Done (#41):** `docs/research/t-verify.md`. Shyden's rule: a backtest refuses dates whose rule or fee rows are not primary-verified. KSEI's 0.003% is verified from FY2019 (KSEI's audited notes), and the 2020 guarantee-fund cut ran 18 Jun – 17 Dec 2020 (KPEI's audited notes). The reference price was the opening price from 13 Mar to 6 Sep 2020 and has been the previous close since 7 Sep 2020 (Kep-00063, then the interim clauses of every II-A until Kep-00196). This corrects T-RULES and T-HIST, which read the attachments rather than the cover decisions. Stamp duty is verified from 1 Jan 2021 (UU 10/2020, and PP 3/2022's Rp10,000,000 exemption from 12 Jan 2022), and unverified before, so the earliest verified date is 2021-01-01 | §14 AC1's start date; `fees.toml`, `auto_reject.toml` |
| OP-1 | Operator: set up trusted publishers on PyPI and TestPyPI for `steadyhand` and `steadyhand-idx` | first publish |
| OP-2 | Operator: approve creating the public GitHub repo and board on `ShydenMcM` | repo creation |
| OP-3 | Operator (optional, parallel): ask brokers whether an official or institutional API programme exists | only future IDX automation |

## 13. Implementation milestones (one plan each)

1. **M1 Foundations:** repo, CI, meta-guards, supply chain, `money`, `types`, `portfolio`, `MarketRules`/`DataSource`/`Broker` protocols, and TestPyPI dev publishing from `develop` (§11).
2. **M2 IDX rules and data:** `rules.py` and data files (after T-RULES), calendar, Yahoo source, cache, fixtures.
3. **M3 Engine and backtester:** `run_day`, SimulatedBroker, RiskManager, CompoundingSizer, corporate actions, metrics, golden tests, performance test.
4. **M4 Income:** dividend ledger, income goal tracker, projection, calendar.
5. **M5 Paper trading and CLI:** state DB, idempotency and atomicity, halts and resume, all CLI commands, CLI journeys.
6. **M6–M9 Strategy waves 1–4**, each with its guides.
7. **M10 First release:** docs, and the first PyPI release from `main`.

## 14. Acceptance criteria for sub-project A

1. `steadyhand-idx init` then `backtest --from 2021-01-01 --to 2025-12-31 --strategy dividend-growth` (2021-01-01 is the earliest date every rule and fee row is primary-verified, §9.1) completes against real Yahoo data (a manual live acceptance run; CI runs the same journey on recorded fixtures) and prints return, drawdown, costs, dividend and income-goal metrics next to the buy-and-hold baseline.
2. `compare` over the same period shows all 11 strategies in one table.
3. `paper run` on consecutive trading days keeps a consistent portfolio, fills orders at the next open with IDX costs applied, honours T+2, credits dividends on pay dates, and is idempotent.
4. Stale, missing or impossible data stops the run with exit code 3 and trades nothing.
5. Breaching either kill switch halts the strategy until `resume`.
6. Every strategy has a complete plain-English guide, available through `explain`.
7. The income report shows current against target monthly income and the three-scenario projection, labelled "Projection, not a promise".
8. All quality gates in §10.5 are green, and both packages are published to TestPyPI from `develop`.

---

## Appendix A: Sources (research of 2026-09-24)

- Regulatory gap for algorithmic tools: https://www.academia.edu/143346320/
- Bappebti robot-trading regulation 12/2022: https://pluang.com/akademi/berita-analisis/aturan-untuk-robot-trading-di-indonesia
- Indonesia fintech overview: https://chambers.com/content/item/5520
- Market manipulation and Art. 104: https://siplawfirm.id/mengenal-pump-and-dump ; OJK enforcement 2026: https://aktual.com/ojk-percepat-pengusutan-32-kasus-manipulasi-saham-di-2026/
- Bareksa licensed robo-advisor: https://investasi.kontan.co.id/news/bareksa-luncurkan-robo-advisor-berlisensi-penasihat-investasi-dari-ojk
- Tax on share sales and dividends: https://pajakstartup.com/2025/03/11/skema-pajak-untuk-investor-pasar-modal-pph-final-atas-saham-dan-obligasi/ ; https://www.heygotrade.com/id/blog/pajak-saham-investor-indonesia/ ; https://help.stockbit.com/id/article/ketentuan-pajak-dividen-untuk-keperluan-spt-1r8j1zt/
- Dividend tax and the reinvestment exemption (primary regulation texts from peraturan.bpk.go.id, verified 2026-09-25 by T-TAX): UU 7/2021 (HPP) https://peraturan.bpk.go.id/Details/185162 ; PP 55/2022 https://peraturan.bpk.go.id/Details/233488 ; PP 19/2009 https://peraturan.bpk.go.id/Details/4933 ; PMK 18/PMK.03/2021 https://peraturan.bpk.go.id/Details/162653 ; PMK 81/2024 https://peraturan.bpk.go.id/Details/306614 ; the full list is in `docs/research/t-tax.md`
- Trading hours, tick table, minimum price and ARA/ARB bands (IDX primary documents, verified 2026-09-25 by T-RULES): Rule II-A Kep-00136/BEI/09-2026 https://www.idx.co.id/Media/bgqhucr0/signed_perubahan_peraturan_nomor-_ii_a__tentang_perdagangan_efek_bersifat_ekuitas.pdf ; Kep-00003/BEI/04-2025 https://www.idx.co.id/Media/mrekbmz3/signed_peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf ; the earlier versions and the 2026–2027 holiday announcements are listed in `docs/research/t-rules.md`
- Special Monitoring Board revision (secondary): https://www.idnfinancials.com/news/65578/idx-to-revise-special-monitoring-board-and-auto-rejection-rules ; https://www.abnrlaw.com/news/indonesia-stock-exchange-revisits-equity-trading-rules
- Dividend pay lag (KSEI schedule letters, IDX 2025 holiday calendar Peng-00213/BEI.POP/10-2024 and Peng-00149/BEI.POP/08-2025, POJK 15/POJK.04/2020 Pasal 51 and 58, verified 2026-09-25 by T-PAY): sources and the 47-row sample in `docs/research/t-pay.md`
- Holidays 2016–2024, Kep-00025/BEI/03-2020 (the March 2020 auto-rejection change and II-A as then in force) and Peng-00504/BEI.OPP/06-2018 (27 Jun 2018 a trading day), verified 2026-09-25 by T-HIST: sources, and which came from the Internet Archive, in `docs/research/t-hist.md`
- Exchange levy, sale tax, VAT, stamp duty and broker fees (PP 41/1994 and PP 14/1997, UU 42/2009, UU 7/2021, PMK 131/2024, UU 10/2020 from peraturan.bpk.go.id; IDX and KPEI annual reports; KSEI Rule VI-A and fee lists; KPEI pages; four brokers' own pages), verified 2026-09-25 by T-FEES: sources, and which are secondary, in `docs/research/t-fees.md`
- KSEI's and KPEI's audited annual reports (KSEI 2019 and 2020, KPEI 2021), the SRO joint decree of August 2020, IDX decisions Kep-00063/BEI/09-2020, Kep-00108/BEI/12-2020, Kep-00061/BEI/07-2021, Kep-00055/BEI/03-2023 and Kep-00196/BEI/12-2024 (idx.co.id as a fallback), IDX's rules page in three Archive captures, and PP 24/2000, UU 10/2020, PMK 151/2021 and PP 3/2022 from peraturan.bpk.go.id, verified 2026-09-25 by T-VERIFY: sources in `docs/research/t-verify.md`
- T+2 settlement: https://www.idx.co.id/en/news/tplus2-settlement/
- SID/RDN: https://help.bions.id/docs/apa-itu-sid-rdn-sre-dan-kartu-akses/
- Broker APIs: IPOT in-app robo trading (indopremier.com), unofficial community bots (github.com/mascahyo1/trading-bot)
- Yahoo data terms: https://scrapfly.io/blog/posts/guide-to-yahoo-finance-api
- IBKR availability in Indonesia: https://brokerchooser.com/broker-reviews/interactive-brokers-review/interactive-brokers-indonesia

**Unverified (to confirm before relying on):** whether each broker's terms explicitly ban automation; IDX coverage and pricing from EODHD, Twelve Data and Polygon; IDX official data pricing; direct eligibility for Alpaca and Saxo; whether IBKR covers IDX; tax treatment of foreign-regulated accounts. The dividend exemption conditions were verified by T-TAX; its own open points are listed in `docs/research/t-tax.md`.

## Appendix B: Spec review log

(Review passes are recorded below. The loop ends on a pass with zero findings.)

- **Pass 1 (2026-09-24):** placeholder scan found 0. Findings, all fixed: (1) engine dependency rule didn't separate runtime from dev deps; (2) the performance-test data source was ambiguous; (3) AC1 needed live data with no CI equivalent; (4) "uncut dividends" was undefined; (5–7) top-N defaults were unspecified for high-yield, momentum-rotation and low-volatility; (8–9) Dependabot ecosystem was ambiguous ("uv (or pip)").
- **Pass 2 (2026-09-24):** 1 finding, fixed: §8 still referred to "N" after pass 1 removed it.
- **Pass 3 (2026-09-24):** mechanical checks: placeholders 0; leftover `top-N`/`pip` ambiguity 0; every §12 ID referenced in the body exists in §12 (T-TAX, T-RULES, T-LQ45, T-PAY, OP-1..3); every milestone in §13 maps to spec sections; the 11 strategies in §8 match AC2's count. Full read: **0 findings. Loop closed.**
- **Pass 4 (2026-09-24, while planning M1):** 5 findings, all fixed: (1) §5 step 1 said a non-positive volume stops the run, which contradicts §5.1 rejecting orders on a zero-volume day; zero volume is now valid data. (2) §6.2 defined portfolio value as settled cash plus holdings, so every sale would look like a loss to the daily loss limit until its proceeds settled; it is now all cash plus holdings, with spending still limited to settled cash. (3) §9.8 paraphrased the disclaimer; it now quotes the exact text of `steadyhand.DISCLAIMER`, which is the README's wording. (4) §13 put TestPyPI publishing in M10, against §11 and the rule that every `develop` merge deploys; it moves to M1. (5) The status line still said draft.
- **Pass 5 (2026-09-24):** mechanical: grep for every term pass 4 touched (settled cash, portfolio value, TestPyPI, non-positive, the disclaimer, zero volume, M10, Draft) found no contradicting wording left. Full read of §5, §6, §9.8, §11, §13 and §14: **0 findings. Loop closed.**
- **Pass 6 (2026-09-25, T-RULES #24):** §3.6, §9.1, §12 and Appendix A were brought into line with the IDX primary documents in `docs/research/t-rules.md`. Two findings, both fixed: (1) §3.6 dated the trading-hours change to 15 Dec 2025 under Kep-00003/BEI/04-2025, but that decision took effect on 8 Apr 2025 and the continuous-session hours have been the same since the 2023 rule; (2) §3.6 called the auto-rejection revision "proposed, no date", but it was adopted as Kep-00136/BEI/09-2026, in force from 28 Sep 2026 with symmetric bands from 1 Jan 2027. A grep for "15 Dec", "under revision", "no implementation date" and "bidiknews" now finds only the correction note. **0 further findings.**
- **Pass 7 (2026-09-25, T-TAX #25):** §3.5, §4, §5, §6.2, §9, §12 and Appendix A were brought into line with the regulation texts in `docs/research/t-tax.md`. Findings, all fixed: (1) §3.5 called the dividend tax a withholding tax, but PP 55/2022 Pasal 9(2)(l) has resident individuals paid gross, and the tax is self-paid only when the investment condition is missed; (2) §3.5 cited PP 9/2021, whose dividend provision PP 55/2022 revoked; (3) §3.5 left the holding period open, and it is 3 tax years (PMK 18/2021 Pasal 36(2)), with a yearly report that is itself a condition (PMK 81/2024 Pasal 370 and 374); (4) §5 said cash arrives net of tax, and it arrives gross, with the default-off switch booking the 10%; (5) `dividend_tax`'s `reinvested_by_deadline: bool` cannot express a holding, a partial claim or a broken one, so §6.2 defines an exemption claim and §4 marks the signature for M4; (6) Appendix A still listed the exemption conditions as unverified. The same wording error in code (`market.py`'s `dividend_tax` docstring said "withheld") was fixed in the same change. A grep for `withholding`, `PP 9/2021`, `once T-TAX`, `net of dividend tax` and `T-TAX confirms` across the repo finds no contradicting wording left.
- **Pass 8 (2026-09-25, T-PAY #27):** §5, §6.2, §9.1, §9.2, §9.5, §12 and Appendix A were brought into line with `docs/research/t-pay.md`. Findings, all fixed: (1) §5 left the default pay lag open, and it is 14 IDX trading days (the 90th percentile of 47 KSEI-scheduled dividends); (2) §9.5 had no key for it, so an operator could not set the value §5 calls configurable, and `[dividends] pay_lag_trading_days` is added; (3) §6.2 would have dated the reinvestment deadline from the modelled pay date, which moves a December payment into January and makes the deadline a year late, so the deadline now takes the ex date's year unless an override gives the real pay date; (4) §9.1 did not say which holiday years are verified, and 2025 is now verified alongside 2026–2027; (5) §9.2 did not say that Yahoo gives no pay date, or that `^JKSE` bars have gaps and cannot define the calendar. A first wording of (1) claimed a lag of 14 never credits early, which 4 of 47 contradict; it was corrected before commit. A grep for `pay_lag`, `pay date`, `T-PAY` and `holidays.toml` across the spec finds no contradicting wording left.
- **Pass 9 (2026-09-25, T-LQ45 #26):** §4, §9.4, §9.5 and §12 were brought into line with `docs/research/t-lq45.md`. Findings, all fixed: (1) §9.4's `lq45_membership.csv` shipped as package data, and IDX's Terms of Use bar redistributing its data for commercial use, which Apache-2.0 would pass on; the file is now user-supplied and never shipped. (2) The (ticker, from_date, to_date) rows were written separately from their source and could overlap or leave holes; the format is now one record per IDX document, each with the full list of 45. (3) §9.4 called the announcements semi-annual, and they are quarterly from May 2024. (4) The survivorship warning looked only at the start date, and the lists have five gaps inside 2016–2025; it now fires on a gap too. (5) §9.5 had no key for the user-supplied file, and `[universe] lq45_members` is added. Recorded for the M2 plan, not changed: §8's "unless the operator configures otherwise" names no config key for another universe. A grep for `lq45_membership`, `from_date, to_date` and `semi-annual LQ45` finds nothing left in the spec.
- **Pass 10 (2026-09-25, T-HIST #37):** §9.1, §12 and Appendix A were brought into line with `docs/research/t-hist.md`. Findings, all fixed: (1) §9.1 listed verified holiday years as 2025–2027 only, and every year from 2016 is now verified from an IDX calendar; (2) §12's T-RULES row still called the pre-2026 years open for M2; (3) §9.1's tick and auto-rejection bullets named only T-RULES, which starts in December 2020; (4) §12 had no row for T-HIST or for T-FEES (#38), which Shyden added on 2026-09-25. Recorded for the M2 plan, not changed here: ticks and bands are primary-verified only from 13 Mar 2020, and Yahoo's zero-volume placeholder bars and adjusted prices (`t-hist.md` §6) bear on §4.3, §5 and §5.1. A grep for `2026–2027`, `open for M2` and `not researched` across the spec finds no contradicting wording left.
- **Pass 11 (2026-09-25, T-FEES #38):** §3, §5.1, §9.1, §12 and Appendix A were brought into line with `docs/research/t-fees.md`. Findings, all fixed: (1) §5.1 named "exchange levy" as one number, while it is four components plus VAT, with VAT not charged on the guarantee fund; (2) §5.1 and §9.1 had no stamp duty, a fixed Rp10,000 per trading day from 2021 that outweighs every rate on small trades; (3) §9.1 did not say that an all-in broker quote must declare what it includes, without which the levy and sale tax are charged twice; (4) §3's sale-tax bullet cited no regulation, and Appendix A's only fee sources were blogs; (5) §12's T-FEES row was still open. Recorded for the M2 plan, not changed here: §4.3's `costs(side, gross, on)` is per trade, and stamp duty is per trading day, so the interface cannot charge it as written; and whether M2 ships stamp duty and the `stockbit` and `ipot` presets at all (`t-fees.md` §6). A grep for `sell tax`, `levy`, `broker fee`, `fees.toml` and `stamp` across the spec finds no contradicting wording left.
- **Pass 12 (2026-09-25, T-VERIFY #41):** §5.1, §9.1, §12, §14 and Appendix A were brought into line with `docs/research/t-verify.md` and Shyden's decision that backtests refuse unverified rows. Findings, all fixed: (1) §9.1's fees bullet shipped `verified = false` rows, which the decision rules out. (2) §14 AC1 started on 2016-01-01, before the earliest verified date. (3) §9.1 cited `t-hist.md` §5 for the reference price, which read the II-A attachments and missed the cover decisions' interim *Harga Previous*. (4) §12's T-HIST row placed the reference switch in 2023–2024, while it was 7 Sep 2020. (5) §12's T-FEES row gave the guarantee-fund window as ending about 16 Dec 2020 from a secondary source, while KPEI's notes say 17 Dec. (6) §5.1 and §12 called the Rp10,000,000 threshold broker practice and charged it from 2021, while it is PP 3/2022's exemption from 12 Jan 2022. (7) §9.1 stated no rule for the start date, so a hard-coded date could drift from the data files; the date is now derived from them.
- **Pass 13 (2026-09-25, review of Pass 12):** a read of Pass 12's diff. Two findings, fixed: (1) §12's T-HIST row still called the verified reference the opening price, while it was the previous close from 7 Sep 2020; (2) §9.1's start-date rule said "the latest of the data files' first dates", which is ambiguous for `fees.toml`, whose tables start on different dates, and did not name the files. It now names the four files and takes the latest first date of any table.
