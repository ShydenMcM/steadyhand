# M5b Paper Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator paper-trade with `steadyhand-idx`: `paper run` plays every trading day the account has not run, in order, saving each day's state, report and audit lines in one transaction; `paper status` and `report` show the account; `resume` and `paper switch` are the two deliberate changes an operator makes to it. A paper account run with its settings unchanged ends exactly where a backtest over the same days ends.

**Architecture:** `steadyhand.snapshot` encodes an `EngineState` and a `DayReport` as canonical, versioned JSON and decodes them back equal (S5). `steadyhand_idx.state` keeps the account, the day reports, the audit log and the run log in `state.sqlite`, saving a day with a compare-and-set on its last day (S6). `steadyhand_idx.paper` works out which days to run, builds their inputs with the engine's public `day_inputs` over the whole range from the opening day, and runs and saves each; `Halt.cause` becomes a keyed `Note` (S7). Every reason an order is refused or cut becomes a keyed `Note` with its lesson (S8). `paper status`, `report`, `resume` and `paper switch` read and change the account through `steadyhand_idx.paper` and print through `steadyhand_idx.paper_pages` (S9).

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. `sqlite3` and `json` from the standard library; no new dependency.

**Spec:** `docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md` (the "M5 spec"), its M5b stories, on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec"), `docs/superpowers/specs/2026-09-26-m4-income-design.md` (the "M4 spec") and `docs/superpowers/specs/2026-09-27-training-design.md` (the "T1 spec"). The M5 spec's S8 is split into S8 and S9 here (scope decision 14). Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how each claim was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2); `steadyhand-idx` keeps its runtime dependencies at `steadyhand` and `yfinance` (M5 §3.1).
- SQL is parameterised only (M5 §9.3). The three logs are append-only, enforced by triggers in the schema, and the schema is upgraded in place by numbered migrations that are never edited once shipped.
- `state.sqlite` is created `0600` whatever the umask (M5 §4.1).
- Only `steadyhand.training`, `steadyhand_idx.training` and `steadyhand_idx.output` import training (T1 §5, M5 §5.7): `paper.py`, `paper_pages.py`, `state.py` and `cli.py` never do.
- Every note a report or the audit log carries is a `Note` built from a key constant, and every key has a lesson in the same story (T1 §1.1, M5 §7.4). Every figure a page shows carries its `FIGURES` key.
- A command's output goes to `stdout`, every error to `stderr`. Exit codes are M5 §8.1's: 0 success (including `already up to date`, and `paper status` or `report` on a halted account), 2 usage or configuration, 3 halted or stopped safely, 1 unexpected.
- Confirmations are typed and there is no `--yes` flag (M5 §7.3); any other answer, or the end of input, exits 2 and changes nothing.
- Tests call steadyhand's own code with real values, recorded data and a real SQLite database in a temporary directory: no stub or mock of steadyhand's code (M5 §9.1). Atomicity is proved with a real trigger, concurrency with two real processes.
- Every `*Error` a task raises is raised by a test that asserts its message. A `match=` holding a regex metacharacter is a raw string (ruff RUF043).
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A function that already existed keeps its old body in the red phase, a class that already existed keeps its old fields, and a function a story renames keeps its old definition beside the new stub; only new names are stubs. A story that retypes existing names and adds only constants (Task 4) has nothing to stub: its stubs step writes the new constants, and every function keeps its old body.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code.
- Test file basenames are unique across `tests/`. English only. The phrase "robot trading" never appears (core §1.3).
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **Two `paper run`s started together.** Expected: each trading day is run and saved exactly once, the second run waiting on SQLite's lock and then finding the days done. Pinned in Task 3 (`test_two_runs_started_together_run_each_day_exactly_once`, two real processes; `test_days_another_run_saves_meanwhile_are_left_to_it`; mutation M259).
2. **A day whose transaction fails after the account row is written.** Expected: the failing run exits 1 (an error nobody raises on purpose), nothing of that day is kept, the account stays at the day before, and the next run completes it. Pinned with a real `BEFORE INSERT ON day_reports` trigger (Task 2 `test_a_day_whose_report_cannot_be_written_leaves_everything_as_it_was`, Task 3 `test_a_day_that_fails_to_save_leaves_the_account_at_the_day_before`).
3. **16:29:59 against 16:30:00 in Jakarta**, on a trading day, a Saturday and Chinese New Year. Expected: the target moves to that day only at 16:30 on a trading day. Pinned in Task 3 (`test_the_target_is_the_latest_completed_trading_day`; mutation M247).
4. **A change typed at a prompt while another run saves a day.** Expected: `resume` or `paper switch` saves nothing, exits 3 and says so; the other run's day stands. Pinned in Task 5 (`test_an_account_changed_while_asking_is_left_as_the_other_run_saved_it`; mutation M279).
5. **`resume` exactly at the drawdown limit.** Expected: refused at the limit and past it, allowed just inside it, and allowed once the operator raises `risk.max_drawdown`. Pinned in Task 5 (`test_resume_is_refused_at_or_past_the_drawdown_limit`, `test_resume_is_allowed_just_inside_the_drawdown_limit`, `test_resume_is_refused_while_the_drawdown_is_still_past_its_limit`; mutation M276).
6. **A snapshot from a newer steadyhand**, or one that is not a whole-number version. Expected: refused with `SnapshotVersionError` (exit 2) or `SnapshotError` naming what is wrong. Pinned in Task 1 (`test_a_document_from_a_newer_steadyhand_is_refused`, `test_a_document_without_a_whole_number_version_is_refused`).

## Scope decisions (read before starting)

1. **No `Portfolio.restore`.** M5 §6.3 asked for one, on the premise that `Portfolio` had no public way to be rebuilt. It has: the public constructor `Portfolio(currency, positions, ledger)` rebuilds the ledger once and checks date order, currency and positions, as `__reduce__` already relies on. The codec calls it.
2. **The codec writes an instrument's currency** as well as its market and symbol, since an `Instrument` carries one. Codes are read through `SNAPSHOT_CURRENCIES` (the rupiah alone), and encoding refuses any other currency, so every saved state can be read back.
3. **A `Decimal` keeps its exponent** (`1.0` and `1` are written differently), so "equal states give equal bytes" holds for equal exact values, and a restored unit price prints as it did.
4. **`upgrade_snapshot(document, steps, newest)` takes its step table as a parameter**, and version 1 has no steps. Version 1 is fixed when Task 3 first writes a state; Tasks 3 and 4 change how the halt and the order reasons are encoded within version 1, since nothing is saved before Task 3.
5. **`key_walk.SAVED_NOTE_READERS`** names each function that builds a `Note` from saved data, by module: the codec's `_read_note` (Task 1, which names it alone as `SAVED_NOTE_READER`) and the store's `_audit_line` (Task 2); the note-key guard exempts exactly those, and a second non-constant `Note` in either module still goes red.
6. **`StateStore.save(account, *, after, report, audit) -> bool` is a compare-and-set** on `last_day`: it writes only if the last day saved is still `after`, and returns `False` otherwise. The busy timeout is 30 seconds, the bar cache's.
7. **The three logs are append-only by trigger**: an `UPDATE` or `DELETE` on `day_reports`, `audit` or `runs` is refused by SQLite itself.
8. **`Account.settings` is `settings_of(config)`**: the ten settings M5 §6.5 lists, by `table.key`. The LQ45 file's path is data, not a setting.
9. **Stale data** (M5 §11, "Yahoo lags the close") is a day on which no stock the universe or the account holds has a bar: `StaleDataError`, exit 3. A day with some bars runs, as a backtest's does.
10. **A stop** (an impossible price, a stale day, a source refusal) records a `stopped` run and a `paper.run.stopped` audit line on the failing day, then exits 3; the days caught up before it stay saved.
11. **A refused run** (the catch-up cap, a changed strategy) writes nothing, not even a `runs` row.
12. **A run whose every day another run saved** records `up to date`; a halted account's run records `halted` and exits 3 (`AccountHaltedError`, printed after the day lines).
13. **`paper status` shows settled and unsettled cash.** M5 §7.1 also names "dividend cash"; the engine keeps none apart (a dividend settles on its pay date), and what is still to reinvest is each open claim's `uncovered`, shown under the claims label.
14. **M5 §10's S8 is split in two.** Keying the `Tradable` reasons (M5 §7.4) makes `Rejected.reason` and `Cut.reason` `Note`s, since a `Tradable` reason flows into `Rejected`, which `report` shows; so every blocked-order reason is keyed at once: 22 keys (`trade.*` 6, `limit.*` 5, `fill.*` 10, `corporate.split.order_cancelled`), with the lessons `orders.not_tradable` and `orders.at_the_open` and `risk.limits` and `shares.splits` extended. That is Task 4 (S8). The paper commands are Task 5 (S9), as T1 §10 allowed its S4 to split.
15. **`Halt.cause` is a `Note`** (`risk.halt.daily_loss`, `risk.halt.drawdown`, lesson `risk.limits`), so a halt's audit line carries its key; the backtest page adds the halt's key.
16. **`cache.py`'s docstring promised** that "M5's daily run stores" today's bar. Nothing needs to: a day is stored by the first read after it is over. The docstring is corrected in Task 3.
17. **`run_paper(store, config, market, now, *, catch_up)`** runs the configured strategy. Passing a `Strategy` in as well would take it to six arguments, over the repository's limit of five; the performance test runs `buy-and-hold` on the synthetic market instead.
18. **`resume` refuses while the drawdown is at or past the configured `risk.max_drawdown`**, whatever the halt's recorded cause, since ordering would only halt again (core §6.1: "refuses while the cause is present"). Raising the limit in the file lets it resume. `HaltCausePresentError`, exit 3.
19. **A change typed at a `resume` or `paper switch` prompt is saved with the same compare-and-set**: a day another run saved meanwhile refuses it with `AccountChangedError`, exit 3.
20. **`Config.goal` is a non-optional `IncomeGoal`**: the file always has one (default Rp10,000,000), so `report --income` needs no "no goal" branch, and `settings_of`'s `goal is None` branch goes.
21. **The engine gains three public names in Task 5**: `income_of(reports, final, market, settings, goal)`, which `backtest` now uses too (one home for fetching the income history); `percent(rate)`, the floor-to-two-places form every limit is written in; and the `UnitValue.drawdown` property, with the drawdown term's key.
22. **Test helpers find one home each**: `reports.text_table` is public for the paper pages; `tests/perf/synthetic.py` holds M3's synthetic market for both performance tests, and `tests/perf` joins pytest's `pythonpath`; the paper helpers and `golden_backtest(cli, end, *, goal=False)` move into `cli_world`.
23. **`report` lists holdings for the latest day only** (the account keeps only today's positions), and says where to see them on any other day. Income-goal progress (M5 §7.2's plain `report`) is in `report --income`, which is the one report that reads the data source.

## Measured performance (M5 §9.3)

Measured in the scratch build on an idle machine (`tests/perf/test_paper_performance.py`), over 45 stocks held by `buy-and-hold` on the synthetic market for five years:

| Measurement | Measured | Budget |
|---|---|---|
| One day's `paper run` on a five-year account | 0.17 s | 1 s |
| A 30-day catch-up on a five-year account | 1.64 s | 10 s |
| The saved state after five years | 650,053 bytes | 800,000 bytes |
| CLI start-up, a command that reads no market data (M5a) | about 0.07 s | 0.5 s |

The time budgets leave about six times the measurement for a slower CI runner, as M3's 30-second budget did; the state's size is the same on every machine, so its budget only leaves room to grow.

## File map

| File | Task | Responsibility |
|---|---|---|
| `.../steadyhand/snapshot.py` | 1, 3, 4 | The canonical, versioned JSON of an `EngineState` and a `DayReport` |
| `.../steadyhand_idx/state.py` | 2 | `state.sqlite`: schema, migrations, `StateStore`, `Account`, `AuditLine`, `Run`, `Outcome` |
| `.../steadyhand/backtest.py` | 3, 5 | The public `day_inputs`; `income_of` |
| `.../steadyhand/__init__.py` | 1, 3–5 | The engine's exports |
| `.../steadyhand/risk.py`, `notes.py` | 3, 4, 5 | The keyed `Halt.cause` and order reasons; `percent`; `UnitValue.drawdown` |
| `.../steadyhand/{view,engine,outcomes,corporate}.py`, `broker/simulated.py` | 4 | Every blocked-order reason a keyed `Note` |
| `.../steadyhand_idx/paper.py` | 3, 5 | The daily cycle; `resume`, `switch` and their refusals |
| `.../steadyhand_idx/paper_pages.py` | 3, 5 | What the paper commands print |
| `.../steadyhand_idx/{cli,notes,config,reports,cache}.py` | 3, 5 | The commands and their exit codes; the paper keys; `Config.goal` |
| `.../training/lessons/en/*.md` (both packages) | 3–5 | The lessons for every new key; T1 module 6 |
| `tests/engine/*`, `tests/golden/test_golden_snapshot.py` | 1, 3, 4 | The codec, the keyed halts and reasons |
| `tests/cli/{test_state,test_paper_run,test_paper_commands,cli_world,...}.py` | 2, 3, 5 | The store, the daily cycle, the commands, the journey |
| `tests/perf/{synthetic,test_paper_performance,test_performance}.py` | 5 | The paper performance budgets |
| `tests/meta/{key_walk,test_note_keys,test_terms}.py` | 1–3 | The guards that follow the saved-note readers and the new figures |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | This plan and the stories | `m5/m5b-plan` |
| 1 | M5b S5 The snapshot codec and its round trips | `m5/s5-snapshot` |
| 2 | M5b S6 The state database: schema, migrations and StateStore | `m5/s6-state` |
| 3 | M5b S7 paper run: day selection, catch-up, the public fetch, atomicity, stops, halts and configuration changes | `m5/s7-paper-run` |
| 4 | M5b S8 Every order reason keyed, with its lessons | `m5/s8-keyed-reasons` |
| 5 | M5b S9 The paper commands: status, report, resume and switch | `m5/s9-paper-commands` |

Stories merge in order: each one's code builds on the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Merge without asking: Shyden's standing rule of 2026-09-27 covers every green PR into `develop` (never `main`). Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: This plan and the stories

On `m5/m5b-plan`, whose PR carries this plan and `HANDOVER.md` (#120).

- [ ] **Step 1: File the stories.** Create one issue per task 1–5, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 2: Open the PR** from `m5/m5b-plan` into `develop` (`Refs #120`), and merge it as **Merging a story** says.

---

### Task 1: M5b S5 The snapshot codec and its round trips

**Acceptance criteria (story text):**
1. `steadyhand.snapshot` has `encode_state`, `decode_state`, `encode_report`, `decode_report`, `to_json` and `from_json`. `to_json` is canonical (sorted keys, no whitespace), so equal states give equal bytes; `from_json` refuses text that is not JSON.
2. `Money` is written as its amount and currency code, a `Decimal` as a string keeping its exponent (scope decision 3), a date in ISO form, an `Enum` as its value, and an `Instrument` as its currency, market and symbol (scope decision 2). A mapping keyed by stock is a list of pairs sorted by market then symbol, whatever order it was built in; a report's frozen stocks keep the order the day froze them in.
3. Every state and every report of both golden runs reads back equal and writes the same JSON again; a small state saves as exactly the JSON the test gives and reads back with its open movement still unsettled; a restored portfolio behaves as the one it was saved from (scope decision 1).
4. The document carries `version`, `SNAPSHOT_VERSION` is 1 and `SNAPSHOT_UPGRADES` is empty; `upgrade_snapshot` applies each older version's step in order (scope decision 4). A newer version raises `SnapshotVersionError` (`this state was written by a newer steadyhand`); a version that is not a whole number, and a state or report that cannot be read, raise `SnapshotError` naming what is wrong. A state in a currency outside `SNAPSHOT_CURRENCIES` is refused before it is saved.
5. The note-key guard exempts the codec's one reader of saved notes by name (scope decision 5), and still goes red on any other `Note` built from non-constant data.
6. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M220–M236 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/snapshot.py`, `tests/engine/test_snapshot.py`, `tests/golden/test_golden_snapshot.py`
- Modify: `.../steadyhand/__init__.py`, `tests/meta/{key_walk,test_note_keys}.py`

**Interfaces:**
- Consumes: `EngineState`, `Holdings`, `Portfolio` (its public constructor), `UnitValue`, `Halt`, `DayReport` and every type they hold; `Note`; `scripts/record_golden.py`'s runs.
- Produces: in `steadyhand.snapshot`, exported from `steadyhand`: `SNAPSHOT_VERSION`, `SNAPSHOT_CURRENCIES`, `SNAPSHOT_UPGRADES`, `SnapshotUpgrade`, `SnapshotError`, `SnapshotVersionError(version, newest)`, `encode_state`, `decode_state`, `encode_report`, `decode_report`, `to_json`, `from_json`, `upgrade_snapshot(document, steps, newest)`. In `tests/meta/key_walk.py`: `SAVED_NOTE_READER`, the codec's one reader; `note_keys(source)` gains `*, reader`, the function whose calls it leaves out.

- [ ] **Step 1: Branch.** `git switch -c m5/s5-snapshot origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_snapshot.py`** (new)

<!-- file: tests/engine/test_snapshot.py -->
```python
"""Saving and reading the engine's state and day reports (M5 spec §6.3, §9.2 "Codec")."""

from collections.abc import Callable
from contextlib import suppress
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import (
    IDR,
    SNAPSHOT_CURRENCIES,
    SNAPSHOT_UPGRADES,
    SNAPSHOT_VERSION,
    CashMovement,
    Costs,
    Currency,
    Cut,
    DayReport,
    DividendClaim,
    EngineState,
    Entitlement,
    Fill,
    Halt,
    Holdings,
    Instrument,
    Money,
    MovementKind,
    Note,
    Order,
    Portfolio,
    Position,
    Protection,
    Rejected,
    Side,
    SnapshotError,
    SnapshotVersionError,
    UnitValue,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
    upgrade_snapshot,
)

D0 = date(2026, 1, 5)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


# Generated values: every type a state or a report holds, within the engine's own checks.

DAYS = st.dates(date(2000, 1, 1), date(2099, 12, 31))
INSTRUMENTS = st.builds(
    Instrument,
    st.from_regex(r"[A-Z0-9][A-Z0-9.\-]{0,5}", fullmatch=True),
    st.sampled_from(["IDX", "NYSE"]),
    st.just(IDR),
)
TEXT = st.text(min_size=1).filter(lambda text: text.strip() != "")
MONEY = st.integers(-(10**15), 10**15).map(rp)
POSITIVE = st.integers(1, 10**15).map(rp)
NOT_NEGATIVE = st.integers(0, 10**15).map(rp)
RATES = st.decimals(min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False)
ORDERS = st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(1, 10**6), DAYS)
HALTS = st.builds(Halt, DAYS, TEXT)
NOTES = st.builds(Note, st.from_regex(r"[a-z]+(\.[a-z_]+)+", fullmatch=True), TEXT)


@st.composite
def fills(draw: st.DrawFn) -> Fill:
    order = draw(ORDERS)
    costs = Costs(draw(NOT_NEGATIVE), draw(NOT_NEGATIVE), draw(NOT_NEGATIVE))
    day = order.placed_on + timedelta(days=draw(st.integers(0, 10)))
    return Fill(order, day, draw(st.integers(1, order.quantity)), draw(POSITIVE), costs)


@st.composite
def cuts(draw: st.DrawFn) -> Cut:
    order = draw(st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(2, 10**6), DAYS))
    return Cut(order, draw(st.integers(1, order.quantity - 1)), draw(TEXT))


@st.composite
def portfolios(draw: st.DrawFn) -> Portfolio:
    held = draw(st.lists(INSTRUMENTS, max_size=4, unique_by=lambda i: (i.market, i.symbol)))
    positions = sorted(
        (Position(i, draw(st.integers(1, 10**9)), draw(NOT_NEGATIVE)) for i in held),
        key=lambda p: (p.instrument.market, p.instrument.symbol),
    )
    moves = draw(
        st.lists(
            st.tuples(DAYS, st.sampled_from(MovementKind), MONEY, st.integers(0, 5)), max_size=8
        )
    )
    ledger = tuple(
        CashMovement(day, kind, amount, day + timedelta(days=lag))
        for day, kind, amount, lag in sorted(moves, key=lambda move: move[0])
    )
    return Portfolio(IDR, tuple(positions), ledger)


@st.composite
def entitlements(draw: st.DrawFn) -> Entitlement:
    ex_date = draw(DAYS)
    pay_date = ex_date + timedelta(days=draw(st.integers(1, 30)))
    return Entitlement(draw(INSTRUMENTS), ex_date, pay_date, draw(POSITIVE))


@st.composite
def claims(draw: st.DrawFn) -> DividendClaim:
    ex_date = draw(DAYS)
    pay_date = ex_date + timedelta(days=draw(st.integers(1, 30)))
    deadline = pay_date + timedelta(days=draw(st.integers(0, 800)))
    gross = draw(st.integers(1, 10**12))
    protections: list[Protection] = []
    covered = 0
    for part in draw(st.lists(st.integers(1, gross), max_size=3)):
        if covered + part <= gross:
            covered += part
            protections.append(Protection(rp(part), draw(DAYS)))
    uncovered = draw(st.integers(0, gross - covered))
    instrument = draw(INSTRUMENTS)
    return DividendClaim(
        instrument, ex_date, pay_date, rp(gross), deadline, rp(uncovered), tuple(protections)
    )


HOLDINGS = st.builds(
    Holdings,
    portfolios(),
    st.lists(ORDERS, max_size=3).map(tuple),
    st.lists(entitlements(), max_size=3).map(tuple),
    st.dictionaries(INSTRUMENTS, TEXT, max_size=3),
    st.dictionaries(INSTRUMENTS, POSITIVE, max_size=3),
    st.lists(claims(), max_size=3).map(tuple),
    st.none() | DAYS,
)
STATES = st.builds(
    EngineState,
    HOLDINGS,
    st.builds(UnitValue, RATES, RATES, RATES),
    st.none() | HALTS,
    st.none() | DAYS,
    st.dictionaries(st.text(), st.text(), max_size=3),
)


def tuples[T](values: st.SearchStrategy[T]) -> st.SearchStrategy[tuple[T, ...]]:
    return st.lists(values, max_size=3).map(tuple)


REPORTS = st.builds(
    DayReport,
    day=DAYS,
    fills=tuples(fills()),
    rejected=tuples(st.builds(Rejected, ORDERS, TEXT)),
    cuts=tuples(cuts()),
    queued=tuples(ORDERS),
    entitled=tuples(entitlements()),
    paid=tuples(entitlements()),
    tax=MONEY,
    daily_cost=MONEY,
    deposit=MONEY,
    frozen=tuples(st.tuples(INSTRUMENTS, TEXT)),
    halt=st.none() | HALTS,
    settled=MONEY,
    unsettled=MONEY,
    holdings_value=MONEY,
    value=MONEY,
    unit_price=RATES,
    warnings=tuples(NOTES),
    notes=tuples(NOTES),
)


@given(STATES)
def test_every_state_reads_back_equal_and_writes_the_same_json_again(state: EngineState) -> None:
    text = to_json(encode_state(state))
    back = decode_state(from_json(text))
    assert back == state
    assert to_json(encode_state(back)) == text


@given(REPORTS)
def test_every_report_reads_back_equal_and_writes_the_same_json_again(report: DayReport) -> None:
    text = to_json(encode_report(report))
    back = decode_report(from_json(text))
    assert back == report
    assert to_json(encode_report(back)) == text


# The worked example: one small state, and exactly the JSON it saves as.


def small_state() -> EngineState:
    opened = EngineState.opening(rp(10_000_000), D0)
    portfolio = opened.holdings.portfolio.charge(
        MovementKind.DAILY_COST, rp(1_500), D0, settles_on=D0 + timedelta(days=2)
    )
    holdings = Holdings(
        portfolio,
        pending=(Order(BBRI, Side.BUY, 500, D0),),
        frozen={TLKM: "excluded: suspended", BBRI: "excluded: under review"},
        last_closes={BBRI: rp(4_150)},
        shortfall_since=D0,
    )
    units = UnitValue(Decimal("10000000"), Decimal("0.9998500"), Decimal("1.000"))
    halt = Halt(D0, "daily loss limit")
    return EngineState(holdings, units, halt, D0, {"set": "IDX:BBRI"})


SMALL_STATE_JSON = (
    '{"halt":{"cause":"daily loss limit","day":"2026-01-05"},'
    '"holdings":{"claims":[],"entitlements":[],'
    '"frozen":[[{"currency":"IDR","market":"IDX","symbol":"BBRI"},"excluded: under review"],'
    '[{"currency":"IDR","market":"IDX","symbol":"TLKM"},"excluded: suspended"]],'
    '"last_closes":[[{"currency":"IDR","market":"IDX","symbol":"BBRI"},'
    '{"amount":4150,"currency":"IDR"}]],'
    '"pending":[{"instrument":{"currency":"IDR","market":"IDX","symbol":"BBRI"},'
    '"placed_on":"2026-01-05","quantity":500,"side":"buy"}],'
    '"portfolio":{"currency":"IDR","ledger":['
    '{"amount":{"amount":10000000,"currency":"IDR"},"day":"2026-01-05","kind":"deposit",'
    '"settles_on":"2026-01-05"},'
    '{"amount":{"amount":-1500,"currency":"IDR"},"day":"2026-01-05","kind":"daily cost",'
    '"settles_on":"2026-01-07"}],"positions":[]},'
    '"shortfall_since":"2026-01-05"},'
    '"last_day":"2026-01-05","memory":{"set":"IDX:BBRI"},'
    '"units":{"high_water":"1.000","price":"0.9998500","units":"10000000"},"version":1}'
)


def test_a_small_state_saves_as_exactly_this_json() -> None:
    assert to_json(encode_state(small_state())) == SMALL_STATE_JSON


def test_a_small_state_reads_back_equal_with_its_open_movement_still_unsettled() -> None:
    back = decode_state(from_json(SMALL_STATE_JSON))
    assert back == small_state()
    portfolio = back.holdings.portfolio
    assert portfolio.settled_cash(D0) == rp(10_000_000)
    assert portfolio.spendable_cash(D0) == rp(9_998_500)
    assert portfolio.settled_cash(D0 + timedelta(days=2)) == rp(9_998_500)


def test_a_decimal_keeps_its_exponent_so_a_restored_unit_price_prints_the_same() -> None:
    units = decode_state(from_json(SMALL_STATE_JSON)).units
    assert (str(units.price), str(units.high_water)) == ("0.9998500", "1.000")


def test_stock_keyed_maps_save_the_same_whatever_order_they_were_built_in() -> None:
    state = small_state()
    reordered = Holdings(
        state.holdings.portfolio,
        pending=state.holdings.pending,
        frozen={BBRI: "excluded: under review", TLKM: "excluded: suspended"},
        last_closes=state.holdings.last_closes,
        shortfall_since=state.holdings.shortfall_since,
    )
    same = EngineState(reordered, state.units, state.halt, state.last_day, state.memory)
    assert list(same.holdings.frozen) != list(state.holdings.frozen)
    assert to_json(encode_state(same)) == to_json(encode_state(state))


def test_a_reports_frozen_stocks_keep_the_order_the_day_froze_them_in() -> None:
    report = small_report()
    text = to_json(encode_report(report))
    assert text.index('"TLKM"') < text.index('"BBRI"')
    assert decode_report(from_json(text)).frozen == report.frozen


def small_report() -> DayReport:
    zero = rp(0)
    return DayReport(
        day=D0,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=(),
        tax=zero,
        daily_cost=zero,
        deposit=zero,
        frozen=((TLKM, "excluded: suspended"), (BBRI, "excluded: under review")),
        halt=None,
        settled=zero,
        unsettled=zero,
        holdings_value=zero,
        value=zero,
        unit_price=Decimal(1),
        warnings=(),
    )


# A restored portfolio behaves as the one it was saved from (M5 spec §6.3).

STOCKS = (BBRI, TLKM)
type Step = tuple[str, int, int, int, int, int]  # kind, days forward, stock, shares, price, lag

STEPS = st.tuples(
    st.sampled_from(["deposit", "buy", "sell", "dividend", "tax", "cost"]),
    st.integers(0, 3),
    st.integers(0, len(STOCKS) - 1),
    st.integers(1, 2_000),
    st.integers(50, 20_000),
    st.integers(0, 3),
)


def take(portfolio: Portfolio, step: Step, today: date) -> Portfolio:
    kind, _forward, stock, shares, price, lag = step
    later = today + timedelta(days=lag)
    if kind == "deposit":
        return portfolio.deposit(rp(shares * price), today)
    if kind == "dividend":
        return portfolio.credit_dividend(rp(shares), today)
    if kind in {"tax", "cost"}:
        charge = MovementKind.TAX if kind == "tax" else MovementKind.DAILY_COST
        return portfolio.charge(charge, rp(shares), today, settles_on=later)
    side = Side.BUY if kind == "buy" else Side.SELL
    order = Order(STOCKS[stock], side, shares, today)
    fill = Fill(order, today, shares, rp(price), Costs(rp(price // 10), rp(0), rp(0)))
    return portfolio.apply_fill(fill, later)


def outcome(portfolio: Portfolio, step: Step, today: date) -> object:
    try:
        return take(portfolio, step, today)
    except ValueError as error:
        return (type(error), str(error))


@given(st.lists(STEPS, max_size=30), STEPS)
def test_a_restored_portfolio_behaves_as_the_one_it_was_saved_from(
    steps: list[Step], following: Step
) -> None:
    portfolio = Portfolio.empty(IDR)
    today = D0
    for step in steps:
        today += timedelta(days=step[1])
        with suppress(ValueError):
            portfolio = take(portfolio, step, today)
    saved = EngineState(Holdings(portfolio))
    restored = decode_state(from_json(to_json(encode_state(saved)))).holdings.portfolio
    assert restored == portfolio
    assert (restored.last_day, restored.cash_balance()) == (
        portfolio.last_day,
        portfolio.cash_balance(),
    )
    for offset in range(-4, 5):
        on = today + timedelta(days=offset)
        assert restored.settled_cash(on) == portfolio.settled_cash(on)
        assert restored.spendable_cash(on) == portfolio.spendable_cash(on)
    assert outcome(restored, following, today) == outcome(portfolio, following, today)


# Documents that cannot be read, and states that cannot be saved.

type Change = Callable[[dict[str, object]], None]


def ledger(document: dict[str, object]) -> list[dict[str, object]]:
    return document["holdings"]["portfolio"]["ledger"]  # type: ignore[index,no-any-return]


def swap_ledger(document: dict[str, object]) -> None:
    moves = ledger(document)
    moves[0], moves[1] = moves[1], moves[0]


def two_positions(document: dict[str, object]) -> None:
    position = {
        "instrument": {"currency": "IDR", "market": "IDX", "symbol": "BBRI"},
        "quantity": 100,
        "cost_basis": {"amount": 400_000, "currency": "IDR"},
    }
    document["holdings"]["portfolio"]["positions"] = [position, dict(position)]  # type: ignore[index]


def set_in(path: tuple[str | int, ...], value: object) -> Change:
    def change(document: dict[str, object]) -> None:
        target: object = document
        for step in path[:-1]:
            target = target[step]  # type: ignore[index]
        target[path[-1]] = value  # type: ignore[index]

    return change


def drop(name: str) -> Change:
    def change(document: dict[str, object]) -> None:
        del document[name]

    return change


AMOUNT = ("holdings", "portfolio", "ledger", 0, "amount", "amount")
STATE_FIELDS = r"\['halt', 'holdings', 'last_day', 'memory', 'units', 'version'\]"

UNREADABLE_STATES: list[tuple[str, Change, str]] = [
    (
        "a ledger out of date order",
        swap_ledger,
        "2026-01-05 is before the last recorded movement, on 2026-01-06",
    ),
    (
        "a movement in a currency it cannot hold",
        set_in(("holdings", "portfolio", "ledger", 0, "amount", "currency"), "USD"),
        "unknown currency 'USD'",
    ),
    (
        "a position of no shares",
        set_in(
            ("holdings", "portfolio", "positions"),
            [
                {
                    "instrument": {"currency": "IDR", "market": "IDX", "symbol": "BBRI"},
                    "quantity": 0,
                    "cost_basis": {"amount": 0, "currency": "IDR"},
                }
            ],
        ),
        "position quantity must be at least 1, got 0",
    ),
    (
        "two positions in one stock",
        two_positions,
        "positions must be unique and sorted by market, then symbol",
    ),
    (
        "a missing field",
        drop("memory"),
        (
            rf"expected the fields {STATE_FIELDS}, "
            r"got \['halt', 'holdings', 'last_day', 'units', 'version'\]"
        ),
    ),
    (
        "an unknown field",
        set_in(("extra",), 1),
        (
            rf"expected the fields {STATE_FIELDS}, "
            r"got \['extra', 'halt', 'holdings', 'last_day', 'memory', 'units', 'version'\]"
        ),
    ),
    ("an amount written as a fraction", set_in(AMOUNT, 1.5), "expected a whole number, got float"),
    ("an amount written as true", set_in(AMOUNT, value=True), "expected a whole number, got bool"),
    (
        "a unit price that is not a number",
        set_in(("units", "price"), "NaN"),
        "expected a finite number, got 'NaN'",
    ),
    (
        "a unit price in words",
        set_in(("units", "price"), "one"),
        "expected a finite number, got 'one'",
    ),
    ("a day that is not a date", set_in(("last_day",), "5 Jan 2026"), "Invalid isoformat"),
    (
        "a strategy memory holding a number",
        set_in(("memory",), {"set": 5}),
        "expected a string, got int",
    ),
    (
        "an object where a list belongs",
        set_in(("holdings", "pending"), {}),
        "expected a list, got dict",
    ),
    (
        "a strategy memory that is not an object",
        set_in(("memory",), ["set"]),
        "expected the strategy memory as an object, got list",
    ),
    (
        "a list where an object belongs",
        set_in(("units",), []),
        "expected an object with units, price, high_water, got list",
    ),
]


@pytest.mark.parametrize(
    ("change", "message"),
    [pytest.param(change, message, id=name) for name, change, message in UNREADABLE_STATES],
)
def test_a_state_that_cannot_be_read_is_refused_naming_what_is_wrong(
    change: Change, message: str
) -> None:
    opened = EngineState.opening(rp(10_000_000), D0)
    portfolio = opened.holdings.portfolio.deposit(rp(1_000), D0 + timedelta(days=1))
    document = encode_state(EngineState(Holdings(portfolio), opened.units))
    change(document)
    with pytest.raises(SnapshotError, match=rf"^the saved state cannot be read: .*{message}"):
        decode_state(document)


def test_a_report_that_cannot_be_read_is_refused_naming_what_is_wrong() -> None:
    document = encode_report(small_report())
    document["tax"] = {"amount": "0", "currency": "IDR"}
    with pytest.raises(
        SnapshotError, match=r"^the saved day report cannot be read: expected a whole number"
    ):
        decode_report(document)


@pytest.mark.parametrize(
    ("currency", "message"),
    [
        (Currency("USD", 2), "a snapshot cannot hold USD with 2 minor units"),
        (Currency("IDR", 2), "a snapshot cannot hold IDR with 2 minor units"),
    ],
)
def test_a_state_in_a_currency_a_snapshot_cannot_hold_is_refused_before_it_is_saved(
    currency: Currency, message: str
) -> None:
    state = EngineState.opening(Money(10_000, currency), D0)
    with pytest.raises(SnapshotError, match=f"^{message}$"):
        encode_state(state)


def test_the_currencies_a_snapshot_can_hold_are_the_rupiah_alone() -> None:
    assert SNAPSHOT_CURRENCIES == {"IDR": IDR}


# Versions (M5 spec §6.3).


def test_this_code_writes_version_1_and_has_no_upgrades_yet() -> None:
    assert SNAPSHOT_VERSION == 1
    assert SNAPSHOT_UPGRADES == {}
    assert encode_state(small_state())["version"] == 1
    assert encode_report(small_report())["version"] == 1


@pytest.mark.parametrize("decode", [decode_state, decode_report])
def test_a_document_from_a_newer_steadyhand_is_refused(decode: Callable[[object], object]) -> None:
    newer = {"version": 2}
    with pytest.raises(
        SnapshotVersionError,
        match=(
            r"^this state was written by a newer steadyhand: its version is 2, and this one "
            r"reads versions up to 1$"
        ),
    ):
        decode(newer)


@pytest.mark.parametrize(
    ("document", "shown"),
    [
        ({}, "None"),
        ({"version": 0}, "0"),
        ({"version": "1"}, "'1'"),
        ({"version": True}, "True"),
        ({"version": 1.0}, "1.0"),
        ([1], "None"),
    ],
)
def test_a_document_without_a_whole_number_version_is_refused(document: object, shown: str) -> None:
    with pytest.raises(
        SnapshotError, match=rf"^a snapshot needs a whole-number version from 1, got {shown}$"
    ):
        upgrade_snapshot(document)


def trail(step: str) -> Callable[[dict[str, object]], dict[str, object]]:
    def upgrade(document: dict[str, object]) -> dict[str, object]:
        done = document.get("trail", [])
        return {**document, "trail": [*done, step]}  # type: ignore[misc]

    return upgrade


def test_an_older_document_is_upgraded_one_version_at_a_time_oldest_first() -> None:
    steps = {1: trail("1 to 2"), 2: trail("2 to 3")}
    original = {"version": 1, "kept": "yes"}
    assert upgrade_snapshot(original, steps, 3) == {
        "version": 3,
        "kept": "yes",
        "trail": ["1 to 2", "2 to 3"],
    }
    assert original == {"version": 1, "kept": "yes"}
    assert upgrade_snapshot({"version": 2}, steps, 3) == {"version": 3, "trail": ["2 to 3"]}
    assert upgrade_snapshot({"version": 3}, steps, 3) == {"version": 3}


def test_canonical_json_has_sorted_keys_and_no_whitespace() -> None:
    assert to_json({"b": 1, "a": [1, "x"], "c": {"z": None, "y": "é"}}) == (
        '{"a":[1,"x"],"b":1,"c":{"y":"\\u00e9","z":null}}'
    )


def test_text_that_is_not_json_is_refused() -> None:
    with pytest.raises(SnapshotError, match=r"^a snapshot is not valid JSON: Expecting value"):
        from_json("not json")
```

**`tests/golden/test_golden_snapshot.py`** (new)

<!-- file: tests/golden/test_golden_snapshot.py -->
```python
"""Every day of the golden backtests saved and read back (M5 spec §9.2 "Codec").

Both recorded runs go through the codec: the switch-off run (248 days, with rejected orders, a
cut and paid dividends) and the switch-on run (307 days, ending with five open claims).
"""

from pathlib import Path

import pytest
from record_golden import run, run_exempt

from steadyhand import (
    BacktestResult,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
)


@pytest.fixture(scope="module")
def golden(tmp_path_factory: pytest.TempPathFactory) -> tuple[BacktestResult, BacktestResult]:
    folder: Path = tmp_path_factory.mktemp("golden")
    return run(folder / "off"), run_exempt(folder / "on")


def test_every_day_report_of_both_golden_runs_reads_back_equal(
    golden: tuple[BacktestResult, BacktestResult],
) -> None:
    off, on = golden
    assert (len(off.run.reports), len(on.run.reports)) == (248, 307)
    for result in golden:
        for report in result.run.reports:
            assert decode_report(from_json(to_json(encode_report(report)))) == report


def test_the_final_state_of_both_golden_runs_reads_back_equal(
    golden: tuple[BacktestResult, BacktestResult],
) -> None:
    off, on = golden
    assert len(on.run.final.holdings.claims) == 5
    for result in (off, on):
        final = result.run.final
        assert decode_state(from_json(to_json(encode_state(final)))) == final
```

**`tests/meta/key_walk.py`** (changed: 2 edits)

<!-- edit: tests/meta/key_walk.py -->
Replace:
```python
TERM_PREFIX = "term."

```
with:
```python
TERM_PREFIX = "term."
SAVED_NOTES = ENGINE / "snapshot.py"
SAVED_NOTE_READER = "_read_note"
"""The one function allowed to build a ``Note`` from a key that is not a constant: the snapshot
reader, which rebuilds a saved note exactly as it was written (M5 spec §6.3). The note was built
from a constant when it was made; read back, its key is data, and it cannot drift."""

```

<!-- edit: tests/meta/key_walk.py -->
Replace:
```python

def note_keys(source: str) -> list[str]:
    """How each ``Note(...)`` call in *source* names its key: a constant's name, or a finding."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or _called(node.func) != "Note":
            continue
```
with:
```python

def note_keys(source: str, *, reader: str | None = None) -> list[str]:
    """How each ``Note(...)`` call in *source* names its key: a constant's name, or a finding.

    Calls inside the function named *reader* are left out: pass it only for the snapshot module.
    """
    tree = ast.parse(source)
    skipped = {
        id(inner)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == reader
        for inner in ast.walk(node)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _called(node.func) != "Note" or id(node) in skipped:
            continue
```

**`tests/meta/test_note_keys.py`** (changed: 3 edits)

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
    NOTE_MODULES,
    TERM_MODULE,
```
with:
```python
    NOTE_MODULES,
    SAVED_NOTE_READER,
    SAVED_NOTES,
    TERM_MODULE,
```

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python

def test_the_literal_detector() -> None:
```
with:
```python

def test_the_note_detector_leaves_out_only_the_reader_it_is_given() -> None:
    source = (
        "def _read(saved):\n"
        "    return Note(str(saved), 't')\n"
        "def other(saved):\n"
        "    return Note(str(saved), 't')\n"
    )
    assert note_keys(source) == [
        "line 2: key is not a constant",
        "line 4: key is not a constant",
    ]
    assert note_keys(source, reader="_read") == ["line 4: key is not a constant"]


def test_the_snapshot_reader_is_the_one_note_built_from_saved_data() -> None:
    source = SAVED_NOTES.read_text(encoding="utf-8")
    assert len([key for key in note_keys(source) if "not a constant" in key]) == 1
    assert note_keys(source, reader=SAVED_NOTE_READER) == []


def test_the_literal_detector() -> None:
```

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
    sources = package_sources()
    used = [key for source in sources.values() for key in note_keys(source)]
    assert len(used) >= len(names) >= 6, "no Note(...) call was found in the packages"
```
with:
```python
    sources = package_sources()
    used = [
        key
        for path, source in sources.items()
        for key in note_keys(source, reader=SAVED_NOTE_READER if path == SAVED_NOTES else None)
    ]
    assert len(used) >= len(names) >= 6, "no Note(...) call was found in the packages"
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.strategies import (
```
with:
```python
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.snapshot import (
    SNAPSHOT_CURRENCIES,
    SNAPSHOT_UPGRADES,
    SNAPSHOT_VERSION,
    SnapshotError,
    SnapshotUpgrade,
    SnapshotVersionError,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
    upgrade_snapshot,
)
from steadyhand.strategies import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "RATIO_PLACES",
    "STRATEGIES",
```
with:
```python
    "RATIO_PLACES",
    "SNAPSHOT_CURRENCIES",
    "SNAPSHOT_UPGRADES",
    "SNAPSHOT_VERSION",
    "STRATEGIES",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Sizer",
    "Split",
```
with:
```python
    "Sizer",
    "SnapshotError",
    "SnapshotUpgrade",
    "SnapshotVersionError",
    "Split",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "cover_claims",
    "dividend_growth",
    "goal_progress",
```
with:
```python
    "cover_claims",
    "decode_report",
    "decode_state",
    "dividend_growth",
    "encode_report",
    "encode_state",
    "from_json",
    "goal_progress",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "settle_claims",
    "year_window_start",
```
with:
```python
    "settle_claims",
    "to_json",
    "upgrade_snapshot",
    "year_window_start",
```

**`packages/steadyhand/src/steadyhand/snapshot.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/snapshot.py -->
```python
"""The engine's state and day reports as JSON documents, for saving (M5 spec §6.3).

A document is a ``dict`` of strings, whole numbers, lists, ``None`` and further documents, and
``to_json`` writes it canonically: sorted keys and no whitespace, so the same values always give
the same bytes. Money is its amount in minor units and its currency's code, a ``Decimal`` its
exact string (the exponent is kept, since ``1.0`` and ``1`` print differently), a date its ISO
form, an enum its value, and an instrument its currency, market and symbol. A mapping keyed by an
instrument becomes a list of ``[instrument, value]`` pairs sorted by market, then symbol, because
a JSON object's keys can only be strings.

Every document carries ``version``. An older one is brought up to date by ``upgrade_snapshot``,
one step per version, before it is read; a newer one raises ``SnapshotVersionError``. Anything
else that cannot be read (a missing or unknown field, a wrong type, a value the engine's own
checks refuse) raises ``SnapshotError``. Decoding rebuilds the portfolio once, through its
constructor, which checks the ledger and the positions as the forward path does (#84).

Standard library only (core spec §4.2).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Currency, Money
from steadyhand.notes import Note
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import CashMovement, MovementKind, Portfolio
from steadyhand.risk import Halt, UnitValue
from steadyhand.types import Costs, Fill, Instrument, Order, Position, Side

SNAPSHOT_VERSION: Final = 1
"""The version this code writes, and the newest it reads."""

type SnapshotUpgrade = Callable[[dict[str, object]], dict[str, object]]
"""One step: a document of version N made into one of version N + 1."""

SNAPSHOT_UPGRADES: Final[Mapping[int, SnapshotUpgrade]] = {}
"""The step from each older version, keyed by the version it upgrades. None yet at version 1."""

SNAPSHOT_CURRENCIES: Final[Mapping[str, Currency]] = {IDR.code: IDR}
"""The currencies a snapshot can hold, by code: a saved state is always one this code reads."""

_UNREADABLE = (TypeError, ValueError)
"""What the readers below, and the engine's own constructors, raise for a bad document."""


class SnapshotError(ValueError):
    """A document this code cannot write or read."""


class SnapshotVersionError(SnapshotError):
    """A document written by a newer steadyhand. M5 exits with code 2."""

    def __init__(self, version: int, newest: int) -> None:
        raise NotImplementedError("SnapshotVersionError.__init__")


def encode_state(state: EngineState) -> dict[str, object]:
    """*state* as a document of the current version."""
    raise NotImplementedError("encode_state")


def decode_state(document: object) -> EngineState:
    """The state *document* holds, upgraded first if it is older."""
    raise NotImplementedError("decode_state")


def encode_report(report: DayReport) -> dict[str, object]:
    """*report* as a document of the current version."""
    raise NotImplementedError("encode_report")


def decode_report(document: object) -> DayReport:
    """The day report *document* holds, upgraded first if it is older."""
    raise NotImplementedError("decode_report")


def upgrade_snapshot(
    document: object,
    steps: Mapping[int, SnapshotUpgrade] = SNAPSHOT_UPGRADES,
    newest: int = SNAPSHOT_VERSION,
) -> dict[str, object]:
    """*document* brought up to version *newest*, one step at a time, oldest first."""
    raise NotImplementedError("upgrade_snapshot")


def to_json(document: Mapping[str, object]) -> str:
    """*document* as canonical JSON: sorted keys, no whitespace, ASCII only."""
    raise NotImplementedError("to_json")


def from_json(text: str) -> object:
    """The document *text* holds."""
    raise NotImplementedError("from_json")


def _code(currency: Currency) -> str:
    raise NotImplementedError("_code")


def _money(value: Money) -> dict[str, object]:
    raise NotImplementedError("_money")


def _instrument(instrument: Instrument) -> dict[str, object]:
    raise NotImplementedError("_instrument")


def _order(order: Order) -> dict[str, object]:
    raise NotImplementedError("_order")


def _fill(fill: Fill) -> dict[str, object]:
    raise NotImplementedError("_fill")


def _portfolio(portfolio: Portfolio) -> dict[str, object]:
    raise NotImplementedError("_portfolio")


def _entitlement(entitlement: Entitlement) -> dict[str, object]:
    raise NotImplementedError("_entitlement")


def _claim(claim: DividendClaim) -> dict[str, object]:
    raise NotImplementedError("_claim")


def _pairs[V](mapping: Mapping[Instrument, V], encode: Callable[[V], object]) -> list[object]:
    raise NotImplementedError("_pairs")


def _halt(halt: Halt | None) -> dict[str, object] | None:
    raise NotImplementedError("_halt")


def _note(note: Note) -> dict[str, object]:
    raise NotImplementedError("_note")


def _day_or_none(day: date | None) -> str | None:
    raise NotImplementedError("_day_or_none")


def _fields(document: object, *names: str) -> tuple[object, ...]:
    """The values of *names* in *document*, which must hold exactly those fields."""
    raise NotImplementedError("_fields")


def _int(value: object) -> int:
    raise NotImplementedError("_int")


def _str(value: object) -> str:
    raise NotImplementedError("_str")


def _list(value: object) -> list[object]:
    raise NotImplementedError("_list")


def _date(value: object) -> date:
    raise NotImplementedError("_date")


def _optional_date(value: object) -> date | None:
    raise NotImplementedError("_optional_date")


def _decimal(value: object) -> Decimal:
    raise NotImplementedError("_decimal")


def _read_currency(value: object) -> Currency:
    raise NotImplementedError("_read_currency")


def _read_money(value: object) -> Money:
    raise NotImplementedError("_read_money")


def _read_instrument(value: object) -> Instrument:
    raise NotImplementedError("_read_instrument")


def _read_order(value: object) -> Order:
    raise NotImplementedError("_read_order")


def _read_fill(value: object) -> Fill:
    raise NotImplementedError("_read_fill")


def _read_position(value: object) -> Position:
    raise NotImplementedError("_read_position")


def _read_movement(value: object) -> CashMovement:
    raise NotImplementedError("_read_movement")


def _read_portfolio(value: object) -> Portfolio:
    raise NotImplementedError("_read_portfolio")


def _read_entitlement(value: object) -> Entitlement:
    raise NotImplementedError("_read_entitlement")


def _read_claim(value: object) -> DividendClaim:
    raise NotImplementedError("_read_claim")


def _read_protection(value: object) -> Protection:
    raise NotImplementedError("_read_protection")


def _read_pairs[V](value: object, read: Callable[[object], V]) -> dict[Instrument, V]:
    raise NotImplementedError("_read_pairs")


def _read_halt(value: object) -> Halt | None:
    raise NotImplementedError("_read_halt")


def _read_note(value: object) -> Note:
    raise NotImplementedError("_read_note")


def _read_memory(value: object) -> dict[str, str]:
    raise NotImplementedError("_read_memory")


def _read_state(document: dict[str, object]) -> EngineState:
    raise NotImplementedError("_read_state")


def _read_report(document: dict[str, object]) -> DayReport:
    raise NotImplementedError("_read_report")


def _read_rejected(value: object) -> Rejected:
    raise NotImplementedError("_read_rejected")


def _read_cut(value: object) -> Cut:
    raise NotImplementedError("_read_cut")


def _read_frozen(value: object) -> tuple[Instrument, str]:
    raise NotImplementedError("_read_frozen")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1323 failed=41 -->
Expected: 1323 run, 41 failed. 40 are `NotImplementedError` from the stubs in `snapshot.py`. The 41st is `test_the_snapshot_reader_is_the_one_note_built_from_saved_data`, which reads `assert 0 == 1`: the reader it names is still a stub, so it builds no `Note`. Three new or changed tests pass against the stubs by design: `test_the_currencies_a_snapshot_can_hold_are_the_rupiah_alone` pins a module constant, and `test_the_note_detector_leaves_out_only_the_reader_it_is_given` and the changed `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used` read source text, which a stub keeps.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/snapshot.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/snapshot.py -->
```python
"""The engine's state and day reports as JSON documents, for saving (M5 spec §6.3).

A document is a ``dict`` of strings, whole numbers, lists, ``None`` and further documents, and
``to_json`` writes it canonically: sorted keys and no whitespace, so the same values always give
the same bytes. Money is its amount in minor units and its currency's code, a ``Decimal`` its
exact string (the exponent is kept, since ``1.0`` and ``1`` print differently), a date its ISO
form, an enum its value, and an instrument its currency, market and symbol. A mapping keyed by an
instrument becomes a list of ``[instrument, value]`` pairs sorted by market, then symbol, because
a JSON object's keys can only be strings.

Every document carries ``version``. An older one is brought up to date by ``upgrade_snapshot``,
one step per version, before it is read; a newer one raises ``SnapshotVersionError``. Anything
else that cannot be read (a missing or unknown field, a wrong type, a value the engine's own
checks refuse) raises ``SnapshotError``. Decoding rebuilds the portfolio once, through its
constructor, which checks the ledger and the positions as the forward path does (#84).

Standard library only (core spec §4.2).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import DayReport, EngineState
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Currency, Money
from steadyhand.notes import Note
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import CashMovement, MovementKind, Portfolio
from steadyhand.risk import Halt, UnitValue
from steadyhand.types import Costs, Fill, Instrument, Order, Position, Side

SNAPSHOT_VERSION: Final = 1
"""The version this code writes, and the newest it reads."""

type SnapshotUpgrade = Callable[[dict[str, object]], dict[str, object]]
"""One step: a document of version N made into one of version N + 1."""

SNAPSHOT_UPGRADES: Final[Mapping[int, SnapshotUpgrade]] = {}
"""The step from each older version, keyed by the version it upgrades. None yet at version 1."""

SNAPSHOT_CURRENCIES: Final[Mapping[str, Currency]] = {IDR.code: IDR}
"""The currencies a snapshot can hold, by code: a saved state is always one this code reads."""

_UNREADABLE = (TypeError, ValueError)
"""What the readers below, and the engine's own constructors, raise for a bad document."""


class SnapshotError(ValueError):
    """A document this code cannot write or read."""


class SnapshotVersionError(SnapshotError):
    """A document written by a newer steadyhand. M5 exits with code 2."""

    def __init__(self, version: int, newest: int) -> None:
        super().__init__(
            f"this state was written by a newer steadyhand: its version is {version}, and this "
            f"one reads versions up to {newest}"
        )


def encode_state(state: EngineState) -> dict[str, object]:
    """*state* as a document of the current version."""
    holdings = state.holdings
    return {
        "version": SNAPSHOT_VERSION,
        "holdings": {
            "portfolio": _portfolio(holdings.portfolio),
            "pending": [_order(order) for order in holdings.pending],
            "entitlements": [_entitlement(e) for e in holdings.entitlements],
            "frozen": _pairs(holdings.frozen, str),
            "last_closes": _pairs(holdings.last_closes, _money),
            "claims": [_claim(claim) for claim in holdings.claims],
            "shortfall_since": _day_or_none(holdings.shortfall_since),
        },
        "units": {
            "units": str(state.units.units),
            "price": str(state.units.price),
            "high_water": str(state.units.high_water),
        },
        "halt": _halt(state.halt),
        "last_day": _day_or_none(state.last_day),
        "memory": dict(state.memory),
    }


def decode_state(document: object) -> EngineState:
    """The state *document* holds, upgraded first if it is older."""
    current = upgrade_snapshot(document)
    try:
        return _read_state(current)
    except _UNREADABLE as error:
        msg = f"the saved state cannot be read: {error}"
        raise SnapshotError(msg) from error


def encode_report(report: DayReport) -> dict[str, object]:
    """*report* as a document of the current version."""
    return {
        "version": SNAPSHOT_VERSION,
        "day": report.day.isoformat(),
        "fills": [_fill(fill) for fill in report.fills],
        "rejected": [{"order": _order(r.order), "reason": r.reason} for r in report.rejected],
        "cuts": [
            {"order": _order(c.order), "quantity": c.quantity, "reason": c.reason}
            for c in report.cuts
        ],
        "queued": [_order(order) for order in report.queued],
        "entitled": [_entitlement(e) for e in report.entitled],
        "paid": [_entitlement(e) for e in report.paid],
        "tax": _money(report.tax),
        "daily_cost": _money(report.daily_cost),
        "deposit": _money(report.deposit),
        "frozen": [[_instrument(i), reason] for i, reason in report.frozen],
        "halt": _halt(report.halt),
        "settled": _money(report.settled),
        "unsettled": _money(report.unsettled),
        "holdings_value": _money(report.holdings_value),
        "value": _money(report.value),
        "unit_price": str(report.unit_price),
        "warnings": [_note(note) for note in report.warnings],
        "notes": [_note(note) for note in report.notes],
    }


def decode_report(document: object) -> DayReport:
    """The day report *document* holds, upgraded first if it is older."""
    current = upgrade_snapshot(document)
    try:
        return _read_report(current)
    except _UNREADABLE as error:
        msg = f"the saved day report cannot be read: {error}"
        raise SnapshotError(msg) from error


def upgrade_snapshot(
    document: object,
    steps: Mapping[int, SnapshotUpgrade] = SNAPSHOT_UPGRADES,
    newest: int = SNAPSHOT_VERSION,
) -> dict[str, object]:
    """*document* brought up to version *newest*, one step at a time, oldest first."""
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(document, dict) or type(version) is not int or version < 1:
        msg = f"a snapshot needs a whole-number version from 1, got {version!r}"
        raise SnapshotError(msg)
    if version > newest:
        raise SnapshotVersionError(version, newest)
    upgraded: dict[str, object] = dict(document)
    while version < newest:
        upgraded = {**steps[version](upgraded), "version": version + 1}
        version += 1
    return upgraded


def to_json(document: Mapping[str, object]) -> str:
    """*document* as canonical JSON: sorted keys, no whitespace, ASCII only."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)


def from_json(text: str) -> object:
    """The document *text* holds."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        msg = f"a snapshot is not valid JSON: {error}"
        raise SnapshotError(msg) from error


def _code(currency: Currency) -> str:
    if SNAPSHOT_CURRENCIES.get(currency.code) != currency:
        msg = f"a snapshot cannot hold {currency.code} with {currency.minor_units} minor units"
        raise SnapshotError(msg)
    return currency.code


def _money(value: Money) -> dict[str, object]:
    return {"amount": value.amount, "currency": _code(value.currency)}


def _instrument(instrument: Instrument) -> dict[str, object]:
    return {
        "currency": _code(instrument.currency),
        "market": instrument.market,
        "symbol": instrument.symbol,
    }


def _order(order: Order) -> dict[str, object]:
    return {
        "instrument": _instrument(order.instrument),
        "side": order.side.value,
        "quantity": order.quantity,
        "placed_on": order.placed_on.isoformat(),
    }


def _fill(fill: Fill) -> dict[str, object]:
    return {
        "order": _order(fill.order),
        "day": fill.day.isoformat(),
        "quantity": fill.quantity,
        "price": _money(fill.price),
        "costs": {
            "fee": _money(fill.costs.fee),
            "levy": _money(fill.costs.levy),
            "tax": _money(fill.costs.tax),
        },
    }


def _portfolio(portfolio: Portfolio) -> dict[str, object]:
    return {
        "currency": _code(portfolio.currency),
        "positions": [
            {
                "instrument": _instrument(p.instrument),
                "quantity": p.quantity,
                "cost_basis": _money(p.cost_basis),
            }
            for p in portfolio.positions
        ],
        "ledger": [
            {
                "day": m.day.isoformat(),
                "kind": m.kind.value,
                "amount": _money(m.amount),
                "settles_on": m.settles_on.isoformat(),
            }
            for m in portfolio.ledger
        ],
    }


def _entitlement(entitlement: Entitlement) -> dict[str, object]:
    return {
        "instrument": _instrument(entitlement.instrument),
        "ex_date": entitlement.ex_date.isoformat(),
        "pay_date": entitlement.pay_date.isoformat(),
        "gross": _money(entitlement.gross),
    }


def _claim(claim: DividendClaim) -> dict[str, object]:
    return {
        "instrument": _instrument(claim.instrument),
        "ex_date": claim.ex_date.isoformat(),
        "pay_date": claim.pay_date.isoformat(),
        "gross": _money(claim.gross),
        "deadline": claim.deadline.isoformat(),
        "uncovered": _money(claim.uncovered),
        "protections": [
            {"amount": _money(p.amount), "until": p.until.isoformat()} for p in claim.protections
        ],
    }


def _pairs[V](mapping: Mapping[Instrument, V], encode: Callable[[V], object]) -> list[object]:
    ordered = sorted(mapping.items(), key=lambda item: (item[0].market, item[0].symbol))
    return [[_instrument(instrument), encode(value)] for instrument, value in ordered]


def _halt(halt: Halt | None) -> dict[str, object] | None:
    return None if halt is None else {"day": halt.day.isoformat(), "cause": halt.cause}


def _note(note: Note) -> dict[str, object]:
    return {"key": note.key, "text": note.text}


def _day_or_none(day: date | None) -> str | None:
    return None if day is None else day.isoformat()


def _fields(document: object, *names: str) -> tuple[object, ...]:
    """The values of *names* in *document*, which must hold exactly those fields."""
    if not isinstance(document, dict):
        msg = f"expected an object with {', '.join(names)}, got {type(document).__name__}"
        raise TypeError(msg)
    if set(document) != set(names):
        msg = f"expected the fields {sorted(names)}, got {sorted(document)}"
        raise ValueError(msg)
    return tuple(document[name] for name in names)


def _int(value: object) -> int:
    if type(value) is not int:
        msg = f"expected a whole number, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _str(value: object) -> str:
    if not isinstance(value, str):
        msg = f"expected a string, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        msg = f"expected a list, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _date(value: object) -> date:
    return date.fromisoformat(_str(value))


def _optional_date(value: object) -> date | None:
    return None if value is None else _date(value)


def _decimal(value: object) -> Decimal:
    text = _str(value)
    try:
        number = Decimal(text)
    except InvalidOperation:
        number = Decimal("NaN")
    if not number.is_finite():
        msg = f"expected a finite number, got {text!r}"
        raise ValueError(msg)
    return number


def _read_currency(value: object) -> Currency:
    code = _str(value)
    if code not in SNAPSHOT_CURRENCIES:
        msg = f"unknown currency {code!r}"
        raise ValueError(msg)
    return SNAPSHOT_CURRENCIES[code]


def _read_money(value: object) -> Money:
    amount, currency = _fields(value, "amount", "currency")
    return Money(_int(amount), _read_currency(currency))


def _read_instrument(value: object) -> Instrument:
    currency, market, symbol = _fields(value, "currency", "market", "symbol")
    return Instrument(_str(symbol), _str(market), _read_currency(currency))


def _read_order(value: object) -> Order:
    instrument, side, quantity, placed_on = _fields(
        value, "instrument", "side", "quantity", "placed_on"
    )
    return Order(_read_instrument(instrument), Side(side), _int(quantity), _date(placed_on))


def _read_fill(value: object) -> Fill:
    order, day, quantity, price, costs = _fields(
        value, "order", "day", "quantity", "price", "costs"
    )
    fee, levy, tax = _fields(costs, "fee", "levy", "tax")
    return Fill(
        _read_order(order),
        _date(day),
        _int(quantity),
        _read_money(price),
        Costs(_read_money(fee), _read_money(levy), _read_money(tax)),
    )


def _read_position(value: object) -> Position:
    instrument, quantity, cost_basis = _fields(value, "instrument", "quantity", "cost_basis")
    return Position(_read_instrument(instrument), _int(quantity), _read_money(cost_basis))


def _read_movement(value: object) -> CashMovement:
    day, kind, amount, settles_on = _fields(value, "day", "kind", "amount", "settles_on")
    return CashMovement(_date(day), MovementKind(kind), _read_money(amount), _date(settles_on))


def _read_portfolio(value: object) -> Portfolio:
    currency, positions, ledger = _fields(value, "currency", "positions", "ledger")
    return Portfolio(
        _read_currency(currency),
        tuple(_read_position(p) for p in _list(positions)),
        tuple(_read_movement(m) for m in _list(ledger)),
    )


def _read_entitlement(value: object) -> Entitlement:
    instrument, ex_date, pay_date, gross = _fields(
        value, "instrument", "ex_date", "pay_date", "gross"
    )
    return Entitlement(
        _read_instrument(instrument), _date(ex_date), _date(pay_date), _read_money(gross)
    )


def _read_claim(value: object) -> DividendClaim:
    instrument, ex_date, pay_date, gross, deadline, uncovered, protections = _fields(
        value, "instrument", "ex_date", "pay_date", "gross", "deadline", "uncovered", "protections"
    )
    return DividendClaim(
        _read_instrument(instrument),
        _date(ex_date),
        _date(pay_date),
        _read_money(gross),
        _date(deadline),
        _read_money(uncovered),
        tuple(_read_protection(p) for p in _list(protections)),
    )


def _read_protection(value: object) -> Protection:
    amount, until = _fields(value, "amount", "until")
    return Protection(_read_money(amount), _date(until))


def _read_pairs[V](value: object, read: Callable[[object], V]) -> dict[Instrument, V]:
    pairs: dict[Instrument, V] = {}
    for pair in _list(value):
        instrument, item = _list(pair)
        pairs[_read_instrument(instrument)] = read(item)
    return pairs


def _read_halt(value: object) -> Halt | None:
    if value is None:
        return None
    day, cause = _fields(value, "day", "cause")
    return Halt(_date(day), _str(cause))


def _read_note(value: object) -> Note:
    key, text = _fields(value, "key", "text")
    return Note(_str(key), _str(text))


def _read_memory(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        msg = f"expected the strategy memory as an object, got {type(value).__name__}"
        raise TypeError(msg)
    return {_str(key): _str(item) for key, item in value.items()}


def _read_state(document: dict[str, object]) -> EngineState:
    _version, holdings, units, halt, last_day, memory = _fields(
        document, "version", "holdings", "units", "halt", "last_day", "memory"
    )
    portfolio, pending, entitlements, frozen, last_closes, claims, shortfall_since = _fields(
        holdings,
        "portfolio",
        "pending",
        "entitlements",
        "frozen",
        "last_closes",
        "claims",
        "shortfall_since",
    )
    count, price, high_water = _fields(units, "units", "price", "high_water")
    return EngineState(
        Holdings(
            _read_portfolio(portfolio),
            tuple(_read_order(order) for order in _list(pending)),
            tuple(_read_entitlement(e) for e in _list(entitlements)),
            _read_pairs(frozen, _str),
            _read_pairs(last_closes, _read_money),
            tuple(_read_claim(claim) for claim in _list(claims)),
            _optional_date(shortfall_since),
        ),
        UnitValue(_decimal(count), _decimal(price), _decimal(high_water)),
        _read_halt(halt),
        _optional_date(last_day),
        _read_memory(memory),
    )


def _read_report(document: dict[str, object]) -> DayReport:
    names = (
        "version",
        "day",
        "fills",
        "rejected",
        "cuts",
        "queued",
        "entitled",
        "paid",
        "tax",
        "daily_cost",
        "deposit",
        "frozen",
        "halt",
        "settled",
        "unsettled",
        "holdings_value",
        "value",
        "unit_price",
        "warnings",
        "notes",
    )
    field = dict(zip(names, _fields(document, *names), strict=True))
    return DayReport(
        day=_date(field["day"]),
        fills=tuple(_read_fill(fill) for fill in _list(field["fills"])),
        rejected=tuple(_read_rejected(r) for r in _list(field["rejected"])),
        cuts=tuple(_read_cut(cut) for cut in _list(field["cuts"])),
        queued=tuple(_read_order(order) for order in _list(field["queued"])),
        entitled=tuple(_read_entitlement(e) for e in _list(field["entitled"])),
        paid=tuple(_read_entitlement(e) for e in _list(field["paid"])),
        tax=_read_money(field["tax"]),
        daily_cost=_read_money(field["daily_cost"]),
        deposit=_read_money(field["deposit"]),
        frozen=tuple(_read_frozen(pair) for pair in _list(field["frozen"])),
        halt=_read_halt(field["halt"]),
        settled=_read_money(field["settled"]),
        unsettled=_read_money(field["unsettled"]),
        holdings_value=_read_money(field["holdings_value"]),
        value=_read_money(field["value"]),
        unit_price=_decimal(field["unit_price"]),
        warnings=tuple(_read_note(note) for note in _list(field["warnings"])),
        notes=tuple(_read_note(note) for note in _list(field["notes"])),
    )


def _read_rejected(value: object) -> Rejected:
    order, reason = _fields(value, "order", "reason")
    return Rejected(_read_order(order), _str(reason))


def _read_cut(value: object) -> Cut:
    order, quantity, reason = _fields(value, "order", "quantity", "reason")
    return Cut(_read_order(order), _int(quantity), _str(reason))


def _read_frozen(value: object) -> tuple[Instrument, str]:
    instrument, reason = _list(value)
    return _read_instrument(instrument), _str(reason)
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1323 passed=1323 -->
Expected: every command exits 0; 1323 passed, 100% branch coverage; the performance step passes its five tests (the ten-year backtest and the four start-up budgets).

- [ ] **Step 7: Mutations.** Run M220–M236 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M5b S5 the snapshot codec and its round trips`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 2: M5b S6 The state database: schema, migrations and StateStore

**Acceptance criteria (story text):**
1. `StateStore(path)` opens or creates `state.sqlite`, `0600` whatever the umask, and brings it to `len(MIGRATIONS)` in one transaction; opening it again keeps what was saved. A database from a newer steadyhand-idx raises `StateSchemaError` and is left as it was (M5 §6.3).
2. The `account` table holds one row. `Account(opened_on, strategy, state, settings)` takes its `last_day` from the state, exists only with a day run, and its settings cannot be changed in place.
3. `save(account, *, after, report, audit) -> bool` writes the account, the day's report and its audit lines in one `BEGIN IMMEDIATE` transaction, only if the last day saved is still `after`, and otherwise writes nothing and returns `False` (scope decision 6). A day whose report cannot be written, proved with a real trigger, leaves everything as it was. A save without a report changes only the account and the audit log.
4. `day_reports`, `audit` and `runs` refuse any update or delete (scope decision 7). `finish(run, audit)` records a run and its audit lines in order; a `Run`'s time is in UTC and its outcome one of the four the database accepts. A second writer waits up to the 30-second busy timeout.
5. `report(day)`, `reports()`, `days()`, `audit()` and `runs()` read back what was saved, oldest first; a saved row that cannot be read is refused naming it. The store's one reader of saved notes is exempted by name, as in Task 1.
6. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M237–M246 and M264 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand-idx/src/steadyhand_idx/state.py`, `tests/cli/test_state.py`
- Modify: `tests/meta/{key_walk,test_note_keys}.py`

**Interfaces:**
- Consumes: Task 1's codec; `paths.private_file`.
- Produces: in `tests/meta/key_walk.py`, `SAVED_NOTE_READERS` in place of Task 1's `SAVED_NOTE_READER`: each module's one reader, by file. In `steadyhand_idx.state`: `STATE_FILE`, `BUSY_TIMEOUT_SECONDS`, `MIGRATIONS`, `StateSchemaError`, `Outcome` (`ran`, `up to date`, `stopped`, `halted`), `Account(opened_on, strategy, state, settings)` with `last_day`, `AuditLine(day, note)`, `Run(at, target, days, outcome, detail)`, `StateStore(path)` with `schema_version`, `account()`, `save(...)`, `finish(run, audit)`, `report(day)`, `reports()`, `days()`, `audit()`, `runs()`, `close()`.

- [ ] **Step 1: Branch.** `git switch -c m5/s6-state origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/test_state.py`** (new)

<!-- file: tests/cli/test_state.py -->
```python
"""The paper account's state database (M5 spec §6.3, §6.4, §9.2 "Migrations")."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from cli_world import mode, umask

from steadyhand import (
    DATA_BAR_MISSING,
    IDR,
    DayReport,
    EngineState,
    Money,
    Note,
)
from steadyhand_idx.state import (
    BUSY_TIMEOUT_SECONDS,
    MIGRATIONS,
    STATE_FILE,
    Account,
    AuditLine,
    Outcome,
    Run,
    StateSchemaError,
    StateStore,
)

D1 = date(2026, 1, 5)
D2 = date(2026, 1, 6)
D3 = date(2026, 1, 7)
SETTINGS = {"account.monthly_contribution_idr": "0", "risk.max_weight": "0.10"}


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def account(day: date, cash: int = 10_000_000, strategy: str = "buy-and-hold") -> Account:
    state = replace(EngineState.opening(rp(cash), D1), last_day=day)
    return Account(D1, strategy, state, SETTINGS)


def report(day: date) -> DayReport:
    zero = rp(0)
    return DayReport(
        day=day,
        fills=(),
        rejected=(),
        cuts=(),
        queued=(),
        entitled=(),
        paid=(),
        tax=zero,
        daily_cost=zero,
        deposit=zero,
        frozen=(),
        halt=None,
        settled=rp(10_000_000),
        unsettled=zero,
        holdings_value=zero,
        value=rp(10_000_000),
        unit_price=Decimal(1),
        warnings=(),
    )


def line(day: date, text: str) -> AuditLine:
    return AuditLine(day, Note(DATA_BAR_MISSING, text))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StateStore]:
    with StateStore(tmp_path / STATE_FILE) as opened:
        yield opened


def saved_through_d2(store: StateStore) -> None:
    assert store.save(account(D1), after=None, report=report(D1), audit=(line(D1, "one"),))
    assert store.save(account(D2), after=D1, report=report(D2), audit=(line(D2, "two"),))


def raw(path: Path) -> closing[sqlite3.Connection]:
    """A second connection to the file, closed when its ``with`` block ends.

    Python 3.13 warns about a connection left for the garbage collector, and ``-W error``
    fails whichever test is running when it is collected.
    """
    return closing(sqlite3.connect(path, isolation_level=None))


# The schema.


def test_a_new_database_reaches_the_current_schema_with_its_tables_and_triggers(
    tmp_path: Path,
) -> None:
    with StateStore(tmp_path / STATE_FILE) as store:
        assert store.schema_version == len(MIGRATIONS) == 1
    with raw(tmp_path / STATE_FILE) as database:
        rows = database.execute("SELECT type, name FROM sqlite_master").fetchall()
    assert {name for kind, name in rows if kind == "table"} == {
        "account",
        "day_reports",
        "audit",
        "runs",
    }
    assert {name for kind, name in rows if kind == "trigger"} == {
        "day_reports_are_kept",
        "day_reports_are_never_removed",
        "audit_is_kept",
        "audit_is_never_removed",
        "runs_are_kept",
        "runs_are_never_removed",
    }


def test_opening_again_keeps_what_was_saved(tmp_path: Path) -> None:
    with StateStore(tmp_path / STATE_FILE) as store:
        saved_through_d2(store)
    with StateStore(tmp_path / STATE_FILE) as store:
        assert (store.schema_version, store.days()) == (1, (D1, D2))


def test_a_database_from_a_newer_steadyhand_idx_is_refused_and_left_as_it_was(
    tmp_path: Path,
) -> None:
    path = tmp_path / STATE_FILE
    with raw(path) as database:
        database.execute("PRAGMA user_version = 2")
    with pytest.raises(
        StateSchemaError,
        match=(
            rf"^{path} is at state schema 2, newer than this steadyhand-idx knows \(1\); "
            r"upgrade steadyhand-idx$"
        ),
    ):
        StateStore(path)
    with raw(path) as database:
        assert database.execute("PRAGMA user_version").fetchone() == (2,)
        assert database.execute("SELECT name FROM sqlite_master").fetchall() == []


@pytest.mark.parametrize("value", [0o000, 0o022, 0o277])
def test_the_database_file_is_0600_whatever_the_umask(tmp_path: Path, value: int) -> None:
    with umask(value), StateStore(tmp_path / STATE_FILE):
        pass
    assert mode(tmp_path / STATE_FILE) == 0o600


def test_a_second_run_waits_up_to_the_busy_timeout(store: StateStore) -> None:
    assert BUSY_TIMEOUT_SECONDS == 30.0
    assert store._db.execute("PRAGMA busy_timeout").fetchone() == (30_000,)


def test_the_account_table_holds_one_row(store: StateStore, tmp_path: Path) -> None:
    saved_through_d2(store)
    with (
        raw(tmp_path / STATE_FILE) as database,
        pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"),
    ):
        database.execute(
            "INSERT INTO account VALUES (2, '2026-01-05', 'x', '{}', '2026-01-05', '{}')"
        )


# Saving days.


def test_there_is_nothing_before_the_first_day(store: StateStore) -> None:
    assert store.account() is None
    assert (store.reports(), store.days(), store.audit(), store.runs()) == ((), (), (), ())
    assert store.report(D1) is None


def test_the_first_day_is_saved_with_its_report_and_its_audit_lines(store: StateStore) -> None:
    first = account(D1)
    assert store.save(first, after=None, report=report(D1), audit=(line(D1, "one"),))
    assert store.account() == first
    assert (store.reports(), store.days()) == ((report(D1),), (D1,))
    assert (store.report(D1), store.report(D2)) == (report(D1), None)
    assert store.audit() == (line(D1, "one"),)


def test_each_later_day_is_saved_after_the_one_before_in_order(store: StateStore) -> None:
    saved_through_d2(store)
    assert store.account() == account(D2)
    assert store.reports() == (report(D1), report(D2))
    assert store.audit() == (line(D1, "one"), line(D2, "two"))


def test_a_save_from_a_day_that_is_no_longer_the_last_writes_nothing(store: StateStore) -> None:
    saved_through_d2(store)
    assert not store.save(account(D3), after=D1, report=report(D3), audit=(line(D3, "late"),))
    assert not store.save(account(D3), after=None, report=report(D3))
    assert store.account() == account(D2)
    assert store.days() == (D1, D2)
    assert store.audit() == (line(D1, "one"), line(D2, "two"))


def test_a_save_without_a_report_changes_only_the_account_and_the_audit_log(
    store: StateStore,
) -> None:
    saved_through_d2(store)
    changed = Account(D1, "other", account(D2).state, {"risk.max_weight": "0.08"})
    assert store.save(changed, after=D2, audit=(line(D2, "switched"),))
    assert store.account() == changed
    assert store.days() == (D1, D2)
    assert store.audit()[-1] == line(D2, "switched")


def test_a_day_whose_report_cannot_be_written_leaves_everything_as_it_was(
    store: StateStore, tmp_path: Path
) -> None:
    saved_through_d2(store)
    with raw(tmp_path / STATE_FILE) as database:
        database.execute(
            "CREATE TRIGGER refuse BEFORE INSERT ON day_reports "
            "BEGIN SELECT RAISE(ABORT, 'refused by the test'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="refused by the test"):
            store.save(account(D3), after=D2, report=report(D3), audit=(line(D3, "three"),))
        assert store.account() == account(D2)
        assert store.days() == (D1, D2)
        assert store.audit() == (line(D1, "one"), line(D2, "two"))
        database.execute("DROP TRIGGER refuse")
        assert store.save(account(D3), after=D2, report=report(D3), audit=(line(D3, "three"),))
        assert store.days() == (D1, D2, D3)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE day_reports SET report = '{}'",
        "DELETE FROM day_reports",
        "UPDATE audit SET line = 'changed'",
        "DELETE FROM audit",
        "UPDATE runs SET detail = 'changed'",
        "DELETE FROM runs",
    ],
)
def test_the_logs_are_append_only(store: StateStore, tmp_path: Path, statement: str) -> None:
    saved_through_d2(store)
    store.finish(Run(datetime(2026, 1, 6, 10, tzinfo=UTC), D2, (D1, D2), Outcome.RAN))
    table = statement.split()[1 if statement.startswith("UPDATE") else 2]
    with (
        raw(tmp_path / STATE_FILE) as database,
        pytest.raises(sqlite3.IntegrityError, match=f"^{table} is append-only$"),
    ):
        database.execute(statement)
    assert (len(store.days()), len(store.audit()), len(store.runs())) == (2, 2, 1)


# Runs.


def test_each_run_is_recorded_in_order_with_its_audit_lines(store: StateStore) -> None:
    runs = [
        Run(datetime(2026, 1, 5, 10, tzinfo=UTC), D1, (D1,), Outcome.RAN),
        Run(datetime(2026, 1, 5, 11, tzinfo=UTC), D1, (), Outcome.UP_TO_DATE, "already"),
        Run(datetime(2026, 1, 6, 10, tzinfo=UTC), D2, (), Outcome.STOPPED, "stale"),
        Run(datetime(2026, 1, 7, 10, tzinfo=UTC), D3, (D2, D3), Outcome.HALTED, "halted"),
    ]
    store.finish(runs[0])
    store.finish(runs[1])
    store.finish(runs[2], (line(D2, "stopped"),))
    store.finish(runs[3])
    assert store.runs() == tuple(runs)
    assert store.audit() == (line(D2, "stopped"),)


def test_the_outcomes_are_the_four_the_database_accepts() -> None:
    assert [outcome.value for outcome in Outcome] == ["ran", "up to date", "stopped", "halted"]


WIB = timezone(timedelta(hours=7))


@pytest.mark.parametrize(
    "at", [datetime.fromisoformat("2026-01-05T10:00"), datetime(2026, 1, 5, 17, tzinfo=WIB)]
)
def test_a_runs_time_is_in_utc(at: datetime) -> None:
    with pytest.raises(ValueError, match=r"^a run's time is in UTC, got 2026-01-05T"):
        Run(at, D1, (), Outcome.RAN)


# Accounts.


def test_an_account_is_saved_only_with_a_day_run() -> None:
    with pytest.raises(ValueError, match=r"^an account is saved only with a day run$"):
        Account(D1, "buy-and-hold", EngineState.opening(rp(1_000), D1))


def test_an_accounts_settings_cannot_be_changed_in_place() -> None:
    settings = dict(SETTINGS)
    saved = Account(D1, "buy-and-hold", account(D1).state, settings)
    settings["risk.max_weight"] = "0.50"
    assert saved.settings == SETTINGS
    with pytest.raises(TypeError):
        saved.settings["risk.max_weight"] = "0.50"  # type: ignore[index]


@pytest.mark.parametrize(
    ("statement", "read", "message"),
    [
        (
            "UPDATE account SET settings = '{\"risk.max_weight\":1}'",
            "account",
            r"^the saved settings are not a table of text values: \{\"risk.max_weight\":1\}$",
        ),
        (
            "UPDATE account SET settings = '[]'",
            "account",
            r"^the saved settings are not a table of text values: \[\]$",
        ),
        (
            (
                "INSERT INTO runs (at, target, days, outcome, detail) VALUES "
                "('2026-01-05T10:00:00+00:00', '2026-01-05', '{\"days\":[5]}', 'ran', '')"
            ),
            "runs",
            r"^a run's days are not a list of dates: \{\"days\":\[5\]\}$",
        ),
        (
            (
                "INSERT INTO runs (at, target, days, outcome, detail) VALUES "
                "('2026-01-05T10:00:00+00:00', '2026-01-05', '[]', 'ran', '')"
            ),
            "runs",
            r"^a run's days are not a list of dates: \[\]$",
        ),
    ],
)
def test_saved_rows_that_cannot_be_read_are_refused(
    store: StateStore, tmp_path: Path, statement: str, read: str, message: str
) -> None:
    saved_through_d2(store)
    with raw(tmp_path / STATE_FILE) as database:
        database.execute(statement)
    with pytest.raises(ValueError, match=message):
        getattr(store, read)()
```

**`tests/meta/key_walk.py`** (changed: 1 edit)

<!-- edit: tests/meta/key_walk.py -->
Replace:
```python
TERM_PREFIX = "term."
SAVED_NOTES = ENGINE / "snapshot.py"
SAVED_NOTE_READER = "_read_note"
"""The one function allowed to build a ``Note`` from a key that is not a constant: the snapshot
reader, which rebuilds a saved note exactly as it was written (M5 spec §6.3). The note was built
from a constant when it was made; read back, its key is data, and it cannot drift."""

```
with:
```python
TERM_PREFIX = "term."
SAVED_NOTE_READERS = {ENGINE / "snapshot.py": "_read_note", IDX / "state.py": "_audit_line"}
"""The functions allowed to build a ``Note`` from a key that is not a constant, one per module:
each reads a saved note back exactly as it was written (M5 spec §6.3). The note was built from a
constant when it was made; read back, its key is data, and it cannot drift."""

```

**`tests/meta/test_note_keys.py`** (changed: 4 edits)

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
import re

from key_walk import (
```
with:
```python
import re
from pathlib import Path

import pytest
from key_walk import (
```

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
    NOTE_MODULES,
    SAVED_NOTE_READER,
    SAVED_NOTES,
    TERM_MODULE,
```
with:
```python
    NOTE_MODULES,
    SAVED_NOTE_READERS,
    TERM_MODULE,
```

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python

def test_the_snapshot_reader_is_the_one_note_built_from_saved_data() -> None:
    source = SAVED_NOTES.read_text(encoding="utf-8")
    assert len([key for key in note_keys(source) if "not a constant" in key]) == 1
    assert note_keys(source, reader=SAVED_NOTE_READER) == []

```
with:
```python

@pytest.mark.parametrize("path", sorted(SAVED_NOTE_READERS), ids=lambda path: path.name)
def test_each_saved_note_reader_is_its_modules_one_note_built_from_saved_data(path: Path) -> None:
    names = {name for name, _ in constants_in(NOTE_MODULES)}
    source = path.read_text(encoding="utf-8")
    assert len([key for key in note_keys(source) if key not in names]) == 1
    read = note_keys(source, reader=SAVED_NOTE_READERS[path])
    assert [key for key in read if key not in names] == []

```

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
        for path, source in sources.items()
        for key in note_keys(source, reader=SAVED_NOTE_READER if path == SAVED_NOTES else None)
    ]
```
with:
```python
        for path, source in sources.items()
        for key in note_keys(source, reader=SAVED_NOTE_READERS.get(path))
    ]
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/state.py`** (new, as stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/state.py -->
```python
"""The paper account's state database, ``state.sqlite`` in the data directory (M5 spec §6.3).

One ``account`` row holds the encoded ``EngineState``, the opening day, the strategy, the last
day run and the settings that day ran with. Three tables are append-only, and triggers refuse
any change to them: ``day_reports`` (one encoded report per trading day), ``audit`` (a key and
a line per event, core spec §9.7) and ``runs`` (one row per ``paper run``).

``StateStore.save`` writes a day in one ``BEGIN IMMEDIATE`` transaction: the account, the day's
report and its audit lines, or nothing. Inside it the store reads ``last_day`` again and writes
only if it is still the day the caller started from, so a day run by two processes at once is
saved exactly once (§6.4). The file is created ``0600`` (§4.1), and its schema is upgraded in
place on ``BarCache``'s pattern (core spec §9.3).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Final

from steadyhand import (
    DayReport,
    EngineState,
    Note,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
)
from steadyhand_idx.paths import private_file

STATE_FILE: Final = "state.sqlite"
BUSY_TIMEOUT_SECONDS: Final = 30.0
"""How long a second ``paper run`` waits for the first one's write lock before failing."""

# Applied in order; PRAGMA user_version records how many have run. Never edit a shipped entry:
# add a new one, so a database made by an older release upgrades in place.
MIGRATIONS: Final[tuple[str, ...]] = (
    """
    CREATE TABLE account (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        opened_on TEXT NOT NULL,
        strategy TEXT NOT NULL,
        state TEXT NOT NULL,
        last_day TEXT NOT NULL,
        settings TEXT NOT NULL
    ) STRICT;
    CREATE TABLE day_reports (
        day TEXT PRIMARY KEY,
        report TEXT NOT NULL
    ) STRICT;
    CREATE TABLE audit (
        id INTEGER PRIMARY KEY,
        day TEXT NOT NULL,
        key TEXT NOT NULL,
        line TEXT NOT NULL
    ) STRICT;
    CREATE TABLE runs (
        id INTEGER PRIMARY KEY,
        at TEXT NOT NULL,
        target TEXT NOT NULL,
        days TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK (outcome IN ('ran', 'up to date', 'stopped', 'halted')),
        detail TEXT NOT NULL
    ) STRICT;
    CREATE TRIGGER day_reports_are_kept BEFORE UPDATE ON day_reports
        BEGIN SELECT RAISE(ABORT, 'day_reports is append-only'); END;
    CREATE TRIGGER day_reports_are_never_removed BEFORE DELETE ON day_reports
        BEGIN SELECT RAISE(ABORT, 'day_reports is append-only'); END;
    CREATE TRIGGER audit_is_kept BEFORE UPDATE ON audit
        BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    CREATE TRIGGER audit_is_never_removed BEFORE DELETE ON audit
        BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    CREATE TRIGGER runs_are_kept BEFORE UPDATE ON runs
        BEGIN SELECT RAISE(ABORT, 'runs is append-only'); END;
    CREATE TRIGGER runs_are_never_removed BEFORE DELETE ON runs
        BEGIN SELECT RAISE(ABORT, 'runs is append-only'); END;
    """,
)


class StateSchemaError(RuntimeError):
    """The state database was written by a newer steadyhand-idx than this one. M5 exits 2."""


class Outcome(Enum):
    """How a ``paper run`` ended (M5 spec §6.3)."""

    RAN = "ran"
    UP_TO_DATE = "up to date"
    STOPPED = "stopped"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class Account:
    """The paper account: opened on ``opened_on`` with ``strategy``, its state after the last
    day run, and the settings that day ran with, by configuration key."""

    opened_on: date
    strategy: str
    state: EngineState
    settings: Mapping[str, str] = field(default_factory=dict)
    last_day: date = field(init=False)
    """The last day run: the state's, which an account always has."""

    def __post_init__(self) -> None:
        raise NotImplementedError("Account.__post_init__")


@dataclass(frozen=True, slots=True)
class AuditLine:
    """One line of the audit log: what happened on ``day``, under its note's key (core §9.7)."""

    day: date
    note: Note


@dataclass(frozen=True, slots=True)
class Run:
    """One ``paper run``: when it ran (UTC), its target day, the days it ran, how it ended."""

    at: datetime
    target: date
    days: tuple[date, ...]
    outcome: Outcome
    detail: str = ""

    def __post_init__(self) -> None:
        raise NotImplementedError("Run.__post_init__")


class StateStore:
    """The state database. Use it as a context manager, or call ``close()``."""

    def __init__(self, path: Path) -> None:
        raise NotImplementedError("StateStore.__init__")

    def __enter__(self) -> StateStore:
        raise NotImplementedError("StateStore.__enter__")

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        raise NotImplementedError("StateStore.__exit__")

    def close(self) -> None:
        raise NotImplementedError("StateStore.close")

    @property
    def schema_version(self) -> int:
        raise NotImplementedError("StateStore.schema_version")

    def account(self) -> Account | None:
        """The account, or ``None`` before the first day is run."""
        raise NotImplementedError("StateStore.account")

    def save(
        self,
        account: Account,
        *,
        after: date | None,
        report: DayReport | None = None,
        audit: Sequence[AuditLine] = (),
    ) -> bool:
        """Write *account*, *report* and *audit* in one transaction, if the last day saved is
        still *after* (``None``: no account yet). Otherwise write nothing and return ``False``:
        another run got there first."""
        raise NotImplementedError("StateStore.save")

    def finish(self, run: Run, audit: Sequence[AuditLine] = ()) -> None:
        """Record *run*, and any *audit* lines that belong to no saved day, in one transaction."""
        raise NotImplementedError("StateStore.finish")

    def report(self, day: date) -> DayReport | None:
        """The report saved for *day*, or ``None``."""
        raise NotImplementedError("StateStore.report")

    def reports(self) -> tuple[DayReport, ...]:
        """Every saved report, oldest first."""
        raise NotImplementedError("StateStore.reports")

    def days(self) -> tuple[date, ...]:
        """Every day with a saved report, oldest first."""
        raise NotImplementedError("StateStore.days")

    def audit(self) -> tuple[AuditLine, ...]:
        """The audit log, in the order it was written."""
        raise NotImplementedError("StateStore.audit")

    def runs(self) -> tuple[Run, ...]:
        """Every recorded run, in the order they ended."""
        raise NotImplementedError("StateStore.runs")

    def _last_day(self) -> date | None:
        raise NotImplementedError("StateStore._last_day")

    def _insert_audit(self, audit: Sequence[AuditLine]) -> None:
        raise NotImplementedError("StateStore._insert_audit")

    def _migrate(self) -> None:
        raise NotImplementedError("StateStore._migrate")

    @contextmanager
    def _write(self) -> Iterator[None]:
        """One transaction, taking the write lock at once, rolled back on any error."""
        raise NotImplementedError("StateStore._write")


def _statements(script: str) -> Iterator[str]:
    """The statements of *script*, each whole: ``sqlite3.complete_statement`` decides where one
    ends, so the semicolons inside a trigger's body do not split it."""
    raise NotImplementedError("_statements")


def _settings(text: str) -> dict[str, str]:
    raise NotImplementedError("_settings")


def _days(text: str) -> list[str]:
    raise NotImplementedError("_days")


def _audit_line(day: str, key: str, line: str) -> AuditLine:
    raise NotImplementedError("_audit_line")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1354 failed=30 -->
Expected: 1354 run, and pytest's summary reads `11 failed, 19 errors`: 30 in all. The 19 errors, and 10 of the failures, are `NotImplementedError`: most tests open a `StateStore`, whose stubbed constructor raises, in their setup. The last failure is `test_each_saved_note_reader_is_its_modules_one_note_built_from_saved_data[state.py]`, `assert 0 == 1`, since the stubbed reader builds no `Note`. `test_the_outcomes_are_the_four_the_database_accepts` passes against the stubs, since an `Enum` is written in the red phase; mutation M264 shows it guards the database's own check.

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/state.py`** (replaces the stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/state.py -->
```python
"""The paper account's state database, ``state.sqlite`` in the data directory (M5 spec §6.3).

One ``account`` row holds the encoded ``EngineState``, the opening day, the strategy, the last
day run and the settings that day ran with. Three tables are append-only, and triggers refuse
any change to them: ``day_reports`` (one encoded report per trading day), ``audit`` (a key and
a line per event, core spec §9.7) and ``runs`` (one row per ``paper run``).

``StateStore.save`` writes a day in one ``BEGIN IMMEDIATE`` transaction: the account, the day's
report and its audit lines, or nothing. Inside it the store reads ``last_day`` again and writes
only if it is still the day the caller started from, so a day run by two processes at once is
saved exactly once (§6.4). The file is created ``0600`` (§4.1), and its schema is upgraded in
place on ``BarCache``'s pattern (core spec §9.3).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Final

from steadyhand import (
    DayReport,
    EngineState,
    Note,
    decode_report,
    decode_state,
    encode_report,
    encode_state,
    from_json,
    to_json,
)
from steadyhand_idx.paths import private_file

STATE_FILE: Final = "state.sqlite"
BUSY_TIMEOUT_SECONDS: Final = 30.0
"""How long a second ``paper run`` waits for the first one's write lock before failing."""

# Applied in order; PRAGMA user_version records how many have run. Never edit a shipped entry:
# add a new one, so a database made by an older release upgrades in place.
MIGRATIONS: Final[tuple[str, ...]] = (
    """
    CREATE TABLE account (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        opened_on TEXT NOT NULL,
        strategy TEXT NOT NULL,
        state TEXT NOT NULL,
        last_day TEXT NOT NULL,
        settings TEXT NOT NULL
    ) STRICT;
    CREATE TABLE day_reports (
        day TEXT PRIMARY KEY,
        report TEXT NOT NULL
    ) STRICT;
    CREATE TABLE audit (
        id INTEGER PRIMARY KEY,
        day TEXT NOT NULL,
        key TEXT NOT NULL,
        line TEXT NOT NULL
    ) STRICT;
    CREATE TABLE runs (
        id INTEGER PRIMARY KEY,
        at TEXT NOT NULL,
        target TEXT NOT NULL,
        days TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK (outcome IN ('ran', 'up to date', 'stopped', 'halted')),
        detail TEXT NOT NULL
    ) STRICT;
    CREATE TRIGGER day_reports_are_kept BEFORE UPDATE ON day_reports
        BEGIN SELECT RAISE(ABORT, 'day_reports is append-only'); END;
    CREATE TRIGGER day_reports_are_never_removed BEFORE DELETE ON day_reports
        BEGIN SELECT RAISE(ABORT, 'day_reports is append-only'); END;
    CREATE TRIGGER audit_is_kept BEFORE UPDATE ON audit
        BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    CREATE TRIGGER audit_is_never_removed BEFORE DELETE ON audit
        BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    CREATE TRIGGER runs_are_kept BEFORE UPDATE ON runs
        BEGIN SELECT RAISE(ABORT, 'runs is append-only'); END;
    CREATE TRIGGER runs_are_never_removed BEFORE DELETE ON runs
        BEGIN SELECT RAISE(ABORT, 'runs is append-only'); END;
    """,
)


class StateSchemaError(RuntimeError):
    """The state database was written by a newer steadyhand-idx than this one. M5 exits 2."""


class Outcome(Enum):
    """How a ``paper run`` ended (M5 spec §6.3)."""

    RAN = "ran"
    UP_TO_DATE = "up to date"
    STOPPED = "stopped"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class Account:
    """The paper account: opened on ``opened_on`` with ``strategy``, its state after the last
    day run, and the settings that day ran with, by configuration key."""

    opened_on: date
    strategy: str
    state: EngineState
    settings: Mapping[str, str] = field(default_factory=dict)
    last_day: date = field(init=False)
    """The last day run: the state's, which an account always has."""

    def __post_init__(self) -> None:
        if self.state.last_day is None:
            msg = "an account is saved only with a day run"
            raise ValueError(msg)
        object.__setattr__(self, "last_day", self.state.last_day)
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))


@dataclass(frozen=True, slots=True)
class AuditLine:
    """One line of the audit log: what happened on ``day``, under its note's key (core §9.7)."""

    day: date
    note: Note


@dataclass(frozen=True, slots=True)
class Run:
    """One ``paper run``: when it ran (UTC), its target day, the days it ran, how it ended."""

    at: datetime
    target: date
    days: tuple[date, ...]
    outcome: Outcome
    detail: str = ""

    def __post_init__(self) -> None:
        if self.at.tzinfo is not UTC:
            msg = f"a run's time is in UTC, got {self.at.isoformat()}"
            raise ValueError(msg)


class StateStore:
    """The state database. Use it as a context manager, or call ``close()``."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db = sqlite3.connect(
            private_file(path), timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None
        )
        try:
            self._migrate()
        except BaseException:
            self._db.close()
            raise

    def __enter__(self) -> StateStore:
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

    def account(self) -> Account | None:
        """The account, or ``None`` before the first day is run."""
        row = self._db.execute(
            "SELECT opened_on, strategy, state, settings FROM account"
        ).fetchone()
        if row is None:
            return None
        opened_on, strategy, state, settings = row
        return Account(
            date.fromisoformat(opened_on),
            strategy,
            decode_state(from_json(state)),
            _settings(settings),
        )

    def save(
        self,
        account: Account,
        *,
        after: date | None,
        report: DayReport | None = None,
        audit: Sequence[AuditLine] = (),
    ) -> bool:
        """Write *account*, *report* and *audit* in one transaction, if the last day saved is
        still *after* (``None``: no account yet). Otherwise write nothing and return ``False``:
        another run got there first."""
        with self._write():
            if self._last_day() != after:
                return False
            self._db.execute(
                "INSERT INTO account (id, opened_on, strategy, state, last_day, settings) "
                "VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET "
                "opened_on = excluded.opened_on, strategy = excluded.strategy, "
                "state = excluded.state, last_day = excluded.last_day, "
                "settings = excluded.settings",
                (
                    account.opened_on.isoformat(),
                    account.strategy,
                    to_json(encode_state(account.state)),
                    account.last_day.isoformat(),
                    to_json(dict(account.settings)),
                ),
            )
            if report is not None:
                self._db.execute(
                    "INSERT INTO day_reports (day, report) VALUES (?, ?)",
                    (report.day.isoformat(), to_json(encode_report(report))),
                )
            self._insert_audit(audit)
            return True

    def finish(self, run: Run, audit: Sequence[AuditLine] = ()) -> None:
        """Record *run*, and any *audit* lines that belong to no saved day, in one transaction."""
        with self._write():
            self._insert_audit(audit)
            self._db.execute(
                "INSERT INTO runs (at, target, days, outcome, detail) VALUES (?, ?, ?, ?, ?)",
                (
                    run.at.isoformat(),
                    run.target.isoformat(),
                    to_json({"days": [day.isoformat() for day in run.days]}),
                    run.outcome.value,
                    run.detail,
                ),
            )

    def report(self, day: date) -> DayReport | None:
        """The report saved for *day*, or ``None``."""
        row = self._db.execute(
            "SELECT report FROM day_reports WHERE day = ?", (day.isoformat(),)
        ).fetchone()
        return None if row is None else decode_report(from_json(row[0]))

    def reports(self) -> tuple[DayReport, ...]:
        """Every saved report, oldest first."""
        rows = self._db.execute("SELECT report FROM day_reports ORDER BY day").fetchall()
        return tuple(decode_report(from_json(text)) for (text,) in rows)

    def days(self) -> tuple[date, ...]:
        """Every day with a saved report, oldest first."""
        rows = self._db.execute("SELECT day FROM day_reports ORDER BY day").fetchall()
        return tuple(date.fromisoformat(day) for (day,) in rows)

    def audit(self) -> tuple[AuditLine, ...]:
        """The audit log, in the order it was written."""
        rows = self._db.execute("SELECT day, key, line FROM audit ORDER BY id").fetchall()
        return tuple(_audit_line(day, key, line) for day, key, line in rows)

    def runs(self) -> tuple[Run, ...]:
        """Every recorded run, in the order they ended."""
        rows = self._db.execute(
            "SELECT at, target, days, outcome, detail FROM runs ORDER BY id"
        ).fetchall()
        return tuple(
            Run(
                datetime.fromisoformat(at).astimezone(UTC),
                date.fromisoformat(target),
                tuple(date.fromisoformat(day) for day in _days(days)),
                Outcome(outcome),
                detail,
            )
            for at, target, days, outcome, detail in rows
        )

    def _last_day(self) -> date | None:
        row = self._db.execute("SELECT last_day FROM account").fetchone()
        return None if row is None else date.fromisoformat(row[0])

    def _insert_audit(self, audit: Sequence[AuditLine]) -> None:
        self._db.executemany(
            "INSERT INTO audit (day, key, line) VALUES (?, ?, ?)",
            [(line.day.isoformat(), line.note.key, line.note.text) for line in audit],
        )

    def _migrate(self) -> None:
        with self._write():
            version = self.schema_version
            if version > len(MIGRATIONS):
                msg = (
                    f"{self._path} is at state schema {version}, newer than this "
                    f"steadyhand-idx knows ({len(MIGRATIONS)}); upgrade steadyhand-idx"
                )
                raise StateSchemaError(msg)
            for number in range(version, len(MIGRATIONS)):
                # One statement at a time: executescript() would commit this transaction first.
                # A trigger's body holds its own semicolons, so statements split at "END;".
                for statement in _statements(MIGRATIONS[number]):
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


def _statements(script: str) -> Iterator[str]:
    """The statements of *script*, each whole: ``sqlite3.complete_statement`` decides where one
    ends, so the semicolons inside a trigger's body do not split it."""
    pending = ""
    for piece in script.split(";"):
        pending += piece + ";"
        if sqlite3.complete_statement(pending):
            if pending.strip(" \n;"):
                yield pending.strip()
            pending = ""


def _settings(text: str) -> dict[str, str]:
    settings = from_json(text)
    if not isinstance(settings, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in settings.items()
    ):
        msg = f"the saved settings are not a table of text values: {text}"
        raise ValueError(msg)
    return settings


def _days(text: str) -> list[str]:
    document = from_json(text)
    days = document.get("days") if isinstance(document, dict) else None
    if not isinstance(days, list) or not all(isinstance(day, str) for day in days):
        msg = f"a run's days are not a list of dates: {text}"
        raise ValueError(msg)
    return days


def _audit_line(day: str, key: str, line: str) -> AuditLine:
    return AuditLine(date.fromisoformat(day), Note(key, line))
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1354 passed=1354 -->
Expected: every command exits 0; 1354 passed, 100% branch coverage; the performance step passes its five tests.

- [ ] **Step 7: Mutations.** Run M237–M246 and M264 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(cli): M5b S6 the state database: schema, migrations and StateStore`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 3: M5b S7 paper run: day selection, catch-up, the public fetch, atomicity, stops, halts and configuration changes

**Acceptance criteria (story text):**
1. `target_day(now, rules)` is today in Jakarta when it is a trading day and the time there is at or after 16:30 (`CLOSE`), else the trading day before; the tests cover 16:29:59 and 16:30:00 on a Monday, a Saturday and Chinese New Year. `days_to_run(last, target, rules)` is every trading day after `last` up to the target, oldest first, or the target alone before the first run (M5 §6.1).
2. The first `paper run` opens the account on the target day with the starting cash (`EngineState.opening`), writes `paper.account.opened`, and runs that day. Running twice changes nothing but the run log, which gains one `up to date` row. Missed days are caught up in order, each saved; 30 days to run proceed, 31 exit 2 writing nothing (`CatchUpError`), and 31 with `--catch-up` proceed.
3. `steadyhand.day_inputs(market, start, end)` is `backtest`'s fetch, public, giving each trading day its inputs oldest first; `paper.py` calls it over the whole range from the opening day (M5 §6.2). A paper account run day by day, and a year caught up in one run, each end in the same state and reports as `backtest` over the same days.
4. A configured strategy other than the saved one exits 2, naming both and the `paper switch` command, and writes nothing (`StrategyChangedError`, scope decision 11).
5. An impossible price, and a day the source has not published (`StaleDataError`, scope decision 9), stop the run with exit 3, keeping the days before it, recording a `stopped` run and a `paper.run.stopped` line (scope decision 10). A day that fails to save leaves the account at the day before. Days another run saves meanwhile are left to it, and two runs started together run each day exactly once (scope decision 12).
6. `Halt.cause` is a keyed `Note` (scope decision 15). A halt is saved with its day and its audit line; later days still run without ordering, and every run exits 3 printing the day lines, then the halt and the exact `resume` command (`AccountHaltedError`).
7. Each day's settings are `settings_of(config)` (scope decision 8). A changed setting writes `paper.setting.changed` naming the key and both values, and applies from the next day run; a changed starting cash is noted once (`paper.setting.starting_cash_ignored`) and changes nothing. The day's decisions write `paper.order.queued`, `paper.order.cut` and `paper.order.skipped` lines (core §9.7).
8. `EXIT_CODES` gains `SnapshotVersionError`, `StateSchemaError`, `CatchUpError` and `StrategyChangedError` at 2, and `StaleDataError` and `AccountHaltedError` at 3; a test pins every row. The seven `paper.*` keys ship with the lessons `paper.daily_run` and `paper.settings`, and `risk.limits` explains the two halt keys.
9. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M247–M263 and M265 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand_idx/{paper,paper_pages}.py`, `.../steadyhand_idx/training/lessons/en/paper.{daily_run,settings}.md`, `tests/cli/test_paper_run.py`
- Modify: `.../steadyhand/{__init__,backtest,notes,risk,snapshot}.py`, `.../steadyhand/training/lessons/en/risk.limits.md`, `.../steadyhand_idx/{cache,cli,notes,reports}.py`, `scripts/record_golden.py`, `tests/cli/{cli_world,test_cli,test_reports}.py`, `tests/engine/test_{backtest,engine,risk,snapshot}.py`, `tests/meta/test_terms.py`

**Interfaces:**
- Consumes: Tasks 1–2; M5a's `World`, `Context`, `EXIT_CODES`, `Page` and `render`; `JAKARTA`.
- Produces: `steadyhand.day_inputs(market, start, end) -> tuple[DayInputs, ...]`; `steadyhand.RISK_HALT_DAILY_LOSS`, `RISK_HALT_DRAWDOWN`. In `steadyhand_idx.paper`: `CLOSE`, `CATCH_UP_CAP`, `STARTING_CASH`, `CatchUpError`, `StrategyChangedError`, `StaleDataError`, `AccountHaltedError`, `PaperRun(target, reports, halt, outcome)`, `target_day(now, rules)`, `days_to_run(last, target, rules)`, `settings_of(config)`, `run_paper(store, config, market, now, *, catch_up)`. In `steadyhand_idx.paper_pages`: `paper_run_page(done)`. In `steadyhand_idx.notes`: the seven `PAPER_*` keys.

- [ ] **Step 1: Branch.** `git switch -c m5/s7-paper-run origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/cli_world.py`** (changed: 2 edits)

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
from itertools import product
from pathlib import Path
```
with:
```python
from itertools import product
from multiprocessing.synchronize import Event
from pathlib import Path
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python

SCRIPT = Path(sys.executable).with_name("steadyhand-idx")
```
with:
```python

def paper_process(home: str, now: str, start: Event) -> None:
    """One ``paper run --catch-up`` in a process of its own, for the concurrency test: it waits
    for *start*, runs over the recorded data at *now*, and exits with the command's code."""
    start.wait()
    cli = Cli(Path(home), recorded_source, datetime.fromisoformat(now))
    sys.exit(cli("paper", "run", "--catch-up").code)


SCRIPT = Path(sys.executable).with_name("steadyhand-idx")
```

**`tests/cli/test_cli.py`** (changed: 5 edits)

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
    IDR,
    DataUnavailableError,
    DataValidationError,
    Instrument,
    InvalidBarError,
    NoTradingDaysError,
    UnavailableDaysError,
```
with:
```python
    IDR,
    RISK_HALT_DAILY_LOSS,
    DataUnavailableError,
    DataValidationError,
    Halt,
    Instrument,
    InvalidBarError,
    Note,
    NoTradingDaysError,
    SnapshotError,
    SnapshotVersionError,
    UnavailableDaysError,
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
from steadyhand_idx.output import UnknownNameError

```
with:
```python
from steadyhand_idx.output import UnknownNameError
from steadyhand_idx.paper import (
    AccountHaltedError,
    CatchUpError,
    StaleDataError,
    StrategyChangedError,
)
from steadyhand_idx.state import StateSchemaError

```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
        (NoTradingDaysError, 2),
        (DataUnavailableError, 3),
        (DataValidationError, 3),
        (InvalidBarError, 3),
    ) == EXIT_CODES
```
with:
```python
        (NoTradingDaysError, 2),
        (SnapshotVersionError, 2),
        (StateSchemaError, 2),
        (CatchUpError, 2),
        (StrategyChangedError, 2),
        (DataUnavailableError, 3),
        (DataValidationError, 3),
        (InvalidBarError, 3),
        (StaleDataError, 3),
        (AccountHaltedError, 3),
    ) == EXIT_CODES
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
        (lambda: NoTradingDaysError("x"), 2),
        (lambda: DataUnavailableError("x"), 3),
```
with:
```python
        (lambda: NoTradingDaysError("x"), 2),
        (lambda: SnapshotVersionError(2, 1), 2),
        (lambda: StateSchemaError("x"), 2),
        (lambda: CatchUpError(31, date(2021, 2, 1)), 2),
        (lambda: StrategyChangedError("buy-and-hold", "retired"), 2),
        (lambda: DataUnavailableError("x"), 3),
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
        (lambda: InvalidBarError("x"), 3),
        (lambda: ConfigRewriteError("x"), 1),
```
with:
```python
        (lambda: InvalidBarError("x"), 3),
        (lambda: StaleDataError(date(2021, 2, 1)), 3),
        (
            lambda: AccountHaltedError(
                Halt(date(2021, 2, 1), Note(RISK_HALT_DAILY_LOSS, "x")), "buy-and-hold"
            ),
            3,
        ),
        (lambda: SnapshotError("x"), 1),
        (lambda: ConfigRewriteError("x"), 1),
```

**`tests/cli/test_paper_run.py`** (new)

<!-- file: tests/cli/test_paper_run.py -->
```python
"""``paper run``: which days it runs, what it saves, and how it stops (M5 spec §6, §9.2).

Every run goes through ``main`` with the recorded Yahoo answers, the real bar cache and the real
state database in a temporary data directory, at a fixed time in Jakarta.
"""

import multiprocessing
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta, timezone
from functools import cache
from pathlib import Path

import pytest
from cli_world import GOLDEN_CONFIG, Cli, Result, market_cli, paper_process, recorded_source
from record_golden import END, START

from steadyhand import (
    RISK_HALT_DAILY_LOSS,
    BacktestResult,
    Bar,
    BuyAndHold,
    CorporateAction,
    DataSource,
    Instrument,
    Market,
    backtest,
    day_inputs,
)
from steadyhand_idx.cli import SourceFactory
from steadyhand_idx.config import load
from steadyhand_idx.notes import (
    PAPER_ACCOUNT_OPENED,
    PAPER_ORDER_CUT,
    PAPER_ORDER_QUEUED,
    PAPER_RUN_STOPPED,
    PAPER_SETTING_CHANGED,
    PAPER_SETTING_STARTING_CASH_IGNORED,
)
from steadyhand_idx.paper import CATCH_UP_CAP, CLOSE, days_to_run, settings_of, target_day
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.state import STATE_FILE, Account, Outcome, StateStore
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe

WIB = timezone(timedelta(hours=7))


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


@cache
def trading_days() -> tuple[date, ...]:
    """The golden window's trading days, from the IDX calendar."""
    return days_to_run(START - timedelta(days=1), END, rules())


def at(day: date, hour: int = 17, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=WIB)


def paper(tmp_path: Path, config: str = GOLDEN_CONFIG) -> Cli:
    return market_cli(tmp_path / "home", config)


def run_on(cli: Cli, day: date, *extra: str) -> Result:
    return replace(cli, now=at(day))("paper", "run", *extra)


@contextmanager
def opened(cli: Cli) -> Iterator[StateStore]:
    with StateStore(cli.home / STATE_FILE) as store:
        yield store


def tables(cli: Cli) -> dict[str, list[tuple[object, ...]]]:
    """Every row of the account, the day reports and the audit log, as SQLite holds them."""
    database = sqlite3.connect(cli.home / STATE_FILE)
    try:
        return {
            table: database.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608
            for table in ("account", "day_reports", "audit")
        }
    finally:
        database.close()


def golden_backtest(cli: Cli, end: date) -> BacktestResult:
    """``buy-and-hold`` from the golden window's first day to *end*, as ``backtest`` runs it over
    the same configuration, universe files and recorded data. Without the income goal: its
    report reads five years before *end* (M4 spec §8), which the recordings do not cover for an
    early *end*, and it changes neither the states nor the day reports."""
    config = load(cli.config)
    universe = Lq45Universe(
        Lq45Membership.load(config.lq45_members), Exclusions.load(config.exclusions)
    )
    with recorded_source(cli.home) as source:
        market = Market(universe, source, IdxMarketRules(broker_fees=config.broker_fees))
        return backtest(BuyAndHold(), market, START, end, replace(config.settings, goal=None))


# Which day is the target (M5 spec §6.1).


@pytest.mark.parametrize(
    ("now", "target"),
    [
        (at(date(2021, 2, 1), 16, 29, 59), date(2021, 1, 29)),
        (at(date(2021, 2, 1), 16, 30, 0), date(2021, 2, 1)),
        (datetime(2021, 2, 1, 9, 30, tzinfo=UTC), date(2021, 2, 1)),
        (at(date(2021, 2, 6), 16, 29, 59), date(2021, 2, 5)),
        (at(date(2021, 2, 6), 16, 30, 0), date(2021, 2, 5)),
        (at(date(2021, 2, 12), 16, 29, 59), date(2021, 2, 11)),
        (at(date(2021, 2, 12), 16, 30, 0), date(2021, 2, 11)),
        (at(date(2021, 2, 15), 9, 0), date(2021, 2, 11)),
    ],
    ids=[
        "Monday before 16:30",
        "Monday at 16:30",
        "Monday at 16:30 given in UTC",
        "Saturday before 16:30",
        "Saturday at 16:30",
        "Chinese New Year before 16:30",
        "Chinese New Year at 16:30",
        "Monday morning after the holiday",
    ],
)
def test_the_target_is_the_latest_completed_trading_day(now: datetime, target: date) -> None:
    assert CLOSE.isoformat() == "16:30:00"
    assert not rules().is_trading_day(date(2021, 2, 6))
    assert not rules().is_trading_day(date(2021, 2, 12))
    assert target_day(now, rules()) == target


def test_the_days_to_run_are_the_trading_days_after_the_last_one_run() -> None:
    assert days_to_run(None, date(2021, 2, 1), rules()) == (date(2021, 2, 1),)
    assert days_to_run(date(2021, 2, 11), date(2021, 2, 16), rules()) == (
        date(2021, 2, 15),
        date(2021, 2, 16),
    )
    assert days_to_run(date(2021, 2, 16), date(2021, 2, 16), rules()) == ()


# The first run, and running twice (M5 spec §6.1, §9.2 "Idempotency").


def test_the_first_run_opens_the_account_on_the_target_day_and_runs_it(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    result = run_on(cli, START)
    assert result.code == 0, result.err
    assert result.out.startswith(
        "2021-02-01: 0 fill(s), 4 order(s) queued, value IDR 100,000,000\n\n"
        "Ran 1 day(s): 2021-02-01. Read a day's report with: steadyhand-idx report\n"
    )
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        assert (account.opened_on, account.strategy, account.last_day) == (
            START,
            "buy-and-hold",
            START,
        )
        assert account.settings == settings_of(load(cli.config))
        lines = [(line.day, line.note.key, line.note.text) for line in store.audit()]
        assert lines[0] == (
            START,
            PAPER_ACCOUNT_OPENED,
            (
                "opened the paper account on 2021-02-01 with IDR 100,000,000 and the "
                "buy-and-hold strategy"
            ),
        )
        assert lines[1:] == [
            (START, PAPER_ORDER_QUEUED, f"queued: buy {order} at the next open")
            for order in ("4100 ASII", "700 BBCA", "7700 TLKM", "3500 UNVR")
        ]
        assert [(run.outcome, run.target, run.days) for run in store.runs()] == [
            (Outcome.RAN, START, (START,))
        ]


def test_running_twice_changes_nothing_but_the_run_log(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    assert run_on(cli, START).code == 0
    before = tables(cli)
    again = run_on(cli, START)
    assert (again.code, again.err) == (0, "")
    assert again.out.startswith("already up to date for 2021-02-01\n")
    assert tables(cli) == before
    with opened(cli) as store:
        assert [(run.outcome, run.days, run.detail) for run in store.runs()] == [
            (Outcome.RAN, (START,), "ran 1 day(s)"),
            (Outcome.UP_TO_DATE, (), "already up to date for 2021-02-01"),
        ]


def test_missed_days_are_caught_up_in_order_each_saved(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, trading_days()[2])
    assert result.code == 0, result.err
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


# The catch-up cap (M5 spec §6.1, §9.2).


def test_thirty_days_to_run_proceed(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, trading_days()[CATCH_UP_CAP])
    assert result.code == 0, result.err
    with opened(cli) as store:
        assert store.days() == trading_days()[: CATCH_UP_CAP + 1]


def test_thirty_one_days_to_run_are_refused_and_nothing_is_written(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    before = tables(cli)
    result = run_on(cli, trading_days()[CATCH_UP_CAP + 1])
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: 31 trading days to run since 2021-02-01, more than 30; run "
        "steadyhand-idx paper run --catch-up to run them all\n"
    )
    assert tables(cli) == before
    with opened(cli) as store:
        assert len(store.runs()) == 1


def test_thirty_one_days_to_run_proceed_with_catch_up(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, trading_days()[CATCH_UP_CAP + 1], "--catch-up")
    assert result.code == 0, result.err
    with opened(cli) as store:
        assert store.days() == trading_days()[: CATCH_UP_CAP + 2]


# The golden invariant (M5 spec §6.2, §9.2).


def test_a_paper_account_run_day_by_day_ends_where_the_backtest_does(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    days = trading_days()[:12]
    for day in days:
        assert run_on(cli, day).code == 0
    expected = golden_backtest(cli, days[-1]).run
    with opened(cli) as store:
        assert store.reports() == expected.reports
        account = store.account()
        assert account is not None
        assert account.state == expected.final


def test_a_year_caught_up_in_one_run_ends_where_the_backtest_does(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    result = run_on(cli, END, "--catch-up")
    assert result.code == 0, result.err
    expected = golden_backtest(cli, END).run
    assert len(expected.reports) == len(trading_days()) == 248
    with opened(cli) as store:
        assert store.reports() == expected.reports
        account = store.account()
        assert account is not None
        assert account.state == expected.final


def test_the_public_fetch_gives_each_trading_day_its_inputs_oldest_first(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    config = load(cli.config)
    universe = Lq45Universe(
        Lq45Membership.load(config.lq45_members), Exclusions.load(config.exclusions)
    )
    with recorded_source(cli.home) as source:
        market = Market(universe, source, rules())
        inputs = day_inputs(market, START, trading_days()[4])
        with pytest.raises(
            ValueError, match=r"^the range ends on 2021-01-31, before it starts on 2021-02-01$"
        ):
            day_inputs(market, START, date(2021, 1, 31))
    assert [found.day for found in inputs] == list(trading_days()[:5])
    assert all(found.members == universe.members_on(found.day) for found in inputs)


# Refusals (M5 spec §6.5, §8.1).


def test_a_changed_strategy_is_refused_naming_both_and_the_switch_command(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    with opened(cli) as store:
        account = store.account()
        assert account is not None
        retired = Account(account.opened_on, "retired", account.state, account.settings)
        assert store.save(retired, after=START)
    before = tables(cli)
    result = run_on(cli, trading_days()[1])
    assert (result.code, result.out) == (2, "")
    assert result.err == (
        "steadyhand-idx: steadyhand.toml names the strategy buy-and-hold, but the paper account "
        "runs retired; to change it, run: steadyhand-idx paper switch buy-and-hold\n"
    )
    assert tables(cli) == before


def test_paper_needs_a_command(tmp_path: Path) -> None:
    result = paper(tmp_path)("paper")
    assert result.code == 2
    assert result.err.startswith("steadyhand-idx: the following arguments are required: command")


# Stops (M5 spec §6.5, §11).


@dataclass(frozen=True, slots=True)
class Edited:
    """The recorded data with each bar passed through ``edit``, which may drop it."""

    inner: DataSource
    edit: Callable[[Bar], Bar | None]

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        edited = (self.edit(bar) for bar in self.inner.bars(instrument, start, end))
        return [bar for bar in edited if bar is not None]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return self.inner.corporate_actions(instrument, start, end)


def edited(edit: Callable[[Bar], Bar | None]) -> SourceFactory:
    @contextmanager
    def source(folder: Path) -> Iterator[DataSource]:
        with recorded_source(folder) as recorded:
            yield Edited(recorded, edit)

    return source


def doubling(symbol: str, day: date) -> SourceFactory:
    """One stock's close doubled on one day: an impossible price."""
    return edited(
        lambda bar: (
            replace(bar, high=bar.close * 2, close=bar.close * 2)
            if (bar.instrument.symbol, bar.day) == (symbol, day)
            else bar
        )
    )


def unpublished(day: date) -> SourceFactory:
    """No bar at all on *day*, as when Yahoo has not yet published the close (M5 spec §11)."""
    return edited(lambda bar: None if bar.day == day else bar)


def test_an_impossible_price_stops_the_run_keeping_the_days_before_it(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    bad = trading_days()[3]
    result = run_on(replace(cli, source=doubling("BBCA", bad)), trading_days()[4])
    assert result.code == 3
    assert result.err.startswith(f"steadyhand-idx: BBCA on {bad}: the close ")
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        runs = store.runs()
        assert (runs[-1].outcome, runs[-1].days) == (Outcome.STOPPED, trading_days()[1:3])
        stop = store.audit()[-1]
        assert (stop.day, stop.note.key) == (bad, PAPER_RUN_STOPPED)
        assert stop.note.text.startswith(f"stopped on {bad}: BBCA on {bad}: the close ")
    assert run_on(cli, trading_days()[4]).code == 0
    with opened(cli) as store:
        assert store.days() == trading_days()[:5]


def test_a_day_the_source_has_not_published_stops_the_run(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    first = run_on(replace(cli, source=unpublished(START)), START)
    assert (first.code, first.out) == (3, "")
    assert first.err == (
        "steadyhand-idx: the data source has no bars for 2021-02-01 yet, so nothing was run for "
        "it; run paper run again later\n"
    )
    with opened(cli) as store:
        assert store.account() is None
        assert [(run.outcome, run.days) for run in store.runs()] == [(Outcome.STOPPED, ())]
        assert [(line.day, line.note.key) for line in store.audit()] == [(START, PAPER_RUN_STOPPED)]
    assert run_on(cli, START).code == 0
    late = trading_days()[2]
    assert run_on(replace(cli, source=unpublished(late)), late).code == 3
    with opened(cli) as store:
        assert store.days() == trading_days()[:2]
        assert store.runs()[-1].days == trading_days()[1:2]
    assert run_on(cli, late).code == 0


# Halts (M5 spec §6.5).

JUMPY_CONFIG = GOLDEN_CONFIG.replace(
    '[risk]\nmax_weight = "0.25"\n', '[risk]\nmax_weight = "0.25"\ndaily_loss_limit = "0.001"\n'
)


def test_a_halt_is_saved_with_its_day_and_every_later_run_exits_3(tmp_path: Path) -> None:
    assert JUMPY_CONFIG != GOLDEN_CONFIG
    cli = paper(tmp_path, JUMPY_CONFIG)
    assert run_on(cli, START).code == 0
    halted = run_on(cli, trading_days()[1])
    assert halted.code == 3
    assert halted.out.startswith("2021-02-02: 4 fill(s), 0 order(s) queued")
    assert halted.err == (
        "steadyhand-idx: the paper account halted on 2021-02-02: daily loss limit: the unit "
        "value fell 2.38%, the limit is 0.10%; no orders are placed until you resume it with: "
        "steadyhand-idx resume buy-and-hold\n"
    )
    with opened(cli) as store:
        halt = store.audit()[-1]
        assert (halt.day, halt.note.key) == (trading_days()[1], RISK_HALT_DAILY_LOSS)
    later = run_on(cli, trading_days()[2])
    assert later.code == 3
    assert later.out.startswith("2021-02-03: 0 fill(s), 0 order(s) queued")
    assert run_on(cli, trading_days()[2]).code == 3
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        assert [run.outcome for run in store.runs()] == [
            Outcome.RAN,
            Outcome.HALTED,
            Outcome.HALTED,
            Outcome.HALTED,
        ]


# Configuration changes (M5 spec §6.5).


def test_a_changed_setting_is_written_in_the_audit_log_and_applies_from_the_next_day(
    tmp_path: Path,
) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    cli.config.write_text(
        GOLDEN_CONFIG.replace('max_weight = "0.25"', 'max_weight = "0.20"'), encoding="utf-8"
    )
    run_on(cli, trading_days()[1])
    with opened(cli) as store:
        changed = [line for line in store.audit() if line.note.key == PAPER_SETTING_CHANGED]
        assert [(line.day, line.note.text) for line in changed] == [
            (
                trading_days()[1],
                "risk.max_weight changed from 0.25 to 0.20; it applies from 2021-02-02",
            )
        ]
        account = store.account()
        assert account is not None
        assert account.settings["risk.max_weight"] == "0.20"


def test_a_changed_starting_cash_is_noted_once_and_changes_nothing(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    cli.config.write_text(
        GOLDEN_CONFIG.replace("starting_cash_idr = 100_000_000", "starting_cash_idr = 200_000_000"),
        encoding="utf-8",
    )
    run_on(cli, trading_days()[1])
    run_on(cli, trading_days()[2])
    expected = golden_backtest(paper(tmp_path / "unchanged"), trading_days()[2]).run
    with opened(cli) as store:
        ignored = [
            line for line in store.audit() if line.note.key == PAPER_SETTING_STARTING_CASH_IGNORED
        ]
        assert [(line.day, line.note.text) for line in ignored] == [
            (
                trading_days()[1],
                (
                    "account.starting_cash_idr changed from 100000000 to 200000000; it is used "
                    "only when the account opens, so the account's cash is unchanged"
                ),
            )
        ]
        assert store.reports() == expected.reports


def test_the_settings_a_day_ran_with_are_recorded_by_configuration_key(tmp_path: Path) -> None:
    config = load(paper(tmp_path).config)
    assert settings_of(config) == {
        "account.starting_cash_idr": "100000000",
        "account.monthly_contribution_idr": "0",
        "account.broker_fees": "custom",
        "goal.monthly_income_target_idr": "1000000",
        "risk.max_weight": "0.25",
        "risk.daily_loss_limit": "0.05",
        "risk.max_drawdown": "0.25",
        "risk.max_volume_participation": "0.10",
        "dividends.pay_lag_trading_days": "14",
        "tax.dividend_reinvestment_exemption": "false",
    }
    no_goal = replace(config, settings=replace(config.settings, goal=None))
    assert settings_of(no_goal)["goal.monthly_income_target_idr"] == "0"


# Atomicity and concurrency (M5 spec §6.4, §9.2).


def test_a_day_that_fails_to_save_leaves_the_account_at_the_day_before(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    before = tables(cli)
    database = sqlite3.connect(cli.home / STATE_FILE, isolation_level=None)
    database.execute(
        "CREATE TRIGGER refuse BEFORE INSERT ON day_reports "
        "BEGIN SELECT RAISE(ABORT, 'refused by the test'); END"
    )
    failed = run_on(cli, trading_days()[1])
    assert failed.code == 1
    assert failed.err.startswith("steadyhand-idx: refused by the test\n")
    assert tables(cli) == before
    database.execute("DROP TRIGGER refuse")
    database.close()
    assert run_on(cli, trading_days()[1]).code == 0
    with opened(cli) as store:
        assert store.days() == trading_days()[:2]


@dataclass(frozen=True, slots=True)
class Interrupted:
    """The recorded data, which runs *interrupt* once, on the first read: as if another
    ``paper run`` worked while this one was fetching."""

    inner: DataSource
    interrupt: Callable[[], object]
    done: list[bool]

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        if not self.done:
            self.done.append(True)
            self.interrupt()
        return self.inner.bars(instrument, start, end)

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return self.inner.corporate_actions(instrument, start, end)


def test_days_another_run_saves_meanwhile_are_left_to_it(tmp_path: Path) -> None:
    cli = paper(tmp_path)
    run_on(cli, START)
    target = trading_days()[3]

    @contextmanager
    def interrupted(folder: Path) -> Iterator[DataSource]:
        with recorded_source(folder) as recorded:
            yield Interrupted(recorded, lambda: run_on(cli, target), [])

    result = run_on(replace(cli, source=interrupted), target)
    assert result.code == 0, result.err
    assert result.out.startswith("already up to date for 2021-02-04\n")
    with opened(cli) as store:
        assert store.days() == trading_days()[:4]
        assert [(run.outcome, run.days) for run in store.runs()] == [
            (Outcome.RAN, (START,)),
            (Outcome.RAN, trading_days()[1:4]),
            (Outcome.UP_TO_DATE, ()),
        ]


def test_two_runs_started_together_run_each_day_exactly_once(tmp_path: Path) -> None:
    together = paper(tmp_path / "together")
    alone = paper(tmp_path / "alone")
    for cli in (together, alone):
        run_on(cli, START)
    target = at(trading_days()[8])
    assert run_on(alone, trading_days()[8]).code == 0
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    processes = [
        context.Process(target=paper_process, args=(str(together.home), target.isoformat(), start))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=120)
    assert [process.exitcode for process in processes] == [0, 0]
    assert tables(together) == tables(alone)
    with opened(together) as store:
        assert store.days() == trading_days()[:9]
        assert len(store.runs()) == 3
```

**`tests/cli/test_reports.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python
    IDR,
    BacktestResult,
```
with:
```python
    IDR,
    RISK_HALT_DAILY_LOSS,
    BacktestResult,
```

<!-- edit: tests/cli/test_reports.py -->
Replace:
```python
    assert halt is not None
    line = f"buy-and-hold stopped ordering on {halt.day}: {halt.cause}"
    assert line in backtest_page(result, ()).lines
    summary, _ = backtest_files(result, tmp_path)
```
with:
```python
    assert halt is not None
    line = f"buy-and-hold stopped ordering on {halt.day}: {halt.cause.text}"
    page = backtest_page(result, ())
    assert line in page.lines
    assert halt.cause.key == RISK_HALT_DAILY_LOSS
    assert RISK_HALT_DAILY_LOSS in page.keys
    summary, _ = backtest_files(result, tmp_path)
```

**`tests/engine/test_backtest.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_MISSING, DATA_BAR_REFUSED, Note
from steadyhand.risk import RiskLimits
```
with:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_MISSING, DATA_BAR_REFUSED, RISK_HALT_DAILY_LOSS, Note
from steadyhand.risk import RiskLimits
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    assert result.run.halt.day == date(2025, 7, 7)
    assert result.run.halt.cause == (
        "daily loss limit: the unit value fell 7.46%, the limit is 5.00%"
    )
```
with:
```python
    assert result.run.halt.day == date(2025, 7, 7)
    assert result.run.halt.cause == Note(
        RISK_HALT_DAILY_LOSS, "daily loss limit: the unit value fell 7.46%, the limit is 5.00%"
    )
```

**`tests/engine/test_engine.py`** (changed: 5 edits)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    EXEMPTION_DEADLINE_MISSED,
    Note,
```
with:
```python
    EXEMPTION_DEADLINE_MISSED,
    RISK_HALT_DAILY_LOSS,
    Note,
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert report.halt.day == D3
    assert report.halt.cause.startswith("daily loss limit: the unit value fell ")
    assert (report.queued, state.holdings.pending) == ((), ())
```
with:
```python
    assert report.halt.day == D3
    assert report.halt.cause.key == RISK_HALT_DAILY_LOSS
    assert report.halt.cause.text.startswith("daily loss limit: the unit value fell ")
    assert (report.queued, state.holdings.pending) == ((), ())
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    due = Entitlement(BBCA, D1, D2, rp(12_500))
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)), state.units, Halt(D1, "test"), D1
    )
    after, report = run_day(
```
with:
```python
    due = Entitlement(BBCA, D1, D2, rp(12_500))
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)),
        state.units,
        Halt(D1, Note(RISK_HALT_DAILY_LOSS, "test")),
        D1,
    )
    after, report = run_day(
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)), state.units, Halt(D1, "test"), D1
    )
```
with:
```python
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)),
        state.units,
        Halt(D1, Note(RISK_HALT_DAILY_LOSS, "test")),
        D1,
    )
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    holdings = Holdings(state.holdings.portfolio, claims=(claim,))
    current = EngineState(holdings, state.units, Halt(D1, "test"), D1)
    kept: list[tuple[date | None, Money]] = []
```
with:
```python
    holdings = Holdings(state.holdings.portfolio, claims=(claim,))
    current = EngineState(holdings, state.units, Halt(D1, Note(RISK_HALT_DAILY_LOSS, "test")), D1)
    kept: list[tuple[date | None, Money]] = []
```

**`tests/engine/test_risk.py`** (changed: 4 edits)

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
from steadyhand.money import IDR, Money
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
```
with:
```python
from steadyhand.money import IDR, Money
from steadyhand.notes import RISK_HALT_DAILY_LOSS, RISK_HALT_DRAWDOWN, Note
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    halt = RiskManager(rules()).halt(fund("1"), fund("0.95"), DAY)
    assert halt == Halt(DAY, "daily loss limit: the unit value fell 5.00%, the limit is 5.00%")
    assert RiskManager(rules()).halt(fund("1"), fund("0.9501"), DAY) is None
```
with:
```python
    halt = RiskManager(rules()).halt(fund("1"), fund("0.95"), DAY)
    cause = "daily loss limit: the unit value fell 5.00%, the limit is 5.00%"
    assert halt == Halt(DAY, Note(RISK_HALT_DAILY_LOSS, cause))
    assert RiskManager(rules()).halt(fund("1"), fund("0.9501"), DAY) is None
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    halt = manager.halt(fund("0.76", "1"), fund("0.75", "1"), DAY)
    assert halt == Halt(
        DAY,
        "drawdown kill switch: the unit value is 25.00% below its high-water mark, "
        "the limit is 25.00%",
    )
    assert manager.halt(fund("0.76", "1"), fund("0.7501", "1"), DAY) is None
```
with:
```python
    halt = manager.halt(fund("0.76", "1"), fund("0.75", "1"), DAY)
    cause = (
        "drawdown kill switch: the unit value is 25.00% below its high-water mark, "
        "the limit is 25.00%"
    )
    assert halt == Halt(DAY, Note(RISK_HALT_DRAWDOWN, cause))
    assert manager.halt(fund("0.76", "1"), fund("0.7501", "1"), DAY) is None
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
def test_a_halt_needs_a_day_and_a_cause() -> None:
    with pytest.raises(ValueError, match=r"^a halt needs a cause$"):
        Halt(DAY, " ")
    with pytest.raises(TypeError, match=r"^halt day must be a date, got str$"):
        Halt("2025-06-02", "x")  # type: ignore[arg-type]
```
with:
```python
def test_a_halt_needs_a_day_and_a_cause() -> None:
    with pytest.raises(TypeError, match=r"^cause must be a Note, got str$"):
        Halt(DAY, "daily loss limit")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^halt day must be a date, got str$"):
        Halt("2025-06-02", Note(RISK_HALT_DAILY_LOSS, "x"))  # type: ignore[arg-type]
```

**`tests/engine/test_snapshot.py`** (changed: 4 edits)

<!-- edit: tests/engine/test_snapshot.py -->
Replace:
```python
    IDR,
    SNAPSHOT_CURRENCIES,
```
with:
```python
    IDR,
    RISK_HALT_DAILY_LOSS,
    SNAPSHOT_CURRENCIES,
```

<!-- edit: tests/engine/test_snapshot.py -->
Replace:
```python
ORDERS = st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(1, 10**6), DAYS)
HALTS = st.builds(Halt, DAYS, TEXT)
NOTES = st.builds(Note, st.from_regex(r"[a-z]+(\.[a-z_]+)+", fullmatch=True), TEXT)

```
with:
```python
ORDERS = st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(1, 10**6), DAYS)
NOTES = st.builds(Note, st.from_regex(r"[a-z]+(\.[a-z_]+)+", fullmatch=True), TEXT)
HALTS = st.builds(Halt, DAYS, NOTES)

```

<!-- edit: tests/engine/test_snapshot.py -->
Replace:
```python
    units = UnitValue(Decimal("10000000"), Decimal("0.9998500"), Decimal("1.000"))
    halt = Halt(D0, "daily loss limit")
    return EngineState(holdings, units, halt, D0, {"set": "IDX:BBRI"})
```
with:
```python
    units = UnitValue(Decimal("10000000"), Decimal("0.9998500"), Decimal("1.000"))
    halt = Halt(D0, Note(RISK_HALT_DAILY_LOSS, "daily loss limit"))
    return EngineState(holdings, units, halt, D0, {"set": "IDX:BBRI"})
```

<!-- edit: tests/engine/test_snapshot.py -->
Replace:
```python
SMALL_STATE_JSON = (
    '{"halt":{"cause":"daily loss limit","day":"2026-01-05"},'
    '"holdings":{"claims":[],"entitlements":[],'
```
with:
```python
SMALL_STATE_JSON = (
    '{"halt":{"cause":{"key":"risk.halt.daily_loss","text":"daily loss limit"},'
    '"day":"2026-01-05"},'
    '"holdings":{"claims":[],"entitlements":[],'
```

**`tests/meta/test_terms.py`** (changed: 1 edit)

<!-- edit: tests/meta/test_terms.py -->
Replace:
```python
from steadyhand import FIGURES, BacktestResult, DayReport, IncomeReport, Money

REPORTS: tuple[type, ...] = (DayReport, BacktestResult, IncomeReport)
FIGURE_TYPES = (Money, Decimal)
```
with:
```python
from steadyhand import FIGURES, BacktestResult, DayReport, IncomeReport, Money
from steadyhand_idx.paper import PaperRun

REPORTS: tuple[type, ...] = (DayReport, BacktestResult, IncomeReport, PaperRun)
FIGURE_TYPES = (Money, Decimal)
```


- [ ] **Step 3: Write the stubs.** New names only.

**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
Replace:
```python
ranges it is missing (spec §9.2). A day counts as fetched only once it is over in Jakarta, so
today's bar is always fetched afresh and never stored here: M5's daily run stores it after it
passes validation.
"""
```
with:
```python
ranges it is missing (spec §9.2). A day counts as fetched only once it is over in Jakarta, so
today's bar is always fetched afresh and never stored here; it is stored by the first read
after the day is over.
"""
```

**`packages/steadyhand-idx/src/steadyhand_idx/cli.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    NoTradingDaysError,
    Strategy,
```
with:
```python
    NoTradingDaysError,
    SnapshotVersionError,
    Strategy,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
)
from steadyhand_idx.paths import (
```
with:
```python
)
from steadyhand_idx.paper import (
    CATCH_UP_CAP,
    AccountHaltedError,
    CatchUpError,
    StaleDataError,
    StrategyChangedError,
    run_paper,
)
from steadyhand_idx.paper_pages import paper_run_page
from steadyhand_idx.paths import (
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe
```
with:
```python
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.state import STATE_FILE, StateSchemaError, StateStore
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    (NoTradingDaysError, 2),
    (DataUnavailableError, 3),
    (DataValidationError, 3),
    (InvalidBarError, 3),
)
```
with:
```python
    (NoTradingDaysError, 2),
    (SnapshotVersionError, 2),
    (StateSchemaError, 2),
    (CatchUpError, 2),
    (StrategyChangedError, 2),
    (DataUnavailableError, 3),
    (DataValidationError, 3),
    (InvalidBarError, 3),
    (StaleDataError, 3),
    (AccountHaltedError, 3),
)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python

def _strategy(name: str) -> Strategy:
```
with:
```python

def _paper_run(ctx: Context) -> str:
    """Run every trading day the paper account has not run (M5 spec §6.1). A halted account
    still runs its days, prints them, and exits 3 with the command that resumes it."""
    raise NotImplementedError("_paper_run")


def _strategy(name: str) -> Strategy:
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

PAPER_ACCOUNT_OPENED = "paper.account.opened"
"""The first ``paper run`` opened the paper account with the starting cash and a strategy."""

PAPER_ORDER_CUT = "paper.order.cut"
"""An order the strategy wanted was made smaller, and why."""

PAPER_ORDER_QUEUED = "paper.order.queued"
"""An order was queued for the next trading day's open."""

PAPER_ORDER_SKIPPED = "paper.order.skipped"
"""An order the strategy wanted was not placed at all, and why."""

PAPER_RUN_STOPPED = "paper.run.stopped"
"""A ``paper run`` stopped on a day whose data could not be trusted; that day was not saved."""

PAPER_SETTING_CHANGED = "paper.setting.changed"
"""A setting changed in ``steadyhand.toml``; it applies from the next day run."""

PAPER_SETTING_STARTING_CASH_IGNORED = "paper.setting.starting_cash_ignored"
"""The starting cash changed after the account opened, so the change has no effect."""
```

**`packages/steadyhand-idx/src/steadyhand_idx/paper.py`** (new, as stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
```python
"""Paper trading: the daily cycle behind ``paper run`` (M5 spec §6).

``run_paper`` works out the latest completed trading day, runs every trading day after the last
one saved up to it, oldest first, and saves each in its own transaction with its report and its
audit lines. Each day starts from the account as the database holds it, decoded, and its inputs
come from ``day_inputs`` over the whole range from the opening day, so an account run day by
day with its configuration unchanged ends exactly where a backtest over the same days does
(§6.2). A day that cannot be run safely stops the run with the days before it kept (§6.5).

The CLI calls ``run_paper``; the B+C scheduler will too.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final

from steadyhand import (
    STRATEGIES,
    DataUnavailableError,
    DataValidationError,
    DayInputs,
    DayReport,
    EngineState,
    Halt,
    InvalidBarError,
    Market,
    MarketRules,
    Note,
    day_inputs,
    run_day,
)
from steadyhand_idx.cache import JAKARTA
from steadyhand_idx.config import Config
from steadyhand_idx.notes import (
    PAPER_ACCOUNT_OPENED,
    PAPER_ORDER_CUT,
    PAPER_ORDER_QUEUED,
    PAPER_ORDER_SKIPPED,
    PAPER_RUN_STOPPED,
    PAPER_SETTING_CHANGED,
    PAPER_SETTING_STARTING_CASH_IGNORED,
)
from steadyhand_idx.paths import APP
from steadyhand_idx.state import Account, AuditLine, Outcome, Run, StateStore

CLOSE: Final = time(16, 30)
"""A trading day is complete at 16:30 in Jakarta: after the close, and after the post-closing
session ends at 16:15 (core spec §5)."""

CATCH_UP_CAP: Final = 30
"""The most trading days one ``paper run`` catches up without ``--catch-up`` (M5 spec §6.1)."""

STARTING_CASH: Final = "account.starting_cash_idr"

_STOPS = (DataValidationError, DataUnavailableError, InvalidBarError)
"""The engine's and the source's refusals of a day's data (core spec §5 step 1)."""


class CatchUpError(ValueError):
    """More trading days to run than ``CATCH_UP_CAP``, without ``--catch-up``. M5 exits 2."""

    def __init__(self, count: int, last: date) -> None:
        raise NotImplementedError("CatchUpError.__init__")


class StrategyChangedError(ValueError):
    """The configuration names another strategy than the account runs. M5 exits 2."""

    def __init__(self, configured: str, saved: str) -> None:
        raise NotImplementedError("StrategyChangedError.__init__")


class StaleDataError(RuntimeError):
    """The data source has no bar for a day to run: it has not published it yet. M5 exits 3."""

    def __init__(self, day: date) -> None:
        raise NotImplementedError("StaleDataError.__init__")


class AccountHaltedError(RuntimeError):
    """The account is halted: ``paper run`` ran its days without ordering. M5 exits 3."""

    def __init__(self, halt: Halt, strategy: str) -> None:
        raise NotImplementedError("AccountHaltedError.__init__")


@dataclass(frozen=True, slots=True)
class PaperRun:
    """What one ``paper run`` did: its target day, the reports of the days it ran, and the
    account's halt, if any, when it ended."""

    target: date
    reports: tuple[DayReport, ...]
    halt: Halt | None
    outcome: Outcome


def target_day(now: datetime, rules: MarketRules) -> date:
    """The latest completed trading day at *now*: today in Jakarta if it is a trading day and
    the time there is at or after ``CLOSE``, else the trading day before (M5 spec §6.1)."""
    raise NotImplementedError("target_day")


def days_to_run(last: date | None, target: date, rules: MarketRules) -> tuple[date, ...]:
    """Every trading day after *last* up to *target*, oldest first; the target alone before the
    first run."""
    raise NotImplementedError("days_to_run")


def settings_of(config: Config) -> dict[str, str]:
    """The settings a day runs with, by configuration key, as the audit log shows them."""
    raise NotImplementedError("settings_of")


def run_paper(
    store: StateStore, config: Config, market: Market, now: datetime, *, catch_up: bool = False
) -> PaperRun:
    """Run every trading day the account has not run, up to the latest completed one."""
    raise NotImplementedError("run_paper")


def _run_one(
    store: StateStore, config: Config, inputs: DayInputs, rules: MarketRules
) -> DayReport | None:
    """Run and save one day, from the account as saved; ``None`` if another run saved it."""
    raise NotImplementedError("_run_one")


def _require_fresh(inputs: DayInputs, state: EngineState) -> None:
    """Refuse a day on which no stock the universe or the account holds has a bar: the source
    has not published it yet (M5 spec §11, "Yahoo lags the close")."""
    raise NotImplementedError("_require_fresh")


def _changes(before: Mapping[str, str], after: Mapping[str, str], day: date) -> list[AuditLine]:
    """An audit line for each setting that changed since the last day run (M5 spec §6.5)."""
    raise NotImplementedError("_changes")


def _decisions(report: DayReport) -> list[AuditLine]:
    """The day's decisions (core spec §9.7): orders queued, cut and skipped with their reasons,
    and a halt with its cause."""
    raise NotImplementedError("_decisions")
```

**`packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py`** (new, as stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
```python
"""What the paper commands print (M5 spec §6, §7), built as ``Page``s for ``output.render``."""

from __future__ import annotations

from steadyhand import FIGURES
from steadyhand_idx.output import Page
from steadyhand_idx.paper import PaperRun
from steadyhand_idx.paths import APP


def paper_run_page(done: PaperRun) -> Page:
    """One line per day run, with the portfolio's value that evening, or that nothing was left to
    run."""
    raise NotImplementedError("paper_run_page")
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
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

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    INCOME_PROJECTION_COSTS_IGNORED,
    Note,
```
with:
```python
    INCOME_PROJECTION_COSTS_IGNORED,
    RISK_HALT_DAILY_LOSS,
    RISK_HALT_DRAWDOWN,
    Note,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "RATIO_PLACES",
    "SNAPSHOT_CURRENCIES",
```
with:
```python
    "RATIO_PLACES",
    "RISK_HALT_DAILY_LOSS",
    "RISK_HALT_DRAWDOWN",
    "SNAPSHOT_CURRENCIES",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "cover_claims",
    "decode_report",
```
with:
```python
    "cover_claims",
    "day_inputs",
    "decode_report",
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

def _window(market: Market, start: date, end: date, settings: BacktestSettings) -> _Window:
```
with:
```python

def day_inputs(market: Market, start: date, end: date) -> tuple[DayInputs, ...]:
    """Every trading day's inputs from *start* to *end*, both inclusive, oldest first.

    This is a backtest's fetch step, public so that paper trading builds each day exactly as a
    backtest over the same range does (M5 spec §6.2). ``refused`` and ``resumed`` depend on the
    days before the one run, so a caller that runs only the later days still fetches from the
    first.
    """
    raise NotImplementedError("day_inputs")


def _window(market: Market, start: date, end: date, settings: BacktestSettings) -> _Window:
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    return _fetch(market, days)

```
with:
```python
    return _fetch(market, days)


def _days(market: Market, start: date, end: date) -> tuple[date, ...]:
    """The trading days from *start* to *end*, once the rules and the universe cover them."""
    raise NotImplementedError("_days")

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
        yield run[0], run[-1]

```
with:
```python
        yield run[0], run[-1]


def _inputs(window: _Window) -> tuple[DayInputs, ...]:
    """Each day of *window* as the engine takes it (M3 spec §7.1)."""
    raise NotImplementedError("_inputs")

```

**`packages/steadyhand/src/steadyhand/notes.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/notes.py -->
Replace:
```python

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
```
with:
```python

RISK_HALT_DAILY_LOSS = "risk.halt.daily_loss"
"""The unit value fell by the daily loss limit or more in one day, so ordering stopped."""

RISK_HALT_DRAWDOWN = "risk.halt.drawdown"
"""The unit value fell by the drawdown limit or more below its high-water mark: ordering stopped."""

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
```

**`packages/steadyhand/src/steadyhand/risk.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
```
with:
```python
from steadyhand.money import Money, Rounding
from steadyhand.notes import RISK_HALT_DAILY_LOSS, RISK_HALT_DRAWDOWN, Note
from steadyhand.outcomes import Cut, Rejected
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1390 failed=51 -->
Expected: 1390 run, 51 failed. 23 are `NotImplementedError` from the stubs of `paper.py`, `paper_pages.py` and `day_inputs`. The other 28 are the new tests meeting code a stub keeps: `Halt` still takes a `str` cause, so every keyed halt fails with `TypeError: cause must be a str, got Note` or `DID NOT RAISE TypeError`, and a saved halt cannot be read (`SnapshotError: … expected a string, got dict`); `paper` is not a command yet, so the paper-run tests exit 2 (`invalid choice: 'paper'`), or find no `account` table in a database no run created; the backtest page reads a halt's `.text`; the note-key guard finds no `Note` built from the seven new keys; and those keys have no lesson yet. The pinned exit-code table and 17 of the re-indexed exit-code cases pass, since the table is a constant written in the red phase; mutation M265 shows it guards the table.

- [ ] **Step 5: Implement.** The lessons and the cache docstring (scope decision 16) are part of this step.

**`packages/steadyhand-idx/src/steadyhand_idx/cli.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    explain.set_defaults(run=_explain)
    return parser
```
with:
```python
    explain.set_defaults(run=_explain)

    paper = commands.add_parser("paper", help="paper trading: run the days, follow the account")
    paper_commands = paper.add_subparsers(dest="paper_command", metavar="command", required=True)
    paper_run = paper_commands.add_parser("run", help="run every trading day not yet run")
    paper_run.add_argument(
        "--catch-up", action="store_true", help=f"run more than {CATCH_UP_CAP} missed days"
    )
    paper_run.set_defaults(run=_paper_run)
    return parser
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    still runs its days, prints them, and exits 3 with the command that resumes it."""
    raise NotImplementedError("_paper_run")

```
with:
```python
    still runs its days, prints them, and exits 3 with the command that resumes it."""
    config = ctx.config()
    with (
        ctx.world.source(config.data_dir) as source,
        StateStore(config.data_dir / STATE_FILE) as store,
    ):
        done = run_paper(
            store, config, _market(config, source), ctx.world.now(), catch_up=ctx.args.catch_up
        )
    text = render(paper_run_page(done), config.training)
    if done.halt is not None:
        ctx.say(text)
        raise AccountHaltedError(done.halt, config.strategy)
    return text

```

**`packages/steadyhand-idx/src/steadyhand_idx/paper.py`** (replaces the stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
```python
"""Paper trading: the daily cycle behind ``paper run`` (M5 spec §6).

``run_paper`` works out the latest completed trading day, runs every trading day after the last
one saved up to it, oldest first, and saves each in its own transaction with its report and its
audit lines. Each day starts from the account as the database holds it, decoded, and its inputs
come from ``day_inputs`` over the whole range from the opening day, so an account run day by
day with its configuration unchanged ends exactly where a backtest over the same days does
(§6.2). A day that cannot be run safely stops the run with the days before it kept (§6.5).

The CLI calls ``run_paper``; the B+C scheduler will too.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final

from steadyhand import (
    STRATEGIES,
    DataUnavailableError,
    DataValidationError,
    DayInputs,
    DayReport,
    EngineState,
    Halt,
    InvalidBarError,
    Market,
    MarketRules,
    Note,
    day_inputs,
    run_day,
)
from steadyhand_idx.cache import JAKARTA
from steadyhand_idx.config import Config
from steadyhand_idx.notes import (
    PAPER_ACCOUNT_OPENED,
    PAPER_ORDER_CUT,
    PAPER_ORDER_QUEUED,
    PAPER_ORDER_SKIPPED,
    PAPER_RUN_STOPPED,
    PAPER_SETTING_CHANGED,
    PAPER_SETTING_STARTING_CASH_IGNORED,
)
from steadyhand_idx.paths import APP
from steadyhand_idx.state import Account, AuditLine, Outcome, Run, StateStore

CLOSE: Final = time(16, 30)
"""A trading day is complete at 16:30 in Jakarta: after the close, and after the post-closing
session ends at 16:15 (core spec §5)."""

CATCH_UP_CAP: Final = 30
"""The most trading days one ``paper run`` catches up without ``--catch-up`` (M5 spec §6.1)."""

STARTING_CASH: Final = "account.starting_cash_idr"

_STOPS = (DataValidationError, DataUnavailableError, InvalidBarError)
"""The engine's and the source's refusals of a day's data (core spec §5 step 1)."""


class CatchUpError(ValueError):
    """More trading days to run than ``CATCH_UP_CAP``, without ``--catch-up``. M5 exits 2."""

    def __init__(self, count: int, last: date) -> None:
        super().__init__(
            f"{count} trading days to run since {last.isoformat()}, more than {CATCH_UP_CAP}; "
            f"run {APP} paper run --catch-up to run them all"
        )


class StrategyChangedError(ValueError):
    """The configuration names another strategy than the account runs. M5 exits 2."""

    def __init__(self, configured: str, saved: str) -> None:
        super().__init__(
            f"steadyhand.toml names the strategy {configured}, but the paper account runs "
            f"{saved}; to change it, run: {APP} paper switch {configured}"
        )


class StaleDataError(RuntimeError):
    """The data source has no bar for a day to run: it has not published it yet. M5 exits 3."""

    def __init__(self, day: date) -> None:
        super().__init__(
            f"the data source has no bars for {day.isoformat()} yet, so nothing was run for "
            "it; run paper run again later"
        )


class AccountHaltedError(RuntimeError):
    """The account is halted: ``paper run`` ran its days without ordering. M5 exits 3."""

    def __init__(self, halt: Halt, strategy: str) -> None:
        super().__init__(
            f"the paper account halted on {halt.day.isoformat()}: {halt.cause.text}; no orders "
            f"are placed until you resume it with: {APP} resume {strategy}"
        )


@dataclass(frozen=True, slots=True)
class PaperRun:
    """What one ``paper run`` did: its target day, the reports of the days it ran, and the
    account's halt, if any, when it ended."""

    target: date
    reports: tuple[DayReport, ...]
    halt: Halt | None
    outcome: Outcome


def target_day(now: datetime, rules: MarketRules) -> date:
    """The latest completed trading day at *now*: today in Jakarta if it is a trading day and
    the time there is at or after ``CLOSE``, else the trading day before (M5 spec §6.1)."""
    local = now.astimezone(JAKARTA)
    day = local.date()
    if rules.is_trading_day(day) and local.time() >= CLOSE:
        return day
    day -= timedelta(days=1)
    while not rules.is_trading_day(day):
        day -= timedelta(days=1)
    return day


def days_to_run(last: date | None, target: date, rules: MarketRules) -> tuple[date, ...]:
    """Every trading day after *last* up to *target*, oldest first; the target alone before the
    first run."""
    if last is None:
        return (target,)
    days: list[date] = []
    day = last + timedelta(days=1)
    while day <= target:
        if rules.is_trading_day(day):
            days.append(day)
        day += timedelta(days=1)
    return tuple(days)


def settings_of(config: Config) -> dict[str, str]:
    """The settings a day runs with, by configuration key, as the audit log shows them."""
    engine = config.settings.engine
    contribution = engine.monthly_contribution
    goal = config.settings.goal
    return {
        STARTING_CASH: str(config.settings.capital.amount),
        "account.monthly_contribution_idr": str(0 if contribution is None else contribution.amount),
        "account.broker_fees": config.broker_fees,
        "goal.monthly_income_target_idr": str(0 if goal is None else goal.monthly_target.amount),
        "risk.max_weight": str(engine.limits.max_weight),
        "risk.daily_loss_limit": str(engine.limits.daily_loss),
        "risk.max_drawdown": str(engine.limits.max_drawdown),
        "risk.max_volume_participation": str(engine.fills.volume_cap),
        "dividends.pay_lag_trading_days": str(engine.pay_lag_trading_days),
        "tax.dividend_reinvestment_exemption": str(engine.dividend_reinvestment_exemption).lower(),
    }


def run_paper(
    store: StateStore, config: Config, market: Market, now: datetime, *, catch_up: bool = False
) -> PaperRun:
    """Run every trading day the account has not run, up to the latest completed one."""
    rules = market.rules
    target = target_day(now, rules)
    at = now.astimezone(UTC)
    account = store.account()
    if account is not None and account.strategy != config.strategy:
        raise StrategyChangedError(config.strategy, account.strategy)
    days = days_to_run(None if account is None else account.last_day, target, rules)
    if account is not None and len(days) > CATCH_UP_CAP and not catch_up:
        raise CatchUpError(len(days), account.last_day)
    if not days:
        halt = None if account is None else account.state.halt
        outcome = Outcome.UP_TO_DATE if halt is None else Outcome.HALTED
        store.finish(Run(at, target, (), outcome, f"already up to date for {target.isoformat()}"))
        return PaperRun(target, (), halt, outcome)
    ran: list[DayReport] = []
    day = days[0]
    try:
        opened_on = target if account is None else account.opened_on
        inputs = {found.day: found for found in day_inputs(market, opened_on, target)}
        for day in days:
            report = _run_one(store, config, inputs[day], rules)
            if report is not None:
                ran.append(report)
    except (*_STOPS, StaleDataError) as error:
        stopped = AuditLine(day, Note(PAPER_RUN_STOPPED, f"stopped on {day.isoformat()}: {error}"))
        days_ran = tuple(report.day for report in ran)
        store.finish(Run(at, target, days_ran, Outcome.STOPPED, str(error)), (stopped,))
        raise
    final = store.account()
    halt = None if final is None else final.state.halt
    if not ran:
        # Another run saved every day first (M5 spec §6.4): this one is up to date.
        outcome = Outcome.UP_TO_DATE if halt is None else Outcome.HALTED
        store.finish(Run(at, target, (), outcome, f"already up to date for {target.isoformat()}"))
        return PaperRun(target, (), halt, outcome)
    outcome = Outcome.RAN if halt is None else Outcome.HALTED
    days_ran = tuple(report.day for report in ran)
    store.finish(Run(at, target, days_ran, outcome, f"ran {len(ran)} day(s)"))
    return PaperRun(target, tuple(ran), halt, outcome)


def _run_one(
    store: StateStore, config: Config, inputs: DayInputs, rules: MarketRules
) -> DayReport | None:
    """Run and save one day, from the account as saved; ``None`` if another run saved it."""
    day = inputs.day
    account = store.account()
    if account is not None and account.last_day >= day:
        return None
    settings = settings_of(config)
    if account is None:
        capital = config.settings.capital
        state = EngineState.opening(capital, day)
        opened_on = day
        lines = [
            AuditLine(
                day,
                Note(
                    PAPER_ACCOUNT_OPENED,
                    f"opened the paper account on {day.isoformat()} with {capital} and the "
                    f"{config.strategy} strategy",
                ),
            )
        ]
    else:
        state = account.state
        opened_on = account.opened_on
        lines = _changes(account.settings, settings, day)
    _require_fresh(inputs, state)
    state, report = run_day(
        state, inputs, STRATEGIES[config.strategy](), rules, config.settings.engine
    )
    lines += _decisions(report)
    saved = store.save(
        Account(opened_on, config.strategy, state, settings),
        after=None if account is None else account.last_day,
        report=report,
        audit=lines,
    )
    return report if saved else None


def _require_fresh(inputs: DayInputs, state: EngineState) -> None:
    """Refuse a day on which no stock the universe or the account holds has a bar: the source
    has not published it yet (M5 spec §11, "Yahoo lags the close")."""
    held = {position.instrument for position in state.holdings.portfolio.positions}
    stocks = inputs.members | held
    if stocks and all(inputs.history.on(stock, inputs.day) is None for stock in stocks):
        raise StaleDataError(inputs.day)


def _changes(before: Mapping[str, str], after: Mapping[str, str], day: date) -> list[AuditLine]:
    """An audit line for each setting that changed since the last day run (M5 spec §6.5)."""
    lines: list[AuditLine] = []
    for key in sorted(after):
        old, new = before.get(key), after[key]
        if old == new:
            continue
        if key == STARTING_CASH:
            text = (
                f"{key} changed from {old} to {new}; it is used only when the account opens, so "
                "the account's cash is unchanged"
            )
            lines.append(AuditLine(day, Note(PAPER_SETTING_STARTING_CASH_IGNORED, text)))
        else:
            text = f"{key} changed from {old} to {new}; it applies from {day.isoformat()}"
            lines.append(AuditLine(day, Note(PAPER_SETTING_CHANGED, text)))
    return lines


def _decisions(report: DayReport) -> list[AuditLine]:
    """The day's decisions (core spec §9.7): orders queued, cut and skipped with their reasons,
    and a halt with its cause."""
    day = report.day
    lines = [
        AuditLine(
            day,
            Note(
                PAPER_ORDER_QUEUED,
                f"queued: {order.side.value} {order.quantity} {order.instrument.symbol} "
                "at the next open",
            ),
        )
        for order in report.queued
    ]
    lines += [
        AuditLine(
            day,
            Note(
                PAPER_ORDER_CUT,
                f"cut: {cut.order.side.value} {cut.order.instrument.symbol} from "
                f"{cut.order.quantity} to {cut.quantity} shares: {cut.reason}",
            ),
        )
        for cut in report.cuts
    ]
    lines += [
        AuditLine(
            day,
            Note(
                PAPER_ORDER_SKIPPED,
                f"skipped: {rejected.order.side.value} {rejected.order.quantity} "
                f"{rejected.order.instrument.symbol}: {rejected.reason}",
            ),
        )
        for rejected in report.rejected
    ]
    if report.halt is not None:
        lines.append(AuditLine(day, report.halt.cause))
    return lines
```

**`packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py`** (replaces the stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
```python
"""What the paper commands print (M5 spec §6, §7), built as ``Page``s for ``output.render``."""

from __future__ import annotations

from steadyhand import FIGURES
from steadyhand_idx.output import Page
from steadyhand_idx.paper import PaperRun
from steadyhand_idx.paths import APP


def paper_run_page(done: PaperRun) -> Page:
    """One line per day run, with the portfolio's value that evening, or that nothing was left to
    run."""
    page = Page()
    if not done.reports:
        page.add(f"already up to date for {done.target.isoformat()}")
        return page
    for report in done.reports:
        page.add(
            f"{report.day.isoformat()}: {len(report.fills)} fill(s), "
            f"{len(report.queued)} order(s) queued, value {report.value}",
            FIGURES["DayReport.value"],
        )
    first, last = done.reports[0].day, done.reports[-1].day
    days = first.isoformat() if first == last else f"{first.isoformat()} to {last.isoformat()}"
    page.add()
    page.add(f"Ran {len(done.reports)} day(s): {days}. Read a day's report with: {APP} report")
    return page
```

**`packages/steadyhand-idx/src/steadyhand_idx/reports.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python

def _halts(runs: Sequence[RunResult]) -> list[str]:
    return [
        f"{run.strategy} stopped ordering on {run.halt.day}: {run.halt.cause}"
        for run in runs
```
with:
```python

def _halts(runs: Sequence[RunResult]) -> list[tuple[str, str]]:
    """Each halt's line, and the key of the limit it reached."""
    return [
        (
            f"{run.strategy} stopped ordering on {run.halt.day}: {run.halt.cause.text}",
            run.halt.cause.key,
        )
        for run in runs
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python
) -> None:
    for halt in _halts(runs):
        page.add()
        page.add(halt)
    if warnings:
```
with:
```python
) -> None:
    for halt, key in _halts(runs):
        page.add()
        page.add(halt, key)
    if warnings:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python
def _markdown_notes(runs: Sequence[RunResult], warnings: Sequence[Note]) -> list[str]:
    lines = [line for halt in _halts(runs) for line in ("", halt)]
    if warnings:
```
with:
```python
def _markdown_notes(runs: Sequence[RunResult], warnings: Sequence[Note]) -> list[str]:
    lines = [line for halt, _key in _halts(runs) for line in ("", halt)]
    if warnings:
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.daily_run.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.daily_run.md -->
```markdown
+++
id = "paper.daily_run"
title = "Paper trading, one day at a time"
summary = "What paper run does each trading day, what it writes down, and why it sometimes stops."
explains = ["paper.account.opened", "paper.order.queued", "paper.order.skipped", "paper.order.cut", "paper.run.stopped"]
module = "using-steadyhand"
position = 4
see_also = ["paper.settings", "risk.limits"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §6", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.7"]
+++

Paper trading runs your strategy on real prices with pretend money. No order reaches a broker.
You run `paper run` once each trading day, after 16:30 in Jakarta, when the day's trading is
over.

The first run **opens** the paper account with your starting cash and your strategy. Each run
after that plays every trading day since the last one, oldest first, exactly as a backtest over
the same days would. If you miss a few days, the next run catches them up.

Each day, the strategy looks at the closing prices and decides what it wants to own. The orders
it makes are **queued**: they fill at the next day's open, as they would for you in your
broker's app. Some orders change on the way. An order is **cut** when a safety limit allows only
part of it, and **skipped** when it cannot be placed at all, for example because there is not
enough settled cash. Each one is written in the audit log with its reason.

A run **stops** when a day's prices cannot be trusted: a price is impossible, or the data source
has not published the day yet. Nothing trades on that day and it is not saved. Days caught up
before it stay saved, and the next run tries the day again.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.settings.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.settings.md -->
```markdown
+++
id = "paper.settings"
title = "Changing your settings while paper trading"
summary = "A changed setting applies from the next day run and is written in the audit log; the starting cash never changes after opening."
explains = ["paper.setting.changed", "paper.setting.starting_cash_ignored"]
module = "using-steadyhand"
position = 5
see_also = ["paper.daily_run"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §6.5"]
+++

You can change most settings in `steadyhand.toml` while a paper account is running: the monthly
contribution, the safety limits, your broker's fee preset, the dividend settings and your income
goal. The next day that `paper run` plays uses the new value, and the audit log records which
setting changed, from what to what, and from which day.

Two settings behave differently:

- **The starting cash** is used only on the day the account opens. Changing it later does not
  add or remove money. The audit log says once that the change was seen and has no effect. To
  add money, set a monthly contribution instead.
- **The strategy** does not change just because the file changes. `paper run` refuses to run
  and tells you the `paper switch` command that makes the change on purpose.

A paper account run with its settings unchanged ends exactly where a backtest over the same
days ends. Once you change a setting, its record is no longer comparable with such a backtest,
which is why each change is written down.
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented: 7 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    window = _window(market, start, end, settings)
    run = _complete(_run(strategy, window, market.rules, settings), market, settings)
    baseline = BuyAndHold()
```
with:
```python
    window = _window(market, start, end, settings)
    inputs = _inputs(window)
    run = _complete(_run(strategy, inputs, market.rules, settings), market, settings)
    baseline = BuyAndHold()
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
        if strategy.name == baseline.name
        else _complete(_run(baseline, window, market.rules, settings), market, settings)
    )
```
with:
```python
        if strategy.name == baseline.name
        else _complete(_run(baseline, inputs, market.rules, settings), market, settings)
    )
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    window = _window(market, start, end, settings)
    baseline = BuyAndHold()
    everyone = (*strategies, *(() if baseline.name in names else (baseline,)))
    runs = tuple(
        _complete(_run(strategy, window, market.rules, settings), market, settings)
        for strategy in everyone
```
with:
```python
    window = _window(market, start, end, settings)
    inputs = _inputs(window)
    baseline = BuyAndHold()
    everyone = (*strategies, *(() if baseline.name in names else (baseline,)))
    runs = tuple(
        _complete(_run(strategy, inputs, market.rules, settings), market, settings)
        for strategy in everyone
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    """
    raise NotImplementedError("day_inputs")

```
with:
```python
    """
    require_type(market, Market, "market")
    require_date(start, "start")
    require_date(end, "end")
    if end < start:
        msg = f"the range ends on {end.isoformat()}, before it starts on {start.isoformat()}"
        raise ValueError(msg)
    return _inputs(_fetch(market, _days(market, start, end)))

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
        raise ValueError(msg)
    rules.require_supported(start)
```
with:
```python
        raise ValueError(msg)
    return _fetch(market, _days(market, start, end))


def _days(market: Market, start: date, end: date) -> tuple[date, ...]:
    """The trading days from *start* to *end*, once the rules and the universe cover them."""
    rules = market.rules
    rules.require_supported(start)
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
        raise NoTradingDaysError(msg)
    return _fetch(market, days)


def _days(market: Market, start: date, end: date) -> tuple[date, ...]:
    """The trading days from *start* to *end*, once the rules and the universe cover them."""
    raise NotImplementedError("_days")

```
with:
```python
        raise NoTradingDaysError(msg)
    return days

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    """Each day of *window* as the engine takes it (M3 spec §7.1)."""
    raise NotImplementedError("_inputs")


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
```
with:
```python
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
```

**`packages/steadyhand/src/steadyhand/risk.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
class Halt:
    """Ordering stopped on ``day``, for ``cause``. In a backtest it lasts to the end of the run."""

    day: date
    cause: str

    def __post_init__(self) -> None:
        require_date(self.day, "halt day")
        require_type(self.cause, str, "cause")
        if not self.cause.strip():
            msg = "a halt needs a cause"
            raise ValueError(msg)

```
with:
```python
class Halt:
    """Ordering stopped on ``day``, for ``cause``, a note under the key of the limit reached.

    In a backtest it lasts to the end of the run; a paper account keeps it until it is resumed.
    """

    day: date
    cause: Note

    def __post_init__(self) -> None:
        require_date(self.day, "halt day")
        require_type(self.cause, Note, "cause")

```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
                )
                return Halt(day, cause)
        drawdown = 1 - ratio_down(after.price, after.high_water)
```
with:
```python
                )
                return Halt(day, Note(RISK_HALT_DAILY_LOSS, cause))
        drawdown = 1 - ratio_down(after.price, after.high_water)
```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
            )
            return Halt(day, cause)
        return None
```
with:
```python
            )
            return Halt(day, Note(RISK_HALT_DRAWDOWN, cause))
        return None
```

**`packages/steadyhand/src/steadyhand/snapshot.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/snapshot.py -->
Replace:
```python
def _halt(halt: Halt | None) -> dict[str, object] | None:
    return None if halt is None else {"day": halt.day.isoformat(), "cause": halt.cause}

```
with:
```python
def _halt(halt: Halt | None) -> dict[str, object] | None:
    return None if halt is None else {"day": halt.day.isoformat(), "cause": _note(halt.cause)}

```

<!-- edit: packages/steadyhand/src/steadyhand/snapshot.py -->
Replace:
```python
    day, cause = _fields(value, "day", "cause")
    return Halt(_date(day), _str(cause))

```
with:
```python
    day, cause = _fields(value, "day", "cause")
    return Halt(_date(day), _read_note(cause))

```

**`packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md`** (changed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md -->
Replace:
```markdown
summary = "The limits that cut or stop a strategy's orders, whatever the strategy wants to do."
explains = []
module = "risk"
```
with:
```markdown
summary = "The limits that cut or stop a strategy's orders, whatever the strategy wants to do."
explains = ["risk.halt.daily_loss", "risk.halt.drawdown"]
module = "risk"
```

**`scripts/record_golden.py`** (implemented: 1 edit)

<!-- edit: scripts/record_golden.py -->
Replace:
```python
        if outcome.halt is None
        else [outcome.halt.day.isoformat(), outcome.halt.cause],
        "warnings": [[note.key, note.text] for note in (*result.warnings, *outcome.warnings)],
```
with:
```python
        if outcome.halt is None
        else [outcome.halt.day.isoformat(), outcome.halt.cause.text],
        "warnings": [[note.key, note.text] for note in (*result.warnings, *outcome.warnings)],
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1390 passed=1390 -->
Expected: every command exits 0; 1390 passed, 100% branch coverage; the performance step passes its five tests.

- [ ] **Step 7: Mutations.** Run M247–M263 and M265 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(cli): M5b S7 paper run: day selection, catch-up, the public fetch, atomicity, stops, halts and configuration changes`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 4: M5b S8 Every order reason keyed, with its lessons

**Acceptance criteria (story text):**
1. `Rejected.reason` and `Cut.reason` are `Note`s, checked on construction, and every reason the engine gives for refusing or cutting an order is built from a key constant with its text unchanged (M5 §7.4, T1 §3.1): `Tradable.why_not`'s six `trade.*` keys, the risk manager's five `limit.*` keys, the simulated broker's ten `fill.*` keys, and `corporate.split.order_cancelled` (scope decision 14).
2. The codec writes each reason as a note and reads it back equal; every golden day report still reads back equal.
3. The lessons `orders.not_tradable` and `orders.at_the_open` join module 6 at positions 6 and 7, and `risk.limits` and `shares.splits` explain their new keys; every key has a lesson.
4. The paper audit lines and the backtest's report keep their text: a keyed reason prints its `text`.
5. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M266–M273 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand/training/lessons/en/orders.{not_tradable,at_the_open}.md`
- Modify: `.../steadyhand/{__init__,broker/simulated,corporate,engine,notes,outcomes,risk,snapshot,view}.py`, `.../steadyhand/training/lessons/en/{risk.limits,shares.splits}.md`, `.../steadyhand_idx/paper.py`, `tests/engine/test_{backtest,corporate,engine,outcomes,risk,simulated_broker,snapshot,view}.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: in `steadyhand.notes`, exported from `steadyhand`: `TRADE_EXCLUDED`, `TRADE_FROZEN`, `TRADE_NOT_HELD`, `TRADE_NOT_IN_UNIVERSE`, `TRADE_NO_BAR`, `TRADE_REFUSED`, `LIMIT_CASH_CUT`, `LIMIT_CASH_SHORT`, `LIMIT_MIN_LOTS`, `LIMIT_WEIGHT_CUT`, `LIMIT_WEIGHT_FULL`, `FILL_CASH_CUT`, `FILL_CASH_SHORT`, `FILL_CHARGES_UNPAID`, `FILL_FROZEN`, `FILL_NO_BAR`, `FILL_NO_REFERENCE`, `FILL_NO_TRADES`, `FILL_OUTSIDE_BAND`, `FILL_VOLUME_CUT`, `FILL_VOLUME_TOO_SMALL`, `CORPORATE_SPLIT_ORDER_CANCELLED`. `Tradable.why_not`, `Rejected.reason` and `Cut.reason` become `Note`.

- [ ] **Step 1: Branch.** `git switch -c m5/s8-keyed-reasons origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_backtest.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_MISSING, DATA_BAR_REFUSED, RISK_HALT_DAILY_LOSS, Note
from steadyhand.risk import RiskLimits
```
with:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import (
    DATA_BAR_MISSING,
    DATA_BAR_REFUSED,
    RISK_HALT_DAILY_LOSS,
    TRADE_NOT_IN_UNIVERSE,
    Note,
)
from steadyhand.risk import RiskLimits
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    assert [rejected.reason for rejected in result.run.reports[0].rejected] == [
        "not in the universe on 2025-06-30"
    ]
```
with:
```python
    assert [rejected.reason for rejected in result.run.reports[0].rejected] == [
        Note(TRADE_NOT_IN_UNIVERSE, "not in the universe on 2025-06-30")
    ]
```

**`tests/engine/test_corporate.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import CORPORATE_SPLIT_FRACTION_DROPPED, Note
from steadyhand.portfolio import MovementKind, Portfolio
```
with:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import (
    CORPORATE_SPLIT_FRACTION_DROPPED,
    CORPORATE_SPLIT_ORDER_CANCELLED,
    Note,
)
from steadyhand.portfolio import MovementKind, Portfolio
```

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
    assert outcome.holdings.pending == (pending[1],)
    assert [(r.order, r.reason) for r in outcome.cancelled] == [(pending[0], "split on ex-date")]
    assert outcome.warnings == ()
```
with:
```python
    assert outcome.holdings.pending == (pending[1],)
    cancelled = Note(CORPORATE_SPLIT_ORDER_CANCELLED, "split on ex-date")
    assert [(r.order, r.reason) for r in outcome.cancelled] == [(pending[0], cancelled)]
    assert outcome.warnings == ()
```

**`tests/engine/test_engine.py`** (changed: 8 edits)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
from steadyhand.notes import (
    DATA_BAR_MISSING,
```
with:
```python
from steadyhand.notes import (
    CORPORATE_SPLIT_ORDER_CANCELLED,
    DATA_BAR_MISSING,
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    RISK_HALT_DAILY_LOSS,
    Note,
```
with:
```python
    RISK_HALT_DAILY_LOSS,
    TRADE_EXCLUDED,
    TRADE_FROZEN,
    TRADE_NO_BAR,
    TRADE_NOT_IN_UNIVERSE,
    TRADE_REFUSED,
    Note,
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    after, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    assert (report.rejected[0].order, report.rejected[0].reason) == (pending, "split on ex-date")
    assert after.holdings.last_closes[BBCA] == rp(1_820)
```
with:
```python
    after, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    cancelled = Note(CORPORATE_SPLIT_ORDER_CANCELLED, "split on ex-date")
    assert (report.rejected[0].order, report.rejected[0].reason) == (pending, cancelled)
    assert after.holdings.last_closes[BBCA] == rp(1_820)
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert [(r.order.side, r.reason) for r in report.rejected] == [
        (Side.SELL, "no bar on 2025-06-04")
    ]
```
with:
```python
    assert [(r.order.side, r.reason) for r in report.rejected] == [
        (Side.SELL, Note(TRADE_NO_BAR, "no bar on 2025-06-04"))
    ]
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, "frozen: excluded: Special Monitoring Board")
    ]
```
with:
```python
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, Note(TRADE_FROZEN, "frozen: excluded: Special Monitoring Board"))
    ]
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert (report.frozen, after.holdings.frozen) == ((), {})
    assert [r.reason for r in report.rejected] == ["excluded: board"]

```
with:
```python
    assert (report.frozen, after.holdings.frozen) == ((), {})
    assert [r.reason for r in report.rejected] == [Note(TRADE_EXCLUDED, "excluded: board")]

```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBRI, "the data source refused 2025-06-04")
    ]
```
with:
```python
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBRI, Note(TRADE_REFUSED, "the data source refused 2025-06-04"))
    ]
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, "not in the universe on 2025-06-02")
    ]
```
with:
```python
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, Note(TRADE_NOT_IN_UNIVERSE, "not in the universe on 2025-06-02"))
    ]
```

**`tests/engine/test_outcomes.py`** (changed: 4 edits)

<!-- edit: tests/engine/test_outcomes.py -->
Replace:
```python
from steadyhand.money import IDR
from steadyhand.outcomes import Cut, Rejected
```
with:
```python
from steadyhand.money import IDR
from steadyhand.notes import FILL_FROZEN, FILL_VOLUME_CUT, Note
from steadyhand.outcomes import Cut, Rejected
```

<!-- edit: tests/engine/test_outcomes.py -->
Replace:
```python

def test_outcomes_keep_the_order_and_the_reason() -> None:
    assert Rejected(ORDER, "frozen: rights issue").reason == "frozen: rights issue"
    cut = Cut(ORDER, 100, "cut to 10% of the day's volume")
    assert (cut.order, cut.quantity) == (ORDER, 100)


@pytest.mark.parametrize("reason", ["", "   "])
def test_every_outcome_needs_a_reason(reason: str) -> None:
    with pytest.raises(ValueError, match=r"^a buy order for BBCA needs a reason$"):
        Rejected(ORDER, reason)
    with pytest.raises(ValueError, match=r"^a buy order for BBCA needs a reason$"):
        Cut(ORDER, 100, reason)

```
with:
```python

def test_outcomes_keep_the_order_and_the_keyed_reason() -> None:
    frozen = Note(FILL_FROZEN, "frozen: rights issue")
    assert Rejected(ORDER, frozen).reason == frozen
    volume = Note(FILL_VOLUME_CUT, "cut to 10% of the day's volume")
    cut = Cut(ORDER, 100, volume)
    assert (cut.order, cut.quantity, cut.reason) == (ORDER, 100, volume)


def test_every_reason_is_a_note_under_a_key() -> None:
    with pytest.raises(TypeError, match=r"^reason must be a Note, got str$"):
        Rejected(ORDER, "frozen: rights issue")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^reason must be a Note, got str$"):
        Cut(ORDER, 100, "cut to 10% of the day's volume")  # type: ignore[arg-type]

```

<!-- edit: tests/engine/test_outcomes.py -->
Replace:
```python
    with pytest.raises(ValueError, match=r"^a cut must leave fewer than 500 shares, got 500$"):
        Cut(ORDER, 500, "no change")
    with pytest.raises(ValueError, match=r"^cut quantity must be at least 1, got 0$"):
        Cut(ORDER, 0, "nothing left")

```
with:
```python
    with pytest.raises(ValueError, match=r"^a cut must leave fewer than 500 shares, got 500$"):
        Cut(ORDER, 500, Note(FILL_VOLUME_CUT, "no change"))
    with pytest.raises(ValueError, match=r"^cut quantity must be at least 1, got 0$"):
        Cut(ORDER, 0, Note(FILL_VOLUME_CUT, "nothing left"))

```

<!-- edit: tests/engine/test_outcomes.py -->
Replace:
```python
        Rejected("BBCA", "no bar")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^reason must be a str, got int$"):
        Rejected(ORDER, 3)  # type: ignore[arg-type]
```
with:
```python
        Rejected("BBCA", "no bar")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^reason must be a Note, got int$"):
        Rejected(ORDER, 3)  # type: ignore[arg-type]
```

**`tests/engine/test_risk.py`** (changed: 9 edits)

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
from steadyhand.money import IDR, Money
from steadyhand.notes import RISK_HALT_DAILY_LOSS, RISK_HALT_DRAWDOWN, Note
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
```
with:
```python
from steadyhand.money import IDR, Money
from steadyhand.notes import (
    LIMIT_CASH_CUT,
    LIMIT_CASH_SHORT,
    LIMIT_MIN_LOTS,
    LIMIT_WEIGHT_CUT,
    LIMIT_WEIGHT_FULL,
    RISK_HALT_DAILY_LOSS,
    RISK_HALT_DRAWDOWN,
    TRADE_FROZEN,
    TRADE_NOT_IN_UNIVERSE,
    Note,
)
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
PRICES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR)}
OPEN = Tradable(DAY, frozenset({BBCA, BBRI}), frozenset({BBCA, BBRI}), {TLKM: "frozen: merger"})

```
with:
```python
PRICES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR)}
MERGER = Note(TRADE_FROZEN, "frozen: merger")
OPEN = Tradable(DAY, frozenset({BBCA, BBRI}), frozenset({BBCA, BBRI}), {TLKM: MERGER})

```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    limits: RiskLimits | None = None,
) -> tuple[list[Order], list[tuple[Order, str]], list[tuple[int, str]]]:
    """Check *orders* for a portfolio worth *value*, spending all of it not *held* by default."""
```
with:
```python
    limits: RiskLimits | None = None,
) -> tuple[list[Order], list[tuple[Order, Note]], list[tuple[int, Note]]]:
    """Check *orders* for a portfolio worth *value*, spending all of it not *held* by default."""
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    assert rejected == [
        (buy(100, TLKM), "frozen: merger"),
        (sell, "frozen: merger"),
        (stranger, "not in the universe on 2025-06-02"),
    ]
```
with:
```python
    assert rejected == [
        (buy(100, TLKM), MERGER),
        (sell, MERGER),
        (stranger, Note(TRADE_NOT_IN_UNIVERSE, "not in the universe on 2025-06-02")),
    ]
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    assert passed == [sell]
    assert rejected == [(buy(100), "not enough cash: IDR 0 can be spent")]

```
with:
```python
    assert passed == [sell]
    assert rejected == [(buy(100), Note(LIMIT_CASH_SHORT, "not enough cash: IDR 0 can be spent"))]

```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    assert passed == [buy(200)]
    assert cuts == [(200, "cut to the 10.00% limit per stock")]
    passed, _, cuts = check(buy(300), value=17_999_990)
```
with:
```python
    assert passed == [buy(200)]
    assert cuts == [(200, Note(LIMIT_WEIGHT_CUT, "cut to the 10.00% limit per stock"))]
    passed, _, cuts = check(buy(300), value=17_999_990)
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    _, rejected, _ = check(buy(100), value=10_000_000, held={BBCA: 900_001})
    assert rejected == [(buy(100), "already at the 10.00% limit per stock")]

```
with:
```python
    _, rejected, _ = check(buy(100), value=10_000_000, held={BBCA: 900_001})
    full = Note(LIMIT_WEIGHT_FULL, "already at the 10.00% limit per stock")
    assert rejected == [(buy(100), full)]

```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    passed, rejected, _ = check(buy(100), buy(200, BBRI), limits=limits)
    assert rejected == [(buy(100), "below the minimum buy of 2 lot(s)")]
    assert passed == [buy(200, BBRI)]
```
with:
```python
    passed, rejected, _ = check(buy(100), buy(200, BBRI), limits=limits)
    assert rejected == [(buy(100), Note(LIMIT_MIN_LOTS, "below the minimum buy of 2 lot(s)"))]
    assert passed == [buy(200, BBRI)]
```

<!-- edit: tests/engine/test_risk.py -->
Replace:
```python
    assert passed == [buy(100)]
    assert rejected == [(buy(100, BBRI), "not enough cash: IDR 98,111 can be spent")]
    passed, _, cuts = check(buy(300), spendable=1_803_777, limits=limits)
    assert passed == [buy(200)]
    assert cuts == [(200, "cut to the IDR 1,803,777 that can be spent")]
    passed, _, _ = check(buy(300), spendable=1_803_776, limits=limits)
```
with:
```python
    assert passed == [buy(100)]
    assert rejected == [
        (buy(100, BBRI), Note(LIMIT_CASH_SHORT, "not enough cash: IDR 98,111 can be spent"))
    ]
    passed, _, cuts = check(buy(300), spendable=1_803_777, limits=limits)
    assert passed == [buy(200)]
    assert cuts == [(200, Note(LIMIT_CASH_CUT, "cut to the IDR 1,803,777 that can be spent"))]
    passed, _, _ = check(buy(300), spendable=1_803_776, limits=limits)
```

**`tests/engine/test_simulated_broker.py`** (changed: 9 edits)

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
from steadyhand.money import IDR, Money
from steadyhand.portfolio import MovementKind, Portfolio
```
with:
```python
from steadyhand.money import IDR, Money
from steadyhand.notes import (
    FILL_CASH_CUT,
    FILL_CASH_SHORT,
    FILL_CHARGES_UNPAID,
    FILL_FROZEN,
    FILL_NO_BAR,
    FILL_NO_REFERENCE,
    FILL_NO_TRADES,
    FILL_OUTSIDE_BAND,
    FILL_VOLUME_CUT,
    FILL_VOLUME_TOO_SMALL,
    Note,
)
from steadyhand.portfolio import MovementKind, Portfolio
```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
@pytest.mark.parametrize(
    ("bars", "frozen", "reason"),
    [
        ([bar(BBCA, 9_000)], {"BBCA": "rights issue"}, "frozen: rights issue"),
        ([], {}, "no bar for BBCA on 2025-06-03"),
        ([bar(BBCA, 9_000, volume=0)], {}, "BBCA did not trade on 2025-06-03"),
        (
            [bar(BBCA, 10_800)],
            {},
            "fill price IDR 10,825 is outside the band IDR 7,650 to IDR 10,800",
```
with:
```python
@pytest.mark.parametrize(
    ("bars", "frozen", "key", "reason"),
    [
        ([bar(BBCA, 9_000)], {"BBCA": "rights issue"}, FILL_FROZEN, "frozen: rights issue"),
        ([], {}, FILL_NO_BAR, "no bar for BBCA on 2025-06-03"),
        ([bar(BBCA, 9_000, volume=0)], {}, FILL_NO_TRADES, "BBCA did not trade on 2025-06-03"),
        (
            [bar(BBCA, 10_800)],
            {},
            FILL_OUTSIDE_BAND,
            "fill price IDR 10,825 is outside the band IDR 7,650 to IDR 10,800",
```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
def test_an_order_that_cannot_trade_is_rejected_with_its_reason(
    bars: list[Bar], frozen: dict[str, str], reason: str
) -> None:
    result = run(portfolio(10_000_000), buy(100), bars=bars, **frozen)
    assert result.fills == ()
    assert [(r.order, r.reason) for r in result.rejected] == [(buy(100), reason)]
    assert result.portfolio == portfolio(10_000_000)
```
with:
```python
def test_an_order_that_cannot_trade_is_rejected_with_its_reason(
    bars: list[Bar], frozen: dict[str, str], key: str, reason: str
) -> None:
    result = run(portfolio(10_000_000), buy(100), bars=bars, **frozen)
    assert result.fills == ()
    assert [(r.order, r.reason) for r in result.rejected] == [(buy(100), Note(key, reason))]
    assert result.portfolio == portfolio(10_000_000)
```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
    assert [r.reason for r in result.rejected] == [
        "no previous close for GOTO to set the price band"
    ]
```
with:
```python
    assert [r.reason for r in result.rejected] == [
        Note(FILL_NO_REFERENCE, "no previous close for GOTO to set the price band")
    ]
```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (100, "cut to 10% of the day's 1,999 shares traded")
    ]
```
with:
```python
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (100, Note(FILL_VOLUME_CUT, "cut to 10% of the day's 1,999 shares traded"))
    ]
```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
    assert [r.reason for r in result.rejected] == [
        "10% of the day's 999 shares traded is less than a lot"
    ]
```
with:
```python
    assert [r.reason for r in result.rejected] == [
        Note(FILL_VOLUME_TOO_SMALL, "10% of the day's 999 shares traded is less than a lot")
    ]
```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (200, "cut to the IDR 1,808,788 that can be spent")
    ]
```
with:
```python
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (200, Note(FILL_CASH_CUT, "cut to the IDR 1,808,788 that can be spent"))
    ]
```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
    result = run(portfolio(902_500 + 1_893), buy(100))
    assert [r.reason for r in result.rejected] == ["not enough cash: IDR 904,393 can be spent"]

```
with:
```python
    result = run(portfolio(902_500 + 1_893), buy(100))
    assert [r.reason for r in result.rejected] == [
        Note(FILL_CASH_SHORT, "not enough cash: IDR 904,393 can be spent")
    ]

```

<!-- edit: tests/engine/test_simulated_broker.py -->
Replace:
```python
    assert [r.reason for r in result.rejected] == [
        "the day's charges of IDR 10,000 exceed the IDR 5,881 that could pay them"
    ]
```
with:
```python
    assert [r.reason for r in result.rejected] == [
        Note(
            FILL_CHARGES_UNPAID,
            "the day's charges of IDR 10,000 exceed the IDR 5,881 that could pay them",
        )
    ]
```

**`tests/engine/test_snapshot.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_snapshot.py -->
Replace:
```python
    order = draw(st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(2, 10**6), DAYS))
    return Cut(order, draw(st.integers(1, order.quantity - 1)), draw(TEXT))

```
with:
```python
    order = draw(st.builds(Order, INSTRUMENTS, st.sampled_from(Side), st.integers(2, 10**6), DAYS))
    return Cut(order, draw(st.integers(1, order.quantity - 1)), draw(NOTES))

```

<!-- edit: tests/engine/test_snapshot.py -->
Replace:
```python
    fills=tuples(fills()),
    rejected=tuples(st.builds(Rejected, ORDERS, TEXT)),
    cuts=tuples(cuts()),
```
with:
```python
    fills=tuples(fills()),
    rejected=tuples(st.builds(Rejected, ORDERS, NOTES)),
    cuts=tuples(cuts()),
```

**`tests/engine/test_view.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import Bar, Instrument, Side
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

D0 = date(2025, 6, 2)
```
with:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import (
    TRADE_FROZEN,
    TRADE_NO_BAR,
    TRADE_NOT_HELD,
    TRADE_NOT_IN_UNIVERSE,
    Note,
)
from steadyhand.types import Bar, Instrument, Side
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

RIGHTS = Note(TRADE_FROZEN, "frozen: rights issue")
NO_BAR = Note(TRADE_NO_BAR, "no bar on 2025-06-02")
D0 = date(2025, 6, 2)
```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
def test_tradable_says_why_a_stock_cannot_be_traded() -> None:
    tradable = Tradable(
        D0, frozenset({BBCA}), frozenset({BBCA, BBRI}), {TLKM: "frozen: rights issue"}
    )
    assert tradable.why_not(BBCA, Side.BUY) is None
    assert tradable.why_not(BBRI, Side.SELL) is None
    assert tradable.why_not(BBRI, Side.BUY) == "not in the universe on 2025-06-02"
    assert tradable.why_not(TLKM, Side.BUY) == "frozen: rights issue"
    assert tradable.why_not(TLKM, Side.SELL) == "frozen: rights issue"
    assert tradable.why_not(Instrument("ASII", "IDX", IDR), Side.SELL) == "not held"

```
with:
```python
def test_tradable_says_why_a_stock_cannot_be_traded() -> None:
    tradable = Tradable(D0, frozenset({BBCA}), frozenset({BBCA, BBRI}), {TLKM: RIGHTS})
    assert tradable.why_not(BBCA, Side.BUY) is None
    assert tradable.why_not(BBRI, Side.SELL) is None
    assert tradable.why_not(BBRI, Side.BUY) == Note(
        TRADE_NOT_IN_UNIVERSE, "not in the universe on 2025-06-02"
    )
    assert tradable.why_not(TLKM, Side.BUY) == RIGHTS
    assert tradable.why_not(TLKM, Side.SELL) == RIGHTS
    assert tradable.why_not(Instrument("ASII", "IDX", IDR), Side.SELL) == Note(
        TRADE_NOT_HELD, "not held"
    )

```

<!-- edit: tests/engine/test_view.py -->
Replace:
```python
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be both tradable and kept out$"):
        Tradable(D0, frozenset({BBCA}), frozenset({BBRI}), {BBRI: "no bar", BBCA: "no bar"})
    with pytest.raises(TypeError, match=r"^buyable must be a frozenset, got set$"):
```
with:
```python
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be both tradable and kept out$"):
        Tradable(D0, frozenset({BBCA}), frozenset({BBRI}), {BBRI: NO_BAR, BBCA: NO_BAR})
    with pytest.raises(TypeError, match=r"^buyable must be a frozenset, got set$"):
```


- [ ] **Step 3: Write the stubs.** This story retypes existing names and adds only constants, so there is nothing to stub: this step writes the 22 key constants, their exports and the imports of the five modules that will use them (`view`, `risk`, `engine`, `corporate`, `broker/simulated`), and every function keeps its old body.

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    CORPORATE_SPLIT_FRACTION_DROPPED,
    DATA_BAR_MISSING,
```
with:
```python
    CORPORATE_SPLIT_FRACTION_DROPPED,
    CORPORATE_SPLIT_ORDER_CANCELLED,
    DATA_BAR_MISSING,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    EXEMPTION_DEADLINE_MISSED,
    INCOME_GROWTH_SHORT_HISTORY,
    INCOME_PROJECTION_COSTS_IGNORED,
    RISK_HALT_DAILY_LOSS,
    RISK_HALT_DRAWDOWN,
    Note,
```
with:
```python
    EXEMPTION_DEADLINE_MISSED,
    FILL_CASH_CUT,
    FILL_CASH_SHORT,
    FILL_CHARGES_UNPAID,
    FILL_FROZEN,
    FILL_NO_BAR,
    FILL_NO_REFERENCE,
    FILL_NO_TRADES,
    FILL_OUTSIDE_BAND,
    FILL_VOLUME_CUT,
    FILL_VOLUME_TOO_SMALL,
    INCOME_GROWTH_SHORT_HISTORY,
    INCOME_PROJECTION_COSTS_IGNORED,
    LIMIT_CASH_CUT,
    LIMIT_CASH_SHORT,
    LIMIT_MIN_LOTS,
    LIMIT_WEIGHT_CUT,
    LIMIT_WEIGHT_FULL,
    RISK_HALT_DAILY_LOSS,
    RISK_HALT_DRAWDOWN,
    TRADE_EXCLUDED,
    TRADE_FROZEN,
    TRADE_NO_BAR,
    TRADE_NOT_HELD,
    TRADE_NOT_IN_UNIVERSE,
    TRADE_REFUSED,
    Note,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "CORPORATE_SPLIT_FRACTION_DROPPED",
    "DATA_BAR_MISSING",
```
with:
```python
    "CORPORATE_SPLIT_FRACTION_DROPPED",
    "CORPORATE_SPLIT_ORDER_CANCELLED",
    "DATA_BAR_MISSING",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "FIGURES",
    "GROWTH_YEARS",
```
with:
```python
    "FIGURES",
    "FILL_CASH_CUT",
    "FILL_CASH_SHORT",
    "FILL_CHARGES_UNPAID",
    "FILL_FROZEN",
    "FILL_NO_BAR",
    "FILL_NO_REFERENCE",
    "FILL_NO_TRADES",
    "FILL_OUTSIDE_BAND",
    "FILL_VOLUME_CUT",
    "FILL_VOLUME_TOO_SMALL",
    "GROWTH_YEARS",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "INCOME_PROJECTION_COSTS_IGNORED",
    "MAX_MINOR_UNITS",
```
with:
```python
    "INCOME_PROJECTION_COSTS_IGNORED",
    "LIMIT_CASH_CUT",
    "LIMIT_CASH_SHORT",
    "LIMIT_MIN_LOTS",
    "LIMIT_WEIGHT_CUT",
    "LIMIT_WEIGHT_FULL",
    "MAX_MINOR_UNITS",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "TERM_YIELD_ON_COST",
    "YEAR_DAYS",
```
with:
```python
    "TERM_YIELD_ON_COST",
    "TRADE_EXCLUDED",
    "TRADE_FROZEN",
    "TRADE_NOT_HELD",
    "TRADE_NOT_IN_UNIVERSE",
    "TRADE_NO_BAR",
    "TRADE_REFUSED",
    "YEAR_DAYS",
```

**`packages/steadyhand/src/steadyhand/broker/simulated.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
```
with:
```python
from steadyhand.money import Money, Rounding
from steadyhand.notes import (
    FILL_CASH_CUT,
    FILL_CASH_SHORT,
    FILL_CHARGES_UNPAID,
    FILL_FROZEN,
    FILL_NO_BAR,
    FILL_NO_REFERENCE,
    FILL_NO_TRADES,
    FILL_OUTSIDE_BAND,
    FILL_VOLUME_CUT,
    FILL_VOLUME_TOO_SMALL,
    Note,
)
from steadyhand.outcomes import Cut, Rejected
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
from steadyhand.money import CurrencyMismatchError, Money, Rounding
from steadyhand.notes import CORPORATE_SPLIT_FRACTION_DROPPED, Note
from steadyhand.outcomes import Rejected
```
with:
```python
from steadyhand.money import CurrencyMismatchError, Money, Rounding
from steadyhand.notes import (
    CORPORATE_SPLIT_FRACTION_DROPPED,
    CORPORATE_SPLIT_ORDER_CANCELLED,
    Note,
)
from steadyhand.outcomes import Rejected
```

**`packages/steadyhand/src/steadyhand/engine.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
from steadyhand.money import Money
from steadyhand.notes import DATA_BAR_MISSING, Note
from steadyhand.outcomes import Cut, Rejected
```
with:
```python
from steadyhand.money import Money
from steadyhand.notes import (
    DATA_BAR_MISSING,
    TRADE_EXCLUDED,
    TRADE_FROZEN,
    TRADE_NO_BAR,
    TRADE_REFUSED,
    Note,
)
from steadyhand.outcomes import Cut, Rejected
```

**`packages/steadyhand/src/steadyhand/notes.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/notes.py -->
Replace:
```python

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
```
with:
```python

CORPORATE_SPLIT_ORDER_CANCELLED = "corporate.split.order_cancelled"
"""An order for a stock that splits that day is cancelled: its quantity no longer fits."""

FILL_CASH_CUT = "fill.cash.cut"
"""A buy at the open was made smaller to the cash that could be spent."""

FILL_CASH_SHORT = "fill.cash.short"
"""A buy at the open found no cash to spend, so it was not filled."""

FILL_CHARGES_UNPAID = "fill.charges_unpaid"
"""A sale was refused: the day's charges would exceed the cash and proceeds to pay them."""

FILL_FROZEN = "fill.frozen"
"""An order for a frozen stock was not filled at the open."""

FILL_NO_BAR = "fill.no_bar"
"""An order was not filled: its stock has no bar that day."""

FILL_NO_REFERENCE = "fill.no_reference"
"""An order was not filled: there is no previous close to set its price band."""

FILL_NO_TRADES = "fill.no_trades"
"""An order was not filled: its stock did not trade that day."""

FILL_OUTSIDE_BAND = "fill.outside_band"
"""An order was not filled: its price at the open was outside the day's price band."""

FILL_VOLUME_CUT = "fill.volume.cut"
"""An order was made smaller to its share of the day's traded volume."""

FILL_VOLUME_TOO_SMALL = "fill.volume.too_small"
"""An order was not filled: its share of the day's volume is less than a lot."""

LIMIT_CASH_CUT = "limit.cash.cut"
"""A buy was made smaller to the cash that can be spent."""

LIMIT_CASH_SHORT = "limit.cash.short"
"""A buy was not placed: there is no cash to spend."""

LIMIT_MIN_LOTS = "limit.min_lots"
"""A buy was not placed: it is below the smallest buy allowed."""

LIMIT_WEIGHT_CUT = "limit.weight.cut"
"""A buy was made smaller to the most one stock may be of the portfolio."""

LIMIT_WEIGHT_FULL = "limit.weight.full"
"""A buy was not placed: the stock is already at its weight limit."""

TRADE_EXCLUDED = "trade.excluded"
"""A stock you excluded is not traded."""

TRADE_FROZEN = "trade.frozen"
"""A frozen stock is not traded."""

TRADE_NO_BAR = "trade.no_bar"
"""A stock with no bar today is not traded."""

TRADE_NOT_HELD = "trade.not_held"
"""A stock that is not held cannot be sold."""

TRADE_NOT_IN_UNIVERSE = "trade.not_in_universe"
"""A stock outside the universe on the day cannot be bought."""

TRADE_REFUSED = "trade.refused"
"""A stock whose data the source refused today is not traded."""

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
```

**`packages/steadyhand/src/steadyhand/risk.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
from steadyhand.money import Money, Rounding
from steadyhand.notes import RISK_HALT_DAILY_LOSS, RISK_HALT_DRAWDOWN, Note
from steadyhand.outcomes import Cut, Rejected
```
with:
```python
from steadyhand.money import Money, Rounding
from steadyhand.notes import (
    LIMIT_CASH_CUT,
    LIMIT_CASH_SHORT,
    LIMIT_MIN_LOTS,
    LIMIT_WEIGHT_CUT,
    LIMIT_WEIGHT_FULL,
    RISK_HALT_DAILY_LOSS,
    RISK_HALT_DRAWDOWN,
    Note,
)
from steadyhand.outcomes import Cut, Rejected
```

**`packages/steadyhand/src/steadyhand/view.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Bar, Instrument, Side
```
with:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import TRADE_NOT_HELD, TRADE_NOT_IN_UNIVERSE, Note
from steadyhand.types import Bar, Instrument, Side
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1389 failed=31 -->
Expected: 1389 run, 31 failed, every one a new or changed test that expects a keyed reason and meets the old string: 27 compare a keyed `Note` with the old text, 3 fail with `TypeError: reason must be a str, got Note` building an outcome from a `Note`, and `test_every_reason_is_a_note_under_a_key` fails with `DID NOT RAISE TypeError`, since the old outcome accepts a string reason. Two changed tests pass against the stubs, since what they check is unchanged: `test_a_cut_leaves_fewer_shares_than_the_order` and `test_a_stock_cannot_be_both_tradable_and_kept_out`.

- [ ] **Step 5: Implement.** The lessons are part of this step.

**`packages/steadyhand-idx/src/steadyhand_idx/paper.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
                f"cut: {cut.order.side.value} {cut.order.instrument.symbol} from "
                f"{cut.order.quantity} to {cut.quantity} shares: {cut.reason}",
            ),
```
with:
```python
                f"cut: {cut.order.side.value} {cut.order.instrument.symbol} from "
                f"{cut.order.quantity} to {cut.quantity} shares: {cut.reason.text}",
            ),
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
                f"skipped: {rejected.order.side.value} {rejected.order.quantity} "
                f"{rejected.order.instrument.symbol}: {rejected.reason}",
            ),
```
with:
```python
                f"skipped: {rejected.order.side.value} {rejected.order.quantity} "
                f"{rejected.order.instrument.symbol}: {rejected.reason.text}",
            ),
```

**`packages/steadyhand/src/steadyhand/broker/simulated.py`** (implemented: 8 edits)

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python
            price = self._price(order, opening)
            if isinstance(price, str):
                session.reject(order, price)
                continue
            wanted = self._volume_capped(order, opening, session)
            if isinstance(wanted, str):
                session.reject(order, wanted)
```
with:
```python
            price = self._price(order, opening)
            if isinstance(price, Note):
                session.reject(order, price)
                continue
            wanted = self._volume_capped(order, opening, session)
            if isinstance(wanted, Note):
                session.reject(order, wanted)
```

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python

    def _price(self, order: Order, opening: Opening) -> Money | str:
        instrument = order.instrument
```
with:
```python

    def _price(self, order: Order, opening: Opening) -> Money | Note:
        instrument = order.instrument
```

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python
        if instrument in opening.frozen:
            return f"frozen: {opening.frozen[instrument]}"
        if bar is None:
            return f"no bar for {instrument.symbol} on {day.isoformat()}"
        if bar.volume == 0:
            return f"{instrument.symbol} did not trade on {day.isoformat()}"
        slippage = self._settings.slippage
```
with:
```python
        if instrument in opening.frozen:
            return Note(FILL_FROZEN, f"frozen: {opening.frozen[instrument]}")
        if bar is None:
            return Note(FILL_NO_BAR, f"no bar for {instrument.symbol} on {day.isoformat()}")
        if bar.volume == 0:
            return Note(FILL_NO_TRADES, f"{instrument.symbol} did not trade on {day.isoformat()}")
        slippage = self._settings.slippage
```

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python
        if reference is None:
            return f"no previous close for {instrument.symbol} to set the price band"
        low, high = self._rules.price_band(instrument, reference, day)
        if not low <= price <= high:
            return f"fill price {price} is outside the band {low} to {high}"
        return price

    def _volume_capped(self, order: Order, opening: Opening, session: _Session) -> int | str:
        cap = self._settings.volume_cap
```
with:
```python
        if reference is None:
            return Note(
                FILL_NO_REFERENCE,
                f"no previous close for {instrument.symbol} to set the price band",
            )
        low, high = self._rules.price_band(instrument, reference, day)
        if not low <= price <= high:
            return Note(
                FILL_OUTSIDE_BAND, f"fill price {price} is outside the band {low} to {high}"
            )
        return price

    def _volume_capped(self, order: Order, opening: Opening, session: _Session) -> int | Note:
        cap = self._settings.volume_cap
```

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python
        if allowed == 0:
            return f"{_percent(cap)} of the day's {volume:,} shares traded is less than a lot"
        if order.quantity <= allowed:
            return order.quantity
        session.cut(order, allowed, f"cut to {_percent(cap)} of the day's {volume:,} shares traded")
        return allowed
```
with:
```python
        if allowed == 0:
            return Note(
                FILL_VOLUME_TOO_SMALL,
                f"{_percent(cap)} of the day's {volume:,} shares traded is less than a lot",
            )
        if order.quantity <= allowed:
            return order.quantity
        session.cut(
            order,
            allowed,
            Note(FILL_VOLUME_CUT, f"cut to {_percent(cap)} of the day's {volume:,} shares traded"),
        )
        return allowed
```

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python

    def reject(self, order: Order, reason: str) -> None:
        self._rejected.append(Rejected(order, reason))

    def cut(self, order: Order, quantity: int, reason: str) -> None:
        self._cuts.append(Cut(order, quantity, reason))
```
with:
```python

    def reject(self, order: Order, reason: Note) -> None:
        self._rejected.append(Rejected(order, reason))

    def cut(self, order: Order, quantity: int, reason: Note) -> None:
        self._cuts.append(Cut(order, quantity, reason))
```

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python
        if quantity == 0:
            self.reject(order, f"not enough cash: {available} can be spent")
            return
        if quantity < wanted:
            self.cut(order, quantity, f"cut to the {available} that can be spent")
        self._book(order, quantity, price)
```
with:
```python
        if quantity == 0:
            self.reject(order, Note(FILL_CASH_SHORT, f"not enough cash: {available} can be spent"))
            return
        if quantity < wanted:
            self.cut(
                order, quantity, Note(FILL_CASH_CUT, f"cut to the {available} that can be spent")
            )
        self._book(order, quantity, price)
```

<!-- edit: packages/steadyhand/src/steadyhand/broker/simulated.py -->
Replace:
```python
            self.reject(
                order, f"the day's charges of {daily} exceed the {covering} that could pay them"
            )
```
with:
```python
            self.reject(
                order,
                Note(
                    FILL_CHARGES_UNPAID,
                    f"the day's charges of {daily} exceed the {covering} that could pay them",
                ),
            )
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
            self._pending.remove(order)
            self._cancelled.append(Rejected(order, "split on ex-date"))

```
with:
```python
            self._pending.remove(order)
            self._cancelled.append(
                Rejected(order, Note(CORPORATE_SPLIT_ORDER_CANCELLED, "split on ex-date"))
            )

```

**`packages/steadyhand/src/steadyhand/engine.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    day = inputs.day
    reasons: dict[Instrument, str] = {}
    for instrument in inputs.refused:
        reasons[instrument] = f"the data source refused {day.isoformat()}"
    for instrument, reason in frozen.items():
        reasons.setdefault(instrument, f"frozen: {reason}")
    for instrument, reason in inputs.excluded.items():
        reasons.setdefault(instrument, f"excluded: {reason}")
    warnings: list[Note] = []
```
with:
```python
    day = inputs.day
    reasons: dict[Instrument, Note] = {}
    for instrument in inputs.refused:
        reasons[instrument] = Note(TRADE_REFUSED, f"the data source refused {day.isoformat()}")
    for instrument, reason in frozen.items():
        reasons.setdefault(instrument, Note(TRADE_FROZEN, f"frozen: {reason}"))
    for instrument, reason in inputs.excluded.items():
        reasons.setdefault(instrument, Note(TRADE_EXCLUDED, f"excluded: {reason}"))
    warnings: list[Note] = []
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
            continue
        reasons[instrument] = f"no bar on {day.isoformat()}"
        warning = f"{instrument.symbol} has no bar on {day.isoformat()}, so it is not traded"
```
with:
```python
            continue
        reasons[instrument] = Note(TRADE_NO_BAR, f"no bar on {day.isoformat()}")
        warning = f"{instrument.symbol} has no bar on {day.isoformat()}, so it is not traded"
```

**`packages/steadyhand/src/steadyhand/outcomes.py`** (implemented: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/outcomes.py -->
Replace:
```python
The broker, the sizer and the risk manager all report the same two things, each with a reason
that the day's report prints (core spec §6.1: every dropped or cut order carries a reason).
"""
```
with:
```python
The broker, the sizer and the risk manager all report the same two things, each with a reason
that the day's report prints (core spec §6.1: every dropped or cut order carries a reason). A
reason is a ``Note``: a sentence under a key that never changes, so a lesson can explain it
(M4 spec §7, M5 spec §7.4).
"""
```

<!-- edit: packages/steadyhand/src/steadyhand/outcomes.py -->
Replace:
```python
from steadyhand._validate import require_int, require_type
from steadyhand.types import Order


def _require_reason(reason: object, order: Order) -> None:
    require_type(reason, str, "reason")
    if not str(reason).strip():
        msg = f"a {order.side.value} order for {order.instrument.symbol} needs a reason"
        raise ValueError(msg)

```
with:
```python
from steadyhand._validate import require_int, require_type
from steadyhand.notes import Note
from steadyhand.types import Order

```

<!-- edit: packages/steadyhand/src/steadyhand/outcomes.py -->
Replace:
```python
    order: Order
    reason: str

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        _require_reason(self.reason, self.order)

```
with:
```python
    order: Order
    reason: Note

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        require_type(self.reason, Note, "reason")

```

<!-- edit: packages/steadyhand/src/steadyhand/outcomes.py -->
Replace:
```python
    quantity: int
    reason: str

```
with:
```python
    quantity: int
    reason: Note

```

<!-- edit: packages/steadyhand/src/steadyhand/outcomes.py -->
Replace:
```python
            raise ValueError(msg)
        _require_reason(self.reason, self.order)
```
with:
```python
            raise ValueError(msg)
        require_type(self.reason, Note, "reason")
```

**`packages/steadyhand/src/steadyhand/risk.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
                if quantity == 0:
                    rejected.append(Rejected(order, f"already at the {limit} limit per stock"))
                    continue
                cuts.append(Cut(order, quantity, f"cut to the {limit} limit per stock"))
            smallest = self._limits.min_lots * lot
            if quantity < smallest:
                reason = f"below the minimum buy of {self._limits.min_lots} lot(s)"
                rejected.append(Rejected(order, reason))
```
with:
```python
                if quantity == 0:
                    full = Note(LIMIT_WEIGHT_FULL, f"already at the {limit} limit per stock")
                    rejected.append(Rejected(order, full))
                    continue
                cut = Note(LIMIT_WEIGHT_CUT, f"cut to the {limit} limit per stock")
                cuts.append(Cut(order, quantity, cut))
            smallest = self._limits.min_lots * lot
            if quantity < smallest:
                reason = Note(
                    LIMIT_MIN_LOTS, f"below the minimum buy of {self._limits.min_lots} lot(s)"
                )
                rejected.append(Rejected(order, reason))
```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
            if affordable == 0:
                rejected.append(Rejected(order, f"not enough cash: {budget} can be spent"))
                continue
            if affordable < quantity:
                cuts.append(Cut(order, affordable, f"cut to the {budget} that can be spent"))
            budget -= self._cost(affordable, price, day)
```
with:
```python
            if affordable == 0:
                short = Note(LIMIT_CASH_SHORT, f"not enough cash: {budget} can be spent")
                rejected.append(Rejected(order, short))
                continue
            if affordable < quantity:
                cut = Note(LIMIT_CASH_CUT, f"cut to the {budget} that can be spent")
                cuts.append(Cut(order, affordable, cut))
            budget -= self._cost(affordable, price, day)
```

**`packages/steadyhand/src/steadyhand/snapshot.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/snapshot.py -->
Replace:
```python
        "fills": [_fill(fill) for fill in report.fills],
        "rejected": [{"order": _order(r.order), "reason": r.reason} for r in report.rejected],
        "cuts": [
            {"order": _order(c.order), "quantity": c.quantity, "reason": c.reason}
            for c in report.cuts
```
with:
```python
        "fills": [_fill(fill) for fill in report.fills],
        "rejected": [
            {"order": _order(r.order), "reason": _note(r.reason)} for r in report.rejected
        ],
        "cuts": [
            {"order": _order(c.order), "quantity": c.quantity, "reason": _note(c.reason)}
            for c in report.cuts
```

<!-- edit: packages/steadyhand/src/steadyhand/snapshot.py -->
Replace:
```python
    order, reason = _fields(value, "order", "reason")
    return Rejected(_read_order(order), _str(reason))

```
with:
```python
    order, reason = _fields(value, "order", "reason")
    return Rejected(_read_order(order), _read_note(reason))

```

<!-- edit: packages/steadyhand/src/steadyhand/snapshot.py -->
Replace:
```python
    order, quantity, reason = _fields(value, "order", "quantity", "reason")
    return Cut(_read_order(order), _int(quantity), _str(reason))

```
with:
```python
    order, quantity, reason = _fields(value, "order", "quantity", "reason")
    return Cut(_read_order(order), _int(quantity), _read_note(reason))

```

**`packages/steadyhand/src/steadyhand/training/lessons/en/orders.at_the_open.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/orders.at_the_open.md -->
```markdown
+++
id = "orders.at_the_open"
title = "What can happen to an order at the next open"
summary = "An order fills at the next day's opening price, unless something on that day stops it or makes it smaller."
explains = ["fill.frozen", "fill.no_bar", "fill.no_trades", "fill.no_reference", "fill.outside_band", "fill.volume.too_small", "fill.volume.cut", "fill.cash.short", "fill.cash.cut", "fill.charges_unpaid"]
module = "using-steadyhand"
position = 7
see_also = ["orders.not_tradable", "risk.limits"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md §5"]
+++

An order made after the close fills the next trading day at the opening price, as you would
place it at the open in your broker's app. steadyhand checks the order again at that moment:

- **Frozen, no bar or no trades.** If the stock was frozen, had no price that day, or did not
  trade at all, the order does not fill.
- **No previous close.** The day's allowed price range is set from the last close. Without one,
  the order does not fill.
- **Outside the price band.** The exchange rejects an order priced outside the day's allowed
  range, so a price at the open beyond it does not fill either.
- **Too much of the day's volume.** An order may take only a small share of the shares traded
  that day. A larger order is cut down to that share, and one whose share is less than a lot
  does not fill.
- **Not enough cash.** A buy is paid from settled cash at the open. If there is less than
  planned, the buy is cut to what can be spent, or does not fill at all.
- **Charges not covered.** A sale is refused if the day's charges would be more than the cash
  and the sale's proceeds could pay.

Each order that does not fill, or fills smaller, is listed in the day's report with its reason.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/orders.not_tradable.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/orders.not_tradable.md -->
```markdown
+++
id = "orders.not_tradable"
title = "Why a stock is not traded on a day"
summary = "The reasons a stock is left out of a day's buying or selling, whatever the strategy wants."
explains = ["trade.not_in_universe", "trade.not_held", "trade.excluded", "trade.frozen", "trade.no_bar", "trade.refused"]
module = "using-steadyhand"
position = 6
see_also = ["orders.at_the_open"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md §6.4", "docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md §7.3"]
+++

Each trading day, steadyhand first works out which stocks can be bought and which can be sold.
A strategy may still ask for others, but those orders are skipped, and the report says why:

- **Not in the universe.** Only stocks in the day's universe, the index list your
  configuration names, can be bought.
- **Not held.** You can only sell what you own: there is no short selling.
- **Excluded.** You listed the stock in your exclusions file, so it is never bought, and a
  holding in it is frozen.
- **Frozen.** A stock you hold is frozen when it is excluded or when a corporate action cannot
  be modelled. It is neither bought nor sold until you deal with it yourself.
- **No bar.** The data source has no price for the stock that day, often because it was
  suspended. With no price there is nothing safe to trade on.
- **Refused.** The data source refused to give that day's prices, so the stock is left alone
  until its data is clean again.

A stock left out on one day can be traded again on a later day once the reason has gone.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md`** (changed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md -->
Replace:
```markdown
summary = "The limits that cut or stop a strategy's orders, whatever the strategy wants to do."
explains = ["risk.halt.daily_loss", "risk.halt.drawdown"]
module = "risk"
```
with:
```markdown
summary = "The limits that cut or stop a strategy's orders, whatever the strategy wants to do."
explains = [
    "risk.halt.daily_loss",
    "risk.halt.drawdown",
    "limit.weight.full",
    "limit.weight.cut",
    "limit.min_lots",
    "limit.cash.short",
    "limit.cash.cut",
]
module = "risk"
```

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md -->
Replace:
```markdown
- **At most 10% in one stock.** A buy that would take one stock above 10% of the portfolio's
  value is cut back to 10%.
- **Daily loss limit.** If the portfolio falls 5% in one day, the strategy **halts**: it places
```
with:
```markdown
- **At most 10% in one stock.** A buy that would take one stock above 10% of the portfolio's
  value is cut back to 10%, and is not placed at all if the stock is already there.
- **A smallest buy.** A buy smaller than the minimum number of lots is not placed.
- **Daily loss limit.** If the portfolio falls 5% in one day, the strategy **halts**: it places
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/shares.splits.md`** (changed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/shares.splits.md -->
Replace:
```markdown
summary = "A split changes how many shares you hold and the price of each, without changing what the holding is worth."
explains = ["corporate.split.fraction_dropped"]
module = "shares-and-dividends"
```
with:
```markdown
summary = "A split changes how many shares you hold and the price of each, without changing what the holding is worth."
explains = ["corporate.split.fraction_dropped", "corporate.split.order_cancelled"]
module = "shares-and-dividends"
```

<!-- edit: packages/steadyhand/src/steadyhand/training/lessons/en/shares.splits.md -->
Replace:
```markdown
in a note, so a report shows slightly less than a real account would.
```
with:
```markdown
in a note, so a report shows slightly less than a real account would.

An order queued for a stock whose split takes effect that day is cancelled: it was sized for
the old share count, so the strategy decides again after the split.
```

**`packages/steadyhand/src/steadyhand/view.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
    sellable: frozenset[Instrument]
    reasons: Mapping[Instrument, str]

```
with:
```python
    sellable: frozenset[Instrument]
    reasons: Mapping[Instrument, Note]

```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python

    def why_not(self, instrument: Instrument, side: Side) -> str | None:
        """Why *instrument* cannot be traded on *side* today, or ``None`` when it can."""
```
with:
```python

    def why_not(self, instrument: Instrument, side: Side) -> Note | None:
        """Why *instrument* cannot be traded on *side* today, or ``None`` when it can."""
```

<!-- edit: packages/steadyhand/src/steadyhand/view.py -->
Replace:
```python
        if side is Side.BUY:
            return f"not in the universe on {self.day.isoformat()}"
        return "not held"

```
with:
```python
        if side is Side.BUY:
            return Note(TRADE_NOT_IN_UNIVERSE, f"not in the universe on {self.day.isoformat()}")
        return Note(TRADE_NOT_HELD, "not held")

```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1389 passed=1389 -->
Expected: every command exits 0; 1389 passed, 100% branch coverage; the performance step passes its five tests.

- [ ] **Step 7: Mutations.** Run M266–M273 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M5b S8 every order reason keyed, with its lessons`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 5: M5b S9 The paper commands: status, report, resume and switch

**Acceptance criteria (story text):**
1. `paper status` shows the opening day, the strategy and the last day run; the halt, if any, with the exact `resume` command; settled and unsettled cash, the holdings value and the total (scope decision 13); each holding's quantity, last close, value and weight; the orders queued for the next open; the dividend entitlements; the open claims under `CLAIMS_LABEL`, each with what is still to reinvest and each protected part until its date; and the frozen stocks with their reasons (M5 §7.1). A halted account exits 0.
2. `report` shows the latest saved day, and `report --day D` any saved day: fills, orders queued, blocked orders with their reasons, cash, holdings value, total, daily charges and deposit, the holdings on the latest day only (scope decision 23), dividends paid and earned, dividend tax, any halt, warnings and notes, each with its key, and any frozen stocks with their reasons. A day with no saved report exits 2 naming the first and last saved days.
3. `report --income` is `income_of` over every saved report, the saved state and five years of each holding's corporate actions through the source, and equals the backtest's income report over the same days; it shows received income, the run-rate, the payment calendar, the goal, the three scenarios under `Projection, not a promise`, and the open claims (M5 §7.2, scope decisions 20–21).
4. `resume <strategy>` must name the account's strategy (else exit 2); with nothing halted it says so and exits 0; while the drawdown is at or past the limit it exits 3 changing nothing (scope decision 18); otherwise it shows the halt, asks for `resume`, clears the halt and writes `paper.resumed` naming who resumed it (`USER`, then `LOGNAME`, then `unknown`), dated today in Jakarta.
5. `paper switch <name>` must name the configured strategy and differ from the saved one (else exit 2), is refused while halted (exit 3); it asks for the name, keeps the holdings and cash, clears the strategy's memory, saves the name and writes `paper.strategy.switched` (M5 §7.3). Any other answer to either prompt, or none, exits 2 and changes nothing; a day another run saves while the prompt waits refuses the change with exit 3 (scope decision 19).
6. Before any day is run, `paper status`, `report`, `resume` and `paper switch` exit 2 saying how to open the account. `EXIT_CODES` gains `NoAccountError`, `NoReportError`, `WrongStrategyError` and `SwitchRefusedError` at 2, and `HaltCausePresentError` and `AccountChangedError` at 3.
7. `paper.resumed` and `paper.strategy.switched` ship with the lessons `paper.status_and_reports` and `paper.halts_and_switching`, module 6 positions 8 and 9, completing T1's module 6.
8. The M5b journey runs `init`, `backtest`, `paper run` twice the same day, `paper status`, `report`, `report --income`, a halt, `resume` and the next `paper run` (M5 §9.1). One day's run on a five-year account, a 30-day catch-up and the size of a five-year state stay inside the budgets **Measured performance** gives.
9. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M274–M295 each turn the whole suite red.

**Files:**
- Create: `.../steadyhand_idx/training/lessons/en/paper.{status_and_reports,halts_and_switching}.md`, `tests/cli/test_paper_commands.py`, `tests/perf/{synthetic,test_paper_performance}.py`
- Modify: `.../steadyhand/{__init__,backtest,risk,terms}.py`, `.../steadyhand_idx/{cli,config,notes,paper,paper_pages,reports}.py`, `pyproject.toml`, `tests/cli/{cli_world,test_cli,test_journeys,test_paper_run}.py`, `tests/perf/test_performance.py`

**Interfaces:**
- Consumes: Tasks 1–4; M4's `IncomeReport`, `CLAIMS_LABEL` and `PROJECTION_LABEL`.
- Produces: `steadyhand.income_of(reports, final, market, settings, goal) -> IncomeReport`, `steadyhand.percent(rate) -> str`, `UnitValue.drawdown`. `Config.goal`. In `steadyhand_idx.paper`: `NoAccountError`, `NoReportError`, `WrongStrategyError`, `HaltCausePresentError`, `SwitchRefusedError` (`not_configured`, `already`), `AccountChangedError`, `saved_account(store)`, `saved_report(store, day)`, `check_resume(account, named, limits)`, `resume(store, account, halt, day, user)`, `check_switch(account, name, configured)`, `switch(store, account, name, day, user)`, `cut_line(cut)`, `skipped_line(rejected)`. In `steadyhand_idx.paper_pages`: `status_page(account, report)`, `day_report_page(report, account)`, `income_page(income)`. `steadyhand_idx.reports.text_table`. In `steadyhand_idx.notes`: `PAPER_RESUMED`, `PAPER_STRATEGY_SWITCHED`.

- [ ] **Step 1: Branch.** `git switch -c m5/s9-paper-commands origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/cli/cli_world.py`** (changed: 6 edits)

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
import os
import stat
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import product
```
with:
```python
import os
import sqlite3
import stat
import subprocess
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta, timezone
from functools import cache
from itertools import product
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python

from record_golden import RECORDED, START, STOCKS, recorded

from steadyhand import DataSource
from steadyhand_idx import BarCache, CachedDataSource, YahooDataSource
from steadyhand_idx.cli import SourceFactory, World, main
from steadyhand_idx.yahoo import YahooHistory
```
with:
```python

from record_golden import END, RECORDED, START, STOCKS, recorded

from steadyhand import BacktestResult, BuyAndHold, DataSource, Market, backtest
from steadyhand_idx import BarCache, CachedDataSource, YahooDataSource
from steadyhand_idx.cli import SourceFactory, World, main
from steadyhand_idx.config import load
from steadyhand_idx.paper import days_to_run
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.state import STATE_FILE, StateStore
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe
from steadyhand_idx.yahoo import YahooHistory
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
class Cli:
    """``steadyhand-idx`` with its data directory at ``home``."""

```
with:
```python
class Cli:
    """``steadyhand-idx`` with its data directory at ``home``, and *env* besides."""

```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
    now: datetime = NOW

```
with:
```python
    now: datetime = NOW
    env: Mapping[str, str] = field(default_factory=dict)

```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
        out, err = io.StringIO(), io.StringIO()
        env = {"STEADYHAND_HOME": str(self.home)}
        world = World(io.StringIO(stdin), out, err, env, lambda: self.now, self.source)
```
with:
```python
        out, err = io.StringIO(), io.StringIO()
        env = {**self.env, "STEADYHAND_HOME": str(self.home)}
        world = World(io.StringIO(stdin), out, err, env, lambda: self.now, self.source)
```

<!-- edit: tests/cli/cli_world.py -->
Replace:
```python
    return Result(done.returncode, done.stdout, done.stderr)
```
with:
```python
    return Result(done.returncode, done.stdout, done.stderr)


WIB = timezone(timedelta(hours=7))


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


@cache
def trading_days() -> tuple[date, ...]:
    """The golden window's trading days, from the IDX calendar."""
    return days_to_run(START - timedelta(days=1), END, rules())


def at(day: date, hour: int = 17, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=WIB)


def paper(tmp_path: Path, config: str = GOLDEN_CONFIG) -> Cli:
    return market_cli(tmp_path / "home", config)


def run_on(cli: Cli, day: date, *extra: str) -> Result:
    return replace(cli, now=at(day))("paper", "run", *extra)


@contextmanager
def opened(cli: Cli) -> Iterator[StateStore]:
    with StateStore(cli.home / STATE_FILE) as store:
        yield store


def tables(cli: Cli) -> dict[str, list[tuple[object, ...]]]:
    """Every row of the account, the day reports and the audit log, as SQLite holds them."""
    database = sqlite3.connect(cli.home / STATE_FILE)
    try:
        return {
            table: database.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608
            for table in ("account", "day_reports", "audit")
        }
    finally:
        database.close()


def golden_backtest(cli: Cli, end: date, *, goal: bool = False) -> BacktestResult:
    """``buy-and-hold`` from the golden window's first day to *end*, as ``backtest`` runs it over
    the same configuration, universe files and recorded data. Without the income goal unless
    *goal*: its report reads five years before *end* (M4 spec §8), which the recordings do not
    cover for an early *end*, and it changes neither the states nor the day reports."""
    config = load(cli.config)
    universe = Lq45Universe(
        Lq45Membership.load(config.lq45_members), Exclusions.load(config.exclusions)
    )
    with recorded_source(cli.home) as source:
        market = Market(universe, source, IdxMarketRules(broker_fees=config.broker_fees))
        return backtest(
            BuyAndHold(),
            market,
            START,
            end,
            config.settings if goal else replace(config.settings, goal=None),
        )
```

**`tests/cli/test_cli.py`** (changed: 6 edits)

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
from datetime import date
from pathlib import Path
```
with:
```python
from datetime import date
from decimal import Decimal
from pathlib import Path
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
from steadyhand_idx.paper import (
    AccountHaltedError,
    CatchUpError,
    StaleDataError,
    StrategyChangedError,
)
```
with:
```python
from steadyhand_idx.paper import (
    AccountChangedError,
    AccountHaltedError,
    CatchUpError,
    HaltCausePresentError,
    NoAccountError,
    NoReportError,
    StaleDataError,
    StrategyChangedError,
    SwitchRefusedError,
    WrongStrategyError,
)
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
        (StrategyChangedError, 2),
        (DataUnavailableError, 3),
```
with:
```python
        (StrategyChangedError, 2),
        (NoAccountError, 2),
        (NoReportError, 2),
        (WrongStrategyError, 2),
        (SwitchRefusedError, 2),
        (DataUnavailableError, 3),
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
        (AccountHaltedError, 3),
    ) == EXIT_CODES
```
with:
```python
        (AccountHaltedError, 3),
        (HaltCausePresentError, 3),
        (AccountChangedError, 3),
    ) == EXIT_CODES
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
        (lambda: StrategyChangedError("buy-and-hold", "retired"), 2),
        (lambda: DataUnavailableError("x"), 3),
```
with:
```python
        (lambda: StrategyChangedError("buy-and-hold", "retired"), 2),
        (NoAccountError, 2),
        (lambda: NoReportError(date(2021, 2, 6), date(2021, 2, 1), date(2021, 2, 5)), 2),
        (lambda: WrongStrategyError("momentum", "buy-and-hold"), 2),
        (lambda: SwitchRefusedError.not_configured("momentum", "buy-and-hold"), 2),
        (lambda: SwitchRefusedError.already("buy-and-hold"), 2),
        (lambda: DataUnavailableError("x"), 3),
```

<!-- edit: tests/cli/test_cli.py -->
Replace:
```python
        ),
        (lambda: SnapshotError("x"), 1),
```
with:
```python
        ),
        (lambda: HaltCausePresentError(Decimal("0.0937918"), Decimal("0.05")), 3),
        (AccountChangedError, 3),
        (lambda: SnapshotError("x"), 1),
```

**`tests/cli/test_journeys.py`** (changed: 2 edits)

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
"""The M5a journeys through the installed ``steadyhand-idx``, each in its own process as a user
runs it (M5 spec §9.1). None reads market data, so none needs the network."""

import stat
from pathlib import Path

from cli_world import SCRIPT, installed

from steadyhand import DISCLAIMER
from steadyhand_idx import __version__

```
with:
```python
"""The journeys of M5 spec §9.1. M5a's run the installed ``steadyhand-idx``, each command in its
own process as a user runs it; none reads market data, so none needs the network. The paper
journey reads market data, so it runs in-process over the recorded Yahoo answers, as every
``paper`` test does."""

import stat
from dataclasses import replace
from pathlib import Path

from cli_world import (
    GOLDEN_CONFIG,
    SCRIPT,
    Cli,
    at,
    installed,
    opened,
    recorded_source,
    trading_days,
    write_universe,
)
from record_golden import START

from steadyhand import DISCLAIMER, RISK_HALT_DAILY_LOSS
from steadyhand_idx import __version__
from steadyhand_idx.notes import PAPER_RESUMED

```

<!-- edit: tests/cli/test_journeys.py -->
Replace:
```python
    assert not home.exists()
```
with:
```python
    assert not home.exists()


def test_a_paper_traders_journey(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cli = Cli(home, recorded_source, at(START))
    cli.init(training="off")
    write_universe(home)
    settings = GOLDEN_CONFIG + '\n[training]\nlevel = "off"\n'
    cli.config.write_text(settings, encoding="utf-8")

    # The golden window: an income report reads five years back, which the recordings cover
    # for this last day (M4 spec §8).
    tested = cli("backtest", "--from", "2021-02-01", "--to", "2022-01-31")
    assert tested.code == 0, tested.err
    assert tested.out.startswith("Backtest: buy-and-hold, 2021-02-01 to 2022-01-31")

    first = cli("paper", "run")
    assert first.code == 0, first.err
    assert first.out.startswith("2021-02-01: 0 fill(s), 4 order(s) queued, value IDR 100,000,000")
    again = cli("paper", "run")
    assert again.code == 0
    assert again.out.startswith("already up to date for 2021-02-01\n")
    status = cli("paper", "status")
    assert status.code == 0
    assert status.out.startswith("Paper account opened on 2021-02-01, running buy-and-hold")
    report = cli("report")
    assert report.code == 0
    assert report.out.startswith("Day report for 2021-02-01\n")
    income = cli("report", "--income")
    assert income.code == 0, income.err
    assert income.out.startswith("Income as of 2021-02-01\n")

    jumpy = settings.replace(
        'max_weight = "0.25"\n', 'max_weight = "0.25"\ndaily_loss_limit = "0.001"\n'
    )
    assert jumpy != settings
    cli.config.write_text(jumpy, encoding="utf-8")
    second = replace(cli, now=at(trading_days()[1]), env={"USER": "trader"})
    halted = second("paper", "run")
    assert halted.code == 3
    assert "steadyhand-idx resume buy-and-hold" in halted.err
    resumed = second("resume", "buy-and-hold", stdin="resume\n")
    assert resumed.code == 0, resumed.err
    assert resumed.out.endswith(
        f"Resumed. From the next day run, the strategy's orders are placed again.\n\n{DISCLAIMER}\n"
    )
    later = replace(cli, now=at(trading_days()[2]))("paper", "run")
    assert later.code == 0, later.err
    with opened(cli) as store:
        assert store.days() == trading_days()[:3]
        keys = [line.note.key for line in store.audit()]
    assert keys.index(PAPER_RESUMED) == keys.index(RISK_HALT_DAILY_LOSS) + 1
```

**`tests/cli/test_paper_commands.py`** (new)

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
    FILL_CASH_CUT,
    IDR,
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
        "- buy 4100 ASII\n"
        "- buy 700 BBCA\n"
        "- buy 7700 TLKM\n"
        "- buy 3500 UNVR\n"
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
        "Cash: IDR 1,406,106 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 83,415,500\n"
        "Total value: IDR 84,821,606\n"
        "\n"
        "Holdings:\n"
        "Stock  Quantity  Last close           Value  Weight\n"
        "ASII       4200   IDR 4,940  IDR 20,748,000  24.46%\n"
        "BBCA        700  IDR 30,125  IDR 21,087,500  24.86%\n"
        "TLKM       7700   IDR 3,150  IDR 24,255,000  28.60%\n"
        "UNVR       3500   IDR 4,950  IDR 17,325,000  20.43%\n"
        "\n"
        "Queued for the next open: none\n"
    ) in result.out


def test_status_shows_a_dividend_entitlement_until_it_is_paid(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 8), quiet())
    result = cli("paper", "status")
    assert (
        "Dividend entitlements:\n"
        "- BBCA: IDR 302,400 before tax, ex-date 2021-04-08, paid on 2021-04-28\n"
    ) in result.out


def test_status_shows_open_claims_under_their_label(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 4, 28), quiet(GOLDEN_CONFIG + EXEMPT))
    result = cli("paper", "status")
    assert "Dividend entitlements: none\n" in result.out
    assert (
        f"Reinvestment-exemption claims ({CLAIMS_LABEL}):\n"
        "- BBCA: IDR 302,400 paid on 2021-04-28, IDR 302,400 still to reinvest by 2022-03-31\n"
    ) in result.out


def test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected(
    tmp_path: Path,
) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet(GOLDEN_CONFIG + EXEMPT))
    result = cli("paper", "status")
    assert (
        "- BBCA: IDR 302,400 paid on 2021-04-28, IDR 0 still to reinvest by 2022-03-31, "
        "IDR 302,400 protected until 2023-12-31\n"
        "- ASII: IDR 356,700 paid on 2021-05-27, IDR 0 still to reinvest by 2022-03-31, "
        "IDR 181,600 protected until 2023-12-31, IDR 175,100 protected until 2023-12-31\n"
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
        "Halted on 2021-02-02: daily loss limit: the unit value fell 2.38%, the limit is 0.10%. "
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
        "ASII       4200   IDR 4,940  IDR 20,748,000  24.46%\n"
    ) in result.out


def test_a_days_report_shows_its_fills_its_cuts_and_its_cash(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 2, 3), quiet())
    result = cli("report", "--day", "2021-02-02")
    assert (result.code, result.err) == (0, "")
    assert result.out == page(
        "Day report for 2021-02-02\n"
        "\n"
        "Fills:\n"
        "- buy 4100 ASII at IDR 6,175: IDR 25,317,500\n"
        "- buy 700 BBCA at IDR 34,875: IDR 24,412,500\n"
        "- buy 7700 TLKM at IDR 3,310: IDR 25,487,000\n"
        "- buy 3400 UNVR at IDR 7,125: IDR 24,225,000\n"
        "\n"
        "Queued for the next open: none\n"
        "\n"
        "Blocked orders:\n"
        "- cut: buy UNVR from 3500 to 3400 shares: cut to the IDR 24,626,548 that can be spent\n"
        "\n"
        "Cash: IDR 341,160 settled, IDR 0 unsettled\n"
        "Holdings value: IDR 97,276,500\n"
        "Total value: IDR 97,617,660\n"
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
    cli = ran_to(tmp_path, date(2021, 6, 30), quiet())
    result = cli("report", "--day", "2021-06-29")
    assert result.code == 0
    assert (
        "Queued for the next open:\n"
        "- buy 100 ASII\n"
        "- buy 100 UNVR\n"
        "\n"
        "Blocked orders:\n"
        "- skipped: buy 100 TLKM: already at the 25.00% limit per stock\n"
    ) in result.out
    assert "Dividends paid:\n- TLKM: IDR 1,293,677 before tax\n" in result.out


def test_the_skipped_order_is_in_the_audit_log_under_its_key(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 29))
    with opened(cli) as store:
        first = next(line for line in store.audit() if line.note.key == PAPER_ORDER_SKIPPED)
    assert (first.day, first.note.text) == (
        date(2021, 6, 29),
        "skipped: buy 100 TLKM: already at the 25.00% limit per stock",
    )


def test_a_report_names_the_key_of_each_blocked_orders_reason(tmp_path: Path) -> None:
    cli = ran_to(tmp_path, date(2021, 6, 30))
    with opened(cli) as store:
        cut, skipped = store.report(trading_days()[1]), store.report(date(2021, 6, 29))
    assert cut is not None
    assert skipped is not None
    assert FILL_CASH_CUT in day_report_page(cut, None).keys
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
        "Received: IDR 210,020 a month, 21.00% of the goal\n"
        "Run-rate: IDR 212,668 a month, 21.27% of the goal\n"
        "\n"
        f"{PROJECTION_LABEL}:\n"
        "Reaching IDR 1,000,000 a month, adding IDR 0 a month\n"
        "- pessimistic: from IDR 2,268,461 a year, growing 0.00% a year: not within 50 years\n"
        "- base: from IDR 2,835,577 a year, growing 5.00% a year: the goal in 17.7 years\n"
        "- optimistic: from IDR 2,835,577 a year, growing 6.69% a year: the goal in 15.0 years\n"
    ) in result.out


def test_the_day_a_limit_halts_the_account_shows_the_halt(tmp_path: Path) -> None:
    result = halted(tmp_path)("report")
    assert result.code == 0
    assert (
        "\n\nHalted on 2021-02-02: daily loss limit: the unit value fell 2.38%, the limit is "
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
        "The paper account halted on 2021-02-02: daily loss limit: the unit value fell 2.38%, "
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
            "fell 2.38%, the limit is 0.10%), by tester"
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
        "steadyhand-idx: the unit value is still 9.37% below its high-water mark, at or past "
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
        "value fell 2.38%, the limit is 0.10%; no orders are placed until you resume it with: "
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

**`tests/cli/test_paper_run.py`** (changed: 5 edits)

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta, timezone
from functools import cache
from pathlib import Path

import pytest
from cli_world import GOLDEN_CONFIG, Cli, Result, market_cli, paper_process, recorded_source
from record_golden import END, START
```
with:
```python
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from cli_world import (
    GOLDEN_CONFIG,
    at,
    golden_backtest,
    opened,
    paper,
    paper_process,
    recorded_source,
    rules,
    run_on,
    tables,
    trading_days,
)
from record_golden import END, START
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    RISK_HALT_DAILY_LOSS,
    BacktestResult,
    Bar,
    BuyAndHold,
    CorporateAction,
```
with:
```python
    RISK_HALT_DAILY_LOSS,
    Bar,
    CorporateAction,
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    Market,
    backtest,
    day_inputs,
```
with:
```python
    Market,
    day_inputs,
```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
from steadyhand_idx.paper import CATCH_UP_CAP, CLOSE, days_to_run, settings_of, target_day
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.state import STATE_FILE, Account, Outcome, StateStore
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe

WIB = timezone(timedelta(hours=7))


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


@cache
def trading_days() -> tuple[date, ...]:
    """The golden window's trading days, from the IDX calendar."""
    return days_to_run(START - timedelta(days=1), END, rules())


def at(day: date, hour: int = 17, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=WIB)


def paper(tmp_path: Path, config: str = GOLDEN_CONFIG) -> Cli:
    return market_cli(tmp_path / "home", config)


def run_on(cli: Cli, day: date, *extra: str) -> Result:
    return replace(cli, now=at(day))("paper", "run", *extra)


@contextmanager
def opened(cli: Cli) -> Iterator[StateStore]:
    with StateStore(cli.home / STATE_FILE) as store:
        yield store


def tables(cli: Cli) -> dict[str, list[tuple[object, ...]]]:
    """Every row of the account, the day reports and the audit log, as SQLite holds them."""
    database = sqlite3.connect(cli.home / STATE_FILE)
    try:
        return {
            table: database.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608
            for table in ("account", "day_reports", "audit")
        }
    finally:
        database.close()


def golden_backtest(cli: Cli, end: date) -> BacktestResult:
    """``buy-and-hold`` from the golden window's first day to *end*, as ``backtest`` runs it over
    the same configuration, universe files and recorded data. Without the income goal: its
    report reads five years before *end* (M4 spec §8), which the recordings do not cover for an
    early *end*, and it changes neither the states nor the day reports."""
    config = load(cli.config)
    universe = Lq45Universe(
        Lq45Membership.load(config.lq45_members), Exclusions.load(config.exclusions)
    )
    with recorded_source(cli.home) as source:
        market = Market(universe, source, IdxMarketRules(broker_fees=config.broker_fees))
        return backtest(BuyAndHold(), market, START, end, replace(config.settings, goal=None))


```
with:
```python
from steadyhand_idx.paper import CATCH_UP_CAP, CLOSE, days_to_run, settings_of, target_day
from steadyhand_idx.state import STATE_FILE, Account, Outcome
from steadyhand_idx.universe import Exclusions, Lq45Membership, Lq45Universe

```

<!-- edit: tests/cli/test_paper_run.py -->
Replace:
```python
    }
    no_goal = replace(config, settings=replace(config.settings, goal=None))
    assert settings_of(no_goal)["goal.monthly_income_target_idr"] == "0"

```
with:
```python
    }

```

**`tests/perf/synthetic.py`** (new)

<!-- file: tests/perf/synthetic.py -->
```python
"""A synthetic market for the performance tests: ten years of prices and dividends for 45
stocks, generated from a fixed seed with integer arithmetic only, under ``PlainRules``, a small
market that is not IDX. Ten years of real fixtures would bloat the repository, and IDX's rule
data does not reach ten years ahead. ``EqualWeight`` rebalances every day, so it trades,
values and sizes every day."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Currency,
    Decision,
    Instrument,
    MarketView,
    Memory,
    Money,
    Note,
    PortfolioView,
    Rounding,
    Side,
    UnsupportedDateError,
)

SEED = 20260926
STOCKS = 45
START, END = date(2016, 1, 4), date(2025, 12, 31)


class PlainRules:
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

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return gross.times(Decimal("0.1"), Rounding.UP)

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        return None

    def protection_end(self, purchase_day: date) -> date:
        return purchase_day

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5


class Lcg:
    """A 64-bit linear congruential generator (Knuth's MMIX constants): integers only, and the
    same sequence on every Python version, which ``random`` does not promise."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def randint(self, low: int, high: int) -> int:
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) % 2**64
        return low + (self._state >> 33) % (high - low + 1)


class Synthetic:
    """Ten years of daily bars and a dividend each year on the first weekday from 15 June, for
    each stock, from ``SEED``. Every year pays, so the last year gives a run-rate to project."""

    def __init__(self) -> None:
        rng = Lcg(SEED)
        self.stocks = [Instrument(f"S{n:03d}", "PLAIN", IDR) for n in range(STOCKS)]
        self._bars: dict[Instrument, list[Bar]] = {}
        self._actions: dict[Instrument, list[CorporateAction]] = {}
        days = [START + timedelta(days=n) for n in range((END - START).days + 1)]
        trading = [day for day in days if day.weekday() < 5]
        for stock in self.stocks:
            close = rng.randint(1_000, 20_000)
            bars: list[Bar] = []
            actions: list[CorporateAction] = []
            paid: set[int] = set()
            for day in trading:
                opening = close * (1_000 + rng.randint(-10, 10)) // 1_000
                close = max(50, opening * (1_000 + rng.randint(-20, 21)) // 1_000)
                high, low = max(opening, close), min(opening, close)
                high_, low_ = Money(high, IDR), Money(low, IDR)
                bars.append(
                    Bar(stock, day, Money(opening, IDR), high_, low_, Money(close, IDR), 10**8)
                )
                if (day.month, day.day) >= (6, 15) and day.year not in paid:
                    paid.add(day.year)
                    actions.append(CashDividend(stock, day, Decimal(close // 50)))
            self._bars[stock] = bars
            self._actions[stock] = actions

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return [bar for bar in self._bars[instrument] if start <= bar.day <= end]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return [a for a in self._actions[instrument] if start <= a.ex_date <= end]


class All:
    """Every synthetic stock, every day, with nothing excluded and no gaps."""

    def __init__(self, stocks: Sequence[Instrument]) -> None:
        self._stocks = frozenset(stocks)

    def members_on(self, day: date) -> frozenset[Instrument]:
        return self._stocks

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return {}

    def first_day(self) -> date:
        return START

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
        return ()


class EqualWeight:
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
```

**`tests/perf/test_paper_performance.py`** (new)

<!-- file: tests/perf/test_paper_performance.py -->
```python
"""``paper run`` on a five-year account stays quick, and its saved state stays small (M5 spec
§9.3). Measured in the M5b scratch build on an idle machine: one day 0.17 s, a 30-day catch-up
1.64 s, and a state of 650,053 bytes. The time budgets leave about six times that for a slower
CI runner; the size is the same on every machine, so its budget only leaves room to grow.

The account is 45 stocks held by ``buy-and-hold`` on ``synthetic``'s market for five years. It is
built by a backtest, which a paper account run with its settings unchanged equals (M5 spec §6.2),
and saved as ``paper run`` saves an account, so the timed runs read, decode, run and write it
exactly as a day's run does.
"""

import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from synthetic import START, All, PlainRules, Synthetic

from steadyhand import BuyAndHold, Market, backtest, encode_state, to_json
from steadyhand_idx.cache import JAKARTA
from steadyhand_idx.config import Config, load
from steadyhand_idx.paper import CATCH_UP_CAP, days_to_run, run_paper, settings_of
from steadyhand_idx.state import STATE_FILE, Account, StateStore

FIVE_YEARS_END = date(2020, 12, 31)
ONE_DAY_BUDGET_SECONDS = 1.0
CATCH_UP_BUDGET_SECONDS = 10.0
SNAPSHOT_BUDGET_BYTES = 800_000

CONFIG = """[account]
starting_cash_idr = 1_000_000_000
monthly_contribution_idr = 10_000_000

[goal]
monthly_income_target_idr = 50_000_000

[consent]
disclaimer_accepted = 2026-09-27
"""


@dataclass(frozen=True, slots=True)
class FiveYears:
    """A paper account after five years, its configuration and its market."""

    config: Config
    market: Market
    snapshot_bytes: int


def five_years(home: Path) -> FiveYears:
    home.mkdir(parents=True)
    (home / "steadyhand.toml").write_text(CONFIG, encoding="utf-8")
    config = load(home / "steadyhand.toml")
    source = Synthetic()
    market = Market(All(source.stocks), source, PlainRules())
    settings = replace(config.settings, goal=None)
    run = backtest(BuyAndHold(), market, START, FIVE_YEARS_END, settings).run
    account = Account(START, config.strategy, run.final, settings_of(config))
    with StateStore(home / STATE_FILE) as store:
        assert store.save(account, after=None, report=run.reports[-1])
    return FiveYears(config, market, len(to_json(encode_state(run.final)).encode()))


def evening(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 17, tzinfo=JAKARTA)


def timed_run(account: FiveYears, day: date) -> tuple[float, int]:
    """Seconds for one ``paper run`` up to *day*, and how many days it ran."""
    with StateStore(account.config.data_dir / STATE_FILE) as store:
        began = time.perf_counter()
        done = run_paper(store, account.config, account.market, evening(day), catch_up=False)
        return time.perf_counter() - began, len(done.reports)


@pytest.fixture(scope="module")
def account(tmp_path_factory: pytest.TempPathFactory) -> FiveYears:
    return five_years(tmp_path_factory.mktemp("paper") / "home")


@pytest.mark.perf
def test_a_saved_five_year_state_is_small(account: FiveYears) -> None:
    assert account.snapshot_bytes < SNAPSHOT_BUDGET_BYTES


@pytest.mark.perf
def test_one_days_run_on_a_five_year_account_is_inside_the_budget(account: FiveYears) -> None:
    day = FIVE_YEARS_END + timedelta(days=1)
    assert day.weekday() == 4
    seconds, ran = timed_run(account, day)
    assert ran == 1
    assert seconds < ONE_DAY_BUDGET_SECONDS, f"took {seconds:.1f} s"


@pytest.mark.perf
def test_a_thirty_day_catch_up_on_a_five_year_account_is_inside_the_budget(
    account: FiveYears,
) -> None:
    rules = account.market.rules
    with StateStore(account.config.data_dir / STATE_FILE) as store:
        saved = store.account()
        assert saved is not None
    last = saved.last_day
    target = last
    while len(days_to_run(last, target, rules)) < CATCH_UP_CAP:
        target += timedelta(days=1)
    seconds, ran = timed_run(account, target)
    assert ran == CATCH_UP_CAP
    assert seconds < CATCH_UP_BUDGET_SECONDS, f"took {seconds:.1f} s"
```

**`tests/perf/test_performance.py`** (changed: 4 edits)

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python

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

```
with:
```python

The market is ``synthetic``'s, which also shows the engine running a market other than IDX.
The strategy rebalances to equal weights every day, so the strategy's run and the baseline's
both trade, value and size every day.
"""

import time
from datetime import timedelta

import pytest
from synthetic import END, START, All, EqualWeight, PlainRules, Synthetic

```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
    BacktestSettings,
    Bar,
    CashDividend,
    CorporateAction,
    Costs,
    Currency,
    Decision,
    EngineSettings,
    IncomeGoal,
    Instrument,
    Market,
    MarketView,
    Memory,
    Money,
    Note,
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

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return gross.times(Decimal("0.1"), Rounding.UP)

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        return None

    def protection_end(self, purchase_day: date) -> date:
        return purchase_day

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
    """Ten years of daily bars and a dividend each year on the first weekday from 15 June, for
    each stock, from ``SEED``. Every year pays, so the last year gives a run-rate to project."""

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
            paid: set[int] = set()
            for day in trading:
                opening = close * (1_000 + rng.randint(-10, 10)) // 1_000
                close = max(50, opening * (1_000 + rng.randint(-20, 21)) // 1_000)
                high, low = max(opening, close), min(opening, close)
                high_, low_ = Money(high, IDR), Money(low, IDR)
                bars.append(
                    Bar(stock, day, Money(opening, IDR), high_, low_, Money(close, IDR), 10**8)
                )
                if (day.month, day.day) >= (6, 15) and day.year not in paid:
                    paid.add(day.year)
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

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
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

```
with:
```python
    BacktestSettings,
    EngineSettings,
    IncomeGoal,
    Market,
    Money,
    backtest,
)

BUDGET_SECONDS = 30

```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
def test_ten_years_of_45_stocks_run_inside_the_budget() -> None:
    source = _Synthetic()
    settings = BacktestSettings(
```
with:
```python
def test_ten_years_of_45_stocks_run_inside_the_budget() -> None:
    source = Synthetic()
    settings = BacktestSettings(
```

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python
    )
    market = Market(_All(source.stocks), source, _PlainRules())
    began = time.perf_counter()
    result = backtest(_EqualWeight(), market, START, END, settings)
    seconds = time.perf_counter() - began
```
with:
```python
    )
    market = Market(All(source.stocks), source, PlainRules())
    began = time.perf_counter()
    result = backtest(EqualWeight(), market, START, END, settings)
    seconds = time.perf_counter() - began
```


- [ ] **Step 3: Write the stubs.** New names only. `_percent`, `_with_income` and `_text_table` keep their old definitions at the end of their modules in this step, since the old code still calls them; Step 5 removes them.

**`packages/steadyhand-idx/src/steadyhand_idx/cli.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    guide,
)
```
with:
```python
    guide,
    income_of,
)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
from steadyhand_idx.config import Config, ConfigMissingError, load, starter
from steadyhand_idx.output import (
```
with:
```python
from steadyhand_idx.config import Config, ConfigMissingError, load, starter
from steadyhand_idx.notes import PAPER_RESUMED, PAPER_STRATEGY_SWITCHED
from steadyhand_idx.output import (
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    CATCH_UP_CAP,
    AccountHaltedError,
    CatchUpError,
    StaleDataError,
    StrategyChangedError,
    run_paper,
)
from steadyhand_idx.paper_pages import paper_run_page
from steadyhand_idx.paths import (
```
with:
```python
    CATCH_UP_CAP,
    AccountChangedError,
    AccountHaltedError,
    CatchUpError,
    HaltCausePresentError,
    NoAccountError,
    NoReportError,
    StaleDataError,
    StrategyChangedError,
    SwitchRefusedError,
    WrongStrategyError,
    check_resume,
    check_switch,
    resume,
    run_paper,
    saved_account,
    saved_report,
    switch,
)
from steadyhand_idx.paper_pages import (
    day_report_page,
    income_page,
    paper_run_page,
    status_page,
)
from steadyhand_idx.paths import (
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    (StrategyChangedError, 2),
    (DataUnavailableError, 3),
```
with:
```python
    (StrategyChangedError, 2),
    (NoAccountError, 2),
    (NoReportError, 2),
    (WrongStrategyError, 2),
    (SwitchRefusedError, 2),
    (DataUnavailableError, 3),
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    (AccountHaltedError, 3),
)
```
with:
```python
    (AccountHaltedError, 3),
    (HaltCausePresentError, 3),
    (AccountChangedError, 3),
)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python

def _strategy(name: str) -> Strategy:
```
with:
```python

def _paper_status(ctx: Context) -> str:
    """The paper account after its last day run (M5 spec §7.1). A halted account exits 0."""
    raise NotImplementedError("_paper_status")


def _report(ctx: Context) -> str:
    """A saved day, the latest by default, or with ``--income`` the income report, which reads
    each holding's corporate actions through the data source (M5 spec §7.2)."""
    raise NotImplementedError("_report")


def _resume(ctx: Context) -> str:
    """Clear a halt once the operator types ``resume`` (M5 spec §7.3, core spec §6.1)."""
    raise NotImplementedError("_resume")


def _paper_switch(ctx: Context) -> str:
    """Move the account to the strategy the configuration names, once the operator types its
    name (M5 spec §7.3)."""
    raise NotImplementedError("_paper_switch")


def _confirm(ctx: Context, expected: str, question: str) -> None:
    """Ask *question*; anything but *expected*, or no answer, changes nothing (M5 spec §7.3)."""
    raise NotImplementedError("_confirm")


def _user(ctx: Context) -> str:
    """Who is running the command, for the audit log (core spec §6.1)."""
    raise NotImplementedError("_user")


def _strategy(name: str) -> Strategy:
```

**`packages/steadyhand-idx/src/steadyhand_idx/notes.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/notes.py -->
Replace:
```python

PAPER_RUN_STOPPED = "paper.run.stopped"
```
with:
```python

PAPER_RESUMED = "paper.resumed"
"""The operator resumed ordering after a halt, and who did it (core spec §6.1)."""

PAPER_RUN_STOPPED = "paper.run.stopped"
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/notes.py -->
Replace:
```python
"""The starting cash changed after the account opened, so the change has no effect."""
```
with:
```python
"""The starting cash changed after the account opened, so the change has no effect."""

PAPER_STRATEGY_SWITCHED = "paper.strategy.switched"
"""The operator switched the account to the configured strategy, keeping its holdings."""
```

**`packages/steadyhand-idx/src/steadyhand_idx/paper.py`** (changed, new names stubbed: 8 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python

The CLI calls ``run_paper``; the B+C scheduler will too.
"""
```
with:
```python

``resume`` clears a halt and ``switch`` moves the account to another strategy, each saved over
the account as it was read, so a day another run saves meanwhile is never overwritten.

The CLI calls these; the B+C scheduler will call ``run_paper`` too.
"""
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final
```
with:
```python
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Final
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
    STRATEGIES,
    DataUnavailableError,
```
with:
```python
    STRATEGIES,
    Cut,
    DataUnavailableError,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
    Note,
    day_inputs,
    run_day,
```
with:
```python
    Note,
    Rejected,
    RiskLimits,
    day_inputs,
    percent,
    run_day,
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
    PAPER_ORDER_SKIPPED,
    PAPER_RUN_STOPPED,
    PAPER_SETTING_CHANGED,
    PAPER_SETTING_STARTING_CASH_IGNORED,
)
```
with:
```python
    PAPER_ORDER_SKIPPED,
    PAPER_RESUMED,
    PAPER_RUN_STOPPED,
    PAPER_SETTING_CHANGED,
    PAPER_SETTING_STARTING_CASH_IGNORED,
    PAPER_STRATEGY_SWITCHED,
)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
            f"are placed until you resume it with: {APP} resume {strategy}"
        )


```
with:
```python
            f"are placed until you resume it with: {APP} resume {strategy}"
        )


class NoAccountError(ValueError):
    """No day has been run, so there is no account to show or change. M5 exits 2."""

    def __init__(self) -> None:
        raise NotImplementedError("NoAccountError.__init__")


class NoReportError(ValueError):
    """``report --day`` named a day with no saved report. M5 exits 2."""

    def __init__(self, day: date, first: date, last: date) -> None:
        raise NotImplementedError("NoReportError.__init__")


class WrongStrategyError(ValueError):
    """``resume`` named another strategy than the account runs. M5 exits 2."""

    def __init__(self, named: str, saved: str) -> None:
        raise NotImplementedError("WrongStrategyError.__init__")


class HaltCausePresentError(RuntimeError):
    """``resume`` while the unit value is still at or past the drawdown limit (core spec §6.1):
    ordering would only halt again. M5 exits 3."""

    def __init__(self, drawdown: Decimal, limit: Decimal) -> None:
        raise NotImplementedError("HaltCausePresentError.__init__")


class SwitchRefusedError(ValueError):
    """``paper switch`` named a strategy the configuration does not, or the one already
    running. M5 exits 2."""

    @classmethod
    def not_configured(cls, name: str, configured: str) -> SwitchRefusedError:
        raise NotImplementedError("SwitchRefusedError.not_configured")

    @classmethod
    def already(cls, name: str) -> SwitchRefusedError:
        raise NotImplementedError("SwitchRefusedError.already")


class AccountChangedError(RuntimeError):
    """Another ``paper run`` saved a day between reading the account and saving the change, so
    nothing was saved. M5 exits 3."""

    def __init__(self) -> None:
        raise NotImplementedError("AccountChangedError.__init__")


```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python

def _require_fresh(inputs: DayInputs, state: EngineState) -> None:
```
with:
```python

def saved_account(store: StateStore) -> Account:
    """The account, which a command that shows or changes it needs."""
    raise NotImplementedError("saved_account")


def saved_report(store: StateStore, day: date) -> DayReport:
    """The report saved for *day*, which must be one of the days run."""
    raise NotImplementedError("saved_report")


def check_resume(account: Account, named: str, limits: RiskLimits) -> Halt | None:
    """The halt ``resume`` would clear, or ``None`` when nothing is halted. *named* must be the
    account's strategy, and the drawdown must be back within *limits* (core spec §6.1)."""
    raise NotImplementedError("check_resume")


def resume(store: StateStore, account: Account, halt: Halt, day: date, user: str) -> None:
    """Clear *account*'s halt and write who resumed it, dated *day*, unless another run saved a
    day since *account* was read."""
    raise NotImplementedError("resume")


def check_switch(account: Account, name: str, configured: str) -> None:
    """Refuse a switch to anything but the configured strategy, to the one already running, or
    while the account is halted (M5 spec §7.3)."""
    raise NotImplementedError("check_switch")


def switch(store: StateStore, account: Account, name: str, day: date, user: str) -> None:
    """Move *account* to the strategy *name*, keeping its holdings and cash and clearing what
    the old strategy remembered, and write who switched it, dated *day*."""
    raise NotImplementedError("switch")


def _save_change(store: StateStore, before: Account, after: Account, line: AuditLine) -> None:
    raise NotImplementedError("_save_change")


def _require_fresh(inputs: DayInputs, state: EngineState) -> None:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
Replace:
```python
    return lines

```
with:
```python
    return lines


def cut_line(cut: Cut) -> str:
    """How a cut order is written, in the audit log and in ``report``."""
    raise NotImplementedError("cut_line")


def skipped_line(rejected: Rejected) -> str:
    """How a skipped order is written, in the audit log and in ``report``."""
    raise NotImplementedError("skipped_line")

```

**`packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
"""What the paper commands print (M5 spec §6, §7), built as ``Page``s for ``output.render``."""

from __future__ import annotations

from steadyhand import FIGURES
from steadyhand_idx.output import Page
from steadyhand_idx.paper import PaperRun
from steadyhand_idx.paths import APP

```
with:
```python
"""What the paper commands print (M5 spec §6, §7), built as ``Page``s for ``output.render``.

Every figure a page shows is added with its ``FIGURES`` key, and every note or reason with its
own key, so the training layer can explain each (T1 spec §6 item 4).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from steadyhand import (
    CLAIMS_LABEL,
    FIGURES,
    DayReport,
    DividendClaim,
    Entitlement,
    Fill,
    Halt,
    Holdings,
    IncomeReport,
    Instrument,
    Money,
    Order,
    ProjectionOutcome,
    ScenarioProjection,
)
from steadyhand_idx.output import Page
from steadyhand_idx.paper import PaperRun, cut_line, skipped_line
from steadyhand_idx.paths import APP
from steadyhand_idx.reports import show, text_table
from steadyhand_idx.state import Account

type Item = tuple[str, tuple[str, ...]]
"""One line of a list, and the keys of what it shows."""

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    page.add(f"Ran {len(done.reports)} day(s): {days}. Read a day's report with: {APP} report")
    return page
```
with:
```python
    page.add(f"Ran {len(done.reports)} day(s): {days}. Read a day's report with: {APP} report")
    return page


def status_page(account: Account, report: DayReport) -> Page:
    """The account after its last day run, *report* being that day's (M5 spec §7.1)."""
    raise NotImplementedError("status_page")


def day_report_page(report: DayReport, account: Account | None) -> Page:
    """One saved day (M5 spec §7.2). Holdings are listed when *report* is *account*'s last day:
    the account keeps only that day's positions. With no *account*, they are left out."""
    raise NotImplementedError("day_report_page")


def income_page(income: IncomeReport) -> Page:
    """The M4 income view of the account (M5 spec §7.2): received income, the run-rate, the
    payment calendar, the goal, the three projections and the open claims."""
    raise NotImplementedError("income_page")


def _halt(page: Page, halt: Halt, strategy: str) -> None:
    raise NotImplementedError("_halt")


def _cash(page: Page, report: DayReport) -> None:
    raise NotImplementedError("_cash")


def _holdings(page: Page, holdings: Holdings, value: Money) -> None:
    """Each position with its last close, its value at that close and its share of *value*."""
    raise NotImplementedError("_holdings")


def _claims(page: Page, claims: Sequence[DividendClaim]) -> None:
    """The open exemption claims, under the label that says they are an estimate (M4 §6.4)."""
    raise NotImplementedError("_claims")


def _section(page: Page, title: str, items: Sequence[Item]) -> None:
    """*title* and a line per item, or *title* and ``none``."""
    raise NotImplementedError("_section")


def _orders(orders: Iterable[Order]) -> list[Item]:
    raise NotImplementedError("_orders")


def _entitlements(entitlements: Iterable[Entitlement]) -> list[Item]:
    raise NotImplementedError("_entitlements")


def _frozen(frozen: Iterable[tuple[Instrument, str]]) -> list[Item]:
    raise NotImplementedError("_frozen")


def _fill(fill: Fill) -> Item:
    raise NotImplementedError("_fill")


def _rate(value: Decimal | None) -> str:
    """A rate as a percentage, or ``n/a`` when it has no divisor to be worked out from."""
    raise NotImplementedError("_rate")


def _scenario(scenario: ScenarioProjection) -> str:
    raise NotImplementedError("_scenario")
```

**`packages/steadyhand-idx/src/steadyhand_idx/reports.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python

def _text_table(rows: Sequence[Sequence[str]]) -> list[str]:
    """*rows* in columns: the first left-aligned, the rest right-aligned, two spaces apart."""
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(
            cell.ljust(width) if column == 0 else cell.rjust(width)
            for column, (cell, width) in enumerate(zip(row, widths, strict=True))
        ).rstrip()
        for row in rows
    ]

```
with:
```python

def text_table(rows: Sequence[Sequence[str]]) -> list[str]:
    """*rows* in columns: the first left-aligned, the rest right-aligned, two spaces apart."""
    raise NotImplementedError("text_table")

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python
    return summary, daily
```
with:
```python
    return summary, daily


def _text_table(rows: Sequence[Sequence[str]]) -> list[str]:
    """*rows* in columns: the first left-aligned, the rest right-aligned, two spaces apart."""
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(
            cell.ljust(width) if column == 0 else cell.rjust(width)
            for column, (cell, width) in enumerate(zip(row, widths, strict=True))
        ).rstrip()
        for row in rows
    ]
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    day_inputs,
)
```
with:
```python
    day_inputs,
    income_of,
)
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.risk import Checked, Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer, Sizer
```
with:
```python
)
from steadyhand.risk import Checked, Halt, RiskLimits, RiskManager, UnitValue, percent
from steadyhand.sizing import CompoundingSizer, Sizer
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "guide",
    "income_report",
    "measure",
    "payment_calendar",
    "project",
```
with:
```python
    "guide",
    "income_of",
    "income_report",
    "measure",
    "payment_calendar",
    "percent",
    "project",
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

def _with_income(
    run: RunResult, market: Market, settings: BacktestSettings, goal: IncomeGoal
) -> RunResult:
    """*run* with its income report, from each final holding's history as the source gives it.

    A source that cannot give it raises, and the backtest stops: an income report is never
    built on missing history (M4 spec §8).
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

```
with:
```python

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
    raise NotImplementedError("income_of")

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    return warnings
```
with:
```python
    return warnings


def _with_income(
    run: RunResult, market: Market, settings: BacktestSettings, goal: IncomeGoal
) -> RunResult:
    """*run* with its income report, from each final holding's history as the source gives it.

    A source that cannot give it raises, and the backtest stops: an income report is never
    built on missing history (M4 spec §8).
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
```

**`packages/steadyhand/src/steadyhand/risk.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python

def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)}%"

```
with:
```python

def percent(rate: Decimal) -> str:
    """*rate* as a percentage to two places, rounded down: how a limit and a breach of it are
    written, so a breach never reads as more than it is."""
    raise NotImplementedError("percent")

```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
                msg = f"{name} cannot be negative, got {getattr(self, name)}"
                raise ValueError(msg)

    def revalue(self, value: Money) -> UnitValue:
```
with:
```python
                msg = f"{name} cannot be negative, got {getattr(self, name)}"
                raise ValueError(msg)

    @property
    def drawdown(self) -> Decimal:
        """How far the price is below the high-water mark, as a share of it."""
        raise NotImplementedError("UnitValue.drawdown")

    def revalue(self, value: Money) -> UnitValue:
```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
        return gross + self._rules.costs(Side.BUY, gross, day).total
```
with:
```python
        return gross + self._rules.costs(Side.BUY, gross, day).total


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)}%"
```

**`packages/steadyhand/src/steadyhand/terms.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/terms.py -->
Replace:
```python
        "ScenarioProjection.years": TERM_YEARS_TO_GOAL,
        "UnitValue.high_water": TERM_HIGH_WATER,
```
with:
```python
        "ScenarioProjection.years": TERM_YEARS_TO_GOAL,
        "UnitValue.drawdown": TERM_DRAWDOWN,
        "UnitValue.high_water": TERM_HIGH_WATER,
```

**`pyproject.toml`** (changed; configuration, needed to collect the tests: 1 edit)

<!-- edit: pyproject.toml -->
Replace:
```toml
testpaths = ["tests"]
pythonpath = ["scripts", "tests/meta", "tests/cli"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra", "-m", "not live and not perf"]
markers = [
    "live: talks to Yahoo; run by the daily yahoo-shape workflow with -m live, never on a PR",
    "perf: times a ten-year backtest; CI runs it with -m perf, without coverage",
]
```
with:
```toml
testpaths = ["tests"]
pythonpath = ["scripts", "tests/meta", "tests/cli", "tests/perf"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra", "-m", "not live and not perf"]
markers = [
    "live: talks to Yahoo; run by the daily yahoo-shape workflow with -m live, never on a PR",
    "perf: times the engine, paper runs and start-up; CI runs it with -m perf, without coverage",
]
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1443 failed=55 -->
Expected: 1443 run, 55 failed. 14 are `NotImplementedError` from the stubs. The other 41 are the new tests meeting code a stub keeps: `paper status`, `paper switch`, `report` and `resume` are not commands yet, so they exit 2 with `invalid choice` (seen as wrong exit codes, wrong messages and empty pages), and the two new keys have no lesson. Some new or changed tests pass against the stubs by design: the pinned exit-code table, a constant written in the red phase (mutation M290 shows it guards the table); `test_the_skipped_order_is_in_the_audit_log_under_its_key`, since Task 3 already writes that line and this task pins it (M274); S7's settings test, which only lost its dead case; and 21 exit-code cases that were there before and only changed their parameter ids.

- [ ] **Step 5: Implement.** The lessons are part of this step.

**`packages/steadyhand-idx/src/steadyhand_idx/cli.py`** (implemented: 7 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    paper_run.set_defaults(run=_paper_run)
    return parser
```
with:
```python
    paper_run.set_defaults(run=_paper_run)
    status = paper_commands.add_parser("status", help="show the paper account as it stands")
    status.set_defaults(run=_paper_status)
    moving = paper_commands.add_parser("switch", help="move the account to the configured strategy")
    moving.add_argument("strategy", metavar="name")
    moving.set_defaults(run=_paper_switch)

    report = commands.add_parser("report", help="show a saved day of the paper account")
    which = report.add_mutually_exclusive_group()
    which.add_argument("--day", type=_day, help="the day to show, by default the latest")
    which.add_argument("--income", action="store_true", help="show the income report instead")
    report.set_defaults(run=_report)

    resuming = commands.add_parser("resume", help="resume ordering after a halt")
    resuming.add_argument("strategy")
    resuming.set_defaults(run=_resume)
    return parser
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    """The paper account after its last day run (M5 spec §7.1). A halted account exits 0."""
    raise NotImplementedError("_paper_status")

```
with:
```python
    """The paper account after its last day run (M5 spec §7.1). A halted account exits 0."""
    config = ctx.config()
    with StateStore(config.data_dir / STATE_FILE) as store:
        account = saved_account(store)
        report = saved_report(store, account.last_day)
    return render(status_page(account, report), config.training)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    each holding's corporate actions through the data source (M5 spec §7.2)."""
    raise NotImplementedError("_report")

```
with:
```python
    each holding's corporate actions through the data source (M5 spec §7.2)."""
    config = ctx.config()
    with StateStore(config.data_dir / STATE_FILE) as store:
        account = saved_account(store)
        if not ctx.args.income:
            day: date = ctx.args.day or account.last_day
            return render(day_report_page(saved_report(store, day), account), config.training)
        reports = store.reports()
    with ctx.world.source(config.data_dir) as source:
        market = _market(config, source)
        income = income_of(reports, account.state, market, config.settings, config.goal)
    return render(income_page(income), config.training)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    """Clear a halt once the operator types ``resume`` (M5 spec §7.3, core spec §6.1)."""
    raise NotImplementedError("_resume")

```
with:
```python
    """Clear a halt once the operator types ``resume`` (M5 spec §7.3, core spec §6.1)."""
    config = ctx.config()
    page = Page()
    with StateStore(config.data_dir / STATE_FILE) as store:
        account = saved_account(store)
        halt = check_resume(account, ctx.args.strategy, config.settings.engine.limits)
        if halt is None:
            page.add("The paper account is not halted; there is nothing to resume.")
            return render(page, config.training)
        ctx.say(f"The paper account halted on {halt.day.isoformat()}: {halt.cause.text}.\n")
        _confirm(ctx, "resume", "Type resume to resume ordering: ")
        resume(store, account, halt, ctx.today(), _user(ctx))
    page.add(
        "Resumed. From the next day run, the strategy's orders are placed again.", PAPER_RESUMED
    )
    return render(page, config.training)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    name (M5 spec §7.3)."""
    raise NotImplementedError("_paper_switch")

```
with:
```python
    name (M5 spec §7.3)."""
    config = ctx.config()
    name: str = ctx.args.strategy
    with StateStore(config.data_dir / STATE_FILE) as store:
        account = saved_account(store)
        check_switch(account, name, config.strategy)
        old = account.strategy
        ctx.say(
            f"The paper account runs {old}; steadyhand.toml names {name}.\n"
            f"Switching keeps the holdings and the cash and clears what {old} remembered; "
            f"{name} trades from the next day run.\n"
        )
        _confirm(ctx, name, f"Type {name} to switch: ")
        switch(store, account, name, ctx.today(), _user(ctx))
    page = Page()
    page.add(f"Switched the paper account to {name}.", PAPER_STRATEGY_SWITCHED)
    return render(page, config.training)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    """Ask *question*; anything but *expected*, or no answer, changes nothing (M5 spec §7.3)."""
    raise NotImplementedError("_confirm")

```
with:
```python
    """Ask *question*; anything but *expected*, or no answer, changes nothing (M5 spec §7.3)."""
    answer = ctx.ask(question)
    if answer != expected:
        msg = f"you typed {answer!r}, not {expected!r}; nothing was changed"
        raise UsageError(msg)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/cli.py -->
Replace:
```python
    """Who is running the command, for the audit log (core spec §6.1)."""
    raise NotImplementedError("_user")

```
with:
```python
    """Who is running the command, for the audit log (core spec §6.1)."""
    env = ctx.world.env
    return env.get("USER") or env.get("LOGNAME") or "unknown"

```

**`packages/steadyhand-idx/src/steadyhand_idx/config.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
    """``steadyhand.toml``, checked. ``settings`` carries the engine settings, the starting cash
    and the income goal; ``training`` is the ``[training]`` table, unread."""

    path: Path
    settings: BacktestSettings
    broker_fees: str
```
with:
```python
    """``steadyhand.toml``, checked. ``settings`` carries the engine settings, the starting cash
    and the income goal, which the file always has and ``goal`` holds as well;
    ``training`` is the ``[training]`` table, unread."""

    path: Path
    settings: BacktestSettings
    goal: IncomeGoal
    broker_fees: str
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
    )
    settings = BacktestSettings(
        capital=Money(get_int(account, "starting_cash_idr", where["account"], minimum=1), IDR),
        engine=engine,
        goal=IncomeGoal(
            Money(
                get_int(tables["goal"], "monthly_income_target_idr", where["goal"], minimum=1),
                IDR,
            )
        ),
    )
```
with:
```python
    )
    goal = IncomeGoal(
        Money(get_int(tables["goal"], "monthly_income_target_idr", where["goal"], minimum=1), IDR)
    )
    settings = BacktestSettings(
        capital=Money(get_int(account, "starting_cash_idr", where["account"], minimum=1), IDR),
        engine=engine,
        goal=goal,
    )
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/config.py -->
Replace:
```python
        settings=settings,
        broker_fees=_choice(
```
with:
```python
        settings=settings,
        goal=goal,
        broker_fees=_choice(
```

**`packages/steadyhand-idx/src/steadyhand_idx/paper.py`** (implemented, rewritten whole)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/paper.py -->
```python
"""Paper trading: the daily cycle behind ``paper run`` (M5 spec §6).

``run_paper`` works out the latest completed trading day, runs every trading day after the last
one saved up to it, oldest first, and saves each in its own transaction with its report and its
audit lines. Each day starts from the account as the database holds it, decoded, and its inputs
come from ``day_inputs`` over the whole range from the opening day, so an account run day by
day with its configuration unchanged ends exactly where a backtest over the same days does
(§6.2). A day that cannot be run safely stops the run with the days before it kept (§6.5).

``resume`` clears a halt and ``switch`` moves the account to another strategy, each saved over
the account as it was read, so a day another run saves meanwhile is never overwritten.

The CLI calls these; the B+C scheduler will call ``run_paper`` too.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Final

from steadyhand import (
    STRATEGIES,
    Cut,
    DataUnavailableError,
    DataValidationError,
    DayInputs,
    DayReport,
    EngineState,
    Halt,
    InvalidBarError,
    Market,
    MarketRules,
    Note,
    Rejected,
    RiskLimits,
    day_inputs,
    percent,
    run_day,
)
from steadyhand_idx.cache import JAKARTA
from steadyhand_idx.config import Config
from steadyhand_idx.notes import (
    PAPER_ACCOUNT_OPENED,
    PAPER_ORDER_CUT,
    PAPER_ORDER_QUEUED,
    PAPER_ORDER_SKIPPED,
    PAPER_RESUMED,
    PAPER_RUN_STOPPED,
    PAPER_SETTING_CHANGED,
    PAPER_SETTING_STARTING_CASH_IGNORED,
    PAPER_STRATEGY_SWITCHED,
)
from steadyhand_idx.paths import APP
from steadyhand_idx.state import Account, AuditLine, Outcome, Run, StateStore

CLOSE: Final = time(16, 30)
"""A trading day is complete at 16:30 in Jakarta: after the close, and after the post-closing
session ends at 16:15 (core spec §5)."""

CATCH_UP_CAP: Final = 30
"""The most trading days one ``paper run`` catches up without ``--catch-up`` (M5 spec §6.1)."""

STARTING_CASH: Final = "account.starting_cash_idr"

_STOPS = (DataValidationError, DataUnavailableError, InvalidBarError)
"""The engine's and the source's refusals of a day's data (core spec §5 step 1)."""


class CatchUpError(ValueError):
    """More trading days to run than ``CATCH_UP_CAP``, without ``--catch-up``. M5 exits 2."""

    def __init__(self, count: int, last: date) -> None:
        super().__init__(
            f"{count} trading days to run since {last.isoformat()}, more than {CATCH_UP_CAP}; "
            f"run {APP} paper run --catch-up to run them all"
        )


class StrategyChangedError(ValueError):
    """The configuration names another strategy than the account runs. M5 exits 2."""

    def __init__(self, configured: str, saved: str) -> None:
        super().__init__(
            f"steadyhand.toml names the strategy {configured}, but the paper account runs "
            f"{saved}; to change it, run: {APP} paper switch {configured}"
        )


class StaleDataError(RuntimeError):
    """The data source has no bar for a day to run: it has not published it yet. M5 exits 3."""

    def __init__(self, day: date) -> None:
        super().__init__(
            f"the data source has no bars for {day.isoformat()} yet, so nothing was run for "
            "it; run paper run again later"
        )


class AccountHaltedError(RuntimeError):
    """The account is halted: ``paper run`` ran its days without ordering. M5 exits 3."""

    def __init__(self, halt: Halt, strategy: str) -> None:
        super().__init__(
            f"the paper account halted on {halt.day.isoformat()}: {halt.cause.text}; no orders "
            f"are placed until you resume it with: {APP} resume {strategy}"
        )


class NoAccountError(ValueError):
    """No day has been run, so there is no account to show or change. M5 exits 2."""

    def __init__(self) -> None:
        super().__init__(f"there is no paper account yet; run {APP} paper run first")


class NoReportError(ValueError):
    """``report --day`` named a day with no saved report. M5 exits 2."""

    def __init__(self, day: date, first: date, last: date) -> None:
        super().__init__(
            f"there is no report for {day.isoformat()}; the saved days run from "
            f"{first.isoformat()} to {last.isoformat()}"
        )


class WrongStrategyError(ValueError):
    """``resume`` named another strategy than the account runs. M5 exits 2."""

    def __init__(self, named: str, saved: str) -> None:
        super().__init__(
            f"the paper account runs {saved}, not {named}; to resume it, run: {APP} resume {saved}"
        )


class HaltCausePresentError(RuntimeError):
    """``resume`` while the unit value is still at or past the drawdown limit (core spec §6.1):
    ordering would only halt again. M5 exits 3."""

    def __init__(self, drawdown: Decimal, limit: Decimal) -> None:
        super().__init__(
            f"the unit value is still {percent(drawdown)} below its high-water mark, at or past "
            f"the {percent(limit)} drawdown limit; the halt stays until it recovers or you raise "
            "risk.max_drawdown"
        )


class SwitchRefusedError(ValueError):
    """``paper switch`` named a strategy the configuration does not, or the one already
    running. M5 exits 2."""

    @classmethod
    def not_configured(cls, name: str, configured: str) -> SwitchRefusedError:
        return cls(
            f"steadyhand.toml names the strategy {configured}, not {name}; edit [strategy] name "
            f"first, then run: {APP} paper switch {name}"
        )

    @classmethod
    def already(cls, name: str) -> SwitchRefusedError:
        return cls(f"the paper account already runs {name}; there is nothing to switch")


class AccountChangedError(RuntimeError):
    """Another ``paper run`` saved a day between reading the account and saving the change, so
    nothing was saved. M5 exits 3."""

    def __init__(self) -> None:
        super().__init__(
            "another paper run saved a day while you were answering; nothing was changed, run "
            "the command again"
        )


@dataclass(frozen=True, slots=True)
class PaperRun:
    """What one ``paper run`` did: its target day, the reports of the days it ran, and the
    account's halt, if any, when it ended."""

    target: date
    reports: tuple[DayReport, ...]
    halt: Halt | None
    outcome: Outcome


def target_day(now: datetime, rules: MarketRules) -> date:
    """The latest completed trading day at *now*: today in Jakarta if it is a trading day and
    the time there is at or after ``CLOSE``, else the trading day before (M5 spec §6.1)."""
    local = now.astimezone(JAKARTA)
    day = local.date()
    if rules.is_trading_day(day) and local.time() >= CLOSE:
        return day
    day -= timedelta(days=1)
    while not rules.is_trading_day(day):
        day -= timedelta(days=1)
    return day


def days_to_run(last: date | None, target: date, rules: MarketRules) -> tuple[date, ...]:
    """Every trading day after *last* up to *target*, oldest first; the target alone before the
    first run."""
    if last is None:
        return (target,)
    days: list[date] = []
    day = last + timedelta(days=1)
    while day <= target:
        if rules.is_trading_day(day):
            days.append(day)
        day += timedelta(days=1)
    return tuple(days)


def settings_of(config: Config) -> dict[str, str]:
    """The settings a day runs with, by configuration key, as the audit log shows them."""
    engine = config.settings.engine
    contribution = engine.monthly_contribution
    return {
        STARTING_CASH: str(config.settings.capital.amount),
        "account.monthly_contribution_idr": str(0 if contribution is None else contribution.amount),
        "account.broker_fees": config.broker_fees,
        "goal.monthly_income_target_idr": str(config.goal.monthly_target.amount),
        "risk.max_weight": str(engine.limits.max_weight),
        "risk.daily_loss_limit": str(engine.limits.daily_loss),
        "risk.max_drawdown": str(engine.limits.max_drawdown),
        "risk.max_volume_participation": str(engine.fills.volume_cap),
        "dividends.pay_lag_trading_days": str(engine.pay_lag_trading_days),
        "tax.dividend_reinvestment_exemption": str(engine.dividend_reinvestment_exemption).lower(),
    }


def run_paper(
    store: StateStore, config: Config, market: Market, now: datetime, *, catch_up: bool = False
) -> PaperRun:
    """Run every trading day the account has not run, up to the latest completed one."""
    rules = market.rules
    target = target_day(now, rules)
    at = now.astimezone(UTC)
    account = store.account()
    if account is not None and account.strategy != config.strategy:
        raise StrategyChangedError(config.strategy, account.strategy)
    days = days_to_run(None if account is None else account.last_day, target, rules)
    if account is not None and len(days) > CATCH_UP_CAP and not catch_up:
        raise CatchUpError(len(days), account.last_day)
    if not days:
        halt = None if account is None else account.state.halt
        outcome = Outcome.UP_TO_DATE if halt is None else Outcome.HALTED
        store.finish(Run(at, target, (), outcome, f"already up to date for {target.isoformat()}"))
        return PaperRun(target, (), halt, outcome)
    ran: list[DayReport] = []
    day = days[0]
    try:
        opened_on = target if account is None else account.opened_on
        inputs = {found.day: found for found in day_inputs(market, opened_on, target)}
        for day in days:
            report = _run_one(store, config, inputs[day], rules)
            if report is not None:
                ran.append(report)
    except (*_STOPS, StaleDataError) as error:
        stopped = AuditLine(day, Note(PAPER_RUN_STOPPED, f"stopped on {day.isoformat()}: {error}"))
        days_ran = tuple(report.day for report in ran)
        store.finish(Run(at, target, days_ran, Outcome.STOPPED, str(error)), (stopped,))
        raise
    final = store.account()
    halt = None if final is None else final.state.halt
    if not ran:
        # Another run saved every day first (M5 spec §6.4): this one is up to date.
        outcome = Outcome.UP_TO_DATE if halt is None else Outcome.HALTED
        store.finish(Run(at, target, (), outcome, f"already up to date for {target.isoformat()}"))
        return PaperRun(target, (), halt, outcome)
    outcome = Outcome.RAN if halt is None else Outcome.HALTED
    days_ran = tuple(report.day for report in ran)
    store.finish(Run(at, target, days_ran, outcome, f"ran {len(ran)} day(s)"))
    return PaperRun(target, tuple(ran), halt, outcome)


def _run_one(
    store: StateStore, config: Config, inputs: DayInputs, rules: MarketRules
) -> DayReport | None:
    """Run and save one day, from the account as saved; ``None`` if another run saved it."""
    day = inputs.day
    account = store.account()
    if account is not None and account.last_day >= day:
        return None
    settings = settings_of(config)
    if account is None:
        capital = config.settings.capital
        state = EngineState.opening(capital, day)
        opened_on = day
        lines = [
            AuditLine(
                day,
                Note(
                    PAPER_ACCOUNT_OPENED,
                    f"opened the paper account on {day.isoformat()} with {capital} and the "
                    f"{config.strategy} strategy",
                ),
            )
        ]
    else:
        state = account.state
        opened_on = account.opened_on
        lines = _changes(account.settings, settings, day)
    _require_fresh(inputs, state)
    state, report = run_day(
        state, inputs, STRATEGIES[config.strategy](), rules, config.settings.engine
    )
    lines += _decisions(report)
    saved = store.save(
        Account(opened_on, config.strategy, state, settings),
        after=None if account is None else account.last_day,
        report=report,
        audit=lines,
    )
    return report if saved else None


def saved_account(store: StateStore) -> Account:
    """The account, which a command that shows or changes it needs."""
    account = store.account()
    if account is None:
        raise NoAccountError
    return account


def saved_report(store: StateStore, day: date) -> DayReport:
    """The report saved for *day*, which must be one of the days run."""
    report = store.report(day)
    if report is None:
        days = store.days()
        raise NoReportError(day, days[0], days[-1])
    return report


def check_resume(account: Account, named: str, limits: RiskLimits) -> Halt | None:
    """The halt ``resume`` would clear, or ``None`` when nothing is halted. *named* must be the
    account's strategy, and the drawdown must be back within *limits* (core spec §6.1)."""
    if named != account.strategy:
        raise WrongStrategyError(named, account.strategy)
    halt = account.state.halt
    if halt is None:
        return None
    units = account.state.units
    if units.drawdown >= limits.max_drawdown:
        raise HaltCausePresentError(units.drawdown, limits.max_drawdown)
    return halt


def resume(store: StateStore, account: Account, halt: Halt, day: date, user: str) -> None:
    """Clear *account*'s halt and write who resumed it, dated *day*, unless another run saved a
    day since *account* was read."""
    line = Note(
        PAPER_RESUMED,
        f"resumed ordering after the halt of {halt.day.isoformat()} ({halt.cause.text}), by {user}",
    )
    resumed = replace(account, state=replace(account.state, halt=None))
    _save_change(store, account, resumed, AuditLine(day, line))


def check_switch(account: Account, name: str, configured: str) -> None:
    """Refuse a switch to anything but the configured strategy, to the one already running, or
    while the account is halted (M5 spec §7.3)."""
    if name != configured:
        raise SwitchRefusedError.not_configured(name, configured)
    if name == account.strategy:
        raise SwitchRefusedError.already(name)
    if account.state.halt is not None:
        raise AccountHaltedError(account.state.halt, account.strategy)


def switch(store: StateStore, account: Account, name: str, day: date, user: str) -> None:
    """Move *account* to the strategy *name*, keeping its holdings and cash and clearing what
    the old strategy remembered, and write who switched it, dated *day*."""
    line = Note(
        PAPER_STRATEGY_SWITCHED,
        f"switched the strategy from {account.strategy} to {name}, keeping the holdings and the "
        f"cash, by {user}",
    )
    switched = Account(account.opened_on, name, replace(account.state, memory={}), account.settings)
    _save_change(store, account, switched, AuditLine(day, line))


def _save_change(store: StateStore, before: Account, after: Account, line: AuditLine) -> None:
    if not store.save(after, after=before.last_day, audit=(line,)):
        raise AccountChangedError


def _require_fresh(inputs: DayInputs, state: EngineState) -> None:
    """Refuse a day on which no stock the universe or the account holds has a bar: the source
    has not published it yet (M5 spec §11, "Yahoo lags the close")."""
    held = {position.instrument for position in state.holdings.portfolio.positions}
    stocks = inputs.members | held
    if stocks and all(inputs.history.on(stock, inputs.day) is None for stock in stocks):
        raise StaleDataError(inputs.day)


def _changes(before: Mapping[str, str], after: Mapping[str, str], day: date) -> list[AuditLine]:
    """An audit line for each setting that changed since the last day run (M5 spec §6.5)."""
    lines: list[AuditLine] = []
    for key in sorted(after):
        old, new = before.get(key), after[key]
        if old == new:
            continue
        if key == STARTING_CASH:
            text = (
                f"{key} changed from {old} to {new}; it is used only when the account opens, so "
                "the account's cash is unchanged"
            )
            lines.append(AuditLine(day, Note(PAPER_SETTING_STARTING_CASH_IGNORED, text)))
        else:
            text = f"{key} changed from {old} to {new}; it applies from {day.isoformat()}"
            lines.append(AuditLine(day, Note(PAPER_SETTING_CHANGED, text)))
    return lines


def cut_line(cut: Cut) -> str:
    """How a cut order is written, in the audit log and in ``report``."""
    order = cut.order
    return (
        f"cut: {order.side.value} {order.instrument.symbol} from {order.quantity} to "
        f"{cut.quantity} shares: {cut.reason.text}"
    )


def skipped_line(rejected: Rejected) -> str:
    """How a skipped order is written, in the audit log and in ``report``."""
    order = rejected.order
    return (
        f"skipped: {order.side.value} {order.quantity} {order.instrument.symbol}: "
        f"{rejected.reason.text}"
    )


def _decisions(report: DayReport) -> list[AuditLine]:
    """The day's decisions (core spec §9.7): orders queued, cut and skipped with their reasons,
    and a halt with its cause."""
    day = report.day
    lines = [
        AuditLine(
            day,
            Note(
                PAPER_ORDER_QUEUED,
                f"queued: {order.side.value} {order.quantity} {order.instrument.symbol} "
                "at the next open",
            ),
        )
        for order in report.queued
    ]
    lines += [AuditLine(day, Note(PAPER_ORDER_CUT, cut_line(cut))) for cut in report.cuts]
    lines += [
        AuditLine(day, Note(PAPER_ORDER_SKIPPED, skipped_line(rejected)))
        for rejected in report.rejected
    ]
    if report.halt is not None:
        lines.append(AuditLine(day, report.halt.cause))
    return lines
```

**`packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py`** (implemented: 7 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    """The account after its last day run, *report* being that day's (M5 spec §7.1)."""
    raise NotImplementedError("status_page")

```
with:
```python
    """The account after its last day run, *report* being that day's (M5 spec §7.1)."""
    page = Page()
    page.add(
        f"Paper account opened on {account.opened_on.isoformat()}, running {account.strategy}; "
        f"last day run {account.last_day.isoformat()}."
    )
    if account.state.halt is not None:
        _halt(page, account.state.halt, account.strategy)
    page.add()
    _cash(page, report)
    page.add()
    holdings = account.state.holdings
    _holdings(page, holdings, report.value)
    page.add()
    _section(page, "Queued for the next open", _orders(holdings.pending))
    page.add()
    _section(page, "Dividend entitlements", _entitlements(holdings.entitlements))
    page.add()
    _claims(page, holdings.claims)
    page.add()
    _section(page, "Frozen stocks", _frozen(holdings.frozen.items()))
    return page

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    the account keeps only that day's positions. With no *account*, they are left out."""
    raise NotImplementedError("day_report_page")

```
with:
```python
    the account keeps only that day's positions. With no *account*, they are left out."""
    page = Page()
    page.add(f"Day report for {report.day.isoformat()}")
    page.add()
    _section(page, "Fills", [_fill(fill) for fill in report.fills])
    page.add()
    _section(page, "Queued for the next open", _orders(report.queued))
    page.add()
    blocked = [(cut_line(cut), (cut.reason.key,)) for cut in report.cuts]
    blocked += [(skipped_line(rejected), (rejected.reason.key,)) for rejected in report.rejected]
    _section(page, "Blocked orders", blocked)
    page.add()
    _cash(page, report)
    page.add(f"Daily charges: {report.daily_cost}", FIGURES["DayReport.daily_cost"])
    page.add(f"Deposit: {report.deposit}", FIGURES["DayReport.deposit"])
    if account is not None:
        page.add()
        if account.last_day == report.day:
            _holdings(page, account.state.holdings, report.value)
        else:
            page.add(
                f"Holdings are shown for the latest day only, {account.last_day.isoformat()}: "
                f"{APP} report"
            )
    page.add()
    paid = [
        (f"{paid.instrument.symbol}: {paid.gross} before tax", (FIGURES["Entitlement.gross"],))
        for paid in report.paid
    ]
    _section(page, "Dividends paid", paid)
    _section(page, "Dividends earned", _entitlements(report.entitled))
    page.add(f"Dividend tax: {report.tax}", FIGURES["DayReport.tax"])
    if report.halt is not None:
        page.add()
        halt = report.halt
        page.add(f"Halted on {halt.day.isoformat()}: {halt.cause.text}", halt.cause.key)
    if report.frozen:
        page.add()
        _section(page, "Frozen stocks", _frozen(report.frozen))
    for title, notes in (("Warnings", report.warnings), ("Notes", report.notes)):
        if notes:
            page.add()
            _section(page, title, [(note.text, (note.key,)) for note in notes])
    return page

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    payment calendar, the goal, the three projections and the open claims."""
    raise NotImplementedError("income_page")


def _halt(page: Page, halt: Halt, strategy: str) -> None:
    raise NotImplementedError("_halt")


def _cash(page: Page, report: DayReport) -> None:
    raise NotImplementedError("_cash")

```
with:
```python
    payment calendar, the goal, the three projections and the open claims."""
    page = Page()
    received = income.received
    page.add(f"Income as of {income.as_of.isoformat()}")
    page.add()
    trailing, average = received.trailing, received.monthly_average
    page.add(
        f"Received in the last 12 months: {trailing.gross} before tax, {trailing.tax} tax, "
        f"{trailing.take_home} take-home",
        FIGURES["IncomeFigures.gross"],
        FIGURES["IncomeFigures.tax"],
        FIGURES["IncomeFigures.take_home"],
    )
    page.add(f"Monthly average: {average.take_home} take-home", FIGURES["IncomeFigures.take_home"])
    page.add(
        f"Current yield: {_rate(received.current_yield)}; yield on cost: "
        f"{_rate(received.yield_on_cost)}",
        FIGURES["ReceivedIncome.current_yield"],
        FIGURES["ReceivedIncome.yield_on_cost"],
    )
    rate = income.run_rate
    page.add(
        f"Run-rate: {rate.annual_gross} a year before tax, {rate.monthly_take_home} a month "
        "take-home",
        FIGURES["RunRate.annual_gross"],
        FIGURES["RunRate.monthly_take_home"],
    )
    page.add(
        f"Dividend growth: {show(income.growth.portfolio)} a year",
        FIGURES["DividendGrowth.portfolio"],
    )
    page.add()
    calendar = income.calendar
    page.add("Payment calendar, take-home by month paid:", FIGURES["PaymentCalendar.months"])
    for line in text_table(
        [[month, str(amount)] for month, amount in zip(MONTHS, calendar.months, strict=True)]
    ):
        page.add(line)
    page.add(
        f"Months with nothing: {calendar.empty_months}; the largest month's share of the year: "
        f"{_rate(calendar.evenness)}",
        FIGURES["PaymentCalendar.evenness"],
    )
    page.add()
    goal = income.goal
    page.add(f"Goal: {goal.target} a month", FIGURES["GoalProgress.target"])
    page.add(
        f"Received: {goal.received} a month, {show(goal.received_share)} of the goal",
        FIGURES["GoalProgress.received"],
        FIGURES["GoalProgress.received_share"],
    )
    page.add(
        f"Run-rate: {goal.run_rate} a month, {show(goal.run_rate_share)} of the goal",
        FIGURES["GoalProgress.run_rate"],
        FIGURES["GoalProgress.run_rate_share"],
    )
    page.add()
    projection = income.projection
    page.add(f"{projection.label}:")
    page.add(
        f"Reaching {projection.target} a month, adding {projection.contribution} a month",
        FIGURES["Projection.target"],
        FIGURES["Projection.contribution"],
    )
    for scenario in projection.scenarios:
        page.add(
            f"- {_scenario(scenario)}",
            FIGURES["ScenarioProjection.starting_gross"],
            FIGURES["ScenarioProjection.growth"],
            *([FIGURES["ScenarioProjection.years"]] if scenario.years is not None else []),
        )
    for note in (*income.growth.notes, *projection.notes):
        page.add(f"- {note.text}", note.key)
    page.add()
    _claims(page, income.claims)
    return page


def _halt(page: Page, halt: Halt, strategy: str) -> None:
    page.add(
        f"Halted on {halt.day.isoformat()}: {halt.cause.text}. No orders are placed until you "
        f"resume it with: {APP} resume {strategy}",
        halt.cause.key,
    )


def _cash(page: Page, report: DayReport) -> None:
    page.add(
        f"Cash: {report.settled} settled, {report.unsettled} unsettled",
        FIGURES["DayReport.settled"],
        FIGURES["DayReport.unsettled"],
    )
    page.add(f"Holdings value: {report.holdings_value}", FIGURES["DayReport.holdings_value"])
    page.add(f"Total value: {report.value}", FIGURES["DayReport.value"])

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    """Each position with its last close, its value at that close and its share of *value*."""
    raise NotImplementedError("_holdings")

```
with:
```python
    """Each position with its last close, its value at that close and its share of *value*."""
    positions = holdings.portfolio.positions
    if not positions:
        page.add("Holdings: none")
        return
    rows = [["Stock", "Quantity", "Last close", "Value", "Weight"]]
    for position in positions:
        close = holdings.last_closes[position.instrument]
        worth = close * position.quantity
        share = Decimal(worth.amount) / Decimal(value.amount)
        rows.append(
            [
                position.instrument.symbol,
                str(position.quantity),
                str(close),
                str(worth),
                show(share),
            ]
        )
    page.add("Holdings:")
    header, *lines = text_table(rows)
    page.add(header, FIGURES["Holdings.last_closes"])
    for line in lines:
        page.add(line)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    """The open exemption claims, under the label that says they are an estimate (M4 §6.4)."""
    raise NotImplementedError("_claims")

```
with:
```python
    """The open exemption claims, under the label that says they are an estimate (M4 §6.4)."""
    items = []
    for claim in claims:
        keys = [FIGURES["DividendClaim.gross"], FIGURES["DividendClaim.uncovered"]]
        line = (
            f"{claim.instrument.symbol}: {claim.gross} paid on {claim.pay_date.isoformat()}, "
            f"{claim.uncovered} still to reinvest by {claim.deadline.isoformat()}"
        )
        for protection in claim.protections:
            line += f", {protection.amount} protected until {protection.until.isoformat()}"
            keys.append(FIGURES["Protection.amount"])
        items.append((line, tuple(keys)))
    title = "Reinvestment-exemption claims"
    _section(page, f"{title} ({CLAIMS_LABEL})" if items else title, items)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    """*title* and a line per item, or *title* and ``none``."""
    raise NotImplementedError("_section")


def _orders(orders: Iterable[Order]) -> list[Item]:
    raise NotImplementedError("_orders")


def _entitlements(entitlements: Iterable[Entitlement]) -> list[Item]:
    raise NotImplementedError("_entitlements")


def _frozen(frozen: Iterable[tuple[Instrument, str]]) -> list[Item]:
    raise NotImplementedError("_frozen")


def _fill(fill: Fill) -> Item:
    raise NotImplementedError("_fill")

```
with:
```python
    """*title* and a line per item, or *title* and ``none``."""
    if not items:
        page.add(f"{title}: none")
        return
    page.add(f"{title}:")
    for line, keys in items:
        page.add(f"- {line}", *keys)


def _orders(orders: Iterable[Order]) -> list[Item]:
    return [
        (f"{order.side.value} {order.quantity} {order.instrument.symbol}", ()) for order in orders
    ]


def _entitlements(entitlements: Iterable[Entitlement]) -> list[Item]:
    return [
        (
            (
                f"{entitlement.instrument.symbol}: {entitlement.gross} before tax, ex-date "
                f"{entitlement.ex_date.isoformat()}, paid on {entitlement.pay_date.isoformat()}"
            ),
            (FIGURES["Entitlement.gross"],),
        )
        for entitlement in entitlements
    ]


def _frozen(frozen: Iterable[tuple[Instrument, str]]) -> list[Item]:
    return [
        (f"{stock.symbol}: {reason}", ())
        for stock, reason in sorted(frozen, key=lambda item: item[0].symbol)
    ]


def _fill(fill: Fill) -> Item:
    order = fill.order
    stock = order.instrument.symbol
    line = f"{order.side.value} {fill.quantity} {stock} at {fill.price}: {fill.gross}"
    return (line, (FIGURES["Fill.price"], FIGURES["Fill.gross"]))

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py -->
Replace:
```python
    """A rate as a percentage, or ``n/a`` when it has no divisor to be worked out from."""
    raise NotImplementedError("_rate")


def _scenario(scenario: ScenarioProjection) -> str:
    raise NotImplementedError("_scenario")
```
with:
```python
    """A rate as a percentage, or ``n/a`` when it has no divisor to be worked out from."""
    return "n/a" if value is None else show(value)


def _scenario(scenario: ScenarioProjection) -> str:
    start = (
        f"{scenario.scenario.value}: from {scenario.starting_gross} a year, growing "
        f"{show(scenario.growth)} a year"
    )
    if scenario.outcome is ProjectionOutcome.REACHED:
        return f"{start}: the goal in {scenario.years} years"
    return f"{start}: {scenario.outcome.value}"
```

**`packages/steadyhand-idx/src/steadyhand_idx/reports.py`** (implemented: 4 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python
    for line, figure in zip(
        _text_table([header, *_by_figure(runs)]), [None, *figures(runs)], strict=True
    ):
```
with:
```python
    for line, figure in zip(
        text_table([header, *_by_figure(runs)]), [None, *figures(runs)], strict=True
    ):
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python
    header = ["Strategy", *(figure.label for figure in shown)]
    lines = _text_table([header, *_by_run(runs, shown, show)])
    page.add(lines[0], *(figure.key for figure in shown))
```
with:
```python
    header = ["Strategy", *(figure.label for figure in shown)]
    lines = text_table([header, *_by_run(runs, shown, show)])
    page.add(lines[0], *(figure.key for figure in shown))
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python
    """*rows* in columns: the first left-aligned, the rest right-aligned, two spaces apart."""
    raise NotImplementedError("text_table")

```
with:
```python
    """*rows* in columns: the first left-aligned, the rest right-aligned, two spaces apart."""
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(
            cell.ljust(width) if column == 0 else cell.rjust(width)
            for column, (cell, width) in enumerate(zip(row, widths, strict=True))
        ).rstrip()
        for row in rows
    ]

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/reports.py -->
Replace:
```python
    return summary, daily


def _text_table(rows: Sequence[Sequence[str]]) -> list[str]:
    """*rows* in columns: the first left-aligned, the rest right-aligned, two spaces apart."""
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(
            cell.ljust(width) if column == 0 else cell.rjust(width)
            for column, (cell, width) in enumerate(zip(row, widths, strict=True))
        ).rstrip()
        for row in rows
    ]
```
with:
```python
    return summary, daily
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.halts_and_switching.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.halts_and_switching.md -->
```markdown
+++
id = "paper.halts_and_switching"
title = "Resuming after a halt, and switching strategy"
summary = "How to resume ordering after a safety limit halts the account, and how to move it to another strategy."
explains = ["paper.resumed", "paper.strategy.switched"]
module = "using-steadyhand"
position = 9
see_also = ["risk.limits", "paper.settings"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §7.3", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.1"]
+++

**Resuming.** When a safety limit halts the account, `paper run` keeps running the days (prices,
settlement and dividends carry on) but places no orders. Ordering starts again only when you
say so, with `resume` and the name of the account's strategy. It shows the halt's day and
cause and asks you to type `resume`. The audit log records that you resumed, who you are and
when.

`resume` refuses while the halt's cause is still there: if the unit value is still at or past
the drawdown limit below its high-water mark, resuming would only halt again. Wait for it to
recover, or raise `risk.max_drawdown` in `steadyhand.toml` if you have decided to accept more.

**Switching.** The account keeps the strategy it was opened with until you change it on purpose.
Edit `[strategy] name` in `steadyhand.toml`; `paper run` then refuses and prints the command to
run: `paper switch` with the new name. It asks you to type the name again. The holdings and the
cash stay as they are, and what the old strategy remembered is cleared, because it means nothing
to another one. From the next day run, the new strategy trades from the holdings it finds.
Switching is refused while the account is halted: resume first.

A switched account's record is no longer comparable with a backtest of either strategy, which is
why the switch is written in the audit log.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.status_and_reports.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.status_and_reports.md -->
```markdown
+++
id = "paper.status_and_reports"
title = "Following your paper account"
summary = "What paper status and report show, and why the income report fetches data when the others do not."
explains = []
module = "using-steadyhand"
position = 8
see_also = ["paper.daily_run", "income.goal"]
sources = ["docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §7.1", "docs/superpowers/specs/2026-09-27-m5-paper-and-cli-design.md §7.2"]
+++

Three commands read the paper account without changing it.

- **`paper status`** shows the account as it stands after the last day run: its cash, settled
  and not yet settled, each holding with its last close, value and share of the whole, the
  orders waiting for the next open, dividends you are entitled to but have not been paid yet,
  and any stock that is frozen. If the account is halted, it says so and prints the exact
  command that resumes it.
- **`report`** shows one saved day: what was bought and sold, what was queued, which orders
  were blocked and why, the cash and value that evening, and the dividends paid and earned.
  It shows the latest day unless you name one with `--day`. Holdings are listed for the latest
  day only, because the account keeps today's positions, not every day's.
- **`report --income`** shows the income view: what the account has received, the run-rate,
  the payment calendar, how far you are from your income goal, and three projections. The
  projections are estimates, never promises. This is the one report that fetches data: it
  reads five years of each holding's dividends through the data source, as a backtest does.

None of these place an order or change a saved day.
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    """*run*, with its income report when the settings set a goal."""
    return run if settings.goal is None else _with_income(run, market, settings, settings.goal)

```
with:
```python
    """*run*, with its income report when the settings set a goal."""
    if settings.goal is None:
        return run
    return replace(run, income=income_of(run.reports, run.final, market, settings, settings.goal))

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    """
    raise NotImplementedError("income_of")

```
with:
```python
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

```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    return warnings


def _with_income(
    run: RunResult, market: Market, settings: BacktestSettings, goal: IncomeGoal
) -> RunResult:
    """*run* with its income report, from each final holding's history as the source gives it.

    A source that cannot give it raises, and the backtest stops: an income report is never
    built on missing history (M4 spec §8).
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
```
with:
```python
    return warnings
```

**`packages/steadyhand/src/steadyhand/risk.py`** (implemented: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
    written, so a breach never reads as more than it is."""
    raise NotImplementedError("percent")

```
with:
```python
    written, so a breach never reads as more than it is."""
    return f"{(rate * 100).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)}%"

```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
        """How far the price is below the high-water mark, as a share of it."""
        raise NotImplementedError("UnitValue.drawdown")

```
with:
```python
        """How far the price is below the high-water mark, as a share of it."""
        return 1 - ratio_down(self.price, self.high_water)

```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
            if quantity < order.quantity:
                limit = _percent(self._limits.max_weight)
                if quantity == 0:
```
with:
```python
            if quantity < order.quantity:
                limit = percent(self._limits.max_weight)
                if quantity == 0:
```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
            if fall >= self._limits.daily_loss:
                limit = _percent(self._limits.daily_loss)
                cause = (
                    f"daily loss limit: the unit value fell {_percent(fall)}, the limit is {limit}"
                )
                return Halt(day, Note(RISK_HALT_DAILY_LOSS, cause))
        drawdown = 1 - ratio_down(after.price, after.high_water)
        if after.units > 0 and drawdown >= self._limits.max_drawdown:
            limit = _percent(self._limits.max_drawdown)
            cause = (
                f"drawdown kill switch: the unit value is {_percent(drawdown)} below its "
                f"high-water mark, the limit is {limit}"
```
with:
```python
            if fall >= self._limits.daily_loss:
                limit = percent(self._limits.daily_loss)
                cause = (
                    f"daily loss limit: the unit value fell {percent(fall)}, the limit is {limit}"
                )
                return Halt(day, Note(RISK_HALT_DAILY_LOSS, cause))
        drawdown = after.drawdown
        if after.units > 0 and drawdown >= self._limits.max_drawdown:
            limit = percent(self._limits.max_drawdown)
            cause = (
                f"drawdown kill switch: the unit value is {percent(drawdown)} below its "
                f"high-water mark, the limit is {limit}"
```

<!-- edit: packages/steadyhand/src/steadyhand/risk.py -->
Replace:
```python
        return gross + self._rules.costs(Side.BUY, gross, day).total


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)}%"
```
with:
```python
        return gross + self._rules.costs(Side.BUY, gross, day).total
```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1443 passed=1443 -->
Expected: every command exits 0; 1443 passed, 100% branch coverage; the performance step passes eight: the ten-year backtest, the four start-up budgets and the three paper budgets of **Measured performance**.

- [ ] **Step 7: Mutations.** Run M274–M295 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(cli): M5b S9 the paper commands: status, report, resume and switch`, ending in the story's issue number as `(#N)`), as **Merging a story** says. Then move #120 to Done, and write the handover.

---

## Mutation checks

Each mutation plants one realistic defect in the story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed lines are printed before the run. The predicted catchers were written before any mutation ran; "More than predicted" lists every other test that went red.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M220 | 1 | `snapshot.py` | The JSON keys are not sorted | 1323 | `test_a_small_state_saves_as_exactly_this_json`, `test_canonical_json_has_sorted_keys_and_no_whitespace` (2 failing) | none |
| M221 | 1 | `snapshot.py` | A stock-keyed map is saved in the order it was built | 1323 | `test_a_small_state_saves_as_exactly_this_json`, `test_stock_keyed_maps_save_the_same_whatever_order_they_were_built_in` (2 failing) | none |
| M222 | 1 | `snapshot.py` | A decimal loses its exponent | 1323 | `test_a_decimal_keeps_its_exponent_so_a_restored_unit_price_prints_the_same`, `test_every_report_reads_back_equal_and_writes_the_same_json_again`, `test_every_state_reads_back_equal_and_writes_the_same_json_again` (3 failing) | none |
| M223 | 1 | `snapshot.py` | A document with extra fields is read | 1323 | `test_a_state_that_cannot_be_read_is_refused_naming_what_is_wrong` (1 failing) | none |
| M224 | 1 | `snapshot.py` | A boolean is read as a whole number | 1323 | `test_a_state_that_cannot_be_read_is_refused_naming_what_is_wrong` (1 failing) | none |
| M225 | 1 | `snapshot.py` | A decimal that is not finite is read | 1323 | `test_a_state_that_cannot_be_read_is_refused_naming_what_is_wrong` (2 failing) | none |
| M226 | 1 | `snapshot.py` | A currency is read by its code alone | 1323 | `test_a_state_in_a_currency_a_snapshot_cannot_hold_is_refused_before_it_is_saved` (1 failing) | none |
| M227 | 1 | `snapshot.py` | An upgrade step is skipped | 1323 | `test_an_older_document_is_upgraded_one_version_at_a_time_oldest_first` (1 failing) | none |
| M228 | 1 | `snapshot.py` | A version one ahead is read | 1323 | `test_a_document_from_a_newer_steadyhand_is_refused` (2 failing) | none |
| M229 | 1 | `snapshot.py` | A boolean version is read | 1323 | `test_a_document_without_a_whole_number_version_is_refused` (1 failing) | none |
| M230 | 1 | `snapshot.py` | An unreadable state escapes as a bare `ValueError` | 1323 | `test_a_state_that_cannot_be_read_is_refused_naming_what_is_wrong` (6 failing) | none |
| M231 | 1 | `snapshot.py` | A report's notes are not saved | 1323 | `test_every_day_report_of_both_golden_runs_reads_back_equal`, `test_every_report_reads_back_equal_and_writes_the_same_json_again` (2 failing) | none |
| M232 | 1 | `snapshot.py` | A movement's settlement day is saved as its own day | 1323 | `test_a_restored_portfolio_behaves_as_the_one_it_was_saved_from`, `test_a_small_state_saves_as_exactly_this_json`, `test_every_state_reads_back_equal_and_writes_the_same_json_again`, `test_the_final_state_of_both_golden_runs_reads_back_equal` (4 failing) | none |
| M233 | 1 | `key_walk.py` | The note guard exempts nothing | 1323 | `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used`, `test_the_note_detector_leaves_out_only_the_reader_it_is_given`, `test_the_snapshot_reader_is_the_one_note_built_from_saved_data` (3 failing) | none |
| M234 | 1 | `snapshot.py` | The codec builds a note from saved data | 1323 | `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used`, `test_the_snapshot_reader_is_the_one_note_built_from_saved_data` (2 failing) | none |
| M235 | 1 | `snapshot.py` | A second currency can be saved | 1323 | `test_a_state_in_a_currency_a_snapshot_cannot_hold_is_refused_before_it_is_saved`, `test_a_state_that_cannot_be_read_is_refused_naming_what_is_wrong`, `test_the_currencies_a_snapshot_can_hold_are_the_rupiah_alone` (3 failing) | none |
| M236 | 1 | `snapshot.py` | The snapshot version is 2 | 1323 | `test_a_decimal_keeps_its_exponent_so_a_restored_unit_price_prints_the_same`, `test_a_document_from_a_newer_steadyhand_is_refused`, `test_a_small_state_reads_back_equal_with_its_open_movement_still_unsettled`, `test_a_small_state_saves_as_exactly_this_json`, `test_this_code_writes_version_1_and_has_no_upgrades_yet` (6 failing) | none |
| M237 | 2 | `state.py` | A save ignores the last day it started from | 1354 | `test_a_save_from_a_day_that_is_no_longer_the_last_writes_nothing` (1 failing) | none |
| M238 | 2 | `state.py` | A schema one ahead is opened | 1354 | `test_a_database_from_a_newer_steadyhand_idx_is_refused_and_left_as_it_was` (1 failing) | none |
| M239 | 2 | `state.py` | The database file keeps the umask's mode | 1354 | `test_the_database_file_is_0600_whatever_the_umask` (3 failing) | none |
| M240 | 2 | `state.py` | The audit log can be deleted from | 1354 | `test_a_new_database_reaches_the_current_schema_with_its_tables_and_triggers`, `test_the_logs_are_append_only` (2 failing) | none |
| M241 | 2 | `state.py` | A failed day is not rolled back | 1354 | `test_a_day_whose_report_cannot_be_written_leaves_everything_as_it_was` (1 failing) | none |
| M242 | 2 | `state.py` | The audit log reads newest first | 1354 | `test_a_day_whose_report_cannot_be_written_leaves_everything_as_it_was`, `test_a_save_from_a_day_that_is_no_longer_the_last_writes_nothing`, `test_a_save_without_a_report_changes_only_the_account_and_the_audit_log`, `test_each_later_day_is_saved_after_the_one_before_in_order` (4 failing) | none |
| M243 | 2 | `state.py` | An account's settings can be changed in place | 1354 | `test_an_accounts_settings_cannot_be_changed_in_place` (1 failing) | none |
| M244 | 2 | `state.py` | A run time in another zone is accepted | 1354 | `test_a_runs_time_is_in_utc` (1 failing) | none |
| M245 | 2 | `state.py` | Valid saved settings are refused | 1354 | `test_a_day_whose_report_cannot_be_written_leaves_everything_as_it_was`, `test_a_save_from_a_day_that_is_no_longer_the_last_writes_nothing`, `test_a_save_without_a_report_changes_only_the_account_and_the_audit_log`, `test_each_later_day_is_saved_after_the_one_before_in_order`, `test_saved_rows_that_cannot_be_read_are_refused`, `test_the_first_day_is_saved_with_its_report_and_its_audit_lines` (6 failing) | none |
| M246 | 2 | `state.py` | The busy timeout is 5 seconds | 1354 | `test_a_second_run_waits_up_to_the_busy_timeout` (1 failing) | none |
| M247 | 3 | `paper.py` | A day completes at 16:29 | 1390 | `test_the_target_is_the_latest_completed_trading_day` (8 failing) | none |
| M248 | 3 | `paper.py` | A day completes only after 16:30 | 1390 | `test_the_target_is_the_latest_completed_trading_day` (2 failing) | none |
| M249 | 3 | `paper.py` | The time is read in its own zone, not Jakarta's | 1390 | `test_the_target_is_the_latest_completed_trading_day` (1 failing) | none |
| M250 | 3 | `paper.py` | The catch-up cap is 31 days | 1390 | `test_thirty_one_days_to_run_are_refused_and_nothing_is_written` (1 failing) | none |
| M251 | 3 | `paper.py` | 30 days to run are refused | 1390 | `test_thirty_days_to_run_proceed` (1 failing) | none |
| M252 | 3 | `paper.py` | A changed strategy runs | 1390 | `test_a_changed_strategy_is_refused_naming_both_and_the_switch_command` (1 failing) | none |
| M253 | 3 | `paper.py` | A day with no bars runs | 1390 | `test_a_day_the_source_has_not_published_stops_the_run` (1 failing) | none |
| M254 | 3 | `paper.py` | A stop is not recorded | 1390 | `test_a_day_the_source_has_not_published_stops_the_run`, `test_an_impossible_price_stops_the_run_keeping_the_days_before_it` (2 failing) | none |
| M255 | 3 | `paper.py` | Inputs are fetched from the first day to run, not the opening day | 1390 | `test_a_changed_starting_cash_is_noted_once_and_changes_nothing`, `test_a_halt_is_saved_with_its_day_and_every_later_run_exits_3`, `test_a_paper_account_run_day_by_day_ends_where_the_backtest_does`, `test_a_year_caught_up_in_one_run_ends_where_the_backtest_does`, `test_missed_days_are_caught_up_in_order_each_saved` (5 failing) | none |
| M256 | 3 | `paper.py` | A changed starting cash is logged as applying | 1390 | `test_a_changed_starting_cash_is_noted_once_and_changes_nothing` (1 failing) | none |
| M257 | 3 | `paper.py` | An account's saved settings are never updated | 1390 | `test_a_changed_setting_is_written_in_the_audit_log_and_applies_from_the_next_day`, `test_a_changed_starting_cash_is_noted_once_and_changes_nothing` (2 failing) | none |
| M258 | 3 | `paper.py` | A halt's audit line is not written | 1390 | `test_a_halt_is_saved_with_its_day_and_every_later_run_exits_3` (1 failing) | none |
| M259 | 3 | `paper.py` | A day another run saved is run again | 1390 | `test_days_another_run_saves_meanwhile_are_left_to_it`, `test_two_runs_started_together_run_each_day_exactly_once` (2 failing) | none |
| M260 | 3 | `cli.py` | A halted run prints nothing before its error | 1390 | `test_a_halt_is_saved_with_its_day_and_every_later_run_exits_3` (1 failing) | none |
| M261 | 3 | `risk.py` | A drawdown halt carries the daily-loss key | 1390 | `test_a_drawdown_at_the_kill_switch_halts`, `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used` (2 failing) | none |
| M262 | 3 | `reports.py` | The backtest page drops a halt's key | 1390 | `test_a_halt_is_reported_on_screen_and_in_the_file` (1 failing) | none |
| M263 | 3 | `risk.limits.md` | The halt keys have no lesson | 1390 | `test_every_key_has_a_lesson` (1 failing) | none |
| M264 | 2 | `state.py` | The run outcome's text changes | 1354 | `test_each_run_is_recorded_in_order_with_its_audit_lines`, `test_the_outcomes_are_the_four_the_database_accepts` (2 failing) | none |
| M265 | 3 | `cli.py` | A stale day exits 1 | 1390 | `test_a_day_the_source_has_not_published_stops_the_run`, `test_each_error_maps_to_its_exit_code`, `test_the_exit_code_table_is_pinned_row_by_row` (3 failing) | none |
| M266 | 4 | `view.py` | A stock not held is reported as outside the universe | 1389 | `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used`, `test_tradable_says_why_a_stock_cannot_be_traded` (2 failing) | none |
| M267 | 4 | `engine.py` | A refused stock is reported as having no bar | 1389 | `test_a_refused_stock_is_neither_bought_nor_sold`, `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used` (2 failing) | none |
| M268 | 4 | `risk.py` | A buy at the weight limit is keyed as a cut | 1389 | `test_a_buy_for_a_stock_already_at_the_limit_is_dropped`, `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used` (2 failing) | none |
| M269 | 4 | `simulated.py` | A volume too small is keyed as a volume cut | 1389 | `test_an_order_is_rejected_when_a_tenth_of_the_volume_is_under_a_lot`, `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used` (2 failing) | none |
| M270 | 4 | `corporate.py` | A split's cancelled order is keyed as a dropped fraction | 1389 | `test_a_split_cancels_pending_orders_and_rescales_the_last_close`, `test_a_split_scales_the_holding_and_the_last_close_and_cancels_its_orders`, `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used` (3 failing) | none |
| M271 | 4 | `snapshot.py` | A rejection's reason is saved as bare text | 1389 | `test_a_year_caught_up_in_one_run_ends_where_the_backtest_does`, `test_every_day_report_of_both_golden_runs_reads_back_equal`, `test_every_report_reads_back_equal_and_writes_the_same_json_again` (3 failing) | none |
| M272 | 4 | `outcomes.py` | A cut's reason is not checked to be a note | 1389 | `test_every_reason_is_a_note_under_a_key`, `test_outcomes_check_their_types` (2 failing) | none |
| M273 | 4 | `orders.at_the_open.md` | The fill keys have no lesson | 1389 | `test_every_key_has_a_lesson` (1 failing) | none |
| M274 | 5 | `paper.py` | A skipped order's line prints the note, not its text | 1443 | `test_a_blocked_order_is_shown_with_its_reason_and_the_dividends_of_the_day`, `test_the_skipped_order_is_in_the_audit_log_under_its_key` (2 failing) | none |
| M275 | 5 | `paper.py` | A cut order's line prints the note, not its text | 1443 | `test_a_days_report_shows_its_fills_its_cuts_and_its_cash`, `test_missed_days_are_caught_up_in_order_each_saved` (2 failing) | none |
| M276 | 5 | `paper.py` | `resume` is allowed at the drawdown limit | 1443 | `test_resume_is_refused_at_or_past_the_drawdown_limit` (1 failing) | none |
| M277 | 5 | `paper.py` | `resume` accepts any strategy name | 1443 | `test_resume_must_name_the_accounts_strategy` (1 failing) | none |
| M278 | 5 | `paper.py` | `resume` leaves the halt in place | 1443 | `test_a_paper_traders_journey`, `test_a_typed_resume_clears_the_halt_and_the_next_day_orders_again`, `test_resume_is_refused_while_the_drawdown_is_still_past_its_limit` (3 failing) | none |
| M279 | 5 | `paper.py` | A change saved over another run's day is not refused | 1443 | `test_an_account_changed_while_asking_is_left_as_the_other_run_saved_it` (1 failing) | none |
| M280 | 5 | `paper.py` | `paper switch` runs while halted | 1443 | `test_switch_is_refused_while_the_account_is_halted` (1 failing) | none |
| M281 | 5 | `paper.py` | `paper switch` keeps the old memory | 1443 | `test_a_typed_switch_keeps_the_holdings_and_cash_and_clears_the_memory` (1 failing) | none |
| M282 | 5 | `paper.py` | `paper switch` to the running strategy is accepted | 1443 | `test_switch_to_the_strategy_already_running_is_refused` (1 failing) | none |
| M283 | 5 | `cli.py` | An answer with spaces around it is accepted | 1443 | `test_any_other_answer_leaves_the_halt_in_place` (1 failing) | none |
| M284 | 5 | `cli.py` | `LOGNAME` wins over `USER` | 1443 | `test_resume_names_who_resumed_from_logname_or_else_unknown` (1 failing) | none |
| M285 | 5 | `paper_pages.py` | Weights are shares of the holdings value, not the total | 1443 | `test_status_shows_each_holding_with_its_last_close_value_and_weight` (1 failing) | none |
| M286 | 5 | `paper_pages.py` | Holdings are shown on every day but the latest | 1443 | `test_a_days_report_shows_its_fills_its_cuts_and_its_cash`, `test_report_shows_the_latest_day_by_default_with_its_holdings` (2 failing) | none |
| M287 | 5 | `cli.py` | `report` shows the opening day by default | 1443 | `test_report_shows_the_latest_day_by_default_with_its_holdings`, `test_the_day_a_limit_halts_the_account_shows_the_halt` (2 failing) | none |
| M288 | 5 | `paper.py` | An unsaved day names the saved days backwards | 1443 | `test_a_day_with_no_saved_report_names_the_first_and_last_saved` (3 failing) | none |
| M289 | 5 | `paper_pages.py` | The received line shows the run-rate share | 1443 | `test_the_income_report_is_the_backtests_over_the_same_days` (1 failing) | none |
| M290 | 5 | `cli.py` | A changed account exits 1 | 1443 | `test_an_account_changed_while_asking_is_left_as_the_other_run_saved_it`, `test_each_error_maps_to_its_exit_code`, `test_the_exit_code_table_is_pinned_row_by_row` (3 failing) | none |
| M291 | 5 | `paper.halts_and_switching.md` | The resume and switch keys have no lesson | 1443 | `test_a_paper_traders_journey`, `test_a_typed_resume_clears_the_halt_and_the_next_day_orders_again`, `test_a_typed_switch_keeps_the_holdings_and_cash_and_clears_the_memory`, `test_every_key_has_a_lesson`, `test_resume_is_refused_while_the_drawdown_is_still_past_its_limit`, `test_resume_names_who_resumed_from_logname_or_else_unknown` (6 failing) | none |
| M292 | 5 | `paper_pages.py` | `paper status` hides the halt | 1443 | `test_a_halted_account_shows_its_halt_and_the_resume_command_and_exits_0` (1 failing) | none |
| M293 | 5 | `paper_pages.py` | A cut's reason key is not on the report page | 1443 | `test_a_report_names_the_key_of_each_blocked_orders_reason` (1 failing) | none |
| M294 | 5 | `paper_pages.py` | The claims are shown without their label | 1443 | `test_status_shows_open_claims_under_their_label` (1 failing) | none |
| M295 | 5 | `paper_pages.py` | A protected part's key is not on the page | 1443 | `test_a_claims_reinvested_parts_are_shown_with_how_long_each_is_protected` (1 failing) | none |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M220',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)\n',
  '    return json.dumps(document, separators=(",", ":"), allow_nan=False)\n'),
 ('M221',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    ordered = sorted(mapping.items(), key=lambda item: (item[0].market, item[0].symbol))\n',
  '    ordered = list(mapping.items())\n'),
 ('M222',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    return number\n',
  '    return number.normalize()\n'),
 ('M223',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    if set(document) != set(names):\n',
  '    if not set(names) <= set(document):\n'),
 ('M224',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    if type(value) is not int:\n',
  '    if not isinstance(value, int):\n'),
 ('M225',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    if not number.is_finite():\n'
  '        msg = f"expected a finite number, got {text!r}"\n'
  '        raise ValueError(msg)\n',
  ''),
 ('M226',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    if SNAPSHOT_CURRENCIES.get(currency.code) != currency:\n',
  '    if currency.code not in SNAPSHOT_CURRENCIES:\n'),
 ('M227',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '        upgraded = {**steps[version](upgraded), "version": version + 1}\n',
  '        upgraded = {**upgraded, "version": version + 1}\n'),
 ('M228',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    if version > newest:\n',
  '    if version > newest + 1:\n'),
 ('M229',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  ' or type(version) is not int or ',
  ' or not isinstance(version, int) or '),
 ('M230',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '        return _read_state(current)\n    except _UNREADABLE as error:\n',
  '        return _read_state(current)\n    except ValueError as error:\n'),
 ('M231',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '        "notes": [_note(note) for note in report.notes],\n',
  '        "notes": [],\n'),
 ('M232',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '                "settles_on": m.settles_on.isoformat(),\n',
  '                "settles_on": m.day.isoformat(),\n'),
 ('M233',
  1,
  'tests/meta/key_walk.py',
  '        if not isinstance(node, ast.Call) or _called(node.func) != "Note" or id(node) in '
  'skipped:\n',
  '        if not isinstance(node, ast.Call) or _called(node.func) != "Note":\n'),
 ('M234',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '    return {"key": note.key, "text": note.text}\n',
  '    return {"key": Note(str(note.key), note.text).key, "text": note.text}\n'),
 ('M235',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  'SNAPSHOT_CURRENCIES: Final[Mapping[str, Currency]] = {IDR.code: IDR}\n',
  'SNAPSHOT_CURRENCIES: Final[Mapping[str, Currency]] = {IDR.code: IDR, "USD": Currency("USD", '
  '2)}\n'),
 ('M236',
  1,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  'SNAPSHOT_VERSION: Final = 1\n',
  'SNAPSHOT_VERSION: Final = 2\n'),
 ('M237',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '            if self._last_day() != after:\n',
  '            if False:\n'),
 ('M238',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '            if version > len(MIGRATIONS):\n',
  '            if version > len(MIGRATIONS) + 1:\n'),
 ('M239',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '            private_file(path), timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None\n',
  '            path, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None\n'),
 ('M240',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '    CREATE TRIGGER audit_is_never_removed BEFORE DELETE ON audit\n'
  "        BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;\n",
  ''),
 ('M241',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '        except BaseException:\n            self._db.execute("ROLLBACK")\n            raise\n',
  '        except BaseException:\n            raise\n'),
 ('M242',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '"SELECT day, key, line FROM audit ORDER BY id"',
  '"SELECT day, key, line FROM audit ORDER BY id DESC"'),
 ('M243',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))\n',
  '        object.__setattr__(self, "settings", dict(self.settings))\n'),
 ('M244',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '        if self.at.tzinfo is not UTC:\n',
  '        if self.at.tzinfo is None:\n'),
 ('M245',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '    if not isinstance(settings, dict) or not all(\n',
  '    if not isinstance(settings, dict) or all(\n'),
 ('M246',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  'BUSY_TIMEOUT_SECONDS: Final = 30.0\n',
  'BUSY_TIMEOUT_SECONDS: Final = 5.0\n'),
 ('M247',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  'CLOSE: Final = time(16, 30)\n',
  'CLOSE: Final = time(16, 29)\n'),
 ('M248',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if rules.is_trading_day(day) and local.time() >= CLOSE:\n',
  '    if rules.is_trading_day(day) and local.time() > CLOSE:\n'),
 ('M249',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    local = now.astimezone(JAKARTA)\n',
  '    local = now\n'),
 ('M250',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  'CATCH_UP_CAP: Final = 30\n',
  'CATCH_UP_CAP: Final = 31\n'),
 ('M251',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if account is not None and len(days) > CATCH_UP_CAP and not catch_up:\n',
  '    if account is not None and len(days) >= CATCH_UP_CAP and not catch_up:\n'),
 ('M252',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if account is not None and account.strategy != config.strategy:\n',
  '    if False:\n'),
 ('M253',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if stocks and all(inputs.history.on(stock, inputs.day) is None for stock in stocks):\n',
  '    if False:\n'),
 ('M254',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        store.finish(Run(at, target, days_ran, Outcome.STOPPED, str(error)), (stopped,))\n',
  ''),
 ('M255',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        inputs = {found.day: found for found in day_inputs(market, opened_on, target)}\n',
  '        inputs = {found.day: found for found in day_inputs(market, days[0], target)}\n'),
 ('M256',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        if key == STARTING_CASH:\n',
  '        if False:\n'),
 ('M257',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        Account(opened_on, config.strategy, state, settings),\n',
  '        Account(opened_on, config.strategy, state, settings if account is None else '
  'account.settings),\n'),
 ('M258',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if report.halt is not None:\n        lines.append(AuditLine(day, report.halt.cause))\n',
  ''),
 ('M259',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if account is not None and account.last_day >= day:\n        return None\n',
  ''),
 ('M260',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '    if done.halt is not None:\n        ctx.say(text)\n',
  '    if False:\n        ctx.say(text)\n'),
 ('M261',
  3,
  'packages/steadyhand/src/steadyhand/risk.py',
  '            return Halt(day, Note(RISK_HALT_DRAWDOWN, cause))\n',
  '            return Halt(day, Note(RISK_HALT_DAILY_LOSS, cause))\n'),
 ('M262',
  3,
  'packages/steadyhand-idx/src/steadyhand_idx/reports.py',
  '        page.add(halt, key)\n',
  '        page.add(halt)\n'),
 ('M263',
  3,
  'packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md',
  'explains = ["risk.halt.daily_loss", "risk.halt.drawdown"]\n',
  'explains = []\n'),
 ('M264',
  2,
  'packages/steadyhand-idx/src/steadyhand_idx/state.py',
  '    UP_TO_DATE = "up to date"\n',
  '    UP_TO_DATE = "up-to-date"\n'),
 ('M265', 3, 'packages/steadyhand-idx/src/steadyhand_idx/cli.py', '    (StaleDataError, 3),\n', ''),
 ('M266',
  4,
  'packages/steadyhand/src/steadyhand/view.py',
  '        return Note(TRADE_NOT_HELD, "not held")\n',
  '        return Note(TRADE_NOT_IN_UNIVERSE, "not held")\n'),
 ('M267',
  4,
  'packages/steadyhand/src/steadyhand/engine.py',
  '        reasons[instrument] = Note(TRADE_REFUSED, f"the data source refused '
  '{day.isoformat()}")\n',
  '        reasons[instrument] = Note(TRADE_NO_BAR, f"the data source refused '
  '{day.isoformat()}")\n'),
 ('M268',
  4,
  'packages/steadyhand/src/steadyhand/risk.py',
  '                    full = Note(LIMIT_WEIGHT_FULL, f"already at the {limit} limit per stock")\n',
  '                    full = Note(LIMIT_WEIGHT_CUT, f"already at the {limit} limit per stock")\n'),
 ('M269',
  4,
  'packages/steadyhand/src/steadyhand/broker/simulated.py',
  '                FILL_VOLUME_TOO_SMALL,\n',
  '                FILL_VOLUME_CUT,\n'),
 ('M270',
  4,
  'packages/steadyhand/src/steadyhand/corporate.py',
  '                Rejected(order, Note(CORPORATE_SPLIT_ORDER_CANCELLED, "split on ex-date"))\n',
  '                Rejected(order, Note(CORPORATE_SPLIT_FRACTION_DROPPED, "split on ex-date"))\n'),
 ('M271',
  4,
  'packages/steadyhand/src/steadyhand/snapshot.py',
  '            {"order": _order(r.order), "reason": _note(r.reason)} for r in report.rejected\n',
  '            {"order": _order(r.order), "reason": r.reason.text} for r in report.rejected\n'),
 ('M272',
  4,
  'packages/steadyhand/src/steadyhand/outcomes.py',
  '        require_type(self.order, Order, "order")\n'
  '        require_type(self.reason, Note, "reason")\n',
  '        require_type(self.order, Order, "order")\n'),
 ('M273',
  4,
  'packages/steadyhand/src/steadyhand/training/lessons/en/orders.at_the_open.md',
  'explains = ["fill.frozen", "fill.no_bar", "fill.no_trades", "fill.no_reference", '
  '"fill.outside_band", "fill.volume.too_small", "fill.volume.cut", "fill.cash.short", '
  '"fill.cash.cut", "fill.charges_unpaid"]\n',
  'explains = []\n'),
 ('M274',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        f"{rejected.reason.text}"\n',
  '        f"{rejected.reason}"\n'),
 ('M275',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        f"{cut.quantity} shares: {cut.reason.text}"\n',
  '        f"{cut.quantity} shares: {cut.reason}"\n'),
 ('M276',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if units.drawdown >= limits.max_drawdown:\n',
  '    if units.drawdown > limits.max_drawdown:\n'),
 ('M277',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if named != account.strategy:\n        raise WrongStrategyError(named, account.strategy)\n',
  ''),
 ('M278',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    resumed = replace(account, state=replace(account.state, halt=None))\n',
  '    resumed = replace(account, state=account.state)\n'),
 ('M279',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if not store.save(after, after=before.last_day, audit=(line,)):\n'
  '        raise AccountChangedError\n',
  '    store.save(after, after=before.last_day, audit=(line,))\n'),
 ('M280',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if account.state.halt is not None:\n'
  '        raise AccountHaltedError(account.state.halt, account.strategy)\n',
  ''),
 ('M281',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  'replace(account.state, memory={})',
  'account.state'),
 ('M282',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '    if name == account.strategy:\n        raise SwitchRefusedError.already(name)\n',
  ''),
 ('M283',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '    if answer != expected:\n',
  '    if answer.strip() != expected:\n'),
 ('M284',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '    return env.get("USER") or env.get("LOGNAME") or "unknown"\n',
  '    return env.get("LOGNAME") or env.get("USER") or "unknown"\n'),
 ('M285',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py',
  '    _holdings(page, holdings, report.value)\n',
  '    _holdings(page, holdings, report.holdings_value)\n'),
 ('M286',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py',
  '        if account.last_day == report.day:\n',
  '        if account.last_day != report.day:\n'),
 ('M287',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '            day: date = ctx.args.day or account.last_day\n',
  '            day: date = ctx.args.day or account.opened_on\n'),
 ('M288',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper.py',
  '        raise NoReportError(day, days[0], days[-1])\n',
  '        raise NoReportError(day, days[-1], days[0])\n'),
 ('M289',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py',
  '        f"Received: {goal.received} a month, {show(goal.received_share)} of the goal",\n',
  '        f"Received: {goal.received} a month, {show(goal.run_rate_share)} of the goal",\n'),
 ('M290',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/cli.py',
  '    (AccountChangedError, 3),\n',
  ''),
 ('M291',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/paper.halts_and_switching.md',
  'explains = ["paper.resumed", "paper.strategy.switched"]\n',
  'explains = []\n'),
 ('M292',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py',
  '    if account.state.halt is not None:\n        _halt(page',
  '    if False:\n        _halt(page'),
 ('M293',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py',
  '    blocked = [(cut_line(cut), (cut.reason.key,)) for cut in report.cuts]\n',
  '    blocked = [(cut_line(cut), ()) for cut in report.cuts]\n'),
 ('M294',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py',
  '    _section(page, f"{title} ({CLAIMS_LABEL})" if items else title, items)\n',
  '    _section(page, title, items)\n'),
 ('M295',
  5,
  'packages/steadyhand-idx/src/steadyhand_idx/paper_pages.py',
  '            keys.append(FIGURES["Protection.amount"])\n',
  '')]
```

## Carried forward

- **The B+C scheduler** calls `run_paper` as the CLI does; a refusal it cannot answer (the catch-up cap, a changed strategy) reaches it as the error `run_paper` raises (`CatchUpError`, `StrategyChangedError`), for it to report, never to resolve.
- **A short backtest can stop on income history** (M5a's Review Focus 2), and so can `report --income`: both read five years before the last day. Whether an income report should leave out a stock whose history it cannot read is still a question for its own ticket.
- **T1's module 6 is complete**, and every key M5 writes has its lesson. M5's report pages add no new report dataclass, so `test_terms.py`'s roots are unchanged (M5 §7.4); the one new figure is `UnitValue.drawdown`.
- **All twenty-three scope decisions amend or fill in the M5 spec.** The spec keeps its approved text; this plan is the record of each change.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

**Before pass 1, while building the code (2026-09-29).** Every story was built and gated first in a scratch chain on `develop` `9cd514c` (S5 `a583773`, S6 `f41d97e`, S7 `e8bab1e`, S8 `dabc803`, S9 `a33a143`), its red phase run against stubs, and its mutations run with predictions written first. That found these things a reading of the spec would not have:

1. `cache.sqlite` was created `0644` under umask 022, against M5 §4.1. It was filed as bug #132 and fixed in PR #133 (`9cd514c`) before this plan; the chain is built on the fix, and `paths.private_file` serves `state.sqlite` too.
2. M5 §6.3's `Portfolio.restore` already exists: the public constructor rebuilds the ledger once and checks it, as `__reduce__` relies on. The spec review's premise ("no public constructor") was wrong (scope decision 1).
3. An `Instrument` carries a currency, so the codec writes it, and refuses to save one it could not read back (scope decision 2). A `Decimal` keeps its exponent, or a restored unit price would print differently (scope decision 3).
4. The note-key guard refused the codec's and the store's readers of saved notes. Each is exempted by name, and a second non-constant `Note` in either module still goes red (scope decision 5, mutation M234).
5. The recorded fixture refuses a range it does not cover, which is not how Yahoo lags (it returns no bar), so the stale-day tests remove the day's bars instead. 2022-02-01 is Chinese New Year, not a trading day.
6. The golden-invariant reference backtest runs without the income goal: its income report reads five years back, past the recordings for an early end, and the goal changes neither states nor reports.
7. Keying `Tradable`'s reasons forces `Rejected.reason` and `Cut.reason` to be keyed too, so M5 §10's S8 split into S8 (every order reason) and S9 (the paper commands) (scope decision 14).
8. S9's first draft passed all 41 new tests on the first run, so each exact page was read by eye before being trusted, and the income page's goal and projection lines were pinned against the golden record (`tests/fixtures/golden/`: 210,020 = 21.00%, 212,668 = 21.27%, base case 17.7 years), not against the page's own output.
9. `report --income`'s "no goal" refusal went green the wrong way in its test: a file without `[goal]` still has the default goal. The branch was dead, as was `settings_of`'s `goal is None`; `Config.goal` became non-optional instead (scope decision 20).
10. The drawdown in `resume`'s refusal is floored, as every limit message is: 9.37%, not the 9.38% first written from rounding by eye.
11. Writing S9's predictions found two defects no test would catch: `resume` exactly at the drawdown limit, and `USER` against `LOGNAME`. Both got tests, and `check_resume`'s `units > 0` guard went as redundant.
12. The coverage gate found a claim's protected parts untested; the recorded data has them by 2021-06-30 with the exemption on (ASII's 181,600 + 175,100 = its 356,700 dividend, protected to 2023-12-31, the purchase year + 2).
13. S9 makes three private helpers public under new names. The red-phase tool kept each old caller and stubbed the new name, so the first red run failed 108 tests, many with `NameError` inside old code. The tool now keeps a removed function's old definition in the red phase (Global Constraints), and the run was repeated.
14. S9's gate once ran beside another session's browser tests (load average 38–56 on four cores): the functional suite was green, and 7 of 8 performance tests failed from starvation. The performance step was re-run on an idle machine and passed; no timing in this plan comes from a loaded run.
15. Mutation predictions corrected from the runs, each understood: M232 and M235 (S5), M245, M255 and M259 (S6, S7), and M291 (S9: a page that shows a key with no lesson cannot render, so every command printing the resume or switch line fails too).

**Pass 1 (2026-09-29).** Mechanical: `prose_check.py` (every cited test exists in some story's tree, and each task's mutation ids and the ranges its text names agree), with a negative control for each check (a range and a citation altered: both reported); `check_plan.py` replays the plan from its own text (red and gate counts, byte-identical trees); no new `noqa` or `pragma` in package code (`git diff` of the packages from the base to S9); each task's Files list against `git diff --name-status`; each interface against the code. Then the whole document read. Found five:
1. Task 5's second criterion gave frozen stocks a key; a frozen stock's reason is plain text. Reworded.
2. Review Focus 6 said "nothing is overwritten" for a newer snapshot; no test shows that, and the codec writes nothing. Removed.
3. The file map gave `tests/meta/test_terms.py` to Task 5; S9 changes `terms.py`, not that test. Corrected to Tasks 1–3.
4. Task 1 said it produces `SAVED_NOTE_READERS`; S5 defines `SAVED_NOTE_READER` (the codec's one reader), and S6 replaces it with the per-module `SAVED_NOTE_READERS`. Found by `interface_check.py` (every name a task's Produces line lists, searched as a definition in that story's tree, with a positive control); its first version matched nothing at all, since macOS `git grep -E` has no `\s` or `\b`, and the control is what now proves the search can see.
5. The replay (`check_plan.py`) rebuilt Tasks 1–3 byte-identical with their red and gate counts, and failed Task 4: rendered with `@@rewrite` (red = the new tests on the old code), its tests could not even be collected, since they import the 22 new key constants (red: 7 run, all errors), and `@@rewrite` renders Python sources only, so the four lesson files were missing (the gate then failed one test, and Task 5's 106, all on keys with no lesson). The red phase recorded for S8 was made the usual way, the constants written and every function keeping its old body, so Task 4 now has the usual stubs and implementation steps, and the Global Constraints say so.

`prose_check.py` itself was M5a's: it read only the last story's tests, so a test S6 generalised (`test_the_snapshot_reader_is_the_one_note_built_from_saved_data`) was reported missing, and its ranges were M5a's. It now reads every story's tree and checks M5b's five ranges.

**Pass 2 (2026-09-30).** Mechanical: the replay of the re-rendered plan (`replay.out`): every task's red and gate counts OK and every tree IDENTICAL to its verified commit, 0 problems; `prose_check.py` 0 problems; `interface_check.py`, whose remaining names are module paths, enum values and the `SAVED_NOTE_READER` that Task 2 replaces. Then the whole document read. Found three:
1. The file map paired `steadyhand/__init__.py` with `backtest.py` under Tasks 3 and 5; Tasks 1 and 4 change the exports too. Given its own row.
2. Task 4's stubs step said it writes the constants and their exports; its blocks also add the imports in `view`, `risk`, `engine`, `corporate` and `broker/simulated`. Said so.
3. Review Focus 2 did not say how the failing run ends: exit 1, as both failed-save tests assert. Added.

**Pass 3 (2026-09-30).** Mechanical: the re-rendered plan's 499 code blocks and 270 replay markers are identical to the replayed plan's, so the replay stands; `prose_check.py` 0 problems; `interface_check.py` unchanged. Then the whole document read, the acceptance criteria against the tests they name. Found one:
1. "Carried forward" said a refusal reaches the B+C scheduler as an exit code; the scheduler calls `run_paper`, so it gets the error `run_paper` raises. Reworded.

**Pass 4 (2026-09-30).** Mechanical: code blocks and replay markers identical to the replayed plan's; `prose_check.py` 0 problems; `interface_check.py` unchanged; the prose diff against the replayed plan holds only the fixes of passes 2 and 3 and this log. Then the whole document read. Found one:
1. Pass 1's list in this log had a blank line between its items 4 and 5, which splits it into two lists. Joined.

**Pass 5 (2026-09-30).** Mechanical: code blocks and replay markers identical to the replayed plan's; `prose_check.py` 0 problems; `interface_check.py` unchanged (its remaining names are module paths, enum values and the `SAVED_NOTE_READER` that Task 2 replaces); a sweep of the prose for repeated words, unbalanced backticks, double spaces and split numbered lists, with a planted split list as its control (reported). Then the whole document read. **Found none. The loop ends here, and the plan is approved (operator rule of 2026-09-24: plans are reviewed to zero, then self-approved).**

## Execution findings

1. **S6 (2026-09-30), PR #141:** `test (py3.13)` failed on `test_strategies_follows_the_configured_level` with 15 `ResourceWarning: unclosed database`. Task 2's `raw()` helper in `tests/cli/test_state.py` returned a `sqlite3.Connection` no test closed; Python 3.13 warns when the collector finalises one, and `-W error` fails whichever test is running then. The plan was built and gated locally on 3.12 alone, which does not warn. `raw()` now returns `closing(...)` and every caller uses `with` (Task 2's block above is the corrected file). A `with sqlite3.connect(...)` would not do: a connection's own context manager ends a transaction and leaves it open.
