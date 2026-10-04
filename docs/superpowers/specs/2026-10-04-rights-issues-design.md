# steadyhand: Rights issues from an operator file (#203)

**Status:** approved by Shyden 2026-10-04 through AskUserQuestion ("Approve the spec"), after its design (decision 5) and three review passes (#203 AC1). **Amended the same day** (decisions 6 to 9) so that no rights issue can slip through untreated: the file declares the dates it was checked for, every run refuses an unchecked day, and Yahoo's own evidence is checked against the file (§3.3, §4.1, §5.1). The amendment's design was approved as presented ("Approve the design"); the amended spec awaits its review passes and Shyden's approval.
**Ticket:** #203 (13 points). **Related:** #200 (its AC7 closes with the real-data run, §10.3), #207 (bonus shares, split off by decision 1), and a new story for building the 2021-2025 list and that run (§11).

## 1. What this delivers

On a rights issue's ex-date, the engine judges the day's close, and fills at that day's open, against the band around the **theoretical ex-rights price** the exchange uses, not the previous close. Rights issues come from a file the operator supplies, beside the LQ45 members file. A held stock with a rights issue is frozen and flagged with a new note.

**Nothing slips through untreated.** The file is required, and it states the spans of dates it was checked for. A backtest or comparison refuses to start, and a paper account refuses a day, unless every day it runs lies in a checked span (§4.1). Inside them, every place where Yahoo's prices show an unreported adjustment ending must match a listed issue, or the run stops naming the stock and the day (§5.1). A missing or empty file no longer means "no rights issues".

### 1.1 Out of scope
- **Bonus shares** (BRPT 2022-12-20, SIDO 2021-09-28): a split-class action that Yahoo reports correctly and our split reader refuses. Ticket #207 (decision 1).
- **Modelling the rights themselves**: exercising, selling or valuing the rights a holder receives. The core spec freezes the stock instead (§5 step 2), and this spec keeps that.
- **Total-return price adjustment for rights issues** (M7's `adjusted_closes` covers splits and dividends). A strategy that reads a price series across a rights ex-date sees the drop. M7's spec decides whether it needs more.
- **Finding rights issues from prices.** Yahoo rescales the earlier prices of some issues and not others (§3.3), and a small issue's drop looks like an ordinary day, so no price rule can find every issue. The list is the operator's; the product checks it wherever Yahoo gives evidence (§5.1) and refuses every day the list does not claim (§4.1).
- **A `Market` built without the wrapper.** The guarantee belongs to the `steadyhand-idx` commands, which always wrap their source (§5). Code that builds a `Market` directly, as the core golden runs do, has no rights handling: their stored results keep BBRI's 2021-09-08 issue as a market move (§10.2).
- **Days a run only reads.** A strategy's look-back reads history before the run's first day. The engine judges, fills and freezes nothing there, so those days need no checked span, and a rights drop in them reaches a strategy's view as it does today (the total-return bullet above).

## 2. Shyden's decisions (2026-10-04)

1. **BRPT and SIDO go to their own ticket** (#207): "Own ticket".
2. **A tie rounds half up, labelled assumed**: "Round half up, assumed". The rounding is to the nearest tick (§3.2); no published case is a tie.
3. **Fills use the same ex-rights reference as the close check**: "Yes, both use TERP".
4. **Rights issues come from a file the operator supplies**, like the LQ45 members file, and the file is never shipped (IDX Terms of Use). Recorded in #203's body.
5. **Design parts 1 and 2 approved as presented**: the file, its loader and its route (§4, §5), then the reference, the freeze, the note and the hint (§6, §7, §8).

After the spec was approved, a side note pointed out that the file would list only the issues that had stopped a run. Shyden: "i don't like this. make sure nothing can slip through untreated". Measured (§3.3), then asked:

6. **Coverage plus a Yahoo cross-check**: "Coverage + Yahoo check". The file declares its checked spans and a run refuses any day outside them; every adjustment Yahoo ends inside a span must match a listed issue. Rejected: coverage alone (a forgotten BBRI would pass the band unseen), and a drop screen as well (it misses BBRI's 4.60% and stops on real crashes).
7. **A paper account refuses an unchecked day**, as a backtest does: "Refuse, same as backtests". Rejected: running it with a warning, which reopens the gap.
8. **The amendment's design approved as presented**: "Approve the design": the required file and its spans (§4, §4.1), coverage for backtests, comparisons and paper (§4.1), the date-only cross-check (§5.1), the stated limit (§12), and the 2021-2025 list for the real run (§10.3). Moving that run to a new story (§11) came after, while writing this amendment, and is put to Shyden with the amended spec.
9. **OJK's year-end books missing from the Internet Archive are opened in Shyden's own Chrome**, one document per year: "Use Chrome". One book (December 2024) had already been fetched by `curl` with a browser's user agent after ojk.go.id refused `curl`'s own; that was disclosed in the question, and is not repeated.

## 3. Measurement

### 3.1 The two stops (#200's AC7 run, fresh cache, 2026-10-04)

The band check over the point-in-time LQ45 timeline judged 81,971 closes on 1,205 days and refused exactly 2, both rights-issue ex-dates in the regular market:

| Stock | Ex-date | Terms | Cum close | Exact TERP | Reference | Band around it | Close | Band around the cum close |
|---|---|---|---|---|---|---|---|---|
| ARTO | 2021-03-05 | 160 rights per 579 shares at Rp2,350 | 11,100 | 9,205.548… | 9,200 | 8,575-11,025 | 9,500 | 10,325-13,300 |
| TPIA | 2021-08-31 | 10 rights per 47 shares at Rp4,082 | 8,650 | 7,848.596… | 7,850 | 7,325-9,400 | 7,850 | 8,050-10,375 |

The bands are `IdxMarketRules().price_band` on each ex-date, around the reference and around the cum close; anyone can recompute them from this table. The last column reproduces #203's table, which cross-checks the probe. Both closes lie inside the band around the reference. ARTO's cum close is 11,100 only after #160 restores Yahoo's unreported factor 1.205795. TPIA's terms are cited in #203 (bisnis.com, cnbcindonesia), and ARTO's too (emitennews, britama).

### 3.2 How IDX rounds the theoretical price (nearest tick)

Each case with its inputs in the table was re-derived from them: (cum close × old + price × rights) / (old + rights), exact.

| Stock | Cum close | Old : rights | Price | Exact | Tick | IDX's reference | Round down would give |
|---|---|---|---|---|---|---|---|
| INET | (published 472.85) | | | 472.85 | 2 | 472 | 472 |
| JSMR | (published 4,040.54) | | | 4,040.54 | 10 | 4,040 | 4,040 |
| BJBR | 1,415 | 1,153 : 80 | 1,355 | 1,411.107… | 5 | 1,410 | 1,410 |
| INCO | 4,050 | 8,233 : 500 | 3,050 | 3,992.745… | 10 | 3,990 | 3,990 |
| PANI | 13,900 | 50,831 : 3,646 | 12,975 | 13,838.092… | 25 | **13,850** | 13,825 |

PANI rules out rounding down. BJBR and INCO rule out rounding up (1,415 and 4,000). Every case fits the nearest tick. TPIA (§3.1) is a second case where nearest and round-down differ, and its real close equals the nearest. **No case is an exact tie, so half-up at a tie is ASSUMED** (decision 2). A wrong guess moves the band by one tick. Sources: cnbcindonesia (BJBR, quoted verbatim, the strongest); indopremier (PANI, INCO), read through WebFetch, which returns a model's rendering of the page, so each was re-derived from its inputs and agreed; INET (bisnis.com) and JSMR (bareksa) are **search-result text only**, because bisnis.com refused the fetch with 403 and their inputs were not published in the snippet, so they support the rule but are not needed for it. Links in #203's comment of 2026-10-04.

**Which tick:** the tick of the tier holding the exact price. Every tier boundary in `tick_sizes.toml` (200, 500, 2,000, 5,000) is a multiple of the ticks on both sides, so rounding to the lower tier's tick can land on the boundary and still be a valid price. A test pins a value at each side of the 5,000 boundary.

### 3.3 The issues the band check never sees (2026-10-04)

The probes and their outputs are in the git-ignored `.superpowers/sdd/203-detect/` (`boundaries.py`, `all.out`, `findings.md`). `boundaries.py` read the whole history (2014-01-06 to 2026-10-03) of the 72 stocks in any LQ45 list effective from 2020-08-03 to 2025-08-31 (`m7-lq45/timeline.json`). 70 answered; SRIL and WSKT returned 404. It found the runs with the product's own reader (`evidence`, `find_runs`, #160) and printed every run ending from 2020-12-01 to 2025-12-31. A run's last day is the last day Yahoo scaled, so the next trading day is an ex-date. The drop is from the restored cum close to the next close.

| Stock | Span's last day | Next trading day | Yahoo's factor | Drop | Today |
|---|---|---|---|---|---|
| ARTO | 2021-03-04 | 2021-03-05 | 1.205795 | 14.41% | stops the run |
| SMRA | 2021-06-03 | 2021-06-04 | 1.032024 | 4.71% | passes as a market move |
| BBRI | 2021-09-07 | 2021-09-08 | 1.100019 | 4.60% | passes |
| MDKA | 2022-04-13 | 2022-04-14 | 1.025009 | 4.98% | passes |
| SMGR | 2022-12-12 | 2022-12-13 | 1.002782 | -3.70% (a rise) | passes |
| BRIS | 2022-12-13 | 2022-12-14 | 1.025316 | 6.18% | passes |
| BBTN | 2022-12-22 | 2022-12-23 | 1.125615 | 4.27% | passes |
| INCO | 2024-06-14 | 2024-06-19 | 1.014340 | -1.73% (a rise) | passes |

SIDO's run ending 2021-09-27 has factor 1.0000004, rounding noise (`is_noise`), and is its bonus share (#207), not an adjustment. No unproven run ends in the window. **All eight are rights issues**, and each span ends on the regular market's cum date exactly. OJK's year-end lists name ARTO (Bank Jago), SMRA, BBRI, MDKA and INCO (Vale Indonesia); news gives the cum dates of SMGR (2022-12-12, bisnis.com), BRIS (2022-12-13, bisnis.com) and BBTN (2022-12-22, kompas and kontan), from search-result text. **Seven of the eight pass the band today**, so a held stock is not frozen and the drop is booked as a loss.

**Yahoo does not rescale every issue.** TPIA's 2021-08-31 issue (§3.1) leaves no run: its prices are whole across the ex-date (cum close 8,650, ex-date close 7,850), and only the band check found it. So Yahoo's evidence can confirm a list but never complete one.

**Yahoo's factor does not match the terms.** SMGR's terms (cum close 6,750, 14,266,416 rights per 100,000,000 shares at Rp6,600) give a cum close to TERP ratio of 1.002782, Yahoo's factor exactly. BBTN's (cum close 1,405, 32,525,443 per 100,000,000 at Rp1,200) give 1.03714, against Yahoo's 1.125615. A check of the listed terms against Yahoo's factor would therefore stop on a correct record, so §5.1 matches the date alone.

### 3.4 Where a complete list comes from

- **OJK's weekly capital market statistics** (Statistik Mingguan Pasar Modal) carry, every week, the year's rights offerings so far ("Perusahaan yang melakukan Penawaran Umum Terbatas (PUT)/Right Issue tahun …"): company, effective date, shares and value, with the year's count in a summary table. The last book of 2021 lists 45 rows against its own count of 45. The Internet Archive holds the year-end books for 2021 and 2025, and November 2022 and December 2024 (its first week); the December 2022 and 2023 books are not there (the first book of January 2023 already counts 2023). ojk.go.id serves them to a browser (decision 9).
- **IDX's quarterly statistics** ("Right Offerings": ratio, exercise price, trading period, dates) give each issue's terms; the 2021 Q4 book was read. IDX's documents follow the rule recorded on 2026-09-25: the Internet Archive first, then idx.co.id by the earlier technique, noted per document. The company's own announcements and the news give the cum and ex-dates, as for ARTO and TPIA.
- The list is the operator's and is never shipped (decision 4). `docs/rights-issues.md` tells an operator how to build it this way.

## 4. The file

`rights_issues.toml`, in the directory of the configured LQ45 members file (`config.lq45_members.parent`). **The file is required**, as the members file is: a command that builds a market without it exits with `DataFileError` naming the path it looked for and `docs/rights-issues.md`. steadyhand never ships it. `docs/rights-issues.md` (new) tells an operator what a record needs, how to build a complete list (§3.4) and where issuers publish the terms, with the same disclaimer guard as `docs/lq45-members.md`.

```toml
schema = 1

[[checked]]
from = 2021-01-01             # every rights issue from here ...
through = 2025-12-31          # ... to here, of every stock the runs use, is listed below
source = "OJK Statistik Mingguan Pasar Modal, year-end PUT lists 2021-2025; terms from IDX quarterly statistics"

[[issue]]
symbol = "ARTO"
ex_date = 2021-03-05          # the regular market's ex-date
old_shares = 579              # every 579 shares held ...
rights = 160                  # ... receive 160 rights
price = 2350                  # exercise price, whole rupiah
source = "emitennews, https://www.emitennews.com/news/cum-besok-rights-issue-bank-jago-arto-rasio-579160-simak-jadwalnya"
```

**The loader** (`steadyhand_idx/rights.py`, using `_datafile` as the members loader does) fails closed with `DataFileError`, naming the file and the record's position and symbol, on:
- a missing or unknown key at the top level or in a record, or a schema other than 1;
- a symbol that is not four capital letters, or an `ex_date` that is not a TOML date;
- `old_shares`, `rights` or `price` that is not an integer (a TOML bool is not an integer), or that is not positive;
- an empty or blank `source`;
- two records with the same symbol and ex-date;
- an `ex_date` that is not an IDX trading day (`IdxMarketRules.is_trading_day`), or a year the holiday table does not cover (the calendar's `UnsupportedDateError`, re-raised as `DataFileError` naming the record);
- no `[[checked]]` span at all; a span with a missing or unknown key, a `from` or `through` that is not a TOML date, `from` after `through`, or a blank `source`; two spans that overlap (they name the same day);
- an issue whose `ex_date` lies in no checked span: listing it claims the day was checked.

A file with spans and no `[[issue]]` is valid: it says those spans were checked and held no rights issue.

### 4.1 Coverage: every day a run judges is checked

A day is **checked** when it lies in one of the file's spans. Every day the engine judges must be checked:
- **`backtest` and `compare`** check every IDX trading day from the run's first day to its last before anything is fetched. The first one outside every span stops the command with `RightsCoverageError` (exit 2). The message names the file, its spans, and that day.
- **`paper run`** runs each unrun day that is checked, in order, and stops at the first that is not, with the same error and exit code. Each day is saved as it runs, so the days before it are kept, and the run is recorded as stopped with an audit line, as for the existing stops (`paper._STOPS`). The stopped day runs once the file is extended. A paper account therefore needs its file kept ahead of the calendar: IDX announces each issue weeks before its ex-date.
- The look-back before a run's first day needs no span (§1.1).

The check lives in the `steadyhand-idx` commands, which know the run's days; the core engine is unchanged.

## 5. The route

- **Core type** (`steadyhand/types.py`): `RightsIssue(instrument, ex_date, old_shares, rights, price: Money)`, frozen, validated like `Split` (positive integers, a `Money` price above zero). It joins `CorporateAction = Split | CashDividend | RightsIssue | OtherAction`. Its method `theoretical_price(cum_close: Money) -> Fraction` returns the exact TERP and refuses a currency mismatch.
- **Every dispatch on the union learns it.** `ActionHistory` (`view.py`) accepts it as it accepts `OtherAction`, without storing it, so the strategy's view is unchanged. `corporate.apply` freezes on it (§7). `income.py` filters by `isinstance`, so it ignores it. The wrapper below sits outside the cache, so nothing from the operator's file is stored. `cache._action_row` today stores any action that is not a split or a dividend as `"other"` and reads its `description`, so a `RightsIssue` reaching it would fail with an `AttributeError`, far from the cause. It now names the three kinds it stores and refuses anything else with a `TypeError` naming the type (fail closed).
- **Source wrapper** (`steadyhand_idx/rights.py`): `WithRights(source, file, rules)` implements `DataSource`, where `source` is a `RestoringSource` (`cache.py`: a source that also reports its restorations) and `file` is the loaded rights file. `bars` and `data_notes` pass through unchanged. `corporate_actions(instrument, start, end)` runs the cross-check (§5.1), then returns the inner source's actions plus the file's issues for that stock with ex-dates in the range, in the same date order the protocol promises.
- **Wiring:** `cli._market` always loads the file and wraps the source it is given in `WithRights`. Backtest, compare and paper all build their `Market` there, so all three see the same issues and the same checks. The CLI test helper that builds the matching backtest (`cli_world.golden_backtest`) builds its `Market` the same way, so a paper run and its reference backtest still agree (§10.2).

### 5.1 The cross-check: Yahoo's evidence against the file

The cache stores, for every range it fetched, the proven runs (`Restoration`: first day, last day, factor) that overlap it (#160 spec §6). A run that is not rounding noise (`Restoration.noise` false) is an adjustment Yahoo applied and did not report, and its **ex-date** is the first IDX trading day after its last day (§3.3).

In `corporate_actions(instrument, start, end)`, `WithRights` reads from the **trading day before `start`** to `end`, because a run that ends the day before an ex-date on `start` does not overlap the range itself (`restorations(BBRI, 2021-09-08, 2021-09-30)` is empty today, `tests/idx/test_yahoo.py`). It asks the inner source for that wider range's actions first and its restorations second: `CachedDataSource.restorations` is a cache read, never a fetch, and the actions read is what fetches a missing range and stores the restorations overlapping it (`cache.py`). It then keeps only the actions from `start` to `end`. For every ex-date found that lies from `start` to `end` and in a checked span, the file must list an issue for that stock on that day. If it does not, `UnlistedRightsIssueError` stops the run (exit 3), naming the stock, the ex-date, the span Yahoo adjusted and its factor, and the file to add the issue to.

- The match is on the date alone. Yahoo's factor is not compared with the listed terms, because it does not always follow them (BBTN, §3.3).
- An ex-date outside every checked span is not judged: no run judges that day (§4.1), and the file makes no claim about it.
- An issue the file lists where Yahoo shows nothing is normal (TPIA) and is used as listed.
- Runs that #160 could not prove are not stored, so they are not checked. Their days are already refused as unpriced. No such run ends inside 2021-2025 for any of the 70 stocks (§3.3); §12 records the gap.
- `UnlistedRightsIssueError` is not a `DataUnavailableError`, so no caller can mistake it for a refused day or an unservable stock (#200, #202): the run stops.

## 6. The reference price

One engine function, `_reference(instrument, previous_close, inputs, rules) -> Money`, gives the price a band is judged around: the rounded TERP, `rules.round_to_nearest_tick(instrument, issue.theoretical_price(previous_close), inputs.day)`, when a `RightsIssue` for the stock is dated today, and `previous_close` otherwise.

Both call sites keep their existing rules for when there is a reference at all, and only replace "the previous close" with `_reference(…)`:
- **`_validate`** (the close check) still skips a stock with no earlier bar, a stock in `inputs.resumed`, and a stock with a `Split` dated today. Those skips keep priority over a rights issue.
- **`_fill`** still builds `Opening.references` from the last earlier bar's close for each stock with a pending order. Each entry now passes through `_reference`. A split's ex-date needs nothing new, because `corporate.apply` has already cancelled that stock's pending orders (`corporate.split.order_cancelled`).

So the close check and the fill band use one reference on a rights ex-date and cannot disagree.

**New `MarketRules` method:** `round_to_nearest_tick(instrument, price: Fraction, on) -> Money`. It rounds to the nearest valid tick, a tie up (decision 2), using the tick of the tier holding `price` (§3.2). `IdxMarketRules` implements it from `tick_sizes.toml`. Every other `MarketRules` in the repo (the perf test's fixed rules and the test doubles) gains it. The engine stays free of IDX.

**A reference below the minimum price:** `price_band` already refuses one with `ValueError` (`rules.py`). `_validate` therefore checks every stock with a `RightsIssue` today and an earlier bar, **whether or not it judges that stock's close** (a resumed stock or a split's ex-date included): it asks `price_band` for the rounded TERP and turns a `ValueError` into `DataValidationError` naming the stock, the day and the reference. The run stops with exit 3, not a traceback. `run_day` runs `_validate` before corporate actions and fills (`engine.py`), so no fill ever meets such a reference.

**`round_to_nearest_tick` below the lowest tier:** a price below the tick table's lowest `from_price` (1) has no tick, and is refused with `ValueError` naming it. `_validate` turns that into `DataValidationError` the same way.

## 7. A held stock

A `RightsIssue` on a stock held at the previous close freezes it for the rest of the run, through the path `OtherAction` already uses (`_Actions.freeze`, `DayReport.frozen`, the paper page's "Frozen stocks"). The frozen reason reads `rights issue: <rights> per <old_shares> at <price>`.

It also adds a warning note **`corporate.rights.frozen`** (new key in `steadyhand/notes.py`) to the day's report, naming the stock, the ex-date and the terms. Its lesson (`steadyhand/training/lessons/en/`) lands in the same story and is market-neutral, as the lesson guard requires (no "Rp", no "IDX"). It explains what a rights issue does to the price, why the run freezes the stock, and what the operator does next. A stock not held is not frozen: it trades on the ex-date inside the band around the reference.

## 8. Errors and messages

- **An issue the file lacks:** the close check is unchanged and still raises `DataValidationError` around the previous close. The CLI's stop message for `DataValidationError` (exit 3) adds one sentence: if that day is a rights issue's ex-date, add the issue to `<path of rights_issues.toml>`. The engine's own message is unchanged, so core stays IDX-free (#203 AC5).
- **Loader errors** exit with the existing `DataFileError` code, naming the record. A missing file is one of them (§4).
- **A day outside every checked span:** `RightsCoverageError` (new, `steadyhand_idx/rights.py`), exit 2, a row in `cli.EXIT_CODES` beside `UniverseCoverageError`, which refuses a run the members file does not cover in the same way (§4.1).
- **An adjustment Yahoo ended where the file lists nothing:** `UnlistedRightsIssueError` (new, same module), exit 3, a row beside `DataValidationError` (§5.1). In paper it is a stop like the others, recorded with its audit line.

## 9. Spec amendments (#203 AC6)

- **Core spec §5 step 1:** "no split explains it" becomes "no split explains it, judged around the theoretical ex-rights price on a rights issue's ex-date". **§5 step 2:** a rights issue from the operator's file (§9.4) is its own action and freezes a held stock with a note, like any other action. **§9.4:** names the required rights file beside the members file, its checked spans, and the two refusals (§4.1, §5.1). Review-log pass 17 cites #203 and Shyden's decision.
- **M3 spec §7.4:** the band's reference on a rights issue's ex-date is the rounded TERP, for the close check and for fills, and the existing skips keep priority. Review-log pass 6 cites #203.

## 10. Testing

### 10.1 Unit and property tests (red first, #203 AC3)
- **TERP:** ARTO's and TPIA's exact Fractions; each §3.2 case reproduces IDX's published reference through `IdxMarketRules.round_to_nearest_tick`; an exact tie rounds up (pinned, marked assumed); values either side of the 5,000 tier boundary.
- **Bands:** ARTO's ex-date close 9,500 passes; the edges 8,575 and 11,025 pass and 8,550 and 11,050 stop the run; TPIA 7,850 passes; the edges 7,325 and 9,400 pass and 7,300 and 9,425 stop. Each edge test uses the bar's close and a one-tick step, in one test per case.
- **Fills:** a pending buy of ARTO filling at an open inside the reference band fills, and one at a single tick outside it gets `fill.outside_band`. Without the file, the same buy is judged around 11,100 as today.
- **Priority:** a split and a rights issue on the same day keep the split's skip; a resumed stock with a rights issue is not judged.
- **Minimum price:** a rights issue whose rounded TERP is below the minimum price stops the run with `DataValidationError` naming the reference, for a judged stock and for a resumed one; an exact TERP below 1 is refused by `round_to_nearest_tick` and reaches the run the same way.
- **Held stock:** frozen with the reason text above, the `corporate.rights.frozen` note on that day only, a pending sell gets `fill.frozen`, and a stock not held is not frozen.
- **Loader:** one test per refusal listed in §4, each naming the record or span, plus ARTO's and TPIA's records loading exactly, a file with spans and no issues loading as "checked, none", and a missing file refused naming the path and the doc.
- **Coverage (§4.1):** a backtest whose first day, last day, or one middle day lies outside every span is refused with exit 2 naming that day, one test per case; adjacent spans (one ends the day before the next begins) cover the join; a span ending on a weekend before the run's last trading day still covers it; the look-back is not checked. Paper: an account with three unrun days whose last is unchecked runs two, saves them, records the stop with its audit line and exits 2; after the span is extended, the next run runs the third.
- **Cross-check (§5.1)**, on the recorded BBRI history (restored span 2014-01-06 to 2021-09-07): a range across 2021-09-08 with no BBRI issue stops with exit 3 naming BBRI, 2021-09-08, the span and factor 1.100019; with the issue listed it passes; a range **starting on** 2021-09-08 still stops (the previous-trading-day lookup); an issue listed on the cum date 2021-09-07 instead stops; a span ending outside every checked span, a noise run, and a range ending before the ex-date pass. The ex-date across holidays uses the trading calendar (INCO: last scaled day 2024-06-14, ex-date 2024-06-19).
- **Wrapper:** issues are merged in date order with Yahoo's actions; out-of-range issues are left out; bars and notes pass through untouched; the cache never stores an issue.
- **Property:** for any cum close on the tick grid, any positive ratio and any exercise price, both at or above 1, the rounded reference is a valid price on the grid of the tier holding the exact TERP, and lies within half that tier's tick of it. It need not lie between the exercise price and the cum close: an exercise price off the grid (TPIA's 4,082) can sit inside the half tick.
- **Cache:** `_action_row` refuses a `RightsIssue` with a `TypeError` naming it.

### 10.2 What changes, and what does not (#203 AC5)
Every golden file is byte-identical: the golden runs build their `Market` without the wrapper (§1.1). The CLI tests change on purpose. Their recorded window (2021-02-01 to 2022-04-29) holds BBRI's 2021-09-08 issue, which the cross-check now demands, so their operator files gain a span covering the window and BBRI's issue with its published terms and source. A CLI run that holds BBRI then freezes it from 2021-09-08 with the `corporate.rights.frozen` note, and the matching reference backtest (`golden_backtest`) is built through the same wrapper, so paper and backtest still agree. Each changed CLI expectation is explained in the PR. The CLI test for exit 3 shows the new sentence and the file's path.

### 10.3 Real data (#203 AC7, done in the new story, §11)
The operator file lists every rights issue, 2021-01-01 to 2025-12-31, by every stock in the point-in-time LQ45 timeline, built as §3.4 says, with one span and its sources. Each year's OJK list is read in full and its row count checked against OJK's own count, and the eight Yahoo ex-dates of §3.3 are all present. `timeline_backtest.py` (git-ignored `.superpowers/sdd/200-unservable/`) then runs buy-and-hold over that timeline from 2021-01-04 to 2025-12-30 to the end, through `WithRights`. The post goes on #203 and #200, which then closes. It lists the stocks frozen by a rights issue, the stocks still reported unservable with their causes (BRPT and SIDO until #207), and the days still refused (#162's volume refusals).

### 10.4 Gates
100% branch coverage on Python 3.12 and 3.13; ruff, format and mypy clean; mutations predicted before running, all red (at least: the reference ignored on a rights day; round down in place of nearest; a tie rounding down; the fill path keeping the previous close; the split skip losing priority; the freeze dropped; the loader accepting a duplicate, a non-trading day, a zero ratio or a bool; the loader accepting a missing file, overlapping spans or an issue outside every span; the coverage check skipping the run's last day; paper running an unchecked day; the cross-check dropped; restorations asked from `start` instead of the trading day before it; noise runs judged; the ex-date taken as the calendar day after the span instead of the trading day; `UnlistedRightsIssueError` made a `DataUnavailableError`).

## 11. Delivery

One branch and one PR for #203. The plan is built by extraction, as #160's was: the code first in a scratch chain, the plan rendered from the verified commits and replayed byte-identical. Two tasks: **T1** core (type, `round_to_nearest_tick` in the protocol and every implementation, `_reference`, close check and fills, freeze, note and lesson, spec amendments); **T2** IDX (`IdxMarketRules.round_to_nearest_tick`, the loader with its spans, `WithRights` with the cross-check, the coverage check in `backtest`, `compare` and `paper run`, the two errors and their exit codes, CLI wiring and hint, the CLI fixtures' file, `docs/rights-issues.md`).

**The real-data run moves to a new story**, because building the list is research of its own: five years of OJK lists, the terms of each issue, and the Chrome downloads of decision 9. That story builds the 2021-2025 file (§10.3), runs #200's AC7 with it, and posts the result. It is filed with its acceptance criteria and an estimate when this amendment is approved, and #203's AC7 points to it.

## 12. Risks
- **The tie rule is assumed.** Mitigation: pinned by one test, labelled in the code's docstring and here. One tick of band is the most it can cost.
- **An operator record with wrong terms** moves the reference. The record carries its source, and the run's freeze note prints the terms so they can be checked.
- **A list that misses an issue Yahoo did not rescale** (TPIA's kind) passes the cross-check, and passes the band too if its drop is small. Mitigation: the list is built from OJK's complete yearly lists, each year's count checked against OJK's own (§10.3), and the file's span is the operator's signed claim, with its source.
- **An unreported adjustment #160 could not prove** is not stored, so the cross-check cannot see where it ends (§5.1). Measured: none ends inside 2021-2025 for the 70 stocks. Its days are refused as unpriced, so the band never judges them; the day after is a resumed stock, which the band skips.
- **A paper account stops when its file runs out** (§4.1). That is the intent (decision 7). The message names the file and the date, and IDX announces issues weeks ahead, so the file can stay ahead of the calendar.
- **A rights issue whose ex-date also carries a dividend:** the TERP uses the cum close as published. No such case is in the 2021-2025 timeline. If one ever fails the band, the run stops naming the stock and day, and the CLI names the file.

## Spec review log
- **Pass 1 (2026-10-04):** every claim about the code was checked against `develop` (`fb879fe`), and every figure was re-run (bands through `IdxMarketRules().price_band`; TERPs as exact fractions). 7 findings, all fixed. (1) §6 said `_fill` sets no reference after refused days; it uses the last earlier bar's close, so `_reference` now only replaces the previous close at each call site, and each site keeps its own skips. (2) §10.1's property claimed the reference lies between the exercise price and the cum close; an exercise price off the tick grid breaks that (4,082 with an exact TERP of 4,083 rounds to 4,080), so the clause is gone. (3) `cache._action_row` stores any unknown action as `"other"` and would fail far from the cause; it now refuses one by name (§5). (4) INET and JSMR were cited as if read, but they are search-result text only; BJBR (verbatim) and INCO carry the "not rounded up" half of the rule (§3.2). (5) A resumed stock skips the close check, yet its fill would meet a below-minimum reference and raise a raw `ValueError`; `_validate` now checks the reference of every stock with an issue that day, judged or not (§6). (6) `round_to_nearest_tick` had no rule below the lowest tier; it refuses (§6). (7) `is_trading_day` raises `UnsupportedDateError` for an uncovered year; the loader re-raises it naming the record (§4).
- **Pass 2 (2026-10-04):** read the whole document top to bottom against pass 1's fixes. 5 findings, all fixed. (1) §4's example record carried an article date that nobody read; it now cites the page alone. (2) §3.1 pointed at a probe in a session scratchpad that will not survive; it now says how to recompute the bands from the table. (3) §1.1 cited §3.1 for Yahoo carrying nothing for TPIA; that fact is #203's. (4) §3.2 said every case was re-derived; INET and JSMR have no inputs in the table, so the sentence names only the ones that were. (5) §10.3 called #162's volume refusals unservable stocks; they are refused days, listed separately.
- **Pass 3 (2026-10-04):** read every line pass 2 changed (§1.1, §3.1, §3.2, §4, §10.3) against the sections they touch, and grepped for placeholders (`TBD`, `TODO`) and for every phrase pass 2 removed. **0 findings. Loop closed.**
