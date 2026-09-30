# M6 Strategy Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first strategies beyond the baseline: `monthly-savings`, which invests the starting cash in monthly instalments, and `dividend-growth`, which holds the stocks that paid a dividend every year and grew it, spread across the months they pay in. `dividend-growth` becomes the default. The engine gives a strategy what it needs: past dividends restated in today's shares, the universe, the modelled pay date, a look-back of years before the run read without prices, notes of its own, and settings in `steadyhand.toml`. Course module 8 gets its lessons.

**Architecture:** The engine's data path (S1): `ActionHistory` holds every corporate action a run loaded, and `MarketView` shows a strategy its dividends (restated by later splits), the universe (`Tradable.members`), a dividend's modelled pay date (`PayDates`) and whether its history is complete; `Decision` carries notes, which the day's report shows after the engine's; `BacktestSettings.lookback_years` makes the fetch read corporate actions from 1 January that many years before the first day; the registry gains `Setting` and each entry's look-back. The IDX data path (S2): Yahoo's actions are read without prices or the holiday calendar, the cache records ranges fetched for actions alone, trading days answer from the holiday data back to 2016, and a refused stock's run-range actions still reach the history. `monthly-savings` and the `[strategy]` settings (S3). `dividend-growth`, the new default, its golden run and its journeys (S4). Module 8's lessons (S5).

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md` (the "M6 spec"), on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec"), `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md` (the "M3 spec"), `docs/superpowers/specs/2026-09-26-m4-income-design.md` (the "M4 spec"), `docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md` (the "M5 spec") and `docs/superpowers/specs/2026-09-27-training-design.md` (the "T1 spec"). The M6 spec's four stories are five here (scope decision 1). Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how each claim was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2); `steadyhand-idx` keeps its runtime dependencies at `steadyhand` and `yfinance` (M5 §3.1).
- A strategy sees nothing after its day (core §4.3): `MarketView` refuses a later date with `LookAheadError`, `pay_date` included, and `ActionHistory` returns no dividend with a later ex-date and restates by no later split (M6 §4.1).
- The competency level never changes what a strategy trades (core §3.3). Lessons explain and never advise; the engine's lessons are market-neutral (no "Rp", "IDX", "Indonesia" or "steadyhand-idx").
- Every note a report carries is a `Note` built from a key constant, and every key has a lesson in the same story (T1 §1.1).
- Every strategy setting is a whole number with a default and bounds, its name belongs to one strategy only, `init` writes it under a one-line comment, a file without it takes its default, and its strategy's guide names it under *Settings you can change* (M6 §4.5, §7).
- Tests call steadyhand's own code with real values and recorded data: no stub or mock of steadyhand's code (M5 §9.1). The golden runs go through the real `YahooDataSource`, `CachedDataSource` and `IdxMarketRules`. Every pay date a test names was read from the calendar, never counted by hand (build finding 5).
- Every `*Error` a task raises is raised by a test that asserts its message. A `match=` holding a regex metacharacter is a raw string (ruff RUF043).
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A function that already existed keeps its old body in the red phase, and a class that already existed keeps its old fields; only new names are stubs, with three exceptions: a new `__post_init__` is stubbed as `return` (it runs whenever an instance is built), a new function the module calls at import keeps its body, and a method a story renames keeps its old definition beside the new stub. A test module that builds a pre-existing class with its new field fails to collect in the red phase, so the red run passes `--continue-on-collection-errors`.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code.
- Test file basenames are unique across `tests/`. English only. The phrase "robot trading" never appears (core §1.3).
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **A `steadyhand.toml` with no `[strategy] name`**, written or trimmed by hand (`init` has always written it). Expected: before M6 it meant `buy-and-hold`; it now means `dividend-growth`, the new default, so `paper run` on an account opened with `buy-and-hold` refuses with the switch message and exit 2, changing nothing, rather than switching strategy silently. Pinned in Task 4 (`test_a_file_without_a_strategy_name_now_means_dividend_growth_so_paper_refuses`; mutation M365).
2. **A look-back the source has nothing for** (a delisted stock, Yahoo's 404). Expected: the run goes on, one `data.dividends.history_refused` warning names the stock, the range and the source's reason, and the stock fails `dividend-growth`'s test. Pinned in Task 1 (`test_a_look_back_the_source_has_nothing_for_is_refused_history_too`; mutation M310) and Task 4's golden run (TLKM).
3. **A dividend whose ex-date falls on a day the source refused prices for** (BBRI's rights issue of 2021). Expected: the strategy's history holds it, read without prices; if the source refuses that read too, the stock's history is incomplete; the engine still credits nothing on a refused day, as M3's warning says. Pinned in Task 2 (`test_a_dividend_on_a_refused_day_reaches_the_history_when_read_without_prices`, `test_a_source_that_refuses_the_actions_too_leaves_that_history_incomplete`; mutations M328–M331).
4. **A split on a dividend's own ex-date.** Expected: the dividend is restated by it, as the engine pays that dividend on the shares held before the split. Pinned in Task 1 (`test_a_dividend_is_restated_by_each_split_from_its_own_ex_date_to_today`; mutation M298).
5. **A review that falls on a holiday or a missed day.** Expected: `dividend-growth` reviews on the first day it decides in each calendar year, whatever that date is, and on its first day, and on no other day. Pinned in Task 4 (`test_it_reviews_on_no_day_but_the_first_and_each_new_years_first`, a property over random days; mutation M361).
6. **`max_stocks` below `min_stocks`** while another strategy runs. Expected: the configuration is refused naming both, so the mistake is found before anyone switches to `dividend-growth`. Pinned in Task 4 (`test_each_bad_value_is_refused_naming_its_table_and_key`; mutations M362, M364).

## Scope decisions (read before starting)

1. **Five stories, not four** (Shyden, 2026-09-30). Read through steadyhand's own Yahoo reader, the look-back failed where the spec's measurement had not (build finding 1): the price checks and the holiday calendar refused most six-year histories. Shyden chose to read dividends and splits without prices or the calendar, with the cache recording those ranges. That is Task 2 (S2), before `monthly-savings`; the spec's S2–S4 are Tasks 3–5.
2. **The `[strategy]` keys are read and written in Task 3**, not Task 1: with no strategy holding a setting in Task 1, the loops over settings in the configuration, `init` and the paper audit could not reach 100% branch coverage without a test registry threaded through all three.
3. **`lookback_years` is a field of `BacktestSettings`** (default 0), not a sixth argument of `backtest` and `compare` (the repository's limit is five, ruff PLR0913, with no exception in package code; `pyproject.toml` exempts `tests/`). `day_inputs(market, start, end, lookback_years=0)` takes it as its fourth argument. The caller sets it from the registry, so the engine never reads the registry.
4. **`MarketView(history, today, tradable, actions, pay_dates)`**: the rules and the pay lag travel as `PayDates(rules, lag_trading_days)` in `market.py`, again for the five-argument limit, and `PayDates.of` is `add_trading_days`, the function the engine and the income calendar use.
5. **A dividend is restated by every split on or after its own ex-date** (the spec says "after"): the engine pays a dividend on the shares held before that day's split, so a split on the same day restates it too.
6. **A refused look-back is any `DataUnavailableError`**, not only a refusal naming days (the spec's own example, a 404, names none). Its warning names the range and the source's reason.
7. **`IdxMarketRules.is_trading_day` answers for every year of the holiday data** (2016 to 2027), not only from `verified_from` (build finding 2); counting trading days needs only the holidays. The M4 income report on 30 June 2021 now places a 2020 dividend's pay month instead of refusing, and its refusal moves to the start of the holiday data.
8. **An income report now reads a holding whose old prices cannot be recovered** (build finding 3): with actions read without prices, `backtest` to 31 January 2022 builds its report with BBRI's 6 April 2021 dividend, where before M6 it stopped with exit 3. Shyden was told of this when he chose the path.
9. **The paper audit** writes a strategy setting absent from the saved settings as "`{key}` is `{new}`, recorded for the first time", and a changed one as "…; the strategy's guide says when a change takes effect" (`monthly-savings` fixes its instalment on its first day, so "it applies from the next day" would be false). Only the running strategy's settings are recorded.
10. **The class is `DividendGrowthStrategy`**: `steadyhand.DividendGrowth` already names the income report's growth figures. It exposes `min_stocks`, `max_stocks` and `growth_years` read-only, as `MonthlySavings` exposes `instalments`.
11. **The too-few note** reads "No stock passed the dividend test; everything is held as cash until one does." for none and "Only 1 stock passed …" for one; the spec's text stands for two or more.
12. **The set memory helpers move to `strategies/_sets.py`** (`read_set`, `write_set`), shared by `buy-and-hold` and `dividend-growth`.
13. **The golden harness**: `GOLDEN_CONFIG` names `buy-and-hold`, since the default is now `dividend-growth`; `record_golden.run` makes every strategy from `VALUES` with its look-back (a two-year test for `dividend-growth`, whose three-year look-back fits in the recordings, which start in 2017); `golden_backtest` runs the configured strategy; the `dividend-growth` golden run refuses TLKM's look-back by script.
14. **A refused stock's actions over the whole run are read for its history** (build finding 6), in a call of their own: a source that reads them without prices gives the refused days' dividends too; if it refuses that call, the stock's history is incomplete. The engine still credits nothing on a refused day (M3 §7.3, unchanged): whether it should now changes M3's figures and is left to its own ticket.
15. **Module 8** holds a lesson per registered strategy, in the engine's wheel, each pointing at its guide, then `strategies.holding_cash`, which explains the too-few note.

## Measured performance (M6 §9.4)

Measured in the scratch build (`tests/perf/test_performance.py`), a year of `dividend-growth` with its default settings over the 45 synthetic stocks, from 2 January to 29 December 2023, reading six years of look-back (from 1 January 2017; the synthetic data starts in 2016):

| Measurement | Measured | Budget |
|---|---|---|
| The year, 260 trading days, holding 25 stocks picked by pay month at each review | 0.37 to 0.40 s at a load of 10 on four cores (0.67 to 0.74 s at 30) | 3 s |

The machine was never idle during the build: another session's browser tests held the load between 10 and 30. The budget leaves about eight times the lower measurement for a slower CI runner; M5's paper budgets leave about six. Every other performance budget is unchanged, and each story's gate runs them.

## File map

| File | Task | Responsibility |
|---|---|---|
| `.../steadyhand/view.py` | 1, 2 | `PastDividend`, `ActionHistory`, `Tradable.members`, the new `MarketView` |
| `.../steadyhand/market.py` | 1, 2 | `PayDates`; `require_supported`'s docstring names `is_trading_day`'s exception |
| `.../steadyhand/engine.py` | 1 | `DayInputs.past_actions`; the strategy's view and notes |
| `.../steadyhand/backtest.py` | 1, 2 | `lookback_years`, the look-back fetch and its warning; a refused stock's history |
| `.../steadyhand/strategies/{protocol,registry}.py` | 1, 3, 4 | `Decision.notes`; `Setting`, `Registered`'s settings and look-back; the new entries |
| `.../steadyhand/strategies/{monthly_savings,dividend_growth,_sets,buy_and_hold}.py` | 3, 4 | The two strategies; the set helpers `buy-and-hold` now shares |
| `.../steadyhand/__init__.py`, `strategies/__init__.py` | 1, 3, 4 | The engine's exports |
| `.../steadyhand/strategies/guides/*.md` | 3, 4 | The two new guides |
| `.../steadyhand/notes.py`, `training/lessons/en/*.md` | 1, 4, 5 | The two new keys and their lessons; module 8 |
| `.../steadyhand_idx/{yahoo,cache,rules}.py` | 2 | Actions without prices; ranges fetched for actions alone; trading days from 2016 |
| `.../steadyhand_idx/{config,cli,paper}.py` | 3, 4 | The `[strategy]` settings, the default, the look-back in each command |
| `scripts/record_golden.py`, `tests/fixtures/golden/dividend-growth_*.json` | 4 | The `dividend-growth` golden run |
| `tests/engine/*`, `tests/idx/*`, `tests/cli/*`, `tests/golden/*`, `tests/perf/*`, `tests/meta/*` | 1–5 | The tests of each |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | This plan and the stories | `m6/m6-plan` |
| 1 | M6 S1 The engine's data path: dividend history, members, pay dates, strategy notes, the look-back and settings | `m6/s1-data-path` |
| 2 | M6 S2 The look-back's IDX data path: dividends read without prices or the calendar | `m6/s2-idx-look-back` |
| 3 | M6 S3 monthly-savings and the [strategy] settings | `m6/s3-monthly-savings` |
| 4 | M6 S4 dividend-growth, the new default, and its golden run | `m6/s4-dividend-growth` |
| 5 | M6 S5 Course module 8 | `m6/s5-module-8` |

Stories merge in order: each one's code builds on the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Merge without asking: Shyden's standing rule of 2026-09-27 covers every green PR into `develop` (never `main`). Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: This plan and the stories

On `m6/m6-plan`, whose PR carries this plan and `HANDOVER.md` (#146).

- [ ] **Step 1: File the stories.** Create one issue per task 1–5, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 2: Open the PR** from `m6/m6-plan` into `develop` (`Refs #146`), and merge it as **Merging a story** says.

---

### Task 1: M6 S1 The engine's data path: dividend history, members, pay dates, strategy notes, the look-back and settings

**Acceptance criteria (story text):**
1. `ActionHistory(actions, incomplete)` holds every corporate action a run loaded. `MarketView.dividends(stock)` returns the stock's cash dividends with an ex-date on or before today, oldest first, each a `PastDividend(ex_date, per_share)` restated by every split from its own ex-date to today (scope decision 5), dividing once; nothing with a later ex-date is returned (a property over random actions and days). Anything but a corporate action, or an incomplete stock that is not an `Instrument`, is refused naming it.
2. `MarketView.pay_date(ex_date)` is `add_trading_days(rules, ex_date, lag)` through `PayDates(rules, lag_trading_days)` (scope decision 4); a later ex-date raises `LookAheadError`, and one the rules cannot place raises their own `UnsupportedDateError`. `MarketView.history_complete(stock)` is false for a stock whose look-back was refused.
3. `Tradable.members` is the universe on its day; a buyable stock outside it is refused naming it, and a member may be kept out. The engine passes the day's members, the run's `ActionHistory` (`DayInputs.past_actions`) and the pay lag to the strategy's view.
4. `Decision.notes` is a tuple of `Note`s, refused otherwise; the day's report shows them after the engine's own, and a halted day, which asks the strategy nothing, shows none.
5. `BacktestSettings.lookback_years` (a whole number from 0, scope decision 3) makes the fetch read each stock's corporate actions from 1 January that many years before the first day to the day before it, in a call of their own, once for `compare`; `day_inputs` takes it as a fourth argument. A look-back the source refuses, with any `DataUnavailableError` (scope decision 6), gives one `data.dividends.history_refused` warning naming the stock, the range and the reason, and the run goes on with that stock's history incomplete; a refusal in the run's own days keeps M3's rule. The key has its lesson (`backtest.data_gaps`).
6. The registry's `Setting(name, default, minimum, maximum, help)` is a whole number with bounds and one line of help, refused otherwise; `Registered` gains `settings` and `lookback`, `values(given)` checks each setting (taking its own from a table that holds other strategies' too), calling an entry makes the strategy from its settings, and `lookback_years(values)` reads the same values. `buy-and-hold` has no settings and reads nothing before a run. The guide guard wants each registered setting named under *Settings you can change*.
7. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M296–M318 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand/{view,market,engine,backtest,notes,__init__}.py`, `.../steadyhand/strategies/{__init__,protocol,registry}.py`, `.../steadyhand/training/lessons/en/backtest.data_gaps.md`
- Test: `tests/engine/{test_view,test_engine,test_backtest,test_buy_and_hold,test_registry,test_risk}.py`, `tests/meta/{test_strategy_guides,test_note_keys,test_legal_line}.py`

**Interfaces:**
- Consumes: `add_trading_days(rules, day, count)`, `MarketRules`, `CorporateAction` (`CashDividend`, `Split`, `OtherAction`), `Note`, `DataUnavailableError`.
- Produces: in `steadyhand.view`, exported from `steadyhand`: `PastDividend(ex_date, per_share)`; `ActionHistory(actions=(), incomplete=())` with `incomplete`, `dividends(instrument, today)` and `complete(instrument)`; `Tradable(day, buyable, sellable, reasons, members)`; `MarketView(history, today, tradable, actions, pay_dates)` with `dividends(instrument)`, `pay_date(ex_date)` and `history_complete(instrument)`. In `steadyhand.market`: `PayDates(rules, lag_trading_days)` with `of(ex_date)`. `DayInputs.past_actions: ActionHistory`; `Decision(weights, memory, notes=())`; `BacktestSettings(capital, engine, goal, lookback_years=0)`; `day_inputs(market, start, end, lookback_years=0)`; `DATA_DIVIDENDS_HISTORY_REFUSED`. In `steadyhand.strategies.registry`: `Setting(name, default, minimum, maximum, help)` with `check(value)`; `Registered(make, summary, turnover, settings=(), lookback=...)` with `values(given=None)`, `__call__(values=None)` and `lookback_years(values=None)`.

- [ ] **Step 1: Branch.** `git switch -c m6/s1-data-path origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_backtest.py`** (changed: 4 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    compare,
)
```
with:
```python
    compare,
    day_inputs,
)
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    DATA_BAR_REFUSED,
    RISK_HALT_DAILY_LOSS,
```
with:
```python
    DATA_BAR_REFUSED,
    DATA_DIVIDENDS_HISTORY_REFUSED,
    RISK_HALT_DAILY_LOSS,
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
from steadyhand.types import Bar, CashDividend, CorporateAction, Instrument
from steadyhand.view import MarketView, PortfolioView
from steadyhand_idx import UNIVERSE_SURVIVORSHIP_GAP, IdxMarketRules
```
with:
```python
from steadyhand.types import Bar, CashDividend, CorporateAction, Instrument
from steadyhand.view import MarketView, PastDividend, PortfolioView
from steadyhand_idx import UNIVERSE_SURVIVORSHIP_GAP, IdxMarketRules
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
        compare([BuyAndHold()], market(_Source(calm())), END, START, settings())
```
with:
```python
        compare([BuyAndHold()], market(_Source(calm())), END, START, settings())


class _Reader:
    """A strategy that records, each day, BBCA's dividends and whether BBCA's and BBRI's
    histories are complete, and asks for nothing."""

    def __init__(self) -> None:
        self.seen: dict[date, tuple[tuple[PastDividend, ...], bool, bool]] = {}

    @property
    def name(self) -> str:
        return "reader"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        self.seen[view.today] = (
            view.dividends(BBCA),
            view.history_complete(BBCA),
            view.history_complete(BBRI),
        )
        return Decision({})


class _Delisted(_Source):
    """A source with nothing at all for BBRI before the run, as Yahoo answers for a delisted
    stock (M6 spec §11): a plain ``DataUnavailableError``, naming no day."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        if instrument == BBRI and end < START:
            self.requests.append(("actions", instrument.symbol, start, end))
            msg = "BBRI.JK: the request to Yahoo failed: HTTP Error 404"
            raise DataUnavailableError(msg)
        return super().corporate_actions(instrument, start, end)


LOOKED_BACK: list[CorporateAction] = [
    CashDividend(BBCA, date(2022, 12, 30), Decimal(90)),
    CashDividend(BBCA, date(2023, 3, 1), Decimal(100)),
    CashDividend(BBCA, date(2025, 7, 2), Decimal(25)),
]
# Two years back from Monday 30 June 2025: from 1 January 2023 to the day before the first day.
SINCE, UNTIL = date(2023, 1, 1), date(2025, 6, 29)


def looking_back(years: int = 2) -> BacktestSettings:
    return replace(settings(), lookback_years=years)


def test_a_look_back_fetches_actions_from_1_january_and_bars_from_the_first_day() -> None:
    source = _Source(calm(), LOOKED_BACK)
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back())
    assert source.requests == [
        ("bars", "BBCA", START, END),
        ("actions", "BBCA", START, END),
        ("bars", "BBRI", START, END),
        ("actions", "BBRI", START, END),
        ("actions", "BBCA", SINCE, UNTIL),
        ("actions", "BBRI", SINCE, UNTIL),
    ]
    # 30 December 2022 is before the look-back; the run's own dividend shows from its ex-date.
    assert reader.seen[START] == ((PastDividend(date(2023, 3, 1), Decimal(100)),), True, True)
    assert reader.seen[END][0] == (
        PastDividend(date(2023, 3, 1), Decimal(100)),
        PastDividend(date(2025, 7, 2), Decimal(25)),
    )
    assert result.warnings == ()


def test_a_refused_look_back_warns_once_and_the_run_goes_on_without_that_history() -> None:
    source = _Source(calm(), LOOKED_BACK, refused={BBRI: [date(2024, 5, 6)]})
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back())
    assert [report.day for report in result.run.reports] == list(DAYS)
    assert result.warnings == (
        Note(
            DATA_DIVIDENDS_HISTORY_REFUSED,
            "BBRI: the data source refused its corporate actions from 2023-01-01 to 2025-06-29, "
            "before the run (BBRI: refused), so its dividend history is incomplete for any "
            "strategy that reads it.",
        ),
    )
    assert reader.seen[START][1:] == (True, False)
    assert reader.seen[END][1:] == (True, False)


def test_a_look_back_the_source_has_nothing_for_is_refused_history_too() -> None:
    source = _Delisted(calm())
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back(1))
    assert [warning.key for warning in result.warnings] == [DATA_DIVIDENDS_HISTORY_REFUSED]
    assert result.warnings[0].text.startswith(
        "BBRI: the data source refused its corporate actions from 2024-01-01 to 2025-06-29, "
        "before the run (BBRI.JK: the request to Yahoo failed: HTTP Error 404)"
    )
    assert reader.seen[END][1:] == (True, False)


def test_a_refusal_in_the_runs_own_days_keeps_its_rules_beside_a_look_back() -> None:
    source = _Source(calm(), refused={BBRI: [date(2025, 7, 3)]})
    result = run(source, chosen=looking_back())
    assert [warning.key for warning in result.warnings] == [DATA_BAR_REFUSED]
    assert ("actions", "BBRI", SINCE, UNTIL) in source.requests


def test_compare_fetches_the_look_back_once_for_every_strategy() -> None:
    source = _Source(calm(), LOOKED_BACK)
    reader = _Reader()
    compare([_Fixed({BBCA: Decimal("0.5")}), reader], market(source), START, END, looking_back(1))
    assert [request for request in source.requests if request[2] < START] == [
        ("actions", "BBCA", date(2024, 1, 1), UNTIL),
        ("actions", "BBRI", date(2024, 1, 1), UNTIL),
    ]
    assert reader.seen[START][0] == ()


def test_day_inputs_give_every_day_the_look_back() -> None:
    source = _Source(calm(), LOOKED_BACK, refused={BBRI: [date(2024, 5, 6)]})
    inputs = day_inputs(market(source), START, END, 2)
    assert all(day.past_actions is inputs[0].past_actions for day in inputs)
    history = inputs[0].past_actions
    assert history.dividends(BBCA, START) == (PastDividend(date(2023, 3, 1), Decimal(100)),)
    assert history.incomplete == frozenset({BBRI})
    assert day_inputs(market(_Source(calm())), START, END)[0].past_actions.incomplete == frozenset()
    with pytest.raises(ValueError, match=r"^lookback_years must be at least 0, got -1$"):
        day_inputs(market(source), START, END, -1)


def test_the_look_back_is_a_whole_number_of_years() -> None:
    with pytest.raises(ValueError, match=r"^lookback_years must be at least 0, got -1$"):
        BacktestSettings(rp(1), lookback_years=-1)
    with pytest.raises(TypeError, match=r"^lookback_years must be an int, got bool$"):
        BacktestSettings(rp(1), lookback_years=True)
```

**`tests/engine/test_buy_and_hold.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_buy_and_hold.py -->
Replace:
```python

from steadyhand.money import IDR, Money
from steadyhand.strategies import BuyAndHold, Decision, InvalidWeightsError, Strategy
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView, PriceHistory, Tradable

```
with:
```python

from steadyhand.market import PayDates
from steadyhand.money import IDR, Money
from steadyhand.notes import DATA_BAR_MISSING, Note
from steadyhand.strategies import BuyAndHold, Decision, InvalidWeightsError, Strategy
from steadyhand.types import Instrument
from steadyhand.view import ActionHistory, MarketView, PortfolioView, PriceHistory, Tradable
from steadyhand_idx import IdxMarketRules

```

<!-- edit: tests/engine/test_buy_and_hold.py -->
Replace:
```python
def view(buyable: set[Instrument], sellable: set[Instrument] | None = None) -> MarketView:
    tradable = Tradable(D0, frozenset(buyable), frozenset(sellable or set()), {})
    return MarketView(PriceHistory([]), D0, tradable)

```
with:
```python
def view(buyable: set[Instrument], sellable: set[Instrument] | None = None) -> MarketView:
    tradable = Tradable(
        D0, frozenset(buyable), frozenset(sellable or set()), {}, frozenset(buyable)
    )
    return MarketView(
        PriceHistory([]), D0, tradable, ActionHistory(), PayDates(IdxMarketRules(), 14)
    )

```

<!-- edit: tests/engine/test_buy_and_hold.py -->
Replace:
```python
        Decision({}, {1: "x"})  # type: ignore[dict-item]

```
with:
```python
        Decision({}, {1: "x"})  # type: ignore[dict-item]


def test_a_decision_carries_notes_and_checks_each_is_a_note() -> None:
    said = Note(DATA_BAR_MISSING, "what the strategy said about the day")
    assert Decision({}).notes == ()
    assert Decision({}, {}, (said,)).notes == (said,)
    with pytest.raises(TypeError, match=r"^note must be a Note, got str$"):
        Decision({}, {}, ("said",))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^notes must be a tuple, got list$"):
        Decision({}, {}, [said])  # type: ignore[arg-type]

```

**`tests/engine/test_engine.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
from steadyhand.types import Bar, CashDividend, Instrument, Order, Side, Split
from steadyhand.view import MarketView, PortfolioView, PriceHistory
from steadyhand_idx import IdxMarketRules
```
with:
```python
from steadyhand.types import Bar, CashDividend, Instrument, Order, Side, Split
from steadyhand.view import ActionHistory, MarketView, PastDividend, PortfolioView, PriceHistory
from steadyhand_idx import IdxMarketRules
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
        assert len(charges) == (1 if report.daily_cost.amount else 0)
```
with:
```python
        assert len(charges) == (1 if report.daily_cost.amount else 0)


class _Says:
    """``buy-and-hold``, saying one thing about each day it decides."""

    def __init__(self, note: Note) -> None:
        self._note = note

    @property
    def name(self) -> str:
        return "says"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        decided = BuyAndHold().decide(view, portfolio, memory)
        return Decision(decided.weights, decided.memory, (self._note,))


class _Looks:
    """A strategy that records what its view shows, and asks for nothing."""

    def __init__(self) -> None:
        self.members: frozenset[Instrument] = frozenset()
        self.buyable: frozenset[Instrument] = frozenset()
        self.dividends: tuple[PastDividend, ...] = ()
        self.complete: tuple[bool, bool] = (False, False)
        self.pay_date = D1

    @property
    def name(self) -> str:
        return "looks"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        self.members, self.buyable = view.tradable.members, view.tradable.buyable
        self.dividends = view.dividends(BBCA)
        self.complete = (view.history_complete(BBCA), view.history_complete(BBRI))
        self.pay_date = view.pay_date(view.today)
        return Decision({})


SAID = Note(DATA_BAR_MISSING, "what the strategy said about the day")


def test_a_strategys_notes_follow_the_engines_own_in_the_days_report() -> None:
    state, _ = day_one()
    claim = DividendClaim(BBCA, date(2025, 5, 27), date(2025, 5, 28), rp(12_500), D1, rp(12_500))
    exempt = replace(half(), dividend_reinvestment_exemption=True)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    _, report = run_day(with_claim(state, claim), inputs, _Says(SAID), rules(), exempt)
    assert [note.key for note in report.notes] == [EXEMPTION_DEADLINE_MISSED, DATA_BAR_MISSING]
    assert report.notes[-1] == SAID
    _, quiet = run_day(state, inputs, _Says(SAID), rules(), half())
    assert quiet.notes == (SAID,)


def test_a_halted_day_asks_the_strategy_nothing_so_it_says_nothing() -> None:
    state, _ = day_one()
    halted = replace(state, halt=Halt(D1, Note(RISK_HALT_DAILY_LOSS, "a fall")))
    _, report = run_day(halted, DayInputs(D2, steady(), members=MEMBERS), _Untouchable(), rules())
    assert report.notes == ()


def test_the_strategy_sees_the_days_members_the_past_dividends_and_the_engines_pay_date() -> None:
    tlkm = Instrument("TLKM", "IDX", IDR)
    past = ActionHistory([CashDividend(BBCA, date(2025, 5, 2), Decimal(100))], [BBRI])
    inputs = DayInputs(D1, steady(), members=MEMBERS | {tlkm}, past_actions=past)
    looks = _Looks()
    lag = replace(half(), pay_lag_trading_days=3)
    run_day(EngineState.opening(rp(10_000_000), D1), inputs, looks, rules(), lag)
    # TLKM is a member with no bar today: kept out of the buyable set, not out of the universe.
    assert (looks.members, looks.buyable) == (MEMBERS | {tlkm}, MEMBERS)
    assert looks.dividends == (PastDividend(date(2025, 5, 2), Decimal(100)),)
    assert looks.complete == (True, False)
    # Three trading days after Monday 2 June 2025.
    assert looks.pay_date == date(2025, 6, 5)


def test_day_inputs_hold_an_action_history() -> None:
    assert DayInputs(D1, steady()).past_actions.incomplete == frozenset()
    with pytest.raises(TypeError, match=r"^past_actions must be an ActionHistory, got tuple$"):
        DayInputs(D1, steady(), past_actions=())  # type: ignore[arg-type]
```

**`tests/engine/test_registry.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_registry.py -->
Replace:
```python

from pathlib import Path
```
with:
```python

from dataclasses import dataclass
from pathlib import Path
```

<!-- edit: tests/engine/test_registry.py -->
Replace:
```python

from steadyhand import GUIDES, STRATEGIES, BuyAndHold, Turnover, guide

```
with:
```python

from steadyhand import (
    GUIDES,
    STRATEGIES,
    BuyAndHold,
    Decision,
    MarketView,
    Memory,
    PortfolioView,
    Registered,
    Setting,
    Turnover,
    guide,
)

```

<!-- edit: tests/engine/test_registry.py -->
Replace:
```python
        guide("nothing")
```
with:
```python
        guide("nothing")


@dataclass(frozen=True)
class _Rounds:
    """A strategy made from two settings, to test the registry without a shipped one."""

    rounds: int
    pause: int

    @property
    def name(self) -> str:
        return "rounds"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        del view, portfolio, memory
        return Decision({})


ROUNDS = Setting("rounds", 3, 1, 9, "How many rounds to play.")
PAUSE = Setting("pause", 0, 0, 5, "Days to wait between rounds.")
ENTRY = Registered(
    _Rounds, "Plays rounds.", Turnover.LOW, (ROUNDS, PAUSE), lambda values: values["rounds"] + 1
)


def test_a_setting_is_a_named_bounded_whole_number_with_one_line_of_help() -> None:
    assert (ROUNDS.name, ROUNDS.default, ROUNDS.minimum, ROUNDS.maximum) == ("rounds", 3, 1, 9)
    assert ROUNDS.help == "How many rounds to play."
    assert Setting("growth_years", 1, 1, 1, "x").default == 1


@pytest.mark.parametrize(
    ("fields", "error", "message"),
    [
        (
            ("Rounds", 3, 1, 9, "x"),
            ValueError,
            r"^a setting's name is a lowercase identifier, got 'Rounds'$",
        ),
        (
            ("two words", 3, 1, 9, "x"),
            ValueError,
            r"^a setting's name is a lowercase identifier, got 'two words'$",
        ),
        (
            ("rounds_", 3, 1, 9, "x"),
            ValueError,
            r"^a setting's name is a lowercase identifier, got 'rounds_'$",
        ),
        ((5, 3, 1, 9, "x"), ValueError, r"^a setting's name is a lowercase identifier, got 5$"),
        (("rounds", 10, 1, 9, "x"), ValueError, r"^rounds: the default 10 must be from 1 to 9$"),
        (("rounds", 0, 1, 9, "x"), ValueError, r"^rounds: the default 0 must be from 1 to 9$"),
        (("rounds", 3, True, 9, "x"), TypeError, r"^rounds: the minimum must be an int, got bool$"),
        (("rounds", "3", 1, 9, "x"), TypeError, r"^rounds: the default must be an int, got str$"),
        (("rounds", 3, 1, 9.0, "x"), TypeError, r"^rounds: the maximum must be an int, got float$"),
        (("rounds", 3, 1, 9, " "), ValueError, r"^rounds: the help is one line of text$"),
        (("rounds", 3, 1, 9, "one\ntwo"), ValueError, r"^rounds: the help is one line of text$"),
        (("rounds", 3, 1, 9, 7), TypeError, r"^rounds help must be a str, got int$"),
    ],
)
def test_a_setting_refuses_a_bad_name_bound_default_or_help(
    fields: tuple[object, ...], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        Setting(*fields)  # type: ignore[arg-type]


def test_a_setting_takes_a_whole_number_within_its_bounds() -> None:
    assert [ROUNDS.check(value) for value in (1, 5, 9)] == [1, 5, 9]
    with pytest.raises(ValueError, match=r"^rounds must be from 1 to 9, got 0$"):
        ROUNDS.check(0)
    with pytest.raises(ValueError, match=r"^rounds must be from 1 to 9, got 10$"):
        ROUNDS.check(10)
    with pytest.raises(TypeError, match=r"^rounds must be a whole number, got bool$"):
        ROUNDS.check(True)
    with pytest.raises(TypeError, match=r"^rounds must be a whole number, got str$"):
        ROUNDS.check("3")


def test_an_entry_makes_its_strategy_from_the_defaults_or_from_given_values() -> None:
    assert ENTRY.values() == {"rounds": 3, "pause": 0}
    assert ENTRY() == _Rounds(3, 0)
    # The flat [strategy] table holds every strategy's settings: each entry takes its own.
    assert ENTRY({"rounds": 5, "pause": 2, "instalments": 12}) == _Rounds(5, 2)


def test_an_entry_refuses_a_missing_or_bad_value() -> None:
    with pytest.raises(ValueError, match=r"^missing the setting pause$"):
        ENTRY({"rounds": 5})
    with pytest.raises(ValueError, match=r"^rounds must be from 1 to 9, got 10$"):
        ENTRY({"rounds": 10, "pause": 0})
    with pytest.raises(ValueError, match=r"^pause must be from 0 to 5, got 6$"):
        ENTRY.lookback_years({"rounds": 1, "pause": 6})


def test_the_look_back_reads_the_same_values() -> None:
    assert ENTRY.lookback_years() == 4
    assert ENTRY.lookback_years({"rounds": 7, "pause": 0}) == 8


def test_buy_and_hold_has_no_settings_and_reads_nothing_before_a_run() -> None:
    entry = STRATEGIES["buy-and-hold"]
    assert entry.settings == ()
    assert entry.values() == {}
    assert entry.lookback_years() == 0
    assert entry.lookback_years({"rounds": 3}) == 0
    assert isinstance(entry({"rounds": 3}), BuyAndHold)


def test_an_entry_refuses_a_setting_twice_or_one_that_is_not_a_setting() -> None:
    with pytest.raises(ValueError, match=r"^the setting rounds is registered twice$"):
        Registered(_Rounds, "x", Turnover.LOW, (ROUNDS, ROUNDS))
    with pytest.raises(TypeError, match=r"^settings must be a tuple, got list$"):
        Registered(_Rounds, "x", Turnover.LOW, [ROUNDS])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^setting must be a Setting, got str$"):
        Registered(_Rounds, "x", Turnover.LOW, ("rounds",))  # type: ignore[arg-type]
```

**`tests/engine/test_risk.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
MERGER = Note(TRADE_FROZEN, "frozen: merger")
OPEN = Tradable(DAY, frozenset({BBCA, BBRI}), frozenset({BBCA, BBRI}), {TLKM: MERGER})

```
with:
```python
MERGER = Note(TRADE_FROZEN, "frozen: merger")
OPEN = Tradable(
    DAY,
    frozenset({BBCA, BBRI}),
    frozenset({BBCA, BBRI}),
    {TLKM: MERGER},
    frozenset({BBCA, BBRI, TLKM}),
)

```

**`tests/engine/test_view.py`** (changed: 9 edits)

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
"""MarketView and PriceHistory: prices up to the decision day, and nothing later (M3 spec §6.1)."""

```
with:
```python
"""MarketView, PriceHistory and ActionHistory: prices and dividends up to the decision day, and
nothing later (M3 spec §6.1, M6 spec §4.1)."""

```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
from decimal import Decimal

import pytest

from steadyhand._ratio import ratio_down
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
```
with:
```python
from decimal import Decimal
from functools import cache
from math import prod

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand._ratio import ratio_down
from steadyhand.market import PayDates, UnsupportedDateError, add_trading_days
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
)
from steadyhand.types import Bar, Instrument, Side
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

```
with:
```python
)
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Instrument,
    OtherAction,
    Side,
    Split,
)
from steadyhand.view import (
    ActionHistory,
    LookAheadError,
    MarketView,
    PastDividend,
    PortfolioView,
    PriceHistory,
    Tradable,
)
from steadyhand_idx import IdxMarketRules

```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
TLKM = Instrument("TLKM", "IDX", IDR)

```
with:
```python
TLKM = Instrument("TLKM", "IDX", IDR)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def pay_dates(lag: int = 14) -> PayDates:
    return PayDates(rules(), lag)

```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
def nothing_tradable(day: date) -> Tradable:
    return Tradable(day, frozenset(), frozenset(), {})


def view_on(offset: int) -> MarketView:
    today = D0 + timedelta(days=offset)
    return MarketView(history(), today, nothing_tradable(today))

```
with:
```python
def nothing_tradable(day: date) -> Tradable:
    return Tradable(day, frozenset(), frozenset(), {}, frozenset())


def view_on(offset: int, actions: ActionHistory | None = None) -> MarketView:
    today = D0 + timedelta(days=offset)
    past = ActionHistory() if actions is None else actions
    return MarketView(history(), today, nothing_tradable(today), past, pay_dates())

```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
def test_the_view_checks_its_arguments() -> None:
    with pytest.raises(TypeError, match=r"^history must be a PriceHistory, got list$"):
        MarketView([], D0, nothing_tradable(D0))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^the tradable set is for 2025-06-03, not 2025-06-02$"):
        MarketView(history(), D0, nothing_tradable(D0 + timedelta(days=1)))
    with pytest.raises(TypeError, match=r"^day must be a date, got str$"):
```
with:
```python
def test_the_view_checks_its_arguments() -> None:
    tradable = nothing_tradable(D0)
    with pytest.raises(TypeError, match=r"^history must be a PriceHistory, got list$"):
        MarketView([], D0, tradable, ActionHistory(), pay_dates())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^the tradable set is for 2025-06-03, not 2025-06-02$"):
        MarketView(
            history(), D0, nothing_tradable(D0 + timedelta(days=1)), ActionHistory(), pay_dates()
        )
    with pytest.raises(TypeError, match=r"^actions must be an ActionHistory, got tuple$"):
        MarketView(history(), D0, tradable, (), pay_dates())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^pay_dates must be a PayDates, got int$"):
        MarketView(history(), D0, tradable, ActionHistory(), 14)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^day must be a date, got str$"):
```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
def test_tradable_says_why_a_stock_cannot_be_traded() -> None:
    tradable = Tradable(D0, frozenset({BBCA}), frozenset({BBCA, BBRI}), {TLKM: RIGHTS})
    assert tradable.why_not(BBCA, Side.BUY) is None
```
with:
```python
def test_tradable_says_why_a_stock_cannot_be_traded() -> None:
    tradable = Tradable(
        D0, frozenset({BBCA}), frozenset({BBCA, BBRI}), {TLKM: RIGHTS}, frozenset({BBCA, TLKM})
    )
    assert tradable.why_not(BBCA, Side.BUY) is None
```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
def test_a_stock_cannot_be_both_tradable_and_kept_out() -> None:
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be both tradable and kept out$"):
        Tradable(D0, frozenset({BBCA}), frozenset({BBRI}), {BBRI: NO_BAR, BBCA: NO_BAR})
    with pytest.raises(TypeError, match=r"^buyable must be a frozenset, got set$"):
        Tradable(D0, {BBCA}, frozenset(), {})  # type: ignore[arg-type]

```
with:
```python
def test_a_stock_cannot_be_both_tradable_and_kept_out() -> None:
    both = {BBRI: NO_BAR, BBCA: NO_BAR}
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be both tradable and kept out$"):
        Tradable(D0, frozenset({BBCA}), frozenset({BBRI}), both, frozenset({BBCA}))
    with pytest.raises(TypeError, match=r"^buyable must be a frozenset, got set$"):
        Tradable(D0, {BBCA}, frozenset(), {}, frozenset({BBCA}))  # type: ignore[arg-type]


def test_every_buyable_stock_is_a_member_and_a_member_may_be_kept_out() -> None:
    tradable = Tradable(D0, frozenset({BBCA}), frozenset(), {TLKM: RIGHTS}, frozenset({BBCA, TLKM}))
    assert tradable.members == frozenset({BBCA, TLKM})
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be buyable outside the universe$"):
        Tradable(D0, frozenset({BBRI, BBCA, TLKM}), frozenset(), {}, frozenset({TLKM}))
    with pytest.raises(TypeError, match=r"^members must be a frozenset, got set$"):
        Tradable(D0, frozenset(), frozenset(), {}, {TLKM})  # type: ignore[arg-type]

```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
    assert ratio_down(7, 0) == 0
```
with:
```python
    assert ratio_down(7, 0) == 0


def test_the_view_shows_dividends_up_to_today_restated_in_todays_shares() -> None:
    actions = ActionHistory(
        [
            CashDividend(BBCA, D0 + timedelta(days=3), Decimal(170)),
            CashDividend(BBCA, date(2024, 4, 1), Decimal(100)),
            Split(BBCA, date(2024, 10, 1), 1, 5),
            CashDividend(BBCA, date(2024, 11, 1), Decimal(25)),
            OtherAction(BBCA, date(2024, 12, 2), "rights issue"),
        ]
    )
    view = view_on(2, actions)
    assert view.dividends(BBCA) == (
        PastDividend(date(2024, 4, 1), Decimal(20)),
        PastDividend(date(2024, 11, 1), Decimal(25)),
    )
    assert view.dividends(BBRI) == ()


def test_a_dividend_is_restated_by_each_split_from_its_own_ex_date_to_today() -> None:
    before, on, after = date(2021, 3, 1), date(2021, 6, 1), date(2022, 1, 3)
    history = ActionHistory(
        [
            CashDividend(BBCA, before, Decimal(100)),
            # Earned on the shares held before that day's split, as the engine pays it.
            CashDividend(BBCA, on, Decimal(100)),
            Split(BBCA, on, 1, 5),
            Split(BBCA, after, 5, 1),
        ]
    )
    assert history.dividends(BBCA, on - timedelta(days=1)) == (PastDividend(before, Decimal(100)),)
    assert history.dividends(BBCA, on) == (
        PastDividend(before, Decimal(20)),
        PastDividend(on, Decimal(20)),
    )
    assert history.dividends(BBCA, after) == (
        PastDividend(before, Decimal(100)),
        PastDividend(on, Decimal(100)),
    )
    # A 1-for-5 reverse split: five shares become one, so Rp 100 a share becomes Rp 500.
    reverse = ActionHistory([CashDividend(BBRI, before, Decimal(100)), Split(BBRI, on, 5, 1)])
    assert reverse.dividends(BBRI, on) == (PastDividend(before, Decimal(500)),)


def test_a_restatement_divides_once() -> None:
    # Two splits that cancel give the amount back exactly: 10 x 3 / 3, not 10 / 3 x 3.
    history = ActionHistory(
        [
            CashDividend(BBCA, date(2024, 4, 1), Decimal(10)),
            Split(BBCA, date(2024, 5, 2), 1, 3),
            Split(BBCA, date(2024, 6, 3), 3, 1),
        ]
    )
    assert history.dividends(BBCA, D0)[0].per_share == Decimal(10)
    thirds = ActionHistory(
        [CashDividend(BBCA, date(2024, 4, 1), Decimal(100)), Split(BBCA, D0, 1, 3)]
    )
    assert thirds.dividends(BBCA, D0)[0].per_share == Decimal("33.33333333333333333333333333")


def test_the_action_history_refuses_what_is_not_an_action_or_a_stock() -> None:
    with pytest.raises(TypeError, match=r"^action must be a CorporateAction, got str$"):
        ActionHistory(["BBCA"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match=r"^incomplete stock must be an Instrument, got str$"):
        ActionHistory((), ["BBCA"])  # type: ignore[list-item]


def test_a_stock_whose_look_back_was_refused_has_incomplete_history() -> None:
    history = ActionHistory((), [BBRI])
    assert history.incomplete == frozenset({BBRI})
    assert history.complete(BBCA)
    assert not history.complete(BBRI)
    view = view_on(0, history)
    assert view.history_complete(BBCA) is True
    assert view.history_complete(BBRI) is False
    assert ActionHistory().incomplete == frozenset()


def test_the_pay_date_is_the_engines_and_a_later_ex_date_is_look_ahead() -> None:
    view = view_on(2)
    assert view.today == date(2025, 6, 4)
    assert view.pay_date(date(2025, 5, 20)) == date(2025, 6, 13)
    assert view.pay_date(date(2025, 5, 20)) == add_trading_days(rules(), date(2025, 5, 20), 14)
    assert view.pay_date(view.today) == date(2025, 6, 26)
    one_day = MarketView(history(), D0, nothing_tradable(D0), ActionHistory(), pay_dates(1))
    assert one_day.pay_date(date(2025, 5, 20)) == date(2025, 5, 21)
    with pytest.raises(LookAheadError, match=r"^asked for 2025-06-05 while deciding on 2025-06-04"):
        view.pay_date(D0 + timedelta(days=3))


def test_an_ex_date_the_rules_cannot_place_raises_their_own_error() -> None:
    with pytest.raises(UnsupportedDateError, match=r"; 2015-12-31 is earlier$"):
        view_on(0).pay_date(date(2015, 12, 30))


_STOCKS = st.sampled_from([BBCA, BBRI])
_DAYS = st.dates(min_value=date(2019, 1, 1), max_value=date(2021, 12, 31))
_DIVIDEND = st.builds(CashDividend, _STOCKS, _DAYS, st.integers(1, 10_000).map(Decimal))
_SPLIT = st.builds(
    lambda stock, day, shares: Split(stock, day, *shares),
    _STOCKS,
    _DAYS,
    st.tuples(st.integers(1, 10), st.integers(1, 10)).filter(lambda pair: pair[0] != pair[1]),
)


@given(st.lists(st.one_of(_DIVIDEND, _SPLIT), max_size=12), _DAYS)
def test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits(
    actions: list[CorporateAction], today: date
) -> None:
    history = ActionHistory(actions)
    for stock in (BBCA, BBRI):
        paid = sorted(
            (
                action
                for action in actions
                if isinstance(action, CashDividend)
                and action.instrument == stock
                and action.ex_date <= today
            ),
            key=lambda action: action.ex_date,
        )
        found = history.dividends(stock, today)
        assert all(dividend.ex_date <= today for dividend in found)
        assert [dividend.ex_date for dividend in found] == [dividend.ex_date for dividend in paid]
        for dividend, source in zip(found, paid, strict=True):
            splits = [
                action
                for action in actions
                if isinstance(action, Split)
                and action.instrument == stock
                and source.ex_date <= action.ex_date <= today
            ]
            old = prod(split.old_shares for split in splits)
            new = prod(split.new_shares for split in splits)
            assert dividend.per_share == source.per_share * old / new
```

**`tests/meta/test_legal_line.py`** (changed: 1 edit)

<!-- edit: tests/meta/test_legal_line.py -->
Replace:
```python
                    found.append(f"{name}: {statement[0]}")
    assert checked >= 8, "no training module's imports were read"
    assert found == []
```
with:
```python
                    found.append(f"{name}: {statement[0]}")
    assert checked >= 8, "fewer than 8 training modules' imports were read"
    assert found == []
```

**`tests/meta/test_note_keys.py`** (changed: 2 edits)

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
    }
    assert len(elsewhere) >= 30, "the packages' modules were not found"
    assert any(name.startswith("steadyhand-idx/") for name in elsewhere)
```
with:
```python
    }
    assert len(elsewhere) >= 30, "fewer than 30 of the packages' modules were found"
    assert any(name.startswith("steadyhand-idx/") for name in elsewhere)
```

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
    ]
    assert len(used) >= len(names) >= 6, "no Note(...) call was found in the packages"
    assert any(note_keys(source) for path, source in sources.items() if IDX in path.parents)
```
with:
```python
    ]
    assert len(used) >= len(names) >= 6, "fewer Note(...) calls in the packages than note keys"
    assert any(note_keys(source) for path, source in sources.items() if IDX in path.parents)
```

**`tests/meta/test_strategy_guides.py`** (changed: 5 edits)

<!-- edit: tests/meta/test_strategy_guides.py -->
Replace:
```python
"""Every registered strategy has a complete plain-English guide (core spec §8, §10.1), shipped
inside the package (M5 spec §5.6).

```
with:
```python
"""Every registered strategy has a complete plain-English guide (core spec §8, §10.1), shipped
inside the package (M5 spec §5.6), whose *Settings you can change* names each of the strategy's
registered settings (M6 spec §7).

```

<!-- edit: tests/meta/test_strategy_guides.py -->
Replace:
```python

from steadyhand.strategies import STRATEGIES, Strategy

```
with:
```python

from steadyhand.strategies import STRATEGIES, Setting, Strategy

```

<!-- edit: tests/meta/test_strategy_guides.py -->
Replace:
```python

def problems(name: str, markdown: str) -> list[str]:
    found = sections(markdown)
    wrong = [f"missing or empty: {section}" for section in SECTIONS if not found.get(section)]
    risks = found.get("Risks", "").lower()
```
with:
```python

def problems(name: str, markdown: str, settings: tuple[Setting, ...] = ()) -> list[str]:
    found = sections(markdown)
    wrong = [f"missing or empty: {section}" for section in SECTIONS if not found.get(section)]
    named = found.get("Settings you can change", "")
    wrong += [
        f"Settings you can change must name `{setting.name}`"
        for setting in settings
        if f"`{setting.name}`" not in named
    ]
    risks = found.get("Risks", "").lower()
```

<!-- edit: tests/meta/test_strategy_guides.py -->
Replace:
```python

def test_a_complete_guide_has_no_problems() -> None:
    assert problems("x", complete("x")) == []

```
with:
```python

ROUNDS = Setting("rounds", 3, 1, 9, "How many rounds to play.")


def test_a_complete_guide_has_no_problems() -> None:
    assert problems("x", complete("x")) == []
    named = complete("x").replace(
        "## Settings you can change\nWords.", "## Settings you can change\n`rounds`."
    )
    assert problems("x", named, (ROUNDS,)) == []


@pytest.mark.parametrize(
    "settings_text",
    [
        "Words.",
        "rounds, written without its backticks.",
        "<!-- `rounds` -->",
    ],
)
def test_the_checker_wants_each_setting_named_in_its_section(settings_text: str) -> None:
    guide = complete("x").replace(
        "## Settings you can change\nWords.", f"## Settings you can change\n{settings_text}"
    )
    # Named elsewhere does not count: only the settings section says what can be changed.
    guide = guide.replace("## Risks\nWords.", "## Risks\nWords. `rounds`.")
    assert guide.count("## Settings you can change\n") == 1
    assert "Settings you can change must name `rounds`" in problems("x", guide, (ROUNDS,))

```

<!-- edit: tests/meta/test_strategy_guides.py -->
Replace:
```python
        name: wrong
        for name in STRATEGIES
        if (wrong := problems(name, (GUIDES / f"{name}.md").read_text(encoding="utf-8")))
    }
```
with:
```python
        name: wrong
        for name, entry in STRATEGIES.items()
        if (
            wrong := problems(
                name, (GUIDES / f"{name}.md").read_text(encoding="utf-8"), entry.settings
            )
        )
    }
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 8 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.market import MarketRules, UnsupportedDateError, add_trading_days
from steadyhand.metrics import (
```
with:
```python
)
from steadyhand.market import MarketRules, PayDates, UnsupportedDateError, add_trading_days
from steadyhand.metrics import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    DATA_BAR_REFUSED,
    EXEMPTION_CLAIM_BROKEN,
```
with:
```python
    DATA_BAR_REFUSED,
    DATA_DIVIDENDS_HISTORY_REFUSED,
    EXEMPTION_CLAIM_BROKEN,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    Registered,
    Strategy,
```
with:
```python
    Registered,
    Setting,
    Strategy,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
from steadyhand.universe import Universe
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

```
with:
```python
from steadyhand.universe import Universe
from steadyhand.view import (
    ActionHistory,
    LookAheadError,
    MarketView,
    PastDividend,
    PortfolioView,
    PriceHistory,
    Tradable,
)

```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "DATA_BAR_REFUSED",
    "DISCLAIMER",
```
with:
```python
    "DATA_BAR_REFUSED",
    "DATA_DIVIDENDS_HISTORY_REFUSED",
    "DISCLAIMER",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "YEAR_DAYS",
    "BacktestResult",
```
with:
```python
    "YEAR_DAYS",
    "ActionHistory",
    "BacktestResult",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "OtherAction",
    "PaymentCalendar",
```
with:
```python
    "OtherAction",
    "PastDividend",
    "PayDates",
    "PaymentCalendar",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "ScenarioProjection",
    "Side",
```
with:
```python
    "ScenarioProjection",
    "Setting",
    "Side",
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, then repeats ``run_day`` over the trading days: once for the strategy and once, with the
same settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work. With an income goal
```
with:
```python
``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, and with a look-back the corporate actions of the years before it (M6 spec §4.3), then
repeats ``run_day`` over the trading days: once for the strategy and once, with the same
settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work. With an income goal
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

from steadyhand._validate import require_date, require_type
from steadyhand.data import DataSource, UnavailableDaysError
from steadyhand.engine import DayInputs, DayReport, EngineSettings, EngineState, run_day
```
with:
```python

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
from steadyhand.engine import DayInputs, DayReport, EngineSettings, EngineState, run_day
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_REFUSED, Note
from steadyhand.risk import Halt
```
with:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_REFUSED, DATA_DIVIDENDS_HISTORY_REFUSED, Note
from steadyhand.risk import Halt
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
from steadyhand.universe import Universe
from steadyhand.view import PriceHistory

```
with:
```python
from steadyhand.universe import Universe
from steadyhand.view import ActionHistory, PriceHistory

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    return warnings
```
with:
```python
    return warnings


def _history_warnings(window: _Window) -> list[Note]:
    """One warning per stock whose look-back the source refused, naming the range and why."""
    raise NotImplementedError("_history_warnings")
```

**`packages/steadyhand/src/steadyhand/engine.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
from steadyhand.exemption import cover_claims, settle_claims
from steadyhand.market import MarketRules
from steadyhand.money import Money
```
with:
```python
from steadyhand.exemption import cover_claims, settle_claims
from steadyhand.market import MarketRules, PayDates
from steadyhand.money import Money
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
from steadyhand.types import CorporateAction, Fill, Instrument, Order, Split
from steadyhand.view import MarketView, PortfolioView, PriceHistory, Tradable

```
with:
```python
from steadyhand.types import CorporateAction, Fill, Instrument, Order, Split
from steadyhand.view import ActionHistory, MarketView, PortfolioView, PriceHistory, Tradable

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python

def _validate(inputs: DayInputs, rules: MarketRules) -> None:
```
with:
```python

def _prices(
    closes: Mapping[Instrument, Money], weights: Mapping[Instrument, Decimal], view: MarketView
) -> dict[Instrument, Money]:
    """Each held stock's close, and the last close of each other stock the strategy weighted."""
    raise NotImplementedError("_prices")


def _validate(inputs: DayInputs, rules: MarketRules) -> None:
```

**`packages/steadyhand/src/steadyhand/market.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python

from datetime import date, timedelta
from typing import Protocol, runtime_checkable

from steadyhand._validate import require_int
from steadyhand.money import Currency, Money
```
with:
```python

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol, runtime_checkable

from steadyhand._validate import require_int, require_type
from steadyhand.money import Currency, Money
```

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python
    return current
```
with:
```python
    return current


@dataclass(frozen=True, slots=True)
class PayDates:
    """When a dividend is modelled as paid: ``lag_trading_days`` trading days after its ex-date,
    by ``rules`` (core spec §5 step 2), through ``add_trading_days`` like the engine's payout."""

    rules: MarketRules
    lag_trading_days: int

    def __post_init__(self) -> None:
        return

    def of(self, ex_date: date) -> date:
        """The modelled pay date of a dividend with *ex_date*."""
        raise NotImplementedError("PayDates.of")
```

**`packages/steadyhand/src/steadyhand/notes.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/notes.py -->
Replace:
```python
"""The data source refused a stock's days in a backtest, so it was not traded on them."""

```
with:
```python
"""The data source refused a stock's days in a backtest, so it was not traded on them."""

DATA_DIVIDENDS_HISTORY_REFUSED = "data.dividends.history_refused"
"""The data source refused a stock's corporate actions before the run, so its dividend history
is incomplete (M6 spec §4.3)."""

```

**`packages/steadyhand/src/steadyhand/strategies/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/__init__.py -->
Replace:
```python
from steadyhand.strategies.protocol import Decision, InvalidWeightsError, Memory, Strategy
from steadyhand.strategies.registry import GUIDES, STRATEGIES, Registered, Turnover, guide

```
with:
```python
from steadyhand.strategies.protocol import Decision, InvalidWeightsError, Memory, Strategy
from steadyhand.strategies.registry import (
    GUIDES,
    STRATEGIES,
    Registered,
    Setting,
    Turnover,
    guide,
)

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/__init__.py -->
Replace:
```python
    "Registered",
    "Strategy",
```
with:
```python
    "Registered",
    "Setting",
    "Strategy",
```

**`packages/steadyhand/src/steadyhand/strategies/protocol.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/protocol.py -->
Replace:
```python
from steadyhand._validate import require_type
from steadyhand.types import Instrument
```
with:
```python
from steadyhand._validate import require_type
from steadyhand.notes import Note
from steadyhand.types import Instrument
```

**`packages/steadyhand/src/steadyhand/strategies/registry.py`** (changed, new names stubbed: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python

Each one has a one-line summary, how much it trades, and a complete plain-English guide in
``guides/<name>.md``, which ships inside the package (core spec §8, §10.1; M5 spec §5.5, §5.6).
"""

from collections.abc import Callable, Mapping
```
with:
```python

Each one has a one-line summary, how much it trades, its settings, how many years of corporate
actions before a run it reads, and a complete plain-English guide in ``guides/<name>.md``, which
ships inside the package (core spec §8, §10.1; M5 spec §5.5, §5.6; M6 spec §4.3, §4.5).
"""

import re
from collections.abc import Callable, Mapping
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python

from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy

```
with:
```python

from steadyhand._validate import require_type
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy

_NAME = re.compile(r"[a-z]+(_[a-z]+)*")

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
    HIGH = "high"

```
with:
```python
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Setting:
    """One of a strategy's settings: a whole number, its default and bounds, and the one line of
    help ``init`` writes above its key in ``steadyhand.toml`` (M6 spec §4.5)."""

    name: str
    default: int
    minimum: int
    maximum: int
    help: str

    def __post_init__(self) -> None:
        return

    def check(self, value: object) -> int:
        """*value*, once it is a whole number within the bounds."""
        raise NotImplementedError("Setting.check")


def _no_lookback(values: Mapping[str, int]) -> int:
    raise NotImplementedError("_no_lookback")

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python

    def __call__(self) -> Strategy:
        return self.make()

```
with:
```python

    def __post_init__(self) -> None:
        return

    def values(self, given: Mapping[str, int] | None = None) -> dict[str, int]:
        """This strategy's settings, checked: each from *given*, which may hold other
        strategies' settings too, as the flat ``[strategy]`` table does, or every default."""
        raise NotImplementedError("Registered.values")

    def __call__(self) -> Strategy:
        return self.make()

    def lookback_years(self, values: Mapping[str, int] | None = None) -> int:
        """The calendar years of corporate actions the strategy reads before a run's first
        day: 0 for a strategy that reads none."""
        raise NotImplementedError("Registered.lookback_years")

```

**`packages/steadyhand/src/steadyhand/view.py`** (changed, new names stubbed: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
"""What a strategy may see on a decision day: prices up to that day, and nothing later.

``PriceHistory`` holds every bar a run can use and is built once. Each day gets a cheap
``MarketView`` over it, which refuses any date after its own day with ``LookAheadError`` (core
spec §4.3). A backtest that peeks at tomorrow's price looks brilliant and means nothing.
```
with:
```python
"""What a strategy may see on a decision day: prices and dividends up to that day, and nothing
later.

``PriceHistory`` holds every bar a run can use, and ``ActionHistory`` every corporate action,
the look-back's included (M6 spec §4.1). Both are built once. Each day gets a cheap
``MarketView`` over them, which refuses any date after its own day with ``LookAheadError`` (core
spec §4.3). A backtest that peeks at tomorrow's price looks brilliant and means nothing.
```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
from itertools import pairwise

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import TRADE_NOT_HELD, TRADE_NOT_IN_UNIVERSE, Note
from steadyhand.types import Bar, Instrument, Side

```
with:
```python
from itertools import pairwise
from math import prod

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_type
from steadyhand.market import PayDates
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import TRADE_NOT_HELD, TRADE_NOT_IN_UNIVERSE, Note
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Instrument,
    OtherAction,
    Side,
    Split,
)

```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
        return self._bars[instrument][index - 1] if index else None

```
with:
```python
        return self._bars[instrument][index - 1] if index else None


@dataclass(frozen=True, slots=True)
class PastDividend:
    """A cash dividend as a strategy sees it (M6 spec §4.1): its ex-date, and its amount per
    share restated in today's shares, so that one year's dividends compare with another's."""

    ex_date: date
    per_share: Decimal


class ActionHistory:
    """Every corporate action a run loaded, the look-back's included, and the stocks whose
    look-back the data source refused (M6 spec §4.1, §4.3). It answers for any day."""

    def __init__(
        self, actions: Iterable[CorporateAction] = (), incomplete: Iterable[Instrument] = ()
    ) -> None:
        raise NotImplementedError("ActionHistory.__init__")

    @property
    def incomplete(self) -> frozenset[Instrument]:
        """The stocks whose look-back the data source refused."""
        raise NotImplementedError("ActionHistory.incomplete")

    def dividends(self, instrument: Instrument, today: date) -> tuple[PastDividend, ...]:
        """The stock's cash dividends with an ex-date on or before *today*, oldest first.

        Each is restated by every split from its own ex-date to *today*: a dividend is earned on
        the shares held before that day's split (``corporate._Actions``), so a split on the same
        day restates it too. After a 1-for-5 reverse split, a Rp 100 dividend is Rp 500 a share.
        """
        raise NotImplementedError("ActionHistory.dividends")

    def complete(self, instrument: Instrument) -> bool:
        """Whether the data source gave the stock's whole look-back."""
        raise NotImplementedError("ActionHistory.complete")


def _restated(per_share: Decimal, splits: list[Split]) -> Decimal:
    """*per_share* in the shares left after *splits*: one division, so it rounds once."""
    raise NotImplementedError("_restated")

```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python

    def _checked(self, day: date) -> date:
```
with:
```python

    def dividends(self, instrument: Instrument) -> tuple[PastDividend, ...]:
        """The stock's cash dividends with an ex-date on or before today, oldest first, each
        restated in today's shares."""
        raise NotImplementedError("MarketView.dividends")

    def pay_date(self, ex_date: date) -> date:
        """The modelled pay date of a dividend with *ex_date*, on or before today: the engine's
        and the income calendar's, from ``add_trading_days`` (M4 spec §3.1)."""
        raise NotImplementedError("MarketView.pay_date")

    def history_complete(self, instrument: Instrument) -> bool:
        """False when the data source refused any part of the stock's look-back (M6 §4.3)."""
        raise NotImplementedError("MarketView.history_complete")

    def _checked(self, day: date) -> date:
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1439 failed=35 -->
Expected: 1439 run, 35 failed (pytest reads `33 failed, 2 errors`). The two errors are `tests/engine/test_registry.py` and `tests/engine/test_risk.py`, which build `Registered` and `Tradable` with their new fields at module level and so cannot be collected while the classes keep their old fields (the tests in them run in the gate, 1486 in all). 12 failures are `NotImplementedError` from the stubs; 16 are `TypeError` and 3 `AttributeError` from the fields and arguments not there yet (`Tradable.members`, `BacktestSettings.lookback_years`, `Decision.notes`, `DayInputs.past_actions`, `Registered.settings`, `day_inputs`'s fourth argument); the last two are the lesson guard (`data.dividends.history_refused` has no lesson yet) and the note-key guard (`fewer Note(...) calls in the packages than note keys`: the new key is not used until `_history_warnings` is written). Seven new or changed tests pass against the stubs by design: `test_a_halted_day_asks_the_strategy_nothing_so_it_says_nothing` pins behaviour that does not change; `test_training_imports_nothing_that_decides` and `test_no_key_is_defined_twice` changed only their messages; and the guide checker is test code, not a stub, so `test_a_complete_guide_has_no_problems` and three cases of `test_the_checker_wants_each_setting_named_in_its_section` run it for real.

- [ ] **Step 5: Implement.** The lesson's new paragraph is part of this step.

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented, rewritten whole)

<!-- file: packages/steadyhand/src/steadyhand/backtest.py -->
```python
"""The backtester: a strategy and the ``buy-and-hold`` baseline over a range of days (M3 spec §7).

``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, and with a look-back the corporate actions of the years before it (M6 spec §4.3), then
repeats ``run_day`` over the trading days: once for the strategy and once, with the same
settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work. With an income goal
set, each run also gets an income report on its last day, from dividend history fetched then.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
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
from steadyhand.notes import DATA_BAR_REFUSED, DATA_DIVIDENDS_HISTORY_REFUSED, Note
from steadyhand.risk import Halt
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy
from steadyhand.types import Bar, CorporateAction, Instrument
from steadyhand.universe import Universe
from steadyhand.view import ActionHistory, PriceHistory


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
    """The capital a run starts with, how the engine runs each day, an optional income goal, and
    how many calendar years of corporate actions before the first day to fetch.

    Both runs share them. With a ``goal``, each run's result carries an income report. The
    caller sets ``lookback_years`` from the registered strategy's (M6 spec §4.3), so the engine
    never reads the registry.
    """

    capital: Money
    engine: EngineSettings = field(default_factory=EngineSettings)
    goal: IncomeGoal | None = None
    lookback_years: int = 0

    def __post_init__(self) -> None:
        require_type(self.capital, Money, "capital")
        require_type(self.engine, EngineSettings, "engine")
        require_int(self.lookback_years, "lookback_years", minimum=0)
        if self.capital.amount <= 0:
            msg = f"the starting capital must be positive, got {self.capital}"
            raise ValueError(msg)
        if self.goal is not None:
            require_type(self.goal, IncomeGoal, "goal")
            if self.goal.monthly_target.currency != self.capital.currency:
                raise CurrencyMismatchError(
                    self.capital.currency, self.goal.monthly_target.currency
                )


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
    def warnings(self) -> tuple[Note, ...]:
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
    warnings: tuple[Note, ...]
    income_impact: IncomeImpact | None = None


@dataclass(frozen=True, slots=True)
class Comparison:
    """Several strategies run over one window (M5 spec §5.4).

    ``runs`` holds each strategy's run in the order they were named, then the baseline's unless
    it was named. ``warnings`` are about the data every run shares, as in ``BacktestResult``.
    """

    start: date
    end: date
    runs: tuple[RunResult, ...]
    warnings: tuple[Note, ...]


@dataclass(frozen=True, slots=True)
class _Window:
    """Everything both runs read: the trading days, the universe on each, and the fetched data.

    ``past`` holds every corporate action fetched, the look-back's included; ``lookback`` is the
    look-back's first and last day, and ``history_refused`` why the source refused a stock's.
    """

    days: tuple[date, ...]
    members: Mapping[date, frozenset[Instrument]]
    excluded: Mapping[date, Mapping[Instrument, str]]
    history: PriceHistory
    actions: Mapping[date, tuple[CorporateAction, ...]]
    refused: Mapping[Instrument, tuple[date, ...]]
    past: ActionHistory
    lookback: tuple[date, date] | None
    history_refused: Mapping[Instrument, str]


def backtest(
    strategy: Strategy, market: Market, start: date, end: date, settings: BacktestSettings
) -> BacktestResult:
    """Run *strategy* and the baseline from *start* to *end*, both inclusive (M3 spec §7.1)."""
    window = _window(market, start, end, settings)
    inputs = _inputs(window)
    run = _complete(_run(strategy, inputs, market.rules, settings), market, settings)
    baseline = BuyAndHold()
    compared = (
        None
        if strategy.name == baseline.name
        else _complete(_run(baseline, inputs, market.rules, settings), market, settings)
    )
    warnings = _data_warnings(market, window, start, end)
    return BacktestResult(start, end, run, compared, warnings, _impact(run, compared))


def compare(
    strategies: Sequence[Strategy],
    market: Market,
    start: date,
    end: date,
    settings: BacktestSettings,
) -> Comparison:
    """Run each of *strategies*, and the baseline unless it is one of them, over one window
    fetched once (M5 spec §5.4). The caller sets the longest look-back among them."""
    for strategy in strategies:
        require_type(strategy, Strategy, "strategy")
    names = [strategy.name for strategy in strategies]
    if not names:
        msg = "name at least one strategy to compare"
        raise ValueError(msg)
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        msg = f"{twice[0]} is named twice; name each strategy once"
        raise ValueError(msg)
    window = _window(market, start, end, settings)
    inputs = _inputs(window)
    baseline = BuyAndHold()
    everyone = (*strategies, *(() if baseline.name in names else (baseline,)))
    runs = tuple(
        _complete(_run(strategy, inputs, market.rules, settings), market, settings)
        for strategy in everyone
    )
    return Comparison(start, end, runs, _data_warnings(market, window, start, end))


def day_inputs(
    market: Market, start: date, end: date, lookback_years: int = 0
) -> tuple[DayInputs, ...]:
    """Every trading day's inputs from *start* to *end*, both inclusive, oldest first.

    This is a backtest's fetch step, public so that paper trading builds each day exactly as a
    backtest over the same range does (M5 spec §6.2). ``refused`` and ``resumed`` depend on the
    days before the one run, so a caller that runs only the later days still fetches from the
    first, and the look-back reaches back from *start* as a backtest's does (M6 spec §4.3).
    """
    require_type(market, Market, "market")
    require_date(start, "start")
    require_date(end, "end")
    require_int(lookback_years, "lookback_years", minimum=0)
    if end < start:
        msg = f"the range ends on {end.isoformat()}, before it starts on {start.isoformat()}"
        raise ValueError(msg)
    return _inputs(_fetch(market, _days(market, start, end), lookback_years))


def _window(market: Market, start: date, end: date, settings: BacktestSettings) -> _Window:
    """Check a run's arguments, then fetch what every strategy over them reads."""
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
    return _fetch(market, _days(market, start, end), settings.lookback_years)


def _days(market: Market, start: date, end: date) -> tuple[date, ...]:
    """The trading days from *start* to *end*, once the rules and the universe cover them."""
    rules = market.rules
    rules.require_supported(start)
    first = market.universe.first_day()
    if start < first:
        raise UniverseCoverageError(start, first)
    days = tuple(day for day in _calendar_days(start, end) if rules.is_trading_day(day))
    if not days:
        msg = f"there is no trading day from {start.isoformat()} to {end.isoformat()}"
        raise NoTradingDaysError(msg)
    return days


def _complete(run: RunResult, market: Market, settings: BacktestSettings) -> RunResult:
    """*run*, with its income report when the settings set a goal."""
    if settings.goal is None:
        return run
    return replace(run, income=income_of(run.reports, run.final, market, settings, settings.goal))


def _data_warnings(market: Market, window: _Window, start: date, end: date) -> tuple[Note, ...]:
    return (
        *market.universe.survivorship_warnings(start, end),
        *_refused_warnings(window),
        *_history_warnings(window),
    )


def _calendar_days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _fetch(market: Market, days: tuple[date, ...], lookback_years: int) -> _Window:
    """Fetch every stock the universe holds on any of *days*, over all of them (M3 spec §7.1).

    A stock whose source refuses some days is fetched again over the clean ranges around them.
    With a look-back, each stock's corporate actions from 1 January, *lookback_years* years
    before the first day, to the day before it are fetched in a call of their own: a refusal
    there is history the run can do without, so it marks the stock's history incomplete and the
    run goes on (M6 spec §4.3).
    """
    members = {day: market.universe.members_on(day) for day in days}
    excluded = {day: market.universe.excluded_on(day) for day in days}
    source = market.source
    start, end = days[0], days[-1]
    stocks = sorted(frozenset().union(*members.values()), key=lambda i: (i.market, i.symbol))
    bars: list[Bar] = []
    actions: list[CorporateAction] = []
    refused: dict[Instrument, tuple[date, ...]] = {}
    for stock in stocks:
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
    past = list(actions)
    lookback = None
    history_refused: dict[Instrument, str] = {}
    if lookback_years:
        lookback = (date(start.year - lookback_years, 1, 1), start - timedelta(days=1))
        for stock in stocks:
            try:
                past += source.corporate_actions(stock, *lookback)
            except DataUnavailableError as error:
                history_refused[stock] = str(error)
    return _Window(
        days,
        members,
        excluded,
        PriceHistory(bars),
        grouped,
        refused,
        ActionHistory(past, history_refused),
        lookback,
        history_refused,
    )


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


def _inputs(window: _Window) -> tuple[DayInputs, ...]:
    """Each day of *window* as the engine takes it (M3 spec §7.1)."""
    inputs: list[DayInputs] = []
    for day in window.days:
        refused = frozenset(stock for stock, found in window.refused.items() if day in found)
        inputs.append(
            DayInputs(
                day,
                window.history,
                window.actions.get(day, ()),
                window.members[day],
                window.excluded[day],
                refused,
                _resumed(window, day) - refused,
                window.past,
            )
        )
    return tuple(inputs)


def _run(
    strategy: Strategy,
    inputs: Sequence[DayInputs],
    rules: MarketRules,
    settings: BacktestSettings,
) -> RunResult:
    state = EngineState.opening(settings.capital, inputs[0].day)
    reports: list[DayReport] = []
    for day in inputs:
        state, report = run_day(state, day, strategy, rules, settings.engine)
        reports.append(report)
    return RunResult(strategy.name, tuple(reports), state, measure(reports, state))


def income_of(
    reports: Sequence[DayReport],
    final: EngineState,
    market: Market,
    settings: BacktestSettings,
    goal: IncomeGoal,
) -> IncomeReport:
    """The income report of a run whose day reports, in order, are *reports* and whose state
    after the last is *final*, from each final holding's history as *market*'s source gives it.
    A backtest and a paper account's ``report --income`` both build theirs here.

    A source that cannot give the history raises, and the caller stops: an income report is
    never built on missing history (M4 spec §8).
    """
    as_of = reports[-1].day
    since = years_before(as_of, HISTORY_YEARS)
    history = {
        position.instrument: tuple(
            market.source.corporate_actions(position.instrument, since, as_of)
        )
        for position in final.holdings.portfolio.positions
    }
    engine = settings.engine
    plan = IncomeSettings(goal, engine.monthly_contribution, engine.pay_lag_trading_days)
    return income_report(reports, final, history, market.rules, plan)


def _impact(run: RunResult, baseline: RunResult | None) -> IncomeImpact | None:
    if baseline is None or run.income is None or baseline.income is None:
        return None
    ours, theirs = run.income.goal, baseline.income.goal
    return IncomeImpact(ours.received - theirs.received, ours.run_rate - theirs.run_rate)


def _resumed(window: _Window, day: date) -> frozenset[Instrument]:
    """Stocks with a refused day between their last bar and *day*: no usable previous close."""
    resumed: set[Instrument] = set()
    for stock, refused in window.refused.items():
        previous = window.history.before(stock, day)
        after = bisect_left(refused, previous.day) if previous is not None else 0
        if after < len(refused) and refused[after] < day:
            resumed.add(stock)
    return frozenset(resumed)


def _refused_warnings(window: _Window) -> list[Note]:
    """One warning per stock, naming each span of consecutive refused trading days."""
    warnings: list[Note] = []
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
            Note(
                DATA_BAR_REFUSED,
                f"{stock.symbol}: the data source refused {len(refused)} day(s) ({named}), so it "
                "was not traded on them, and a holding was valued at its last clean close. A "
                "dividend whose ex-date falls on a refused day is unknown and was not credited.",
            )
        )
    return warnings


def _history_warnings(window: _Window) -> list[Note]:
    """One warning per stock whose look-back the source refused, naming the range and why."""
    if window.lookback is None:
        return []
    since, until = (day.isoformat() for day in window.lookback)
    return [
        Note(
            DATA_DIVIDENDS_HISTORY_REFUSED,
            f"{stock.symbol}: the data source refused its corporate actions from {since} to "
            f"{until}, before the run ({window.history_refused[stock]}), so its dividend "
            "history is incomplete for any strategy that reads it.",
        )
        for stock in sorted(window.history_refused, key=lambda i: (i.market, i.symbol))
    ]
```

**`packages/steadyhand/src/steadyhand/engine.py`** (implemented: 10 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    §7.3), and ``resumed`` those whose data is clean again today after refused days, which have
    no usable previous close for the band check.
    """
```
with:
```python
    §7.3), and ``resumed`` those whose data is clean again today after refused days, which have
    no usable previous close for the band check. ``past_actions`` holds every corporate action
    the run loaded, the look-back's included, for the strategy's view (M6 spec §4.1).
    """
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    resumed: frozenset[Instrument] = frozenset()

```
with:
```python
    resumed: frozenset[Instrument] = frozenset()
    past_actions: ActionHistory = field(default_factory=ActionHistory)

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
            require_type(getattr(self, name), frozenset, name)

```
with:
```python
            require_type(getattr(self, name), frozenset, name)
        require_type(self.past_actions, ActionHistory, "past_actions")

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    notes: tuple[Note, ...] = ()
    """The day's exemption-claim events (M4 spec §6.3, §6.4). Empty with the switch off."""

```
with:
```python
    notes: tuple[Note, ...] = ()
    """The day's exemption-claim events (M4 spec §6.3, §6.4), then what the strategy said about
    the day (M6 spec §4.4)."""

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    memory = state.memory
    if halt is None:
```
with:
```python
    memory = state.memory
    strategy_notes: tuple[Note, ...] = ()
    if halt is None:
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        seen = PortfolioView(value, spendable, worth)
        view = MarketView(history, day, tradable)
        decision = strategy.decide(view, seen, state.memory)
        prices = dict(closes)
        for stock in decision.weights:
            if stock not in prices and (close := view.last_close(stock)) is not None:
                prices[stock] = close
        sized = CompoundingSizer(rules).size(decision.weights, seen, held, prices, day)
```
with:
```python
        seen = PortfolioView(value, spendable, worth)
        view = MarketView(
            history,
            day,
            tradable,
            inputs.past_actions,
            PayDates(rules, settings.pay_lag_trading_days),
        )
        decision = strategy.decide(view, seen, state.memory)
        prices = _prices(closes, decision.weights, view)
        sized = CompoundingSizer(rules).size(decision.weights, seen, held, prices, day)
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        memory = decision.memory

```
with:
```python
        memory = decision.memory
        strategy_notes = decision.notes

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        warnings=(*corporate.warnings, *warnings),
        notes=claimed.notes,
    )
```
with:
```python
        warnings=(*corporate.warnings, *warnings),
        notes=(*claimed.notes, *strategy_notes),
    )
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    """Each held stock's close, and the last close of each other stock the strategy weighted."""
    raise NotImplementedError("_prices")

```
with:
```python
    """Each held stock's close, and the last close of each other stock the strategy weighted."""
    prices = dict(closes)
    for stock in weights:
        if stock not in prices and (close := view.last_close(stock)) is not None:
            prices[stock] = close
    return prices

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    sellable = frozenset(held - reasons.keys())
    return Tradable(day, buyable, sellable, reasons), warnings

```
with:
```python
    sellable = frozenset(held - reasons.keys())
    return Tradable(day, buyable, sellable, reasons, inputs.members), warnings

```

**`packages/steadyhand/src/steadyhand/market.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python
    def __post_init__(self) -> None:
        return

    def of(self, ex_date: date) -> date:
        """The modelled pay date of a dividend with *ex_date*."""
        raise NotImplementedError("PayDates.of")
```
with:
```python
    def __post_init__(self) -> None:
        require_type(self.rules, MarketRules, "rules")
        require_int(self.lag_trading_days, "lag_trading_days", minimum=1)

    def of(self, ex_date: date) -> date:
        """The modelled pay date of a dividend with *ex_date*."""
        return add_trading_days(self.rules, ex_date, self.lag_trading_days)
```

**`packages/steadyhand/src/steadyhand/strategies/protocol.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/protocol.py -->
Replace:
```python
class Decision:
    """A strategy's answer for one day: target weights, and what to remember until tomorrow.

    A stock missing from ``weights`` is targeted at zero. Weights are ``Decimal``, none is
    negative, and together they are at most 1; the rest is held as cash.
    """
```
with:
```python
class Decision:
    """A strategy's answer for one day: target weights, what to remember until tomorrow, and
    anything it says about the day.

    A stock missing from ``weights`` is targeted at zero. Weights are ``Decimal``, none is
    negative, and together they are at most 1; the rest is held as cash. The engine adds
    ``notes`` to the day's report after its own (M6 spec §4.4).
    """
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/protocol.py -->
Replace:
```python
    memory: Memory = field(default_factory=dict)

```
with:
```python
    memory: Memory = field(default_factory=dict)
    notes: tuple[Note, ...] = ()

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/protocol.py -->
Replace:
```python
            require_type(value, str, "memory value")

```
with:
```python
            require_type(value, str, "memory value")
        require_type(self.notes, tuple, "notes")
        for note in self.notes:
            require_type(note, Note, "note")

```

**`packages/steadyhand/src/steadyhand/strategies/registry.py`** (implemented: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
    def __post_init__(self) -> None:
        return

    def check(self, value: object) -> int:
        """*value*, once it is a whole number within the bounds."""
        raise NotImplementedError("Setting.check")


def _no_lookback(values: Mapping[str, int]) -> int:
    raise NotImplementedError("_no_lookback")

```
with:
```python
    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            msg = f"a setting's name is a lowercase identifier, got {self.name!r}"
            raise ValueError(msg)
        for part in ("default", "minimum", "maximum"):
            value = getattr(self, part)
            if type(value) is not int:
                msg = f"{self.name}: the {part} must be an int, got {type(value).__name__}"
                raise TypeError(msg)
        if not self.minimum <= self.default <= self.maximum:
            msg = (
                f"{self.name}: the default {self.default} must be from {self.minimum} "
                f"to {self.maximum}"
            )
            raise ValueError(msg)
        require_type(self.help, str, f"{self.name} help")
        if not self.help.strip() or "\n" in self.help:
            msg = f"{self.name}: the help is one line of text"
            raise ValueError(msg)

    def check(self, value: object) -> int:
        """*value*, once it is a whole number within the bounds."""
        if type(value) is not int:
            msg = f"{self.name} must be a whole number, got {type(value).__name__}"
            raise TypeError(msg)
        if not self.minimum <= value <= self.maximum:
            msg = f"{self.name} must be from {self.minimum} to {self.maximum}, got {value}"
            raise ValueError(msg)
        return value


def _no_lookback(values: Mapping[str, int]) -> int:
    del values
    return 0

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
class Registered:
    """One shipped strategy: what makes it, a one-line summary and how much it trades.

    Calling the entry makes the strategy, as calling the class did before. The registry is
    fixed data, so ``tests/engine/test_registry.py`` checks every summary and turnover.
    """

    make: Callable[[], Strategy]
    summary: str
    turnover: Turnover

    def __post_init__(self) -> None:
        return

```
with:
```python
class Registered:
    """One shipped strategy: what makes it, a one-line summary, how much it trades, its settings,
    and how many calendar years of corporate actions before a run's first day it reads.

    ``make`` takes each setting as a keyword argument. Calling the entry checks the values and
    makes the strategy, from every setting's default when no values are given; ``lookback_years``
    takes the same values (M6 spec §4.3, §4.5). The registry is fixed data, so
    ``tests/engine/test_registry.py`` checks every summary and turnover.
    """

    make: Callable[..., Strategy]
    summary: str
    turnover: Turnover
    settings: tuple[Setting, ...] = ()
    lookback: Callable[[Mapping[str, int]], int] = _no_lookback

    def __post_init__(self) -> None:
        require_type(self.settings, tuple, "settings")
        names: set[str] = set()
        for setting in self.settings:
            require_type(setting, Setting, "setting")
            if setting.name in names:
                msg = f"the setting {setting.name} is registered twice"
                raise ValueError(msg)
            names.add(setting.name)

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
        strategies' settings too, as the flat ``[strategy]`` table does, or every default."""
        raise NotImplementedError("Registered.values")

    def __call__(self) -> Strategy:
        return self.make()

```
with:
```python
        strategies' settings too, as the flat ``[strategy]`` table does, or every default."""
        if given is None:
            return {setting.name: setting.default for setting in self.settings}
        found: dict[str, int] = {}
        for setting in self.settings:
            if setting.name not in given:
                msg = f"missing the setting {setting.name}"
                raise ValueError(msg)
            found[setting.name] = setting.check(given[setting.name])
        return found

    def __call__(self, values: Mapping[str, int] | None = None) -> Strategy:
        return self.make(**self.values(values))

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
        day: 0 for a strategy that reads none."""
        raise NotImplementedError("Registered.lookback_years")

```
with:
```python
        day: 0 for a strategy that reads none."""
        return self.lookback(self.values(values))

```

**`packages/steadyhand/src/steadyhand/training/lessons/en/backtest.data_gaps.md`** (changed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/backtest.data_gaps.md -->
Replace:
```markdown
summary = "What steadyhand does when a stock has no price for a day, and why the report warns you about it."
explains = ["data.bar.missing", "data.bar.refused"]
module = "using-steadyhand"
position = 3
see_also = ["risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++
```
with:
```markdown
summary = "What steadyhand does when a stock has no price for a day, and why the report warns you about it."
explains = ["data.bar.missing", "data.bar.refused", "data.dividends.history_refused"]
module = "using-steadyhand"
position = 3
see_also = ["risk.backtests_mislead"]
sources = [
    "docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md",
    "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md",
]
+++
```

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/backtest.data_gaps.md -->
Replace:
```markdown
  last clean close. It lists the refused days in one warning per stock.

```
with:
```markdown
  last clean close. It lists the refused days in one warning per stock.
- **Refused dividend history.** A strategy that judges a stock by the dividends it paid reads
  the years before the run as well. If the data source refuses a stock's history for those
  years, the run goes on, and one warning names the stock and the years refused. The stock's
  dividend history counts as incomplete, so such a strategy treats it as not qualifying.

```

**`packages/steadyhand/src/steadyhand/view.py`** (implemented, rewritten whole)

<!-- file: packages/steadyhand/src/steadyhand/view.py -->
```python
"""What a strategy may see on a decision day: prices and dividends up to that day, and nothing
later.

``PriceHistory`` holds every bar a run can use, and ``ActionHistory`` every corporate action,
the look-back's included (M6 spec §4.1). Both are built once. Each day gets a cheap
``MarketView`` over them, which refuses any date after its own day with ``LookAheadError`` (core
spec §4.3). A backtest that peeks at tomorrow's price looks brilliant and means nothing.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from math import prod

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_type
from steadyhand.market import PayDates
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import TRADE_NOT_HELD, TRADE_NOT_IN_UNIVERSE, Note
from steadyhand.types import (
    Bar,
    CashDividend,
    CorporateAction,
    Instrument,
    OtherAction,
    Side,
    Split,
)


class LookAheadError(LookupError):
    """A strategy asked for data dated after the day it is deciding on."""

    def __init__(self, asked: date, today: date) -> None:
        super().__init__(
            f"asked for {asked.isoformat()} while deciding on {today.isoformat()}: "
            "a decision may use nothing dated after its own day"
        )


class PriceHistory:
    """Every bar a run can use, indexed by instrument and day. It answers for any day."""

    def __init__(self, bars: Iterable[Bar]) -> None:
        grouped: dict[Instrument, list[Bar]] = {}
        for bar in bars:
            require_type(bar, Bar, "bar")
            grouped.setdefault(bar.instrument, []).append(bar)
        self._bars: dict[Instrument, tuple[Bar, ...]] = {}
        self._days: dict[Instrument, tuple[date, ...]] = {}
        for instrument, found in grouped.items():
            found.sort(key=lambda bar: bar.day)
            for earlier, later in pairwise(found):
                if earlier.day == later.day:
                    msg = f"two bars for {instrument.symbol} on {later.day.isoformat()}"
                    raise ValueError(msg)
            self._bars[instrument] = tuple(found)
            self._days[instrument] = tuple(bar.day for bar in found)

    @property
    def instruments(self) -> frozenset[Instrument]:
        return frozenset(self._bars)

    def between(self, instrument: Instrument, start: date | None, end: date) -> tuple[Bar, ...]:
        """The instrument's bars from *start* (or its first) to *end*, both inclusive."""
        days = self._days.get(instrument, ())
        first = 0 if start is None else bisect_left(days, start)
        return self._bars.get(instrument, ())[first : bisect_right(days, end)]

    def on(self, instrument: Instrument, day: date) -> Bar | None:
        found = self.between(instrument, day, day)
        return found[0] if found else None

    def before(self, instrument: Instrument, day: date) -> Bar | None:
        """The instrument's last bar dated strictly before *day*."""
        days = self._days.get(instrument, ())
        index = bisect_left(days, day)
        return self._bars[instrument][index - 1] if index else None


@dataclass(frozen=True, slots=True)
class PastDividend:
    """A cash dividend as a strategy sees it (M6 spec §4.1): its ex-date, and its amount per
    share restated in today's shares, so that one year's dividends compare with another's."""

    ex_date: date
    per_share: Decimal


class ActionHistory:
    """Every corporate action a run loaded, the look-back's included, and the stocks whose
    look-back the data source refused (M6 spec §4.1, §4.3). It answers for any day."""

    def __init__(
        self, actions: Iterable[CorporateAction] = (), incomplete: Iterable[Instrument] = ()
    ) -> None:
        dividends: dict[Instrument, list[CashDividend]] = {}
        splits: dict[Instrument, list[Split]] = {}
        for action in actions:
            if isinstance(action, CashDividend):
                dividends.setdefault(action.instrument, []).append(action)
            elif isinstance(action, Split):
                splits.setdefault(action.instrument, []).append(action)
            elif not isinstance(action, OtherAction):
                msg = f"action must be a CorporateAction, got {type(action).__name__}"
                raise TypeError(msg)
        self._dividends = {
            stock: tuple(sorted(found, key=lambda dividend: dividend.ex_date))
            for stock, found in dividends.items()
        }
        self._days = {
            stock: tuple(dividend.ex_date for dividend in found)
            for stock, found in self._dividends.items()
        }
        self._splits = {
            stock: tuple(sorted(found, key=lambda split: split.ex_date))
            for stock, found in splits.items()
        }
        refused = frozenset(incomplete)
        for stock in refused:
            require_type(stock, Instrument, "incomplete stock")
        self._incomplete = refused

    @property
    def incomplete(self) -> frozenset[Instrument]:
        """The stocks whose look-back the data source refused."""
        return self._incomplete

    def dividends(self, instrument: Instrument, today: date) -> tuple[PastDividend, ...]:
        """The stock's cash dividends with an ex-date on or before *today*, oldest first.

        Each is restated by every split from its own ex-date to *today*: a dividend is earned on
        the shares held before that day's split (``corporate._Actions``), so a split on the same
        day restates it too. After a 1-for-5 reverse split, a Rp 100 dividend is Rp 500 a share.
        """
        known = self._dividends.get(instrument, ())
        found = known[: bisect_right(self._days.get(instrument, ()), today)]
        splits = [split for split in self._splits.get(instrument, ()) if split.ex_date <= today]
        return tuple(
            PastDividend(
                dividend.ex_date,
                _restated(
                    dividend.per_share,
                    [split for split in splits if split.ex_date >= dividend.ex_date],
                ),
            )
            for dividend in found
        )

    def complete(self, instrument: Instrument) -> bool:
        """Whether the data source gave the stock's whole look-back."""
        return instrument not in self._incomplete


def _restated(per_share: Decimal, splits: list[Split]) -> Decimal:
    """*per_share* in the shares left after *splits*: one division, so it rounds once."""
    if not splits:
        return per_share
    old = prod(split.old_shares for split in splits)
    new = prod(split.new_shares for split in splits)
    return per_share * old / new


@dataclass(frozen=True, slots=True)
class Tradable:
    """Today's buyable and sellable stocks, and why a stock is neither (M3 spec §6.4).

    ``reasons`` explains stocks kept out for a cause (frozen, excluded, refused data, no bar).
    Any other stock is out because it is not in the universe (for a buy) or not held (a sell).
    ``members`` is the universe on ``day`` (M6 spec §4.2), so a strategy can tell a stock that
    left it from one kept out today; every buyable stock is a member.
    """

    day: date
    buyable: frozenset[Instrument]
    sellable: frozenset[Instrument]
    reasons: Mapping[Instrument, Note]
    members: frozenset[Instrument]

    def __post_init__(self) -> None:
        require_date(self.day, "tradable day")
        for name, group in (
            ("buyable", self.buyable),
            ("sellable", self.sellable),
            ("members", self.members),
        ):
            require_type(group, frozenset, name)
        clash = sorted(i.symbol for i in (self.buyable | self.sellable) if i in self.reasons)
        if clash:
            msg = f"{', '.join(clash)} cannot be both tradable and kept out"
            raise ValueError(msg)
        outside = sorted(i.symbol for i in self.buyable - self.members)
        if outside:
            msg = f"{', '.join(outside)} cannot be buyable outside the universe"
            raise ValueError(msg)

    def why_not(self, instrument: Instrument, side: Side) -> Note | None:
        """Why *instrument* cannot be traded on *side* today, or ``None`` when it can."""
        allowed = self.buyable if side is Side.BUY else self.sellable
        if instrument in allowed:
            return None
        if instrument in self.reasons:
            return self.reasons[instrument]
        if side is Side.BUY:
            return Note(TRADE_NOT_IN_UNIVERSE, f"not in the universe on {self.day.isoformat()}")
        return Note(TRADE_NOT_HELD, "not held")


class MarketView:
    """The market as a strategy sees it on ``today``.

    *actions* hold the dividend history and *pay_dates* model a dividend's pay date as the
    engine pays it (M6 spec §4.1).
    """

    def __init__(
        self,
        history: PriceHistory,
        today: date,
        tradable: Tradable,
        actions: ActionHistory,
        pay_dates: PayDates,
    ) -> None:
        require_type(history, PriceHistory, "history")
        require_date(today, "today")
        require_type(tradable, Tradable, "tradable")
        require_type(actions, ActionHistory, "actions")
        require_type(pay_dates, PayDates, "pay_dates")
        if tradable.day != today:
            msg = f"the tradable set is for {tradable.day.isoformat()}, not {today.isoformat()}"
            raise ValueError(msg)
        self._history = history
        self._today = today
        self._tradable = tradable
        self._actions = actions
        self._pay_dates = pay_dates

    @property
    def today(self) -> date:
        return self._today

    @property
    def tradable(self) -> Tradable:
        return self._tradable

    def bar(self, instrument: Instrument, day: date | None = None) -> Bar | None:
        """The bar for *day* (today by default), or ``None`` if the stock has none that day."""
        when = self._today if day is None else self._checked(day)
        return self._history.on(instrument, when)

    def history(
        self, instrument: Instrument, start: date | None = None, end: date | None = None
    ) -> tuple[Bar, ...]:
        """Bars from *start* (or the first) to *end* (today by default), both inclusive."""
        last = self._today if end is None else self._checked(end)
        return self._history.between(instrument, start, last)

    def last_close(self, instrument: Instrument) -> Money | None:
        """The most recent close on or before today."""
        found = self._history.between(instrument, None, self._today)
        return found[-1].close if found else None

    def dividends(self, instrument: Instrument) -> tuple[PastDividend, ...]:
        """The stock's cash dividends with an ex-date on or before today, oldest first, each
        restated in today's shares."""
        return self._actions.dividends(instrument, self._today)

    def pay_date(self, ex_date: date) -> date:
        """The modelled pay date of a dividend with *ex_date*, on or before today: the engine's
        and the income calendar's, from ``add_trading_days`` (M4 spec §3.1)."""
        return self._pay_dates.of(self._checked(ex_date))

    def history_complete(self, instrument: Instrument) -> bool:
        """False when the data source refused any part of the stock's look-back (M6 §4.3)."""
        return self._actions.complete(instrument)

    def _checked(self, day: date) -> date:
        require_date(day, "day")
        if day > self._today:
            raise LookAheadError(day, self._today)
        return day


@dataclass(frozen=True, slots=True)
class PortfolioView:
    """The portfolio as a strategy sees it: values at the last close, and what it may spend.

    ``value`` is all cash, settled and unsettled, plus ``holdings`` (core spec §6.2).
    ``spendable`` is what may be spent today, including every dividend already paid: the
    portfolio's ``spendable_cash``, or zero while a charge waits on unsettled sale proceeds.
    """

    value: Money
    spendable: Money
    holdings: Mapping[Instrument, Money]

    def __post_init__(self) -> None:
        require_type(self.value, Money, "value")
        require_type(self.spendable, Money, "spendable")
        for amount in (self.spendable, *self.holdings.values()):
            if amount.currency != self.value.currency:
                raise CurrencyMismatchError(self.value.currency, amount.currency)
        if self.spendable.amount < 0:
            msg = f"spendable cash cannot be negative, got {self.spendable}"
            raise ValueError(msg)
        held = sum((amount for amount in self.holdings.values()), Money.zero(self.value.currency))
        if held + self.spendable > self.value:
            msg = f"holdings {held} and spendable {self.spendable} exceed the value {self.value}"
            raise ValueError(msg)

    def weight(self, instrument: Instrument) -> Decimal:
        """The instrument's share of the value, rounded down so weights never sum above 1."""
        held = self.holdings.get(instrument)
        if held is None:
            return Decimal(0)
        return ratio_down(held.amount, self.value.amount)
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1486 passed=1486 -->
Expected: every command exits 0; 1486 passed, 100% branch coverage; the performance step passes its eight tests: the ten-year backtest, the four start-up budgets and the three paper budgets. CI's second job runs the same 1486 tests on Python 3.13 under `-W error`.

- [ ] **Step 7: Mutations.** Run M296–M318 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M6 S1 the engine's data path: dividend history, members, strategy notes, the look-back and strategy settings`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 2: M6 S2 The look-back's IDX data path: dividends read without prices or the calendar

**Acceptance criteria (story text):**
1. `actions_in(history, instrument, start, end)` reads a range's splits and cash dividends, restated through every later reported split, without recovering a price or reading the holiday calendar; `YahooDataSource.corporate_actions` returns it, so a range whose prices cannot be recovered (BBRI before 7 September 2021) or which the calendar does not cover still gives its actions, while `bars` still refuses them. One download serves both.
2. The cache's schema gains `fetched_actions` (migration 2): a range fetched for its actions alone is stored all or nothing, stays in its range, is recorded as fetched for actions only (its bars still count as missing), and is not stored when refused. `CachedDataSource.corporate_actions` fetches only the parts not yet stored either way (`missing_actions`), trims them to trading days where the calendar covers them, and asks for a gap reaching before the calendar whole. A cache written before M6 is upgraded and keeps its ranges.
3. `IdxMarketRules.is_trading_day` answers for every year of the holiday data, from 2016 (scope decision 7): the income report on 30 June 2021 places a 2020 dividend's pay month, and refuses one before 2016.
4. A refused stock's actions over the whole run are read for its history in a call of their own: a dividend on a refused day reaches the strategy's view from its ex-date with its history complete, while the engine credits nothing on that day and the run's warnings are unchanged; a source that refuses that call, with any `DataUnavailableError`, leaves the stock's history incomplete (scope decision 14).
5. `backtest` to 31 January 2022 builds its income report with BBRI's 6 April 2021 dividend (Rp440,572 gross) in the run-rate, where before M6 it stopped with exit 3 (scope decision 8); a source with no history at all still stops it.
6. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M319–M331 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand_idx/{yahoo,cache,rules}.py`, `.../steadyhand/{backtest,market,view}.py`
- Test: `tests/idx/{test_yahoo,test_cache,test_rules}.py`, `tests/engine/{test_backtest,test_income_report,test_view}.py`, `tests/cli/{cli_world,test_backtest_command}.py`

**Interfaces:**
- Consumes: Task 1's `ActionHistory`, `_fetch` and its look-back; `YahooHistory`, `IdxCalendar`, `BarCache`, `MIGRATIONS`.
- Produces: `steadyhand_idx.yahoo.actions_in(history, instrument, start, end)`; `BarCache.store_actions(instrument, span, actions)` and `BarCache.fetched_actions(instrument)`; `CachedDataSource.missing_actions(instrument, start, end)`; cache schema version 2.

- [ ] **Step 1: Branch.** `git switch -c m6/s2-idx-look-back origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/cli_world.py`** (changed: 2 edits)

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python

def golden_backtest(cli: Cli, end: date, *, goal: bool = False) -> BacktestResult:
    """``buy-and-hold`` from the golden window's first day to *end*, as ``backtest`` runs it over
    the same configuration, universe files and recorded data. Without the income goal unless
    *goal*: its report reads five years before *end* (M4 spec §8), which the recordings do not
    cover for an early *end*, and it changes neither the states nor the day reports."""
    config = load(cli.config)
```
with:
```python

def golden_backtest(
    cli: Cli, end: date, *, goal: bool = False, start: date = START
) -> BacktestResult:
    """``buy-and-hold`` from *start*, the golden window's first day by default, to *end*, as
    ``backtest`` runs it over the same configuration, universe files and recorded data. Without
    the income goal unless *goal*: its report reads five years before *end* (M4 spec §8), which
    the recordings do not cover for an early *end*, and it changes neither the states nor the
    day reports."""
    config = load(cli.config)
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
            market,
            START,
            end,
```
with:
```python
            market,
            start,
            end,
```

**`tests/cli/test_backtest_command.py`** (changed: 3 edits)

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
import stat
from pathlib import Path

import pytest
from cli_world import GOLDEN_CONFIG, PLACEHOLDERS, Cli, market_cli
from record_golden import END, GOLDEN, RECORDED, START, recorded, run, settings, universe
```
with:
```python
import stat
from datetime import date
from pathlib import Path

import pytest
from cli_world import GOLDEN_CONFIG, PLACEHOLDERS, Cli, golden_backtest, market_cli
from record_golden import END, GOLDEN, RECORDED, START, recorded, run, settings, universe
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    DISCLAIMER,
    BacktestResult,
    BuyAndHold,
    Market,
    backtest,
```
with:
```python
    DISCLAIMER,
    IDR,
    BacktestResult,
    BuyAndHold,
    Market,
    Money,
    backtest,
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python

def test_history_the_source_cannot_recover_stops_the_run_safely_with_exit_3(market: Cli) -> None:
    # The income report reads five years before the last day, and Yahoo's BBRI prices before
    # 2021-09-07 carry an event it does not report: an income report is never built on missing
    # history (M4 spec §8), so the run stops and trades nothing.
    result = market("backtest", "--from", "2022-01-25", "--to", "2022-01-31")
    assert result.code == 3
    assert result.out == ""
    assert result.err.startswith(
        "steadyhand-idx: BBRI.JK: Yahoo's prices for 1111 day(s) from 2017-01-31 to 2021-09-07 "
    )
    assert result.err.endswith("so the prices traded on those days cannot be recovered\n")
    assert not (market.home / "reports").exists()

```
with:
```python

def test_a_holding_whose_old_prices_cannot_be_recovered_keeps_its_dividend_history(
    market: Cli,
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

**`tests/engine/test_backtest.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
        ("bars", "BBRI", START, END),
        ("bars", "BBRI", START, date(2025, 7, 2)),
```
with:
```python
        ("bars", "BBRI", START, END),
        # Its actions over the whole run, for its history: this source refuses those too.
        ("actions", "BBRI", START, END),
        ("bars", "BBRI", START, date(2025, 7, 2)),
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
        ("bars", "BBRI", START, END),
        ("bars", "BBRI", DAYS[1], DAYS[-2]),
```
with:
```python
        ("bars", "BBRI", START, END),
        ("actions", "BBRI", START, END),
        ("bars", "BBRI", DAYS[1], DAYS[-2]),
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python

def test_compare_fetches_the_look_back_once_for_every_strategy() -> None:
```
with:
```python

class _Unpriced(_Source):
    """A source that reads corporate actions without prices, as the IDX source does (M6 plan
    scope decision 13): it refuses a stock's bars on its refused days, never its actions."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        self.requests.append(("actions", instrument.symbol, start, end))
        return [
            a for a in self._actions if a.instrument == instrument and start <= a.ex_date <= end
        ]


REFUSED_DIVIDEND = CashDividend(BBCA, date(2025, 7, 3), Decimal(40))
"""A BBCA dividend whose ex-date is one of its refused days."""


@pytest.mark.parametrize("years", [0, 2])
def test_a_dividend_on_a_refused_day_reaches_the_history_when_read_without_prices(
    years: int,
) -> None:
    refused = {BBCA: [date(2025, 7, 3), date(2025, 7, 4)]}
    source = _Unpriced(calm(), [*LOOKED_BACK, REFUSED_DIVIDEND], refused=refused)
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back(years))
    assert ("actions", "BBCA", START, END) in source.requests
    # The strategy sees it from its ex-date, and BBCA's history is complete ...
    before, on = reader.seen[date(2025, 7, 2)], reader.seen[date(2025, 7, 3)]
    assert REFUSED_DIVIDEND.ex_date not in [dividend.ex_date for dividend in before[0]]
    assert on[0][-1] == PastDividend(date(2025, 7, 3), Decimal(40))
    assert on[1:] == (True, True)
    # ... while the engine still credits nothing on a refused day, as its warning says.
    assert all(e.ex_date != REFUSED_DIVIDEND.ex_date for r in result.run.reports for e in r.paid)
    assert [warning.key for warning in result.warnings] == [DATA_BAR_REFUSED]


class _Failing(_Source):
    """A source whose read of BBCA's actions over the whole run fails outright, as Yahoo's does
    after its retries: a plain ``DataUnavailableError``, naming no day."""

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        if (instrument, start, end) == (BBCA, START, END):
            self.requests.append(("actions", instrument.symbol, start, end))
            msg = "BBCA.JK: no data from Yahoo after 3 attempts"
            raise DataUnavailableError(msg)
        return super().corporate_actions(instrument, start, end)


@pytest.mark.parametrize("source_type", [_Source, _Failing], ids=["days refused", "read failed"])
def test_a_source_that_refuses_the_actions_too_leaves_that_history_incomplete(
    source_type: type[_Source],
) -> None:
    refused = {BBCA: [date(2025, 7, 3), date(2025, 7, 4)]}
    source = source_type(calm(), [*LOOKED_BACK, REFUSED_DIVIDEND], refused=refused)
    reader = _Reader()
    result = run(source, strategy=reader, chosen=looking_back())
    # Only the clean days' actions are known, so BBCA's history is incomplete from the start.
    assert reader.seen[START][1:] == (False, True)
    assert reader.seen[END][0][-1] == PastDividend(date(2025, 7, 2), Decimal(25))
    assert [warning.key for warning in result.warnings] == [DATA_BAR_REFUSED]


def test_compare_fetches_the_look_back_once_for_every_strategy() -> None:
```

**`tests/engine/test_income_report.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_income_report.py -->
Replace:
```python

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

```
with:
```python

def test_a_year_window_before_the_holiday_data_is_refused_not_guessed() -> None:
    # A report on 30 June 2021 reads the dividends back to 1 July 2020. The IDX holidays reach
    # back to 2016, so a dividend on 8 December 2020 is paid 14 trading days later, on 4 January
    # 2021: 9, 24, 25 and 31 December and 1 January were holidays (M6 spec §4.1). One on 8
    # December 2015, read by a report in 2016, has no pay month anyone knows.
    settings = IncomeSettings(IncomeGoal(rp(10_000)))
    placed = income_report(
        [report(date(2021, 6, 30))],
        final(),
        {BBCA: [CashDividend(BBCA, date(2020, 12, 8), Decimal(50))]},
        rules(),
        settings,
    )
    paid = [dividend for held in placed.run_rate.holdings for dividend in held.dividends]
    assert [(dividend.ex_date, dividend.pay_date) for dividend in paid] == [
        (date(2020, 12, 8), date(2021, 1, 4))
    ]
    early: dict[Instrument, Sequence[CorporateAction]] = {
        BBCA: [CashDividend(BBCA, date(2015, 12, 8), Decimal(50))]
    }
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2015"):
        income_report([report(date(2016, 6, 30))], final(), early, rules(), settings)

```

**`tests/engine/test_view.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
def test_an_ex_date_the_rules_cannot_place_raises_their_own_error() -> None:
    with pytest.raises(UnsupportedDateError, match=r"; 2015-12-31 is earlier$"):
        view_on(0).pay_date(date(2015, 12, 30))
```
with:
```python
def test_an_ex_date_the_rules_cannot_place_raises_their_own_error() -> None:
    # The IDX holidays start in 2016; 2020's are there, before the rules' verified tables begin.
    assert view_on(0).pay_date(date(2020, 6, 10)) == date(2020, 6, 30)
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2015"):
        view_on(0).pay_date(date(2015, 12, 30))
```

**`tests/idx/test_cache.py`** (changed: 4 edits)

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.yahoo import YahooDataSource, YahooHistory, history_from_json, unadjust

```
with:
```python
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.yahoo import (
    YahooDataSource,
    YahooHistory,
    YahooRow,
    history_from_json,
    unadjust,
)

```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
        raw.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    with pytest.raises(CacheSchemaError, match=r"c\.sqlite is at cache schema 2, newer than this"):
        BarCache(path)
```
with:
```python
        raw.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    with pytest.raises(
        CacheSchemaError,
        match=r"c\.sqlite is at cache schema 3, newer than this steadyhand-idx knows \(2\);",
    ):
        BarCache(path)
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
    assert [bar.day for bar in source.bars(BBCA, today, today)] == [today]  # nothing to fill
    assert len(counting.asked) == 2
```
with:
```python
    assert [bar.day for bar in source.bars(BBCA, today, today)] == [today]  # nothing to fill
    assert source.corporate_actions(BBCA, today, today) == [Split(BBCA, today, 1, 5)]
    assert len(counting.asked) == 2
```

<!-- edit: tests/idx/test_cache.py -->
Replace:
```python
    assert abs((jakarta_today() - date.today()).days) <= 1  # noqa: DTZ011 - comparing two clocks
```
with:
```python
    assert abs((jakarta_today() - date.today()).days) <= 1  # noqa: DTZ011 - comparing two clocks


LOOK_BACK = (date(2017, 1, 31), date(2021, 9, 30))
"""BBRI's years before a run: its prices up to 2021-09-07 cannot be recovered."""


def test_a_cache_from_before_m6_is_upgraded_and_keeps_its_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.sqlite"
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS[:1])
    with BarCache(path) as old:
        old.store(BBCA, SEP, *bbca(*SEP))
        assert old.schema_version == 1
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS)
    with BarCache(path) as upgraded:
        assert upgraded.schema_version == 2
        assert upgraded.fetched_actions(BBCA) == [SEP]
        upgraded.store_actions(BBCA, OCT, [Split(BBCA, date(2021, 10, 13), 1, 5)])
        assert upgraded.fetched_actions(BBCA) == [(date(2021, 9, 1), date(2021, 10, 29))]
        assert upgraded.fetched(BBCA) == [SEP]


def test_actions_stored_alone_leave_their_bars_missing(cache: BarCache) -> None:
    split = Split(BBCA, date(2021, 10, 13), 1, 5)
    cache.store_actions(BBCA, OCT, [split])
    assert cache.actions(BBCA, *OCT) == [split]
    assert cache.fetched_actions(BBCA) == [OCT]
    assert cache.fetched(BBCA) == []
    cache.store_actions(BBCA, OCT, [split])  # the same again changes nothing
    assert cache.actions(BBCA, *OCT) == [split]


def test_actions_stored_alone_are_all_or_nothing_and_stay_in_their_range(cache: BarCache) -> None:
    dividend = CashDividend(BBCA, date(2021, 10, 5), Decimal(25))
    cache.store_actions(BBCA, OCT, [dividend])
    changed = CashDividend(BBCA, date(2021, 10, 5), Decimal(30))
    later = CashDividend(BBCA, date(2021, 11, 17), Decimal(25))
    with pytest.raises(CacheConflictError, match=r"^BBCA 2021-10-05: cached dividend"):
        cache.store_actions(BBCA, (date(2021, 10, 1), date(2021, 11, 30)), [later, changed])
    assert cache.actions(BBCA, date(2021, 10, 1), date(2021, 11, 30)) == [dividend]
    assert cache.fetched_actions(BBCA) == [OCT]
    with pytest.raises(ValueError, match=r"^BBCA 2021-11-17 is not BBCA in 2021-10-01 to"):
        cache.store_actions(BBCA, OCT, [later])
    with pytest.raises(ValueError, match=r"^BBRI 2021-10-05 is not BBCA in 2021-10-01 to"):
        cache.store_actions(BBCA, OCT, [CashDividend(BBRI, date(2021, 10, 5), Decimal(1))])


def test_missing_actions_skips_ranges_stored_either_way(cache: BarCache) -> None:
    cache.store(BBCA, (date(2021, 9, 1), date(2021, 9, 10)), [], [])
    cache.store_actions(BBCA, (date(2021, 9, 20), date(2021, 9, 24)), [])
    source = CachedDataSource(YahooDataSource(calendar()), cache, calendar())
    assert source.missing_actions(BBCA, date(2021, 9, 1), date(2021, 9, 30)) == [
        (date(2021, 9, 13), date(2021, 9, 17)),  # 11-12 Sep is a weekend
        (date(2021, 9, 27), date(2021, 9, 30)),
    ]
    # The bars of the range stored for its actions alone are still missing.
    assert source.missing(BBCA, date(2021, 9, 20), date(2021, 9, 24)) == [
        (date(2021, 9, 20), date(2021, 9, 24))
    ]
    # A gap reaching into a year the calendar does not cover is asked for whole.
    assert source.missing_actions(BBCA, date(2015, 1, 1), date(2021, 9, 10)) == [
        (date(2015, 1, 1), date(2021, 8, 31))
    ]


def test_a_look_back_is_fetched_once_without_its_prices(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBRI.JK_2017-01-31_2022-01-31.json", date(2026, 9, 25))
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
        source.bars(BBRI, *LOOK_BACK)


def test_a_refused_look_back_is_not_stored(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    counting.history = YahooHistory("X.JK", (), ((date(2021, 10, 13), Decimal("0.3333")),))
    for _ in range(2):
        with pytest.raises(DataUnavailableError, match=r"^BBCA: Yahoo's split ratio 0\.3333 on"):
            source.corporate_actions(BBCA, *OCT)
    # One download, which the Yahoo source keeps for its next call; nothing reaches the cache.
    assert counting.asked == [OCT]
    assert cache.fetched_actions(BBCA) == []
    assert cache.actions(BBCA, *OCT) == []


def test_a_look_back_before_the_calendar_is_asked_for_whole(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    row = YahooRow(date(2015, 6, 1), *(Decimal(1000),) * 4, volume=100, dividend=Decimal(50))
    counting.history = YahooHistory("BBCA.JK", (row,), ())
    span = (date(2015, 1, 1), date(2016, 1, 3))
    assert source.corporate_actions(BBCA, *span) == [
        CashDividend(BBCA, date(2015, 6, 1), Decimal(50))
    ]
    assert counting.asked == [span]
    assert cache.fetched_actions(BBCA) == [span]
```

**`tests/idx/test_rules.py`** (changed: 2 edits)

<!-- edit: tests/idx/test_rules.py -->
Replace:
```python
        lambda: rules().protection_end(date(2020, 12, 31)),
        lambda: rules().is_trading_day(date(2020, 12, 31)),
    ],
```
with:
```python
        lambda: rules().protection_end(date(2020, 12, 31)),
    ],
```

<!-- edit: tests/idx/test_rules.py -->
Replace:
```python
    assert not rules().is_trading_day(date(2026, 12, 31))
```
with:
```python
    assert not rules().is_trading_day(date(2026, 12, 31))


def test_trading_days_answer_for_every_year_of_holiday_data_before_the_rules_are_verified() -> None:
    # A pay date modelled for a 2020 dividend counts 2020's trading days (M6 spec §4.1).
    assert rules().is_trading_day(date(2020, 12, 30))
    assert not rules().is_trading_day(date(2020, 12, 31))
    assert rules().is_trading_day(date(2016, 1, 4))
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2015"):
        rules().is_trading_day(date(2015, 12, 31))
    with pytest.raises(UnsupportedDateError, match="primary-verified from 2021-01-01"):
        rules().require_supported(date(2020, 12, 30))
```

**`tests/idx/test_yahoo.py`** (changed: 5 edits)

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python
    UnavailableDaysError,
)
```
with:
```python
    UnavailableDaysError,
    UnsupportedDateError,
)
```

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python
    YahooRow,
    history_from_frames,
```
with:
```python
    YahooRow,
    actions_in,
    history_from_frames,
```

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python
UNVR_FILE = FIXTURES / "UNVR.JK_2023-05-15_2023-06-09.json"
BBCA = Instrument("BBCA", "IDX", IDR)
```
with:
```python
UNVR_FILE = FIXTURES / "UNVR.JK_2023-05-15_2023-06-09.json"
BBRI_FIVE_YEARS = FIXTURES / "BBRI.JK_2017-01-31_2022-01-31.json"
BBCA = Instrument("BBCA", "IDX", IDR)
```

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python
        source.bars(BBCA, date(2021, 10, 2), date(2021, 10, 1))

```
with:
```python
        source.bars(BBCA, date(2021, 10, 2), date(2021, 10, 1))
    with pytest.raises(ValueError, match=r"^end 2021-10-01 is before start 2021-10-02$"):
        source.corporate_actions(BBCA, date(2021, 10, 2), date(2021, 10, 1))

```

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python
    assert len(source.bars(UNVR, date(2023, 5, 15), date(2023, 6, 9))) == 17
```
with:
```python
    assert len(source.bars(UNVR, date(2023, 5, 15), date(2023, 6, 9))) == 17


def test_actions_are_read_where_the_prices_cannot_be_recovered() -> None:
    # BBRI's prices before 2021-09-07 carry a rights issue Yahoo does not report, so no bar can
    # be recovered there, but a dividend needs no price (M6 spec §4.3).
    history = history_from_json(BBRI_FIVE_YEARS)
    refused = (date(2021, 2, 1), date(2021, 9, 7))
    with pytest.raises(UnrecoverablePricesError):
        unadjust(history, BBRI, calendar(), *refused)
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
        unadjust(history, BBCA, calendar(), *year)


def test_the_source_reads_a_ranges_actions_without_its_prices() -> None:
    replay = Replay(BBRI_FIVE_YEARS)
    source = YahooDataSource(calendar(), download=replay, sleep=lambda _: None)
    refused = (date(2021, 2, 1), date(2021, 9, 7))
    assert source.corporate_actions(BBRI, *refused) == [
        CashDividend(BBRI, date(2021, 4, 6), Decimal("89.91268"))
    ]
    with pytest.raises(UnrecoverablePricesError):
        source.bars(BBRI, *refused)
    assert replay.calls == [("BBRI.JK", *refused)]
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`** (changed, new names stubbed: 8 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
after the day is over.
"""
```
with:
```python
after the day is over.

Corporate actions can also be fetched alone (M6 spec §4.3): a strategy's look-back reads the
years before a run, whose prices it never needs. Such a range is recorded as fetched for
actions only, so its bars still count as missing.
"""
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
    Split,
)
```
with:
```python
    Split,
    UnsupportedDateError,
)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
    CREATE TABLE fetched (
        symbol TEXT NOT NULL,
```
with:
```python
    CREATE TABLE fetched (
        symbol TEXT NOT NULL,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        PRIMARY KEY (symbol, start, end)
    ) STRICT;
    """,
    """
    CREATE TABLE fetched_actions (
        symbol TEXT NOT NULL,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python

    def _insert_bar(self, symbol: str, day: date, row: _BarRow) -> None:
```
with:
```python

    def store_actions(
        self, instrument: Instrument, span: tuple[date, date], actions: Sequence[CorporateAction]
    ) -> None:
        """Store one range's actions, fetched without its bars, all of them or none, and mark the
        range as fetched for actions only (M6 spec §4.3)."""
        raise NotImplementedError("BarCache.store_actions")

    def _require_within(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        located: Sequence[tuple[Instrument, date]],
    ) -> None:
        raise NotImplementedError("BarCache._require_within")

    def _insert_bar(self, symbol: str, day: date, row: _BarRow) -> None:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python

    @staticmethod
```
with:
```python

    def fetched_actions(self, instrument: Instrument) -> list[tuple[date, date]]:
        """Every range whose actions are stored for *instrument*, with or without its bars,
        merged where they touch or overlap."""
        raise NotImplementedError("BarCache.fetched_actions")

    @staticmethod
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        return instrument.symbol

```
with:
```python
        return instrument.symbol


def _merged(rows: Sequence[tuple[str, str]]) -> list[tuple[date, date]]:
    """Stored ``(start, end)`` rows, in start order, merged where they touch or overlap."""
    raise NotImplementedError("_merged")

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python

    def _fill(self, instrument: Instrument, start: date, end: date) -> date:
```
with:
```python

    def missing_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> list[tuple[date, date]]:
        """The parts of *start* to *end* whose actions are not yet stored, with or without bars.

        A gap in years the holiday calendar covers is trimmed to its trading days, as in
        ``missing``. A gap reaching into a year it does not cover is asked for whole: actions
        need no calendar, and such a gap is the start of a look-back, years long.
        """
        raise NotImplementedError("CachedDataSource.missing_actions")

    def _trading(self, first: date, last: date) -> tuple[date, date] | None:
        """*first* to *last* narrowed to its first and last trading day, or ``None`` if it has
        none."""
        raise NotImplementedError("CachedDataSource._trading")

    def _today_for(self, start: date, end: date) -> date:
        """Today, once *start* to *end* is a range that can be read today."""
        raise NotImplementedError("CachedDataSource._today_for")

    def _fill(self, instrument: Instrument, start: date, end: date) -> date:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
        return today
```
with:
```python
        return today


def _gaps(covered: Sequence[tuple[date, date]], start: date, end: date) -> list[tuple[date, date]]:
    """The parts of *start* to *end* outside *covered*, merged ranges in start order."""
    raise NotImplementedError("_gaps")
```

**`packages/steadyhand-idx/src/steadyhand_idx/rules.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/rules.py -->
Replace:
```python
``fees.toml`` and ``holidays.toml``, and the refusal names the table that sets it. The date is
derived from the files and never written into code.
"""
```
with:
```python
``fees.toml`` and ``holidays.toml``, and the refusal names the table that sets it. The date is
derived from the files and never written into code. ``is_trading_day`` alone answers for every
year ``holidays.toml`` covers, from 2016: counting trading days needs only the holidays, and a
strategy models the pay date of a dividend from before ``verified_from`` (M6 spec §4.1).
"""
```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (changed, new names stubbed: 4 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
contradicts the calendar, and is refused.
"""
```
with:
```python
contradicts the calendar, and is refused.

Corporate actions need neither: a dividend is restated through the reported splits alone. So
``corporate_actions`` reads only splits and dividends, and a range whose prices cannot be
recovered, or which the holiday calendar does not cover, still gives its actions. That is what a
strategy's look-back reads (M6 spec §4.3): on 2026-09-30 the price checks refused 11 of the 45
LQ45 members' six-year look-backs, and reading the actions alone refused 2 (unusable splits).
"""
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

def unadjust(
```
with:
```python

def actions_in(
    history: YahooHistory, instrument: Instrument, start: date, end: date
) -> list[CorporateAction]:
    """The splits and cash dividends with an ex-date from *start* to *end*, in date order.

    A dividend is restated through every reported split after its ex-date, as prices are. No
    price is recovered and no calendar is read, so actions never depend on either.
    """
    raise NotImplementedError("actions_in")


def _factor(history: YahooHistory, day: date) -> Decimal:
    """The product of every reported split ratio after *day*, which Yahoo divided *day* by."""
    raise NotImplementedError("_factor")


def unadjust(
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

    def _unadjusted(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[list[Bar], list[CorporateAction]]:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        ticker = ticker_for(instrument)
        return unadjust(self._fetch(ticker, start, end), instrument, self._calendar, start, end)

```
with:
```python

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
        raise NotImplementedError("YahooDataSource._history")

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

    def _unadjusted(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[list[Bar], list[CorporateAction]]:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        ticker = ticker_for(instrument)
        return unadjust(self._fetch(ticker, start, end), instrument, self._calendar, start, end)


def download_history(ticker: str, start: date, end: date) -> YahooHistory:  # pragma: no cover
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

def _clean_ranges(days: Sequence[date], refused: frozenset[date]) -> Iterator[tuple[date, date]]:
```
with:
```python

def _unpriced_actions(
    source: DataSource, stock: Instrument, start: date, end: date
) -> Sequence[CorporateAction] | None:
    """A refused stock's actions from *start* to *end*, refused days included, or ``None`` when
    the source refuses them as well (M6 plan scope decision 13)."""
    raise NotImplementedError("_unpriced_actions")


def _clean_ranges(days: Sequence[date], refused: frozenset[date]) -> Iterator[tuple[date, date]]:
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1500 failed=20 -->
Expected: 1500 run, 20 failed. 7 are `NotImplementedError` from the stubs in `yahoo.py`, `cache.py` and `backtest.py`. Four are `UnsupportedDateError` and two `UnrecoverablePricesError`: the old code reads actions through the price checks and the holiday calendar, and refuses trading days before 2021. Two are `assert (True, True) == (False, True)`: a stock whose refused days' actions are unknown still reads complete. The other five are `AssertionError`s on what the old code does: the two pinned request lists without the whole-run read, the two cases of the refused-day test, and the backtest to 31 January 2022, which still stops with exit 3. Twelve changed tests pass against the stubs by design: `test_every_rule_refuses_an_unverified_day`'s nine cases (only `is_trading_day` left the list), `test_a_cache_from_a_newer_release_is_refused` (its schema number moved), `test_today_is_always_fetched_and_never_stored` and `test_a_reversed_range_is_refused` (each gained an assertion on the actions path the old code already had).

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`** (implemented, rewritten whole)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
```python
"""A local SQLite cache of bars and corporate actions, keyed by (ticker, date) (spec §9.3).

``BarCache`` stores what a data source returned, one range at a time, in one transaction: the
bars, the actions and the fact that the range was fetched. A stored row is never overwritten.
A different value for a row already stored is a ``CacheConflictError`` and nothing is written,
so good cached data survives a bad fetch (spec §5 step 1).

``CachedDataSource`` puts the cache in front of another ``DataSource`` and fetches only the
ranges it is missing (spec §9.2). A day counts as fetched only once it is over in Jakarta, so
today's bar is always fetched afresh and never stored here; it is stored by the first read
after the day is over.

Corporate actions can also be fetched alone (M6 spec §4.3): a strategy's look-back reads the
years before a run, whose prices it never needs. Such a range is recorded as fetched for
actions only, so its bars still count as missing.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from zoneinfo import ZoneInfo

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    DataSource,
    Instrument,
    Money,
    OtherAction,
    Split,
    UnsupportedDateError,
)
from steadyhand_idx.calendar import IdxCalendar

JAKARTA = ZoneInfo("Asia/Jakarta")
_ONE_DAY = timedelta(days=1)
_BUSY_TIMEOUT_SECONDS = 30.0

# Applied in order; PRAGMA user_version records how many have run. Never edit a shipped entry:
# add a new one, so a cache made by an older release upgrades in place.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE bars (
        symbol TEXT NOT NULL,
        day TEXT NOT NULL,
        open INTEGER NOT NULL,
        high INTEGER NOT NULL,
        low INTEGER NOT NULL,
        close INTEGER NOT NULL,
        volume INTEGER NOT NULL,
        PRIMARY KEY (symbol, day)
    ) STRICT;
    CREATE TABLE actions (
        symbol TEXT NOT NULL,
        ex_date TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('split', 'dividend', 'other')),
        old_shares INTEGER,
        new_shares INTEGER,
        per_share TEXT,
        description TEXT,
        PRIMARY KEY (symbol, ex_date, kind)
    ) STRICT;
    CREATE TABLE fetched (
        symbol TEXT NOT NULL,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        PRIMARY KEY (symbol, start, end)
    ) STRICT;
    """,
    """
    CREATE TABLE fetched_actions (
        symbol TEXT NOT NULL,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        PRIMARY KEY (symbol, start, end)
    ) STRICT;
    """,
)


class CacheConflictError(RuntimeError):
    """A fetched value differs from the one already cached. Nothing from that fetch is stored."""


class CacheSchemaError(RuntimeError):
    """The cache file was written by a newer steadyhand-idx than this one."""


type _BarRow = tuple[int, int, int, int, int]
type _ActionRow = tuple[int | None, int | None, str | None, str | None]


def _action_row(action: CorporateAction) -> tuple[str, _ActionRow]:
    if isinstance(action, Split):
        return "split", (action.old_shares, action.new_shares, None, None)
    if isinstance(action, CashDividend):
        return "dividend", (None, None, str(action.per_share), None)
    return "other", (None, None, None, action.description)


class BarCache:
    """The cache file. Use it as a context manager, or call ``close()``."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_SECONDS, isolation_level=None)
        try:
            self._migrate()
        except BaseException:
            self._db.close()
            raise

    def __enter__(self) -> BarCache:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    @property
    def schema_version(self) -> int:
        return int(self._db.execute("PRAGMA user_version").fetchone()[0])

    def _migrate(self) -> None:
        with self._write():
            version = self.schema_version
            if version > len(MIGRATIONS):
                msg = (
                    f"{self._path} is at cache schema {version}, newer than this "
                    f"steadyhand-idx knows ({len(MIGRATIONS)}); upgrade steadyhand-idx"
                )
                raise CacheSchemaError(msg)
            for number in range(version, len(MIGRATIONS)):
                # One statement at a time: executescript() would commit this transaction first.
                for statement in MIGRATIONS[number].split(";"):
                    if statement.strip():
                        self._db.execute(statement)
                self._db.execute(f"PRAGMA user_version = {number + 1}")

    @contextmanager
    def _write(self) -> Iterator[None]:
        """One transaction, taking the write lock at once, rolled back on any error."""
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        self._db.execute("COMMIT")

    def store(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        bars: Sequence[Bar],
        actions: Sequence[CorporateAction],
    ) -> None:
        """Store one fetched range, all of it or none of it, and mark the range as fetched."""
        start, end = span
        symbol = self._symbol(instrument)
        located = [(b.instrument, b.day) for b in bars] + [
            (a.instrument, a.ex_date) for a in actions
        ]
        self._require_within(instrument, span, located)
        with self._write():
            for bar in bars:
                row: _BarRow = (
                    bar.open.amount,
                    bar.high.amount,
                    bar.low.amount,
                    bar.close.amount,
                    bar.volume,
                )
                self._insert_bar(symbol, bar.day, row)
            for action in actions:
                kind, values = _action_row(action)
                self._insert_action(symbol, action.ex_date, kind, values)
            self._db.execute(
                "INSERT OR IGNORE INTO fetched VALUES (?, ?, ?)",
                (symbol, start.isoformat(), end.isoformat()),
            )

    def store_actions(
        self, instrument: Instrument, span: tuple[date, date], actions: Sequence[CorporateAction]
    ) -> None:
        """Store one range's actions, fetched without its bars, all of them or none, and mark the
        range as fetched for actions only (M6 spec §4.3)."""
        start, end = span
        symbol = self._symbol(instrument)
        self._require_within(instrument, span, [(a.instrument, a.ex_date) for a in actions])
        with self._write():
            for action in actions:
                kind, values = _action_row(action)
                self._insert_action(symbol, action.ex_date, kind, values)
            self._db.execute(
                "INSERT OR IGNORE INTO fetched_actions VALUES (?, ?, ?)",
                (symbol, start.isoformat(), end.isoformat()),
            )

    def _require_within(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        located: Sequence[tuple[Instrument, date]],
    ) -> None:
        start, end = span
        for owner, day in located:
            if owner != instrument or not start <= day <= end:
                symbol = instrument.symbol
                msg = f"{owner.symbol} {day.isoformat()} is not {symbol} in {start} to {end}"
                raise ValueError(msg)

    def _insert_bar(self, symbol: str, day: date, row: _BarRow) -> None:
        found = self._db.execute(
            "SELECT open, high, low, close, volume FROM bars WHERE symbol = ? AND day = ?",
            (symbol, day.isoformat()),
        ).fetchone()
        if found is None:
            self._db.execute(
                "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?)", (symbol, day.isoformat(), *row)
            )
        elif tuple(found) != row:
            msg = (
                f"{symbol} {day.isoformat()}: cached bar {tuple(found)} differs from fetched {row}"
            )
            raise CacheConflictError(msg)

    def _insert_action(self, symbol: str, day: date, kind: str, values: _ActionRow) -> None:
        found = self._db.execute(
            "SELECT old_shares, new_shares, per_share, description FROM actions "
            "WHERE symbol = ? AND ex_date = ? AND kind = ?",
            (symbol, day.isoformat(), kind),
        ).fetchone()
        if found is None:
            self._db.execute(
                "INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (symbol, day.isoformat(), kind, *values),
            )
        elif tuple(found) != values:
            msg = (
                f"{symbol} {day.isoformat()}: cached {kind} {tuple(found)} "
                f"differs from fetched {values}"
            )
            raise CacheConflictError(msg)

    def bars(self, instrument: Instrument, start: date, end: date) -> list[Bar]:
        symbol = self._symbol(instrument)
        rows = self._db.execute(
            "SELECT day, open, high, low, close, volume FROM bars "
            "WHERE symbol = ? AND day BETWEEN ? AND ? ORDER BY day",
            (symbol, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [
            Bar(
                instrument,
                date.fromisoformat(day),
                Money(opening, IDR),
                Money(high, IDR),
                Money(low, IDR),
                Money(closing, IDR),
                volume,
            )
            for day, opening, high, low, closing, volume in rows
        ]

    def actions(self, instrument: Instrument, start: date, end: date) -> list[CorporateAction]:
        symbol = self._symbol(instrument)
        rows = self._db.execute(
            "SELECT ex_date, kind, old_shares, new_shares, per_share, description FROM actions "
            "WHERE symbol = ? AND ex_date BETWEEN ? AND ? ORDER BY ex_date, kind",
            (symbol, start.isoformat(), end.isoformat()),
        ).fetchall()
        found: list[CorporateAction] = []
        for day, kind, old, new, per_share, description in rows:
            ex_date = date.fromisoformat(day)
            if kind == "split":
                found.append(Split(instrument, ex_date, old, new))
            elif kind == "dividend":
                found.append(CashDividend(instrument, ex_date, Decimal(per_share)))
            else:
                found.append(OtherAction(instrument, ex_date, description))
        return found

    def fetched(self, instrument: Instrument) -> list[tuple[date, date]]:
        """Every range stored for *instrument*, merged where they touch or overlap."""
        rows = self._db.execute(
            "SELECT start, end FROM fetched WHERE symbol = ? ORDER BY start, end",
            (self._symbol(instrument),),
        ).fetchall()
        return _merged(rows)

    def fetched_actions(self, instrument: Instrument) -> list[tuple[date, date]]:
        """Every range whose actions are stored for *instrument*, with or without its bars,
        merged where they touch or overlap."""
        rows = self._db.execute(
            "SELECT start, end FROM fetched WHERE symbol = ? "
            "UNION SELECT start, end FROM fetched_actions WHERE symbol = ? ORDER BY start, end",
            (self._symbol(instrument), self._symbol(instrument)),
        ).fetchall()
        return _merged(rows)

    @staticmethod
    def _symbol(instrument: Instrument) -> str:
        if instrument.market != "IDX" or instrument.currency != IDR:
            msg = f"this cache holds IDX IDR stocks, not {instrument.symbol} on {instrument.market}"
            raise ValueError(msg)
        return instrument.symbol


def _merged(rows: Sequence[tuple[str, str]]) -> list[tuple[date, date]]:
    """Stored ``(start, end)`` rows, in start order, merged where they touch or overlap."""
    merged: list[tuple[date, date]] = []
    for first, last in rows:
        start, end = date.fromisoformat(first), date.fromisoformat(last)
        if merged and start <= merged[-1][1] + _ONE_DAY:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def jakarta_today() -> date:
    """Today's date in Jakarta, where the IDX trading day is counted."""
    return datetime.now(JAKARTA).date()


class CachedDataSource:
    """A ``DataSource`` that answers from ``BarCache`` and fetches only what it is missing."""

    def __init__(
        self,
        upstream: DataSource,
        cache: BarCache,
        calendar: IdxCalendar | None = None,
        *,
        today: Callable[[], date] = jakarta_today,
    ) -> None:
        self._upstream = upstream
        self._cache = cache
        self._calendar = IdxCalendar.shipped() if calendar is None else calendar
        self._today = today

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        today = self._fill(instrument, start, end)
        cached = self._cache.bars(instrument, start, min(end, today - _ONE_DAY))
        if end < today:
            return cached
        return [*cached, *self._upstream.bars(instrument, today, today)]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        """The range's actions. A part not yet stored is fetched without its bars and stored
        as fetched for actions only, so a look-back never reads a price (M6 spec §4.3)."""
        today = self._today_for(start, end)
        complete = min(end, today - _ONE_DAY)
        if start <= complete:
            for first, last in self.missing_actions(instrument, start, complete):
                actions = self._upstream.corporate_actions(instrument, first, last)
                self._cache.store_actions(instrument, (first, last), actions)
        cached = self._cache.actions(instrument, start, complete)
        if end < today:
            return cached
        return [*cached, *self._upstream.corporate_actions(instrument, today, today)]

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
        """The parts of *start* to *end* not yet stored, trimmed to trading days.

        A gap holding no trading day (a weekend, a holiday) is not missing: there is nothing
        there to fetch, and asking Yahoo for it would fail.
        """
        gaps = _gaps(self._cache.fetched(instrument), start, end)
        return [span for first, last in gaps if (span := self._trading(first, last)) is not None]

    def missing_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> list[tuple[date, date]]:
        """The parts of *start* to *end* whose actions are not yet stored, with or without bars.

        A gap in years the holiday calendar covers is trimmed to its trading days, as in
        ``missing``. A gap reaching into a year it does not cover is asked for whole: actions
        need no calendar, and such a gap is the start of a look-back, years long.
        """
        found: list[tuple[date, date]] = []
        for first, last in _gaps(self._cache.fetched_actions(instrument), start, end):
            try:
                span = self._trading(first, last)
            except UnsupportedDateError:
                span = (first, last)
            if span is not None:
                found.append(span)
        return found

    def _trading(self, first: date, last: date) -> tuple[date, date] | None:
        """*first* to *last* narrowed to its first and last trading day, or ``None`` if it has
        none."""
        days = self._calendar.trading_days(first, last)
        return (days[0], days[-1]) if days else None

    def _today_for(self, start: date, end: date) -> date:
        """Today, once *start* to *end* is a range that can be read today."""
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        today = self._today()
        if end > today:
            msg = (
                f"no bars exist yet after today ({today.isoformat()}); asked for {end.isoformat()}"
            )
            raise ValueError(msg)
        return today

    def _fill(self, instrument: Instrument, start: date, end: date) -> date:
        """Fetch and store every missing range that is over, and return today."""
        today = self._today_for(start, end)
        complete = min(end, today - _ONE_DAY)
        if start <= complete:
            for first, last in self.missing(instrument, start, complete):
                bars = self._upstream.bars(instrument, first, last)
                actions = self._upstream.corporate_actions(instrument, first, last)
                self._cache.store(instrument, (first, last), bars, actions)
        return today


def _gaps(covered: Sequence[tuple[date, date]], start: date, end: date) -> list[tuple[date, date]]:
    """The parts of *start* to *end* outside *covered*, merged ranges in start order."""
    gaps: list[tuple[date, date]] = []
    cursor = start
    for first, last in covered:
        if last < cursor:
            continue
        if first > end:
            break
        if first > cursor:
            gaps.append((cursor, first - _ONE_DAY))
        cursor = last + _ONE_DAY
    if cursor <= end:
        gaps.append((cursor, end))
    return gaps
```

**`packages/steadyhand-idx/src/steadyhand_idx/rules.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/rules.py -->
Replace:
```python
    def is_trading_day(self, day: date) -> bool:
        self.require_supported(day)
        return self._tables.calendar.is_trading_day(day)
```
with:
```python
    def is_trading_day(self, day: date) -> bool:
        return self._tables.calendar.is_trading_day(day)
```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (implemented: 8 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    """
    raise NotImplementedError("actions_in")

```
with:
```python
    """
    actions: list[CorporateAction] = [
        _split(instrument, day, ratio) for day, ratio in history.splits if start <= day <= end
    ]
    for row in history.rows:
        if start <= row.day <= end and row.dividend > 0:
            factor = _factor(history, row.day)
            actions.append(CashDividend(instrument, row.day, row.dividend * factor))
    actions.sort(key=lambda action: action.ex_date)
    return actions

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    """The product of every reported split ratio after *day*, which Yahoo divided *day* by."""
    raise NotImplementedError("_factor")

```
with:
```python
    """The product of every reported split ratio after *day*, which Yahoo divided *day* by."""
    factor = Decimal(1)
    for split_day, ratio in history.splits:
        if split_day > day:
            factor *= ratio
    return factor

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    """The bars and actions from *start* to *end*, with Yahoo's split adjustments reversed."""
    splits = [(day, ratio) for day, ratio in history.splits]
    bars: list[Bar] = []
    actions: list[CorporateAction] = [
        _split(instrument, day, ratio) for day, ratio in splits if start <= day <= end
    ]
    unrecoverable: list[date] = []
```
with:
```python
    """The bars and actions from *start* to *end*, with Yahoo's split adjustments reversed."""
    actions = actions_in(history, instrument, start, end)
    bars: list[Bar] = []
    unrecoverable: list[date] = []
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
            raise DataUnavailableError(msg)
        factor = Decimal(1)
        for day, ratio in splits:
            if day > row.day:
                factor *= ratio
        prices = [_whole(value * factor) for value in (row.open, row.high, row.low, row.close)]
```
with:
```python
            raise DataUnavailableError(msg)
        factor = _factor(history, row.day)
        prices = [_whole(value * factor) for value in (row.open, row.high, row.low, row.close)]
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
            raise DataUnavailableError(msg) from error
        if row.dividend > 0:
            actions.append(CashDividend(instrument, row.day, row.dividend * factor))
    if unrecoverable:
        raise UnrecoverablePricesError(history.ticker, unrecoverable)
    actions.sort(key=lambda action: action.ex_date)
    return bars, actions
```
with:
```python
            raise DataUnavailableError(msg) from error
    if unrecoverable:
        raise UnrecoverablePricesError(history.ticker, unrecoverable)
    return bars, actions
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return self._unadjusted(instrument, start, end)[0]

```
with:
```python
    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        history = self._history(instrument, start, end)
        return unadjust(history, instrument, self._calendar, start, end)[0]

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    ) -> Sequence[CorporateAction]:
        return self._unadjusted(instrument, start, end)[1]

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
        raise NotImplementedError("YahooDataSource._history")

```
with:
```python
    ) -> Sequence[CorporateAction]:
        """The splits and dividends in the range, read without its prices (``actions_in``)."""
        return actions_in(self._history(instrument, start, end), instrument, start, end)

    def _history(self, instrument: Instrument, start: date, end: date) -> YahooHistory:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        return self._fetch(ticker_for(instrument), start, end)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

    def _unadjusted(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[list[Bar], list[CorporateAction]]:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        ticker = ticker_for(instrument)
        return unadjust(self._fetch(ticker, start, end), instrument, self._calendar, start, end)


```
with:
```python


```

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented: 7 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

    ``past`` holds every corporate action fetched, the look-back's included; ``lookback`` is the
    look-back's first and last day, and ``history_refused`` why the source refused a stock's.
    """
```
with:
```python

    ``past`` holds every corporate action fetched, the look-back's and a refused stock's refused
    days' included; ``lookback`` is the look-back's first and last day, and ``history_refused``
    why the source refused a stock's.
    """
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

    A stock whose source refuses some days is fetched again over the clean ranges around them.
    With a look-back, each stock's corporate actions from 1 January, *lookback_years* years
```
with:
```python

    A stock whose source refuses some days is fetched again over the clean ranges around them;
    for its history, its actions over the whole run are read in a call of their own, which a
    source that reads them without prices answers for the refused days too. If the source
    refuses that call, those days' actions are unknown and the stock's history is incomplete.
    With a look-back, each stock's corporate actions from 1 January, *lookback_years* years
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    refused: dict[Instrument, tuple[date, ...]] = {}
    for stock in stocks:
```
with:
```python
    refused: dict[Instrument, tuple[date, ...]] = {}
    past: list[CorporateAction] = []
    unknown: set[Instrument] = set()
    for stock in stocks:
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
            refused[stock] = named
            for low, high in _clean_ranges(days, frozenset(named)):
                bars += source.bars(stock, low, high)
                actions += source.corporate_actions(stock, low, high)
            continue
        bars += found[0]
        actions += found[1]
    by_day: dict[date, list[CorporateAction]] = {}
```
with:
```python
            refused[stock] = named
            whole = _unpriced_actions(source, stock, start, end)
            clean: list[CorporateAction] = []
            for low, high in _clean_ranges(days, frozenset(named)):
                bars += source.bars(stock, low, high)
                clean += source.corporate_actions(stock, low, high)
            actions += clean
            if whole is None:
                unknown.add(stock)
            past += clean if whole is None else whole
            continue
        bars += found[0]
        actions += found[1]
        past += found[1]
    by_day: dict[date, list[CorporateAction]] = {}
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    grouped = {day: tuple(found) for day, found in by_day.items()}
    past = list(actions)
    lookback = None
```
with:
```python
    grouped = {day: tuple(found) for day, found in by_day.items()}
    lookback = None
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
        refused,
        ActionHistory(past, history_refused),
        lookback,
```
with:
```python
        refused,
        ActionHistory(past, {*history_refused, *unknown}),
        lookback,
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    the source refuses them as well (M6 plan scope decision 13)."""
    raise NotImplementedError("_unpriced_actions")

```
with:
```python
    the source refuses them as well (M6 plan scope decision 13)."""
    try:
        return source.corporate_actions(stock, start, end)
    except DataUnavailableError:
        return None

```

**`packages/steadyhand/src/steadyhand/market.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python

        The message names the rule table that sets the limit. Every other method checks this.
        """
```
with:
```python

        The message names the rule table that sets the limit. Every other method checks this,
        except ``is_trading_day``, which answers for every year of holiday data (M6 spec §4.1).
        """
```

**`packages/steadyhand/src/steadyhand/view.py`** (implemented: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
class ActionHistory:
    """Every corporate action a run loaded, the look-back's included, and the stocks whose
    look-back the data source refused (M6 spec §4.1, §4.3). It answers for any day."""

```
with:
```python
class ActionHistory:
    """Every corporate action a run loaded, the look-back's included, and the stocks whose history
    is incomplete: the data source refused their look-back, or their actions on days whose prices
    it refused (M6 spec §4.1, §4.3). It answers for any day."""

```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
    def incomplete(self) -> frozenset[Instrument]:
        """The stocks whose look-back the data source refused."""
        return self._incomplete
```
with:
```python
    def incomplete(self) -> frozenset[Instrument]:
        """The stocks whose history the data source did not give in full."""
        return self._incomplete
```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
    def complete(self, instrument: Instrument) -> bool:
        """Whether the data source gave the stock's whole look-back."""
        return instrument not in self._incomplete
```
with:
```python
    def complete(self, instrument: Instrument) -> bool:
        """Whether the data source gave the stock's whole history."""
        return instrument not in self._incomplete
```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
    def history_complete(self, instrument: Instrument) -> bool:
        """False when the data source refused any part of the stock's look-back (M6 §4.3)."""
        return self._actions.complete(instrument)
```
with:
```python
    def history_complete(self, instrument: Instrument) -> bool:
        """False when the data source refused any part of the stock's corporate actions: its
        look-back, or those of the days whose prices it refused (M6 §4.3)."""
        return self._actions.complete(instrument)
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1500 passed=1500 -->
Expected: every command exits 0; 1500 passed, 100% branch coverage; the performance step passes its eight tests, as Task 1's. CI's second job runs the same 1500 tests on Python 3.13 under `-W error`.

- [ ] **Step 7: Mutations.** Run M319–M331 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(cli): M6 S2 the look-back's IDX data path: dividends read without prices or the calendar, actions-only cache ranges, and trading days from the holiday data`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 3: M6 S3 monthly-savings and the [strategy] settings

**Acceptance criteria (story text):**
1. `MonthlySavings(instalments)` (registered as `monthly-savings`, one setting `instalments`: default 12, 1 to 120) fixes its instalment on its first day as the spendable cash divided by `instalments`, rounded down. On the first day it decides in each calendar month it spends its spendable cash less a reserve for the instalments still due after this one, split equally across the stocks buyable that day, and keeps every holding at its weight; later days that month buy nothing. It never sells, a month with nothing buyable waits for a day that has something, after the last instalment it spends everything each month, and `instalments = 1` is a lump sum then monthly reinvestment. The reserve for the instalments still due is never spent before its month: a property over random months, days, top-ups and buyable stocks checks it against the months the test itself counts, never the strategy's own memory (the strategy reads no price, so none is drawn).
2. `steadyhand.toml`'s `[strategy]` holds `name` and, flat beside it, every registered strategy's settings, each checked whichever strategy runs (a whole number within its bounds, naming the table and key), a file without one taking its default. A setting's name belongs to one strategy only. `init` writes every setting under its one-line comment.
3. `backtest`, `compare` and `paper run` make the strategy from the configuration's settings. The paper audit records the running strategy's settings, writes a first-seen setting as "recorded for the first time" and a changed one with "the strategy's guide says when a change takes effect" (scope decision 9).
4. `guides/monthly-savings.md` has every section core §8 asks for and names `instalments`; `strategies` lists `monthly-savings`, and `explain monthly-savings` prints its guide.
5. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M332–M344 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand/strategies/monthly_savings.py`, `.../steadyhand/strategies/guides/monthly-savings.md`, `tests/engine/test_monthly_savings.py`
- Modify: `.../steadyhand/{__init__,strategies/__init__,strategies/registry}.py`, `.../steadyhand_idx/{config,cli,paper}.py`
- Test: `tests/cli/{test_config,test_backtest_command,test_paper_run,test_journeys,test_strategies_command}.py`, `tests/engine/test_registry.py`

**Interfaces:**
- Consumes: Task 1's `Setting`, `Registered.values`, `MarketView`, `Decision`.
- Produces: `MonthlySavings(instalments)` with `instalments`, exported from `steadyhand`; the registry entry `monthly-savings`; `steadyhand_idx.config.strategy_keys(strategies)` and `Config.strategy_settings: Mapping[str, int]`; `settings_of(config)` gains `strategy.<setting>` keys.

- [ ] **Step 1: Branch.** `git switch -c m6/s3-monthly-savings origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/test_backtest_command.py`** (changed: 1 edit)

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
    del seconds
```
with:
```python
    del seconds


def test_monthly_savings_spreads_the_starting_cash_over_its_instalments(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home", GOLDEN_CONFIG + "\n[strategy]\ninstalments = 4\n")
    result = market("backtest", *WINDOW, "--strategy", "monthly-savings")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Backtest: monthly-savings, 2021-02-01 to 2022-01-31, 248 trading days\n\n"
    )
    assert result.out.split("\n\n")[1].splitlines()[:2] == [
        "                       monthly-savings     buy-and-hold",
        "Final value            IDR 100,655,756   IDR 97,889,490",
    ]
    daily = market.home / "reports" / "backtest-monthly-savings-2021-02-01-2022-01-31.csv"
    cash: dict[str, list[int]] = {}
    with daily.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            held = int(row["settled_cash"]) + int(row["unsettled_cash"])
            cash.setdefault(row["day"][:7], []).append(held)
    # Each instalment of 25,000,000 fills the day after the month's first trading day, and the
    # instalments still due stay back as cash until their month.
    for bought, month in enumerate(["2021-02", "2021-03", "2021-04", "2021-05"], start=1):
        reserve = (4 - bought) * 25_000_000
        assert reserve <= cash[month][1] < reserve + 25_000_000, month
```

**`tests/cli/test_config.py`** (changed: 7 edits)

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
    BacktestSettings,
    EngineSettings,
```
with:
```python
    BacktestSettings,
    BuyAndHold,
    EngineSettings,
```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
    Money,
    RiskLimits,
)
from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.config import KEYS, Config, ConfigMissingError, load, starter

```
with:
```python
    Money,
    Registered,
    RiskLimits,
    Setting,
    Turnover,
)
from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.config import (
    KEYS,
    Config,
    ConfigMissingError,
    load,
    starter,
    strategy_keys,
)

```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
    assert config.strategy == "buy-and-hold"
    assert config.lq45_members == tmp_path / "lq45_members.toml"
```
with:
```python
    assert config.strategy == "buy-and-hold"
    assert config.strategy_settings == {"instalments": 12}
    assert config.lq45_members == tmp_path / "lq45_members.toml"
```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
            written += 1
    assert written == 14

```
with:
```python
            written += 1
    assert written == 15
    assert "# The months monthly-savings spreads the starting cash over: 1 to 120.\n" in "\n".join(
        lines
    )
    assert "instalments = 12" in lines

```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
        lambda c: c.settings.engine.dividend_reinvestment_exemption,
    ),
]

```
with:
```python
        lambda c: c.settings.engine.dividend_reinvestment_exemption,
    ),
    ("strategy", "instalments = 1", lambda c: c.strategy_settings == {"instalments": 1}),
    ("strategy", "instalments = 120", lambda c: c.strategy_settings == {"instalments": 120}),
    ("strategy", 'name = "monthly-savings"', lambda c: c.strategy == "monthly-savings"),
]

```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
        'name = "dividend-growth"',
        "name must be one of buy-and-hold, got 'dividend-growth'",
    ),
    ("risk", 'max_weight = "0"', 'max_weight must be above 0 and at most 1, got "0"'),
```
with:
```python
        'name = "dividend-growth"',
        "name must be one of buy-and-hold, monthly-savings, got 'dividend-growth'",
    ),
    # A setting of a strategy that is not running is checked all the same (M6 spec §4.5).
    ("strategy", "instalments = 0", "instalments must be an integer of at least 1, got 0"),
    ("strategy", "instalments = 121", "instalments must be at most 120, got 121"),
    ("strategy", 'instalments = "12"', "instalments must be an integer of at least 1, got '12'"),
    ("strategy", "instalments = true", "instalments must be an integer of at least 1, got True"),
    ("strategy", "instalment = 12", "unknown key 'instalment'"),
    ("risk", 'max_weight = "0"', 'max_weight must be above 0 and at most 1, got "0"'),
```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
        config.training["level"] = "new"  # type: ignore[index]
```
with:
```python
        config.training["level"] = "new"  # type: ignore[index]


def test_a_setting_name_may_belong_to_one_strategy_only() -> None:
    rounds = Setting("rounds", 3, 1, 9, "How many rounds.")
    one = Registered(BuyAndHold, "One.", Turnover.LOW, (rounds,))
    assert [key.name for key in strategy_keys({"one": one})] == ["name", "rounds"]
    with pytest.raises(
        ValueError, match=r"^\[strategy\] rounds would be the key of more than one setting$"
    ):
        strategy_keys({"one": one, "two": Registered(BuyAndHold, "Two.", Turnover.LOW, (rounds,))})
    named = Registered(BuyAndHold, "Named.", Turnover.LOW, (Setting("name", 1, 1, 1, "x"),))
    with pytest.raises(ValueError, match=r"^\[strategy\] name would be the key of more than"):
        strategy_keys({"named": named})
    assert [key.name for key in KEYS["strategy"]] == ["name", "instalments"]
```

**`tests/cli/test_journeys.py`** (changed: 1 edit)

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
    assert listed.code == 0
    assert "buy-and-hold  low" in listed.out
    assert "What this means" in listed.out
```
with:
```python
    assert listed.code == 0
    assert "buy-and-hold     low" in listed.out
    assert "monthly-savings  low" in listed.out
    assert "What this means" in listed.out
```

**`tests/cli/test_paper_run.py`** (changed: 3 edits)

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
from steadyhand import (
    RISK_HALT_DAILY_LOSS,
```
with:
```python
from steadyhand import (
    IDR,
    RISK_HALT_DAILY_LOSS,
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    Market,
    day_inputs,
```
with:
```python
    Market,
    Money,
    day_inputs,
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
        assert len(store.runs()) == 3
```
with:
```python
        assert len(store.runs()) == 3


MONTHLY_CONFIG = GOLDEN_CONFIG + '\n[strategy]\nname = "monthly-savings"\ninstalments = 4\n'
"""The golden settings with ``monthly-savings`` spreading the starting cash over four months."""


def test_the_settings_of_the_strategy_that_runs_are_recorded_with_the_engines(
    tmp_path: Path,
) -> None:
    monthly = settings_of(load(paper(tmp_path, MONTHLY_CONFIG).config))
    assert monthly["strategy.instalments"] == "4"
    plain = settings_of(load(paper(tmp_path / "plain").config))
    assert [key for key in plain if key.startswith("strategy.")] == []


def test_a_changed_strategy_setting_is_recorded_and_its_guide_says_when_it_applies(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path, MONTHLY_CONFIG)
    run_on(cli, START)
    cli.config.write_text(
        MONTHLY_CONFIG.replace("instalments = 4", "instalments = 6"), encoding="utf-8"
    )
    run_on(cli, trading_days()[1])
    with opened(cli) as store:
        changed = [
            (line.day, line.note.text)
            for line in store.audit()
            if line.note.key == PAPER_SETTING_CHANGED
        ]
        account = store.account()
    assert changed == [
        (
            trading_days()[1],
            (
                "strategy.instalments changed from 4 to 6; the strategy's guide says when a "
                "change takes effect"
            ),
        )
    ]
    assert account is not None
    # monthly-savings fixed its instalment on its first day: a quarter of the starting cash.
    assert account.state.memory["instalment"] == "25000000"


def test_a_strategy_switched_to_records_its_settings_the_first_day_it_runs(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    cli.config.write_text(MONTHLY_CONFIG, encoding="utf-8")
    assert cli("paper", "switch", "monthly-savings", stdin="monthly-savings\n").code == 0
    run_on(cli, trading_days()[1])
    with opened(cli) as store:
        recorded = [
            (line.day, line.note.text)
            for line in store.audit()
            if line.note.key == PAPER_SETTING_CHANGED
        ]
        account = store.account()
    assert recorded == [
        (trading_days()[1], "strategy.instalments is 4, recorded for the first time")
    ]
    assert account is not None
    # buy-and-hold had spent all but Rp 341,160 of the starting cash: monthly-savings sizes its
    # instalment from that cash, not from the portfolio's value (M6 spec §5).
    cash = account.state.holdings.portfolio.spendable_cash(trading_days()[1])
    assert cash == Money(341_160, IDR)
    assert account.state.memory == {"instalment": "85290", "due": "3", "month": "2021-02"}
```

**`tests/cli/test_strategies_command.py`** (changed: 3 edits)

<!-- edit: tests/cli/test_strategies_command.py -->
Replace:
```python

from cli_world import Cli
```
with:
```python

import pytest
from cli_world import Cli
```

<!-- edit: tests/cli/test_strategies_command.py -->
Replace:
```python
        (
            "Strategy      Turnover  What it does\n"
            "buy-and-hold  low       Buys every stock it can on its first day in equal parts, "
            "then holds and reinvests.\n\n"
            "Read a strategy's guide with: steadyhand-idx explain <strategy>\n\n"
```
with:
```python
        (
            "Strategy         Turnover  What it does\n"
            "buy-and-hold     low       Buys every stock it can on its first day in equal parts, "
            "then holds and reinvests.\n"
            "monthly-savings  low       Invests the starting cash in monthly instalments across "
            "every stock it can buy, and never sells.\n\n"
            "Read a strategy's guide with: steadyhand-idx explain <strategy>\n\n"
```

<!-- edit: tests/cli/test_strategies_command.py -->
Replace:
```python

def test_explain_prints_the_guide_then_the_footer(cli: Cli) -> None:
    assert cli("explain", "buy-and-hold") == (
        0,
        f"{guide('buy-and-hold').rstrip()}\n\n{DISCLAIMER}\n",
        "",
    )

```
with:
```python

@pytest.mark.parametrize("name", ["buy-and-hold", "monthly-savings"])
def test_explain_prints_the_guide_then_the_footer(cli: Cli, name: str) -> None:
    assert guide(name).startswith(f"# {name}\n")
    assert cli("explain", name) == (0, f"{guide(name).rstrip()}\n\n{DISCLAIMER}\n", "")

```

**`tests/engine/test_monthly_savings.py`** (new)

<!-- file: tests/engine/test_monthly_savings.py -->
```python
"""monthly-savings: the starting cash in monthly instalments, never selling (M6 spec §5)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand._ratio import ratio_down
from steadyhand.market import PayDates
from steadyhand.money import IDR, Money
from steadyhand.strategies import MonthlySavings, Strategy
from steadyhand.types import Instrument
from steadyhand.view import ActionHistory, MarketView, PortfolioView, PriceHistory, Tradable
from steadyhand_idx import IdxMarketRules

STOCKS = [Instrument(code, "IDX", IDR) for code in ("ASII", "BBCA", "BBRI", "TLKM")]
ASII, BBCA, BBRI, TLKM = STOCKS
JUNE, LATER_IN_JUNE, JULY, AUGUST = (
    date(2025, 6, 2),
    date(2025, 6, 3),
    date(2025, 7, 1),
    date(2025, 8, 1),
)


@cache
def pay_dates() -> PayDates:
    return PayDates(IdxMarketRules(), 14)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def view(day: date, buyable: set[Instrument]) -> MarketView:
    tradable = Tradable(day, frozenset(buyable), frozenset(), {}, frozenset(buyable))
    return MarketView(PriceHistory([]), day, tradable, ActionHistory(), pay_dates())


def portfolio(spendable: int, held: dict[Instrument, int] | None = None) -> PortfolioView:
    holdings = {stock: rp(value) for stock, value in (held or {}).items()}
    return PortfolioView(rp(spendable + sum((held or {}).values())), rp(spendable), holdings)


def test_it_is_a_strategy_named_monthly_savings() -> None:
    strategy: Strategy = MonthlySavings(12)
    assert isinstance(strategy, Strategy)
    assert strategy.name == "monthly-savings"
    assert MonthlySavings(12).instalments == 12
    with pytest.raises(ValueError, match=r"^instalments must be at least 1, got 0$"):
        MonthlySavings(0)


def test_its_first_day_fixes_the_instalment_and_buys_one_split_equally() -> None:
    decision = MonthlySavings(12).decide(view(JUNE, {BBCA, BBRI}), portfolio(12_000_000), {})
    # The instalment is 12,000,000 // 12 = 1,000,000; eleven stay back, so 500,000 a stock.
    each = ratio_down(500_000, 12_000_000)
    assert each == Decimal("0.04166666666666666666666666666")
    assert decision.weights == {BBCA: each, BBRI: each}
    assert decision.memory == {"instalment": "1000000", "due": "11", "month": "2025-06"}
    assert decision.notes == ()


def test_the_instalment_is_whole_and_rounded_down() -> None:
    decision = MonthlySavings(7).decide(view(JUNE, {BBCA}), portfolio(1_000_000), {})
    # 1,000,000 // 7 = 142,857 a month; six of them, 857,142, stay back.
    assert decision.memory["instalment"] == "142857"
    assert decision.weights == {BBCA: ratio_down(1_000_000 - 6 * 142_857, 1_000_000)}


def test_later_days_in_the_month_keep_every_holding_and_buy_nothing() -> None:
    memory = {"instalment": "1000000", "due": "11", "month": "2025-06"}
    held = portfolio(11_300_000, {BBCA: 600_000, ASII: 400_000})
    decision = MonthlySavings(12).decide(view(LATER_IN_JUNE, {BBCA, BBRI}), held, memory)
    assert decision.weights == {BBCA: held.weight(BBCA), ASII: held.weight(ASII)}
    assert decision.memory == memory


def test_the_next_month_buys_its_instalment_with_the_cash_that_arrived_since() -> None:
    memory = {"instalment": "1000000", "due": "11", "month": "2025-06"}
    # 11,000,000 of reserve and 300,000 of dividends: ten instalments stay back, 1,300,000 goes.
    held = portfolio(11_300_000, {BBCA: 1_000_000})
    decision = MonthlySavings(12).decide(view(JULY, {BBCA, BBRI}), held, memory)
    each = ratio_down(650_000, 12_300_000)
    assert decision.weights == {BBCA: held.weight(BBCA) + each, BBRI: each}
    assert decision.memory == {"instalment": "1000000", "due": "10", "month": "2025-07"}


def test_the_last_instalment_spends_everything_and_so_does_every_month_after() -> None:
    last = {"instalment": "1000000", "due": "1", "month": "2025-06"}
    decision = MonthlySavings(12).decide(view(JULY, {BBCA}), portfolio(1_250_000), last)
    assert decision.weights == {BBCA: ratio_down(1_250_000, 1_250_000)}
    assert decision.memory == {"instalment": "1000000", "due": "0", "month": "2025-07"}
    after = MonthlySavings(12).decide(view(AUGUST, {BBCA}), portfolio(80_000), decision.memory)
    assert after.weights == {BBCA: Decimal(1)}
    assert after.memory == {"instalment": "1000000", "due": "0", "month": "2025-08"}


def test_one_instalment_is_a_lump_sum_then_monthly_reinvestment() -> None:
    decision = MonthlySavings(1).decide(view(JUNE, {BBCA, BBRI}), portfolio(9_000_000), {})
    assert decision.weights == {BBCA: Decimal("0.5"), BBRI: Decimal("0.5")}
    assert decision.memory == {"instalment": "9000000", "due": "0", "month": "2025-06"}


def test_a_month_with_nothing_buyable_waits_for_a_day_that_has_something() -> None:
    first = MonthlySavings(12).decide(view(JUNE, set()), portfolio(12_000_000), {})
    assert first.weights == {}
    assert first.memory == {"instalment": "1000000", "due": "12"}
    retry = MonthlySavings(12).decide(
        view(LATER_IN_JUNE, {BBCA}), portfolio(12_000_000), first.memory
    )
    assert retry.weights == {BBCA: ratio_down(1_000_000, 12_000_000)}
    assert retry.memory == {"instalment": "1000000", "due": "11", "month": "2025-06"}


def test_it_never_sells_and_keeps_a_stock_that_left_the_universe() -> None:
    memory = {"instalment": "1000000", "due": "5", "month": "2025-06"}
    held = portfolio(5_000_000, {TLKM: 2_000_000})
    decision = MonthlySavings(12).decide(view(JULY, {BBCA}), held, memory)
    assert decision.weights == {TLKM: held.weight(TLKM), BBCA: ratio_down(1_000_000, 7_000_000)}


def test_a_first_day_on_a_portfolio_that_holds_stocks_sizes_the_instalment_from_cash() -> None:
    held = portfolio(4_000_000, {TLKM: 6_000_000})
    decision = MonthlySavings(4).decide(view(JUNE, {BBCA}), held, {})
    # The portfolio is worth 10,000,000 but only 4,000,000 is cash: 1,000,000 a month.
    assert decision.memory == {"instalment": "1000000", "due": "3", "month": "2025-06"}
    assert decision.weights == {TLKM: held.weight(TLKM), BBCA: ratio_down(1_000_000, 10_000_000)}


@given(
    instalments=st.integers(1, 24),
    start=st.integers(1_000, 10**10),
    months=st.lists(
        st.tuples(st.integers(0, 10**8), st.integers(0, 4), st.integers(1, 3)),
        min_size=1,
        max_size=30,
    ),
)
def test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month(
    instalments: int, start: int, months: list[tuple[int, int, int]]
) -> None:
    strategy = MonthlySavings(instalments)
    memory: dict[str, str] = {}
    cash, invested = start, 0
    # Counted here, not read from the strategy's memory: a month buys once, on its first day
    # with something to buy, so the instalments still due are the ones no month has bought yet.
    bought: set[int] = set()
    for number, (arrived, buyable, days) in enumerate(months):
        if buyable:
            bought.add(number)
        for day in range(1, days + 1):
            held = portfolio(cash, {BBCA: invested} if invested else {})
            when = date(2025 + number // 12, number % 12 + 1, day)
            decision = strategy.decide(view(when, set(STOCKS[:buyable])), held, memory)
            memory = dict(decision.memory)
            added = sum(decision.weights.values()) - held.weight(BBCA)
            assert all(decision.weights[stock] >= held.weight(stock) for stock in held.holdings)
            spent = int(added * held.value.amount)
            cash, invested = cash - spent, invested + spent
            due = max(instalments - len(bought), 0)
            assert int(memory["due"]) == due
            assert cash >= due * int(memory["instalment"])
        cash += arrived
```

**`tests/engine/test_registry.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_registry.py -->
Replace:
```python
    Memory,
    PortfolioView,
```
with:
```python
    Memory,
    MonthlySavings,
    PortfolioView,
```

<!-- edit: tests/engine/test_registry.py -->
Replace:
```python
        Registered(_Rounds, "x", Turnover.LOW, ("rounds",))  # type: ignore[arg-type]
```
with:
```python
        Registered(_Rounds, "x", Turnover.LOW, ("rounds",))  # type: ignore[arg-type]


def test_monthly_savings_spreads_the_starting_cash_over_12_instalments_by_default() -> None:
    entry = STRATEGIES["monthly-savings"]
    assert entry.make is MonthlySavings
    assert entry.turnover is Turnover.LOW
    assert entry.settings == (
        Setting(
            "instalments",
            12,
            1,
            120,
            "The months monthly-savings spreads the starting cash over: 1 to 120.",
        ),
    )
    assert entry.lookback_years() == 0
    made = entry({"instalments": 6, "rounds": 1})
    assert isinstance(made, MonthlySavings)
    assert made.instalments == 6
    assert isinstance(entry(), MonthlySavings)
    assert entry().name == "monthly-savings"
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/config.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
and the key. Rates are strings parsed to ``Decimal``, so a TOML float is refused.

```
with:
```python
and the key. Rates are strings parsed to ``Decimal``, so a TOML float is refused.

``[strategy]`` holds ``name`` and, flat beside it, every registered strategy's settings (M6 spec
§4.5). Each is checked whichever strategy runs, so a mistake is found before anyone switches to
that strategy, and a file written before a setting existed takes its default.

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
    Money,
    RiskLimits,
```
with:
```python
    Money,
    Registered,
    RiskLimits,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python

KEYS: Final[Mapping[str, tuple[Key, ...]]] = MappingProxyType(
```
with:
```python

def strategy_keys(strategies: Mapping[str, Registered]) -> tuple[Key, ...]:
    """``[strategy]``'s keys: ``name``, then each registered strategy's settings, in registry
    order. A setting's name may belong to one strategy only, so the flat table stays unambiguous
    (M6 spec §4.5)."""
    keys = [Key("name", "buy-and-hold", "The strategy to run: see steadyhand-idx strategies.")]
    for entry in strategies.values():
        keys += [Key(setting.name, setting.default, setting.help) for setting in entry.settings]
    names = [key.name for key in keys]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        msg = f"[strategy] {twice[0]} would be the key of more than one setting"
        raise ValueError(msg)
    return tuple(keys)


KEYS: Final[Mapping[str, tuple[Key, ...]]] = MappingProxyType(
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
        ),
        "strategy": (
            Key("name", "buy-and-hold", "The strategy to run: see steadyhand-idx strategies."),
        ),
        "risk": (
```
with:
```python
        ),
        "strategy": strategy_keys(STRATEGIES),
        "risk": (
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python

def _consent(row: Row, where: Where) -> date:
```
with:
```python

def _strategy_settings(row: Row, where: Where) -> dict[str, int]:
    """Every registered strategy's settings, each a whole number within its bounds."""
    raise NotImplementedError("_strategy_settings")


def _consent(row: Row, where: Where) -> date:
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    Memory,
    Registered,
```
with:
```python
    Memory,
    MonthlySavings,
    Registered,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "MonthlyIncome",
    "MovementKind",
```
with:
```python
    "MonthlyIncome",
    "MonthlySavings",
    "MovementKind",
```

**`packages/steadyhand/src/steadyhand/strategies/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/__init__.py -->
Replace:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Decision, InvalidWeightsError, Memory, Strategy
```
with:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.monthly_savings import MonthlySavings
from steadyhand.strategies.protocol import Decision, InvalidWeightsError, Memory, Strategy
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/__init__.py -->
Replace:
```python
    "Memory",
    "Registered",
```
with:
```python
    "Memory",
    "MonthlySavings",
    "Registered",
```

**`packages/steadyhand/src/steadyhand/strategies/monthly_savings.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/monthly_savings.py -->
```python
"""``monthly-savings``: the starting cash invested in monthly instalments (M6 spec §5).

On its first day it fixes the instalment: the cash it may spend that day divided by
``instalments``, rounded down to a whole minor unit. On the first day it decides in each
calendar month it spends its spendable cash less a reserve for the instalments still due after
this one, split equally across the stocks buyable that day, and keeps every holding at its
current weight. It never sells. Top-ups and dividends go in with the next instalment, and after
the last one it spends all its cash each month. A month in which no stock can be bought is not
counted: the next day tries again. With ``instalments = 1`` it invests everything on its first
day, then reinvests monthly.
"""

from __future__ import annotations

from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_int
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.view import MarketView, PortfolioView

_INSTALMENT = "instalment"
"""The memory key holding the instalment, in whole minor units."""

_DUE = "due"
"""The memory key holding how many instalments are still due."""

_MONTH = "month"
"""The memory key holding the last month it bought in, as ``YYYY-MM``."""


class MonthlySavings:
    """Invest the starting cash in equal monthly instalments, then reinvest each month."""

    def __init__(self, instalments: int) -> None:
        raise NotImplementedError("MonthlySavings.__init__")

    @property
    def name(self) -> str:
        raise NotImplementedError("MonthlySavings.name")

    @property
    def instalments(self) -> int:
        """How many instalments a run that starts now spreads its cash over."""
        raise NotImplementedError("MonthlySavings.instalments")

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        raise NotImplementedError("MonthlySavings.decide")
```

**`packages/steadyhand/src/steadyhand/strategies/registry.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy
```
with:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.monthly_savings import MonthlySavings
from steadyhand.strategies.protocol import Strategy
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
        ),
    }
```
with:
```python
        ),
        "monthly-savings": Registered(
            MonthlySavings,
            "Invests the starting cash in monthly instalments across every stock it can buy, "
            "and never sells.",
            Turnover.LOW,
            (
                Setting(
                    "instalments",
                    12,
                    1,
                    120,
                    "The months monthly-savings spreads the starting cash over: 1 to 120.",
                ),
            ),
        ),
    }
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1529 failed=29 -->
Expected: 1529 run, 29 failed. 16 are `NotImplementedError` from the stubs; 3 are `AttributeError` (`Config.strategy_settings`); 4 are `Failed: DID NOT RAISE DataFileError`, the `instalments` bounds not yet checked; one `KeyError` and one assertion are the audit's missing `strategy.instalments`; one `FileNotFoundError` is the guide not yet written, and the guide guard names it; the last two are the CLI run of `monthly-savings` (exit 1 on the stub) and the audit of a switched-to strategy. Five new or changed tests pass against the stubs by design: `strategy_keys` runs at import, so its body is in the stubs step and `test_the_starter_file_writes_every_key_under_its_comment` and `test_a_setting_name_may_belong_to_one_strategy_only` run it; the registry entry is data, so `test_strategies_lists_each_name_turnover_and_summary`, `test_a_first_time_users_journey` (which lists it) and `test_explain_prints_the_guide_then_the_footer[buy-and-hold]` pass.

- [ ] **Step 5: Implement.** The guide is part of this step.

**`packages/steadyhand-idx/src/steadyhand_idx/cli.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    config = ctx.config()
    strategy = _strategy(ctx.args.strategy or config.strategy)
    start, end = _window(ctx)
```
with:
```python
    config = ctx.config()
    strategy = _strategy(ctx.args.strategy or config.strategy, config)
    start, end = _window(ctx)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
        raise UsageError(msg)
    strategies = [_strategy(name) for name in names]
    start, end = _window(ctx)
```
with:
```python
        raise UsageError(msg)
    strategies = [_strategy(name, config) for name in names]
    start, end = _window(ctx)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python

def _strategy(name: str) -> Strategy:
    if name not in STRATEGIES:
        raise UnknownNameError.among(name, STRATEGIES, kind="strategy")
    return STRATEGIES[name]()

```
with:
```python

def _strategy(name: str, config: Config) -> Strategy:
    """The registered strategy *name*, made with the settings in the configuration."""
    if name not in STRATEGIES:
        raise UnknownNameError.among(name, STRATEGIES, kind="strategy")
    return STRATEGIES[name](config.strategy_settings)

```

**`packages/steadyhand-idx/src/steadyhand_idx/config.py`** (implemented: 4 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
    and the income goal, which the file always has and ``goal`` holds as well;
    ``training`` is the ``[training]`` table, unread."""

```
with:
```python
    and the income goal, which the file always has and ``goal`` holds as well;
    ``strategy_settings`` every registered strategy's settings, by name; ``training`` is the
    ``[training]`` table, unread."""

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
    strategy: str
    lq45_members: Path
```
with:
```python
    strategy: str
    strategy_settings: Mapping[str, int]
    lq45_members: Path
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
        strategy=_choice(tables["strategy"], "name", where["strategy"], STRATEGIES),
        lq45_members=path.parent / get_str(tables["universe"], "lq45_members", where["universe"]),
```
with:
```python
        strategy=_choice(tables["strategy"], "name", where["strategy"], STRATEGIES),
        strategy_settings=MappingProxyType(
            _strategy_settings(tables["strategy"], where["strategy"])
        ),
        lq45_members=path.parent / get_str(tables["universe"], "lq45_members", where["universe"]),
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
    """Every registered strategy's settings, each a whole number within its bounds."""
    raise NotImplementedError("_strategy_settings")

```
with:
```python
    """Every registered strategy's settings, each a whole number within its bounds."""
    values: dict[str, int] = {}
    for entry in STRATEGIES.values():
        for setting in entry.settings:
            value = get_int(row, setting.name, where, minimum=setting.minimum)
            if value > setting.maximum:
                msg = f"{where}: {setting.name} must be at most {setting.maximum}, got {value}"
                raise DataFileError(msg)
            values[setting.name] = value
    return values

```

**`packages/steadyhand-idx/src/steadyhand_idx/paper.py`** (implemented: 5 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
def settings_of(config: Config) -> dict[str, str]:
    """The settings a day runs with, by configuration key, as the audit log shows them."""
    engine = config.settings.engine
    contribution = engine.monthly_contribution
    return {
```
with:
```python
def settings_of(config: Config) -> dict[str, str]:
    """The settings a day runs with, by configuration key, as the audit log shows them: the
    engine's, and the settings of the strategy that runs (M6 spec §4.5)."""
    engine = config.settings.engine
    contribution = engine.monthly_contribution
    strategy = {
        f"strategy.{setting.name}": str(config.strategy_settings[setting.name])
        for setting in STRATEGIES[config.strategy].settings
    }
    return {
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
        "tax.dividend_reinvestment_exemption": str(engine.dividend_reinvestment_exemption).lower(),
    }
```
with:
```python
        "tax.dividend_reinvestment_exemption": str(engine.dividend_reinvestment_exemption).lower(),
        **strategy,
    }
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
    _require_fresh(inputs, state)
    state, report = run_day(
        state, inputs, STRATEGIES[config.strategy](), rules, config.settings.engine
    )
    lines += _decisions(report)
```
with:
```python
    _require_fresh(inputs, state)
    strategy = STRATEGIES[config.strategy](config.strategy_settings)
    state, report = run_day(state, inputs, strategy, rules, config.settings.engine)
    lines += _decisions(report)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
def _changes(before: Mapping[str, str], after: Mapping[str, str], day: date) -> list[AuditLine]:
    """An audit line for each setting that changed since the last day run (M5 spec §6.5)."""
    lines: list[AuditLine] = []
```
with:
```python
def _changes(before: Mapping[str, str], after: Mapping[str, str], day: date) -> list[AuditLine]:
    """An audit line for each setting that changed since the last day run (M5 spec §6.5).

    A strategy's setting is recorded the first time a day runs with it, as after ``paper
    switch``, and its guide, not this line, says when a change takes effect: ``monthly-savings``
    fixes its instalments on its first day (M6 spec §5).
    """
    lines: list[AuditLine] = []
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
            continue
        if key == STARTING_CASH:
            text = (
```
with:
```python
            continue
        if old is None:
            text = f"{key} is {new}, recorded for the first time"
            lines.append(AuditLine(day, Note(PAPER_SETTING_CHANGED, text)))
        elif key.startswith("strategy."):
            text = (
                f"{key} changed from {old} to {new}; the strategy's guide says when a change "
                "takes effect"
            )
            lines.append(AuditLine(day, Note(PAPER_SETTING_CHANGED, text)))
        elif key == STARTING_CASH:
            text = (
```

**`packages/steadyhand/src/steadyhand/strategies/guides/monthly-savings.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/strategies/guides/monthly-savings.md -->
```markdown
# monthly-savings

> steadyhand is example software that you run yourself, on your own account, and you make your
> own decisions with it. It is not financial advice. You can lose money.

## What it does

It spreads your starting cash over a number of monthly instalments, 12 by default, instead of
investing it all on the first day. On the first day it runs, it divides the cash it can spend by
the number of instalments, and that amount is the instalment. On the first day it runs in each
calendar month, it invests one instalment, split equally across every stock in the universe (by
default the LQ45, IDX's list of 45 large, easily traded stocks) that can be bought that day, and
keeps the rest of the starting cash back for the instalments still to come.

Cash that arrives in between, from a dividend (a share of a company's profit paid to its
shareholders) or from a monthly top-up, goes in with the next instalment. After the last
instalment it invests all its cash each month. It never sells: a stock that joins the LQ45 is
bought from the next instalment on, and a stock that leaves it stays in the portfolio. If no
stock can be bought on its first day in a month, that month's instalment waits for the next day
one can.

## Why people use it

Investing a large sum all at once means buying at whatever the prices are on that one day.
Spreading it over months, often called dollar-cost averaging, buys at many different prices
instead, so a fall soon after you start costs less. Many people also find it an easier way to
begin. Run it beside `buy-and-hold` with `steadyhand-idx compare` to see what spreading the
purchases out cost or saved over the same days.

## When it tends to do badly

When prices rise through the months it is still investing, it buys later and higher than a lump
sum would have, so in a rising market it is expected to trail `buy-and-hold`. The cash waiting
for its instalment earns nothing in steadyhand's model, although a real account might pay some
interest on it. Once every instalment is invested it behaves much like `buy-and-hold`, and falls
with the market as that does.

## Risks

- **You can lose money.** Share prices can fall a long way and stay down for years, and
  spreading the purchases out does not stop that.
- **Fee drag:** every monthly purchase pays a broker commission, the exchange levy and, on some
  days, stamp duty. Small instalments split across many stocks pay these costs many times over.
- Every stock is bought in whole lots of 100 shares, so a small instalment split across many
  stocks may leave cash unspent, which waits for the next month.
- A stock can be suspended, or its prices can be missing. steadyhand then does not trade it and
  values it at its last known price, which may turn out to be wrong.

## How often it trades

Once a month: it buys on its first day in each calendar month, and it never sells.

## Settings you can change

- `instalments`: how many monthly instalments the starting cash is spread over, from 1 to 120.
  The default is 12. With 1 it invests everything on its first day, then reinvests each month.
  It is fixed when the strategy starts, from the cash it holds then: changing it later does not
  change a run or a paper account already under way.
- `monthly_contribution`: cash added on the first trading day of each month, which goes in with
  that month's instalment. The default is 0.
- The risk limits: the most any one stock may be of the portfolio (10% by default), which caps
  each purchase, and the daily loss and drawdown limits that stop all trading when they are
  reached.
```

**`packages/steadyhand/src/steadyhand/strategies/monthly_savings.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/monthly_savings.py -->
```python
"""``monthly-savings``: the starting cash invested in monthly instalments (M6 spec §5).

On its first day it fixes the instalment: the cash it may spend that day divided by
``instalments``, rounded down to a whole minor unit. On the first day it decides in each
calendar month it spends its spendable cash less a reserve for the instalments still due after
this one, split equally across the stocks buyable that day, and keeps every holding at its
current weight. It never sells. Top-ups and dividends go in with the next instalment, and after
the last one it spends all its cash each month. A month in which no stock can be bought is not
counted: the next day tries again. With ``instalments = 1`` it invests everything on its first
day, then reinvests monthly.
"""

from __future__ import annotations

from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_int
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.view import MarketView, PortfolioView

_INSTALMENT = "instalment"
"""The memory key holding the instalment, in whole minor units."""

_DUE = "due"
"""The memory key holding how many instalments are still due."""

_MONTH = "month"
"""The memory key holding the last month it bought in, as ``YYYY-MM``."""


class MonthlySavings:
    """Invest the starting cash in equal monthly instalments, then reinvest each month."""

    def __init__(self, instalments: int) -> None:
        require_int(instalments, "instalments", minimum=1)
        self._instalments = instalments

    @property
    def name(self) -> str:
        return "monthly-savings"

    @property
    def instalments(self) -> int:
        """How many instalments a run that starts now spreads its cash over."""
        return self._instalments

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        cash = portfolio.spendable.amount
        if _INSTALMENT in memory:
            instalment, due = int(memory[_INSTALMENT]), int(memory[_DUE])
        else:
            instalment, due = cash // self._instalments, self._instalments
        bought = {_MONTH: memory[_MONTH]} if _MONTH in memory else {}
        weights = {stock: portfolio.weight(stock) for stock in portfolio.holdings}
        month = f"{view.today:%Y-%m}"
        buying = view.tradable.buyable
        if buying and bought.get(_MONTH) != month:
            reserve = (due - 1) * instalment if due > 0 else 0
            each = ratio_down(max(cash - reserve, 0) // len(buying), portfolio.value.amount)
            for stock in buying:
                weights[stock] = weights.get(stock, Decimal(0)) + each
            due, bought[_MONTH] = max(due - 1, 0), month
        return Decision(weights, {_INSTALMENT: str(instalment), _DUE: str(due), **bought})
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1529 passed=1529 -->
Expected: every command exits 0; 1529 passed, 100% branch coverage; the performance step passes its eight tests, as Task 1's. CI's second job runs the same 1529 tests on Python 3.13 under `-W error`.

- [ ] **Step 7: Mutations.** Run M332–M344 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M6 S3 monthly-savings, its instalments key and guide, and the [strategy] settings in steadyhand.toml`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 4: M6 S4 dividend-growth, the new default, and its golden run

**Acceptance criteria (story text):**
1. `DividendGrowthStrategy(min_stocks, max_stocks, growth_years)` (scope decision 10), registered as `dividend-growth` with `min_stocks` 15 (1 to 45), `max_stocks` 25 (1 to 45, at least `min_stocks`) and `growth_years` 5 (1 to 10), reads `growth_years` + 1 years before a run. Its settings are refused below 1, and `max_stocks` below `min_stocks` is refused naming both, by the strategy and by the configuration whichever strategy runs.
2. **The test**, on a review in year Y with G = `growth_years`: a member with a complete history that paid a cash dividend in every calendar year from Y−G−1 to Y−1 (by ex-date, per share, restated) and whose total for Y−1 is at least its total for Y−G−1. Pinned at its boundaries: a year with none, the first or last year missing, equal totals, just below, several dividends a year added up, restated by a split, an earlier larger dividend, incomplete history, a non-member.
3. **Candidates** are passers it can buy and passers it holds (a suspended passer is kept). Up to `max_stocks` are all held; with more, it picks one at a time the candidate whose least crowded pay month (from last year's modelled pay dates) has the fewest picks, then the higher trailing yield (the last 365 days' dividends over the last close), then market and symbol. Each pick targets 1 / max(`min_stocks`, picks), rounded down; everything else targets 0. Fewer than `min_stocks` picks adds the `strategy.too_few_qualified` note (scope decision 11), whose lesson is `strategies.holding_cash`.
4. It reviews on its first day and on the first day it decides in each calendar year, and on no other day (a property over random days). Between reviews it keeps every holding and splits the spendable cash across its picks it can buy, never above a pick's target.
5. `dividend-growth` is the default `init` writes and a file without `name` means (such a file beside a `buy-and-hold` paper account then refuses to run, naming both strategies and `paper switch`). `backtest` and `paper run` read the strategy's look-back, and `compare` the longest among its strategies. `guides/dividend-growth.md` has every section, names its settings and says what the spec's §7 asks.
6. The golden run (scope decision 13): `dividend-growth` over the golden window with `VALUES`, TLKM's look-back refused, reproduces `tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json` exactly and holds the reviews worked by hand; the recorder writes it byte for byte; the other two golden files are unchanged. The CLI journeys: `backtest --strategy dividend-growth` ends as the library run, `compare` with all three strategies ends each as it does alone, `paper run` across 2021 into 2022 ends where the backtest does and shows the review, `explain dividend-growth`, and `init` writing the new keys and default.
7. A year of `dividend-growth` over the 45 synthetic stocks, reading six years of look-back, runs inside its measured budget.
8. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M345–M369 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand/strategies/{dividend_growth,_sets}.py`, `.../steadyhand/strategies/guides/dividend-growth.md`, `.../steadyhand/training/lessons/en/strategies.holding_cash.md`, `tests/engine/test_dividend_growth.py`, `tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json` (generated)
- Modify: `.../steadyhand/{__init__,notes,strategies/__init__,strategies/buy_and_hold,strategies/registry}.py`, `.../steadyhand_idx/{config,cli,paper}.py`, `scripts/record_golden.py`
- Test: `tests/cli/{cli_world,test_config,test_backtest_command,test_compare_command,test_paper_run,test_journeys,test_strategies_command}.py`, `tests/engine/test_registry.py`, `tests/golden/test_golden_backtest.py`, `tests/perf/test_performance.py`

**Interfaces:**
- Consumes: Tasks 1–3: `MarketView.dividends`, `pay_date`, `history_complete`, `Tradable.members`, `Decision.notes`, `Setting`, `Registered`, `BacktestSettings.lookback_years`, `day_inputs`, `Config.strategy_settings`.
- Produces: `DividendGrowthStrategy(min_stocks, max_stocks, growth_years)` with `passes(view, stock)`, `min_stocks`, `max_stocks` and `growth_years`, and `STRATEGY_TOO_FEW_QUALIFIED`, exported from `steadyhand`; `steadyhand.strategies._sets.read_set(text, currency)` and `write_set(stocks)`; in `scripts/record_golden.py`: `VALUES`, `GROWTH_GOLDEN`, `REFUSED_HISTORY`, `recorded_refusing_history`, `run(folder, strategy, end, *, income, download)`, `run_growth`, `record_growth`; in `tests/cli/cli_world.py`: `GROWTH_CONFIG`.

- [ ] **Step 1: Branch.** `git switch -c m6/s4-dividend-growth origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/cli_world.py`** (changed: 5 edits)

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python

from steadyhand import BacktestResult, BuyAndHold, DataSource, Market, backtest
from steadyhand_idx import BarCache, CachedDataSource, YahooDataSource
```
with:
```python

from steadyhand import STRATEGIES, BacktestResult, DataSource, Market, backtest
from steadyhand_idx import BarCache, CachedDataSource, YahooDataSource
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python

[risk]
```
with:
```python

[strategy]
name = "buy-and-hold"

[risk]
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
"""The golden run's settings (``record_golden.settings``), so a CLI backtest over its window must
reproduce its figures exactly."""

```
with:
```python
"""The golden run's settings (``record_golden.settings``), so a CLI backtest over its window must
reproduce its figures exactly. It names ``buy-and-hold``, the golden run's strategy, since the
default is ``dividend-growth`` (M6 spec §7)."""

GROWTH_CONFIG = GOLDEN_CONFIG.replace(
    'name = "buy-and-hold"',
    'name = "dividend-growth"\nmin_stocks = 2\nmax_stocks = 2\ngrowth_years = 2',
)
"""The golden settings running ``dividend-growth`` with the golden run's values
(``record_golden.VALUES``): a two-year test, whose look-back fits in the recordings."""

```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
) -> BacktestResult:
    """``buy-and-hold`` from *start*, the golden window's first day by default, to *end*, as
    ``backtest`` runs it over the same configuration, universe files and recorded data. Without
    the income goal unless *goal*: its report reads five years before *end* (M4 spec §8), which
```
with:
```python
) -> BacktestResult:
    """The configured strategy, with its look-back, from *start*, the golden window's first day
    by default, to *end*, as ``backtest`` runs it over the same configuration, universe files and
    recorded data. Without
    the income goal unless *goal*: its report reads five years before *end* (M4 spec §8), which
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
    )
    with recorded_source(cli.home) as source:
        market = Market(universe, source, IdxMarketRules(broker_fees=config.broker_fees))
        return backtest(
            BuyAndHold(),
            market,
            start,
            end,
            config.settings if goal else replace(config.settings, goal=None),
        )
```
with:
```python
    )
    entry = STRATEGIES[config.strategy]
    lookback = entry.lookback_years(config.strategy_settings)
    chosen = replace(config.settings, lookback_years=lookback)
    with recorded_source(cli.home) as source:
        market = Market(universe, source, IdxMarketRules(broker_fees=config.broker_fees))
        return backtest(
            entry(config.strategy_settings),
            market,
            start,
            end,
            chosen if goal else replace(chosen, goal=None),
        )
```

**`tests/cli/test_backtest_command.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python
import pytest
from cli_world import GOLDEN_CONFIG, PLACEHOLDERS, Cli, golden_backtest, market_cli
from record_golden import END, GOLDEN, RECORDED, START, recorded, run, settings, universe
```
with:
```python
import pytest
from cli_world import (
    GOLDEN_CONFIG,
    GROWTH_CONFIG,
    PLACEHOLDERS,
    Cli,
    golden_backtest,
    market_cli,
)
from record_golden import END, GOLDEN, RECORDED, START, recorded, run, settings, universe
```

<!-- edit: tests/cli/test_backtest_command.py -->
Replace:
```python

def test_monthly_savings_spreads_the_starting_cash_over_its_instalments(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home", GOLDEN_CONFIG + "\n[strategy]\ninstalments = 4\n")
    result = market("backtest", *WINDOW, "--strategy", "monthly-savings")
```
with:
```python

def test_dividend_growth_reads_its_look_back_and_ends_as_the_library_run(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home", GROWTH_CONFIG)
    result = market("backtest", *WINDOW, "--strategy", "dividend-growth")
    assert (result.code, result.err) == (0, "")
    assert result.out.startswith(
        "Backtest: dividend-growth, 2021-02-01 to 2022-01-31, 248 trading days\n\n"
    )
    daily = market.home / "reports" / "backtest-dividend-growth-2021-02-01-2022-01-31.csv"
    with daily.open(encoding="utf-8", newline="") as file:
        last = list(csv.reader(file))[-1]
    expected = run(tmp_path / "library", "dividend-growth").run.reports[-1].value.amount
    assert int(last[1]) == expected
    # Blind to its three years of dividends, nothing would pass and it would hold only cash.
    assert expected != 100_000_000


def test_monthly_savings_spreads_the_starting_cash_over_its_instalments(tmp_path: Path) -> None:
    config = GOLDEN_CONFIG.replace(
        'name = "buy-and-hold"', 'name = "buy-and-hold"\ninstalments = 4'
    )
    market = market_cli(tmp_path / "home", config)
    result = market("backtest", *WINDOW, "--strategy", "monthly-savings")
```

**`tests/cli/test_compare_command.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_compare_command.py -->
Replace:
```python
import pytest
from cli_world import Cli, market_cli
from record_golden import GOLDEN

```
with:
```python
import pytest
from cli_world import GROWTH_CONFIG, Cli, market_cli
from record_golden import GOLDEN, run

```

<!-- edit: tests/cli/test_compare_command.py -->
Replace:
```python
    return market_cli(tmp_path / "home")

```
with:
```python
    return market_cli(tmp_path / "home")


def test_each_strategy_ends_as_it_does_alone_with_the_longest_look_back(tmp_path: Path) -> None:
    market = market_cli(tmp_path / "home", GROWTH_CONFIG)
    names = ("buy-and-hold", "monthly-savings", "dividend-growth")
    assert market("compare", *WINDOW, *names).code == 0
    with (market.home / "reports" / f"{STEM}.csv").open(encoding="utf-8", newline="") as file:
        final = {row["strategy"]: int(row["final_value"]) for row in csv.DictReader(file)}
    # One fetch with dividend-growth's three-year look-back serves all three; each run alone
    # takes its own (none for the other two), so any difference would show here.
    alone = {name: run(tmp_path / name, name).run.metrics.final_value.amount for name in names}
    assert final == alone
    assert len(set(alone.values())) == 3

```

**`tests/cli/test_config.py`** (changed: 6 edits)

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
    assert config.broker_fees == "custom"
    assert config.strategy == "buy-and-hold"
    assert config.strategy_settings == {"instalments": 12}
    assert config.lq45_members == tmp_path / "lq45_members.toml"
```
with:
```python
    assert config.broker_fees == "custom"
    assert config.strategy == "dividend-growth"
    assert config.strategy_settings == {
        "instalments": 12,
        "min_stocks": 15,
        "max_stocks": 25,
        "growth_years": 5,
    }
    assert config.lq45_members == tmp_path / "lq45_members.toml"
```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
            written += 1
    assert written == 15
    assert "# The months monthly-savings spreads the starting cash over: 1 to 120.\n" in "\n".join(
```
with:
```python
            written += 1
    assert written == 18
    assert "# The months monthly-savings spreads the starting cash over: 1 to 120.\n" in "\n".join(
```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
    assert "instalments = 12" in lines

```
with:
```python
    assert "instalments = 12" in lines
    assert 'name = "dividend-growth"' in lines
    (index,) = [i for i, line in enumerate(lines) if line == "max_stocks = 25"]
    assert lines[index - 1] == (
        "# The most stocks dividend-growth holds: 1 to 45, and at least min_stocks."
    )
    assert "min_stocks = 15" in lines
    assert "growth_years = 5" in lines

```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
    ),
    ("strategy", "instalments = 1", lambda c: c.strategy_settings == {"instalments": 1}),
    ("strategy", "instalments = 120", lambda c: c.strategy_settings == {"instalments": 120}),
    ("strategy", 'name = "monthly-savings"', lambda c: c.strategy == "monthly-savings"),
]
```
with:
```python
    ),
    ("strategy", "instalments = 1", lambda c: c.strategy_settings["instalments"] == 1),
    ("strategy", "instalments = 120", lambda c: c.strategy_settings["instalments"] == 120),
    ("strategy", 'name = "monthly-savings"', lambda c: c.strategy == "monthly-savings"),
    ("strategy", 'name = "buy-and-hold"', lambda c: c.strategy == "buy-and-hold"),
    ("strategy", "min_stocks = 1", lambda c: c.strategy_settings["min_stocks"] == 1),
    # max_stocks equal to min_stocks is allowed: both at the default max, then the default min.
    ("strategy", "min_stocks = 25", lambda c: c.strategy_settings["min_stocks"] == 25),
    ("strategy", "max_stocks = 15", lambda c: c.strategy_settings["max_stocks"] == 15),
    ("strategy", "max_stocks = 45", lambda c: c.strategy_settings["max_stocks"] == 45),
    ("strategy", "growth_years = 1", lambda c: c.strategy_settings["growth_years"] == 1),
    ("strategy", "growth_years = 10", lambda c: c.strategy_settings["growth_years"] == 10),
]
```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
        "strategy",
        'name = "dividend-growth"',
        "name must be one of buy-and-hold, monthly-savings, got 'dividend-growth'",
    ),
```
with:
```python
        "strategy",
        'name = "momentum"',
        "name must be one of buy-and-hold, dividend-growth, monthly-savings, got 'momentum'",
    ),
    ("strategy", "min_stocks = 0", "min_stocks must be an integer of at least 1, got 0"),
    ("strategy", "min_stocks = 46", "min_stocks must be at most 45, got 46"),
    ("strategy", "max_stocks = 0", "max_stocks must be an integer of at least 1, got 0"),
    ("strategy", "max_stocks = 46", "max_stocks must be at most 45, got 46"),
    ("strategy", "growth_years = 0", "growth_years must be an integer of at least 1, got 0"),
    ("strategy", "growth_years = 11", "growth_years must be at most 10, got 11"),
    # The rule across two settings names both, whichever one moved.
    ("strategy", "max_stocks = 14", "max_stocks must be at least min_stocks (15), got 14"),
    ("strategy", "min_stocks = 26", "max_stocks must be at least min_stocks (26), got 25"),
    # ... and holds while another strategy runs (M6 spec §4.5).
    (
        "strategy",
        'name = "buy-and-hold"\nmin_stocks = 20\nmax_stocks = 19',
        "max_stocks must be at least min_stocks (20), got 19",
    ),
```

<!-- edit: tests/cli/test_config.py -->
Replace:
```python
        strategy_keys({"named": named})
    assert [key.name for key in KEYS["strategy"]] == ["name", "instalments"]
```
with:
```python
        strategy_keys({"named": named})
    assert [key.name for key in KEYS["strategy"]] == [
        "name",
        "instalments",
        "min_stocks",
        "max_stocks",
        "growth_years",
    ]
```

**`tests/cli/test_journeys.py`** (changed: 4 edits)

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
from steadyhand_idx import __version__
from steadyhand_idx.notes import PAPER_RESUMED
```
with:
```python
from steadyhand_idx import __version__
from steadyhand_idx.config import load
from steadyhand_idx.notes import PAPER_RESUMED
```

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
    assert stat.S_IMODE((home / "steadyhand.toml").stat().st_mode) == 0o600

```
with:
```python
    assert stat.S_IMODE((home / "steadyhand.toml").stat().st_mode) == 0o600
    written = load(home / "steadyhand.toml")
    assert written.strategy == "dividend-growth"
    assert written.strategy_settings == {
        "instalments": 12,
        "min_stocks": 15,
        "max_stocks": 25,
        "growth_years": 5,
    }

```

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
    assert "monthly-savings  low" in listed.out
    assert "What this means" in listed.out
```
with:
```python
    assert "monthly-savings  low" in listed.out
    assert "dividend-growth  low" in listed.out
    assert "What this means" in listed.out
```

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
    assert explained.out.startswith("# buy-and-hold\n")

```
with:
```python
    assert explained.out.startswith("# buy-and-hold\n")
    assert installed(home, "explain", "dividend-growth").out.startswith("# dividend-growth\n")

```

**`tests/cli/test_paper_run.py`** (changed: 3 edits)

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    GOLDEN_CONFIG,
    at,
```
with:
```python
    GOLDEN_CONFIG,
    GROWTH_CONFIG,
    at,
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
        "runs retired; to change it, run: steadyhand-idx paper switch buy-and-hold\n"
    )
```
with:
```python
        "runs retired; to change it, run: steadyhand-idx paper switch buy-and-hold\n"
    )
    assert tables(cli) == before


def test_a_file_without_a_strategy_name_now_means_dividend_growth_so_paper_refuses(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    # Without [strategy] name a file meant buy-and-hold before M6; it now means the new default.
    unnamed = GOLDEN_CONFIG.replace('name = "buy-and-hold"\n', "")
    assert unnamed != GOLDEN_CONFIG
    cli.config.write_text(unnamed, encoding="utf-8")
    before = tables(cli)
    result = run_on(cli, trading_days()[1])
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: steadyhand.toml names the strategy dividend-growth, but the paper account "
        "runs buy-and-hold; to change it, run: steadyhand-idx paper switch dividend-growth\n"
    )
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python

MONTHLY_CONFIG = GOLDEN_CONFIG + '\n[strategy]\nname = "monthly-savings"\ninstalments = 4\n'
"""The golden settings with ``monthly-savings`` spreading the starting cash over four months."""

```
with:
```python

MONTHLY_CONFIG = GOLDEN_CONFIG.replace(
    'name = "buy-and-hold"', 'name = "monthly-savings"\ninstalments = 4'
)
"""The golden settings with ``monthly-savings`` spreading the starting cash over four months."""


def test_dividend_growth_reviews_again_on_the_first_trading_day_of_2022(tmp_path: Path) -> None:
    cli = paper(tmp_path, GROWTH_CONFIG)
    run_on(cli, START)
    result = run_on(cli, END, "--catch-up")
    assert result.code == 0, result.err
    expected = golden_backtest(cli, END).run
    with opened(cli) as store:
        reports = store.reports()
        account = store.account()
    assert reports == expected.reports
    assert account is not None
    assert account.state == expected.final
    # 3 January 2022 tests 2019 to 2021: TLKM now passes and UNVR no longer does. The orders
    # it places that day fill on the 4th.
    filled = {
        (fill.order.instrument.symbol, fill.order.side.value)
        for report in reports
        if report.day == date(2022, 1, 4)
        for fill in report.fills
    }
    assert {("TLKM", "buy"), ("UNVR", "sell")} <= filled
    assert account.state.memory == {"set": "IDX:BBCA IDX:TLKM", "year": "2022"}

```

**`tests/cli/test_strategies_command.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_strategies_command.py -->
Replace:
```python
            "then holds and reinvests.\n"
            "monthly-savings  low       Invests the starting cash in monthly instalments across "
```
with:
```python
            "then holds and reinvests.\n"
            "dividend-growth  low       Holds the stocks that paid a dividend in each of the last "
            "six years and grew it, spread across pay months, and reviews them yearly.\n"
            "monthly-savings  low       Invests the starting cash in monthly instalments across "
```

<!-- edit: tests/cli/test_strategies_command.py -->
Replace:
```python

@pytest.mark.parametrize("name", ["buy-and-hold", "monthly-savings"])
def test_explain_prints_the_guide_then_the_footer(cli: Cli, name: str) -> None:
```
with:
```python

@pytest.mark.parametrize("name", ["buy-and-hold", "dividend-growth", "monthly-savings"])
def test_explain_prints_the_guide_then_the_footer(cli: Cli, name: str) -> None:
```

**`tests/engine/test_dividend_growth.py`** (new)

<!-- file: tests/engine/test_dividend_growth.py -->
```python
"""dividend-growth: the stocks that paid a dividend every year and grew it, spread across the
months they pay in (M6 spec §6).

Most tests review on 2 January 2025 with ``growth_years`` 2, so a stock passes when it paid in
2022, 2023 and 2024 and its 2024 total is at least its 2022 total. Every pay date below was read
from the calendar (``PayDates(IdxMarketRules(), 14)``), never counted by hand.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand._ratio import ratio_down
from steadyhand.market import PayDates
from steadyhand.money import IDR, Money
from steadyhand.notes import STRATEGY_TOO_FEW_QUALIFIED, Note
from steadyhand.strategies import DividendGrowthStrategy, Strategy
from steadyhand.types import Bar, CashDividend, CorporateAction, Instrument, Split
from steadyhand.view import ActionHistory, MarketView, PortfolioView, PriceHistory, Tradable
from steadyhand_idx import IdxMarketRules

STOCKS = [Instrument(code, "IDX", IDR) for code in ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")]
ASII, BBCA, BBRI, TLKM, UNVR = STOCKS
REVIEW = date(2025, 1, 2)
"""The first trading day of 2025."""

YEARS = (2022, 2023, 2024)
"""Y - growth_years - 1 to Y - 1 for a 2025 review with growth_years 2."""

MARCH, SEPTEMBER, DECEMBER = date(2024, 3, 4), date(2024, 9, 2), date(2024, 12, 2)
"""Ex-dates that pay in their own month: 26 March, 23 September and 20 December 2024."""

LATE_DECEMBER = date(2024, 12, 20)
"""An ex-date that pays in the next year: 15 January 2025."""

EARLY_JANUARY = date(2024, 1, 4)
"""An ex-date that pays on 24 January 2024, and the first day inside the trailing year."""


@cache
def pay_dates() -> PayDates:
    return PayDates(IdxMarketRules(), 14)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def paid(
    stock: Instrument, amounts: tuple[int | str, ...] = (100, 100, 100), on: date = MARCH
) -> list[CashDividend]:
    """One dividend a year in 2022, 2023 and 2024, on *on*'s month and day."""
    return [
        CashDividend(stock, date(year, on.month, on.day), Decimal(amount))
        for year, amount in zip(YEARS, amounts, strict=True)
    ]


def view(
    day: date,
    buyable: set[Instrument],
    actions: Sequence[CorporateAction] | ActionHistory | None = None,
    *,
    members: set[Instrument] | None = None,
    closes: dict[Instrument, int] | None = None,
) -> MarketView:
    universe = frozenset(buyable if members is None else members | buyable)
    tradable = Tradable(day, frozenset(buyable), frozenset(), {}, universe)
    bars = [
        Bar(stock, day, rp(close), rp(close), rp(close), rp(close), 1_000)
        for stock, close in (closes or {}).items()
    ]
    history = actions if isinstance(actions, ActionHistory) else ActionHistory(actions or [])
    return MarketView(PriceHistory(bars), day, tradable, history, pay_dates())


def portfolio(spendable: int, held: dict[Instrument, int] | None = None) -> PortfolioView:
    holdings = {stock: rp(value) for stock, value in (held or {}).items()}
    return PortfolioView(rp(spendable + sum((held or {}).values())), rp(spendable), holdings)


def growth(min_stocks: int = 1, max_stocks: int = 45, growth_years: int = 2) -> Strategy:
    return DividendGrowthStrategy(min_stocks, max_stocks, growth_years)


def test_the_dates_above_pay_where_the_tests_say() -> None:
    of = pay_dates().of
    assert [of(day) for day in (MARCH, SEPTEMBER, DECEMBER)] == [
        date(2024, 3, 26),
        date(2024, 9, 23),
        date(2024, 12, 20),
    ]
    assert of(LATE_DECEMBER) == date(2025, 1, 15)
    assert of(EARLY_JANUARY) == date(2024, 1, 24)
    assert REVIEW - timedelta(days=365) == date(2024, 1, 3)


def test_it_is_a_strategy_named_dividend_growth_with_its_settings() -> None:
    strategy: Strategy = DividendGrowthStrategy(15, 25, 5)
    assert isinstance(strategy, Strategy)
    assert strategy.name == "dividend-growth"
    made = DividendGrowthStrategy(15, 25, 5)
    assert (made.min_stocks, made.max_stocks, made.growth_years) == (15, 25, 5)
    assert DividendGrowthStrategy(3, 3, 1).max_stocks == 3


@pytest.mark.parametrize(
    ("settings", "error", "message"),
    [
        ((0, 25, 5), ValueError, "min_stocks must be at least 1, got 0"),
        ((15, 0, 5), ValueError, "max_stocks must be at least 1, got 0"),
        ((15, 25, 0), ValueError, "growth_years must be at least 1, got 0"),
        ((15, 14, 5), ValueError, "max_stocks must be at least min_stocks (15), got 14"),
        ((True, 25, 5), TypeError, "min_stocks must be an int, got bool"),
    ],
)
def test_its_settings_are_checked_when_it_is_made(
    settings: tuple[int, int, int], error: type[Exception], message: str
) -> None:
    with pytest.raises(error) as caught:
        DividendGrowthStrategy(*settings)
    assert str(caught.value) == message


SPLIT_2024 = Split(BBCA, date(2024, 1, 10), 1, 2)
"""A 1-into-2 split between the 2023 and 2024 dividends: earlier dividends halve."""

TESTED = [
    ("grew", paid(BBCA, (100, 105, 110)), True),
    ("the last total equals the first", paid(BBCA, (100, 90, 100)), True),
    ("the last total is just below the first", paid(BBCA, (100, 120, "99.99")), False),
    ("a year with no dividend", [paid(BBCA)[0], paid(BBCA)[2]], False),
    (
        "the first year missing, a year before it paid",
        [CashDividend(BBCA, date(2021, 3, 4), Decimal(100)), *paid(BBCA)[1:]],
        False,
    ),
    (
        "the last year missing, today's year paid",
        [*paid(BBCA)[:2], CashDividend(BBCA, REVIEW, Decimal(200))],
        False,
    ),
    (
        "several dividends in a year are added up",
        [*paid(BBCA, (100, 100, 40)), CashDividend(BBCA, SEPTEMBER, Decimal(60))],
        True,
    ),
    (
        "several dividends in a year still fall short",
        [*paid(BBCA, (100, 100, 40)), CashDividend(BBCA, SEPTEMBER, Decimal("59.99"))],
        False,
    ),
    ("restated by a later split: 50, 50, 50", [*paid(BBCA, (100, 100, 50)), SPLIT_2024], True),
    ("restated by a later split: 50, 50, 49", [*paid(BBCA, (100, 100, 49)), SPLIT_2024], False),
    (
        "a larger dividend before the window does not count",
        [CashDividend(BBCA, date(2021, 3, 4), Decimal(500)), *paid(BBCA)],
        True,
    ),
    ("no dividend at all", [], False),
]


@pytest.mark.parametrize(
    ("actions", "passes"), [(a, p) for _, a, p in TESTED], ids=[name for name, _, _ in TESTED]
)
def test_the_dividend_test_at_its_boundaries(
    actions: list[CorporateAction], *, passes: bool
) -> None:
    strategy = DividendGrowthStrategy(1, 45, 2)
    assert strategy.passes(view(REVIEW, {BBCA}, actions), BBCA) is passes


def test_a_stock_with_an_incomplete_history_or_outside_the_universe_fails() -> None:
    strategy = DividendGrowthStrategy(1, 45, 2)
    actions: list[CorporateAction] = [*paid(BBCA), *paid(TLKM)]
    assert strategy.passes(view(REVIEW, {BBCA, TLKM}, actions), BBCA) is True
    refused = ActionHistory(actions, {BBCA})
    assert strategy.passes(view(REVIEW, {BBCA, TLKM}, refused), BBCA) is False
    # TLKM holds its record but has left the universe: it is neither buyable nor a member.
    assert strategy.passes(view(REVIEW, {BBCA}, actions), TLKM) is False


def test_growth_years_sets_how_many_years_must_have_paid() -> None:
    two_years = paid(BBCA)[1:]
    assert DividendGrowthStrategy(1, 45, 1).passes(view(REVIEW, {BBCA}, two_years), BBCA)
    assert not DividendGrowthStrategy(1, 45, 2).passes(view(REVIEW, {BBCA}, two_years), BBCA)


def test_with_at_most_max_stocks_passing_it_holds_them_all_in_equal_parts() -> None:
    actions = [*paid(ASII), *paid(BBCA), *paid(BBRI), *paid(TLKM, (100, 100, 99))]
    decision = growth(min_stocks=2, max_stocks=3).decide(
        view(REVIEW, {ASII, BBCA, BBRI, TLKM}, actions), portfolio(9_000_000), {}
    )
    third = ratio_down(1, 3)
    assert third == Decimal("0.3333333333333333333333333333")
    assert decision.weights == {ASII: third, BBCA: third, BBRI: third}
    assert decision.memory == {"set": "IDX:ASII IDX:BBCA IDX:BBRI", "year": "2025"}
    assert decision.notes == ()


def test_exactly_min_stocks_passing_holds_them_in_equal_parts_with_no_note() -> None:
    decision = growth(min_stocks=2, max_stocks=3).decide(
        view(REVIEW, {ASII, BBCA}, [*paid(ASII), *paid(BBCA)]), portfolio(9_000_000), {}
    )
    assert decision.weights == {ASII: Decimal("0.5"), BBCA: Decimal("0.5")}
    assert decision.notes == ()


@pytest.mark.parametrize(
    ("passers", "text"),
    [
        (
            [],
            "No stock passed the dividend test; everything is held as cash until one does.",
        ),
        (
            [ASII],
            "Only 1 stock passed the dividend test; the rest is held as cash until more do.",
        ),
        (
            [ASII, BBCA, BBRI],
            "Only 3 stocks passed the dividend test; the rest is held as cash until more do.",
        ),
    ],
)
def test_fewer_than_min_stocks_passing_leaves_the_rest_in_cash_and_says_so(
    passers: list[Instrument], text: str
) -> None:
    actions = [dividend for stock in passers for dividend in paid(stock)]
    decision = growth(min_stocks=4, max_stocks=5).decide(
        view(REVIEW, set(STOCKS), actions), portfolio(8_000_000), {}
    )
    # Each passer takes a quarter, 1 / min_stocks, and the rest stays in cash.
    assert decision.weights == dict.fromkeys(passers, Decimal("0.25"))
    assert decision.notes == (Note(STRATEGY_TOO_FEW_QUALIFIED, text),)
    assert decision.memory["year"] == "2025"


def test_a_review_sells_what_failed_or_left_and_keeps_a_suspended_passer() -> None:
    actions = [*paid(ASII), *paid(BBRI), *paid(TLKM), *paid(UNVR), *paid(BBCA, (100, 100, 1))]
    held = {ASII: 1_000_000, BBCA: 1_000_000, TLKM: 1_000_000}
    today = view(
        REVIEW,
        {BBCA, BBRI},
        actions,
        # ASII (held) and UNVR (not held) pass but are suspended; TLKM passes but left.
        members={ASII, BBCA, BBRI, UNVR},
    )
    decision = growth(min_stocks=1, max_stocks=5).decide(today, portfolio(1_000_000, held), {})
    # Candidates: BBRI (buyable) and ASII (held). BBCA failed and TLKM left, so both go to 0;
    # UNVR can neither be bought nor is held.
    assert decision.weights == {ASII: Decimal("0.5"), BBRI: Decimal("0.5")}
    assert decision.memory["set"] == "IDX:ASII IDX:BBRI"


def test_with_more_passers_than_max_stocks_it_spreads_pay_months_before_yield() -> None:
    actions = [
        *paid(ASII, (100, 100, 100), MARCH),
        *paid(BBCA, (120, 120, 120), MARCH),
        *paid(TLKM, (20, 20, 20), SEPTEMBER),
    ]
    closes = dict.fromkeys((ASII, BBCA, TLKM), 2_000)
    decision = growth(max_stocks=2).decide(
        view(REVIEW, {ASII, BBCA, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: BBCA 6%, ASII 5%, TLKM 1%. First pick, no month is crowded: BBCA. Second: ASII
    # would share March with BBCA, TLKM pays alone in September, so TLKM despite its yield.
    assert decision.weights == {BBCA: Decimal("0.5"), TLKM: Decimal("0.5")}


def test_a_stock_paying_in_two_months_is_as_crowded_as_its_least_crowded_month() -> None:
    actions = [
        *paid(BBCA, (60, 60, 60), MARCH),
        *paid(BBCA, (60, 60, 60), SEPTEMBER),
        *paid(ASII, (100, 100, 100), MARCH),
        *paid(TLKM, (40, 40, 40), MARCH),
        *paid(TLKM, (40, 40, 40), DECEMBER),
    ]
    closes = dict.fromkeys((ASII, BBCA, TLKM), 1_000)
    decision = growth(max_stocks=2).decide(
        view(REVIEW, {ASII, BBCA, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: BBCA 12%, ASII 10%, TLKM 8%. BBCA first, crowding March and September. ASII's one
    # month, March, has 1 picked; TLKM's least crowded, December, has 0: TLKM.
    assert decision.weights == {BBCA: Decimal("0.5"), TLKM: Decimal("0.5")}


def test_the_pay_months_are_last_years_modelled_pay_dates() -> None:
    actions = [
        # BBCA's ex-dates are in December; they pay in January.
        *paid(BBCA, (300, 300, 300), LATE_DECEMBER),
        *paid(ASII, (200, 200, 200), EARLY_JANUARY),
        *paid(TLKM, (100, 100, 100), DECEMBER),
        # BBRI paid in September before last year; last year it paid in January.
        *paid(BBRI, (250, 250, 250), SEPTEMBER)[:2],
        CashDividend(BBRI, EARLY_JANUARY, Decimal(250)),
    ]
    closes = dict.fromkeys((ASII, BBCA, BBRI, TLKM), 10_000)
    decision = growth(max_stocks=2).decide(
        view(REVIEW, {ASII, BBCA, BBRI, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: BBCA 3%, BBRI 2.5%, ASII 2%, TLKM 1%. BBCA pays in January. ASII and BBRI pay in
    # January too (BBRI's September is not last year's), and TLKM in December: TLKM.
    assert decision.weights == {BBCA: Decimal("0.5"), TLKM: Decimal("0.5")}


def test_the_trailing_yield_is_the_last_365_days_of_dividends_over_the_last_close() -> None:
    actions = [
        # ASII's 2024 dividend is on 3 January, exactly 365 days back, so outside the window.
        *paid(ASII, (100, 100, 900), date(2024, 1, 3)),
        *paid(BBCA, (100, 100, 100), EARLY_JANUARY),
        *paid(BBRI, (150, 150, 150), EARLY_JANUARY),
        # TLKM's dividends are the largest, but it has no close to divide by.
        *paid(TLKM, (999, 999, 999), EARLY_JANUARY),
    ]
    closes = {ASII: 1_000, BBCA: 1_000, BBRI: 2_000}
    decision = growth(max_stocks=1).decide(
        view(REVIEW, {ASII, BBCA, BBRI, TLKM}, actions, closes=closes), portfolio(1_000_000), {}
    )
    # Yields: ASII 0, BBCA 10%, BBRI 7.5%, TLKM 0.
    assert decision.weights == {BBCA: Decimal(1)}


def test_equal_coverage_and_yield_go_to_market_then_symbol() -> None:
    other = Instrument("AALI", "JKT", IDR)
    stocks = [TLKM, BBCA, ASII, other]
    actions = [dividend for stock in stocks for dividend in paid(stock)]
    decision = growth(max_stocks=2).decide(
        view(REVIEW, set(stocks), actions), portfolio(1_000_000), {}
    )
    # No closes, so every yield is 0 and every month is March. IDX sorts before JKT.
    assert decision.weights == {ASII: Decimal("0.5"), BBCA: Decimal("0.5")}


HOLDING = {ASII: 400, BBCA: 490, TLKM: 50}
"""Picked ASII and BBCA, and TLKM held from before: a 1,000 portfolio with 60 to spend."""


def between(
    buyable: set[Instrument], chosen: str = "IDX:ASII IDX:BBCA", min_stocks: int = 2
) -> dict[Instrument, Decimal]:
    memory = {"set": chosen, "year": "2025"}
    decision = growth(min_stocks=min_stocks, max_stocks=5).decide(
        view(date(2025, 3, 3), buyable), portfolio(60, HOLDING), memory
    )
    assert decision.memory == memory
    assert decision.notes == ()
    return dict(decision.weights)


def test_between_reviews_it_keeps_every_holding_and_tops_up_its_picks_to_their_target() -> None:
    # 60 // 2 = 30 each, 3%. ASII 40% -> 43%. BBCA 49% takes only 1%, up to its target of 50%.
    assert between({ASII, BBCA, TLKM}) == {
        ASII: Decimal("0.43"),
        BBCA: Decimal("0.5"),
        TLKM: Decimal("0.05"),
    }


def test_between_reviews_a_pick_it_cannot_buy_today_gets_nothing() -> None:
    # BBCA alone may be bought: 6% offered, 1% taken.
    assert between({BBCA, TLKM}) == {
        ASII: Decimal("0.4"),
        BBCA: Decimal("0.5"),
        TLKM: Decimal("0.05"),
    }
    assert between(set()) == {ASII: Decimal("0.4"), BBCA: Decimal("0.49"), TLKM: Decimal("0.05")}


def test_between_reviews_the_target_is_one_over_min_stocks_when_fewer_were_picked() -> None:
    # One pick, min_stocks 4: ASII may reach 25%, which is below the 40% it holds.
    assert between({ASII}, "IDX:ASII", min_stocks=4)[ASII] == Decimal("0.4")
    # UNVR, picked but not held, is offered all 60 (6%) and takes it, under its 25% target.
    assert between({UNVR}, "IDX:UNVR", min_stocks=4)[UNVR] == Decimal("0.06")


def test_it_reviews_on_its_first_day_and_its_first_day_in_each_year_only() -> None:
    strategy = growth(min_stocks=1, max_stocks=5)
    actions = [*paid(ASII), CashDividend(ASII, date(2025, 3, 4), Decimal(100)), *paid(BBCA)]
    held = portfolio(0, {ASII: 500, TLKM: 500})

    def decide(day: date, memory: dict[str, str]) -> dict[Instrument, Decimal]:
        decision = strategy.decide(view(day, {ASII, BBCA, TLKM}, actions), held, memory)
        return dict(decision.weights)

    # A first day in June reviews: TLKM fails, so it goes; ASII and BBCA pass.
    assert decide(date(2025, 6, 10), {}) == {ASII: Decimal("0.5"), BBCA: Decimal("0.5")}
    # Later that year it only keeps what it holds.
    kept = {"set": "IDX:ASII IDX:BBCA", "year": "2025"}
    # BBCA, picked but not held, is offered the spendable cash: none, so a weight of 0.
    assert decide(date(2025, 12, 30), kept) == {
        ASII: Decimal("0.5"),
        BBCA: Decimal(0),
        TLKM: Decimal("0.5"),
    }
    # The first day of 2026 reviews again: ASII paid in 2023 to 2025, BBCA stopped in 2024.
    assert decide(date(2026, 1, 2), kept) == {ASII: Decimal(1)}


@given(
    st.lists(
        st.dates(min_value=date(2025, 1, 1), max_value=date(2027, 12, 31)),
        min_size=1,
        max_size=12,
        unique=True,
    ).map(sorted)
)
def test_it_reviews_on_no_day_but_the_first_and_each_new_years_first(days: list[date]) -> None:
    """A review sells TLKM, which never passes; any other day keeps it."""
    strategy = growth()
    actions: list[CorporateAction] = [
        CashDividend(ASII, date(year, 3, 4), Decimal(100)) for year in range(2020, 2028)
    ]
    held = portfolio(0, {ASII: 500, TLKM: 500})
    memory: dict[str, str] = {}
    last_year = None
    for day in days:
        decision = strategy.decide(view(day, {ASII, TLKM}, actions), held, memory)
        reviewed = TLKM not in decision.weights
        assert reviewed is (day.year != last_year)
        memory, last_year = dict(decision.memory), day.year
```

**`tests/engine/test_registry.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_registry.py -->
Replace:
```python
    Decision,
    MarketView,
```
with:
```python
    Decision,
    DividendGrowthStrategy,
    MarketView,
```

<!-- edit: tests/engine/test_registry.py -->
Replace:
```python
    assert entry().name == "monthly-savings"
```
with:
```python
    assert entry().name == "monthly-savings"


def test_dividend_growth_holds_15_to_25_stocks_grown_over_5_years_by_default() -> None:
    entry = STRATEGIES["dividend-growth"]
    assert entry.make is DividendGrowthStrategy
    assert entry.turnover is Turnover.LOW
    assert entry.summary == (
        "Holds the stocks that paid a dividend in each of the last six years and grew it, "
        "spread across pay months, and reviews them yearly."
    )
    assert entry.settings == (
        Setting(
            "min_stocks",
            15,
            1,
            45,
            "Below this many passing stocks, dividend-growth holds the rest as cash: 1 to 45.",
        ),
        Setting(
            "max_stocks",
            25,
            1,
            45,
            "The most stocks dividend-growth holds: 1 to 45, and at least min_stocks.",
        ),
        Setting(
            "growth_years",
            5,
            1,
            10,
            "The years over which dividend-growth wants dividends to have grown: 1 to 10.",
        ),
    )
    made = entry()
    assert isinstance(made, DividendGrowthStrategy)
    assert (made.name, made.min_stocks, made.max_stocks, made.growth_years) == (
        "dividend-growth",
        15,
        25,
        5,
    )
    given = entry({"min_stocks": 2, "max_stocks": 3, "growth_years": 4, "instalments": 9})
    assert isinstance(given, DividendGrowthStrategy)
    assert (given.min_stocks, given.max_stocks, given.growth_years) == (2, 3, 4)
    # The test reads a dividend in each of growth_years + 1 years before the run's first.
    assert entry.lookback_years() == 6
    assert entry.lookback_years({"min_stocks": 15, "max_stocks": 25, "growth_years": 2}) == 3
    assert entry.lookback_years({"min_stocks": 15, "max_stocks": 25, "growth_years": 10}) == 11
    with pytest.raises(
        ValueError, match=r"^max_stocks must be at least min_stocks \(15\), got 14$"
    ):
        entry({"min_stocks": 15, "max_stocks": 14, "growth_years": 5})
```

**`tests/golden/test_golden_backtest.py`** (changed: 6 edits)

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
``uv run python scripts/record_golden.py`` and review the diff.

```
with:
```python
``uv run python scripts/record_golden.py`` and review the diff.

``dividend-growth`` has a golden run of its own, over the same window with a two-year test, a
look-back holding UNVR's 2020 split, TLKM's look-back refused, and a review in January 2022.

```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    GOLDEN,
    HISTORY_START,
```
with:
```python
    GOLDEN,
    GROWTH_GOLDEN,
    HISTORY_START,
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    record_exempt,
    recorded,
    run,
    run_exempt,
    summary,
```
with:
```python
    record_exempt,
    record_growth,
    recorded,
    run,
    run_exempt,
    run_growth,
    summary,
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    DATA_BAR_REFUSED,
    EXEMPTION_CLAIM_BROKEN,
```
with:
```python
    DATA_BAR_REFUSED,
    DATA_DIVIDENDS_HISTORY_REFUSED,
    EXEMPTION_CLAIM_BROKEN,
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    STRATEGIES,
    Money,
```
with:
```python
    STRATEGIES,
    STRATEGY_TOO_FEW_QUALIFIED,
    Money,
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    assert taxed == {"2021-11-01": 22_450, "2022-04-01": 16_000}

```
with:
```python
    assert taxed == {"2021-11-01": 22_450, "2022-04-01": 16_000}


def test_the_dividend_growth_run_reproduces_its_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(GROWTH_GOLDEN.read_text(encoding="utf-8"))
    assert summary(run_growth(tmp_path)) == stored


def test_the_recorder_writes_the_dividend_growth_file_byte_for_byte(tmp_path: Path) -> None:
    written = record_growth(tmp_path / "cache", tmp_path / "growth.json")
    assert written.read_bytes() == GROWTH_GOLDEN.read_bytes()


def test_the_dividend_growth_run_reviews_as_worked_by_hand() -> None:
    stored = json.loads(GROWTH_GOLDEN.read_text(encoding="utf-8"))
    # 1 February 2021 tests the dividends of 2018 to 2020, a share in today's shares. BBCA's
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
        [
            "2022-01-03",
            STRATEGY_TOO_FEW_QUALIFIED,
            "Only 1 stock passed the dividend test; the rest is held as cash until more do.",
        ]
    ]
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
        "before the run"
    )

```

**`tests/perf/test_performance.py`** (changed: 4 edits)

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
"""A ten-year backtest over 45 stocks finishes in under 30 seconds (core spec §10.4, M3 §9).

The market is ``synthetic``'s, which also shows the engine running a market other than IDX.
The strategy rebalances to equal weights every day, so the strategy's run and the baseline's
both trade, value and size every day.
"""

import time
from datetime import timedelta

```
with:
```python
"""A ten-year backtest over 45 stocks finishes in under 30 seconds (core spec §10.4, M3 §9), and
a year of ``dividend-growth`` over them in under 3 (M6 spec §9.4).

The market is ``synthetic``'s, which also shows the engine running a market other than IDX.
The strategy rebalances to equal weights every day, so the strategy's run and the baseline's
both trade, value and size every day. The ``dividend-growth`` year took 0.37 to 0.40 s at a
load of 10 on four cores (0.67 to 0.74 s at 30); its budget leaves about eight times that for a
slower CI runner.
"""

import time
from datetime import date, timedelta

```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
    IDR,
    BacktestSettings,
```
with:
```python
    IDR,
    STRATEGIES,
    BacktestSettings,
```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
BUDGET_SECONDS = 30

```
with:
```python
BUDGET_SECONDS = 30
GROWTH_BUDGET_SECONDS = 3

```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"
```
with:
```python
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"


@pytest.mark.perf
def test_a_year_of_dividend_growth_over_45_stocks_runs_inside_its_budget() -> None:
    source = Synthetic()
    entry = STRATEGIES["dividend-growth"]
    # The default six years of look-back, from 1 January 2017: the synthetic data starts in 2016.
    settings = BacktestSettings(Money(1_000_000_000, IDR), lookback_years=entry.lookback_years())
    market = Market(All(source.stocks), source, PlainRules())
    began = time.perf_counter()
    result = backtest(entry(), market, date(2023, 1, 2), date(2023, 12, 29), settings)
    seconds = time.perf_counter() - began
    # It did the work it is timed on: more stocks passed than max_stocks, so the review picked
    # 25 by their pay months, reading six years of dividends for each of the 45.
    assert len(result.run.reports) == 260
    assert len(result.run.final.holdings.portfolio.positions) == 25
    assert seconds < GROWTH_BUDGET_SECONDS, f"took {seconds:.1f} s"
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/cli.py`** (changed, new names stubbed: 4 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
```
with:
```python
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    NoTradingDaysError,
    SnapshotVersionError,
    Strategy,
    UniverseCoverageError,
```
with:
```python
    NoTradingDaysError,
    Registered,
    SnapshotVersionError,
    UniverseCoverageError,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python

def _strategy(name: str, config: Config) -> Strategy:
    """The registered strategy *name*, made with the settings in the configuration."""
    if name not in STRATEGIES:
        raise UnknownNameError.among(name, STRATEGIES, kind="strategy")
    return STRATEGIES[name](config.strategy_settings)

```
with:
```python

def _entry(name: str) -> Registered:
    """The registry's entry for the strategy *name*."""
    raise NotImplementedError("_entry")

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    page.add(guide(name).rstrip("\n"))
    return render(page, ctx.training())
```
with:
```python
    page.add(guide(name).rstrip("\n"))
    return render(page, ctx.training())


def _strategy(name: str, config: Config) -> Strategy:
    """The registered strategy *name*, made with the settings in the configuration."""
    if name not in STRATEGIES:
        raise UnknownNameError.among(name, STRATEGIES, kind="strategy")
    return STRATEGIES[name](config.strategy_settings)
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    RISK_HALT_DRAWDOWN,
    TRADE_EXCLUDED,
```
with:
```python
    RISK_HALT_DRAWDOWN,
    STRATEGY_TOO_FEW_QUALIFIED,
    TRADE_EXCLUDED,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    Decision,
    InvalidWeightsError,
```
with:
```python
    Decision,
    DividendGrowthStrategy,
    InvalidWeightsError,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "STRATEGIES",
    "TERM_ANNUAL_RETURN",
```
with:
```python
    "STRATEGIES",
    "STRATEGY_TOO_FEW_QUALIFIED",
    "TERM_ANNUAL_RETURN",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "DividendGrowth",
    "DividendTotals",
```
with:
```python
    "DividendGrowth",
    "DividendGrowthStrategy",
    "DividendTotals",
```

**`packages/steadyhand/src/steadyhand/notes.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/notes.py -->
Replace:
```python

TRADE_EXCLUDED = "trade.excluded"
```
with:
```python

STRATEGY_TOO_FEW_QUALIFIED = "strategy.too_few_qualified"
"""``dividend-growth`` found fewer stocks passing its test than its ``min_stocks``, so the rest
of the portfolio is held as cash (M6 spec §6)."""

TRADE_EXCLUDED = "trade.excluded"
```

**`packages/steadyhand/src/steadyhand/strategies/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/__init__.py -->
Replace:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.monthly_savings import MonthlySavings
```
with:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.dividend_growth import DividendGrowthStrategy
from steadyhand.strategies.monthly_savings import MonthlySavings
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/__init__.py -->
Replace:
```python
    "Decision",
    "InvalidWeightsError",
```
with:
```python
    "Decision",
    "DividendGrowthStrategy",
    "InvalidWeightsError",
```

**`packages/steadyhand/src/steadyhand/strategies/_sets.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/_sets.py -->
```python
"""A set of stocks as a strategy remembers it: ``MARKET:SYMBOL`` entries separated by spaces,
in order, so the same set is always the same text."""

from __future__ import annotations

from collections.abc import Iterable

from steadyhand.money import Currency
from steadyhand.types import Instrument


def write_set(stocks: Iterable[Instrument]) -> str:
    raise NotImplementedError("write_set")


def read_set(text: str, currency: Currency) -> frozenset[Instrument]:
    raise NotImplementedError("read_set")
```

**`packages/steadyhand/src/steadyhand/strategies/dividend_growth.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/dividend_growth.py -->
```python
"""``dividend-growth``: the stocks that paid a dividend every year and grew it (M6 spec §6).

It reviews on the first day it decides in each calendar year, which is also a run's first day.
A stock passes in year Y when it is in the universe, its dividend history is complete, it paid a
cash dividend in every calendar year from Y - growth_years - 1 to Y - 1 (by ex-date, restated in
today's shares), and its total for Y - 1 is at least its total for Y - growth_years - 1. The
passers it can buy, and those it holds, are its candidates. Up to ``max_stocks`` are held, in
equal parts of 1 / max(``min_stocks``, number held); with more candidates than that it picks
them one at a time to spread the months they pay in, then by trailing yield, then by market and
symbol. Everything else is sold. Fewer than ``min_stocks`` leaves the rest in cash, with a note.
Between reviews it keeps its holdings and puts new cash into the stocks it picked, never above
the review's target.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_int
from steadyhand.notes import STRATEGY_TOO_FEW_QUALIFIED, Note
from steadyhand.strategies._sets import read_set, write_set
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

_SET_KEY = "set"
"""The memory key holding the stocks it picked, written as ``buy-and-hold`` writes its set."""

_YEAR_KEY = "year"
"""The memory key holding the calendar year it last reviewed."""

_TRAILING_DAYS = 365
"""The window of the trailing yield that breaks a tie: the dividends of the last 365 days."""


class DividendGrowthStrategy:
    """Hold the stocks whose dividends were paid every year and grew, spread across pay months."""

    def __init__(self, min_stocks: int, max_stocks: int, growth_years: int) -> None:
        raise NotImplementedError("DividendGrowthStrategy.__init__")

    @property
    def name(self) -> str:
        raise NotImplementedError("DividendGrowthStrategy.name")

    @property
    def min_stocks(self) -> int:
        """Below this many picked stocks, the rest of the money is held as cash."""
        raise NotImplementedError("DividendGrowthStrategy.min_stocks")

    @property
    def max_stocks(self) -> int:
        """The most stocks it holds."""
        raise NotImplementedError("DividendGrowthStrategy.max_stocks")

    @property
    def growth_years(self) -> int:
        """The years over which a stock's dividends must have grown."""
        raise NotImplementedError("DividendGrowthStrategy.growth_years")

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        raise NotImplementedError("DividendGrowthStrategy.decide")

    def passes(self, view: MarketView, stock: Instrument) -> bool:
        """Whether *stock* passes the dividend test in today's year (M6 spec §6)."""
        raise NotImplementedError("DividendGrowthStrategy.passes")

    def _review(self, view: MarketView, portfolio: PortfolioView) -> Decision:
        raise NotImplementedError("DividendGrowthStrategy._review")

    def _spread(self, view: MarketView, candidates: Sequence[Instrument]) -> list[Instrument]:
        """``max_stocks`` of *candidates*, picked one at a time: each time the one whose least
        crowded pay month has the fewest stocks already picked, then the higher trailing yield,
        then by market and symbol."""
        raise NotImplementedError("DividendGrowthStrategy._spread")

    def _between(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        raise NotImplementedError("DividendGrowthStrategy._between")


def _trailing_yield(view: MarketView, stock: Instrument) -> Decimal:
    """The stock's dividends of the last 365 days, restated in today's shares, over its last
    close."""
    raise NotImplementedError("_trailing_yield")


def _too_few(count: int) -> str:
    raise NotImplementedError("_too_few")
```

**`packages/steadyhand/src/steadyhand/strategies/registry.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.monthly_savings import MonthlySavings
```
with:
```python
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.dividend_growth import DividendGrowthStrategy
from steadyhand.strategies.monthly_savings import MonthlySavings
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
    return 0

```
with:
```python
    return 0


def _dividend_growth_lookback(values: Mapping[str, int]) -> int:
    """The years ``dividend-growth`` tests before a run's first year: ``growth_years`` + 1."""
    raise NotImplementedError("_dividend_growth_lookback")

```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
        ),
    }
```
with:
```python
        ),
        "dividend-growth": Registered(
            DividendGrowthStrategy,
            "Holds the stocks that paid a dividend in each of the last six years and grew it, "
            "spread across pay months, and reviews them yearly.",
            Turnover.LOW,
            (
                Setting(
                    "min_stocks",
                    15,
                    1,
                    45,
                    "Below this many passing stocks, dividend-growth holds the rest as cash: "
                    "1 to 45.",
                ),
                Setting(
                    "max_stocks",
                    25,
                    1,
                    45,
                    "The most stocks dividend-growth holds: 1 to 45, and at least min_stocks.",
                ),
                Setting(
                    "growth_years",
                    5,
                    1,
                    10,
                    "The years over which dividend-growth wants dividends to have grown: 1 to 10.",
                ),
            ),
            _dividend_growth_lookback,
        ),
    }
```

**`scripts/record_golden.py`** (changed, new names stubbed: 7 edits)

<!-- edit: scripts/record_golden.py -->
Replace:
```python

Run it only after a change that moves the numbers on purpose, and review the diff: the files are
```
with:
```python

Last it runs ``dividend-growth`` over the first run's window with ``VALUES``, a two-year test
whose three-year look-back (from 1 January 2018) fits in the recordings, and with TLKM's
look-back refused by script, and writes
``tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json``. The look-back holds UNVR's
2020 split, and the window crosses into 2022, where the strategy reviews again.

Run it only after a change that moves the numbers on purpose, and review the diff: the files are
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
from collections.abc import Callable
from datetime import date
```
with:
```python
from collections.abc import Callable
from dataclasses import replace
from datetime import date
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    BacktestSettings,
    Decision,
```
with:
```python
    BacktestSettings,
    DataUnavailableError,
    Decision,
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
RECORDED = date(2026, 9, 27)
```
with:
```python
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
GROWTH_GOLDEN = TESTS / "fixtures" / "golden" / "dividend-growth_2021-02-01_2022-01-31.json"
VALUES = {"instalments": 12, "min_stocks": 2, "max_stocks": 2, "growth_years": 2}
"""Every registered strategy's settings in the golden runs. ``dividend-growth`` tests two years
of growth, so its look-back of three years, from 1 January 2018, fits in the recordings."""
REFUSED_HISTORY = "TLKM.JK"
"""The stock whose look-back the ``dividend-growth`` golden run is refused."""
RECORDED = date(2026, 9, 27)
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    return history_from_json(FIXTURES / name)

```
with:
```python
    return history_from_json(FIXTURES / name)


def recorded_refusing_history(ticker: str, start: date, end: date) -> YahooHistory:
    """The recordings, except that TLKM's look-back is refused, as Yahoo refuses a stock it
    has nothing for: a range that ends before the run and starts after ``HISTORY_START``, where
    the income report's history starts."""
    raise NotImplementedError("recorded_refusing_history")

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    return _backtest(folder, STRATEGIES[strategy](), end, settings(income=income), recorded)

```
with:
```python
    return _backtest(folder, STRATEGIES[strategy](), end, settings(income=income), recorded)


def run_growth(folder: Path) -> BacktestResult:
    """Back-test ``dividend-growth`` over the first run's window, TLKM's look-back refused."""
    raise NotImplementedError("run_growth")

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python

def _write(pinned: dict[str, object], golden: Path) -> Path:
```
with:
```python

def record_growth(folder: Path, golden: Path = GROWTH_GOLDEN) -> Path:
    """Run the ``dividend-growth`` golden backtest with its cache in *folder*, and write its
    summary to *golden*."""
    raise NotImplementedError("record_growth")


def _write(pinned: dict[str, object], golden: Path) -> Path:
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1594 failed=58 -->
Expected: 1594 run, 58 failed. 42 are `NotImplementedError` from the stubs. The default is still `buy-and-hold` (`strategy_keys` keeps its old body), so the starter file, the consent-only file, the first user's journey and the file without a `name` beside a `buy-and-hold` account fail on it; three `Failed: DID NOT RAISE DataFileError` are the rule across `min_stocks` and `max_stocks`; three `FileNotFoundError`s are the guide and the golden file not yet written; the lesson and note-key guards name `strategy.too_few_qualified`, and the guide guard `dividend-growth`; the CLI journeys exit 1 on the stub. Six new or changed tests pass against the stubs by design: `test_the_dates_above_pay_where_the_tests_say` pins the calendar's pay dates; `test_monthly_savings_spreads_the_starting_cash_over_its_instalments` changed only its configuration's text; and `test_a_setting_name_may_belong_to_one_strategy_only`, `test_strategies_lists_each_name_turnover_and_summary` and two cases of `test_explain_prints_the_guide_then_the_footer` read the registry's data, which the stubs step writes.

- [ ] **Step 5: Implement.** The guide, the lesson and the golden file are part of this step.

**`packages/steadyhand-idx/src/steadyhand_idx/cli.py`** (implemented: 4 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    config = ctx.config()
    strategy = _strategy(ctx.args.strategy or config.strategy, config)
    start, end = _window(ctx)
    with ctx.world.source(config.data_dir) as source:
        result = backtest(strategy, _market(config, source), start, end, config.settings)
    written = backtest_files(result, config.data_dir / REPORTS)
```
with:
```python
    config = ctx.config()
    entry = _entry(ctx.args.strategy or config.strategy)
    start, end = _window(ctx)
    settings = replace(
        config.settings, lookback_years=entry.lookback_years(config.strategy_settings)
    )
    with ctx.world.source(config.data_dir) as source:
        result = backtest(
            entry(config.strategy_settings), _market(config, source), start, end, settings
        )
    written = backtest_files(result, config.data_dir / REPORTS)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
        raise UsageError(msg)
    strategies = [_strategy(name, config) for name in names]
    start, end = _window(ctx)
    with ctx.world.source(config.data_dir) as source:
        comparison = compare(strategies, _market(config, source), start, end, config.settings)
    written = comparison_files(comparison, config.data_dir / REPORTS)
```
with:
```python
        raise UsageError(msg)
    entries = [_entry(name) for name in names]
    start, end = _window(ctx)
    # One window for every strategy: the longest look-back among them (M6 spec §4.3).
    lookback = max(entry.lookback_years(config.strategy_settings) for entry in entries)
    strategies = [entry(config.strategy_settings) for entry in entries]
    settings = replace(config.settings, lookback_years=lookback)
    with ctx.world.source(config.data_dir) as source:
        comparison = compare(strategies, _market(config, source), start, end, settings)
    written = comparison_files(comparison, config.data_dir / REPORTS)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    """The registry's entry for the strategy *name*."""
    raise NotImplementedError("_entry")

```
with:
```python
    """The registry's entry for the strategy *name*."""
    if name not in STRATEGIES:
        raise UnknownNameError.among(name, STRATEGIES, kind="strategy")
    return STRATEGIES[name]

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    return render(page, ctx.training())


def _strategy(name: str, config: Config) -> Strategy:
    """The registered strategy *name*, made with the settings in the configuration."""
    if name not in STRATEGIES:
        raise UnknownNameError.among(name, STRATEGIES, kind="strategy")
    return STRATEGIES[name](config.strategy_settings)
```
with:
```python
    return render(page, ctx.training())
```

**`packages/steadyhand-idx/src/steadyhand_idx/config.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
    (M6 spec §4.5)."""
    keys = [Key("name", "buy-and-hold", "The strategy to run: see steadyhand-idx strategies.")]
    for entry in strategies.values():
```
with:
```python
    (M6 spec §4.5)."""
    keys = [Key("name", "dividend-growth", "The strategy to run: see steadyhand-idx strategies.")]
    for entry in strategies.values():
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
def _strategy_settings(row: Row, where: Where) -> dict[str, int]:
    """Every registered strategy's settings, each a whole number within its bounds."""
    values: dict[str, int] = {}
```
with:
```python
def _strategy_settings(row: Row, where: Where) -> dict[str, int]:
    """Every registered strategy's settings, each a whole number within its bounds, and each
    strategy made from them once, so a rule across its settings (``max_stocks`` at least
    ``min_stocks``) is checked too (M6 spec §4.5)."""
    values: dict[str, int] = {}
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
            values[setting.name] = value
    return values
```
with:
```python
            values[setting.name] = value
        try:
            entry(values)
        except ValueError as error:
            msg = f"{where}: {error}"
            raise DataFileError(msg) from None
    return values
```

**`packages/steadyhand-idx/src/steadyhand_idx/paper.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
        opened_on = target if account is None else account.opened_on
        inputs = {found.day: found for found in day_inputs(market, opened_on, target)}
        for day in days:
```
with:
```python
        opened_on = target if account is None else account.opened_on
        entry = STRATEGIES[config.strategy]
        lookback = entry.lookback_years(config.strategy_settings)
        inputs = {found.day: found for found in day_inputs(market, opened_on, target, lookback)}
        for day in days:
```

**`packages/steadyhand/src/steadyhand/strategies/_sets.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/_sets.py -->
```python
"""A set of stocks as a strategy remembers it: ``MARKET:SYMBOL`` entries separated by spaces,
in order, so the same set is always the same text."""

from __future__ import annotations

from collections.abc import Iterable

from steadyhand.money import Currency
from steadyhand.types import Instrument


def write_set(stocks: Iterable[Instrument]) -> str:
    return " ".join(sorted(f"{stock.market}:{stock.symbol}" for stock in stocks))


def read_set(text: str, currency: Currency) -> frozenset[Instrument]:
    entries = (entry.split(":") for entry in text.split())
    return frozenset(Instrument(symbol, market, currency) for market, symbol in entries)
```

**`packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py -->
Replace:
```python
from steadyhand._ratio import ratio_down
from steadyhand.money import Currency
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView
```
with:
```python
from steadyhand._ratio import ratio_down
from steadyhand.strategies._sets import read_set, write_set
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.view import MarketView, PortfolioView
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py -->
Replace:
```python
        currency = portfolio.value.currency
        chosen = _read(memory[_SET_KEY], currency) if _SET_KEY in memory else view.tradable.buyable
        weights = {instrument: portfolio.weight(instrument) for instrument in portfolio.holdings}
```
with:
```python
        currency = portfolio.value.currency
        chosen = (
            read_set(memory[_SET_KEY], currency) if _SET_KEY in memory else view.tradable.buyable
        )
        weights = {instrument: portfolio.weight(instrument) for instrument in portfolio.holdings}
```

<!-- edit: packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py -->
Replace:
```python
                weights[instrument] = weights.get(instrument, Decimal(0)) + each
        return Decision(weights, {_SET_KEY: _write(chosen)})


def _write(chosen: frozenset[Instrument]) -> str:
    return " ".join(sorted(f"{i.market}:{i.symbol}" for i in chosen))


def _read(text: str, currency: Currency) -> frozenset[Instrument]:
    stocks = (entry.split(":") for entry in text.split())
    return frozenset(Instrument(symbol, market, currency) for market, symbol in stocks)
```
with:
```python
                weights[instrument] = weights.get(instrument, Decimal(0)) + each
        return Decision(weights, {_SET_KEY: write_set(chosen)})
```

**`packages/steadyhand/src/steadyhand/strategies/dividend_growth.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/dividend_growth.py -->
```python
"""``dividend-growth``: the stocks that paid a dividend every year and grew it (M6 spec §6).

It reviews on the first day it decides in each calendar year, which is also a run's first day.
A stock passes in year Y when it is in the universe, its dividend history is complete, it paid a
cash dividend in every calendar year from Y - growth_years - 1 to Y - 1 (by ex-date, restated in
today's shares), and its total for Y - 1 is at least its total for Y - growth_years - 1. The
passers it can buy, and those it holds, are its candidates. Up to ``max_stocks`` are held, in
equal parts of 1 / max(``min_stocks``, number held); with more candidates than that it picks
them one at a time to spread the months they pay in, then by trailing yield, then by market and
symbol. Everything else is sold. Fewer than ``min_stocks`` leaves the rest in cash, with a note.
Between reviews it keeps its holdings and puts new cash into the stocks it picked, never above
the review's target.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_int
from steadyhand.notes import STRATEGY_TOO_FEW_QUALIFIED, Note
from steadyhand.strategies._sets import read_set, write_set
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

_SET_KEY = "set"
"""The memory key holding the stocks it picked, written as ``buy-and-hold`` writes its set."""

_YEAR_KEY = "year"
"""The memory key holding the calendar year it last reviewed."""

_TRAILING_DAYS = 365
"""The window of the trailing yield that breaks a tie: the dividends of the last 365 days."""


class DividendGrowthStrategy:
    """Hold the stocks whose dividends were paid every year and grew, spread across pay months."""

    def __init__(self, min_stocks: int, max_stocks: int, growth_years: int) -> None:
        require_int(min_stocks, "min_stocks", minimum=1)
        require_int(max_stocks, "max_stocks", minimum=1)
        require_int(growth_years, "growth_years", minimum=1)
        if max_stocks < min_stocks:
            msg = f"max_stocks must be at least min_stocks ({min_stocks}), got {max_stocks}"
            raise ValueError(msg)
        self._min = min_stocks
        self._max = max_stocks
        self._growth_years = growth_years

    @property
    def name(self) -> str:
        return "dividend-growth"

    @property
    def min_stocks(self) -> int:
        """Below this many picked stocks, the rest of the money is held as cash."""
        return self._min

    @property
    def max_stocks(self) -> int:
        """The most stocks it holds."""
        return self._max

    @property
    def growth_years(self) -> int:
        """The years over which a stock's dividends must have grown."""
        return self._growth_years

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        if memory.get(_YEAR_KEY) != str(view.today.year):
            return self._review(view, portfolio)
        return self._between(view, portfolio, memory)

    def passes(self, view: MarketView, stock: Instrument) -> bool:
        """Whether *stock* passes the dividend test in today's year (M6 spec §6)."""
        if stock not in view.tradable.members or not view.history_complete(stock):
            return False
        year = view.today.year
        first = year - self._growth_years - 1
        totals: defaultdict[int, Decimal] = defaultdict(Decimal)
        for dividend in view.dividends(stock):
            totals[dividend.ex_date.year] += dividend.per_share
        if any(totals[paid] == 0 for paid in range(first, year)):
            return False
        return totals[year - 1] >= totals[first]

    def _review(self, view: MarketView, portfolio: PortfolioView) -> Decision:
        reachable = view.tradable.buyable | frozenset(portfolio.holdings)
        candidates = [
            stock
            for stock in sorted(reachable, key=lambda i: (i.market, i.symbol))
            if self.passes(view, stock)
        ]
        picked = candidates if len(candidates) <= self._max else self._spread(view, candidates)
        target = ratio_down(1, max(self._min, len(picked)))
        notes: tuple[Note, ...] = ()
        if len(picked) < self._min:
            notes = (Note(STRATEGY_TOO_FEW_QUALIFIED, _too_few(len(picked))),)
        memory = {_SET_KEY: write_set(picked), _YEAR_KEY: str(view.today.year)}
        return Decision(dict.fromkeys(picked, target), memory, notes)

    def _spread(self, view: MarketView, candidates: Sequence[Instrument]) -> list[Instrument]:
        """``max_stocks`` of *candidates*, picked one at a time: each time the one whose least
        crowded pay month has the fewest stocks already picked, then the higher trailing yield,
        then by market and symbol."""
        last_year = view.today.year - 1
        months = {
            stock: frozenset(
                view.pay_date(dividend.ex_date).month
                for dividend in view.dividends(stock)
                if dividend.ex_date.year == last_year
            )
            for stock in candidates
        }
        yields = {stock: _trailing_yield(view, stock) for stock in candidates}
        crowding: defaultdict[int, int] = defaultdict(int)
        picked: list[Instrument] = []
        left = list(candidates)
        for _ in range(self._max):
            best = min(
                left,
                key=lambda stock: (
                    min(crowding[month] for month in months[stock]),
                    -yields[stock],
                    stock.market,
                    stock.symbol,
                ),
            )
            picked.append(best)
            left.remove(best)
            for month in months[best]:
                crowding[month] += 1
        return picked

    def _between(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        chosen = read_set(memory[_SET_KEY], portfolio.value.currency)
        target = ratio_down(1, max(self._min, len(chosen)))
        weights = {stock: portfolio.weight(stock) for stock in portfolio.holdings}
        buying = chosen & view.tradable.buyable
        if buying:
            each = ratio_down(portfolio.spendable.amount // len(buying), portfolio.value.amount)
            for stock in buying:
                held = weights.get(stock, Decimal(0))
                weights[stock] = held + min(each, max(target - held, Decimal(0)))
        return Decision(weights, dict(memory))


def _trailing_yield(view: MarketView, stock: Instrument) -> Decimal:
    """The stock's dividends of the last 365 days, restated in today's shares, over its last
    close."""
    since = view.today - timedelta(days=_TRAILING_DAYS)
    paid = sum(
        (dividend.per_share for dividend in view.dividends(stock) if dividend.ex_date > since),
        Decimal(0),
    )
    close = view.last_close(stock)
    return paid / close.amount if close is not None and close.amount else Decimal(0)


def _too_few(count: int) -> str:
    if count == 0:
        return "No stock passed the dividend test; everything is held as cash until one does."
    stocks = "stock" if count == 1 else "stocks"
    return (
        f"Only {count} {stocks} passed the dividend test; the rest is held as cash until more do."
    )
```

**`packages/steadyhand/src/steadyhand/strategies/guides/dividend-growth.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/strategies/guides/dividend-growth.md -->
```markdown
# dividend-growth

> steadyhand is example software that you run yourself, on your own account, and you make your
> own decisions with it. It is not financial advice. You can lose money.

## What it does

It holds stocks from the universe (by default the LQ45, IDX's list of 45 large, easily traded
stocks) that have paid a dividend (a share of a company's profit paid to its shareholders) every
year, and paid at least as much last year as five years before.

Once a year, on the first day it runs in each calendar year and on its very first day, it
reviews its stocks. A stock passes when it paid a cash dividend in each of the last six calendar
years, each counted in the year of its ex-date (the first day the shares trade without that
dividend), and when its dividends last year added up to at least what they added up to five
years earlier. Amounts are compared per share, restated for any split in between, so a split
does not look like a cut.

It holds every stock that passes, up to 25 of them, in equal parts of the portfolio: one part
for each stock it holds, but never more than a fifteenth each. With more than 25 passing, it
picks them one at a time so that the months their dividends arrive in are spread across the
year: each time it takes the stock whose quietest pay month has the fewest stocks already picked,
then the one paying the most over the last year for its price. It sells what no longer passes.
Fewer than 15 passing means the rest of the portfolio waits as cash, and the report says how
many passed.

Between reviews it keeps what it holds and puts new cash, from dividends and monthly top-ups,
into the stocks it picked, never taking one above its share.

## Why people use it

A company that has paid a dividend every year, and pays more than it used to, has usually been
earning steadily. Owning several of them, paying in different months, gives an income that
arrives through the year and has tended to grow, which is what the income goal measures.

## When it tends to do badly

The test compares the totals of only two years, the last one and the one five years before it,
and asks of the years between only that each paid something. So it lets in companies whose
dividends swing with their profits, such as coal and metal miners, as long as last year was a
good one; those dividends can fall sharply the next year. A year in which many companies cut
their dividends can leave most of the portfolio in cash until the next review finds enough
stocks passing again, and cash earns nothing in steadyhand's model. Choosing by past dividends also misses companies that are only starting to
pay.

## Risks

- **You can lose money.** Share prices can fall a long way and stay down for years, whatever a
  company has paid before, and a dividend can be cut or stopped.
- **Fee drag:** every purchase and sale pays a broker commission, the exchange levy and, on some
  days, stamp duty, and a sale also pays tax. The yearly review sells stocks that no longer pass,
  so each review costs more than a year of buy-and-hold does.
- **The pay months are modelled.** The data source gives each dividend's ex-date, not the day
  it was paid, so steadyhand assumes each dividend is paid a set number of trading days after
  its ex-date (the pay lag, 14 by default). Real payments can come earlier or later.
- **Old data may not compare.** When a company changes its shares in a way the data source does
  not report as a split, such as a rights issue, its earlier dividends may be scaled, so a year
  before the change may not compare fairly with a year after it. A stock whose history the data
  source refuses does not pass, and the backtest warns about it.
- Every stock is bought in whole lots of 100 shares, so some cash can stay uninvested.

## How often it trades

Once a year it sells what no longer passes and evens out what it holds. In between it only buys,
when a dividend or a top-up arrives.

## Settings you can change

- `min_stocks`: below this many passing stocks, it holds the rest of the portfolio as cash
  instead of putting more into fewer stocks. From 1 to 45; the default is 15.
- `max_stocks`: the most stocks it holds. From 1 to 45, and at least `min_stocks`; the default is
  25.
- `growth_years`: how many years back the dividend test compares last year with. From 1 to 10;
  the default is 5, which asks for a dividend in each of the last six years. A longer test needs a
  longer history, which the data source must have.
- `monthly_contribution`: cash added on the first trading day of each month, which goes into the
  stocks it picked. The default is 0.
- The risk limits: the most any one stock may be of the portfolio (10% by default), which caps
  each purchase, and the daily loss and drawdown limits that stop all trading when they are
  reached.
```

**`packages/steadyhand/src/steadyhand/strategies/registry.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/strategies/registry.py -->
Replace:
```python
    """The years ``dividend-growth`` tests before a run's first year: ``growth_years`` + 1."""
    raise NotImplementedError("_dividend_growth_lookback")

```
with:
```python
    """The years ``dividend-growth`` tests before a run's first year: ``growth_years`` + 1."""
    return values["growth_years"] + 1

```

**`packages/steadyhand/src/steadyhand/training/lessons/en/strategies.holding_cash.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/strategies.holding_cash.md -->
```markdown
+++
id = "strategies.holding_cash"
title = "When a strategy holds cash"
summary = "Why dividend-growth keeps part of the portfolio in cash when too few stocks pass its test, and what that costs."
explains = ["strategy.too_few_qualified"]
see_also = ["dividends.basics", "risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

`dividend-growth` holds only stocks that passed its dividend test at its last yearly review, and
it gives each an equal share of the portfolio, never more than one part in `min_stocks` (15 by
default). When fewer stocks pass than that, it does not spread the money over the few it has:
the shares they would have taken stay in cash, and the report says how many stocks passed.

This keeps the portfolio from resting on a handful of companies, which is a risk of its own. The
cost is that cash earns nothing in steadyhand's model, so a year with many dividend cuts can
leave the portfolio holding a lot of it until the next review finds enough stocks passing again.
Lowering `min_stocks` puts more of the money to work in fewer stocks. Which way is better is a
choice about risk, and a backtest over past years only shows what it would have done then.
```

**`scripts/record_golden.py`** (implemented: 6 edits)

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    the income report's history starts."""
    raise NotImplementedError("recorded_refusing_history")

```
with:
```python
    the income report's history starts."""
    if ticker == REFUSED_HISTORY and start > HISTORY_START and end < START:
        msg = f"{ticker}: refused by the golden test's script"
        raise DataUnavailableError(msg)
    return recorded(ticker, start, end)

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
def run(
    folder: Path, strategy: str = "buy-and-hold", end: date = END, *, income: bool = True
) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules.

```
with:
```python
def run(
    folder: Path,
    strategy: str = "buy-and-hold",
    end: date = END,
    *,
    income: bool = True,
    download: Callable[[str, date, date], YahooHistory] = recorded,
) -> BacktestResult:
    """Back-test *strategy*, made from ``VALUES`` with its look-back, from ``START`` to *end*
    through the real source, cache and rules.

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    """
    return _backtest(folder, STRATEGIES[strategy](), end, settings(income=income), recorded)

```
with:
```python
    """
    entry = STRATEGIES[strategy]
    chosen = replace(settings(income=income), lookback_years=entry.lookback_years(VALUES))
    return _backtest(folder, entry(VALUES), end, chosen, download)

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    """Back-test ``dividend-growth`` over the first run's window, TLKM's look-back refused."""
    raise NotImplementedError("run_growth")

```
with:
```python
    """Back-test ``dividend-growth`` over the first run's window, TLKM's look-back refused."""
    return run(folder, "dividend-growth", download=recorded_refusing_history)

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    summary to *golden*."""
    raise NotImplementedError("record_growth")

```
with:
```python
    summary to *golden*."""
    return _write(summary(run_growth(folder)), golden)

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
        print(record_exempt(Path(scratch) / "exemption"))
    return 0
```
with:
```python
        print(record_exempt(Path(scratch) / "exemption"))
        print(record_growth(Path(scratch) / "dividend-growth"))
    return 0
```

Generate `tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/dividend-growth_2021-02-01_2022-01-31.json sha256=e91a14ab1f06d681abdab339d7f938559c78ac61e3dd9ae96327d68203e0fcd2 -->
```bash
uv run python scripts/record_golden.py
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1594 passed=1594 -->
Expected: every command exits 0; 1594 passed, 100% branch coverage; the performance step passes its nine tests: Task 1's eight and the `dividend-growth` year. CI's second job runs the same 1594 tests on Python 3.13 under `-W error`.

- [ ] **Step 7: Mutations.** Run M345–M369 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M6 S4 dividend-growth, the new default, and its golden run`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 5: M6 S5 Course module 8

**Acceptance criteria (story text):**
1. Module 8 (`strategies`) holds `strategies.buy_and_hold`, `strategies.monthly_savings` and `strategies.dividend_growth`, one per registered strategy, each citing its guide and pointing at it rather than copying it, then `strategies.holding_cash` (scope decision 15). The lessons are in the engine's wheel and market-neutral, and no lesson carries advice phrasing.
2. Every module of the course has lessons; the guard that pinned module 8 empty now pins its four lessons in order.
3. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M370–M372 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand/training/lessons/en/strategies.{buy_and_hold,monthly_savings,dividend_growth}.md`
- Modify: `.../steadyhand/training/lessons/en/strategies.holding_cash.md`
- Test: `tests/meta/test_lessons.py`

**Interfaces:**
- Consumes: Task 4's `strategies.holding_cash` and the three guides; the course's module 8.
- Produces: the three lessons; `strategies.holding_cash` placed at position 4.

- [ ] **Step 1: Branch.** `git switch -c m6/s5-module-8 origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/meta/test_lessons.py`** (changed: 2 edits)

<!-- edit: tests/meta/test_lessons.py -->
Replace:
```python

from steadyhand import DISCLAIMER
from steadyhand.training import Catalogue, Level, explain
```
with:
```python

from steadyhand import DISCLAIMER, STRATEGIES
from steadyhand.training import Catalogue, Level, explain
```

<!-- edit: tests/meta/test_lessons.py -->
Replace:
```python

def test_the_modules_written_in_t1_have_lessons(real: Catalogue) -> None:
    counts = {module.slug: len(module.lessons) for module in real.course()}
    written = [slug for slug in counts if slug != "strategies"]
    assert len(written) == 7
    assert [slug for slug in written if counts[slug] == 0] == []
    assert counts["strategies"] == 0

```
with:
```python

def test_every_module_has_lessons(real: Catalogue) -> None:
    counts = {module.slug: len(module.lessons) for module in real.course()}
    assert len(counts) == 8
    assert [slug for slug, count in counts.items() if count == 0] == []


def test_module_8_has_a_lesson_for_each_strategy_citing_its_guide(real: Catalogue) -> None:
    """One lesson per registered strategy, pointing at its guide rather than copying it (M6
    spec §7), then the lesson on the cash dividend-growth holds."""
    (strategies,) = [module for module in real.course() if module.slug == "strategies"]
    lessons = {lesson.id: lesson for lesson in strategies.lessons}
    expected = [f"strategies.{name.replace('-', '_')}" for name in STRATEGIES]
    assert len(expected) == 3
    assert list(lessons) == [*expected, "strategies.holding_cash"]
    for name, lesson_id in zip(STRATEGIES, expected, strict=True):
        guide = f"packages/steadyhand/src/steadyhand/strategies/guides/{name}.md"
        assert guide in lessons[lesson_id].sources, lesson_id
        words = " ".join(lessons[lesson_id].body.split())
        assert "Its guide, which the explain command prints" in words, lesson_id

```


- [ ] **Step 3: Run the whole suite and watch it fail.** This story adds no Python name, so there are no stubs. `uv run pytest -p no:cacheprovider --continue-on-collection-errors > red.txt 2>&1; rc=$?`

<!-- check: red total=1595 failed=2 -->
Expected: 1595 run, 2 failed, both `AssertionError`: `test_every_module_has_lessons` names `strategies`, and `test_module_8_has_a_lesson_for_each_strategy_citing_its_guide` finds none of the four lessons in the module.

- [ ] **Step 4: Write the lessons.**

**`packages/steadyhand/src/steadyhand/training/lessons/en/strategies.buy_and_hold.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/strategies.buy_and_hold.md -->
```markdown
+++
id = "strategies.buy_and_hold"
title = "buy-and-hold, the yardstick"
summary = "The simplest strategy, and the one every backtest is measured against: buy once, in equal parts, then hold."
explains = []
module = "strategies"
position = 1
see_also = ["backtest.basics", "strategies.monthly_savings", "strategies.dividend_growth"]
sources = ["packages/steadyhand/src/steadyhand/strategies/guides/buy-and-hold.md", "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

`buy-and-hold` spends its starting cash on its first day, in equal parts, on every stock it can
buy. After that it never sells: dividends and new cash buy more of the same stocks.

Every backtest runs it beside the strategy you chose, over the same days and with the same
costs. A strategy that trades more has to do better than this to be worth its extra costs and
its extra decisions, and often does not. Its guide, which the explain command prints, gives the
whole rule, its settings and its risks.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/strategies.dividend_growth.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/strategies.dividend_growth.md -->
```markdown
+++
id = "strategies.dividend_growth"
title = "dividend-growth, a test of past dividends"
summary = "How dividend-growth chooses stocks by the dividends they paid, and why a good record is not a promise."
explains = []
module = "strategies"
position = 3
see_also = ["dividends.basics", "strategies.holding_cash", "backtest.data_gaps"]
sources = ["packages/steadyhand/src/steadyhand/strategies/guides/dividend-growth.md", "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

Once a year, `dividend-growth` keeps the stocks that paid a dividend in every one of the last
six years and paid at least as much last year as five years before, with the amounts restated
for any split. It holds them in equal parts, spread so that their dividends arrive in different
months, and sells what no longer passes.

A long record of paying and raising dividends says something about a company's past, and
nothing certain about its future: a dividend can be cut in any year, and a company whose
dividends swing with its business can still pass. The test also needs years of history, so a
stock whose history the data source could not give is left out. Its guide, which the explain
command prints, gives the whole rule, its settings and the ways it tends to do badly.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/strategies.holding_cash.md`** (changed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/strategies.holding_cash.md -->
Replace:
```markdown
explains = ["strategy.too_few_qualified"]
see_also = ["dividends.basics", "risk.backtests_mislead"]
```
with:
```markdown
explains = ["strategy.too_few_qualified"]
module = "strategies"
position = 4
see_also = ["dividends.basics", "risk.backtests_mislead"]
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/strategies.monthly_savings.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/strategies.monthly_savings.md -->
```markdown
+++
id = "strategies.monthly_savings"
title = "monthly-savings, investing in instalments"
summary = "Why a strategy might invest its starting cash a little each month instead of all at once, and what waiting costs."
explains = []
module = "strategies"
position = 2
see_also = ["strategies.buy_and_hold", "risk.backtests_mislead"]
sources = ["packages/steadyhand/src/steadyhand/strategies/guides/monthly-savings.md", "docs/superpowers/specs/2026-09-30-m6-strategy-wave-1-design.md"]
+++

`monthly-savings` splits its starting cash into equal monthly instalments (12 by default) and
invests one each month across every stock it can buy. It never sells.

Spreading the buying out means no single day's prices decide the whole portfolio. The cost is
that money waiting for its month earns nothing in the model, and in a market that mostly rises,
investing later tends to trail investing everything at once. Neither is a mistake; they are
different answers to how much a bad first day should matter to you. Its guide, which the explain
command prints, gives the whole rule and when a change to its instalments takes effect.
```


- [ ] **Step 5: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1595 passed=1595 -->
Expected: every command exits 0; 1595 passed, 100% branch coverage; the performance step passes its nine tests, as Task 4's. CI's second job runs the same 1595 tests on Python 3.13 under `-W error`.

- [ ] **Step 6: Mutations.** Run M370–M372 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 7: Commit, push and merge** (`feat(training): M6 S5 course module 8, a lesson for each strategy`, ending in the story's issue number as `(#N)`), as **Merging a story** says. Then move #146 to Done, and write the handover.

---

## Mutation checks

Each mutation plants one realistic defect in the story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed lines are printed before the run. The predicted catchers were written before any mutation ran; six were corrected after the first run, each with its reason in the plan review log (pass 1, finding 3). "More than predicted" lists every other test that went red.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M296 | 1 | `view.py` | A dividend on today is left out | 1486 | `test_a_dividend_is_restated_by_each_split_from_its_own_ex_date_to_today` (2 failing) | `test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits` |
| M297 | 1 | `view.py` | A split after today restates the dividends | 1486 | `test_a_dividend_is_restated_by_each_split_from_its_own_ex_date_to_today`, `test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits` (2 failing) | none |
| M298 | 1 | `view.py` | A split on a dividend's own ex-date does not restate it | 1486 | `test_a_dividend_is_restated_by_each_split_from_its_own_ex_date_to_today` (2 failing) | `test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits` |
| M299 | 1 | `view.py` | A restatement divides before it multiplies | 1486 | `test_a_restatement_divides_once` (2 failing) | `test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits` |
| M300 | 1 | `view.py` | Any object passes as an action, and a real other action is refused | 1486 | `test_the_action_history_refuses_what_is_not_an_action_or_a_stock`, `test_the_view_shows_dividends_up_to_today_restated_in_todays_shares` (2 failing) | none |
| M301 | 1 | `view.py` | Every history reads complete | 1486 | `test_a_look_back_the_source_has_nothing_for_is_refused_history_too`, `test_a_refused_look_back_warns_once_and_the_run_goes_on_without_that_history`, `test_a_stock_whose_look_back_was_refused_has_incomplete_history`, `test_the_strategy_sees_the_days_members_the_past_dividends_and_the_engines_pay_date` (4 failing) | none |
| M302 | 1 | `view.py` | A buyable stock outside the universe is accepted | 1486 | `test_every_buyable_stock_is_a_member_and_a_member_may_be_kept_out` (1 failing) | none |
| M303 | 1 | `view.py` | A pay date is given for an ex-date after today | 1486 | `test_the_pay_date_is_the_engines_and_a_later_ex_date_is_look_ahead` (1 failing) | none |
| M304 | 1 | `market.py` | The pay date is one trading day late | 1486 | `test_the_pay_date_is_the_engines_and_a_later_ex_date_is_look_ahead`, `test_the_strategy_sees_the_days_members_the_past_dividends_and_the_engines_pay_date` (2 failing) | none |
| M305 | 1 | `engine.py` | The strategy's notes come before the engine's | 1486 | `test_a_strategys_notes_follow_the_engines_own_in_the_days_report` (1 failing) | none |
| M306 | 1 | `engine.py` | The strategy's notes are dropped | 1486 | `test_a_strategys_notes_follow_the_engines_own_in_the_days_report` (1 failing) | none |
| M307 | 1 | `engine.py` | The universe is only what can be bought today | 1486 | `test_the_strategy_sees_the_days_members_the_past_dividends_and_the_engines_pay_date` (1 failing) | none |
| M308 | 1 | `engine.py` | The strategy sees no dividend history | 1486 | `test_a_look_back_fetches_actions_from_1_january_and_bars_from_the_first_day`, `test_a_look_back_the_source_has_nothing_for_is_refused_history_too`, `test_a_refused_look_back_warns_once_and_the_run_goes_on_without_that_history`, `test_the_strategy_sees_the_days_members_the_past_dividends_and_the_engines_pay_date` (4 failing) | none |
| M309 | 1 | `backtest.py` | The look-back starts on 2 January | 1486 | `test_a_look_back_fetches_actions_from_1_january_and_bars_from_the_first_day`, `test_a_look_back_the_source_has_nothing_for_is_refused_history_too`, `test_a_refusal_in_the_runs_own_days_keeps_its_rules_beside_a_look_back`, `test_a_refused_look_back_warns_once_and_the_run_goes_on_without_that_history`, `test_compare_fetches_the_look_back_once_for_every_strategy` (5 failing) | none |
| M310 | 1 | `backtest.py` | A look-back the source has nothing for stops the run | 1486 | `test_a_look_back_the_source_has_nothing_for_is_refused_history_too` (1 failing) | none |
| M311 | 1 | `backtest.py` | A refused look-back gives no warning | 1486 | `test_a_look_back_the_source_has_nothing_for_is_refused_history_too`, `test_a_refused_look_back_warns_once_and_the_run_goes_on_without_that_history` (2 failing) | none |
| M312 | 1 | `backtest.py` | A backtest fetches no look-back | 1486 | `test_a_look_back_fetches_actions_from_1_january_and_bars_from_the_first_day`, `test_a_look_back_the_source_has_nothing_for_is_refused_history_too`, `test_a_refusal_in_the_runs_own_days_keeps_its_rules_beside_a_look_back`, `test_a_refused_look_back_warns_once_and_the_run_goes_on_without_that_history`, `test_compare_fetches_the_look_back_once_for_every_strategy` (5 failing) | none |
| M313 | 1 | `backtest.py` | The public fetch gives no look-back | 1486 | `test_day_inputs_give_every_day_the_look_back` (1 failing) | none |
| M314 | 1 | `registry.py` | A setting's value is taken unchecked | 1486 | `test_an_entry_refuses_a_missing_or_bad_value` (1 failing) | none |
| M315 | 1 | `registry.py` | A boolean passes as a setting's whole number | 1486 | `test_a_setting_takes_a_whole_number_within_its_bounds` (1 failing) | none |
| M316 | 1 | `registry.py` | A default above the maximum is accepted | 1486 | `test_a_setting_refuses_a_bad_name_bound_default_or_help` (1 failing) | none |
| M317 | 1 | `registry.py` | The look-back ignores the values given | 1486 | `test_an_entry_refuses_a_missing_or_bad_value`, `test_the_look_back_reads_the_same_values` (2 failing) | none |
| M318 | 1 | `protocol.py` | A list passes as a decision's notes | 1486 | `test_a_decision_carries_notes_and_checks_each_is_a_note` (1 failing) | none |
| M319 | 2 | `yahoo.py` | A dividend is not restated through later splits | 1500 | `test_a_look_back_is_fetched_once_without_its_prices`, `test_actions_are_read_where_the_prices_cannot_be_recovered`, `test_actions_need_no_calendar` (23 failing) | 20 more tests, including `test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected`, `test_a_holding_whose_old_prices_cannot_be_recovered_keeps_its_dividend_history`, `test_a_strategy_is_shown_beside_the_baseline` |
| M320 | 2 | `yahoo.py` | Actions are read through the price checks | 1500 | `test_a_holding_whose_old_prices_cannot_be_recovered_keeps_its_dividend_history`, `test_a_look_back_before_the_calendar_is_asked_for_whole`, `test_a_look_back_is_fetched_once_without_its_prices`, `test_the_source_reads_a_ranges_actions_without_its_prices` (4 failing) | none |
| M321 | 2 | `rules.py` | Trading days before the rules' first day are refused | 1500 | `test_a_year_window_before_the_holiday_data_is_refused_not_guessed`, `test_trading_days_answer_for_every_year_of_holiday_data_before_the_rules_are_verified` (3 failing) | `test_an_ex_date_the_rules_cannot_place_raises_their_own_error` |
| M322 | 2 | `cache.py` | A range stored for its actions is not recorded | 1500 | `test_a_cache_from_before_m6_is_upgraded_and_keeps_its_ranges`, `test_a_look_back_before_the_calendar_is_asked_for_whole`, `test_a_look_back_is_fetched_once_without_its_prices`, `test_actions_stored_alone_are_all_or_nothing_and_stay_in_their_range`, `test_actions_stored_alone_leave_their_bars_missing`, `test_missing_actions_skips_ranges_stored_either_way` (6 failing) | none |
| M323 | 2 | `cache.py` | Touching ranges are not merged | 1500 | `test_a_cache_from_before_m6_is_upgraded_and_keeps_its_ranges` (2 failing) | `test_fetched_ranges_merge_where_they_touch` |
| M324 | 2 | `cache.py` | A gap before the calendar is dropped | 1500 | `test_a_look_back_before_the_calendar_is_asked_for_whole`, `test_missing_actions_skips_ranges_stored_either_way` (2 failing) | none |
| M325 | 2 | `cache.py` | Actions are fetched wherever bars are missing | 1500 | `test_a_look_back_is_fetched_once_without_its_prices` (2 failing) | `test_a_look_back_before_the_calendar_is_asked_for_whole` |
| M326 | 2 | `cache.py` | Actions fetched alone are not stored | 1500 | `test_a_look_back_before_the_calendar_is_asked_for_whole`, `test_a_look_back_is_fetched_once_without_its_prices` (8 failing) | `test_a_holding_whose_old_prices_cannot_be_recovered_keeps_its_dividend_history`, `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_income_report_is_the_backtests_over_the_same_days`, `test_the_recorder_writes_the_stored_file_byte_for_byte`, `test_the_recorder_writes_the_switch_on_file_byte_for_byte`, `test_the_switch_on_run_reproduces_its_stored_results_exactly` |
| M327 | 2 | `cache.py` | Actions outside their range are stored | 1500 | `test_actions_stored_alone_are_all_or_nothing_and_stay_in_their_range` (1 failing) | none |
| M328 | 2 | `backtest.py` | A refused day's dividend never reaches the history | 1500 | `test_a_dividend_on_a_refused_day_reaches_the_history_when_read_without_prices` (2 failing) | none |
| M329 | 2 | `backtest.py` | A refused whole-run read leaves the history complete | 1500 | `test_a_source_that_refuses_the_actions_too_leaves_that_history_incomplete` (2 failing) | none |
| M330 | 2 | `backtest.py` | Stocks with unknown days are not marked incomplete | 1500 | `test_a_source_that_refuses_the_actions_too_leaves_that_history_incomplete` (2 failing) | none |
| M331 | 2 | `backtest.py` | A whole-run read refused with a plain DataUnavailableError stops the run | 1500 | `test_a_source_that_refuses_the_actions_too_leaves_that_history_incomplete` (1 failing) | none |
| M332 | 3 | `monthly_savings.py` | The current instalment is kept back as reserve | 1529 | `test_its_first_day_fixes_the_instalment_and_buys_one_split_equally`, `test_monthly_savings_spreads_the_starting_cash_over_its_instalments`, `test_one_instalment_is_a_lump_sum_then_monthly_reinvestment`, `test_the_last_instalment_spends_everything_and_so_does_every_month_after`, `test_the_next_month_buys_its_instalment_with_the_cash_that_arrived_since` (9 failing) | `test_a_first_day_on_a_portfolio_that_holds_stocks_sizes_the_instalment_from_cash`, `test_a_month_with_nothing_buyable_waits_for_a_day_that_has_something`, `test_it_never_sells_and_keeps_a_stock_that_left_the_universe`, `test_the_instalment_is_whole_and_rounded_down` |
| M333 | 3 | `monthly_savings.py` | It buys on every day of a month | 1529 | `test_later_days_in_the_month_keep_every_holding_and_buy_nothing`, `test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month` (3 failing) | `test_monthly_savings_spreads_the_starting_cash_over_its_instalments` |
| M334 | 3 | `monthly_savings.py` | The instalments due never go down | 1529 | `test_its_first_day_fixes_the_instalment_and_buys_one_split_equally`, `test_the_last_instalment_spends_everything_and_so_does_every_month_after`, `test_the_next_month_buys_its_instalment_with_the_cash_that_arrived_since` (9 failing) | `test_a_first_day_on_a_portfolio_that_holds_stocks_sizes_the_instalment_from_cash`, `test_a_month_with_nothing_buyable_waits_for_a_day_that_has_something`, `test_a_strategy_switched_to_records_its_settings_the_first_day_it_runs`, `test_monthly_savings_spreads_the_starting_cash_over_its_instalments`, `test_one_instalment_is_a_lump_sum_then_monthly_reinvestment`, `test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month` |
| M335 | 3 | `monthly_savings.py` | Its holdings are dropped, so sold | 1529 | `test_it_never_sells_and_keeps_a_stock_that_left_the_universe`, `test_later_days_in_the_month_keep_every_holding_and_buy_nothing` (6 failing) | `test_a_first_day_on_a_portfolio_that_holds_stocks_sizes_the_instalment_from_cash`, `test_monthly_savings_spreads_the_starting_cash_over_its_instalments`, `test_the_next_month_buys_its_instalment_with_the_cash_that_arrived_since`, `test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month` |
| M336 | 3 | `config.py` | A setting one above its maximum is accepted | 1529 | `test_each_bad_value_is_refused_naming_its_table_and_key` (1 failing) | none |
| M337 | 3 | `config.py` | A setting below its minimum is accepted | 1529 | `test_each_bad_value_is_refused_naming_its_table_and_key` (3 failing) | none |
| M338 | 3 | `config.py` | Two strategies may share a setting's key | 1529 | `test_a_setting_name_may_belong_to_one_strategy_only` (1 failing) | none |
| M339 | 3 | `config.py` | A setting's key defaults to its minimum | 1529 | `test_a_file_with_only_the_consent_takes_every_default`, `test_the_starter_file_writes_every_key_under_its_comment` (2 failing) | none |
| M340 | 3 | `paper.py` | The running strategy's settings are not recorded | 1529 | `test_a_changed_strategy_setting_is_recorded_and_its_guide_says_when_it_applies`, `test_the_settings_of_the_strategy_that_runs_are_recorded_with_the_engines` (3 failing) | `test_a_strategy_switched_to_records_its_settings_the_first_day_it_runs` |
| M341 | 3 | `paper.py` | A setting seen for the first time reads as changed from None | 1529 | `test_a_strategy_switched_to_records_its_settings_the_first_day_it_runs` (1 failing) | none |
| M342 | 3 | `paper.py` | A strategy setting's change says it applies from the next day | 1529 | `test_a_changed_strategy_setting_is_recorded_and_its_guide_says_when_it_applies` (1 failing) | none |
| M343 | 3 | `paper.py` | Paper runs the strategy with its default settings | 1529 | `test_a_changed_strategy_setting_is_recorded_and_its_guide_says_when_it_applies` (2 failing) | `test_a_strategy_switched_to_records_its_settings_the_first_day_it_runs` |
| M344 | 3 | `cli.py` | backtest and compare run the strategy with its default settings | 1529 | `test_monthly_savings_spreads_the_starting_cash_over_its_instalments` (1 failing) | none |
| M345 | 4 | `dividend_growth.py` | A stock outside the universe passes | 1594 | `test_a_review_sells_what_failed_or_left_and_keeps_a_suspended_passer`, `test_a_stock_with_an_incomplete_history_or_outside_the_universe_fails` (2 failing) | none |
| M346 | 4 | `dividend_growth.py` | A stock with incomplete history passes | 1594 | `test_a_stock_with_an_incomplete_history_or_outside_the_universe_fails` (1 failing) | none |
| M347 | 4 | `dividend_growth.py` | The test reads one year too few | 1594 | `test_growth_years_sets_how_many_years_must_have_paid`, `test_the_dividend_test_at_its_boundaries` (5 failing) | `test_dividend_growth_reviews_again_on_the_first_trading_day_of_2022`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_recorder_writes_the_dividend_growth_file_byte_for_byte` |
| M348 | 4 | `dividend_growth.py` | A total equal to the first year's fails | 1594 | `test_exactly_min_stocks_passing_holds_them_in_equal_parts_with_no_note`, `test_the_dividend_test_at_its_boundaries`, `test_with_at_most_max_stocks_passing_it_holds_them_all_in_equal_parts` (17 failing) | 10 more tests, including `test_a_review_sells_what_failed_or_left_and_keeps_a_suspended_passer`, `test_a_stock_paying_in_two_months_is_as_crowded_as_its_least_crowded_month`, `test_a_stock_with_an_incomplete_history_or_outside_the_universe_fails` |
| M349 | 4 | `dividend_growth.py` | A suspended holding that passes is sold | 1594 | `test_a_review_sells_what_failed_or_left_and_keeps_a_suspended_passer` (1 failing) | none |
| M350 | 4 | `dividend_growth.py` | Fewer than min_stocks are bought at full weight | 1594 | `test_fewer_than_min_stocks_passing_leaves_the_rest_in_cash_and_says_so` (2 failing) | none |
| M351 | 4 | `dividend_growth.py` | The too-few note is not written | 1594 | `test_fewer_than_min_stocks_passing_leaves_the_rest_in_cash_and_says_so`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_recorder_writes_the_dividend_growth_file_byte_for_byte` (6 failing) | `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used` |
| M352 | 4 | `dividend_growth.py` | Exactly min_stocks gives the too-few note | 1594 | `test_exactly_min_stocks_passing_holds_them_in_equal_parts_with_no_note` (3 failing) | `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_recorder_writes_the_dividend_growth_file_byte_for_byte` |
| M353 | 4 | `dividend_growth.py` | A stock counts its most crowded pay month | 1594 | `test_a_stock_paying_in_two_months_is_as_crowded_as_its_least_crowded_month` (1 failing) | none |
| M354 | 4 | `dividend_growth.py` | Among equally spread candidates, the lower yield is picked first | 1594 | `test_the_pay_months_are_last_years_modelled_pay_dates`, `test_the_trailing_yield_is_the_last_365_days_of_dividends_over_the_last_close`, `test_with_more_passers_than_max_stocks_it_spreads_pay_months_before_yield` (3 failing) | none |
| M355 | 4 | `dividend_growth.py` | Pay months count every year's dividends | 1594 | `test_the_pay_months_are_last_years_modelled_pay_dates` (1 failing) | none |
| M356 | 4 | `dividend_growth.py` | Pay months are the ex-date months | 1594 | `test_the_pay_months_are_last_years_modelled_pay_dates` (1 failing) | none |
| M357 | 4 | `dividend_growth.py` | The trailing year includes its first day | 1594 | `test_the_trailing_yield_is_the_last_365_days_of_dividends_over_the_last_close` (1 failing) | none |
| M358 | 4 | `dividend_growth.py` | The trailing yield ignores the price | 1594 | `test_the_trailing_yield_is_the_last_365_days_of_dividends_over_the_last_close` (1 failing) | none |
| M359 | 4 | `dividend_growth.py` | Cash goes to a pick that cannot be bought | 1594 | `test_between_reviews_a_pick_it_cannot_buy_today_gets_nothing` (1 failing) | none |
| M360 | 4 | `dividend_growth.py` | A pick is topped up past its target | 1594 | `test_between_reviews_a_pick_it_cannot_buy_today_gets_nothing`, `test_between_reviews_it_keeps_every_holding_and_tops_up_its_picks_to_their_target`, `test_between_reviews_the_target_is_one_over_min_stocks_when_fewer_were_picked` (3 failing) | none |
| M361 | 4 | `dividend_growth.py` | It reviews only on its first day | 1594 | `test_dividend_growth_reviews_again_on_the_first_trading_day_of_2022`, `test_it_reviews_on_its_first_day_and_its_first_day_in_each_year_only`, `test_it_reviews_on_no_day_but_the_first_and_each_new_years_first`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_recorder_writes_the_dividend_growth_file_byte_for_byte` (5 failing) | none |
| M362 | 4 | `dividend_growth.py` | max_stocks one below min_stocks is accepted | 1594 | `test_dividend_growth_holds_15_to_25_stocks_grown_over_5_years_by_default`, `test_each_bad_value_is_refused_naming_its_table_and_key`, `test_its_settings_are_checked_when_it_is_made` (5 failing) | none |
| M363 | 4 | `registry.py` | The look-back is one year short | 1594 | `test_dividend_growth_holds_15_to_25_stocks_grown_over_5_years_by_default`, `test_the_dividend_growth_run_reproduces_its_stored_results_exactly`, `test_the_recorder_writes_the_dividend_growth_file_byte_for_byte` (4 failing) | `test_dividend_growth_reviews_again_on_the_first_trading_day_of_2022` |
| M364 | 4 | `config.py` | The rule across two settings is not checked | 1594 | `test_each_bad_value_is_refused_naming_its_table_and_key` (3 failing) | none |
| M365 | 4 | `config.py` | The default strategy stays buy-and-hold | 1594 | `test_a_file_with_only_the_consent_takes_every_default`, `test_a_first_time_users_journey`, `test_the_starter_file_writes_every_key_under_its_comment` (4 failing) | `test_a_file_without_a_strategy_name_now_means_dividend_growth_so_paper_refuses` |
| M366 | 4 | `cli.py` | compare takes the first strategy's look-back | 1594 | `test_each_strategy_ends_as_it_does_alone_with_the_longest_look_back` (1 failing) | none |
| M367 | 4 | `cli.py` | A backtest of dividend-growth has no look-back | 1594 | `test_dividend_growth_reads_its_look_back_and_ends_as_the_library_run` (1 failing) | none |
| M368 | 4 | `paper.py` | Paper runs with no look-back | 1594 | `test_dividend_growth_reviews_again_on_the_first_trading_day_of_2022` (1 failing) | none |
| M369 | 4 | `dividend-growth.md` | The guide stops naming max_stocks | 1594 | `test_every_registered_strategy_has_a_complete_guide` (1 failing) | none |
| M370 | 5 | `strategies.dividend_growth.md` | A strategy lesson does not cite its guide | 1595 | `test_module_8_has_a_lesson_for_each_strategy_citing_its_guide` (1 failing) | none |
| M371 | 5 | `strategies.holding_cash.md` | The holding-cash lesson is not in module 8 | 1595 | `test_module_8_has_a_lesson_for_each_strategy_citing_its_guide` (1 failing) | none |
| M372 | 5 | `strategies.dividend_growth.md` | A module 8 lesson leaves a gap in the positions, so the course refuses to load | 1595 | `test_module_8_has_a_lesson_for_each_strategy_citing_its_guide` (115 failing) | 95 more tests, including `test_a_blocked_order_is_shown_with_its_reason_and_the_dividends_of_the_day`, `test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected`, `test_a_day_that_fails_to_save_leaves_the_account_at_the_day_before` |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M296',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '        found = known[: bisect_right(self._days.get(instrument, ()), today)]\n',
  '        found = known[: bisect_left(self._days.get(instrument, ()), today)]\n'),
 ('M297',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '        splits = [split for split in self._splits.get(instrument, ()) if split.ex_date <= '
  'today]\n',
  '        splits = list(self._splits.get(instrument, ()))\n'),
 ('M298',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '                    [split for split in splits if split.ex_date >= dividend.ex_date],\n',
  '                    [split for split in splits if split.ex_date > dividend.ex_date],\n'),
 ('M299',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '    return per_share * old / new\n',
  '    return per_share / new * old\n'),
 ('M300',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '            elif not isinstance(action, OtherAction):\n',
  '            elif isinstance(action, OtherAction):\n'),
 ('M301',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '        return instrument not in self._incomplete\n',
  '        return True\n'),
 ('M302',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '        outside = sorted(i.symbol for i in self.buyable - self.members)\n',
  '        outside: list[str] = []\n'),
 ('M303',
  1,
  'packages/steadyhand/src/steadyhand/view.py',
  '        return self._pay_dates.of(self._checked(ex_date))\n',
  '        return self._pay_dates.of(ex_date)\n'),
 ('M304',
  1,
  'packages/steadyhand/src/steadyhand/market.py',
  '        return add_trading_days(self.rules, ex_date, self.lag_trading_days)\n',
  '        return add_trading_days(self.rules, ex_date, self.lag_trading_days + 1)\n'),
 ('M305',
  1,
  'packages/steadyhand/src/steadyhand/engine.py',
  '        notes=(*claimed.notes, *strategy_notes),\n',
  '        notes=(*strategy_notes, *claimed.notes),\n'),
 ('M306',
  1,
  'packages/steadyhand/src/steadyhand/engine.py',
  '        strategy_notes = decision.notes\n',
  ''),
 ('M307',
  1,
  'packages/steadyhand/src/steadyhand/engine.py',
  '    return Tradable(day, buyable, sellable, reasons, inputs.members), warnings\n',
  '    return Tradable(day, buyable, sellable, reasons, buyable), warnings\n'),
 ('M308',
  1,
  'packages/steadyhand/src/steadyhand/engine.py',
  '            inputs.past_actions,\n',
  '            ActionHistory(),\n'),
 ('M309',
  1,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '        lookback = (date(start.year - lookback_years, 1, 1), start - timedelta(days=1))\n',
  '        lookback = (date(start.year - lookback_years, 1, 2), start - timedelta(days=1))\n'),
 ('M310',
  1,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '            except DataUnavailableError as error:\n'
  '                history_refused[stock] = str(error)\n',
  '            except UnavailableDaysError as error:\n'
  '                history_refused[stock] = str(error)\n'),
 ('M311',
  1,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '        *_history_warnings(window),\n',
  ''),
 ('M312',
  1,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    return _fetch(market, _days(market, start, end), settings.lookback_years)\n',
  '    return _fetch(market, _days(market, start, end), 0)\n'),
 ('M313',
  1,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    return _inputs(_fetch(market, _days(market, start, end), lookback_years))\n',
  '    return _inputs(_fetch(market, _days(market, start, end), 0))\n'),
 ('M314',
  1,
  'packages/steadyhand/src/steadyhand/strategies/registry.py',
  '            found[setting.name] = setting.check(given[setting.name])\n',
  '            found[setting.name] = given[setting.name]\n'),
 ('M315',
  1,
  'packages/steadyhand/src/steadyhand/strategies/registry.py',
  '        if type(value) is not int:\n            msg = f"{self.name} must be a whole number',
  '        if not isinstance(value, int):\n            msg = f"{self.name} must be a whole number'),
 ('M316',
  1,
  'packages/steadyhand/src/steadyhand/strategies/registry.py',
  '        if not self.minimum <= self.default <= self.maximum:\n',
  '        if not self.minimum <= self.default:\n'),
 ('M317',
  1,
  'packages/steadyhand/src/steadyhand/strategies/registry.py',
  '        return self.lookback(self.values(values))\n',
  '        return self.lookback(self.values())\n'),
 ('M318',
  1,
  'packages/steadyhand/src/steadyhand/strategies/protocol.py',
  '        require_type(self.notes, tuple, "notes")\n',
  ''),
 ('M319',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '            factor = _factor(history, row.day)\n            actions.append(',
  '            factor = Decimal(1)\n            actions.append('),
 ('M320',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/yahoo.py',
  '        return actions_in(self._history(instrument, start, end), instrument, start, end)\n',
  '        return unadjust(self._history(instrument, start, end), instrument, self._calendar, '
  'start, end)[1]\n'),
 ('M321',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/rules.py',
  '        return self._tables.calendar.is_trading_day(day)\n',
  '        self.require_supported(day)\n'
  '        return self._tables.calendar.is_trading_day(day)\n'),
 ('M322',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '            self._db.execute(\n'
  '                "INSERT OR IGNORE INTO fetched_actions VALUES (?, ?, ?)",\n'
  '                (symbol, start.isoformat(), end.isoformat()),\n'
  '            )\n',
  ''),
 ('M323',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '        if merged and start <= merged[-1][1] + _ONE_DAY:\n',
  '        if merged and start <= merged[-1][1]:\n'),
 ('M324',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '            except UnsupportedDateError:\n                span = (first, last)\n',
  '            except UnsupportedDateError:\n                span = None\n'),
 ('M325',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '            for first, last in self.missing_actions(instrument, start, complete):\n',
  '            for first, last in self.missing(instrument, start, complete):\n'),
 ('M326',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '                self._cache.store_actions(instrument, (first, last), actions)\n',
  '                pass\n'),
 ('M327',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/cache.py',
  '        self._require_within(instrument, span, [(a.instrument, a.ex_date) for a in actions])\n',
  ''),
 ('M328',
  2,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '            past += clean if whole is None else whole\n',
  '            past += clean\n'),
 ('M329',
  2,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '            if whole is None:\n                unknown.add(stock)\n',
  ''),
 ('M330',
  2,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '        ActionHistory(past, {*history_refused, *unknown}),\n',
  '        ActionHistory(past, history_refused),\n'),
 ('M331',
  2,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    except DataUnavailableError:\n        return None\n',
  '    except UnavailableDaysError:\n        return None\n'),
 ('M332',
  3,
  'packages/steadyhand/src/steadyhand/strategies/monthly_savings.py',
  '            reserve = (due - 1) * instalment if due > 0 else 0\n',
  '            reserve = due * instalment if due > 0 else 0\n'),
 ('M333',
  3,
  'packages/steadyhand/src/steadyhand/strategies/monthly_savings.py',
  '        if buying and bought.get(_MONTH) != month:\n',
  '        if buying:\n'),
 ('M334',
  3,
  'packages/steadyhand/src/steadyhand/strategies/monthly_savings.py',
  '            due, bought[_MONTH] = max(due - 1, 0), month\n',
  '            bought[_MONTH] = month\n'),
 ('M335',
  3,
  'packages/steadyhand/src/steadyhand/strategies/monthly_savings.py',
  '        weights = {stock: portfolio.weight(stock) for stock in portfolio.holdings}\n',
  '        weights: dict[Instrument, Decimal] = {}\n'),
 ('M336',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/config.py',
  '            if value > setting.maximum:\n',
  '            if value > setting.maximum + 1:\n'),
 ('M337',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/config.py',
  '            value = get_int(row, setting.name, where, minimum=setting.minimum)\n',
  '            value = get_int(row, setting.name, where, minimum=0)\n'),
 ('M338',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/config.py',
  '    if twice:\n        msg = f"[strategy] {twice[0]} would be',
  '    if False:\n        msg = f"[strategy] {twice[0]} would be'),
 ('M339',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/config.py',
  '        keys += [Key(setting.name, setting.default, setting.help) for setting in '
  'entry.settings]\n',
  '        keys += [Key(setting.name, setting.minimum, setting.help) for setting in '
  'entry.settings]\n'),
 ('M340',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        for setting in STRATEGIES[config.strategy].settings\n',
  '        for setting in ()\n'),
 ('M341',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        if old is None:\n            text = f"{key} is {new}, recorded for the first time"\n',
  '        if False:\n            text = f"{key} is {new}, recorded for the first time"\n'),
 ('M342',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        elif key.startswith("strategy."):\n',
  '        elif False:\n'),
 ('M343',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    strategy = STRATEGIES[config.strategy](config.strategy_settings)\n',
  '    strategy = STRATEGIES[config.strategy]()\n'),
 ('M344',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '    return STRATEGIES[name](config.strategy_settings)\n',
  '    return STRATEGIES[name]()\n'),
 ('M345',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        if stock not in view.tradable.members or not view.history_complete(stock):\n',
  '        if not view.history_complete(stock):\n'),
 ('M346',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        if stock not in view.tradable.members or not view.history_complete(stock):\n',
  '        if stock not in view.tradable.members:\n'),
 ('M347',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        first = year - self._growth_years - 1\n',
  '        first = year - self._growth_years\n'),
 ('M348',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        return totals[year - 1] >= totals[first]\n',
  '        return totals[year - 1] > totals[first]\n'),
 ('M349',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        reachable = view.tradable.buyable | frozenset(portfolio.holdings)\n',
  '        reachable = view.tradable.buyable\n'),
 ('M350',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        target = ratio_down(1, max(self._min, len(picked)))\n',
  '        target = ratio_down(1, len(picked))\n'),
 ('M351',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '            notes = (Note(STRATEGY_TOO_FEW_QUALIFIED, _too_few(len(picked))),)\n',
  '            notes = ()\n'),
 ('M352',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        if len(picked) < self._min:\n',
  '        if len(picked) <= self._min:\n'),
 ('M353',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '                    min(crowding[month] for month in months[stock]),\n',
  '                    max(crowding[month] for month in months[stock]),\n'),
 ('M354',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '                    -yields[stock],\n',
  '                    yields[stock],\n'),
 ('M355',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '                if dividend.ex_date.year == last_year\n',
  '                if dividend.ex_date.year <= last_year\n'),
 ('M356',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '                view.pay_date(dividend.ex_date).month\n',
  '                dividend.ex_date.month\n'),
 ('M357',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        (dividend.per_share for dividend in view.dividends(stock) if dividend.ex_date > '
  'since),\n',
  '        (dividend.per_share for dividend in view.dividends(stock) if dividend.ex_date >= '
  'since),\n'),
 ('M358',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '    return paid / close.amount if close is not None and close.amount else Decimal(0)\n',
  '    return paid\n'),
 ('M359',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        buying = chosen & view.tradable.buyable\n',
  '        buying = chosen\n'),
 ('M360',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '                weights[stock] = held + min(each, max(target - held, Decimal(0)))\n',
  '                weights[stock] = held + each\n'),
 ('M361',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        if memory.get(_YEAR_KEY) != str(view.today.year):\n',
  '        if not memory:\n'),
 ('M362',
  4,
  'packages/steadyhand/src/steadyhand/strategies/dividend_growth.py',
  '        if max_stocks < min_stocks:\n',
  '        if max_stocks < min_stocks - 1:\n'),
 ('M363',
  4,
  'packages/steadyhand/src/steadyhand/strategies/registry.py',
  '    return values["growth_years"] + 1\n',
  '    return values["growth_years"]\n'),
 ('M364',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/config.py',
  '        try:\n            entry(values)\n',
  '        try:\n            pass\n'),
 ('M365',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/config.py',
  '    keys = [Key("name", "dividend-growth",',
  '    keys = [Key("name", "buy-and-hold",'),
 ('M366',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '    lookback = max(entry.lookback_years(config.strategy_settings) for entry in entries)\n',
  '    lookback = entries[0].lookback_years(config.strategy_settings)\n'),
 ('M367',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '        config.settings, lookback_years=entry.lookback_years(config.strategy_settings)\n',
  '        config.settings, lookback_years=0\n'),
 ('M368',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        inputs = {found.day: found for found in day_inputs(market, opened_on, target, '
  'lookback)}\n',
  '        inputs = {found.day: found for found in day_inputs(market, opened_on, target)}\n'),
 ('M369',
  4,
  'packages/steadyhand/src/steadyhand/strategies/guides/dividend-growth.md',
  '- `max_stocks`: the most stocks it holds.',
  '- The most stocks it holds.'),
 ('M370',
  5,
  'packages/steadyhand/src/steadyhand/training/lessons/en/strategies.dividend_growth.md',
  'sources = ["packages/steadyhand/src/steadyhand/strategies/guides/dividend-growth.md", ',
  'sources = ['),
 ('M371',
  5,
  'packages/steadyhand/src/steadyhand/training/lessons/en/strategies.holding_cash.md',
  'module = "strategies"\nposition = 4\n',
  ''),
 ('M372',
  5,
  'packages/steadyhand/src/steadyhand/training/lessons/en/strategies.dividend_growth.md',
  'position = 3\n',
  'position = 5\n')]
```

## Carried forward

- **The engine credits nothing on a refused day** (scope decision 14): a held stock's dividend on a day the source refused prices for is still left out of the account, as M3's warning says, although the source can now read it. Crediting it changes M3's figures and belongs to its own ticket, for Shyden to decide.
- **Yahoo may scale dividends before an event it does not report** (build finding 4), as it scales prices: BBRI's recorded dividends before its 2021 rights issue could not be checked against what BBRI paid. The `dividend-growth` guide's *Risks* says that data from before such an event may not compare with data after it.
- **Wave 2 (M7) starts with `ma-trend`**, the first strategy that needs price bars from before a run's first day, which M7 builds (M6 §1.1); the point-in-time value strategy stays deferred (core §8). The settings mechanism (`Setting`, the flat `[strategy]` table, the guide guard) is what later strategies will use.
- **All fifteen scope decisions amend or fill in the M6 spec.** The spec keeps its approved text; this plan is the record of each change.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

**Before pass 1, while building the code (2026-09-30).** Every story was built and gated first in a scratch chain on `develop` `e2d36e4` (S1 `31ff423`, S2 `3726991`, S3 `e6c5a1f`, S4 `c1745a7`, S5 `9c87c50`), its red phase run against stubs, and its mutations run with predictions written first. That found these things a reading of the spec would not have (the plan cites them as build findings, by number):

1. **The look-back could not read the history the spec measured.** The spec's counts came from `yfinance` directly; through steadyhand's own reader, the price checks and the holiday calendar (2016 onwards) refused 11 of 45 six-year look-backs in February 2025 and every look-back from 2021 (it would start in 2015). Read without prices or the calendar, 2 of 45 were refused (unusable split ratios). Shyden chose that path as its own story (scope decision 1).
2. **Pay dates before 2021 were refused.** `is_trading_day` checked `verified_from` first, so a January 2021 review could not place a 2020 dividend's pay month. It now answers from the holiday data (scope decision 7), and the M4 income report places 2020 pay months.
3. **The income report now reads a holding whose old prices cannot be recovered** (scope decision 8): a pinned M4 test that stopped with exit 3 now builds the report with BBRI's 2021 dividend.
4. **Yahoo may scale dividends before an event it does not report**, as it scales prices; not verifiable here (Carried forward).
5. **A pay date counted by hand was wrong**: 8 December 2020 plus 14 trading days is 4 January 2021, not 30 December 2020 (9 December 2020 was a holiday). Every date in the tests is read from the calendar.
6. **A dividend on a refused run day was missing from the strategy's history, which still read complete.** Probing the golden run through the strategy's own view showed BBRI with no 2021 dividend at the January 2022 review: its 6 April 2021 dividend fell inside the 146 days Yahoo's prices were refused. The IDX source reads it without prices, so the history now holds it (scope decision 14).
7. **Mutation M331 went unseen at first.** Every test source refused the whole-run read with `UnavailableDaysError`, so narrowing the catch to that subclass turned nothing red; Yahoo's own failure after its retries is a plain `DataUnavailableError`. The test is now parametrised over both.
8. **Review Focus 1 had no test.** A file with no `[strategy] name` beside a `buy-and-hold` paper account is now pinned to refuse with the switch message.
9. **The scripted refusal in the `dividend-growth` golden run misfired twice.** Keyed on "ends before the run", it also refused TLKM's income history and stopped the run; keyed on the look-back's first day, 1 January 2018, it matched nothing, since the cache asks from the first trading day (2 January), and the recorded run bought TLKM. Reading the recorded file, not a test, showed the second. It is keyed on the range's shape: after the recordings start and before the run.
10. **A worked answer was wrong**: between reviews, a pick that cannot be offered any cash is written into the weights as 0 (a stock left out of the weights also targets 0). The test states the 0.
11. **The red phase needed three new stub rules.** A new `__post_init__` stubbed as a raise broke every import (the registry builds its entries at import), a new function called at import (`strategy_keys`) did the same, and a renamed method (`YahooDataSource._unadjusted`) left the old callers calling nothing. Test modules that build a pre-existing class with its new field fail to collect, and pytest then stops the whole run, so the red step passes `--continue-on-collection-errors` (Global Constraints).
12. **The machine was never idle while timing the performance test**: another session's browser tests held the load at 10 to 30 on four cores. The budget is set from the run at 10 (Measured performance).
13. **A guard's message named the wrong failure.** In S1's red phase the note-key guard reported "no Note(...) call was found in the packages" for a key defined but not yet used: its condition is fewer calls than keys. Swept: two liveness checks said "no" or "not found" for "fewer than N" (`test_legal_line.py`, `test_note_keys.py`). All three now say what they count (Task 1).

**Pass 1 (2026-10-01).** Mechanical: `check_plan.py` replayed the plan from its own text (`replay.out`): every task's red and gate counts OK, every story's tree IDENTICAL to its verified commit, the recorder's golden file matching its SHA-256, 0 problems. `prose_check.py` (all 25 cited tests exist in some story's tree; each task's mutation range agrees with the list) and `interface_check.py` (every **Produces** name defined in its story's tree; the rest are module paths, a file suffix and a lesson id), each with a negative control (a planted citation, a wrong range and an undefined name: all three reported). Both checkers came over from M5b still carrying its ranges and searching no `scripts/`; they were read and fixed first, since a clean result from them meant nothing until then. No new `noqa` or `pragma` in `packages/` from the base to S5 (the search finds the one that already exists); no "robot trading" added; test basenames unique across 88 files. The mutations then ran, all 77, on the commits of the time; after the rebuilds this pass led to, each was run again on its story's final commit (pass 2). Then the whole document read. Found three:
1. The plan cited build findings by `build-log.md`'s numbers, a file it does not carry. They are renumbered to this log's.
2. The `dividend-growth` guide (Task 4) said a stock passes when it "paid more lately than five years before" (an equal total passes), that the test "looks at only two years" (it asks for a dividend in each of six), called a part of the portfolio a "share", and named banks' dividend cuts of 2020 and 2021, which were never checked here. They are rewritten, and S4 and S5 rebuilt (`e09afb6`, `e7a79f1`): each re-gated (1594 and 1595 passed at 100%, perf and Python 3.13 clean), its red unchanged (58 and 2 failed), and its mutations run on the new commit.
3. **Seven mutations missed a predicted catcher**, though every one turned the suite red. One was a real gap: under M333 (`monthly-savings` buys on every day of a month) the reserve property stayed green, because it checked the cash against the strategy's own `due` counter, which the defect moves in step. The property now counts the months that bought itself, and goes red under M333 (planted by hand before the run). Swept: of every `@given` test's assertions, the only other one that reads a strategy's memory is `buy-and-hold`'s, which compares it with the memory the test gave it. S3 to S5 rebuilt (`e6c5a1f`, `c1745a7`, `9c87c50`), re-gated, and their red phases and mutations re-run. The other six were wrong predictions, corrected in the list with the reason: `test_the_dividend_growth_run_reviews_as_worked_by_hand` reads the stored golden file, so no code mutation can reach it (M346, M351, M361, M363); TLKM's refused look-back leaves the golden run without TLKM's years anyway, so ignoring `history_complete` changes nothing there (M346); with the yields reversed, the two-months test still picks TLKM and BBCA, by another route (M354); and the switched-to test names `instalments = 4`, so it cannot see a wrong default (M339).

**Pass 2 (2026-10-01).** Mechanical: the rendered plan (`mut-final.log` assembled from the three runs, each mutation from the run on its story's final commit: 77, none missed, every total its story's gate count) replayed from its own text (`replay2.out`): every task's red and gate counts OK, every tree IDENTICAL to its final commit, the recorder's golden file matching its SHA-256, 0 problems; its 809 code blocks and replay markers are identical to the re-rendered plan's after this pass's prose fixes (the comparison reports the pre-rebuild plan as different, its control). `prose_check.py`: 106 cited tests exist, all five mutation ranges agree; `interface_check.py` unchanged. Then the whole document read, each red phase's counts and kinds against its log. Found four:
1. Task 3's first criterion said the reserve property runs "over random months, top-ups and prices". It draws months, days, top-ups and buyable stocks, and no price: the strategy reads none. The criterion now says so, and that the test counts the months itself.
2. Task 2's red phase put the calendar's refusal of 2015 under "refuses trading days before 2021". It now names both.
3. Task 5's red phase repeated its step's "no stubs" sentence. Removed.
4. **Mutation checks** said every prediction was written before any run, though six were corrected after the first; it now points to pass 1's finding 3.

**Pass 3 (2026-10-01).** Mechanical: the rendered plan's 809 code blocks and replay markers are identical to those replayed in pass 2, so that replay stands; `prose_check.py` 0 problems; `interface_check.py` unchanged; no unfilled field. Then the whole document read, every mutation's description against the change it plants, and the File map against each story's `git diff --name-only`. Found three:
1. Four mutation descriptions misnamed their defect: M372 moves a lesson to position 5, which leaves a gap the course refuses to load (that is why 115 tests went red), not merely "out of order"; M344's defect reaches `compare` as well as `backtest`; M354 reverses the second key of the pick, not a tie-break; M331's said "only a days refusal is handled" where the effect is that a plain refusal stops the run.
2. The File map left out `market.py` in Task 2 (a docstring naming `is_trading_day`'s exception), the export modules (Tasks 1, 3 and 4) and `buy_and_hold.py` (Task 4 moves its set helpers out).
3. **Measured performance** said M3's budget leaves about six times its measurement; it leaves about three (30 s over 10.46 s locally). The comparison now names M5's paper budgets alone.

**Pass 4 (2026-10-01).** Mechanical: code blocks and replay markers identical to those replayed in pass 2; `prose_check.py` 0 problems; `interface_check.py` unchanged; every "scope decision N" and "build finding N" citation checked against the decision or finding it names; every Review Focus pin checked in `mut-final.log` (each named mutation turned its named test red). Then the whole document read. Found one:
1. Pass 1's entry said the mutations ran "all 77 on the final commits", but they ran on the commits of that time; the runs on the final commits came after the rebuilds (pass 2). Corrected.

**Pass 5 (2026-10-01).** Mechanical: code blocks and replay markers identical to those replayed in pass 2; `prose_check.py` 0 problems; `interface_check.py` unchanged; a sweep of the prose for repeated words, unbalanced backticks, double spaces and broken numbered lists, 0 problems, with planted controls (a repeated word, a stray backtick, a double space and a numbering jump: all four reported). Then the whole document read, and every section a claim cites looked up. Found three:
1. **Carried forward** said "`momentum` and `value` are M7 (M6 §1.1)". §1.1 says no such thing: wave 2 (M7) starts with `ma-trend`, the first strategy needing price bars from before a run, and the point-in-time value strategy stays deferred. The line now says that.
2. **Measured performance** began "No machine was idle", and named M3's and M5's budgets as "unchanged", leaving out M5a's start-up budgets. It now says the machine was never idle, and that every other budget is unchanged. This log's build finding 12 had the same wording.
3. The goal said "a strategy what they need". Now "what it needs".

**Pass 6 (2026-10-01).** Mechanical: code blocks and replay markers identical to those replayed in pass 2; `prose_check.py` and the prose sweep 0 problems; `interface_check.py` unchanged. Then the whole document read, and every factual claim looked up at its source: the spec sections cited, the build log's counts, the note texts in the code, `pyproject.toml`, the income module's names, the golden files, the synthetic market's start. Found one:
1. Scope decision 3 said ruff's five-argument limit has "no exception anywhere"; `pyproject.toml` exempts `tests/` from PLR0913. It now says the limit holds in package code, with `tests/` exempt.

**Pass 7 (2026-10-01).** Mechanical: code blocks and replay markers identical to those replayed in pass 2; `prose_check.py` and the prose sweep 0 problems; `interface_check.py` unchanged; the last claims looked up (the engine's payout and the income calendar both call `add_trading_days`; no `pyproject.toml` or `uv.lock` change in any story). Then the whole document read. Found one:
1. Task 3's first criterion, as pass 2 left it, ended with a clause ("counted by the test itself") whose subject was unclear. It now says what the property checks against: the months the test counts, never the strategy's memory.

**Pass 8 (2026-10-01).** Mechanical: code blocks and replay markers identical to those replayed in pass 2 (so the replay of the final commits stands); `prose_check.py`, the prose sweep and the unfilled-field check 0 problems; `interface_check.py` unchanged (its remaining names are module paths, a file suffix and a lesson id). Then the whole document read, the sections changed since pass 7 against their sources. **Found none. The loop ends here, and the plan is approved (operator rule of 2026-09-24: plans are reviewed to zero, then self-approved).**
