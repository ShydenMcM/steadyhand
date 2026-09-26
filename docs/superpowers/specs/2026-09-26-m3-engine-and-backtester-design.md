# steadyhand M3: Engine and Backtester

**Status:** approved by Shyden on 2026-09-26, after the design was approved in conversation and the review loop closed on pass 3.
**Parent spec:** `2026-09-24-steadyhand-core-design.md` (the "core spec"). M3 is its milestone 3 (§13). Everything the core spec already settles still holds. This document adds the decisions M3 needs and says where it narrows or moves scope.
**Inputs:** the M2 plan's "Carried forward to later plans" section (`docs/superpowers/plans/2026-09-25-m2-idx-rules-and-data.md`, line 7015) and Shyden's answers of 2026-09-26 (§2).

## 1. What M3 delivers

A market-neutral daily engine and a backtester built on it, in the `steadyhand` package, plus the IDX pieces that plug into them:

- `run_day`: one trading day, from yesterday's state to today's state (core spec §5).
- The simulated fill, the `CompoundingSizer` and the `RiskManager` (core spec §5.1, §6).
- Corporate actions: splits, dividend entitlements and payments, and freezes.
- `MarketView` with `LookAheadError`, the `Strategy` protocol, and one strategy, `buy-and-hold`.
- `backtest`: runs a strategy and the `buy-and-hold` baseline over a date range, and reports metrics for both.
- A golden backtest on recorded real Yahoo data, a look-ahead truncation test, and a performance test.

### 1.1 Scope moved or narrowed

| Item | Core spec | M3 decision | Why |
|---|---|---|---|
| `buy-and-hold` | M6 (wave 1) | **M3** | The golden test and every baseline comparison need it. |
| `dividend-growth` golden test | M3 (§10.3) | **M6** | The strategy is built in M6. The golden harness M3 builds takes it then. |
| Income goal tracker, projection | M4 | M4 (unchanged) | M3 reports dividends as cash totals only. |
| SQLite state, idempotency on disk, halts across restarts, `resume`, audit log file, CLI | M5 | M5 (unchanged) | M3's state is an in-memory value. M5 saves it. |
| `dividend_pay_dates.csv` override | §5 step 2 | **M5** | The file is configuration. M3 uses the pay lag alone. |
| Price history before the backtest's start | not stated | **M6** | Only strategies with a look-back window need it; `buy-and-hold` does not. |

### 1.2 Delivery: one spec, two plans

M2's single plan ran to 7,000 lines, and M3 is larger. M3 is therefore planned and delivered as **M3a** (the engine day, §4–§6) and **M3b** (the backtester, metrics and tests, §7–§9), each with its own plan reviewed to zero, one branch and one PR per story, and every story on the board with full acceptance criteria before any code.

## 2. Shyden's decisions (2026-09-26)

1. **Architecture: a pure core.** `run_day` takes the previous state and the day's inputs and returns a new state and a report. Nothing is changed in place. This matches M1's `Portfolio`, which is already immutable.
2. **Rights issues: skip refused days.** On a day the data source refuses for a stock (a rights-issue day Yahoo cannot recover), that stock cannot be traded. It stays out of the tradable set until its prices are clean again, and a warning names the stock and the days. A position already held is frozen and valued at its last clean close.
3. **A start before the LQ45 file: refuse.** If the universe does not cover the start date, the backtest stops before day one with an error naming the first date the universe covers. Nothing is guessed.
4. **Kill switches in a backtest: halt for the rest of the run.** After a halt no orders are queued, holdings are kept, dividends still arrive, and the result records the halt's date and cause.

## 3. Architecture

### 3.1 The pure core

```
EngineState(day n-1) + DayInputs(day n) --run_day--> EngineState(day n) + DayReport(day n)
```

- **`EngineState`** (frozen): the `Portfolio`, pending orders, dividend entitlements awaiting payment, frozen instruments with their reasons, the halt (date and cause) or none, the time-weighted unit value and its high-water mark, the last close of every held stock, and the last day run.
- **`DayInputs`**: the day, today's bars, corporate actions with today's ex-date, the tradable set (§6.4), and a `MarketView` over the bars up to today.
- **`DayReport`**: fills; rejections and cuts, each with a reason; orders queued; dividends entitled and paid; tax and daily costs booked; freezes and halts; cash settled and unsettled; holdings value; warnings.
- `backtest` repeats `run_day` over the trading days. M5 will save each new state in one SQLite transaction, which gives "a crash leaves yesterday's state" and "a second run is a no-op" without extra machinery.

Rejected alternatives: a stateful `Engine` object whose parts change shared state in place (atomicity and idempotency then need their own machinery), and an event bus (overbuilt for a once-a-day loop).

### 3.2 Modules (engine package, standard library only)

Following core spec §4.1:

| Module | Contents |
|---|---|
| `engine.py` | `EngineState`, `DayInputs`, `DayReport`, `run_day`, `DataValidationError` |
| `broker/simulated.py` | `SimulatedBroker`: the next-open fill model (§5) |
| `sizing.py` | `Sizer` protocol, `CompoundingSizer` |
| `risk.py` | `RiskLimits`, `RiskManager`, `Halt` |
| `corporate.py` | splits, entitlements, payments, freezes (§4) |
| `view.py` | `MarketView`, `LookAheadError` |
| `universe.py` | the `Universe` protocol (§7.2) |
| `strategies/` | `Strategy` protocol, `buy_and_hold.py`, and the guide `docs/strategies/buy-and-hold.md` |
| `backtest.py` | `backtest`, `BacktestSettings`, `BacktestResult` |
| `metrics.py` | the metrics of §8 |

`data.py` gains `UnavailableDaysError` (§7.3). `portfolio.py` gains the movements and operations of §3.3. The `Broker` protocol stays for M5's manual "Confirm Fill" broker. The pure core does not call it, and its docstring's "the simulated broker arrives in M3" is corrected to say so.

### 3.3 Portfolio additions

`MovementKind` gains `DIVIDEND`, `TAX` and `DAILY_COST`. `Portfolio` gains:

- `apply_split(instrument, old_shares, new_shares, on)`: scales the quantity and keeps the total cost basis. A fractional share left by the ratio is dropped and reported as a warning (cash in lieu is not modelled).
- `credit_dividend(gross, on)` and `charge(kind, amount, on)`: settled on the day booked. Dividend cash is spendable from the next decision.

## 4. Corporate actions (in `run_day`, before fills)

1. **Split or reverse split** with today's ex-date: `apply_split` on the position, and the stored last close is scaled by `old_shares / new_shares`, rounded down, so a day without a bar never values post-split shares at a pre-split price. Pending orders for that stock are cancelled with the reason "split on ex-date", because their quantities predate the split. The strategy decides again today.
2. **Cash dividend** with today's ex-date: holding the stock at the previous close creates an entitlement of `quantity × per_share`, rounded down to a whole rupiah. The pay date is the ex-date plus `pay_lag_trading_days` (default **14**, core spec §5 step 2), counted with `rules.is_trading_day`. A stock bought at today's open has no entitlement.
3. **Pay date reached:** the gross amount is credited, and `rules.dividend_tax(gross, reinvested_by_deadline=False, on=pay_date)` is booked as `TAX` (M4 reshapes this call, core spec §6.2).
4. **Any other action** (`OtherAction`) on a held stock freezes it for the rest of the run, with the action's description as the reason. The Yahoo source never reports one (M2 carried-forward), so this path is exercised by the engine's own tests and by future distributions.

## 5. Simulated fills (`SimulatedBroker`)

At today's open, for each order queued yesterday, in the order: all sells, then all buys.

1. **Rejected** if the stock is frozen, has no bar today or traded zero volume.
2. **Price:** the open × (1 + slippage) for a buy, rounded up to a whole rupiah; × (1 − slippage) for a sell, rounded down. Then `rules.round_to_tick` against the trader. Slippage defaults to **0.10%**. The order is **rejected** if that price is outside `rules.price_band(instrument, previous close, day)`.
3. **Volume cap:** the quantity is cut to **10%** of today's volume (configurable), rounded down to whole lots, and the cut is reported. Zero lots means rejected.
4. **Cash:** a buy whose total cost exceeds settled cash (which includes every dividend already paid) is cut to the lots affordable, or rejected if none are. Sale proceeds settle on `rules.settlement_date(day)` (T+2).
5. **Costs:** `rules.costs(side, gross, day)` per fill. After all fills, `rules.daily_costs(buys + sells, day)` once, booked as `DAILY_COST` (stamp duty; M2 carried-forward).

## 6. Deciding, sizing and risk

### 6.1 Decide

The strategy receives the `MarketView` and a read-only view of the portfolio, and returns target weights. `MarketView` exposes bars dated on or before today only. Any later date raises `LookAheadError`. Weights must be non-negative and sum to at most 1; otherwise `run_day` raises, because that is a strategy bug.

### 6.2 Size (`CompoundingSizer`)

Portfolio value is all cash (settled and unsettled) plus holdings at the last close (core spec §6.2). For each stock the target value is weight × portfolio value, and the difference from the current value is turned into whole lots at the last close, **rounded down**. Buys are then limited to settled cash, which includes dividends already paid. Sells come first in the queue.

### 6.3 Risk (`RiskManager`)

Every limit comes from `RiskLimits`, with the core spec §6.1 defaults: cash only; **10%** maximum weight per stock (a buy is cut to the cap); a **1 lot** minimum; excluded stocks never bought; a daily loss limit of **5%**; and a drawdown kill switch at **25%** below the high-water mark. Every dropped or cut order carries a reason.

- **Measured on a time-weighted unit value**, like a fund's price per unit. A top-up buys units at today's value, so a deposit never looks like a gain and never hides a loss. The daily loss and the drawdown are both read from this unit value.
- **A halt** is checked after today's valuation. On a halt no orders are queued today, and none are queued on any later day of the run (decision 4). Holdings, dividends and settlement carry on.

### 6.4 The tradable set

- **Buyable:** universe members on the day, minus exclusions, frozen stocks, stocks on a refused day (§7.3) and stocks with no bar today.
- **Sellable:** held stocks, minus frozen stocks, stocks on a refused day and stocks with no bar today. A held stock that has left the universe can still be sold.
- "Outside the tradable set" means a stock that is in neither list.
- A held stock that becomes excluded is frozen and flagged (core spec §6.1). Every held stock is valued every day, including frozen ones. The strategy may target any stock, but only buyable stocks are bought and only sellable ones are sold. Anything else is dropped with its reason.

### 6.5 Top-ups

`monthly_contribution` (default 0) is deposited on the first trading day of each month, before the decision.

### 6.6 `buy-and-hold`

The baseline (core spec §8, strategy 1). On its first day it fixes its set: the buyable stocks that day. It never sells. Each day it targets every held stock at its current weight, so nothing is traded against it, and it splits the spendable cash equally across every stock in its set that is buyable today. Dividends and top-ups are therefore reinvested equally across the set. A stock in the set that leaves the universe is still held. Its guide `docs/strategies/buy-and-hold.md` has the six sections of core spec §8, and the §10.1 guard that fails on a registered strategy without a complete guide arrives with it.

## 7. The backtester

### 7.1 `backtest(strategy, start, end, universe, source, rules, settings) -> BacktestResult`

Before day one, in this order, each failure stopping the run with a named error and no result:

1. `rules.require_supported(start)`: the error names the rule table (M2 carried-forward). For IDX that is 2021-01-01 or later.
2. The universe covers `start`, otherwise an error names the first date it covers (decision 3).
3. Bars and corporate actions are fetched for the whole window for every instrument that `members_on` returns on any trading day in it. Refused days are handled by §7.3; any other `DataUnavailableError` stops the run.

It then runs `run_day` for each trading day, runs `buy-and-hold` the same way with identical settings (unless the strategy *is* `buy-and-hold`), and returns both runs' daily reports, final states, warnings, halts and metrics.

### 7.2 The `Universe` protocol

`members_on(day) -> frozenset[Instrument]`, `excluded_on(day) -> Mapping[Instrument, str]` (reason), and `first_day() -> date`. `steadyhand-idx` adapts `Lq45Membership` and `Exclusions` to it. Because the backtest refuses a start before the first list, `Lq45Membership.survivorship_warnings` loses its "starts before the first list" branch and its test; the gap warnings stay.

### 7.3 Refused days (decision 2)

`data.py` gains `UnavailableDaysError(DataUnavailableError)` carrying `days`. The IDX `UnrecoverablePricesError` becomes a subclass of it. The backtester catches it, records the days, and fetches the clean ranges around them. On a refused day the stock is outside the tradable set. If held, it is frozen and valued at its last clean close. The first clean day after a refused span is treated like a stock's first day in §7.4. The last clean close can be months old and predates the rights issue, so the band around it says nothing about that day. The result carries one warning per stock naming its refused days.

### 7.4 Data validation

A non-positive price, a negative or non-integer volume, a wrong currency and a high or low that fails to bracket the open and close are already refused when M1's `Bar` is built, so no bar that reaches `run_day` carries one. Each day, before anything trades, `run_day` raises `DataValidationError` naming the stock, the day and the check if:

- the close lies outside `rules.price_band(instrument, previous close, day)`. This is skipped on a stock's first day in the window, the first day after refused days, and a split's ex-date (M2 carried-forward, scope decision 7).

A backtest stops on the error (M5 maps it to exit code 3). **Missing bars are handled differently in a backtest than in paper mode.** In paper mode, a held stock with no bar means Yahoo has not published yet, so the run stops (M5). Over history, a trading day with no bar is a fact about the past, for example a suspension. The stock is then outside the tradable set for that day, valued at its last close, and a warning names the day.

## 8. Metrics (`metrics.py`)

For each run: final value; total deposited; time-weighted total return; compound annual return over the run's calendar days; maximum drawdown with its peak and trough dates; costs split into commission (`fee`), levy, sale tax and daily costs (stamp duty); turnover per year ((gross bought + gross sold) ÷ 2 ÷ the average daily portfolio value, scaled to 365 calendar days); dividends gross, tax and net; and the final trailing 12-month net dividend income. The strategy's trailing 12-month dividend income is shown against the baseline's (core spec §7). Money stays integer rupiah. Ratios are `Decimal`, computed with `Decimal.ln` and `Decimal.exp` where a power is needed, never `float`.

## 9. Testing

The core spec's §10 applies in full. For M3:

- **Unit and property tests** (hypothesis): cash never goes negative; every quantity is a whole number of lots; every fill price is a valid tick inside the band; a buy moves cash by exactly minus (gross plus that fill's costs) and a sell by gross minus its costs; daily costs are booked once on each day with trades and never on a day without; a deposit leaves the unit value unchanged; splits keep the total cost basis.
- **Look-ahead:** `buy-and-hold` runs under a `MarketView` that raises on any later date, and the truncation check (running to D and to D+k gives identical decisions up to D) holds.
- **Golden backtest:** newly recorded real Yahoo fixtures for about five LQ45 stocks over about a year, chosen so that the window holds at least one cash dividend and one split. A small membership file in the real format lists them. `buy-and-hold` must reproduce the stored results exactly, in integer rupiah. `RiskLimits` in the golden settings allow 25% per stock so five stocks can be fully invested. Any change to the stored numbers comes with a reviewed update.
- **Performance:** 10 years of synthetic prices for 45 stocks (a fixed seed, generated in the test) finish in **under 30 seconds** on a GitHub-hosted runner, with a recorded baseline. IDX rule data does not cover 10 years ahead, so this test runs against a small fixed-rules `MarketRules` written for the test. That also proves the engine runs with a market other than IDX.
- **Mutation-verified:** every plan task lists the mutations that must turn its suite red, as M2's did.
- **Meta-guard fix:** `tests/meta/test_disclaimer.py` checks READMEs only, so `docs/lq45-members.md`'s disclaimer is not machine-checked. M3a's first story extends the guard to every user-facing doc under `docs/` (excluding `docs/superpowers/` and `docs/research/`).

## 10. Stories

**M3a, the engine day:** (1) engine additions: `Universe`, `UnavailableDaysError` and the Yahoo subclass, `Portfolio` movements and operations, the disclaimer guard; (2) `MarketView`, `LookAheadError`, the `Strategy` protocol, `buy-and-hold`, its guide and the §10.1 guide guard; (3) `SimulatedBroker`; (4) `CompoundingSizer`, `RiskManager` and the unit value; (5) corporate actions; (6) `run_day` with validation.

**M3b, the backtester:** (7) `backtest` with pre-flight, refused days, halts and the baseline, plus the `survivorship_warnings` change; (8) metrics; (9) golden fixtures, the golden test and the truncation test; (10) the performance test.

The plans fix exact signatures, test counts and mutations.

## 11. Risks

- **Rights-issue detection finds non-whole-rupiah days only.** An unpublished factor that happens to give whole rupiah on some day passes undetected. M2 measured four affected stocks in 2021–2025. The AC1 live run (M5) is the check on real data.
- **Real history may fail the band check.** If the AC1 live run hits a close outside the band that the data cannot explain, it stops with a named error, and the fix is a decision then, not a silent skip.
- **Excluding BBRI through 2021-09-07** understates 2021 dividend income. That is the cautious direction, as decided.

## Spec review log

(Passes are recorded below. The loop ends on a pass with zero findings.)

- **Pass 1 (2026-09-26):** mechanical, then a full read. Every signature, field and default cited was checked against the code on `develop` (`market.py`, `data.py`, `types.py`, `portfolio.py`, `universe.py`, `yahoo.py`) and against the core spec (§4.1, §5, §6, §8, §10, §13, §14). Placeholder scan clean. Eight findings, all fixed: (1) validation listed malformed prices that `Bar` already refuses at construction; (2) "settled cash plus dividend cash" named two pools where `Portfolio` has one; (3) the tradable set did not say what may be sold, or what happens to a held stock that leaves the universe or is excluded; (4) `buy-and-hold`'s behaviour was not specified, nor was the §10.1 guide guard that must arrive with the first registered strategy; (5) the fetch did not say which instruments are fetched; (6) the reason given for skipping the band check after refused days was an unverified claim about the exchange, and is now one about the data; (7) "excluding BBRI until 2021-09-08" was ambiguous about the boundary; (8) the property "costs never understate `rules.costs`" compared the code with itself, a tautology, and is now a cash-movement identity. "Outside the tradable set" is now defined.
- **Pass 2 (2026-09-26):** a full read of the revised document. Four findings, all fixed: (1) §5 rejected an order on its fill price before step 2 had computed that price; (2) a split rescaled the position but not the stored last close, so a split ex-date with no bar would value post-split shares at the pre-split price; (3) turnover's formula was ambiguous about its denominator and its annualisation; (4) story 2 did not carry the §10.1 guide guard that §6.6 says arrives with `buy-and-hold`.
- **Pass 3 (2026-09-26):** read every line pass 2 changed (§4 step 1, §5 steps 1 and 2, §8's turnover, §10's story 2) against the sections they touch (§3.3, §6.4, §6.6, §7.4). **0 findings. Loop closed.**
