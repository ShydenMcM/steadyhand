# steadyhand: Recovering Yahoo's unreported price factor (#160)

**Status:** design approved by Shyden in conversation on 2026-10-01, in three parts, after four decisions (§2). One of them was asked twice, because the measurement behind his first answer was wrong (§3.4). The written spec is awaiting review.
**Amends:** the core spec (`2026-09-24-steadyhand-core-design.md`) §9.2, which refuses every day whose prices are not whole rupiah after the reported splits are reversed, and the M6 spec (`2026-09-30-m6-strategy-wave-1-design.md`) §4.3, whose look-back reads dividends on those days unchanged.
**Ticket:** #160. It was filed as "credit a dividend whose ex-date falls on a refused day (measure first)". Its measurement (AC1) found that the amounts themselves are wrong, so Shyden re-directed it on 2026-10-01: recover the factor (§3.1).

## 1. What this delivers

Yahoo's "unadjusted" IDX history carries adjustments Yahoo does not report. A rights issue scales every earlier price, and every earlier dividend, by a factor nobody publishes. Today `unadjust` (`yahoo.py`) refuses each such day with `UnrecoverablePricesError`, so the stock is unpriced there. `actions_in` passes the scaled dividends on as if they were correct.

This work infers that factor from the IDX tick grid, proves it, and restores the prices and dividends of every run of days where the proof holds. Days where it does not hold stay refused, as today. Every restored span is reported to the user with a keyed note.

### 1.1 Out of scope

- **BRPT.** Its refused days fit the grid at f = 1 exactly (§3.2): its prices need no factor, so something else refuses them, probably a volume that is not whole after a split is reversed. That gets a ticket of its own.
- **Days before 2014-01-06.** No tick grid is known for them (§4.2), so they stay refused.
- **Volume.** Yahoo does not scale it (§3.2), so it is never restored.
- **A factor of 2 or more.** It cannot be told apart from a grid ratio (§3.3), so a run whose true factor is 2 or more stays refused, or in a one-tier span is read as f/2 (§11).

## 2. Shyden's decisions (2026-10-01)

Each was asked with its reasoning, measured options and a recommendation, and the recommended option was chosen every time.

1. **The proof rule: strict tiers (B).** A run is restored only when exactly one factor in [1, 2) puts every price of the run within Rp0.01 of its own tier's tick, and the run has at least 20 prices. First chosen: A, which also accepted the tier below. Re-asked after §3.4: B. Rejected: a mean-score threshold (it could not tell INCO's real 5-day factor from noise, and it rejected SIDO and CTRA).
2. **The grid before 2020-03-13: an inference-only table (A).** `tick_sizes.toml` ships only rows verified from IDX's own text (core §9.1), and its first row is 2020-03-13. Inference may use the five tiers from 2016-05-02 and the three tiers from 2014-01-06 (`docs/research/t-hist.md` §3, supported by prices but unverified), held in the inference module with that citation and never used to validate an order. Rejected: the shipped table only (every span before 2020 would stay refused), and adding the rows to `tick_sizes.toml` (that would break core §9.1 for order validation too).
3. **Reporting: a keyed note with a lesson (A).** `data.prices.restored`, once per stock per run, naming the span, the factor and the proof's size, explained by a lesson. Rejected: silent restoration (no trail for a user comparing against Yahoo), and a note only in the fetch summary (a report read later would carry no trail).
4. **Where recovery lives: the source, from the whole history (1).** `YahooDataSource` infers from the ticker's whole history, caches the restored bars, and keeps a record of each restoration. Rejected: caching Yahoo's raw rows and restoring on every read (it changes core §9.3's validated-rows-only cache), and a shipped file of measured factors (it misses any new rights issue until someone measures it).

5. **How the note reaches a run: a core `DataSource.data_notes` method (1).** Asked after review pass 1 found that section 2's premise was false: `survivorship_warnings` reaches runs through the core engine (`backtest._data_warnings` reads the Universe protocol), not through the commands. Rejected: the CLI printing notes beside a run (saved runs and paper reports would carry no trail, against decision 3). This is the one core interface change.

## 3. Measurement

All figures were read through the product's own reader (`download_history`, the reported-split reversal in `_factor`) with yfinance 1.7.0, for 2015-01-02 to 2026-09-29 unless stated. The probes and their outputs are in the git-ignored `.superpowers/sdd/2026-10-01-160-refused-dividends/` (`measure.py`, `factor.py`, `spans.py`, `unique.py`, `unique3.py`, `findings.md`).

### 3.1 The amount is wrong, not missing (AC1)

The only refused-day dividend in the three golden windows is BBRI's on 2021-04-06, and no golden run held BBRI that day, so crediting it would move no golden figure. But Yahoo records it as Rp89.91268, scaled by the same factor as BBRI's prices. f = 1.1000190 puts all 584 prices of the recorded refused span (2021-02-01 to 2021-09-07) on the Rp10 tick, and the clean span after it gives exactly 1.0000000. 89.91268 × f = 98.9057, against the Rp98.905659443 BRI announced (Liputan6). Crediting the recorded amount would have paid 9.09% too little. M6's look-back reads BBRI's 2019 and 2020 dividends with the same shortfall.

### 3.2 Who is refused, and what the rule recovers

63 large IDX stocks were read (the union of LQ45 members 2019–2025 as far as known; WSKT returned 404). 43 have no refused day. Under the approved rule (strict tiers, one factor in [1, 2), at least 20 prices, every candidate tried):

| Stock | Refused days | Restored | Factor |
|---|---|---|---|
| BBRI | 1,605 | 1,605 | 1.100019 (2015-01-02 to 2021-09-07) |
| BBTN | 1,926 | 1,926 | 1.1256151 |
| SMGR | 1,917 | 1,917 | 1.0027822 |
| SIDO | 1,619 | 1,619 | 1.0000004 |
| MDKA | 1,463 | 1,463 | 1.025009 from 2018-08-15, 1.0686262 before (two stacked adjustments) |
| MEDC | 1,362 | 1,362 | 1.18125 from 2017-12-08, 1.3124999 before (stacked) |
| BRIS | 1,117 | 1,117 | 1.0253162 |
| ESSA | 510 | 510 | 1.138843 |
| PTPP | 463 | 463 | 1.052105 |
| JSMR | 459 | 459 | 1.002342 |
| WIKA | 447 | 447 | 1.079828 |
| TPIA | 418 | 418 | 1.0187 |
| CTRA | 363 | 363 | 1.0000002 |
| EXCL | 326 | 326 | 1.013797 |
| INCO | 5 | 5 | 1.0143395 (20 prices, 2024-06-10 to 2024-06-14) |
| ARTO | 994 | 266 | 1.2057949 (2020-03-30 to 2021-03-04) and short runs at 1.6028112; the rest breaks into runs of 1–3 days |
| MAPI | 2 | 0 | two single days, no unique factor |
| BRPT | 2,258 | (2,250 at f = 1) | prices need no factor; out of scope (§1.1) |

Three independent checks agree with the recovered factors. BBRI's 2021 dividend matches BRI's announcement to Rp0.00004. SIDO's restored dividends come out as round amounts (25.0, 26.0, 29.0, 15.0, 21.0, 22.0, 27.0, 12.5, 18.9, 15.3), and SMGR's as two-decimal amounts (304.91, 304.92, 135.83, 207.64, 40.33, 188.30, 172.64). And the run boundaries MDKA and MEDC produce fall on single days, where an adjustment would.

Volume is not scaled: all 146 refused days in BBRI's recording have whole volumes, and volume ÷ f is never whole.

### 3.3 Why [1, 2)

- **f ≥ 1.** A rights issue lowers every earlier price. Below 1, f/2 also fits wherever halving moves the prices into the finer tier: one BBRI quarter of 2018 scored 0 at 0.5500095, and a clean control "found" 0.5.
- **f < 2.** The ratios between adjacent ticks (1→2, 2→5, 5→10, 10→25) are all 2 or more, so 2f or 2.5f can fit as well as f. Searched to 4, SMGR passed 1.0028, 2.0056 and 3.0083 (one tier, Rp25), and PTPP, WIKA, EXCL and INCO passed f and 2.5f. A window narrower than the smallest grid ratio is the only one in which "exactly one factor" means something.
- The largest measured factor is 1.6028 (ARTO).

### 3.4 The correction behind decision 1

The first measurement of rule A built its candidates from grid points of each stock's own tier only, so the extra candidates A's tier-below allowance admits were never tried. Tried with every whole rupiah, A makes SMGR non-unique (1.0027822, 1.2033387 and 1.6044516 all fit, because a Rp25-grid price × 1.2 or × 1.6 lands on the Rp10 grid) and CTRA non-unique (1.0000002 and 1.2000002), losing 2,280 days for 94 more ARTO days. Shyden chose B on the corrected numbers. Every rule in this spec is stated as it was measured with the full candidate set.

## 4. The proof

The inference is a pure module, `steadyhand_idx.factor`, with no network, cache or calendar access. Its input is the refused days of one ticker (the days whose reversed prices are not whole rupiah, which `unadjust` already finds), each with its four reversed prices as `Decimal`s, in date order. Flat zero-volume rows on holidays are dropped before it, as today.

### 4.1 Runs

Walk the refused days newest first. The newest day starts a run, and its candidates are found from its open p1 (§4.3). Each older day joins the run when at least one of the run's candidates still fits all four of its prices; the run keeps only those. A day that no candidate fits ends the run and starts the next one. A run left with no candidate at all is a single unprovable day.

### 4.2 The grid for a day

| Days | Tiers (lower bound inclusive, tier chosen by the price itself) | Source |
|---|---|---|
| From 2020-03-13 | Rp1 from 1, Rp2 from 200, Rp5 from 500, Rp10 from 2,000, Rp25 from 5,000 | `tick_sizes.toml` through `ticks.py` (verified) |
| 2016-05-02 to 2020-03-12 | the same five tiers | inference-only, `t-hist.md` §3 ("supported by data") |
| 2014-01-06 to 2016-05-01 | Rp1 from 1, Rp5 from 500, Rp25 from 5,000 | inference-only, `t-hist.md` §3 (news values, unverified) |
| Before 2014-01-06 | none: the day is never provable | |

The two inference-only rows live in `factor.py` as a constant whose comment cites `t-hist.md` §3. They are never read by order validation. A wrong row cannot produce a wrong factor (§4.4); it can only leave a run unproven.

### 4.3 Candidates and fit

A price p fits a factor f when p × f lies within Rp0.01 of a multiple of the tick of the tier that p × f falls in, on that day's grid. The candidates for a run are f = g ÷ p1 for every whole rupiah g with p1 ≤ g < 2·p1, that is, every factor in [1, 2) that puts p1 on a whole rupiah. That set contains every factor any grid could accept, so no rival is missed (§3.4).

### 4.4 Proven

A run is proven when exactly one candidate fits every price in it and it has at least 20 prices (5 days). Anything else (no candidate, two or more, or fewer than 20 prices) leaves every day of the run refused, raising `UnrecoverablePricesError` exactly as today.

The safety claim is that a proven factor is the true one, within [1, 2). Two arguments support it. Thousands of prices each have to land within Rp0.01 of the grid under one parameter. And every alternative in [1, 2) is tried.

### 4.5 Restoring

- **The factor** is the proven candidate refined over the whole run: the mean of (nearest tick ÷ recorded price) over every price in the run, rounded to 7 significant figures (`Decimal`, `ROUND_HALF_EVEN`).
- **A price** becomes the tick multiple nearest to recorded × f: whole rupiah, so a `Money`.
- **A dividend** with an ex-date in the run becomes recorded × split factor × f, quantised to Rp0.0001 (`ROUND_HALF_EVEN`). BBRI 2021: 98.9057.
- **Volume** is unchanged.
- **f = 1** restores nothing: the days stay refused, for whatever other reason they fail (BRPT).

## 5. The source

- **Whole-history inference.** When the reversal finds refused days in a fetched range, `YahooDataSource` fetches that ticker's whole history once, from 2014-01-06 to today in Jakarta, through the same `download_history` and request policy. It builds the runs over all of it. Each run is therefore complete whatever range was asked for, so a day always gets the same factor and the same restored values. That keeps the cache, the golden files and the paper account consistent with each other. The whole history is fetched at most once per ticker per source instance.
- **`bars`** returns restored bars for days in proven runs and raises `UnrecoverablePricesError` for the days left (unproven runs, and days before 2014-01-06), naming them as today.
- **`corporate_actions`** stays calendar-free. Its dividends go through the same runs: a dividend in a proven run is restored (§4.5). A dividend whose ex-date falls in an unproven run is now refused with `UnavailableDaysError` naming that ex-date, because its amount is known to be wrong. M6's look-back then marks the stock incomplete (`history_complete` false, warning `data.dividends.history_refused`), as for any refused look-back (M6 §4.3). Measured impact: ARTO's and MAPI's refused spans from 2016 carry no dividends.
- **`restorations(instrument, start, end) -> tuple[Restoration, ...]`** returns the proven runs overlapping the range. `Restoration` is a frozen dataclass holding `instrument`, `first`, `last`, `factor: Decimal` and `prices: int`.

## 6. The cache

- Restored bars are stored as ordinary validated bars (core §9.3 unchanged).
- A new table `restorations (symbol TEXT, first TEXT, last TEXT, factor TEXT, prices INTEGER, PRIMARY KEY (symbol, first))` records each proven run, so the note can be rebuilt from a cache read without refetching. `CachedDataSource.restorations` reads it.
- **Migration** (the next entry in `cache.py`'s ordered list): it creates the table, and deletes every row of `actions`, `fetched_actions` and `fetched`. Everything is then re-read once under the new rules. That is what corrects a cache that already holds BBRI's Rp89.91268. Bars from refused days were never stored, so no stored bar is wrong, and clearing `fetched` makes the cache fetch the newly restorable days.

## 7. Notes and the lesson

- **Key** `data.prices.restored`, defined in `steadyhand_idx.notes` and checked by the key meta-test (`tests/meta/test_note_keys.py`).
- **Text**, once per stock per proven run overlapping the run's range, look-back included: "`<SYMBOL>`: Yahoo's prices from `<first>` to `<last>` carry an adjustment Yahoo does not report, so steadyhand restored them: every price and dividend in that span is multiplied by `<f>`, proven by `<n>` prices that fit the IDX tick grid at that factor and at no other."
- **Path (decision 5):** the core `DataSource` protocol gains `data_notes(instruments, start, end) -> Sequence[Note]`, and `backtest._data_warnings` includes it over the run's whole window, look-back included, beside `market.universe.survivorship_warnings` (which reaches runs the same way). The note therefore appears wherever data warnings appear: backtests, comparisons, paper reports and saved runs. `YahooDataSource` and `CachedDataSource` build it from their restorations; the test fakes return `()`.
- **Lesson** `idx.restored_prices` (`explains = ["data.prices.restored"]`, `see_also = ["backtest.data_gaps", "idx.ticks"]`). It explains what an unreported adjustment is, why the tick grid proves the factor, and that a restored figure can differ from what Yahoo shows.

## 8. Errors

- Unproven days: `UnrecoverablePricesError`, unchanged, naming every such day in the range.
- A dividend in an unproven run: `UnavailableDaysError` naming the ex-date (new for `corporate_actions`).
- Network failure on the whole-history fetch: `DataUnavailableError` after the request policy's retries, as for any fetch (fail closed).

## 9. Testing

TDD throughout, at 100% branch coverage, with each guard proven by a mutation that turns it red.

### 9.1 Unit and property tests

- **Synthetic runs:** true tick-grid prices scaled by a known f recover exactly that f; f/2 and 2f are rejected by the bounds; a run crossing tiers; two stacked runs split on the right day; fewer than 20 prices stays refused; two fitting candidates stays refused; f = 1 restores nothing; a day before 2014-01-06 is never provable; each grid era is used on its own days.
- **Property (Hypothesis, `ci` profile):** random true grid prices × a random f in [1, 2) either recover that f or stay refused, and never give a different f. This is §4.4's safety claim as a test.
- **The BBRI recording:** f = 1.100019, and the 2021-04-06 dividend restores to 98.9057, within Rp0.0001 of BRI's announced 98.905659443.
- **Restoring:** prices land on ticks as `Money`; dividends are quantised to Rp0.0001; volume is unchanged.
- **Source:** the whole history is fetched once per ticker; a restored day is identical whatever range was asked for; a dividend in an unproven run is refused; `restorations` returns exactly the overlapping runs.
- **Cache migration:** the table exists; actions and both coverage tables are cleared; the migration runs once (idempotent at the version); a restoration survives a round trip.
- **Notes:** one note per stock per run, with the exact text; the key passes the meta-test; the lesson renders and lists the key.

### 9.2 Golden runs and other consequences (intended, each explained in its PR)

- **Golden runs.** Of the golden fixtures (ASII, BBCA, BBRI, TLKM, UNVR), only BBRI has refused days. It becomes priced and tradable from 2017-01-31 to 2021-09-07, so the golden figures change. Each changed figure is re-recorded with its cause stated.
- **M6's look-back** reads BBRI's corrected 2019 and 2020 dividends (each about 10% higher).
- **The M4 income report** shows BBRI's 2021 dividend as 98.9057.

### 9.3 Non-functional

- Inferring the runs of the BBRI recording finishes within a budget the plan measures and pins (perf marker, outside coverage, as the M3b perf test is).
- One extra Yahoo request per affected ticker, at most once per source instance.

## 10. Stories

1. **S1 `factor.py`:** the pure inference (§4): grids, candidates, runs, proof, restoration, with the property test.
2. **S2 the source and the cache:** whole-history inference, restored `bars` and `corporate_actions`, `restorations`, the cache table and migration (§5, §6), and the BBRI recording tests.
3. **S3 notes, lesson and golden runs:** the key, the helper, the commands' warnings, the lesson (§7), the golden re-records (§9.2), and the amendment text in core §9.2 and M6 §4.3.

## 11. Risks

- **A true factor of 2 or more** stays refused, or in a one-tier span is read as f/2. The largest measured factor is 1.6028; the property test bounds the claim to [1, 2).
- **The inference-only grids are unverified.** A wrong row can only leave a run unproven, never prove a wrong factor (§4.2, §4.4).
- **Yahoo changes how it adjusts.** The daily yahoo-shape workflow and the BBRI recording test would show it.
- **The migration re-reads every cached range once.** That is a one-off cost on the first run after upgrading.

## Spec review log

(Review passes are logged here. The loop closes on a pass that finds nothing.)
