# steadyhand — Sub-project A: Core Engine, IDX Rules, Backtester and Paper Trading

- **Status:** Draft for operator review
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
   - A **0.1% final tax on the gross value of every sale**, on top of broker fees.
   - Dividends to resident individuals carry a **10% final withholding tax**. Under PP 9/2021 this can be **exempted if the dividend is reinvested in Indonesia by the end of the third month after the tax year** (for example, a 2026 dividend must be reinvested by 31 March 2027). *The exact exemption conditions, including any minimum holding period, must be confirmed against the regulation text before this feature is built (task T-TAX in §12). Until then the tax treatment is a config switch, and the default is the conservative 10%.*
6. **Market mechanics.**
   - A lot is 100 shares, and regular-market orders must be in whole lots.
   - Settlement is T+2.
   - Trading hours changed on 15 Dec 2025 (Kep-00003/BEI/04-2025): Session I 09:00–12:00 WIB Monday to Thursday, with a shorter Friday session; Session II 13:30–15:49:59; pre-closing auction 15:50–15:59:59.
   - The auto-rejection bands (ARA/ARB) are **under revision**. The proposed bands are 35% for stocks at Rp 10–200, 25% for Rp 200–5,000 and 20% above Rp 5,000, with no implementation date yet.
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
│                                # holidays.toml, lq45_membership.csv, exclusions.csv
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
    def dividend_tax(self, gross: Money, reinvested_by_deadline: bool, on: date) -> Money: ...
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
   - a price or volume is non-positive or malformed.

   Good cached data is never overwritten by data that fails validation.
2. **Corporate actions.**
   - A **split** or **reverse split** adjusts the share count and the average cost of the position.
   - Holding a stock on the day before its **ex-date** creates a dividend **entitlement**.
   - On the **pay date**, cash net of dividend tax is credited as *dividend cash*, tagged with its reinvestment deadline.
   - Yahoo gives ex-dates, not pay dates, so the pay date is `ex_date + pay_lag_trading_days`. The default lag is a config value, and a per-stock override file (`dividend_pay_dates.csv`) wins when a row exists for that stock.
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
- Costs: broker fee (configurable per broker, and different for buys and sells), exchange levy, and the 0.1% sell tax, all from `fees.toml` with effective dates.
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

- **`CompoundingSizer` (default):** position sizes are computed from **current** portfolio value, meaning settled cash plus holdings at the last close, times the target weights. Gains and reinvested dividends increase future sizes automatically. This is the "start small, reinvest profits" behaviour.
- **Top-ups:** `monthly_contribution` in config adds cash on the first trading day of each month, in backtest and paper modes. It is optional and defaults to 0.
- **Reinvestment:** dividend cash is spent on the next day's targets. Its deadline tag means income reports can show how much dividend cash still needs reinvesting for the tax exemption (once T-TAX confirms the rule).

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

- `tick_sizes.toml`: the IDX price-tier tick table. **Implementation must source the current table from an IDX primary document** (task T-RULES). Boundary tests are written against that source, not against memory.
- `auto_reject.toml`: ARA/ARB bands by price tier, with **effective-from dates**. The current bands and the proposed revision (§3.6) are both entered once their dates are confirmed from IDX primary sources (T-RULES).
- `fees.toml`: broker fee (buy/sell), levy and sell tax, as named broker presets plus `custom`. The defaults are marked "check against your broker's fee schedule".
- `holidays.toml`: IDX non-trading days by year. `calendar.py` refuses to run for a year that has no holiday data, instead of assuming no holidays.
- `sessions.toml`: trading sessions with effective dates, used for scheduling and reports.

When a rule changes, the change is a data-file edit with a new effective date. Backtests over past dates keep using the rules that applied on those dates.

### 9.2 Yahoo data source

- `yfinance` is pinned to an exact version, and Dependabot proposes upgrades.
- It fetches unadjusted OHLCV plus dividends and splits.
- Retries use exponential backoff: 3 attempts, then `DataUnavailableError` (fail closed).
- It is rate-limited and polite, and fetches only what the cache is missing.
- A scheduled CI workflow (daily, and not a PR gate) fetches a small fixed set of tickers and checks the response shape. On failure it opens a GitHub issue, so a Yahoo format change is noticed before it can break a user's run.

### 9.3 Cache and state

- `cache.py`: SQLite holding bars and actions, keyed by (ticker, date). Validated rows only (§5 step 1).
- `state.py`: SQLite holding paper portfolio, queued orders, fills, entitlements, dividend ledger, halts, run log (unique per trading date), and the audit log.
- Schema migrations are versioned, applied in order and tested. Both files sit in the user's data directory, outside the repo, and are git-ignored.

### 9.4 Universe and survivorship bias

- `lq45_membership.csv`: (ticker, from_date, to_date), taken from IDX's semi-annual LQ45 constituent announcements.
- Historical coverage is best-effort. **A backtest whose period starts before the earliest membership date the file covers prints a survivorship-bias warning** in its report and output.
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

[tax]
dividend_reinvestment_exemption = false   # enable only after T-TAX confirms the rule
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

The README, every strategy guide, `init` and every report footer carry the disclaimer: *steadyhand is example software you run yourself; it is not financial advice; you can lose money.* The disclaimer is written once in a shared constant and tested for presence (§10.1).

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
| T-TAX | Confirm the PP 9/2021 dividend-reinvestment exemption conditions (deadline, holding period, qualifying investments) from the regulation text | enabling `dividend_reinvestment_exemption`; default stays 10% |
| T-RULES | Source the current IDX tick table, current ARA/ARB bands, the revision's effective date, and the 2026–2027 holiday calendar from IDX primary documents | `rules.py` data files and their boundary tests |
| T-LQ45 | Assemble dated LQ45 membership from IDX announcements as far back as available | survivorship coverage of backtests |
| T-PAY | Decide the default dividend pay-lag from a sample of real IDX dividend announcements | pay-date modelling default |
| OP-1 | Operator: set up trusted publishers on PyPI and TestPyPI for `steadyhand` and `steadyhand-idx` | first publish |
| OP-2 | Operator: approve creating the public GitHub repo and board on `ShydenMcM` | repo creation |
| OP-3 | Operator (optional, parallel): ask brokers whether an official or institutional API programme exists | only future IDX automation |

## 13. Implementation milestones (one plan each)

1. **M1 Foundations:** repo, CI, meta-guards, supply chain, `money`, `types`, `portfolio`, `MarketRules`/`DataSource`/`Broker` protocols.
2. **M2 IDX rules and data:** `rules.py` and data files (after T-RULES), calendar, Yahoo source, cache, fixtures.
3. **M3 Engine and backtester:** `run_day`, SimulatedBroker, RiskManager, CompoundingSizer, corporate actions, metrics, golden tests, performance test.
4. **M4 Income:** dividend ledger, income goal tracker, projection, calendar.
5. **M5 Paper trading and CLI:** state DB, idempotency and atomicity, halts and resume, all CLI commands, CLI journeys.
6. **M6–M9 Strategy waves 1–4**, each with its guides.
7. **M10 First release:** docs, TestPyPI → PyPI.

## 14. Acceptance criteria for sub-project A

1. `steadyhand-idx init` then `backtest --from 2016-01-01 --to 2025-12-31 --strategy dividend-growth` completes against real Yahoo data (a manual live acceptance run; CI runs the same journey on recorded fixtures) and prints return, drawdown, costs, dividend and income-goal metrics next to the buy-and-hold baseline.
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
- Trading hours 2026: https://bidiknews.co.id/jadwal-perdagangan-bursa-efek-indonesia-2026-lengkap-untuk-investor-dan-trader-saham/
- ARA/ARB and Special Monitoring Board revision: https://www.idnfinancials.com/news/65578/idx-to-revise-special-monitoring-board-and-auto-rejection-rules ; https://www.abnrlaw.com/news/indonesia-stock-exchange-revisits-equity-trading-rules
- T+2 settlement: https://www.idx.co.id/en/news/tplus2-settlement/
- SID/RDN: https://help.bions.id/docs/apa-itu-sid-rdn-sre-dan-kartu-akses/
- Broker APIs: IPOT in-app robo trading (indopremier.com), unofficial community bots (github.com/mascahyo1/trading-bot)
- Yahoo data terms: https://scrapfly.io/blog/posts/guide-to-yahoo-finance-api
- IBKR availability in Indonesia: https://brokerchooser.com/broker-reviews/interactive-brokers-review/interactive-brokers-indonesia

**Unverified (to confirm before relying on):** whether each broker's terms explicitly ban automation; IDX coverage and pricing from EODHD, Twelve Data and Polygon; IDX official data pricing; direct eligibility for Alpaca and Saxo; whether IBKR covers IDX; tax treatment of foreign-regulated accounts; the PP 9/2021 exemption conditions (T-TAX).

## Appendix B: Spec review log

(Review passes are recorded below. The loop ends on a pass with zero findings.)

- **Pass 1 (2026-09-24):** placeholder scan found 0. Findings, all fixed: (1) engine dependency rule didn't separate runtime from dev deps; (2) the performance-test data source was ambiguous; (3) AC1 needed live data with no CI equivalent; (4) "uncut dividends" was undefined; (5–7) top-N defaults were unspecified for high-yield, momentum-rotation and low-volatility; (8–9) Dependabot ecosystem was ambiguous ("uv (or pip)").
- **Pass 2 (2026-09-24):** 1 finding, fixed: §8 still referred to "N" after pass 1 removed it.
- **Pass 3 (2026-09-24):** mechanical checks: placeholders 0; leftover `top-N`/`pip` ambiguity 0; every §12 ID referenced in the body exists in §12 (T-TAX, T-RULES, T-LQ45, T-PAY, OP-1..3); every milestone in §13 maps to spec sections; the 11 strategies in §8 match AC2's count. Full read: **0 findings. Loop closed.**
