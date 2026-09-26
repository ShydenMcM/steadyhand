# M4a Income Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `steadyhand` an income report, `income_report(reports, final, history, rules, settings) -> IncomeReport`: what a run received by month and over the trailing year, what its holdings pay at their run-rate and in which months, their measured dividend growth, a three-scenario projection to an income goal, and the goal tracker; and have the backtester attach one to each run when a goal is set, with the strategy's income impact against the baseline.

**Architecture:** A new pure module, `income.py`, reads what the engine already emits (the day reports and the last state) plus each holding's dividend history, which the caller fetches. Each figure has its own public function, built and hand-tested one story at a time (`received_income`, `run_rate`, `payment_calendar`, `dividend_growth`, `project`, `goal_progress`), and `income_report` assembles them. `notes.py` gives every sentence a report says a stable key for the training sub-project, guarded by an AST meta-test. The backtester fetches five years of history for each final holding and attaches the reports after both runs. The golden run gains its income report on five-year recordings of the same stocks.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. The engine gains no dependency.

**Spec:** `docs/superpowers/specs/2026-09-26-m4-income-design.md` (the "M4 spec"), stories S1–S4 of its §10, on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec"). Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how each claim was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2). No task adds a dependency.
- `float` never appears in the engine; `tests/meta/test_no_float.py` scans every engine module on disk, `income.py` and `notes.py` included.
- Money is integer minor units (`Money`). Income rounds down and tax rounds up. Every ratio is a `Decimal` worked out at 50 significant digits and rounded half-even to `RATIO_PLACES` (eight places); a power uses `Decimal.ln` and `Decimal.exp` (M4 §3.2, §5.2).
- Values verbatim from the specs: the pay lag defaults to **14** trading days; the year window is **365** days ending on the report's day, both ends included (M4 §3.2); growth compares windows **4** years apart and the history reaches back **5** years; the projection runs at most **600** months ("not within 50 years"); pessimistic starts from **80%** of the run-rate gross and grows at `min(0%, measured)`, base at `min(measured, 5%)`, optimistic at `min(measured, 10%)` (M4 §5.3); every projection carries `"Projection, not a promise"`; a note key matches `^[a-z]+(\.[a-z_]+)+$` (M4 §7).
- Take-home is gross less the **full** dividend tax, `rules.dividend_tax(gross, reinvested_by_deadline=False, on=…)`, whatever the engine booked (M4 decision 2). M4b removes the flag (M4 §4, S5).
- Every `*Error` a task raises is raised by a test that asserts its message (core §10.2). Every `pytest.raises` has a `match=` written as a raw string.
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A function that already existed keeps its old body in the red phase, so a test of changed behaviour fails on its own assertion. A test that passes against the stubs is listed with its reason in its task.
- No test computes a shared value from new code at module level; shared values come from `functools.cache` helpers or plain functions called inside each test.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code. A function takes at most five arguments (ruff `PLR0913`; scope decision 1).
- Test file basenames are unique across `tests/`.
- English only. The phrase "robot trading" never appears (core §1.3).
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **A split on the same ex-date as a dividend.** The engine pays that dividend on the shares held before the split (`corporate.apply_actions` entitles from the previous close), so its amount is on the old basis. Expected: the run-rate restates it, or it would disagree with what the engine pays. Pinned in Task 2 (`test_only_a_split_from_the_ex_date_to_the_run_rate_day_restates_a_dividend`), scope decision 4.
2. **A split whose ratio has no decimal form (1-for-3).** Expected: Rp100 a share on 3,000 shares after the split is exactly Rp100,000, not Rp99,999 from a rounded third. Pinned in Task 2 (`test_a_split_no_decimal_can_hold_is_still_restated_exactly`), scope decision 5.
3. **A dividend so small its tax takes all of it** (Rp1, taxed at 10% rounded up). Expected: a calendar with nothing to share has no evenness and counts twelve empty months, rather than dividing by zero. Pinned in Task 2 (`test_a_calendar_with_nothing_to_share_has_no_evenness`), scope decision 8.
4. **A run shorter than a year that ends soon after the rules' first day** (2021-01-01), holding a stock that paid in December 2020. Expected: the report stops with the rules' `UnsupportedDateError` rather than guessing that dividend's pay month. Pinned in Task 4 (`test_a_year_window_before_the_rules_first_day_is_refused_not_guessed`).
5. **A goal already met, and a portfolio that is all idle cash.** Expected: 0.0 years for the first; `CANNOT` for the second, even when the goal would count as met, because the projection starts from the holdings' value. Pinned in Task 3 (`test_a_goal_already_met_takes_no_time`, `test_nothing_to_project_from_cannot_be_projected`) and Task 4 (`test_the_projection_starts_from_the_holdings_not_the_idle_cash`).

## Scope decisions (read before starting)

1. **`income_report(reports, final, history, rules, settings)`.** M4 §3.2 lists seven arguments; the project's lint allows five and carries no suppression, so the goal, the contribution and the pay lag travel together as `IncomeSettings(goal, monthly_contribution=None, pay_lag_trading_days=14)`, as M3b grouped `Market`. The backtester builds it from `BacktestSettings.goal` and the engine's settings, so the contribution and the lag still have one source each.
2. **Each figure is its own public function**, `received_income`, `run_rate`, `payment_calendar`, `dividend_growth`, `project` and `goal_progress`, so that each story's figures are hand-tested where they are built. `income_report` only assembles them. `RunRate` carries its `as_of`, which keeps `project` and `payment_calendar` within five arguments.
3. **The year window has one definition**, `metrics.year_window_start(end)`, used by `measure` and by every income window. M4 §3.2 defines the window as "the window `metrics.measure` uses"; sharing the function makes that true by construction.
4. **A split on the dividend's own ex-date restates it** (Review Focus 1). M4 §3.3 says "after the dividend's"; the engine pays a same-day dividend on the pre-split shares, so the amount is on the old basis, and the run-rate must agree with the engine. This amends §3.3 to "on or after".
5. **Restatement is exact in integers.** M4 §3.3 asks for "exact `Decimal` arithmetic", which a 1-for-3 split cannot give: a third has no decimal form. A dividend's run-rate amount is `per_share.as_integer_ratio()` times the shares times the old counts, floor-divided by the new counts, rounded once. Growth, which is only a rounded ratio, restates a share's amount in the 50-digit context.
6. **`notes.py` and its meta-test land in S3, not S1** (M4 §10 lists them under S1). S3 builds the first notes; in S1 a key constant would be dead code and a meta-test with no `Note(...)` call to find would pass vacuously.
7. **Every key is a constant in `notes.py`, named after its value** (`INCOME_GROWTH_SHORT_HISTORY = "income.growth.short_history"`). The meta-test checks the shape and the naming, that no key string appears anywhere else in the engine, that every `Note(...)` names its key by a constant, and that every key is used.
8. **Evenness is `None` whenever the calendar's total is zero**, not only when the run-rate is (M4 §5.1): a Rp1 dividend is a run-rate whose tax leaves nothing to take home (Review Focus 3).
9. **A run-rate dividend is an `Entitlement`**: the dividend as the shares held now would be entitled to it, paid on its modelled pay date. It is the engine's own type, so a test compares the two directly.
10. **The portfolio's monthly take-home is worked out from its own annual gross**, not summed from the holdings' rounded monthly figures, so it can be a rupiah or two more than their sum.
11. **The projection checks the monthly take-home rounded down**, `(I − tax(I)) ÷ 12`, against the target, at month 0 and after each month's steps; years are `m ÷ 12` rounded up to one decimal place, and `None` unless `REACHED`. `Projection.label` is a property returning `PROJECTION_LABEL`.
12. **`project` refuses a goal in another currency** up front, as do `IncomeSettings` for its contribution, `income_report` against the portfolio, and `BacktestSettings` against the capital: otherwise the mismatch would surface as a `CurrencyMismatchError` deep in a comparison.
13. **The backtester fetches history from `years_before(as_of, HISTORY_YEARS)`**, with `HISTORY_YEARS = 5`, for each final holding of each run, through `market.source.corporate_actions`. A source that cannot give it stops the backtest (M4 §8).
14. **The golden fixtures become five-year recordings** (M4 §9, §11). The year-long recordings reached back only to 2021-02-01, and growth needs 2017-02-01. The five stocks were recorded again on 2026-09-27 from 2017-01-31 to 2022-01-31; every row the old files hold is identical in the new ones (Task 0 checks it), so the golden figures cannot move, and Task 4 checks they did not. The recordings travel in Task 0's PR; Task 4 moves `record_golden.py` onto them and deletes the year-long files.
15. **The truncation check runs without a goal.** An income report reads no bar after its day, and a run cut in April 2021 would need history from 2016, before the recordings start.
16. **The performance test's synthetic dividend moves to the first weekday from 15 June.** It was paid only when 15 June fell on a weekday; 15 June 2025 is a Sunday, so the last year paid nothing, the run-rate was zero, and the projection returned `CANNOT` at once, timing nothing.
17. **The projection's properties run 100 examples**, like `test_engine.py`'s, not the profile's 500: each example simulates up to three times 600 months.

## File map

| File | Task | Responsibility |
|---|---|---|
| `tests/fixtures/yahoo/{ASII,BBCA,BBRI,TLKM,UNVR}.JK_2017-01-31_2022-01-31.json` | 0 | The five-year recordings for the golden run's income report |
| `packages/steadyhand/src/steadyhand/income.py` | 1–4 | Received income, run-rate, calendar, growth, projection, goal tracker, `income_report` |
| `.../steadyhand/metrics.py` | 1 | `year_window_start`, shared by `measure` and `income.py` |
| `.../steadyhand/market.py`, `corporate.py` | 2 | `add_trading_days`, moved out of `corporate.py` |
| `.../steadyhand/notes.py` | 3 | `Note` and the key constants |
| `.../steadyhand/backtest.py` | 4 | `BacktestSettings.goal`, `RunResult.income`, `IncomeImpact`, the history fetch |
| `scripts/record_golden.py`, `tests/fixtures/golden/…json` | 4 | The golden run's goal, its income summary, the five-year recordings |
| `tests/perf/test_performance.py` | 4 | A goal in the ten-year run |
| `.../steadyhand/__init__.py` | 1–4 | The public API |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | The M4 spec, the M4a plan, the stories and the five-year recordings (docs and data) | `m4/spec` |
| 1 | S1 Received income: by month, the trailing year, take-home and yields | `m4/s1-received-income` |
| 2 | S2 Run-rate and payment calendar, with split restatement | `m4/s2-run-rate` |
| 3 | S3 Notes, measured dividend growth and the projection | `m4/s3-projection` |
| 4 | S4 The income report, the goal tracker and the backtester's income | `m4/s4-income-report` |

Stories merge in order: each one's code builds on the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Then ask Shyden to approve the merge with `AskUserQuestion`, naming the PR, the head SHA **as read from the file in that same turn** (`cut -c1-7 "${TMPDIR}/head-sha"`), and the CI state. Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: The M4 spec, the M4a plan, the stories and the five-year recordings

Documentation and data only, on `m4/spec`, whose PR carries the M4 spec, this plan, `HANDOVER.md` and the five recordings (#86).

- [ ] **Step 1: Commit the recordings.** The five files were recorded on 2026-09-27 with `uv run python scripts/record_yahoo_fixture.py <SYMBOL> 2017-01-31 2022-01-31` (yfinance 1.7.0), and are committed to `tests/fixtures/yahoo/` exactly as recorded. Each must have this SHA-256:
  - `ASII.JK_2017-01-31_2022-01-31.json`: `800964c34a7dbbb27e48c6a826a44bce7e259cf4f47906cfafb6bce72bd5e71e`
  - `BBCA.JK_2017-01-31_2022-01-31.json`: `88c03cfbe81f0b056d1b1cb88807e49ff3ccac86606ef728daa6b7bf6b0df501`
  - `BBRI.JK_2017-01-31_2022-01-31.json`: `2176bc31ccf244f840ad95689bd99cd5cc1076ff055db3bdb45d1659566d0ff8`
  - `TLKM.JK_2017-01-31_2022-01-31.json`: `7b823b9c58fa417d90cc940a675312db8c05a163219bb3bc12f8c214f30ca81b`
  - `UNVR.JK_2017-01-31_2022-01-31.json`: `c924d4017f9807a53ec8456e5929d4c033d5e0580910919a6e4990147dcc6700`

  A later recording can differ, because Yahoo's answers can change. It is then a new fixture, reviewed like code, and Task 4's golden SHA-256 must be regenerated with it.
- [ ] **Step 2: Check them against the year-long recordings.** Every row the year-long files hold must be in the new files unchanged, with no extra day in that year and the same split history, or the golden figures could move:

  ```bash
  uv run python - <<'EOF'
  import json
  from pathlib import Path
  folder = Path("tests/fixtures/yahoo")
  for stock in ("ASII", "BBCA", "BBRI", "TLKM", "UNVR"):
      old = json.loads((folder / f"{stock}.JK_2021-02-01_2022-01-31.json").read_text())
      new = json.loads((folder / f"{stock}.JK_2017-01-31_2022-01-31.json").read_text())
      rows = {row["day"]: row for row in new["rows"]}
      days = {row["day"] for row in old["rows"]}
      differ = [row["day"] for row in old["rows"] if rows.get(row["day"]) != row]
      extra = [day for day in rows if "2021-02-01" <= day <= "2022-01-31" and day not in days]
      print(stock, len(new["rows"]), len(differ), len(extra), old["splits"] == new["splits"])
  EOF
  ```

  Expected: `ASII 1261 0 0 True`, `BBCA 1262 0 0 True`, `BBRI 1262 0 0 True`, `TLKM 1261 0 0 True`, `UNVR 1262 0 0 True`. Then `uv run pytest -m live -k 2017-01-31 tests/idx/test_yahoo_live.py` passes 5.
- [ ] **Step 3: File the stories.** Create one issue per task 1–4, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 4: Open the PR** from `m4/spec` into `develop` (`Refs #86`), and merge it as **Merging a story** says. #86 stays In Progress until the M4b plan is merged too.

---

### Task 1: S1 Received income: by month, the trailing year, take-home and yields

**Acceptance criteria (story text):**
1. A new module, `income.py`, has `received_income(reports, final, rules) -> ReceivedIncome`, as of the last report's day (M4 §4).
2. `by_month` holds one `MonthlyIncome(month, figures)` for every calendar month from the first day's to the last day's, months with nothing paid included; `month` is the month's first day. `IncomeFigures` holds gross paid, tax booked (`DayReport.tax`), net booked and take-home.
3. Take-home is, for each entitlement paid, its gross less `rules.dividend_tax(gross, reinvested_by_deadline=False, on=<pay day>)`: the full tax, whatever the engine booked (decision 2).
4. `trailing` covers the year window ending on the last day, and `monthly_average` divides each of its four figures by 12, rounding each down on its own. The window's first day is `metrics.year_window_start(end)`, which `measure` now uses too (scope decision 3).
5. `current_yield` is the trailing gross over the last day's value and `yield_on_cost` over the final positions' cost; each is `None` when its divisor is zero, and rounded half-even to eight places.
6. A run with no days raises `ValueError`. A property: take-home is never more than gross, nor below zero.
7. The engine exports the new names. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M67–M73 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/income.py`
- Modify: `.../steadyhand/metrics.py`, `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_income_received.py`; modify `tests/engine/test_metrics.py`

**Interfaces:**
- Consumes: M3's `DayReport` (`day`, `paid`, `tax`, `value`), `EngineState.holdings.portfolio` (`currency`, `positions[*].cost_basis`), `MarketRules.dividend_tax`, `metrics.RATIO_PLACES`, `metrics.YEAR_DAYS`.
- Produces: `year_window_start(end: date) -> date` (in `metrics`); `IncomeFigures(gross, tax, net, take_home: Money)` with `zero(currency)` and `+`; `MonthlyIncome(month: date, figures: IncomeFigures)`; `ReceivedIncome(as_of: date, by_month: tuple[MonthlyIncome, ...], trailing: IncomeFigures, monthly_average: IncomeFigures, current_yield: Decimal | None, yield_on_cost: Decimal | None)`; `received_income(reports: Sequence[DayReport], final: EngineState, rules: MarketRules) -> ReceivedIncome`.

- [ ] **Step 1: Branch.** `git switch -c m4/s1-received-income origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_income_received.py`** (new)

<!-- file: tests/engine/test_income_received.py -->
```python
"""received_income: dividends by month and over the trailing year, take-home and yields (M4 §4).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.income import IncomeFigures, MonthlyIncome, received_income
from steadyhand.money import IDR, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

BBCA = Instrument("BBCA", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
BOUGHT = date(2024, 1, 2)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def paid(day: date, gross: int, stock: Instrument = BBCA) -> Entitlement:
    return Entitlement(stock, day - timedelta(days=20), day, rp(gross))


def report(
    day: date, *, paid: Sequence[Entitlement] = (), tax: int = 0, value: int = 1_000_000
) -> DayReport:
    return DayReport(
        day=day,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=tuple(paid),
        tax=rp(tax),
        daily_cost=rp(0),
        deposit=rp(0),
        frozen=(),
        halt=None,
        settled=rp(value),
        unsettled=rp(0),
        holdings_value=rp(0),
        value=rp(value),
        unit_price=Decimal(1),
        warnings=(),
    )


def final(**cost: int) -> EngineState:
    """The last state: 100 shares of each named stock, bought for the given total cost."""
    book = Portfolio.empty(IDR)
    for symbol, total in cost.items():
        order = Order(Instrument(symbol, "IDX", IDR), Side.BUY, 100, BOUGHT)
        fill = Fill(order, BOUGHT, 100, rp(total // 100), Costs.zero(IDR))
        book = book.deposit(rp(total), BOUGHT).apply_fill(fill, BOUGHT)
    return EngineState(Holdings(book))


def figures(gross: int, tax: int, net: int, take_home: int) -> IncomeFigures:
    return IncomeFigures(rp(gross), rp(tax), rp(net), rp(take_home))


def test_each_month_sums_what_was_paid_and_booked_and_empty_months_are_kept() -> None:
    run = [
        report(
            date(2025, 1, 30),
            paid=[paid(date(2025, 1, 30), 1_000), paid(date(2025, 1, 30), 555, TLKM)],
            tax=156,
        ),
        report(date(2025, 3, 3)),
        report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 2_000)], tax=200),
    ]
    income = received_income(run, final(), rules())
    assert income.as_of == date(2025, 3, 10)
    assert income.by_month == (
        # Take-home: 1,000 - 100 = 900, and 555 - 56 (55.5 rounded up) = 499.
        MonthlyIncome(date(2025, 1, 1), figures(1_555, 156, 1_399, 1_399)),
        MonthlyIncome(date(2025, 2, 1), figures(0, 0, 0, 0)),
        MonthlyIncome(date(2025, 3, 1), figures(2_000, 200, 1_800, 1_800)),
    )


def test_take_home_is_after_the_full_tax_whatever_was_booked() -> None:
    # Decision 2: nothing was booked (as if exempt), but living off it means paying the 10%.
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], tax=0)]
    income = received_income(run, final(), rules())
    assert income.by_month[0].figures == figures(1_000, 0, 1_000, 900)
    assert income.trailing == figures(1_000, 0, 1_000, 900)


def test_the_trailing_year_is_the_365_days_ending_on_the_last_day() -> None:
    # The window ending on Monday 7 July 2025 starts on Monday 8 July 2024.
    run = [
        report(date(2024, 7, 5), paid=[paid(date(2024, 7, 5), 5_000)], tax=500),
        report(date(2024, 7, 8), paid=[paid(date(2024, 7, 8), 1_200)], tax=120),
        report(date(2025, 7, 7), paid=[paid(date(2025, 7, 7), 2_400)], tax=240),
    ]
    income = received_income(run, final(), rules())
    assert income.trailing == figures(3_600, 360, 3_240, 3_240)
    # Each figure / 12: 3,600 -> 300, 360 -> 30, 3,240 -> 270.
    assert income.monthly_average == figures(300, 30, 270, 270)
    # By month is not trimmed: July 2024 keeps both of its payments, and there are 13 months.
    assert len(income.by_month) == 13
    assert income.by_month[0] == MonthlyIncome(date(2024, 7, 1), figures(6_200, 620, 5_580, 5_580))


def test_each_monthly_average_is_rounded_down_on_its_own() -> None:
    # Paid 12 with 2 booked, take-home 12 - 2 (1.2 rounded up) = 10. Each / 12 rounds down:
    # gross 1, tax 0, net 10 -> 0 and take-home 0, so net is not gross - tax here.
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 12)], tax=2)]
    income = received_income(run, final(), rules())
    assert income.trailing == figures(12, 2, 10, 10)
    assert income.monthly_average == figures(1, 0, 0, 0)


def test_the_current_yield_and_the_yield_on_cost() -> None:
    run = [
        report(date(2025, 3, 3), value=10),
        report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], tax=100, value=40_000),
    ]
    income = received_income(run, final(BBCA=15_000, TLKM=10_000), rules())
    # 1,000 / 40,000 on the last day's value; 1,000 / (15,000 + 10,000) on cost.
    assert income.current_yield == Decimal("0.02500000")
    assert income.yield_on_cost == Decimal("0.04000000")


def test_a_yield_is_rounded_half_even_to_eight_places() -> None:
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], value=3_000)]
    income = received_income(run, final(BBCA=6_000), rules())
    # 1,000 / 3,000 = 0.333333333...; 1,000 / 6,000 = 0.1666666666... rounds up to ...67.
    assert income.current_yield == Decimal("0.33333333")
    assert income.yield_on_cost == Decimal("0.16666667")


def test_a_yield_is_none_when_its_divisor_is_zero() -> None:
    run = [report(date(2025, 3, 10), paid=[paid(date(2025, 3, 10), 1_000)], value=0)]
    income = received_income(run, final(), rules())
    assert income.current_yield is None
    assert income.yield_on_cost is None


def test_months_run_across_a_year_end() -> None:
    run = [report(date(2024, 12, 30)), report(date(2025, 2, 3))]
    income = received_income(run, final(), rules())
    months = [month.month for month in income.by_month]
    assert months == [date(2024, 12, 1), date(2025, 1, 1), date(2025, 2, 1)]


def test_a_run_with_no_days_has_no_income_report() -> None:
    with pytest.raises(ValueError, match=r"^a run with no days has no income report$"):
        received_income([], final(), rules())


@given(st.lists(st.integers(min_value=1, max_value=10**12), min_size=1, max_size=5))
def test_take_home_is_never_more_than_gross(amounts: list[int]) -> None:
    day = date(2025, 3, 10)
    run = [report(day, paid=[paid(day, amount) for amount in amounts])]
    trailing = received_income(run, final(), rules()).trailing
    assert Money.zero(IDR) <= trailing.take_home <= trailing.gross
```

**`tests/engine/test_metrics.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_metrics.py -->
Replace:
```python
from steadyhand.engine import DayReport, EngineState
from steadyhand.metrics import RATIO_PLACES, CostBreakdown, DividendTotals, Drawdown, measure
from steadyhand.money import IDR, Money
```
with:
```python
from steadyhand.engine import DayReport, EngineState
from steadyhand.metrics import (
    RATIO_PLACES,
    CostBreakdown,
    DividendTotals,
    Drawdown,
    measure,
    year_window_start,
)
from steadyhand.money import IDR, Money
```

<!-- edit: tests/engine/test_metrics.py -->
Replace:
```python

def test_a_run_with_no_days_has_no_metrics() -> None:
```
with:
```python

def test_the_year_window_is_365_days_with_both_ends_included() -> None:
    assert year_window_start(date(2022, 1, 10)) == date(2021, 1, 11)
    # Across 29 February 2024, 365 days ending on 31 December start on 2 January.
    assert year_window_start(date(2024, 12, 31)) == date(2024, 1, 2)


def test_a_run_with_no_days_has_no_metrics() -> None:
```


- [ ] **Step 3: Write the stubs.** New names only; everything that existed keeps its current body.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.market import MarketRules, UnsupportedDateError
```
with:
```python
)
from steadyhand.income import IncomeFigures, MonthlyIncome, ReceivedIncome, received_income
from steadyhand.market import MarketRules, UnsupportedDateError
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    measure,
)
```
with:
```python
    measure,
    year_window_start,
)
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Holdings",
    "Instrument",
```
with:
```python
    "Holdings",
    "IncomeFigures",
    "Instrument",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Money",
    "MovementKind",
```
with:
```python
    "Money",
    "MonthlyIncome",
    "MovementKind",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "PriceHistory",
    "Rejected",
```
with:
```python
    "PriceHistory",
    "ReceivedIncome",
    "Rejected",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "measure",
    "run_day",
]
```
with:
```python
    "measure",
    "received_income",
    "run_day",
    "year_window_start",
]
```

**`packages/steadyhand/src/steadyhand/income.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/income.py -->
```python
"""Dividend income: what a run received, what its holdings pay now, and where that leads (M4 spec).

Every function here is pure. The caller passes the run's day reports, its last state and, where a
figure needs it, each holding's dividend history; nothing here reads a file or the network.
Money stays integer minor units, income rounds down and tax rounds up. Every ratio is a
``Decimal`` worked out at 50 significant digits and rounded half-even to ``RATIO_PLACES``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, Money

_MONTHS = 12
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class IncomeFigures:
    """Dividends over a period (M4 spec §4).

    ``gross`` is what was paid, ``tax`` what the engine booked, and ``net`` what that left.
    ``take_home`` is what the full dividend tax leaves, whatever the engine booked (decision 2):
    the figure an investor living off dividends keeps. In a monthly average each of the four is
    divided and rounded down on its own, so ``net`` there can be a minor unit off
    ``gross - tax``.
    """

    gross: Money
    tax: Money
    net: Money
    take_home: Money

    @classmethod
    def zero(cls, currency: Currency) -> IncomeFigures:
        raise NotImplementedError("IncomeFigures.zero")

    def __add__(self, other: IncomeFigures) -> IncomeFigures:
        raise NotImplementedError("IncomeFigures.__add__")


@dataclass(frozen=True, slots=True)
class MonthlyIncome:
    """One calendar month's dividends. ``month`` is the month's first day."""

    month: date
    figures: IncomeFigures


@dataclass(frozen=True, slots=True)
class ReceivedIncome:
    """The dividends a run received, as of its last day (M4 spec §4).

    ``by_month`` holds every calendar month from the first day's to the last day's, including
    months with nothing paid. ``trailing`` covers the year window ending on ``as_of``, and
    ``monthly_average`` is each trailing figure divided by 12, rounded down. ``current_yield``
    divides the trailing gross by the last day's value, and ``yield_on_cost`` by what the final
    positions cost; each is ``None`` when its divisor is zero.
    """

    as_of: date
    by_month: tuple[MonthlyIncome, ...]
    trailing: IncomeFigures
    monthly_average: IncomeFigures
    current_yield: Decimal | None
    yield_on_cost: Decimal | None


def received_income(
    reports: Sequence[DayReport], final: EngineState, rules: MarketRules
) -> ReceivedIncome:
    """The income received by a run whose day reports, in order, are *reports*."""
    raise NotImplementedError("received_income")


def _day_figures(report: DayReport, rules: MarketRules, currency: Currency) -> IncomeFigures:
    raise NotImplementedError("_day_figures")


def _take_home(gross: Money, rules: MarketRules, on: date) -> Money:
    """What the full dividend tax on *on* leaves of *gross* (decision 2)."""
    raise NotImplementedError("_take_home")


def _per_month(amount: Money) -> Money:
    """A year's *amount* as a monthly figure, rounded down."""
    raise NotImplementedError("_per_month")


def _ratio(numerator: Money, denominator: Money) -> Decimal | None:
    raise NotImplementedError("_ratio")


def _months(first: date, last: date) -> Iterator[date]:
    """The first day of every calendar month from *first*'s to *last*'s."""
    raise NotImplementedError("_months")
```

**`packages/steadyhand/src/steadyhand/metrics.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/metrics.py -->
Replace:
```python

def _rounded(value: Decimal) -> Decimal:
```
with:
```python

def year_window_start(end: date) -> date:
    """The first day of the year window ending on *end*: ``YEAR_DAYS`` days, both ends included."""
    raise NotImplementedError("year_window_start")


def _rounded(value: Decimal) -> Decimal:
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=757 failed=11 -->
Expected: 757 run, 11 failed, every one `NotImplementedError`: the ten tests of `test_income_received.py` and `test_the_year_window_is_365_days_with_both_ends_included`. `measure` keeps its own window until Step 5, so every other test passes.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/income.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/income.py -->
```python
"""Dividend income: what a run received, what its holdings pay now, and where that leads (M4 spec).

Every function here is pure. The caller passes the run's day reports, its last state and, where a
figure needs it, each holding's dividend history; nothing here reads a file or the network.
Money stays integer minor units, income rounds down and tax rounds up. Every ratio is a
``Decimal`` worked out at 50 significant digits and rounded half-even to ``RATIO_PLACES``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, Money

_MONTHS = 12
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class IncomeFigures:
    """Dividends over a period (M4 spec §4).

    ``gross`` is what was paid, ``tax`` what the engine booked, and ``net`` what that left.
    ``take_home`` is what the full dividend tax leaves, whatever the engine booked (decision 2):
    the figure an investor living off dividends keeps. In a monthly average each of the four is
    divided and rounded down on its own, so ``net`` there can be a minor unit off
    ``gross - tax``.
    """

    gross: Money
    tax: Money
    net: Money
    take_home: Money

    @classmethod
    def zero(cls, currency: Currency) -> IncomeFigures:
        nothing = Money.zero(currency)
        return cls(nothing, nothing, nothing, nothing)

    def __add__(self, other: IncomeFigures) -> IncomeFigures:
        return IncomeFigures(
            self.gross + other.gross,
            self.tax + other.tax,
            self.net + other.net,
            self.take_home + other.take_home,
        )


@dataclass(frozen=True, slots=True)
class MonthlyIncome:
    """One calendar month's dividends. ``month`` is the month's first day."""

    month: date
    figures: IncomeFigures


@dataclass(frozen=True, slots=True)
class ReceivedIncome:
    """The dividends a run received, as of its last day (M4 spec §4).

    ``by_month`` holds every calendar month from the first day's to the last day's, including
    months with nothing paid. ``trailing`` covers the year window ending on ``as_of``, and
    ``monthly_average`` is each trailing figure divided by 12, rounded down. ``current_yield``
    divides the trailing gross by the last day's value, and ``yield_on_cost`` by what the final
    positions cost; each is ``None`` when its divisor is zero.
    """

    as_of: date
    by_month: tuple[MonthlyIncome, ...]
    trailing: IncomeFigures
    monthly_average: IncomeFigures
    current_yield: Decimal | None
    yield_on_cost: Decimal | None


def received_income(
    reports: Sequence[DayReport], final: EngineState, rules: MarketRules
) -> ReceivedIncome:
    """The income received by a run whose day reports, in order, are *reports*."""
    if not reports:
        msg = "a run with no days has no income report"
        raise ValueError(msg)
    as_of = reports[-1].day
    since = year_window_start(as_of)
    currency = final.holdings.portfolio.currency
    months: dict[date, IncomeFigures] = {}
    trailing = IncomeFigures.zero(currency)
    for report in reports:
        figures = _day_figures(report, rules, currency)
        month = report.day.replace(day=1)
        months[month] = months.get(month, IncomeFigures.zero(currency)) + figures
        if report.day >= since:
            trailing += figures
    by_month = tuple(
        MonthlyIncome(month, months.get(month, IncomeFigures.zero(currency)))
        for month in _months(reports[0].day, as_of)
    )
    average = IncomeFigures(
        _per_month(trailing.gross),
        _per_month(trailing.tax),
        _per_month(trailing.net),
        _per_month(trailing.take_home),
    )
    cost = sum(
        (position.cost_basis for position in final.holdings.portfolio.positions),
        Money.zero(currency),
    )
    return ReceivedIncome(
        as_of,
        by_month,
        trailing,
        average,
        _ratio(trailing.gross, reports[-1].value),
        _ratio(trailing.gross, cost),
    )


def _day_figures(report: DayReport, rules: MarketRules, currency: Currency) -> IncomeFigures:
    nothing = Money.zero(currency)
    gross = sum((entitlement.gross for entitlement in report.paid), nothing)
    take_home = sum(
        (_take_home(entitlement.gross, rules, report.day) for entitlement in report.paid), nothing
    )
    return IncomeFigures(gross, report.tax, gross - report.tax, take_home)


def _take_home(gross: Money, rules: MarketRules, on: date) -> Money:
    """What the full dividend tax on *on* leaves of *gross* (decision 2)."""
    return gross - rules.dividend_tax(gross, reinvested_by_deadline=False, on=on)


def _per_month(amount: Money) -> Money:
    """A year's *amount* as a monthly figure, rounded down."""
    return Money(amount.amount // _MONTHS, amount.currency)


def _ratio(numerator: Money, denominator: Money) -> Decimal | None:
    if denominator.amount == 0:
        return None
    quotient = _CONTEXT.divide(numerator.amount, denominator.amount)
    return quotient.quantize(RATIO_PLACES, context=_CONTEXT)


def _months(first: date, last: date) -> Iterator[date]:
    """The first day of every calendar month from *first*'s to *last*'s."""
    month = first.replace(day=1)
    while month <= last:
        yield month
        month = date(month.year + month.month // _MONTHS, month.month % _MONTHS + 1, 1)
```

**`packages/steadyhand/src/steadyhand/metrics.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/metrics.py -->
Replace:
```python
    )
    since = last - timedelta(days=YEAR_DAYS - 1)
    trailing = [report for report in reports if report.day >= since]
```
with:
```python
    )
    since = year_window_start(last)
    trailing = [report for report in reports if report.day >= since]
```

<!-- edit: packages/steadyhand/src/steadyhand/metrics.py -->
Replace:
```python
    """The first day of the year window ending on *end*: ``YEAR_DAYS`` days, both ends included."""
    raise NotImplementedError("year_window_start")

```
with:
```python
    """The first day of the year window ending on *end*: ``YEAR_DAYS`` days, both ends included."""
    return end - timedelta(days=YEAR_DAYS - 1)

```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=757 passed=757 -->
Expected: every command exits 0; 757 passed, 100% branch coverage; the performance test passes.

- [ ] **Step 7: Mutations.** Run M67–M73 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S1 received income by month and over the trailing year`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 2: S2 Run-rate and payment calendar, with split restatement

**Acceptance criteria (story text):**
1. `add_trading_days(rules, day, count)` moves from `corporate.py` (where it was private) to `market.py`, public, so the engine's pay date and the calendar's pay month come from one function. `count` is an `int` of at least 0; closed days are skipped; a day the rules do not cover raises their `UnsupportedDateError`.
2. `run_rate(portfolio, history, rules, as_of, pay_lag_trading_days) -> RunRate`: for each holding, every `CashDividend` in its history with an ex-date in the year window ending on `as_of`, restated onto today's share basis by every split from the dividend's ex-date (inclusive; scope decision 4) to `as_of`, times the shares held now, rounded down once and exactly (scope decision 5). A dividend that rounds to nothing is left out; each other is an `Entitlement` paid on `add_trading_days(rules, ex_date, pay_lag_trading_days)`.
3. Each holding and the portfolio have an annual gross and a monthly take-home, `(annual gross − the full tax on as_of) ÷ 12` rounded down; the portfolio's from its own annual gross (scope decision 10).
4. A held stock missing from the history, or a history holding another stock's action, raises `ValueError`; so does a pay lag below 1.
5. `payment_calendar(rate, rules) -> PaymentCalendar`: each run-rate dividend's take-home (its amount less the full tax on `as_of`) in the month of its pay date, January first, per holding and in total; `empty_months`; and `evenness`, the largest month over the total, `None` when the total is zero (scope decision 8).
6. Properties: with no later split, the run-rate prices a dividend exactly as `apply_actions` credits it, pay date included; restating across two splits equals restating across their combined ratio.
7. The engine exports the new names. Every gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M74–M82 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand/market.py`, `.../steadyhand/corporate.py`, `.../steadyhand/income.py`, `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_add_trading_days.py`, `tests/engine/test_income_run_rate.py`

**Interfaces:**
- Consumes: Task 1's `income.py` (`_take_home`, `_per_month`, `_ratio`), `metrics.year_window_start`; M3's `Entitlement`, `Portfolio.positions`, `CashDividend`, `Split`, `CorporateAction`.
- Produces: `add_trading_days(rules: MarketRules, day: date, count: int) -> date` (in `market`); `HoldingRunRate(instrument, shares: int, dividends: tuple[Entitlement, ...], annual_gross: Money, monthly_take_home: Money)`; `RunRate(as_of: date, holdings: tuple[HoldingRunRate, ...], annual_gross: Money, monthly_take_home: Money)`; `run_rate(portfolio: Portfolio, history: Mapping[Instrument, Sequence[CorporateAction]], rules: MarketRules, as_of: date, pay_lag_trading_days: int) -> RunRate`; `HoldingCalendar(instrument, months: tuple[Money, ...])`; `PaymentCalendar(months: tuple[Money, ...], holdings: tuple[HoldingCalendar, ...], empty_months: int, evenness: Decimal | None)`; `payment_calendar(rate: RunRate, rules: MarketRules) -> PaymentCalendar`; private `_history_of` and `_split_ratio`, which Task 3 uses.

- [ ] **Step 1: Branch.** `git switch -c m4/s2-run-rate origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_add_trading_days.py`** (new)

<!-- file: tests/engine/test_add_trading_days.py -->
```python
"""add_trading_days: the one function behind the engine's pay date and the calendar's pay month."""

from datetime import date
from functools import cache

import pytest

from steadyhand.market import UnsupportedDateError, add_trading_days
from steadyhand_idx import IdxMarketRules


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def test_it_skips_weekends_and_holidays_across_a_year_end() -> None:
    # From Friday 27 December 2024: Monday 30th is one; 31 December and 1 January are closed,
    # so Thursday 2 January is two and Friday 3 January is three.
    assert add_trading_days(rules(), date(2024, 12, 27), 3) == date(2025, 1, 3)


def test_it_skips_a_long_closure() -> None:
    # Idul Fitri 2025 closed the market from Friday 28 March to Monday 7 April.
    assert add_trading_days(rules(), date(2025, 3, 27), 1) == date(2025, 4, 8)


def test_it_may_start_on_a_day_the_market_is_closed() -> None:
    assert add_trading_days(rules(), date(2025, 1, 4), 1) == date(2025, 1, 6)


def test_zero_days_is_the_day_itself() -> None:
    assert add_trading_days(rules(), date(2025, 1, 4), 0) == date(2025, 1, 4)


def test_the_count_is_a_whole_number_of_days_not_below_zero() -> None:
    with pytest.raises(ValueError, match=r"^count must be at least 0, got -1$"):
        add_trading_days(rules(), date(2025, 1, 6), -1)
    with pytest.raises(TypeError, match=r"^count must be an int, got bool$"):
        add_trading_days(rules(), date(2025, 1, 6), True)


def test_a_day_past_the_holiday_data_is_refused_not_guessed() -> None:
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2028"):
        add_trading_days(rules(), date(2027, 12, 30), 3)
```

**`tests/engine/test_income_run_rate.py`** (new)

<!-- file: tests/engine/test_income_run_rate.py -->
```python
"""run_rate and payment_calendar: what the holdings pay now, and in which months (M4 §3.3, §5.1).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah. The run-rate is taken on Monday 7 July 2025, whose
year window starts on Monday 8 July 2024, with a pay lag of three trading days unless a test says
otherwise.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.income import (
    HoldingCalendar,
    HoldingRunRate,
    RunRate,
    payment_calendar,
    run_rate,
)
from steadyhand.money import IDR, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import (
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    Order,
    OtherAction,
    Side,
    Split,
)
from steadyhand_idx import IdxMarketRules

ASII = Instrument("ASII", "IDX", IDR)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
UNVR = Instrument("UNVR", "IDX", IDR)
AS_OF = date(2025, 7, 7)
BOUGHT = date(2024, 1, 2)
LAG = 3


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(**shares: int) -> Portfolio:
    """A portfolio holding the given shares, bought at Rp1 each before any dividend here."""
    book = Portfolio.empty(IDR)
    for symbol, quantity in shares.items():
        order = Order(Instrument(symbol, "IDX", IDR), Side.BUY, quantity, BOUGHT)
        fill = Fill(order, BOUGHT, quantity, rp(1), Costs.zero(IDR))
        book = book.deposit(rp(quantity), BOUGHT).apply_fill(fill, BOUGHT)
    return book


def dividend(stock: Instrument, ex_date: date, per_share: str) -> CashDividend:
    return CashDividend(stock, ex_date, Decimal(per_share))


def rate_of(
    portfolio: Portfolio, history: dict[Instrument, Sequence[CorporateAction]], lag: int = LAG
) -> RunRate:
    return run_rate(portfolio, history, rules(), AS_OF, lag)


def months(**amounts: int) -> tuple[Money, ...]:
    """Twelve monthly amounts, January first, from keyword arguments such as ``jan=900``."""
    names = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    return tuple(rp(amounts.get(name, 0)) for name in names)


def test_the_run_rate_restates_each_trailing_dividend_and_rounds_it_down() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [
            dividend(BBCA, date(2024, 7, 8), "12.5"),
            Split(BBCA, date(2025, 1, 6), 1, 5),
            OtherAction(BBCA, date(2025, 2, 3), "rights issue"),
            dividend(BBCA, date(2025, 4, 21), "55.5"),
        ],
        TLKM: [],
    }
    rate = rate_of(holding(BBCA=1_501, TLKM=100), history)
    # 12.5 a share before the 1-for-5 split is 2.5 now: 2.5 x 1,501 = 3,752.5, down to 3,752.
    # 55.5 x 1,501 = 83,305.5, down to 83,305. Paid three trading days after each ex-date.
    bbca = HoldingRunRate(
        BBCA,
        1_501,
        (
            Entitlement(BBCA, date(2024, 7, 8), date(2024, 7, 11), rp(3_752)),
            Entitlement(BBCA, date(2025, 4, 21), date(2025, 4, 24), rp(83_305)),
        ),
        # 3,752 + 83,305 = 87,057; tax 8,705.7 up to 8,706; (87,057 - 8,706) / 12 = 6,529.25.
        rp(87_057),
        rp(6_529),
    )
    assert rate == RunRate(
        AS_OF, (bbca, HoldingRunRate(TLKM, 100, (), rp(0), rp(0))), rp(87_057), rp(6_529)
    )


def test_the_year_window_holds_both_of_its_ends_and_nothing_outside_them() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [
            dividend(BBCA, date(2024, 7, 7), "1"),
            dividend(BBCA, date(2024, 7, 8), "2"),
            dividend(BBCA, AS_OF, "3"),
            dividend(BBCA, date(2025, 7, 8), "4"),
        ]
    }
    rate = rate_of(holding(BBCA=100), history)
    assert [entitled.ex_date for entitled in rate.holdings[0].dividends] == [
        date(2024, 7, 8),
        AS_OF,
    ]
    assert rate.annual_gross == rp(500)


def test_only_a_split_from_the_ex_date_to_the_run_rate_day_restates_a_dividend() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        # Before the dividend: it is already on today's basis.
        ASII: [Split(ASII, date(2024, 8, 1), 1, 2), dividend(ASII, date(2024, 9, 2), "10")],
        # After the run-rate's day: the shares held now are still on the old basis.
        BBRI: [dividend(BBRI, date(2025, 4, 21), "10"), Split(BBRI, date(2025, 7, 8), 1, 2)],
        # On the dividend's own ex-date: the engine pays it on the shares held before the split.
        UNVR: [dividend(UNVR, date(2025, 4, 21), "10"), Split(UNVR, date(2025, 4, 21), 1, 2)],
    }
    rate = rate_of(holding(ASII=100, BBRI=100, UNVR=100), history)
    assert [held.annual_gross for held in rate.holdings] == [rp(1_000), rp(1_000), rp(500)]


def test_a_split_no_decimal_can_hold_is_still_restated_exactly() -> None:
    # 100 a share before a 1-for-3 split, on 3,000 shares now: exactly 100,000. A Decimal third
    # (33.333...) times 3,000 would round down to 99,999.
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, date(2024, 9, 2), "100"), Split(BBCA, date(2025, 1, 6), 1, 3)]
    }
    assert rate_of(holding(BBCA=3_000), history).annual_gross == rp(100_000)


def test_the_portfolio_monthly_take_home_is_worked_out_from_its_own_annual_gross() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, date(2025, 4, 21), "0.65")],
        TLKM: [dividend(TLKM, date(2025, 4, 21), "0.65")],
    }
    rate = rate_of(holding(BBCA=100, TLKM=100), history)
    # Each holding: 65 - 7 (6.5 up) = 58, / 12 = 4. The portfolio: 130 - 13 = 117, / 12 = 9.
    assert [held.monthly_take_home for held in rate.holdings] == [rp(4), rp(4)]
    assert rate.monthly_take_home == rp(9)


def test_the_pay_date_is_the_engines_for_the_same_lag() -> None:
    # 14 trading days after Monday 21 April 2025, skipping 1, 12 and 13 May: Wednesday 14 May.
    ex = date(2025, 4, 21)
    history: dict[Instrument, Sequence[CorporateAction]] = {BBCA: [dividend(BBCA, ex, "10")]}
    rate = rate_of(holding(BBCA=100), history, PAY_LAG_TRADING_DAYS)
    engine = apply_actions(Holdings(holding(BBCA=100)), history[BBCA], ex, rules())
    assert rate.holdings[0].dividends[0].pay_date == date(2025, 5, 14)
    assert engine.entitled[0].pay_date == date(2025, 5, 14)


def test_a_held_stock_missing_from_the_history_is_an_error() -> None:
    with pytest.raises(
        ValueError,
        match=r"^TLKM: no dividend history was passed for a stock the portfolio holds$",
    ):
        rate_of(holding(BBCA=100, TLKM=100), {BBCA: []})


def test_a_history_holding_another_stocks_action_is_an_error() -> None:
    wrong: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(TLKM, date(2025, 4, 21), "10")]
    }
    with pytest.raises(ValueError, match=r"^BBCA: its history holds an action for TLKM$"):
        rate_of(holding(BBCA=100), wrong)


def test_the_pay_lag_is_at_least_one_trading_day() -> None:
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        rate_of(holding(BBCA=100), {BBCA: []}, 0)


prices = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal(10_000),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
ratios = st.tuples(st.integers(1, 10), st.integers(1, 10)).filter(lambda pair: pair[0] != pair[1])


@given(prices, st.integers(min_value=1, max_value=10**7))
def test_without_a_later_split_a_dividend_is_priced_as_the_engine_credits_it(
    per_share: Decimal, shares: int
) -> None:
    ex = date(2025, 4, 21)
    paid = CashDividend(BBCA, ex, per_share)
    engine = apply_actions(Holdings(holding(BBCA=shares)), [paid], ex, rules())
    rate = run_rate(holding(BBCA=shares), {BBCA: [paid]}, rules(), ex, PAY_LAG_TRADING_DAYS)
    assert rate.holdings[0].dividends == engine.entitled


@given(prices, st.integers(min_value=1, max_value=10**6), ratios, ratios)
def test_restating_across_two_splits_equals_restating_across_their_combined_ratio(
    per_share: Decimal, shares: int, first: tuple[int, int], second: tuple[int, int]
) -> None:
    combined = (first[0] * second[0], first[1] * second[1])
    assume(combined[0] != combined[1])
    paid = CashDividend(BBCA, date(2024, 9, 2), per_share)
    two: list[CorporateAction] = [
        paid,
        Split(BBCA, date(2024, 10, 1), *first),
        Split(BBCA, date(2025, 1, 6), *second),
    ]
    one: list[CorporateAction] = [paid, Split(BBCA, date(2024, 10, 1), *combined)]
    assert rate_of(holding(BBCA=shares), {BBCA: two}) == rate_of(holding(BBCA=shares), {BBCA: one})


def test_the_calendar_puts_each_dividend_in_its_pay_month_as_take_home() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        # Friday 27 December 2024: three trading days on is Friday 3 January 2025.
        # Thursday 27 March 2025: the market reopened after Idul Fitri on 8 April, so 10 April.
        BBCA: [dividend(BBCA, date(2024, 12, 27), "10"), dividend(BBCA, date(2025, 3, 27), "5")],
        TLKM: [dividend(TLKM, date(2025, 4, 21), "3")],
    }
    rate = rate_of(holding(BBCA=100, TLKM=200), history)
    assert [paid.pay_date for paid in rate.holdings[0].dividends] == [
        date(2025, 1, 3),
        date(2025, 4, 10),
    ]
    calendar = payment_calendar(rate, rules())
    # BBCA 1,000 - 100 in January and 500 - 50 in April; TLKM 600 - 60 in April.
    assert calendar.holdings == (
        HoldingCalendar(BBCA, months(jan=900, apr=450)),
        HoldingCalendar(TLKM, months(apr=540)),
    )
    assert calendar.months == months(jan=900, apr=990)
    assert calendar.empty_months == 10
    # 990 / (900 + 990) = 0.5238095238...
    assert calendar.evenness == Decimal("0.52380952")


def test_a_calendar_paying_the_same_every_month_scores_one_twelfth() -> None:
    ex_dates = [
        date(2024, 7, 15),
        date(2024, 8, 12),
        date(2024, 9, 9),
        date(2024, 10, 14),
        date(2024, 11, 11),
        date(2024, 12, 9),
        date(2025, 1, 13),
        date(2025, 2, 10),
        date(2025, 3, 10),
        date(2025, 4, 14),
        date(2025, 5, 19),
        date(2025, 6, 16),
    ]
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, ex, "10") for ex in ex_dates]
    }
    calendar = payment_calendar(rate_of(holding(BBCA=100), history), rules())
    assert calendar.months == (rp(900),) * 12
    assert calendar.empty_months == 0
    assert calendar.evenness == Decimal("0.08333333")


def test_a_calendar_paying_in_one_month_scores_one() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [dividend(BBCA, date(2025, 4, 21), "10")]
    }
    calendar = payment_calendar(rate_of(holding(BBCA=100), history), rules())
    assert calendar.empty_months == 11
    assert calendar.evenness == Decimal("1.00000000")


def test_a_calendar_with_nothing_to_share_has_no_evenness() -> None:
    silent = payment_calendar(rate_of(holding(TLKM=100), {TLKM: []}), rules())
    assert silent.months == months()
    assert silent.empty_months == 12
    assert silent.evenness is None
    # A Rp1 dividend is a run-rate, but its tax (0.1 up to 1) leaves nothing to take home.
    tiny = rate_of(holding(BBCA=1), {BBCA: [dividend(BBCA, date(2025, 4, 21), "1")]})
    assert tiny.annual_gross == rp(1)
    calendar = payment_calendar(tiny, rules())
    assert calendar.empty_months == 12
    assert calendar.evenness is None
```


- [ ] **Step 3: Write the stubs.** New names only; everything that existed keeps its current body. `corporate.py` adds no name, so it keeps its private helper until Step 5.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.income import IncomeFigures, MonthlyIncome, ReceivedIncome, received_income
from steadyhand.market import MarketRules, UnsupportedDateError
from steadyhand.metrics import (
```
with:
```python
)
from steadyhand.income import (
    HoldingCalendar,
    HoldingRunRate,
    IncomeFigures,
    MonthlyIncome,
    PaymentCalendar,
    ReceivedIncome,
    RunRate,
    payment_calendar,
    received_income,
    run_rate,
)
from steadyhand.market import MarketRules, UnsupportedDateError, add_trading_days
from steadyhand.metrics import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Halt",
    "Holdings",
```
with:
```python
    "Halt",
    "HoldingCalendar",
    "HoldingRunRate",
    "Holdings",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "OtherAction",
    "Portfolio",
```
with:
```python
    "OtherAction",
    "PaymentCalendar",
    "Portfolio",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Rounding",
    "RunResult",
```
with:
```python
    "Rounding",
    "RunRate",
    "RunResult",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "__version__",
    "apply_actions",
    "backtest",
    "measure",
    "received_income",
    "run_day",
    "year_window_start",
```
with:
```python
    "__version__",
    "add_trading_days",
    "apply_actions",
    "backtest",
    "measure",
    "payment_calendar",
    "received_income",
    "run_day",
    "run_rate",
    "year_window_start",
```

**`packages/steadyhand/src/steadyhand/income.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
```
with:
```python

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, Money

```
with:
```python

from steadyhand._validate import require_int
from steadyhand.corporate import Entitlement
from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules, add_trading_days
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Split

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

def _day_figures(report: DayReport, rules: MarketRules, currency: Currency) -> IncomeFigures:
```
with:
```python

@dataclass(frozen=True, slots=True)
class HoldingRunRate:
    """What one holding would pay in a year at its trailing dividends (M4 spec §5.1).

    ``dividends`` are the holding's cash dividends with an ex-date in the year window ending on
    the run-rate's day, each restated onto today's share basis (§3.3), multiplied by the shares
    held now and rounded down, and paid on its modelled pay date. A dividend that rounds to
    nothing is left out, as the engine leaves out a zero entitlement.
    """

    instrument: Instrument
    shares: int
    dividends: tuple[Entitlement, ...]
    annual_gross: Money
    monthly_take_home: Money


@dataclass(frozen=True, slots=True)
class RunRate:
    """What the final portfolio would pay in a year at its holdings' trailing dividends.

    A monthly take-home is the annual gross less the full dividend tax on ``as_of``, divided by
    12 and rounded down. The portfolio's is worked out from its own annual gross, so it can be a
    minor unit or two more than the holdings' monthly figures added up.
    """

    as_of: date
    holdings: tuple[HoldingRunRate, ...]
    annual_gross: Money
    monthly_take_home: Money


@dataclass(frozen=True, slots=True)
class HoldingCalendar:
    """One holding's expected take-home by month of the year, January first."""

    instrument: Instrument
    months: tuple[Money, ...]


@dataclass(frozen=True, slots=True)
class PaymentCalendar:
    """Expected take-home by month of the year, January first, from the run-rate (M4 §5.1).

    Each dividend counts in the month of its modelled pay date, less the full tax on the
    run-rate's day. ``empty_months`` counts the months with nothing, and ``evenness`` is the
    largest month's share of the year: 1/12 when every month is equal, 1 when one month has it
    all, and ``None`` when there is nothing to share.
    """

    months: tuple[Money, ...]
    holdings: tuple[HoldingCalendar, ...]
    empty_months: int
    evenness: Decimal | None


def run_rate(
    portfolio: Portfolio,
    history: Mapping[Instrument, Sequence[CorporateAction]],
    rules: MarketRules,
    as_of: date,
    pay_lag_trading_days: int,
) -> RunRate:
    """The run-rate of *portfolio*'s holdings on *as_of* (M4 spec §5.1).

    *history* holds each held stock's corporate actions; a stock the portfolio holds and
    *history* lacks is an error, never read as a stock that pays nothing.
    """
    raise NotImplementedError("run_rate")


def payment_calendar(rate: RunRate, rules: MarketRules) -> PaymentCalendar:
    """Where in the year *rate*'s dividends would arrive, as take-home (M4 spec §5.1)."""
    raise NotImplementedError("payment_calendar")


def _history_of(
    stock: Instrument, history: Mapping[Instrument, Sequence[CorporateAction]]
) -> Sequence[CorporateAction]:
    raise NotImplementedError("_history_of")


def _split_ratio(ex_date: date, actions: Sequence[CorporateAction], as_of: date) -> tuple[int, int]:
    """The (old, new) share counts of every split from *ex_date* to *as_of*, multiplied together.

    A split on the dividend's own ex-date counts: the engine pays that dividend on the shares
    held before the split (``corporate.apply_actions``), so it is on the old basis.
    """
    raise NotImplementedError("_split_ratio")


def _restated_gross(
    dividend: CashDividend, shares: int, actions: Sequence[CorporateAction], as_of: date
) -> Money:
    """*dividend* on *shares* of today's basis, rounded down once (M4 spec §3.3).

    Worked in integers from the exact ratio of ``per_share``, so a 1-for-3 split, whose ratio
    no ``Decimal`` can hold, still gives the exact amount before the one rounding.
    """
    raise NotImplementedError("_restated_gross")


def _day_figures(report: DayReport, rules: MarketRules, currency: Currency) -> IncomeFigures:
```

**`packages/steadyhand/src/steadyhand/market.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python

from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.money import Currency, Money
```
with:
```python

from datetime import date, timedelta
from typing import Protocol, runtime_checkable

from steadyhand._validate import require_int
from steadyhand.money import Currency, Money
```

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python
        """Whether the market is open on *day*. Raises for a year with no holiday data."""
        ...
```
with:
```python
        """Whether the market is open on *day*. Raises for a year with no holiday data."""
        ...


def add_trading_days(rules: MarketRules, day: date, count: int) -> date:
    """The day *count* trading days after *day*, which need not be a trading day itself.

    The engine's dividend pay date and the income calendar's pay month both come from here, so
    the two cannot disagree (M4 spec §3.1).
    """
    raise NotImplementedError("add_trading_days")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=778 failed=21 -->
Expected: 778 run, 21 failed, every one `NotImplementedError`: the tests of the two new files that call `add_trading_days`, `run_rate` or `payment_calendar`.

- [ ] **Step 5: Implement.** `corporate.py` drops its private `_add_trading_days` and calls `market.add_trading_days`.

**`packages/steadyhand/src/steadyhand/corporate.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
from dataclasses import dataclass, field
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules
from steadyhand.money import CurrencyMismatchError, Money, Rounding
```
with:
```python
from dataclasses import dataclass, field
from datetime import date

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules, add_trading_days
from steadyhand.money import CurrencyMismatchError, Money, Rounding
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
        if isinstance(action, CashDividend):
            run.entitle(action, _add_trading_days(rules, day, pay_lag_trading_days))
    run.pay(rules)
```
with:
```python
        if isinstance(action, CashDividend):
            run.entitle(action, add_trading_days(rules, day, pay_lag_trading_days))
    run.pay(rules)
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
        )


def _add_trading_days(rules: MarketRules, day: date, count: int) -> date:
    current = day
    for _ in range(count):
        current += timedelta(days=1)
        while not rules.is_trading_day(current):
            current += timedelta(days=1)
    return current
```
with:
```python
        )
```

**`packages/steadyhand/src/steadyhand/income.py`** (implemented: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    """
    raise NotImplementedError("run_rate")

```
with:
```python
    """
    require_int(pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
    since = year_window_start(as_of)
    nothing = Money.zero(portfolio.currency)
    holdings: list[HoldingRunRate] = []
    for position in portfolio.positions:
        stock = position.instrument
        actions = _history_of(stock, history)
        dividends = [
            action
            for action in actions
            if isinstance(action, CashDividend) and since <= action.ex_date <= as_of
        ]
        paid: list[Entitlement] = []
        for dividend in sorted(dividends, key=lambda found: found.ex_date):
            gross = _restated_gross(dividend, position.quantity, actions, as_of)
            if gross.amount > 0:
                pay = add_trading_days(rules, dividend.ex_date, pay_lag_trading_days)
                paid.append(Entitlement(stock, dividend.ex_date, pay, gross))
        annual = sum((entitlement.gross for entitlement in paid), nothing)
        monthly = _per_month(_take_home(annual, rules, as_of))
        holdings.append(HoldingRunRate(stock, position.quantity, tuple(paid), annual, monthly))
    total = sum((holding.annual_gross for holding in holdings), nothing)
    return RunRate(as_of, tuple(holdings), total, _per_month(_take_home(total, rules, as_of)))

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    """Where in the year *rate*'s dividends would arrive, as take-home (M4 spec §5.1)."""
    raise NotImplementedError("payment_calendar")

```
with:
```python
    """Where in the year *rate*'s dividends would arrive, as take-home (M4 spec §5.1)."""
    nothing = Money.zero(rate.annual_gross.currency)
    totals = [nothing] * _MONTHS
    holdings: list[HoldingCalendar] = []
    for holding in rate.holdings:
        months = [nothing] * _MONTHS
        for dividend in holding.dividends:
            months[dividend.pay_date.month - 1] += _take_home(dividend.gross, rules, rate.as_of)
        totals = [total + month for total, month in zip(totals, months, strict=True)]
        holdings.append(HoldingCalendar(holding.instrument, tuple(months)))
    year = sum(totals, nothing)
    return PaymentCalendar(
        tuple(totals),
        tuple(holdings),
        sum(1 for month in totals if month.amount == 0),
        _ratio(max(totals), year),
    )

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
) -> Sequence[CorporateAction]:
    raise NotImplementedError("_history_of")

```
with:
```python
) -> Sequence[CorporateAction]:
    actions = history.get(stock)
    if actions is None:
        msg = f"{stock.symbol}: no dividend history was passed for a stock the portfolio holds"
        raise ValueError(msg)
    for action in actions:
        if action.instrument != stock:
            msg = f"{stock.symbol}: its history holds an action for {action.instrument.symbol}"
            raise ValueError(msg)
    return actions

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    """
    raise NotImplementedError("_split_ratio")

```
with:
```python
    """
    old = new = 1
    for action in actions:
        if isinstance(action, Split) and ex_date <= action.ex_date <= as_of:
            old *= action.old_shares
            new *= action.new_shares
    return old, new

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    """
    raise NotImplementedError("_restated_gross")

```
with:
```python
    """
    old, new = _split_ratio(dividend.ex_date, actions, as_of)
    numerator, denominator = dividend.per_share.as_integer_ratio()
    currency = dividend.instrument.currency
    scale = 10**currency.minor_units
    return Money(numerator * shares * old * scale // (denominator * new), currency)

```

**`packages/steadyhand/src/steadyhand/market.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python
    """
    raise NotImplementedError("add_trading_days")
```
with:
```python
    """
    require_int(count, "count", minimum=0)
    current = day
    for _ in range(count):
        current += timedelta(days=1)
        while not rules.is_trading_day(current):
            current += timedelta(days=1)
    return current
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=778 passed=778 -->
Expected: every command exits 0; 778 passed, 100% branch coverage; the performance test passes.

- [ ] **Step 7: Mutations.** Run M74–M82; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S2 run-rate and payment calendar`, ending in the story's issue number as `(#N)`).

---

### Task 3: S3 Notes, measured dividend growth and the projection

**Acceptance criteria (story text):**
1. `notes.py` (scope decision 6): `Note(key, text)` refuses a key that is not a dotted lowercase identifier and a blank text; the keys are constants named after their values, `INCOME_GROWTH_SHORT_HISTORY` and `INCOME_PROJECTION_COSTS_IGNORED`. `tests/meta/test_note_keys.py` walks the AST and asserts each key's shape and name, that no key string appears in any other engine module, that every `Note(...)` names its key by a constant, and that every key is used (scope decision 7).
2. `years_before(day, years)` gives the same month and day, 29 February becoming 28 February.
3. `dividend_growth(rate, history) -> DividendGrowth`: for each holding with a run-rate, `recent` and `earlier` are its restated dividends a share over the year windows ending on the run-rate's day and 4 years before; its growth is `(recent / earlier) ** (1/4) − 1` at 50 digits, rounded; `earlier` of 0 gives 0% and a note keyed `income.growth.short_history` naming it. The portfolio's growth weights each holding's by its run-rate gross.
4. `IncomeGoal(monthly_target)` is positive `Money`; `IncomeSettings(goal, monthly_contribution=None, pay_lag_trading_days=14)` checks its parts, the contribution positive and in the goal's currency.
5. `project(rate, growth, holdings_value, settings, rules) -> Projection`: three `ScenarioProjection`s as M4 §5.3 amended by decision 5, `CANNOT` decided first (no run-rate or no holdings' value), then month 0, then months 1 to 600 in §5.3's order, with years rounded up to a tenth, or `NOT_WITHIN`. Every projection carries `PROJECTION_LABEL` and a note keyed `income.projection.costs_ignored`, and refuses a goal in another currency.
6. Properties: a zero run-rate cannot be projected; a larger contribution never takes longer; pessimistic never beats base and base never beats optimistic, with `NOT_WITHIN` after every number.
7. The engine exports the new names. Every gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M83–M97 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/notes.py`
- Modify: `.../steadyhand/income.py`, `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_notes.py`, `tests/engine/test_income_projection.py`, `tests/meta/test_note_keys.py`

**Interfaces:**
- Consumes: Task 2's `RunRate` (its `as_of`, `holdings` and `annual_gross`), `_history_of` and `_split_ratio`; Task 1's `_per_month`; `MarketRules.dividend_tax`; `metrics.year_window_start`; `corporate.PAY_LAG_TRADING_DAYS`. The tests build run-rates with Task 2's `run_rate`.
- Produces: `Note(key: str, text: str)`, `INCOME_GROWTH_SHORT_HISTORY`, `INCOME_PROJECTION_COSTS_IGNORED` (in `notes`); `PROJECTION_LABEL`, `PROJECTION_MONTHS`, `GROWTH_YEARS`, `PESSIMISTIC_START`, `BASE_GROWTH_CAP`, `OPTIMISTIC_GROWTH_CAP`; `years_before(day: date, years: int) -> date`; `HoldingGrowth(instrument, recent: Decimal, earlier: Decimal, growth: Decimal)`; `DividendGrowth(holdings: tuple[HoldingGrowth, ...], portfolio: Decimal, notes: tuple[Note, ...])`; `dividend_growth(rate: RunRate, history: Mapping[Instrument, Sequence[CorporateAction]]) -> DividendGrowth`; `IncomeGoal(monthly_target: Money)`; `IncomeSettings(goal: IncomeGoal, monthly_contribution: Money | None = None, pay_lag_trading_days: int = 14)`; `Scenario` and `ProjectionOutcome` enums; `ScenarioProjection(scenario, starting_gross: Money, growth: Decimal, outcome, years: Decimal | None)`; `Projection(target: Money, contribution: Money, scenarios: tuple[ScenarioProjection, ...], notes: tuple[Note, ...])` with `.label`; `project(rate: RunRate, growth: DividendGrowth, holdings_value: Money, settings: IncomeSettings, rules: MarketRules) -> Projection`.

- [ ] **Step 1: Branch.** `git switch -c m4/s3-projection origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_income_projection.py`** (new)

<!-- file: tests/engine/test_income_projection.py -->
```python
"""dividend_growth and project: measured growth and the three-scenario projection (M4 §5.2, §5.3).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah. Growth is measured on Monday 7 July 2025: its year
window starts on 8 July 2024, and the window four years earlier runs from 8 July 2020 to
7 July 2021.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from steadyhand.income import (
    PROJECTION_LABEL,
    DividendGrowth,
    HoldingGrowth,
    IncomeGoal,
    IncomeSettings,
    Projection,
    ProjectionOutcome,
    RunRate,
    Scenario,
    ScenarioProjection,
    dividend_growth,
    project,
    run_rate,
    years_before,
)
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.portfolio import Portfolio
from steadyhand.types import (
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    Order,
    Side,
    Split,
)
from steadyhand_idx import IdxMarketRules

ASII = Instrument("ASII", "IDX", IDR)
BBCA = Instrument("BBCA", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
UNVR = Instrument("UNVR", "IDX", IDR)
USD = Currency("USD", 2)
AS_OF = date(2025, 7, 7)
BOUGHT = date(2020, 1, 2)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


class _TaxFree(IdxMarketRules):
    """IDX, but in a market that taxes no dividend, so a projection's arithmetic stays exact."""

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)


@cache
def tax_free() -> _TaxFree:
    return _TaxFree()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(**shares: int) -> Portfolio:
    book = Portfolio.empty(IDR)
    for symbol, quantity in shares.items():
        order = Order(Instrument(symbol, "IDX", IDR), Side.BUY, quantity, BOUGHT)
        fill = Fill(order, BOUGHT, quantity, rp(1), Costs.zero(IDR))
        book = book.deposit(rp(quantity), BOUGHT).apply_fill(fill, BOUGHT)
    return book


def dividend(stock: Instrument, ex_date: date, per_share: str) -> CashDividend:
    return CashDividend(stock, ex_date, Decimal(per_share))


def growth_of(
    portfolio: Portfolio, history: dict[Instrument, Sequence[CorporateAction]]
) -> DividendGrowth:
    return dividend_growth(run_rate(portfolio, history, rules(), AS_OF, 3), history)


def rate(gross: int) -> RunRate:
    return RunRate(AS_OF, (), rp(gross), rp(0))


def measured(growth: str) -> DividendGrowth:
    return DividendGrowth((), Decimal(growth), ())


def goal(target: int, contribution: int | None = None) -> IncomeSettings:
    added = None if contribution is None else rp(contribution)
    return IncomeSettings(IncomeGoal(rp(target)), added)


def years(projection: Projection) -> dict[Scenario, Decimal | None]:
    return {found.scenario: found.years for found in projection.scenarios}


def test_years_before_keeps_the_month_and_day() -> None:
    assert years_before(AS_OF, 4) == date(2021, 7, 7)
    assert years_before(date(2024, 2, 29), 4) == date(2020, 2, 29)
    assert years_before(date(2024, 2, 29), 1) == date(2023, 2, 28)


def test_growth_is_the_yearly_rate_between_year_windows_four_years_apart() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        # Earlier 200 a share, 100 on today's basis after the 1-for-2 split; recent
        # 46.41 + 100 = 146.41. 146.41 / 100 = 1.4641 = 1.1 ** 4: 10% a year. The 2023 dividend
        # is in neither window.
        BBCA: [
            dividend(BBCA, date(2020, 11, 16), "200"),
            Split(BBCA, date(2022, 6, 1), 1, 2),
            dividend(BBCA, date(2023, 5, 2), "999"),
            dividend(BBCA, date(2024, 11, 18), "46.41"),
            dividend(BBCA, date(2025, 4, 21), "100"),
        ],
        # 81 / 100 = 0.81, whose fourth root is 0.9486832980...: -5.131670...% a year.
        TLKM: [dividend(TLKM, date(2021, 4, 19), "100"), dividend(TLKM, date(2025, 4, 21), "81")],
        # Nothing four years ago: taken as 0%, with a note.
        UNVR: [dividend(UNVR, date(2025, 4, 21), "10")],
        # Nothing in the last year: no run-rate, so no weight and no entry.
        ASII: [dividend(ASII, date(2021, 4, 19), "50")],
    }
    growth = growth_of(holding(ASII=100, BBCA=100, TLKM=100, UNVR=100), history)
    assert growth.holdings == (
        HoldingGrowth(BBCA, Decimal("146.41"), Decimal(100), Decimal("0.10000000")),
        HoldingGrowth(TLKM, Decimal(81), Decimal(100), Decimal("-0.05131670")),
        HoldingGrowth(UNVR, Decimal(10), Decimal(0), Decimal(0)),
    )
    # Weighted by run-rate gross (14,641, 8,100 and 1,000 of 23,741):
    # (0.1 x 14,641 - 0.0513167 x 8,100 + 0 x 1,000) / 23,741 = 1,048.43473 / 23,741.
    assert growth.portfolio == Decimal("0.04416136")
    assert growth.notes == (
        Note(
            INCOME_GROWTH_SHORT_HISTORY,
            "UNVR: no dividend was found in the year ending 2021-07-07, so its dividend "
            "growth is taken as 0%",
        ),
    )


def test_the_earlier_window_holds_both_of_its_ends_and_nothing_outside_them() -> None:
    history: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [
            dividend(BBCA, date(2020, 7, 7), "1000"),
            dividend(BBCA, date(2020, 7, 8), "4"),
            dividend(BBCA, date(2021, 7, 7), "6"),
            dividend(BBCA, date(2021, 7, 8), "500"),
            dividend(BBCA, date(2025, 4, 21), "10"),
        ]
    }
    growth = growth_of(holding(BBCA=100), history)
    assert growth.holdings == (HoldingGrowth(BBCA, Decimal(10), Decimal(10), Decimal(0)),)


def test_a_portfolio_with_nothing_paying_has_no_growth() -> None:
    growth = growth_of(holding(TLKM=100), {TLKM: []})
    assert growth == DividendGrowth((), Decimal(0), ())


def test_an_income_goal_is_a_positive_amount_of_money() -> None:
    with pytest.raises(ValueError, match=r"^an income goal must be positive, got IDR 0$"):
        IncomeGoal(rp(0))
    with pytest.raises(TypeError, match=r"^monthly_target must be a Money, got int$"):
        IncomeGoal(5_000)  # type: ignore[arg-type]


def test_income_settings_default_to_no_contribution_and_the_engines_pay_lag() -> None:
    plain = IncomeSettings(IncomeGoal(rp(5_000)))
    assert plain.monthly_contribution is None
    assert plain.pay_lag_trading_days == 14


def test_income_settings_check_their_parts() -> None:
    target = IncomeGoal(rp(5_000))
    with pytest.raises(TypeError, match=r"^goal must be an IncomeGoal, got Money$"):
        IncomeSettings(rp(5_000))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^monthly_contribution must be a Money, got int$"):
        IncomeSettings(target, 1_000)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^a monthly contribution must be positive, got IDR 0$"):
        IncomeSettings(target, rp(0))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        IncomeSettings(target, Money(100, USD))
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        IncomeSettings(target, pay_lag_trading_days=0)


def test_a_goal_already_met_takes_no_time() -> None:
    # (120,000 - 12,000) / 12 = 9,000: met before the first month.
    projection = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_000), rules())
    assert years(projection)[Scenario.BASE] == Decimal("0.0")
    assert years(projection)[Scenario.OPTIMISTIC] == Decimal("0.0")


def test_a_short_run_simulated_by_hand() -> None:
    # Income 120,000 on a value of 1,200,000: a 10% yield, which reinvesting keeps.
    # Month 1: 10,000 a month less 1,000 tax reinvests 9,000, adding 9,000 x 10% = 900:
    #   income 120,900, whose take-home (120,900 - 12,090) / 12 = 9,067 misses 9,070.
    # Month 2: 10,075 a month less 1,008 (1,007.5 up) reinvests 9,067, adding 906.7 down to
    #   906: income 121,806, take-home (121,806 - 12,181) / 12 = 9,135. Met: 2 months, 0.2 years.
    # Reinvesting the tax too would add 1,000 in month 1, reach 9,075 and meet it a month early.
    projection = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_070), rules())
    assert years(projection)[Scenario.BASE] == Decimal("0.2")
    assert years(projection)[Scenario.OPTIMISTIC] == Decimal("0.2")


def test_the_contribution_is_reinvested_each_month() -> None:
    # Month 1 with 1,000 added: 9,000 + 1,000 reinvested adds 1,000, income 121,000, take-home
    # (121,000 - 12,100) / 12 = 9,075: met at once. Without it, month 1 gives 9,067 and
    # month 2 gives 9,135 (the test above).
    added = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_075, 1_000), rules())
    plain = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_075), rules())
    assert years(added)[Scenario.BASE] == Decimal("0.1")
    assert years(plain)[Scenario.BASE] == Decimal("0.2")


def test_dividends_grow_at_month_twelve_before_the_target_is_checked() -> None:
    # No tax, and a value so large that reinvesting adds nothing: income stays 240 (20 a
    # month) until month 12 grows it 5% to 252 (21 a month), which meets 21 in month 12.
    projection = project(rate(240), measured("0.05"), rp(10**12), goal(21), tax_free())
    assert years(projection)[Scenario.BASE] == Decimal("1.0")


def test_the_last_month_is_the_six_hundredth() -> None:
    # No tax, reinvesting adds nothing, and 5% growth multiplies income by 21/20 each year:
    # after k years 12 x 20**50 becomes 12 x 21**k x 20**(50 - k), exactly, which is
    # 21**k x 20**(50 - k) a month. That reaches 21**50 in month 600 and never 21**50 + 1.
    start, value = 12 * 20**50, rp(10**140)
    met = project(rate(start), measured("0.05"), value, goal(21**50), tax_free())
    missed = project(rate(start), measured("0.05"), value, goal(21**50 + 1), tax_free())
    assert years(met)[Scenario.BASE] == Decimal("50.0")
    base = missed.scenarios[1]
    assert (base.scenario, base.outcome, base.years) == (
        Scenario.BASE,
        ProjectionOutcome.NOT_WITHIN,
        None,
    )


def test_nothing_to_project_from_cannot_be_projected() -> None:
    silent = project(rate(0), measured("0"), rp(1_200_000), goal(1), rules())
    # With no holdings' value, even a goal the income already meets cannot be projected.
    unvalued = project(rate(120_000), measured("0"), rp(0), goal(1), rules())
    for projection in (silent, unvalued):
        assert [(s.outcome, s.years) for s in projection.scenarios] == [
            (ProjectionOutcome.CANNOT, None)
        ] * 3


@pytest.mark.parametrize(
    ("growth", "pessimistic", "base", "optimistic"),
    [
        ("-0.03", "-0.03", "-0.03", "-0.03"),
        ("0.07", "0", "0.05", "0.07"),
        ("0.12", "0", "0.05", "0.10"),
    ],
)
def test_each_scenario_starts_and_grows_as_the_spec_says(
    growth: str, pessimistic: str, base: str, optimistic: str
) -> None:
    projection = project(rate(1_001), measured(growth), rp(10_000), goal(1), rules())
    # The pessimistic start is 80% of 1,001 = 800.8, rounded down.
    assert [(s.scenario, s.starting_gross, s.growth) for s in projection.scenarios] == [
        (Scenario.PESSIMISTIC, rp(800), Decimal(pessimistic)),
        (Scenario.BASE, rp(1_001), Decimal(base)),
        (Scenario.OPTIMISTIC, rp(1_001), Decimal(optimistic)),
    ]


def test_a_projection_carries_its_label_the_goal_and_the_costs_note() -> None:
    projection = project(rate(120_000), measured("0"), rp(1_200_000), goal(9_000, 500), rules())
    assert projection.label == PROJECTION_LABEL == "Projection, not a promise"
    assert (projection.target, projection.contribution) == (rp(9_000), rp(500))
    assert [note.key for note in projection.notes] == [INCOME_PROJECTION_COSTS_IGNORED]
    assert projection.scenarios[1] == ScenarioProjection(
        Scenario.BASE, rp(120_000), Decimal(0), ProjectionOutcome.REACHED, Decimal("0.0")
    )


def test_a_goal_in_another_currency_is_refused() -> None:
    dollars = IncomeSettings(IncomeGoal(Money(100, USD)))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        project(rate(120_000), measured("0"), rp(1_200_000), dollars, rules())


def rank(scenario: ScenarioProjection) -> Decimal:
    """Years, with ``NOT_WITHIN`` after every number."""
    return Decimal("Infinity") if scenario.years is None else scenario.years


grosses = st.integers(min_value=12, max_value=10**9)
values = st.integers(min_value=1, max_value=10**11)
targets = st.integers(min_value=1, max_value=10**7)
rates = st.decimals(min_value=Decimal("-0.2"), max_value=Decimal("0.2"), places=4, allow_nan=False)
added = st.integers(min_value=0, max_value=10**6)

# Each example simulates up to three times 600 months, so these run fewer examples than the
# profile's default.


@settings(max_examples=100)
@given(values, targets, added)
def test_a_zero_run_rate_cannot_be_projected(value: int, target: int, contribution: int) -> None:
    projection = project(
        rate(0), measured("0"), rp(value), goal(target, contribution or None), rules()
    )
    assert {s.outcome for s in projection.scenarios} == {ProjectionOutcome.CANNOT}


@settings(max_examples=100)
@given(grosses, values, targets, rates, added, added)
def test_a_larger_contribution_never_takes_longer(
    gross: int, value: int, target: int, growth: Decimal, smaller: int, extra: int
) -> None:
    less = project(
        rate(gross), measured(str(growth)), rp(value), goal(target, smaller or None), rules()
    )
    more = project(
        rate(gross),
        measured(str(growth)),
        rp(value),
        goal(target, smaller + extra or None),
        rules(),
    )
    for fewer, larger in zip(less.scenarios, more.scenarios, strict=True):
        assert rank(larger) <= rank(fewer)


@settings(max_examples=100)
@given(grosses, values, targets, rates, added)
def test_pessimistic_never_beats_base_and_base_never_beats_optimistic(
    gross: int, value: int, target: int, growth: Decimal, contribution: int
) -> None:
    projection = project(
        rate(gross), measured(str(growth)), rp(value), goal(target, contribution or None), rules()
    )
    pessimistic, base, optimistic = (rank(s) for s in projection.scenarios)
    assert pessimistic >= base >= optimistic
```

**`tests/engine/test_notes.py`** (new)

<!-- file: tests/engine/test_notes.py -->
```python
"""Note: a stable key and a sentence (M4 spec §7)."""

import pytest

from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, Note


def test_a_note_keeps_its_key_and_text() -> None:
    note = Note(INCOME_GROWTH_SHORT_HISTORY, "BBCA: taken as 0%")
    assert (note.key, note.text) == ("income.growth.short_history", "BBCA: taken as 0%")


@pytest.mark.parametrize("key", ["income", "Income.growth", "income.growth.", "income..growth"])
def test_a_key_is_a_dotted_lowercase_identifier(key: str) -> None:
    with pytest.raises(ValueError, match=r"^a note key is a dotted lowercase identifier, got '"):
        Note(key, "some text")


def test_a_note_has_words() -> None:
    with pytest.raises(ValueError, match=r"^the note income\.growth\.short_history has no text$"):
        Note(INCOME_GROWTH_SHORT_HISTORY, "  ")


def test_a_key_and_a_text_are_strings() -> None:
    with pytest.raises(TypeError, match=r"^key must be a str, got int$"):
        Note(1, "some text")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^text must be a str, got NoneType$"):
        Note(INCOME_GROWTH_SHORT_HISTORY, None)  # type: ignore[arg-type]
```

**`tests/meta/test_note_keys.py`** (new)

<!-- file: tests/meta/test_note_keys.py -->
```python
"""Every note key is a stable constant, defined once and used (M4 spec §7).

The training sub-project attaches lessons to keys, so a key must never be reworded or reused,
and no note may be built from a literal that could drift from its constant. The keys are read
from ``notes.py`` and the ``Note(...)`` calls from every engine module, both by walking the AST,
so a comment or a docstring that mentions a key is never a finding.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
NOTES = ENGINE / "notes.py"
KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
KNOWN = {"income.growth.short_history", "income.projection.costs_ignored"}


def key_constants(source: str) -> list[tuple[str, str]]:
    """Every public module-level constant in *source* whose value is a string: (name, value)."""
    found: list[tuple[str, str]] = []
    for node in ast.parse(source).body:
        targets: list[ast.expr] = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        value = getattr(node, "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            found += [
                (t.id, value.value)
                for t in targets
                if isinstance(t, ast.Name) and not t.id.startswith("_")
            ]
    return found


def note_keys(source: str) -> list[str]:
    """How each ``Note(...)`` call in *source* names its key: a constant's name, or a finding."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or _called(node.func) != "Note":
            continue
        keywords = [keyword.value for keyword in node.keywords if keyword.arg == "key"]
        key = node.args[0] if node.args else next(iter(keywords), None)
        if isinstance(key, ast.Name):
            found.append(key.id)
        elif isinstance(key, ast.Attribute):
            found.append(key.attr)
        else:
            found.append(f"line {node.lineno}: key is not a constant")
    return found


def string_literals(source: str) -> list[str]:
    """Every string constant anywhere in *source*. A key matches only a string equal to it, so
    a docstring or a message that mentions a key among other words is not a finding."""
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _called(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def engine_sources() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in sorted(ENGINE.rglob("*.py"))}


def test_the_constant_detector() -> None:
    source = "A = 'x.y'\n_B = 'z.w'\nC: str = 'c.d'\nD = 2\nE = F = 'e.f'\n"
    assert key_constants(source) == [("A", "x.y"), ("C", "c.d"), ("E", "e.f"), ("F", "e.f")]


def test_the_note_detector() -> None:
    source = (
        "Note(KEY, 't')\n"
        "notes.Note(notes.OTHER, 't')\n"
        "Note(key=NAMED, text='t')\n"
        "Note('income.x', 't')\n"
        "Note(f'{a}.b', 't')\n"
        "Note(make(), 't')\n"
        "Note()\n"
        "Other('income.y', 't')\n"
    )
    assert note_keys(source) == [
        "KEY",
        "OTHER",
        "NAMED",
        "line 4: key is not a constant",
        "line 5: key is not a constant",
        "line 6: key is not a constant",
        "line 7: key is not a constant",
    ]


def test_the_literal_detector() -> None:
    source = '"""Mentions income.x in passing."""\nK = "income.x"\nNote("income.y", "t")\n'
    assert {"income.x", "income.y"} <= set(string_literals(source))
    assert "income.x" not in string_literals('"""Mentions income.x in passing."""\n')


def test_every_key_is_a_dotted_lowercase_identifier_named_after_itself() -> None:
    keys = key_constants(NOTES.read_text(encoding="utf-8"))
    assert {value for _, value in keys} >= KNOWN
    for name, value in keys:
        assert KEY.fullmatch(value), f"{name} = {value!r} is not a dotted lowercase identifier"
        assert name == value.upper().replace(".", "_"), f"{name} is not named after {value!r}"


def test_no_key_is_defined_twice() -> None:
    keys = key_constants(NOTES.read_text(encoding="utf-8"))
    values = [value for _, value in keys]
    assert len(set(values)) == len(values) >= len(KNOWN)
    elsewhere = {
        path.name: sorted(set(values) & set(string_literals(source)))
        for path, source in engine_sources().items()
        if path != NOTES
    }
    assert len(elsewhere) >= 10, "the engine's modules were not found"
    assert {name: found for name, found in elsewhere.items() if found} == {}


def test_every_note_is_built_from_a_key_constant_and_every_key_is_used() -> None:
    names = {name for name, _ in key_constants(NOTES.read_text(encoding="utf-8"))}
    used = [key for source in engine_sources().values() for key in note_keys(source)]
    assert len(used) >= len(KNOWN), "no Note(...) call was found in the engine"
    assert sorted(set(used) - names) == []
    assert sorted(names - set(used)) == []
```


- [ ] **Step 3: Write the stubs.** New names only; everything that existed keeps its current body.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed, rewritten whole)

<!-- file: packages/steadyhand/src/steadyhand/__init__.py -->
```python
"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

from steadyhand.backtest import (
    BacktestResult,
    BacktestSettings,
    Market,
    NoTradingDaysError,
    RunResult,
    UniverseCoverageError,
    backtest,
)
from steadyhand.broker import Broker, FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import (
    PAY_LAG_TRADING_DAYS,
    CorporateOutcome,
    Entitlement,
    Holdings,
    apply_actions,
)
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
from steadyhand.disclaimer import DISCLAIMER
from steadyhand.engine import (
    DataValidationError,
    DayInputs,
    DayOrderError,
    DayReport,
    EngineSettings,
    EngineState,
    run_day,
)
from steadyhand.income import (
    BASE_GROWTH_CAP,
    GROWTH_YEARS,
    OPTIMISTIC_GROWTH_CAP,
    PESSIMISTIC_START,
    PROJECTION_LABEL,
    PROJECTION_MONTHS,
    DividendGrowth,
    HoldingCalendar,
    HoldingGrowth,
    HoldingRunRate,
    IncomeFigures,
    IncomeGoal,
    IncomeSettings,
    MonthlyIncome,
    PaymentCalendar,
    Projection,
    ProjectionOutcome,
    ReceivedIncome,
    RunRate,
    Scenario,
    ScenarioProjection,
    dividend_growth,
    payment_calendar,
    project,
    received_income,
    run_rate,
    years_before,
)
from steadyhand.market import MarketRules, UnsupportedDateError, add_trading_days
from steadyhand.metrics import (
    RATIO_PLACES,
    YEAR_DAYS,
    CostBreakdown,
    DividendTotals,
    Drawdown,
    Metrics,
    measure,
    year_window_start,
)
from steadyhand.money import (
    IDR,
    MAX_MINOR_UNITS,
    Currency,
    CurrencyMismatchError,
    Money,
    Rounding,
)
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import (
    CashMovement,
    ChronologyError,
    InsufficientCashError,
    InsufficientSharesError,
    MissingPriceError,
    MovementKind,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.risk import Checked, Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.strategies import (
    STRATEGIES,
    BuyAndHold,
    Decision,
    InvalidWeightsError,
    Memory,
    Strategy,
)
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    InvalidBarError,
    Order,
    OrderAck,
    OtherAction,
    Position,
    Side,
    Split,
)
from steadyhand.universe import Universe
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

__version__: str = version("steadyhand")

__all__ = [
    "BASE_GROWTH_CAP",
    "DISCLAIMER",
    "GROWTH_YEARS",
    "IDR",
    "INCOME_GROWTH_SHORT_HISTORY",
    "INCOME_PROJECTION_COSTS_IGNORED",
    "MAX_MINOR_UNITS",
    "OPTIMISTIC_GROWTH_CAP",
    "PAY_LAG_TRADING_DAYS",
    "PESSIMISTIC_START",
    "PROJECTION_LABEL",
    "PROJECTION_MONTHS",
    "RATIO_PLACES",
    "STRATEGIES",
    "YEAR_DAYS",
    "BacktestResult",
    "BacktestSettings",
    "Bar",
    "Broker",
    "BuyAndHold",
    "CashDividend",
    "CashMovement",
    "Checked",
    "ChronologyError",
    "CompoundingSizer",
    "CorporateAction",
    "CorporateOutcome",
    "CostBreakdown",
    "Costs",
    "Currency",
    "CurrencyMismatchError",
    "Cut",
    "DataSource",
    "DataUnavailableError",
    "DataValidationError",
    "DayInputs",
    "DayOrderError",
    "DayReport",
    "Decision",
    "DividendGrowth",
    "DividendTotals",
    "Drawdown",
    "EngineSettings",
    "EngineState",
    "Entitlement",
    "Fill",
    "FillResult",
    "FillSettings",
    "Halt",
    "HoldingCalendar",
    "HoldingGrowth",
    "HoldingRunRate",
    "Holdings",
    "IncomeFigures",
    "IncomeGoal",
    "IncomeSettings",
    "Instrument",
    "InsufficientCashError",
    "InsufficientSharesError",
    "InvalidBarError",
    "InvalidWeightsError",
    "LookAheadError",
    "Market",
    "MarketRules",
    "MarketView",
    "Memory",
    "Metrics",
    "MissingPriceError",
    "Money",
    "MonthlyIncome",
    "MovementKind",
    "NegativeProceedsError",
    "NoTradingDaysError",
    "Note",
    "Opening",
    "Order",
    "OrderAck",
    "OtherAction",
    "PaymentCalendar",
    "Portfolio",
    "PortfolioView",
    "Position",
    "PriceHistory",
    "Projection",
    "ProjectionOutcome",
    "ReceivedIncome",
    "Rejected",
    "RiskLimits",
    "RiskManager",
    "Rounding",
    "RunRate",
    "RunResult",
    "Scenario",
    "ScenarioProjection",
    "Side",
    "SimulatedBroker",
    "Sizer",
    "Split",
    "Strategy",
    "Tradable",
    "UnavailableDaysError",
    "UnitValue",
    "Universe",
    "UniverseCoverageError",
    "UnsupportedDateError",
    "__version__",
    "add_trading_days",
    "apply_actions",
    "backtest",
    "dividend_growth",
    "measure",
    "payment_calendar",
    "project",
    "received_income",
    "run_day",
    "run_rate",
    "year_window_start",
    "years_before",
]
```

**`packages/steadyhand/src/steadyhand/income.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

from collections.abc import Iterator, Mapping, Sequence
```
with:
```python

import calendar
from collections.abc import Iterator, Mapping, Sequence
```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand._validate import require_int
from steadyhand.corporate import Entitlement
from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules, add_trading_days
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Split

```
with:
```python
from decimal import ROUND_HALF_EVEN, Context, Decimal
from enum import Enum

from steadyhand._validate import require_int, require_type
from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement
from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules, add_trading_days
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, CurrencyMismatchError, Money, Rounding
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Split

PROJECTION_LABEL = "Projection, not a promise"
"""Carried by every projection: it reports years, never a date (core spec §7)."""

PROJECTION_MONTHS = 600
"""A projection stops after 50 years: a target not met by then is ``NOT_WITHIN``."""

GROWTH_YEARS = 4
"""Dividend growth compares the trailing year with the year ending this many years earlier."""

PESSIMISTIC_START = Decimal("0.8")
"""The pessimistic scenario starts from this share of the run-rate (core spec §7)."""

BASE_GROWTH_CAP = Decimal("0.05")
OPTIMISTIC_GROWTH_CAP = Decimal("0.10")
"""The base and optimistic scenarios grow dividends at the measured rate, up to these caps."""

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

def run_rate(
```
with:
```python

@dataclass(frozen=True, slots=True)
class HoldingGrowth:
    """One holding's measured dividend growth (M4 spec §5.2).

    ``recent`` and ``earlier`` are its dividends a share, restated onto today's basis, over the
    year windows ending on the run-rate's day and ``GROWTH_YEARS`` years before it. ``growth``
    is the yearly rate that turns one into the other over those years, or 0 when ``earlier`` is
    0: it paid nothing then, or its history does not reach back that far.
    """

    instrument: Instrument
    recent: Decimal
    earlier: Decimal
    growth: Decimal


@dataclass(frozen=True, slots=True)
class DividendGrowth:
    """Each paying holding's growth, and the portfolio's: theirs weighted by run-rate gross.

    A holding whose run-rate is zero carries no weight and is left out. ``notes`` name each
    holding whose growth could not be measured.
    """

    holdings: tuple[HoldingGrowth, ...]
    portfolio: Decimal
    notes: tuple[Note, ...]


@dataclass(frozen=True, slots=True)
class IncomeGoal:
    """The monthly take-home income an investor wants their dividends to reach."""

    monthly_target: Money

    def __post_init__(self) -> None:
        raise NotImplementedError("IncomeGoal.__post_init__")


@dataclass(frozen=True, slots=True)
class IncomeSettings:
    """What an income report needs beyond the run itself.

    The contribution and the pay lag are the engine's (``EngineSettings``), so that the
    projection adds what the run added and the calendar pays when the engine paid.
    """

    goal: IncomeGoal
    monthly_contribution: Money | None = None
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS

    def __post_init__(self) -> None:
        raise NotImplementedError("IncomeSettings.__post_init__")


class Scenario(Enum):
    """The three projections of core spec §7, as amended by decision 5."""

    PESSIMISTIC = "pessimistic"
    BASE = "base"
    OPTIMISTIC = "optimistic"


class ProjectionOutcome(Enum):
    """``REACHED`` in some years, ``NOT_WITHIN`` 50 years, or ``CANNOT``: nothing to project."""

    REACHED = "reached"
    NOT_WITHIN = "not within 50 years"
    CANNOT = "cannot project"


@dataclass(frozen=True, slots=True)
class ScenarioProjection:
    """One scenario: where it starts, how its dividends grow, and when it meets the target.

    ``years`` is rounded up to a tenth, and is ``None`` unless the outcome is ``REACHED``.
    """

    scenario: Scenario
    starting_gross: Money
    growth: Decimal
    outcome: ProjectionOutcome
    years: Decimal | None


@dataclass(frozen=True, slots=True)
class Projection:
    """How long until the goal is met, in three scenarios (M4 spec §5.3). Never a promise."""

    target: Money
    contribution: Money
    scenarios: tuple[ScenarioProjection, ...]
    notes: tuple[Note, ...]

    @property
    def label(self) -> str:
        raise NotImplementedError("Projection.label")


def years_before(day: date, years: int) -> date:
    """The same month and day *years* years before *day*; 29 February becomes 28 February."""
    raise NotImplementedError("years_before")


def run_rate(
```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
        _ratio(max(totals), year),
    )


```
with:
```python
        _ratio(max(totals), year),
    )


def dividend_growth(
    rate: RunRate, history: Mapping[Instrument, Sequence[CorporateAction]]
) -> DividendGrowth:
    """Each paying holding's dividend growth over ``GROWTH_YEARS`` years (M4 spec §5.2).

    This is the growth of what the portfolio holds, a share at a time, not of the income it
    received: received income also grows with every contribution and reinvested dividend,
    which the projection adds month by month, so measuring from it would count them twice.
    """
    raise NotImplementedError("dividend_growth")


def project(
    rate: RunRate,
    growth: DividendGrowth,
    holdings_value: Money,
    settings: IncomeSettings,
    rules: MarketRules,
) -> Projection:
    """How long until the goal is met, in each scenario (M4 spec §5.3).

    Each scenario starts from the run-rate's gross and the holdings' value; idle cash is not
    assumed invested. Month by month it reinvests the take-home part of the income plus the
    contribution at the portfolio's current yield, grows dividends once a year, and checks the
    monthly take-home against the target. Income rounds down, tax rounds up, and trading costs
    are left out.
    """
    raise NotImplementedError("project")


@dataclass(frozen=True, slots=True)
class _Projector:
    """One goal's month-by-month simulation, shared by the three scenarios."""

    target: Money
    contribution: Money
    rules: MarketRules
    as_of: date

    def years(self, income: Money, value: Money, growth: Decimal) -> Decimal | None:
        """Years until the target is met, rounded up to a tenth, or ``None`` after 600 months."""
        raise NotImplementedError("_Projector.years")

    def _met(self, income: Money) -> bool:
        raise NotImplementedError("_Projector._met")

    def _tax(self, gross: Money) -> Money:
        raise NotImplementedError("_Projector._tax")


def _tenths(months: int) -> Decimal:
    """*months* in years, rounded up to one decimal place."""
    raise NotImplementedError("_tenths")


def _per_share(actions: Sequence[CorporateAction], end: date, as_of: date) -> Decimal:
    """The cash dividends a share in the year window ending on *end*, on *as_of*'s basis."""
    raise NotImplementedError("_per_share")


```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

def _months(first: date, last: date) -> Iterator[date]:
```
with:
```python

def _rounded(value: Decimal) -> Decimal:
    raise NotImplementedError("_rounded")


def _months(first: date, last: date) -> Iterator[date]:
```

**`packages/steadyhand/src/steadyhand/notes.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/notes.py -->
```python
"""Notes: a stable key and a sentence, for anything a report says beyond its figures (M4 spec §7).

A key is a dotted lowercase identifier that is never reworded, so the training sub-project can
attach a lesson to it; the text is free to change. Every key is a constant below, named after its
value, and every ``Note`` in the engine is built from one of them, never from a literal
(``tests/meta/test_note_keys.py``). This module imports nothing from the rest of the engine, so
any engine module can use it without an import cycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from steadyhand._validate import require_type

INCOME_GROWTH_SHORT_HISTORY = "income.growth.short_history"
"""A holding whose dividend growth could not be measured, which therefore counts as 0%."""

INCOME_PROJECTION_COSTS_IGNORED = "income.projection.costs_ignored"
"""On every projection: the trading costs of reinvesting are left out."""

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")


@dataclass(frozen=True, slots=True)
class Note:
    """Something a report says in words, under a key that never changes."""

    key: str
    text: str

    def __post_init__(self) -> None:
        raise NotImplementedError("Note.__post_init__")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=812 failed=29 -->
Expected: 812 run, 29 failed: 28 `NotImplementedError`, and `test_every_note_is_built_from_a_key_constant_and_every_key_is_used`, whose liveness check finds no `Note(...)` call while the functions that build notes are stubs. Five tests of `test_note_keys.py` pass against the stubs by design: its three detector tests read literal sources, and the shape and single-definition checks read `notes.py`'s constants, which the stubs already hold.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/income.py`** (implemented, rewritten whole)

<!-- file: packages/steadyhand/src/steadyhand/income.py -->
```python
"""Dividend income: what a run received, what its holdings pay now, and where that leads (M4 spec).

Every function here is pure. The caller passes the run's day reports, its last state and, where a
figure needs it, each holding's dividend history; nothing here reads a file or the network.
Money stays integer minor units, income rounds down and tax rounds up. Every ratio is a
``Decimal`` worked out at 50 significant digits and rounded half-even to ``RATIO_PLACES``.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal
from enum import Enum

from steadyhand._validate import require_int, require_type
from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement
from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules, add_trading_days
from steadyhand.metrics import RATIO_PLACES, year_window_start
from steadyhand.money import Currency, CurrencyMismatchError, Money, Rounding
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Split

PROJECTION_LABEL = "Projection, not a promise"
"""Carried by every projection: it reports years, never a date (core spec §7)."""

PROJECTION_MONTHS = 600
"""A projection stops after 50 years: a target not met by then is ``NOT_WITHIN``."""

GROWTH_YEARS = 4
"""Dividend growth compares the trailing year with the year ending this many years earlier."""

PESSIMISTIC_START = Decimal("0.8")
"""The pessimistic scenario starts from this share of the run-rate (core spec §7)."""

BASE_GROWTH_CAP = Decimal("0.05")
OPTIMISTIC_GROWTH_CAP = Decimal("0.10")
"""The base and optimistic scenarios grow dividends at the measured rate, up to these caps."""

_MONTHS = 12
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class IncomeFigures:
    """Dividends over a period (M4 spec §4).

    ``gross`` is what was paid, ``tax`` what the engine booked, and ``net`` what that left.
    ``take_home`` is what the full dividend tax leaves, whatever the engine booked (decision 2):
    the figure an investor living off dividends keeps. In a monthly average each of the four is
    divided and rounded down on its own, so ``net`` there can be a minor unit off
    ``gross - tax``.
    """

    gross: Money
    tax: Money
    net: Money
    take_home: Money

    @classmethod
    def zero(cls, currency: Currency) -> IncomeFigures:
        nothing = Money.zero(currency)
        return cls(nothing, nothing, nothing, nothing)

    def __add__(self, other: IncomeFigures) -> IncomeFigures:
        return IncomeFigures(
            self.gross + other.gross,
            self.tax + other.tax,
            self.net + other.net,
            self.take_home + other.take_home,
        )


@dataclass(frozen=True, slots=True)
class MonthlyIncome:
    """One calendar month's dividends. ``month`` is the month's first day."""

    month: date
    figures: IncomeFigures


@dataclass(frozen=True, slots=True)
class ReceivedIncome:
    """The dividends a run received, as of its last day (M4 spec §4).

    ``by_month`` holds every calendar month from the first day's to the last day's, including
    months with nothing paid. ``trailing`` covers the year window ending on ``as_of``, and
    ``monthly_average`` is each trailing figure divided by 12, rounded down. ``current_yield``
    divides the trailing gross by the last day's value, and ``yield_on_cost`` by what the final
    positions cost; each is ``None`` when its divisor is zero.
    """

    as_of: date
    by_month: tuple[MonthlyIncome, ...]
    trailing: IncomeFigures
    monthly_average: IncomeFigures
    current_yield: Decimal | None
    yield_on_cost: Decimal | None


def received_income(
    reports: Sequence[DayReport], final: EngineState, rules: MarketRules
) -> ReceivedIncome:
    """The income received by a run whose day reports, in order, are *reports*."""
    if not reports:
        msg = "a run with no days has no income report"
        raise ValueError(msg)
    as_of = reports[-1].day
    since = year_window_start(as_of)
    currency = final.holdings.portfolio.currency
    months: dict[date, IncomeFigures] = {}
    trailing = IncomeFigures.zero(currency)
    for report in reports:
        figures = _day_figures(report, rules, currency)
        month = report.day.replace(day=1)
        months[month] = months.get(month, IncomeFigures.zero(currency)) + figures
        if report.day >= since:
            trailing += figures
    by_month = tuple(
        MonthlyIncome(month, months.get(month, IncomeFigures.zero(currency)))
        for month in _months(reports[0].day, as_of)
    )
    average = IncomeFigures(
        _per_month(trailing.gross),
        _per_month(trailing.tax),
        _per_month(trailing.net),
        _per_month(trailing.take_home),
    )
    cost = sum(
        (position.cost_basis for position in final.holdings.portfolio.positions),
        Money.zero(currency),
    )
    return ReceivedIncome(
        as_of,
        by_month,
        trailing,
        average,
        _ratio(trailing.gross, reports[-1].value),
        _ratio(trailing.gross, cost),
    )


@dataclass(frozen=True, slots=True)
class HoldingRunRate:
    """What one holding would pay in a year at its trailing dividends (M4 spec §5.1).

    ``dividends`` are the holding's cash dividends with an ex-date in the year window ending on
    the run-rate's day, each restated onto today's share basis (§3.3), multiplied by the shares
    held now and rounded down, and paid on its modelled pay date. A dividend that rounds to
    nothing is left out, as the engine leaves out a zero entitlement.
    """

    instrument: Instrument
    shares: int
    dividends: tuple[Entitlement, ...]
    annual_gross: Money
    monthly_take_home: Money


@dataclass(frozen=True, slots=True)
class RunRate:
    """What the final portfolio would pay in a year at its holdings' trailing dividends.

    A monthly take-home is the annual gross less the full dividend tax on ``as_of``, divided by
    12 and rounded down. The portfolio's is worked out from its own annual gross, so it can be a
    minor unit or two more than the holdings' monthly figures added up.
    """

    as_of: date
    holdings: tuple[HoldingRunRate, ...]
    annual_gross: Money
    monthly_take_home: Money


@dataclass(frozen=True, slots=True)
class HoldingCalendar:
    """One holding's expected take-home by month of the year, January first."""

    instrument: Instrument
    months: tuple[Money, ...]


@dataclass(frozen=True, slots=True)
class PaymentCalendar:
    """Expected take-home by month of the year, January first, from the run-rate (M4 §5.1).

    Each dividend counts in the month of its modelled pay date, less the full tax on the
    run-rate's day. ``empty_months`` counts the months with nothing, and ``evenness`` is the
    largest month's share of the year: 1/12 when every month is equal, 1 when one month has it
    all, and ``None`` when there is nothing to share.
    """

    months: tuple[Money, ...]
    holdings: tuple[HoldingCalendar, ...]
    empty_months: int
    evenness: Decimal | None


@dataclass(frozen=True, slots=True)
class HoldingGrowth:
    """One holding's measured dividend growth (M4 spec §5.2).

    ``recent`` and ``earlier`` are its dividends a share, restated onto today's basis, over the
    year windows ending on the run-rate's day and ``GROWTH_YEARS`` years before it. ``growth``
    is the yearly rate that turns one into the other over those years, or 0 when ``earlier`` is
    0: it paid nothing then, or its history does not reach back that far.
    """

    instrument: Instrument
    recent: Decimal
    earlier: Decimal
    growth: Decimal


@dataclass(frozen=True, slots=True)
class DividendGrowth:
    """Each paying holding's growth, and the portfolio's: theirs weighted by run-rate gross.

    A holding whose run-rate is zero carries no weight and is left out. ``notes`` name each
    holding whose growth could not be measured.
    """

    holdings: tuple[HoldingGrowth, ...]
    portfolio: Decimal
    notes: tuple[Note, ...]


@dataclass(frozen=True, slots=True)
class IncomeGoal:
    """The monthly take-home income an investor wants their dividends to reach."""

    monthly_target: Money

    def __post_init__(self) -> None:
        require_type(self.monthly_target, Money, "monthly_target")
        if self.monthly_target.amount <= 0:
            msg = f"an income goal must be positive, got {self.monthly_target}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class IncomeSettings:
    """What an income report needs beyond the run itself.

    The contribution and the pay lag are the engine's (``EngineSettings``), so that the
    projection adds what the run added and the calendar pays when the engine paid.
    """

    goal: IncomeGoal
    monthly_contribution: Money | None = None
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS

    def __post_init__(self) -> None:
        require_type(self.goal, IncomeGoal, "goal")
        if self.monthly_contribution is not None:
            require_type(self.monthly_contribution, Money, "monthly_contribution")
            if self.monthly_contribution.amount <= 0:
                msg = f"a monthly contribution must be positive, got {self.monthly_contribution}"
                raise ValueError(msg)
            target = self.goal.monthly_target
            if self.monthly_contribution.currency != target.currency:
                raise CurrencyMismatchError(target.currency, self.monthly_contribution.currency)
        require_int(self.pay_lag_trading_days, "pay_lag_trading_days", minimum=1)


class Scenario(Enum):
    """The three projections of core spec §7, as amended by decision 5."""

    PESSIMISTIC = "pessimistic"
    BASE = "base"
    OPTIMISTIC = "optimistic"


class ProjectionOutcome(Enum):
    """``REACHED`` in some years, ``NOT_WITHIN`` 50 years, or ``CANNOT``: nothing to project."""

    REACHED = "reached"
    NOT_WITHIN = "not within 50 years"
    CANNOT = "cannot project"


@dataclass(frozen=True, slots=True)
class ScenarioProjection:
    """One scenario: where it starts, how its dividends grow, and when it meets the target.

    ``years`` is rounded up to a tenth, and is ``None`` unless the outcome is ``REACHED``.
    """

    scenario: Scenario
    starting_gross: Money
    growth: Decimal
    outcome: ProjectionOutcome
    years: Decimal | None


@dataclass(frozen=True, slots=True)
class Projection:
    """How long until the goal is met, in three scenarios (M4 spec §5.3). Never a promise."""

    target: Money
    contribution: Money
    scenarios: tuple[ScenarioProjection, ...]
    notes: tuple[Note, ...]

    @property
    def label(self) -> str:
        return PROJECTION_LABEL


def years_before(day: date, years: int) -> date:
    """The same month and day *years* years before *day*; 29 February becomes 28 February."""
    year = day.year - years
    if (day.month, day.day) == (2, 29) and not calendar.isleap(year):
        return date(year, 2, 28)
    return day.replace(year=year)


def run_rate(
    portfolio: Portfolio,
    history: Mapping[Instrument, Sequence[CorporateAction]],
    rules: MarketRules,
    as_of: date,
    pay_lag_trading_days: int,
) -> RunRate:
    """The run-rate of *portfolio*'s holdings on *as_of* (M4 spec §5.1).

    *history* holds each held stock's corporate actions; a stock the portfolio holds and
    *history* lacks is an error, never read as a stock that pays nothing.
    """
    require_int(pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
    since = year_window_start(as_of)
    nothing = Money.zero(portfolio.currency)
    holdings: list[HoldingRunRate] = []
    for position in portfolio.positions:
        stock = position.instrument
        actions = _history_of(stock, history)
        dividends = [
            action
            for action in actions
            if isinstance(action, CashDividend) and since <= action.ex_date <= as_of
        ]
        paid: list[Entitlement] = []
        for dividend in sorted(dividends, key=lambda found: found.ex_date):
            gross = _restated_gross(dividend, position.quantity, actions, as_of)
            if gross.amount > 0:
                pay = add_trading_days(rules, dividend.ex_date, pay_lag_trading_days)
                paid.append(Entitlement(stock, dividend.ex_date, pay, gross))
        annual = sum((entitlement.gross for entitlement in paid), nothing)
        monthly = _per_month(_take_home(annual, rules, as_of))
        holdings.append(HoldingRunRate(stock, position.quantity, tuple(paid), annual, monthly))
    total = sum((holding.annual_gross for holding in holdings), nothing)
    return RunRate(as_of, tuple(holdings), total, _per_month(_take_home(total, rules, as_of)))


def payment_calendar(rate: RunRate, rules: MarketRules) -> PaymentCalendar:
    """Where in the year *rate*'s dividends would arrive, as take-home (M4 spec §5.1)."""
    nothing = Money.zero(rate.annual_gross.currency)
    totals = [nothing] * _MONTHS
    holdings: list[HoldingCalendar] = []
    for holding in rate.holdings:
        months = [nothing] * _MONTHS
        for dividend in holding.dividends:
            months[dividend.pay_date.month - 1] += _take_home(dividend.gross, rules, rate.as_of)
        totals = [total + month for total, month in zip(totals, months, strict=True)]
        holdings.append(HoldingCalendar(holding.instrument, tuple(months)))
    year = sum(totals, nothing)
    return PaymentCalendar(
        tuple(totals),
        tuple(holdings),
        sum(1 for month in totals if month.amount == 0),
        _ratio(max(totals), year),
    )


def dividend_growth(
    rate: RunRate, history: Mapping[Instrument, Sequence[CorporateAction]]
) -> DividendGrowth:
    """Each paying holding's dividend growth over ``GROWTH_YEARS`` years (M4 spec §5.2).

    This is the growth of what the portfolio holds, a share at a time, not of the income it
    received: received income also grows with every contribution and reinvested dividend,
    which the projection adds month by month, so measuring from it would count them twice.
    """
    earlier_end = years_before(rate.as_of, GROWTH_YEARS)
    found: list[HoldingGrowth] = []
    notes: list[Note] = []
    weighted = Decimal(0)
    for holding in rate.holdings:
        if holding.annual_gross.amount == 0:
            continue
        actions = _history_of(holding.instrument, history)
        recent = _per_share(actions, rate.as_of, rate.as_of)
        earlier = _per_share(actions, earlier_end, rate.as_of)
        if earlier == 0:
            growth = Decimal(0)
            notes.append(
                Note(
                    INCOME_GROWTH_SHORT_HISTORY,
                    f"{holding.instrument.symbol}: no dividend was found in the year ending "
                    f"{earlier_end.isoformat()}, so its dividend growth is taken as 0%",
                )
            )
        else:
            yearly = _CONTEXT.divide(_CONTEXT.divide(recent, earlier).ln(_CONTEXT), GROWTH_YEARS)
            growth = _rounded(_CONTEXT.subtract(yearly.exp(_CONTEXT), Decimal(1)))
        found.append(HoldingGrowth(holding.instrument, recent, earlier, growth))
        weighted = _CONTEXT.add(weighted, _CONTEXT.multiply(growth, holding.annual_gross.amount))
    total = rate.annual_gross.amount
    portfolio = _rounded(_CONTEXT.divide(weighted, total)) if total else Decimal(0)
    return DividendGrowth(tuple(found), portfolio, tuple(notes))


def project(
    rate: RunRate,
    growth: DividendGrowth,
    holdings_value: Money,
    settings: IncomeSettings,
    rules: MarketRules,
) -> Projection:
    """How long until the goal is met, in each scenario (M4 spec §5.3).

    Each scenario starts from the run-rate's gross and the holdings' value; idle cash is not
    assumed invested. Month by month it reinvests the take-home part of the income plus the
    contribution at the portfolio's current yield, grows dividends once a year, and checks the
    monthly take-home against the target. Income rounds down, tax rounds up, and trading costs
    are left out.
    """
    target = settings.goal.monthly_target
    if target.currency != rate.annual_gross.currency:
        raise CurrencyMismatchError(rate.annual_gross.currency, target.currency)
    given = settings.monthly_contribution
    contribution = Money.zero(target.currency) if given is None else given
    measured = growth.portfolio
    plans = (
        (
            Scenario.PESSIMISTIC,
            rate.annual_gross.times(PESSIMISTIC_START, Rounding.DOWN),
            min(Decimal(0), measured),
        ),
        (Scenario.BASE, rate.annual_gross, min(measured, BASE_GROWTH_CAP)),
        (Scenario.OPTIMISTIC, rate.annual_gross, min(measured, OPTIMISTIC_GROWTH_CAP)),
    )
    projector = _Projector(target, contribution, rules, rate.as_of)
    scenarios: list[ScenarioProjection] = []
    for scenario, start, rate_of_growth in plans:
        if rate.annual_gross.amount == 0 or holdings_value.amount == 0:
            outcome, years = ProjectionOutcome.CANNOT, None
        else:
            years = projector.years(start, holdings_value, rate_of_growth)
            outcome = ProjectionOutcome.NOT_WITHIN if years is None else ProjectionOutcome.REACHED
        scenarios.append(ScenarioProjection(scenario, start, rate_of_growth, outcome, years))
    note = Note(
        INCOME_PROJECTION_COSTS_IGNORED,
        "Reinvesting costs broker fees and levies, which this projection leaves out, so it "
        "reaches the target a little sooner than a real portfolio would",
    )
    return Projection(target, contribution, tuple(scenarios), (note,))


@dataclass(frozen=True, slots=True)
class _Projector:
    """One goal's month-by-month simulation, shared by the three scenarios."""

    target: Money
    contribution: Money
    rules: MarketRules
    as_of: date

    def years(self, income: Money, value: Money, growth: Decimal) -> Decimal | None:
        """Years until the target is met, rounded up to a tenth, or ``None`` after 600 months."""
        if self._met(income):
            return _tenths(0)
        for month in range(1, PROJECTION_MONTHS + 1):
            monthly = _per_month(income)
            new = monthly - self._tax(monthly) + self.contribution
            income += Money(new.amount * income.amount // value.amount, income.currency)
            value += new
            if month % _MONTHS == 0:
                income = income.times(1 + growth, Rounding.DOWN)
            if self._met(income):
                return _tenths(month)
        return None

    def _met(self, income: Money) -> bool:
        return _per_month(income - self._tax(income)) >= self.target

    def _tax(self, gross: Money) -> Money:
        return self.rules.dividend_tax(gross, reinvested_by_deadline=False, on=self.as_of)


def _tenths(months: int) -> Decimal:
    """*months* in years, rounded up to one decimal place."""
    return Decimal(-(-months * 10 // _MONTHS)).scaleb(-1)


def _per_share(actions: Sequence[CorporateAction], end: date, as_of: date) -> Decimal:
    """The cash dividends a share in the year window ending on *end*, on *as_of*'s basis."""
    since = year_window_start(end)
    total = Decimal(0)
    for action in actions:
        if isinstance(action, CashDividend) and since <= action.ex_date <= end:
            old, new = _split_ratio(action.ex_date, actions, as_of)
            restated = _CONTEXT.divide(_CONTEXT.multiply(action.per_share, old), new)
            total = _CONTEXT.add(total, restated)
    return total


def _history_of(
    stock: Instrument, history: Mapping[Instrument, Sequence[CorporateAction]]
) -> Sequence[CorporateAction]:
    actions = history.get(stock)
    if actions is None:
        msg = f"{stock.symbol}: no dividend history was passed for a stock the portfolio holds"
        raise ValueError(msg)
    for action in actions:
        if action.instrument != stock:
            msg = f"{stock.symbol}: its history holds an action for {action.instrument.symbol}"
            raise ValueError(msg)
    return actions


def _split_ratio(ex_date: date, actions: Sequence[CorporateAction], as_of: date) -> tuple[int, int]:
    """The (old, new) share counts of every split from *ex_date* to *as_of*, multiplied together.

    A split on the dividend's own ex-date counts: the engine pays that dividend on the shares
    held before the split (``corporate.apply_actions``), so it is on the old basis.
    """
    old = new = 1
    for action in actions:
        if isinstance(action, Split) and ex_date <= action.ex_date <= as_of:
            old *= action.old_shares
            new *= action.new_shares
    return old, new


def _restated_gross(
    dividend: CashDividend, shares: int, actions: Sequence[CorporateAction], as_of: date
) -> Money:
    """*dividend* on *shares* of today's basis, rounded down once (M4 spec §3.3).

    Worked in integers from the exact ratio of ``per_share``, so a 1-for-3 split, whose ratio
    no ``Decimal`` can hold, still gives the exact amount before the one rounding.
    """
    old, new = _split_ratio(dividend.ex_date, actions, as_of)
    numerator, denominator = dividend.per_share.as_integer_ratio()
    currency = dividend.instrument.currency
    scale = 10**currency.minor_units
    return Money(numerator * shares * old * scale // (denominator * new), currency)


def _day_figures(report: DayReport, rules: MarketRules, currency: Currency) -> IncomeFigures:
    nothing = Money.zero(currency)
    gross = sum((entitlement.gross for entitlement in report.paid), nothing)
    take_home = sum(
        (_take_home(entitlement.gross, rules, report.day) for entitlement in report.paid), nothing
    )
    return IncomeFigures(gross, report.tax, gross - report.tax, take_home)


def _take_home(gross: Money, rules: MarketRules, on: date) -> Money:
    """What the full dividend tax on *on* leaves of *gross* (decision 2)."""
    return gross - rules.dividend_tax(gross, reinvested_by_deadline=False, on=on)


def _per_month(amount: Money) -> Money:
    """A year's *amount* as a monthly figure, rounded down."""
    return Money(amount.amount // _MONTHS, amount.currency)


def _ratio(numerator: Money, denominator: Money) -> Decimal | None:
    if denominator.amount == 0:
        return None
    return _rounded(_CONTEXT.divide(numerator.amount, denominator.amount))


def _rounded(value: Decimal) -> Decimal:
    return value.quantize(RATIO_PLACES, context=_CONTEXT)


def _months(first: date, last: date) -> Iterator[date]:
    """The first day of every calendar month from *first*'s to *last*'s."""
    month = first.replace(day=1)
    while month <= last:
        yield month
        month = date(month.year + month.month // _MONTHS, month.month % _MONTHS + 1, 1)
```

**`packages/steadyhand/src/steadyhand/notes.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/notes.py -->
```python
"""Notes: a stable key and a sentence, for anything a report says beyond its figures (M4 spec §7).

A key is a dotted lowercase identifier that is never reworded, so the training sub-project can
attach a lesson to it; the text is free to change. Every key is a constant below, named after its
value, and every ``Note`` in the engine is built from one of them, never from a literal
(``tests/meta/test_note_keys.py``). This module imports nothing from the rest of the engine, so
any engine module can use it without an import cycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from steadyhand._validate import require_type

INCOME_GROWTH_SHORT_HISTORY = "income.growth.short_history"
"""A holding whose dividend growth could not be measured, which therefore counts as 0%."""

INCOME_PROJECTION_COSTS_IGNORED = "income.projection.costs_ignored"
"""On every projection: the trading costs of reinvesting are left out."""

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")


@dataclass(frozen=True, slots=True)
class Note:
    """Something a report says in words, under a key that never changes."""

    key: str
    text: str

    def __post_init__(self) -> None:
        require_type(self.key, str, "key")
        require_type(self.text, str, "text")
        if _KEY.fullmatch(self.key) is None:
            msg = f"a note key is a dotted lowercase identifier, got {self.key!r}"
            raise ValueError(msg)
        if not self.text.strip():
            msg = f"the note {self.key} has no text"
            raise ValueError(msg)
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=812 passed=812 -->
Expected: every command exits 0; 812 passed, 100% branch coverage; the performance test passes.

- [ ] **Step 7: Mutations.** Run M83–M97; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S3 notes, measured dividend growth and the projection`, ending in the story's issue number as `(#N)`).

---

### Task 4: S4 The income report, the goal tracker and the backtester's income

**Acceptance criteria (story text):**
1. `goal_progress(goal, received, rate) -> GoalProgress`: the target, the monthly average take-home received and the run-rate's monthly take-home, each with its share of the target, not capped at 1 (M4 §5.4).
2. `income_report(reports, final, history, rules, settings) -> IncomeReport`, as of the last report's day: received income, run-rate (with the settings' pay lag), calendar, growth, the projection from the last day's holdings' value (idle cash is not assumed invested), and the goal tracker. A goal in another currency than the portfolio raises `CurrencyMismatchError`; a year window reaching before the rules' first day raises their `UnsupportedDateError` (Review Focus 4).
3. `BacktestSettings` gains `goal: IncomeGoal | None = None`, in the capital's currency. With a goal, after both runs, the backtester fetches each final holding's corporate actions from `years_before(as_of, HISTORY_YEARS)` (`HISTORY_YEARS = 5`) to `as_of` through `market.source` and attaches an `IncomeReport` to each `RunResult.income`; a `DataUnavailableError` stops the backtest. `BacktestResult.income_impact` is an `IncomeImpact(received, run_rate)`, the strategy's monthly take-home figures minus the baseline's, when there is a goal and a baseline, and `None` otherwise.
4. The golden run reads the five-year recordings, sets a goal of Rp1,000,000 a month and pins its income report; every figure the S9 golden file pinned is unchanged (Step 6 checks it). The golden test checks the recordings reach five years back and that the run-rate's dividends match what the engine paid (BBCA's across its split); the truncation check runs without a goal (scope decision 15). The year-long recordings are deleted.
5. The ten-year performance test sets a goal, and both runs' income reports stay inside its 30 s budget, with a run-rate to project (scope decision 16).
6. The engine exports the new names. Every gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M98–M103 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand/income.py`, `.../steadyhand/backtest.py`, `.../steadyhand/__init__.py`, `scripts/record_golden.py`, `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` (generated)
- Delete: `tests/fixtures/yahoo/{ASII,BBCA,BBRI,TLKM,UNVR}.JK_2021-02-01_2022-01-31.json`
- Test: create `tests/engine/test_income_report.py`; modify `tests/engine/test_backtest.py`, `tests/golden/test_golden_backtest.py`, `tests/perf/test_performance.py`

**Interfaces:**
- Consumes: every earlier task's function; M3's `backtest`, `RunResult`, `BacktestResult`, `DataSource.corporate_actions`.
- Produces: `HISTORY_YEARS = 5`; `GoalProgress(target, received: Money, received_share: Decimal, run_rate: Money, run_rate_share: Decimal)`; `IncomeReport(as_of, received, run_rate, calendar, growth, projection, goal)`; `income_report(...) -> IncomeReport`; `goal_progress(goal: IncomeGoal, received: ReceivedIncome, rate: RunRate) -> GoalProgress`; `BacktestSettings(capital, engine=EngineSettings(), goal: IncomeGoal | None = None)`; `RunResult.income: IncomeReport | None = None`; `IncomeImpact(received: Money, run_rate: Money)`; `BacktestResult.income_impact: IncomeImpact | None = None`. M5's `report --income` renders `IncomeReport`.

- [ ] **Step 1: Branch.** `git switch -c m4/s4-income-report origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_backtest.py`** (changed: 4 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
"""backtest: the pre-flight checks, the fetch, refused days, halts and the baseline (M3 spec §7)."""

```
with:
```python
"""backtest: the pre-flight checks, the fetch, refused days, halts, the baseline (M3 spec §7), and
the income reports and income impact when a goal is set (M4 spec §8)."""

```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    BacktestSettings,
    Market,
```
with:
```python
    BacktestSettings,
    IncomeImpact,
    Market,
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
)
from steadyhand.data import DataUnavailableError, UnavailableDaysError
from steadyhand.engine import DataValidationError, EngineSettings
from steadyhand.market import UnsupportedDateError
from steadyhand.metrics import measure
from steadyhand.money import IDR, Currency, Money
from steadyhand.risk import RiskLimits
```
with:
```python
)
from steadyhand.corporate import Entitlement
from steadyhand.data import DataUnavailableError, UnavailableDaysError
from steadyhand.engine import DataValidationError, EngineSettings
from steadyhand.income import IncomeGoal
from steadyhand.market import UnsupportedDateError
from steadyhand.metrics import measure
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.risk import RiskLimits
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    assert result.warnings == ()
```
with:
```python
    assert result.warnings == ()


# Dividends from before the run, which only an income report's history fetch reaches.
EARLIER: list[CorporateAction] = [
    CashDividend(BBCA, date(2025, 4, 21), Decimal(100)),
    CashDividend(BBRI, date(2025, 3, 20), Decimal(50)),
]
# Five years before the last day, Friday 11 July 2025.
HISTORY_FROM = date(2020, 7, 11)


def with_goal(contribution: int | None = None, lag: int = 14) -> BacktestSettings:
    limits = RiskLimits(max_weight=Decimal("0.5"))
    top_up = None if contribution is None else rp(contribution)
    engine = EngineSettings(limits=limits, monthly_contribution=top_up, pay_lag_trading_days=lag)
    return BacktestSettings(rp(100_000_000), engine, IncomeGoal(rp(1_000_000)))


def monthly_take_home(gross: int) -> int:
    """A year's gross less 10% tax, rounded up, over 12 months, rounded down."""
    return (gross - -(-gross // 10)) // 12


def test_without_a_goal_there_is_no_income_report_and_no_history_fetch() -> None:
    source = _Source(calm(), EARLIER)
    result = run(source)
    assert result.baseline is not None
    assert (result.run.income, result.baseline.income, result.income_impact) == (None, None, None)
    assert [request for request in source.requests if request[2] < START] == []


def test_with_a_goal_each_run_reports_its_income_from_five_years_of_history() -> None:
    source = _Source(calm(), EARLIER)
    result = run(source, chosen=with_goal(lag=3))
    assert result.baseline is not None
    # The strategy ends holding BBCA; the baseline BBCA and BBRI. Each is asked for once a run.
    assert [request for request in source.requests if request[2] < START] == [
        ("actions", "BBCA", HISTORY_FROM, END),
        ("actions", "BBCA", HISTORY_FROM, END),
        ("actions", "BBRI", HISTORY_FROM, END),
    ]
    ours, theirs = result.run.income, result.baseline.income
    assert ours is not None
    assert theirs is not None
    assert ours.as_of == theirs.as_of == END
    held = {p.instrument: p.quantity for p in result.baseline.final.holdings.portfolio.positions}
    shares = result.run.final.holdings.portfolio.positions[0].quantity
    # Three trading days after Monday 21 April 2025 is Thursday 24 April, with the run's lag.
    assert ours.run_rate.holdings[0].dividends == (
        Entitlement(BBCA, date(2025, 4, 21), date(2025, 4, 24), rp(100 * shares)),
    )
    baseline_gross = 100 * held[BBCA] + 50 * held[BBRI]
    assert theirs.run_rate.annual_gross == rp(baseline_gross)
    # Neither run was paid a dividend, so only the run-rates differ.
    assert result.income_impact == IncomeImpact(
        rp(0), rp(monthly_take_home(100 * shares) - monthly_take_home(baseline_gross))
    )


def test_the_income_report_projects_with_the_engines_contribution() -> None:
    result = run(_Source(calm(), EARLIER), chosen=with_goal(contribution=5_000_000))
    assert result.run.income is not None
    assert result.run.income.projection.contribution == rp(5_000_000)


def test_a_buy_and_hold_backtest_with_a_goal_has_no_income_impact() -> None:
    result = run(_Source(calm(), EARLIER), strategy=BuyAndHold(), chosen=with_goal())
    assert result.baseline is None
    assert result.run.income is not None
    assert result.income_impact is None


class _NoHistory(_Source):
    """A source with the run's own days and nothing before them."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        if start < START:
            msg = f"{instrument.symbol}: no history before {START.isoformat()}"
            raise DataUnavailableError(msg)
        return super().corporate_actions(instrument, start, end)


def test_history_the_source_cannot_give_stops_the_backtest() -> None:
    with pytest.raises(DataUnavailableError, match=r"^BBCA: no history before 2025-06-30$"):
        run(_NoHistory(calm()), chosen=with_goal())


def test_a_goal_is_an_income_goal_in_the_capitals_currency() -> None:
    with pytest.raises(TypeError, match=r"^goal must be an IncomeGoal, got Money$"):
        BacktestSettings(rp(1), EngineSettings(), rp(1))  # type: ignore[arg-type]
    dollars = IncomeGoal(Money(100, Currency("USD", 2)))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        BacktestSettings(rp(1), EngineSettings(), dollars)
```

**`tests/engine/test_income_report.py`** (new)

<!-- file: tests/engine/test_income_report.py -->
```python
"""income_report and goal_progress: the report assembled, and the goal tracker (M4 §3.2, §5.4).

Every expected number is worked out by hand in the test, never by the code under test. IDX taxes
a dividend at 10%, rounded up to the rupiah. Each part of the report has its own tests; these
check that the report puts the right inputs into each part.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.income import (
    GROWTH_YEARS,
    HISTORY_YEARS,
    GoalProgress,
    IncomeFigures,
    IncomeGoal,
    IncomeSettings,
    ProjectionOutcome,
    ReceivedIncome,
    RunRate,
    dividend_growth,
    goal_progress,
    income_report,
    payment_calendar,
    project,
    received_income,
    run_rate,
    years_before,
)
from steadyhand.market import UnsupportedDateError
from steadyhand.metrics import year_window_start
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import Portfolio
from steadyhand.types import CashDividend, CorporateAction, Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

BBCA = Instrument("BBCA", "IDX", IDR)
USD = Currency("USD", 2)
AS_OF = date(2025, 7, 7)
BOUGHT = date(2024, 1, 2)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def report(
    day: date, *, paid: Sequence[Entitlement] = (), tax: int = 0, holdings: int = 900_000
) -> DayReport:
    return DayReport(
        day=day,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=tuple(paid),
        tax=rp(tax),
        daily_cost=rp(0),
        deposit=rp(0),
        frozen=(),
        halt=None,
        settled=rp(100_000),
        unsettled=rp(0),
        holdings_value=rp(holdings),
        value=rp(holdings + 100_000),
        unit_price=Decimal(1),
        warnings=(),
    )


def final(shares: int = 1_000) -> EngineState:
    order = Order(BBCA, Side.BUY, shares, BOUGHT)
    fill = Fill(order, BOUGHT, shares, rp(900), Costs.zero(IDR))
    book = Portfolio.empty(IDR).deposit(rp(shares * 900), BOUGHT).apply_fill(fill, BOUGHT)
    return EngineState(Holdings(book))


def history() -> dict[Instrument, Sequence[CorporateAction]]:
    return {
        BBCA: [
            CashDividend(BBCA, date(2021, 4, 19), Decimal(40)),
            CashDividend(BBCA, date(2025, 4, 21), Decimal(50)),
        ]
    }


def run() -> list[DayReport]:
    pay = date(2025, 5, 14)
    paid = Entitlement(BBCA, date(2025, 4, 21), pay, rp(50_000))
    return [report(pay, paid=[paid], tax=5_000), report(AS_OF)]


def test_the_report_gathers_every_part_as_of_the_last_day() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)), rp(1_000), pay_lag_trading_days=3)
    got = income_report(run(), final(), history(), rules(), settings)
    rate = run_rate(final().holdings.portfolio, history(), rules(), AS_OF, 3)
    growth = dividend_growth(rate, history())
    received = received_income(run(), final(), rules())
    assert got.as_of == AS_OF
    assert got.received == received
    assert got.run_rate == rate
    assert got.calendar == payment_calendar(rate, rules())
    assert got.growth == growth
    assert got.projection == project(rate, growth, rp(900_000), settings, rules())
    assert got.goal == goal_progress(settings.goal, received, rate)
    # By hand: 50 x 1,000 = 50,000 a year, (50,000 - 5,000) / 12 = 3,750 a month; received
    # the same 45,000 of take-home, 3,750 a month; 3,750 / 10,000 = 0.375 of the goal.
    assert got.goal == GoalProgress(
        rp(10_000), rp(3_750), Decimal("0.375"), rp(3_750), Decimal("0.375")
    )


def test_the_projection_starts_from_the_holdings_not_the_idle_cash() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    idle = [*run()[:-1], report(AS_OF, holdings=0)]
    got = income_report(idle, final(), history(), rules(), settings)
    assert {s.outcome for s in got.projection.scenarios} == {ProjectionOutcome.CANNOT}


def test_the_calendar_pays_after_the_settings_pay_lag() -> None:
    # 21 April 2025 plus 3 trading days is 24 April; plus 14 is 14 May.
    goal = IncomeGoal(rp(10_000))
    short = income_report(run(), final(), history(), rules(), IncomeSettings(goal))
    quick = IncomeSettings(goal, pay_lag_trading_days=3)
    shorter = income_report(run(), final(), history(), rules(), quick)
    assert short.calendar.months.index(max(short.calendar.months)) == 4
    assert shorter.calendar.months.index(max(shorter.calendar.months)) == 3


def test_a_goal_in_another_currency_than_the_portfolio_is_refused() -> None:
    dollars = IncomeSettings(IncomeGoal(Money(100, USD)))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        income_report(run(), final(), history(), rules(), dollars)


def test_a_run_with_no_days_has_no_income_report() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    with pytest.raises(ValueError, match=r"^a run with no days has no income report$"):
        income_report([], final(), history(), rules(), settings)


def test_a_year_window_before_the_rules_first_day_is_refused_not_guessed() -> None:
    # A report on 30 June 2021 reads the dividends back to 1 July 2020, and IDX's rules start on
    # 1 January 2021: the pay month of a dividend on 8 December 2020 is not known.
    early: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [CashDividend(BBCA, date(2020, 12, 8), Decimal(50))]
    }
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    with pytest.raises(
        UnsupportedDateError, match=r"^steadyhand's IDX rules are primary-verified from 2021-01-01"
    ):
        income_report([report(date(2021, 6, 30))], final(), early, rules(), settings)


def test_a_holding_without_history_stops_the_report() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    with pytest.raises(ValueError, match=r"^BBCA: no dividend history was passed for a stock"):
        income_report(run(), final(), {}, rules(), settings)


def figures(take_home: int) -> IncomeFigures:
    return IncomeFigures(rp(0), rp(0), rp(0), rp(take_home))


def test_goal_shares_are_not_capped_at_one() -> None:
    received = ReceivedIncome(AS_OF, (), figures(3_000), figures(250), None, None)
    rate = RunRate(AS_OF, (), rp(16_667), rp(1_250))
    progress = goal_progress(IncomeGoal(rp(1_000)), received, rate)
    # 250 / 1,000 received; 1,250 / 1,000 at the run-rate: past the goal, and reported as such.
    assert progress == GoalProgress(rp(1_000), rp(250), Decimal("0.25"), rp(1_250), Decimal("1.25"))


def test_goal_progress_refuses_a_goal_in_another_currency() -> None:
    received = ReceivedIncome(AS_OF, (), figures(3_000), figures(250), None, None)
    rate = RunRate(AS_OF, (), rp(16_667), rp(1_250))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine USD with IDR$"):
        goal_progress(IncomeGoal(Money(100, USD)), received, rate)


def test_five_years_of_history_hold_every_window_the_report_reads() -> None:
    assert (HISTORY_YEARS, GROWTH_YEARS) == (5, 4)
    # The oldest window read is growth's earlier one: from 8 July 2020 to 7 July 2021. Five
    # years of history start on 7 July 2020, a day before it.
    assert year_window_start(years_before(AS_OF, GROWTH_YEARS)) == date(2020, 7, 8)
    assert years_before(AS_OF, HISTORY_YEARS) == date(2020, 7, 7)
```

**`tests/golden/test_golden_backtest.py`** (changed: 4 edits)

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
through the real ``YahooDataSource``, ``CachedDataSource``, ``IdxMarketRules`` and engine. Its
result must equal the stored file exactly, in integer rupiah. After a change that moves the
numbers on purpose, re-record with ``uv run python scripts/record_golden.py`` and review the diff.

```
with:
```python
through the real ``YahooDataSource``, ``CachedDataSource``, ``IdxMarketRules`` and engine. Its
result, its income report included, must equal the stored file exactly, in integer rupiah.
After a change that moves the numbers on purpose, re-record with
``uv run python scripts/record_golden.py`` and review the diff.

```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
import pytest
from record_golden import GOLDEN, main, record, run, summary

from steadyhand import STRATEGIES
from steadyhand_idx import IdxMarketRules
```
with:
```python
import pytest
from record_golden import END, GOLDEN, HISTORY_START, STOCKS, main, record, recorded, run, summary

from steadyhand import HISTORY_YEARS, IDR, STRATEGIES, Money, years_before
from steadyhand_idx import IdxMarketRules
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
def test_a_fetch_outside_the_recording_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^ASII\.JK: the fixture covers 2021-02-01 to 2022-01-31"):
        run(tmp_path, end=date(2022, 2, 7))

```
with:
```python
def test_a_fetch_outside_the_recording_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^ASII\.JK: the fixture covers 2017-01-31 to 2022-01-31"):
        run(tmp_path, end=date(2022, 2, 7))
    with pytest.raises(
        ValueError, match=r"^ASII\.JK: the fixture covers 2017-01-31 to 2022-01-31, not 2017-01-30"
    ):
        recorded("ASII.JK", date(2017, 1, 30), END)


def test_the_recordings_reach_five_years_before_the_run_ends() -> None:
    # Growth reads a year window four years back, so five years of history must be there.
    assert years_before(END, HISTORY_YEARS) == HISTORY_START
    for stock in STOCKS:
        rows = recorded(f"{stock}.JK", HISTORY_START, END).rows
        assert (rows[0].day, rows[-1].day) == (HISTORY_START, END), stock


def test_the_income_report_agrees_with_what_the_engine_paid(tmp_path: Path) -> None:
    result = run(tmp_path)
    income = result.run.income
    assert income is not None
    paid = {
        (e.instrument.symbol, e.ex_date): e for report in result.run.reports for e in report.paid
    }
    expected = [dividend for held in income.run_rate.holdings for dividend in held.dividends]
    # Every dividend of the trailing year was paid in the run, on the pay date the calendar uses.
    assert len(expected) == len(paid) == 7
    assert all(e.pay_date == paid[(e.instrument.symbol, e.ex_date)].pay_date for e in expected)
    # BBCA's 2021-04-08 dividend: Rp432 a share on the 700 shares held before the 1-for-5 split,
    # and Rp86.4 a share, restated, on the 3,500 held after it. Rp302,400 either way.
    bbca = paid[("BBCA", date(2021, 4, 8))]
    assert bbca.gross == Money(302_400, IDR)
    assert bbca in expected

```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    # day before UNVR's ex-date; each longer run goes on for twenty more trading days.
    short = run(tmp_path / "short", strategy, cut)
    longer = run(tmp_path / "long", strategy, _trading_days_after(cut, 20))
    count = len(short.run.reports)
```
with:
```python
    # day before UNVR's ex-date; each longer run goes on for twenty more trading days.
    # Decisions only: an income report reads no bar after its day, and a run cut this early
    # would need history from before the recordings start.
    short = run(tmp_path / "short", strategy, cut, income=False)
    longer = run(tmp_path / "long", strategy, _trading_days_after(cut, 20), income=False)
    count = len(short.run.reports)
```

**`tests/perf/test_performance.py`** (changed: 6 edits)

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
    EngineSettings,
    Instrument,
```
with:
```python
    EngineSettings,
    IncomeGoal,
    Instrument,
```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
class _Synthetic:
    """Ten years of daily bars and one June dividend a year for each stock, from ``SEED``."""

```
with:
```python
class _Synthetic:
    """Ten years of daily bars and a dividend each year on the first weekday from 15 June, for
    each stock, from ``SEED``. Every year pays, so the last year gives a run-rate to project."""

```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
            actions: list[CorporateAction] = []
            for day in trading:
```
with:
```python
            actions: list[CorporateAction] = []
            paid: set[int] = set()
            for day in trading:
```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
                )
                if day.month == 6 and day.day == 15:
                    actions.append(CashDividend(stock, day, Decimal(close // 50)))
```
with:
```python
                )
                if (day.month, day.day) >= (6, 15) and day.year not in paid:
                    paid.add(day.year)
                    actions.append(CashDividend(stock, day, Decimal(close // 50)))
```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
    settings = BacktestSettings(
        Money(1_000_000_000, IDR), EngineSettings(monthly_contribution=Money(10_000_000, IDR))
    )
```
with:
```python
    settings = BacktestSettings(
        Money(1_000_000_000, IDR),
        EngineSettings(monthly_contribution=Money(10_000_000, IDR)),
        IncomeGoal(Money(50_000_000, IDR)),
    )
```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
    assert all(run.metrics.dividends.gross.amount > 0 for run in runs)
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"
```
with:
```python
    assert all(run.metrics.dividends.gross.amount > 0 for run in runs)
    # Each run's income report, from five years of history, is inside the same budget, and its
    # projection had a run-rate to simulate.
    assert all(
        run.income is not None and run.income.run_rate.annual_gross.amount > 0 for run in runs
    )
    assert result.income_impact is not None
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"
```


- [ ] **Step 3: Write the stubs.** New names only; everything that existed keeps its current body, the recorder's `run` and `settings` included.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed, rewritten whole)

<!-- file: packages/steadyhand/src/steadyhand/__init__.py -->
```python
"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

from steadyhand.backtest import (
    BacktestResult,
    BacktestSettings,
    IncomeImpact,
    Market,
    NoTradingDaysError,
    RunResult,
    UniverseCoverageError,
    backtest,
)
from steadyhand.broker import Broker, FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import (
    PAY_LAG_TRADING_DAYS,
    CorporateOutcome,
    Entitlement,
    Holdings,
    apply_actions,
)
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
from steadyhand.disclaimer import DISCLAIMER
from steadyhand.engine import (
    DataValidationError,
    DayInputs,
    DayOrderError,
    DayReport,
    EngineSettings,
    EngineState,
    run_day,
)
from steadyhand.income import (
    BASE_GROWTH_CAP,
    GROWTH_YEARS,
    HISTORY_YEARS,
    OPTIMISTIC_GROWTH_CAP,
    PESSIMISTIC_START,
    PROJECTION_LABEL,
    PROJECTION_MONTHS,
    DividendGrowth,
    GoalProgress,
    HoldingCalendar,
    HoldingGrowth,
    HoldingRunRate,
    IncomeFigures,
    IncomeGoal,
    IncomeReport,
    IncomeSettings,
    MonthlyIncome,
    PaymentCalendar,
    Projection,
    ProjectionOutcome,
    ReceivedIncome,
    RunRate,
    Scenario,
    ScenarioProjection,
    dividend_growth,
    goal_progress,
    income_report,
    payment_calendar,
    project,
    received_income,
    run_rate,
    years_before,
)
from steadyhand.market import MarketRules, UnsupportedDateError, add_trading_days
from steadyhand.metrics import (
    RATIO_PLACES,
    YEAR_DAYS,
    CostBreakdown,
    DividendTotals,
    Drawdown,
    Metrics,
    measure,
    year_window_start,
)
from steadyhand.money import (
    IDR,
    MAX_MINOR_UNITS,
    Currency,
    CurrencyMismatchError,
    Money,
    Rounding,
)
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import (
    CashMovement,
    ChronologyError,
    InsufficientCashError,
    InsufficientSharesError,
    MissingPriceError,
    MovementKind,
    NegativeProceedsError,
    Portfolio,
)
from steadyhand.risk import Checked, Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.strategies import (
    STRATEGIES,
    BuyAndHold,
    Decision,
    InvalidWeightsError,
    Memory,
    Strategy,
)
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Fill,
    Instrument,
    InvalidBarError,
    Order,
    OrderAck,
    OtherAction,
    Position,
    Side,
    Split,
)
from steadyhand.universe import Universe
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

__version__: str = version("steadyhand")

__all__ = [
    "BASE_GROWTH_CAP",
    "DISCLAIMER",
    "GROWTH_YEARS",
    "HISTORY_YEARS",
    "IDR",
    "INCOME_GROWTH_SHORT_HISTORY",
    "INCOME_PROJECTION_COSTS_IGNORED",
    "MAX_MINOR_UNITS",
    "OPTIMISTIC_GROWTH_CAP",
    "PAY_LAG_TRADING_DAYS",
    "PESSIMISTIC_START",
    "PROJECTION_LABEL",
    "PROJECTION_MONTHS",
    "RATIO_PLACES",
    "STRATEGIES",
    "YEAR_DAYS",
    "BacktestResult",
    "BacktestSettings",
    "Bar",
    "Broker",
    "BuyAndHold",
    "CashDividend",
    "CashMovement",
    "Checked",
    "ChronologyError",
    "CompoundingSizer",
    "CorporateAction",
    "CorporateOutcome",
    "CostBreakdown",
    "Costs",
    "Currency",
    "CurrencyMismatchError",
    "Cut",
    "DataSource",
    "DataUnavailableError",
    "DataValidationError",
    "DayInputs",
    "DayOrderError",
    "DayReport",
    "Decision",
    "DividendGrowth",
    "DividendTotals",
    "Drawdown",
    "EngineSettings",
    "EngineState",
    "Entitlement",
    "Fill",
    "FillResult",
    "FillSettings",
    "GoalProgress",
    "Halt",
    "HoldingCalendar",
    "HoldingGrowth",
    "HoldingRunRate",
    "Holdings",
    "IncomeFigures",
    "IncomeGoal",
    "IncomeImpact",
    "IncomeReport",
    "IncomeSettings",
    "Instrument",
    "InsufficientCashError",
    "InsufficientSharesError",
    "InvalidBarError",
    "InvalidWeightsError",
    "LookAheadError",
    "Market",
    "MarketRules",
    "MarketView",
    "Memory",
    "Metrics",
    "MissingPriceError",
    "Money",
    "MonthlyIncome",
    "MovementKind",
    "NegativeProceedsError",
    "NoTradingDaysError",
    "Note",
    "Opening",
    "Order",
    "OrderAck",
    "OtherAction",
    "PaymentCalendar",
    "Portfolio",
    "PortfolioView",
    "Position",
    "PriceHistory",
    "Projection",
    "ProjectionOutcome",
    "ReceivedIncome",
    "Rejected",
    "RiskLimits",
    "RiskManager",
    "Rounding",
    "RunRate",
    "RunResult",
    "Scenario",
    "ScenarioProjection",
    "Side",
    "SimulatedBroker",
    "Sizer",
    "Split",
    "Strategy",
    "Tradable",
    "UnavailableDaysError",
    "UnitValue",
    "Universe",
    "UniverseCoverageError",
    "UnsupportedDateError",
    "__version__",
    "add_trading_days",
    "apply_actions",
    "backtest",
    "dividend_growth",
    "goal_progress",
    "income_report",
    "measure",
    "payment_calendar",
    "project",
    "received_income",
    "run_day",
    "run_rate",
    "year_window_start",
    "years_before",
]
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed, rewritten whole)

<!-- file: packages/steadyhand/src/steadyhand/backtest.py -->
```python
"""The backtester: a strategy and the ``buy-and-hold`` baseline over a range of days (M3 spec §7).

``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, then repeats ``run_day`` over the trading days: once for the strategy and once, with the
same settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work. With an income goal
set, each run also gets an income report on its last day, from dividend history fetched then.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from steadyhand._validate import require_date, require_type
from steadyhand.data import DataSource, UnavailableDaysError
from steadyhand.engine import DayInputs, DayReport, EngineSettings, EngineState, run_day
from steadyhand.income import (
    HISTORY_YEARS,
    IncomeGoal,
    IncomeReport,
    IncomeSettings,
    income_report,
    years_before,
)
from steadyhand.market import MarketRules
from steadyhand.metrics import Metrics, measure
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.risk import Halt
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy
from steadyhand.types import Bar, CorporateAction, Instrument
from steadyhand.universe import Universe
from steadyhand.view import PriceHistory


class UniverseCoverageError(LookupError):
    """The backtest starts before the universe's first known membership (M3 spec, decision 3)."""

    def __init__(self, start: date, first: date) -> None:
        super().__init__(
            f"the backtest starts on {start.isoformat()}, but the universe's membership is only "
            f"known from {first.isoformat()}; start on {first.isoformat()} or later"
        )


class NoTradingDaysError(ValueError):
    """The range holds no trading day, so there is nothing to run."""


@dataclass(frozen=True, slots=True)
class Market:
    """Where a backtest's world comes from: the stocks it may hold, their data, and the rules."""

    universe: Universe
    source: DataSource
    rules: MarketRules

    def __post_init__(self) -> None:
        require_type(self.universe, Universe, "universe")
        require_type(self.source, DataSource, "source")
        require_type(self.rules, MarketRules, "rules")


@dataclass(frozen=True, slots=True)
class BacktestSettings:
    """The capital a run starts with, how the engine runs each day, and an optional income goal.

    Both runs share them. With a ``goal``, each run's result carries an income report.
    """

    capital: Money
    engine: EngineSettings = field(default_factory=EngineSettings)
    goal: IncomeGoal | None = None

    def __post_init__(self) -> None:
        require_type(self.capital, Money, "capital")
        require_type(self.engine, EngineSettings, "engine")
        if self.capital.amount <= 0:
            msg = f"the starting capital must be positive, got {self.capital}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RunResult:
    """One strategy's run: every day's report, in order, the state after the last day, what the
    run achieved (M3 spec §8), and its income report when the settings set a goal (M4 spec §8)."""

    strategy: str
    reports: tuple[DayReport, ...]
    final: EngineState
    metrics: Metrics
    income: IncomeReport | None = None

    @property
    def halt(self) -> Halt | None:
        """The halt that stopped ordering, which lasts to the end of the run (decision 4)."""
        return self.final.halt

    @property
    def warnings(self) -> tuple[str, ...]:
        """Every day's warnings, in day order."""
        return tuple(warning for report in self.reports for warning in report.warnings)


@dataclass(frozen=True, slots=True)
class IncomeImpact:
    """The strategy's monthly take-home income minus the baseline's (core spec §7).

    ``received`` compares the monthly averages over the trailing year and ``run_rate`` the
    run-rates. Each is negative when the strategy earns less than ``buy-and-hold``.
    """

    received: Money
    run_rate: Money


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The strategy's run and, unless the strategy is the baseline, the baseline's.

    ``warnings`` are about the data both runs share: gaps in the universe's membership record,
    and each stock whose data source refused some of its days. ``income_impact`` is set when
    there is a goal and a baseline.
    """

    start: date
    end: date
    run: RunResult
    baseline: RunResult | None
    warnings: tuple[str, ...]
    income_impact: IncomeImpact | None = None


@dataclass(frozen=True, slots=True)
class _Window:
    """Everything both runs read: the trading days, the universe on each, and the fetched data."""

    days: tuple[date, ...]
    members: Mapping[date, frozenset[Instrument]]
    excluded: Mapping[date, Mapping[Instrument, str]]
    history: PriceHistory
    actions: Mapping[date, tuple[CorporateAction, ...]]
    refused: Mapping[Instrument, tuple[date, ...]]


def backtest(
    strategy: Strategy, market: Market, start: date, end: date, settings: BacktestSettings
) -> BacktestResult:
    """Run *strategy* and the baseline from *start* to *end*, both inclusive (M3 spec §7.1)."""
    require_type(market, Market, "market")
    require_date(start, "start")
    require_date(end, "end")
    require_type(settings, BacktestSettings, "settings")
    if end < start:
        msg = f"the backtest ends on {end.isoformat()}, before it starts on {start.isoformat()}"
        raise ValueError(msg)
    rules = market.rules
    if settings.capital.currency != rules.currency:
        msg = (
            f"the capital is in {settings.capital.currency.code}, "
            f"but the market trades in {rules.currency.code}"
        )
        raise ValueError(msg)
    rules.require_supported(start)
    first = market.universe.first_day()
    if start < first:
        raise UniverseCoverageError(start, first)
    days = tuple(day for day in _calendar_days(start, end) if rules.is_trading_day(day))
    if not days:
        msg = f"there is no trading day from {start.isoformat()} to {end.isoformat()}"
        raise NoTradingDaysError(msg)
    window = _fetch(market, days)
    run = _run(strategy, window, rules, settings)
    baseline = BuyAndHold()
    compared = None if strategy.name == baseline.name else _run(baseline, window, rules, settings)
    warnings = (*market.universe.survivorship_warnings(start, end), *_refused_warnings(window))
    return BacktestResult(start, end, run, compared, warnings)


def _calendar_days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _fetch(market: Market, days: tuple[date, ...]) -> _Window:
    """Fetch every stock the universe holds on any of *days*, over all of them (M3 spec §7.1).

    A stock whose source refuses some days is fetched again over the clean ranges around them.
    """
    members = {day: market.universe.members_on(day) for day in days}
    excluded = {day: market.universe.excluded_on(day) for day in days}
    source = market.source
    start, end = days[0], days[-1]
    bars: list[Bar] = []
    actions: list[CorporateAction] = []
    refused: dict[Instrument, tuple[date, ...]] = {}
    for stock in sorted(frozenset().union(*members.values()), key=lambda i: (i.market, i.symbol)):
        try:
            found = (source.bars(stock, start, end), source.corporate_actions(stock, start, end))
        except UnavailableDaysError as error:
            named = tuple(day for day in error.days if start <= day <= end)
            if not named:
                raise
            refused[stock] = named
            for low, high in _clean_ranges(days, frozenset(named)):
                bars += source.bars(stock, low, high)
                actions += source.corporate_actions(stock, low, high)
            continue
        bars += found[0]
        actions += found[1]
    by_day: dict[date, list[CorporateAction]] = {}
    for action in actions:
        by_day.setdefault(action.ex_date, []).append(action)
    grouped = {day: tuple(found) for day, found in by_day.items()}
    return _Window(days, members, excluded, PriceHistory(bars), grouped, refused)


def _clean_ranges(days: Sequence[date], refused: frozenset[date]) -> Iterator[tuple[date, date]]:
    """Each run of consecutive trading days holding no refused day, as its first and last day.

    Built from trading days, so a range that holds only a weekend or a holiday is never asked for.
    """
    run: list[date] = []
    for day in days:
        if day not in refused:
            run.append(day)
        elif run:
            yield run[0], run[-1]
            run = []
    if run:
        yield run[0], run[-1]


def _run(
    strategy: Strategy, window: _Window, rules: MarketRules, settings: BacktestSettings
) -> RunResult:
    state = EngineState.opening(settings.capital, window.days[0])
    reports: list[DayReport] = []
    for day in window.days:
        refused = frozenset(stock for stock, found in window.refused.items() if day in found)
        inputs = DayInputs(
            day,
            window.history,
            window.actions.get(day, ()),
            window.members[day],
            window.excluded[day],
            refused,
            _resumed(window, day) - refused,
        )
        state, report = run_day(state, inputs, strategy, rules, settings.engine)
        reports.append(report)
    return RunResult(strategy.name, tuple(reports), state, measure(reports, state))


def _with_income(
    run: RunResult, market: Market, settings: BacktestSettings, goal: IncomeGoal
) -> RunResult:
    """*run* with its income report, from each final holding's history as the source gives it.

    A source that cannot give it raises, and the backtest stops: an income report is never
    built on missing history (M4 spec §8).
    """
    raise NotImplementedError("_with_income")


def _impact(run: RunResult, baseline: RunResult | None) -> IncomeImpact | None:
    raise NotImplementedError("_impact")


def _resumed(window: _Window, day: date) -> frozenset[Instrument]:
    """Stocks with a refused day between their last bar and *day*: no usable previous close."""
    resumed: set[Instrument] = set()
    for stock, refused in window.refused.items():
        previous = window.history.before(stock, day)
        after = bisect_left(refused, previous.day) if previous is not None else 0
        if after < len(refused) and refused[after] < day:
            resumed.add(stock)
    return frozenset(resumed)


def _refused_warnings(window: _Window) -> list[str]:
    """One warning per stock, naming each span of consecutive refused trading days."""
    warnings: list[str] = []
    for stock in sorted(window.refused, key=lambda i: (i.market, i.symbol)):
        refused = window.refused[stock]
        spans: list[list[date]] = []
        for day in refused:
            if (
                spans
                and bisect_left(window.days, day) == bisect_left(window.days, spans[-1][-1]) + 1
            ):
                spans[-1].append(day)
            else:
                spans.append([day])
        named = ", ".join(
            span[0].isoformat()
            if len(span) == 1
            else f"{span[0].isoformat()} to {span[-1].isoformat()}"
            for span in spans
        )
        warnings.append(
            f"{stock.symbol}: the data source refused {len(refused)} day(s) ({named}), so it was "
            "not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited."
        )
    return warnings
```

**`packages/steadyhand/src/steadyhand/income.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
"""Dividend growth compares the trailing year with the year ending this many years earlier."""

```
with:
```python
"""Dividend growth compares the trailing year with the year ending this many years earlier."""

HISTORY_YEARS = 5
"""An income report needs each holding's corporate actions from this many years before its day,
which holds every window it reads (M4 spec §3.2)."""

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

def years_before(day: date, years: int) -> date:
```
with:
```python

@dataclass(frozen=True, slots=True)
class GoalProgress:
    """How far the income is from the goal (M4 spec §5.4).

    ``received`` is the monthly average take-home over the trailing year and ``run_rate`` the
    run-rate's monthly take-home; each share is that figure over the target, not capped at 1.
    """

    target: Money
    received: Money
    received_share: Decimal
    run_rate: Money
    run_rate_share: Decimal


@dataclass(frozen=True, slots=True)
class IncomeReport:
    """A run's dividend income, as of its last day: everything M5's ``report --income`` shows."""

    as_of: date
    received: ReceivedIncome
    run_rate: RunRate
    calendar: PaymentCalendar
    growth: DividendGrowth
    projection: Projection
    goal: GoalProgress


def income_report(
    reports: Sequence[DayReport],
    final: EngineState,
    history: Mapping[Instrument, Sequence[CorporateAction]],
    rules: MarketRules,
    settings: IncomeSettings,
) -> IncomeReport:
    """The income report of a run whose day reports, in order, are *reports* (M4 spec §3.2).

    *history* holds, for every stock in the final portfolio, its corporate actions with an
    ex-date from ``HISTORY_YEARS`` years before the last day to the last day. The caller fetches
    it; nothing here reads a file or the network.
    """
    raise NotImplementedError("income_report")


def goal_progress(goal: IncomeGoal, received: ReceivedIncome, rate: RunRate) -> GoalProgress:
    """The goal tracker: received and run-rate monthly take-home against the target (§5.4)."""
    raise NotImplementedError("goal_progress")


def years_before(day: date, years: int) -> date:
```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python

def _rounded(value: Decimal) -> Decimal:
```
with:
```python

def _share(part: Money, target: Money) -> Decimal:
    raise NotImplementedError("_share")


def _rounded(value: Decimal) -> Decimal:
```

**`scripts/record_golden.py`** (changed, new names stubbed: 4 edits)

<!-- edit: scripts/record_golden.py -->
Replace:
```python
runs ``buy-and-hold`` over the recorded Yahoo fixtures for ASII, BBCA, BBRI, TLKM and UNVR from
1 February 2021 to 31 January 2022, and writes everything the golden test pins to
``tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json``. The window holds BBCA's
1-for-5 split, seven cash dividends, and 146 days of BBRI prices that Yahoo cannot unadjust (its
rights issue). Run it only after a change that moves the numbers on purpose, and review the diff:
the file is never edited by hand.
"""
```
with:
```python
runs ``buy-and-hold`` over the recorded Yahoo fixtures for ASII, BBCA, BBRI, TLKM and UNVR from
1 February 2021 to 31 January 2022, with an income goal, and writes everything the golden test pins,
its income report included, to
``tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json``. The window holds BBCA's
1-for-5 split, seven cash dividends, and 146 days of BBRI prices that Yahoo cannot unadjust (its
rights issue). The recordings reach back to 31 January 2017, five years before the run ends, for
the income report's dividend growth (M4 spec §9). Run it only after a change that moves the
numbers on purpose, and review the diff: the file is never edited by hand.
"""
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    EngineSettings,
    Market,
```
with:
```python
    EngineSettings,
    IncomeFigures,
    IncomeGoal,
    IncomeReport,
    Market,
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
START, END = date(2021, 2, 1), date(2022, 1, 31)
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
RECORDED = date(2026, 9, 26)
"""The day the fixtures were recorded; the cache treats it as today."""
```
with:
```python
START, END = date(2021, 2, 1), date(2022, 1, 31)
HISTORY_START = date(2017, 1, 31)
"""Where the recordings start: five years before the run ends (M4 spec §9)."""
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
RECORDED = date(2026, 9, 27)
"""The day the fixtures were recorded; the cache treats it as today."""
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python

def record(folder: Path, golden: Path = GOLDEN) -> Path:
```
with:
```python

def _income(report: IncomeReport | None) -> object:
    """Every figure of an income report, as JSON values."""
    raise NotImplementedError("_income")


def _figures(figures: IncomeFigures) -> list[int]:
    raise NotImplementedError("_figures")


def record(folder: Path, golden: Path = GOLDEN) -> Path:
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=830 failed=20 -->
Expected: 830 run, 20 failed. Nine are `NotImplementedError`. The other eleven fail on their own assertions because `backtest`, `BacktestSettings` and the recorder keep their old bodies until Step 5: no history is fetched, no report is attached and no goal is checked (five in `test_backtest.py`), the recorder still reads the year-long files (`test_a_fetch_outside_the_recording_is_refused`, `test_the_recordings_reach_five_years_before_the_run_ends`, `test_the_income_report_agrees_with_what_the_engine_paid`), and its `run` does not yet take `income`, a `TypeError` in the three truncation checks. Two pass against the stubs by design: `test_without_a_goal_there_is_no_income_report_and_no_history_fetch` pins the old behaviour, and `test_five_years_of_history_hold_every_window_the_report_reads` pins constants and Task 3's functions.

- [ ] **Step 5: Implement.** Delete the year-long recordings with the implementation, not before: the red phase above still reads them.

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
            raise ValueError(msg)

```
with:
```python
            raise ValueError(msg)
        if self.goal is not None:
            require_type(self.goal, IncomeGoal, "goal")
            if self.goal.monthly_target.currency != self.capital.currency:
                raise CurrencyMismatchError(
                    self.capital.currency, self.goal.monthly_target.currency
                )

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    compared = None if strategy.name == baseline.name else _run(baseline, window, rules, settings)
    warnings = (*market.universe.survivorship_warnings(start, end), *_refused_warnings(window))
    return BacktestResult(start, end, run, compared, warnings)

```
with:
```python
    compared = None if strategy.name == baseline.name else _run(baseline, window, rules, settings)
    if settings.goal is not None:
        run = _with_income(run, market, settings, settings.goal)
        compared = (
            None if compared is None else _with_income(compared, market, settings, settings.goal)
        )
    warnings = (*market.universe.survivorship_warnings(start, end), *_refused_warnings(window))
    return BacktestResult(start, end, run, compared, warnings, _impact(run, compared))

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    """
    raise NotImplementedError("_with_income")


def _impact(run: RunResult, baseline: RunResult | None) -> IncomeImpact | None:
    raise NotImplementedError("_impact")

```
with:
```python
    """
    as_of = run.reports[-1].day
    since = years_before(as_of, HISTORY_YEARS)
    history = {
        position.instrument: tuple(
            market.source.corporate_actions(position.instrument, since, as_of)
        )
        for position in run.final.holdings.portfolio.positions
    }
    engine = settings.engine
    plan = IncomeSettings(goal, engine.monthly_contribution, engine.pay_lag_trading_days)
    income = income_report(run.reports, run.final, history, market.rules, plan)
    return replace(run, income=income)


def _impact(run: RunResult, baseline: RunResult | None) -> IncomeImpact | None:
    if baseline is None or run.income is None or baseline.income is None:
        return None
    ours, theirs = run.income.goal, baseline.income.goal
    return IncomeImpact(ours.received - theirs.received, ours.run_rate - theirs.run_rate)

```

**`packages/steadyhand/src/steadyhand/income.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    """
    raise NotImplementedError("income_report")

```
with:
```python
    """
    received = received_income(reports, final, rules)
    portfolio = final.holdings.portfolio
    target = settings.goal.monthly_target
    if target.currency != portfolio.currency:
        raise CurrencyMismatchError(portfolio.currency, target.currency)
    rate = run_rate(portfolio, history, rules, received.as_of, settings.pay_lag_trading_days)
    growth = dividend_growth(rate, history)
    return IncomeReport(
        received.as_of,
        received,
        rate,
        payment_calendar(rate, rules),
        growth,
        project(rate, growth, reports[-1].holdings_value, settings, rules),
        goal_progress(settings.goal, received, rate),
    )

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    """The goal tracker: received and run-rate monthly take-home against the target (§5.4)."""
    raise NotImplementedError("goal_progress")

```
with:
```python
    """The goal tracker: received and run-rate monthly take-home against the target (§5.4)."""
    target = goal.monthly_target
    got, expected = received.monthly_average.take_home, rate.monthly_take_home
    return GoalProgress(target, got, _share(got, target), expected, _share(expected, target))

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
def _share(part: Money, target: Money) -> Decimal:
    raise NotImplementedError("_share")

```
with:
```python
def _share(part: Money, target: Money) -> Decimal:
    if part.currency != target.currency:
        raise CurrencyMismatchError(target.currency, part.currency)
    return _rounded(_CONTEXT.divide(part.amount, target.amount))

```

**`scripts/record_golden.py`** (implemented: 6 edits)

<!-- edit: scripts/record_golden.py -->
Replace:
```python

def settings() -> BacktestSettings:
    """Rp100,000,000, and 25% a stock so that five stocks can be fully invested (M3 spec §9)."""
    limits = RiskLimits(max_weight=Decimal("0.25"))
    return BacktestSettings(Money(100_000_000, IDR), EngineSettings(limits=limits))

```
with:
```python

def settings(*, income: bool = True) -> BacktestSettings:
    """Rp100,000,000, 25% a stock so that five stocks can be fully invested (M3 spec §9), and a
    goal of Rp1,000,000 a month, so that the run carries an income report (M4 spec §9)."""
    limits = RiskLimits(max_weight=Decimal("0.25"))
    goal = IncomeGoal(Money(1_000_000, IDR)) if income else None
    return BacktestSettings(Money(100_000_000, IDR), EngineSettings(limits=limits), goal)

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    """Yahoo's recorded answer. A range outside the recording is refused, never invented."""
    if start < START or end > END:
        msg = f"{ticker}: the fixture covers {START} to {END}, not {start} to {end}"
        raise ValueError(msg)
    return history_from_json(FIXTURES / f"{ticker}_{START.isoformat()}_{END.isoformat()}.json")

```
with:
```python
    """Yahoo's recorded answer. A range outside the recording is refused, never invented."""
    if start < HISTORY_START or end > END:
        msg = f"{ticker}: the fixture covers {HISTORY_START} to {END}, not {start} to {end}"
        raise ValueError(msg)
    name = f"{ticker}_{HISTORY_START.isoformat()}_{END.isoformat()}.json"
    return history_from_json(FIXTURES / name)

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python

def run(folder: Path, strategy: str = "buy-and-hold", end: date = END) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules."""
    folder.mkdir(parents=True, exist_ok=True)
```
with:
```python

def run(
    folder: Path, strategy: str = "buy-and-hold", end: date = END, *, income: bool = True
) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules.

    Without *income* there is no goal, so no history is fetched before ``START``: an earlier
    *end* would need recordings from before ``HISTORY_START``.
    """
    folder.mkdir(parents=True, exist_ok=True)
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
        market = Market(universe(), source, IdxMarketRules())
        return backtest(STRATEGIES[strategy](), market, START, end, settings())

```
with:
```python
        market = Market(universe(), source, IdxMarketRules())
        return backtest(STRATEGIES[strategy](), market, START, end, settings(income=income))

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
        },
    }
```
with:
```python
        },
        "income": _income(outcome.income),
    }
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    """Every figure of an income report, as JSON values."""
    raise NotImplementedError("_income")


def _figures(figures: IncomeFigures) -> list[int]:
    raise NotImplementedError("_figures")

```
with:
```python
    """Every figure of an income report, as JSON values."""
    if report is None:
        return None
    received, rate, growth = report.received, report.run_rate, report.growth
    goal = report.goal
    return {
        "as_of": report.as_of.isoformat(),
        "received": {
            "by_month": [[m.month.isoformat(), *_figures(m.figures)] for m in received.by_month],
            "trailing": _figures(received.trailing),
            "monthly_average": _figures(received.monthly_average),
            "yields": [str(received.current_yield), str(received.yield_on_cost)],
        },
        "run_rate": {
            "holdings": [
                [
                    h.instrument.symbol,
                    h.shares,
                    h.annual_gross.amount,
                    h.monthly_take_home.amount,
                    [
                        [e.ex_date.isoformat(), e.pay_date.isoformat(), e.gross.amount]
                        for e in h.dividends
                    ],
                ]
                for h in rate.holdings
            ],
            "annual_gross": rate.annual_gross.amount,
            "monthly_take_home": rate.monthly_take_home.amount,
        },
        "calendar": {
            "months": [month.amount for month in report.calendar.months],
            "empty_months": report.calendar.empty_months,
            "evenness": str(report.calendar.evenness),
        },
        "growth": {
            "holdings": [
                [g.instrument.symbol, str(g.recent), str(g.earlier), str(g.growth)]
                for g in growth.holdings
            ],
            "portfolio": str(growth.portfolio),
            "notes": [[note.key, note.text] for note in growth.notes],
        },
        "projection": [
            [
                s.scenario.value,
                s.starting_gross.amount,
                str(s.growth),
                s.outcome.value,
                None if s.years is None else str(s.years),
            ]
            for s in report.projection.scenarios
        ],
        "goal": [
            goal.target.amount,
            goal.received.amount,
            str(goal.received_share),
            goal.run_rate.amount,
            str(goal.run_rate_share),
        ],
    }


def _figures(figures: IncomeFigures) -> list[int]:
    return [
        figures.gross.amount,
        figures.tax.amount,
        figures.net.amount,
        figures.take_home.amount,
    ]

```

Generate `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json sha256=7a3f05dcdac2908ada4b19421a9faadbd360b0339183ef0fc057c6a94ed29db9 -->
```bash
uv run python scripts/record_golden.py
```

Delete `tests/fixtures/yahoo/ASII.JK_2021-02-01_2022-01-31.json`, which nothing reads any more:

<!-- delete: tests/fixtures/yahoo/ASII.JK_2021-02-01_2022-01-31.json -->
```bash
git rm tests/fixtures/yahoo/ASII.JK_2021-02-01_2022-01-31.json
```

Delete `tests/fixtures/yahoo/BBCA.JK_2021-02-01_2022-01-31.json`, which nothing reads any more:

<!-- delete: tests/fixtures/yahoo/BBCA.JK_2021-02-01_2022-01-31.json -->
```bash
git rm tests/fixtures/yahoo/BBCA.JK_2021-02-01_2022-01-31.json
```

Delete `tests/fixtures/yahoo/BBRI.JK_2021-02-01_2022-01-31.json`, which nothing reads any more:

<!-- delete: tests/fixtures/yahoo/BBRI.JK_2021-02-01_2022-01-31.json -->
```bash
git rm tests/fixtures/yahoo/BBRI.JK_2021-02-01_2022-01-31.json
```

Delete `tests/fixtures/yahoo/TLKM.JK_2021-02-01_2022-01-31.json`, which nothing reads any more:

<!-- delete: tests/fixtures/yahoo/TLKM.JK_2021-02-01_2022-01-31.json -->
```bash
git rm tests/fixtures/yahoo/TLKM.JK_2021-02-01_2022-01-31.json
```

Delete `tests/fixtures/yahoo/UNVR.JK_2021-02-01_2022-01-31.json`, which nothing reads any more:

<!-- delete: tests/fixtures/yahoo/UNVR.JK_2021-02-01_2022-01-31.json -->
```bash
git rm tests/fixtures/yahoo/UNVR.JK_2021-02-01_2022-01-31.json
```


- [ ] **Step 6: Check the golden figures did not move.** Every value the S9 golden file pinned must be unchanged, with `income` the only addition:

  ```bash
  uv run python - <<'EOF'
  import json, subprocess
  path = "tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json"
  old = json.loads(subprocess.run(["git", "show", f"origin/develop:{path}"], capture_output=True, text=True, check=True).stdout)
  new = json.loads(open(path, encoding="utf-8").read())
  print(sorted(set(new) - set(old)), sorted(set(old) - set(new)), all(new[key] == old[key] for key in old), len(old))
  EOF
  ```

  Expected: `['income'] [] True 10`. Hand-checked income figures, from the recorded dividends: BBCA's run-rate is 86.4 (Rp432 before the 1-for-5 split) × 3,500 + 25 × 3,500 = Rp389,900 a year, and (389,900 − 38,990) ÷ 12 = Rp29,242 a month; June's calendar is TLKM's 1,293,677 − 129,368 plus UNVR's 360,000 − 36,000 = Rp1,488,309, and evenness is 1,488,309 ÷ 2,552,019 = 0.58318884; BBCA's growth windows hold 86.4 + 25 = 111.40 and 26 + 16 = 42.00 a share on today's basis.

- [ ] **Step 7: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=830 passed=830 -->
Expected: every command exits 0; 830 passed, 100% branch coverage; the performance test passes, on the machine that wrote this plan in 8.5 s.

- [ ] **Step 8: Mutations.** Run M98–M103; each must turn the whole suite red with the total unchanged.
- [ ] **Step 9: Commit, push and merge** (`feat(engine): S4 the income report, the goal tracker and the backtester's income`, ending in the story's issue number as `(#N)`).

---

## Mutation checks

Each mutation plants one realistic defect in the story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed lines are printed before the run. The predicted catchers were written before any run; "More than predicted" lists the other tests that also went red.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M67 | 1 | `income.py` | take-home uses the tax booked, not the full tax | 757 | `test_take_home_is_after_the_full_tax_whatever_was_booked` (1 failing) | none |
| M68 | 1 | `income.py` | the trailing year drops its first day | 757 | `test_the_trailing_year_is_the_365_days_ending_on_the_last_day` (1 failing) | none |
| M69 | 1 | `income.py` | the average net is the average gross less the average tax | 757 | `test_each_monthly_average_is_rounded_down_on_its_own` (1 failing) | none |
| M70 | 1 | `income.py` | months with nothing paid are left out | 757 | `test_each_month_sums_what_was_paid_and_booked_and_empty_months_are_kept`, `test_months_run_across_a_year_end`, `test_the_trailing_year_is_the_365_days_ending_on_the_last_day` (3 failing) | none |
| M71 | 1 | `income.py` | the yield on cost divides by the value | 757 | `test_a_yield_is_rounded_half_even_to_eight_places`, `test_the_current_yield_and_the_yield_on_cost` (2 failing) | none |
| M72 | 1 | `income.py` | the current yield divides by the first day's value | 757 | `test_the_current_yield_and_the_yield_on_cost` (1 failing) | none |
| M73 | 1 | `metrics.py` | the year window is a day too long | 757 | `test_dividends_and_the_income_of_the_last_365_days`, `test_the_year_window_is_365_days_with_both_ends_included` (2 failing) | none |
| M74 | 2 | `market.py` | a pay date counts closed days | 778 | `test_a_day_past_the_holiday_data_is_refused_not_guessed`, `test_it_may_start_on_a_day_the_market_is_closed`, `test_it_skips_a_long_closure`, `test_it_skips_weekends_and_holidays_across_a_year_end`, `test_the_calendar_puts_each_dividend_in_its_pay_month_as_take_home`, `test_the_pay_date_is_the_engines_for_the_same_lag` (10 failing) | `test_a_dividend_entitles_what_was_held_at_the_previous_close`, `test_a_dividend_on_a_holding_is_entitled_on_its_ex_date`, `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_recorder_writes_the_stored_file_byte_for_byte` |
| M75 | 2 | `income.py` | a split on the dividend's own ex-date is not restated | 778 | `test_only_a_split_from_the_ex_date_to_the_run_rate_day_restates_a_dividend` (1 failing) | none |
| M76 | 2 | `income.py` | a split after the run-rate's day is restated | 778 | `test_only_a_split_from_the_ex_date_to_the_run_rate_day_restates_a_dividend` (1 failing) | none |
| M77 | 2 | `income.py` | restatement divides as a Decimal before multiplying | 778 | `test_a_split_no_decimal_can_hold_is_still_restated_exactly` (1 failing) | none |
| M78 | 2 | `income.py` | the run-rate's window drops its first day | 778 | `test_the_run_rate_restates_each_trailing_dividend_and_rounds_it_down`, `test_the_year_window_holds_both_of_its_ends_and_nothing_outside_them` (2 failing) | none |
| M79 | 2 | `income.py` | the portfolio's monthly take-home is the holdings' added up | 778 | `test_the_portfolio_monthly_take_home_is_worked_out_from_its_own_annual_gross` (1 failing) | none |
| M80 | 2 | `income.py` | the calendar uses the ex-date's month | 778 | `test_the_calendar_puts_each_dividend_in_its_pay_month_as_take_home` (1 failing) | none |
| M81 | 2 | `income.py` | the calendar shows gross, not take-home | 778 | `test_a_calendar_paying_the_same_every_month_scores_one_twelfth`, `test_a_calendar_with_nothing_to_share_has_no_evenness`, `test_the_calendar_puts_each_dividend_in_its_pay_month_as_take_home` (3 failing) | none |
| M82 | 2 | `income.py` | a holding missing from the history counts as paying nothing | 778 | `test_a_held_stock_missing_from_the_history_is_an_error` (1 failing) | none |
| M83 | 3 | `income.py` | growth compares three years back, not four | 812 | `test_growth_is_the_yearly_rate_between_year_windows_four_years_apart`, `test_the_earlier_window_holds_both_of_its_ends_and_nothing_outside_them` (2 failing) | none |
| M84 | 3 | `income.py` | growth takes a square root, not a fourth root | 812 | `test_growth_is_the_yearly_rate_between_year_windows_four_years_apart` (1 failing) | none |
| M85 | 3 | `income.py` | a holding with no run-rate is measured | 812 | `test_a_portfolio_with_nothing_paying_has_no_growth`, `test_growth_is_the_yearly_rate_between_year_windows_four_years_apart` (2 failing) | none |
| M86 | 3 | `income.py` | the portfolio's growth is not weighted by gross | 812 | `test_growth_is_the_yearly_rate_between_year_windows_four_years_apart` (1 failing) | none |
| M87 | 3 | `income.py` | pessimistic growth is a flat 0% | 812 | `test_each_scenario_starts_and_grows_as_the_spec_says` (2 failing) | `test_pessimistic_never_beats_base_and_base_never_beats_optimistic` |
| M88 | 3 | `income.py` | base growth is not capped at 5% | 812 | `test_each_scenario_starts_and_grows_as_the_spec_says` (3 failing) | `test_pessimistic_never_beats_base_and_base_never_beats_optimistic` |
| M89 | 3 | `income.py` | a goal already met is not seen before month 1 | 812 | `test_a_goal_already_met_takes_no_time`, `test_a_projection_carries_its_label_the_goal_and_the_costs_note` (2 failing) | none |
| M90 | 3 | `income.py` | the target is checked before the year's growth | 812 | `test_dividends_grow_at_month_twelve_before_the_target_is_checked`, `test_the_last_month_is_the_six_hundredth` (2 failing) | none |
| M91 | 3 | `income.py` | the projection stops at month 599 | 812 | `test_the_last_month_is_the_six_hundredth` (1 failing) | none |
| M92 | 3 | `income.py` | the projection reinvests the tax too | 812 | `test_a_short_run_simulated_by_hand`, `test_the_contribution_is_reinvested_each_month` (2 failing) | none |
| M93 | 3 | `income.py` | no holdings' value is still projected | 812 | `test_nothing_to_project_from_cannot_be_projected` (1 failing) | none |
| M94 | 3 | `income.py` | pessimistic starts from the whole run-rate | 812 | `test_each_scenario_starts_and_grows_as_the_spec_says` (3 failing) | none |
| M95 | 3 | `income.py` | a note is built from a literal key | 812 | `test_every_note_is_built_from_a_key_constant_and_every_key_is_used`, `test_no_key_is_defined_twice` (2 failing) | none |
| M96 | 3 | `notes.py` | a key constant is reworded | 812 | `test_every_key_is_a_dotted_lowercase_identifier_named_after_itself` (1 failing) | none |
| M97 | 3 | `income.py` | years round down, not up | 812 | `test_a_short_run_simulated_by_hand`, `test_the_contribution_is_reinvested_each_month` (2 failing) | none |
| M98 | 4 | `income.py` | the goal tracker uses gross, not take-home | 830 | `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_goal_shares_are_not_capped_at_one`, `test_the_recorder_writes_the_stored_file_byte_for_byte`, `test_the_report_gathers_every_part_as_of_the_last_day` (4 failing) | none |
| M99 | 4 | `income.py` | the projection counts idle cash as invested | 830 | `test_the_projection_starts_from_the_holdings_not_the_idle_cash`, `test_the_report_gathers_every_part_as_of_the_last_day` (4 failing) | `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_recorder_writes_the_stored_file_byte_for_byte` |
| M100 | 4 | `income.py` | the report ignores the settings' pay lag | 830 | `test_the_calendar_pays_after_the_settings_pay_lag`, `test_the_report_gathers_every_part_as_of_the_last_day`, `test_with_a_goal_each_run_reports_its_income_from_five_years_of_history` (3 failing) | none |
| M101 | 4 | `backtest.py` | the backtester fetches four years of history | 830 | `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_recorder_writes_the_stored_file_byte_for_byte`, `test_with_a_goal_each_run_reports_its_income_from_five_years_of_history` (3 failing) | none |
| M102 | 4 | `backtest.py` | the income impact is the baseline's minus the strategy's | 830 | `test_with_a_goal_each_run_reports_its_income_from_five_years_of_history` (1 failing) | none |
| M103 | 4 | `backtest.py` | the baseline gets no income report | 830 | `test_with_a_goal_each_run_reports_its_income_from_five_years_of_history` (1 failing) | none |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M67',
  1,
  'packages/steadyhand/src/steadyhand/income.py',
  '    take_home = sum(\n'
  '        (_take_home(entitlement.gross, rules, report.day) for entitlement in report.paid), '
  'nothing\n'
  '    )\n',
  '    take_home = gross - report.tax\n'),
 ('M68',
  1,
  'packages/steadyhand/src/steadyhand/income.py',
  '        if report.day >= since:\n',
  '        if report.day > since:\n'),
 ('M69',
  1,
  'packages/steadyhand/src/steadyhand/income.py',
  '        _per_month(trailing.net),\n',
  '        _per_month(trailing.gross) - _per_month(trailing.tax),\n'),
 ('M70',
  1,
  'packages/steadyhand/src/steadyhand/income.py',
  '        for month in _months(reports[0].day, as_of)\n',
  '        for month in sorted(months)\n'),
 ('M71',
  1,
  'packages/steadyhand/src/steadyhand/income.py',
  '        _ratio(trailing.gross, cost),\n',
  '        _ratio(trailing.gross, reports[-1].value),\n'),
 ('M72',
  1,
  'packages/steadyhand/src/steadyhand/income.py',
  '        _ratio(trailing.gross, reports[-1].value),\n',
  '        _ratio(trailing.gross, reports[0].value),\n'),
 ('M73',
  1,
  'packages/steadyhand/src/steadyhand/metrics.py',
  '    return end - timedelta(days=YEAR_DAYS - 1)\n',
  '    return end - timedelta(days=YEAR_DAYS)\n'),
 ('M74',
  2,
  'packages/steadyhand/src/steadyhand/market.py',
  '        current += timedelta(days=1)\n'
  '        while not rules.is_trading_day(current):\n'
  '            current += timedelta(days=1)\n',
  '        current += timedelta(days=1)\n'),
 ('M75',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  'and ex_date <= action.ex_date <= as_of:',
  'and ex_date < action.ex_date <= as_of:'),
 ('M76',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  'and ex_date <= action.ex_date <= as_of:',
  'and ex_date <= action.ex_date:'),
 ('M77',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  '    return Money(numerator * shares * old * scale // (denominator * new), currency)\n',
  '    return Money(int(dividend.per_share * old / new * shares * scale), currency)\n'),
 ('M78',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  'isinstance(action, CashDividend) and since <= action.ex_date <= as_of',
  'isinstance(action, CashDividend) and since < action.ex_date <= as_of'),
 ('M79',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  '    return RunRate(as_of, tuple(holdings), total, _per_month(_take_home(total, rules, '
  'as_of)))\n',
  '    monthly_total = sum((held.monthly_take_home for held in holdings), nothing)\n'
  '    return RunRate(as_of, tuple(holdings), total, monthly_total)\n'),
 ('M80',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  '            months[dividend.pay_date.month - 1] +=',
  '            months[dividend.ex_date.month - 1] +='),
 ('M81',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  '+= _take_home(dividend.gross, rules, rate.as_of)\n',
  '+= dividend.gross\n'),
 ('M82',
  2,
  'packages/steadyhand/src/steadyhand/income.py',
  '    actions = history.get(stock)\n',
  '    actions = history.get(stock, ())\n'),
 ('M83',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  'GROWTH_YEARS = 4\n',
  'GROWTH_YEARS = 3\n'),
 ('M84',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '.ln(_CONTEXT), GROWTH_YEARS)',
  '.ln(_CONTEXT), 2)'),
 ('M85',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '        if holding.annual_gross.amount == 0:\n            continue\n',
  ''),
 ('M86',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '_CONTEXT.multiply(growth, holding.annual_gross.amount))',
  'growth)'),
 ('M87',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '            min(Decimal(0), measured),\n',
  '            Decimal(0),\n'),
 ('M88',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  'min(measured, BASE_GROWTH_CAP)',
  'measured'),
 ('M89',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '        if self._met(income):\n            return _tenths(0)\n',
  ''),
 ('M90',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '            if month % _MONTHS == 0:\n'
  '                income = income.times(1 + growth, Rounding.DOWN)\n'
  '            if self._met(income):\n'
  '                return _tenths(month)\n',
  '            if self._met(income):\n'
  '                return _tenths(month)\n'
  '            if month % _MONTHS == 0:\n'
  '                income = income.times(1 + growth, Rounding.DOWN)\n'),
 ('M91',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  'range(1, PROJECTION_MONTHS + 1)',
  'range(1, PROJECTION_MONTHS)'),
 ('M92',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '            new = monthly - self._tax(monthly) + self.contribution\n',
  '            new = monthly + self.contribution\n'),
 ('M93',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  'if rate.annual_gross.amount == 0 or holdings_value.amount == 0:',
  'if rate.annual_gross.amount == 0:'),
 ('M94',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '            rate.annual_gross.times(PESSIMISTIC_START, Rounding.DOWN),\n',
  '            rate.annual_gross,\n'),
 ('M95',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '                    INCOME_GROWTH_SHORT_HISTORY,\n',
  '                    "income.growth.short_history",\n'),
 ('M96',
  3,
  'packages/steadyhand/src/steadyhand/notes.py',
  'INCOME_PROJECTION_COSTS_IGNORED = "income.projection.costs_ignored"\n',
  'INCOME_PROJECTION_COSTS_IGNORED = "income.projection.costs"\n'),
 ('M97',
  3,
  'packages/steadyhand/src/steadyhand/income.py',
  '    return Decimal(-(-months * 10 // _MONTHS)).scaleb(-1)\n',
  '    return Decimal(months * 10 // _MONTHS).scaleb(-1)\n'),
 ('M98',
  4,
  'packages/steadyhand/src/steadyhand/income.py',
  '    got, expected = received.monthly_average.take_home, rate.monthly_take_home\n',
  '    got, expected = received.monthly_average.gross, rate.monthly_take_home\n'),
 ('M99',
  4,
  'packages/steadyhand/src/steadyhand/income.py',
  '        project(rate, growth, reports[-1].holdings_value, settings, rules),\n',
  '        project(rate, growth, reports[-1].value, settings, rules),\n'),
 ('M100',
  4,
  'packages/steadyhand/src/steadyhand/income.py',
  'received.as_of, settings.pay_lag_trading_days)',
  'received.as_of, PAY_LAG_TRADING_DAYS)'),
 ('M101',
  4,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    since = years_before(as_of, HISTORY_YEARS)\n',
  '    since = years_before(as_of, HISTORY_YEARS - 1)\n'),
 ('M102',
  4,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    return IncomeImpact(ours.received - theirs.received, ours.run_rate - theirs.run_rate)\n',
  '    return IncomeImpact(theirs.received - ours.received, theirs.run_rate - ours.run_rate)\n'),
 ('M103',
  4,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '        compared = (\n'
  '            None if compared is None else _with_income(compared, market, settings, '
  'settings.goal)\n'
  '        )\n',
  '        compared = compared\n')]
```

## Carried forward

- **M4b** (stories S5–S8) gets its own plan after this one merges, verified against the tree M4a leaves. S5 first reads PMK 18/2021's in-force date from BPK (M4 §6.1) and moves `income.py`'s `dividend_tax` calls off the `reinvested_by_deadline` flag.
- **Scope decisions 4 and 5 amend M4 §3.3**: a split on the dividend's own ex-date restates it, and restatement is exact in integers. The M4 spec says "after" and "exact `Decimal` arithmetic"; this plan is the record of the change.
- **M5** renders `IncomeReport` for `report --income`, and every `Note` by its key.
- **The training sub-project** is brainstormed next (M4 spec decision 8). Its lessons attach to `notes.py`'s keys; keying M3's plain-string warnings is its work.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

**How the code was verified.** Each story's code was written first in a scratch clone, one commit per story on top of the five-year recordings (`6650fce`), and each commit passed CI's whole gate (`gates.py`: ruff, format, mypy, the suite under `HYPOTHESIS_PROFILE=ci` at 100% branch coverage, and the performance step): S1 757, S2 778, S3 812, S4 830 passed. Every code block in this plan was rendered from those commits (`render.py`), and each story's red phase was run from its tests and stubs on the previous story's tree (`redrun.py`). `check_plan.py` then replayed this plan from its own text on a fresh worktree: every red and gate count reproduced, the golden file regenerated to its SHA-256, and each story's tree was byte-identical to its verified commit ("problems: 0"). Every mutation was planted on its own story's commit with its predicted catchers written first.

- **While writing (2026-09-26), before the passes.** Five things were found by running, not reading. (1) The truncation check failed once the golden run had a goal: a run cut in April 2021 asked for history from 2016, before the recordings start (scope decision 15). (2) The performance test's last synthetic year paid no dividend, because 15 June 2025 is a Sunday, so its projection would have timed nothing (scope decision 16). (3) Reasoning through M92 before running it showed the hand-simulated short run could not tell reinvesting take-home from reinvesting everything; its target moved from 9,100 to 9,070, which only take-home misses in month 1. (4) S2's first red run failed 14 tests with `NameError`: its stubs kept `corporate.py`'s old callers but dropped the private helper they call. The stub rule now keeps a module that only removes functions as it was, so every S2 red failure is `NotImplementedError`. (5) The plan tools could not delete a file, and three of them wrote their pytest report through a relative path; both fixed in the tool copies under `.superpowers/sdd/2026-09-26-m4a-income/`.
- **Pass 1 (2026-09-26): 3 findings, all fixed.** Mechanical checks: the replay above; the live Yahoo check on the five recordings (`-m live -k 2017-01-31`, 5 passed); the overlap check of Task 0 Step 2 (0 differing rows, 0 extra days, identical splits, for all five); every M4 spec section from §3.2 to §9 mapped to a task and a test. Then a full read. (1) The commit lines said `(#<story>)`, which reads as an unfilled placeholder; they now say the story's issue number ends the message. (2) Task 2's interfaces said Task 3 uses `_restated_gross`; it uses `_history_of` and `_split_ratio`. (3) Task 3's "Consumes" listed `run_rate` and `_take_home`, which its code never calls; it now names what `project` and `dividend_growth` read, and says the tests build run-rates with `run_rate`.
- **Pass 2 (2026-09-26): 1 finding, closed by running.** `check_plan.py` replayed the built plan file ("problems: 0"). Then a full read of the rendered plan. (1) Two scripts the plan prints, Task 0 Step 2's overlap check and Task 4 Step 6's golden comparison, had never been run as printed; the checks behind their expected outputs were earlier, different scripts. Both were cut from the plan text and run: the first on the recordings commit, printing the five expected lines; the second on S4's commit against `origin/develop`, printing `['income'] [] True 10`. No text changed.
- **Pass 3 (2026-09-26): no findings.** The replay of the final file again reproduced every red and gate count, the golden SHA-256 and all four story trees byte for byte. A read of every task's criteria, interfaces and steps against the mutation table and the M4 spec found nothing. The loop closes, and the plan is approved under Shyden's standing rule of 2026-09-24.
