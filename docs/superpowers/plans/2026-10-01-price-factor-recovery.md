# #160 Recovering Yahoo's Unreported Price Factor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the prices and dividends Yahoo scales by a factor it does not report, when the IDX tick grid proves that factor, instead of refusing every such day. BBRI's prices up to its 2021 rights issue become tradable, and its 2021 dividend is credited at BRI's announced Rp98.9057 a share instead of Yahoo's Rp89.91268. Every backtest that uses a restored price says so in its warnings, and a lesson explains why.

**Architecture:** A pure proof module, `steadyhand_idx.factor` (S1): rows with a price off whole rupiah after the reported splits are reversed form runs, newest first; a run is proven when exactly one factor from 1 to below 2 puts all of at least 20 prices on their day's tick grid. The source and the cache (S2): `YahooDataSource` reads a ticker's whole history once when a range has such a price, restores the bars and dividends of every proven run, refuses the rest as before, and reports its runs as `Restoration`s; `BarCache` stores them in a new `restorations` table, and its migration clears the stored actions and ranges so everything is read again under the new rules. The notes and the lesson (S3): the core `DataSource` protocol gains `data_notes`, which `backtest._data_warnings` includes over the whole window, look-back included, so every restored run gets one `data.prices.restored` warning, explained by the lesson `idx.restored_prices`.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md` (the "#160 spec"), on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec"), `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md` (the "M3 spec"), `docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md` (the "M6 spec") and `docs/superpowers/specs/2026-09-27-training-design.md` (the "T1 spec"). Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how each claim was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2); `steadyhand-idx` keeps its runtime dependencies at `steadyhand` and `yfinance` (M5 §3.1).
- Fail closed (core §9.2): a day no proven run covers is refused with `UnrecoverablePricesError` naming it, exactly as before #160, and a dividend in an unproven run is refused, because its amount is known to be wrong (#160 §5, §8).
- `factor.py` is pure: no network, cache or calendar (#160 §4). Its inference-only grids are never read by order validation, which reads `tick_sizes.toml` alone (#160 §4.2).
- Money stays exact: a restored price is a whole-rupiah `Money`, a restored dividend a `Decimal` quantised to Rp0.0001 with `ROUND_HALF_EVEN`, a factor a `Decimal` to 7 significant figures (#160 §4.5). No float reaches a figure.
- Every note a report carries is a `Note` built from a key constant, and every key has a lesson in the same story (T1 §1.1).
- Tests call steadyhand's own code with real values and recorded data: no stub or mock of steadyhand's code (M5 §9.1). The golden runs go through the real `YahooDataSource`, `CachedDataSource` and `IdxMarketRules`, over BBRI's whole recorded history.
- Every `*Error` a task raises is raised by a test that asserts its message. A `match=` holding a regex metacharacter is a raw string (ruff RUF043).
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A function that already existed keeps its old body in the red phase, and a class that already existed keeps its old fields; only new names are stubs, with three exceptions: a new `__post_init__` is stubbed as `return`, a new function the module calls at import keeps its body, and a method a story renames keeps its old definition beside the new stub. A test module that builds a pre-existing class with its new field fails to collect in the red phase, so the red run passes `--continue-on-collection-errors`.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code.
- Test file basenames are unique across `tests/`. English only. The phrase "robot trading" never appears (core §1.3).
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **Float noise at the first price** (TINS 2014, #160 §3.5). Expected: candidates start at the whole rupiah nearest p1, so f = 1 stays a candidate beside f ≈ 2 and the run stays refused rather than "proving" 1.9999995. Pinned in Task 1 (`test_upward_noise_at_the_first_price_keeps_one_as_a_candidate`; mutation M373) and by the property test over noisy prices.
2. **A dividend whose ex-date falls in an unproven run.** Expected: `corporate_actions` refuses it with `UnprovenDividendsError` (an `UnavailableDaysError`) naming the ex-date, so M6's look-back marks the stock incomplete instead of reading a scaled amount. Pinned in Task 2 (`test_a_dividend_in_an_unproven_run_is_refused_naming_its_ex_date`; mutation M389). Measured on the 62 stocks: only CTRA's four dividends of 2014 to 2016 fall in an unproven run (scope decision 19).
3. **A row whose split-reversed volume is not whole shares, inside a proven run.** Expected: its prices still count as evidence, but the day stays refused (#162). Pinned in Task 2 (`test_a_row_whose_volume_is_not_whole_stays_refused_though_its_prices_count`, `test_bbri_s_golden_years_are_restored_except_where_a_volume_is_not_whole`; mutation M393).
4. **A cache that already holds BBRI's scaled Rp89.91268.** Expected: migration 3 clears `actions`, `fetched_actions` and `fetched`, so the first run after upgrading reads everything again under the new rules. Pinned in Task 2 (`test_the_restorations_migration_reads_every_range_again`; mutations M397, M398).
5. **A backtest ending today, with a run met only in today's bar.** Expected: today's bar is never stored, so `CachedDataSource.data_notes` adds the upstream's notes to the stored ones, each once. Pinned in Task 3 (`test_a_run_read_only_in_today_s_bar_still_has_its_note`; mutation M410); "each once" by `test_the_cached_source_s_notes_come_from_its_stored_restorations` (mutation M409).
6. **The notes cost no request.** Expected: `YahooDataSource.data_notes` reads only the runs already inferred, so a backtest makes no extra Yahoo request for its warnings (#160 §9.3). Pinned in Task 3 (`test_data_notes_name_the_runs_already_read_and_never_ask_yahoo`; mutations M407, M408).
7. **A true factor just below 2 under downward float noise** (scope decision 19). Expected: the window reaches 2·(p1 + Rp0.01), so the true factor is tried beside f = 1 and the run is refused rather than "proven" at 1, which would restore prices at half their value. Pinned in Task 1 (`test_downward_noise_near_a_factor_of_two_keeps_the_true_factor_a_candidate`, and the property's `@example`; mutation M374).
8. **Yahoo's unfinished day** (scope decision 20). Expected: a row with no price is no bar, so the whole-history read to today goes on; a dividend on such a row is refused, not lost. Pinned in Task 2 (`test_a_row_yahoo_gives_no_price_is_no_bar`, `test_a_dividend_on_a_row_with_no_price_is_refused`; mutations M395, M396).

## Scope decisions (read before starting)

1. **`unadjust(history, instrument, calendar, span, runs=())`** takes the range as one `span` tuple, as `BarCache.store` does: a sixth argument breaks ruff's PLR0913, which the repository suppresses nowhere in package code. Its 16 call sites change with it.
2. **Only rows with a price off whole rupiah are restored** in a proven run's span. A row whose prices are whole keeps its stored value, so the cache never meets a conflict. The whole history is read when any row in the asked range has such a price.
3. **`UnprovenDividendsError(UnavailableDaysError)`** names the ex-dates of the dividends in unproven runs (#160 §5, §8).
4. **`CachedDataSource(upstream: RestoringSource)`**: an idx `Protocol`, a `DataSource` with `restorations`, which the cache stores with each range it fetches.
5. **`record_golden.replay(download)` is the one replay source.** The golden runs, the CLI world and the tests build their Yahoo source with it. `WHOLE_RECORDED` (2026-10-01) is BBRI's whole-history recording day, which the replay passes as `today`.
6. **`YahooDataSource._request` is split from `_fetch`**, so the whole-history read never replaces the range `_fetch` keeps for `bars` and `corporate_actions` to share.
7. **M6's cache upgrade test is pinned to `MIGRATIONS[:2]`**; migration 3 has its own test.
8. **The golden window meets a restoration, not a refusal.** Refusals stay covered by `tests/engine/test_backtest.py` (refused days) and by `test_yahoo.py` calling `unadjust` directly.
9. **The paper CLI tests that showed a cut or a skipped order now use tight settings** (`max_weight` 0.19): with BBRI tradable, the golden settings never block an order in the replayed year (scanned: no cut or skip line, 12 queued). `FILL_CASH_CUT` stays covered by `tests/engine/test_simulated_broker.py`.
10. **`test_reports.py` covers the Markdown warnings branch with an explicit warned run**, since S2's golden run carries no warning; S3's carries one.
11. **The live Yahoo test starts at the calendar's first day**, the start of the whole-history recording.
12. **The proof's performance is its own perf test** (`tests/perf/test_factor_performance.py`), outside coverage, as M3b's is. Its budget is in **Measured performance**.
13. **`Restoration` is defined in Task 2**, where a source first returns one; its `noise` and `note` come in Task 3, where the note is first read.
14. **`YahooDataSource.data_notes` never fetches**: it reads the runs already inferred. Every range a backtest reads has been read by the time `_data_warnings` runs, and a range that read no run had no price to restore.
15. **`CachedDataSource.data_notes`** is the notes of the stored restorations, then the upstream's, each once (`dict.fromkeys`): today's bar is never stored, so a run met only there would otherwise lose its note.
16. **The warnings' order** is the universe's, then the source's notes, then refused days, then refused look-backs. `_stocks(members)` gives the stocks fetched to both `_fetch` and `_data_warnings`.
17. **The price count in a note has a thousands separator** ("proven by 7,380 prices").
18. **The amendments** to core §4.3 and §9.2 and M6 §4.3 are made in Task 3, each with a line in that spec's review log, as M6 amended the core spec.
19. **The window's upper edge** (Shyden, 2026-10-02; amends #160 §4.3 and the measured claim in §5). The candidates run from the whole rupiah nearest p1 up to, not including, 2·(p1 + Rp0.01), where the approved spec stopped below 2·p1. The property test found that a true factor just below 2 with downward float noise put 2·p1 below the true price, so f = 1 was the only candidate and was "proven", restoring prices at half their value (the mirror of the TINS case at the lower edge, §3.5). A recorded price may sit up to `FIT_TOLERANCE` off the true one, the slack every fit already allows, so the true factor is now always tried. 20,000 random examples pass on the fix (177 s) and fail on the old window. Measured through steadyhand's reader on all 62 stocks, one run changes: CTRA's noise run from 2014-01-06 to 2016-07-12 (603 days) is refused, because doubling its prices fits the grid too. Its 127 trading days in 2016 stay refused, as before #160, and its four dividends there (2014-07-04, 2015-07-08, 2015-09-30, 2016-06-23) are refused as in an unproven run, so a look-back reaching mid-2016 marks CTRA incomplete. §5's "no dividend falls in an unproven run" no longer holds for CTRA.
20. **A row Yahoo gives with no price is no bar** (found while measuring decision 19). Yahoo's unfinished day has a NaN close (all 62 stocks on 2026-10-01), and comparing a NaN `Decimal` raises, so the whole-history read, which runs to today, stopped every such stock during the trading day. `history_from_frames` leaves out a row whose open, high, low, close or volume is NaN, as a day Yahoo does not show, and refuses one that carries a dividend, which would otherwise be lost with it.
21. **The spec's "days with an unwhole price" are the proof's evidence** (found in plan review pass 3): days with a price off whole rupiah, leaving out a flat row with no volume, which repeats an earlier close (§3.6). BBRI's 1,845 in #160 §3.2 and its 1,103 in §9.2 are such counts; counting every day with a price off whole rupiah gives 1,914 and 1,160 (69 and 57 flat days). The tests assert the evidence counts and their comments say so.

## Measured performance (#160 §9.3)

Measured in the scratch build (`tests/perf/test_factor_performance.py`), reading the evidence of BBRI's whole recording (3,135 days from 2014-01-06, 1,845 of them evidence: a price off whole rupiah on a day that is not a flat row with no volume, scope decision 21) and finding its one run, at factor 1.100019:

| Measurement | Measured | Budget |
|---|---|---|
| `find_runs(evidence(history))` over the whole recording | 0.024 to 0.028 s, five times in a row, at a load of 12 on six cores | 1 s |

The machine was not idle: other sessions held the load at about 12. The budget leaves about thirty-five times the slowest measurement for a slower CI runner. The test times only the proof, not reading the recording from disk, which pytest's own timing (0.04 s for the whole test) includes. Every other performance budget is unchanged, and each story's gate runs them. Task 2 also corrects M6's performance docstring, which said "four cores": the machine has six (`sysctl hw.physicalcpu`).

## File map

| File | Task | Responsibility |
|---|---|---|
| `.../steadyhand_idx/factor.py` | 1, 2, 3 | The proof: grids, candidates, runs, refining, restoring; `Restoration`, its note |
| `.../steadyhand_idx/yahoo.py` | 2, 3 | Whole-history inference, restored bars and dividends, `restorations`, `data_notes` |
| `.../steadyhand_idx/cache.py` | 2, 3 | The `restorations` table and migration 3; `RestoringSource`; `data_notes` |
| `.../steadyhand_idx/notes.py`, `training/lessons/en/idx.restored_prices.md` | 3 | `DATA_PRICES_RESTORED` and its lesson |
| `.../steadyhand/data.py`, `.../steadyhand/backtest.py` | 3 | `DataSource.data_notes`; the source's notes in a run's data warnings |
| `scripts/record_golden.py`, `tests/fixtures/golden/*.json` | 2, 3 | The one replay source; the golden runs, re-recorded |
| `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`, `…/2026-09-30-m6-strategy-wave-1-design.md` | 3 | The amendments |
| `tests/idx/*`, `tests/engine/*`, `tests/cli/*`, `tests/golden/*`, `tests/perf/*` | 1–3 | The tests of each |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | This plan, BBRI's whole recording and the stories | `docs/160-plan` |
| 1 | #160 S1 The price-factor proof | `feat/160-s1-factor` |
| 2 | #160 S2 Restored prices and dividends in the source and the cache | `feat/160-s2-source-cache` |
| 3 | #160 S3 A note for each restored run, and its lesson | `feat/160-s3-notes` |

Stories merge in order: each one's code builds on the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Merge without asking: Shyden's standing rule of 2026-09-27 covers every green PR into `develop` (never `main`). Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: This plan, BBRI's whole recording and the stories

On `docs/160-plan`, whose PR carries this plan, `HANDOVER.md` and `tests/fixtures/yahoo/BBRI.JK_2014-01-06_2026-10-01.json`: BBRI's whole Yahoo history from 2014-01-06, recorded on 2026-10-01 (SHA-256 `edb9482492b5a0e97feccbe60609f28ef505d8952da387f525e0ed4c4e8dc4d0`). Task 2's tests read it, and it agrees row for row with BBRI's three older recordings wherever they overlap (`test_bbri_s_whole_recording_agrees_with_every_older_recording`).

- [ ] **Step 1: File the stories.** Create one issue per task 1–3, titled as in the Stories table, whose body is that task's acceptance criteria and `Refs #160`. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 2: Open the PR** from `docs/160-plan` into `develop` (`Refs #160`), and merge it as **Merging a story** says.

---

### Task 1: #160 S1 The price-factor proof

**Acceptance criteria (story text):**
1. `steadyhand_idx.factor` is pure (no network, cache or calendar). `Grid` gives each day's tiers: `tick_sizes.toml` from its first verified day, the five-tier inference grid from 2016-05-02, the three-tier one from 2014-01-06, and none before (#160 §4.2); a price takes its own tier's tick, and the first tier's below it.
2. `candidates(row, grid)` are g / p1 for every whole rupiah g from the one nearest the open p1 up to, not including, 2·(p1 + Rp0.01), that put all four prices within Rp0.01 of a tick (scope decision 19). Float noise at p1 keeps the true factor a candidate at both edges: f = 1 under upward noise (the TINS case) and a factor just below 2 under downward noise.
3. `find_runs(rows, grid)` walks newest first: an older row joins while one of the run's candidates still fits it, and the run keeps those. A run is proven when exactly one candidate fits and it has at least 20 prices; its factor is the mean of (nearest tick / recorded price), to 7 significant figures. Pinned: a known factor recovered exactly, f/2 and 2f outside the window, two candidates refused, fewer than 20 prices refused, stacked runs split on the right day, a day no candidate fits alone, a day before 2014-01-06 never provable, each grid era on its own days, a run crossing tiers.
4. `restore_price` is the tick multiple nearest recorded × f, as a `Money`; `restore_dividend` is recorded × f quantised to Rp0.0001; `is_noise(f)` is whether f rounds to 1.000000.
5. A property (Hypothesis, `ci` profile): random true grid prices, with or without float noise up to Rp0.001, scaled by a random f in [1, 2), recover that f or stay refused, and never give another; the counterexample that found scope decision 19 is pinned as an `@example`.
6. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M373–M385 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand_idx/factor.py`, `tests/idx/test_factor.py`

**Interfaces:**
- Consumes: `steadyhand_idx.ticks` (`TICKS_FILE`, `TickRow`, `TickTier`, `parse_ticks`), `steadyhand_idx._datafile` (`Dated`, `load_shipped`), `Money`, `IDR`.
- Produces: in `steadyhand_idx.factor`: `GRID_START`, `FIVE_TIERS_FROM`, `FIT_TOLERANCE`, `MIN_PRICES`, `FACTOR_DIGITS`, `NOISE_QUANTUM`, `DIVIDEND_QUANTUM`; `PriceRow(day, prices)`; `Run(days, prices, factor)` with `first` and `last`; `Grid(verified)` with `shipped()`, `tiers_on(day)`, `nearest(value, day)` and `fits(price, factor, day)`; `candidates(row, grid)`; `find_runs(rows, grid=None)`; `is_noise(factor)`; `restore_price(recorded, factor, day, grid=None)`; `restore_dividend(recorded, factor)`.

- [ ] **Step 1: Branch.** `git switch -c feat/160-s1-factor origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/idx/test_factor.py`** (new)

<!-- file: tests/idx/test_factor.py -->
```python
"""Recovering Yahoo's unreported price factor from the IDX tick grid (#160 spec §4, §9.1)."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from steadyhand import IDR, Money
from steadyhand_idx._datafile import Dated, Where, load_shipped
from steadyhand_idx.factor import (
    FIT_TOLERANCE,
    GRID_START,
    MIN_PRICES,
    Grid,
    PriceRow,
    Run,
    candidates,
    find_runs,
    is_noise,
    restore_dividend,
    restore_price,
)
from steadyhand_idx.ticks import TickRow, TickTier, parse_ticks


def grid() -> Grid:
    """The shipped grid, read inside each test so a stub cannot fail the module's collection."""
    return Grid.shipped()


VERIFIED_DAY = date(2021, 3, 1)


def days_from(first: date, count: int) -> list[date]:
    return [first + timedelta(days=offset) for offset in range(count)]


def recorded(
    true_days: Sequence[Sequence[int]],
    factor: Decimal,
    first: date = VERIFIED_DAY,
    noise: Decimal = Decimal(0),
) -> list[PriceRow]:
    """What Yahoo would show for *true_days*, each a day's four traded prices, over *factor*."""
    return [
        PriceRow(day, tuple(Decimal(price) / factor + noise for price in prices))
        for day, prices in zip(days_from(first, len(true_days)), true_days, strict=True)
    ]


def restored(rows: Sequence[PriceRow], run: Run) -> list[list[int]]:
    assert run.factor is not None
    return [[restore_price(p, run.factor, row.day).amount for p in row.prices] for row in rows]


# Six days on the Rp10 and Rp25 tiers of the five-tier grid: 24 prices, enough for a proof.
TRUE_DAYS = [
    [3550, 3600, 3520, 3580],
    [3580, 3620, 3560, 3610],
    [3610, 3640, 3590, 3600],
    [5025, 5100, 4990, 5075],
    [5075, 5150, 5050, 5125],
    [5125, 5175, 5100, 5150],
]


def test_true_grid_prices_scaled_by_a_known_factor_recover_it() -> None:
    rows = recorded(TRUE_DAYS, Decimal("1.100019"))
    (run,) = find_runs(rows)
    assert run.factor == Decimal("1.100019")
    assert (run.first, run.last, run.prices) == (VERIFIED_DAY, VERIFIED_DAY + timedelta(5), 24)
    assert restored(rows, run) == TRUE_DAYS


def test_a_run_crossing_tiers_is_proven_on_each_price_s_own_tier() -> None:
    crossing = [[480, 505, 476, 498], [1995, 2010, 1990, 2000], [4990, 5025, 4980, 5000]]
    rows = recorded(crossing * 2, Decimal("1.3"))
    (run,) = find_runs(rows)
    assert run.factor == Decimal("1.300000")
    assert restored(rows, run) == crossing * 2
    # Each price on its own tier's tick: Rp5 below Rp2,000, Rp10 from it.
    fitting = [grid().fits(Decimal(p), Decimal(1), VERIFIED_DAY) for p in (1995, 2005, 2010)]
    assert fitting == [True, False, True]


def test_the_window_rejects_half_and_double_the_factor_although_both_fit_the_grid() -> None:
    # Multiples of Rp100: halved they sit on the Rp5 or Rp10 tier, doubled on the Rp10 or Rp25 tier.
    true_days = [
        [3500, 8400, 6300, 7100],
        [4200, 9500, 6400, 8600],
        [8300, 8800, 4700, 7400],
        [8000, 2100, 5500, 3500],
        [6200, 2600, 4900, 2600],
        [7500, 7300, 8500, 6700],
    ]
    rows = recorded(true_days, Decimal("1.7"))
    half, double = Decimal("0.85"), Decimal("3.4")
    assert all(
        grid().fits(p, half, row.day) and grid().fits(p, double, row.day)
        for row in rows
        for p in row.prices
    )
    (run,) = find_runs(rows)
    assert run.factor == Decimal("1.700000")


def test_two_fitting_candidates_leave_the_run_refused() -> None:
    # Odd multiples of Rp50 on the Rp25 tier also fit 1.5 times the factor, which is inside [1, 2).
    true_days = [
        [6350, 6450, 6550, 6650],
        [6850, 6950, 7050, 7150],
        [7350, 7450, 7550, 7650],
        [6350, 7150, 6450, 7050],
        [7650, 6550, 6950, 7350],
        [6650, 7450, 6850, 7550],
    ]
    rows = recorded(true_days, Decimal("1.2"))
    assert [round(f, 6) for f in candidates(rows[-1], grid())] == [
        Decimal("1.200000"),
        Decimal("1.800000"),
    ]
    (run,) = find_runs(rows)
    assert run.factor is None
    assert run.prices == 24


def test_fewer_than_twenty_prices_stay_refused() -> None:
    rows = recorded(TRUE_DAYS[:4], Decimal("1.1"))
    (run,) = find_runs(rows)
    assert run.prices == MIN_PRICES - 4
    assert run.factor is None
    assert find_runs(recorded(TRUE_DAYS[:5], Decimal("1.1")))[0].factor == Decimal("1.100000")


def test_two_stacked_adjustments_split_on_the_day_the_factor_changes() -> None:
    older = recorded(TRUE_DAYS, Decimal("1.3"))
    newer = recorded(TRUE_DAYS, Decimal("1.1"), first=VERIFIED_DAY + timedelta(6))
    first, second = find_runs([*older, *newer])
    assert (first.first, first.last, first.factor) == (
        VERIFIED_DAY,
        VERIFIED_DAY + timedelta(5),
        Decimal("1.300000"),
    )
    assert (second.first, second.last, second.factor) == (
        VERIFIED_DAY + timedelta(6),
        VERIFIED_DAY + timedelta(11),
        Decimal("1.100000"),
    )


def test_a_row_that_no_candidate_fits_is_a_single_unprovable_day() -> None:
    rows = [
        *recorded(TRUE_DAYS, Decimal("1.1")),
        PriceRow(VERIFIED_DAY + timedelta(6), (Decimal("0.4"),) * 4),
    ]
    proven, odd = find_runs(rows)
    assert proven.factor == Decimal("1.100000")
    assert (odd.days, odd.prices, odd.factor) == ((VERIFIED_DAY + timedelta(6),), 4, None)
    assert candidates(rows[-1], grid()) == []


def test_a_day_before_the_first_grid_is_never_provable() -> None:
    before = GRID_START - timedelta(days=len(TRUE_DAYS))
    rows = recorded(TRUE_DAYS, Decimal("1.1"), first=before)
    assert grid().tiers_on(GRID_START - timedelta(1)) is None
    assert all(run.factor is None and len(run.days) == 1 for run in find_runs(rows))
    with pytest.raises(ValueError, match=r"no tick grid for 2013-12-31, before 2014-01-06"):
        restore_price(Decimal(3550), Decimal(1), date(2013, 12, 31))


@pytest.mark.parametrize(
    ("price", "fits_on"),
    [
        # 2,015 is on the old Rp5 grid but off the five-tier Rp10 grid; 301 is on the old Rp1 grid
        # but off the five-tier Rp2 grid (t-hist.md §3).
        (2015, {date(2014, 1, 6), date(2016, 4, 29)}),
        (301, {date(2014, 1, 6), date(2016, 4, 29)}),
        # 2,010 is on both grids; 5,010 on neither.
        (
            2010,
            {
                date(2014, 1, 6),
                date(2016, 4, 29),
                date(2016, 5, 2),
                date(2020, 3, 12),
                date(2020, 3, 13),
            },
        ),
        (5010, set()),
    ],
)
def test_each_grid_era_is_used_on_its_own_days(price: int, fits_on: set[date]) -> None:
    edges = [
        date(2014, 1, 6),
        date(2016, 4, 29),
        date(2016, 5, 2),
        date(2020, 3, 12),
        date(2020, 3, 13),
    ]
    assert {day for day in edges if grid().fits(Decimal(price), Decimal(1), day)} == fits_on


def test_the_verified_era_reads_the_shipped_tick_table() -> None:
    table = parse_ticks(load_shipped("tick_sizes.toml"))
    assert grid().tiers_on(date(2020, 3, 13)) == table.on(date(2020, 3, 13)).tiers
    assert Grid.shipped() is Grid.shipped()


def test_the_verified_table_takes_over_on_its_own_first_day() -> None:
    sevens = (TickTier(1, 7),)
    verified = Dated(Where("test", "ticks"), (date(2020, 3, 13),), (TickRow("test", 100, sevens),))
    grid = Grid(verified)
    assert grid.tiers_on(date(2020, 3, 13)) == sevens
    assert grid.tiers_on(date(2020, 3, 12)) != sevens
    assert not grid.fits(Decimal(8), Decimal(1), date(2020, 3, 13))
    assert grid.fits(Decimal(8), Decimal(1), date(2020, 3, 12))


def test_a_price_below_the_first_tier_uses_the_first_tick() -> None:
    assert grid().nearest(Decimal("0.6"), VERIFIED_DAY) == 1
    assert grid().nearest(Decimal("0.4"), VERIFIED_DAY) == 0


def test_a_fit_is_within_one_rupiah_cent() -> None:
    assert grid().fits(Decimal(3550) + FIT_TOLERANCE, Decimal(1), VERIFIED_DAY)
    assert not grid().fits(
        Decimal(3550) + FIT_TOLERANCE + Decimal("0.0001"), Decimal(1), VERIFIED_DAY
    )


def test_a_noise_run_is_restored_onto_the_grid_it_almost_sits_on() -> None:
    rows = recorded(TRUE_DAYS, Decimal(1), noise=Decimal("0.0006"))
    (run,) = find_runs(rows)
    assert run.factor == Decimal("0.9999999")  # noise: it rounds to 1.000000
    assert restored(rows, run) == TRUE_DAYS


# TINS 2014 (spec §3.5): reversing an odd split leaves Rp0.0006 of upward noise, and on the old
# three-tier grid twice every price is on the Rp5 tier too.
TINS_DAYS = [[1965, 1975, 1960, 1970], [1910, 1925, 1905, 1915], [2045, 2050, 2040, 2045]] * 2


def test_upward_noise_at_the_first_price_keeps_one_as_a_candidate() -> None:
    rows = recorded(TINS_DAYS, Decimal(1), first=date(2014, 3, 3), noise=Decimal("0.0006"))
    assert rows[-1].prices[0] == Decimal("2045.0006")
    assert [round(f, 6) for f in candidates(rows[-1], grid())] == [
        Decimal("1.000000"),
        Decimal("1.999999"),
    ]
    (run,) = find_runs(rows)
    assert run.factor is None


def test_downward_noise_at_the_first_price_keeps_one_as_a_candidate() -> None:
    rows = recorded(TRUE_DAYS, Decimal(1), noise=Decimal("-0.0006"))
    assert round(candidates(rows[-1], grid())[0], 6) == 1
    assert find_runs(rows)[0].factor == 1


# The upper edge (plan scope decision 19): downward noise at p1 puts 2 * p1 just below the true
# whole rupiah when the true factor is near 2. Here true prices of Rp50 and Rp82 on the 2015 grid,
# recorded over 1.9999201 with Rp0.001 of downward noise, give p1 = 24.9999988: the true price,
# Rp50, is above 2 * p1, so a window that stopped below 2 * p1 left f = 1 alone and "proved" it.
EDGE_DAYS = [[50, 50, 50, 50]] * 4 + [[50, 50, 50, 82]]


def test_downward_noise_near_a_factor_of_two_keeps_the_true_factor_a_candidate() -> None:
    rows = recorded(
        EDGE_DAYS, Decimal("1.9999201"), first=date(2015, 3, 2), noise=Decimal("-0.001")
    )
    assert [round(f, 6) for f in candidates(rows[-1], grid())] == [
        Decimal("1.000000"),
        Decimal("2.000000"),
    ]
    (run,) = find_runs(rows)
    assert run.factor is None


def test_restored_prices_are_whole_rupiah_on_their_tick() -> None:
    assert restore_price(Decimal("3227.2706"), Decimal("1.100019"), VERIFIED_DAY) == Money(
        3550, IDR
    )
    assert restore_price(Decimal("4568.10"), Decimal("1.100019"), VERIFIED_DAY) == Money(5025, IDR)


def test_restored_dividends_are_quantised_to_one_hundredth_of_a_rupiah_cent() -> None:
    assert restore_dividend(Decimal("89.91268"), Decimal("1.100019")) == Decimal("98.9057")
    assert restore_dividend(Decimal("10.00005"), Decimal(1)) == Decimal("10.0000")
    assert restore_dividend(Decimal("10.00015"), Decimal(1)) == Decimal("10.0002")


def test_no_rows_form_no_runs() -> None:
    assert find_runs([]) == ()


ERAS = (date(2015, 3, 2), date(2017, 3, 1), VERIFIED_DAY)


@st.composite
def true_run(draw: st.DrawFn) -> tuple[date, list[list[int]]]:
    """Five to eight days of traded prices on one era's grid, within a factor of two."""
    first = draw(st.sampled_from(ERAS))
    base = draw(st.integers(min_value=50, max_value=20_000))
    days = draw(st.integers(min_value=5, max_value=8))
    prices: list[list[int]] = []
    for offset in range(days):
        day = first + timedelta(offset)
        raw = draw(st.lists(st.integers(base, 2 * base), min_size=4, max_size=4))
        nearest = [grid().nearest(Decimal(p), day) for p in raw]
        prices.append([int(n) for n in nearest if n is not None])
    return first, prices


@example(drawn=(date(2015, 3, 2), EDGE_DAYS), factor=Decimal("1.9999201"), noise=Decimal("-0.001"))
@given(
    true_run(),
    st.decimals(min_value=1, max_value=Decimal("1.9999999"), places=7),
    st.sampled_from([Decimal(0), Decimal("0.001"), Decimal("-0.001"), Decimal("0.0004")]),
)
def test_a_proven_factor_restores_the_true_prices(
    drawn: tuple[date, list[list[int]]], factor: Decimal, noise: Decimal
) -> None:
    """The safety claim (spec §4.4): a run is either proven at the true factor or left refused."""
    first, true_days = drawn
    rows = recorded(true_days, factor, first=first, noise=noise)
    for run in find_runs(rows):
        if run.factor is not None:
            members = [row for row in rows if run.first <= row.day <= run.last]
            want = [true_days[rows.index(row)] for row in members]
            assert restored(members, run) == want


@pytest.mark.parametrize(
    ("factor", "noise"),
    [
        (Decimal("0.9999995"), True),
        (Decimal("0.9999999"), True),
        (Decimal("1.0000004"), True),
        (Decimal("1.000001"), False),
        (Decimal("0.9999994"), False),
    ],
)
def test_a_noise_factor_is_one_that_rounds_to_one(factor: Decimal, *, noise: bool) -> None:
    assert is_noise(factor) is noise


def test_noise_is_judged_at_six_decimal_places() -> None:
    assert is_noise(Decimal("1.0000005"))
    assert not is_noise(Decimal("1.0000015"))
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/factor.py`** (new, as stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
```python
"""Recovering the price factor Yahoo applies without reporting it, from the IDX tick grid (#160).

Yahoo's "unadjusted" IDX history carries adjustments it does not report: a rights issue scales
every earlier price by a factor nobody publishes, so after the reported splits are reversed those
prices are not whole rupiah. Every real price sat on the tick grid of its day, so the one factor
that puts a whole run of them back on that grid is the factor Yahoo applied (spec §4).

This module is pure: no network, cache or calendar. Its input is the rows of one ticker's history
with a price that is not whole after the reported splits are reversed, in date order, and its
output is the runs those rows form, each proven or not.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal
from functools import cache

from steadyhand import IDR, Money
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.ticks import TICKS_FILE, TickRow, TickTier, parse_ticks

GRID_START = date(2014, 1, 6)
"""The first day with a known tick grid. A price before it is never provable (spec §4.2)."""

FIVE_TIERS_FROM = date(2016, 5, 2)
"""The first day of the five-tier grid in the inference-only history (t-hist.md §3)."""

FIT_TOLERANCE = Decimal("0.01")
"""A price times a factor fits when it is this close to its tier's tick, in rupiah (spec §4.3)."""

MIN_PRICES = 20
"""A run needs at least this many prices (five days) to be proven (spec §4.4, decision 1)."""

FACTOR_DIGITS = 7
"""A proven factor is refined over its run and kept to this many significant figures (§4.5)."""

NOISE_QUANTUM = Decimal("0.000001")
"""A proven factor that rounds to 1 here is a rounding error, not an adjustment (§4.5)."""

DIVIDEND_QUANTUM = Decimal("0.0001")
"""A restored dividend is quantised to this many rupiah per share (spec §4.5)."""

# Inference only (spec decision 2): these grids are never read by order validation, which uses
# tick_sizes.toml alone. docs/research/t-hist.md §3: five tiers from 2 May 2016 to 12 Mar 2020
# ("unverified but supported by data") and three tiers from 6 Jan 2014 to 1 May 2016 (values
# from the news, unverified). A wrong row can only leave a run unproven, never prove a wrong
# factor, because every candidate must fit every price of its run (spec §4.4).
_FIVE_TIERS = (
    TickTier(1, 1),
    TickTier(200, 2),
    TickTier(500, 5),
    TickTier(2000, 10),
    TickTier(5000, 25),
)
_THREE_TIERS = (TickTier(1, 1), TickTier(500, 5), TickTier(5000, 25))

_SIGNIFICANT = Context(prec=FACTOR_DIGITS, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class PriceRow:
    """One day's open, high, low and close after the reported splits are reversed."""

    day: date
    prices: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class Run:
    """Consecutive rows that one or more factors fit, oldest day first.

    ``factor`` is the refined factor when exactly one candidate fits every price and the run has at
    least ``MIN_PRICES`` prices, and ``None`` otherwise.
    """

    days: tuple[date, ...]
    prices: int
    factor: Decimal | None

    @property
    def first(self) -> date:
        raise NotImplementedError("Run.first")

    @property
    def last(self) -> date:
        raise NotImplementedError("Run.last")


def is_noise(factor: Decimal) -> bool:
    """Whether a proven *factor* rounds to 1.000000: a rounding error, not an adjustment."""
    raise NotImplementedError("is_noise")


class Grid:
    """The tick grid of each day: ``tick_sizes.toml`` where it is verified, inference before."""

    def __init__(self, verified: Dated[TickRow]) -> None:
        raise NotImplementedError("Grid.__init__")

    @classmethod
    def shipped(cls) -> Grid:
        raise NotImplementedError("Grid.shipped")

    def tiers_on(self, day: date) -> tuple[TickTier, ...] | None:
        """The day's tiers, or ``None`` before ``GRID_START``."""
        raise NotImplementedError("Grid.tiers_on")

    def nearest(self, value: Decimal, day: date) -> Decimal | None:
        """The multiple of *value*'s own tier's tick nearest *value*; ``None`` with no grid."""
        raise NotImplementedError("Grid.nearest")

    def fits(self, price: Decimal, factor: Decimal, day: date) -> bool:
        raise NotImplementedError("Grid.fits")


@cache
def _shipped() -> Grid:
    raise NotImplementedError("_shipped")


def candidates(row: PriceRow, grid: Grid) -> list[Decimal]:
    """Every factor from about 1 to about 2 that puts all of *row*'s prices on its grid.

    The factors tried are g / p1 for every whole rupiah g from the one nearest the open p1 up to,
    not including, 2 * (p1 + FIT_TOLERANCE): every factor that puts p1 on a whole rupiah. Both
    edges allow for float noise in p1, so the true factor is always tried. At the lower edge,
    starting at the nearest whole rupiah keeps f = 1 under upward noise (§3.5). At the upper
    edge, a recorded price may sit up to FIT_TOLERANCE off the true one, the slack every fit
    already allows, so a true factor just below 2 is still tried under downward noise. A factor
    tried past either edge can only make a second fit, which refuses the run (§4.4).
    """
    raise NotImplementedError("candidates")


def find_runs(rows: Sequence[PriceRow], grid: Grid | None = None) -> tuple[Run, ...]:
    """The runs *rows* form, oldest first (spec §4.1).

    The rows are walked newest first. The newest starts a run with its candidates; each older row
    joins while at least one of the run's candidates still fits all its prices, and the run keeps
    only those. A row that none fits ends the run and starts the next.
    """
    raise NotImplementedError("find_runs")


def _close(members: list[PriceRow], passing: list[Decimal], grid: Grid) -> Run:
    raise NotImplementedError("_close")


def _refine(rows: list[PriceRow], factor: Decimal, grid: Grid, count: int) -> Decimal:
    """The mean of (nearest tick / recorded price) over every price, to 7 significant figures."""
    raise NotImplementedError("_refine")


def _on_grid(value: Decimal, day: date, grid: Grid) -> Decimal:
    raise NotImplementedError("_on_grid")


def restore_price(recorded: Decimal, factor: Decimal, day: date, grid: Grid | None = None) -> Money:
    """The tick multiple nearest *recorded* times *factor*, as the price traded on *day*."""
    raise NotImplementedError("restore_price")


def restore_dividend(recorded: Decimal, factor: Decimal) -> Decimal:
    """*recorded* (its reported splits already reversed) times *factor*, to Rp0.0001."""
    raise NotImplementedError("restore_dividend")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1625 failed=30 -->
Expected: 1625 run, 30 failed (pytest reads `30 failed`), every one `NotImplementedError` from the stubs: each test of `tests/idx/test_factor.py`. The module reads the shipped grid inside each test (`grid()`), never at import, so it collects under the stubs.

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/factor.py`** (replaces the stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
```python
"""Recovering the price factor Yahoo applies without reporting it, from the IDX tick grid (#160).

Yahoo's "unadjusted" IDX history carries adjustments it does not report: a rights issue scales
every earlier price by a factor nobody publishes, so after the reported splits are reversed those
prices are not whole rupiah. Every real price sat on the tick grid of its day, so the one factor
that puts a whole run of them back on that grid is the factor Yahoo applied (spec §4).

This module is pure: no network, cache or calendar. Its input is the rows of one ticker's history
with a price that is not whole after the reported splits are reversed, in date order, and its
output is the runs those rows form, each proven or not.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal
from functools import cache

from steadyhand import IDR, Money
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.ticks import TICKS_FILE, TickRow, TickTier, parse_ticks

GRID_START = date(2014, 1, 6)
"""The first day with a known tick grid. A price before it is never provable (spec §4.2)."""

FIVE_TIERS_FROM = date(2016, 5, 2)
"""The first day of the five-tier grid in the inference-only history (t-hist.md §3)."""

FIT_TOLERANCE = Decimal("0.01")
"""A price times a factor fits when it is this close to its tier's tick, in rupiah (spec §4.3)."""

MIN_PRICES = 20
"""A run needs at least this many prices (five days) to be proven (spec §4.4, decision 1)."""

FACTOR_DIGITS = 7
"""A proven factor is refined over its run and kept to this many significant figures (§4.5)."""

NOISE_QUANTUM = Decimal("0.000001")
"""A proven factor that rounds to 1 here is a rounding error, not an adjustment (§4.5)."""

DIVIDEND_QUANTUM = Decimal("0.0001")
"""A restored dividend is quantised to this many rupiah per share (spec §4.5)."""

# Inference only (spec decision 2): these grids are never read by order validation, which uses
# tick_sizes.toml alone. docs/research/t-hist.md §3: five tiers from 2 May 2016 to 12 Mar 2020
# ("unverified but supported by data") and three tiers from 6 Jan 2014 to 1 May 2016 (values
# from the news, unverified). A wrong row can only leave a run unproven, never prove a wrong
# factor, because every candidate must fit every price of its run (spec §4.4).
_FIVE_TIERS = (
    TickTier(1, 1),
    TickTier(200, 2),
    TickTier(500, 5),
    TickTier(2000, 10),
    TickTier(5000, 25),
)
_THREE_TIERS = (TickTier(1, 1), TickTier(500, 5), TickTier(5000, 25))

_SIGNIFICANT = Context(prec=FACTOR_DIGITS, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class PriceRow:
    """One day's open, high, low and close after the reported splits are reversed."""

    day: date
    prices: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class Run:
    """Consecutive rows that one or more factors fit, oldest day first.

    ``factor`` is the refined factor when exactly one candidate fits every price and the run has at
    least ``MIN_PRICES`` prices, and ``None`` otherwise.
    """

    days: tuple[date, ...]
    prices: int
    factor: Decimal | None

    @property
    def first(self) -> date:
        return self.days[0]

    @property
    def last(self) -> date:
        return self.days[-1]


def is_noise(factor: Decimal) -> bool:
    """Whether a proven *factor* rounds to 1.000000: a rounding error, not an adjustment."""
    return factor.quantize(NOISE_QUANTUM) == 1


class Grid:
    """The tick grid of each day: ``tick_sizes.toml`` where it is verified, inference before."""

    def __init__(self, verified: Dated[TickRow]) -> None:
        self._verified = verified

    @classmethod
    def shipped(cls) -> Grid:
        return _shipped()

    def tiers_on(self, day: date) -> tuple[TickTier, ...] | None:
        """The day's tiers, or ``None`` before ``GRID_START``."""
        if day >= self._verified.first:
            return self._verified.on(day).tiers
        if day >= FIVE_TIERS_FROM:
            return _FIVE_TIERS
        if day >= GRID_START:
            return _THREE_TIERS
        return None

    def nearest(self, value: Decimal, day: date) -> Decimal | None:
        """The multiple of *value*'s own tier's tick nearest *value*; ``None`` with no grid."""
        tiers = self.tiers_on(day)
        if tiers is None:
            return None
        tick = next((tier.tick for tier in reversed(tiers) if tier.from_price <= value), 1)
        return (value / tick).to_integral_value(ROUND_HALF_EVEN) * tick

    def fits(self, price: Decimal, factor: Decimal, day: date) -> bool:
        value = price * factor
        nearest = self.nearest(value, day)
        return nearest is not None and abs(value - nearest) <= FIT_TOLERANCE


@cache
def _shipped() -> Grid:
    return Grid(parse_ticks(load_shipped(TICKS_FILE)))


def candidates(row: PriceRow, grid: Grid) -> list[Decimal]:
    """Every factor from about 1 to about 2 that puts all of *row*'s prices on its grid.

    The factors tried are g / p1 for every whole rupiah g from the one nearest the open p1 up to,
    not including, 2 * (p1 + FIT_TOLERANCE): every factor that puts p1 on a whole rupiah. Both
    edges allow for float noise in p1, so the true factor is always tried. At the lower edge,
    starting at the nearest whole rupiah keeps f = 1 under upward noise (§3.5). At the upper
    edge, a recorded price may sit up to FIT_TOLERANCE off the true one, the slack every fit
    already allows, so a true factor just below 2 is still tried under downward noise. A factor
    tried past either edge can only make a second fit, which refuses the run (§4.4).
    """
    first = row.prices[0]
    start = max(int(first.to_integral_value(ROUND_HALF_UP)), 1)
    found: list[Decimal] = []
    whole = start
    while whole < 2 * (first + FIT_TOLERANCE):
        factor = whole / first
        if all(grid.fits(price, factor, row.day) for price in row.prices):
            found.append(factor)
        whole += 1
    return found


def find_runs(rows: Sequence[PriceRow], grid: Grid | None = None) -> tuple[Run, ...]:
    """The runs *rows* form, oldest first (spec §4.1).

    The rows are walked newest first. The newest starts a run with its candidates; each older row
    joins while at least one of the run's candidates still fits all its prices, and the run keeps
    only those. A row that none fits ends the run and starts the next.
    """
    tiles = Grid.shipped() if grid is None else grid
    found: list[Run] = []
    members: list[PriceRow] = []
    passing: list[Decimal] = []
    for row in reversed(rows):
        if members:
            still = [f for f in passing if all(tiles.fits(p, f, row.day) for p in row.prices)]
            if still:
                members.append(row)
                passing = still
                continue
            found.append(_close(members, passing, tiles))
        members = [row]
        passing = candidates(row, tiles)
    if members:
        found.append(_close(members, passing, tiles))
    return tuple(reversed(found))


def _close(members: list[PriceRow], passing: list[Decimal], grid: Grid) -> Run:
    oldest_first = members[::-1]
    count = sum(len(row.prices) for row in oldest_first)
    days = tuple(row.day for row in oldest_first)
    if len(passing) != 1 or count < MIN_PRICES:
        return Run(days, count, None)
    return Run(days, count, _refine(oldest_first, passing[0], grid, count))


def _refine(rows: list[PriceRow], factor: Decimal, grid: Grid, count: int) -> Decimal:
    """The mean of (nearest tick / recorded price) over every price, to 7 significant figures."""
    total = Decimal(0)
    for row in rows:
        for price in row.prices:
            total += _on_grid(price * factor, row.day, grid) / price
    return _SIGNIFICANT.plus(total / count)


def _on_grid(value: Decimal, day: date, grid: Grid) -> Decimal:
    nearest = grid.nearest(value, day)
    if nearest is None:
        msg = f"there is no tick grid for {day.isoformat()}, before {GRID_START.isoformat()}"
        raise ValueError(msg)
    return nearest


def restore_price(recorded: Decimal, factor: Decimal, day: date, grid: Grid | None = None) -> Money:
    """The tick multiple nearest *recorded* times *factor*, as the price traded on *day*."""
    tiles = Grid.shipped() if grid is None else grid
    return Money(int(_on_grid(recorded * factor, day, tiles)), IDR)


def restore_dividend(recorded: Decimal, factor: Decimal) -> Decimal:
    """*recorded* (its reported splits already reversed) times *factor*, to Rp0.0001."""
    return (recorded * factor).quantize(DIVIDEND_QUANTUM, ROUND_HALF_EVEN)
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1625 passed=1625 -->
Expected: every command exits 0; 1625 passed, 100% branch coverage; the performance step passes its nine tests, unchanged by this story. CI's second job runs the same 1625 tests on Python 3.13 under `-W error`.

- [ ] **Step 7: Mutations.** Run M373–M385 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(idx): #160 S1 the price-factor proof`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 2: #160 S2 Restored prices and dividends in the source and the cache

**Acceptance criteria (story text):**
1. `YahooDataSource(..., today=jakarta_today)` reads a ticker's whole history once, from 2014-01-06 to `today`, when a range has a row with a price off whole rupiah after the reported splits are reversed, and builds its runs from those rows (`evidence`: a flat row with no volume is no evidence; volume plays no part). A range whose prices are all whole reads nothing more. A restored day is the same whatever range is asked.
2. `bars` returns restored bars for the days in proven runs and raises `UnrecoverablePricesError` naming the rest, as before: unproven runs, rows whose volume is not whole (#162), days before 2014-01-06. A flat row with no volume inside a proven run is restored.
3. `corporate_actions` restores a dividend in a proven run (BBRI 2021-04-06: Rp98.9057, within Rp0.0001 of BRI's announced 98.905659443) and refuses one in an unproven run with `UnprovenDividendsError` naming its ex-date (scope decision 3). `restorations(instrument, start, end)` returns the proven runs overlapping the range as `Restoration(instrument, first, last, factor, prices)`.
4. BBRI's whole recording proves one factor, 1.100019, up to 2021-09-07; of its golden years, every day is restored except where a volume is not whole; the recording agrees with every older BBRI recording where they overlap.
5. `BarCache`'s migration 3 creates `restorations (symbol, first, last, factor, prices)` and clears `actions`, `fetched_actions` and `fetched`, once. `store` and `store_actions` take the range's restorations, refuse one that does not overlap it, and refuse a different restoration for a stored run (`CacheConflictError`). `CachedDataSource` stores the upstream's restorations with each range and answers `restorations` from the cache, never a fetch.
6. The golden runs are re-recorded over BBRI's restored prices, each changed figure worked out by hand: BBRI is ordered on the first day and bought at the next open, and its 2021 dividend on 4,500 shares is credited at Rp98.9057 a share, Rp445,075; the CLI's figures follow.
7. A row Yahoo gives with no open, high, low, close or volume is no bar; one that carries a dividend is refused naming its day (scope decision 20). With two proven runs, `restorations` returns only the run a range overlaps.
8. Inferring BBRI's whole recording finishes inside its measured budget.
9. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M386–M402 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand_idx/{factor,yahoo,cache}.py`, `scripts/record_golden.py`, `tests/fixtures/golden/*.json` (generated)
- Create: `tests/perf/test_factor_performance.py`
- Modify: `tests/perf/test_performance.py` (its docstring named four cores; the machine has six)
- Test: `tests/idx/{test_yahoo,test_yahoo_live,test_cache}.py`, `tests/cli/{cli_world,test_backtest_command,test_compare_command,test_journeys,test_paper_commands,test_paper_run,test_reports}.py`, `tests/golden/{test_golden_backtest,test_golden_snapshot}.py`

**Interfaces:**
- Consumes: Task 1's `factor` module; `tests/fixtures/yahoo/BBRI.JK_2014-01-06_2026-10-01.json` (Task 0).
- Produces: in `steadyhand_idx.factor`: `Restoration(instrument, first, last, factor, prices)`. In `steadyhand_idx.yahoo`: `YahooDataSource(calendar=None, *, download=None, sleep=..., policy=..., today=jakarta_today)` with `restorations(instrument, start, end)`; `UnprovenDividendsError(ticker, days)`; `reversed_prices(history, row)`; `evidence(history)`; `unadjust(history, instrument, calendar, span, runs=())`; `actions_in(history, instrument, start, end, runs=())`. In `steadyhand_idx.cache`: `RestoringSource`; `BarCache.store(instrument, span, bars, actions, restorations=())`, `store_actions(instrument, span, actions, restorations=())` and `restorations(instrument, start, end)`; `CachedDataSource(upstream, cache, calendar=None, *, today=...)` with `restorations(instrument, start, end)`. In `scripts/record_golden.py`: `WHOLE_RECORDED`, `WHOLE_HISTORIES`, `replay(download=recorded)`.

- [ ] **Step 1: Branch.** `git switch -c feat/160-s2-source-cache origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/cli_world.py`** (changed: 3 edits)

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python

from record_golden import END, RECORDED, START, STOCKS, recorded

from steadyhand import STRATEGIES, BacktestResult, DataSource, Market, backtest
from steadyhand_idx import BarCache, CachedDataSource, YahooDataSource
from steadyhand_idx.cli import SourceFactory, World, main
```
with:
```python

from record_golden import END, RECORDED, START, STOCKS, recorded, replay

from steadyhand import STRATEGIES, BacktestResult, DataSource, Market, backtest
from steadyhand_idx import BarCache, CachedDataSource
from steadyhand_idx.cli import SourceFactory, World, main
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python

def _no_wait(seconds: float) -> None:
    del seconds


@contextmanager
```
with:
```python

@contextmanager
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
    on the day they were recorded, as the golden test reads them."""
    yahoo = YahooDataSource(download=recorded_or_empty, sleep=_no_wait)
    with BarCache(folder / "cache.sqlite") as cache:
        yield CachedDataSource(yahoo, cache, today=lambda: RECORDED)

```
with:
```python
    on the day they were recorded, as the golden test reads them."""
    with BarCache(folder / "cache.sqlite") as cache:
        yield CachedDataSource(replay(recorded_or_empty), cache, today=lambda: RECORDED)

```

**`tests/cli/test_backtest_command.py`** (changed: 10 edits)

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
)
from record_golden import END, GOLDEN, RECORDED, START, recorded, run, settings, universe

```
with:
```python
)
from record_golden import END, GOLDEN, RECORDED, START, replay, run, settings, universe

```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
)
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules, YahooDataSource
from steadyhand_idx.training import catalogue
```
with:
```python
)
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules
from steadyhand_idx.training import catalogue
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    assert len(expected) == 248
    assert sum(int(row[5]) for row in rows[1:]) == 2_800_277

```
with:
```python
    assert len(expected) == 248
    assert sum(int(row[5]) for row in rows[1:]) == 2_699_239

```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))["metrics"]
    assert stored["final_value"] == 97_889_490
    assert stored["dividends"] == {"gross": 2_800_277, "tax": 280_028}
    table = result.out.split("\n\n")[1].splitlines()
    assert table == [
        "                          buy-and-hold",
        "Final value             IDR 97,889,490",
        "Deposited              IDR 100,000,000",
        "Total return                    -2.11%",
        "Annual return                   -2.11%",
        "Largest drawdown                18.16%",
        "Trading costs              IDR 239,759",
        "Turnover a year                 54.42%",
        "Dividends before tax     IDR 2,800,277",
        "Dividend tax               IDR 280,028",
        "Income goal a month      IDR 1,000,000",
        "Received a month           IDR 210,020",
        "Received, of the goal           21.00%",
        "Run-rate a month           IDR 212,668",
        "Run-rate, of the goal           21.27%",
    ]
    costs = stored["costs"]
    assert costs["fee"] + costs["levy"] + costs["sale_tax"] + costs["daily"] == 239_759

```
with:
```python
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))["metrics"]
    assert stored["final_value"] == 96_825_198
    assert stored["dividends"] == {"gross": 2_699_239, "tax": 269_925}
    table = result.out.split("\n\n")[1].splitlines()
    assert table == [
        "                          buy-and-hold",
        "Final value             IDR 96,825,198",
        "Deposited              IDR 100,000,000",
        "Total return                    -3.17%",
        "Annual return                   -3.17%",
        "Largest drawdown                17.65%",
        "Trading costs              IDR 279,116",
        "Turnover a year                 54.14%",
        "Dividends before tax     IDR 2,699,239",
        "Dividend tax               IDR 269,925",
        "Income goal a month      IDR 1,000,000",
        "Received a month           IDR 202,442",
        "Received, of the goal           20.24%",
        "Run-rate a month           IDR 206,964",
        "Run-rate, of the goal           20.70%",
    ]
    costs = stored["costs"]
    assert costs["fee"] + costs["levy"] + costs["sale_tax"] + costs["daily"] == 279_116

```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    )
    assert (
        "\n\nWarnings:\n- BBRI: the data source refused 146 day(s) (2021-02-01 to 2021-09-07)"
        in result.out
    )
    assert f"\n\nWrote {reports / f'{STEM}.md'}\nWrote {reports / f'{STEM}.csv'}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    refused = catalogue().for_key(DATA_BAR_REFUSED).id
    assert f"More: steadyhand-idx learn {refused}\n" in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")
```
with:
```python
    )
    # BBRI's prices up to 2021-09-07 are restored (#160), so nothing in the window is refused.
    assert "Warnings:" not in result.out
    assert f"\n\nWrote {reports / f'{STEM}.md'}\nWrote {reports / f'{STEM}.csv'}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
    refused = catalogue().for_key(DATA_BAR_REFUSED).id
    assert f"More: steadyhand-idx learn {refused}\n" not in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    ]
    assert lines[6] == "| Final value | IDR 97,889,490 |"
    assert "\n## Warnings\n\n- BBRI: the data source refused 146 day(s)" in text
    assert "## Day warnings" not in text
```
with:
```python
    ]
    assert lines[6] == "| Final value | IDR 96,825,198 |"
    assert "## Warnings" not in text
    assert "## Day warnings" not in text
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
) -> None:
    # The income report reads five years before the last day. Yahoo's BBRI prices before
    # 2021-09-07 carry an event it does not report, so they cannot be recovered, but a dividend
    # needs no price: the report is built, with BBRI's 6 April 2021 dividend in its run-rate
    # (M6 spec §4.3). Before M6 the whole run stopped with exit 3.
    result = market("backtest", "--from", "2022-01-25", "--to", "2022-01-31")
    assert (result.code, result.err) == (0, "")
    assert "Run-rate a month           IDR 208,538\n" in result.out
    found = golden_backtest(market, date(2022, 1, 31), goal=True, start=date(2022, 1, 25))
    assert found.run.income is not None
    held = {h.instrument.symbol: h.dividends for h in found.run.income.run_rate.holdings}
    assert [(d.ex_date, d.gross) for d in held["BBRI"]] == [(date(2021, 4, 6), Money(440_572, IDR))]

```
with:
```python
) -> None:
    # The income report reads five years before the last day. Yahoo's BBRI rows before
    # 2017-11-10 have volumes that are not whole shares once its split is reversed, so those days
    # cannot be recovered (#162), but a dividend needs no price: the report is built, with BBRI's
    # 6 April 2021 dividend in its run-rate (M6 spec §4.3), at its restored Rp98.9057 a share on
    # 4,900 shares (#160). Before M6 the whole run stopped with exit 3.
    result = market("backtest", "--from", "2022-01-25", "--to", "2022-01-31")
    assert (result.code, result.err) == (0, "")
    assert "Run-rate a month           IDR 211,843\n" in result.out
    found = golden_backtest(market, date(2022, 1, 31), goal=True, start=date(2022, 1, 25))
    assert found.run.income is not None
    held = {h.instrument.symbol: h.dividends for h in found.run.income.run_rate.holdings}
    assert [(d.ex_date, d.gross) for d in held["BBRI"]] == [(date(2021, 4, 6), Money(484_637, IDR))]

```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
        last = list(csv.reader(file))[-1]
    yahoo = YahooDataSource(download=recorded, sleep=no_wait)
    with BarCache(tmp_path / "bars.sqlite") as cache:
        source = CachedDataSource(yahoo, cache, today=lambda: RECORDED)
        rules = IdxMarketRules(broker_fees="ajaib")
```
with:
```python
        last = list(csv.reader(file))[-1]
    with BarCache(tmp_path / "bars.sqlite") as cache:
        source = CachedDataSource(replay(), cache, today=lambda: RECORDED)
        rules = IdxMarketRules(broker_fees="ajaib")
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    assert int(last[1]) != golden.run.reports[-1].value.amount


def no_wait(seconds: float) -> None:
    del seconds

```
with:
```python
    assert int(last[1]) != golden.run.reports[-1].value.amount

```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
        "                       monthly-savings     buy-and-hold",
        "Final value            IDR 100,655,756   IDR 97,889,490",
    ]
```
with:
```python
        "                       monthly-savings     buy-and-hold",
        "Final value             IDR 98,752,838   IDR 96,825,198",
    ]
```

**`tests/cli/test_compare_command.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_compare_command.py -->
Replace:
```python
    assert row.startswith("buy-and-hold")
    assert "IDR 97,889,490" in row
    assert row.endswith("21.27%")
    assert result.out.startswith(
        "Comparison, 2021-02-01 to 2022-01-31, 248 trading days\n\nStrategy"
    )
    assert "\n\nWarnings:\n- BBRI: the data source refused 146 day(s)" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
```
with:
```python
    assert row.startswith("buy-and-hold")
    assert "IDR 96,825,198" in row
    assert row.endswith("20.70%")
    assert result.out.startswith(
        "Comparison, 2021-02-01 to 2022-01-31, 248 trading days\n\nStrategy"
    )
    assert "Warnings:" not in result.out  # BBRI's prices are restored (#160): none is refused
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
```

<!-- edit: tests/cli/test_compare_command.py -->
Replace:
```python
    assert lines[5] == "|---|" + "---:|" * 14
    assert lines[6].startswith("| buy-and-hold | IDR 97,889,490 | IDR 100,000,000 | -2.11% | ")
    assert lines[-1] == DISCLAIMER
```
with:
```python
    assert lines[5] == "|---|" + "---:|" * 14
    assert lines[6].startswith("| buy-and-hold | IDR 96,825,198 | IDR 100,000,000 | -3.17% | ")
    assert lines[-1] == DISCLAIMER
```

**`tests/cli/test_journeys.py`** (changed: 1 edit)

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
    assert first.code == 0, first.err
    assert first.out.startswith("2021-02-01: 0 fill(s), 4 order(s) queued, value IDR 100,000,000")
    again = cli("paper", "run")
```
with:
```python
    assert first.code == 0, first.err
    assert first.out.startswith("2021-02-01: 0 fill(s), 5 order(s) queued, value IDR 100,000,000")
    again = cli("paper", "run")
```

**`tests/cli/test_paper_commands.py`** (changed, rewritten whole)

<!-- file: tests/cli/test_paper_commands.py -->
```python
"""``paper status``, ``report``, ``resume`` and ``paper switch`` (M5 spec §7, §9.2).

Each command runs through ``main`` over an account that ``paper run`` built from the recorded
Yahoo answers, in a temporary data directory, at a fixed time in Jakarta. Pages are compared
whole with training off, so a figure that moves or a line that goes missing is seen; the keys
each page names are checked on the page itself.
"""

import io
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from cli_world import (
    GOLDEN_CONFIG,
    Cli,
    at,
    golden_backtest,
    opened,
    paper,
    recorded_source,
    run_on,
    tables,
    trading_days,
)
from record_golden import END, START

from steadyhand import (
    CLAIMS_LABEL,
    CORPORATE_SPLIT_ORDER_CANCELLED,
    DATA_BAR_REFUSED,
    DISCLAIMER,
    FIGURES,
    IDR,
    LIMIT_WEIGHT_CUT,
    LIMIT_WEIGHT_FULL,
    PROJECTION_LABEL,
    RISK_HALT_DRAWDOWN,
    DayReport,
    EngineState,
    Halt,
    Holdings,
    Instrument,
    Money,
    Note,
    Portfolio,
    RiskLimits,
    UnitValue,
)
from steadyhand_idx.cli import World, main
from steadyhand_idx.notes import PAPER_ORDER_SKIPPED, PAPER_RESUMED, PAPER_STRATEGY_SWITCHED
from steadyhand_idx.paper import HaltCausePresentError, check_resume
from steadyhand_idx.paper_pages import day_report_page, income_page, status_page
from steadyhand_idx.state import Account, Outcome

QUIET = '\n[training]\nlevel = "off"\n'
"""Training off: a page is then its lines and the disclaimer, nothing else."""

EXEMPT = "\n[tax]\ndividend_reinvestment_exemption = true\n"

JUMPY = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\ndaily_loss_limit = "0.001"\n'
)
"""A daily-loss limit the golden run's second day breaches (as ``paper run``'s halt test)."""

TIGHT = GOLDEN_CONFIG.replace('[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.19"\n')
"""A 19% limit per stock, under buy-and-hold's 20% of each of the five: its first orders are cut to
the limit and its later top-ups skipped. With BBRI's prices restored (#160), the golden settings
spread the money five ways and never block an order."""

DEEP = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\nmax_drawdown = "0.05"\n'
)
"""A drawdown limit breached on 2021-03-08 and still breached on 2021-04-30: 9.37% below,
rounded down as every limit is written."""


def quiet(config: str = GOLDEN_CONFIG) -> str:
    assert "[training]" not in config
    return config + QUIET


def page(text: str) -> str:
    """The page as a command prints it with training off."""
    return f"{text}\n\n{DISCLAIMER}\n"


def ran_to(tmp_path: Path, day: date, config: str = GOLDEN_CONFIG) -> Cli:
    """An account opened on the golden window's first day and run up to *day*."""
    cli = paper(tmp_path, config)
    assert run_on(cli, START).code == 0
    if day != START:
        done = run_on(cli, day, "--catch-up")
        assert done.code in (0, 3), done.err
    return replace(cli, now=at(day))


def halted(tmp_path: Path) -> Cli:
    """An account halted by the daily-loss limit on 2021-02-02, the day it is left on."""
    cli = paper(tmp_path, quiet(JUMPY))
    assert run_on(cli, START).code == 0
    assert run_on(cli, trading_days()[1]).code == 3
    return replace(cli, now=at(trading_days()[1]), env={"USER": "tester"})


def retired(cli: Cli) -> None:
    """Save the account as run by a strategy since removed, as a changed configuration leaves
    it (only ``buy-and-hold`` is registered)."""
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.state.memory
        moved = Account(account.opened_on, "retired", account.state, account.settings)
        assert store.save(moved, after=account.last_day)


# paper status (M5 spec §7.1).


def test_status_before_the_first_run_says_how_to_open_the_account(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    result = cli("paper", "status")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n"
    )


def test_status_on_the_opening_day_shows_the_cash_and_the_orders_queued(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START, quiet())
    result = cli("paper", "status")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "Paper account opened on 2021-02-01, running buy-and-hold; last day run 2021-02-01.\n"
        "\n"
        "Cash: IDR 100,000,000 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 0\n"
        "Total value: IDR 100,000,000\n"
        "\n"
        "Holdings: none\n"
        "\n"
        "Queued for the next open:\n"
        "- buy 3300 ASII\n"
        "- buy 500 BBCA\n"
        "- buy 4500 BBRI\n"
        "- buy 6100 TLKM\n"
        "- buy 2800 UNVR\n"
        "\n"
        "Dividend entitlements: none\n"
        "\n"
        "Reinvestment-exemption claims: none\n"
        "\n"
        "Frozen stocks: none"
    )


def test_status_shows_each_holding_with_its_last_close_value_and_weight(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet())
    result = cli("paper", "status")
    assert result.code == 0
    assert (
        "Cash: IDR 1,587,638 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 84,138,500\n"
        "Total value: IDR 85,726,138\n"
        "\n"
        "Holdings:\n"
        "Stock  Quantity  Last close           Value  Weight\n"
        "ASII       3300   IDR 4,940  IDR 16,302,000  19.02%\n"
        "BBCA        500  IDR 30,125  IDR 15,062,500  17.57%\n"
        "BBRI       4600   IDR 3,940  IDR 18,124,000  21.14%\n"
        "TLKM       6600   IDR 3,150  IDR 20,790,000  24.25%\n"
        "UNVR       2800   IDR 4,950  IDR 13,860,000  16.17%\n"
        "\n"
        "Queued for the next open:\n"
        "- buy 100 TLKM\n"
    ) in result.out


def test_status_shows_a_dividend_entitlement_until_it_is_paid(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 8), quiet())
    result = cli("paper", "status")
    assert (
        "Dividend entitlements:\n"
        "- BBRI: IDR 445,075 before tax, ex-date 2021-04-06, paid on 2021-04-26\n"
        "- BBCA: IDR 216,000 before tax, ex-date 2021-04-08, paid on 2021-04-28\n"
    ) in result.out


def test_status_shows_open_claims_under_their_label(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 28), quiet(GOLDEN_CONFIG + EXEMPT))
    result = cli("paper", "status")
    assert "Dividend entitlements: none\n" in result.out
    assert (
        f"Reinvestment-exemption claims ({CLAIMS_LABEL}):\n"
        "- BBRI: IDR 445,075 paid on 2021-04-26, IDR 120,075 still to reinvest by 2022-03-31, "
        "IDR 325,000 protected until 2023-12-31\n"
        "- BBCA: IDR 216,000 paid on 2021-04-28, IDR 216,000 still to reinvest by 2022-03-31\n"
    ) in result.out


def test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected(
    tmp_path: Path,
) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet(GOLDEN_CONFIG + EXEMPT))
    result = cli("paper", "status")
    assert (
        "- BBRI: IDR 445,075 paid on 2021-04-26, IDR 0 still to reinvest by 2022-03-31, "
        "IDR 325,000 protected until 2023-12-31, IDR 120,075 protected until 2023-12-31\n"
        "- BBCA: IDR 216,000 paid on 2021-04-28, IDR 0 still to reinvest by 2022-03-31, "
        "IDR 195,925 protected until 2023-12-31, IDR 20,075 protected until 2023-12-31\n"
    ) in result.out
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        report = store.report(account.last_day)
        assert report is not None
    assert FIGURES["Protection.amount"] in status_page(account, report).keys


def test_a_halted_account_shows_its_halt_and_the_resume_command_and_exits_0(
    tmp_path: Path,
) -> None:
    cli = halted(tmp_path)
    result = cli("paper", "status")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Paper account opened on 2021-02-01, running buy-and-hold; last day run 2021-02-02.\n"
        "Halted on 2021-02-02: daily loss limit: the unit value fell 2.53%, the limit is 0.10%. "
        "No orders are placed until you resume it with: steadyhand-idx resume buy-and-hold\n"
        "\n"
    )


def test_status_lists_frozen_stocks_with_their_reasons() -> None:
    stock = Instrument("BBRI", "IDX", IDR)
    cash = Money(1_000, IDR)
    holdings = Holdings(
        Portfolio.empty(IDR).deposit(cash, START), frozen={stock: "suspended by the exchange"}
    )
    state = EngineState(holdings, last_day=START)
    report = paper_day(state)
    shown = status_page(Account(START, "buy-and-hold", state), report)
    assert "Frozen stocks:\n- BBRI: suspended by the exchange" in "\n".join(shown.lines)


def paper_day(state: EngineState) -> DayReport:
    """A saved report for *state*'s day with nothing in it but its cash."""
    assert state.last_day is not None
    cash = state.holdings.portfolio.cash_balance()
    nothing = Money(0, IDR)
    return DayReport(
        day=state.last_day,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=(),
        tax=nothing,
        daily_cost=nothing,
        deposit=nothing,
        frozen=(),
        halt=None,
        settled=cash,
        unsettled=nothing,
        holdings_value=nothing,
        value=cash,
        unit_price=state.units.price,
        warnings=(),
    )


def test_the_status_page_names_every_figure_it_shows(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 28), GOLDEN_CONFIG + EXEMPT)
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        report = store.report(account.last_day)
        assert report is not None
    shown = status_page(account, report)
    assert shown.keys == [
        FIGURES["DayReport.settled"],
        FIGURES["DayReport.unsettled"],
        FIGURES["DayReport.holdings_value"],
        FIGURES["DayReport.value"],
        FIGURES["Holdings.last_closes"],
        FIGURES["DividendClaim.gross"],
        FIGURES["DividendClaim.uncovered"],
        FIGURES["Protection.amount"],
    ]


# report (M5 spec §7.2).


@pytest.mark.parametrize("extra", [(), ("--income",), ("--day", "2021-02-01")])
def test_report_before_the_first_run_says_how_to_open_the_account(
    tmp_path: Path, extra: tuple[str, ...]
) -> None:
    result = paper(tmp_path)("report", *extra)
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n"
    )


def test_report_shows_the_latest_day_by_default_with_its_holdings(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet())
    result = cli("report")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith("Day report for 2021-06-30\n\n")
    assert (
        "Holdings:\n"
        "Stock  Quantity  Last close           Value  Weight\n"
        "ASII       3300   IDR 4,940  IDR 16,302,000  19.02%\n"
    ) in result.out


def test_a_days_report_shows_its_fills_its_blocked_orders_and_its_cash(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 2, 3), quiet(TIGHT))
    result = cli("report", "--day", "2021-02-02")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "Day report for 2021-02-02\n"
        "\n"
        "Fills:\n"
        "- buy 3100 ASII at IDR 6,175: IDR 19,142,500\n"
        "- buy 500 BBCA at IDR 34,875: IDR 17,437,500\n"
        "- buy 4300 BBRI at IDR 4,500: IDR 19,350,000\n"
        "- buy 5800 TLKM at IDR 3,310: IDR 19,198,000\n"
        "- buy 2700 UNVR at IDR 7,125: IDR 19,237,500\n"
        "\n"
        "Queued for the next open: none\n"
        "\n"
        "Blocked orders:\n"
        "- skipped: buy 100 ASII: already at the 19.00% limit per stock\n"
        "- skipped: buy 200 BBRI: already at the 19.00% limit per stock\n"
        "- skipped: buy 300 TLKM: already at the 19.00% limit per stock\n"
        "- skipped: buy 100 UNVR: already at the 19.00% limit per stock\n"
        "\n"
        "Cash: IDR 5,428,219 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 92,136,500\n"
        "Total value: IDR 97,564,719\n"
        "Daily charges: IDR 10,000\n"
        "Deposit: IDR 0\n"
        "\n"
        "Holdings are shown for the latest day only, 2021-02-03: steadyhand-idx report\n"
        "\n"
        "Dividends paid: none\n"
        "Dividends earned: none\n"
        "Dividend tax: IDR 0"
    )


def test_a_blocked_order_is_shown_with_its_reason_and_the_dividends_of_the_day(
    tmp_path: Path,
) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet(TIGHT))
    result = cli("report", "--day", "2021-06-29")
    assert result.code == 0
    assert (
        "Queued for the next open:\n"
        "- buy 100 UNVR\n"
        "\n"
        "Blocked orders:\n"
        "- skipped: buy 100 ASII: already at the 19.00% limit per stock\n"
        "- skipped: buy 100 BBRI: already at the 19.00% limit per stock\n"
        "- skipped: buy 100 TLKM: already at the 19.00% limit per stock\n"
    ) in result.out
    assert "Dividends paid:\n- TLKM: IDR 991,259 before tax\n" in result.out


def test_the_skipped_order_is_in_the_audit_log_under_its_key(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 29), TIGHT)
    with opened(cli) as store:
        first = next(line for line in store.audit() if line.note.key == PAPER_ORDER_SKIPPED)
    assert (first.day, first.note.text) == (
        date(2021, 2, 2),
        "skipped: buy 100 ASII: already at the 19.00% limit per stock",
    )


def test_a_report_names_the_key_of_each_blocked_orders_reason(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), TIGHT)
    with opened(cli) as store:
        cut, skipped = store.report(START), store.report(date(2021, 6, 29))
    assert cut is not None
    assert skipped is not None
    assert LIMIT_WEIGHT_CUT in day_report_page(cut, None).keys
    assert LIMIT_WEIGHT_FULL in day_report_page(skipped, None).keys


@pytest.mark.parametrize("day", ["2021-01-29", "2021-02-06", "2021-02-04"])
def test_a_day_with_no_saved_report_names_the_first_and_last_saved(
    tmp_path: Path, day: str
) -> None:
    cli = ran_to(tmp_path, date(2021, 2, 3))
    result = cli("report", "--day", day)
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        f"steadyhand-idx: there is no report for {day}; the saved days run from 2021-02-01 "
        "to 2021-02-03\n"
    )


def test_the_income_report_is_the_backtests_over_the_same_days(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, END, quiet())
    result = cli("report", "--income")
    assert (result.code, result.err) == (0, "")
    reference = golden_backtest(cli, END, goal=True).run.income
    assert reference is not None
    assert result.out == page("\n".join(income_page(reference).lines))
    # The golden record's income figures (tests/fixtures/golden), as the page writes them.
    assert (
        "Goal: IDR 1,000,000 a month\n"
        "Received: IDR 202,442 a month, 20.24% of the goal\n"
        "Run-rate: IDR 206,964 a month, 20.70% of the goal\n"
        "\n"
        f"{PROJECTION_LABEL}:\n"
        "Reaching IDR 1,000,000 a month, adding IDR 0 a month\n"
        "- pessimistic: from IDR 2,207,626 a year, growing 0.00% a year: not within 50 years\n"
        "- base: from IDR 2,759,533 a year, growing 5.00% a year: the goal in 18.0 years\n"
        "- optimistic: from IDR 2,759,533 a year, growing 6.09% a year: the goal in 16.0 years\n"
    ) in result.out


def test_the_day_a_limit_halts_the_account_shows_the_halt(tmp_path: Path) -> None:
    result = halted(tmp_path)("report")
    assert result.code == 0
    assert (
        "\n\nHalted on 2021-02-02: daily loss limit: the unit value fell 2.53%, the limit is "
        "0.10%\n"
    ) in result.out


def test_a_days_frozen_stocks_warnings_and_notes_are_listed_with_their_keys() -> None:
    stock = Instrument("BBRI", "IDX", IDR)
    state = EngineState(Holdings(Portfolio.empty(IDR).deposit(Money(1_000, IDR), START)))
    report = replace(
        paper_day(replace(state, last_day=START)),
        frozen=((stock, "suspended by the exchange"),),
        warnings=(Note(DATA_BAR_REFUSED, "BBRI: the source refused the day"),),
        notes=(Note(CORPORATE_SPLIT_ORDER_CANCELLED, "BBRI: an order was cancelled"),),
    )
    shown = day_report_page(report, None)
    assert "\n".join(shown.lines).endswith(
        "\n\nFrozen stocks:\n- BBRI: suspended by the exchange"
        "\n\nWarnings:\n- BBRI: the source refused the day"
        "\n\nNotes:\n- BBRI: an order was cancelled"
    )
    assert shown.keys[-2:] == [DATA_BAR_REFUSED, CORPORATE_SPLIT_ORDER_CANCELLED]


# resume (M5 spec §7.3, core spec §6.1).


def test_resume_before_the_first_run_says_how_to_open_the_account(tmp_path: Path) -> None:
    result = paper(tmp_path)("resume", "buy-and-hold")
    assert (result.code, result.err) == (
        2,
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n",
    )


def test_resume_must_name_the_accounts_strategy(tmp_path: Path) -> None:
    cli = halted(tmp_path)
    before = tables(cli)
    result = cli("resume", "momentum", stdin="resume\n")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: the paper account runs buy-and-hold, not momentum; to resume it, run: "
        "steadyhand-idx resume buy-and-hold\n"
    )
    assert tables(cli) == before


def test_resume_when_nothing_is_halted_says_so_and_changes_nothing(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START, quiet())
    before = tables(cli)
    result = cli("resume", "buy-and-hold", stdin="resume\n")
    assert (result.code, result.err) == (0, "")
    assert result.out == page("The paper account is not halted; there is nothing to resume.")
    assert tables(cli) == before


def test_a_typed_resume_clears_the_halt_and_the_next_day_orders_again(tmp_path: Path) -> None:
    cli = halted(tmp_path)
    result = cli("resume", "buy-and-hold", stdin="resume\n")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "The paper account halted on 2021-02-02: daily loss limit: the unit value fell 2.53%, "
        "the limit is 0.10%.\n"
        "Type resume to resume ordering: "
        "Resumed. From the next day run, the strategy's orders are placed again."
    )
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.state.halt is None
        line = store.audit()[-1]
    assert (line.day, line.note.key, line.note.text) == (
        trading_days()[1],
        PAPER_RESUMED,
        (
            "resumed ordering after the halt of 2021-02-02 (daily loss limit: the unit value "
            "fell 2.53%, the limit is 0.10%), by tester"
        ),
    )
    later = run_on(cli, trading_days()[2])
    assert later.code == 0, later.err
    with opened(cli) as store:
        assert store.runs()[-1].outcome is Outcome.RAN


def test_resume_names_who_resumed_from_logname_or_else_unknown(tmp_path: Path) -> None:
    cli = replace(halted(tmp_path), env={"LOGNAME": "operator"})
    assert cli("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(cli) as store:
        assert store.audit()[-1].note.text.endswith(", by operator")
    again = halted(tmp_path / "again")
    assert replace(again, env={})("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(again) as store:
        assert store.audit()[-1].note.text.endswith(", by unknown")
    both = replace(halted(tmp_path / "both"), env={"USER": "tester", "LOGNAME": "operator"})
    assert both("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(both) as store:
        assert store.audit()[-1].note.text.endswith(", by tester")


@pytest.mark.parametrize("answer", ["", "\n", "yes\n", "Resume\n", " resume\n"])
def test_any_other_answer_leaves_the_halt_in_place(tmp_path: Path, answer: str) -> None:
    cli = halted(tmp_path)
    before = tables(cli)
    result = cli("resume", "buy-and-hold", stdin=answer)
    assert result.code == 2
    assert result.err == (
        f"steadyhand-idx: you typed {answer.rstrip(chr(10))!r}, not 'resume'; nothing was changed\n"
    )
    assert tables(cli) == before


def test_resume_is_refused_while_the_drawdown_is_still_past_its_limit(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 30), quiet(DEEP))
    before = tables(cli)
    result = cli("resume", "buy-and-hold", stdin="resume\n")
    assert (result.code, result.out) == (3, "")
    assert result.err == (
        "steadyhand-idx: the unit value is still 9.12% below its high-water mark, at or past "
        "the 5.00% drawdown limit; the halt stays until it recovers or you raise "
        "risk.max_drawdown\n"
    )
    assert tables(cli) == before
    raised = DEEP.replace('max_drawdown = "0.05"', 'max_drawdown = "0.10"')
    cli.config.write_text(quiet(raised), encoding="utf-8")
    assert cli("resume", "buy-and-hold", stdin="resume\n").code == 0
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.state.halt is None
        assert store.audit()[-1].note.key == PAPER_RESUMED


def drawn_down() -> tuple[Account, Halt]:
    """An account halted by the drawdown kill switch whose unit value is 5.00% below its
    high-water mark."""
    halt = Halt(START, Note(RISK_HALT_DRAWDOWN, "drawdown kill switch"))
    cash = Portfolio.empty(IDR).deposit(Money(1_000, IDR), START)
    units = UnitValue(Decimal(1_000), Decimal("0.95"), Decimal(1))
    return Account(START, "buy-and-hold", EngineState(Holdings(cash), units, halt, START)), halt


@pytest.mark.parametrize("limit", ["0.0499", "0.05"])
def test_resume_is_refused_at_or_past_the_drawdown_limit(limit: str) -> None:
    account, _halt = drawn_down()
    with pytest.raises(HaltCausePresentError, match=r"still 5\.00% below"):
        check_resume(account, "buy-and-hold", RiskLimits(max_drawdown=Decimal(limit)))


def test_resume_is_allowed_just_inside_the_drawdown_limit() -> None:
    account, halt = drawn_down()
    assert check_resume(account, "buy-and-hold", RiskLimits(max_drawdown=Decimal("0.0501"))) == halt


class RacingScreen(io.StringIO):
    """A terminal on which, once the question is shown, another ``paper run`` saves a day
    before the answer is typed: the account changes between the question and the answer."""

    def __init__(self, other: Cli) -> None:
        super().__init__()
        self._other = other
        self.raced = False

    def flush(self) -> None:
        if not self.raced:
            self.raced = True
            assert self._other("paper", "run").code == 3
        super().flush()


def test_an_account_changed_while_asking_is_left_as_the_other_run_saved_it(
    tmp_path: Path,
) -> None:
    cli = halted(tmp_path)
    other = replace(cli, now=at(trading_days()[2]))
    screen, err = RacingScreen(other), io.StringIO()
    env = {"STEADYHAND_HOME": str(cli.home)}
    answer = io.StringIO("resume\n")
    world = World(answer, screen, err, env, lambda: cli.now, recorded_source)
    assert main(["resume", "buy-and-hold"], world) == 3
    assert screen.raced
    assert err.getvalue() == (
        "steadyhand-idx: another paper run saved a day while you were answering; nothing was "
        "changed, run the command again\n"
    )
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert account.last_day == trading_days()[2]
        assert account.state.halt is not None
        assert PAPER_RESUMED not in [line.note.key for line in store.audit()]


# paper switch (M5 spec §7.3).


def test_switch_before_the_first_run_says_how_to_open_the_account(tmp_path: Path) -> None:
    result = paper(tmp_path)("paper", "switch", "buy-and-hold")
    assert (result.code, result.err) == (
        2,
        "steadyhand-idx: there is no paper account yet; run steadyhand-idx paper run first\n",
    )


def test_switch_must_name_the_configured_strategy(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START)
    retired(cli)
    before = tables(cli)
    result = cli("paper", "switch", "momentum", stdin="momentum\n")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: steadyhand.toml names the strategy buy-and-hold, not momentum; edit "
        "[strategy] name first, then run: steadyhand-idx paper switch momentum\n"
    )
    assert tables(cli) == before


def test_switch_to_the_strategy_already_running_is_refused(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, START)
    before = tables(cli)
    result = cli("paper", "switch", "buy-and-hold", stdin="buy-and-hold\n")
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: the paper account already runs buy-and-hold; there is nothing to switch\n"
    )
    assert tables(cli) == before


def test_switch_is_refused_while_the_account_is_halted(tmp_path: Path) -> None:
    cli = halted(tmp_path)
    retired(cli)
    before = tables(cli)
    result = cli("paper", "switch", "buy-and-hold", stdin="buy-and-hold\n")
    assert (result.code, result.out) == (3, "")
    assert result.err == (
        "steadyhand-idx: the paper account halted on 2021-02-02: daily loss limit: the unit "
        "value fell 2.53%, the limit is 0.10%; no orders are placed until you resume it with: "
        "steadyhand-idx resume retired\n"
    )
    assert tables(cli) == before


def test_a_typed_switch_keeps_the_holdings_and_cash_and_clears_the_memory(
    tmp_path: Path,
) -> None:
    cli = replace(ran_to(tmp_path, trading_days()[1], quiet()), env={"USER": "tester"})
    retired(cli)
    with opened(cli) as store:
        before = store.account()
        assert before is not None
    result = cli("paper", "switch", "buy-and-hold", stdin="buy-and-hold\n")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "The paper account runs retired; steadyhand.toml names buy-and-hold.\n"
        "Switching keeps the holdings and the cash and clears what retired remembered; "
        "buy-and-hold trades from the next day run.\n"
        "Type buy-and-hold to switch: "
        "Switched the paper account to buy-and-hold."
    )
    with opened(cli) as store:
        after = store.account()
        assert after is not None
        line = store.audit()[-1]
    assert after.strategy == "buy-and-hold"
    assert after.state.memory == {}
    assert after.state.holdings == before.state.holdings
    assert after.state.units == before.state.units
    assert (after.last_day, after.settings) == (before.last_day, before.settings)
    assert (line.day, line.note.key, line.note.text) == (
        trading_days()[1],
        PAPER_STRATEGY_SWITCHED,
        (
            "switched the strategy from retired to buy-and-hold, keeping the holdings and the "
            "cash, by tester"
        ),
    )
    assert run_on(cli, trading_days()[2]).code == 0


@pytest.mark.parametrize("answer", ["", "yes\n", "retired\n"])
def test_any_other_answer_leaves_the_strategy_as_it_was(tmp_path: Path, answer: str) -> None:
    cli = ran_to(tmp_path, START)
    retired(cli)
    before = tables(cli)
    result = cli("paper", "switch", "buy-and-hold", stdin=answer)
    assert result.code == 2
    assert result.err == (
        f"steadyhand-idx: you typed {answer.rstrip(chr(10))!r}, not 'buy-and-hold'; nothing was "
        "changed\n"
    )
    assert tables(cli) == before
```

**`tests/cli/test_paper_run.py`** (changed: 6 edits)

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    PAPER_ACCOUNT_OPENED,
    PAPER_ORDER_CUT,
    PAPER_ORDER_QUEUED,
```
with:
```python
    PAPER_ACCOUNT_OPENED,
    PAPER_ORDER_QUEUED,
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    assert result.out.startswith(
        "2021-02-01: 0 fill(s), 4 order(s) queued, value IDR 100,000,000\n\n"
        "Ran 1 day(s): 2021-02-01. Read a day's report with: steadyhand-idx report\n"
```
with:
```python
    assert result.out.startswith(
        "2021-02-01: 0 fill(s), 5 order(s) queued, value IDR 100,000,000\n\n"
        "Ran 1 day(s): 2021-02-01. Read a day's report with: steadyhand-idx report\n"
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
            (START, PAPER_ORDER_QUEUED, f"queued: buy {order} at the next open")
            for order in ("4100 ASII", "700 BBCA", "7700 TLKM", "3500 UNVR")
        ]
```
with:
```python
            (START, PAPER_ORDER_QUEUED, f"queued: buy {order} at the next open")
            for order in ("3300 ASII", "500 BBCA", "4500 BBRI", "6100 TLKM", "2800 UNVR")
        ]
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    assert result.out.startswith(
        "2021-02-02: 4 fill(s), 0 order(s) queued, value IDR 97,617,660\n"
        "2021-02-03: 0 fill(s), 0 order(s) queued, value IDR 98,786,660\n"
    )
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        cut = [line.note for line in store.audit() if line.note.key == PAPER_ORDER_CUT]
        assert [(line.text) for line in cut] == [
            "cut: buy UNVR from 3500 to 3400 shares: cut to the IDR 24,626,548 that can be spent"
        ]

```
with:
```python
    assert result.out.startswith(
        "2021-02-02: 5 fill(s), 0 order(s) queued, value IDR 97,464,230\n"
        "2021-02-03: 0 fill(s), 0 order(s) queued, value IDR 98,501,230\n"
    )
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        caught_up = store.report(trading_days()[1])
    assert caught_up is not None
    assert [fill.order.instrument.symbol for fill in caught_up.fills] == [
        "ASII",
        "BBCA",
        "BBRI",
        "TLKM",
        "UNVR",
    ]

```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    assert halted.code == 3
    assert halted.out.startswith("2021-02-02: 4 fill(s), 0 order(s) queued")
    assert halted.err == (
        "steadyhand-idx: the paper account halted on 2021-02-02: daily loss limit: the unit "
        "value fell 2.38%, the limit is 0.10%; no orders are placed until you resume it with: "
        "steadyhand-idx resume buy-and-hold\n"
```
with:
```python
    assert halted.code == 3
    assert halted.out.startswith("2021-02-02: 5 fill(s), 0 order(s) queued")
    assert halted.err == (
        "steadyhand-idx: the paper account halted on 2021-02-02: daily loss limit: the unit "
        "value fell 2.53%, the limit is 0.10%; no orders are placed until you resume it with: "
        "steadyhand-idx resume buy-and-hold\n"
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    assert account is not None
    # buy-and-hold had spent all but Rp 341,160 of the starting cash: monthly-savings sizes its
    # instalment from that cash, not from the portfolio's value (M6 spec §5).
    cash = account.state.holdings.portfolio.spendable_cash(trading_days()[1])
    assert cash == Money(341_160, IDR)
    assert account.state.memory == {"instalment": "85290", "due": "3", "month": "2021-02"}
```
with:
```python
    assert account is not None
    # buy-and-hold had spent all but Rp 1,579,730 of the starting cash: monthly-savings sizes its
    # instalment from that cash, not from the portfolio's value (M6 spec §5).
    cash = account.state.holdings.portfolio.spendable_cash(trading_days()[1])
    assert cash == Money(1_579_730, IDR)
    assert account.state.memory == {"instalment": "394932", "due": "3", "month": "2021-02"}
```

**`tests/cli/test_reports.py`** (changed: 6 edits)

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python
import pytest
from record_golden import END, RECORDED, START, recorded, settings, universe

from steadyhand import (
    IDR,
```
with:
```python
import pytest
from record_golden import END, RECORDED, START, replay, settings, universe

from steadyhand import (
    DATA_BAR_REFUSED,
    IDR,
```

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python
    Money,
    PortfolioView,
```
with:
```python
    Money,
    Note,
    PortfolioView,
```

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python
)
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules, YahooDataSource
from steadyhand_idx.reports import (
```
with:
```python
)
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules
from steadyhand_idx.reports import (
```

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python

def no_wait(seconds: float) -> None:
    del seconds


@pytest.fixture(scope="module")
def market(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Market]:
    yahoo = YahooDataSource(download=recorded, sleep=no_wait)
    with BarCache(tmp_path_factory.mktemp("bars") / "bars.sqlite") as cache:
        source = CachedDataSource(yahoo, cache, today=lambda: RECORDED)
        yield Market(universe(), source, IdxMarketRules())
```
with:
```python

@pytest.fixture(scope="module")
def market(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Market]:
    with BarCache(tmp_path_factory.mktemp("bars") / "bars.sqlite") as cache:
        source = CachedDataSource(replay(), cache, today=lambda: RECORDED)
        yield Market(universe(), source, IdxMarketRules())
```

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python
    assert lines[3].split("  ")[0] == "Final value"
    assert lines[3].endswith("IDR 100,000,000   IDR 97,889,490")

```
with:
```python
    assert lines[3].split("  ")[0] == "Final value"
    assert lines[3].endswith("IDR 100,000,000   IDR 96,825,198")

```

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python
    quiet = replace(result, warnings=())
    assert "Warnings:" in backtest_page(result, ()).lines
    assert "Warnings:" not in backtest_page(quiet, ()).lines
    summary, _ = backtest_files(quiet, tmp_path)
    assert "## Warnings" not in summary.read_text(encoding="utf-8")

```
with:
```python
    quiet = replace(result, warnings=())
    warned = replace(result, warnings=(Note(DATA_BAR_REFUSED, "BBRI: the source refused a day"),))
    assert "Warnings:" in backtest_page(warned, ()).lines
    assert "Warnings:" not in backtest_page(quiet, ()).lines
    summary, _ = backtest_files(quiet, tmp_path)
    assert "## Warnings" not in summary.read_text(encoding="utf-8")
    summary, _ = backtest_files(warned, tmp_path / "warned")
    assert "\n## Warnings\n\n- BBRI: the source refused a day\n" in summary.read_text(
        encoding="utf-8"
    )

```

**`tests/golden/test_golden_backtest.py`** (changed: 8 edits)

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    CLAIMS_LABEL,
    DATA_BAR_REFUSED,
    DATA_DIVIDENDS_HISTORY_REFUSED,
```
with:
```python
    CLAIMS_LABEL,
    DATA_DIVIDENDS_HISTORY_REFUSED,
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
        # Reinvested by the deadline: ASII's buy on 2 July 2021 (1,900 x 5,050 = 9,595,000)
        # covers the four claims paid before it, oldest first: 86,400 (200 BBCA shares x Rp432,
        # before the split), 139,200 (1,600 ASII x 87) and 140,000 (1,400 UNVR x 100) stay whole.
        ["BBCA", "2021-04-08", "2021-04-28", 86_400, "2022-03-31", 0, [[86_400, until]]],
        ["ASII", "2021-05-03", "2021-05-27", 139_200, "2022-03-31", 0, [[139_200, until]]],
        ["UNVR", "2021-06-08", "2021-06-28", 140_000, "2022-03-31", 0, [[140_000, until]]],
        # Broken after reinvestment: selling 2,400 of the 2,500 BBCA shares on 2 November
        # releases 16,128,478 x 2,400 / 2,500 = 15,483,338.88, rounded up to 15,483,339, so
        # 645,139 stays invested against 869,630 protected. The 224,491 short at the close of
        # 4 November, the sale's settlement date, breaks from the newest claim, TLKM's
        # (3,000 x 168.01 = 504,030): 504,030 - 224,491 = 279,539 stays protected.
        ["TLKM", "2021-06-09", "2021-06-29", 504_030, "2022-03-31", 0, [[279_539, until]]],
        # Still open at the end: 100 BBCA x 120, with a year to be reinvested.
        ["BBCA", "2022-03-28", "2022-04-18", 12_000, "2023-03-31", 12_000, []],
    ]
    # 10% of 224,491 is 22,449.1, rounded up. Taxed at the deadline: ASII's 3,500 x 45 = 157,500
    # and BBCA's 100 x 25 = 2,500 were never reinvested, so 15,750 + 250 on 1 April 2022.
    assert stored["taxes"] == [["2021-11-04", 22_450], ["2022-04-01", 16_000]]
    assert [note[:2] for note in stored["notes"]] == [
```
with:
```python
        # Reinvested by the deadline: ASII's buy on 2 July 2021 (1,900 x 5,050 = 9,595,000)
        # covers the five claims paid before it, oldest first: 217,592 (2,200 BBRI x Rp98.9057,
        # its restored dividend, rounded down), 86,400 (200 BBCA shares x Rp432, before the
        # split), 139,200 (1,600 ASII x 87) and 140,000 (1,400 UNVR x 100) stay whole.
        ["BBRI", "2021-04-06", "2021-04-26", 217_592, "2022-03-31", 0, [[217_592, until]]],
        ["BBCA", "2021-04-08", "2021-04-28", 86_400, "2022-03-31", 0, [[86_400, until]]],
        ["ASII", "2021-05-03", "2021-05-27", 139_200, "2022-03-31", 0, [[139_200, until]]],
        ["UNVR", "2021-06-08", "2021-06-28", 140_000, "2022-03-31", 0, [[140_000, until]]],
        # Broken after reinvestment: selling 2,400 of the 2,500 BBCA shares on 2 November, and
        # every other share, releases 16,128,478 x 2,400 / 2,500 = 15,483,338.88, rounded up to
        # 15,483,339, so 645,139 stays invested against 1,087,222 protected. The 442,083 short at
        # the close of 4 November, the sale's settlement date, breaks from the newest claim,
        # TLKM's (3,000 x 168.01 = 504,030): 504,030 - 442,083 = 61,947 stays protected.
        ["TLKM", "2021-06-09", "2021-06-29", 504_030, "2022-03-31", 0, [[61_947, until]]],
        # Still open at the end: 100 BBCA x 120, with a year to be reinvested.
        ["BBCA", "2022-03-28", "2022-04-18", 12_000, "2023-03-31", 12_000, []],
    ]
    # 10% of 442,083 is 44,208.3, rounded up. Taxed at the deadline: ASII's 3,500 x 45 = 157,500
    # and BBCA's 100 x 25 = 2,500 were never reinvested, so 15,750 + 250 on 1 April 2022.
    assert stored["taxes"] == [["2021-11-04", 44_209], ["2022-04-01", 16_000]]
    assert [note[:2] for note in stored["notes"]] == [
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    taxed = {month[0]: month[2] for month in stored["income"]["received"]["by_month"] if month[2]}
    assert taxed == {"2021-11-01": 22_450, "2022-04-01": 16_000}

```
with:
```python
    taxed = {month[0]: month[2] for month in stored["income"]["received"]["by_month"] if month[2]}
    assert taxed == {"2021-11-01": 44_209, "2022-04-01": 16_000}

```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    # 260, 355, 553 grew. UNVR's 183, 241, 194 are its dividends of before its 1-for-5 split of
    # January 2020 restated, so 194 >= 183 passes (unrestated, 915 would not). BBRI passes but
    # its prices are refused that day, so it cannot be bought; ASII's 184 < 190 fails, and
    # TLKM's look-back was refused. Two picks at half each, the risk limit's 25% bought on the
    # 2nd: 700 x 34,875 and 3,500 x 7,125, just under Rp25,000,000 each.
    assert [fill[:5] for fill in stored["fills"] if fill[0] == "2021-02-02"] == [
        ["2021-02-02", "BBCA", "buy", 700, 34_875],
        ["2021-02-02", "UNVR", "buy", 3_500, 7_125],
    ]
    # 3 January 2022 tests 2019 to 2021. BBCA's 71, 110.6, 111.4 (restated by its October 2021
    # split) pass; UNVR's 166 < 241 fails, and so do BBRI's 89.9 < 120.2 and ASII; TLKM's
    # history is still incomplete. One pick under min_stocks 2: the note, and UNVR is sold.
    assert stored["notes"] == [
```
with:
```python
    # 260, 355, 553 grew. UNVR's 183, 241, 194 are its dividends of before its 1-for-5 split of
    # January 2020 restated, so 194 >= 183 passes (unrestated, 915 would not). BBRI's restored
    # 106.7, 132.2, 168.2 grew; ASII's 184 < 190 fails, and TLKM's look-back was refused. Three
    # pass for two places, so the picks spread their pay months: none is crowded yet, so the
    # higher trailing yield goes first, BBRI's 168.2 a share on a close of 4,400, then UNVR's
    # above BBCA's. Half each, the risk limit's 25%, sized at the 1st's close and bought at the
    # 2nd's open: 25,000,000 / 4,400 and / 7,025, in lots of 100.
    assert [fill[:5] for fill in stored["fills"] if fill[0] == "2021-02-02"] == [
        ["2021-02-02", "BBRI", "buy", 5_600, 4_500],
        ["2021-02-02", "UNVR", "buy", 3_500, 7_125],
    ]
    # 3 January 2022 tests 2019 to 2021. BBCA's 71, 110.6, 111.4 (restated by its October 2021
    # split) pass; UNVR's 166 < 241 fails, and so do BBRI's 98.9 < 132.2 and ASII; TLKM's
    # history is still incomplete. One pick under min_stocks 2: the note, BBRI and UNVR are
    # sold, and BBCA is bought.
    assert stored["notes"] == [
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    assert [fill[:3] for fill in stored["fills"] if fill[2] == "sell"] == [
        ["2022-01-04", "UNVR", "sell"]
    ]
    assert stored["positions"] == {"BBCA": 3_500}
    assert [warning[0] for warning in stored["warnings"]] == [
        DATA_BAR_REFUSED,
        DATA_DIVIDENDS_HISTORY_REFUSED,
    ]
    assert stored["warnings"][1][1].startswith(
        "TLKM: the data source refused its corporate actions from 2018-01-01 to 2021-01-31, "
```
with:
```python
    assert [fill[:3] for fill in stored["fills"] if fill[2] == "sell"] == [
        ["2022-01-04", "BBRI", "sell"],
        ["2022-01-04", "UNVR", "sell"],
    ]
    assert stored["positions"] == {"BBCA": 2_900}
    assert [warning[0] for warning in stored["warnings"]] == [DATA_DIVIDENDS_HISTORY_REFUSED]
    assert stored["warnings"][0][1].startswith(
        "TLKM: the data source refused its corporate actions from 2018-01-01 to 2021-01-31, "
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
def test_the_window_holds_the_events_it_was_chosen_for(tmp_path: Path) -> None:
    """The golden file is only worth pinning if the run meets a split, dividends and refusals."""
    result = run(tmp_path)
```
with:
```python
def test_the_window_holds_the_events_it_was_chosen_for(tmp_path: Path) -> None:
    """The golden file is only worth pinning if the run meets a split, dividends, and prices
    restored from an adjustment Yahoo does not report (#160)."""
    result = run(tmp_path)
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    paid = {e.instrument.symbol for report in result.run.reports for e in report.paid}
    assert paid == {"ASII", "BBCA", "TLKM", "UNVR"}
    assert "BBRI" not in held
    assert result.warnings[0].key == DATA_BAR_REFUSED
    assert result.warnings[0].text.startswith(
        "BBRI: the data source refused 146 day(s) (2021-02-01 to 2021-09-07),"
    )

```
with:
```python
    paid = {e.instrument.symbol for report in result.run.reports for e in report.paid}
    assert paid == {"ASII", "BBCA", "BBRI", "TLKM", "UNVR"}
    # BBRI's prices up to 2021-09-07 are restored (f = 1.100019), so it is ordered on the first
    # day and bought at the next open, and its 2021 dividend is credited at the restored Rp98.9057
    # a share.
    (bbri,) = [
        e for report in result.run.reports for e in report.paid if e.instrument.symbol == "BBRI"
    ]
    assert (bbri.ex_date, bbri.gross) == (date(2021, 4, 6), Money(445_075, IDR))  # 4,500 shares
    assert held["BBRI"] == 4_600
    assert result.warnings == ()

```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    # Every dividend of the trailing year was paid in the run, on the pay date the calendar uses.
    assert len(expected) == len(paid) == 7
    assert all(e.pay_date == paid[(e.instrument.symbol, e.ex_date)].pay_date for e in expected)
    # BBCA's 2021-04-08 dividend: Rp432 a share on the 700 shares held before the 1-for-5 split,
    # and Rp86.4 a share, restated, on the 3,500 held after it. Rp302,400 either way.
    bbca = paid[("BBCA", date(2021, 4, 8))]
    assert bbca.gross == Money(302_400, IDR)
    assert bbca in expected
```
with:
```python
    # Every dividend of the trailing year was paid in the run, on the pay date the calendar uses.
    assert len(expected) == len(paid) == 8
    assert all(e.pay_date == paid[(e.instrument.symbol, e.ex_date)].pay_date for e in expected)
    # BBCA's 2021-04-08 dividend: Rp432 a share on the 500 shares held before the 1-for-5 split,
    # and Rp86.4 a share, restated, on the 2,500 held after it. Rp216,000 either way.
    bbca = paid[("BBCA", date(2021, 4, 8))]
    assert bbca.gross == Money(216_000, IDR)
    assert bbca in expected
```

**`tests/golden/test_golden_snapshot.py`** (changed: 1 edit)

<!-- edit: tests/golden/test_golden_snapshot.py -->
Replace:
```python
    off, on = golden
    assert len(on.run.final.holdings.claims) == 5
    for result in (off, on):
```
with:
```python
    off, on = golden
    assert len(on.run.final.holdings.claims) == 6
    for result in (off, on):
```

**`tests/idx/test_cache.py`** (changed: 10 edits)

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.yahoo import (
```
with:
```python
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import Restoration
from steadyhand_idx.yahoo import (
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
    history = history_from_json(FIXTURES / "BBCA.JK_2021-09-01_2021-11-30.json")
    return unadjust(history, BBCA, calendar(), start, end)

```
with:
```python
    history = history_from_json(FIXTURES / "BBCA.JK_2021-09-01_2021-11-30.json")
    return unadjust(history, BBCA, calendar(), (start, end))

```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
        CacheSchemaError,
        match=r"c\.sqlite is at cache schema 3, newer than this steadyhand-idx knows \(2\);",
    ):
```
with:
```python
        CacheSchemaError,
        match=r"c\.sqlite is at cache schema 4, newer than this steadyhand-idx knows \(3\);",
    ):
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
class Counting:
    """A real YahooDataSource on a recording, counting what reaches it."""

    def __init__(self, name: str) -> None:
        self.history = history_from_json(FIXTURES / name)
        self.asked: list[tuple[date, date]] = []
        self.source = YahooDataSource(calendar(), download=self._download, sleep=lambda _: None)

```
with:
```python
class Counting:
    """A real YahooDataSource on a recording, counting what reaches it. A whole-history request
    (#160) gets the same recording."""

    def __init__(self, name: str, today: date = date(2026, 9, 25)) -> None:
        self.history = history_from_json(FIXTURES / name)
        self.asked: list[tuple[date, date]] = []
        self.source = YahooDataSource(
            calendar(), download=self._download, sleep=lambda _: None, today=lambda: today
        )

```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
def source_for(cache: BarCache, name: str, today: date) -> tuple[CachedDataSource, Counting]:
    counting = Counting(name)
    return CachedDataSource(counting.source, cache, calendar(), today=lambda: today), counting
```
with:
```python
def source_for(cache: BarCache, name: str, today: date) -> tuple[CachedDataSource, Counting]:
    counting = Counting(name, today)
    return CachedDataSource(counting.source, cache, calendar(), today=lambda: today), counting
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
def test_unrecoverable_prices_are_never_cached(cache: BarCache) -> None:
    source, _ = source_for(cache, "BBRI.JK_2021-08-02_2021-09-30.json", date(2026, 9, 25))
    with pytest.raises(DataUnavailableError, match="cannot be recovered"):
```
with:
```python
def test_unrecoverable_prices_are_never_cached(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBRI.JK_2021-08-02_2021-09-30.json", date(2026, 9, 25))
    # Three refused days from 3 September are 12 prices, too few to prove a factor (#160).
    rows = tuple(row for row in counting.history.rows if row.day >= date(2021, 9, 3))
    counting.history = replace(counting.history, rows=rows)
    with pytest.raises(DataUnavailableError, match="cannot be recovered"):
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
LOOK_BACK = (date(2017, 1, 31), date(2021, 9, 30))
"""BBRI's years before a run: its prices up to 2021-09-07 cannot be recovered."""

```
with:
```python
LOOK_BACK = (date(2017, 1, 31), date(2021, 9, 30))
"""BBRI's years before a run. Its prices up to 2021-09-07 carry an unreported factor, restored
(#160); its rows before 2017-11-10 have volumes that are not whole shares, so they stay refused."""

```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
        assert old.schema_version == 1
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS)
    with BarCache(path) as upgraded:
```
with:
```python
        assert old.schema_version == 1
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS[:2])
    with BarCache(path) as upgraded:
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
    first = source.corporate_actions(BBRI, *LOOK_BACK)
    assert [(a.ex_date, a.per_share) for a in first if isinstance(a, CashDividend)] == [
        (date(2017, 3, 23), Decimal("389.63463")),
        (date(2018, 4, 2), Decimal("97.04093")),
        (date(2019, 5, 24), Decimal("120.15633")),
        (date(2020, 2, 27), Decimal("152.90845")),
        (date(2021, 4, 6), Decimal("89.91268")),
    ]
    in_2019 = [action for action in first if action.ex_date.year == 2019]
    assert source.corporate_actions(BBRI, date(2019, 1, 1), date(2019, 12, 31)) == in_2019
    assert counting.asked == [LOOK_BACK]
    assert cache.fetched(BBRI) == []
    with pytest.raises(DataUnavailableError, match="cannot be recovered"):
```
with:
```python
    first = source.corporate_actions(BBRI, *LOOK_BACK)
    # Each restored: Yahoo's amount times 1.100019, to Rp0.0001 (#160 spec §4.5).
    assert [(a.ex_date, a.per_share) for a in first if isinstance(a, CashDividend)] == [
        (date(2017, 3, 23), Decimal("428.6055")),
        (date(2018, 4, 2), Decimal("106.7469")),
        (date(2019, 5, 24), Decimal("132.1742")),
        (date(2020, 2, 27), Decimal("168.2022")),
        (date(2021, 4, 6), Decimal("98.9057")),
    ]
    in_2019 = [action for action in first if action.ex_date.year == 2019]
    assert source.corporate_actions(BBRI, date(2019, 1, 1), date(2019, 12, 31)) == in_2019
    # The look-back, then the whole history once, for the runs (#160 spec §5).
    assert counting.asked == [LOOK_BACK, (date(2014, 1, 6), date(2026, 9, 25))]
    assert cache.fetched(BBRI) == []
    (stored,) = source.restorations(BBRI, *LOOK_BACK)
    assert (stored.first, stored.last, stored.factor) == (
        date(2017, 1, 31),
        date(2021, 9, 7),
        Decimal("1.100019"),
    )
    with pytest.raises(DataUnavailableError, match="cannot be recovered"):
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
    assert cache.fetched_actions(BBCA) == [span]
```
with:
```python
    assert cache.fetched_actions(BBCA) == [span]


RESTORED = Restoration(BBRI, date(2017, 1, 31), date(2021, 9, 7), Decimal("1.100019"), 4_412)
"""BBRI's proven run in its five-year recording (#160)."""


def test_the_restorations_migration_reads_every_range_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.sqlite"
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS[:2])
    with BarCache(path) as old:
        old.store(BBCA, SEP, *bbca(*SEP))
        old.store_actions(BBCA, OCT, [Split(BBCA, date(2021, 10, 13), 1, 5)])
        assert old.schema_version == 2
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS)
    for _ in range(2):  # the second opening finds nothing left to run
        with BarCache(path) as upgraded:
            assert upgraded.schema_version == 3
            assert upgraded.fetched(BBCA) == []
            assert upgraded.fetched_actions(BBCA) == []
            assert upgraded.actions(BBCA, SEP[0], OCT[1]) == []
            assert len(upgraded.bars(BBCA, *SEP)) == len(calendar().trading_days(*SEP))
            assert upgraded.restorations(BBCA, SEP[0], OCT[1]) == []


def test_a_restoration_round_trips_and_a_different_one_is_a_conflict(cache: BarCache) -> None:
    cache.store(BBRI, SEP, [], [], [RESTORED])
    cache.store_actions(BBRI, SEP, [], [RESTORED])  # the same again changes nothing
    assert cache.restorations(BBRI, date(2021, 9, 7), date(2021, 9, 30)) == [RESTORED]
    assert cache.restorations(BBRI, date(2021, 9, 8), date(2021, 9, 30)) == []
    assert cache.restorations(BBCA, *SEP) == []
    changed = replace(RESTORED, factor=Decimal("1.100020"))
    august = (date(2021, 8, 2), date(2021, 8, 31))
    with pytest.raises(CacheConflictError, match=r"^BBRI 2017-01-31: cached restoration"):
        cache.store_actions(BBRI, august, [CashDividend(BBRI, august[0], Decimal(1))], [changed])
    assert cache.actions(BBRI, *august) == []
    assert cache.fetched_actions(BBRI) == [SEP]  # nothing from the refused range was stored
    with pytest.raises(ValueError, match=r"^BBRI's restoration 2017-01-31 to 2021-09-07 does not"):
        cache.store(BBRI, OCT, [], [], [RESTORED])
    with pytest.raises(ValueError, match=r"^BBRI's restoration .* does not overlap BBCA in"):
        cache.store_actions(BBCA, SEP, [], [RESTORED])


def test_the_cached_source_stores_the_upstreams_restorations_with_each_range(
    cache: BarCache,
) -> None:
    source, counting = source_for(cache, "BBRI.JK_2017-01-31_2022-01-31.json", date(2026, 9, 25))
    assert len(source.bars(BBRI, *SEP)) == len(calendar().trading_days(*SEP))
    assert cache.restorations(BBRI, *SEP) == [RESTORED]
    source.corporate_actions(BBRI, date(2019, 1, 1), date(2019, 12, 31))
    assert source.restorations(BBRI, date(2019, 1, 1), date(2021, 9, 30)) == [RESTORED]
    source.bars(BBRI, *OCT)  # every price whole: nothing restored, nothing more read
    assert source.restorations(BBRI, *OCT) == []
    assert counting.asked == [
        (date(2021, 9, 1), date(2021, 9, 30)),
        (date(2014, 1, 6), date(2026, 9, 25)),
        (date(2019, 1, 2), date(2019, 12, 30)),
        (date(2021, 10, 1), date(2021, 10, 29)),
    ]
```

**`tests/idx/test_yahoo.py`** (changed, rewritten whole)

<!-- file: tests/idx/test_yahoo.py -->
```python
"""The Yahoo data source, run on real recorded responses (spec §10.3: real data, replayed)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache
from itertools import pairwise
from pathlib import Path

import pandas as pd
import pytest

from steadyhand import (
    IDR,
    CashDividend,
    DataSource,
    DataUnavailableError,
    Instrument,
    Money,
    Side,
    Split,
    UnavailableDaysError,
    UnsupportedDateError,
)
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import GRID_START, Restoration, find_runs
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.yahoo import (
    RequestPolicy,
    UnprovenDividendsError,
    UnrecoverablePricesError,
    YahooDataSource,
    YahooHistory,
    YahooRow,
    actions_in,
    evidence,
    history_from_frames,
    history_from_json,
    history_to_json,
    ticker_for,
    unadjust,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
BBCA_FILE = FIXTURES / "BBCA.JK_2021-09-01_2021-11-30.json"
BBRI_FILE = FIXTURES / "BBRI.JK_2021-08-02_2021-09-30.json"
UNVR_FILE = FIXTURES / "UNVR.JK_2023-05-15_2023-06-09.json"
BBRI_FIVE_YEARS = FIXTURES / "BBRI.JK_2017-01-31_2022-01-31.json"
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
UNVR = Instrument("UNVR", "IDX", IDR)


@cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def test_tickers_are_the_symbol_with_jk() -> None:
    assert ticker_for(BBCA) == "BBCA.JK"
    with pytest.raises(
        ValueError, match=r"^Yahoo's \.JK tickers cover IDX IDR stocks, not X on ASX$"
    ):
        ticker_for(Instrument("X", "ASX", IDR))


def test_splits_are_reversed_using_the_whole_split_history() -> None:
    bars, actions = unadjust(
        history_from_json(BBCA_FILE), BBCA, calendar(), (date(2021, 9, 1), date(2021, 11, 30))
    )
    by_day = {bar.day: bar for bar in bars}
    # Yahoo reads 6,550 for the open on 1 Sep 2021: a fifth of what traded, for the later split.
    first = by_day[date(2021, 9, 1)]
    assert (first.open, first.close, first.volume) == (rp(32_750), rp(32_825), 13_472_500)
    assert by_day[date(2021, 10, 12)].close == rp(36_600)  # the last day before the split
    assert by_day[date(2021, 10, 13)].open == rp(7_400)  # the first day after it
    assert actions == [
        Split(BBCA, date(2021, 10, 13), 1, 5),
        CashDividend(BBCA, date(2021, 11, 17), Decimal("25.0")),
    ]


def test_there_is_one_bar_per_trading_day() -> None:
    start, end = date(2021, 9, 1), date(2021, 11, 30)
    bars, _ = unadjust(history_from_json(BBCA_FILE), BBCA, calendar(), (start, end))
    assert [bar.day for bar in bars] == list(calendar().trading_days(start, end))


@pytest.mark.parametrize(
    ("path", "instrument", "start", "end"),
    [
        (BBCA_FILE, BBCA, date(2021, 9, 1), date(2021, 11, 30)),
        (BBRI_FILE, BBRI, date(2021, 9, 8), date(2021, 9, 30)),
        (UNVR_FILE, UNVR, date(2023, 5, 15), date(2023, 6, 9)),
    ],
)
def test_recovered_prices_obey_the_ticks_and_bands(
    path: Path, instrument: Instrument, start: date, end: date
) -> None:
    """Real data against the rule tables: every price is on the tick grid, and every day's prices
    sit inside the auto-rejection band around the previous close, except across a split, where
    the reference is the theoretical price (t-verify.md §4.2)."""
    bars, actions = unadjust(history_from_json(path), instrument, calendar(), (start, end))
    split_days = {action.ex_date for action in actions if isinstance(action, Split)}
    for bar in bars:
        for price in (bar.open, bar.high, bar.low, bar.close):
            assert rules().round_to_tick(instrument, price, Side.BUY, bar.day) == price, bar.day
    checked = 0
    for previous, bar in pairwise(bars):
        if bar.day in split_days:
            continue
        low, high = rules().price_band(instrument, previous.close, bar.day)
        assert low <= bar.low, bar.day
        assert bar.high <= high, bar.day
        checked += 1
    assert checked == len(bars) - 1 - len(split_days & {bar.day for bar in bars[1:]})
    assert checked > 10


def test_an_unreported_adjustment_is_refused_with_every_day_named() -> None:
    history = history_from_json(BBRI_FILE)
    with pytest.raises(
        UnrecoverablePricesError,
        match=(
            r"^BBRI\.JK: Yahoo's prices for 25 day\(s\) from 2021-08-02 to 2021-09-07 carry an "
            r"adjustment it does not report as a split"
        ),
    ) as caught:
        unadjust(history, BBRI, calendar(), (date(2021, 8, 2), date(2021, 9, 30)))
    assert isinstance(caught.value, UnavailableDaysError)
    assert caught.value.days == calendar().trading_days(date(2021, 8, 2), date(2021, 9, 7))
    bars, _ = unadjust(history, BBRI, calendar(), (date(2021, 9, 8), date(2021, 9, 30)))
    assert bars[0].close == rp(3_730)


def test_a_zero_volume_trading_day_is_kept() -> None:
    bars, _ = unadjust(
        history_from_json(UNVR_FILE), UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9))
    )
    quiet = [bar for bar in bars if bar.volume == 0]
    # Yahoo gives UNVR no volume on 24 May 2023, though its open and close differ. The day is
    # kept, and spec §5.1 rejects orders on it: the cautious reading of a missing number.
    assert [(bar.day, bar.open, bar.close) for bar in quiet] == [
        (date(2023, 5, 24), rp(4_450), rp(4_410))
    ]


def _with_row(history: YahooHistory, row: YahooRow) -> YahooHistory:
    return replace(history, rows=tuple(sorted((*history.rows, row), key=lambda r: r.day)))


def test_a_flat_empty_bar_on_a_holiday_is_dropped() -> None:
    placeholder = YahooRow(date(2023, 5, 18), *(Decimal(4450),) * 4, volume=0, dividend=Decimal(0))
    history = _with_row(history_from_json(UNVR_FILE), placeholder)
    bars, _ = unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))
    assert date(2023, 5, 18) not in {bar.day for bar in bars}


def test_trading_on_a_holiday_is_refused() -> None:
    traded = YahooRow(date(2023, 5, 18), *(Decimal(4450),) * 4, volume=100, dividend=Decimal(0))
    history = _with_row(history_from_json(UNVR_FILE), traded)
    with pytest.raises(
        DataUnavailableError,
        match=r"^UNVR\.JK: Yahoo shows trading on 2023-05-18, which the IDX calendar says",
    ):
        unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))


def test_an_inconsistent_bar_is_refused() -> None:
    history = history_from_json(UNVR_FILE)
    broken = replace(history.rows[0], high=Decimal(1))
    with pytest.raises(
        DataUnavailableError, match=r"^UNVR\.JK: UNVR 2023-05-15: .* do not bracket"
    ):
        unadjust(
            replace(history, rows=(broken,)),
            UNVR,
            calendar(),
            (date(2023, 5, 15), date(2023, 5, 15)),
        )


@pytest.mark.parametrize(("ratio", "old", "new"), [("5.0", 1, 5), ("0.2", 5, 1), ("1.5", 2, 3)])
def test_split_ratios_become_whole_share_counts(ratio: str, old: int, new: int) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    _, actions = unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))
    assert actions == [Split(UNVR, date(2023, 5, 22), old, new)]


@pytest.mark.parametrize("ratio", ["0.3333", "0", "-2"])
def test_an_unusable_split_ratio_is_refused(ratio: str) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    with pytest.raises(DataUnavailableError, match=rf"^UNVR: Yahoo's split ratio {ratio} on"):
        unadjust(history, UNVR, calendar(), (date(2023, 5, 15), date(2023, 6, 9)))


def _frames(history: YahooHistory) -> tuple[pd.DataFrame, pd.Series]:
    """The pandas objects yfinance returns, rebuilt from a recording: the same columns, dtypes
    and time zone as ``Ticker.history`` and ``Ticker.splits`` (checked live by test_yahoo_live)."""
    index = pd.DatetimeIndex([pd.Timestamp(row.day) for row in history.rows]).tz_localize(
        "Asia/Jakarta"
    )
    frame = pd.DataFrame(
        {
            "Open": [float(row.open) for row in history.rows],
            "High": [float(row.high) for row in history.rows],
            "Low": [float(row.low) for row in history.rows],
            "Close": [float(row.close) for row in history.rows],
            "Adj Close": [float(row.close) for row in history.rows],
            "Volume": [row.volume for row in history.rows],
            "Dividends": [float(row.dividend) for row in history.rows],
            "Stock Splits": [0.0 for _ in history.rows],
        },
        index=index,
    )
    split_index = pd.DatetimeIndex([pd.Timestamp(day) for day, _ in history.splits])
    splits = pd.Series(
        [float(ratio) for _, ratio in history.splits],
        index=split_index.tz_localize("Asia/Jakarta"),
    )
    return frame, splits


@pytest.mark.parametrize("path", [BBCA_FILE, BBRI_FILE, UNVR_FILE])
def test_frames_convert_to_exactly_what_was_recorded(path: Path) -> None:
    recorded = history_from_json(path)
    assert history_from_frames(recorded.ticker, *_frames(recorded)) == recorded


@pytest.mark.parametrize("column", ["Open", "High", "Low", "Close", "Volume"])
def test_a_row_yahoo_gives_no_price_is_no_bar(column: str) -> None:
    """Yahoo's unfinished day has no close (as today's had on 2026-10-01): it is no bar, and
    reading the whole history up to today must not stop on it (plan scope decision 20)."""
    history = history_from_json(BBCA_FILE)
    frame, splits = _frames(history)
    frame[column] = frame[column].astype(float)
    frame.loc[frame.index[-1], column] = float("nan")
    assert history_from_frames("BBCA.JK", frame, splits).rows == history.rows[:-1]


def test_a_dividend_on_a_row_with_no_price_is_refused() -> None:
    history = history_from_json(BBCA_FILE)
    frame, splits = _frames(history)
    last = frame.index[-1]
    frame.loc[last, "Close"] = float("nan")
    frame.loc[last, "Dividends"] = 25.0
    day = history.rows[-1].day.isoformat()
    with pytest.raises(
        DataUnavailableError,
        match=rf"^BBCA\.JK: Yahoo has no prices for {day}, the ex-date of a dividend",
    ):
        history_from_frames("BBCA.JK", frame, splits)


def test_a_changed_response_shape_is_refused() -> None:
    frame, splits = _frames(history_from_json(UNVR_FILE))
    with pytest.raises(DataUnavailableError, match=r"^X\.JK: Yahoo's response has no 'Dividends'"):
        history_from_frames("X.JK", frame.drop(columns=["Dividends"]), splits)
    with pytest.raises(DataUnavailableError, match=r"^X\.JK: Yahoo returned no rows$"):
        history_from_frames("X.JK", frame.iloc[0:0], splits)
    with pytest.raises(DataUnavailableError, match="dates are in UTC, expected Asia/Jakarta"):
        history_from_frames("X.JK", frame.tz_convert("UTC"), splits)


def test_recordings_round_trip_through_json(tmp_path: Path) -> None:
    recorded = history_from_json(BBCA_FILE)
    path = tmp_path / "copy.json"
    path.write_text(history_to_json(recorded, recorded=date(2026, 9, 25), source="test"))
    assert history_from_json(path) == recorded


class Replay:
    """Serves a recording in place of the network, failing the first *failures* calls."""

    def __init__(self, path: Path, failures: int = 0) -> None:
        self.history = history_from_json(path)
        self.failures = failures
        self.calls: list[tuple[str, date, date]] = []

    def __call__(self, ticker: str, start: date, end: date) -> YahooHistory:
        self.calls.append((ticker, start, end))
        if len(self.calls) <= self.failures:
            msg = f"{ticker}: the request to Yahoo failed: timeout {len(self.calls)}"
            raise DataUnavailableError(msg)
        return self.history


def test_the_source_is_a_data_source_and_downloads_each_range_once() -> None:
    replay, slept = Replay(BBCA_FILE), list[float]()
    source = YahooDataSource(calendar(), download=replay, sleep=slept.append)
    assert isinstance(source, DataSource)
    start, end = date(2021, 10, 1), date(2021, 10, 29)
    assert len(source.bars(BBCA, start, end)) == len(calendar().trading_days(start, end))
    assert source.corporate_actions(BBCA, start, end) == [Split(BBCA, date(2021, 10, 13), 1, 5)]
    assert replay.calls == [("BBCA.JK", start, end)]
    source.bars(BBCA, start, date(2021, 10, 28))
    assert slept == [1.0]  # a pause before every request after the first


def test_failures_are_retried_with_backoff_then_raised() -> None:
    replay, slept = Replay(BBCA_FILE, failures=2), list[float]()
    source = YahooDataSource(calendar(), download=replay, sleep=slept.append)
    assert source.bars(BBCA, date(2021, 10, 1), date(2021, 10, 1))
    assert slept == [1.0, 2.0]
    replay, slept = Replay(BBCA_FILE, failures=3), list[float]()
    source = YahooDataSource(
        calendar(), download=replay, sleep=slept.append, policy=RequestPolicy(attempts=3)
    )
    with pytest.raises(
        DataUnavailableError,
        match=(
            r"^BBCA\.JK: no data from Yahoo for 2021-10-01 to 2021-10-01 after 3 attempts: "
            r"BBCA\.JK: the request to Yahoo failed: timeout 3$"
        ),
    ) as caught:
        source.bars(BBCA, date(2021, 10, 1), date(2021, 10, 1))
    assert isinstance(caught.value.__cause__, DataUnavailableError)


def test_a_reversed_range_is_refused() -> None:
    source = YahooDataSource(calendar(), download=Replay(BBCA_FILE))
    with pytest.raises(ValueError, match=r"^end 2021-10-01 is before start 2021-10-02$"):
        source.bars(BBCA, date(2021, 10, 2), date(2021, 10, 1))
    with pytest.raises(ValueError, match=r"^end 2021-10-01 is before start 2021-10-02$"):
        source.corporate_actions(BBCA, date(2021, 10, 2), date(2021, 10, 1))


def test_the_default_source_uses_the_shipped_calendar() -> None:
    source = YahooDataSource(download=Replay(UNVR_FILE))
    assert len(source.bars(UNVR, date(2023, 5, 15), date(2023, 6, 9))) == 17


def test_actions_are_read_where_the_prices_cannot_be_recovered() -> None:
    # BBRI's prices before 2021-09-07 carry a rights issue Yahoo does not report, so without the
    # runs of its whole history no bar can be recovered there, but a dividend needs no price
    # (M6 spec §4.3).
    history = history_from_json(BBRI_FIVE_YEARS)
    refused = (date(2021, 2, 1), date(2021, 9, 7))
    with pytest.raises(UnrecoverablePricesError):
        unadjust(history, BBRI, calendar(), refused)
    assert actions_in(history, BBRI, *refused) == [
        CashDividend(BBRI, date(2021, 4, 6), Decimal("89.91268"))
    ]
    # Yahoo divided the 2017 dividend by the 5-for-1 split of 10 November 2017; it is restated.
    assert actions_in(history, BBRI, date(2017, 1, 31), date(2017, 12, 29)) == [
        CashDividend(BBRI, date(2017, 3, 23), Decimal("389.63463")),
        Split(BBRI, date(2017, 11, 10), 1, 5),
    ]


def test_actions_need_no_calendar() -> None:
    # 2015 is before the IDX holidays begin: its bars cannot be checked, but its actions can be
    # read, restated through the 2-for-1 split that followed.
    row = YahooRow(date(2015, 6, 1), *(Decimal(1000),) * 4, volume=100, dividend=Decimal(50))
    history = YahooHistory("BBCA.JK", (row,), ((date(2016, 6, 1), Decimal("2.0")),))
    year = (date(2015, 1, 1), date(2015, 12, 31))
    assert actions_in(history, BBCA, *year) == [CashDividend(BBCA, date(2015, 6, 1), Decimal(100))]
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2015"):
        unadjust(history, BBCA, calendar(), year)


TODAY = date(2026, 9, 25)


def restoring(path: Path = BBRI_FIVE_YEARS) -> tuple[YahooDataSource, Replay]:
    """The source on a recording, which also serves the whole-history request (#160)."""
    replay = Replay(path)
    source = YahooDataSource(calendar(), download=replay, sleep=lambda _: None, today=lambda: TODAY)
    return source, replay


def test_the_source_restores_a_ranges_prices_and_dividends_reading_the_whole_history_once() -> None:
    source, replay = restoring()
    restored = (date(2021, 2, 1), date(2021, 9, 7))
    assert source.corporate_actions(BBRI, *restored) == [
        CashDividend(BBRI, date(2021, 4, 6), Decimal("98.9057"))
    ]
    bars = source.bars(BBRI, *restored)
    assert [bar.day for bar in bars] == list(calendar().trading_days(*restored))
    assert (bars[0].open, bars[0].close) == (rp(4_180), rp(4_400))
    later = (date(2021, 10, 1), date(2021, 10, 29))
    source.bars(BBRI, *later)
    assert replay.calls == [
        ("BBRI.JK", *restored),
        ("BBRI.JK", GRID_START, TODAY),
        ("BBRI.JK", *later),
    ]


def test_a_range_whose_prices_are_all_whole_reads_no_whole_history() -> None:
    source, replay = restoring(BBCA_FILE)
    october = (date(2021, 10, 1), date(2021, 10, 29))
    assert source.bars(BBCA, *october)
    assert source.restorations(BBCA, *october) == ()
    assert replay.calls == [("BBCA.JK", *october)]


def test_a_restored_day_is_the_same_whatever_range_is_asked() -> None:
    source, _ = restoring()
    whole = source.bars(BBRI, date(2021, 2, 1), date(2021, 9, 7))
    week = source.bars(BBRI, date(2021, 3, 1), date(2021, 3, 5))
    assert week == [bar for bar in whole if date(2021, 3, 1) <= bar.day <= date(2021, 3, 5)]
    assert len(week) == 5


def test_restorations_are_the_proven_runs_overlapping_the_range() -> None:
    source, _ = restoring()
    run = Restoration(BBRI, date(2017, 1, 31), date(2021, 9, 7), Decimal("1.100019"), 4_412)
    assert source.restorations(BBRI, date(2021, 9, 1), date(2021, 9, 30)) == (run,)
    assert source.restorations(BBRI, date(2021, 9, 8), date(2021, 9, 30)) == ()


def unwhole(day: date, price: str, *, volume: int = 100, dividend: str = "0") -> YahooRow:
    return YahooRow(day, *(Decimal(price),) * 4, volume=volume, dividend=Decimal(dividend))


def test_a_dividend_in_an_unproven_run_is_refused_naming_its_ex_date() -> None:
    # Two days off the grid are 8 prices, too few for a proof: their dividend is known to be
    # wrong, in a look-back as in a backtest's own days (#160 spec §5).
    rows = (
        unwhole(date(2021, 3, 1), "1000.5"),
        unwhole(date(2021, 3, 2), "1001.5", dividend="20.5"),
    )
    history = YahooHistory("BBCA.JK", rows, ())
    source = YahooDataSource(calendar(), download=lambda *_: history, today=lambda: TODAY)
    for start in (date(2021, 1, 4), date(2021, 3, 1)):
        with pytest.raises(
            UnprovenDividendsError,
            match=(
                r"^BBCA\.JK: the dividend\(s\) with ex-date 2021-03-02 fall in days whose prices "
                r"carry an adjustment Yahoo does not report and steadyhand could not prove"
            ),
        ) as caught:
            source.corporate_actions(BBCA, start, date(2021, 3, 31))
        assert isinstance(caught.value, UnavailableDaysError)
        assert caught.value.days == (date(2021, 3, 2),)
    with pytest.raises(UnrecoverablePricesError) as refused:
        source.bars(BBCA, date(2021, 3, 1), date(2021, 3, 2))
    assert refused.value.days == (date(2021, 3, 1), date(2021, 3, 2))
    assert source.restorations(BBCA, date(2021, 3, 1), date(2021, 3, 2)) == ()


def test_the_proof_reads_every_row_with_a_price_off_whole_rupiah_and_nothing_else() -> None:
    rows = (
        unwhole(date(2021, 3, 1), "1000.25"),
        unwhole(date(2021, 3, 2), "1000"),  # whole: never evidence
        unwhole(date(2021, 3, 3), "1000.25", volume=0),  # flat with no volume: no evidence
        unwhole(date(2021, 3, 4), "1000.25", volume=7),  # its volume plays no part
    )
    history = YahooHistory("BBCA.JK", rows, ((date(2021, 6, 1), Decimal("2.0")),))
    assert [(row.day, row.prices) for row in evidence(history)] == [
        (date(2021, 3, 1), (Decimal("2000.500"),) * 4),
        (date(2021, 3, 4), (Decimal("2000.500"),) * 4),
    ]


TRUE = (3550, 3600, 3530, 3580, 3610, 3640)
"""Six traded prices on the Rp10 grid, none a whole rupiah once divided by 1.1."""


def scaled(day: date, price: int, *, volume: int = 100, split: int = 1) -> YahooRow:
    """A flat day as Yahoo shows it: divided by 1.1, and by a later *split*, volume multiplied."""
    recorded = Decimal(price) / Decimal("1.1") / split
    return YahooRow(day, *(recorded,) * 4, volume=volume, dividend=Decimal(0))


def test_a_flat_row_with_no_volume_inside_a_proven_run_is_restored_though_it_is_no_evidence() -> (
    None
):
    days = calendar().trading_days(date(2021, 3, 1), date(2021, 3, 9))
    rows = [scaled(day, price) for day, price in zip(days, TRUE, strict=False)]
    rows[2] = scaled(days[2], TRUE[2], volume=0)
    history = YahooHistory("BBCA.JK", tuple(rows), ())
    runs = find_runs(evidence(history))
    assert [(run.first, run.last, run.prices, run.factor) for run in runs] == [
        (days[0], days[5], 20, Decimal("1.100000"))
    ]
    bars, _ = unadjust(history, BBCA, calendar(), (days[0], days[5]), runs)
    assert [(bar.close, bar.volume) for bar in bars] == [
        (rp(p), 0 if i == 2 else 100) for i, p in enumerate(TRUE)
    ]


def test_restorations_leave_out_a_proven_run_outside_the_range() -> None:
    """Two adjustments stacked: each range reads only the run it overlaps."""
    days = calendar().trading_days(date(2021, 3, 1), date(2021, 3, 31))
    older, newer = days[:6], days[6:12]
    rows = [
        *(
            YahooRow(day, *(Decimal(p) / Decimal("1.3"),) * 4, 100, Decimal(0))
            for day, p in zip(older, TRUE, strict=True)
        ),
        *(
            YahooRow(day, *(Decimal(p) / Decimal("1.1"),) * 4, 100, Decimal(0))
            for day, p in zip(newer, TRUE, strict=True)
        ),
    ]
    history = YahooHistory("BBCA.JK", tuple(rows), ())
    source = YahooDataSource(calendar(), download=lambda *_: history, today=lambda: TODAY)
    assert [
        (r.first, r.last, r.factor) for r in source.restorations(BBCA, newer[0], newer[-1])
    ] == [(newer[0], newer[-1], Decimal("1.100000"))]
    assert [
        (r.first, r.last, r.factor) for r in source.restorations(BBCA, older[0], older[-1])
    ] == [(older[0], older[4], Decimal("1.300000"))]  # 3,640 / 1.3 is whole: no evidence


def test_a_row_whose_volume_is_not_whole_stays_refused_though_its_prices_count() -> None:
    days = calendar().trading_days(date(2021, 3, 1), date(2021, 3, 9))
    rows = [
        scaled(day, price, volume=151 if day < days[5] else 200, split=2)
        for day, price in zip(days, TRUE, strict=False)
    ]
    history = YahooHistory("BBCA.JK", tuple(rows), ((date(2021, 6, 1), Decimal("2.0")),))
    runs = find_runs(evidence(history))
    assert [run.prices for run in runs if run.factor is not None] == [24]
    with pytest.raises(UnrecoverablePricesError) as refused:
        unadjust(history, BBCA, calendar(), (days[0], days[5]), runs)
    assert refused.value.days == tuple(days[:5])  # 151 / 2 is not whole; 200 / 2 is
    (bar,) = unadjust(history, BBCA, calendar(), (days[5], days[5]), runs)[0]
    assert (bar.close, bar.volume) == (rp(TRUE[5]), 100)


def test_a_failed_whole_history_read_fails_closed() -> None:
    history = history_from_json(BBRI_FIVE_YEARS)

    def refuse_whole(ticker: str, start: date, end: date) -> YahooHistory:
        del end
        if start == GRID_START:
            msg = f"{ticker}: the request to Yahoo failed: timeout"
            raise DataUnavailableError(msg)
        return history

    slept: list[float] = []
    source = YahooDataSource(
        calendar(), download=refuse_whole, sleep=slept.append, today=lambda: TODAY
    )
    with pytest.raises(
        DataUnavailableError,
        match=r"^BBRI\.JK: no data from Yahoo for 2014-01-06 to 2026-09-25 after 3 attempts",
    ):
        source.bars(BBRI, date(2021, 3, 1), date(2021, 3, 5))
    assert slept == [1.0, 1.0, 2.0]  # the pause after the range, then the backoff


BBRI_WHOLE = FIXTURES / "BBRI.JK_2014-01-06_2026-10-01.json"


def test_bbri_s_whole_recording_proves_one_factor_up_to_its_rights_issue() -> None:
    (run,) = find_runs(evidence(history_from_json(BBRI_WHOLE)))
    assert (run.first, run.last, len(run.days), run.prices, run.factor) == (
        date(2014, 1, 6),
        date(2021, 9, 7),
        1_845,
        7_380,
        Decimal("1.100019"),
    )


def test_bbri_s_2021_dividend_restores_to_what_bri_announced() -> None:
    history = history_from_json(BBRI_WHOLE)
    runs = find_runs(evidence(history))
    (dividend,) = actions_in(history, BBRI, date(2021, 4, 1), date(2021, 4, 30), runs)
    assert isinstance(dividend, CashDividend)
    assert dividend.per_share == Decimal("98.9057")
    assert abs(dividend.per_share - Decimal("98.905659443")) <= Decimal("0.0001")  # Liputan6


def test_bbri_s_golden_years_are_restored_except_where_a_volume_is_not_whole() -> None:
    # #160 spec §9.2: 1,103 days from 2017-01-31 to 2021-09-07 are evidence, a price off whole
    # rupiah on a day that is not a flat row with no volume (57 flat days there have one too); the
    # 153 before the 5-for-1 split of 2017-11-10 also have a volume that is not whole (#162).
    history = history_from_json(BBRI_WHOLE)
    runs = find_runs(evidence(history))
    span = (date(2017, 1, 31), date(2021, 9, 7))
    assert len([row for row in evidence(history) if span[0] <= row.day <= span[1]]) == 1_103
    with pytest.raises(UnrecoverablePricesError) as refused:
        unadjust(history, BBRI, calendar(), span, runs)
    assert (len(refused.value.days), refused.value.days[-1]) == (153, date(2017, 11, 9))
    bars, _ = unadjust(history, BBRI, calendar(), (date(2017, 11, 10), span[1]), runs)
    assert len(bars) == len(calendar().trading_days(date(2017, 11, 10), span[1]))


@pytest.mark.parametrize(
    "older", sorted(FIXTURES.glob("BBRI.JK_20[12]*.json")), ids=lambda p: p.stem
)
def test_bbri_s_whole_recording_agrees_with_every_older_recording(older: Path) -> None:
    whole = history_from_json(BBRI_WHOLE)
    rows = {row.day: row for row in whole.rows}
    recorded = history_from_json(older)
    assert recorded.splits == whole.splits
    assert all(rows[row.day] == row for row in recorded.rows)
    assert len(recorded.rows) > 40
```

**`tests/idx/test_yahoo_live.py`** (changed: 1 edit)

<!-- edit: tests/idx/test_yahoo_live.py -->
Replace:
```python
def outcome(history: YahooHistory) -> object:
    first, last = history.rows[0].day, history.rows[-1].day
    instrument = Instrument(history.ticker.removesuffix(SUFFIX), "IDX", IDR)
    try:
        return unadjust(history, instrument, IdxCalendar.shipped(), first, last)
    except UnrecoverablePricesError as error:
```
with:
```python
def outcome(history: YahooHistory) -> object:
    """What the recording gives from the first year the holiday calendar covers: a recording of
    BBRI's whole history starts in 2014 (#160)."""
    calendar = IdxCalendar.shipped()
    first, last = max(history.rows[0].day, calendar.first_day), history.rows[-1].day
    instrument = Instrument(history.ticker.removesuffix(SUFFIX), "IDX", IDR)
    try:
        return unadjust(history, instrument, calendar, (first, last))
    except UnrecoverablePricesError as error:
```

**`tests/perf/test_factor_performance.py`** (new)

<!-- file: tests/perf/test_factor_performance.py -->
```python
"""Proving BBRI's unreported price factor over its whole recorded history finishes inside a
second (#160 spec §9.3).

The recording holds 3,135 days from 2014-01-06. 1,845 of them are the proof's evidence: a price
off whole rupiah on a day that is not a flat row with no volume (69 such flat days have one too).
Reading the evidence and finding the runs took 0.024 to 0.028 s five times in a row at a load of
12 on six cores; the budget leaves about thirty-five times that for a slower CI runner.
"""

import time
from pathlib import Path

import pytest

from steadyhand_idx.factor import find_runs
from steadyhand_idx.yahoo import evidence, history_from_json

BUDGET_SECONDS = 1
RECORDING = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "yahoo"
    / "BBRI.JK_2014-01-06_2026-10-01.json"
)


@pytest.mark.perf
def test_bbri_s_whole_history_is_proven_inside_the_budget() -> None:
    history = history_from_json(RECORDING)
    started = time.perf_counter()
    (run,) = find_runs(evidence(history))
    elapsed = time.perf_counter() - started
    assert run.factor is not None
    assert elapsed < BUDGET_SECONDS, f"{elapsed:.2f} s"
```

**`tests/perf/test_performance.py`** (changed: 1 edit)

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
both trade, value and size every day. The ``dividend-growth`` year took 0.37 to 0.40 s at a
load of 10 on four cores (0.67 to 0.74 s at 30); its budget leaves about eight times that for a
slower CI runner.
```
with:
```python
both trade, value and size every day. The ``dividend-growth`` year took 0.37 to 0.40 s at a
load of 10 on six cores (0.67 to 0.74 s at 30); its budget leaves about eight times that for a
slower CI runner.
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`** (changed, new names stubbed: 8 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
actions only, so its bars still count as missing.
"""
```
with:
```python
actions only, so its bars still count as missing.

Each fetched range also stores the upstream's restorations overlapping it (#160 spec §6): the
runs of a stock's history whose prices and dividends were restored, so a report can say so
from a cache read alone.
"""
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
from types import TracebackType
from zoneinfo import ZoneInfo
```
with:
```python
from types import TracebackType
from typing import Protocol
from zoneinfo import ZoneInfo
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
from steadyhand_idx.calendar import IdxCalendar

```
with:
```python
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import Restoration

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
    """,
)
```
with:
```python
    """,
    # #160 spec §6: every proven run is recorded, and every range is read again under the new
    # rules. That corrects a cached dividend Yahoo scaled by an unreported factor (BBRI's 2021
    # dividend was cached as 89.91268, not 98.9057). Bars from refused days were never stored,
    # so no stored bar is wrong; clearing ``fetched`` fetches the days that can now be restored.
    """
    CREATE TABLE restorations (
        symbol TEXT NOT NULL,
        first TEXT NOT NULL,
        last TEXT NOT NULL,
        factor TEXT NOT NULL,
        prices INTEGER NOT NULL,
        PRIMARY KEY (symbol, first)
    ) STRICT;
    DELETE FROM actions;
    DELETE FROM fetched_actions;
    DELETE FROM fetched;
    """,
)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
    """The cache file was written by a newer steadyhand-idx than this one."""

```
with:
```python
    """The cache file was written by a newer steadyhand-idx than this one."""


class RestoringSource(DataSource, Protocol):
    """A data source that also says which runs of a stock's history it restored."""

    def restorations(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[Restoration]: ...

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python

    def _insert_bar(self, symbol: str, day: date, row: _BarRow) -> None:
```
with:
```python

    def _require_overlapping(
        self, instrument: Instrument, span: tuple[date, date], restorations: Sequence[Restoration]
    ) -> None:
        raise NotImplementedError("BarCache._require_overlapping")

    def _insert_restorations(self, symbol: str, restorations: Sequence[Restoration]) -> None:
        raise NotImplementedError("BarCache._insert_restorations")

    def _insert_bar(self, symbol: str, day: date, row: _BarRow) -> None:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
                found.append(OtherAction(instrument, ex_date, description))
        return found

    def fetched(self, instrument: Instrument) -> list[tuple[date, date]]:
```
with:
```python
                found.append(OtherAction(instrument, ex_date, description))
        return found

    def restorations(self, instrument: Instrument, start: date, end: date) -> list[Restoration]:
        """The stored restorations overlapping *start* to *end*, oldest first."""
        raise NotImplementedError("BarCache.restorations")

    def fetched(self, instrument: Instrument) -> list[tuple[date, date]]:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
```
with:
```python

    def restorations(self, instrument: Instrument, start: date, end: date) -> list[Restoration]:
        """The restorations stored with the ranges read so far that overlap *start* to *end*:
        a cache read, never a fetch (#160 spec §6)."""
        raise NotImplementedError("CachedDataSource.restorations")

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
```

**`packages/steadyhand-idx/src/steadyhand_idx/factor.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
Replace:
```python

from steadyhand import IDR, Money
from steadyhand_idx._datafile import Dated, load_shipped
```
with:
```python

from steadyhand import IDR, Instrument, Money
from steadyhand_idx._datafile import Dated, load_shipped
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
Replace:
```python
    return factor.quantize(NOISE_QUANTUM) == 1

```
with:
```python
    return factor.quantize(NOISE_QUANTUM) == 1


@dataclass(frozen=True, slots=True)
class Restoration:
    """A proven run of one stock's history, as a data source restored it (spec §5)."""

    instrument: Instrument
    first: date
    last: date
    factor: Decimal
    prices: int

```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (changed, new names stubbed: 9 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
factor nobody publishes, so after reversing the reported splits those prices are no longer whole
rupiah. They cannot be recovered, and a day like that raises ``UnrecoverablePricesError`` naming
it (fail closed, spec §9.2). Measured on 2026-09-25 over 25 large IDX stocks for 2021-2025: BBRI
up to 2021-09-07, SMGR up to 2022-12-12, MDKA up to 2022-04-13 and five INCO days in June 2024.

```
with:
```python
factor nobody publishes, so after reversing the reported splits those prices are no longer whole
rupiah. When a range has such a price, the source reads the stock's whole history once, finds the
runs of those days, and restores every price and dividend of each run whose factor the tick grid
proves (``steadyhand_idx.factor``, #160). A day in no proven run still raises
``UnrecoverablePricesError`` naming it (fail closed, spec §9.2), and a dividend in an unproven run
is refused, because its amount is known to be wrong.

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

Corporate actions need neither: a dividend is restated through the reported splits alone. So
``corporate_actions`` reads only splits and dividends, and a range whose prices cannot be
recovered, or which the holiday calendar does not cover, still gives its actions. That is what a
strategy's look-back reads (M6 spec §4.3): on 2026-09-30 the price checks refused 11 of the 45
LQ45 members' six-year look-backs, and reading the actions alone refused 2 (unusable splits).
"""
```
with:
```python

Corporate actions need no calendar: a dividend is restated through the reported splits, and
through a proven run's factor. So ``corporate_actions`` reads only splits and dividends, and a
range the holiday calendar does not cover still gives its actions. That is what a strategy's
look-back reads (M6 spec §4.3).
"""
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
import json
import time
```
with:
```python
import json
import math
import time
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
)
from steadyhand_idx.calendar import IdxCalendar

```
with:
```python
)
from steadyhand_idx.cache import jakarta_today
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import (
    GRID_START,
    PriceRow,
    Restoration,
    Run,
    find_runs,
    restore_dividend,
    restore_price,
)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

def history_to_json(history: YahooHistory, *, recorded: date, source: str) -> str:
```
with:
```python

def _priced(ticker: str, day: date, record: pd.Series) -> bool:
    """Whether Yahoo gives *record* its prices and volume. A row without them is a day Yahoo has
    no prices for, such as its unfinished day: no bar, like a day it leaves out. A dividend on such
    a row would be lost with it, so that row is refused instead (fail closed)."""
    raise NotImplementedError("_priced")


def history_to_json(history: YahooHistory, *, recorded: date, source: str) -> str:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    return actions

```
with:
```python
    return actions


class UnprovenDividendsError(UnavailableDaysError):
    """Dividends whose ex-date falls in a run of Yahoo's prices carrying an unreported adjustment
    that could not be proven: their recorded amounts are known to be wrong (#160 spec §5)."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        raise NotImplementedError("UnprovenDividendsError.__init__")


def reversed_prices(history: YahooHistory, row: YahooRow) -> tuple[Decimal, ...]:
    """*row*'s open, high, low and close with every reported split after it reversed."""
    raise NotImplementedError("reversed_prices")


def _all_whole(prices: Sequence[Decimal]) -> bool:
    raise NotImplementedError("_all_whole")


def _placeholder(row: YahooRow) -> bool:
    """A flat row with no volume: it repeats an earlier close, on a holiday or not."""
    raise NotImplementedError("_placeholder")


def evidence(history: YahooHistory) -> list[PriceRow]:
    """The proof's input (#160 spec §4): every row with a price that is not whole after the
    reported splits are reversed, in date order, except a flat row with no volume, which repeats
    an earlier close and is no evidence. Its volume plays no part (spec §3.6)."""
    raise NotImplementedError("evidence")


def _covering(runs: Sequence[Run], day: date) -> Run | None:
    raise NotImplementedError("_covering")


def _amounts(prices: Sequence[Decimal], run: Run | None, day: date) -> list[int] | None:
    """The traded prices: whole as they are, restored in a proven run, else ``None``."""
    raise NotImplementedError("_amounts")

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
```
with:
```python

    def restorations(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[Restoration, ...]:
        """The proven runs overlapping the range, oldest first. A range with no price that is
        not whole reads no runs, and restores nothing, so it has none."""
        raise NotImplementedError("YahooDataSource.restorations")

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
        return self._fetch(ticker_for(instrument), start, end)

```
with:
```python
        return self._fetch(ticker_for(instrument), start, end)

    def _runs_for(self, history: YahooHistory, start: date, end: date) -> tuple[Run, ...]:
        """The runs of the stock's whole history, from ``GRID_START`` to today, read once per
        ticker, when the range has a price that is not whole; none otherwise (#160 spec §5)."""
        raise NotImplementedError("YahooDataSource._runs_for")

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
        raise DataUnavailableError(msg) from failure


def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
```
with:
```python
        raise DataUnavailableError(msg) from failure

    def _request(self, ticker: str, start: date, end: date) -> YahooHistory:
        """Ask Yahoo, under the request policy: a pause between requests, retries with backoff."""
        raise NotImplementedError("YahooDataSource._request")


def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
```

**`scripts/record_golden.py`** (changed, new names stubbed: 3 edits)

<!-- edit: scripts/record_golden.py -->
Replace:
```python
from steadyhand_idx.cache import BarCache, CachedDataSource
from steadyhand_idx.universe import Lq45Membership, Lq45Record, Lq45Universe
```
with:
```python
from steadyhand_idx.cache import BarCache, CachedDataSource
from steadyhand_idx.factor import GRID_START
from steadyhand_idx.universe import Lq45Membership, Lq45Record, Lq45Universe
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
"""The day the fixtures were recorded; the cache treats it as today."""

```
with:
```python
"""The day the fixtures were recorded; the cache treats it as today."""
WHOLE_RECORDED = date(2026, 10, 1)
"""The day BBRI's whole history was recorded (#160 spec §9.2). The replay's sources take it as
today, so a whole-history request, from ``GRID_START`` to today, is the recording's own range."""
WHOLE_HISTORIES = ("BBRI.JK",)
"""The stocks with a whole-history recording: those with a price that is not whole rupiah."""

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
        return backtest(strategy, market, START, end, backtest_settings)

```
with:
```python
        return backtest(strategy, market, START, end, backtest_settings)


def replay(download: Callable[[str, date, date], YahooHistory] = recorded) -> YahooDataSource:
    """The real ``YahooDataSource`` on *download*, waiting for nothing, on the day the whole
    histories were recorded."""
    raise NotImplementedError("replay")

```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1650 failed=144 -->
Expected: 1650 run, 144 failed (pytest reads `137 failed, 7 errors`). The 7 errors are fixtures that build the golden replay source (`record_golden.replay`, a stub) and stop at setup, and 8 more tests stop in a stub directly. 42 are `TypeError`s from arguments not there yet: `unadjust` called with its `span` (25), `YahooDataSource(..., today=...)` (16) and `BarCache.store` with restorations (1). 45 are CLI runs that exit 1 because their source is the stubbed replay, and the 42 others follow from those runs or from the old code: no report file or paper account written (`FileNotFoundError`, `sqlite3.OperationalError: no such table: account`, empty audit lines), the old golden figure `97889490` where `96825198` is wanted, the six tests of a row Yahoo gives no price (the old code keeps it as a bar, its NaN volume stops the conversion with a `ValueError`, and a dividend on it is not refused), and the rest of the golden and restoration assertions. Five tests pass against the stubs, each for a stated reason: `test_a_cache_from_a_newer_release_is_refused`, whose message counts `MIGRATIONS`, a constant in its final form; and the four cases of `test_bbri_s_whole_recording_agrees_with_every_older_recording`, which read only the recordings, the whole one arriving with Task 0.

- [ ] **Step 5: Implement.** The golden files are part of this step.

**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`** (implemented: 10 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        actions: Sequence[CorporateAction],
    ) -> None:
```
with:
```python
        actions: Sequence[CorporateAction],
        restorations: Sequence[Restoration] = (),
    ) -> None:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        self._require_within(instrument, span, located)
        with self._write():
            for bar in bars:
```
with:
```python
        self._require_within(instrument, span, located)
        self._require_overlapping(instrument, span, restorations)
        with self._write():
            self._insert_restorations(symbol, restorations)
            for bar in bars:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
    def store_actions(
        self, instrument: Instrument, span: tuple[date, date], actions: Sequence[CorporateAction]
    ) -> None:
```
with:
```python
    def store_actions(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        actions: Sequence[CorporateAction],
        restorations: Sequence[Restoration] = (),
    ) -> None:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        self._require_within(instrument, span, [(a.instrument, a.ex_date) for a in actions])
        with self._write():
            for action in actions:
```
with:
```python
        self._require_within(instrument, span, [(a.instrument, a.ex_date) for a in actions])
        self._require_overlapping(instrument, span, restorations)
        with self._write():
            self._insert_restorations(symbol, restorations)
            for action in actions:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
    ) -> None:
        raise NotImplementedError("BarCache._require_overlapping")

    def _insert_restorations(self, symbol: str, restorations: Sequence[Restoration]) -> None:
        raise NotImplementedError("BarCache._insert_restorations")

```
with:
```python
    ) -> None:
        start, end = span
        for run in restorations:
            if run.instrument != instrument or run.first > end or run.last < start:
                msg = (
                    f"{run.instrument.symbol}'s restoration {run.first} to {run.last} does not "
                    f"overlap {instrument.symbol} in {start} to {end}"
                )
                raise ValueError(msg)

    def _insert_restorations(self, symbol: str, restorations: Sequence[Restoration]) -> None:
        for run in restorations:
            values = (run.last.isoformat(), str(run.factor), run.prices)
            found = self._db.execute(
                "SELECT last, factor, prices FROM restorations WHERE symbol = ? AND first = ?",
                (symbol, run.first.isoformat()),
            ).fetchone()
            if found is None:
                self._db.execute(
                    "INSERT INTO restorations VALUES (?, ?, ?, ?, ?)",
                    (symbol, run.first.isoformat(), *values),
                )
            elif tuple(found) != values:
                msg = (
                    f"{symbol} {run.first.isoformat()}: cached restoration {tuple(found)} "
                    f"differs from fetched {values}"
                )
                raise CacheConflictError(msg)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        """The stored restorations overlapping *start* to *end*, oldest first."""
        raise NotImplementedError("BarCache.restorations")

```
with:
```python
        """The stored restorations overlapping *start* to *end*, oldest first."""
        rows = self._db.execute(
            "SELECT first, last, factor, prices FROM restorations "
            "WHERE symbol = ? AND first <= ? AND last >= ? ORDER BY first",
            (self._symbol(instrument), end.isoformat(), start.isoformat()),
        ).fetchall()
        return [
            Restoration(
                instrument, date.fromisoformat(first), date.fromisoformat(last), Decimal(f), prices
            )
            for first, last, f, prices in rows
        ]

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        self,
        upstream: DataSource,
        cache: BarCache,
```
with:
```python
        self,
        upstream: RestoringSource,
        cache: BarCache,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
                actions = self._upstream.corporate_actions(instrument, first, last)
                self._cache.store_actions(instrument, (first, last), actions)
        cached = self._cache.actions(instrument, start, complete)
```
with:
```python
                actions = self._upstream.corporate_actions(instrument, first, last)
                restored = self._upstream.restorations(instrument, first, last)
                self._cache.store_actions(instrument, (first, last), actions, restored)
        cached = self._cache.actions(instrument, start, complete)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        a cache read, never a fetch (#160 spec §6)."""
        raise NotImplementedError("CachedDataSource.restorations")

```
with:
```python
        a cache read, never a fetch (#160 spec §6)."""
        return self._cache.restorations(instrument, start, end)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
                actions = self._upstream.corporate_actions(instrument, first, last)
                self._cache.store(instrument, (first, last), bars, actions)
        return today
```
with:
```python
                actions = self._upstream.corporate_actions(instrument, first, last)
                restored = self._upstream.restorations(instrument, first, last)
                self._cache.store(instrument, (first, last), bars, actions, restored)
        return today
```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (implemented, rewritten whole)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
```python
"""``YahooDataSource``: unadjusted IDX prices from Yahoo Finance's ``.JK`` tickers (spec §9.2).

Yahoo's "unadjusted" history is not unadjusted (docs/research/t-hist.md §6). Even with
``auto_adjust=False`` every price before a split is divided by the split ratio, and every
dividend with it. Splits are reported, so their adjustment is reversed exactly here, using the
stock's full split history (a split after the requested range still adjusts the prices in it).

Some adjustments are not reported. A rights issue, for one, scales every earlier price by a
factor nobody publishes, so after reversing the reported splits those prices are no longer whole
rupiah. When a range has such a price, the source reads the stock's whole history once, finds the
runs of those days, and restores every price and dividend of each run whose factor the tick grid
proves (``steadyhand_idx.factor``, #160). A day in no proven run still raises
``UnrecoverablePricesError`` naming it (fail closed, spec §9.2), and a dividend in an unproven run
is refused, because its amount is known to be wrong.

Trading days come from ``holidays.toml``, never from which days have bars. A flat bar with no
volume on a holiday is a Yahoo placeholder and is dropped. A bar with trading on a holiday
contradicts the calendar, and is refused.

Corporate actions need no calendar: a dividend is restated through the reported splits, and
through a proven run's factor. So ``corporate_actions`` reads only splits and dividends, and a
range the holiday calendar does not cover still gives its actions. That is what a strategy's
look-back reads (M6 spec §4.3).
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, cast

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    DataUnavailableError,
    Instrument,
    InvalidBarError,
    Money,
    Split,
    UnavailableDaysError,
)
from steadyhand_idx.cache import jakarta_today
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import (
    GRID_START,
    PriceRow,
    Restoration,
    Run,
    find_runs,
    restore_dividend,
    restore_price,
)

if TYPE_CHECKING:
    import pandas as pd

SUFFIX = ".JK"
PRICE_COLUMNS = ("Open", "High", "Low", "Close")
REQUIRED_COLUMNS = (*PRICE_COLUMNS, "Volume", "Dividends")
YAHOO_TIMEZONE = "Asia/Jakarta"
# A reversed price counts as whole rupiah when it is this close to one. Yahoo's floats carry noise
# far below a rupiah; an unreported adjustment leaves a visible fraction (BBRI's close on
# 7 Sep 2021 reads 3,554.484130859375 in Yahoo's recorded response).
WHOLE_RUPIAH_TOLERANCE = Decimal("0.0001")
_SPLIT_DENOMINATOR_LIMIT = 1000


class UnrecoverablePricesError(UnavailableDaysError):
    """Yahoo's prices for these days carry an adjustment it does not report, and no factor could
    be proven for them, so the traded prices cannot be worked out. ``days`` lists every such day
    in the requested range."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        found = tuple(days)
        super().__init__(
            f"{ticker}: Yahoo's prices for {len(found)} day(s) from "
            f"{found[0].isoformat()} to {found[-1].isoformat()} carry an adjustment it "
            "does not report as a split (for example a rights issue), so the prices traded on "
            "those days cannot be recovered",
            found,
        )


@dataclass(frozen=True, slots=True)
class YahooRow:
    """One day as Yahoo gives it, split-adjusted. Numbers are Decimals of Yahoo's own floats."""

    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    dividend: Decimal


@dataclass(frozen=True, slots=True)
class YahooHistory:
    """What one request returns: the rows in range and the stock's whole split history.

    Each split is (ex date, new shares per old share), so a 5-for-1 split is 5.
    """

    ticker: str
    rows: tuple[YahooRow, ...]
    splits: tuple[tuple[date, Decimal], ...]


type Downloader = Callable[[str, date, date], YahooHistory]


def ticker_for(instrument: Instrument) -> str:
    if instrument.market != "IDX" or instrument.currency != IDR:
        msg = (
            f"Yahoo's .JK tickers cover IDX IDR stocks, "
            f"not {instrument.symbol} on {instrument.market}"
        )
        raise ValueError(msg)
    return instrument.symbol + SUFFIX


def _decimal(value: object) -> Decimal:
    """A pandas/numpy number as the Decimal of its shortest float spelling."""
    return Decimal(repr(float(cast("float", value))))


def history_from_frames(ticker: str, frame: pd.DataFrame, splits: pd.Series) -> YahooHistory:
    """Convert ``Ticker.history(auto_adjust=False, actions=True)`` and ``Ticker.splits``."""
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        msg = f"{ticker}: Yahoo's response has no {missing[0]!r} column; its format has changed"
        raise DataUnavailableError(msg)
    if frame.empty:
        msg = f"{ticker}: Yahoo returned no rows"
        raise DataUnavailableError(msg)
    for index in (frame.index, splits.index):
        zone = str(getattr(index, "tz", None))
        if zone != YAHOO_TIMEZONE and len(index):
            msg = f"{ticker}: Yahoo's dates are in {zone}, expected {YAHOO_TIMEZONE}"
            raise DataUnavailableError(msg)
    rows = tuple(
        YahooRow(
            day=day,
            open=_decimal(record["Open"]),
            high=_decimal(record["High"]),
            low=_decimal(record["Low"]),
            close=_decimal(record["Close"]),
            volume=int(record["Volume"]),
            dividend=_decimal(record["Dividends"]),
        )
        for stamp, record in frame.iterrows()
        if _priced(ticker, day := cast("pd.Timestamp", stamp).date(), record)
    )
    split_rows = tuple(
        (cast("pd.Timestamp", stamp).date(), _decimal(ratio)) for stamp, ratio in splits.items()
    )
    return YahooHistory(ticker, rows, split_rows)


def _priced(ticker: str, day: date, record: pd.Series) -> bool:
    """Whether Yahoo gives *record* its prices and volume. A row without them is a day Yahoo has
    no prices for, such as its unfinished day: no bar, like a day it leaves out. A dividend on such
    a row would be lost with it, so that row is refused instead (fail closed)."""
    if not any(math.isnan(float(record[column])) for column in (*PRICE_COLUMNS, "Volume")):
        return True
    if float(record["Dividends"]) != 0:
        msg = f"{ticker}: Yahoo has no prices for {day.isoformat()}, the ex-date of a dividend"
        raise DataUnavailableError(msg)
    return False


def history_to_json(history: YahooHistory, *, recorded: date, source: str) -> str:
    """A recorded response, as committed under ``tests/fixtures/yahoo`` (spec §10.3)."""
    document = {
        "ticker": history.ticker,
        "recorded": recorded.isoformat(),
        "source": source,
        "splits": [[day.isoformat(), str(ratio)] for day, ratio in history.splits],
        "rows": [
            {
                "day": row.day.isoformat(),
                "open": str(row.open),
                "high": str(row.high),
                "low": str(row.low),
                "close": str(row.close),
                "volume": row.volume,
                "dividend": str(row.dividend),
            }
            for row in history.rows
        ],
    }
    return json.dumps(document, indent=1) + "\n"


def history_from_json(path: Path) -> YahooHistory:
    """Load a recorded response written by ``history_to_json``."""
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = tuple(
        YahooRow(
            day=date.fromisoformat(row["day"]),
            open=Decimal(row["open"]),
            high=Decimal(row["high"]),
            low=Decimal(row["low"]),
            close=Decimal(row["close"]),
            volume=int(row["volume"]),
            dividend=Decimal(row["dividend"]),
        )
        for row in document["rows"]
    )
    splits = tuple((date.fromisoformat(day), Decimal(ratio)) for day, ratio in document["splits"])
    return YahooHistory(str(document["ticker"]), rows, splits)


def _split(instrument: Instrument, day: date, ratio: Decimal) -> Split:
    fraction = Fraction(ratio).limit_denominator(_SPLIT_DENOMINATOR_LIMIT)
    if fraction <= 0 or Decimal(fraction.numerator) / fraction.denominator != ratio:
        msg = f"{instrument.symbol}: Yahoo's split ratio {ratio} on {day.isoformat()} is not usable"
        raise DataUnavailableError(msg)
    return Split(instrument, day, fraction.denominator, fraction.numerator)


def _whole(value: Decimal) -> int | None:
    nearest = value.to_integral_value()
    return int(nearest) if abs(value - nearest) <= WHOLE_RUPIAH_TOLERANCE else None


def actions_in(
    history: YahooHistory,
    instrument: Instrument,
    start: date,
    end: date,
    runs: Sequence[Run] = (),
) -> list[CorporateAction]:
    """The splits and cash dividends with an ex-date from *start* to *end*, in date order.

    A dividend is restated through every reported split after its ex-date, as prices are, and
    through the factor of the proven run its ex-date falls in. One whose ex-date falls in an
    unproven run is refused, naming it: its amount is known to be wrong. No calendar is read.
    """
    actions: list[CorporateAction] = [
        _split(instrument, day, ratio) for day, ratio in history.splits if start <= day <= end
    ]
    refused: list[date] = []
    for row in history.rows:
        if start <= row.day <= end and row.dividend > 0:
            amount = row.dividend * _factor(history, row.day)
            run = _covering(runs, row.day)
            if run is not None and run.factor is None:
                refused.append(row.day)
                continue
            if run is not None and run.factor is not None:
                amount = restore_dividend(amount, run.factor)
            actions.append(CashDividend(instrument, row.day, amount))
    if refused:
        raise UnprovenDividendsError(history.ticker, refused)
    actions.sort(key=lambda action: action.ex_date)
    return actions


class UnprovenDividendsError(UnavailableDaysError):
    """Dividends whose ex-date falls in a run of Yahoo's prices carrying an unreported adjustment
    that could not be proven: their recorded amounts are known to be wrong (#160 spec §5)."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        found = tuple(days)
        named = ", ".join(day.isoformat() for day in found)
        super().__init__(
            f"{ticker}: the dividend(s) with ex-date {named} fall in days whose prices carry an "
            "adjustment Yahoo does not report and steadyhand could not prove, so the amounts "
            "are known to be wrong",
            found,
        )


def reversed_prices(history: YahooHistory, row: YahooRow) -> tuple[Decimal, ...]:
    """*row*'s open, high, low and close with every reported split after it reversed."""
    factor = _factor(history, row.day)
    return tuple(value * factor for value in (row.open, row.high, row.low, row.close))


def _all_whole(prices: Sequence[Decimal]) -> bool:
    return all(_whole(price) is not None for price in prices)


def _placeholder(row: YahooRow) -> bool:
    """A flat row with no volume: it repeats an earlier close, on a holiday or not."""
    return row.volume == 0 and row.open == row.high == row.low == row.close


def evidence(history: YahooHistory) -> list[PriceRow]:
    """The proof's input (#160 spec §4): every row with a price that is not whole after the
    reported splits are reversed, in date order, except a flat row with no volume, which repeats
    an earlier close and is no evidence. Its volume plays no part (spec §3.6)."""
    found: list[PriceRow] = []
    for row in history.rows:
        prices = reversed_prices(history, row)
        if not _placeholder(row) and not _all_whole(prices):
            found.append(PriceRow(row.day, prices))
    return found


def _covering(runs: Sequence[Run], day: date) -> Run | None:
    return next((run for run in runs if run.first <= day <= run.last), None)


def _amounts(prices: Sequence[Decimal], run: Run | None, day: date) -> list[int] | None:
    """The traded prices: whole as they are, restored in a proven run, else ``None``."""
    whole = [_whole(price) for price in prices]
    if all(amount is not None for amount in whole):
        return [cast("int", amount) for amount in whole]
    if run is None or run.factor is None:
        return None
    return [restore_price(price, run.factor, day).amount for price in prices]


def _factor(history: YahooHistory, day: date) -> Decimal:
    """The product of every reported split ratio after *day*, which Yahoo divided *day* by."""
    factor = Decimal(1)
    for split_day, ratio in history.splits:
        if split_day > day:
            factor *= ratio
    return factor


def unadjust(
    history: YahooHistory,
    instrument: Instrument,
    calendar: IdxCalendar,
    span: tuple[date, date],
    runs: Sequence[Run] = (),
) -> tuple[list[Bar], list[CorporateAction]]:
    """The bars and actions from the first to the last day of *span*, with Yahoo's split
    adjustments reversed and the prices of every day in a proven run of *runs* restored."""
    start, end = span
    bars: list[Bar] = []
    unrecoverable: list[date] = []
    for row in history.rows:
        if not start <= row.day <= end:
            continue
        flat = row.open == row.high == row.low == row.close
        if not calendar.is_trading_day(row.day):
            if row.volume == 0 and flat:
                continue
            msg = (
                f"{history.ticker}: Yahoo shows trading on {row.day.isoformat()}, "
                "which the IDX calendar says was a holiday"
            )
            raise DataUnavailableError(msg)
        amounts = _amounts(reversed_prices(history, row), _covering(runs, row.day), row.day)
        volume = _whole(row.volume / _factor(history, row.day))
        if amounts is None or volume is None:
            unrecoverable.append(row.day)
            continue
        opening, high, low, closing = (Money(amount, IDR) for amount in amounts)
        try:
            bars.append(Bar(instrument, row.day, opening, high, low, closing, volume))
        except InvalidBarError as error:
            msg = f"{history.ticker}: {error}"
            raise DataUnavailableError(msg) from error
    if unrecoverable:
        raise UnrecoverablePricesError(history.ticker, unrecoverable)
    return bars, actions_in(history, instrument, start, end, runs)


@dataclass(frozen=True, slots=True)
class RequestPolicy:
    """How politely and how persistently Yahoo is asked (spec §9.2)."""

    attempts: int = 3
    backoff_seconds: float = 1.0
    pause_seconds: float = 1.0


class YahooDataSource:
    """A ``DataSource`` backed by Yahoo Finance. Wrap it in ``CachedDataSource`` for real use."""

    def __init__(
        self,
        calendar: IdxCalendar | None = None,
        *,
        download: Downloader | None = None,
        sleep: Callable[[float], None] = time.sleep,
        policy: RequestPolicy = RequestPolicy(),  # noqa: B008 - a frozen value, safe to share
        today: Callable[[], date] = jakarta_today,
    ) -> None:
        self._calendar = IdxCalendar.shipped() if calendar is None else calendar
        self._download = download_history if download is None else download
        self._sleep = sleep
        self._policy = policy
        self._today = today
        self._requests = 0
        self._last: tuple[tuple[str, date, date], YahooHistory] | None = None
        self._runs: dict[str, tuple[Run, ...]] = {}

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        history = self._history(instrument, start, end)
        runs = self._runs_for(history, start, end)
        return unadjust(history, instrument, self._calendar, (start, end), runs)[0]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        """The splits and dividends in the range, read without the calendar (``actions_in``)."""
        history = self._history(instrument, start, end)
        return actions_in(history, instrument, start, end, self._runs_for(history, start, end))

    def restorations(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[Restoration, ...]:
        """The proven runs overlapping the range, oldest first. A range with no price that is
        not whole reads no runs, and restores nothing, so it has none."""
        history = self._history(instrument, start, end)
        return tuple(
            Restoration(instrument, run.first, run.last, run.factor, run.prices)
            for run in self._runs_for(history, start, end)
            if run.factor is not None and run.first <= end and run.last >= start
        )

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        return self._fetch(ticker_for(instrument), start, end)

    def _runs_for(self, history: YahooHistory, start: date, end: date) -> tuple[Run, ...]:
        """The runs of the stock's whole history, from ``GRID_START`` to today, read once per
        ticker, when the range has a price that is not whole; none otherwise (#160 spec §5)."""
        if all(
            _all_whole(reversed_prices(history, row))
            for row in history.rows
            if start <= row.day <= end
        ):
            return ()
        ticker = history.ticker
        if ticker not in self._runs:
            whole = self._request(ticker, GRID_START, self._today())
            self._runs[ticker] = find_runs(evidence(whole))
        return self._runs[ticker]

    def _fetch(self, ticker: str, start: date, end: date) -> YahooHistory:
        """One download per range: ``bars`` then ``corporate_actions`` reuse it."""
        key = (ticker, start, end)
        if self._last is not None and self._last[0] == key:
            return self._last[1]
        history = self._request(ticker, start, end)
        self._last = (key, history)
        return history

    def _request(self, ticker: str, start: date, end: date) -> YahooHistory:
        """Ask Yahoo, under the request policy: a pause between requests, retries with backoff."""
        failure: DataUnavailableError | None = None
        for attempt in range(self._policy.attempts):
            if attempt:
                self._sleep(self._policy.backoff_seconds * 2 ** (attempt - 1))
            elif self._requests:
                self._sleep(self._policy.pause_seconds)
            self._requests += 1
            try:
                return self._download(ticker, start, end)
            except DataUnavailableError as error:
                failure = error
        msg = (
            f"{ticker}: no data from Yahoo for {start.isoformat()} to {end.isoformat()} "
            f"after {self._policy.attempts} attempts: {failure}"
        )
        raise DataUnavailableError(msg) from failure


def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
    """Ask Yahoo for one ticker's history (network; run daily by the yahoo-shape workflow).

    This is the only function that talks to Yahoo, and the only code excluded from coverage:
    ``tests/meta/test_coverage_exclusions.py`` holds it to that. Everything it returns goes
    through ``history_from_frames``, which the tests run on real recorded data.
    """
    import yfinance  # noqa: PLC0415 - a heavy import, paid only when data is really fetched

    yfinance.config.debug.hide_exceptions = False  # raise a failure instead of logging it
    try:
        handle = yfinance.Ticker(ticker)
        frame = handle.history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),  # yfinance's end is exclusive
            auto_adjust=False,
            actions=True,
        )
        splits = handle.splits
    except Exception as error:  # a network library's failures are not ours to enumerate
        msg = f"{ticker}: the request to Yahoo failed: {error}"
        raise DataUnavailableError(msg) from error
    return history_from_frames(ticker, frame, splits)
```

**`scripts/record_golden.py`** (implemented: 3 edits)

<!-- edit: scripts/record_golden.py -->
Replace:
```python
def recorded(ticker: str, start: date, end: date, *, last: date = END) -> YahooHistory:
    """Yahoo's recorded answer from the recordings ending on *last*. A range outside the
    recording is refused, never invented."""
    if start < HISTORY_START or end > last:
```
with:
```python
def recorded(ticker: str, start: date, end: date, *, last: date = END) -> YahooHistory:
    """Yahoo's recorded answer from the recordings ending on *last*, or from a whole-history
    recording for exactly its range. A range outside the recordings is refused, never invented."""
    if ticker in WHOLE_HISTORIES and (start, end) == (GRID_START, WHOLE_RECORDED):
        return history_from_json(FIXTURES / f"{ticker}_{start.isoformat()}_{end.isoformat()}.json")
    if start < HISTORY_START or end > last:
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    folder.mkdir(parents=True, exist_ok=True)
    yahoo = YahooDataSource(download=download, sleep=_no_wait)
    with BarCache(folder / "bars.sqlite") as store:
        source = CachedDataSource(yahoo, store, today=lambda: RECORDED)
        market = Market(universe(), source, IdxMarketRules())
```
with:
```python
    folder.mkdir(parents=True, exist_ok=True)
    with BarCache(folder / "bars.sqlite") as store:
        source = CachedDataSource(replay(download), store, today=lambda: RECORDED)
        market = Market(universe(), source, IdxMarketRules())
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    histories were recorded."""
    raise NotImplementedError("replay")

```
with:
```python
    histories were recorded."""
    return YahooDataSource(download=download, sleep=_no_wait, today=lambda: WHOLE_RECORDED)

```

Generate `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json sha256=fa3223e8ed25278d96435190cd94e42bac38d2a49d5991cff323b6f806ff8306 -->
```bash
uv run python scripts/record_golden.py
```

Generate `tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json sha256=bc9f00747ed5ebd648a2bb57d4abddea92cb27e1dd45837124a06f3b8a6f67a4 -->
```bash
uv run python scripts/record_golden.py
```

Generate `tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json sha256=b9170717b5d511acb8bccf258ddcdc12561f7aa8d8ef8839d3b3ea038dcef120 -->
```bash
uv run python scripts/record_golden.py
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1650 passed=1650 -->
Expected: every command exits 0; 1650 passed, 100% branch coverage; the performance step passes its ten tests: the nine before it and `test_bbri_s_whole_history_is_proven_inside_the_budget`. CI's second job runs the same 1650 tests on Python 3.13 under `-W error`.

- [ ] **Step 7: Mutations.** Run M386–M402 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(idx): #160 S2 restore Yahoo's unreported price factor in the source and the cache`, ending in the story's issue number as `(#N)`), as **Merging a story** says. The PR body lists every golden figure that changed, with its cause.

---

### Task 3: #160 S3 A note for each restored run, and its lesson

**Acceptance criteria (story text):**
1. `DATA_PRICES_RESTORED = "data.prices.restored"` is in `steadyhand_idx.notes` and passes the key meta-test. `Restoration.noise` is whether its factor rounds to 1.000000, and `Restoration.note` is the #160 spec §7 text, the factor's or the noise run's, with the price count written "7,380".
2. The core `DataSource` protocol gains `data_notes(instruments, start, end) -> Sequence[Note]`, and a source without it is not a `DataSource`. `YahooDataSource.data_notes` is one note per proven run overlapping the range among the runs already read, never a request (scope decision 14); `CachedDataSource.data_notes` is the stored restorations' notes and the upstream's, each once (scope decision 15). The test sources return none.
3. `backtest` and `compare` include the source's notes over every stock fetched, from the look-back's first day (or the run's) to the last, after the universe's warnings (scope decision 16).
4. The lesson `idx.restored_prices` (module `how-idx-works`, position 8, `see_also` `backtest.data_gaps` and `idx.ticks`) explains the key and prints with `learn`.
5. The golden runs carry BBRI's one restored-prices warning and no figure changes; `backtest` and `compare` print it under *Warnings* and point at the lesson.
6. Core §4.3 and §9.2 and M6 §4.3 carry the #160 amendments, each with a line in its review log.
7. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M403–M412 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand_idx/training/lessons/en/idx.restored_prices.md`
- Modify: `.../steadyhand/{data,backtest}.py`, `.../steadyhand_idx/{notes,factor,yahoo,cache}.py`, `tests/fixtures/golden/*.json` (generated), `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`, `docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md`
- Test: `tests/idx/{test_factor,test_yahoo,test_cache}.py`, `tests/engine/{test_backtest,test_protocols}.py`, `tests/cli/{cli_world,test_backtest_command,test_compare_command,test_learn,test_paper_run}.py`, `tests/golden/test_golden_backtest.py`, `tests/perf/synthetic.py`

**Interfaces:**
- Consumes: Task 2's `Restoration`, `YahooDataSource`, `CachedDataSource`, `BarCache.restorations`; `backtest._data_warnings`.
- Produces: `DATA_PRICES_RESTORED` in `steadyhand_idx.notes`; `Restoration.noise` and `Restoration.note`; `DataSource.data_notes(instruments, start, end)`; `YahooDataSource.data_notes` and `CachedDataSource.data_notes`; `RESTORED` in `tests/cli/cli_world.py`; the lesson `idx.restored_prices`.

- [ ] **Step 1: Branch.** `git switch -c feat/160-s3-notes origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/cli_world.py`** (changed: 1 edit)

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
(``record_golden.VALUES``): a two-year test, whose look-back fits in the recordings."""

```
with:
```python
(``record_golden.VALUES``): a two-year test, whose look-back fits in the recordings."""

RESTORED = (
    "BBRI: Yahoo's prices from 2014-01-06 to 2021-09-07 carry an adjustment Yahoo does not "
    "report, so steadyhand restored them: every price and dividend in that span is multiplied "
    "by 1.100019, proven by 7,380 prices that fit the IDX tick grid at that factor and at no "
    "other."
)
"""The golden window's one warning: BBRI's restoration in its whole recording (#160)."""

```

**`tests/cli/test_backtest_command.py`** (changed: 5 edits)

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    PLACEHOLDERS,
    Cli,
```
with:
```python
    PLACEHOLDERS,
    RESTORED,
    Cli,
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules
from steadyhand_idx.training import catalogue
```
with:
```python
from steadyhand_idx import BarCache, CachedDataSource, IdxMarketRules
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.training import catalogue
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    )
    # BBRI's prices up to 2021-09-07 are restored (#160), so nothing in the window is refused.
    assert "Warnings:" not in result.out
    assert f"\n\nWrote {reports / f'{STEM}.md'}\nWrote {reports / f'{STEM}.csv'}\n\n" in result.out
```
with:
```python
    )
    # BBRI's prices up to 2021-09-07 are restored (#160): the one warning says so, and nothing
    # in the window is refused.
    assert f"\n\nWarnings:\n- {RESTORED}\n\n" in result.out
    assert f"\n\nWrote {reports / f'{STEM}.md'}\nWrote {reports / f'{STEM}.csv'}\n\n" in result.out
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    assert f"More: steadyhand-idx learn {refused}\n" not in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")
```
with:
```python
    assert f"More: steadyhand-idx learn {refused}\n" not in result.out
    restored = catalogue().for_key(DATA_PRICES_RESTORED).id
    assert restored == "idx.restored_prices"
    assert f"More: steadyhand-idx learn {restored}\n" in result.out
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    assert lines[6] == "| Final value | IDR 96,825,198 |"
    assert "## Warnings" not in text
    assert "## Day warnings" not in text
```
with:
```python
    assert lines[6] == "| Final value | IDR 96,825,198 |"
    assert f"\n## Warnings\n\n- {RESTORED}\n" in text
    assert "## Day warnings" not in text
```

**`tests/cli/test_compare_command.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_compare_command.py -->
Replace:
```python
import pytest
from cli_world import GROWTH_CONFIG, Cli, market_cli
from record_golden import GOLDEN, run
```
with:
```python
import pytest
from cli_world import GROWTH_CONFIG, RESTORED, Cli, market_cli
from record_golden import GOLDEN, run
```

<!-- edit: tests/cli/test_compare_command.py -->
Replace:
```python
    )
    assert "Warnings:" not in result.out  # BBRI's prices are restored (#160): none is refused
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
```
with:
```python
    )
    # BBRI's prices are restored (#160): that is the one warning, and none is refused.
    assert f"\n\nWarnings:\n- {RESTORED}\n\n" in result.out
    assert "\n\nWhat this means\n• Prices, and what your portfolio is worth: " in result.out
```

**`tests/cli/test_learn.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_learn.py -->
Replace:
```python
from steadyhand import DISCLAIMER
from steadyhand_idx.training import catalogue
```
with:
```python
from steadyhand import DISCLAIMER
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.training import catalogue
```

<!-- edit: tests/cli/test_learn.py -->
Replace:
```python
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")

```
with:
```python
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")


def test_the_restored_prices_lesson_explains_its_note_and_prints(cli: Cli) -> None:
    lesson = catalogue().for_key(DATA_PRICES_RESTORED)
    assert (lesson.id, lesson.module, lesson.position) == (
        "idx.restored_prices",
        "how-idx-works",
        8,
    )
    assert lesson.see_also == ("backtest.data_gaps", "idx.ticks")
    result = cli("learn", lesson.id)
    assert result.code == 0, result.err
    assert result.out.startswith(f"{lesson.title}\n\n{lesson.body.strip()}\n\nSee also: ")

```

**`tests/cli/test_paper_run.py`** (changed: 3 edits)

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    Money,
    day_inputs,
```
with:
```python
    Money,
    Note,
    day_inputs,
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
        return self.inner.corporate_actions(instrument, start, end)


def edited(edit: Callable[[Bar], Bar | None]) -> SourceFactory:
```
with:
```python
        return self.inner.corporate_actions(instrument, start, end)

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


def edited(edit: Callable[[Bar], Bar | None]) -> SourceFactory:
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
        return self.inner.corporate_actions(instrument, start, end)


def test_days_another_run_saves_meanwhile_are_left_to_it(tmp_path: Path) -> None:
```
with:
```python
        return self.inner.corporate_actions(instrument, start, end)

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


def test_days_another_run_saves_meanwhile_are_left_to_it(tmp_path: Path) -> None:
```

**`tests/engine/test_backtest.py`** (changed: 6 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
from steadyhand_idx import UNIVERSE_SURVIVORSHIP_GAP, IdxMarketRules

```
with:
```python
from steadyhand_idx import UNIVERSE_SURVIVORSHIP_GAP, IdxMarketRules
from steadyhand_idx.notes import DATA_PRICES_RESTORED

```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
GAP = Note(UNIVERSE_SURVIVORSHIP_GAP, "a gap")

```
with:
```python
GAP = Note(UNIVERSE_SURVIVORSHIP_GAP, "a gap")
RESTORED = Note(DATA_PRICES_RESTORED, "restored")

```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
        broken: frozenset[Instrument] = frozenset(),
    ) -> None:
```
with:
```python
        broken: frozenset[Instrument] = frozenset(),
        notes: Sequence[Note] = (),
    ) -> None:
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
        self._broken = broken
        self.requests: list[tuple[str, str, date, date]] = []

```
with:
```python
        self._broken = broken
        self._notes = notes
        self.requests: list[tuple[str, str, date, date]] = []
        self.noted: list[tuple[tuple[str, ...], date, date]] = []

```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
            a for a in self._actions if a.instrument == instrument and start <= a.ex_date <= end
        ]

    def _check(self, kind: str, instrument: Instrument, start: date, end: date) -> None:
```
with:
```python
            a for a in self._actions if a.instrument == instrument and start <= a.ex_date <= end
        ]

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        self.noted.append((tuple(i.symbol for i in instruments), start, end))
        return self._notes

    def _check(self, kind: str, instrument: Instrument, start: date, end: date) -> None:
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python

def test_compare_fetches_the_look_back_once_for_every_strategy() -> None:
```
with:
```python

def test_the_source_s_data_notes_cover_the_window_and_follow_the_universe_s() -> None:
    source = _Source(calm(), notes=[RESTORED])
    result = run(source, _Universe([(START, frozenset({BBCA, BBRI}))], warnings=[GAP]))
    assert source.noted == [(("BBCA", "BBRI"), START, END)]
    assert result.warnings == (GAP, RESTORED)


def test_the_source_s_data_notes_reach_back_over_the_look_back() -> None:
    source = _Source(calm(), LOOKED_BACK, notes=[RESTORED])
    result = run(source, chosen=looking_back())
    assert source.noted == [(("BBCA", "BBRI"), SINCE, END)]
    assert result.warnings == (RESTORED,)
    compared = _Source(calm(), LOOKED_BACK, notes=[RESTORED])
    comparison = compare([_Reader()], market(compared), START, END, looking_back(1))
    assert compared.noted == [(("BBCA", "BBRI"), date(2024, 1, 1), END)]
    assert comparison.warnings == (RESTORED,)


def test_compare_fetches_the_look_back_once_for_every_strategy() -> None:
```

**`tests/engine/test_protocols.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python
        return ()


class _MinimalBroker:
```
with:
```python
        return ()

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


class _MinimalBroker:
```

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python

def test_a_minimal_class_satisfies_broker() -> None:
```
with:
```python

def test_data_notes_is_required_of_a_data_source() -> None:
    members = {name: value for name, value in vars(_MinimalSource).items() if name != "data_notes"}
    assert not isinstance(type("Partial", (), members)(), DataSource)


def test_a_minimal_class_satisfies_broker() -> None:
```

**`tests/golden/test_golden_backtest.py`** (changed: 3 edits)

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    Money,
    years_before,
)
from steadyhand_idx import IdxMarketRules

```
with:
```python
    Money,
    Note,
    years_before,
)
from steadyhand_idx import IdxMarketRules
from steadyhand_idx.notes import DATA_PRICES_RESTORED

```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    assert stored["positions"] == {"BBCA": 2_900}
    assert [warning[0] for warning in stored["warnings"]] == [DATA_DIVIDENDS_HISTORY_REFUSED]
    assert stored["warnings"][0][1].startswith(
        "TLKM: the data source refused its corporate actions from 2018-01-01 to 2021-01-31, "
```
with:
```python
    assert stored["positions"] == {"BBCA": 2_900}
    assert [warning[0] for warning in stored["warnings"]] == [
        DATA_PRICES_RESTORED,
        DATA_DIVIDENDS_HISTORY_REFUSED,
    ]
    assert stored["warnings"][1][1].startswith(
        "TLKM: the data source refused its corporate actions from 2018-01-01 to 2021-01-31, "
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    assert held["BBRI"] == 4_600
    assert result.warnings == ()

```
with:
```python
    assert held["BBRI"] == 4_600
    # The restoration is the run's one warning: BBRI's whole recording from GRID_START.
    assert result.warnings == (
        Note(
            DATA_PRICES_RESTORED,
            "BBRI: Yahoo's prices from 2014-01-06 to 2021-09-07 carry an adjustment Yahoo does "
            "not report, so steadyhand restored them: every price and dividend in that span is "
            "multiplied by 1.100019, proven by 7,380 prices that fit the IDX tick grid at that "
            "factor and at no other.",
        ),
    )

```

**`tests/idx/test_cache.py`** (changed: 1 edit)

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
        (date(2021, 10, 1), date(2021, 10, 29)),
    ]
```
with:
```python
        (date(2021, 10, 1), date(2021, 10, 29)),
    ]


FIVE_YEARS = "BBRI.JK_2017-01-31_2022-01-31.json"


def test_the_cached_source_s_notes_come_from_its_stored_restorations(cache: BarCache) -> None:
    source, _ = source_for(cache, FIVE_YEARS, date(2026, 9, 25))
    source.bars(BBRI, *SEP)
    assert source.data_notes([BBRI, BBCA], *SEP) == (RESTORED.note,)  # stored and upstream: once
    fresh, counting = source_for(cache, FIVE_YEARS, date(2026, 9, 25))
    assert fresh.data_notes([BBRI], *SEP) == (RESTORED.note,)
    assert fresh.data_notes([BBRI], *OCT) == ()
    assert counting.asked == []


def test_a_run_read_only_in_today_s_bar_still_has_its_note(cache: BarCache) -> None:
    today = date(2021, 9, 7)
    source, counting = source_for(cache, FIVE_YEARS, today)
    source.bars(BBRI, today, today)  # today's bar is never stored, nor its restoration
    assert cache.restorations(BBRI, today, today) == []
    assert source.data_notes([BBRI], today, today) == (RESTORED.note,)
    assert counting.asked == [(today, today), (date(2014, 1, 6), today)]
```

**`tests/idx/test_factor.py`** (changed: 4 edits)

<!-- edit: tests/idx/test_factor.py -->
Replace:
```python

from steadyhand import IDR, Money
from steadyhand_idx._datafile import Dated, Where, load_shipped
```
with:
```python

from steadyhand import IDR, Instrument, Money
from steadyhand.notes import Note
from steadyhand_idx._datafile import Dated, Where, load_shipped
```

<!-- edit: tests/idx/test_factor.py -->
Replace:
```python
    PriceRow,
    Run,
```
with:
```python
    PriceRow,
    Restoration,
    Run,
```

<!-- edit: tests/idx/test_factor.py -->
Replace:
```python
)
from steadyhand_idx.ticks import TickRow, TickTier, parse_ticks
```
with:
```python
)
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.ticks import TickRow, TickTier, parse_ticks
```

<!-- edit: tests/idx/test_factor.py -->
Replace:
```python
    assert not is_noise(Decimal("1.0000015"))
```
with:
```python
    assert not is_noise(Decimal("1.0000015"))


BBRI = Instrument("BBRI", "IDX", IDR)


def test_a_restoration_s_note_names_its_span_factor_and_proof() -> None:
    run = Restoration(BBRI, date(2017, 1, 31), date(2021, 9, 7), Decimal("1.100019"), 4_412)
    assert not run.noise
    assert run.note == Note(
        DATA_PRICES_RESTORED,
        "BBRI: Yahoo's prices from 2017-01-31 to 2021-09-07 carry an adjustment Yahoo does not "
        "report, so steadyhand restored them: every price and dividend in that span is "
        "multiplied by 1.100019, proven by 4,412 prices that fit the IDX tick grid at that "
        "factor and at no other.",
    )


def test_a_noise_restoration_s_note_says_it_is_a_rounding_error() -> None:
    run = Restoration(BBRI, date(2019, 1, 2), date(2019, 3, 29), Decimal("0.9999999"), 240)
    assert run.noise
    assert run.note == Note(
        DATA_PRICES_RESTORED,
        "BBRI: Yahoo's prices from 2019-01-02 to 2019-03-29 miss whole rupiah by a rounding "
        "error after its reported splits are reversed, so steadyhand put each one on the IDX "
        "tick grid, proven by 240 prices that fit it with no other factor.",
    )
```

**`tests/idx/test_yahoo.py`** (changed: 1 edit)

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python

def unwhole(day: date, price: str, *, volume: int = 100, dividend: str = "0") -> YahooRow:
```
with:
```python

def test_data_notes_name_the_runs_already_read_and_never_ask_yahoo() -> None:
    source, replay = restoring()
    september = (date(2021, 9, 1), date(2021, 9, 30))
    assert source.data_notes([BBRI, BBCA], *september) == ()
    source.bars(BBRI, *september)
    calls = list(replay.calls)
    run = Restoration(BBRI, date(2017, 1, 31), date(2021, 9, 7), Decimal("1.100019"), 4_412)
    assert source.data_notes([BBCA, BBRI], *september) == (run.note,)
    assert source.data_notes([BBRI], date(2021, 9, 8), date(2021, 9, 30)) == ()
    assert replay.calls == calls


def unwhole(day: date, price: str, *, volume: int = 100, dividend: str = "0") -> YahooRow:
```

**`tests/perf/synthetic.py`** (changed: 1 edit)

<!-- edit: tests/perf/synthetic.py -->
Replace:
```python
        return [a for a in self._actions[instrument] if start <= a.ex_date <= end]


class All:
```
with:
```python
        return [a for a in self._actions[instrument] if start <= a.ex_date <= end]

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        return ()


class All:
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
    Money,
    OtherAction,
```
with:
```python
    Money,
    Note,
    OtherAction,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
```
with:
```python

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> tuple[Note, ...]:
        """One note per restoration stored for *instruments* overlapping the range, and per run
        the upstream inferred for today's bar, which is never stored; each note once."""
        raise NotImplementedError("CachedDataSource.data_notes")

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
```

**`packages/steadyhand-idx/src/steadyhand_idx/factor.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
Replace:
```python

from steadyhand import IDR, Instrument, Money
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.ticks import TICKS_FILE, TickRow, TickTier, parse_ticks
```
with:
```python

from steadyhand import IDR, Instrument, Money, Note
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.ticks import TICKS_FILE, TickRow, TickTier, parse_ticks
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
Replace:
```python
    prices: int

```
with:
```python
    prices: int
    @property
    def noise(self) -> bool:
        """Whether the factor rounds to 1.000000: a split reversal's rounding error (§4.5)."""
        raise NotImplementedError("Restoration.noise")

    @property
    def note(self) -> Note:
        """What a backtest's warnings say about this run (spec §7)."""
        raise NotImplementedError("Restoration.note")

```

**`packages/steadyhand-idx/src/steadyhand_idx/notes.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/notes.py -->
Replace:
```python
"""The LQ45 record has no list between two dates more than one review apart."""

```
with:
```python
"""The LQ45 record has no list between two dates more than one review apart."""

DATA_PRICES_RESTORED = "data.prices.restored"
"""Yahoo's prices over a span carry an adjustment it does not report, or a rounding error, and
the source restored them to the IDX tick grid (#160 spec §7)."""

```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    Money,
    Split,
```
with:
```python
    Money,
    Note,
    Split,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
```
with:
```python

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> tuple[Note, ...]:
        """One note per proven run overlapping the range among the runs already inferred: never
        a request, since every range a backtest reads has been read by then (#160 spec §7)."""
        raise NotImplementedError("YahooDataSource.data_notes")

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
```
with:
```python

def _proven(
    instrument: Instrument, runs: Sequence[Run], start: date, end: date
) -> tuple[Restoration, ...]:
    """The proven *runs* overlapping *start* to *end*, oldest first, as restorations."""
    raise NotImplementedError("_proven")


def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

def _calendar_days(start: date, end: date) -> Iterator[date]:
```
with:
```python

def _stocks(members: Mapping[date, frozenset[Instrument]]) -> list[Instrument]:
    """Every stock the universe holds on any day, in a fixed order: the stocks fetched."""
    raise NotImplementedError("_stocks")


def _calendar_days(start: date, end: date) -> Iterator[date]:
```

**`packages/steadyhand/src/steadyhand/data.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/data.py -->
Replace:
```python

from steadyhand.types import Bar, CorporateAction, Instrument
```
with:
```python

from steadyhand.notes import Note
from steadyhand.types import Bar, CorporateAction, Instrument
```

<!-- edit: packages/steadyhand/src/steadyhand/data.py -->
Replace:
```python
        """Splits, cash dividends and other actions with an ex-date in the range."""
        ...
```
with:
```python
        """Splits, cash dividends and other actions with an ex-date in the range."""
        ...

    def data_notes(
        self, instruments: Sequence[Instrument], start: date, end: date
    ) -> Sequence[Note]:
        """Notes on the data supplied for *instruments* from *start* to *end*, for a backtest's
        warnings: a source that changed nothing it supplied returns none."""
        ...
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1659 failed=15 -->
Expected: 1659 run, 15 failed (pytest reads `15 failed`). 5 are `NotImplementedError` from the stubs: `Restoration.noise`, which both note tests read first, `YahooDataSource.data_notes` once and `CachedDataSource.data_notes` twice; the rest are the behaviour not there yet: `_data_warnings` never asks the source (the two backtest tests see no `data_notes` call), the golden runs and the `backtest` and `compare` commands carry no warning, the dividend-growth golden run has one warning where two are wanted, `learn` finds no lesson for `data.prices.restored`, and the key meta-tests find `DATA_PRICES_RESTORED` with no lesson and no `Note` built from it. One test passes against the stubs: `test_data_notes_is_required_of_a_data_source`, because the stubbed protocol already lists `data_notes`; mutation M411 shows it goes red without it.

- [ ] **Step 5: Implement.** The lesson, the golden files and the spec amendments are part of this step.

**`docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`** (changed: 3 edits)

<!-- edit: docs/superpowers/specs/2026-09-24-steadyhand-core-design.md -->
Replace:
```markdown
    def corporate_actions(self, instrument: Instrument, start: date, end: date) -> Sequence[CorporateAction]: ...

```
with:
```markdown
    def corporate_actions(self, instrument: Instrument, start: date, end: date) -> Sequence[CorporateAction]: ...
    def data_notes(self, instruments: Sequence[Instrument], start: date, end: date) -> Sequence[Note]: ...  # a backtest's data warnings (#160 spec §7)

```

<!-- edit: docs/superpowers/specs/2026-09-24-steadyhand-core-design.md -->
Replace:
```markdown
- `yfinance` is pinned to an exact version, and Dependabot proposes upgrades.
- It fetches OHLCV plus dividends and splits. Yahoo's prices are split-adjusted even with `auto_adjust=False` (`t-hist.md` §6), so the source reverses every reported split using the stock's whole split history. An adjustment Yahoo does not report, such as a rights issue, leaves prices that are not whole rupiah after reversal. Those days cannot be recovered and are refused with `UnrecoverablePricesError`, naming them (measured on 2026-09-25: BBRI to 2021-09-07, SMGR to 2022-12-12, MDKA to 2022-04-13, five INCO days in June 2024). A zero-volume bar on a trading day is kept as "did not trade"; a flat empty bar on a holiday is dropped; trading on a holiday is refused.
- Yahoo's dividends carry the **ex date only**, with no pay or recording date (`docs/research/t-pay.md` §5). Trading days come from `holidays.toml`, never from which days have bars: `^JKSE` has no bar for 22 Sep 2026, which was a trading day (`t-pay.md` §2).
```
with:
```markdown
- `yfinance` is pinned to an exact version, and Dependabot proposes upgrades.
- It fetches OHLCV plus dividends and splits. Yahoo's prices are split-adjusted even with `auto_adjust=False` (`t-hist.md` §6), so the source reverses every reported split using the stock's whole split history. An adjustment Yahoo does not report, such as a rights issue, leaves prices that are not whole rupiah after reversal. When exactly one factor from 1 to below 2 puts a whole run of those prices back on the IDX tick grid, the source restores the run's prices and dividends by that factor, and a backtest's warnings say so with the key `data.prices.restored` (#160 spec §4–§7). The days the proof cannot settle are refused with `UnrecoverablePricesError`, naming them (measured on 2026-09-25, before #160: BBRI to 2021-09-07, SMGR to 2022-12-12, MDKA to 2022-04-13, five INCO days in June 2024). A zero-volume bar on a trading day is kept as "did not trade"; a flat empty bar on a holiday is dropped; trading on a holiday is refused.
- Yahoo's dividends carry the **ex date only**, with no pay or recording date (`docs/research/t-pay.md` §5). Trading days come from `holidays.toml`, never from which days have bars: `^JKSE` has no bar for 22 Sep 2026, which was a trading day (`t-pay.md` §2).
```

<!-- edit: docs/superpowers/specs/2026-09-24-steadyhand-core-design.md -->
Replace:
```markdown
- **Pass 15 (2026-09-30, the M6 spec):** §8 and §9.5 were brought into line with the M6 spec's scope decisions (`docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md`). (1) `dividend-growth`'s rule was "has not fallen in any of the last 5 calendar years", which 4 of 45 LQ45 stocks passed for a January 2021 review and 1 of 45 in 2025 (M6 spec §3); it is now "paid in each of the last 6 years, and the latest year's total is at least the total five years before", which 19 and 20 passed (SD1); (2) "weighted towards spreading pay months" became "chosen to spread pay months", with equal weights (SD2); (3) §9.5's `[strategy]` table names its flat, optional keys (SD3). A grep for `has not fallen` and `weighted towards` finds no contradicting wording left.
```
with:
```markdown
- **Pass 15 (2026-09-30, the M6 spec):** §8 and §9.5 were brought into line with the M6 spec's scope decisions (`docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md`). (1) `dividend-growth`'s rule was "has not fallen in any of the last 5 calendar years", which 4 of 45 LQ45 stocks passed for a January 2021 review and 1 of 45 in 2025 (M6 spec §3); it is now "paid in each of the last 6 years, and the latest year's total is at least the total five years before", which 19 and 20 passed (SD1); (2) "weighted towards spreading pay months" became "chosen to spread pay months", with equal weights (SD2); (3) §9.5's `[strategy]` table names its flat, optional keys (SD3). A grep for `has not fallen` and `weighted towards` finds no contradicting wording left.
- **Pass 16 (2026-10-01, the #160 spec):** §4.3 and §9.2 were brought into line with the #160 spec (`docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md`). (1) `DataSource` gains `data_notes`, which a backtest's data warnings include (its §7, decision 5); (2) a run of prices that are not whole rupiah after the reported splits are reversed is restored when the tick grid proves one factor for it, and only the days the proof cannot settle are refused (its §4 and §5).
```

**`docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md`** (changed: 2 edits)

<!-- edit: docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md -->
Replace:
```markdown
- **One fetch path.** Both backtests and `paper run` (through `day_inputs`) build their inputs in `backtest._fetch`, so the look-back is added there. The look-back's actions are fetched in a separate call from the run's own range, because `_fetch` re-raises an `UnavailableDaysError` whose days all fall outside the run (`backtest.py`, the `if not named: raise`), and a refusal in the look-back must not stop the run.
- **A refused look-back** marks the stock incomplete (`history_complete` is false) and adds one warning with the new key `data.dividends.history_refused` to the run's data warnings, naming the stock and the refused range. `dividend-growth` treats an incomplete stock as not passing. The run does not stop: the missing data is history, and the stock can still be traded on its own merits by other strategies.
```
with:
```markdown
- **One fetch path.** Both backtests and `paper run` (through `day_inputs`) build their inputs in `backtest._fetch`, so the look-back is added there. The look-back's actions are fetched in a separate call from the run's own range, because `_fetch` re-raises an `UnavailableDaysError` whose days all fall outside the run (`backtest.py`, the `if not named: raise`), and a refusal in the look-back must not stop the run.
- **Dividends on days whose prices carry an adjustment Yahoo does not report** (#160 spec §5): the look-back reads a dividend in a run the tick grid proves restored by that run's factor, where it read Yahoo's scaled amount unchanged, and a dividend in an unproven run is refused with `UnavailableDaysError` naming its ex-date, which is a refused look-back as below.
- **A refused look-back** marks the stock incomplete (`history_complete` is false) and adds one warning with the new key `data.dividends.history_refused` to the run's data warnings, naming the stock and the refused range. `dividend-growth` treats an incomplete stock as not passing. The run does not stop: the missing data is history, and the stock can still be traded on its own merits by other strategies.
```

<!-- edit: docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md -->
Replace:
```markdown
- **Pass 6 (2026-09-30):** the §4–§7 to §9 map again, then a full read. **0 findings. Loop closed.**
```
with:
```markdown
- **Pass 6 (2026-09-30):** the §4–§7 to §9 map again, then a full read. **0 findings. Loop closed.**
- **Pass 7 (2026-10-01, the #160 spec):** §4.3 was brought into line with the #160 spec (`docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md` §5): the look-back reads a dividend on a day Yahoo adjusted without saying restored when the tick grid proves the factor, and refuses it when it does not.
```

**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        the upstream inferred for today's bar, which is never stored; each note once."""
        raise NotImplementedError("CachedDataSource.data_notes")

```
with:
```python
        the upstream inferred for today's bar, which is never stored; each note once."""
        stored = (
            restoration.note
            for instrument in instruments
            for restoration in self._cache.restorations(instrument, start, end)
        )
        return tuple(dict.fromkeys((*stored, *self._upstream.data_notes(instruments, start, end))))

```

**`packages/steadyhand-idx/src/steadyhand_idx/factor.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
Replace:
```python
    prices: int
    @property
    def noise(self) -> bool:
        """Whether the factor rounds to 1.000000: a split reversal's rounding error (§4.5)."""
        raise NotImplementedError("Restoration.noise")

```
with:
```python
    prices: int

    @property
    def noise(self) -> bool:
        """Whether the factor rounds to 1.000000: a split reversal's rounding error (§4.5)."""
        return is_noise(self.factor)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/factor.py -->
Replace:
```python
        """What a backtest's warnings say about this run (spec §7)."""
        raise NotImplementedError("Restoration.note")

```
with:
```python
        """What a backtest's warnings say about this run (spec §7)."""
        span = f"{self.instrument.symbol}: Yahoo's prices from {self.first} to {self.last}"
        if self.noise:
            return Note(
                DATA_PRICES_RESTORED,
                f"{span} miss whole rupiah by a rounding error after its reported splits are "
                "reversed, so steadyhand put each one on the IDX tick grid, proven by "
                f"{self.prices:,} prices that fit it with no other factor.",
            )
        return Note(
            DATA_PRICES_RESTORED,
            f"{span} carry an adjustment Yahoo does not report, so steadyhand restored them: "
            f"every price and dividend in that span is multiplied by {self.factor}, proven by "
            f"{self.prices:,} prices that fit the IDX tick grid at that factor and at no other.",
        )

```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.restored_prices.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.restored_prices.md -->
```markdown
+++
id = "idx.restored_prices"
title = "Restored prices: an adjustment Yahoo does not report"
summary = "Why some of Yahoo's old prices are not whole rupiah, and how steadyhand puts them back."
explains = ["data.prices.restored"]
module = "how-idx-works"
position = 8
see_also = ["backtest.data_gaps", "idx.ticks"]
sources = [
    "docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md §4",
    "docs/superpowers/specs/2026-10-01-price-factor-recovery-design.md §7",
]
+++

steadyhand reads its prices from Yahoo. Yahoo **adjusts** old prices after some events, such as
a rights issue, so that a chart does not show a jump on the day of the event. It does this by
multiplying every earlier price by one number, the **factor**. For splits, Yahoo says which
splits it applied, and steadyhand undoes them. For some other events it applies a factor and
does not say so.

**How steadyhand notices.** Every real price on IDX sat on a tick: a whole number of rupiah, in
steps that depend on the price. After the reported splits are undone, a price that is not whole
rupiah cannot be what was traded. So it still carries an adjustment Yahoo did not report.

**How the tick grid proves the factor.** steadyhand tries every factor from 1 to just below 2
that puts the newest such price on a whole rupiah. It keeps only the factors that put *every*
price of the span back on that day's tick grid, within one hundredth of a rupiah. When exactly
one factor fits, and at least 20 prices (five days) agree on it, that factor is the one Yahoo
applied. steadyhand then restores each price to its tick, and each dividend in the span by the
same factor. When no factor fits, or more than one does, those days stay refused, as before.

**A rounding error.** Sometimes the factor is 1: nothing was adjusted, but undoing a reported
split left each price a tiny fraction away from a whole rupiah. steadyhand puts those prices on
the grid too, and its note says it was a rounding error.

**What you will see.** A backtest that uses restored prices warns you, naming the stock, the
span, the factor and how many prices proved it. For example, Stock A's prices over two years
might all be multiplied by 1.1. A restored figure can differ from the one Yahoo shows for that
day, because Yahoo's figure still carries the adjustment and steadyhand's does not.
```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
        history = self._history(instrument, start, end)
        return tuple(
            Restoration(instrument, run.first, run.last, run.factor, run.prices)
            for run in self._runs_for(history, start, end)
            if run.factor is not None and run.first <= end and run.last >= start
        )

```
with:
```python
        history = self._history(instrument, start, end)
        return _proven(instrument, self._runs_for(history, start, end), start, end)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
        a request, since every range a backtest reads has been read by then (#160 spec §7)."""
        raise NotImplementedError("YahooDataSource.data_notes")

```
with:
```python
        a request, since every range a backtest reads has been read by then (#160 spec §7)."""
        return tuple(
            restoration.note
            for instrument in instruments
            for restoration in _proven(
                instrument, self._runs.get(ticker_for(instrument), ()), start, end
            )
        )

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    """The proven *runs* overlapping *start* to *end*, oldest first, as restorations."""
    raise NotImplementedError("_proven")

```
with:
```python
    """The proven *runs* overlapping *start* to *end*, oldest first, as restorations."""
    return tuple(
        Restoration(instrument, run.first, run.last, run.factor, run.prices)
        for run in runs
        if run.factor is not None and run.first <= end and run.last >= start
    )

```

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
def _data_warnings(market: Market, window: _Window, start: date, end: date) -> tuple[Note, ...]:
    return (
        *market.universe.survivorship_warnings(start, end),
        *_refused_warnings(window),
```
with:
```python
def _data_warnings(market: Market, window: _Window, start: date, end: date) -> tuple[Note, ...]:
    """The universe's warnings, the source's notes on everything fetched, look-back included,
    then the refusals (#160 spec §7)."""
    since = start if window.lookback is None else window.lookback[0]
    return (
        *market.universe.survivorship_warnings(start, end),
        *market.source.data_notes(_stocks(window.members), since, end),
        *_refused_warnings(window),
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    """Every stock the universe holds on any day, in a fixed order: the stocks fetched."""
    raise NotImplementedError("_stocks")

```
with:
```python
    """Every stock the universe holds on any day, in a fixed order: the stocks fetched."""
    return sorted(frozenset().union(*members.values()), key=lambda i: (i.market, i.symbol))

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    start, end = days[0], days[-1]
    stocks = sorted(frozenset().union(*members.values()), key=lambda i: (i.market, i.symbol))
    bars: list[Bar] = []
```
with:
```python
    start, end = days[0], days[-1]
    stocks = _stocks(members)
    bars: list[Bar] = []
```

**`packages/steadyhand/src/steadyhand/data.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/data.py -->
Replace:
```python

    Both methods cover *start* to *end* inclusive, return items in date order, and raise
    ``DataUnavailableError`` rather than return partial data (fail closed).
    """
```
with:
```python

    ``bars`` and ``corporate_actions`` cover *start* to *end* inclusive, return items in date
    order, and raise ``DataUnavailableError`` rather than return partial data (fail closed).
    ``data_notes`` says what the source did to the data it has supplied (#160 spec §7).
    """
```

Generate `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json sha256=c2eed563943129d72ae783146742475df587168b521729cb9b0bf2bbc256489b -->
```bash
uv run python scripts/record_golden.py
```

Generate `tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json sha256=5705d831022a0885b3f489b4a861d56bd4cf9d7feb35e0a418387d37dc12a433 -->
```bash
uv run python scripts/record_golden.py
```

Generate `tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json sha256=e11b0f622c8518aeb694f0d68e82915f7bc1efb307f0a1eff9445f87012a00fb -->
```bash
uv run python scripts/record_golden.py
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1659 passed=1659 -->
Expected: every command exits 0; 1659 passed, 100% branch coverage; the performance step passes its ten tests, unchanged by this story. CI's second job runs the same 1659 tests on Python 3.13 under `-W error`.

- [ ] **Step 7: Mutations.** Run M403–M412 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(idx): #160 S3 a note for each restored run, data_notes on every source, and the lesson`, ending in the story's issue number as `(#N)`), as **Merging a story** says. Then comment on #160 with each story's evidence and leave it open for Shyden: its title and criteria still describe crediting a refused day's dividend, and rewriting them to the spec is his (the classifier refused that write before).

---

## Mutation checks

Each mutation plants one realistic defect in the story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed lines are printed before the run. The predicted catchers were written before any mutation ran; a prediction is the least set the mutation must reach, and "More than predicted" lists every other test that went red.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M373 | 1 | `factor.py` | Candidates start at the first whole rupiah at or above p1, not the nearest | 1625 | `test_a_noise_run_is_restored_onto_the_grid_it_almost_sits_on`, `test_upward_noise_at_the_first_price_keeps_one_as_a_candidate` (3 failing) | `test_a_proven_factor_restores_the_true_prices` |
| M374 | 1 | `factor.py` | The window stops below 2·p1, as the approved spec had it | 1625 | `test_a_proven_factor_restores_the_true_prices`, `test_downward_noise_near_a_factor_of_two_keeps_the_true_factor_a_candidate` (2 failing) | none |
| M375 | 1 | `factor.py` | Two fitting candidates prove the first | 1625 | `test_two_fitting_candidates_leave_the_run_refused` (4 failing) | `test_a_proven_factor_restores_the_true_prices`, `test_downward_noise_near_a_factor_of_two_keeps_the_true_factor_a_candidate`, `test_upward_noise_at_the_first_price_keeps_one_as_a_candidate` |
| M376 | 1 | `factor.py` | Sixteen prices prove a run | 1625 | `test_fewer_than_twenty_prices_stay_refused` (1 failing) | none |
| M377 | 1 | `factor.py` | The five-tier grid is read back to 2014 | 1625 | `test_each_grid_era_is_used_on_its_own_days` (3 failing) | `test_upward_noise_at_the_first_price_keeps_one_as_a_candidate` |
| M378 | 1 | `factor.py` | A day before 2014-01-06 reads the three-tier grid | 1625 | `test_a_day_before_the_first_grid_is_never_provable` (1 failing) | none |
| M379 | 1 | `factor.py` | The refined factor keeps every digit | 1625 | `test_a_noise_run_is_restored_onto_the_grid_it_almost_sits_on`, `test_downward_noise_at_the_first_price_keeps_one_as_a_candidate` (2 failing) | none |
| M380 | 1 | `factor.py` | A restored dividend is not quantised | 1625 | `test_restored_dividends_are_quantised_to_one_hundredth_of_a_rupiah_cent` (1 failing) | none |
| M381 | 1 | `factor.py` | Only a factor of exactly 1 is noise | 1625 | `test_a_noise_factor_is_one_that_rounds_to_one`, `test_noise_is_judged_at_six_decimal_places` (4 failing) | none |
| M382 | 1 | `factor.py` | Every older row joins the run | 1625 | `test_a_noise_run_is_restored_onto_the_grid_it_almost_sits_on`, `test_the_window_rejects_half_and_double_the_factor_although_both_fit_the_grid`, `test_two_stacked_adjustments_split_on_the_day_the_factor_changes` (4 failing) | `test_downward_noise_at_the_first_price_keeps_one_as_a_candidate` |
| M383 | 1 | `factor.py` | Every price reads the first tier's tick | 1625 | `test_a_run_crossing_tiers_is_proven_on_each_price_s_own_tier` (13 failing) | 10 more tests, including `test_a_noise_run_is_restored_onto_the_grid_it_almost_sits_on`, `test_a_row_that_no_candidate_fits_is_a_single_unprovable_day`, `test_downward_noise_at_the_first_price_keeps_one_as_a_candidate` |
| M384 | 1 | `factor.py` | A price exactly Rp0.01 off its tick does not fit | 1625 | `test_a_fit_is_within_one_rupiah_cent` (1 failing) | none |
| M385 | 1 | `factor.py` | The verified table starts a day late | 1625 | `test_the_verified_table_takes_over_on_its_own_first_day` (1 failing) | none |
| M386 | 2 | `yahoo.py` | The whole history is read on every call | 1650 | `test_the_cached_source_stores_the_upstreams_restorations_with_each_range`, `test_the_source_restores_a_ranges_prices_and_dividends_reading_the_whole_history_once` (3 failing) | `test_a_look_back_is_fetched_once_without_its_prices` |
| M387 | 2 | `yahoo.py` | The proof reads the asked range, not the whole history | 1650 | `test_the_cached_source_stores_the_upstreams_restorations_with_each_range`, `test_the_source_restores_a_ranges_prices_and_dividends_reading_the_whole_history_once` (4 failing) | `test_a_failed_whole_history_read_fails_closed`, `test_a_look_back_is_fetched_once_without_its_prices` |
| M388 | 2 | `yahoo.py` | A range of whole prices still reads the whole history | 1650 | `test_a_range_whose_prices_are_all_whole_reads_no_whole_history` (108 failing) | 91 more tests, including `test_a_blocked_order_is_shown_with_its_reason_and_the_dividends_of_the_day`, `test_a_changed_setting_is_written_in_the_audit_log_and_applies_from_the_next_day`, `test_a_changed_starting_cash_is_noted_once_and_changes_nothing` |
| M389 | 2 | `yahoo.py` | A dividend in an unproven run is read at Yahoo's amount | 1650 | `test_a_dividend_in_an_unproven_run_is_refused_naming_its_ex_date` (1 failing) | none |
| M390 | 2 | `yahoo.py` | A dividend in a proven run is not restored | 1650 | `test_bbri_s_2021_dividend_restores_to_what_bri_announced`, `test_the_source_restores_a_ranges_prices_and_dividends_reading_the_whole_history_once` (25 failing) | 23 more tests, including `test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected`, `test_a_holding_whose_old_prices_cannot_be_recovered_keeps_its_dividend_history`, `test_a_look_back_is_fetched_once_without_its_prices` |
| M391 | 2 | `yahoo.py` | A flat row with no volume counts as evidence | 1650 | `test_the_proof_reads_every_row_with_a_price_off_whole_rupiah_and_nothing_else` (6 failing) | `test_a_flat_row_with_no_volume_inside_a_proven_run_is_restored_though_it_is_no_evidence`, `test_bbri_s_golden_years_are_restored_except_where_a_volume_is_not_whole`, `test_bbri_s_whole_recording_proves_one_factor_up_to_its_rights_issue`, `test_restorations_are_the_proven_runs_overlapping_the_range`, `test_the_cached_source_stores_the_upstreams_restorations_with_each_range` |
| M392 | 2 | `yahoo.py` | An unproven run's prices are restored with no factor | 1650 | `test_a_dividend_in_an_unproven_run_is_refused_naming_its_ex_date`, `test_unrecoverable_prices_are_never_cached` (2 failing) | none |
| M393 | 2 | `yahoo.py` | A row whose volume is not whole is kept | 1650 | `test_a_row_whose_volume_is_not_whole_stays_refused_though_its_prices_count`, `test_bbri_s_golden_years_are_restored_except_where_a_volume_is_not_whole` (3 failing) | `test_a_look_back_is_fetched_once_without_its_prices` |
| M394 | 2 | `yahoo.py` | Restorations outside the range are returned | 1650 | `test_restorations_leave_out_a_proven_run_outside_the_range` (1 failing) | none |
| M395 | 2 | `yahoo.py` | A dividend on a row with no price is dropped with the row | 1650 | `test_a_dividend_on_a_row_with_no_price_is_refused` (1 failing) | none |
| M396 | 2 | `yahoo.py` | A row with no price is kept | 1650 | `test_a_dividend_on_a_row_with_no_price_is_refused`, `test_a_row_yahoo_gives_no_price_is_no_bar` (6 failing) | none |
| M397 | 2 | `cache.py` | The migration keeps the stored actions | 1650 | `test_the_restorations_migration_reads_every_range_again` (1 failing) | none |
| M398 | 2 | `cache.py` | The migration keeps the fetched ranges | 1650 | `test_the_restorations_migration_reads_every_range_again` (1 failing) | none |
| M399 | 2 | `cache.py` | The cache reads restorations inside the range only | 1650 | `test_a_restoration_round_trips_and_a_different_one_is_a_conflict`, `test_the_cached_source_stores_the_upstreams_restorations_with_each_range` (3 failing) | `test_a_look_back_is_fetched_once_without_its_prices` |
| M400 | 2 | `cache.py` | A different restoration for a stored run is accepted | 1650 | `test_a_restoration_round_trips_and_a_different_one_is_a_conflict` (1 failing) | none |
| M401 | 2 | `cache.py` | A restoration outside the stored range is accepted | 1650 | `test_a_restoration_round_trips_and_a_different_one_is_a_conflict` (1 failing) | none |
| M402 | 2 | `cache.py` | Restorations are not stored with a range's bars | 1650 | `test_the_cached_source_stores_the_upstreams_restorations_with_each_range` (1 failing) | none |
| M403 | 3 | `factor.py` | The two note texts are swapped | 1659 | `test_a_noise_restoration_s_note_says_it_is_a_rounding_error`, `test_a_restoration_s_note_names_its_span_factor_and_proof` (12 failing) | 10 more tests, including `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_markdown_file_holds_the_summary_and_the_disclaimer` |
| M404 | 3 | `factor.py` | The proof's price count loses its thousands separator | 1659 | `test_a_restoration_s_note_names_its_span_factor_and_proof`, `test_the_window_holds_the_events_it_was_chosen_for` (11 failing) | 9 more tests, including `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_markdown_file_holds_the_summary_and_the_disclaimer` |
| M405 | 3 | `backtest.py` | The notes cover the run, not its look-back | 1659 | `test_the_source_s_data_notes_reach_back_over_the_look_back` (1 failing) | none |
| M406 | 3 | `backtest.py` | The source's notes never reach the warnings | 1659 | `test_the_source_s_data_notes_cover_the_window_and_follow_the_universe_s`, `test_the_source_s_data_notes_reach_back_over_the_look_back`, `test_the_window_holds_the_events_it_was_chosen_for` (12 failing) | 9 more tests, including `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_markdown_file_holds_the_summary_and_the_disclaimer` |
| M407 | 3 | `yahoo.py` | Yahoo's notes take in runs before the range | 1659 | `test_data_notes_name_the_runs_already_read_and_never_ask_yahoo` (1 failing) | none |
| M408 | 3 | `yahoo.py` | Yahoo's notes fetch the range again | 1659 | `test_data_notes_name_the_runs_already_read_and_never_ask_yahoo` (2 failing) | `test_the_cached_source_s_notes_come_from_its_stored_restorations` |
| M409 | 3 | `cache.py` | A run stored and met today gets two notes | 1659 | `test_the_cached_source_s_notes_come_from_its_stored_restorations` (12 failing) | 11 more tests, including `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_recorder_writes_the_dividend_growth_file_byte_for_byte` |
| M410 | 3 | `cache.py` | A run met only in today's bar gets no note | 1659 | `test_a_run_read_only_in_today_s_bar_still_has_its_note` (1 failing) | none |
| M411 | 3 | `data.py` | data_notes is not part of DataSource | 1659 | `test_data_notes_is_required_of_a_data_source` (1 failing) | none |
| M412 | 3 | `idx.restored_prices.md` | The lesson does not explain the key | 1659 | `test_every_key_has_a_lesson`, `test_the_restored_prices_lesson_explains_its_note_and_prints` (16 failing) | 14 more tests, including `test_a_member_with_no_bars_gives_day_warnings_in_the_file`, `test_a_paper_traders_journey`, `test_dividend_growth_reads_its_look_back_and_ends_as_the_library_run` |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M373',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    start = max(int(first.to_integral_value(ROUND_HALF_UP)), 1)\n',
  '    start = max(int(first) + (first != int(first)), 1)\n'),
 ('M374',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    while whole < 2 * (first + FIT_TOLERANCE):\n',
  '    while whole < 2 * first:\n'),
 ('M375',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    if len(passing) != 1 or count < MIN_PRICES:\n',
  '    if not passing or count < MIN_PRICES:\n'),
 ('M376',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    if len(passing) != 1 or count < MIN_PRICES:\n',
  '    if len(passing) != 1 or count < MIN_PRICES - 4:\n'),
 ('M377',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '        if day >= FIVE_TIERS_FROM:\n',
  '        if day >= GRID_START:\n'),
 ('M378',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '        if day >= GRID_START:\n',
  '        if True:\n'),
 ('M379',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    return _SIGNIFICANT.plus(total / count)\n',
  '    return total / count\n'),
 ('M380',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    return (recorded * factor).quantize(DIVIDEND_QUANTUM, ROUND_HALF_EVEN)\n',
  '    return recorded * factor\n'),
 ('M381',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    return factor.quantize(NOISE_QUANTUM) == 1\n',
  '    return factor == 1\n'),
 ('M382',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '            still = [f for f in passing if all(tiles.fits(p, f, row.day) for p in '
  'row.prices)]\n',
  '            still = passing\n'),
 ('M383',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '        tick = next((tier.tick for tier in reversed(tiers) if tier.from_price <= value), 1)\n',
  '        tick = next((tier.tick for tier in tiers if tier.from_price <= value), 1)\n'),
 ('M384',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '    return nearest is not None and abs(value - nearest) <= FIT_TOLERANCE\n',
  '    return nearest is not None and abs(value - nearest) < FIT_TOLERANCE\n'),
 ('M385',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '        if day >= self._verified.first:\n',
  '        if day > self._verified.first:\n'),
 ('M386',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '        if ticker not in self._runs:\n',
  '        if True:\n'),
 ('M387',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '            whole = self._request(ticker, GRID_START, self._today())\n',
  '            whole = self._request(ticker, start, end)\n'),
 ('M388',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '        ):\n            return ()\n',
  '        ):\n            pass\n'),
 ('M389',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '            if run is not None and run.factor is None:\n',
  '            if False:\n'),
 ('M390',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '                amount = restore_dividend(amount, run.factor)\n',
  '                pass\n'),
 ('M391',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '        if not _placeholder(row) and not _all_whole(prices):\n',
  '        if not _all_whole(prices):\n'),
 ('M392',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '    if run is None or run.factor is None:\n        return None\n',
  '    if run is None:\n        return None\n'),
 ('M393',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '        if amounts is None or volume is None:\n',
  '        if amounts is None:\n'),
 ('M394',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '            if run.factor is not None and run.first <= end and run.last >= start\n',
  '            if run.factor is not None\n'),
 ('M395',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '        return True\n    if float(record["Dividends"]) != 0:\n',
  '        return True\n    if False:\n'),
 ('M396',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '    if not any(math.isnan(float(record[column])) for column in (*PRICE_COLUMNS, "Volume")):\n',
  '    if True:\n'),
 ('M397',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '    DELETE FROM actions;\n',
  ''),
 ('M398',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '    DELETE FROM fetched;\n',
  ''),
 ('M399',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  'WHERE symbol = ? AND first <= ? AND last >= ? ORDER BY first',
  'WHERE symbol = ? AND first >= ? AND last <= ? ORDER BY first'),
 ('M400',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '            elif tuple(found) != values:\n',
  '            elif False:\n'),
 ('M401',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '            if run.instrument != instrument or run.first > end or run.last < start:\n',
  '            if run.instrument != instrument:\n'),
 ('M402',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '                restored = self._upstream.restorations(instrument, first, last)\n'
  '                self._cache.store(instrument',
  '                restored = ()\n                self._cache.store(instrument'),
 ('M403',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '        if self.noise:\n',
  '        if not self.noise:\n'),
 ('M404',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/factor.py',
  '            f"{self.prices:,} prices that fit the IDX tick grid at that factor and at no '
  'other.",\n',
  '            f"{self.prices} prices that fit the IDX tick grid at that factor and at no '
  'other.",\n'),
 ('M405',
  3,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    since = start if window.lookback is None else window.lookback[0]\n',
  '    since = start\n'),
 ('M406',
  3,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '        *market.source.data_notes(_stocks(window.members), since, end),\n',
  ''),
 ('M407',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '                instrument, self._runs.get(ticker_for(instrument), ()), start, end\n',
  '                instrument, self._runs.get(ticker_for(instrument), ()), GRID_START, end\n'),
 ('M408',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '                instrument, self._runs.get(ticker_for(instrument), ()), start, end\n',
  '                instrument,\n'
  '                self._runs_for(self._history(instrument, start, end), start, end),\n'
  '                start,\n'
  '                end,\n'),
 ('M409',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '        return tuple(dict.fromkeys((*stored, *self._upstream.data_notes(instruments, start, '
  'end))))\n',
  '        return (*stored, *self._upstream.data_notes(instruments, start, end))\n'),
 ('M410',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '        return tuple(dict.fromkeys((*stored, *self._upstream.data_notes(instruments, start, '
  'end))))\n',
  '        return tuple(stored)\n'),
 ('M411',
  3,
  'packages/steadyhand/src/steadyhand/data.py',
  '    def data_notes(\n'
  '        self, instruments: Sequence[Instrument], start: date, end: date\n'
  '    ) -> Sequence[Note]:\n'
  '        """Notes on the data supplied for *instruments* from *start* to *end*, for a '
  "backtest's\n"
  '        warnings: a source that changed nothing it supplied returns none."""\n'
  '        ...\n',
  ''),
 ('M412',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.restored_prices.md',
  'explains = ["data.prices.restored"]\n',
  'explains = []\n')]
```

## Carried forward

- **#161:** paper reports carry no data warning of any kind, this one included (#160 decision 6).
- **#162:** a row whose split-reversed volume is not whole shares stays refused inside a proven run; BBRI's 153 such days before 2017-11-10 and BRPT's are its subject (#160 decision 7).
- **A true factor of 2 or more** stays refused, or in a one-tier span is read as f/2 (#160 §11). The largest measured factor is 1.6028.
- **CTRA before mid-2016** (scope decision 19): its noise run is refused because the data cannot tell f = 1 from f = 2, so its four dividends there are unknown and dividend-growth fails CTRA's look-back for runs starting before 2023. A source that settles CTRA's 2014–2016 prices would lift it.
- **All twenty-one scope decisions fill in or amend the #160 spec.** The spec keeps its approved text; this plan is the record of each choice.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

**Before pass 1, while building the code (2026-10-01 and 2026-10-02).** Every story was built and gated first in a scratch chain on `develop` `136765f` plus Task 0's fixture commit `f2dcaaf` (the final chain: S1 `6e04a09`, S2 `fc092ab`, S3 `1493a52`; each rebuild is named below), its red phase run against stubs, and its mutations run with predictions written first. That found these things a reading of the spec would not have:

1. **S1's red phase failed at collection.** `tests/idx/test_factor.py` built `GRID = Grid.shipped()` at import, and the stub raises there, so pytest collected nothing. Each test now calls a `grid()` helper. The chain was rebuilt (S2 and S3 replayed, their changed lines compared identical), and the plan tools now run an import-time check before every red phase.
2. **`Run.noise` had no caller in the package** once S3 reads `Restoration.noise`. It is gone from S1, and the chain was rebuilt the same way.
3. **Task 2 AC 6 said BBRI "is bought on the first day".** The golden run orders it on 2021-02-01 and it fills at the next open. The criterion now says so and names the dividend: Rp445,075 (4,500 × 98.9057 = 445,075.65, credited whole).
4. **Two red-phase expectations were written from memory.** RED3 named `Restoration.note` as the stub the note tests stop in; the run's JUnit report shows `Restoration.noise`, read first. RED2 said 26 other failures where 137 − 101 = 36. Every red and gate expectation in this plan is now copied from the final run's output (S1 gained a test and S2 seven since, so the counts moved again).
5. **The proof's upper edge was unsafe.** The gate's property test (CI profile) found a true factor of 1.9999201 with −Rp0.001 of noise on Rp50 and Rp82 (2015) that left f = 1 as the only candidate below 2·p1: "proven", and the prices restored at half. Candidates now run up to 2·(p1 + `FIT_TOLERANCE`) (scope decision 19; Shyden chose "close the edge", 2026-10-02). A rounded bound was tried first and admitted f = 2.5 at p1 = 0.4. Control: 20,000 examples pass on the fix (177 s), and the same run on the old window finds its own counterexample (1.9999345, −0.001). Across all 62 stocks only CTRA's 2014-01-06 to 2016-07-12 noise run (603 days, 4 dividends) changes, to refused.
6. **Yahoo's unfinished day crashed the whole-history read.** Every one of the 62 stocks had a NaN close on 2026-10-01, and `_whole` compares a NaN `Decimal`, which raises. The defect was already on `develop` for any range that includes today; S2 made every restoring read reach it. `history_from_frames` now drops a priceless row and refuses one that carries a dividend (scope decision 20; six tests, red first).
7. **Mutation M394 caught nothing.** The overlap filter in S2's `restorations` was never exercised: the only test asked for a range with no unwhole price, which reads no runs. A new S2 test with two stacked runs was predicted green on the code and red with the filter removed, and both were seen.
8. **M383's named catcher could not see what it claimed.** The crossing-tiers test's true prices were multiples of 1 as well as of their tier, so a tick-1 grid passed it. It now pins 1,995, 2,005 and 2,010 at the Rp10 boundary. Three mispredicted catcher sets (M379, M382, M392) were corrected to the run's, each with its reason: an unrounded 1.100019000 equals 1.100019, M382 never reaches the no-fit test, and M392's named test passes no runs.
9. **The performance docstrings named the wrong machine.** S2's perf test and M6's both said "four cores"; `sysctl hw.physicalcpu` reads 6. Both now say six, S2's with the numbers measured for this plan (0.024 to 0.028 s at a load of 12). S2 was amended and S3 replayed on it (S2 `49438a4`, S3 `c5ff133`); the change is three docstring lines, so the red phases and mutations, run on the commits before it, stand, and the gate was run again on the new chain.
10. **A stopped mutation run had lost the end of its log.** The run hit the two-hour background limit after M399, and the buffered tail of its output, M399's third catcher, never reached the file. A check that every block lists as many tests as it says failed found it; M399 was run again alone. The plan tools now write their logs line by line, and the gate and the mutations run as separate jobs.

**Pass 1 (2026-10-02).** Mechanical: `check_plan.py` replayed the plan from its own text (`replay.out`): every task's red and gate counts OK, the three golden files' SHA-256 OK in Tasks 2 and 3, and every story's tree IDENTICAL to its verified commit (S1 `bc6f9e4`, S2 `49438a4`, S3 `c5ff133`, the chain before pass 2); 0 problems. `prose_check.py`: all 63 cited tests exist. `interface_check.py`: every name each task produces is defined in its story's tree. Two new checks, each with a negative control: `cite_check.py` (every line citing a mutation and a test: the mutation's catchers include the test) and `files_check.py` (each task's **Files** block names exactly what its story commit changes). Then the whole plan was read. Four findings, all fixed:
1. **Three Review Focus items and the S3 red phase cited mutation numbers from before decision 20.** Its two mutations (M395, M396) moved every later number up by two, and Review Focus 4, 5 and 6 and the S3 red-phase text kept the old ones, each naming a mutation its test does not catch. They now cite M397–M398, M409–M410, M407–M408 and M411. `cite_check.py` found all seven, and it runs on every pass from now on.
2. **Task 2's Files block left out `tests/perf/test_performance.py`**, whose docstring the story corrects (finding 9). Added; found by `files_check.py`.
3. **`prose_check.py` checked M6's mutation ranges**, typed into the copy and never updated, so it reported five mismatches against a correct plan. It now works out each story's range from `mutations.py` and exits non-zero on a problem (control: a plan with one range misspelled fails).
4. **`interface_check.py` read a module, a file path and a lesson id as names** and reported `py`, `yahoo` and `restored_prices` missing. It now checks each as what it is: the module's file, the path and the lesson file exist in the story's tree (control: three misspelled ones are each reported).

**Pass 2 (2026-10-02).** Mechanical (`pass_checks.sh`): code blocks and replay markers identical to those replayed in pass 1, `prose_check.py`, `interface_check.py`, `cite_check.py` and `files_check.py` 0 problems; every `pragma: no cover` and `noqa` in the plan is one `develop` already has; no "robot trading". Then the plan was read, and with it every comment and docstring line the three stories add (`comments_of.py` over the chain's diff), since a comment is a claim no test checks. Two findings, both fixed:
1. **A golden-test comment repeated the wording build finding 3 corrected**: "so it is bought on the first day". The fix had reached Task 2's criterion and not the comment beside the figures. It now says BBRI is ordered on the first day and bought at the next open.
2. **Three test comments cited "plan review pass 1"**, which this log files as build findings. They now cite scope decisions 19 and 20, and the stacked-runs test's docstring cites nothing.
The chain was rebuilt (S1 `6f683f6`, S2 `b0f2470`, S3 `f4fe668`): six comment lines, so the red phases and mutations stand; the gate and the replay were run again on it: every story green at 100% branch coverage (1625, 1650, 1659), and the replay of the rendered plan OK at every red and gate count, every golden SHA-256 OK, every tree IDENTICAL to its new commit, 0 problems.

**Pass 3 (2026-10-02).** Mechanical (`pass_checks.sh`): code blocks and replay markers identical to those replayed after pass 2; every check 0 problems. Then the whole plan and every added comment and docstring were read. Two findings, both fixed:
1. **Review Focus 2 said no dividend falls in an unproven run**, which scope decision 19 makes false for CTRA's four dividends of 2014 to 2016. It now names them.
2. **"Days with a price off whole rupiah" counted the evidence.** BBRI's 1,845 (the perf test's docstring and **Measured performance**) and its 1,103 (a `test_yahoo.py` comment) leave out flat rows with no volume; with them the counts are 1,914 and 1,160 (69 and 57 flat days), read from the code. The label came from the spec's table, so scope decision 21 records what the spec's counts are, and both texts now say "evidence".
The chain was rebuilt (S1 `6f683f6`, S2 `41c33ce`, S3 `543ed59`): two test texts, so the red phases and mutations stand; the gate and the replay were run again: every story green at 100% branch coverage (1625, 1650, 1659), and the replay OK at every red and gate count, every golden SHA-256 OK, every tree IDENTICAL to its new commit, 0 problems.

**Pass 4 (2026-10-02).** Mechanical (`pass_checks.sh`): every check 0 problems. Then the whole plan and every added comment and docstring were read. One finding, fixed:
1. **Task 3's last step closed #160**, whose title and criteria still describe crediting a refused day's dividend ("Credit a dividend whose ex-date falls on a day the source refused prices for", read 2026-10-02). Rewriting them to the spec is Shyden's, so the step now posts the evidence and leaves the issue open for him.

**Pass 5 (2026-10-02).** Mechanical (`pass_checks.sh`): every check 0 problems. Then the whole plan and every added comment were read, and each number in a comment was recomputed. One finding, fixed:
1. **A test comment gave the noisy first price as p1 = 24.999998**; the test's own `recorded` gives 24.9999988 (read by running it), so the stated figure was wrong at its own precision. S1 was amended and S2 and S3 replayed on it with `amend_chain.py`, a new tool that checks every step (S1 `6e04a09`, S2 `fc092ab`, S3 `1493a52`); the gate and the replay were run again: every story green at 100% branch coverage (1625, 1650, 1659), and the replay OK at every red and gate count, every golden SHA-256 OK, every tree IDENTICAL to its new commit, 0 problems.

**Pass 6 (2026-10-02).** Mechanical (`pass_checks.sh`): every check 0 problems. Then the whole plan was read, and the measured figures with no recorded source were measured again: CTRA's run (603 days, refused, 127 calendar trading days in 2016, dividends on 2014-07-04, 2015-07-08, 2015-09-30 and 2016-06-23; `ctra_probe.py` on the cached history), decision 9's scan (`paper_scan.py`: on the golden settings 12 orders queued and no day report with a `limit.*`, `fill.*` or skip key; its control, the tests' 0.19 limit, finds 2 `limit.weight.cut` and 147 `limit.weight.full`) and decision 1's 16 call sites (`unadjust(` on the base commit). All agree. One finding, fixed:
1. **The review log's opening named the chain from after pass 2**, two rebuilds out of date. It now reads the final chain from `stories.txt` when the plan is rendered (a `CHAIN` field `build_plan.py` fills), so a rebuild cannot leave it stale.

**Pass 7 (2026-10-02).** The gate and the replay of pass 5's chain: every story green at 100% branch coverage, the replay OK at every count and SHA-256 and every tree IDENTICAL, 0 problems. Mechanical (`pass_checks.sh`): every check 0 problems once the render ran. Then the whole plan was read, and Task 0's fixture SHA-256 was recomputed from its commit (it agrees). One finding, fixed:
1. **The render failed and the checks passed anyway.** Pass 6's entry in this log spelled out the new `CHAIN` field with its brackets, so the renderer met it twice and stopped; `pass_checks.sh`, run next, checked the previous render and reported 0 problems. The entry no longer spells the field, and `pass_checks.sh` now renders first and stops if the render fails.

**Pass 8 (2026-10-02).** Mechanical (`pass_checks.sh`, rendering first): every check 0 problems; code blocks and replay markers identical to those replayed after pass 5, so that replay stands; the prose before this log identical to what pass 7 read, and the added comments unchanged since pass 5. Then this log was read in full. **No findings: the plan is approved.**
