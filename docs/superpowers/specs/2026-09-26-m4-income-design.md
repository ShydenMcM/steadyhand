# steadyhand M4: Income

**Status:** draft. The design was approved in conversation, section by section, on 2026-09-26; the review loop closed on pass 10 with no findings, and the document awaits Shyden's approval.
**Parent spec:** `2026-09-24-steadyhand-core-design.md` (the "core spec"). M4 is its milestone 4 (§13): the dividend ledger, the income goal tracker, the projection and the payment calendar (§7), and the reinvestment exemption claim (§6.2). Everything the core spec settles still holds unless §2 below amends it.
**Inputs:** core spec §6.2 and §7, `docs/research/t-tax.md` §3, §4 and §7, `docs/research/t-pay.md` §4, and Shyden's answers of 2026-09-26 (§2).

## 1. What M4 delivers

- **M4a, income reporting** (read-only over what the engine already emits): `income_report`, a pure function returning an `IncomeReport` with received income by month and over the trailing 12 months, take-home income, yields, the run-rate of the current holdings, the payment calendar, the goal tracker and the three-scenario projection. The backtester produces one for the strategy and one for the baseline when a goal is set, and reports the strategy's income impact against the baseline.
- **M4b, the reinvestment exemption claim**: an engine switch, off by default, that replaces the flat 10% tax at pay with a claim for each dividend: reinvestment by the deadline, protection through the holding period, and tax booked when either fails. With the switch off, every run gives the same figures and ledger as M3's.

### 1.1 Scope moved or narrowed

| Item | Where the core spec puts it | Where it goes now | Why |
|---|---|---|---|
| `report --income` rendering | M5 (CLI) | M5 (unchanged) | M4 is library only. `IncomeReport` is what M5 renders. |
| Pay-date override file `dividend_pay_dates.csv` | §5 step 2, §6.2 | Not in M4 | No code reads it yet. M4 uses the modelled pay date, and the exemption deadline uses the ex-date's tax year, which §6.2 already names as the conservative default. |
| Training and onboarding | Not in the core spec | A separate sub-project, brainstormed after this spec (§2, decision 8) | M4 only leaves the hook: a stable key on everything it reports (§7). |

### 1.2 Delivery: one spec, two plans

M4a (stories S1–S4) and M4b (S5–S8) each get their own plan, reviewed to zero and executed in order. M4a does not depend on M4b: with the switch off by default, the tax the engine books is unchanged, and M4a's take-home figure does not depend on it (decision 2).

## 2. Shyden's decisions (2026-09-26)

1. **Split M4** into M4a (reporting) and M4b (exemption claim): one spec, two plans.
2. **The goal is measured on take-home income**: gross less the full dividend tax, whatever the exemption switch says. Living off dividends means not reinvesting them, so the exemption cannot apply then. The rate is read from the rules, never hard-coded.
3. **The projection starts from the run-rate of the current holdings**: each holding's per-share dividends over the trailing 12 months × the shares held now. The goal tracker's current figure stays on income actually received.
4. **Pure functions with the dividend history passed in.** `income.py` does no I/O. The caller fetches the history through `DataSource`.
5. **Design sections 1–3 approved as presented** (report contents, projection mechanics, calendar and backtest wiring). This includes two **amendments to core spec §7**: the pessimistic scenario's dividend growth is `min(0%, measured)` instead of a flat 0%, so a shrinking dividend can never leave pessimistic rosier than base; and every scenario reinvests the take-home part of each dividend, not all of it, which errs low when the exemption would have applied.
6. **The protection check has a settlement-cycle grace** (§6.4), an **amendment to core spec §6.2**, whose check has no grace. A rotation (sell one stock, buy another within the cycle) keeps the claim, as PMK 18/2021 Pasal 36(3) allows. A shortfall still there when the cycle ends breaks the claim.
7. **Design section 5 approved**: the tests, the eight stories, and stable keys on everything M4 adds.
8. **Training is its own sub-project** (Shyden, 2026-09-26: *"I want this to also teach people how to actually do trading. Newbie friendly with good training for everything. but it should have an opt-out option. as part of the first laungh we should ask the user their competency level and if they want training or not"*). Shyden chose three things: it is brainstormed after this spec is approved; it combines contextual explanations with a lesson course; and its content is written once as Markdown in the repo, shown by the CLI from M5 and rendered later by the dashboard. **Its legal line** (core spec §3.3): a competency level may change how much is explained, and never what the tool suggests trading.

**Correction to the design as presented.** Section 4 (the exemption) was presented with a protection end of "31 Dec of the purchase year + 3". Core spec §6.2 and T-TAX §3 count three tax years **including** the purchase year: a March 2027 purchase is held through 31 Dec 2029. The rule is therefore **31 Dec of the purchase year + 2**, and this spec uses that.

## 3. Architecture

### 3.1 Modules

| Module | Package | Story | Contents |
|---|---|---|---|
| `notes.py` | `steadyhand` | S1 | `Note(key, text)` and the key constants (§7). It imports nothing from the engine, so `engine.py`, `exemption.py` and `income.py` can all use it without a cycle |
| `income.py` | `steadyhand` | S1–S4 | `income_report`, `IncomeReport` and its parts, `IncomeGoal`, `PROJECTION_LABEL` |
| `market.py` | `steadyhand` | S2 | `add_trading_days(rules, day, count)`, moved from `corporate.py`'s private `_add_trading_days` so that the engine's pay date and the calendar's pay month come from one function |
| `backtest.py` | `steadyhand` | S4 | the goal setting, the income reports and the income impact |
| `exemption.py` | `steadyhand` | S5–S7 | `DividendClaim`, `Protection`, and the daily claim bookkeeping |
| `corporate.py`, `engine.py` | `steadyhand` | S5–S7 | the switch, and claims carried in `Holdings` |
| `market.py`, `rules.py`, `fees.py`, data file | both | S5 | the reshaped `dividend_tax` and the two date rules (§6.1) |

The engine stays market-neutral (core spec §4.2): every Indonesian date and rate comes through `MarketRules`. The no-float meta-guard already covers every engine module found on disk (`tests/meta/test_no_float.py`, `guarded_files`), so the new modules are guarded without any change to it.

### 3.2 The entry point

```python
def income_report(
    reports: Sequence[DayReport],
    final: EngineState,
    history: Mapping[Instrument, Sequence[CorporateAction]],
    rules: MarketRules,
    goal: IncomeGoal,
    monthly_contribution: Money | None,
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS,
) -> IncomeReport: ...
```

- `reports` are the run's day reports in order, as `metrics.measure` takes them. The report is **as of the last report's day** (`as_of`).
- **Windows.** A *year window ending on* a date `d` is the days from `d − (YEAR_DAYS − 1)` to `d`, both inclusive: the window `metrics.measure` uses for `trailing_income`. "n years before" a date is the same month and day n years earlier, with 29 February becoming 28 February.
- `history` holds, for **every** stock in the final portfolio, its corporate actions with an ex-date from `as_of − 5 years` to `as_of`, which contains every window below. A holding missing from `history` is a caller error (`ValueError`). A stock with a shorter history is not an error (§5.2).
- `IncomeGoal(monthly_target: Money)` holds only the target. The contribution is passed separately, so it has one source: the backtester passes `settings.engine.monthly_contribution`.
- The function walks `reports` once. Everything it returns is `Money` or `Decimal`; ratios are rounded to `metrics.RATIO_PLACES`.

### 3.3 Split restatement

`DataSource` returns unadjusted dividends: `yahoo.py` reverses Yahoo's split adjustment. A per-share amount paid before a split is therefore on the old share basis. Wherever M4 compares or multiplies per-share dividends by today's shares (the run-rate, the calendar and growth), it first restates each dividend onto today's basis: it multiplies `per_share` by `old_shares / new_shares` for every `Split` in `history` whose ex-date is after the dividend's and on or before `as_of`. This is exact `Decimal` arithmetic, rounded only where the result becomes `Money`.

## 4. Received income (S1)

- **By month:** for every calendar month from the first report's month to `as_of`'s, including months with nothing paid: gross paid (the `paid` entitlements of reports in that month), tax booked (`DayReport.tax`), net booked (gross − tax), and **take-home**. Take-home is the sum, over each entitlement paid, of `gross − rules.dividend_tax(gross, on=pay day)` at the full rate (decision 2).
- **Trailing 12 months:** the same four figures over the reports in the year window ending on `as_of` (§3.2), and the **monthly average** of each of the four (core spec §7): the trailing figure ÷ 12, rounded down to the currency's minor unit. The monthly average take-home is the goal tracker's figure (§5.4).
- **Current yield:** trailing gross ÷ the last report's `value`. **Yield on cost:** trailing gross ÷ the sum of `cost_basis` over the final portfolio's positions. Either is `None` when its divisor is zero.
- While M4b has not landed, the full-rate call is `dividend_tax(gross, reinvested_by_deadline=False, on=day)`; S5 removes the flag (§6.1).

## 5. Run-rate, calendar and projection (S2, S3)

### 5.1 Run-rate and calendar (S2)

- **Run-rate**, per holding: every `CashDividend` in `history` with an ex-date in the year window ending on `as_of`, restated (§3.3), × the shares held at `as_of`, each rounded down to the minor unit as `corporate.py` rounds an entitlement. It is given as annual gross and as monthly take-home: annual take-home ÷ 12, rounded down, where annual take-home = gross − the full tax on `as_of`.
- **Calendar:** each of those same dividends is placed in the month of its **modelled pay date**, `add_trading_days(rules, ex_date, pay_lag_trading_days)`, the same function and lag the engine credits with (the backtester passes its `settings.engine.pay_lag_trading_days`), so that the calendar and the engine cannot disagree. The result is expected take-home per month of the year (1–12), per holding and in total; `empty_months`, the count of months with none; and **evenness**, the largest month's share of the calendar's total. A perfectly even calendar scores 1/12; one that pays everything in a single month scores 1. Each dividend's take-home here is its amount less `tax(amount, on=as_of)`; a month's figure is the sum of its dividends', and evenness divides the largest month by the sum of all twelve, so the calendar never depends on a second rounding of the annual figure. Evenness is `None` when the run-rate is zero.

### 5.2 Measured dividend growth (S3)

- For each holding with a non-zero run-rate: `W0` is the sum of its restated per-share dividends with an ex-date in the year window ending on `as_of`, and `W4` the same over the year window ending on `as_of − 4 years`. Its growth is `(W0 / W4) ** (1/4) − 1`, computed under a local `Decimal` context and rounded to `RATIO_PLACES`.
- A holding whose `W4` is zero (it paid nothing then, or its history does not reach back that far) counts as **0%** growth, and a note with key `income.growth.short_history` names it.
- The portfolio's measured growth is each holding's growth weighted by its share of the annual run-rate gross. Holdings with a zero run-rate are skipped: they carry no weight.
- **How this reads core spec §7.** Its base scenario uses "the portfolio's own trailing 5-year dividend growth". This spec reads that as the per-share dividend growth of what the portfolio holds, not the growth of the income it received. Received income also grows with every contribution and every reinvested dividend, which the projection already adds month by month, so measuring growth from it would count them twice and overstate every scenario.

### 5.3 The projection (S3)

Three scenarios (core spec §7 as amended by decision 5):

| Scenario | Starting income | Dividend growth `g` |
|---|---|---|
| Pessimistic | run-rate gross × 0.8 | `min(0%, measured)` |
| Base | run-rate gross | `min(measured, 5%)` |
| Optimistic | run-rate gross | `min(measured, 10%)` |

For each scenario, working in `Money`, with income rounded **down** and tax rounded **up**:

- Start: `V` = the holdings' value at the last report (`DayReport.holdings_value`; idle cash is not assumed invested), and `I` = the scenario's starting annual gross.
- `CANNOT` is decided first (see Outcomes). **Month 0:** otherwise, if `(I − tax(I)) ÷ 12 ≥ target`, the result is 0 years.
- For each month `m` from 1 to 600, in this order: (1) `new = (I ÷ 12 − tax(I ÷ 12)) + contribution` (contribution zero when `None`); (2) `I = I + new × (I / V)`, then `V = V + new`; (3) if `m` is a multiple of 12, `I = I × (1 + g)`; (4) if `(I − tax(I)) ÷ 12 ≥ target`, the target is met and the result is `m ÷ 12` years, **rounded up** to one decimal place.
- `tax(x)` is `rules.dividend_tax(x, on=as_of)` at the full rate: the projection reinvests take-home, which errs low even where the exemption would apply.
- **Outcomes:** `REACHED` with years, `NOT_WITHIN` (not met by month 600, "not within 50 years"), or `CANNOT` (the run-rate is zero or `V` is zero: nothing to project from).
- Trading costs on reinvestment are ignored; a note with key `income.projection.costs_ignored` says so on every projection.
- Every projection carries `PROJECTION_LABEL = "Projection, not a promise"`. It reports years, never a date (core spec §7).

### 5.4 The goal tracker (S4)

`GoalProgress`: the target; the monthly average take-home received (§4) and its share of the target; the run-rate monthly take-home (§5.1) and its share of the target. Shares are `Decimal` ratios and are not capped at 1.

## 6. The exemption claim (M4b: S5–S7)

### 6.1 Rules interface (S5)

- `MarketRules.dividend_tax(gross, *, on) -> Money`: the full tax on a gross dividend. The `reinvested_by_deadline` flag is removed.
- `MarketRules.reinvestment_deadline(ex_date) -> date | None`: the last day a dividend with that ex-date may be reinvested, or `None` where the market has no exemption. For IDX it is 31 March of the year after the ex-date's year (PMK 18/2021 Pasal 36(1)(a); the ex-date year is never later than the real pay year, t-pay.md §4).
- `MarketRules.protection_end(purchase_day) -> date`: the last day a qualifying purchase must stay invested. For IDX it is 31 December of the purchase year + 2 (§2, correction).
- The month count (3), the holding years (3) and the rule's start are **effective-dated rows in the IDX data file**, as every market value is (core spec §3.6). T-TAX leaves PMK 18/2021's in-force date blank, so **S5's first task reads it** from the BPK page T-TAX cites, before the row is written. A dividend whose ex-date falls before the rule's start gets `None`.

### 6.2 The switch and the claim (S5)

- `EngineSettings.dividend_reinvestment_exemption: bool = False`.
- **Off:** at pay, `dividend_tax(gross, on=pay day)` is booked as `TAX`, exactly as now. No claim ever exists. Every figure and ledger entry the S9 golden test checks stays identical, and every existing test passes unchanged apart from those that call `dividend_tax` with the old flag.
- `DayReport` gains `notes: tuple[Note, ...]`, where the engine's claim events are reported (§6.3, §6.4). It is empty with the switch off.
- **On:** at pay, no tax is booked and a `DividendClaim` opens: instrument, ex-date, pay date, gross, deadline, and its protections (none yet). A dividend whose deadline is `None` is taxed at pay, as with the switch off. `Holdings` carries the open claims beside `entitlements`, so M5 can save them.

### 6.3 Reinvestment and the deadline (S6)

- **Matching:** each buy fill's `gross` (not its costs, which are not an investment) covers open claims with `pay_date ≤ fill day ≤ deadline` that still have an uncovered amount, **oldest pay date first**. Each covered amount becomes a `Protection(amount, until=protection_end(fill day))` on that claim.
- **The deadline:** on the first trading day after a claim's deadline, the claim's uncovered amount is taxed at the rate in force on its **pay date**, and that tax is booked as `TAX` on that day. The ledger cannot book into the past (`ChronologyError`), so a note with key `exemption.deadline_missed` records that the tax was owed from the pay date. The claim then keeps only its protections. A claim fully covered by its deadline books nothing and emits no note, just as `corporate.py` books no zero tax today (`if tax.amount > 0`).

### 6.4 Protection and breaks (S7)

- At each day's close, **protected** is the sum of protections whose `until` is on or after the day, and **invested** is the sum of `cost_basis` over the portfolio's positions. Protections past their `until` fall away, and a claim with nothing uncovered and nothing protected is closed.
- If `protected > invested`, a **shortfall** has begun, and the day it first appeared is kept in `Holdings`. If a shortfall is still present at the close of `rules.settlement_date(first day)`, the current shortfall **breaks**: protections are removed, latest `until` first, until the removed amount covers the shortfall (the last one partly). Tax is due on the removed amounts at each claim's pay-date rate, and is booked as `TAX` on that day with a note keyed `exemption.claim_broken`, which records that the tax was owed from each claim's pay date. Core spec §6.2 dates this tax to the pay date; the ledger cannot book into the past (§6.3), so the date lives in the note and the booking is today's. A day on which the shortfall has gone clears the kept day.
- This grace is a stated modelling assumption (T-TAX §5 calls the gap a grey area). Every claim figure is labelled an **estimate** that depends on the investor filing the annual realisation reports (T-TAX §7), which the engine cannot see.

### 6.5 Claims in the report (S8)

`IncomeReport.claims`: for each open claim, what remains to reinvest and by when, and what is protected and until when, labelled `ESTIMATE`. It is empty when the switch is off. The by-month tax figure shows tax in the month it was **booked**, so with the switch on a deadline's tax appears in April, not in the pay month.

## 7. Stable keys (training hook)

Every note M4 adds is a `Note(key, text)`. The key is a dotted lowercase identifier (`income.growth.short_history`), unique within the codebase and never reworded; the text is free to change. The training sub-project attaches lessons to keys. Each key is defined once, as a module-level constant, and every `Note` is built from one of those constants, never from a literal. A meta-test walks the engine's AST and asserts three things: every key constant matches `^[a-z]+(\.[a-z_]+)+$`; no key value is defined twice; and no `Note(...)` call takes a string literal as its key. M3's existing plain-string warnings are left for the training sub-project to key.

## 8. Backtest wiring (S4)

- `BacktestSettings.goal: IncomeGoal | None = None`.
- With a goal set, after both runs the backtester fetches `history` for each final holding of each run through `market.source.corporate_actions(stock, as_of − 5 years, as_of)`, and attaches an `IncomeReport` to each `RunResult` (`RunResult.income: IncomeReport | None`). A `DataUnavailableError` propagates: an income report on missing data is never silently skipped.
- `BacktestResult.income_impact`: with a goal and a baseline, the strategy's minus the baseline's monthly average take-home received and run-rate monthly take-home (decision 2; core spec §7, "Strategy income impact"). Otherwise `None`.

## 9. Testing

- **Hand-worked unit tests** for every figure, each with its arithmetic written beside it, as S8's metrics were: by-month and trailing sums, take-home, both yields including their `None` cases, run-rate rounding, split restatement across a split on each side of a dividend, calendar months across a year end and a holiday, evenness at 1/12 and at 1, growth including the zero-`W4` and short-history cases, every projection outcome including month 0, month 600 and a hand-simulated short run, the backtest wiring, and every claim transition in M4b.
- **Properties** (hypothesis, run under `HYPOTHESIS_PROFILE=ci`): take-home ≤ gross; a larger contribution never gives more years; `years(pessimistic) ≥ years(base) ≥ years(optimistic)`, with `NOT_WITHIN` ranked after every number; a zero run-rate gives `CANNOT`; a dividend with no later split is unchanged by restatement, and restating across two splits equals restating across their combined ratio; with the switch on, the tax booked for any one claim never exceeds the full tax on its gross plus one minor unit for each separate booking after the first (each booking rounds up on its own).
- **Golden:** every figure and ledger entry the S9 golden backtest checks stays identical through M4b (switch off). S4 adds the income report on the same recorded data. S8 records a switch-on golden run whose claim figures are hand-checked for at least one claim of each kind: one fully reinvested by its deadline, one taxed at its deadline, and one broken after reinvestment.
- **Fixtures:** the golden stocks' recorded fixtures must cover five years before the golden run's end, for growth. S4's first task checks this and, where they do not, re-records them with `scripts/record_yahoo_fixture.py`.
- **Performance:** `income_report` walks the reports once, and the projection is at most 3 × 600 months. The S10 performance test gains a goal, and must stay within its 30 s budget.
- **Mutations:** each story's plan task lists predicted mutations, each turning the whole suite red with the test total unchanged, run under `HYPOTHESIS_PROFILE=ci`.
- **Meta:** the stable-key test (§7). The no-float guard needs no change (§3.1).

## 10. Stories

Each story is a ticket on the steadyhand board (project 1), with its plan task's acceptance criteria, before any code.

| Story | Plan | Delivers |
|---|---|---|
| S1 | M4a | `notes.py`, the stable-key meta-test, `income.py` skeleton, by-month and trailing received income, take-home, yields (§4) |
| S2 | M4a | `add_trading_days` in `market.py`, split restatement, run-rate and calendar (§3.3, §5.1) |
| S3 | M4a | measured growth and the projection (§5.2, §5.3) |
| S4 | M4a | goal tracker, `income_report` assembled, backtest wiring and income impact, the golden income report, the fixture check (§5.4, §8) |
| S5 | M4b | the PMK 18/2021 in-force date, the reshaped `dividend_tax`, the two date rules and their data rows, the switch and `DividendClaim` in `Holdings`, `DayReport.notes`, `income.py`'s calls moved off the flag, with the switch-off figures and ledger unchanged (§6.1, §6.2) |
| S6 | M4b | reinvestment matching and deadline tax (§6.3) |
| S7 | M4b | protection, the settlement grace and breaks (§6.4) |
| S8 | M4b | claims in the income report and the switch-on golden run (§6.5) |

## 11. Risks

- **Fixture depth.** Growth needs five years of dividend history before the golden run's end. If the recorded fixtures are shorter, S4 re-records them, which changes fixture files that S9's golden test reads; the S9 figures must then be re-verified, not simply re-accepted.
- **The PMK 18/2021 in-force date** is unrecorded (T-TAX's table leaves it blank). S5 cannot write its data row until it is read from a primary source.
- **The protection grace** (decision 6) and the ex-date-year deadline are modelling choices resting on T-TAX's unverified items (§3, §5). They are labelled estimates, and the switch stays off by default.
- **Growth from four intervals** is sensitive to one unusual year at either end. The caps (5%, 10%) bound the upside. Nothing floors the downside, by design: a measured decline is projected as a decline in every scenario, which errs low, and the `income.growth.short_history` note flags the holdings whose growth could not be measured.
- **Training** will want keys on M3's existing warnings. That retro-fit belongs to the training sub-project, not M4.

## Spec review log

- **Pass 1 (2026-09-26): 6 findings, all fixed.** (1) `income_report`'s signature lacked the pay-lag parameter the calendar section used, and the calendar cited a `settings` object the function does not have. (2) The received trailing window (365 days) and the run-rate and growth windows ("1 year") differed by a day across a leap year; every window is now the one defined year window (§3.2). (3) The "history does not reach back" test for growth could not be checked from the data, and meant the same as `W4 = 0`, so it was folded into that test. (4) The projection's monthly order of reinvest, growth and target check was ambiguous at month 12k; it is now numbered. (5) "Byte-identical golden" was unachievable once `Holdings` gains claim fields; it now names the figures and ledger. (6) "No key has two meanings" was not mechanically checkable; keys are now constants, checked by an AST meta-test. Mechanical checks: every cited name exists (`Portfolio.positions`, `EngineState.holdings`, `DayReport.holdings_value`, `EngineSettings.pay_lag_trading_days`, `rules.settlement_date`, `corporate._add_trading_days`, `metrics.RATIO_PLACES` and `YEAR_DAYS`, `scripts/record_yahoo_fixture.py`, `tests/meta/test_no_float.py::guarded_files`).
- **Pass 2 (2026-09-26): 9 findings, all fixed.** (1) Pass 1's fix (5) missed three other "byte-identical" claims (§1, §9 golden, S5's row). (2) `Note` lived in `income.py`, which imports `DayReport` from the engine, while the engine had to build notes, making an import cycle; `Note` now has its own module, `notes.py`, in S1. (3) The engine's claim notes had nowhere to go; `DayReport.notes` is added. (4) S5 must also move `income.py`'s `dividend_tax` calls off the removed flag; its row says so. (5) The calendar's take-home could be rounded two ways (per dividend or annual); it is now per dividend, and evenness divides by the calendar's own total. (6) The property "restate and back is the identity" named an inverse the spec never defines; it is replaced by two checkable properties. (7) The history window started at `as_of − 5 years` in §3.2 and a day later in §8; both now start at `as_of − 5 years`. (8) The income impact compared run-rate gross, against decision 2; it now compares take-home. (9) A pronoun for Shyden was replaced by the name, and a missing blank line before §5.2 was restored.
- **Pass 3 (2026-09-26): 3 findings, all fixed.** (1) Evenness was defined as a share of "the annual take-home" in one sentence and of the calendar's own total in the next; it is now the calendar's total throughout. (2) The property "switch-on tax never exceeds the full tax on everything paid" is false: a claim taxed in pieces rounds each piece up, so Rp2 split 1 + 1 books 2 against a full tax of 1. It now allows one minor unit per booking after the first, per claim. (3) Whether `CANNOT` or the month-0 check comes first was unstated; `CANNOT` is decided first.
- **Pass 4 (2026-09-26): 1 finding, fixed.** Core spec §7's "portfolio's own trailing 5-year dividend growth" could be read as the growth of income received, which includes contributions and reinvestment that the projection adds separately. §5.2 used the per-share reading without saying it was an interpretation; it now says so, with the reason.
- **Pass 5 (2026-09-26): 2 findings, both fixed.** Checked line by line against core spec §7. (1) §7 asks for monthly averages of gross, tax and net; §4 averaged only take-home, and now averages all four. (2) §7 says every scenario reinvests all dividends; the approved design reinvests take-home, which was not recorded as an amendment. Decision 5 now lists both amendments.
- **Pass 6 (2026-09-26): 2 findings, both fixed.** Checked against core spec §6.2. (1) §6.2 dates a broken claim's tax to the original pay date; §6.4 booked it today without saying why, while §6.3 explained the same constraint for the deadline. §6.4 now gives the reason, and its note carries the pay date. (2) Decision 6 changes §6.2's check, but was not labelled as an amendment; it now is.
- **Pass 7 (2026-09-26): 1 finding, fixed.** Internal cross-references resolve and all four note keys match the key pattern (checked by script). A claim fully covered by its deadline would have booked a zero `TAX` and a "deadline missed" note; §6.3 now books nothing for it, as `corporate.py` already does.
- **Pass 8 (2026-09-26): 1 finding, fixed.** §9's switch-on golden check "on at least one dividend: reinvested, deadline-taxed, and broken" could mean one dividend through all three states or one of each; it now asks for one claim of each kind.
- **Pass 9 (2026-09-26): 1 finding, fixed.** §11 claimed pessimistic's `min(0%, measured)` "bounds the downside"; it does not, since no scenario floors a negative growth. The risk now says the downside is deliberately unfloored.
- **Pass 10 (2026-09-26): no findings.** A single full read of §1–§11 against core spec §6.2 and §7, with every earlier fix in place. The loop closes.
