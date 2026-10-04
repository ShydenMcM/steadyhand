# steadyhand: Rights issues from an operator file (#203)

**Status:** written 2026-10-04, design approved by Shyden through AskUserQuestion the same day; the written spec awaits his approval (#203 AC1).
**Ticket:** #203 (13 points). **Related:** #200 (its AC7 closes with this ticket's real-data run), #207 (bonus shares, split off by decision 1).

## 1. What this delivers

On a rights issue's ex-date, the engine judges the day's close, and fills at that day's open, against the band around the **theoretical ex-rights price** the exchange uses, not the previous close. Rights issues come from a file the operator supplies, beside the LQ45 members file. A held stock with a rights issue is frozen and flagged with a new note. Without the file, nothing changes.

### 1.1 Out of scope
- **Bonus shares** (BRPT 2022-12-20, SIDO 2021-09-28): a split-class action that Yahoo reports correctly and our split reader refuses. Ticket #207 (decision 1).
- **Modelling the rights themselves**: exercising, selling or valuing the rights a holder receives. The core spec freezes the stock instead (§5 step 2), and this spec keeps that.
- **Total-return price adjustment for rights issues** (M7's `adjusted_closes` covers splits and dividends). A strategy that reads a price series across a rights ex-date sees the drop. M7's spec decides whether it needs more.
- **Finding rights issues automatically.** Yahoo carries ARTO's issue only as an unreported price factor and TPIA's not at all (#203), so its data cannot find every issue.

## 2. Shyden's decisions (2026-10-04)

1. **BRPT and SIDO go to their own ticket** (#207): "Own ticket".
2. **A tie rounds half up, labelled assumed**: "Round half up, assumed". The rounding is to the nearest tick (§3.2); no published case is a tie.
3. **Fills use the same ex-rights reference as the close check**: "Yes, both use TERP".
4. **Rights issues come from a file the operator supplies**, like the LQ45 members file, and the file is never shipped (IDX Terms of Use). Recorded in #203's body.
5. **Design parts 1 and 2 approved as presented**: the file, its loader and its route (§4, §5), then the reference, the freeze, the note and the hint (§6, §7, §8).

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

## 4. The file

`rights_issues.toml`, in the directory of the configured LQ45 members file (`config.lq45_members.parent`). If the file is absent, there are no rights issues; `exclusions.csv` already works this way. steadyhand never ships it. `docs/rights-issues.md` (new) tells an operator what a record needs and where issuers publish the terms, with the same disclaimer guard as `docs/lq45-members.md`.

```toml
schema = 1

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
- an `ex_date` that is not an IDX trading day (`IdxMarketRules.is_trading_day`), or a year the holiday table does not cover (the calendar's `UnsupportedDateError`, re-raised as `DataFileError` naming the record).

## 5. The route

- **Core type** (`steadyhand/types.py`): `RightsIssue(instrument, ex_date, old_shares, rights, price: Money)`, frozen, validated like `Split` (positive integers, a `Money` price above zero). It joins `CorporateAction = Split | CashDividend | RightsIssue | OtherAction`. Its method `theoretical_price(cum_close: Money) -> Fraction` returns the exact TERP and refuses a currency mismatch.
- **Every dispatch on the union learns it.** `ActionHistory` (`view.py`) accepts it as it accepts `OtherAction`, without storing it, so the strategy's view is unchanged. `corporate.apply` freezes on it (§7). `income.py` filters by `isinstance`, so it ignores it. The wrapper below sits outside the cache, so nothing from the operator's file is stored. `cache._action_row` today stores any action that is not a split or a dividend as `"other"` and reads its `description`, so a `RightsIssue` reaching it would fail with an `AttributeError`, far from the cause. It now names the three kinds it stores and refuses anything else with a `TypeError` naming the type (fail closed).
- **Source wrapper** (`steadyhand_idx/rights.py`): `WithRights(source, issues)` implements `DataSource`. `bars` and `data_notes` pass through unchanged. `corporate_actions(instrument, start, end)` returns the inner source's actions plus the file's issues for that stock with ex-dates in the range, in the same date order the protocol promises.
- **Wiring:** `cli._market` wraps the source it is given in `WithRights` when the file exists. Backtest, compare and paper all build their `Market` there, so all three see the same issues.

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
- **Loader errors** exit with the existing `DataFileError` code, naming the record.

## 9. Spec amendments (#203 AC6)

- **Core spec §5 step 1:** "no split explains it" becomes "no split explains it, judged around the theoretical ex-rights price on a rights issue's ex-date". **§5 step 2:** a rights issue from the operator's file (§9.4) is its own action and freezes a held stock with a note, like any other action. **§9.4:** names the optional rights file beside the members file. Review-log pass 17 cites #203 and Shyden's decision.
- **M3 spec §7.4:** the band's reference on a rights issue's ex-date is the rounded TERP, for the close check and for fills, and the existing skips keep priority. Review-log pass 6 cites #203.

## 10. Testing

### 10.1 Unit and property tests (red first, #203 AC3)
- **TERP:** ARTO's and TPIA's exact Fractions; each §3.2 case reproduces IDX's published reference through `IdxMarketRules.round_to_nearest_tick`; an exact tie rounds up (pinned, marked assumed); values either side of the 5,000 tier boundary.
- **Bands:** ARTO's ex-date close 9,500 passes; the edges 8,575 and 11,025 pass and 8,550 and 11,050 stop the run; TPIA 7,850 passes; the edges 7,325 and 9,400 pass and 7,300 and 9,425 stop. Each edge test uses the bar's close and a one-tick step, in one test per case.
- **Fills:** a pending buy of ARTO filling at an open inside the reference band fills, and one at a single tick outside it gets `fill.outside_band`. Without the file, the same buy is judged around 11,100 as today.
- **Priority:** a split and a rights issue on the same day keep the split's skip; a resumed stock with a rights issue is not judged.
- **Minimum price:** a rights issue whose rounded TERP is below the minimum price stops the run with `DataValidationError` naming the reference, for a judged stock and for a resumed one; an exact TERP below 1 is refused by `round_to_nearest_tick` and reaches the run the same way.
- **Held stock:** frozen with the reason text above, the `corporate.rights.frozen` note on that day only, a pending sell gets `fill.frozen`, and a stock not held is not frozen.
- **Loader:** one test per refusal listed in §4, each naming the record, plus ARTO's and TPIA's records loading exactly.
- **Wrapper:** issues are merged in date order with Yahoo's actions; out-of-range issues are left out; bars and notes pass through untouched; the cache never stores an issue.
- **Property:** for any cum close on the tick grid, any positive ratio and any exercise price, both at or above 1, the rounded reference is a valid price on the grid of the tier holding the exact TERP, and lies within half that tier's tick of it. It need not lie between the exercise price and the cum close: an exercise price off the grid (TPIA's 4,082) can sit inside the half tick.
- **Cache:** `_action_row` refuses a `RightsIssue` with a `TypeError` naming it.

### 10.2 Nothing else changes (#203 AC5)
Every golden file is byte-identical. A run without the file, or with issues outside its range, produces the same reports as `develop`, checked on the golden runs. The CLI test for exit 3 shows the new sentence and the file's path.

### 10.3 Real data (#203 AC7)
With ARTO's and TPIA's records in an operator file, `timeline_backtest.py` (git-ignored `.superpowers/sdd/200-unservable/`) runs buy-and-hold over the point-in-time LQ45 from 2021-01-04 to 2025-12-30 to the end. Posted on #203 and on #200, which then closes. The post lists the stocks still reported unservable with their causes (BRPT and SIDO until #207) and the days still refused (#162's volume refusals).

### 10.4 Gates
100% branch coverage on Python 3.12 and 3.13; ruff, format and mypy clean; mutations predicted before running, all red (at least: the reference ignored on a rights day; round down in place of nearest; a tie rounding down; the fill path keeping the previous close; the split skip losing priority; the freeze dropped; the loader accepting a duplicate, a non-trading day, a zero ratio or a bool).

## 11. Delivery

One branch and one PR for #203. The plan is built by extraction, as #160's was: the code first in a scratch chain, the plan rendered from the verified commits and replayed byte-identical. Three tasks: **T1** core (type, `round_to_nearest_tick` in the protocol and every implementation, `_reference`, close check and fills, freeze, note and lesson, spec amendments); **T2** IDX (`IdxMarketRules.round_to_nearest_tick`, the loader, `WithRights`, CLI wiring and hint, `docs/rights-issues.md`); **T3** the real-data run and its posts.

## 12. Risks
- **The tie rule is assumed.** Mitigation: pinned by one test, labelled in the code's docstring and here. One tick of band is the most it can cost.
- **An operator record with wrong terms** moves the reference. The record carries its source, and the run's freeze note prints the terms so they can be checked.
- **A rights issue whose ex-date also carries a dividend:** the TERP uses the cum close as published. No such case is in the 2021-2025 timeline. If one ever fails the band, the run stops naming the stock and day, and the CLI names the file.

## Spec review log
- **Pass 1 (2026-10-04):** every claim about the code was checked against `develop` (`fb879fe`), and every figure was re-run (bands through `IdxMarketRules().price_band`; TERPs as exact fractions). 7 findings, all fixed. (1) §6 said `_fill` sets no reference after refused days; it uses the last earlier bar's close, so `_reference` now only replaces the previous close at each call site, and each site keeps its own skips. (2) §10.1's property claimed the reference lies between the exercise price and the cum close; an exercise price off the tick grid breaks that (4,082 with an exact TERP of 4,083 rounds to 4,080), so the clause is gone. (3) `cache._action_row` stores any unknown action as `"other"` and would fail far from the cause; it now refuses one by name (§5). (4) INET and JSMR were cited as if read, but they are search-result text only; BJBR (verbatim) and INCO carry the "not rounded up" half of the rule (§3.2). (5) A resumed stock skips the close check, yet its fill would meet a below-minimum reference and raise a raw `ValueError`; `_validate` now checks the reference of every stock with an issue that day, judged or not (§6). (6) `round_to_nearest_tick` had no rule below the lowest tier; it refuses (§6). (7) `is_trading_day` raises `UnsupportedDateError` for an uncovered year; the loader re-raises it naming the record (§4).
- **Pass 2 (2026-10-04):** read the whole document top to bottom against pass 1's fixes. 5 findings, all fixed. (1) §4's example record carried an article date that nobody read; it now cites the page alone. (2) §3.1 pointed at a probe in a session scratchpad that will not survive; it now says how to recompute the bands from the table. (3) §1.1 cited §3.1 for Yahoo carrying nothing for TPIA; that fact is #203's. (4) §3.2 said every case was re-derived; INET and JSMR have no inputs in the table, so the sentence names only the ones that were. (5) §10.3 called #162's volume refusals unservable stocks; they are refused days, listed separately.
- **Pass 3 (2026-10-04):** read every line pass 2 changed (§1.1, §3.1, §3.2, §4, §10.3) against the sections they touch, and grepped for placeholders (`TBD`, `TODO`) and for every phrase pass 2 removed. **0 findings. Loop closed.**
