# steadyhand M6: Strategy wave 1

**Status:** design approved by Shyden in conversation on 2026-09-30, in three parts, after six decisions (§2). One of them replaced part of an approved design once a measurement contradicted it (§3). The review loop closed on pass 6. The written spec was approved by Shyden on 2026-09-30, including five details the design parts had not shown (listed to him one by one: the instalment sized from cash, a refused look-back as a warning, a suspended passer kept, the new keys optional, the settings mechanism in S1).
**Parent spec:** `2026-09-24-steadyhand-core-design.md` (the "core spec"): §4.3 (strategies return weights), §8 (the strategy library, wave 1), §10.1 (guides), §13 item 6 and §14 AC1, AC2 and AC6. M6 also builds what earlier specs left to it: the `dividend-growth` golden test (M3 spec, scope table), a look-back before a run's first day (M3 spec, scope table: "price history before the backtest's start", moved to M6; M6 builds it for corporate actions and moves bars on to M7, SD4), and course module 8's first lessons (training spec, module table).

## 1. What M6 delivers

Wave 1 is `buy-and-hold`, `monthly-savings` and `dividend-growth` (core §8). `buy-and-hold` was built in M3 as the baseline. M6 adds the other two, the engine support `dividend-growth` needs to see dividend history, strategy settings in `steadyhand.toml`, and the guides and lessons. `dividend-growth` becomes the default strategy, as core §8 says.

### 1.1 Out of scope

- **A look-back for price bars.** Wave 2's `ma-trend` (200-day average) is the first strategy that needs bars from before a run's first day, so M7 builds it. M6 looks back for corporate actions only.
- **Published pay dates.** Pay dates stay modelled: ex-date plus the engine's payout lag (core §5 step 2). Yahoo gives no pay dates.
- **Strategies from later waves**, and the deferred point-in-time value strategy (core §8).

## 2. Shyden's decisions (2026-09-30)

Each was asked with its reasoning and options; the recommended option was chosen every time.

1. **`monthly-savings` drip-feeds the starting capital** over a number of monthly instalments, so `compare` shows investing a lump sum (`buy-and-hold`) against spreading it out. Rejected: buying the current universe monthly with everything invested on day one (its rows would look almost like `buy-and-hold`'s), and a separate monthly amount of its own (it duplicates `monthly_contribution_idr`).
2. **When too few stocks qualify, `dividend-growth` holds the ones that do and keeps the rest as cash.** It never relaxes its own rule and never concentrates into a few stocks.
3. **The spread of pay months decides *which* stocks are held, not their weights.** Weights stay equal. Recorded as scope decision SD2.
4. **`dividend-growth` reviews once a year**, on its first day of each calendar year and on a run's first day, since its test can only change when a calendar year closes.
5. **Dividend history reaches a strategy through `MarketView`**, under the same look-ahead guard as prices, and each strategy declares how many years of history before a run it needs.
6. **The pass test is "paid every year, and grew over five years"** (§3). This replaced the strict "never fell" test of the approved part 2 after the measurement in §3 showed it passes almost nothing on IDX.

The three design parts (`monthly-savings`, `dividend-growth`, engine and deliverables) were then approved as shown; §5, §6 and §4 carry them, with decision 6 applied to §6.

## 3. Measurement: how many LQ45 stocks pass

Core §8 promises 15–25 stocks. Before writing the rule down, it was measured on 2026-09-30:

- **Lists.** The LQ45 in force for a review on the first trading day of January 2021 (the *IDX Company Fact Sheet LQ45* booklet for August 2020 – January 2021, Internet Archive capture `20260712195632`) and for a review on 3 February 2025, the list's first day (the booklet for February – July 2025, capture `20260712201348`), as `docs/research/t-lq45.md` §3 cites them. Both read as 45 distinct codes. In the 2020 booklet, `BTPN` appears only inside a company name ("Bank BTPN Syariah Tbk."), so it was dropped as a false match.
- **Dividends.** Yahoo, through `yfinance` 1.7.0, summed per calendar year of ex-date. `SRIL` (in the 2020 list, since delisted) returned HTTP 404 and counts as not passing.
- **Counts** (every rule also requires a dividend in each of the six calendar years before the review):

  | Rule | Jan 2021 | Feb 2025 |
  |---|---|---|
  | Never lower than the year before (the approved part 2) | 4 | 1 |
  | Each year may fall at most 10% | 6 | 3 |
  | Each year may fall at most 20% | 8 | 8 |
  | **Last year's total at least the total five years earlier** | **19** | **20** |
  | That, and no single fall over 25% | 10 | 7 |
  | Paid every year, no growth test | 28 | 25 |

- **Why the strict rule fails here.** IDX dividends are cyclical: the banks cut in 2020–21, the coal payers follow coal prices, and UNVR has paid less every year since 2019. Summing by calendar year also creates false cuts: ICBP and INDF each paid an extra interim in November 2018, so 2019 looks like a fall. Comparing only the two ends of the window is immune to that.
- **What the chosen rule admits.** Cyclical payers whose dividends grew across the window, such as ADRO, PTBA, ITMG, UNTR and ANTM in 2025. The guide says so (§7).
- **Caveat.** Two review dates and one data source. The golden test (§9.3) and the CLI journey pin the rule's behaviour, not these counts.

## 4. Engine changes

### 4.1 Dividend history in `MarketView`

- **`ActionHistory`** (new, beside `PriceHistory` in `view.py`) holds every corporate action a run loaded, including the look-back years (§4.3). `DayInputs` gains `past_actions: ActionHistory`. Its `actions` field (today's ex-dates, which the engine applies) is unchanged.
- **`MarketView.dividends(instrument) -> tuple[PastDividend, ...]`** returns that stock's cash dividends with an ex-date on or before today, oldest first. `PastDividend` has `ex_date` and `per_share`, which is **adjusted for every split with an ex-date after the dividend's and on or before today**. A 1-for-5 split later turns a Rp 100 dividend into Rp 500 a share, so years stay comparable. Nothing with an ex-date after today is ever returned.
- **`MarketView.pay_date(ex_date) -> date`** is the modelled pay date, `add_trading_days(rules, ex_date, pay_lag_trading_days)`: the same function the engine and the income calendar use (M4 spec §3.1), so the three cannot disagree. It takes an ex-date on or before today, and a later one raises `LookAheadError`, as a later bar does. `MarketView` gains the rules and the lag for this. The holiday calendar starts on 2016-01-01, so an earlier ex-date raises the rules' own unsupported-date error. `dividend-growth` asks only about last year's dividends (§6), which is 2020 at the earliest.
- **`MarketView.history_complete(instrument) -> bool`** is false when the source refused any part of that stock's look-back (§4.3).

### 4.2 `Tradable.members`

`Tradable` gains `members: frozenset[Instrument]`, the universe on its day. Today a stock that is not buyable is either kept out for a reason (frozen, excluded, refused, no bar) or simply not a member, and a strategy cannot tell a stock that has left the LQ45 from one suspended today. `members` must include every stock in `buyable`; `__post_init__` checks it.

### 4.3 The look-back

- **`Registered` gains `settings`** (§4.5) and **`lookback_years(values) -> int`**, the calendar years of corporate actions the strategy needs before a run's first day. It is 0 for `buy-and-hold` and `monthly-savings`, and `growth_years + 1` for `dividend-growth` (6 by default).
- **`backtest`, `compare` and `paper run`** fetch corporate actions from 1 January of (the first day's year minus the look-back) for every stock the universe holds on any day of the run. Bars are still fetched from the first day. The CLI's `compare` passes the largest look-back among its strategies. Trading still starts on the first day, and `rules.require_supported(start)` is unchanged: the look-back is read-only history, never traded.
- **One fetch path.** Both backtests and `paper run` (through `day_inputs`) build their inputs in `backtest._fetch`, so the look-back is added there. The look-back's actions are fetched in a separate call from the run's own range, because `_fetch` re-raises an `UnavailableDaysError` whose days all fall outside the run (`backtest.py`, the `if not named: raise`), and a refusal in the look-back must not stop the run.
- **Dividends on days whose prices carry an adjustment Yahoo does not report** (#160 spec §5): the look-back reads a dividend in a run the tick grid proves restored by that run's factor, where it read Yahoo's scaled amount unchanged, and a dividend in an unproven run is refused with `UnavailableDaysError` naming its ex-date, which is a refused look-back as below.
- **A refused look-back** marks the stock incomplete (`history_complete` is false) and adds one warning with the new key `data.dividends.history_refused` to the run's data warnings, naming the stock and the refused range. `dividend-growth` treats an incomplete stock as not passing. The run does not stop: the missing data is history, and the stock can still be traded on its own merits by other strategies.
- **`paper run`** builds its inputs with the public `day_inputs` over the whole range from the account's opening day (M5 spec §6.2), so its look-back starts from 1 January of (the opening day's year minus the look-back), through the cache like everything else. After a `paper switch` to a strategy with a longer look-back, the next `paper run` fetches the longer range.
- **The engine's entry points** `backtest`, `compare` and `day_inputs` gain `lookback_years: int = 0`. The CLI passes the registered strategy's value, so the engine never reads the registry, and S1 can test the look-back before any strategy needs one.

### 4.4 Notes from a strategy

`Decision` gains `notes: tuple[Note, ...] = ()`, each checked to be a `Note` in `__post_init__`. The engine appends them to that day's `DayReport.notes`, after its own. Every key is a constant in `steadyhand.notes` (`tests/meta/test_note_keys.py`). M6 adds `strategy.too_few_qualified` (§6).

### 4.5 Strategy settings in `steadyhand.toml`

- **`Registered.settings`** is a tuple of `Setting(name, default, minimum, maximum, help)`, all integers in wave 1. `make(values)` builds the strategy from a mapping of every setting's value. `lookback_years` takes the same mapping.
- **The keys are flat, in `[strategy]`**, beside `name`: `instalments`, `min_stocks`, `max_stocks`, `growth_years`. Every registered strategy's keys are read and checked whether or not it is the chosen one, so a mistake is found before anyone switches to it. `init` writes every key with its one-line `help` as the comment, as it writes every other key. A setting name may belong to only one strategy (a test checks the registry), so a flat table cannot become ambiguous.
- **Optional keys.** A missing strategy key takes its default, so a `steadyhand.toml` written before M6 still loads. (Today's `get_int` refuses a missing key, so these keys are read through an optional path.)
- **Cross-field check:** `max_stocks` must be at least `min_stocks`. A breach, like any bad setting, is a `DataFileError`: exit code 2.
- **`paper run`'s audit line for a changed setting** (M5 spec §6.5) covers these keys like any other.
- **When a setting takes effect.** A strategy reads its settings each day it decides, except where §5 says otherwise.

## 5. `monthly-savings`

- **Setting:** `instalments`, default 12, from 1 to 120.
- **Its first day:** instalment = the spendable cash that day divided by `instalments`, rounded down to a whole rupiah. It remembers the instalment, and `instalments` as the number still due (`due`). It uses cash rather than portfolio value (the approved part 1 said value; on a fresh run the two are equal), so a `paper switch` onto a portfolio that already holds stocks never reserves money it does not have. Later changes to `instalments` do not change a run that has started; the guide says so.
- **Buying days:** the first day it decides in each calendar month, the run's first day included. It remembers the last month it bought in as `YYYY-MM`, so days skipped by a paper run do not matter.
- **What it spends:** all spendable cash, less the reserve, and never below zero. The reserve is (`due` − 1) × the instalment while `due` is above 0, and 0 after. Marking a month takes 1 from `due`, down to 0. Top-ups and dividends that arrived since the last buying day go in with the instalment. After the last instalment it spends all spendable cash each buying day.
- **Weights:** every holding keeps its current weight, and the spend is split equally across the stocks buyable that day, each adding `ratio_down(spend // n, value)` as `buy-and-hold` does (`view.tradable.buyable`, today's universe, so new LQ45 members are bought). It never sells, and a stock that leaves the LQ45 stays held.
- **No stock buyable:** it does not mark the month, so the next day tries again. The instalment count goes down only on a day it marks.
- **Memory:** `instalment` (whole rupiah), `due` (instalments still due) and `month` (`YYYY-MM`).
- `instalments = 1` is a lump sum with monthly reinvestment.

## 6. `dividend-growth`

- **Settings:** `min_stocks` 15 (1 to 45), `max_stocks` 25 (1 to 45, at least `min_stocks`), `growth_years` 5 (1 to 10).
- **Review days:** the first day it decides in each calendar year, and a run's first day. It remembers the year it last reviewed.
- **The test**, on a review day in year Y, with G = `growth_years`: the stock is a member (§4.2), its history is complete (§4.1), it paid a cash dividend in every calendar year from Y−G−1 to Y−1 (by ex-date, per share, split-adjusted to today), and its total for Y−1 is at least its total for Y−G−1.
- **Candidates:** members that pass and are buyable today, plus held members that pass (a passer suspended on review day is kept, not sold).
- **Picking:** if there are at most `max_stocks` candidates, all are held. Otherwise it picks one at a time, `max_stocks` times. A candidate's pay months are the calendar months of `view.pay_date(ex_date)` for its dividends with ex-date in Y−1. Each pick is the candidate with the lowest *coverage*: the fewest stocks already picked that pay in any one of its months (the minimum over its months). Ties go to the higher trailing yield (the split-adjusted dividends with an ex-date after today minus 365 days and on or before today, divided by the last close), then to market and symbol.
- **Weights on a review day:** each picked stock targets 1 / max(`min_stocks`, number picked), rounded down with `ratio_down` so the total never exceeds 1. Every other stock targets 0 and is sold if sellable. The risk manager's `max_weight` still applies.
- **Too few:** when fewer than `min_stocks` are picked, the decision carries a `strategy.too_few_qualified` note: "Only N stocks passed the dividend test; the rest is held as cash until more do." With none, it holds all cash.
- **Between reviews:** holdings keep their current weights. The spendable cash (dividends and top-ups) is split equally across the picked stocks buyable today, but no stock is taken above its review-day target. Whatever that leaves is held as cash.
- **Memory:** `set` (the picked stocks, written as `buy-and-hold` writes its set) and `year` (last reviewed).

## 7. The default, the guides and the lessons

- **The default** in `init`'s starter configuration becomes `dividend-growth` (core §8). Existing `steadyhand.toml` files are not rewritten.
- **Guides:** `guides/monthly-savings.md` and `guides/dividend-growth.md`, with the sections core §8 requires (`tests/meta/test_strategy_guides.py`). *Settings you can change* names every registered setting of that strategy, and a new guard checks it. `dividend-growth`'s *When it tends to do badly* and *Risks* say that the rule admits cyclical payers whose dividends swing, that a year of widespread cuts can leave most of the portfolio in cash, and that pay months are modelled. `monthly-savings`'s say that money waiting to be invested earns nothing in the model, and that spreading out is expected to trail a lump sum in a rising market.
- **Course module 8 (`strategies`)** gets three lessons, one per wave-1 strategy, each pointing at its guide rather than copying it (training spec, module table). Both new keys, `strategy.too_few_qualified` and `data.dividends.history_refused`, get a lesson, as every key must (`tests/meta/test_lessons.py`, `test_every_key_has_a_lesson`).

## 8. Errors

No new exit codes. A bad strategy setting is a configuration error (exit code 2). A refused look-back is a warning (§4.3), not a data stop. Data stops (exit code 3) keep M3's and M5's rules for the run's own days.

## 9. Testing

### 9.1 Unit and property tests

- **`ActionHistory` and the view:** nothing with a later ex-date is ever returned (a Hypothesis property over random actions and days); split adjustment of earlier dividends only; `pay_date` equals `add_trading_days` for the same inputs, and a later ex-date raises; `history_complete`.
- **The engine and the fetch:** `Tradable.members` refuses a buyable non-member; a strategy's notes reach `DayReport.notes` after the engine's own; the look-back fetches actions from the right 1 January and bars from the first day; a look-back refusal gives one `data.dividends.history_refused` warning and does not stop the run, while a refusal in the run's own days keeps M3's behaviour; the CLI's `compare` passes the largest look-back among its strategies.
- **`monthly-savings`:** the reserve is never spent before its month (a property over random months, top-ups and prices); it never sells; skipped days; no stock buyable; the last instalment; `instalments = 1`; a first day on a portfolio that already holds stocks sizes the instalment from cash.
- **`dividend-growth`:** the test at its boundaries (a year with no dividend, last total equal to the first, just below it, incomplete history, a non-member); picking by coverage then yield then symbol, on hand-built candidates whose correct answer is worked out by hand in the test; weights at 0, fewer than `min_stocks`, exactly `min_stocks` and above `max_stocks`; a suspended passer kept; between-review caps; it reviews on a run's first day and on its first day of each calendar year, and on no other day.
- **Settings:** every key bounded, the cross-field check, a missing key taking its default (a pre-M6 file loads), unique names across the registry, `init` writes them all; `paper run` writes an audit line when one changes.

### 9.2 Meta-guards

The guide guard gains the settings check (§7). The note-key guard covers the two new keys. The public-API guard covers the new exports.

### 9.3 Golden and journeys

- **The `dividend-growth` golden backtest** in the M3 harness (`tests/golden/test_golden_backtest.py`), on recorded fixtures that include a look-back, a split inside it, a stock whose look-back is refused, and a year boundary.
- **CLI journeys** on recorded fixtures: `backtest --strategy dividend-growth` and `--strategy monthly-savings`; `compare` with all three wave-1 strategies; `paper run` across a year boundary with `dividend-growth`, showing the review; `explain` for both new guides; `init` writing the new keys and the new default.

### 9.4 Non-functional

The existing performance test gains a `dividend-growth` year over the LQ45. Its limit is set by the plan from a measured run, not guessed here.

### 9.5 Mutations

Each story's plan lists its predicted mutations and their catchers, run under `HYPOTHESIS_PROFILE=ci`, as in M5b.

## 10. Stories

| Story | Delivers |
|---|---|
| S1 | The engine's data path and the settings mechanism: `ActionHistory`, `past_actions`, `MarketView.dividends`, `pay_date`, `history_complete`, `Tradable.members`, `Decision.notes`, the look-back fetch with `lookback_years` on `backtest`, `compare` and `day_inputs`, its `data.dividends.history_refused` warning and that key's lesson, `Setting`, `Registered.settings` and `lookback_years`, and reading and writing `[strategy]` keys (no strategy has any yet). |
| S2 | `monthly-savings`, its `instalments` key and its guide, with its CLI journeys. |
| S3 | `dividend-growth`, its `min_stocks`, `max_stocks` and `growth_years` keys and its guide, the `strategy.too_few_qualified` note and that key's lesson, the golden test, the default switch and its CLI journeys. |
| S4 | Course module 8: a lesson for each of the three wave-1 strategies. |

This is the split Shyden approved in part 3, with the settings placed in S1 because S2 and S3 both need them. A key's lesson lands in the story that adds the key, because `tests/meta/test_lessons.py` fails for a key without one.

## 11. Risks

- **Yahoo's dividend history** may have gaps or errors before 2021 that change who passes. The golden test pins behaviour on fixtures; the live acceptance run (core AC1) is where real data is seen.
- **Delisted members** (such as `SRIL`) may be refused for their whole history. §4.3 makes that a warning for the look-back; for the run's own days, M3's rules apply unchanged.
- **The measured counts are two dates.** In another year the rule could pass fewer than 15, and the strategy would then hold cash, as decision 2 intends.

## Scope decisions

- **SD1:** core §8's line for `dividend-growth` reads "whose total dividend per share has not fallen in any of the last 5 calendar years". It becomes "that paid a dividend in each of the last 6 calendar years, with the latest year's total at least the total five years before it" (decision 6, §3).
- **SD2:** "weighted towards spreading pay months" becomes "chosen to spread pay months"; weights are equal (decision 3).
- **SD3:** strategy settings are flat keys in `[strategy]` (§4.5), not per-strategy tables.
- **SD4 (amends the M3 spec's scope table):** M3 moved "price history before the backtest's start" to M6. M6's look-back covers corporate actions only, and bars move on to M7, whose `ma-trend` is the first strategy to need them (§1.1).

When this spec is approved, core §8's `dividend-growth` row (SD1, SD2), core §9.5's configuration description (SD3) and the M3 spec's scope table (SD4) are edited to match, each with a line in that spec's review log, as the M2 plan's scope decisions were (core spec, review pass 14).

## Spec review log

- **Pass 1 (2026-09-30):** mechanical: placeholders 0; every file, function and guard the spec names was read in the code (`backtest._fetch` and its `if not named: raise`, `day_inputs`, `add_trading_days`, `is_trading_day` raising for a year with no holiday data, `get_int` refusing a missing key, `EXIT_CODES` giving `DataFileError` exit 2, `DayReport.notes`, `Tradable`'s fields, `test_every_key_has_a_lesson`, the guides directory). 8 findings, all fixed: (1) §5 cited part 2 for `monthly-savings`, which was part 1; (2) the M3 spec moved the pre-start look-back to M6 and nothing said M6 moves bars on, now SD4; (3) §10's story split had drifted from the approved one; (4) `data.dividends.history_refused` had no lesson, which `test_every_key_has_a_lesson` requires; (5) a pre-M6 `steadyhand.toml` would have failed to load, so the strategy keys are optional; (6) and (7) the configuration exit code and the trailing-yield window were not stated; (8) the review-day rounding and `monthly-savings`' split arithmetic were not pinned.
- **Pass 2 (2026-09-30):** full read. 11 findings, all fixed: the 2025 column named a month it was not; `dividends()` takes no date, so its `LookAheadError` sentence moved to `pay_date`; `paper run` builds from the account's opening day through `day_inputs`, not a window (read in `paper.py`), so `day_inputs` gains `lookback_years` too; S1 could not register keys for strategies that do not exist yet, nor test a look-back without one, so the entry points take `lookback_years` and each strategy's keys land with it; `monthly-savings`' reserve arithmetic was loose; "one rupiah below" did not fit `Decimal` dividends; notes were not type-checked; the scope-decision heading claimed all four amend the core spec.
- **Pass 3 (2026-09-30):** full read, with a grep for every term passes 1–2 touched. 1 finding, fixed: SD1–SD4 amend two parent specs and nothing said those would be edited to match.
- **Pass 4 (2026-09-30):** full read. 1 finding, fixed: §9.1 had no test for `Tradable.members`, `Decision.notes`, a missing key's default, or the look-back fetch outside the golden test.
- **Pass 5 (2026-09-30):** mechanical: every behaviour in §4–§7 mapped to a test in §9. 4 findings, all fixed: no test for a changed setting's audit line, for the instalment sized from cash on a held portfolio, or for `dividend-growth` reviewing on no other day; and "`compare` fetches the largest look-back" put in the engine a choice the CLI makes.
- **Pass 6 (2026-09-30):** the §4–§7 to §9 map again, then a full read. **0 findings. Loop closed.**
- **Pass 7 (2026-10-01, the #160 spec):** §4.3 was brought into line with the #160 spec (`docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md` §5): the look-back reads a dividend on a day Yahoo adjusted without saying restored when the tick grid proves the factor, and refuses it when it does not.
