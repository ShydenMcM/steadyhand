# M3b Backtester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `steadyhand` a backtester, `backtest(strategy, market, start, end, settings) -> BacktestResult`, that runs a strategy and the `buy-and-hold` baseline over a range of days with the M3a engine day, reports each run's metrics, and is pinned by a golden run on a year of real recorded Yahoo data, a look-ahead truncation check and a ten-year performance test.

**Architecture:** `backtest` checks the range before day one (the rules' first date, the universe's first list, at least one trading day), fetches every bar and corporate action for every stock the universe holds on any day, fetching again around days the source refuses, then repeats M3a's pure `run_day` for the strategy and for the baseline. `measure` turns each run's `DayReport`s and final `EngineState` into `Metrics`. Nothing changes in place; M5 will add the CLI and the saved state.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. The engine gains no dependency.

**Spec:** `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md` (the "M3 spec"), stories 7–10 of its §10, on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec") and the M3a plan `docs/superpowers/plans/2026-09-26-m3a-engine-day.md`. Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how it was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2, M3 §3.2). No task adds a dependency.
- `float` never appears in the engine; `tests/meta/test_no_float.py` scans every engine module on disk. The performance test's synthetic prices come from integer arithmetic too.
- Money is integer minor units (`Money`); rates, weights, unit values and metrics are `Decimal`. A metric is worked out at 50 significant digits and rounded half-even to eight decimal places; a power uses `Decimal.ln` and `Decimal.exp` (M3 §8).
- Defaults, verbatim from the specs: dividend pay lag **14** trading days; maximum weight **10%** per stock, and **25%** in the golden settings so five stocks can be fully invested (M3 §9); the performance budget is **under 30 seconds** for **10 years** of **45** stocks (core §10.4).
- Every `*Error` a task adds is raised by a test that asserts its message (core §10.2). Every `pytest.raises` has a `match=` written as a raw string.
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A test that passes against the stubs is listed with its reason in its task. Configuration a test needs in order to be collected (a pytest marker) is part of the red step.
- No test computes a shared value from new code at module level; shared values come from `functools.cache` helpers or plain functions called inside each test.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code.
- Test file basenames are unique across `tests/`.
- English only. The phrase "robot trading" never appears (core §1.3). Every user-facing doc keeps the disclaimer verbatim.
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **A stock the source refuses on the backtest's first day** (BBRI through 2021-09-07, its rights issue). Expected: it is not buyable that day, so `buy-and-hold` never adds it to its set; one warning names its refused days. Pinned in Task 7 (`test_refusals_on_the_first_and_last_days_leave_one_range_between`) and Task 9 (`test_the_window_holds_the_events_it_was_chosen_for`).
2. **A dividend whose ex-date falls on a refused day.** Yahoo adjusts that day's dividend by the same unreported factor as its prices (BBRI's 2021-04-06 row shows 89.91268), so the amount is unknown. Expected: nothing is credited and the stock's warning says so, rather than a wrong amount booked in silence. Pinned in Task 7 (`test_refused_days_are_fetched_around_and_the_stock_sits_them_out`, which asserts the warning's text).
3. **A run so short that its annual return is astronomical** (13.5% in one day). Expected: it is reported, exact to eight places, not refused by `Decimal`. Pinned in Task 8 (`test_a_huge_annualised_return_from_a_short_run_is_reported_whole`).
4. **A source whose refusal names no day in the window it was asked for.** Expected: the run stops with the source's error instead of retrying as if every day were clean. Pinned in Task 7 (`test_a_refusal_naming_no_day_in_the_window_stops_the_run`).
5. **A backtest that ends past the shipped holiday data.** Expected: it stops before day one with the calendar's error naming the first year it lacks. Pinned in Task 7 (`test_an_end_the_calendar_does_not_cover_is_refused`).

## Scope decisions (read before starting)

1. **`backtest(strategy, market, start, end, settings)`.** M3 §7.1 lists seven arguments; the project's lint allows five and the repository carries no suppression, so the spec's `universe`, `source` and `rules` travel together as `Market(universe, source, rules)`, which checks each part's type.
2. **The `Universe` protocol gains `survivorship_warnings(start, end)`.** The result must carry the membership record's gap warnings (core §9.4), and only the universe knows its record. `Lq45Membership.survivorship_warnings` loses its "starts before the first list" branch and its test (M3 §7.2), and `docs/lq45-members.md` now says such a start is refused.
3. **The golden universe is built in code, not loaded from a file.** M3 §9 asks for "a small membership file in the real format", but the loader accepts only full lists of 45 codes, and no real LQ45 list is ever committed (`docs/research/t-lq45.md` §5). The five stocks are one `Lq45Record` whose source says it is a test selection, not an LQ45 list.
4. **The recorded fixtures travel with this plan; the golden result is generated.** Yahoo's answers cannot be recorded again identically later, so Task 0's PR commits the five year-long recordings. The golden result is deterministic from them, so Task 9 writes it with `scripts/record_golden.py` and checks its SHA-256, and a test requires the committed file to equal the script's output byte for byte.
5. **The fetch spans the first to the last trading day**, and after a refusal the clean ranges are runs of consecutive trading days, so a range holding only a weekend or a holiday is never requested.
6. **"Resumed" means a refused day lies between the stock's last bar and today.** That is M3 §7.3's "first clean day after refused days" whenever the stock trades that day, and it also covers a stock with no bar on its first clean day.
7. **A refusal that names no day in the requested window stops the run.** It contradicts the request, and retrying would treat every day as clean.
8. **A dividend on a refused day is not credited, and the warning says so** (Review Focus 2). The cautious direction, like the BBRI exclusion (M3 §11).
9. **Metrics conventions** (M3 §8 leaves them open): the trailing year is the 365 calendar days ending on the run's last day; annual figures scale by 365 over the run's calendar days, first and last included; the drawdown's running peak starts at the opening unit value of 1 on the first day, and of two equal falls the first is reported; turnover of a portfolio worth nothing is 0.
10. **`DayReport` gains `unit_price`**, the unit value at the day's close, because the drawdown needs it day by day. Adding a required field makes every `run_day` call fail with `TypeError` in Task 8's red phase, which is recorded there.
11. **The strategy's dividend income is shown against the baseline's** as the two runs' `metrics.trailing_income`; M5's report prints them side by side.
12. **The performance test is marked `perf` and runs in its own CI step without coverage.** Under coverage's tracing the ten-year run took 30.7 s locally, against 10.2 s without: timed that way it measures the tracer. The step sits inside the required `test (py3.12)` and `test (py3.13)` jobs, so it gates every merge.
13. **`Portfolio` keeps its cash balance and its still-unsettled movements.** Before this, every cash query summed the whole ledger and every new snapshot re-checked it: one synthetic year took 12.5 s and ten years ran past 600 s. Booking now checks only the new movement, and a query from the last day onwards reads the kept figures; an earlier day still reads the whole ledger. A hypothesis property compares every figure with the whole ledger read directly.
14. **`require_type` says "a UnitValue", not "an UnitValue":** every type name here that starts with U is said "you". Found while writing `Market`'s checks.
15. **The capital's currency must be the market's.** A mismatch would otherwise surface as a `CurrencyMismatchError` deep inside the first day.

## File map

| File | Task | Responsibility |
|---|---|---|
| `tests/fixtures/yahoo/{ASII,BBCA,BBRI,TLKM,UNVR}.JK_2021-02-01_2022-01-31.json` | 0 | The recorded Yahoo responses for the golden backtest |
| `packages/steadyhand/src/steadyhand/backtest.py` | 7, 8 | `Market`, `BacktestSettings`, `RunResult`, `BacktestResult`, `backtest`, the two errors |
| `.../steadyhand/universe.py`, `steadyhand_idx/universe.py` | 7 | `survivorship_warnings` on the protocol and on `Lq45Universe` |
| `.../steadyhand/_validate.py` | 7 | The article in `require_type`'s message |
| `.../steadyhand/metrics.py`, `engine.py` | 8 | `Metrics`, `measure`; `DayReport.unit_price` |
| `scripts/record_golden.py`, `tests/fixtures/golden/…json` | 9 | The golden run and its generated result |
| `.../steadyhand/portfolio.py`, `pyproject.toml`, `.github/workflows/ci.yml` | 10 | Kept cash totals; the `perf` marker and CI step |
| `.../steadyhand/__init__.py` | 7, 8 | The public API |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | The M3b plan, the stories and the golden fixtures (docs and data) | `m3/m3b-plan` |
| 7 | S7 backtest: pre-flight, refused days, halts and the baseline | `m3/s7-backtest` |
| 8 | S8 Metrics | `m3/s8-metrics` |
| 9 | S9 The golden backtest and the truncation check | `m3/s9-golden` |
| 10 | S10 The performance test and a linear-time cash ledger | `m3/s10-performance` |

Stories merge in order: each one's code builds on the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Then ask Shyden to approve the merge with `AskUserQuestion`, naming the PR, the head SHA **as read from the file in that same turn** (`cut -c1-7 "${TMPDIR}/head-sha"`), and the CI state. Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: The M3b plan, the stories and the golden fixtures

Documentation and data only, on `m3/m3b-plan`, whose PR carries this plan, `HANDOVER.md` and the five recordings (#61).

- [ ] **Step 1: Commit the recordings.** The five files were recorded on 2026-09-26 with `uv run python scripts/record_yahoo_fixture.py <SYMBOL> 2021-02-01 2022-01-31`, and are committed to `tests/fixtures/yahoo/` exactly as recorded. Each must have this SHA-256:
  - `ASII.JK_2021-02-01_2022-01-31.json`: `945a13ae3cdb37f05b5c1b5d32f0946b315b3aa559de31dd5815516fa8640cc0`
  - `BBCA.JK_2021-02-01_2022-01-31.json`: `6ab9b938904047d8c0458ec32b032293c4cf63f84a403161c5a2ae5bee0137ae`
  - `BBRI.JK_2021-02-01_2022-01-31.json`: `bfd55e08a120c16a1238a9005808529affb34c15722af52bb386868622ae7b9c`
  - `TLKM.JK_2021-02-01_2022-01-31.json`: `2941bae901acf90988d6d206fb414b352d635e6974bf9ad7fec72e4d68d9dfa8`
  - `UNVR.JK_2021-02-01_2022-01-31.json`: `3dae66bbb3522c04fcfd33b8fdef718104945bf1ef8ab7bc96d3893276ebb4b0`

  A later recording can differ, because Yahoo's answers can change. It is then a new fixture, reviewed like code, and Task 9's golden SHA-256 must be regenerated with it.
- [ ] **Step 2: Check them.** `uv run pytest -m live -k 2021-02-01 tests/idx/test_yahoo_live.py` passes 5, and replaying them gives 248 bars each for ASII, BBCA, TLKM and UNVR, and an `UnrecoverablePricesError` naming 146 days from 2021-02-01 to 2021-09-07 for BBRI.
- [ ] **Step 3: File the stories.** Create one issue per task 7–10, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 4: Open the PR** from `m3/m3b-plan` into `develop` (`Refs #61`), and merge it as **Merging a story** says. Then move #61 to Done.

---

### Task 7: S7 backtest: pre-flight, refused days, halts and the baseline

**Acceptance criteria (story text):**
1. `backtest(strategy, market, start, end, settings) -> BacktestResult` (scope decision 1), where `Market(universe, source, rules)` and `BacktestSettings(capital, engine=EngineSettings())` check their parts' types and the capital is positive.
2. Before day one, in order, each stopping the run with a named error and nothing fetched: `market`, `start`, `end` and `settings` have the right types (`TypeError`); `end` is not before `start` (`ValueError`); the capital is in the market's currency (`ValueError`); `rules.require_supported(start)` (`UnsupportedDateError`); `start` is not before `universe.first_day()` (`UniverseCoverageError`, naming the first date it covers); the range holds a trading day (`NoTradingDaysError`). An end past the holiday data stops with the calendar's `UnsupportedDateError`.
3. Every stock `members_on` returns on any trading day in the window is fetched, bars and corporate actions, from the first to the last trading day.
4. On an `UnavailableDaysError` the stock's refused days in the window are recorded and each run of consecutive clean trading days is fetched instead. On a refused day the stock is outside the tradable set and a holding is valued at its last clean close; on its first day after refused days the band check is skipped (scope decision 6). A refusal naming no day in the window, and any other `DataUnavailableError`, stops the run.
5. Both the strategy and `buy-and-hold` run every trading day through `run_day` with the same settings, from `EngineState.opening(capital, first trading day)`; a `buy-and-hold` backtest has no separate baseline. A halt lasts to the end of the run and is `RunResult.halt`. A `DataValidationError` stops the backtest.
6. `BacktestResult.warnings` are the universe's `survivorship_warnings(start, end)`, then one per refused stock naming its spans of refused days and saying a dividend on one of them is unknown; `RunResult.warnings` gathers every day's warnings in order.
7. `Universe` gains `survivorship_warnings(start, end) -> Sequence[str]`; `Lq45Universe` forwards its membership's, which no longer warn about a start before the first list, and `docs/lq45-members.md` says that start is refused. `require_type` writes "a UnitValue".
8. The engine exports `Market`, `BacktestSettings`, `BacktestResult`, `RunResult`, `backtest`, `UniverseCoverageError` and `NoTradingDaysError`. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M34–M44 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/backtest.py`
- Modify: `.../steadyhand/__init__.py`, `.../steadyhand/_validate.py`, `.../steadyhand/universe.py`, `packages/steadyhand-idx/src/steadyhand_idx/universe.py`, `docs/lq45-members.md`
- Test: create `tests/engine/test_backtest.py`; modify `tests/engine/test_protocols.py`, `tests/engine/test_validate.py`, `tests/idx/test_lq45_universe.py`, `tests/idx/test_universe.py`

**Interfaces:**
- Consumes: M3a's `run_day`, `DayInputs(day, history, actions, members, excluded, refused, resumed)`, `EngineState.opening(capital, day)`, `EngineSettings`, `PriceHistory`, `BuyAndHold`; M2's `UnavailableDaysError.days`.
- Produces: `Market(universe: Universe, source: DataSource, rules: MarketRules)`; `BacktestSettings(capital: Money, engine: EngineSettings = EngineSettings())`; `RunResult(strategy: str, reports: tuple[DayReport, ...], final: EngineState)` with `.halt` and `.warnings`; `BacktestResult(start, end, run: RunResult, baseline: RunResult | None, warnings: tuple[str, ...])`; `backtest(strategy: Strategy, market: Market, start: date, end: date, settings: BacktestSettings) -> BacktestResult`; `Universe.survivorship_warnings(start: date, end: date) -> Sequence[str]`.

- [ ] **Step 1: Branch.** `git switch -c m3/s7-backtest origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_backtest.py`** (new)

<!-- file: tests/engine/test_backtest.py -->
```python
"""backtest: the pre-flight checks, the fetch, refused days, halts and the baseline (M3 spec §7)."""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand.backtest import (
    BacktestResult,
    BacktestSettings,
    Market,
    NoTradingDaysError,
    UniverseCoverageError,
    backtest,
)
from steadyhand.data import DataUnavailableError, UnavailableDaysError
from steadyhand.engine import DataValidationError, EngineSettings
from steadyhand.market import UnsupportedDateError
from steadyhand.money import IDR, Currency, Money
from steadyhand.risk import RiskLimits
from steadyhand.strategies import BuyAndHold, Decision, Memory, Strategy
from steadyhand.types import Bar, CashDividend, CorporateAction, Instrument
from steadyhand.view import MarketView, PortfolioView
from steadyhand_idx import IdxMarketRules

BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
# The trading days from Monday 30 June to Friday 11 July 2025, by the shipped IDX calendar.
DAYS = (
    date(2025, 6, 30),
    date(2025, 7, 1),
    date(2025, 7, 2),
    date(2025, 7, 3),
    date(2025, 7, 4),
    date(2025, 7, 7),
    date(2025, 7, 8),
    date(2025, 7, 9),
    date(2025, 7, 10),
    date(2025, 7, 11),
)
START, END = DAYS[0], DAYS[-1]


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def settings(contribution: int | None = None) -> BacktestSettings:
    """Half the portfolio per stock, so two stocks can be fully invested."""
    limits = RiskLimits(max_weight=Decimal("0.5"))
    top_up = None if contribution is None else rp(contribution)
    return BacktestSettings(
        rp(100_000_000), EngineSettings(limits=limits, monthly_contribution=top_up)
    )


def bar(stock: Instrument, day: date, close: int, open_: int | None = None) -> Bar:
    start = close if open_ is None else open_
    high, low = rp(max(start, close)), rp(min(start, close))
    return Bar(stock, day, rp(start), high, low, rp(close), 10**7)


def flat(stock: Instrument, close: int, days: Sequence[date] = DAYS) -> list[Bar]:
    return [bar(stock, day, close) for day in days]


class _Source:
    """An in-memory data source that records every request and can refuse days, as Yahoo does."""

    def __init__(
        self,
        bars: Sequence[Bar],
        actions: Sequence[CorporateAction] = (),
        refused: Mapping[Instrument, Sequence[date]] | None = None,
        broken: frozenset[Instrument] = frozenset(),
    ) -> None:
        self._bars = bars
        self._actions = actions
        self._refused = {} if refused is None else refused
        self._broken = broken
        self.requests: list[tuple[str, str, date, date]] = []

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        self._check("bars", instrument, start, end)
        return [b for b in self._bars if b.instrument == instrument and start <= b.day <= end]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        self._check("actions", instrument, start, end)
        return [
            a for a in self._actions if a.instrument == instrument and start <= a.ex_date <= end
        ]

    def _check(self, kind: str, instrument: Instrument, start: date, end: date) -> None:
        self.requests.append((kind, instrument.symbol, start, end))
        if instrument in self._broken:
            msg = f"{instrument.symbol}: no data"
            raise DataUnavailableError(msg)
        days = [day for day in self._refused.get(instrument, ()) if start <= day <= end]
        if days:
            msg = f"{instrument.symbol}: refused"
            raise UnavailableDaysError(msg, days)


class _Universe:
    """Members from each listed date on, with exclusions and gap warnings to pass through."""

    def __init__(
        self,
        lists: Sequence[tuple[date, frozenset[Instrument]]],
        excluded: Mapping[Instrument, str] | None = None,
        warnings: Sequence[str] = (),
    ) -> None:
        self._lists = lists
        self._excluded = {} if excluded is None else excluded
        self._warnings = tuple(warnings)
        self.asked: list[tuple[date, date]] = []

    def members_on(self, day: date) -> frozenset[Instrument]:
        found = [members for start, members in self._lists if start <= day]
        if not found:
            msg = f"no members on {day.isoformat()}"
            raise LookupError(msg)
        return found[-1]

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return self._excluded

    def first_day(self) -> date:
        return self._lists[0][0]

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        self.asked.append((start, end))
        return self._warnings


class _Fixed:
    """A strategy that always asks for the same weights."""

    def __init__(self, weights: Mapping[Instrument, Decimal]) -> None:
        self._weights = weights

    @property
    def name(self) -> str:
        return "fixed"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        return Decision(self._weights)


def pair() -> _Universe:
    return _Universe([(START, frozenset({BBCA, BBRI}))])


def calm() -> list[Bar]:
    return flat(BBCA, 9_000) + flat(BBRI, 4_000)


def market(source: _Source, universe: _Universe | None = None) -> Market:
    return Market(pair() if universe is None else universe, source, rules())


def run(
    source: _Source,
    universe: _Universe | None = None,
    strategy: Strategy | None = None,
    chosen: BacktestSettings | None = None,
) -> BacktestResult:
    return backtest(
        _Fixed({BBCA: Decimal("0.5")}) if strategy is None else strategy,
        market(source, universe),
        START,
        END,
        settings() if chosen is None else chosen,
    )


def test_the_strategy_and_the_baseline_each_run_every_trading_day() -> None:
    result = run(_Source(calm()))
    assert (result.start, result.end) == (START, END)
    assert result.run.strategy == "fixed"
    assert result.baseline is not None
    assert result.baseline.strategy == "buy-and-hold"
    assert [report.day for report in result.run.reports] == list(DAYS)
    assert [report.day for report in result.baseline.reports] == list(DAYS)
    assert result.run.final.last_day == END
    assert result.baseline.final.last_day == END
    assert {order.instrument for order in result.run.reports[0].queued} == {BBCA}
    assert {order.instrument for order in result.baseline.reports[0].queued} == {BBCA, BBRI}


def test_both_runs_share_the_settings() -> None:
    result = run(_Source(calm()), chosen=settings(contribution=5_000_000))
    assert result.baseline is not None
    for outcome in (result.run, result.baseline):
        deposits = {report.day: report.deposit for report in outcome.reports}
        assert deposits[date(2025, 7, 1)] == rp(5_000_000)
        assert sum(amount.amount for amount in deposits.values()) == 5_000_000
        # At the default 10% cap these day-one buys would be cut; at 50% they are not.
        assert outcome.reports[0].cuts == ()


def test_a_buy_and_hold_backtest_is_its_own_baseline() -> None:
    result = run(_Source(calm()), strategy=BuyAndHold())
    assert result.run.strategy == "buy-and-hold"
    assert result.baseline is None


def test_a_start_the_rules_do_not_cover_is_refused_before_anything_is_fetched() -> None:
    source = _Source(calm())
    with pytest.raises(UnsupportedDateError, match=r"; 2020-12-30 is earlier$"):
        backtest(BuyAndHold(), market(source), date(2020, 12, 30), END, settings())
    assert source.requests == []


def test_a_start_before_the_universe_is_refused_naming_its_first_day() -> None:
    source = _Source(calm())
    late = _Universe([(date(2025, 7, 1), frozenset({BBCA}))])
    with pytest.raises(
        UniverseCoverageError,
        match=(
            r"^the backtest starts on 2025-06-30, but the universe's membership is only known "
            r"from 2025-07-01; start on 2025-07-01 or later$"
        ),
    ):
        run(source, late)
    assert source.requests == []


def test_an_end_the_calendar_does_not_cover_is_refused() -> None:
    with pytest.raises(
        UnsupportedDateError,
        match=r"^holidays\.toml has no IDX holidays for \d{4}, so its trading days are unknown",
    ):
        backtest(BuyAndHold(), market(_Source([])), START, date(2099, 1, 5), settings())


@pytest.mark.parametrize(
    ("start", "end", "error", "message"),
    [
        (
            END,
            START,
            ValueError,
            r"^the backtest ends on 2025-06-30, before it starts on 2025-07-11$",
        ),
        (
            date(2025, 7, 5),
            date(2025, 7, 6),
            NoTradingDaysError,
            r"^there is no trading day from 2025-07-05 to 2025-07-06$",
        ),
    ],
)
def test_a_range_must_run_forwards_and_hold_a_trading_day(
    start: date, end: date, error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        backtest(BuyAndHold(), market(_Source(calm())), start, end, settings())


def test_a_market_checks_its_parts() -> None:
    with pytest.raises(TypeError, match=r"^universe must be a Universe, got NoneType$"):
        Market(None, _Source([]), rules())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^source must be a DataSource, got NoneType$"):
        Market(pair(), None, rules())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^rules must be a MarketRules, got NoneType$"):
        Market(pair(), _Source([]), None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^market must be a Market, got NoneType$"):
        backtest(BuyAndHold(), None, START, END, settings())  # type: ignore[arg-type]


def test_the_capital_is_positive_and_in_the_markets_currency() -> None:
    with pytest.raises(ValueError, match=r"^the starting capital must be positive, got IDR 0$"):
        BacktestSettings(rp(0))
    with pytest.raises(TypeError, match=r"^capital must be a Money, got int$"):
        BacktestSettings(100)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^engine must be an EngineSettings, got NoneType$"):
        BacktestSettings(rp(1), None)  # type: ignore[arg-type]
    dollars = BacktestSettings(Money(100_000, Currency("USD", 2)))
    with pytest.raises(ValueError, match=r"^the capital is in USD, but the market trades in IDR$"):
        backtest(BuyAndHold(), market(_Source(calm())), START, END, dollars)
    with pytest.raises(TypeError, match=r"^settings must be a BacktestSettings, got NoneType$"):
        backtest(BuyAndHold(), market(_Source(calm())), START, END, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^start must be a date, got str$"):
        backtest(BuyAndHold(), market(_Source(calm())), "2025-06-30", END, settings())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^end must be a date, got str$"):
        backtest(BuyAndHold(), market(_Source(calm())), START, "2025-07-11", settings())  # type: ignore[arg-type]


def test_every_stock_the_universe_holds_on_any_day_is_fetched_for_the_whole_window() -> None:
    joins = date(2025, 7, 7)
    universe = _Universe([(START, frozenset({BBCA})), (joins, frozenset({BBCA, TLKM}))])
    source = _Source(flat(BBCA, 9_000) + flat(TLKM, 3_000))
    result = run(source, universe, strategy=_Fixed({TLKM: Decimal("0.5")}))
    assert source.requests == [
        ("bars", "BBCA", START, END),
        ("actions", "BBCA", START, END),
        ("bars", "TLKM", START, END),
        ("actions", "TLKM", START, END),
    ]
    queued = [{order.instrument for order in report.queued} for report in result.run.reports]
    assert queued[5:] == [{TLKM}, set(), set(), set(), set()]
    assert all(not found for found in queued[:5])
    assert [rejected.reason for rejected in result.run.reports[0].rejected] == [
        "not in the universe on 2025-06-30"
    ]


def test_refused_days_are_fetched_around_and_the_stock_sits_them_out() -> None:
    refused = (date(2025, 7, 3), date(2025, 7, 4), date(2025, 7, 7), date(2025, 7, 10))
    clean = [day for day in DAYS if day not in refused]
    # BBRI reopens on 8 July at 5,200, outside the band around its last clean close of 4,000:
    # after refused days that close says nothing, so the band check must skip it.
    bbri = [bar(BBRI, day, 4_000) for day in clean if day < date(2025, 7, 8)] + [
        bar(BBRI, day, 5_200) for day in clean if day >= date(2025, 7, 8)
    ]
    source = _Source(flat(BBCA, 9_000) + bbri, refused={BBRI: refused})
    universe = _Universe([(START, frozenset({BBCA, BBRI}))], warnings=["a gap"])
    result = run(source, universe, strategy=BuyAndHold())
    assert source.requests == [
        ("bars", "BBCA", START, END),
        ("actions", "BBCA", START, END),
        ("bars", "BBRI", START, END),
        ("bars", "BBRI", START, date(2025, 7, 2)),
        ("actions", "BBRI", START, date(2025, 7, 2)),
        ("bars", "BBRI", date(2025, 7, 8), date(2025, 7, 9)),
        ("actions", "BBRI", date(2025, 7, 8), date(2025, 7, 9)),
        ("bars", "BBRI", END, END),
        ("actions", "BBRI", END, END),
    ]
    assert universe.asked == [(START, END)]
    assert result.warnings == (
        "a gap",
        (
            "BBRI: the data source refused 4 day(s) (2025-07-03 to 2025-07-07, 2025-07-10), so it "
            "was not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited."
        ),
    )
    reports = {report.day: report for report in result.run.reports}
    held = {p.instrument: p.quantity for p in result.run.final.holdings.portfolio.positions}
    for day in refused:
        assert all(order.instrument != BBRI for order in reports[day].queued)
        assert all(fill.order.instrument != BBRI for fill in reports[day].fills)
    bbca = next(
        fill.quantity for fill in reports[date(2025, 7, 1)].fills if fill.order.instrument == BBCA
    )
    bbri_held = next(
        fill.quantity for fill in reports[date(2025, 7, 1)].fills if fill.order.instrument == BBRI
    )
    assert reports[date(2025, 7, 3)].holdings_value == rp(9_000 * bbca + 4_000 * bbri_held)
    assert reports[date(2025, 7, 8)].holdings_value == rp(9_000 * bbca + 5_200 * bbri_held)
    assert held[BBRI] == bbri_held


class _OutOfWindow(_Source):
    """A source whose first answer for BBRI refuses a day after the window, contradicting the
    request, and which answers normally after that. Retrying would hide the contradiction."""

    def __init__(self, bars: Sequence[Bar]) -> None:
        super().__init__(bars)
        self._refused_once = False

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        if instrument == BBRI and not self._refused_once:
            self._refused_once = True
            msg = "BBRI: refused"
            raise UnavailableDaysError(msg, [date(2025, 8, 1)])
        return super().bars(instrument, start, end)


def test_a_refusal_naming_no_day_in_the_window_stops_the_run() -> None:
    with pytest.raises(UnavailableDaysError, match=r"^BBRI: refused$"):
        run(_OutOfWindow(calm()))


def test_refusals_on_the_first_and_last_days_leave_one_range_between() -> None:
    source = _Source(calm(), refused={BBRI: (START, END)})
    result = run(source, strategy=BuyAndHold())
    assert [r for r in source.requests if r[1] == "BBRI"] == [
        ("bars", "BBRI", START, END),
        ("bars", "BBRI", DAYS[1], DAYS[-2]),
        ("actions", "BBRI", DAYS[1], DAYS[-2]),
    ]
    assert result.warnings[0].startswith(
        "BBRI: the data source refused 2 day(s) (2025-06-30, 2025-07-11),"
    )
    # Refused on day one, BBRI is not buyable then, so buy-and-hold never adds it to its set.
    assert result.run.final.memory == {"set": "IDX:BBCA"}


def test_any_other_unavailable_data_stops_the_run() -> None:
    with pytest.raises(DataUnavailableError, match=r"^BBRI: no data$"):
        run(_Source(calm(), broken=frozenset({BBRI})))


def test_a_close_outside_the_band_stops_the_backtest() -> None:
    jumped = flat(BBCA, 9_000, DAYS[:3]) + flat(BBCA, 12_000, DAYS[3:]) + flat(BBRI, 4_000)
    with pytest.raises(
        DataValidationError,
        match=r"^BBCA on 2025-07-03: the close IDR 12,000 is outside the band IDR 7,650 to",
    ):
        run(_Source(jumped))


def test_a_halt_lasts_to_the_end_of_the_run_and_is_recorded() -> None:
    # Fully invested half and half; BBCA's 15% fall on 7 July takes the portfolio past 5%.
    fall = flat(BBCA, 9_000, DAYS[:5]) + flat(BBCA, 7_650, DAYS[5:]) + flat(BBRI, 4_000)
    result = run(_Source(fall), strategy=BuyAndHold())
    assert result.run.halt is not None
    assert result.run.halt.day == date(2025, 7, 7)
    assert result.run.halt.cause == (
        "daily loss limit: the unit value fell 7.46%, the limit is 5.00%"
    )
    reports = {report.day: report for report in result.run.reports}
    assert reports[date(2025, 7, 7)].halt == result.run.halt
    assert all(report.queued == () for day, report in reports.items() if day >= date(2025, 7, 7))
    assert all(report.halt is None for day, report in reports.items() if day != date(2025, 7, 7))


def test_exclusions_and_corporate_actions_reach_their_days() -> None:
    universe = _Universe([(START, frozenset({BBCA, BBRI, TLKM}))], {TLKM: "Special Monitoring"})
    dividend = CashDividend(BBCA, date(2025, 7, 8), Decimal(50))
    source = _Source(calm() + flat(TLKM, 3_000), [dividend])
    result = run(source, universe, strategy=BuyAndHold())
    assert {order.instrument for order in result.run.reports[0].queued} == {BBCA, BBRI}
    entitled = {report.day: report.entitled for report in result.run.reports}
    held = next(
        fill.quantity for fill in result.run.reports[1].fills if fill.order.instrument == BBCA
    )
    assert [(e.instrument, e.gross) for e in entitled[date(2025, 7, 8)]] == [(BBCA, rp(50 * held))]
    assert all(not found for day, found in entitled.items() if day != date(2025, 7, 8))


def test_a_run_gathers_every_days_warnings_in_order() -> None:
    gap = date(2025, 7, 8)
    source = _Source(flat(BBCA, 9_000) + [b for b in flat(BBRI, 4_000) if b.day != gap])
    result = run(source, strategy=BuyAndHold())
    assert result.run.warnings == (
        (
            "BBRI has no bar on 2025-07-08, so it is not traded; it is valued at its last close, "
            "IDR 4,000"
        ),
    )
    assert result.warnings == ()
```

**`tests/engine/test_protocols.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python
        return date(2021, 1, 4)


def test_a_minimal_class_satisfies_universe() -> None:
```
with:
```python
        return date(2021, 1, 4)

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        return ()


def test_a_minimal_class_satisfies_universe() -> None:
```

**`tests/engine/test_validate.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_validate.py -->
Replace:
```python
from steadyhand._validate import require_date, require_int, require_type

```
with:
```python
from steadyhand._validate import require_date, require_int, require_type
from steadyhand.risk import UnitValue

```

<!-- edit: tests/engine/test_validate.py -->
Replace:
```python
        require_type("1", int, "order")
```
with:
```python
        require_type("1", int, "order")


def test_require_type_uses_a_before_a_u_that_sounds_like_you() -> None:
    with pytest.raises(TypeError, match=r"^units must be a UnitValue, got int$"):
        require_type(1, UnitValue, "units")
```

**`tests/idx/test_lq45_universe.py`** (changed: 1 edit)

<!-- edit: tests/idx/test_lq45_universe.py -->
Replace:
```python
    assert Lq45Universe(membership()).excluded_on(FIRST) == {}
```
with:
```python
    assert Lq45Universe(membership()).excluded_on(FIRST) == {}


def test_survivorship_warnings_are_the_memberships() -> None:
    gapped = Lq45Membership(
        [
            Lq45Record(FIRST, date(2021, 1, 25), "Peng-1", "review", frozenset(CODES[:45])),
            Lq45Record(
                date(2022, 2, 1), date(2022, 1, 25), "Peng-3", "review", frozenset(CODES[1:])
            ),
        ]
    )
    warnings = Lq45Universe(gapped).survivorship_warnings(FIRST, date(2022, 6, 30))
    assert warnings == tuple(gapped.survivorship_warnings(FIRST, date(2022, 6, 30)))
    assert len(warnings) == 1
    assert "between 2021-02-01 (Peng-1) and 2022-02-01 (Peng-3)" in warnings[0]
```

**`tests/idx/test_universe.py`** (changed: 1 edit)

<!-- edit: tests/idx/test_universe.py -->
Replace:
```python

def test_warnings_for_an_early_start_and_each_gap_spanned(membership: Lq45Membership) -> None:
    warnings = membership.survivorship_warnings(date(2021, 1, 4), date(2023, 12, 29))
    assert len(warnings) == 2
    assert warnings[0].startswith(
        "Survivorship bias: the backtest starts on 2021-01-04, before the first LQ45 list in "
        "lq45_members.toml (2022-08-01, Peng-test/2022-08-01)."
    )
    assert "no LQ45 list between 2022-08-01" in warnings[1]
    assert "and 2023-08-01 (Peng-test/2023-08-01), more than one review apart" in warnings[1]
    assert membership.survivorship_warnings(date(2024, 2, 1), date(2024, 7, 31)) == []
```
with:
```python

def test_a_warning_for_each_gap_spanned(membership: Lq45Membership) -> None:
    # A start before the first list needs no warning: the backtest refuses it (M3 spec §7.2).
    warnings = membership.survivorship_warnings(date(2022, 8, 1), date(2023, 12, 29))
    assert warnings == [
        (
            "Survivorship bias: lq45_members.toml has no LQ45 list between 2022-08-01 "
            "(Peng-test/2022-08-01) and 2023-08-01 (Peng-test/2023-08-01), more than one review "
            "apart. The backtest uses the earlier list until the later one."
        )
    ]
    assert membership.survivorship_warnings(date(2021, 1, 4), date(2022, 7, 29)) == []
    assert membership.survivorship_warnings(date(2024, 2, 1), date(2024, 7, 31)) == []
```


- [ ] **Step 3: Write the stubs.** New names only; everything that existed keeps its current body.

**`packages/steadyhand-idx/src/steadyhand_idx/universe.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python
        return self._membership.records[0].effective
```
with:
```python
        return self._membership.records[0].effective

    def survivorship_warnings(self, start: date, end: date) -> tuple[str, ...]:
        raise NotImplementedError("Lq45Universe.survivorship_warnings")
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python

from steadyhand.broker import Broker, FillResult, FillSettings, Opening, SimulatedBroker
```
with:
```python

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
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "STRATEGIES",
    "Bar",
```
with:
```python
    "STRATEGIES",
    "BacktestResult",
    "BacktestSettings",
    "Bar",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "LookAheadError",
    "MarketRules",
```
with:
```python
    "LookAheadError",
    "Market",
    "MarketRules",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "NegativeProceedsError",
    "Opening",
```
with:
```python
    "NegativeProceedsError",
    "NoTradingDaysError",
    "Opening",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Rounding",
    "Side",
```
with:
```python
    "Rounding",
    "RunResult",
    "Side",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Universe",
    "UnsupportedDateError",
    "__version__",
    "apply_actions",
    "run_day",
```
with:
```python
    "Universe",
    "UniverseCoverageError",
    "UnsupportedDateError",
    "__version__",
    "apply_actions",
    "backtest",
    "run_day",
```

**`packages/steadyhand/src/steadyhand/_validate.py`** (changed, new names stubbed: 0 edit)

**`packages/steadyhand/src/steadyhand/backtest.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/backtest.py -->
```python
"""The backtester: a strategy and the ``buy-and-hold`` baseline over a range of days (M3 spec §7).

``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, then repeats ``run_day`` over the trading days: once for the strategy and once, with the
same settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from steadyhand._validate import require_date, require_type
from steadyhand.data import DataSource, UnavailableDaysError
from steadyhand.engine import DayInputs, DayReport, EngineSettings, EngineState, run_day
from steadyhand.market import MarketRules
from steadyhand.money import Money
from steadyhand.risk import Halt
from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy
from steadyhand.types import Bar, CorporateAction, Instrument
from steadyhand.universe import Universe
from steadyhand.view import PriceHistory


class UniverseCoverageError(LookupError):
    """The backtest starts before the universe's first known membership (M3 spec, decision 3)."""

    def __init__(self, start: date, first: date) -> None:
        raise NotImplementedError("UniverseCoverageError.__init__")


class NoTradingDaysError(ValueError):
    """The range holds no trading day, so there is nothing to run."""


@dataclass(frozen=True, slots=True)
class Market:
    """Where a backtest's world comes from: the stocks it may hold, their data, and the rules."""

    universe: Universe
    source: DataSource
    rules: MarketRules

    def __post_init__(self) -> None:
        raise NotImplementedError("Market.__post_init__")


@dataclass(frozen=True, slots=True)
class BacktestSettings:
    """The capital a run starts with, and how the engine runs each day. Both runs share them."""

    capital: Money
    engine: EngineSettings = field(default_factory=EngineSettings)

    def __post_init__(self) -> None:
        raise NotImplementedError("BacktestSettings.__post_init__")


@dataclass(frozen=True, slots=True)
class RunResult:
    """One strategy's run: every day's report, in order, and the state after the last day."""

    strategy: str
    reports: tuple[DayReport, ...]
    final: EngineState

    @property
    def halt(self) -> Halt | None:
        """The halt that stopped ordering, which lasts to the end of the run (decision 4)."""
        raise NotImplementedError("RunResult.halt")

    @property
    def warnings(self) -> tuple[str, ...]:
        """Every day's warnings, in day order."""
        raise NotImplementedError("RunResult.warnings")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The strategy's run and, unless the strategy is the baseline, the baseline's.

    ``warnings`` are about the data both runs share: gaps in the universe's membership record,
    and each stock whose data source refused some of its days.
    """

    start: date
    end: date
    run: RunResult
    baseline: RunResult | None
    warnings: tuple[str, ...]


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
    raise NotImplementedError("backtest")


def _calendar_days(start: date, end: date) -> Iterator[date]:
    raise NotImplementedError("_calendar_days")


def _fetch(market: Market, days: tuple[date, ...]) -> _Window:
    """Fetch every stock the universe holds on any of *days*, over all of them (M3 spec §7.1).

    A stock whose source refuses some days is fetched again over the clean ranges around them.
    """
    raise NotImplementedError("_fetch")


def _clean_ranges(days: Sequence[date], refused: frozenset[date]) -> Iterator[tuple[date, date]]:
    """Each run of consecutive trading days holding no refused day, as its first and last day.

    Built from trading days, so a range that holds only a weekend or a holiday is never asked for.
    """
    raise NotImplementedError("_clean_ranges")


def _run(
    strategy: Strategy, window: _Window, rules: MarketRules, settings: BacktestSettings
) -> RunResult:
    raise NotImplementedError("_run")


def _resumed(window: _Window, day: date) -> frozenset[Instrument]:
    """Stocks with a refused day between their last bar and *day*: no usable previous close."""
    raise NotImplementedError("_resumed")


def _refused_warnings(window: _Window) -> list[str]:
    """One warning per stock, naming each span of consecutive refused trading days."""
    raise NotImplementedError("_refused_warnings")
```

**`packages/steadyhand/src/steadyhand/universe.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/universe.py -->
Replace:
```python

from collections.abc import Mapping
from datetime import date
```
with:
```python

from collections.abc import Mapping, Sequence
from datetime import date
```

<!-- edit: packages/steadyhand/src/steadyhand/universe.py -->
Replace:
```python
        """The first day whose membership is known."""
        ...
```
with:
```python
        """The first day whose membership is known."""
        ...

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        """What a backtest from *start* to *end* must print about gaps in the membership record.

        A stock that joined and left inside a gap never appears, so the results look better than
        a real investor's would have (core spec §9.4).
        """
        ...
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=711 failed=22 -->
Expected: 711 run (the 9 `live` tests deselected), 22 failed: 20 with `NotImplementedError`, and 2 with `AssertionError` because a changed function keeps its old body until Step 5: `test_require_type_uses_a_before_a_u_that_sounds_like_you` (the old article rule) and `test_a_warning_for_each_gap_spanned` (the old early-start warning). None passes against the stubs.

- [ ] **Step 5: Implement.**

**`docs/lq45-members.md`** (changed: 1 edit)

<!-- edit: docs/lq45-members.md -->
Replace:
```markdown

A backtest that starts before your first record, or runs across two records more than one review apart, prints a **survivorship-bias warning**. Reviews were every six months until January 2024 and every three months from May 2024. A gap means stocks that joined and left the LQ45 inside it never appear in the backtest, so its results look better than a real investor's would have. Five reviews between 2016 and 2025 have no primary list anyone has found (`t-lq45.md` §3).

```
with:
```markdown

A backtest refuses to start before your first record, and names the first date it can start on. One that runs across two records more than one review apart prints a **survivorship-bias warning**. Reviews were every six months until January 2024 and every three months from May 2024. A gap means stocks that joined and left the LQ45 inside it never appear in the backtest, so its results look better than a real investor's would have. Five reviews between 2016 and 2025 have no primary list anyone has found (`t-lq45.md` §3).

```

**`packages/steadyhand-idx/src/steadyhand_idx/universe.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python
    def survivorship_warnings(self, start: date, end: date) -> list[str]:
        """What a backtest from *start* to *end* must print about missing lists (spec §9.4)."""
        warnings: list[str] = []
        first = self._records[0]
        if start < first.effective:
            warnings.append(
                f"Survivorship bias: the backtest starts on {start.isoformat()}, before the first "
                f"LQ45 list in {self._file} ({first.effective.isoformat()}, {first.source}). "
                "Stocks that left the LQ45 before then are missing from the universe."
            )
        for earlier, later in self.gaps():
```
with:
```python
    def survivorship_warnings(self, start: date, end: date) -> list[str]:
        """What a backtest from *start* to *end* must print about missing lists (spec §9.4).

        A start before the first list needs no warning: the backtest refuses it (M3 spec §7.2).
        """
        warnings: list[str] = []
        for earlier, later in self.gaps():
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python
    def survivorship_warnings(self, start: date, end: date) -> tuple[str, ...]:
        raise NotImplementedError("Lq45Universe.survivorship_warnings")
```
with:
```python
    def survivorship_warnings(self, start: date, end: date) -> tuple[str, ...]:
        return tuple(self._membership.survivorship_warnings(start, end))
```

**`packages/steadyhand/src/steadyhand/_validate.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/_validate.py -->
Replace:
```python
        name = expected.__name__
        article = "an" if name[0].lower() in "aeiou" else "a"
        msg = f"{what} must be {article} {name}, got {type(value).__name__}"
```
with:
```python
        name = expected.__name__
        # "an" before a vowel sound; every type name here starting with U says "you" (UnitValue).
        article = "an" if name[0].lower() in "aeio" else "a"
        msg = f"{what} must be {article} {name}, got {type(value).__name__}"
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/backtest.py -->
```python
"""The backtester: a strategy and the ``buy-and-hold`` baseline over a range of days (M3 spec §7).

``backtest`` checks the range before day one, fetches every bar and corporate action the run can
need, then repeats ``run_day`` over the trading days: once for the strategy and once, with the
same settings, for the baseline. Nothing is guessed: a start the rules or the universe do not
cover stops the run with an error that names the first date that would work.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from steadyhand._validate import require_date, require_type
from steadyhand.data import DataSource, UnavailableDaysError
from steadyhand.engine import DayInputs, DayReport, EngineSettings, EngineState, run_day
from steadyhand.market import MarketRules
from steadyhand.money import Money
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
    """The capital a run starts with, and how the engine runs each day. Both runs share them."""

    capital: Money
    engine: EngineSettings = field(default_factory=EngineSettings)

    def __post_init__(self) -> None:
        require_type(self.capital, Money, "capital")
        require_type(self.engine, EngineSettings, "engine")
        if self.capital.amount <= 0:
            msg = f"the starting capital must be positive, got {self.capital}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RunResult:
    """One strategy's run: every day's report, in order, and the state after the last day."""

    strategy: str
    reports: tuple[DayReport, ...]
    final: EngineState

    @property
    def halt(self) -> Halt | None:
        """The halt that stopped ordering, which lasts to the end of the run (decision 4)."""
        return self.final.halt

    @property
    def warnings(self) -> tuple[str, ...]:
        """Every day's warnings, in day order."""
        return tuple(warning for report in self.reports for warning in report.warnings)


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The strategy's run and, unless the strategy is the baseline, the baseline's.

    ``warnings`` are about the data both runs share: gaps in the universe's membership record,
    and each stock whose data source refused some of its days.
    """

    start: date
    end: date
    run: RunResult
    baseline: RunResult | None
    warnings: tuple[str, ...]


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
    return RunResult(strategy.name, tuple(reports), state)


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


- [ ] **Step 6: Run the whole gate.** `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, then `HYPOTHESIS_PROFILE=ci uv run pytest -W error --cov --cov-report=term-missing`, each with its exit status read as above.

<!-- check: gate total=711 passed=711 -->
Expected: every command exits 0; 711 passed, 9 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M34–M44 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S7 backtest …`), as **Merging a story** says.

---

### Task 8: S8 Metrics

**Acceptance criteria (story text):**
1. `measure(reports, final) -> Metrics` for a run's day reports in order and its last state; no reports raises `ValueError`.
2. `Metrics` holds: `final_value` (the last day's value); `deposited` (the ledger's deposits only); `total_return` (the unit value less 1, time-weighted, so a deposit is never a gain); `annual_return` (compounded over the run's calendar days, first and last included, to 365; −1 for a total loss); `drawdown` (`Drawdown(depth, peak, trough)`, the deepest fall from a running peak that starts at 1, the first of equal falls); `costs` (`CostBreakdown(fee, levy, sale_tax, daily)` with `.total`); `turnover` ((bought + sold) ÷ 2 ÷ the average daily value, scaled to 365 days; 0 when the average is 0); `dividends` (`DividendTotals(gross, tax)` with `.net`); and `trailing_income` (net dividends paid in the 365 days ending on the last day).
3. Money stays integer rupiah; every ratio is worked out at 50 digits with `Decimal.ln`/`Decimal.exp` and rounded half-even to eight places (`RATIO_PLACES`), and a huge annual return is reported, not refused.
4. `DayReport.unit_price` is the unit value at the day's close; `RunResult.metrics` is `measure(reports, final)` for both runs.
5. A hypothesis property checks the drawdown against every (peak, later day) pair.
6. The engine exports `Metrics`, `Drawdown`, `CostBreakdown`, `DividendTotals`, `measure`, `RATIO_PLACES` and `YEAR_DAYS`. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M45–M54 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/metrics.py`
- Modify: `.../steadyhand/engine.py`, `.../steadyhand/backtest.py`, `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_metrics.py`; modify `tests/engine/test_backtest.py`, `tests/engine/test_engine.py`

**Interfaces:**
- Consumes: Task 7's `RunResult`; M3a's `DayReport`, `EngineState`, `Portfolio.ledger`, `MovementKind.DEPOSIT`.
- Produces: `measure(reports: Sequence[DayReport], final: EngineState) -> Metrics`; `Metrics(final_value, deposited, total_return, annual_return, drawdown, costs, turnover, dividends, trailing_income)`; `DayReport.unit_price: Decimal`; `RunResult.metrics: Metrics`.

- [ ] **Step 1: Branch.** `git switch -c m3/s8-metrics origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_backtest.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
from steadyhand.market import UnsupportedDateError
from steadyhand.money import IDR, Currency, Money
```
with:
```python
from steadyhand.market import UnsupportedDateError
from steadyhand.metrics import measure
from steadyhand.money import IDR, Currency, Money
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    assert {order.instrument for order in result.baseline.reports[0].queued} == {BBCA, BBRI}

```
with:
```python
    assert {order.instrument for order in result.baseline.reports[0].queued} == {BBCA, BBRI}


def test_each_run_carries_its_metrics() -> None:
    result = run(_Source(calm()), chosen=settings(contribution=5_000_000))
    assert result.baseline is not None
    for outcome in (result.run, result.baseline):
        assert outcome.metrics == measure(outcome.reports, outcome.final)
        assert outcome.metrics.deposited == rp(105_000_000)
        assert outcome.metrics.final_value == outcome.reports[-1].value
    assert result.run.metrics != result.baseline.metrics

```

**`tests/engine/test_engine.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python

def test_settings_and_state_check_their_parts() -> None:
```
with:
```python

def test_each_report_carries_the_unit_price_at_the_close() -> None:
    _, first = day_one()
    assert first.unit_price == Decimal(1)
    state, second = day_two()
    # Rp10,000,000 bought 10,000,000 units at 1, so a unit is worth a ten-millionth of the value.
    assert second.unit_price == Decimal(second.value.amount) / Decimal(10_000_000)
    assert second.unit_price != Decimal(1)
    assert second.unit_price == state.units.price


def test_settings_and_state_check_their_parts() -> None:
```

**`tests/engine/test_metrics.py`** (new)

<!-- file: tests/engine/test_metrics.py -->
```python
"""measure: one run's returns, drawdown, costs, turnover and dividends (M3 spec §8).

Every expected number is worked out by hand in the test, never by the code under test.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.metrics import RATIO_PLACES, CostBreakdown, DividendTotals, Drawdown, measure
from steadyhand.money import IDR, Money
from steadyhand.portfolio import Portfolio
from steadyhand.risk import UnitValue
from steadyhand.types import Costs, Fill, Instrument, Order, Side

BBCA = Instrument("BBCA", "IDX", IDR)
MONDAY = date(2025, 7, 7)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def report(
    day: date,
    *,
    value: int = 1_000_000,
    price: str = "1",
    fills: Sequence[Fill] = (),
    paid: Sequence[Entitlement] = (),
    tax: int = 0,
    daily: int = 0,
) -> DayReport:
    return DayReport(
        day=day,
        fills=tuple(fills),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=tuple(paid),
        tax=rp(tax),
        daily_cost=rp(daily),
        deposit=rp(0),
        frozen=(),
        halt=None,
        settled=rp(value),
        unsettled=rp(0),
        holdings_value=rp(0),
        value=rp(value),
        unit_price=Decimal(price),
        warnings=(),
    )


def final(price: str = "1", deposits: Sequence[int] = (1_000_000,)) -> EngineState:
    portfolio = Portfolio.empty(IDR)
    for amount in deposits:
        portfolio = portfolio.deposit(rp(amount), MONDAY)
    units = UnitValue(Decimal(sum(deposits)), Decimal(price), max(Decimal(1), Decimal(price)))
    return EngineState(Holdings(portfolio), units)


def fill(side: Side, quantity: int, price: int, fee: int = 0, levy: int = 0, tax: int = 0) -> Fill:
    order = Order(BBCA, side, quantity, MONDAY)
    return Fill(order, MONDAY, quantity, rp(price), Costs(rp(fee), rp(levy), rp(tax)))


def paid(day: date, gross: int) -> Entitlement:
    return Entitlement(BBCA, day - timedelta(days=20), day, rp(gross))


def days(count: int, start: date = MONDAY) -> list[date]:
    return [start + timedelta(days=n) for n in range(count)]


def test_returns_are_time_weighted_and_compounded_over_calendar_days() -> None:
    # 2021 and 2022 hold 730 calendar days. Growth of 1.21 over two years is 10% a year.
    run = [report(date(2021, 1, 1)), report(date(2022, 12, 31), value=1_815_000, price="1.21")]
    metrics = measure(run, final("1.21", deposits=(1_000_000, 500_000)))
    assert metrics.total_return == Decimal("0.21000000")
    assert metrics.annual_return == Decimal("0.10000000")
    assert metrics.final_value == rp(1_815_000)
    assert metrics.deposited == rp(1_500_000)


def test_only_deposits_count_as_deposited() -> None:
    # A dividend is cash coming in too, but it is a return, not money put in.
    portfolio = Portfolio.empty(IDR).deposit(rp(1_000_000), MONDAY)
    portfolio = portfolio.credit_dividend(rp(50_000), MONDAY)
    state = EngineState(Holdings(portfolio), UnitValue(Decimal(1_000_000)))
    assert measure([report(MONDAY, value=1_050_000)], state).deposited == rp(1_000_000)


def test_a_deposit_is_not_a_gain() -> None:
    # Half as much again was deposited, but the unit value never moved: no return at all.
    run = [report(day, value=1_500_000) for day in days(3)]
    metrics = measure(run, final("1", deposits=(1_000_000, 500_000)))
    assert (metrics.total_return, metrics.annual_return) == (Decimal(0), Decimal(0))


def test_a_total_loss_compounds_to_minus_one() -> None:
    run = [report(MONDAY), report(MONDAY + timedelta(days=9), value=0, price="0")]
    metrics = measure(run, final("0"))
    assert metrics.total_return == Decimal("-1.00000000")
    assert metrics.annual_return == Decimal("-1.00000000")


def test_a_one_day_run_scales_its_day_to_a_year() -> None:
    # 0.1% on one day, compounded over 365: 1.001 ** 365 = 1.44025131...
    metrics = measure([report(MONDAY, price="1.001")], final("1.001"))
    assert metrics.total_return == Decimal("0.00100000")
    assert metrics.annual_return == Decimal("0.44025131")


def test_a_huge_annualised_return_from_a_short_run_is_reported_whole() -> None:
    # 13.5% in one day compounds to 1.135 ** 365 - 1 = 118437561766240817509.438579149... a
    # year (worked out at 60 digits). Its eight places are still exact, and not refused.
    metrics = measure([report(MONDAY, price="1.135")], final("1.135"))
    assert metrics.annual_return == Decimal("118437561766240817509.43857915")


def test_the_drawdown_is_the_deepest_fall_from_a_running_peak() -> None:
    # 1.1 -> 0.99 is a 10% fall; 1.2 -> 1.05 is 12.5%, the deeper one.
    prices = ["1", "1.1", "0.99", "1.2", "1.05"]
    run = [report(day, price=p) for day, p in zip(days(5), prices, strict=True)]
    drawdown = measure(run, final("1.05")).drawdown
    assert drawdown == Drawdown(Decimal("0.12500000"), days(5)[3], days(5)[4])


def test_equal_falls_report_the_first_and_the_peak_starts_at_one() -> None:
    # The run opens at a unit value of 1, so a first day at 0.9 is already a 10% fall.
    prices = ["0.9", "1", "0.9"]
    run = [report(day, price=p) for day, p in zip(days(3), prices, strict=True)]
    drawdown = measure(run, final("0.9")).drawdown
    assert drawdown == Drawdown(Decimal("0.10000000"), MONDAY, MONDAY)


def test_a_run_that_never_falls_has_no_drawdown() -> None:
    run = [report(day, price=p) for day, p in zip(days(3), ["1", "1.01", "1.02"], strict=True)]
    assert measure(run, final("1.02")).drawdown == Drawdown(Decimal(0), MONDAY, MONDAY)


def test_costs_are_split_by_kind() -> None:
    fills = [
        fill(Side.BUY, 100, 9_000, fee=1_350, levy=270),
        fill(Side.SELL, 100, 9_100, 1_365, 273, 910),
    ]
    run = [report(MONDAY, fills=fills[:1]), report(days(2)[1], fills=fills[1:], daily=10_000)]
    costs = measure(run, final()).costs
    assert costs == CostBreakdown(rp(2_715), rp(543), rp(910), rp(10_000))
    assert costs.total == rp(14_168)


def test_turnover_is_half_the_traded_value_over_the_average_value_per_year() -> None:
    # Rp400,000 bought and Rp200,000 sold over two days, against an average value of
    # Rp1,000,000: 600,000 / 2 / 1,000,000 = 0.3 of the portfolio in 2 days, or 54.75 a year.
    fills = [fill(Side.BUY, 100, 4_000), fill(Side.SELL, 100, 2_000)]
    run = [report(MONDAY, fills=fills[:1]), report(days(2)[1], fills=fills[1:])]
    assert measure(run, final()).turnover == Decimal("54.75000000")


def test_the_average_value_uses_every_day() -> None:
    # Values of 1,000,000 and 3,000,000 average 2,000,000: 600,000 / 2 / 2,000,000 over 2 days.
    fills = [fill(Side.BUY, 100, 6_000)]
    run = [report(MONDAY, fills=fills), report(days(2)[1], value=3_000_000)]
    assert measure(run, final()).turnover == Decimal("27.37500000")


def test_turnover_of_a_worthless_portfolio_is_zero() -> None:
    run = [report(day, value=0, price="0") for day in days(2)]
    assert measure(run, final("0")).turnover == Decimal("0E-8")


def test_dividends_and_the_income_of_the_last_365_days() -> None:
    last = date(2022, 1, 10)
    # 365 days ending on 10 January 2022 start on 11 January 2021.
    run = [
        report(date(2021, 1, 10), paid=[paid(date(2021, 1, 10), 1_000)], tax=100),
        report(date(2021, 1, 11), paid=[paid(date(2021, 1, 11), 2_000)], tax=200),
        report(last, paid=[paid(last, 4_000)], tax=400),
    ]
    metrics = measure(run, final())
    assert metrics.dividends == DividendTotals(rp(7_000), rp(700))
    assert metrics.dividends.net == rp(6_300)
    assert metrics.trailing_income == rp(5_400)


def test_a_run_with_no_days_has_no_metrics() -> None:
    with pytest.raises(ValueError, match=r"^a run with no days has no metrics$"):
        measure([], final())


def _deepest_fall(prices: Sequence[Decimal]) -> Decimal:
    """Every (peak, later day) pair checked: an oracle with no running state."""
    worst = Decimal(0)
    for later, price in enumerate(prices):
        for peak in [Decimal(1), *prices[: later + 1]]:
            if peak > 0:
                worst = max(worst, (peak - price) / peak)
    return worst.quantize(RATIO_PLACES)


@given(st.lists(st.decimals(min_value=0, max_value=5, places=3), min_size=1, max_size=30))
def test_the_drawdown_matches_every_pair_checked(prices: list[Decimal]) -> None:
    run = [report(day, price=str(p)) for day, p in zip(days(len(prices)), prices, strict=True)]
    drawdown = measure(run, final(str(prices[-1]))).drawdown
    assert drawdown.depth == _deepest_fall(prices)
    assert Decimal(0) <= drawdown.depth <= Decimal(1)
    assert drawdown.peak <= drawdown.trough
```


- [ ] **Step 3: Write the stubs.** New names only; everything that existed keeps its current body.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
from steadyhand.market import MarketRules, UnsupportedDateError
from steadyhand.money import (
```
with:
```python
from steadyhand.market import MarketRules, UnsupportedDateError
from steadyhand.metrics import (
    RATIO_PLACES,
    YEAR_DAYS,
    CostBreakdown,
    DividendTotals,
    Drawdown,
    Metrics,
    measure,
)
from steadyhand.money import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "PAY_LAG_TRADING_DAYS",
    "STRATEGIES",
    "BacktestResult",
```
with:
```python
    "PAY_LAG_TRADING_DAYS",
    "RATIO_PLACES",
    "STRATEGIES",
    "YEAR_DAYS",
    "BacktestResult",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "CorporateOutcome",
    "Costs",
```
with:
```python
    "CorporateOutcome",
    "CostBreakdown",
    "Costs",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Decision",
    "EngineSettings",
```
with:
```python
    "Decision",
    "DividendTotals",
    "Drawdown",
    "EngineSettings",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Memory",
    "MissingPriceError",
```
with:
```python
    "Memory",
    "Metrics",
    "MissingPriceError",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "backtest",
    "run_day",
```
with:
```python
    "backtest",
    "measure",
    "run_day",
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
from steadyhand.market import MarketRules
from steadyhand.money import Money
```
with:
```python
from steadyhand.market import MarketRules
from steadyhand.metrics import Metrics, measure
from steadyhand.money import Money
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
class RunResult:
    """One strategy's run: every day's report, in order, and the state after the last day."""

```
with:
```python
class RunResult:
    """One strategy's run: every day's report, in order, the state after the last day, and what
    the run achieved (M3 spec §8)."""

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    final: EngineState

```
with:
```python
    final: EngineState
    metrics: Metrics

```

**`packages/steadyhand/src/steadyhand/engine.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
from datetime import date, timedelta

```
with:
```python
from datetime import date, timedelta
from decimal import Decimal

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    value: Money
    warnings: tuple[str, ...]
```
with:
```python
    value: Money
    unit_price: Decimal
    """The price of one unit at today's close, which a deposit leaves unchanged (M3 spec §6.3)."""
    warnings: tuple[str, ...]
```

**`packages/steadyhand/src/steadyhand/metrics.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/metrics.py -->
```python
"""What one backtest run achieved: returns, drawdown, costs, turnover and dividends (M3 spec §8).

Money stays integer minor units. Every ratio is a ``Decimal`` worked out at 50 significant
digits and then rounded half-even to eight decimal places, so the same run always reports the
same digits, and they are exact while the whole part has fewer than 40 digits. A power is taken
with ``Decimal.ln`` and ``Decimal.exp``, never with ``float``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand.engine import DayReport, EngineState
from steadyhand.money import Money
from steadyhand.portfolio import MovementKind
from steadyhand.types import Fill

RATIO_PLACES = Decimal("0.00000001")
"""Every ratio is reported to eight decimal places."""
YEAR_DAYS = 365
"""Calendar days in the year that annual figures are scaled to, and in the trailing year."""
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class Drawdown:
    """The run's deepest fall in the unit value, from ``peak`` to ``trough``, as a fraction.

    A run whose unit value never fell has a depth of 0, with both dates on its first day.
    """

    depth: Decimal
    peak: date
    trough: date


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Trading costs by kind: broker fees, exchange levies, sale tax and the daily stamp duty."""

    fee: Money
    levy: Money
    sale_tax: Money
    daily: Money

    @property
    def total(self) -> Money:
        raise NotImplementedError("CostBreakdown.total")


@dataclass(frozen=True, slots=True)
class DividendTotals:
    """Cash dividends paid during the run, and the tax booked on them."""

    gross: Money
    tax: Money

    @property
    def net(self) -> Money:
        raise NotImplementedError("DividendTotals.net")


@dataclass(frozen=True, slots=True)
class Metrics:
    """One run's results (M3 spec §8).

    ``total_return`` is time-weighted: the unit value's change, so deposits are not gains.
    ``annual_return`` compounds it over the run's calendar days. ``turnover`` is the share of
    the average portfolio traded in a year. ``trailing_income`` is the net dividend income paid
    in the last ``YEAR_DAYS`` calendar days of the run.
    """

    final_value: Money
    deposited: Money
    total_return: Decimal
    annual_return: Decimal
    drawdown: Drawdown
    costs: CostBreakdown
    turnover: Decimal
    dividends: DividendTotals
    trailing_income: Money


def measure(reports: Sequence[DayReport], final: EngineState) -> Metrics:
    """The metrics of a run whose day reports, in order, are *reports* and last state *final*."""
    raise NotImplementedError("measure")


def _rounded(value: Decimal) -> Decimal:
    """*value* to eight places, in a context wide enough for its whole part, so that a huge
    annualised return from a short run is reported rather than refused."""
    raise NotImplementedError("_rounded")


def _annual(growth: Decimal, days: int) -> Decimal:
    """Compound annual return: ``growth`` over ``days`` calendar days, scaled to a year."""
    raise NotImplementedError("_annual")


def _drawdown(reports: Sequence[DayReport]) -> Drawdown:
    """The deepest fall from a running peak of the unit value, which starts at 1."""
    raise NotImplementedError("_drawdown")


def _turnover(reports: Sequence[DayReport], fills: Sequence[Fill], days: int) -> Decimal:
    """(Gross bought + gross sold) / 2 / the average daily value, scaled to a year."""
    raise NotImplementedError("_turnover")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=729 failed=50 -->
Expected: 729 run, 50 failed: 16 with `NotImplementedError`, and 34 because `DayReport` now requires `unit_price` while `run_day` keeps its old body until Step 5 (scope decision 10): 33 raise `TypeError`, and `test_settings_and_state_check_their_parts` fails its `pytest.raises(TypeError, match=…)` on that `TypeError`'s message. None passes against the stubs.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
        reports.append(report)
    return RunResult(strategy.name, tuple(reports), state)

```
with:
```python
        reports.append(report)
    return RunResult(strategy.name, tuple(reports), state, measure(reports, state))

```

**`packages/steadyhand/src/steadyhand/engine.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        value=value,
        warnings=(*corporate.warnings, *warnings),
```
with:
```python
        value=value,
        unit_price=units.price,
        warnings=(*corporate.warnings, *warnings),
```

**`packages/steadyhand/src/steadyhand/metrics.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/metrics.py -->
```python
"""What one backtest run achieved: returns, drawdown, costs, turnover and dividends (M3 spec §8).

Money stays integer minor units. Every ratio is a ``Decimal`` worked out at 50 significant
digits and then rounded half-even to eight decimal places, so the same run always reports the
same digits, and they are exact while the whole part has fewer than 40 digits. A power is taken
with ``Decimal.ln`` and ``Decimal.exp``, never with ``float``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal

from steadyhand.engine import DayReport, EngineState
from steadyhand.money import Money
from steadyhand.portfolio import MovementKind
from steadyhand.types import Fill

RATIO_PLACES = Decimal("0.00000001")
"""Every ratio is reported to eight decimal places."""
YEAR_DAYS = 365
"""Calendar days in the year that annual figures are scaled to, and in the trailing year."""
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class Drawdown:
    """The run's deepest fall in the unit value, from ``peak`` to ``trough``, as a fraction.

    A run whose unit value never fell has a depth of 0, with both dates on its first day.
    """

    depth: Decimal
    peak: date
    trough: date


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Trading costs by kind: broker fees, exchange levies, sale tax and the daily stamp duty."""

    fee: Money
    levy: Money
    sale_tax: Money
    daily: Money

    @property
    def total(self) -> Money:
        return self.fee + self.levy + self.sale_tax + self.daily


@dataclass(frozen=True, slots=True)
class DividendTotals:
    """Cash dividends paid during the run, and the tax booked on them."""

    gross: Money
    tax: Money

    @property
    def net(self) -> Money:
        return self.gross - self.tax


@dataclass(frozen=True, slots=True)
class Metrics:
    """One run's results (M3 spec §8).

    ``total_return`` is time-weighted: the unit value's change, so deposits are not gains.
    ``annual_return`` compounds it over the run's calendar days. ``turnover`` is the share of
    the average portfolio traded in a year. ``trailing_income`` is the net dividend income paid
    in the last ``YEAR_DAYS`` calendar days of the run.
    """

    final_value: Money
    deposited: Money
    total_return: Decimal
    annual_return: Decimal
    drawdown: Drawdown
    costs: CostBreakdown
    turnover: Decimal
    dividends: DividendTotals
    trailing_income: Money


def measure(reports: Sequence[DayReport], final: EngineState) -> Metrics:
    """The metrics of a run whose day reports, in order, are *reports* and last state *final*."""
    if not reports:
        msg = "a run with no days has no metrics"
        raise ValueError(msg)
    first, last = reports[0].day, reports[-1].day
    days = (last - first).days + 1
    currency = final.holdings.portfolio.currency
    nothing = Money.zero(currency)
    deposited = sum(
        (m.amount for m in final.holdings.portfolio.ledger if m.kind is MovementKind.DEPOSIT),
        nothing,
    )
    fills = [fill for report in reports for fill in report.fills]
    costs = CostBreakdown(
        sum((fill.costs.fee for fill in fills), nothing),
        sum((fill.costs.levy for fill in fills), nothing),
        sum((fill.costs.tax for fill in fills), nothing),
        sum((report.daily_cost for report in reports), nothing),
    )
    dividends = DividendTotals(
        sum((e.gross for report in reports for e in report.paid), nothing),
        sum((report.tax for report in reports), nothing),
    )
    since = last - timedelta(days=YEAR_DAYS - 1)
    trailing = [report for report in reports if report.day >= since]
    trailing_income = sum((e.gross for report in trailing for e in report.paid), nothing) - sum(
        (report.tax for report in trailing), nothing
    )
    return Metrics(
        final_value=reports[-1].value,
        deposited=deposited,
        total_return=_rounded(_CONTEXT.subtract(final.units.price, Decimal(1))),
        annual_return=_annual(final.units.price, days),
        drawdown=_drawdown(reports),
        costs=costs,
        turnover=_turnover(reports, fills, days),
        dividends=dividends,
        trailing_income=trailing_income,
    )


def _rounded(value: Decimal) -> Decimal:
    """*value* to eight places, in a context wide enough for its whole part, so that a huge
    annualised return from a short run is reported rather than refused."""
    wide = Context(prec=max(_CONTEXT.prec, value.adjusted() + 1 + 8), rounding=ROUND_HALF_EVEN)
    return value.quantize(RATIO_PLACES, context=wide)


def _annual(growth: Decimal, days: int) -> Decimal:
    """Compound annual return: ``growth`` over ``days`` calendar days, scaled to a year."""
    if growth == 0:
        return _rounded(Decimal(-1))
    exponent = _CONTEXT.divide(_CONTEXT.multiply(growth.ln(_CONTEXT), YEAR_DAYS), days)
    return _rounded(_CONTEXT.subtract(exponent.exp(_CONTEXT), Decimal(1)))


def _drawdown(reports: Sequence[DayReport]) -> Drawdown:
    """The deepest fall from a running peak of the unit value, which starts at 1."""
    peak, peak_day = Decimal(1), reports[0].day
    deepest = Drawdown(Decimal(0), peak_day, peak_day)
    for report in reports:
        if report.unit_price > peak:
            peak, peak_day = report.unit_price, report.day
            continue
        depth = _CONTEXT.divide(_CONTEXT.subtract(peak, report.unit_price), peak)
        if depth > deepest.depth:
            deepest = Drawdown(depth, peak_day, report.day)
    return Drawdown(_rounded(deepest.depth), deepest.peak, deepest.trough)


def _turnover(reports: Sequence[DayReport], fills: Sequence[Fill], days: int) -> Decimal:
    """(Gross bought + gross sold) / 2 / the average daily value, scaled to a year."""
    traded = sum(fill.gross.amount for fill in fills)
    average = _CONTEXT.divide(sum(report.value.amount for report in reports), len(reports))
    if average == 0:
        return _rounded(Decimal(0))
    yearly = _CONTEXT.divide(_CONTEXT.multiply(traded, YEAR_DAYS), _CONTEXT.multiply(2, days))
    return _rounded(_CONTEXT.divide(yearly, average))
```


- [ ] **Step 6: Run the whole gate** as in Task 7.

<!-- check: gate total=729 passed=729 -->
Expected: every command exits 0; 729 passed, 9 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M45–M54; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S8 metrics`).

---

### Task 9: S9 The golden backtest and the truncation check

**Acceptance criteria (story text):**
1. `scripts/record_golden.py` runs `buy-and-hold` from 2021-02-01 to 2022-01-31 over ASII, BBCA, BBRI, TLKM and UNVR (scope decision 3) with Rp100,000,000 and 25% a stock, through the real `YahooDataSource` (replaying Task 0's recordings and refusing any range outside them), `CachedDataSource`, `IdxMarketRules` and engine, and writes every day's value and unit price, every fill, dividend, position, warning and metric to `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json`.
2. The golden test requires the run to equal the stored file exactly, and the script's output to equal it byte for byte; a change to the numbers comes with a re-recording and a reviewed diff.
3. The window is shown to hold what it was chosen for: BBCA's 1-for-5 split (every share bought became five), dividends from ASII, BBCA, TLKM and UNVR, and BBRI's 146 refused days.
4. The truncation check: every registered strategy, run to D and to D plus 20 trading days, gives identical reports up to D, for D on 2021-04-07, 2021-10-12 and 2021-11-29 (the days before BBCA's dividend ex-date, its split and UNVR's ex-date).
5. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M55–M56 each turn the whole suite red.

**Files:**
- Create: `scripts/record_golden.py`, `tests/golden/test_golden_backtest.py`, `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` (generated)

**Interfaces:**
- Consumes: Task 7's `backtest`, `Market`, `BacktestSettings`; Task 8's `Metrics`; M2's `YahooDataSource(download=…, sleep=…)`, `CachedDataSource(upstream, cache, today=…)`, `BarCache`, `Lq45Universe`; Task 0's fixtures.
- Produces: `record_golden.run(folder, strategy="buy-and-hold", end=END) -> BacktestResult`, `summary(result) -> dict`, `record(folder, golden=GOLDEN) -> Path`, `main(argv) -> int`.

- [ ] **Step 1: Branch.** `git switch -c m3/s9-golden origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/golden/test_golden_backtest.py`** (new)

<!-- file: tests/golden/test_golden_backtest.py -->
```python
"""The golden backtest, and the look-ahead truncation check (M3 spec §9, core spec §10.3).

``scripts/record_golden.py`` runs ``buy-and-hold`` over a year of real, recorded Yahoo data
through the real ``YahooDataSource``, ``CachedDataSource``, ``IdxMarketRules`` and engine. Its
result must equal the stored file exactly, in integer rupiah. After a change that moves the
numbers on purpose, re-record with ``uv run python scripts/record_golden.py`` and review the diff.

The truncation check: every registered strategy, run to day D and to D plus 20 trading days,
makes the same decisions up to D, so no decision can have read a later price.
"""

import json
from datetime import date
from functools import cache
from pathlib import Path

import pytest
from record_golden import GOLDEN, main, record, run, summary

from steadyhand import STRATEGIES
from steadyhand_idx import IdxMarketRules


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def test_buy_and_hold_reproduces_the_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert summary(run(tmp_path)) == stored


def test_the_recorder_writes_the_stored_file_byte_for_byte(tmp_path: Path) -> None:
    written = record(tmp_path / "cache", tmp_path / "golden.json")
    assert written.read_bytes() == GOLDEN.read_bytes()


def test_the_recorder_takes_no_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["extra"]) == 2
    assert "uv run python scripts/record_golden.py" in capsys.readouterr().out


def test_the_window_holds_the_events_it_was_chosen_for(tmp_path: Path) -> None:
    """The golden file is only worth pinning if the run meets a split, dividends and refusals."""
    result = run(tmp_path)
    held = {p.instrument.symbol: p.quantity for p in result.run.final.holdings.portfolio.positions}
    # BBCA's 1-for-5 split on 13 October 2021: every share bought became five.
    bought = sum(
        fill.quantity
        for report in result.run.reports
        for fill in report.fills
        if fill.order.instrument.symbol == "BBCA"
    )
    assert bought > 0
    assert held["BBCA"] == 5 * bought
    paid = {e.instrument.symbol for report in result.run.reports for e in report.paid}
    assert paid == {"ASII", "BBCA", "TLKM", "UNVR"}
    assert "BBRI" not in held
    assert result.warnings[0].startswith(
        "BBRI: the data source refused 146 day(s) (2021-02-01 to 2021-09-07),"
    )


def test_a_fetch_outside_the_recording_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^ASII\.JK: the fixture covers 2021-02-01 to 2022-01-31"):
        run(tmp_path, end=date(2022, 2, 7))


@pytest.mark.parametrize("strategy", sorted(STRATEGIES))
@pytest.mark.parametrize("cut", [date(2021, 4, 7), date(2021, 10, 12), date(2021, 11, 29)])
def test_a_run_to_day_d_decides_as_a_longer_run_did_up_to_d(
    strategy: str, cut: date, tmp_path: Path
) -> None:
    # The cuts fall on the day before BBCA's dividend ex-date, the day before its split, and the
    # day before UNVR's ex-date; each longer run goes on for twenty more trading days.
    short = run(tmp_path / "short", strategy, cut)
    longer = run(tmp_path / "long", strategy, _trading_days_after(cut, 20))
    count = len(short.run.reports)
    assert short.run.reports[-1].day == cut
    assert len(longer.run.reports) == count + 20
    assert longer.run.reports[:count] == short.run.reports


def _trading_days_after(day: date, count: int) -> date:
    found = 0
    while found < count:
        day = date.fromordinal(day.toordinal() + 1)
        found += rules().is_trading_day(day)
    return day
```


- [ ] **Step 3: Write the stubs.**

**`scripts/record_golden.py`** (new, as stubs)

<!-- file: scripts/record_golden.py -->
```python
"""Record the golden backtest's results (M3 spec §9).

    uv run python scripts/record_golden.py

runs ``buy-and-hold`` over the recorded Yahoo fixtures for ASII, BBCA, BBRI, TLKM and UNVR from
1 February 2021 to 31 January 2022, and writes everything the golden test pins to
``tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json``. The window holds BBCA's
1-for-5 split, seven cash dividends, and 146 days of BBRI prices that Yahoo cannot unadjust (its
rights issue). Run it only after a change that moves the numbers on purpose, and review the diff:
the file is never edited by hand.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestResult,
    BacktestSettings,
    EngineSettings,
    Market,
    Money,
    RiskLimits,
    backtest,
)
from steadyhand_idx import IdxMarketRules
from steadyhand_idx.cache import BarCache, CachedDataSource
from steadyhand_idx.universe import Lq45Membership, Lq45Record, Lq45Universe
from steadyhand_idx.yahoo import YahooDataSource, YahooHistory, history_from_json

TESTS = Path(__file__).resolve().parents[1] / "tests"
FIXTURES = TESTS / "fixtures" / "yahoo"
GOLDEN = TESTS / "fixtures" / "golden" / "buy-and-hold_2021-02-01_2022-01-31.json"
START, END = date(2021, 2, 1), date(2022, 1, 31)
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
RECORDED = date(2026, 9, 26)
"""The day the fixtures were recorded; the cache treats it as today."""


def settings() -> BacktestSettings:
    """Rp100,000,000, and 25% a stock so that five stocks can be fully invested (M3 spec §9)."""
    raise NotImplementedError("settings")


def recorded(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer. A range outside the recording is refused, never invented."""
    raise NotImplementedError("recorded")


def universe() -> Lq45Universe:
    """The five stocks as the whole universe. It is a test selection, not an LQ45 list: the
    loader takes only full lists of 45, and steadyhand ships none (t-lq45.md §5)."""
    raise NotImplementedError("universe")


def run(folder: Path, strategy: str = "buy-and-hold", end: date = END) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules."""
    raise NotImplementedError("run")


def _no_wait(seconds: float) -> None:
    raise NotImplementedError("_no_wait")


def summary(result: BacktestResult) -> dict[str, object]:
    """Everything the golden file pins, as JSON values."""
    raise NotImplementedError("summary")


def record(folder: Path, golden: Path = GOLDEN) -> Path:
    """Run the golden backtest with its cache in *folder*, and write its summary to *golden*."""
    raise NotImplementedError("record")


def main(argv: list[str]) -> int:
    raise NotImplementedError("main")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=737 failed=8 -->
Expected: 737 run, 8 failed: 7 with `NotImplementedError`, and `test_buy_and_hold_reproduces_the_stored_results_exactly` with `FileNotFoundError`, because the golden file is generated in Step 5. None passes against the stubs.

- [ ] **Step 5: Implement, then generate the golden file.**

**`scripts/record_golden.py`** (replaces the stubs)

<!-- file: scripts/record_golden.py -->
```python
"""Record the golden backtest's results (M3 spec §9).

    uv run python scripts/record_golden.py

runs ``buy-and-hold`` over the recorded Yahoo fixtures for ASII, BBCA, BBRI, TLKM and UNVR from
1 February 2021 to 31 January 2022, and writes everything the golden test pins to
``tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json``. The window holds BBCA's
1-for-5 split, seven cash dividends, and 146 days of BBRI prices that Yahoo cannot unadjust (its
rights issue). Run it only after a change that moves the numbers on purpose, and review the diff:
the file is never edited by hand.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestResult,
    BacktestSettings,
    EngineSettings,
    Market,
    Money,
    RiskLimits,
    backtest,
)
from steadyhand_idx import IdxMarketRules
from steadyhand_idx.cache import BarCache, CachedDataSource
from steadyhand_idx.universe import Lq45Membership, Lq45Record, Lq45Universe
from steadyhand_idx.yahoo import YahooDataSource, YahooHistory, history_from_json

TESTS = Path(__file__).resolve().parents[1] / "tests"
FIXTURES = TESTS / "fixtures" / "yahoo"
GOLDEN = TESTS / "fixtures" / "golden" / "buy-and-hold_2021-02-01_2022-01-31.json"
START, END = date(2021, 2, 1), date(2022, 1, 31)
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
RECORDED = date(2026, 9, 26)
"""The day the fixtures were recorded; the cache treats it as today."""


def settings() -> BacktestSettings:
    """Rp100,000,000, and 25% a stock so that five stocks can be fully invested (M3 spec §9)."""
    limits = RiskLimits(max_weight=Decimal("0.25"))
    return BacktestSettings(Money(100_000_000, IDR), EngineSettings(limits=limits))


def recorded(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer. A range outside the recording is refused, never invented."""
    if start < START or end > END:
        msg = f"{ticker}: the fixture covers {START} to {END}, not {start} to {end}"
        raise ValueError(msg)
    return history_from_json(FIXTURES / f"{ticker}_{START.isoformat()}_{END.isoformat()}.json")


def universe() -> Lq45Universe:
    """The five stocks as the whole universe. It is a test selection, not an LQ45 list: the
    loader takes only full lists of 45, and steadyhand ships none (t-lq45.md §5)."""
    record = Lq45Record(
        START,
        START,
        "steadyhand golden test: five stocks chosen for their events, not an LQ45 list",
        "review",
        frozenset(STOCKS),
    )
    return Lq45Universe(Lq45Membership([record]))


def run(folder: Path, strategy: str = "buy-and-hold", end: date = END) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules."""
    folder.mkdir(parents=True, exist_ok=True)
    yahoo = YahooDataSource(download=recorded, sleep=_no_wait)
    with BarCache(folder / "bars.sqlite") as store:
        source = CachedDataSource(yahoo, store, today=lambda: RECORDED)
        market = Market(universe(), source, IdxMarketRules())
        return backtest(STRATEGIES[strategy](), market, START, end, settings())


def _no_wait(seconds: float) -> None:
    del seconds


def summary(result: BacktestResult) -> dict[str, object]:
    """Everything the golden file pins, as JSON values."""
    outcome, metrics = result.run, result.run.metrics
    portfolio = outcome.final.holdings.portfolio
    return {
        "window": [result.start.isoformat(), result.end.isoformat()],
        "strategy": outcome.strategy,
        "days": [[r.day.isoformat(), r.value.amount, str(r.unit_price)] for r in outcome.reports],
        "fills": [
            [
                f.day.isoformat(),
                f.order.instrument.symbol,
                f.order.side.value,
                f.quantity,
                f.price.amount,
                f.costs.fee.amount,
                f.costs.levy.amount,
                f.costs.tax.amount,
            ]
            for r in outcome.reports
            for f in r.fills
        ],
        "dividends": [
            [r.day.isoformat(), e.instrument.symbol, e.ex_date.isoformat(), e.gross.amount]
            for r in outcome.reports
            for e in r.paid
        ],
        "positions": {p.instrument.symbol: p.quantity for p in portfolio.positions},
        "cash": portfolio.cash_balance().amount,
        "halt": None
        if outcome.halt is None
        else [outcome.halt.day.isoformat(), outcome.halt.cause],
        "warnings": [*result.warnings, *outcome.warnings],
        "metrics": {
            "final_value": metrics.final_value.amount,
            "deposited": metrics.deposited.amount,
            "total_return": str(metrics.total_return),
            "annual_return": str(metrics.annual_return),
            "drawdown": [
                str(metrics.drawdown.depth),
                metrics.drawdown.peak.isoformat(),
                metrics.drawdown.trough.isoformat(),
            ],
            "costs": {
                "fee": metrics.costs.fee.amount,
                "levy": metrics.costs.levy.amount,
                "sale_tax": metrics.costs.sale_tax.amount,
                "daily": metrics.costs.daily.amount,
            },
            "turnover": str(metrics.turnover),
            "dividends": {
                "gross": metrics.dividends.gross.amount,
                "tax": metrics.dividends.tax.amount,
            },
            "trailing_income": metrics.trailing_income.amount,
        },
    }


def record(folder: Path, golden: Path = GOLDEN) -> Path:
    """Run the golden backtest with its cache in *folder*, and write its summary to *golden*."""
    text = json.dumps(summary(run(folder)), indent=1, sort_keys=True) + "\n"
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(text, encoding="utf-8")
    return golden


def main(argv: list[str]) -> int:
    if argv:
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as scratch:
        print(record(Path(scratch)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Generate `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json sha256=649d002ac97185c29b95586f60af6adb79b1c078ffdf5e656a045b2af420e1d3 -->
```bash
uv run python scripts/record_golden.py
```


- [ ] **Step 6: Review the golden numbers before accepting them.** Each dividend is the holding times the per-share amount (BBCA 700 × 432 = 302,400), the tax is 10%, each pay date is 14 trading days after its ex-date, BBCA's 700 shares become 3,500 at the split, and BBRI is never bought.
- [ ] **Step 7: Run the whole gate** as in Task 7.

<!-- check: gate total=737 passed=737 -->
Expected: every command exits 0; 737 passed, 9 deselected, 100% branch coverage.

- [ ] **Step 8: Mutations.** Run M55–M56; each must turn the whole suite red with the total unchanged.
- [ ] **Step 9: Commit, push and merge** (`test(engine): S9 golden backtest …`).

---

### Task 10: S10 The performance test and a linear-time cash ledger

**Acceptance criteria (story text):**
1. `tests/perf/test_performance.py`, marked `perf`: `equal-weight` (rebalanced daily) and the baseline over every weekday from 2016-01-04 to 2025-12-31, 45 synthetic stocks from a fixed seed with integer arithmetic, a monthly contribution and one June dividend a year, under `_PlainRules` (a market that is not IDX), finish in under 30 seconds; the test also checks that both runs traded, received dividends and never halted.
2. The `perf` marker is registered and deselected by default; CI's `test` jobs run it in their own step, `uv run --locked pytest -W error -m perf -p no:cacheprovider`, without coverage (scope decision 12).
3. `Portfolio` keeps its balance and the movements that settle after its last day; `cash_balance`, `settled_cash` and `spendable_cash` from the last day onwards read them, an earlier day reads the whole ledger, and booking checks only the new movement (scope decision 13). A hypothesis property compares every figure, on days before, on and after the last, with the whole ledger read directly.
4. Every quality gate is green at 100% branch coverage, the perf step passes, and mutations M57–M59 each turn the whole suite red.

**Files:**
- Modify: `packages/steadyhand/src/steadyhand/portfolio.py`, `pyproject.toml`, `.github/workflows/ci.yml`
- Test: create `tests/perf/test_performance.py`; modify `tests/engine/test_portfolio_properties.py`

**Interfaces:**
- Consumes: Tasks 7 and 8; M3a's `MarketRules` protocol.
- Produces: nothing new in the public API; `Portfolio`'s behaviour is unchanged.

- [ ] **Step 1: Branch.** `git switch -c m3/s10-performance origin/develop`

- [ ] **Step 2: Write the failing tests, the stubs, and the marker registration.** The new `Portfolio` helpers are stubbed; every existing method keeps its body, so the old ledger scan still answers.

**`tests/engine/test_portfolio_properties.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_portfolio_properties.py -->
Replace:
```python
    InsufficientSharesError,
    NegativeProceedsError,
```
with:
```python
    InsufficientSharesError,
    MovementKind,
    NegativeProceedsError,
```

<!-- edit: tests/engine/test_portfolio_properties.py -->
Replace:
```python
    assert after.position(stock) is None
```
with:
```python
    assert after.position(stock) is None


def _settled(portfolio: Portfolio, on: date) -> Money:
    """The ledger read whole: credits and debits that have settled by *on*."""
    return sum((m.amount for m in portfolio.ledger if m.settles_on <= on), start=rp(0))


def _spendable(portfolio: Portfolio, on: date) -> Money:
    """The ledger read whole: every debit, and the credits that have settled by *on*."""
    kept = (m.amount for m in portfolio.ledger if m.amount.amount < 0 or m.settles_on <= on)
    return sum(kept, start=rp(0))


LATER_STEP = st.tuples(
    st.sampled_from(["deposit", "buy", "sell", "dividend", "duty-later"]),
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=0, max_value=len(STOCKS) - 1),
    st.integers(min_value=1, max_value=5_000),
    st.integers(min_value=50, max_value=20_000),
    st.integers(min_value=0, max_value=50_000),
)


@given(st.lists(LATER_STEP, max_size=40))
def test_the_kept_totals_agree_with_the_whole_ledger_on_every_day(steps: list[Step]) -> None:
    portfolio = Portfolio.empty(IDR)
    today = D0
    for kind, forward, stock_index, shares, price, fee in steps:
        today += timedelta(days=forward)
        stock = STOCKS[stock_index]
        with suppress(InsufficientCashError, InsufficientSharesError, NegativeProceedsError):
            if kind == "deposit":
                portfolio = portfolio.deposit(rp(shares * 1_000), today)
            elif kind == "dividend":
                portfolio = portfolio.credit_dividend(rp(shares), today)
            elif kind == "duty-later":
                later = today + timedelta(days=2)
                portfolio = portfolio.charge(
                    MovementKind.DAILY_COST, rp(10_000), today, settles_on=later
                )
            else:
                side = Side.BUY if kind == "buy" else Side.SELL
                fill = make_fill(side, stock, shares, price, fee, today)
                portfolio = portfolio.apply_fill(fill, today + timedelta(days=2))
        assert portfolio.cash_balance() == sum((m.amount for m in portfolio.ledger), start=rp(0))
        for offset in range(-4, 4):
            probe = today + timedelta(days=offset)
            assert portfolio.settled_cash(probe) == _settled(portfolio, probe)
            assert portfolio.spendable_cash(probe) == _spendable(portfolio, probe)
        rebuilt = Portfolio(portfolio.currency, portfolio.positions, portfolio.ledger)
        assert rebuilt == portfolio
        assert rebuilt.spendable_cash(today) == portfolio.spendable_cash(today)
```

**`tests/perf/test_performance.py`** (new)

<!-- file: tests/perf/test_performance.py -->
```python
"""A ten-year backtest over 45 stocks finishes in under 30 seconds (core spec §10.4, M3 §9).

The prices are synthetic, generated here from a fixed seed with integer arithmetic only: ten
years of real fixtures would bloat the repository. IDX's rule data does not reach ten years
ahead, so the run uses ``_PlainRules``, a small market written for this test, which also shows
the engine running a market other than IDX. The strategy rebalances to equal weights every day,
so the strategy's run and the baseline's both trade, value and size every day.
"""

import time
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal

import pytest

from steadyhand import (
    IDR,
    BacktestSettings,
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Currency,
    Decision,
    EngineSettings,
    Instrument,
    Market,
    MarketView,
    Memory,
    Money,
    PortfolioView,
    Rounding,
    Side,
    UnsupportedDateError,
    backtest,
)

SEED = 20260926
STOCKS = 45
START, END = date(2016, 1, 4), date(2025, 12, 31)
BUDGET_SECONDS = 30


class _PlainRules:
    """A market open on weekdays, with one-rupiah ticks, lots of 100 and flat-rate costs."""

    @property
    def currency(self) -> Currency:
        return IDR

    @property
    def verified_from(self) -> date:
        return date(2000, 1, 3)

    def require_supported(self, day: date) -> None:
        if day < self.verified_from:
            msg = f"the plain market opens on {self.verified_from.isoformat()}"
            raise UnsupportedDateError(msg)

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        return price

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        return reference.times(Decimal("0.65"), Rounding.UP), reference.times(
            Decimal("1.35"), Rounding.DOWN
        )

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        fee = gross.times(Decimal("0.0015"), Rounding.UP)
        tax = gross.times(Decimal("0.001"), Rounding.UP) if side is Side.SELL else Money.zero(IDR)
        return Costs(fee, Money.zero(IDR), tax)

    def daily_costs(self, traded: Money, on: date) -> Money:
        return Money(10_000 if traded.amount else 0, IDR)

    def settlement_date(self, trade_date: date) -> date:
        day, left = trade_date, 2
        while left:
            day += timedelta(days=1)
            left -= self.is_trading_day(day)
        return day

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return gross.times(Decimal("0.1"), Rounding.UP)

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5


class _Lcg:
    """A 64-bit linear congruential generator (Knuth's MMIX constants): integers only, and the
    same sequence on every Python version, which ``random`` does not promise."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def randint(self, low: int, high: int) -> int:
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) % 2**64
        return low + (self._state >> 33) % (high - low + 1)


class _Synthetic:
    """Ten years of daily bars and one June dividend a year for each stock, from ``SEED``."""

    def __init__(self) -> None:
        rng = _Lcg(SEED)
        self.stocks = [Instrument(f"S{n:03d}", "PLAIN", IDR) for n in range(STOCKS)]
        self._bars: dict[Instrument, list[Bar]] = {}
        self._actions: dict[Instrument, list[CorporateAction]] = {}
        days = [START + timedelta(days=n) for n in range((END - START).days + 1)]
        trading = [day for day in days if day.weekday() < 5]
        for stock in self.stocks:
            close = rng.randint(1_000, 20_000)
            bars: list[Bar] = []
            actions: list[CorporateAction] = []
            for day in trading:
                opening = close * (1_000 + rng.randint(-10, 10)) // 1_000
                close = max(50, opening * (1_000 + rng.randint(-20, 21)) // 1_000)
                high, low = max(opening, close), min(opening, close)
                high_, low_ = Money(high, IDR), Money(low, IDR)
                bars.append(
                    Bar(stock, day, Money(opening, IDR), high_, low_, Money(close, IDR), 10**8)
                )
                if day.month == 6 and day.day == 15:
                    actions.append(CashDividend(stock, day, Decimal(close // 50)))
            self._bars[stock] = bars
            self._actions[stock] = actions

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return [bar for bar in self._bars[instrument] if start <= bar.day <= end]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return [a for a in self._actions[instrument] if start <= a.ex_date <= end]


class _All:
    """Every synthetic stock, every day, with nothing excluded and no gaps."""

    def __init__(self, stocks: Sequence[Instrument]) -> None:
        self._stocks = frozenset(stocks)

    def members_on(self, day: date) -> frozenset[Instrument]:
        return self._stocks

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return {}

    def first_day(self) -> date:
        return START

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        return ()


class _EqualWeight:
    """Every buyable stock at the same weight, rebalanced every day."""

    @property
    def name(self) -> str:
        return "equal-weight"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        buyable = view.tradable.buyable
        if not buyable:
            return Decision({})
        each = Decimal(1) / len(buyable)
        return Decision(
            {stock: each.quantize(Decimal("0.0001"), Rounding.DOWN.value) for stock in buyable}
        )


@pytest.mark.perf
def test_ten_years_of_45_stocks_run_inside_the_budget() -> None:
    source = _Synthetic()
    settings = BacktestSettings(
        Money(1_000_000_000, IDR), EngineSettings(monthly_contribution=Money(10_000_000, IDR))
    )
    market = Market(_All(source.stocks), source, _PlainRules())
    began = time.perf_counter()
    result = backtest(_EqualWeight(), market, START, END, settings)
    seconds = time.perf_counter() - began
    assert result.baseline is not None
    runs = (result.run, result.baseline)
    # The run did the work it is timed on: every weekday, trades and dividends in both runs.
    weekdays = sum((START + timedelta(days=n)).weekday() < 5 for n in range((END - START).days + 1))
    assert [len(run.reports) for run in runs] == [weekdays, weekdays]
    assert all(run.halt is None for run in runs)
    assert all(sum(len(r.fills) for r in run.reports) > 45 for run in runs)
    assert all(run.metrics.dividends.gross.amount > 0 for run in runs)
    assert seconds < BUDGET_SECONDS, f"took {seconds:.1f} s, over the {BUDGET_SECONDS} s budget"
```


**`packages/steadyhand/src/steadyhand/portfolio.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
``spendable_cash`` subtracts every debit at once and adds a credit only once it has settled.
"""
```
with:
```python
``spendable_cash`` subtracts every debit at once and adds a credit only once it has settled.

Each snapshot also keeps its cash balance and the few movements that settle after its last day,
so the day's cash is read without summing the ledger, and booking a movement checks only that
movement. A ten-year backtest books over a hundred thousand of them (M3 spec §9).
"""
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
```
with:
```python
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
    ledger: tuple[CashMovement, ...] = ()

```
with:
```python
    ledger: tuple[CashMovement, ...] = ()
    _balance: Money = field(init=False, repr=False, compare=False)
    """The sum of every movement in the ledger."""
    _open: tuple[CashMovement, ...] = field(init=False, repr=False, compare=False)
    """Every movement that settles after the last day, in ledger order."""

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python

    @classmethod
```
with:
```python

    def _check_positions(self) -> None:
        raise NotImplementedError("Portfolio._check_positions")

    @classmethod
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
        return sum(kept, start=Money.zero(self.currency))

```
with:
```python
        return sum(kept, start=Money.zero(self.currency))

    def _settling_after(self, on: date, *, credits_only: bool) -> Money:
        """The movements (or only the credits) that settle after *on*.

        From *on* the last day onwards those are all among ``_open``; an earlier day needs the
        whole ledger.
        """
        raise NotImplementedError("Portfolio._settling_after")

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
        return Portfolio(self.currency, tuple(sorted(others, key=_sort_key)), ledger)
```
with:
```python
        return Portfolio(self.currency, tuple(sorted(others, key=_sort_key)), ledger)

    def _next(self, positions: tuple[Position, ...], movement: CashMovement | None) -> Portfolio:
        """This snapshot with *positions* held and *movement* booked after the rest.

        Only what is new is checked. Every caller has already refused a movement dated before
        the last or in another currency, so the ledger holds without reading it again.
        """
        raise NotImplementedError("Portfolio._next")
```

**`pyproject.toml`** (changed; configuration, needed to collect the tests: 1 edit)

<!-- edit: pyproject.toml -->
Replace:
```toml
pythonpath = ["scripts"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra", "-m", "not live"]
markers = [
    "live: talks to Yahoo; run by the daily yahoo-shape workflow with -m live, never on a PR",
]
```
with:
```toml
pythonpath = ["scripts"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra", "-m", "not live and not perf"]
markers = [
    "live: talks to Yahoo; run by the daily yahoo-shape workflow with -m live, never on a PR",
    "perf: times a ten-year backtest; CI runs it with -m perf, without coverage",
]
```


- [ ] **Step 3: Run the whole suite, then the performance test, and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`, then `uv run pytest -m perf -p no:cacheprovider`.

<!-- check: red total=738 failed=0 -->
Expected: 738 run, 0 failed. The new property passes against the old `Portfolio` by design: it pins behaviour the old ledger scan already had, so that the rewrite in Step 4 cannot change it. The red is the performance test, which on the old `Portfolio` does not finish inside 600 s (measured 2026-09-26; one synthetic year alone took 12.5 s, and the cost grows with the square of the days). Stop it once it passes 30 s.

- [ ] **Step 4: Implement.**

**`.github/workflows/ci.yml`** (changed: 1 edit)

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml
      - run: uv run --locked pytest -W error --cov --cov-report=term-missing

```
with:
```yaml
      - run: uv run --locked pytest -W error --cov --cov-report=term-missing
      # The ten-year backtest is timed on its own: under coverage's tracing it would time the
      # tracer, which roughly triples the run.
      - name: Performance, a ten-year backtest in under 30 seconds
        run: uv run --locked pytest -W error -m perf -p no:cacheprovider

```

**`packages/steadyhand/src/steadyhand/portfolio.py`** (implemented, rewritten whole)

<!-- file: packages/steadyhand/src/steadyhand/portfolio.py -->
```python
"""A cash-only portfolio: a ledger of cash movements plus the positions they bought.

A ``Portfolio`` is an immutable snapshot, and every operation returns a new one. That makes a
failed step harmless (the old snapshot is still there) and lets the daily run commit or discard
a whole day at once.

Each ``CashMovement`` carries the date it settles, so T+2 is a date comparison, not a separate
balance to keep in step. Buys are debited on the trade date, which is conservative: the broker
takes the money at settlement, but the cash is never available to spend twice. A debit that
settles later, such as a day's stamp duty netted with its trades, is held back the same way:
``spendable_cash`` subtracts every debit at once and adds a credit only once it has settled.

Each snapshot also keeps its cash balance and the few movements that settle after its last day,
so the day's cash is read without summing the ledger, and booking a movement checks only that
movement. A ten-year backtest books over a hundred thousand of them (M3 spec §9).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from steadyhand._validate import require_date, require_type
from steadyhand.money import Currency, CurrencyMismatchError, Money
from steadyhand.types import Fill, Instrument, Position, Side, Split


class MovementKind(Enum):
    DEPOSIT = "deposit"
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    TAX = "tax"
    DAILY_COST = "daily cost"


_CHARGES = frozenset({MovementKind.TAX, MovementKind.DAILY_COST})
"""The movements ``Portfolio.charge`` books: money taken that buys nothing."""


@dataclass(frozen=True, slots=True)
class CashMovement:
    """One change to cash. Credits are positive and debits negative."""

    day: date
    kind: MovementKind
    amount: Money
    settles_on: date

    def __post_init__(self) -> None:
        require_date(self.day, "movement day")
        require_type(self.kind, MovementKind, "kind")
        require_type(self.amount, Money, "amount")
        require_date(self.settles_on, "settles_on")
        if self.settles_on < self.day:
            raise _settlement_before_trade(self.settles_on, self.day)


class InsufficientCashError(ValueError):
    """A buy needs more cash than the portfolio can spend."""

    def __init__(self, day: date, needed: Money, available: Money) -> None:
        super().__init__(f"{day.isoformat()}: needs {needed} but only {available} can be spent")


class InsufficientSharesError(ValueError):
    """A sell asks for more shares than are held. There is no shorting."""

    def __init__(self, day: date, instrument: Instrument, wanted: int, held: int) -> None:
        super().__init__(
            f"{day.isoformat()}: cannot sell {wanted} {instrument.symbol}, only {held} held"
        )


class NegativeProceedsError(ValueError):
    """A sell would cost more than it raises."""

    def __init__(self, fill: Fill) -> None:
        super().__init__(
            f"{fill.day.isoformat()}: selling {fill.quantity} {fill.order.instrument.symbol} "
            f"raises {fill.gross} but costs {fill.costs.total}"
        )


class ChronologyError(ValueError):
    """An operation is dated before the last one already recorded."""

    def __init__(self, day: date, last: date) -> None:
        super().__init__(
            f"{day.isoformat()} is before the last recorded movement, on {last.isoformat()}"
        )


class MissingPriceError(LookupError):
    """A held instrument has no price to value it at."""


def _settlement_before_trade(settles_on: date, day: date) -> ValueError:
    return ValueError(f"settles on {settles_on.isoformat()}, before the trade on {day.isoformat()}")


def _sort_key(position: Position) -> tuple[str, str]:
    return (position.instrument.market, position.instrument.symbol)


@dataclass(frozen=True, slots=True)
class Portfolio:
    """An immutable snapshot of cash (as a ledger) and positions (sorted by market, symbol)."""

    currency: Currency
    positions: tuple[Position, ...] = ()
    ledger: tuple[CashMovement, ...] = ()
    _balance: Money = field(init=False, repr=False, compare=False)
    """The sum of every movement in the ledger."""
    _open: tuple[CashMovement, ...] = field(init=False, repr=False, compare=False)
    """Every movement that settles after the last day, in ledger order."""

    def __post_init__(self) -> None:
        require_type(self.currency, Currency, "currency")
        require_type(self.ledger, tuple, "ledger")
        self._check_positions()
        for movement in self.ledger:
            require_type(movement, CashMovement, "ledger entry")
        previous: date | None = None
        for movement in self.ledger:
            if movement.amount.currency != self.currency:
                raise CurrencyMismatchError(self.currency, movement.amount.currency)
            if previous is not None and movement.day < previous:
                raise ChronologyError(movement.day, previous)
            previous = movement.day
        balance = sum((m.amount for m in self.ledger), start=Money.zero(self.currency))
        still_open = tuple(
            m for m in self.ledger if previous is not None and m.settles_on > previous
        )
        object.__setattr__(self, "_balance", balance)
        object.__setattr__(self, "_open", still_open)

    def _check_positions(self) -> None:
        require_type(self.positions, tuple, "positions")
        for position in self.positions:
            require_type(position, Position, "position")
        keys = [_sort_key(p) for p in self.positions]
        if keys != sorted(set(keys)):
            msg = "positions must be unique and sorted by market, then symbol"
            raise ValueError(msg)
        for position in self.positions:
            if position.instrument.currency != self.currency:
                raise CurrencyMismatchError(self.currency, position.instrument.currency)

    @classmethod
    def empty(cls, currency: Currency) -> Portfolio:
        return cls(currency)

    @property
    def last_day(self) -> date | None:
        return self.ledger[-1].day if self.ledger else None

    def cash_balance(self) -> Money:
        return self._balance

    def settled_cash(self, on: date) -> Money:
        require_date(on, "on")
        return self._balance - self._settling_after(on, credits_only=False)

    def spendable_cash(self, on: date) -> Money:
        """What can be spent on *on* without ever overdrawing: settled credits, less every debit."""
        require_date(on, "on")
        return self._balance - self._settling_after(on, credits_only=True)

    def _settling_after(self, on: date, *, credits_only: bool) -> Money:
        """The movements (or only the credits) that settle after *on*.

        From *on* the last day onwards those are all among ``_open``; an earlier day needs the
        whole ledger.
        """
        last = self.last_day
        pool = self._open if last is None or on >= last else self.ledger
        later = (
            m.amount
            for m in pool
            if m.settles_on > on and not (credits_only and m.amount.amount < 0)
        )
        return sum(later, start=Money.zero(self.currency))

    def unsettled_cash(self, on: date) -> Money:
        return self.cash_balance() - self.settled_cash(on)

    def position(self, instrument: Instrument) -> Position | None:
        for position in self.positions:
            if position.instrument == instrument:
                return position
        return None

    def holdings_value(self, closes: Mapping[Instrument, Money]) -> Money:
        total = Money.zero(self.currency)
        for position in self.positions:
            close = closes.get(position.instrument)
            if close is None:
                msg = f"no close price for {position.instrument.symbol}"
                raise MissingPriceError(msg)
            total += close * position.quantity
        return total

    def deposit(self, amount: Money, on: date) -> Portfolio:
        self._require_not_before_last(on)
        if amount.currency != self.currency:
            raise CurrencyMismatchError(self.currency, amount.currency)
        if amount.amount <= 0:
            msg = f"a deposit must be positive, got {amount}"
            raise ValueError(msg)
        movement = CashMovement(on, MovementKind.DEPOSIT, amount, on)
        return self._next(self.positions, movement)

    def credit_dividend(self, gross: Money, on: date) -> Portfolio:
        """Book a dividend paid on *on*. It settles that day, so the next decision can spend it."""
        return self._book(MovementKind.DIVIDEND, gross, on)

    def charge(
        self, kind: MovementKind, amount: Money, on: date, *, settles_on: date | None = None
    ) -> Portfolio:
        """Take *amount* for tax or a daily cost on *on*, settling on *settles_on* (default *on*).

        Either way it is held back from ``spendable_cash`` at once.
        """
        require_type(kind, MovementKind, "kind")
        if kind not in _CHARGES:
            msg = f"charge books tax or a daily cost, not a {kind.value}"
            raise ValueError(msg)
        return self._book(kind, amount, on, sign=-1, settles_on=settles_on)

    def apply_split(self, split: Split) -> Portfolio:
        """Turn every ``old_shares`` held into ``new_shares``, keeping the total cost basis.

        A fraction of a share left by the ratio is dropped (cash in lieu is not modelled), and a
        holding that rounds to no shares at all is removed with its basis. The caller reports it.
        """
        require_type(split, Split, "split")
        self._require_not_before_last(split.ex_date)
        held = self.position(split.instrument)
        if held is None:
            msg = f"{split.ex_date.isoformat()}: no {split.instrument.symbol} is held to split"
            raise ValueError(msg)
        quantity = held.quantity * split.new_shares // split.old_shares
        updated = Position(held.instrument, quantity, held.cost_basis) if quantity else None
        return self._replaced(held.instrument, updated, None)

    def apply_fill(self, fill: Fill, settles_on: date) -> Portfolio:
        """Book a fill. A buy is debited on its trade date; a sell is credited on *settles_on*."""
        self._require_not_before_last(fill.day)
        require_date(settles_on, "settles_on")
        if settles_on < fill.day:
            raise _settlement_before_trade(settles_on, fill.day)
        if fill.price.currency != self.currency:
            raise CurrencyMismatchError(self.currency, fill.price.currency)
        if fill.order.side is Side.BUY:
            return self._buy(fill)
        return self._sell(fill, settles_on)

    def _book(
        self,
        kind: MovementKind,
        amount: Money,
        on: date,
        *,
        sign: int = 1,
        settles_on: date | None = None,
    ) -> Portfolio:
        self._require_not_before_last(on)
        require_type(amount, Money, "amount")
        if amount.currency != self.currency:
            raise CurrencyMismatchError(self.currency, amount.currency)
        if amount.amount <= 0:
            msg = f"a {kind.value} must be positive, got {amount}"
            raise ValueError(msg)
        movement = CashMovement(on, kind, amount * sign, on if settles_on is None else settles_on)
        return self._next(self.positions, movement)

    def _require_not_before_last(self, day: date) -> None:
        require_date(day, "day")
        last = self.last_day
        if last is not None and day < last:
            raise ChronologyError(day, last)

    def _buy(self, fill: Fill) -> Portfolio:
        instrument = fill.order.instrument
        cost = fill.gross + fill.costs.total
        available = self.spendable_cash(fill.day)
        if cost > available:
            raise InsufficientCashError(fill.day, cost, available)
        held = self.position(instrument)
        if held is None:
            updated = Position(instrument, fill.quantity, cost)
        else:
            updated = Position(instrument, held.quantity + fill.quantity, held.cost_basis + cost)
        movement = CashMovement(fill.day, MovementKind.BUY, -cost, fill.day)
        return self._with(movement, instrument, updated)

    def _sell(self, fill: Fill, settles_on: date) -> Portfolio:
        instrument = fill.order.instrument
        held = self.position(instrument)
        if held is None or fill.quantity > held.quantity:
            held_quantity = 0 if held is None else held.quantity
            raise InsufficientSharesError(fill.day, instrument, fill.quantity, held_quantity)
        proceeds = fill.gross - fill.costs.total
        if proceeds.amount < 0:
            raise NegativeProceedsError(fill)
        remaining: Position | None = None
        if fill.quantity < held.quantity:
            # The basis released by a partial sale rounds up, so the gain reported on the
            # shares sold is never overstated.
            released = -(-held.cost_basis.amount * fill.quantity // held.quantity)
            remaining = Position(
                instrument,
                held.quantity - fill.quantity,
                Money(held.cost_basis.amount - released, self.currency),
            )
        movement = CashMovement(fill.day, MovementKind.SELL, proceeds, settles_on)
        return self._with(movement, instrument, remaining)

    def _with(
        self, movement: CashMovement, instrument: Instrument, position: Position | None
    ) -> Portfolio:
        return self._replaced(instrument, position, movement)

    def _replaced(
        self, instrument: Instrument, position: Position | None, movement: CashMovement | None
    ) -> Portfolio:
        others = [p for p in self.positions if p.instrument != instrument]
        if position is not None:
            others.append(position)
        return self._next(tuple(sorted(others, key=_sort_key)), movement)

    def _next(self, positions: tuple[Position, ...], movement: CashMovement | None) -> Portfolio:
        """This snapshot with *positions* held and *movement* booked after the rest.

        Only what is new is checked. Every caller has already refused a movement dated before
        the last or in another currency, so the ledger holds without reading it again.
        """
        ledger, balance, still_open = self.ledger, self._balance, self._open
        if movement is not None:
            ledger = (*ledger, movement)
            balance += movement.amount
            still_open = tuple(m for m in (*still_open, movement) if m.settles_on > movement.day)
        snapshot = object.__new__(Portfolio)
        for name, value in (
            ("currency", self.currency),
            ("positions", positions),
            ("ledger", ledger),
            ("_balance", balance),
            ("_open", still_open),
        ):
            object.__setattr__(snapshot, name, value)
        snapshot._check_positions()
        return snapshot
```


- [ ] **Step 5: Run the whole gate** as in Task 7, then the performance step.

<!-- check: gate total=738 passed=738 -->
Expected: every command exits 0; 738 passed, 10 deselected, 100% branch coverage; the performance test passes (10.2 s on the machine that wrote this plan).

- [ ] **Step 6: Mutations.** Run M57–M59; each must turn the whole suite red with the total unchanged.
- [ ] **Step 7: Commit, push and merge** (`perf(engine): S10 …`). After CI's first run, record both `test` jobs' performance-step times on the story as its baseline.

---

## Mutation checks

Each mutation plants one realistic defect in its own story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed line is printed before the run. Revert with `git checkout -- <path>` only after the story is committed. The total must not move. The "caught by" column is what the run showed; every prediction was written before the first run, and "more than predicted" lists the catchers the prediction missed. The failing count counts each parametrised case, so it can exceed the number of test names. In the first run M37 and M54 were predicted to survive, and they did: the stray-refusal source refused every request, so a refetch raised anyway, and no measured ledger held a credit that was not a deposit. Each then got the test named here (`_OutOfWindow` now refuses once; `test_only_deposits_count_as_deposited`). The table is the third run, on this plan's own commits.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M34 | 7 | `backtest.py` | a start before the universe's first list is not refused | 711 | `test_a_start_before_the_universe_is_refused_naming_its_first_day` (1 failing) | none |
| M35 | 7 | `backtest.py` | no stock is ever resumed, so the band check runs after refused days | 711 | `test_refused_days_are_fetched_around_and_the_stock_sits_them_out` (1 failing) | none |
| M36 | 7 | `backtest.py` | refused days are fetched again as if clean | 711 | `test_refusals_on_the_first_and_last_days_leave_one_range_between`, `test_refused_days_are_fetched_around_and_the_stock_sits_them_out` (2 failing) | none |
| M37 | 7 | `backtest.py` | a refusal naming no day in the window is ignored | 711 | `test_a_refusal_naming_no_day_in_the_window_stops_the_run` (1 failing) | none |
| M38 | 7 | `backtest.py` | a buy-and-hold backtest runs a second, duplicate baseline | 711 | `test_a_buy_and_hold_backtest_is_its_own_baseline` (1 failing) | none |
| M39 | 7 | `backtest.py` | the universe's survivorship warnings are dropped | 711 | `test_refused_days_are_fetched_around_and_the_stock_sits_them_out` (1 failing) | none |
| M40 | 7 | `backtest.py` | consecutive refused days are never joined into one span | 711 | `test_refused_days_are_fetched_around_and_the_stock_sits_them_out` (1 failing) | none |
| M41 | 7 | `universe.py` | Lq45Universe reports no survivorship warnings | 711 | `test_survivorship_warnings_are_the_memberships` (1 failing) | none |
| M42 | 7 | `backtest.py` | a capital in another currency is not refused | 711 | `test_the_capital_is_positive_and_in_the_markets_currency` (1 failing) | none |
| M43 | 7 | `_validate.py` | require_type writes "an UnitValue" again | 711 | `test_require_type_uses_a_before_a_u_that_sounds_like_you` (2 failing) | `test_a_market_checks_its_parts` |
| M44 | 7 | `backtest.py` | only the first day's members are fetched | 711 | `test_every_stock_the_universe_holds_on_any_day_is_fetched_for_the_whole_window` (1 failing) | none |
| M45 | 8 | `metrics.py` | the trailing year holds 366 days | 729 | `test_dividends_and_the_income_of_the_last_365_days` (1 failing) | none |
| M46 | 8 | `metrics.py` | the drawdown's peak starts at the first close, not at 1 | 729 | `test_equal_falls_report_the_first_and_the_peak_starts_at_one`, `test_the_drawdown_matches_every_pair_checked` (3 failing) | `test_turnover_of_a_worthless_portfolio_is_zero` |
| M47 | 8 | `metrics.py` | of two equal falls the last is reported | 729 | `test_equal_falls_report_the_first_and_the_peak_starts_at_one` (1 failing) | none |
| M48 | 8 | `metrics.py` | the run's calendar days leave out the last day | 729 | `test_returns_are_time_weighted_and_compounded_over_calendar_days`, `test_the_average_value_uses_every_day`, `test_turnover_is_half_the_traded_value_over_the_average_value_per_year` (3 failing) | none |
| M49 | 8 | `metrics.py` | turnover is not halved | 729 | `test_the_average_value_uses_every_day`, `test_turnover_is_half_the_traded_value_over_the_average_value_per_year` (2 failing) | none |
| M50 | 8 | `metrics.py` | sale tax is left out of the costs | 729 | `test_costs_are_split_by_kind` (1 failing) | none |
| M51 | 8 | `engine.py` | a report carries yesterday's unit price | 729 | `test_each_report_carries_the_unit_price_at_the_close` (1 failing) | none |
| M52 | 8 | `metrics.py` | ratios are worked out at 28 digits | 729 | `test_a_huge_annualised_return_from_a_short_run_is_reported_whole` (1 failing) | none |
| M53 | 8 | `backtest.py` | a run's metrics read only its first day | 729 | `test_each_run_carries_its_metrics` (1 failing) | none |
| M54 | 8 | `metrics.py` | every credit counts as deposited | 729 | `test_only_deposits_count_as_deposited` (1 failing) | none |
| M55 | 9 | `view.py` | the view's last close reads the whole history, a look-ahead | 737 | `test_a_run_to_day_d_decides_as_a_longer_run_did_up_to_d`, `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_recorder_writes_the_stored_file_byte_for_byte` (9 failing) | `test_a_halt_lasts_to_the_end_of_the_run_and_is_recorded`, `test_refused_days_are_fetched_around_and_the_stock_sits_them_out`, `test_the_view_shows_today_and_earlier`, `test_the_window_holds_the_events_it_was_chosen_for` |
| M56 | 9 | `rules.py` | dividend tax is charged on one rupiah too many | 737 | `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_recorder_writes_the_stored_file_byte_for_byte` (5 failing) | `test_an_entitlement_is_paid_and_taxed_on_its_pay_date_even_after_a_sale`, `test_dividend_tax_and_trading_days`, `test_dividends_still_arrive_while_halted` |
| M57 | 10 | `portfolio.py` | a new movement is never kept as unsettled | 738 | `test_the_kept_totals_agree_with_the_whole_ledger_on_every_day` (7 failing) | `test_a_deferred_charge_is_held_back_from_spending_at_once`, `test_a_sale_receives_the_open_less_slippage_rounded_down_and_settles_at_t_plus_2`, `test_a_sales_only_day_nets_its_stamp_duty_with_the_sales`, `test_proceeds_are_unsettled_until_the_settlement_date`, `test_sale_proceeds_are_spendable_once_settled`, `test_sale_proceeds_cannot_fund_a_same_day_buy` |
| M58 | 10 | `portfolio.py` | an earlier day's cash is read from the kept movements only | 738 | `test_the_kept_totals_agree_with_the_whole_ledger_on_every_day` (1 failing) | none |
| M59 | 10 | `portfolio.py` | booking a movement leaves the kept balance unchanged | 738 | `test_the_kept_totals_agree_with_the_whole_ledger_on_every_day` (83 failing) | 80 more tests, including `test_a_back_dated_fill_is_refused_and_changes_nothing`, `test_a_buy_is_cut_to_the_lots_the_cash_pays_for`, `test_a_buy_pays_the_open_plus_slippage_rounded_up_to_a_tick` |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M34',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    if start < first:\n',
  '    if start < first and False:\n'),
 ('M35',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '            _resumed(window, day) - refused,',
  '            frozenset(),'),
 ('M36',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '        if day not in refused:\n',
  '        if True:\n'),
 ('M37',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '            if not named:\n                raise\n',
  '            if not named:\n                pass\n'),
 ('M38',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  'None if strategy.name == baseline.name else',
  'None if False else'),
 ('M39',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '(*market.universe.survivorship_warnings(start, end), *_refused_warnings(window))',
  '(*_refused_warnings(window),)'),
 ('M40',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '== bisect_left(window.days, spans[-1][-1]) + 1',
  '== bisect_left(window.days, spans[-1][-1])'),
 ('M41',
  7,
  'packages/steadyhand-idx/src/steadyhand_idx/universe.py',
  'return tuple(self._membership.survivorship_warnings(start, end))',
  'return ()'),
 ('M42',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  '    if settings.capital.currency != rules.currency:\n',
  '    if False:\n'),
 ('M43', 7, 'packages/steadyhand/src/steadyhand/_validate.py', 'in "aeio" else', 'in "aeiou" else'),
 ('M44',
  7,
  'packages/steadyhand/src/steadyhand/backtest.py',
  'frozenset().union(*members.values())',
  'members[days[0]]'),
 ('M45',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  'timedelta(days=YEAR_DAYS - 1)',
  'timedelta(days=YEAR_DAYS)'),
 ('M46',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  'peak, peak_day = Decimal(1), reports[0].day',
  'peak, peak_day = reports[0].unit_price, reports[0].day'),
 ('M47',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  'if depth > deepest.depth:',
  'if depth >= deepest.depth:'),
 ('M48',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  'days = (last - first).days + 1',
  'days = (last - first).days or 1'),
 ('M49',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  '_CONTEXT.multiply(2, days)',
  '_CONTEXT.multiply(1, days)'),
 ('M50',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  'sum((fill.costs.tax for fill in fills), nothing)',
  'nothing'),
 ('M51',
  8,
  'packages/steadyhand/src/steadyhand/engine.py',
  'unit_price=units.price,',
  'unit_price=state.units.price,'),
 ('M52',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  '_CONTEXT = Context(prec=50,',
  '_CONTEXT = Context(prec=28,'),
 ('M53',
  8,
  'packages/steadyhand/src/steadyhand/backtest.py',
  'measure(reports, state)',
  'measure(reports[:1], state)'),
 ('M54',
  8,
  'packages/steadyhand/src/steadyhand/metrics.py',
  'if m.kind is MovementKind.DEPOSIT',
  'if m.amount.amount > 0'),
 ('M55',
  9,
  'packages/steadyhand/src/steadyhand/view.py',
  'found = self._history.between(instrument, None, self._today)',
  'found = self._history.between(instrument, None, date.max)'),
 ('M56',
  9,
  'packages/steadyhand-idx/src/steadyhand_idx/rules.py',
  'def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:\n',
  'def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:\n'
  '        gross = gross + Money(1, gross.currency)\n'),
 ('M57',
  10,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  'tuple(m for m in (*still_open, movement) if m.settles_on > movement.day)',
  'tuple(m for m in still_open if m.settles_on > movement.day)'),
 ('M58',
  10,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  'pool = self._open if last is None or on >= last else self.ledger',
  'pool = self._open'),
 ('M59',
  10,
  'packages/steadyhand/src/steadyhand/portfolio.py',
  '            balance += movement.amount\n',
  '')]
```

## Carried forward to M4 and later

- **The ledger is still a tuple, copied on every booking**, which is quadratic in the number of bookings. Under the profiler, `Portfolio._next`, whose own time is mostly that copy, took 3.2 s of a 25.2 s ten-year run. Making it linear means changing `Portfolio.ledger`'s type, a public M1 API; M5, which saves the ledger, is the place to decide its shape.
- **M5:** the report prints `metrics.trailing_income` for the strategy beside the baseline's (scope decision 11), and maps `DataValidationError` to exit code 3.
- **M6:** the `dividend-growth` golden test uses `scripts/record_golden.py`'s harness; price history before the backtest's start arrives for strategies with a look-back window.
- **A dividend on a refused day** is unknown (scope decision 8). If a source can recover it later, the warning is where it will change.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

- **Pass 1 (2026-09-26):** mechanical, then a full read of the prose. Every code block was rendered by `render.py` from four story commits that each passed CI's gate (`ruff check`, `ruff format --check`, `mypy`, `HYPOTHESIS_PROFILE=ci pytest -W error --cov` at 100% branch coverage, and, for Task 10, the `perf` step). `check_plan.py` then replayed the plan from its own text on top of the fixtures commit: it wrote the blocks before each red marker, ran the whole suite, wrote the rest, ran the golden recorder and checked its SHA-256, required each tree to be byte-identical to its story's commit, and ran the suite again. All four trees were identical and all eight count claims matched. The red phases came from stubs generated by `stubgen.py`, which now also stubs `scripts/`; the one test that passes against its stubs is listed with its reason (Task 10). All 26 mutations were run over the whole suite in their own story's tree, with predictions written first: every one turned the suite red with the total unchanged. The first run left M37 and M54 alive, as predicted, and each got a test; the chain was rebuilt and every gate, red run and mutation run again. Building the stories found, and fixed before this pass: a shadowed `days` in the refused-days fetch that would have fetched the wrong ranges; a currency printed as its `repr`; "an UnitValue"; `Decimal`'s refusal of a huge annual return, then two digits of noise at 28-digit precision; and the engine running past 600 s for ten years, now 10.2 s. Spec coverage was checked section by section against M3 §7, §8, §9 and §10's stories 7–10; every deviation is a numbered scope decision. Placeholder scan clean. The read found six things, all fixed: (1) Task 0 told the executor to record the fixtures again, although they are committed as recorded; it now gives each file's SHA-256 and says what a new recording means; (2) Task 7's criterion 2 gave `ValueError` for arguments of the wrong type, which raise `TypeError`; (3) Task 10's Step 2 did not say it writes stubs; (4) the carried-forward cost of the ledger copy was an estimate, and is now the profiler's measurement; (5) the mutation section did not say that M37's and M54's first predictions were "survives", nor that a failing count counts parametrised cases; (6) `HANDOVER.md` repeated the estimate in (4).
- **Pass 2 (2026-09-26):** mechanical, then a read of every line pass 1 changed. `check_plan.py` again rebuilt all four story trees byte-identical to the verified commits, regenerated the golden file to its SHA-256, and matched all eight count claims; a placeholder scan found nothing, and all 44 test names the prose cites exist in the final tree (the first probe matched only unindented `def` lines and missed three methods of a test class; it was fixed and re-run). Read: one finding, fixed: the carried-forward note called `Portfolio._next`'s own time "that copy", but it also rebuilds the short tuple of open movements; it now says the time is mostly the copy.
- **Pass 3 (2026-09-26):** mechanical and a read of the one line pass 2 changed (the carried-forward note on the ledger copy) against the profile it cites and the scope decision it follows. The replay again rebuilt all four trees byte-identical, the golden SHA-256 and all eight count claims matched. **0 findings. Loop closed; the plan is approved.**
