# steadyhand: Recovering Yahoo's unreported price factor (#160)

**Status:** design approved by Shyden in conversation on 2026-10-01, in three parts, after four decisions; three more were decided during review (§2). One of them was asked twice, because the measurement behind his first answer was wrong (§3.4). The written spec was reviewed to zero (pass 7 found nothing) and approved on 2026-10-01 under Shyden's standing rule for reviewed specs; decisions 5 to 7 came out of that review.
**Amends:** the core spec (`2026-09-24-steadyhand-core-design.md`) §4.3, whose `DataSource` protocol gains `data_notes` (§7), and §9.2, which refuses every day whose prices are not whole rupiah after the reported splits are reversed, and the M6 spec (`2026-09-30-m6-strategy-wave-1-design.md`) §4.3, whose look-back reads dividends on those days unchanged.
**Ticket:** #160. It was filed as "credit a dividend whose ex-date falls on a refused day (measure first)". Its measurement (AC1) found that the amounts themselves are wrong, so Shyden re-directed it on 2026-10-01: recover the factor (§3.1).

## 1. What this delivers

Yahoo's "unadjusted" IDX history carries adjustments Yahoo does not report. A rights issue scales every earlier price, and every earlier dividend, by a factor nobody publishes. Today `unadjust` (`yahoo.py`) refuses each such day with `UnrecoverablePricesError`, so the stock is unpriced there. `actions_in` passes the scaled dividends on as if they were correct.

This work infers that factor from the IDX tick grid, proves it, and restores the prices and dividends of every run of days where the proof holds. Days where it does not hold stay refused, as today. Every restored span is reported to the user with a keyed note.

### 1.1 Out of scope

- **Volumes that are not whole shares after a split is reversed.** They refuse a day whatever its prices, today and after this work (§3.6). BRPT has it on every refused day, and eight of the restored stocks have it on many days. It has a ticket of its own, #162 (decision 7).
- **Days before 2014-01-06.** No tick grid is known for them (§4.2), so they stay refused.
- **Paper reports.** No data warning reaches them today, so the note does not either; the whole class has a ticket of its own, #161 (decision 6).
- **Restoring volume.** The unreported factor does not scale it (§3.2), so it is never multiplied by f.
- **A factor of 2 or more.** It cannot be told apart from a grid ratio (§3.3), so a run whose true factor is 2 or more stays refused, or in a one-tier span is read as f/2 (§11).

## 2. Shyden's decisions (2026-10-01)

Each was asked with its reasoning, measured options and a recommendation, and the recommended option was chosen every time.

1. **The proof rule: strict tiers (B).** A run is restored only when exactly one factor in [1, 2) puts every price of the run within Rp0.01 of its own tier's tick, and the run has at least 20 prices. Review pass 2 moved the window's lower edge to the whole rupiah nearest p1, so that f = 1 is always tried (§3.5); that only removes a wrong proof. First chosen: A, which also accepted the tier below. Re-asked after §3.4: B. Rejected: a mean-score threshold (it could not tell INCO's real 5-day factor from noise, and it rejected SIDO and CTRA).
2. **The grid before 2020-03-13: an inference-only table (A).** `tick_sizes.toml` ships only rows verified from IDX's own text (core §9.1), and its first row is 2020-03-13. Inference may use the five tiers from 2016-05-02 and the three tiers from 2014-01-06 (`docs/research/t-hist.md` §3, supported by prices but unverified), held in the inference module with that citation and never used to validate an order. Rejected: the shipped table only (every span before 2020 would stay refused), and adding the rows to `tick_sizes.toml` (that would break core §9.1 for order validation too).
3. **Reporting: a keyed note with a lesson (A).** `data.prices.restored`, once per stock per run, naming the span, the factor and the proof's size, explained by a lesson. Rejected: silent restoration (no trail for a user comparing against Yahoo), and a note only in the fetch summary (a report read later would carry no trail).
4. **Where recovery lives: the source, from the whole history (1).** `YahooDataSource` infers from the ticker's whole history, caches the restored bars, and keeps a record of each restoration. Rejected: caching Yahoo's raw rows and restoring on every read (it changes core §9.3's validated-rows-only cache), and a shipped file of measured factors (it misses any new rights issue until someone measures it).
5. **How the note reaches a run: a core `DataSource.data_notes` method (1).** Asked after review pass 1 found that the approved design's premise was false: the commands do not carry data warnings. `survivorship_warnings` reaches a backtest through the core engine (`backtest._data_warnings` reads the `Universe` protocol). Rejected: the CLI printing notes beside a backtest (saved reports would carry no trail, against decision 3). This is the one core interface change.
6. **Paper reports: a separate ticket (A).** Asked after review pass 1 found that no data warning reaches a paper report today. Paper accounts build each day through `day_inputs` and `DayReport`, never through `_data_warnings`, so survivorship, refused days and refused history are all missing there as well. Every proven span ends by 2024-06-14, so a paper account opened now never trades a restored price; only its look-back's dividends can be restored values. This ticket covers backtests, comparisons and their saved reports, and the whole class goes to its own ticket, #161. Rejected: the restored note alone in paper (one data warning of four), and all four inside #160 (paper code no part of this design covered).
7. **Volumes that are not whole: a separate ticket (A).** Asked after review pass 3 found that many rows in proven runs are also refused because their split-reversed volume is not whole shares (§3.6), so the days that become tradable are fewer than the design's table showed. #160 restores prices and dividends, and a row whose volume is not whole stays refused, as today. The volume defect, BRPT included, is #162. Rejected: rounding volumes inside #160 (it changes core §9.2's fail-closed rule for every stock, with no price factor involved), and leaving those rows out of the proof's evidence (the same factors from far fewer prices, and none for CTRA: SIDO's evidence would shrink from 1,859 days to 7).

## 3. Measurement

All figures were read through the product's own reader (`download_history`, the reported-split reversal in `_factor`) with yfinance 1.7.0, for 2014-01-06 to 2026-09-29 unless stated: the range the source reads (§5). The probes and their outputs are in the git-ignored `.superpowers/sdd/2026-10-01-160-refused-dividends/` (`measure.py`, `factor.py`, `spans.py`, `unique.py`, `unique3.py`, `unique4.py`, `findings.md`). `unique6.py` is the rule as this spec states it, and `unique6-upper2.jsonl` its output for all 62 stocks; `volume.py` measures §3.6.

### 3.1 The amount is wrong, not missing (AC1)

The only refused-day dividend in the three golden windows is BBRI's on 2021-04-06, and no golden run held BBRI that day, so crediting it would move no golden figure. But Yahoo records it as Rp89.91268, scaled by the same factor as BBRI's prices. f = 1.1000190 puts all 584 prices of the recorded refused span (2021-02-01 to 2021-09-07) on the Rp10 tick, and the clean span after it gives exactly 1.0000000. 89.91268 × f = 98.9057, against the Rp98.905659443 BRI announced (Liputan6). Crediting the recorded amount would have paid 9.09% too little. M6's look-back reads BBRI's 2019 and 2020 dividends with the same shortfall.

### 3.2 Who is refused, and what the rule recovers

63 large IDX stocks were asked for (the union of LQ45 members 2019–2025 as far as known), and 62 answered (WSKT returned 404). 40 have no day with a price that is not whole rupiah after the reported splits are reversed (an "unwhole price" below). Under the approved rule (strict tiers, one factor, at least 20 prices, every candidate from §4.3 tried):

| Stock | Days with an unwhole price | In a proven run | Tradable after restoring | Factor |
|---|---|---|---|---|
| BBTN | 2,166 | 2,166 | 2,166 | 1.1256151 |
| SMGR | 2,157 | 2,157 | 2,157 | 1.0027822 |
| SIDO | 1,859 | 1,859 | 7 | 1.0000004: rounding noise, not an adjustment (§3.5) |
| BBRI | 1,845 | 1,845 | 1,110 | 1.100019 (2014-01-06 to 2021-09-07) |
| MEDC | 1,602 | 1,602 | 928 | 1.18125 from 2017-12-08, 1.3124999 before (stacked) |
| MDKA | 1,463 | 1,463 | 753 | 1.025009 from 2018-08-15, 1.0686262 before (two stacked adjustments; listed 2015-06-19) |
| BRIS | 1,117 | 1,117 | 1,117 | 1.0253162 |
| ESSA | 734 | 734 | 131 | 1.138843 |
| PTPP | 703 | 703 | 703 | 1.052105 |
| JSMR | 699 | 699 | 699 | 1.002342 |
| WIKA | 687 | 687 | 687 | 1.079828 |
| TPIA | 606 | 606 | 47 | 1.0187 |
| CTRA | 603 | 603 | 1 | 1.0000002: rounding noise, not an adjustment (§3.5) |
| EXCL | 566 | 566 | 566 | 1.013797 |
| ANTM | 432 | 432 | 432 | 1.190509 (2014-01-06 to 2015-10-15) |
| HMSP | 415 | 415 | 16 | 1.061481 (2014-01-06 to 2015-10-19) |
| BRPT | 150 | 147 | 0 | 1.0 and 1.0000001: rounding noise; every day is also refused for volume (§3.6) |
| TKIM | 117 | 117 | 117 | 1.307958 (2014-01-06 to 2014-07-03) |
| INCO | 5 | 5 | 5 | 1.0143395 (20 prices, 2024-06-10 to 2024-06-14) |
| ARTO | 994 | 266 | 266 | 1.2057949 (2020-03-30 to 2021-03-04) and short runs at 1.6028112; the rest breaks into runs of 1–3 days |
| TINS | 69 | 0 | 0 | two candidates, about 1 and about 2 (§3.5) |
| MAPI | 2 | 0 | 0 | two single days, no unique factor |

ANTM, HMSP, TKIM and TINS appear only from 2014: their refused days all end before 2016-05-02, where the first survey (`spans.py`) began. Reading from 2014 extended every proven run that had begun on 2015-01-02 or 2015-01-05 back to 2014-01-06 at the same factor, so the three-tier grid fitted every 2014 and 2015 price of those runs. The factors of ANTM, HMSP and TKIM have no independent check yet. Three independent checks agree with the other recovered factors. BBRI's 2021 dividend matches BRI's announcement to Rp0.00004. SIDO's restored dividends come out as round amounts (25.0, 26.0, 29.0, 15.0, 21.0, 22.0, 27.0, 12.5, 18.9, 15.3), and SMGR's as two-decimal amounts (304.91, 304.92, 135.83, 207.64, 40.33, 188.30, 172.64). And the run boundaries MDKA and MEDC produce fall on single days, where an adjustment would.

The unreported factor does not scale volume: all 146 refused days in BBRI's recording have whole volumes, and volume ÷ f is never whole.

### 3.3 Why [1, 2)

- **f ≥ 1, less rounding.** A rights issue lowers every earlier price. Below 1, f/2 also fits wherever halving moves the prices into the finer tier: one BBRI quarter of 2018 scored 0 at 0.5500095, and a clean control "found" 0.5. The window opens at the factor that puts p1 on its nearest whole rupiah, which can be just below 1, so that f = 1 is always tried (§3.5).
- **f < 2.** The ratios between adjacent ticks (1→2, 2→5, 5→10, 10→25) are all 2 or more, so 2f or 2.5f can fit as well as f. Searched to 4, SMGR passed 1.0028, 2.0056 and 3.0083 (one tier, Rp25), and PTPP, WIKA, EXCL and INCO passed f and 2.5f. A window narrower than the smallest grid ratio is the only one in which "exactly one factor" means something.
- The largest measured factor is 1.6028 (ARTO).

### 3.4 The correction behind decision 1

The first measurement of rule A built its candidates from grid points of each stock's own tier only, so the extra candidates A's tier-below allowance admits were never tried. Tried with every whole rupiah, A makes SMGR non-unique (1.0027822, 1.2033387 and 1.6044516 all fit, because a Rp25-grid price × 1.2 or × 1.6 lands on the Rp10 grid) and CTRA non-unique (1.0000002 and 1.2000002), losing 2,280 days for 94 more ARTO days. Shyden chose B on the corrected numbers. Every rule in this spec is stated as it was measured with the full candidate set.

### 3.5 Rounding noise, and the correction found in review pass 2

Some refused days are not scaled at all. Reversing a reported split multiplies Yahoo's float prices by the ratio, and when the ratio is not round the result misses a whole rupiah by more than `unadjust`'s Rp0.0001 (`WHOLE_RUPIAH_TOLERANCE`). TINS's 2014 split is reported as 1.4797794117647058, and its reversed closes read 1,965.0006, 1,910.0005, 2,045.0006. SIDO's and CTRA's factors, 1.0000004 and 1.0000002, are the same thing: their prices sit within Rp0.01 of the grid at f = 1.

The first statement of the candidates started at the first whole rupiah at or above p1. When p1 carries upward noise (TINS: 2,045.0006), that drops f = 1, and f = 1.9999995 was then the only candidate left and was "proven": it would have doubled TINS's prices. Starting at the whole rupiah nearest p1 keeps f = 1 in the set. TINS then has two candidates and stays refused, and no other stock's result changed (predicted before the run: `unique4.prediction`).

Restoring a noise run is still right, because it puts each price on the grid it already almost sits on. But it is not an unreported adjustment, so its note says so (§7).

### 3.6 Volumes that are not whole, found in review pass 3

A refused row can have a second defect. Reversing a reported split also divides Yahoo's volume by the ratio, and that often misses a whole share: BBRI's 2014-01-06 volume is 123,158,677 with a 5-for-1 split reported for 2017-11-10, so 24,631,735.4 shares. `unadjust` refuses such a row today, and still will (decision 7). Odd reported ratios make it common: SIDO's are 2.0152671755725188 and 1.0076335877862594, CTRA's 1.0108695652173914 and 1.0061728395061729.

The volume says nothing about the price factor, so those rows stay in the proof's evidence. Measured, that input gives the same runs and factors as the first one, which took every refused row (`unique6.py` against `unique4.py`): only BRPT changed, because its rows whose prices are already whole no longer enter the proof at all. Leaving the volume-refused rows out instead (`unique5.py`) finds the same factors from far fewer prices, except that CTRA is left with one day and no proof. The table's last numeric column counts the days a restoration actually makes tradable. Dividends are restored across the whole of every proven run, whatever the volumes.

## 4. The proof

The inference is a pure module, `steadyhand_idx.factor`, with no network, cache or calendar access. Its input is the rows of one ticker's history with an unwhole price, in date order, each with its four prices as `Decimal`s after the reported splits are reversed (`_factor`). A row enters it when one of its reversed prices is not whole; its volume plays no part (§3.6). The input needs no calendar: every flat zero-volume row is left out of it, on a holiday or not, because it repeats an earlier close and is no evidence. That is how §3 measured.

### 4.1 Runs

Walk those rows newest first. The newest day starts a run, and its candidates are found from its open p1 (§4.3). Each older day joins the run when at least one of the run's candidates still fits all four of its prices; the run keeps only those. A day that no candidate fits ends the run and starts the next one. A run left with no candidate at all is a single unprovable day.

### 4.2 The grid for a day

| Days | Tiers (lower bound inclusive, tier chosen by the price itself) | Source |
|---|---|---|
| From 2020-03-13 | Rp1 from 1, Rp2 from 200, Rp5 from 500, Rp10 from 2,000, Rp25 from 5,000 | `tick_sizes.toml` through `ticks.py` (verified) |
| 2016-05-02 to 2020-03-12 | the same five tiers | inference-only, `t-hist.md` §3 ("supported by data") |
| 2014-01-06 to 2016-05-01 | Rp1 from 1, Rp5 from 500, Rp25 from 5,000 | inference-only, `t-hist.md` §3 (news values, unverified) |
| Before 2014-01-06 | none: the day is never provable | |

The two inference-only rows live in `factor.py` as a constant whose comment cites `t-hist.md` §3. They are never read by order validation. A wrong row cannot produce a wrong factor (§4.4); it can only leave a run unproven.

### 4.3 Candidates and fit

A price p fits a factor f when p × f lies within Rp0.01 of a multiple of the tick of the tier that p × f falls in, on that day's grid. The candidates for a run are f = g ÷ p1 for every whole rupiah g from the one nearest p1 up to, not including, 2·p1: every factor that puts p1 on a whole rupiah, from about 1 to below 2. That set contains every factor any grid could accept, f = 1 included, so no rival is missed (§3.4, §3.5).

### 4.4 Proven

A run is proven when exactly one candidate fits every price in it and it has at least 20 prices (5 days). Anything else (no candidate, two or more, or fewer than 20 prices) leaves every day of the run refused, raising `UnrecoverablePricesError` exactly as today.

The safety claim is that a proven factor is the true one, for a true factor from 1 to below 2. Two arguments support it. Thousands of prices each have to land within Rp0.01 of the grid under one parameter. And every alternative from about 1 to below 2 is tried, f = 1 included.

### 4.5 Restoring

- **The factor** is the proven candidate refined over the whole run: the mean of (nearest tick ÷ recorded price) over every price in the run, rounded to 7 significant figures (`Decimal`, `ROUND_HALF_EVEN`).
- **A price** becomes the tick multiple nearest to recorded × f: whole rupiah, so a `Money`. A flat zero-volume row on a trading day between a proven run's first and last day is restored the same way, though it was no evidence.
- **A dividend** with an ex-date in the run becomes recorded × split factor × f, quantised to Rp0.0001 (`ROUND_HALF_EVEN`). BBRI 2021: 98.9057.
- **Volume** is unchanged, and a row whose reversed volume is not whole stays refused whatever its prices (§3.6, #162).
- **A noise run** is a proven run whose factor rounds to 1.000000. It is restored like any other run (§3.5); only its note differs (§7).

## 5. The source

- **Whole-history inference.** When the reversal finds a row with an unwhole price in a fetched range, `YahooDataSource` fetches that ticker's whole history once, from 2014-01-06 to today in Jakarta, through the same `download_history` and request policy. It builds the runs over all of it, and restores from those rows. Each run is therefore complete whatever range was asked for, so a day always gets the same factor and the same restored values. That keeps the cache, the golden files and the paper account consistent with each other. The whole history is fetched at most once per ticker per source instance.
- **`today`.** `YahooDataSource` has no clock now. It gains a `today` callable, defaulting to the date in Jakarta, injected the way `CachedDataSource`'s is, so a test fixes the whole history's end.
- **`bars`** keeps today's calendar checks and holiday drops. `holidays.toml` covers 2016 onward, so a bar before 2016 is refused by the calendar (`UnsupportedDateError`) as today, and a 2014 or 2015 restoration reaches dividends only. It returns restored bars for days in proven runs and raises `UnrecoverablePricesError` for the days left (unproven runs, rows whose volume is not whole, and days before 2014-01-06), naming them as today.
- **`corporate_actions`** stays calendar-free: it finds the rows with an unwhole price in its range as §4 does, without the calendar, and fetches the whole history when there are any. Its dividends go through the same runs: a dividend in a proven run is restored (§4.5). A dividend whose ex-date falls in an unproven run is now refused with `UnavailableDaysError` naming that ex-date, because its amount is known to be wrong. M6's look-back then marks the stock incomplete (`history_complete` false, warning `data.dividends.history_refused`), as for any refused look-back (M6 §4.3). Inside a backtest's own window the same refusal reaches `backtest._unpriced_actions`, which returns `None`, so the stock's actions over the backtest are unknown and its history is incomplete (M6 plan scope decision 14), where today the scaled amount is read. Measured impact: no dividend's ex-date falls in any unproven run of the 62 stocks (TINS, ARTO, BRPT and MAPI; `unproven_divs.py`).
- **`restorations(instrument, start, end) -> tuple[Restoration, ...]`** returns the proven runs overlapping the range. `Restoration` is a frozen dataclass holding `instrument`, `first`, `last`, `factor: Decimal` and `prices: int`.

## 6. The cache

- Restored bars are stored as ordinary validated bars (core §9.3 unchanged).
- A new table `restorations (symbol TEXT, first TEXT, last TEXT, factor TEXT, prices INTEGER, PRIMARY KEY (symbol, first))` records each proven run, so the note can be rebuilt from a cache read without refetching. `CachedDataSource.restorations` reads it.
- **Migration** (the next entry in `cache.py`'s `MIGRATIONS`): it creates the table, and deletes every row of `actions`, `fetched_actions` and `fetched`. Everything is then re-read once under the new rules. That is what corrects a cache that already holds BBRI's Rp89.91268. Bars from refused days were never stored, so no stored bar is wrong, and clearing `fetched` makes the cache fetch the newly restorable days.

## 7. Notes and the lesson

- **Key** `data.prices.restored`, defined in `steadyhand_idx.notes` and checked by the key meta-test (`tests/meta/test_note_keys.py`).
- **Text**, once per stock per proven run overlapping the backtest's range, look-back included: "`<SYMBOL>`: Yahoo's prices from `<first>` to `<last>` carry an adjustment Yahoo does not report, so steadyhand restored them: every price and dividend in that span is multiplied by `<f>`, proven by `<n>` prices that fit the IDX tick grid at that factor and at no other." A noise run (§4.5) reads instead: "`<SYMBOL>`: Yahoo's prices from `<first>` to `<last>` miss whole rupiah by a rounding error after its reported splits are reversed, so steadyhand put each one on the IDX tick grid, proven by `<n>` prices that fit it with no other factor."
- **Path (decision 5):** the core `DataSource` protocol gains `data_notes(instruments, start, end) -> Sequence[Note]`, and `backtest._data_warnings` includes it over the backtest's whole window, look-back included, beside `market.universe.survivorship_warnings` (which reaches runs the same way). The note therefore appears wherever data warnings appear: backtests, comparisons and their saved reports (`reports.py`). Paper reports carry no data warning of any kind, so they do not carry this one either (decision 6). `DataSource` is `runtime_checkable` and `Market` checks its source against it, so every implementation gains the method: `YahooDataSource` and `CachedDataSource` build the note from their restorations, and the test fakes return `()`. Those are `Edited` and `Interrupted` (`tests/cli/test_paper_run.py`), `Synthetic` (`tests/perf/synthetic.py`), `_Source` (`tests/engine/test_backtest.py`, whose four subclasses inherit it) and `_MinimalSource` (`tests/engine/test_protocols.py`).
- **Lesson** `idx.restored_prices`, in the `how-idx-works` module (`explains = ["data.prices.restored"]`, `see_also = ["backtest.data_gaps", "idx.ticks"]`). It explains what an unreported adjustment is, why the tick grid proves the factor, what a rounding error from a reported split is, and that a restored figure can differ from what Yahoo shows.

## 8. Errors

- Unproven days: `UnrecoverablePricesError`, unchanged, naming every such day in the range.
- A dividend in an unproven run: `UnavailableDaysError` naming the ex-date (new for `corporate_actions`).
- Network failure on the whole-history fetch: `DataUnavailableError` at once, naming the ticker and the range, as for any fetch (fail closed; no retry since #179).

## 9. Testing

TDD throughout, at 100% branch coverage, with each guard proven by a mutation that turns it red.

### 9.1 Unit and property tests

- **Synthetic runs:** true tick-grid prices scaled by a known f recover exactly that f; f/2 and 2f are rejected by the bounds; a run crossing tiers; two stacked runs split on the right day; fewer than 20 prices stays refused; two fitting candidates stays refused; a day before 2014-01-06 is never provable; each grid era is used on its own days; flat zero-volume rows are no evidence but are restored inside a run; a row with a volume that is not whole stays refused, and its prices still count as evidence; a row whose prices are whole never enters the proof; a noise run is restored and gets the noise text.
- **The TINS case:** true prices with upward noise at p1 (2,045.0006 and its neighbours) keep f = 1 as a candidate, find f ≈ 2 as well, and stay refused. Mutating the start back to the first whole rupiah at or above p1 must turn this red.
- **Property (Hypothesis, `ci` profile):** random true grid prices, with or without float noise of up to Rp0.001, × a random f in [1, 2) either recover that f or stay refused, and never give a different f. This is §4.4's safety claim as a test.
- **The BBRI recording:** f = 1.100019, and the 2021-04-06 dividend restores to 98.9057, within Rp0.0001 of BRI's announced 98.905659443.
- **Restoring:** prices land on ticks as `Money`; dividends are quantised to Rp0.0001; volume is unchanged.
- **Source:** the whole history is fetched once per ticker and ends on the injected `today`; a restored day is identical whatever range was asked for; a dividend in an unproven run is refused, in a look-back and inside a backtest's window; `restorations` returns exactly the overlapping runs.
- **Cache migration:** the table exists; actions and both coverage tables are cleared; the migration runs once (idempotent at the version); a restoration survives a round trip.
- **Notes:** one note per stock per run, with the exact text; `_data_warnings` includes `data_notes` over the window, look-back included, in a backtest and in a comparison; the key passes the meta-test; the lesson renders and lists the key.

### 9.2 Golden runs and other consequences (intended, each explained in its PR)

- **Golden runs.** Of the golden fixtures (ASII, BBCA, BBRI, TLKM, UNVR), only BBRI has refused days. Of its 1,103 days from 2017-01-31 to 2021-09-07 with an unwhole price, 950 become tradable: every day from 2017-11-10, and the days before it whose volume is whole. The other 153, all before 2017-11-10, stay refused for volume (§3.6). The golden figures change. Each changed figure is re-recorded with its cause stated.
- **The recordings.** The golden replay (`record_golden.recorded`) refuses any range outside a recording, and every recording starts on 2017-01-31, so it would refuse the whole-history fetch. BBRI therefore gains a whole-history recording, from 2014-01-06 to the day it is recorded, which the replay serves for that request; the replay's sources pass that day as `today`. A test asserts it agrees row for row with BBRI's existing recordings wherever they overlap, so a change in Yahoo's data between the two recording days is caught rather than baked into the golden figures.
- **M6's look-back** reads BBRI's corrected 2019 and 2020 dividends (each about 10% higher).
- **The M4 income report** shows BBRI's 2021 dividend as 98.9057.

### 9.3 Non-functional

- Inferring the runs of the BBRI recording finishes within a budget the plan measures and pins (perf marker, outside coverage, as the M3b perf test is).
- One extra Yahoo request per affected ticker, at most once per source instance.

## 10. Stories

1. **S1 `factor.py`:** the pure inference (§4): grids, candidates, runs, proof, restoration, with the property test.
2. **S2 the source and the cache:** whole-history inference with the injected `today`, restored `bars` and `corporate_actions`, `restorations`, the cache table and migration (§5, §6), BBRI's whole-history recording, the BBRI recording tests, and the golden re-records (§9.2), which change in this story because it is the one that prices BBRI.
3. **S3 notes and the lesson:** the key, the core `DataSource.data_notes` method in every implementation and in `_data_warnings` (§7), the lesson, the golden runs' new warning, and the amendment text in core §4.3 and §9.2 and M6 §4.3.

## 11. Risks

- **A true factor of 2 or more** stays refused, or in a one-tier span is read as f/2. The largest measured factor is 1.6028; the property test bounds the claim to [1, 2).
- **The window's edges.** Float noise at p1 moved the lower edge once (TINS, §3.5). The start now rounds, and the property test draws noisy prices so that an edge effect of this kind goes red.
- **The inference-only grids are unverified.** A wrong row can only leave a run unproven, never prove a wrong factor (§4.2, §4.4).
- **Yahoo changes how it adjusts.** The daily yahoo-shape workflow and the BBRI recording test would show it.
- **The migration re-reads every cached range once.** That is a one-off cost on the first run after upgrading.

## Spec review log

(Review passes are logged here. The loop closes on a pass that finds nothing.)

- **Pass 1 (2026-10-01).** Every named file, symbol, table, marker and cited section was grepped. Found and fixed: (1) the status line counted four decisions; (2) §7's premise that the commands carry notes was false, so decision 5 was asked; (3) §7 claimed paper reports, which carry no data warning at all, so decision 6 was asked; (4) the implementations that must gain `data_notes` were miscounted in conversation, which named an `InMemoryDataSource` that does not exist: there are seven classes, now listed in §7; (5) `YahooDataSource` has no clock, so `today` is added (§5); (6) the golden replay refuses ranges outside its recordings, so BBRI needs a whole-history recording (§9.2); (7) the golden re-records sat in S3, but S2 is the story that prices BBRI, so they moved; (8) §5 omitted the refusal's effect inside a run's own window; (9) S3 still named "the helper" and "the commands' warnings" from the rejected path; (10) the protocol change amends core §4.3; (11) `MIGRATIONS` and the lesson's module are now named. The M4 income report reads no warnings (`income.py`), so §9.2's line about it concerns the dividend amount only, which is correct.

- **Pass 2 (2026-10-01).** A full read, every name re-grepped, and the rule re-run from the range the source reads. Found and fixed: (1) the measurements began on 2015-01-02 (and the survey on 2016-05-02) while the source reads from 2014-01-06; re-run from 2014, every proven run reached 2014 at the same factor, and ANTM, HMSP, TKIM and TINS appeared (§3.2); (2) the survey said 43 stocks had no refused day where 44 had from 2016, and 40 have from 2014; (3) **TINS proved a wrong factor**, 1.9999995, because the candidates started at the first whole rupiah at or above p1 and its noise put p1 just above one; the start now rounds, TINS stays refused, nothing else changed, as predicted (§3.5); (4) §4.5's "f = 1 restores nothing" contradicted §3.2, which restores SIDO and CTRA at factors that round to 1.000000: the rule is now stated as volume (BRPT) plus noise runs with their own note text (§4.5, §7); (5) "run" meant both a span of refused days and a backtest, so the backtest is named as such in §5, §7 and §9; (6) §4's input relied on the calendar, which has no year before 2016 and raises `UnsupportedDateError` for every 2014 and 2015 day (checked): the input is now calendar-free, as measured; (7) decision 5 cited a "section 2" that no reader has; (8) the status line said the design was approved after six decisions.

- **Pass 3 (2026-10-01).** A full read, and the rule re-run with the volume separated from the prices. Found and fixed: (1) BRPT's rows, whose prices are whole, formed "proven" f = 1 runs that would have emitted a note for a restoration that never happens; rows now enter the proof only when a price is off the grid; (2) predicting that only BRPT would change, the run showed that many rows in proven runs are also refused for volume (BBRI 735 of 1,845, SIDO 1,852 of 1,859), so the table overstated the tradable days; decision 7 was asked, the table now shows both counts, and #162 holds the volume defect (§3.6); (3) the claim that 2014 extended "every other" proven run was true only of runs that began in January 2015; (4) ANTM, HMSP and TKIM had been presented beside checked factors without saying theirs are unchecked; (5) §4.4 stated the safety claim on [1, 2) after the window's lower edge had moved; (6) the golden BBRI line counted days that stay refused for volume.

- **Pass 4 (2026-10-01).** A full read. Found and fixed: (1) §4, §4.1 and §5 still called the proof's input "refused rows", which since pass 3 includes rows refused for volume alone that never enter it; (2) `bars` did not name rows whose volume is not whole among the days it refuses; (3) §3.6 compared the wrong pair of measurements for "identical either way", and the volume-free input (`unique5.py`) does not keep CTRA's proof; (4) §1.1 said BRPT has the volume defect "alone", where 150 of its rows also carry price noise; (5) §5's measured impact covered ARTO and MAPI from 2016 only: re-measured from 2014 over every unproven run, no dividend falls in one.

- **Pass 5 (2026-10-01).** Every backticked name checked mechanically (`names_check.py`). Its first run reported nothing missing, because `git grep` matched the spec itself; excluding the spec, it reports exactly the names this work creates, plus `InMemoryDataSource`, which the pass 1 entry cites as absent. Every cited section was re-read. Found and fixed: §5 cited M6 plan scope decision 13 for the refused stock's actions, copying the code, which was wrong too: it is 14 (13 is the golden harness). `backtest._unpriced_actions` and the `_Unpriced` test source are corrected in their own commit; no other code cites a scope decision.

- **Pass 6 (2026-10-01).** A full read. Found and fixed: "prices off the grid" named the proof's input, but a whole-rupiah price can be off its tick grid and never enters the input; the input is now named by its test, a price that is not whole rupiah after the reported splits are reversed ("an unwhole price"), defined once in §3.2.

- **Pass 7 (2026-10-01).** A full read of every section and every log entry, and the name check re-run (only names this work creates are missing). Nothing found. The loop is closed.
