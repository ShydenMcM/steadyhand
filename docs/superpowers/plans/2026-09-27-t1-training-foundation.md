# T1 Training Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every sentence and every figure a steadyhand report shows a stable key, and give every key a lesson: M3's warnings become keyed `Note`s, figures get `term.*` keys, a stdlib-only `steadyhand.training` library loads and checks the lessons and renders the inline explanation for a user's level, CI guards keep the catalogue complete and the legal line structural, and the first 33 lessons ship inside both wheels.

**Architecture:** Keys first (S1): the four warning producers build `Note`s from key constants, `terms.py` maps every figure field to a term, and two AST meta-tests derive the key and figure sets from the source rather than a list. Then the library (S2, S3): `Catalogue.load` reads lesson files (Markdown with a TOML header) and the course file and enforces every file rule; `explain` turns the keys a command showed into the text for `new`, `some`, `experienced` or `off`. Guards that need the repo (does a key exist, does a cited path exist, does "Start here" carry the disclaimer, is there advice phrasing, does anything outside training import training) live in `tests/meta/` and run first on a fixture catalogue, then (S4) on the real lessons of both packages, where they stay.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. The engine gains no dependency: `tomllib`, `difflib` and `importlib.resources` are in the standard library.

**Spec:** `docs/superpowers/specs/2026-09-27-training-design.md` (the "T1 spec"), stories S1–S4 of its §9, on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec") and `docs/superpowers/specs/2026-09-26-m4-income-design.md` (the "M4 spec"). Every code block and every lesson below was generated from a tree that passed the whole gate, not typed; the plan review log says how each claim was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2). No task adds a dependency.
- A key, note or term, matches `^[a-z]+(\.[a-z_]+)+$`, sits in a module-level constant named after its value (`TERM_RUN_RATE = "term.run_rate"`), and is never reworded (M4 §7, T1 §3). Term keys, and only term keys, start with `term.`.
- A lesson id has the same shape as a key and equals its file name without `.md`. Title 1–60 characters; summary one sentence of at most 160 characters ending in `.`, with no `. ` inside (T1 §4.1).
- Only `steadyhand.training` and `steadyhand_idx.training` import either training package (T1 §5 item 1). `steadyhand.training` imports the standard library, `steadyhand.notes`, `steadyhand.terms` and `steadyhand._validate` only; `steadyhand_idx.training` may add `steadyhand.training` and `steadyhand_idx.notes` (§5 item 2), and still imports the engine's public API only (core §4.2).
- The advice phrases, matched in any case: `you should buy`, `you should sell`, `we recommend`, `recommended stock`, `best stock`, `guaranteed`, `can't lose`, `cannot lose`; and, case-sensitively, a word of exactly four capital letters followed within three words by `buy` or `sell` in any case (§5 item 4). Lessons use made-up names ("Stock A").
- The disclaimer is `steadyhand.DISCLAIMER`, carried verbatim by the "Start here" lesson (core §9.8).
- Every IDX rule value a lesson states is copied from a research document under `docs/research/`, which the lesson names in `sources` (T1 §10).
- Every `*Error` a task raises is raised by a test that asserts its message or its fields. A `pytest.raises` names what it expects, with `match=` or by asserting the raised error's fields, and a `match=` holding a regex metacharacter is a raw string (ruff RUF043).
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A function that already existed keeps its old body in the red phase. A test that passes against the stubs is listed with its reason in its task.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code.
- Test file basenames are unique across `tests/`. English only. The phrase "robot trading" never appears (core §1.3).
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **A lesson saved by a Windows editor**, with a UTF-8 byte-order mark or CRLF line endings. Expected: it loads exactly as the same file without them, rather than failing as a broken header. Pinned in Task 2 (`test_a_byte_order_mark_is_not_part_of_the_header`, `test_a_file_with_windows_line_endings_reads_the_same`).
2. **`position = true` in a lesson header.** TOML has booleans, and Python's `bool` is an `int`, so a naive check reads it as position 1. Expected: refused, naming the file and `position`. Pinned in Task 2 (the `position true` case of `test_a_broken_lesson_names_its_file_and_field`; mutation M113), and the same for a course `number` (`number true`).
3. **A caller passing one key as a string.** `explain(catalogue, "term.run_rate", …)` would otherwise look up each character. Expected: a `TypeError` naming the mistake. Pinned in Task 3 (`test_bad_arguments_are_refused`).
4. **Advice phrasing a simple substring check misses**: split across a line break, inside a quote or an HTML comment (the CLI prints a body as written), or with a curly apostrophe (`can’t lose`). Expected: found. Pinned in Task 3 (`test_a_phrase_is_found_across_lines_quotes_and_curly_apostrophes`; mutation M128).
5. **A lesson missing from an installed wheel** while the source tree is complete, which no source-tree test can see. Expected: CI's `build` job fails. Pinned in Task 4 (the build step; mutation M138, run by hand).

## Scope decisions (read before starting)

1. **`LessonNotFound` is named `LessonNotFoundError`.** ruff's N818 requires the suffix, and every other exception in the codebase has it (`MembershipUnknownError`, `NoTradingDaysError`). This amends T1 §7's name; nothing else about it changes.
2. **`LESSONS` and `catalogue()` land in S4, not S2.** git cannot hold an empty folder, and a catalogue loaded from a missing folder must fail loudly, so the lesson roots exist only once lessons do. S2 ships the loader, `course.toml` and `COURSE`, and runs the guards on a fixture catalogue, as T1 §8 says. This changes the order of work only.
3. **The figure walk follows public properties as well as fields, and skips private names.** T1 §3.2 defines a term as "a figure a report can show"; `Costs.total`, `Fill.gross`, `CostBreakdown.total` and `DividendTotals.net` are shown and are properties, while `Portfolio._balance` is a private field no report shows. The walk finds 65 figure fields, which S1's `FIGURES` maps to 41 terms. It also fails if two walked classes share a name, since `"Class.field"` would then be ambiguous.
4. **The AST helpers have one home each.** The tests run under `--import-mode=importlib` with no packages, so a test module cannot import another. `tests/meta/key_walk.py` (the key and term sets) and `tests/meta/markdown_text.py` (Markdown as a reader sees it, moved out of `test_disclaimer.py`) sit on pytest's `pythonpath`, and every guard derives from them.
5. **`Catalogue.load` checks every rule a lesson file can break, alone or against the other files; the catalogue guards check what needs the repo.** Whether an explained key exists and whether a `sources` path exists need the key modules' source and the repo's files, which an installed copy lacks, so those two live in `tests/meta/lesson_rules.py`. The loader also refuses a lesson with no body, a title or summary on more than one line, a list naming an entry twice, a lesson listing itself in `see_also`, and a missing root folder.
6. **`course.toml`** is one `[[module]]` table per module, with exactly `number`, `slug` and `title`; numbers run 1, 2, 3 … in file order, and a slug matches `[a-z]+(-[a-z]+)*`.
7. **`explain` looks up every key at every level**, so a key with no lesson raises `LessonNotFoundError` whatever the setting (T1 §7: it is a bug). It returns the block without a trailing newline, or `""`.
8. **The advice scan reads HTML comments**, because `learn <id>` will print a body as written, and reads a curly apostrophe as a straight one. The "Start here" check reads the body as a reader sees it: comments removed, quote markers and line wrapping ignored.
9. **The legal import guard** resolves relative imports and reads `from steadyhand import training` as importing training. The training allowlist accepts `from steadyhand import notes` as the allowed submodule and refuses any other name taken from `steadyhand` itself.
10. **`steadyhand.training` stays out of `steadyhand.__all__`.** The public-API guard required every public name to be exported from `steadyhand`, which would make `steadyhand/__init__.py` import training, the one import T1 §5 forbids. The guard now leaves the training package out and checks `steadyhand.training.__all__` instead, including the names its own `__init__` defines.
11. **The golden file stores a warning as `[key, text]`**, the shape M4's notes already have there. Its figures do not move; Task 1 checks that.
12. **The story chain starts from `develop` plus the T1 spec** (Task 0's PR), because a lesson cites the spec in `sources`.
13. **The engine's lessons are market-neutral**: no `Rp`, `IDX`, `Indonesia` or `steadyhand-idx`, and a guard says so. The two "Start here" lessons live in the IDX folder, since they describe the IDX distribution and its commands.
14. **The LQ45 lesson's id is `idx.universe`**: an id has the shape of a key, which has no digits. The loader caught `idx.lq45` on the first load of the real lessons.
15. **The root README's status line was stale** ("Design phase. There is no usable code yet.", written before M1). S4 corrects it while adding the course and the Contributing section.
16. **S4 stays one story.** T1 §10 allows splitting it by module if its PR grows past a reviewable size. The 33 lessons are 871 lines, about 7,000 words, and the plan groups them by module. A split would not shrink the first part much: the guards it switches on need every keyed lesson, which is 20 of the 33 (the other 13 explain no key).

## File map

| File | Task | Responsibility |
|---|---|---|
| `packages/steadyhand/src/steadyhand/notes.py`, `terms.py` | 1 | The engine's note keys; the term keys and `FIGURES` |
| `packages/steadyhand-idx/src/steadyhand_idx/notes.py` | 1 | The IDX note key |
| `.../steadyhand/corporate.py`, `engine.py`, `backtest.py`, `universe.py`; `.../steadyhand_idx/universe.py` | 1 | Warnings become `Note`s |
| `scripts/record_golden.py`, `tests/fixtures/golden/…json` | 1 | Warnings stored as `[key, text]` |
| `tests/meta/key_walk.py`, `test_note_keys.py`, `test_terms.py` | 1 | The key sets, the key guard over both packages, the derived figure guard |
| `.../steadyhand/training/catalogue.py`, `__init__.py` | 2–4 | `Lesson`, `Module`, `Catalogue`, the errors; `LESSONS` from Task 4 |
| `.../steadyhand_idx/training/course.toml`, `__init__.py` | 2, 4 | The course; `COURSE`; `LESSONS` and `catalogue()` from Task 4 |
| `tests/fixtures/training/…` | 2 | A fixture catalogue in both package folders |
| `tests/meta/lesson_rules.py`, `markdown_text.py`, `test_lesson_rules.py` | 2, 3 | The catalogue guards and the advice scan, proven on the fixture |
| `.../steadyhand/training/render.py` | 3 | `Level`, `explain` |
| `tests/meta/test_legal_line.py` | 3 | T1 §5 items 1, 2 and 4 |
| `tests/meta/test_public_api.py`, `test_disclaimer.py` | 2, 4 | Training left out of the engine's exports and checked on its own; `normalised` moved out |
| `.../training/lessons/en/*.md` (both packages) | 4 | The 33 lessons |
| `tests/meta/test_lessons.py` | 4 | The guards over the real lessons |
| `.github/workflows/ci.yml` | 4 | The built-wheel check |
| `README.md`, `packages/*/README.md` | 4 | The course, the Contributing section |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | The T1 spec, this plan and the stories (docs only) | `t1/training-spec` |
| 1 | T1 S1 Keyed warnings and term keys | `t1/s1-keys` |
| 2 | T1 S2 The lesson catalogue and the course | `t1/s2-catalogue` |
| 3 | T1 S3 The renderer and the legal line | `t1/s3-renderer` |
| 4 | T1 S4 The lessons, the course content and the built-wheel check | `t1/s4-content` |

Stories merge in order: each one's code builds on the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Merge without asking: Shyden's standing rule of 2026-09-27 covers every green PR into `develop` (never `main`). Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: The T1 spec, this plan and the stories

Documentation only, on `t1/training-spec`, whose PR carries the T1 spec, this plan and `HANDOVER.md` (#96).

- [ ] **Step 1: File the stories.** Create one issue per task 1–4, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 2: Open the PR** from `t1/training-spec` into `develop` (`Refs #96`), and merge it as **Merging a story** says. Then delete the superseded `m4/m4b-plan` branch.

---

### Task 1: T1 S1 Keyed warnings and term keys

**Acceptance criteria (story text):**
1. The four warning producers build `Note`s from key constants, with each text unchanged character for character: `corporate.split.fraction_dropped` (a split drops a fraction), `data.bar.missing` (`engine._tradable`) and `data.bar.refused` (`backtest._refused_warnings`) in `steadyhand/notes.py`, and `universe.survivorship.gap` (`Lq45Membership.survivorship_warnings`) in a new `steadyhand_idx/notes.py` (T1 §3.1).
2. `CorporateOutcome.warnings`, `DayReport.warnings`, `BacktestResult.warnings`, `RunResult.warnings` and the `Universe` protocol's `survivorship_warnings` (and `Lq45Universe`'s) carry `Note`s. The IDX package imports `Note` from `steadyhand`.
3. The golden file keeps every figure; its warnings become `[key, text]` pairs with unchanged text (scope decision 11).
4. `steadyhand/terms.py` holds one `TERM_*` constant per term and `FIGURES`, mapping each figure field `"Class.field"` to its term: 41 terms over 65 fields (T1 §3.2, scope decision 3).
5. `tests/meta/test_terms.py` derives the figure fields by walking `DayReport`, `BacktestResult` and `IncomeReport` through fields, public properties, tuples, mappings and optionals, and fails on a figure with no term, an entry naming no field, a term missing from `FIGURES`, or two walked classes sharing a name.
6. `tests/meta/test_note_keys.py` covers the key modules of both packages: the shape, the naming, the term prefix on terms only, no key defined twice or used as a literal anywhere in either package, every `Note` built from a note key constant, every note key used.
7. The engine exports the new constants. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M104–M111 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/terms.py`, `packages/steadyhand-idx/src/steadyhand_idx/notes.py`, `tests/meta/key_walk.py`, `tests/meta/test_terms.py`
- Modify: `.../steadyhand/notes.py`, `corporate.py`, `engine.py`, `backtest.py`, `universe.py`, `__init__.py`; `.../steadyhand_idx/universe.py`, `__init__.py`; `scripts/record_golden.py`; `pyproject.toml` (pytest's `pythonpath`)
- Test: `tests/meta/test_note_keys.py`, and the tests that compared warnings with strings: `tests/engine/test_{corporate,engine,backtest,protocols}.py`, `tests/golden/test_golden_backtest.py`, `tests/idx/test_{universe,lq45_universe}.py`, `tests/perf/test_performance.py`

**Interfaces:**
- Consumes: M4's `Note(key, text)` and `notes.py`; M3's report types.
- Produces: `CORPORATE_SPLIT_FRACTION_DROPPED`, `DATA_BAR_MISSING`, `DATA_BAR_REFUSED` (in `steadyhand.notes`); `UNIVERSE_SURVIVORSHIP_GAP` (in `steadyhand_idx.notes`, exported by `steadyhand_idx`); the 41 `TERM_*` constants and `FIGURES: Mapping[str, str]` (in `steadyhand.terms`, exported by `steadyhand`); `Universe.survivorship_warnings(start, end) -> Sequence[Note]`; in `tests/meta/key_walk.py`: `key_constants`, `note_keys`, `string_literals`, `package_sources`, `constants_in`, `note_key_values`, `term_key_values`, `all_keys`, and the paths `ENGINE`, `IDX`, `NOTE_MODULES`, `TERM_MODULE`, `KEY_MODULES`.

- [ ] **Step 1: Branch.** `git switch -c t1/s1-keys origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_backtest.py`** (changed: 9 edits)

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.risk import RiskLimits
```
with:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_MISSING, DATA_BAR_REFUSED, Note
from steadyhand.risk import RiskLimits
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
from steadyhand.view import MarketView, PortfolioView
from steadyhand_idx import IdxMarketRules

```
with:
```python
from steadyhand.view import MarketView, PortfolioView
from steadyhand_idx import UNIVERSE_SURVIVORSHIP_GAP, IdxMarketRules

```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
START, END = DAYS[0], DAYS[-1]

```
with:
```python
START, END = DAYS[0], DAYS[-1]
GAP = Note(UNIVERSE_SURVIVORSHIP_GAP, "a gap")

```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
        excluded: Mapping[Instrument, str] | None = None,
        warnings: Sequence[str] = (),
    ) -> None:
```
with:
```python
        excluded: Mapping[Instrument, str] | None = None,
        warnings: Sequence[Note] = (),
    ) -> None:
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        self.asked.append((start, end))
```
with:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
        self.asked.append((start, end))
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    source = _Source(flat(BBCA, 9_000) + bbri, refused={BBRI: refused})
    universe = _Universe([(START, frozenset({BBCA, BBRI}))], warnings=["a gap"])
    result = run(source, universe, strategy=BuyAndHold())
```
with:
```python
    source = _Source(flat(BBCA, 9_000) + bbri, refused={BBRI: refused})
    universe = _Universe([(START, frozenset({BBCA, BBRI}))], warnings=[GAP])
    result = run(source, universe, strategy=BuyAndHold())
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    assert result.warnings == (
        "a gap",
        (
            "BBRI: the data source refused 4 day(s) (2025-07-03 to 2025-07-07, 2025-07-10), so it "
            "was not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited."
        ),
```
with:
```python
    assert result.warnings == (
        GAP,
        Note(
            DATA_BAR_REFUSED,
            "BBRI: the data source refused 4 day(s) (2025-07-03 to 2025-07-07, 2025-07-10), so it "
            "was not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited.",
        ),
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    ]
    assert result.warnings[0].startswith(
        "BBRI: the data source refused 2 day(s) (2025-06-30, 2025-07-11),"
```
with:
```python
    ]
    assert result.warnings[0].key == DATA_BAR_REFUSED
    assert result.warnings[0].text.startswith(
        "BBRI: the data source refused 2 day(s) (2025-06-30, 2025-07-11),"
```

<!-- edit: tests/engine/test_backtest.py -->
Replace:
```python
    assert result.run.warnings == (
        (
            "BBRI has no bar on 2025-07-08, so it is not traded; it is valued at its last close, "
            "IDR 4,000"
        ),
```
with:
```python
    assert result.run.warnings == (
        Note(
            DATA_BAR_MISSING,
            "BBRI has no bar on 2025-07-08, so it is not traded; it is valued at its last close, "
            "IDR 4,000",
        ),
```

**`tests/engine/test_corporate.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import MovementKind, Portfolio
```
with:
```python
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import CORPORATE_SPLIT_FRACTION_DROPPED, Note
from steadyhand.portfolio import MovementKind, Portfolio
```

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
    assert outcome.warnings == (
        (
            "BBCA: the 1-for-5 split on 2025-06-02 turned 1203 shares into 240; the fraction of "
            "a share left over is dropped (cash in lieu is not modelled)"
        ),
```
with:
```python
    assert outcome.warnings == (
        Note(
            CORPORATE_SPLIT_FRACTION_DROPPED,
            "BBCA: the 1-for-5 split on 2025-06-02 turned 1203 shares into 240; the fraction of "
            "a share left over is dropped (cash in lieu is not modelled)",
        ),
```

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
    assert outcome.holdings.portfolio.positions == ()
    assert "turned 4 shares into 0" in outcome.warnings[0]

```
with:
```python
    assert outcome.holdings.portfolio.positions == ()
    assert outcome.warnings[0].key == CORPORATE_SPLIT_FRACTION_DROPPED
    assert "turned 4 shares into 0" in outcome.warnings[0].text

```

**`tests/engine/test_engine.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
from steadyhand.money import IDR, Money
from steadyhand.portfolio import MissingPriceError, MovementKind
```
with:
```python
from steadyhand.money import IDR, Money
from steadyhand.notes import DATA_BAR_MISSING, Note
from steadyhand.portfolio import MissingPriceError, MovementKind
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert report.warnings == (
        (
            "BBCA has no bar on 2025-06-04, so it is not traded; it is valued at its last "
            "close, IDR 9,100"
        ),
```
with:
```python
    assert report.warnings == (
        Note(
            DATA_BAR_MISSING,
            "BBCA has no bar on 2025-06-04, so it is not traded; it is valued at its last "
            "close, IDR 9,100",
        ),
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    )
    assert report.warnings == ("BBRI has no bar on 2025-06-02, so it is not traded",)
    assert [o.instrument for o in report.queued] == [BBCA]
```
with:
```python
    )
    assert report.warnings == (
        Note(DATA_BAR_MISSING, "BBRI has no bar on 2025-06-02, so it is not traded"),
    )
    assert [o.instrument for o in report.queued] == [BBCA]
```

**`tests/engine/test_protocols.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python
from steadyhand.money import IDR, Currency, Money
from steadyhand.types import Bar, CorporateAction, Costs, Fill, Instrument, Order, OrderAck, Side
```
with:
```python
from steadyhand.money import IDR, Currency, Money
from steadyhand.notes import Note
from steadyhand.types import Bar, CorporateAction, Costs, Fill, Instrument, Order, OrderAck, Side
```

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        return ()
```
with:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
        return ()
```

**`tests/golden/test_golden_backtest.py`** (changed: 2 edits)

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python

from steadyhand import HISTORY_YEARS, IDR, STRATEGIES, Money, years_before
from steadyhand_idx import IdxMarketRules
```
with:
```python

from steadyhand import DATA_BAR_REFUSED, HISTORY_YEARS, IDR, STRATEGIES, Money, years_before
from steadyhand_idx import IdxMarketRules
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    assert "BBRI" not in held
    assert result.warnings[0].startswith(
        "BBRI: the data source refused 146 day(s) (2021-02-01 to 2021-09-07),"
```
with:
```python
    assert "BBRI" not in held
    assert result.warnings[0].key == DATA_BAR_REFUSED
    assert result.warnings[0].text.startswith(
        "BBRI: the data source refused 146 day(s) (2021-02-01 to 2021-09-07),"
```

**`tests/idx/test_lq45_universe.py`** (changed: 2 edits)

<!-- edit: tests/idx/test_lq45_universe.py -->
Replace:
```python
from steadyhand import IDR, Instrument, Universe
from steadyhand_idx.universe import (
```
with:
```python
from steadyhand import IDR, Instrument, Universe
from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP
from steadyhand_idx.universe import (
```

<!-- edit: tests/idx/test_lq45_universe.py -->
Replace:
```python
    assert len(warnings) == 1
    assert "between 2021-02-01 (Peng-1) and 2022-02-01 (Peng-3)" in warnings[0]
```
with:
```python
    assert len(warnings) == 1
    assert warnings[0].key == UNIVERSE_SURVIVORSHIP_GAP
    assert "between 2021-02-01 (Peng-1) and 2022-02-01 (Peng-3)" in warnings[0].text
```

**`tests/idx/test_universe.py`** (changed: 3 edits)

<!-- edit: tests/idx/test_universe.py -->
Replace:
```python

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.universe import (
```
with:
```python

from steadyhand import Note
from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP
from steadyhand_idx.universe import (
```

<!-- edit: tests/idx/test_universe.py -->
Replace:
```python
    assert warnings == [
        (
            "Survivorship bias: lq45_members.toml has no LQ45 list between 2022-08-01 "
            "(Peng-test/2022-08-01) and 2023-08-01 (Peng-test/2023-08-01), more than one review "
            "apart. The backtest uses the earlier list until the later one."
        )
```
with:
```python
    assert warnings == [
        Note(
            UNIVERSE_SURVIVORSHIP_GAP,
            "Survivorship bias: lq45_members.toml has no LQ45 list between 2022-08-01 "
            "(Peng-test/2022-08-01) and 2023-08-01 (Peng-test/2023-08-01), more than one review "
            "apart. The backtest uses the earlier list until the later one.",
        )
```

<!-- edit: tests/idx/test_universe.py -->
Replace:
```python
    later = membership.survivorship_warnings(date(2024, 9, 2), date(2025, 3, 3))
    assert [w.split(" between ")[1][:10] for w in later] == ["2024-08-01"]

```
with:
```python
    later = membership.survivorship_warnings(date(2024, 9, 2), date(2025, 3, 3))
    assert [w.text.split(" between ")[1][:10] for w in later] == ["2024-08-01"]

```

**`tests/meta/key_walk.py`** (new)

<!-- file: tests/meta/key_walk.py -->
```python
"""The note and term keys of both packages, read from their source by walking the AST.

Shared by the key, term and training guards, so each derives the same key sets the same way
and none keeps a list. A comment or a docstring that mentions a key is never read as one.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
IDX = ROOT / "packages/steadyhand-idx/src/steadyhand_idx"
NOTE_MODULES = (ENGINE / "notes.py", IDX / "notes.py")
TERM_MODULE = ENGINE / "terms.py"
KEY_MODULES = (*NOTE_MODULES, TERM_MODULE)
TERM_PREFIX = "term."


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


def package_sources() -> dict[Path, str]:
    """Every Python file of both packages, by path."""
    paths = sorted([*ENGINE.rglob("*.py"), *IDX.rglob("*.py")])
    return {path: path.read_text(encoding="utf-8") for path in paths}


def constants_in(paths: tuple[Path, ...]) -> list[tuple[str, str]]:
    return [pair for path in paths for pair in key_constants(path.read_text(encoding="utf-8"))]


def note_key_values() -> set[str]:
    """Every note key both packages define."""
    return {value for _, value in constants_in(NOTE_MODULES)}


def term_key_values() -> set[str]:
    """Every term key the engine defines."""
    return {value for _, value in constants_in((TERM_MODULE,))}


def all_keys() -> set[str]:
    """Every note and term key: what the lesson catalogue must explain, each exactly once."""
    return note_key_values() | term_key_values()
```

**`tests/meta/test_note_keys.py`** (changed: 2 edits)

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
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

```
with:
```python
"""Every note and term key is a stable constant, defined once and used (M4 §7, T1 §3.1).

The training sub-project attaches lessons to keys, so a key must never be reworded or reused,
and no note may be built from a literal that could drift from its constant. The keys are read
from the key modules of both packages and the ``Note(...)`` calls from every module of both,
all by walking the AST (``key_walk.py``), so a comment or a docstring that mentions a key is
never a finding.
"""

import re

from key_walk import (
    ENGINE,
    IDX,
    KEY_MODULES,
    NOTE_MODULES,
    TERM_MODULE,
    TERM_PREFIX,
    constants_in,
    key_constants,
    note_keys,
    package_sources,
    string_literals,
)

KEY = r"[a-z]+(\.[a-z_]+)+"
KNOWN = {
    "corporate.split.fraction_dropped",
    "data.bar.missing",
    "data.bar.refused",
    "income.growth.short_history",
    "income.projection.costs_ignored",
    "universe.survivorship.gap",
    "term.run_rate",
}

```

<!-- edit: tests/meta/test_note_keys.py -->
Replace:
```python
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
```
with:
```python
def test_every_key_is_a_dotted_lowercase_identifier_named_after_itself() -> None:
    keys = constants_in(KEY_MODULES)
    assert {value for _, value in keys} >= KNOWN
    for name, value in keys:
        assert re.fullmatch(KEY, value), f"{name} = {value!r} is not a dotted lowercase identifier"
        assert name == value.upper().replace(".", "_"), f"{name} is not named after {value!r}"


def test_terms_and_only_terms_carry_the_term_prefix() -> None:
    notes = [value for _, value in constants_in(NOTE_MODULES)]
    terms = [value for _, value in constants_in((TERM_MODULE,))]
    assert len(notes) >= 6
    assert len(terms) >= 30
    assert [value for value in notes if value.startswith(TERM_PREFIX)] == []
    assert [value for value in terms if not value.startswith(TERM_PREFIX)] == []


def test_no_key_is_defined_twice() -> None:
    values = [value for _, value in constants_in(KEY_MODULES)]
    assert len(set(values)) == len(values) >= len(KNOWN)
    elsewhere = {
        path.relative_to(ENGINE.parents[2]).as_posix(): sorted(
            set(values) & set(string_literals(source))
        )
        for path, source in package_sources().items()
        if path not in KEY_MODULES
    }
    assert len(elsewhere) >= 30, "the packages' modules were not found"
    assert any(name.startswith("steadyhand-idx/") for name in elsewhere)
    assert {name: found for name, found in elsewhere.items() if found} == {}


def test_every_note_is_built_from_a_note_key_and_every_note_key_is_used() -> None:
    names = {name for name, _ in constants_in(NOTE_MODULES)}
    sources = package_sources()
    used = [key for source in sources.values() for key in note_keys(source)]
    assert len(used) >= len(names) >= 6, "no Note(...) call was found in the packages"
    assert any(note_keys(source) for path, source in sources.items() if IDX in path.parents)
    assert sorted(set(used) - names) == []
```

**`tests/meta/test_terms.py`** (new)

<!-- file: tests/meta/test_terms.py -->
```python
"""Every figure a report can show has a term, and ``FIGURES`` names only real fields (T1 §3.2).

The figure fields are derived here, never listed: the walk starts at the report types and
follows their fields and properties into every dataclass they hold, through tuples, mappings
and optionals. A field or property typed ``Money`` or ``Decimal`` is a figure. Private names are
skipped, since no report shows them. So a figure added to any nested dataclass fails this test
until ``FIGURES`` gives it a term, without anyone adding the class to a list.
"""

import dataclasses
import typing
from collections.abc import Mapping
from decimal import Decimal
from types import NoneType

from key_walk import TERM_MODULE, key_constants

from steadyhand import FIGURES, BacktestResult, DayReport, IncomeReport, Money

REPORTS: tuple[type, ...] = (DayReport, BacktestResult, IncomeReport)
FIGURE_TYPES = (Money, Decimal)


def figure_fields(roots: tuple[type, ...]) -> tuple[set[str], dict[str, set[type]]]:
    """Every public ``Money`` or ``Decimal`` field or property reachable from *roots*, as
    ``"Class.name"``, and every class visited under its name (two classes sharing a name would
    make a ``"Class.name"`` ambiguous)."""
    figures: set[str] = set()
    visited: dict[str, set[type]] = {}

    def visit_class(cls: type) -> None:
        if cls in visited.get(cls.__name__, set()):
            return
        visited.setdefault(cls.__name__, set()).add(cls)
        hints = typing.get_type_hints(cls)
        members = [(field.name, hints[field.name]) for field in dataclasses.fields(cls)]
        for name, member in vars(cls).items():
            if isinstance(member, property) and member.fget is not None:
                members.append((name, typing.get_type_hints(member.fget).get("return", NoneType)))
        for name, hint in members:
            if not name.startswith("_"):
                visit_type(f"{cls.__name__}.{name}", hint)

    def visit_type(where: str, hint: object) -> None:
        if hint in FIGURE_TYPES:
            figures.add(where)
        elif isinstance(hint, type) and dataclasses.is_dataclass(hint):
            visit_class(hint)
        else:
            for argument in typing.get_args(hint):
                visit_type(where, argument)

    for root in roots:
        visit_class(root)
    return figures, visited


@dataclasses.dataclass(frozen=True)
class _Leaf:
    amount: Money
    count: int


@dataclasses.dataclass(frozen=True)
class _Root:
    rate: Decimal
    maybe: Decimal | None
    leaves: tuple[_Leaf, ...]
    by_name: Mapping[str, _Leaf]
    parent: "_Root | None"
    label: str
    _hidden: Money

    @property
    def total(self) -> Money:
        return self._hidden

    @property
    def _secret(self) -> Money:
        return self._hidden

    @property
    def described(self) -> str:
        return self.label


def test_the_walk_follows_fields_properties_and_containers() -> None:
    figures, visited = figure_fields((_Root,))
    assert figures == {"_Root.rate", "_Root.maybe", "_Root.total", "_Leaf.amount"}
    assert set(visited) == {"_Root", "_Leaf"}


def test_the_walk_reaches_every_report() -> None:
    figures, visited = figure_fields(REPORTS)
    assert {
        "DayReport.value",
        "Fill.price",
        "Metrics.total_return",
        "RunRate.annual_gross",
        "ScenarioProjection.years",
        "Costs.total",
    } <= figures
    assert len(figures) >= 60
    assert {name: classes for name, classes in visited.items() if len(classes) > 1} == {}


def test_every_figure_has_a_term() -> None:
    figures, _ = figure_fields(REPORTS)
    assert sorted(figures - set(FIGURES)) == []


def test_figures_names_only_fields_that_exist() -> None:
    figures, _ = figure_fields(REPORTS)
    assert sorted(set(FIGURES) - figures) == []


def test_every_term_is_a_figures_value_and_every_value_is_a_term() -> None:
    terms = {value for _, value in key_constants(TERM_MODULE.read_text(encoding="utf-8"))}
    assert len(terms) >= 30
    assert sorted(terms - set(FIGURES.values())) == []
    assert sorted(set(FIGURES.values()) - terms) == []
```

**`tests/perf/test_performance.py`** (changed: 2 edits)

<!-- edit: tests/perf/test_performance.py -->
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

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        return ()
```
with:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
        return ()
```


- [ ] **Step 3: Write the stubs.** New names only; every function that existed keeps its current body, so each producer still returns strings.

**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
Replace:
```python
from steadyhand_idx.fees import BrokerPreset, FeeSchedule
from steadyhand_idx.rules import IdxMarketRules, RuleTables
```
with:
```python
from steadyhand_idx.fees import BrokerPreset, FeeSchedule
from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP
from steadyhand_idx.rules import IdxMarketRules, RuleTables
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
Replace:
```python
__all__ = [
    "BarCache",
```
with:
```python
__all__ = [
    "UNIVERSE_SURVIVORSHIP_GAP",
    "BarCache",
```

**`packages/steadyhand-idx/src/steadyhand_idx/notes.py`** (new, as stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/notes.py -->
```python
"""The IDX distribution's note keys (M4 spec §7, T1 spec §3.1).

Each key follows the engine's rules in ``steadyhand.notes``: a dotted lowercase identifier that is
never reworded, held in a constant named after its value, so a lesson can attach to it. The
engine's key meta-test (``tests/meta/test_note_keys.py``) reads this module as well as the
engine's, so a key is never defined twice across the two packages.
"""

from __future__ import annotations

UNIVERSE_SURVIVORSHIP_GAP = "universe.survivorship.gap"
"""The LQ45 record has no list between two dates more than one review apart."""
```

**`packages/steadyhand-idx/src/steadyhand_idx/universe.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python

from steadyhand import IDR, Instrument
from steadyhand_idx._datafile import (
```
with:
```python

from steadyhand import IDR, Instrument, Note
from steadyhand_idx._datafile import (
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python
    rows,
)

LQ45_SIZE = 45
```
with:
```python
    rows,
)
from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP

LQ45_SIZE = 45
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, INCOME_PROJECTION_COSTS_IGNORED, Note
from steadyhand.outcomes import Cut, Rejected
```
with:
```python
)
from steadyhand.notes import (
    CORPORATE_SPLIT_FRACTION_DROPPED,
    DATA_BAR_MISSING,
    DATA_BAR_REFUSED,
    INCOME_GROWTH_SHORT_HISTORY,
    INCOME_PROJECTION_COSTS_IGNORED,
    Note,
)
from steadyhand.outcomes import Cut, Rejected
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    Strategy,
)
```
with:
```python
    Strategy,
)
from steadyhand.terms import (
    FIGURES,
    TERM_ANNUAL_RETURN,
    TERM_BROKER_FEE,
    TERM_CASH_MOVEMENT,
    TERM_CONTRIBUTION,
    TERM_COST_BASIS,
    TERM_CURRENT_YIELD,
    TERM_DAILY_COST,
    TERM_DEPOSIT,
    TERM_DIVIDEND_GROSS,
    TERM_DIVIDEND_GROWTH,
    TERM_DIVIDEND_NET,
    TERM_DIVIDEND_PER_SHARE,
    TERM_DIVIDEND_TAX,
    TERM_DRAWDOWN,
    TERM_EVENNESS,
    TERM_GOAL_SHARE,
    TERM_HIGH_WATER,
    TERM_HOLDINGS_VALUE,
    TERM_INCOME_TARGET,
    TERM_LAST_CLOSE,
    TERM_LEVY,
    TERM_MONTHLY_TAKE_HOME,
    TERM_PAYMENT_CALENDAR,
    TERM_PORTFOLIO_VALUE,
    TERM_RECEIVED_INCOME,
    TERM_RUN_RATE,
    TERM_SALE_TAX,
    TERM_SETTLED_CASH,
    TERM_STARTING_INCOME,
    TERM_TAKE_HOME,
    TERM_TOTAL_RETURN,
    TERM_TRADE_PRICE,
    TERM_TRADE_VALUE,
    TERM_TRADING_COSTS,
    TERM_TRAILING_INCOME,
    TERM_TURNOVER,
    TERM_UNIT_PRICE,
    TERM_UNITS,
    TERM_UNSETTLED_CASH,
    TERM_YEARS_TO_GOAL,
    TERM_YIELD_ON_COST,
)
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "BASE_GROWTH_CAP",
    "DISCLAIMER",
    "GROWTH_YEARS",
```
with:
```python
    "BASE_GROWTH_CAP",
    "CORPORATE_SPLIT_FRACTION_DROPPED",
    "DATA_BAR_MISSING",
    "DATA_BAR_REFUSED",
    "DISCLAIMER",
    "FIGURES",
    "GROWTH_YEARS",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "STRATEGIES",
    "YEAR_DAYS",
```
with:
```python
    "STRATEGIES",
    "TERM_ANNUAL_RETURN",
    "TERM_BROKER_FEE",
    "TERM_CASH_MOVEMENT",
    "TERM_CONTRIBUTION",
    "TERM_COST_BASIS",
    "TERM_CURRENT_YIELD",
    "TERM_DAILY_COST",
    "TERM_DEPOSIT",
    "TERM_DIVIDEND_GROSS",
    "TERM_DIVIDEND_GROWTH",
    "TERM_DIVIDEND_NET",
    "TERM_DIVIDEND_PER_SHARE",
    "TERM_DIVIDEND_TAX",
    "TERM_DRAWDOWN",
    "TERM_EVENNESS",
    "TERM_GOAL_SHARE",
    "TERM_HIGH_WATER",
    "TERM_HOLDINGS_VALUE",
    "TERM_INCOME_TARGET",
    "TERM_LAST_CLOSE",
    "TERM_LEVY",
    "TERM_MONTHLY_TAKE_HOME",
    "TERM_PAYMENT_CALENDAR",
    "TERM_PORTFOLIO_VALUE",
    "TERM_RECEIVED_INCOME",
    "TERM_RUN_RATE",
    "TERM_SALE_TAX",
    "TERM_SETTLED_CASH",
    "TERM_STARTING_INCOME",
    "TERM_TAKE_HOME",
    "TERM_TOTAL_RETURN",
    "TERM_TRADE_PRICE",
    "TERM_TRADE_VALUE",
    "TERM_TRADING_COSTS",
    "TERM_TRAILING_INCOME",
    "TERM_TURNOVER",
    "TERM_UNITS",
    "TERM_UNIT_PRICE",
    "TERM_UNSETTLED_CASH",
    "TERM_YEARS_TO_GOAL",
    "TERM_YIELD_ON_COST",
    "YEAR_DAYS",
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.risk import Halt
```
with:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import DATA_BAR_REFUSED, Note
from steadyhand.risk import Halt
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    baseline: RunResult | None
    warnings: tuple[str, ...]
    income_impact: IncomeImpact | None = None
```
with:
```python
    baseline: RunResult | None
    warnings: tuple[Note, ...]
    income_impact: IncomeImpact | None = None
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
from steadyhand.money import CurrencyMismatchError, Money, Rounding
from steadyhand.outcomes import Rejected
```
with:
```python
from steadyhand.money import CurrencyMismatchError, Money, Rounding
from steadyhand.notes import CORPORATE_SPLIT_FRACTION_DROPPED, Note
from steadyhand.outcomes import Rejected
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
    frozen: tuple[tuple[Instrument, str], ...]
    warnings: tuple[str, ...]

```
with:
```python
    frozen: tuple[tuple[Instrument, str], ...]
    warnings: tuple[Note, ...]

```

**`packages/steadyhand/src/steadyhand/engine.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
from steadyhand.money import Money
from steadyhand.outcomes import Cut, Rejected
```
with:
```python
from steadyhand.money import Money
from steadyhand.notes import DATA_BAR_MISSING, Note
from steadyhand.outcomes import Cut, Rejected
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    """The price of one unit at today's close, which a deposit leaves unchanged (M3 spec §6.3)."""
    warnings: tuple[str, ...]

```
with:
```python
    """The price of one unit at today's close, which a deposit leaves unchanged (M3 spec §6.3)."""
    warnings: tuple[Note, ...]

```

**`packages/steadyhand/src/steadyhand/notes.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/notes.py -->
Replace:
```python
A key is a dotted lowercase identifier that is never reworded, so the training sub-project can
attach a lesson to it; the text is free to change. Every key is a constant below, named after its
value, and every ``Note`` in the engine is built from one of them, never from a literal
(``tests/meta/test_note_keys.py``). This module imports nothing from the rest of the engine, so
any engine module can use it without an import cycle.
"""
```
with:
```python
A key is a dotted lowercase identifier that is never reworded, so the training sub-project can
attach a lesson to it; the text is free to change. Every key is a constant below (or, for the
IDX distribution, in ``steadyhand_idx.notes``), named after its value, and every ``Note`` in
either package is built from one of them, never from a literal
(``tests/meta/test_note_keys.py``). Figures have keys too, in ``steadyhand.terms``. This module
imports nothing from the rest of the engine, so any engine module can use it without an import
cycle.
"""
```

<!-- edit: packages/steadyhand/src/steadyhand/notes.py -->
Replace:
```python
from steadyhand._validate import require_type

```
with:
```python
from steadyhand._validate import require_type

CORPORATE_SPLIT_FRACTION_DROPPED = "corporate.split.fraction_dropped"
"""A split left a fraction of a share, which is dropped: cash in lieu is not modelled."""

DATA_BAR_MISSING = "data.bar.missing"
"""A member or a holding has no bar on a day, so it is not traded that day."""

DATA_BAR_REFUSED = "data.bar.refused"
"""The data source refused a stock's days in a backtest, so it was not traded on them."""

```

**`packages/steadyhand/src/steadyhand/terms.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/terms.py -->
```python
"""Terms: a stable key for each figure a report can show (T1 spec §3.2).

A term key follows the note rules in ``steadyhand.notes``: a dotted lowercase identifier that is
never reworded, in a constant named after its value, here always under ``term.``. A lesson
attaches to a term, so a report's labels can be explained as well as its notes.

``FIGURES`` maps every figure field, as ``"Class.field"``, to its term. Several fields share a
term when they show the same quantity. ``tests/meta/test_terms.py`` derives the figure fields
itself, by walking the report types, and fails when one is missing here or when an entry here
names a field that does not exist. This module imports nothing from the rest of the engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

TERM_ANNUAL_RETURN = "term.annual_return"
"""The total return compounded to a yearly rate over the run's calendar days."""

TERM_BROKER_FEE = "term.broker_fee"
"""What the broker charges on a trade."""

TERM_CASH_MOVEMENT = "term.cash_movement"
"""One change to cash: positive when money comes in, negative when it goes out."""

TERM_CONTRIBUTION = "term.contribution"
"""The money added each month in a projection."""

TERM_COST_BASIS = "term.cost_basis"
"""What a holding cost to buy, costs included."""

TERM_CURRENT_YIELD = "term.current_yield"
"""A year's dividends as a share of what the holdings are worth today."""

TERM_DAILY_COST = "term.daily_cost"
"""A cost charged by the day rather than by the trade."""

TERM_DEPOSIT = "term.deposit"
"""Money paid into the portfolio."""

TERM_DIVIDEND_GROSS = "term.dividend_gross"
"""A dividend before tax."""

TERM_DIVIDEND_GROWTH = "term.dividend_growth"
"""The yearly rate at which dividends a share have grown, or are assumed to grow."""

TERM_DIVIDEND_NET = "term.dividend_net"
"""A dividend after tax."""

TERM_DIVIDEND_PER_SHARE = "term.dividend_per_share"
"""The dividends one share paid over a year."""

TERM_DIVIDEND_TAX = "term.dividend_tax"
"""The tax taken from a dividend before it is paid."""

TERM_DRAWDOWN = "term.drawdown"
"""The largest fall from a high point to a later low point."""

TERM_EVENNESS = "term.evenness"
"""The largest month's share of a year's dividend income."""

TERM_GOAL_SHARE = "term.goal_share"
"""How much of the income target an amount covers."""

TERM_HIGH_WATER = "term.high_water"
"""The highest unit price the portfolio has reached."""

TERM_HOLDINGS_VALUE = "term.holdings_value"
"""What the shares held are worth at the day's closing prices."""

TERM_INCOME_TARGET = "term.income_target"
"""The yearly dividend income the goal asks for."""

TERM_LAST_CLOSE = "term.last_close"
"""A stock's most recent closing price."""

TERM_LEVY = "term.levy"
"""The exchange's charges on a trade, collected by the broker."""

TERM_MONTHLY_TAKE_HOME = "term.monthly_take_home"
"""The run-rate after tax, spread over twelve months."""

TERM_PAYMENT_CALENDAR = "term.payment_calendar"
"""The expected dividend income in each month of the year."""

TERM_PORTFOLIO_VALUE = "term.portfolio_value"
"""Cash plus holdings: what the whole portfolio is worth."""

TERM_RECEIVED_INCOME = "term.received_income"
"""The dividends actually paid over the last year."""

TERM_RUN_RATE = "term.run_rate"
"""What the dividends held now would pay over a year if nothing changed."""

TERM_SALE_TAX = "term.sale_tax"
"""The tax charged on the value of every sale."""

TERM_SETTLED_CASH = "term.settled_cash"
"""Cash that has arrived and can be spent."""

TERM_STARTING_INCOME = "term.starting_income"
"""The yearly dividend income a projection starts from."""

TERM_TAKE_HOME = "term.take_home"
"""What dividends leave after the full dividend tax, whatever tax the engine booked."""

TERM_TOTAL_RETURN = "term.total_return"
"""The portfolio's gain or loss over the run, with deposits not counted as gains."""

TERM_TRADE_PRICE = "term.trade_price"
"""The price a trade was filled at."""

TERM_TRADE_VALUE = "term.trade_value"
"""The number of shares traded times the price, before costs."""

TERM_TRADING_COSTS = "term.trading_costs"
"""Everything a trade costs on top of its value."""

TERM_TRAILING_INCOME = "term.trailing_income"
"""The dividend income after tax paid in the last year of a run."""

TERM_TURNOVER = "term.turnover"
"""How much of the portfolio is traded in a year."""

TERM_UNIT_PRICE = "term.unit_price"
"""The price of one unit when the portfolio is counted as a fund."""

TERM_UNITS = "term.units"
"""How many units of the portfolio exist when it is counted as a fund."""

TERM_UNSETTLED_CASH = "term.unsettled_cash"
"""Cash from a sale that has not arrived yet."""

TERM_YEARS_TO_GOAL = "term.years_to_goal"
"""How many years a projection takes to reach the income target."""

TERM_YIELD_ON_COST = "term.yield_on_cost"
"""A year's dividends as a share of what the holdings cost to buy."""

FIGURES: Mapping[str, str] = MappingProxyType(
    {
        "CashMovement.amount": TERM_CASH_MOVEMENT,
        "CostBreakdown.daily": TERM_DAILY_COST,
        "CostBreakdown.fee": TERM_BROKER_FEE,
        "CostBreakdown.levy": TERM_LEVY,
        "CostBreakdown.sale_tax": TERM_SALE_TAX,
        "CostBreakdown.total": TERM_TRADING_COSTS,
        "Costs.fee": TERM_BROKER_FEE,
        "Costs.levy": TERM_LEVY,
        "Costs.tax": TERM_SALE_TAX,
        "Costs.total": TERM_TRADING_COSTS,
        "DayReport.daily_cost": TERM_DAILY_COST,
        "DayReport.deposit": TERM_DEPOSIT,
        "DayReport.holdings_value": TERM_HOLDINGS_VALUE,
        "DayReport.settled": TERM_SETTLED_CASH,
        "DayReport.tax": TERM_DIVIDEND_TAX,
        "DayReport.unit_price": TERM_UNIT_PRICE,
        "DayReport.unsettled": TERM_UNSETTLED_CASH,
        "DayReport.value": TERM_PORTFOLIO_VALUE,
        "DividendGrowth.portfolio": TERM_DIVIDEND_GROWTH,
        "DividendTotals.gross": TERM_DIVIDEND_GROSS,
        "DividendTotals.net": TERM_DIVIDEND_NET,
        "DividendTotals.tax": TERM_DIVIDEND_TAX,
        "Drawdown.depth": TERM_DRAWDOWN,
        "Entitlement.gross": TERM_DIVIDEND_GROSS,
        "Fill.gross": TERM_TRADE_VALUE,
        "Fill.price": TERM_TRADE_PRICE,
        "GoalProgress.received": TERM_RECEIVED_INCOME,
        "GoalProgress.received_share": TERM_GOAL_SHARE,
        "GoalProgress.run_rate": TERM_RUN_RATE,
        "GoalProgress.run_rate_share": TERM_GOAL_SHARE,
        "GoalProgress.target": TERM_INCOME_TARGET,
        "HoldingCalendar.months": TERM_PAYMENT_CALENDAR,
        "HoldingGrowth.earlier": TERM_DIVIDEND_PER_SHARE,
        "HoldingGrowth.growth": TERM_DIVIDEND_GROWTH,
        "HoldingGrowth.recent": TERM_DIVIDEND_PER_SHARE,
        "HoldingRunRate.annual_gross": TERM_RUN_RATE,
        "HoldingRunRate.monthly_take_home": TERM_MONTHLY_TAKE_HOME,
        "Holdings.last_closes": TERM_LAST_CLOSE,
        "IncomeFigures.gross": TERM_DIVIDEND_GROSS,
        "IncomeFigures.net": TERM_DIVIDEND_NET,
        "IncomeFigures.take_home": TERM_TAKE_HOME,
        "IncomeFigures.tax": TERM_DIVIDEND_TAX,
        "IncomeImpact.received": TERM_RECEIVED_INCOME,
        "IncomeImpact.run_rate": TERM_RUN_RATE,
        "Metrics.annual_return": TERM_ANNUAL_RETURN,
        "Metrics.deposited": TERM_DEPOSIT,
        "Metrics.final_value": TERM_PORTFOLIO_VALUE,
        "Metrics.total_return": TERM_TOTAL_RETURN,
        "Metrics.trailing_income": TERM_TRAILING_INCOME,
        "Metrics.turnover": TERM_TURNOVER,
        "PaymentCalendar.evenness": TERM_EVENNESS,
        "PaymentCalendar.months": TERM_PAYMENT_CALENDAR,
        "Position.cost_basis": TERM_COST_BASIS,
        "Projection.contribution": TERM_CONTRIBUTION,
        "Projection.target": TERM_INCOME_TARGET,
        "ReceivedIncome.current_yield": TERM_CURRENT_YIELD,
        "ReceivedIncome.yield_on_cost": TERM_YIELD_ON_COST,
        "RunRate.annual_gross": TERM_RUN_RATE,
        "RunRate.monthly_take_home": TERM_MONTHLY_TAKE_HOME,
        "ScenarioProjection.growth": TERM_DIVIDEND_GROWTH,
        "ScenarioProjection.starting_gross": TERM_STARTING_INCOME,
        "ScenarioProjection.years": TERM_YEARS_TO_GOAL,
        "UnitValue.high_water": TERM_HIGH_WATER,
        "UnitValue.price": TERM_UNIT_PRICE,
        "UnitValue.units": TERM_UNITS,
    }
)
"""Every figure field a report can show, as ``"Class.field"``, and the term that explains it."""
```

**`packages/steadyhand/src/steadyhand/universe.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/universe.py -->
Replace:
```python

from steadyhand.types import Instrument
```
with:
```python

from steadyhand.notes import Note
from steadyhand.types import Instrument
```

**`pyproject.toml`** (changed; configuration, needed to collect the tests: 1 edit)

<!-- edit: pyproject.toml -->
Replace:
```toml
testpaths = ["tests"]
pythonpath = ["scripts"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra", "-m", "not live and not perf"]
```
with:
```toml
testpaths = ["tests"]
pythonpath = ["scripts", "tests/meta"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra", "-m", "not live and not perf"]
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=836 failed=11 -->
Expected: 836 run, 11 failed, each on its own assertion, since the four producers keep their old bodies and still return strings: six `AssertionError`s comparing strings with `Note`s (in `test_backtest.py`, `test_corporate.py`, `test_engine.py` and `test_universe.py`) and four `AttributeError: 'str' object has no attribute 'key'` (in `test_backtest.py`, `test_corporate.py`, `test_golden_backtest.py` and `test_lq45_universe.py`). The eleventh, also an `AssertionError`, is `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used`, whose liveness check finds only M4's two `Note(...)` calls for six note keys. Eight tests pass against the stubs by design: the key-shape, term-prefix and no-duplicate checks in `test_note_keys.py` and the five tests of `test_terms.py` read constants and `FIGURES`, which are data and exist in full in the red phase. Mutations M107–M111 prove each of them can go red.

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/universe.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python

    def survivorship_warnings(self, start: date, end: date) -> list[str]:
        """What a backtest from *start* to *end* must print about missing lists (spec §9.4).
```
with:
```python

    def survivorship_warnings(self, start: date, end: date) -> list[Note]:
        """What a backtest from *start* to *end* must print about missing lists (spec §9.4).
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python
        """
        warnings: list[str] = []
        for earlier, later in self.gaps():
            if start < later.effective and earlier.effective <= end:
                warnings.append(
                    f"Survivorship bias: {self._file} has no LQ45 list between "
                    f"{earlier.effective.isoformat()} ({earlier.source}) and "
                    f"{later.effective.isoformat()} ({later.source}), more than one review apart. "
                    "The backtest uses the earlier list until the later one."
                )
```
with:
```python
        """
        warnings: list[Note] = []
        for earlier, later in self.gaps():
            if start < later.effective and earlier.effective <= end:
                warnings.append(
                    Note(
                        UNIVERSE_SURVIVORSHIP_GAP,
                        f"Survivorship bias: {self._file} has no LQ45 list between "
                        f"{earlier.effective.isoformat()} ({earlier.source}) and "
                        f"{later.effective.isoformat()} ({later.source}), more than one review "
                        "apart. The backtest uses the earlier list until the later one.",
                    )
                )
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python

    def survivorship_warnings(self, start: date, end: date) -> tuple[str, ...]:
        return tuple(self._membership.survivorship_warnings(start, end))
```
with:
```python

    def survivorship_warnings(self, start: date, end: date) -> tuple[Note, ...]:
        return tuple(self._membership.survivorship_warnings(start, end))
```

**`packages/steadyhand/src/steadyhand/backtest.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
    @property
    def warnings(self) -> tuple[str, ...]:
        """Every day's warnings, in day order."""
```
with:
```python
    @property
    def warnings(self) -> tuple[Note, ...]:
        """Every day's warnings, in day order."""
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python

def _refused_warnings(window: _Window) -> list[str]:
    """One warning per stock, naming each span of consecutive refused trading days."""
    warnings: list[str] = []
    for stock in sorted(window.refused, key=lambda i: (i.market, i.symbol)):
```
with:
```python

def _refused_warnings(window: _Window) -> list[Note]:
    """One warning per stock, naming each span of consecutive refused trading days."""
    warnings: list[Note] = []
    for stock in sorted(window.refused, key=lambda i: (i.market, i.symbol)):
```

<!-- edit: packages/steadyhand/src/steadyhand/backtest.py -->
Replace:
```python
        warnings.append(
            f"{stock.symbol}: the data source refused {len(refused)} day(s) ({named}), so it was "
            "not traded on them, and a holding was valued at its last clean close. A dividend "
            "whose ex-date falls on a refused day is unknown and was not credited."
        )
```
with:
```python
        warnings.append(
            Note(
                DATA_BAR_REFUSED,
                f"{stock.symbol}: the data source refused {len(refused)} day(s) ({named}), so it "
                "was not traded on them, and a holding was valued at its last clean close. A "
                "dividend whose ex-date falls on a refused day is unknown and was not credited.",
            )
        )
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
        self._newly_frozen: list[tuple[Instrument, str]] = []
        self._warnings: list[str] = []

```
with:
```python
        self._newly_frozen: list[tuple[Instrument, str]] = []
        self._warnings: list[Note] = []

```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
                self._warnings.append(
                    f"{stock.symbol}: the {split.new_shares}-for-{split.old_shares} split on "
                    f"{self._day.isoformat()} turned {held.quantity} shares into {kept}; the "
                    "fraction of a share left over is dropped (cash in lieu is not modelled)"
                )
```
with:
```python
                self._warnings.append(
                    Note(
                        CORPORATE_SPLIT_FRACTION_DROPPED,
                        f"{stock.symbol}: the {split.new_shares}-for-{split.old_shares} split on "
                        f"{self._day.isoformat()} turned {held.quantity} shares into {kept}; the "
                        "fraction of a share left over is dropped (cash in lieu is not modelled)",
                    )
                )
```

**`packages/steadyhand/src/steadyhand/engine.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    closes: Mapping[Instrument, Money],
) -> tuple[Tradable, list[str]]:
    """Today's buyable and sellable stocks (M3 spec §6.4), and a warning for each missing bar."""
```
with:
```python
    closes: Mapping[Instrument, Money],
) -> tuple[Tradable, list[Note]]:
    """Today's buyable and sellable stocks (M3 spec §6.4), and a warning for each missing bar."""
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        reasons.setdefault(instrument, f"excluded: {reason}")
    warnings: list[str] = []
    for instrument in sorted(inputs.members | held, key=lambda i: (i.market, i.symbol)):
```
with:
```python
        reasons.setdefault(instrument, f"excluded: {reason}")
    warnings: list[Note] = []
    for instrument in sorted(inputs.members | held, key=lambda i: (i.market, i.symbol)):
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
            warning += f"; it is valued at its last close, {closes[instrument]}"
        warnings.append(warning)
    buyable = frozenset(inputs.members - reasons.keys())
```
with:
```python
            warning += f"; it is valued at its last close, {closes[instrument]}"
        warnings.append(Note(DATA_BAR_MISSING, warning))
    buyable = frozenset(inputs.members - reasons.keys())
```

**`packages/steadyhand/src/steadyhand/universe.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/universe.py -->
Replace:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[str]:
        """What a backtest from *start* to *end* must print about gaps in the membership record.
```
with:
```python

    def survivorship_warnings(self, start: date, end: date) -> Sequence[Note]:
        """What a backtest from *start* to *end* must print about gaps in the membership record.
```

**`scripts/record_golden.py`** (implemented: 1 edit)

<!-- edit: scripts/record_golden.py -->
Replace:
```python
        else [outcome.halt.day.isoformat(), outcome.halt.cause],
        "warnings": [*result.warnings, *outcome.warnings],
        "metrics": {
```
with:
```python
        else [outcome.halt.day.isoformat(), outcome.halt.cause],
        "warnings": [[note.key, note.text] for note in (*result.warnings, *outcome.warnings)],
        "metrics": {
```

Generate `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json sha256=2b73b38fafaead1be44b2c53e1d4a64e115b03ee291fbdab859c713b83503070 -->
```bash
uv run python scripts/record_golden.py
```


- [ ] **Step 6: Check the golden figures did not move.** Only the warnings' shape may change, and their text must not:

  ```bash
  uv run python - <<'EOF'
  import json, subprocess
  path = "tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json"
  old = json.loads(subprocess.run(["git", "show", f"origin/develop:{path}"], capture_output=True, text=True, check=True).stdout)
  new = json.loads(open(path, encoding="utf-8").read())
  print(sorted(key for key in old if old[key] != new[key]), [text for _, text in new["warnings"]] == old["warnings"], [key for key, _ in new["warnings"]])
  EOF
  ```

  Expected: `['warnings'] True ['data.bar.refused']`.

- [ ] **Step 7: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=836 passed=836 -->
Expected: every command exits 0; 836 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 8.6 s against the 30 s budget).

- [ ] **Step 8: Mutations.** Run M104–M111 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 9: Commit, push and merge** (`feat(engine): T1 S1 keyed warnings and term keys`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 2: T1 S2 The lesson catalogue and the course

**Acceptance criteria (story text):**
1. A new package, `steadyhand.training` (standard library only), has `Lesson`, `Module`, `Catalogue` with `load(roots, course)`, `lessons()`, `lesson(id)`, `for_key(key)` and `course()`, and the errors `LessonError(origin, field, problem)` and `LessonNotFoundError(wanted, closest)` (T1 §7, scope decision 1). `lesson` and `for_key` name up to three closest matches (`difflib`).
2. `load` reads every `*.md` under each root, in subfolders too, and the course file, as UTF-8 with or without a byte-order mark and with either line ending. It enforces every rule of T1 §4.1 and scope decision 5, and each broken rule raises `LessonError` naming the file and the field.
3. `steadyhand_idx/training/course.toml` lists the eight modules of T1 §4.3 in order, and `steadyhand_idx.training.COURSE` finds it inside the installed package (scope decision 6).
4. The loader tests have one malformed case per rule, each asserting the file and the field; the course has its own cases.
5. The catalogue guards (`tests/meta/lesson_rules.py`: a key with no lesson, a lesson explaining an unknown key, a `sources` path that is not a repo file, "Start here" without the disclaimer) pass on a fixture catalogue in both package folders, and each fails on a broken copy (T1 §8).
6. The public-API guard leaves `steadyhand.training` out of `steadyhand` and checks `steadyhand.training.__all__` (scope decision 10). `normalised` moves to `tests/meta/markdown_text.py`.
7. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and M112–M121 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/training/__init__.py`, `training/catalogue.py`; `packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py`, `training/course.toml`; `tests/fixtures/training/…`; `tests/meta/lesson_rules.py`, `tests/meta/markdown_text.py`
- Modify: `tests/meta/test_disclaimer.py`, `tests/meta/test_public_api.py`
- Test: create `tests/training/test_catalogue.py`, `tests/training/test_course.py`, `tests/meta/test_lesson_rules.py`

**Interfaces:**
- Consumes: nothing from Task 1 at runtime; the guards consume `key_walk`'s key sets in Task 4.
- Produces: `Lesson(id, title, summary, explains: tuple[str, ...], module: str | None, position: int | None, see_also: tuple[str, ...], sources: tuple[str, ...], body: str, origin: str)`; `Module(number: int, slug: str, title: str, lessons: tuple[Lesson, ...])`; `Catalogue.load(roots: Iterable[Traversable], course: Traversable) -> Catalogue`, `.lessons() -> tuple[Lesson, ...]` (by id), `.lesson(lesson_id: str) -> Lesson`, `.for_key(key: str) -> Lesson`, `.course() -> tuple[Module, ...]`; `LessonError(origin: str, field: str, problem: str)`; `LessonNotFoundError(wanted: str, closest: tuple[str, ...])`; `steadyhand_idx.training.COURSE: Traversable`; in `lesson_rules.py`: `unexplained(catalogue, keys) -> list[str]`, `unknown(catalogue, keys) -> list[str]`, `missing_sources(catalogue, root: Path) -> list[str]`, `start_here_problems(catalogue, disclaimer: str) -> list[str]`; in `markdown_text.py`: `normalised(markdown: str) -> str`.

- [ ] **Step 1: Branch.** `git switch -c t1/s2-catalogue origin/develop`

- [ ] **Step 2: Write the failing tests and the fixtures.**

**`tests/fixtures/training/course.toml`** (new)

<!-- file: tests/fixtures/training/course.toml -->
```toml
# A fixture course for the catalogue guards' own tests (T1 spec §8).

[[module]]
number = 1
slug = "start-here"
title = "Start here"

[[module]]
number = 2
slug = "how-idx-works"
title = "How IDX works"

[[module]]
number = 3
slug = "later"
title = "Coming later"
```

**`tests/fixtures/training/engine/en/fixture.returns.md`** (new)

<!-- file: tests/fixtures/training/engine/en/fixture.returns.md -->
```markdown
+++
id = "fixture.returns"
title = "Returns"
summary = "How much a portfolio gained or lost."
explains = ["term.fixture_return", "fixture.note.gap"]
see_also = ["fixture.lots"]
sources = ["README.md", "docs/lq45-members.md §2"]
+++

A fixture lesson that explains a term and a note.
```

**`tests/fixtures/training/engine/en/start.welcome.md`** (new)

<!-- file: tests/fixtures/training/engine/en/start.welcome.md -->
```markdown
+++
id = "start.welcome"
title = "Welcome"
summary = "What this software is and is not."
explains = []
module = "start-here"
position = 1
sources = ["packages/steadyhand/src/steadyhand/disclaimer.py"]
+++

A fixture lesson for the catalogue guards. It carries the disclaimer, wrapped as Markdown
wraps it:

> steadyhand is example software that you run yourself, on your own account, and you make
> your own decisions with it. It is not financial advice. You can lose money.
```

**`tests/fixtures/training/idx/en/fixture.lots.md`** (new)

<!-- file: tests/fixtures/training/idx/en/fixture.lots.md -->
```markdown
+++
id = "fixture.lots"
title = "Lots"
summary = "Shares are bought in lots of a fixed size."
explains = ["fixture.lot.size"]
module = "how-idx-works"
position = 1
see_also = ["fixture.returns"]
+++

A fixture lesson in the other package's folder.
```

**`tests/meta/lesson_rules.py`** (new)

<!-- file: tests/meta/lesson_rules.py -->
```python
"""The catalogue guards that need the repo (T1 spec §8), as functions over a loaded catalogue.

``Catalogue.load`` checks every rule a lesson file can break on its own. What is left needs the
repo: the key sets (derived from the key modules' source by ``key_walk``), the paths ``sources``
cites, and the disclaimer. Each function returns its findings, so a test asserts ``[]`` and a
failure names what is wrong. Until the real lessons land they run against the fixture
catalogue; then against both packages' lesson folders.
"""

from collections.abc import Set
from pathlib import Path, PurePosixPath

from markdown_text import normalised

from steadyhand.training import Catalogue

SECTION = " §"
FIRST_MODULE = "start-here"


def unexplained(catalogue: Catalogue, keys: Set[str]) -> list[str]:
    """Every key that no lesson explains."""
    explained = {key for lesson in catalogue.lessons() for key in lesson.explains}
    return sorted(keys - explained)


def unknown(catalogue: Catalogue, keys: Set[str]) -> list[str]:
    """Every key a lesson explains that is not a note or term key, as ``id: key``."""
    return [
        f"{lesson.id}: {key}"
        for lesson in catalogue.lessons()
        for key in lesson.explains
        if key not in keys
    ]


def missing_sources(catalogue: Catalogue, root: Path) -> list[str]:
    """Every ``sources`` entry whose path is not a file in the repo, as ``id: entry``."""
    found: list[str] = []
    for lesson in catalogue.lessons():
        for source in lesson.sources:
            path = PurePosixPath(source.split(SECTION, 1)[0])
            if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                found.append(f"{lesson.id}: {source}")
    return found


def start_here_problems(catalogue: Catalogue, disclaimer: str) -> list[str]:
    """Why the course does not open with a lesson carrying the disclaimer verbatim, if it
    does not. The text is compared as a reader sees it, however the Markdown wraps it."""
    modules = catalogue.course()
    if not modules or modules[0].slug != FIRST_MODULE:
        return [f"the course does not start with {FIRST_MODULE}"]
    if not modules[0].lessons:
        return [f"{FIRST_MODULE} has no lesson"]
    first = modules[0].lessons[0]
    if disclaimer not in normalised(first.body):
        return [f"{first.id} does not carry the disclaimer"]
    return []
```

**`tests/meta/markdown_text.py`** (new)

<!-- file: tests/meta/markdown_text.py -->
```python
"""Markdown as a reader sees it, for the guards that look for a sentence in a document."""

import re

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, quote markers and comments removed.

    A sentence inside an HTML comment is never shown to a reader, so it does not count.
    """
    shown = _COMMENT.sub(" ", markdown)
    lines = (line.strip().removeprefix(">").strip() for line in shown.splitlines())
    return " ".join(" ".join(lines).split())
```

**`tests/meta/test_disclaimer.py`** (changed: 2 edits)

<!-- edit: tests/meta/test_disclaimer.py -->
Replace:
```python

import re
from pathlib import Path

```
with:
```python

from pathlib import Path

from markdown_text import normalised

```

<!-- edit: tests/meta/test_disclaimer.py -->
Replace:
```python
INTERNAL = frozenset({"superpowers", "research"})
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, quote markers and comments removed.

    A disclaimer inside an HTML comment is never shown to a reader, so it does not count.
    """
    shown = _COMMENT.sub(" ", markdown)
    lines = (line.strip().removeprefix(">").strip() for line in shown.splitlines())
    return " ".join(" ".join(lines).split())

```
with:
```python
INTERNAL = frozenset({"superpowers", "research"})

```

**`tests/meta/test_lesson_rules.py`** (new)

<!-- file: tests/meta/test_lesson_rules.py -->
```python
"""The catalogue guards, proven on a fixture catalogue (T1 spec §8).

The fixture passes every guard, and each broken copy fails exactly the guard it breaks. The
guards run over the real lesson folders in ``test_lessons.py``.
"""

import shutil
from pathlib import Path

import pytest
from lesson_rules import missing_sources, start_here_problems, unexplained, unknown

from steadyhand import DISCLAIMER
from steadyhand.training import Catalogue

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/training"
KEYS = frozenset({"term.fixture_return", "fixture.note.gap", "fixture.lot.size"})


def load(folder: Path) -> Catalogue:
    return Catalogue.load([folder / "engine/en", folder / "idx/en"], folder / "course.toml")


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    return Path(shutil.copytree(FIXTURE, tmp_path / "training"))


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} is not in {path.name} exactly once"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_the_fixture_passes_every_guard() -> None:
    catalogue = load(FIXTURE)
    assert len(catalogue.lessons()) == 3
    assert unexplained(catalogue, KEYS) == []
    assert unknown(catalogue, KEYS) == []
    assert missing_sources(catalogue, ROOT) == []
    assert start_here_problems(catalogue, DISCLAIMER) == []


def test_a_key_with_no_lesson_is_found() -> None:
    assert unexplained(load(FIXTURE), KEYS | {"fixture.new.key"}) == ["fixture.new.key"]


def test_a_lesson_explaining_a_key_that_does_not_exist_is_found() -> None:
    assert unknown(load(FIXTURE), KEYS - {"fixture.lot.size"}) == ["fixture.lots: fixture.lot.size"]


@pytest.mark.parametrize(
    "source",
    ["docs/nowhere.md", "docs/nowhere.md §3", "docs", "/etc/hosts", "../steadyhand/README.md"],
)
def test_a_source_that_is_not_a_repo_file_is_found(copy: Path, source: str) -> None:
    edit(copy / "engine/en/fixture.returns.md", '"README.md"', f'"{source}"')
    assert missing_sources(load(copy), ROOT) == [f"fixture.returns: {source}"]


def test_a_source_with_a_section_is_checked_by_its_path() -> None:
    lesson = load(FIXTURE).lesson("fixture.returns")
    assert "docs/lq45-members.md §2" in lesson.sources
    assert missing_sources(load(FIXTURE), ROOT) == []


def test_a_start_lesson_without_the_disclaimer_is_found(copy: Path) -> None:
    edit(copy / "engine/en/start.welcome.md", "You can lose money.", "You can lose.")
    assert start_here_problems(load(copy), DISCLAIMER) == [
        "start.welcome does not carry the disclaimer"
    ]


def test_a_disclaimer_hidden_in_a_comment_does_not_count(copy: Path) -> None:
    edit(copy / "engine/en/start.welcome.md", "> steadyhand is", "<!--\n> steadyhand is")
    edit(copy / "engine/en/start.welcome.md", "You can lose money.", "You can lose money. -->")
    assert start_here_problems(load(copy), DISCLAIMER) == [
        "start.welcome does not carry the disclaimer"
    ]


def test_a_course_that_does_not_open_with_start_here_is_found(copy: Path) -> None:
    edit(copy / "course.toml", 'slug = "start-here"', 'slug = "begin"')
    edit(copy / "engine/en/start.welcome.md", '"start-here"', '"begin"')
    assert start_here_problems(load(copy), DISCLAIMER) == [
        "the course does not start with start-here"
    ]


def test_a_start_module_with_no_lesson_is_found(copy: Path) -> None:
    edit(copy / "engine/en/start.welcome.md", 'module = "start-here"\nposition = 1\n', "")
    assert start_here_problems(load(copy), DISCLAIMER) == ["start-here has no lesson"]
```

**`tests/meta/test_public_api.py`** (changed: 5 edits)

<!-- edit: tests/meta/test_public_api.py -->
Replace:
```python
The expected set is derived from the source, not listed, so a new public class cannot be
forgotten from ``__all__``.
"""
```
with:
```python
The expected set is derived from the source, not listed, so a new public class cannot be
forgotten from ``__all__``. The one exception is ``steadyhand.training``: only the output layer
may import it (T1 spec §5), so ``steadyhand`` must not re-export it, and its public names are
importable from ``steadyhand.training`` instead.
"""
```

<!-- edit: tests/meta/test_public_api.py -->
Replace:
```python
import steadyhand

```
with:
```python
import steadyhand
import steadyhand.training

```

<!-- edit: tests/meta/test_public_api.py -->
Replace:
```python
CONSTANT = re.compile(r"[A-Z][A-Z0-9_]*")


def public_modules() -> list[str]:
    modules: list[str] = []
    for path in sorted((SRC / "steadyhand").rglob("*.py")):
        parts = path.relative_to(SRC).with_suffix("").parts
        if any(part.startswith("_") for part in parts):
            continue  # private modules, and __init__ files, which only re-export
        modules.append(".".join(parts))
    return modules
```
with:
```python
CONSTANT = re.compile(r"[A-Z][A-Z0-9_]*")
TRAINING = "steadyhand.training"


def public_modules(package: str = "steadyhand") -> list[str]:
    """The public modules under *package*. For ``steadyhand`` that leaves out training."""
    modules: list[str] = []
    for path in sorted((SRC / package.replace(".", "/")).rglob("*.py")):
        parts = path.relative_to(SRC).with_suffix("").parts
        if any(part.startswith("_") for part in parts):
            continue  # private modules, and __init__ files, which only re-export
        name = ".".join(parts)
        if package != TRAINING and (name == TRAINING or name.startswith(f"{TRAINING}.")):
            continue
        modules.append(name)
    return modules
```

<!-- edit: tests/meta/test_public_api.py -->
Replace:
```python

def definitions() -> dict[str, str]:
    """Every public name, mapped to the module that defines it."""
    found: dict[str, str] = {}
    for module in public_modules():
        path = SRC / (module.replace(".", "/") + ".py")
```
with:
```python

def definitions(package: str = "steadyhand") -> dict[str, str]:
    """Every public name under *package*, mapped to the module that defines it."""
    found: dict[str, str] = {}
    for module in public_modules(package):
        path = SRC / (module.replace(".", "/") + ".py")
```

<!-- edit: tests/meta/test_public_api.py -->
Replace:
```python
    assert extra == []
```
with:
```python
    assert extra == []


def test_training_is_left_out_of_the_engine_and_exports_its_own_names() -> None:
    assert not any(module.startswith(TRAINING) for module in public_modules())
    found = definitions(TRAINING)
    assert {"Catalogue", "Lesson", "LessonError"} <= set(found)
    assert sorted(set(found) ^ set(steadyhand.training.__all__)) == []
    wrong = sorted(
        name
        for name, module in found.items()
        if getattr(steadyhand.training, name) is not getattr(importlib.import_module(module), name)
    )
    assert wrong == []
    assert not set(found) & set(steadyhand.__all__)
```

**`tests/training/test_catalogue.py`** (new)

<!-- file: tests/training/test_catalogue.py -->
```python
"""The lesson loader: every rule of T1 spec §4.1, and the course file (§4.3).

Each malformed case writes a good catalogue with exactly one file changed, and asserts that the
``LessonError`` names that file and the field, not only that something was raised.
"""

from pathlib import Path

import pytest

from steadyhand.training import Catalogue, Lesson, LessonError, LessonNotFoundError, Module

GOOD = {
    "engine/start.welcome.md": (
        'id = "start.welcome"\ntitle = "Welcome"\nsummary = "What this software is."\n'
        'explains = []\nmodule = "start-here"\nposition = 1'
    ),
    "engine/income.run_rate.md": (
        'id = "income.run_rate"\ntitle = "Run-rate"\nsummary = "What holdings pay in a year."\n'
        'explains = ["term.run_rate"]\nmodule = "income-goal"\nposition = 1\n'
        'see_also = ["idx.lots"]\nsources = ["README.md"]'
    ),
    "engine/data.gaps.md": (
        'id = "data.gaps"\ntitle = "Gaps in the data"\nsummary = "Why a day can be missing."\n'
        'explains = ["data.bar.missing", "data.bar.refused"]'
    ),
    "idx/idx.lots.md": (
        'id = "idx.lots"\ntitle = "Lots"\nsummary = "Shares trade in lots of 100."\n'
        'explains = ["idx.lot.size"]\nmodule = "how-idx-works"\nposition = 1'
    ),
    "idx/idx.ticks.md": (
        'id = "idx.ticks"\ntitle = "Tick sizes"\nsummary = "Prices move in fixed steps."\n'
        'explains = ["idx.tick.size"]\nmodule = "how-idx-works"\nposition = 2'
    ),
}
COURSE = (
    '[[module]]\nnumber = 1\nslug = "start-here"\ntitle = "Start here"\n\n'
    '[[module]]\nnumber = 2\nslug = "how-idx-works"\ntitle = "How IDX works"\n\n'
    '[[module]]\nnumber = 3\nslug = "income-goal"\ntitle = "The income goal"\n\n'
    '[[module]]\nnumber = 4\nslug = "strategies"\ntitle = "Strategies"\n'
)


def lesson_text(header: str, body: str = "Some words about it.") -> str:
    return f"+++\n{header}\n+++\n\n{body}\n"


def changed(path: str, old: str, new: str) -> str:
    """The good header of *path* with *old* replaced once by *new*: the case's one defect."""
    assert GOOD[path].count(old) == 1, f"{old!r} is not in {path} exactly once"
    return lesson_text(GOOD[path].replace(old, new))


def build(
    tmp_path: Path, files: dict[str, str | None] | None = None, course: str = COURSE
) -> Catalogue:
    texts: dict[str, str | None] = {name: lesson_text(header) for name, header in GOOD.items()}
    texts.update(files or {})
    for name, text in texts.items():
        if text is not None:
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "course.toml").write_text(course, encoding="utf-8")
    return Catalogue.load([tmp_path / "engine", tmp_path / "idx"], tmp_path / "course.toml")


def test_a_good_catalogue_loads(tmp_path: Path) -> None:
    catalogue = build(tmp_path)
    assert [lesson.id for lesson in catalogue.lessons()] == [
        "data.gaps",
        "idx.lots",
        "idx.ticks",
        "income.run_rate",
        "start.welcome",
    ]
    run_rate = catalogue.lesson("income.run_rate")
    assert run_rate == Lesson(
        id="income.run_rate",
        title="Run-rate",
        summary="What holdings pay in a year.",
        explains=("term.run_rate",),
        module="income-goal",
        position=1,
        see_also=("idx.lots",),
        sources=("README.md",),
        body="Some words about it.",
        origin=str(tmp_path / "engine/income.run_rate.md"),
    )
    assert catalogue.for_key("data.bar.refused") is catalogue.lesson("data.gaps")
    assert catalogue.for_key("idx.lot.size") is catalogue.lesson("idx.lots")
    assert [(m.number, m.slug, m.title) for m in catalogue.course()] == [
        (1, "start-here", "Start here"),
        (2, "how-idx-works", "How IDX works"),
        (3, "income-goal", "The income goal"),
        (4, "strategies", "Strategies"),
    ]
    how = catalogue.course()[1]
    assert how == Module(
        2,
        "how-idx-works",
        "How IDX works",
        (catalogue.lesson("idx.lots"), catalogue.lesson("idx.ticks")),
    )
    assert catalogue.course()[3].lessons == ()


def test_lessons_are_found_in_subfolders_and_other_files_are_ignored(tmp_path: Path) -> None:
    catalogue = build(
        tmp_path,
        {
            "engine/start.welcome.md": None,
            "engine/deeper/start.welcome.md": lesson_text(GOOD["engine/start.welcome.md"]),
            "engine/notes.txt": "not a lesson",
        },
    )
    assert catalogue.lesson("start.welcome").origin.endswith("deeper/start.welcome.md")
    assert len(catalogue.lessons()) == len(GOOD)


def test_a_file_with_windows_line_endings_reads_the_same(tmp_path: Path) -> None:
    text = lesson_text(GOOD["idx/idx.lots.md"], "First line.\n\nSecond line.")
    catalogue = build(tmp_path, {"idx/idx.lots.md": text.replace("\n", "\r\n")})
    assert catalogue.lesson("idx.lots").body == "First line.\n\nSecond line."
    assert catalogue.lesson("idx.lots").summary == "Shares trade in lots of 100."


def test_a_byte_order_mark_is_not_part_of_the_header(tmp_path: Path) -> None:
    text = "\ufeff" + lesson_text(GOOD["idx/idx.lots.md"])
    catalogue = build(tmp_path, {"idx/idx.lots.md": text}, course="\ufeff" + COURSE)
    assert catalogue.lesson("idx.lots").title == "Lots"
    assert len(catalogue.course()) == 4


def test_titles_and_summaries_at_their_limits_load(tmp_path: Path) -> None:
    title, summary = "T" * 60, "S" * 159 + "."
    catalogue = build(
        tmp_path,
        {
            "idx/idx.lots.md": changed("idx/idx.lots.md", '"Lots"', f'"{title}"'),
            "idx/idx.ticks.md": changed(
                "idx/idx.ticks.md", '"Prices move in fixed steps."', f'"{summary}"'
            ),
        },
    )
    assert catalogue.lesson("idx.lots").title == title
    assert catalogue.lesson("idx.ticks").summary == summary


def test_text_outside_ascii_loads(tmp_path: Path) -> None:
    text = changed("idx/idx.lots.md", '"Lots"', '"Lot — 100 lembar"')
    assert build(tmp_path, {"idx/idx.lots.md": text}).lesson("idx.lots").title == "Lot — 100 lembar"


LOTS = "idx/idx.lots.md"
TICKS = "idx/idx.ticks.md"
RUN = "engine/income.run_rate.md"

LESSON_CASES = [
    ("no opening fence", LOTS, GOOD[LOTS] + "\n+++\n\nBody.\n", "header"),
    ("no closing fence", LOTS, f"+++\n{GOOD[LOTS]}\n\nBody.\n", "header"),
    ("not TOML", LOTS, lesson_text(GOOD[LOTS] + "\nthis is not toml"), "header"),
    ("no body", LOTS, f"+++\n{GOOD[LOTS]}\n+++\n\n  \n", "body"),
    ("unknown field", LOTS, changed(LOTS, "position = 1", 'position = 1\nlevel = "new"'), "level"),
    ("no id", LOTS, changed(LOTS, 'id = "idx.lots"\n', ""), "id"),
    ("no title", LOTS, changed(LOTS, 'title = "Lots"\n', ""), "title"),
    (
        "no summary",
        LOTS,
        changed(LOTS, 'summary = "Shares trade in lots of 100."\n', ""),
        "summary",
    ),
    ("no explains", LOTS, changed(LOTS, 'explains = ["idx.lot.size"]\n', ""), "explains"),
    ("id not a key", LOTS, changed(LOTS, '"idx.lots"', '"Idx.Lots"'), "id"),
    ("id not a string", LOTS, changed(LOTS, '"idx.lots"', "3"), "id"),
    ("id not the file name", LOTS, changed(LOTS, '"idx.lots"', '"idx.lot"'), "id"),
    ("empty title", LOTS, changed(LOTS, '"Lots"', '"  "'), "title"),
    ("long title", LOTS, changed(LOTS, '"Lots"', '"' + "T" * 61 + '"'), "title"),
    ("title on two lines", LOTS, changed(LOTS, '"Lots"', '"Lots\\nof them"'), "title"),
    ("title not text", LOTS, changed(LOTS, '"Lots"', "7"), "title"),
    ("summary without a stop", LOTS, changed(LOTS, 'of 100."', 'of 100"'), "summary"),
    (
        "summary of two sentences",
        LOTS,
        changed(LOTS, "Shares trade", "Yes. Shares trade"),
        "summary",
    ),
    (
        "long summary",
        LOTS,
        changed(LOTS, '"Shares trade in lots of 100."', '"' + "S" * 160 + '."'),
        "summary",
    ),
    ("explains not a list", LOTS, changed(LOTS, '["idx.lot.size"]', '"idx.lot.size"'), "explains"),
    ("explains a bad key", LOTS, changed(LOTS, '["idx.lot.size"]', '["lot size"]'), "explains"),
    (
        "explains a key twice",
        LOTS,
        changed(LOTS, '["idx.lot.size"]', '["idx.lot.size", "idx.lot.size"]'),
        "explains",
    ),
    ("explains an empty entry", LOTS, changed(LOTS, '["idx.lot.size"]', '[""]'), "explains"),
    ("module without position", LOTS, changed(LOTS, "\nposition = 1", ""), "position"),
    ("position without module", LOTS, changed(LOTS, 'module = "how-idx-works"\n', ""), "module"),
    ("module not a slug", LOTS, changed(LOTS, '"how-idx-works"', '"How IDX"'), "module"),
    ("module not in the course", LOTS, changed(LOTS, '"how-idx-works"', '"costs"'), "module"),
    ("position zero", LOTS, changed(LOTS, "position = 1", "position = 0"), "position"),
    ("position true", LOTS, changed(LOTS, "position = 1", "position = true"), "position"),
    ("position as text", LOTS, changed(LOTS, "position = 1", 'position = "1"'), "position"),
    ("position repeated", TICKS, changed(TICKS, "position = 2", "position = 1"), "position"),
    ("position gap", TICKS, changed(TICKS, "position = 2", "position = 3"), "position"),
    ("see_also unresolved", RUN, changed(RUN, '["idx.lots"]', '["idx.lot"]'), "see_also"),
    ("see_also itself", RUN, changed(RUN, '["idx.lots"]', '["income.run_rate"]'), "see_also"),
    ("see_also not a list", RUN, changed(RUN, '["idx.lots"]', '"idx.lots"'), "see_also"),
    ("sources empty entry", RUN, changed(RUN, '["README.md"]', '[" "]'), "sources"),
    ("sources not a list", RUN, changed(RUN, '["README.md"]', '"README.md"'), "sources"),
    ("sources not text", RUN, changed(RUN, '["README.md"]', "[1]"), "sources"),
]


@pytest.mark.parametrize(
    ("path", "text", "field"),
    [case[1:] for case in LESSON_CASES],
    ids=[case[0] for case in LESSON_CASES],
)
def test_a_broken_lesson_names_its_file_and_field(
    tmp_path: Path, path: str, text: str, field: str
) -> None:
    with pytest.raises(LessonError) as raised:
        build(tmp_path, {path: text})
    assert (raised.value.origin, raised.value.field) == (str(tmp_path / path), field)
    assert str(raised.value).startswith(f"{tmp_path / path}: {field}: ")


def test_an_id_used_in_both_packages_names_the_second_file(tmp_path: Path) -> None:
    copy = lesson_text(GOOD[LOTS].replace('["idx.lot.size"]', "[]"))
    with pytest.raises(LessonError) as raised:
        build(tmp_path, {"idx/deeper/idx.lots.md": copy})
    first, second = sorted([str(tmp_path / LOTS), str(tmp_path / "idx/deeper/idx.lots.md")])
    assert (raised.value.origin, raised.value.field) == (second, "id")
    assert raised.value.problem == f"idx.lots is also {first}"


def test_a_key_explained_by_two_lessons_names_the_second(tmp_path: Path) -> None:
    text = changed(TICKS, '["idx.tick.size"]', '["idx.tick.size", "idx.lot.size"]')
    with pytest.raises(LessonError) as raised:
        build(tmp_path, {TICKS: text})
    assert (raised.value.origin, raised.value.field) == (str(tmp_path / TICKS), "explains")
    assert raised.value.problem == "idx.lot.size is already explained by idx.lots"


def test_a_missing_root_is_named(tmp_path: Path) -> None:
    build(tmp_path)
    missing = tmp_path / "nowhere"
    with pytest.raises(LessonError) as raised:
        Catalogue.load([tmp_path / "engine", missing], tmp_path / "course.toml")
    assert (raised.value.origin, raised.value.field) == (str(missing), "root")


COURSE_CASES = [
    ("not TOML", COURSE + "\nnot toml", "course"),
    ("unknown table", COURSE + "\n[extra]\nx = 1\n", "extra"),
    ("no modules", 'title = "x"\n', "title"),
    ("empty", "", "module"),
    ("module not a table list", "module = [1]\n", "module[1]"),
    ("number out of order", COURSE.replace("number = 2", "number = 3"), "module[2].number"),
    ("number true", COURSE.replace("number = 1", "number = true"), "module[1].number"),
    ("slug not a slug", COURSE.replace('"start-here"', '"Start here"'), "module[1].slug"),
    ("slug twice", COURSE.replace('"how-idx-works"', '"start-here"'), "module[2].slug"),
    ("no title", COURSE.replace('title = "Start here"\n', ""), "module[1].title"),
    ("long title", COURSE.replace('"Start here"', '"' + "T" * 61 + '"'), "module[1].title"),
    (
        "extra field",
        COURSE.replace('title = "Start here"', 'title = "Start here"\ncolour = 1'),
        "module[1].colour",
    ),
]


@pytest.mark.parametrize(
    ("course", "field"), [case[1:] for case in COURSE_CASES], ids=[case[0] for case in COURSE_CASES]
)
def test_a_broken_course_names_the_field(tmp_path: Path, course: str, field: str) -> None:
    with pytest.raises(LessonError) as raised:
        build(tmp_path, course=course)
    assert (raised.value.origin, raised.value.field) == (str(tmp_path / "course.toml"), field)


def test_an_unknown_id_names_the_closest(tmp_path: Path) -> None:
    catalogue = build(tmp_path)
    with pytest.raises(LessonNotFoundError) as raised:
        catalogue.lesson("idx.lot")
    assert raised.value.wanted == "idx.lot"
    assert raised.value.closest == ("idx.lots", "idx.ticks")
    assert str(raised.value) == "no lesson for 'idx.lot'; the closest: idx.lots, idx.ticks"


def test_an_id_like_nothing_names_no_closest(tmp_path: Path) -> None:
    with pytest.raises(LessonNotFoundError) as raised:
        build(tmp_path).lesson("zzzz")
    assert raised.value.closest == ()
    assert str(raised.value) == "no lesson for 'zzzz'"


def test_a_key_with_no_lesson_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(LessonNotFoundError) as raised:
        build(tmp_path).for_key("data.bar.missed")
    assert raised.value.closest[0] == "data.bar.missing"
```

**`tests/training/test_course.py`** (new)

<!-- file: tests/training/test_course.py -->
```python
"""The shipped course file: the eight modules of T1 spec §4.3, in order."""

from steadyhand.training import Catalogue
from steadyhand_idx.training import COURSE


def test_the_course_lists_the_eight_modules_in_order() -> None:
    modules = Catalogue.load([], COURSE).course()
    assert [(module.number, module.slug, module.title) for module in modules] == [
        (1, "start-here", "Start here"),
        (2, "shares-and-dividends", "Shares and dividends"),
        (3, "how-idx-works", "How IDX works"),
        (4, "costs-and-tax", "Costs and tax"),
        (5, "risk", "Risk, and why backtests mislead"),
        (6, "using-steadyhand", "Using steadyhand"),
        (7, "income-goal", "The income goal"),
        (8, "strategies", "Strategies"),
    ]
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py`** (new, as stubs)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py -->
```python
"""steadyhand_idx.training: the IDX distribution's lessons and its course (T1 spec §4.2, §4.3).

Like ``steadyhand.training``, only the output layer may import it, and it imports nothing that
decides what to trade (T1 spec §5).
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

COURSE: Traversable = files(__name__) / "course.toml"
"""The course's module list, shipped inside the wheel."""

__all__ = ["COURSE"]
```

**`packages/steadyhand/src/steadyhand/training/__init__.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/training/__init__.py -->
```python
"""steadyhand.training: lessons that explain what a report shows (T1 spec).

Only the output layer may import this package, and it imports nothing that decides what to
trade (T1 spec §5): the level a user picks changes how much is explained, never what the tool
suggests. It uses the standard library only.
"""

from steadyhand.training.catalogue import (
    Catalogue,
    Lesson,
    LessonError,
    LessonNotFoundError,
    Module,
)

__all__ = ["Catalogue", "Lesson", "LessonError", "LessonNotFoundError", "Module"]
```

**`packages/steadyhand/src/steadyhand/training/catalogue.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/training/catalogue.py -->
```python
"""The lesson catalogue: the lesson files, the course, and the rules they keep (T1 spec §4, §7).

A lesson is a Markdown file ``<id>.md`` whose TOML header sits between two ``+++`` lines.
``Catalogue.load`` reads every lesson under the roots it is given and the course file, checks
every rule of §4.1, and raises ``LessonError`` naming the file and the field of the first rule
broken. It reads only what it is given, as UTF-8 with or without a byte-order mark. Whether a
key a lesson explains exists, and whether a ``sources`` path exists, is for the catalogue guards
to check against the repo: an installed copy has neither the key modules' source nor the
repo's paths.
"""

from __future__ import annotations

import difflib
import re
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import cast

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
_SLUG = re.compile(r"[a-z]+(-[a-z]+)*")
_FENCE = "+++"
_TITLE_LIMIT = 60
_SUMMARY_LIMIT = 160
_CLOSEST = 3
_FIELDS = ("id", "title", "summary", "explains", "module", "position", "see_also", "sources")
_REQUIRED = ("id", "title", "summary", "explains")
_MODULE_FIELDS = ("number", "slug", "title")


class LessonError(ValueError):
    """A lesson file or the course file breaks a rule (T1 spec §4.1)."""

    def __init__(self, origin: str, field: str, problem: str) -> None:
        raise NotImplementedError("LessonError.__init__")


class LessonNotFoundError(LookupError):
    """No lesson has the id, or explains the key, that was asked for."""

    def __init__(self, wanted: str, closest: tuple[str, ...]) -> None:
        raise NotImplementedError("LessonNotFoundError.__init__")


@dataclass(frozen=True, slots=True)
class Lesson:
    """One lesson: its header fields, its Markdown body, and the file it came from."""

    id: str
    title: str
    summary: str
    explains: tuple[str, ...]
    module: str | None
    position: int | None
    see_also: tuple[str, ...]
    sources: tuple[str, ...]
    body: str
    origin: str


@dataclass(frozen=True, slots=True)
class Module:
    """One course module, and its lessons in course order. A module may be empty for now."""

    number: int
    slug: str
    title: str
    lessons: tuple[Lesson, ...]


class Catalogue:
    """Every lesson and the course, checked against each other. Build one with ``load``."""

    __slots__ = ("_by_id", "_by_key", "_modules")

    def __init__(self, lessons: Mapping[str, Lesson], modules: tuple[Module, ...]) -> None:
        raise NotImplementedError("Catalogue.__init__")

    @classmethod
    def load(cls, roots: Iterable[Traversable], course: Traversable) -> Catalogue:
        """Read every ``*.md`` under each root and the course file, and check every rule."""
        raise NotImplementedError("Catalogue.load")

    def lessons(self) -> tuple[Lesson, ...]:
        """Every lesson, by id."""
        raise NotImplementedError("Catalogue.lessons")

    def lesson(self, lesson_id: str) -> Lesson:
        """The lesson with *lesson_id*, or ``LessonNotFoundError`` naming the closest ids."""
        raise NotImplementedError("Catalogue.lesson")

    def for_key(self, key: str) -> Lesson:
        """The lesson that explains *key*. A key with no lesson is a bug (T1 spec §7)."""
        raise NotImplementedError("Catalogue.for_key")

    def course(self) -> tuple[Module, ...]:
        """The course's modules, in order."""
        raise NotImplementedError("Catalogue.course")


def _closest(wanted: str, names: Iterable[str]) -> tuple[str, ...]:
    raise NotImplementedError("_closest")


def _markdown_files(root: Traversable) -> Iterator[Traversable]:
    raise NotImplementedError("_markdown_files")


def _read_lesson(file: Traversable) -> Lesson:
    raise NotImplementedError("_read_lesson")


def _split(text: str, origin: str) -> tuple[dict[str, object], str]:
    """The TOML header and the body of a lesson file."""
    raise NotImplementedError("_split")


def _line(value: object, origin: str, field: str, limit: int) -> str:
    raise NotImplementedError("_line")


def _summary(value: object, origin: str) -> str:
    raise NotImplementedError("_summary")


def _key(value: object, origin: str, field: str) -> str:
    raise NotImplementedError("_key")


def _strings(value: object, origin: str, field: str) -> tuple[str, ...]:
    raise NotImplementedError("_strings")


def _keys(value: object, origin: str, field: str) -> tuple[str, ...]:
    raise NotImplementedError("_keys")


def _read_course(course: Traversable) -> tuple[tuple[int, str, str], ...]:
    """The course file's modules as (number, slug, title), numbered 1, 2, 3 … in file order."""
    raise NotImplementedError("_read_course")


def _modules(
    course: tuple[tuple[int, str, str], ...], lessons: Iterable[Lesson]
) -> tuple[Module, ...]:
    """Each course module with its lessons, positions running 1, 2, 3 … with no gap or repeat."""
    raise NotImplementedError("_modules")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=913 failed=76 -->
Expected: 913 run, 76 failed, every one `NotImplementedError`: the loader and course tests, and the guard tests, whose fixture catalogue cannot load. One passes against the stubs by design: `test_training_is_left_out_of_the_engine_and_exports_its_own_names` reads names, which the stubs keep.

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/training/course.toml`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/course.toml -->
```toml
# The steadyhand course: its modules in order (T1 spec §4.3). A lesson joins a module by giving
# its slug as `module` and its place as `position`. A module with no lessons yet is listed as
# "coming later".

[[module]]
number = 1
slug = "start-here"
title = "Start here"

[[module]]
number = 2
slug = "shares-and-dividends"
title = "Shares and dividends"

[[module]]
number = 3
slug = "how-idx-works"
title = "How IDX works"

[[module]]
number = 4
slug = "costs-and-tax"
title = "Costs and tax"

[[module]]
number = 5
slug = "risk"
title = "Risk, and why backtests mislead"

[[module]]
number = 6
slug = "using-steadyhand"
title = "Using steadyhand"

[[module]]
number = 7
slug = "income-goal"
title = "The income goal"

[[module]]
number = 8
slug = "strategies"
title = "Strategies"
```

**`packages/steadyhand/src/steadyhand/training/catalogue.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/training/catalogue.py -->
```python
"""The lesson catalogue: the lesson files, the course, and the rules they keep (T1 spec §4, §7).

A lesson is a Markdown file ``<id>.md`` whose TOML header sits between two ``+++`` lines.
``Catalogue.load`` reads every lesson under the roots it is given and the course file, checks
every rule of §4.1, and raises ``LessonError`` naming the file and the field of the first rule
broken. It reads only what it is given, as UTF-8 with or without a byte-order mark. Whether a
key a lesson explains exists, and whether a ``sources`` path exists, is for the catalogue guards
to check against the repo: an installed copy has neither the key modules' source nor the
repo's paths.
"""

from __future__ import annotations

import difflib
import re
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import cast

_KEY = re.compile(r"[a-z]+(\.[a-z_]+)+")
_SLUG = re.compile(r"[a-z]+(-[a-z]+)*")
_FENCE = "+++"
_TITLE_LIMIT = 60
_SUMMARY_LIMIT = 160
_CLOSEST = 3
_FIELDS = ("id", "title", "summary", "explains", "module", "position", "see_also", "sources")
_REQUIRED = ("id", "title", "summary", "explains")
_MODULE_FIELDS = ("number", "slug", "title")


class LessonError(ValueError):
    """A lesson file or the course file breaks a rule (T1 spec §4.1)."""

    def __init__(self, origin: str, field: str, problem: str) -> None:
        super().__init__(f"{origin}: {field}: {problem}")
        self.origin = origin
        self.field = field
        self.problem = problem


class LessonNotFoundError(LookupError):
    """No lesson has the id, or explains the key, that was asked for."""

    def __init__(self, wanted: str, closest: tuple[str, ...]) -> None:
        hint = f"; the closest: {', '.join(closest)}" if closest else ""
        super().__init__(f"no lesson for {wanted!r}{hint}")
        self.wanted = wanted
        self.closest = closest


@dataclass(frozen=True, slots=True)
class Lesson:
    """One lesson: its header fields, its Markdown body, and the file it came from."""

    id: str
    title: str
    summary: str
    explains: tuple[str, ...]
    module: str | None
    position: int | None
    see_also: tuple[str, ...]
    sources: tuple[str, ...]
    body: str
    origin: str


@dataclass(frozen=True, slots=True)
class Module:
    """One course module, and its lessons in course order. A module may be empty for now."""

    number: int
    slug: str
    title: str
    lessons: tuple[Lesson, ...]


class Catalogue:
    """Every lesson and the course, checked against each other. Build one with ``load``."""

    __slots__ = ("_by_id", "_by_key", "_modules")

    def __init__(self, lessons: Mapping[str, Lesson], modules: tuple[Module, ...]) -> None:
        self._by_id = dict(lessons)
        self._by_key = {key: lesson for lesson in lessons.values() for key in lesson.explains}
        self._modules = modules

    @classmethod
    def load(cls, roots: Iterable[Traversable], course: Traversable) -> Catalogue:
        """Read every ``*.md`` under each root and the course file, and check every rule."""
        slugs = _read_course(course)
        by_id: dict[str, Lesson] = {}
        by_key: dict[str, Lesson] = {}
        for root in roots:
            if not root.is_dir():
                raise LessonError(str(root), "root", "is not a folder")
            for file in _markdown_files(root):
                lesson = _read_lesson(file)
                first = by_id.setdefault(lesson.id, lesson)
                if first is not lesson:
                    raise LessonError(lesson.origin, "id", f"{lesson.id} is also {first.origin}")
                for key in lesson.explains:
                    owner = by_key.setdefault(key, lesson)
                    if owner is not lesson:
                        msg = f"{key} is already explained by {owner.id}"
                        raise LessonError(lesson.origin, "explains", msg)
        for lesson in by_id.values():
            for other in lesson.see_also:
                if other not in by_id:
                    raise LessonError(lesson.origin, "see_also", f"no lesson {other!r}")
        return cls(by_id, _modules(slugs, by_id.values()))

    def lessons(self) -> tuple[Lesson, ...]:
        """Every lesson, by id."""
        return tuple(self._by_id[name] for name in sorted(self._by_id))

    def lesson(self, lesson_id: str) -> Lesson:
        """The lesson with *lesson_id*, or ``LessonNotFoundError`` naming the closest ids."""
        found = self._by_id.get(lesson_id)
        if found is None:
            raise LessonNotFoundError(lesson_id, _closest(lesson_id, self._by_id))
        return found

    def for_key(self, key: str) -> Lesson:
        """The lesson that explains *key*. A key with no lesson is a bug (T1 spec §7)."""
        found = self._by_key.get(key)
        if found is None:
            raise LessonNotFoundError(key, _closest(key, self._by_key))
        return found

    def course(self) -> tuple[Module, ...]:
        """The course's modules, in order."""
        return self._modules


def _closest(wanted: str, names: Iterable[str]) -> tuple[str, ...]:
    return tuple(difflib.get_close_matches(wanted, sorted(names), n=_CLOSEST))


def _markdown_files(root: Traversable) -> Iterator[Traversable]:
    for entry in sorted(root.iterdir(), key=lambda found: found.name):
        if entry.is_dir():
            yield from _markdown_files(entry)
        elif entry.name.endswith(".md"):
            yield entry


def _read_lesson(file: Traversable) -> Lesson:
    origin = str(file)
    header, body = _split(file.read_text(encoding="utf-8-sig"), origin)
    for name in sorted(header):
        if name not in _FIELDS:
            raise LessonError(origin, name, "is not a lesson field")
    for name in _REQUIRED:
        if name not in header:
            raise LessonError(origin, name, "is required")
    lesson_id = _key(header["id"], origin, "id")
    if lesson_id != file.name.removesuffix(".md"):
        raise LessonError(origin, "id", f"{lesson_id} is not the file's name")
    module = header.get("module")
    position = header.get("position")
    if (module is None) != (position is None):
        missing = "position" if position is None else "module"
        raise LessonError(origin, missing, "module and position are given together or not at all")
    if module is not None and (not isinstance(module, str) or not _SLUG.fullmatch(module)):
        raise LessonError(origin, "module", f"{module!r} is not a module slug")
    if position is not None and (type(position) is not int or position < 1):
        raise LessonError(origin, "position", f"{position!r} is not a whole number from 1")
    see_also = _keys(header.get("see_also", []), origin, "see_also")
    if lesson_id in see_also:
        raise LessonError(origin, "see_also", "a lesson does not list itself")
    return Lesson(
        id=lesson_id,
        title=_line(header["title"], origin, "title", _TITLE_LIMIT),
        summary=_summary(header["summary"], origin),
        explains=_keys(header["explains"], origin, "explains"),
        module=module,
        position=position,
        see_also=see_also,
        sources=_strings(header.get("sources", []), origin, "sources"),
        body=body,
        origin=origin,
    )


def _split(text: str, origin: str) -> tuple[dict[str, object], str]:
    """The TOML header and the body of a lesson file."""
    lines = text.splitlines()
    if not lines or lines[0] != _FENCE:
        raise LessonError(origin, "header", f"the file does not start with a {_FENCE} line")
    try:
        end = lines.index(_FENCE, 1)
    except ValueError:
        raise LessonError(origin, "header", f"the header has no closing {_FENCE} line") from None
    try:
        header = tomllib.loads("\n".join(lines[1:end]))
    except tomllib.TOMLDecodeError as error:
        raise LessonError(origin, "header", f"is not valid TOML ({error})") from None
    body = "\n".join(lines[end + 1 :]).strip()
    if not body:
        raise LessonError(origin, "body", "the lesson has no text")
    return header, body


def _line(value: object, origin: str, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise LessonError(origin, field, "is not text")
    if not value.strip() or len(value) > limit or "\n" in value:
        raise LessonError(origin, field, f"is not one line of 1 to {limit} characters")
    return value


def _summary(value: object, origin: str) -> str:
    summary = _line(value, origin, "summary", _SUMMARY_LIMIT)
    if not summary.endswith(".") or ". " in summary:
        raise LessonError(origin, "summary", "is not one sentence ending in a full stop")
    return summary


def _key(value: object, origin: str, field: str) -> str:
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise LessonError(origin, field, f"{value!r} is not a dotted lowercase identifier")
    return value


def _strings(value: object, origin: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise LessonError(origin, field, "is not a list")
    items = tuple(cast("list[object]", value))
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise LessonError(origin, field, f"{item!r} is not text")
    if len(set(items)) != len(items):
        raise LessonError(origin, field, "lists an entry twice")
    return cast("tuple[str, ...]", items)


def _keys(value: object, origin: str, field: str) -> tuple[str, ...]:
    return tuple(_key(item, origin, field) for item in _strings(value, origin, field))


def _read_course(course: Traversable) -> tuple[tuple[int, str, str], ...]:
    """The course file's modules as (number, slug, title), numbered 1, 2, 3 … in file order."""
    origin = str(course)
    try:
        data = tomllib.loads(course.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as error:
        raise LessonError(origin, "course", f"is not valid TOML ({error})") from None
    extra = sorted(set(data) - {"module"})
    if extra:
        raise LessonError(origin, extra[0], "is not a course field")
    entries = data.get("module")
    if not isinstance(entries, list) or not entries:
        raise LessonError(origin, "module", "the course lists no modules")
    modules: list[tuple[int, str, str]] = []
    for number, entry in enumerate(cast("list[object]", entries), start=1):
        where = f"module[{number}]"
        if not isinstance(entry, dict):
            raise LessonError(origin, where, "is not a table")
        fields = cast("dict[str, object]", entry)
        for name in sorted(set(fields) ^ set(_MODULE_FIELDS)):
            problem = "is not a module field" if name in fields else "is required"
            raise LessonError(origin, f"{where}.{name}", problem)
        if type(fields["number"]) is not int or fields["number"] != number:
            raise LessonError(origin, f"{where}.number", f"is not {number}")
        slug = fields["slug"]
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
            raise LessonError(origin, f"{where}.slug", f"{slug!r} is not a module slug")
        if any(slug == seen for _, seen, _ in modules):
            raise LessonError(origin, f"{where}.slug", f"{slug} is listed twice")
        title = _line(fields["title"], origin, f"{where}.title", _TITLE_LIMIT)
        modules.append((number, slug, title))
    return tuple(modules)


def _modules(
    course: tuple[tuple[int, str, str], ...], lessons: Iterable[Lesson]
) -> tuple[Module, ...]:
    """Each course module with its lessons, positions running 1, 2, 3 … with no gap or repeat."""
    placed: dict[str, dict[int, Lesson]] = {slug: {} for _, slug, _ in course}
    for lesson in sorted(lessons, key=lambda found: found.origin):
        if lesson.module is None or lesson.position is None:
            continue
        if lesson.module not in placed:
            raise LessonError(lesson.origin, "module", f"{lesson.module} is not in the course")
        slots = placed[lesson.module]
        other = slots.setdefault(lesson.position, lesson)
        if other is not lesson:
            msg = f"{lesson.module} already has {other.id} at {lesson.position}"
            raise LessonError(lesson.origin, "position", msg)
    for slug, slots in placed.items():
        for expected, position in enumerate(sorted(slots), start=1):
            if position != expected:
                msg = f"{slug} has no lesson at {expected}, so {position} leaves a gap"
                raise LessonError(slots[position].origin, "position", msg)
    return tuple(
        Module(number, slug, title, tuple(placed[slug][p] for p in sorted(placed[slug])))
        for number, slug, title in course
    )
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 7.

<!-- check: gate total=913 passed=913 -->
Expected: every command exits 0; 913 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 13.3 s against the 30 s budget).

- [ ] **Step 7: Mutations.** Run M112–M121; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(training): T1 S2 the lesson catalogue and the course`, ending in `(#N)`).

---

### Task 3: T1 S3 The renderer and the legal line

**Acceptance criteria (story text):**
1. `Level` (`off`, `new`, `some`, `experienced`, the values `steadyhand.toml` stores) and `explain(catalogue, keys, level, program) -> str` in `steadyhand.training` (T1 §6 item 4, §7): at `new` the "What this means" block with one line per lesson, at `some` one "Learn more with … learn:" line, at `experienced` and `off` nothing, and with no keys nothing at every level.
2. One line per lesson however many of its keys were shown, in the order the keys first appeared, from both packages. A key with no lesson raises `LessonNotFoundError` at every level (scope decision 7). A string passed as the keys, a blank program name and wrong argument types are refused.
3. The renderer tests compare with hand-written expected text.
4. `tests/meta/test_legal_line.py` holds T1 §5's items 1, 2 and 4: no module of either package outside the training packages imports them (relative imports and `from steadyhand import training` included); each training package imports only its allowlist; and the advice scan finds the §5 phrases across line breaks, quote markers, HTML comments and curly apostrophes, naming the file and the phrase (scope decisions 8 and 9).
5. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and M122–M131 each turn the whole suite red; M122–M124 are T1 §8's named mutations.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/training/render.py`, `tests/meta/test_legal_line.py`, `tests/training/test_render.py`
- Modify: `.../steadyhand/training/__init__.py`, `tests/meta/lesson_rules.py`

**Interfaces:**
- Consumes: Task 2's `Catalogue.for_key`, `LessonNotFoundError`, `Lesson.id`, `.title`, `.summary`; the fixture catalogue.
- Produces: `Level(StrEnum)`; `explain(catalogue: Catalogue, keys: Iterable[str], level: Level, program: str) -> str`; in `lesson_rules.py`: `ADVICE_PHRASES`, `TICKER_ADVICE`, `advice_phrases(text: str) -> list[str]`, `advice_findings(catalogue) -> list[str]`.

- [ ] **Step 1: Branch.** `git switch -c t1/s3-renderer origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/meta/lesson_rules.py`** (changed: 2 edits)

<!-- edit: tests/meta/lesson_rules.py -->
Replace:
```python

from collections.abc import Set
```
with:
```python

import re
from collections.abc import Set
```

<!-- edit: tests/meta/lesson_rules.py -->
Replace:
```python
    return []
```
with:
```python
    return []


ADVICE_PHRASES = (
    "you should buy",
    "you should sell",
    "we recommend",
    "recommended stock",
    "best stock",
    "guaranteed",
    "can't lose",
    "cannot lose",
)
"""Advice phrasing, matched in any case (T1 spec §5 item 4). A backstop: the import rule is the
control."""

TICKER_ADVICE = re.compile(r"\b[A-Z]{4}\b(?:\W+\w+){0,2}?\W+(?i:buy|sell)\b")
"""A word of exactly four capital letters, followed within three words by buy or sell in any
case: a real IDX ticker used as advice. Lessons use made-up names such as "Stock A"."""


def advice_phrases(text: str) -> list[str]:
    """Every advice phrase in *text*: across line breaks and quote markers, with a curly
    apostrophe read as a straight one. HTML comments are scanned too, since the command line
    prints a lesson's body as it is written."""
    lines = (line.strip().removeprefix(">") for line in text.replace("\u2019", "'").splitlines())
    shown = " ".join(" ".join(lines).split())
    lowered = shown.casefold()
    found = [phrase for phrase in ADVICE_PHRASES if phrase in lowered]
    found += [match.group(0) for match in TICKER_ADVICE.finditer(shown)]
    return found


def advice_findings(catalogue: Catalogue) -> list[str]:
    """Every advice phrase in a lesson's title, summary or body, as ``file: phrase``."""
    return [
        f"{lesson.origin}: {phrase}"
        for lesson in catalogue.lessons()
        for text in (lesson.title, lesson.summary, lesson.body)
        for phrase in advice_phrases(text)
    ]
```

**`tests/meta/test_legal_line.py`** (new)

<!-- file: tests/meta/test_legal_line.py -->
```python
"""The legal line is structural (T1 spec §5): the level changes how much is explained, never what
the tool suggests trading.

1. Only the output layer may import training. No module of either package outside the two
   training packages imports either of them (the CLI's output layer joins the exceptions in M5).
   This covers any new module, a strategy or a broker say, without anyone listing it.
2. Training imports nothing that decides: only the standard library and a short allowlist.
4. The advice-phrase backstop over every lesson's title, summary and body.

Imports are read from the AST, relative ones resolved, so a comment or a docstring that names a
module is never a finding.
"""

import ast
import shutil
import sys
from pathlib import Path

import pytest
from key_walk import ENGINE, IDX
from lesson_rules import ADVICE_PHRASES, advice_findings, advice_phrases

from steadyhand.training import Catalogue

TRAINING = ("steadyhand.training", "steadyhand_idx.training")
ENGINE_TRAINING_MAY_IMPORT = ("steadyhand.notes", "steadyhand.terms", "steadyhand._validate")
IDX_TRAINING_MAY_IMPORT = (
    *ENGINE_TRAINING_MAY_IMPORT,
    "steadyhand.training",
    "steadyhand_idx.notes",
)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/training"

type Statement = tuple[str, tuple[str, ...]]
"""One import statement: the module it names, and for ``from`` imports the names it takes."""


def module_name(path: Path) -> str:
    """The dotted name of a source file of either package."""
    for package in (ENGINE, IDX):
        if package in path.parents:
            parts = path.relative_to(package.parent).with_suffix("").parts
            return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    msg = f"{path} is not in either package"
    raise ValueError(msg)


def statements(source: str, module: str, *, is_package: bool) -> list[Statement]:
    """Every import statement in *source*, each module resolved to its absolute name."""
    package = module if is_package else module.rpartition(".")[0]
    found: list[Statement] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [(alias.name, ()) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                base = f"{parent}.{base}" if base else parent
            found.append((base, tuple(alias.name for alias in node.names)))
    return found


def _within(name: str, modules: tuple[str, ...]) -> bool:
    return any(name == module or name.startswith(f"{module}.") for module in modules)


def imports_training(statement: Statement) -> bool:
    base, names = statement
    return _within(base, TRAINING) or any(_within(f"{base}.{name}", TRAINING) for name in names)


def allowed(statement: Statement, allowlist: tuple[str, ...], own: str) -> bool:
    def ok(name: str) -> bool:
        return name.split(".", maxsplit=1)[0] in sys.stdlib_module_names or _within(
            name, (*allowlist, own)
        )

    base, names = statement
    return ok(base) or (bool(names) and all(ok(f"{base}.{name}") for name in names))


def sources() -> list[tuple[str, bool, str]]:
    """Every module of both packages: (dotted name, is a package, source)."""
    paths = sorted([*ENGINE.rglob("*.py"), *IDX.rglob("*.py")])
    return [(module_name(p), p.name == "__init__.py", p.read_text(encoding="utf-8")) for p in paths]


def test_the_module_names_are_resolved_from_paths() -> None:
    assert module_name(ENGINE / "__init__.py") == "steadyhand"
    assert module_name(ENGINE / "broker/simulated.py") == "steadyhand.broker.simulated"
    assert module_name(IDX / "training/__init__.py") == "steadyhand_idx.training"
    with pytest.raises(ValueError, match="is not in either package"):
        module_name(Path("/elsewhere/x.py"))


def test_the_training_import_detector() -> None:
    source = (
        "import steadyhand.training\n"
        "from steadyhand import training\n"
        "from steadyhand.training.render import explain\n"
        "from steadyhand_idx.training import COURSE\n"
        "import steadyhand.trainingx\n"
        "from steadyhand import Money\n"
        '"""import steadyhand.training"""\n'
    )
    found = statements(source, "steadyhand.engine", is_package=False)
    assert [imports_training(statement) for statement in found] == [
        True,
        True,
        True,
        True,
        False,
        False,
    ]


def test_relative_imports_are_resolved() -> None:
    assert statements("from .training import explain\n", "steadyhand", is_package=True) == [
        ("steadyhand.training", ("explain",))
    ]
    assert statements("from . import training\n", "steadyhand", is_package=True) == [
        ("steadyhand", ("training",))
    ]
    assert statements(
        "from ..training import x\n", "steadyhand.broker.simulated", is_package=False
    ) == [("steadyhand.training", ("x",))]
    assert statements(
        "from . import catalogue\n", "steadyhand.training.render", is_package=False
    ) == [("steadyhand.training", ("catalogue",))]
    assert all(
        imports_training(s)
        for s in statements(
            "from . import training\nfrom .training import e\n", "steadyhand", is_package=True
        )
    )


@pytest.mark.parametrize(
    ("line", "ok"),
    [
        ("import re", True),
        ("from __future__ import annotations", True),
        ("from collections.abc import Iterable", True),
        ("from steadyhand.notes import Note", True),
        ("from steadyhand import notes", True),
        ("from steadyhand._validate import require_type", True),
        ("from steadyhand.training.catalogue import Catalogue", True),
        ("from . import catalogue", True),
        ("from steadyhand.risk import RiskLimits", False),
        ("from steadyhand import Money", False),
        ("from steadyhand import notes, risk", False),
        ("import steadyhand", False),
        ("import yaml", False),
        ("from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP", False),
    ],
)
def test_the_engine_training_allowlist(line: str, *, ok: bool) -> None:
    (statement,) = statements(line, "steadyhand.training.render", is_package=False)
    assert allowed(statement, ENGINE_TRAINING_MAY_IMPORT, "steadyhand.training") is ok


@pytest.mark.parametrize(
    ("line", "ok"),
    [
        ("from steadyhand.training import Catalogue", True),
        ("from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP", True),
        ("from importlib.resources import files", True),
        ("from steadyhand_idx.universe import Lq45Universe", False),
        ("from steadyhand_idx import Lq45Universe", False),
        ("from steadyhand.backtest import backtest", False),
    ],
)
def test_the_idx_training_allowlist(line: str, *, ok: bool) -> None:
    (statement,) = statements(line, "steadyhand_idx.training", is_package=True)
    assert allowed(statement, IDX_TRAINING_MAY_IMPORT, "steadyhand_idx.training") is ok


def test_only_training_imports_training() -> None:
    modules = sources()
    inside = [name for name, _, _ in modules if _within(name, TRAINING)]
    assert len(modules) >= 40
    assert {"steadyhand.training", "steadyhand_idx.training"} <= set(inside)
    found = [
        f"{name}: {base}"
        for name, is_package, source in modules
        if not _within(name, TRAINING)
        for base, names in statements(source, name, is_package=is_package)
        if imports_training((base, names))
    ]
    assert found == []


def test_training_imports_nothing_that_decides() -> None:
    checked = 0
    found: list[str] = []
    for name, is_package, source in sources():
        for own, allowlist in zip(
            TRAINING, (ENGINE_TRAINING_MAY_IMPORT, IDX_TRAINING_MAY_IMPORT), strict=True
        ):
            if not _within(name, (own,)):
                continue
            for statement in statements(source, name, is_package=is_package):
                checked += 1
                if not allowed(statement, allowlist, own):
                    found.append(f"{name}: {statement[0]}")
    assert checked >= 8, "no training module's imports were read"
    assert found == []


@pytest.mark.parametrize("phrase", ADVICE_PHRASES)
def test_each_advice_phrase_is_found_in_any_case(phrase: str) -> None:
    assert advice_phrases(f"Here {phrase.upper()} it is.") == [phrase]


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("BBCA is a buy.", ["BBCA is a buy"]),
        ("Then TLKM, you sell.", ["TLKM, you sell"]),
        ("ASII looks cheap, BUY", ["ASII looks cheap, BUY"]),
        ("UNVR one two three sell", []),
        ("Stock A is one you might buy.", []),
        ("The IDX lets you buy in lots.", []),
        ("BBCAX is a buy.", []),
        ("bbca is a buy.", []),
        ("BBCA is a buyer.", []),
    ],
)
def test_a_ticker_followed_by_buy_or_sell_is_found(text: str, found: list[str]) -> None:
    assert advice_phrases(text) == found


def test_a_phrase_is_found_across_lines_quotes_and_curly_apostrophes() -> None:
    assert advice_phrases("You should\n> buy it.") == ["you should buy"]
    assert advice_phrases("You can" + chr(0x2019) + "t lose.") == ["can't lose"]
    assert advice_phrases("<!-- we recommend it -->") == ["we recommend"]


def test_the_fixture_lessons_carry_no_advice() -> None:
    catalogue = Catalogue.load([FIXTURE / "engine/en", FIXTURE / "idx/en"], FIXTURE / "course.toml")
    assert len(catalogue.lessons()) == 3
    assert advice_findings(catalogue) == []


def test_an_advice_finding_names_the_file_and_the_phrase(tmp_path: Path) -> None:
    copy = Path(shutil.copytree(FIXTURE, tmp_path / "training"))
    lesson = copy / "idx/en/fixture.lots.md"
    lesson.write_text(lesson.read_text(encoding="utf-8") + "\nYou should buy lots.\n", "utf-8")
    catalogue = Catalogue.load([copy / "engine/en", copy / "idx/en"], copy / "course.toml")
    assert advice_findings(catalogue) == [f"{lesson}: you should buy"]
```

**`tests/training/test_render.py`** (new)

<!-- file: tests/training/test_render.py -->
```python
"""The inline explanation for each level (T1 spec §6 item 4), with hand-written expected text.

The fixture catalogue has an engine lesson explaining two keys (a term and a note) and an IDX
lesson explaining one, so one run covers dedup, first-appearance order and both packages.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from steadyhand.training import Catalogue, LessonNotFoundError, Level, explain

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/training"
PROGRAM = "steadyhand-idx"
SHOWN = ["fixture.lot.size", "term.fixture_return", "fixture.note.gap", "fixture.lot.size"]


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load([FIXTURE / "engine/en", FIXTURE / "idx/en"], FIXTURE / "course.toml")


def test_new_gives_a_line_per_lesson_in_first_appearance_order(catalogue: Catalogue) -> None:
    assert explain(catalogue, SHOWN, Level.NEW, PROGRAM) == (
        "What this means\n"
        "• Lots: Shares are bought in lots of a fixed size. "
        "More: steadyhand-idx learn fixture.lots\n"
        "• Returns: How much a portfolio gained or lost. "
        "More: steadyhand-idx learn fixture.returns"
    )


def test_some_names_the_lessons_only(catalogue: Catalogue) -> None:
    assert explain(catalogue, SHOWN, Level.SOME, PROGRAM) == (
        "Learn more with steadyhand-idx learn: fixture.lots, fixture.returns"
    )


def test_two_keys_of_one_lesson_give_one_line(catalogue: Catalogue) -> None:
    shown = ["fixture.note.gap", "term.fixture_return"]
    assert explain(catalogue, shown, Level.NEW, PROGRAM) == (
        "What this means\n"
        "• Returns: How much a portfolio gained or lost. "
        "More: steadyhand-idx learn fixture.returns"
    )
    assert explain(catalogue, shown, Level.SOME, PROGRAM) == (
        "Learn more with steadyhand-idx learn: fixture.returns"
    )


@pytest.mark.parametrize("level", [Level.EXPERIENCED, Level.OFF])
def test_experienced_and_off_show_nothing(catalogue: Catalogue, level: Level) -> None:
    assert explain(catalogue, SHOWN, level, PROGRAM) == ""


@pytest.mark.parametrize("level", list(Level))
def test_no_keys_show_nothing_at_every_level(catalogue: Catalogue, level: Level) -> None:
    assert explain(catalogue, [], level, PROGRAM) == ""


@pytest.mark.parametrize("level", list(Level))
def test_an_unknown_key_is_a_bug_at_every_level(catalogue: Catalogue, level: Level) -> None:
    with pytest.raises(LessonNotFoundError, match=r"'fixture.lot.sise'"):
        explain(catalogue, ["fixture.note.gap", "fixture.lot.sise"], level, PROGRAM)


def test_the_program_name_is_the_callers(catalogue: Catalogue) -> None:
    assert explain(catalogue, ["fixture.lot.size"], Level.NEW, "sh") == (
        "What this means\n"
        "• Lots: Shares are bought in lots of a fixed size. More: sh learn fixture.lots"
    )


def test_keys_may_be_read_once(catalogue: Catalogue) -> None:
    def shown() -> Iterator[str]:
        yield from SHOWN

    assert explain(catalogue, shown(), Level.SOME, PROGRAM) == (
        "Learn more with steadyhand-idx learn: fixture.lots, fixture.returns"
    )


def test_the_levels_are_the_settings_values() -> None:
    assert [level.value for level in Level] == ["off", "new", "some", "experienced"]
    assert Level("some") is Level.SOME


def test_bad_arguments_are_refused(catalogue: Catalogue) -> None:
    with pytest.raises(TypeError, match=r"^level must be a Level, got str$"):
        explain(catalogue, SHOWN, "new", PROGRAM)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^keys is the keys the output showed, not one key$"):
        explain(catalogue, "fixture.lot.size", Level.NEW, PROGRAM)
    with pytest.raises(TypeError, match=r"^a key must be a str, got int$"):
        explain(catalogue, [3], Level.NEW, PROGRAM)  # type: ignore[list-item]
    with pytest.raises(
        ValueError, match=r"^program is the command the user types, and it is blank$"
    ):
        explain(catalogue, SHOWN, Level.NEW, " ")
    with pytest.raises(TypeError, match=r"^program must be a str, got NoneType$"):
        explain(catalogue, SHOWN, Level.NEW, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^catalogue must be a Catalogue, got dict$"):
        explain({}, SHOWN, Level.NEW, PROGRAM)  # type: ignore[arg-type]
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/training/__init__.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/training/__init__.py -->
Replace:
```python
)

__all__ = ["Catalogue", "Lesson", "LessonError", "LessonNotFoundError", "Module"]
```
with:
```python
)
from steadyhand.training.render import Level, explain

__all__ = [
    "Catalogue",
    "Lesson",
    "LessonError",
    "LessonNotFoundError",
    "Level",
    "Module",
    "explain",
]
```

**`packages/steadyhand/src/steadyhand/training/render.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/training/render.py -->
```python
"""How much explanation goes under a command's output, by the user's level (T1 spec §6).

``explain`` returns the text and the caller prints it. The level changes only how much is
explained; nothing here can see, or change, what a command suggests (T1 spec §5).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from steadyhand._validate import require_type
from steadyhand.training.catalogue import Catalogue, Lesson

_HEADING = "What this means"
_BULLET = "•"


class Level(StrEnum):
    """How much a user wants explained. The values are what ``steadyhand.toml`` stores."""

    OFF = "off"
    NEW = "new"
    SOME = "some"
    EXPERIENCED = "experienced"


def explain(catalogue: Catalogue, keys: Iterable[str], level: Level, program: str) -> str:
    """The explanation for the keys a command's output showed, or ``""`` (T1 spec §6 item 4).

    *keys* come in the order the output first showed them. Each lesson appears once, however
    many of its keys were shown. Every key is looked up whatever the level, so a key with no
    lesson raises ``LessonNotFoundError`` at every level: it is a bug, not a setting.
    """
    raise NotImplementedError("explain")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=975 failed=16 -->
Expected: 975 run, 16 failed, every one `NotImplementedError`: the renderer tests. The tests of `test_legal_line.py` pass against the stubs by design. They check detectors written in the test itself, and a repo whose imports and fixture lessons already keep the legal line; mutations M122–M131 prove each can go red. `test_the_levels_are_the_settings_values` passes too: `Level` is an enum, which the stubs keep.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/training/render.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/training/render.py -->
```python
"""How much explanation goes under a command's output, by the user's level (T1 spec §6).

``explain`` returns the text and the caller prints it. The level changes only how much is
explained; nothing here can see, or change, what a command suggests (T1 spec §5).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from steadyhand._validate import require_type
from steadyhand.training.catalogue import Catalogue, Lesson

_HEADING = "What this means"
_BULLET = "•"


class Level(StrEnum):
    """How much a user wants explained. The values are what ``steadyhand.toml`` stores."""

    OFF = "off"
    NEW = "new"
    SOME = "some"
    EXPERIENCED = "experienced"


def explain(catalogue: Catalogue, keys: Iterable[str], level: Level, program: str) -> str:
    """The explanation for the keys a command's output showed, or ``""`` (T1 spec §6 item 4).

    *keys* come in the order the output first showed them. Each lesson appears once, however
    many of its keys were shown. Every key is looked up whatever the level, so a key with no
    lesson raises ``LessonNotFoundError`` at every level: it is a bug, not a setting.
    """
    require_type(catalogue, Catalogue, "catalogue")
    require_type(level, Level, "level")
    require_type(program, str, "program")
    if isinstance(keys, str):
        msg = "keys is the keys the output showed, not one key"
        raise TypeError(msg)
    if not program.strip():
        msg = "program is the command the user types, and it is blank"
        raise ValueError(msg)
    lessons: dict[str, Lesson] = {}
    for key in keys:
        require_type(key, str, "a key")
        lesson = catalogue.for_key(key)
        lessons.setdefault(lesson.id, lesson)
    if not lessons or level in (Level.OFF, Level.EXPERIENCED):
        return ""
    if level is Level.SOME:
        return f"Learn more with {program} learn: {', '.join(lessons)}"
    lines = [
        f"{_BULLET} {lesson.title}: {lesson.summary} More: {program} learn {lesson.id}"
        for lesson in lessons.values()
    ]
    return "\n".join([_HEADING, *lines])
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 7.

<!-- check: gate total=975 passed=975 -->
Expected: every command exits 0; 975 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 11.9 s against the 30 s budget).

- [ ] **Step 7: Mutations.** Run M122–M131; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(training): T1 S3 the renderer and the legal line`, ending in `(#N)`).

---

### Task 4: T1 S4 The lessons, the course content and the built-wheel check

**Acceptance criteria (story text):**
1. 33 lessons: 18 in `steadyhand/training/lessons/en/` (market-neutral, scope decision 13) and 15 in `steadyhand_idx/training/lessons/en/`. Every note and term key is explained by exactly one lesson. Course modules 1–5 and 7 and the backtest half of module 6 have lessons; module 8 is empty.
2. The "Start here" lesson carries the disclaimer verbatim.
3. Every IDX rule value a lesson states is copied from the research document it names in `sources`, and every `sources` path exists.
4. `steadyhand.training.LESSONS`, `steadyhand_idx.training.LESSONS` and `steadyhand_idx.training.catalogue()` load both packages' lessons from inside the installed packages (scope decision 2).
5. `tests/meta/test_lessons.py` switches every catalogue guard on over the real lessons, with the advice scan, the market-neutral check, the module check, and T1 §6's own example rendered exactly as written.
6. CI's `build` job installs both wheels into a clean venv, loads `catalogue()` from them, and asserts every lesson came from `site-packages` and that their count equals the `*.md` files in both source lesson folders.
7. `README.md` mentions the course and the `learn` command M5 adds, gains a Contributing section with the lesson rule, and its stale status line is corrected; both package READMEs mention their lessons.
8. Every lesson is read against core spec §3 item 3 before merge: it explains, and never tells the reader what to trade.
9. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and M132–M139 each turn red (M138 by hand, in the build step).

**Files:**
- Create: the 33 lessons; `tests/meta/test_lessons.py`
- Modify: `.../steadyhand/training/__init__.py`, `.../steadyhand_idx/training/__init__.py`, `tests/meta/test_public_api.py`, `.github/workflows/ci.yml`, `README.md`, `packages/steadyhand/README.md`, `packages/steadyhand-idx/README.md`

**Interfaces:**
- Consumes: everything from Tasks 1–3; `key_walk.all_keys()`.
- Produces: `steadyhand.training.LESSONS: Traversable`; `steadyhand_idx.training.LESSONS: Traversable`; `steadyhand_idx.training.catalogue() -> Catalogue`.

The lessons, by module (`E` is the engine's folder, `I` the IDX folder):

| # | Module | Lessons, in course order |
|---|---|---|
| 1 | Start here | `start.welcome` (I), `start.explanations` (I) |
| 2 | Shares and dividends | `shares.basics`, `shares.prices`, `shares.cost_basis`, `dividends.basics`, `shares.splits` (all E) |
| 3 | How IDX works | `idx.lots`, `idx.ticks`, `idx.auto_reject`, `idx.sessions`, `idx.settlement`, `idx.special_monitoring`, `idx.universe` (all I) |
| 4 | Costs and tax | `costs.trading`, `costs.sale_tax`, `costs.stamp_duty`, `tax.dividend`, `tax.exemption` (all I) |
| 5 | Risk, and why backtests mislead | `risk.drawdown`, `risk.returns`, `risk.limits`, `risk.backtests_mislead` (E), `idx.survivorship` (I) |
| 6 | Using steadyhand | `backtest.basics`, `backtest.report`, `backtest.data_gaps` (all E); paper trading in M5 |
| 7 | The income goal | `income.received`, `income.run_rate`, `income.calendar`, `income.growth`, `income.goal`, `income.projection` (all E) |
| 8 | Strategies | none yet (M6–M9) |

- [ ] **Step 1: Branch.** `git switch -c t1/s4-content origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/meta/test_lessons.py`** (new)

<!-- file: tests/meta/test_lessons.py -->
```python
"""The catalogue guards, switched on over the real lessons of both packages (T1 spec §8).

``catalogue()`` loading at all proves every rule ``Catalogue.load`` checks: ids unique across
both packages and equal to their file names, each key explained at most once, every
``see_also`` resolved, every course position in place. The tests below add what needs the repo.
After T1, a story that adds a note or a term key cannot merge until its lesson exists.
"""

from pathlib import Path

import pytest
from key_walk import ENGINE, IDX, all_keys
from lesson_rules import (
    advice_findings,
    missing_sources,
    start_here_problems,
    unexplained,
    unknown,
)

from steadyhand import DISCLAIMER
from steadyhand.training import Catalogue, Level, explain
from steadyhand_idx.training import catalogue

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = (ENGINE / "training/lessons/en", IDX / "training/lessons/en")
NOT_NEUTRAL = ("Rp", "IDX", "Indonesia", "steadyhand-idx")


@pytest.fixture(scope="module")
def real() -> Catalogue:
    return catalogue()


def test_every_lesson_file_is_loaded(real: Catalogue) -> None:
    files = sorted(path for folder in FOLDERS for path in folder.rglob("*.md"))
    assert len(files) >= 30
    assert len(real.lessons()) == len(files)
    assert all(any(path.is_relative_to(folder) for folder in FOLDERS) for path in files)


def test_every_key_has_a_lesson(real: Catalogue) -> None:
    keys = all_keys()
    assert len(keys) >= 40
    assert unexplained(real, keys) == []


def test_no_lesson_explains_a_key_that_does_not_exist(real: Catalogue) -> None:
    assert sum(len(lesson.explains) for lesson in real.lessons()) >= 40
    assert unknown(real, all_keys()) == []


def test_every_source_is_a_repo_file(real: Catalogue) -> None:
    assert sum(len(lesson.sources) for lesson in real.lessons()) >= 20
    assert missing_sources(real, ROOT) == []


def test_the_course_opens_with_the_disclaimer(real: Catalogue) -> None:
    assert start_here_problems(real, DISCLAIMER) == []


def test_no_lesson_carries_advice_phrasing(real: Catalogue) -> None:
    assert advice_findings(real) == []


def test_the_engine_lessons_are_market_neutral(real: Catalogue) -> None:
    engine = [lesson for lesson in real.lessons() if Path(lesson.origin).is_relative_to(FOLDERS[0])]
    assert len(engine) >= 10
    found = [
        f"{lesson.id}: {word}"
        for lesson in engine
        for word in NOT_NEUTRAL
        if word in f"{lesson.title} {lesson.summary} {lesson.body}"
    ]
    assert found == []


def test_the_modules_written_in_t1_have_lessons(real: Catalogue) -> None:
    counts = {module.slug: len(module.lessons) for module in real.course()}
    written = [slug for slug in counts if slug != "strategies"]
    assert len(written) == 7
    assert [slug for slug in written if counts[slug] == 0] == []
    assert counts["strategies"] == 0


def test_the_spec_example_renders_as_written(real: Catalogue) -> None:
    assert explain(real, ["term.run_rate"], Level.NEW, "steadyhand-idx") == (
        "What this means\n"
        "• Run-rate: What the dividends you hold now would pay over a year if nothing changed. "
        "More: steadyhand-idx learn income.run_rate"
    )
```

**`tests/meta/test_public_api.py`** (changed: 1 edit)

<!-- edit: tests/meta/test_public_api.py -->
Replace:
```python
    assert not any(module.startswith(TRAINING) for module in public_modules())
    found = definitions(TRAINING)
    assert {"Catalogue", "Lesson", "LessonError"} <= set(found)
    assert sorted(set(found) ^ set(steadyhand.training.__all__)) == []
```
with:
```python
    assert not any(module.startswith(TRAINING) for module in public_modules())
    # The training package defines its lesson root in its own __init__, as well as re-exporting.
    own = SRC / "steadyhand/training/__init__.py"
    found = {
        **definitions(TRAINING),
        **dict.fromkeys(public_definitions(own.read_text(encoding="utf-8")), TRAINING),
    }
    assert {"Catalogue", "Lesson", "LessonError", "LESSONS"} <= set(found)
    assert sorted(set(found) ^ set(steadyhand.training.__all__)) == []
```


- [ ] **Step 3: Write the stubs.** The lesson roots are constants; `catalogue()` is new.

**`packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py -->
Replace:
```python

COURSE: Traversable = files(__name__) / "course.toml"
"""The course's module list, shipped inside the wheel."""

__all__ = ["COURSE"]
```
with:
```python

from steadyhand.training import LESSONS as ENGINE_LESSONS
from steadyhand.training import Catalogue

COURSE: Traversable = files(__name__) / "course.toml"
"""The course's module list, shipped inside the wheel."""

LESSONS: Traversable = files(__name__) / "lessons" / "en"
"""The IDX lessons, shipped inside the wheel."""


def catalogue() -> Catalogue:
    """Both packages' lessons and the course, loaded and checked (T1 spec §7)."""
    raise NotImplementedError("catalogue")


__all__ = ["COURSE", "LESSONS", "catalogue"]
```

**`packages/steadyhand/src/steadyhand/training/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/training/__init__.py -->
Replace:
```python
"""

```
with:
```python
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

```

<!-- edit: packages/steadyhand/src/steadyhand/training/__init__.py -->
Replace:
```python

__all__ = [
    "Catalogue",
```
with:
```python

LESSONS: Traversable = files(__name__) / "lessons" / "en"
"""The engine's lessons: the market-neutral ones, shipped inside the wheel (T1 spec §4.2)."""

__all__ = [
    "LESSONS",
    "Catalogue",
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=984 failed=9 -->
Expected: 984 run, 9 failed, every one on setup with `NotImplementedError: catalogue`: the nine tests of `test_lessons.py`, whose fixture calls the stubbed `catalogue()`. The lessons, the build step and the READMEs are the implementation, so none of them is there yet. `test_training_is_left_out_of_the_engine_and_exports_its_own_names` passes against the stubs: `LESSONS` is a constant.

- [ ] **Step 5: Implement, and write the lessons.** Each IDX rule value below was copied from the research document its lesson cites.

**`.github/workflows/ci.yml`** (changed: 1 edit)

<!-- edit: .github/workflows/ci.yml -->
Replace:
```yaml
          "${RUNNER_TEMP}/engine-only/bin/python" -c "import steadyhand; print(steadyhand.__version__)"

```
with:
```yaml
          "${RUNNER_TEMP}/engine-only/bin/python" -c "import steadyhand; print(steadyhand.__version__)"
      - name: Both wheels ship every lesson, and the catalogue loads from them
        run: |
          expected="$(find packages/*/src/*/training/lessons -name '*.md' | wc -l)"
          test "${expected}" -gt 0
          uv venv "${RUNNER_TEMP}/lessons"
          uv pip install --python "${RUNNER_TEMP}/lessons" dist/*.whl
          cd "${RUNNER_TEMP}"
          "${RUNNER_TEMP}/lessons/bin/python" - "${expected}" <<'PY'
          import sys
          from steadyhand_idx.training import catalogue
          lessons = catalogue().lessons()
          outside = [lesson.origin for lesson in lessons if "site-packages" not in lesson.origin]
          assert outside == [], outside
          assert len(lessons) == int(sys.argv[1]), (len(lessons), sys.argv[1])
          print(len(lessons), "lessons load from the installed wheels")
          PY

```

**`README.md`** (changed: 3 edits)

<!-- edit: README.md -->
Replace:
```markdown

**Design phase. There is no usable code yet.** The approved design for the first sub-project is in
[`docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`](docs/superpowers/specs/2026-09-24-steadyhand-core-design.md).
```
with:
```markdown

**Early development.** The engine library, the IDX rules, the backtester, income reporting and the
lesson catalogue are built; the command line (`steadyhand-idx`) comes next. The approved design
for the first sub-project is in
[`docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`](docs/superpowers/specs/2026-09-24-steadyhand-core-design.md).
```

<!-- edit: README.md -->
Replace:
```markdown
- `steadyhand-idx`: the IDX distribution, with IDX trading rules, Yahoo Finance `.JK` data, paper trading, a CLI, and an income goal tracker that shows when dividends could cover a monthly target.

```
with:
```markdown
- `steadyhand-idx`: the IDX distribution, with IDX trading rules, Yahoo Finance `.JK` data, paper trading, a CLI, and an income goal tracker that shows when dividends could cover a monthly target.
- A course for first-time investors, and plain-English explanations under each command's output at the level you choose, or none. The lessons already ship inside both packages; the `steadyhand-idx learn` command that shows them arrives with the CLI.

```

<!-- edit: README.md -->
Replace:
```markdown

## Licence
```
with:
```markdown

## Contributing

Every sentence a report says beyond its figures, and every figure it shows, carries a stable key,
and each key is explained by exactly one lesson in `packages/*/src/*/training/lessons/en/`. A pull
request that adds a note key or a term key must add its lesson in the same pull request: CI fails
until it does. A lesson that states an IDX rule value copies it from a research document under
`docs/research/` and names that document in its `sources`.

## Licence
```

**`packages/steadyhand-idx/README.md`** (changed: 1 edit)

<!-- edit: packages/steadyhand-idx/README.md -->
Replace:
```markdown

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
```
with:
```markdown

It ships a course for first-time investors, with lessons on how IDX works, its costs and its
taxes. The `steadyhand-idx learn` command that shows them arrives with the CLI.

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py -->
Replace:
```python
    """Both packages' lessons and the course, loaded and checked (T1 spec §7)."""
    raise NotImplementedError("catalogue")

```
with:
```python
    """Both packages' lessons and the course, loaded and checked (T1 spec §7)."""
    return Catalogue.load([ENGINE_LESSONS, LESSONS], COURSE)

```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/costs.sale_tax.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/costs.sale_tax.md -->
```markdown
+++
id = "costs.sale_tax"
title = "The 0.1% sale tax"
summary = "Every sale of shares on IDX pays a final tax of 0.1% of its value, and buying pays none."
explains = ["term.sale_tax"]
module = "costs-and-tax"
position = 2
see_also = ["costs.trading"]
sources = ["docs/research/t-fees.md §2"]
+++

When you sell shares on IDX, 0.1% of the sale's value is taken as tax. Selling Rp10,000,000 of
shares pays Rp10,000 of tax. Buying pays no tax.

It is charged on the sale's **value**, not on any profit, so a sale at a loss pays it just the
same. The exchange collects it through your broker, who takes it from the
money the sale brings in, so you never pay it separately.

The rate has been 0.1% throughout the years steadyhand's data covers.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/costs.stamp_duty.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/costs.stamp_duty.md -->
```markdown
+++
id = "costs.stamp_duty"
title = "Stamp duty"
summary = "A fixed Rp10,000 charge on a day's trade confirmation when that day's trades are worth more than Rp10,000,000."
explains = ["term.daily_cost"]
module = "costs-and-tax"
position = 3
see_also = ["costs.trading"]
sources = ["docs/research/t-fees.md §3"]
+++

Each day you trade, your broker sends a **trade confirmation**, a document listing that day's
trades. Indonesian law charges a stamp duty of Rp10,000 on it. Since 12 January 2022, a
confirmation worth Rp10,000,000 or less is exempt.

steadyhand books it as a **daily cost**: one charge per day, not per trade, and only on days
whose trades pass the threshold.

On small trades it is the largest cost there is. A Rp11,000,000 trade pays about 0.09% in stamp
duty alone, while a Rp100,000,000 trade pays 0.01%. A small portfolio that trades often can lose
a noticeable part of its value this way.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/costs.trading.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/costs.trading.md -->
```markdown
+++
id = "costs.trading"
title = "What a trade costs"
summary = "Every trade pays the broker's fee and the exchange's levy on top of its value, and a sale also pays tax."
explains = ["term.broker_fee", "term.levy", "term.trading_costs"]
module = "costs-and-tax"
position = 1
see_also = ["costs.sale_tax", "costs.stamp_duty", "backtest.report"]
sources = ["docs/research/t-fees.md §1", "docs/research/t-fees.md §4"]
+++

Buying or selling shares costs money on top of the trade's value. On IDX there are three parts:

- **The broker's fee**, also called commission: what your broker charges for placing the order.
  Each broker sets its own rate, as a percentage of the trade's value, and charges VAT on it.
- **The levy**: the exchange's charges, which the broker collects and passes on. Since
  1 April 2022 it is 0.0433% of the trade's value on each side, buying or selling. It is made up
  of the exchange's fee (0.018%), the clearing house's fee (0.009%), the settlement fee (0.003%),
  VAT on those three, and a guarantee fund contribution (0.010%).
- **The sale tax**: 0.1% of the value of every sale. Its own lesson explains it.

The **trading costs** of a trade are all three added up.

Retail brokers usually quote one all-in rate for each side. One broker's quote checked in 2026
was 0.1513% to buy and 0.2513% to sell, including the levy, the VAT and the sale tax. steadyhand
records what each broker preset's rate already includes, so nothing is charged twice. Check the
preset you use against your own broker's fee page.

Costs look small, but they are paid on every trade. A strategy that trades often can lose more to
costs than it gains.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.auto_reject.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.auto_reject.md -->
```markdown
+++
id = "idx.auto_reject"
title = "Auto-rejection: how far a price may move in a day"
summary = "The exchange refuses any order priced too far above or below the previous close."
explains = []
module = "how-idx-works"
position = 3
see_also = ["idx.ticks"]
sources = ["docs/research/t-rules.md §3"]
+++

To stop wild swings, the exchange refuses an order priced **more than** a set percentage above or
below a reference price, normally the previous day's close. A price exactly on the limit is
accepted. The limits are called **auto-rejection** bands.

The upper limit depends on the price:

| Previous close | Highest accepted rise |
|---|---|
| up to Rp200 | 35% |
| over Rp200 to Rp5,000 | 25% |
| over Rp5,000 | 20% |

The lower limit has changed several times. It has been 15% at every price since 8 April 2025,
and from 1 January 2027 it becomes the same as the upper limit in each price range. From
28 September 2026 the lowest price a share may trade at is Rp1 instead of Rp50, and a share
priced Rp1 to Rp10 may move by Rp1 either way instead of by a percentage.

So until the end of 2026 a stock can fall at most about 15% in a day, however bad the news.
If sellers want lower prices, the stock stops at the limit and the selling carries on the next
day. steadyhand also uses the bands to spot impossible price data.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.lots.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.lots.md -->
```markdown
+++
id = "idx.lots"
title = "Lots: shares come in hundreds"
summary = "On the Indonesia Stock Exchange you buy and sell shares in lots of 100."
explains = []
module = "how-idx-works"
position = 1
see_also = ["idx.ticks"]
sources = ["docs/research/t-rules.md §1"]
+++

On the Indonesia Stock Exchange (IDX), shares trade in **lots**. One lot is 100 shares, and an
order on the regular market must be for whole lots: 100, 200 or 1,000 shares, never 150.

So the smallest purchase of a stock is one lot. At a price of Rp4,000 a share, one lot costs
Rp400,000 before costs.

This matters most when a portfolio is small. If a strategy wants Rp300,000 of that stock, it
cannot buy it: the nearest amounts are nothing or Rp400,000. steadyhand always rounds a planned
purchase **down** to whole lots, and drops any order smaller than one lot, so some cash can be
left unspent.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.sessions.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.sessions.md -->
```markdown
+++
id = "idx.sessions"
title = "Trading hours"
summary = "When the Indonesia Stock Exchange is open, and how the day's opening and closing prices are set."
explains = []
module = "how-idx-works"
position = 4
see_also = ["backtest.basics"]
sources = ["docs/research/t-rules.md §5"]
+++

The regular market's hours, in Western Indonesia Time:

| | Monday to Thursday | Friday |
|---|---|---|
| Pre-opening: orders gathered, then matched at one price | 08:45 to 08:59:59 | same |
| Session I | 09:00 to 12:00 | 09:00 to 11:30 |
| Session II | 13:30 to 15:49:59 | 14:00 to 15:49:59 |
| Pre-closing: orders gathered for the closing price | 15:50 to 15:59:59 | same |
| Post-closing: trading at the closing price | 16:02 to 16:15 | same |

The **opening price** comes from the pre-opening auction, and the **closing price** from the
pre-closing one. In each, orders are collected for a few minutes and then matched at a single
price.

steadyhand works with a day's opening and closing prices, not with the minutes in between. In a
backtest, an order decided after one day's close is filled at the next day's opening price.
The exchange is closed at weekends and on its published holidays.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.settlement.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.settlement.md -->
```markdown
+++
id = "idx.settlement"
title = "Settlement: when money and shares change hands"
summary = "A trade on IDX settles two trading days after it is made, so a sale's cash cannot be spent until then."
explains = ["term.settled_cash", "term.unsettled_cash"]
module = "how-idx-works"
position = 5
see_also = ["idx.lots"]
sources = ["docs/research/t-rules.md §7", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.2"]
+++

When your order fills, the trade is agreed at once, but the money and the shares move later. On
IDX that happens on the second trading day after the trade, called **T+2**. A sale on Monday
settles on Wednesday, and a sale on Friday settles on Tuesday, if no holiday falls between.

So steadyhand tracks cash in two parts:

- **Settled cash** has arrived and can be spent.
- **Unsettled cash** is money from a sale that has not arrived yet.

Only settled cash is spent on new purchases. If a strategy sells one stock to buy another, the
purchase may have to wait until the sale's cash settles.

The portfolio's value counts both, because the unsettled money is yours: it is only on its way.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.special_monitoring.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.special_monitoring.md -->
```markdown
+++
id = "idx.special_monitoring"
title = "The Special Monitoring Board"
summary = "Stocks the exchange watches closely trade differently, and steadyhand leaves them out by default."
explains = []
module = "how-idx-works"
position = 6
see_also = ["idx.universe"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §3", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.4", "docs/research/t-rules.md §3"]
+++

The exchange places some stocks it is watching closely on the **Special Monitoring Board**
(Papan Pemantauan Khusus). Stocks there trade in a call auction for the whole day: orders are
collected and matched at set times, not continuously.

steadyhand leaves these stocks out by default. It never buys one, and if you hold one, it
freezes the holding and flags it so that you decide what to do. It does not model the board's
auctions, and staying out keeps a strategy clear of the stocks the exchange itself is worried
about.

The data steadyhand uses cannot tell it which stocks are on the board, so you keep that list
yourself, in the exclusions file in your data folder, with the dates you added each one.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.survivorship.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.survivorship.md -->
```markdown
+++
id = "idx.survivorship"
title = "Survivorship bias"
summary = "Testing on today's stock list, or a list with gaps, makes the past look better than it was."
explains = ["universe.survivorship.gap"]
module = "risk"
position = 5
see_also = ["idx.universe", "risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.4"]
+++

The companies on a list today are the ones that did well enough to be there. The ones that
shrank, failed or were taken off are missing. Run a backtest on today's list and those losers
never appear, so the past looks kinder than it was. This is **survivorship bias**.

steadyhand avoids most of it by using the LQ45 list that was in effect on each day of a backtest,
not today's. That only works if your file holds every list.

**When the lists have a gap.** If two lists in your file are more than one review apart,
steadyhand does not know who joined and left in between. It keeps using the earlier list until
the later one takes effect, and the backtest warns you, naming the gap. A stock that joined and
left inside the gap never appears, so the result may look better than a real investor's would
have. Filling the gap in your file removes the warning.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.ticks.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.ticks.md -->
```markdown
+++
id = "idx.ticks"
title = "Tick sizes: the steps a price moves in"
summary = "A price on IDX moves in fixed steps, and the step is larger for dearer shares."
explains = []
module = "how-idx-works"
position = 2
see_also = ["idx.lots", "idx.auto_reject"]
sources = ["docs/research/t-rules.md §1", "docs/research/t-hist.md §6"]
+++

A share price cannot be any number. It moves in fixed steps called **ticks**, and the size of
the step depends on the price:

| Price | Tick |
|---|---|
| below Rp200 | Rp1 |
| Rp200 to below Rp500 | Rp2 |
| Rp500 to below Rp2,000 | Rp5 |
| Rp2,000 to below Rp5,000 | Rp10 |
| Rp5,000 and above | Rp25 |

So a stock at Rp4,990 can be offered at Rp4,990 or Rp5,000, but not at Rp4,995, and a stock at
Rp5,000 moves to Rp5,025 next, not Rp5,010. The step is set by the price of the order itself.

These steps have been the same since at least March 2020. steadyhand keeps them, with their
dates, in a data file rather than in its code, so a change to the rules is a change to the data.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.universe.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/idx.universe.md -->
```markdown
+++
id = "idx.universe"
title = "The LQ45"
summary = "The LQ45 is the exchange's list of 45 large, easily traded stocks, and steadyhand's default choice of stocks."
explains = []
module = "how-idx-works"
position = 7
see_also = ["idx.survivorship"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §9.4"]
+++

The **LQ45** is a list the exchange keeps of 45 large stocks that trade a lot every day. Its
members change at regular reviews: every six months until January 2024, and every three months
from May 2024. A member can also be replaced between reviews.

steadyhand's strategies choose from the LQ45 by default. Large, busy stocks are easier to buy
and sell at a fair price, even in small amounts.

The exchange's terms do not allow its data to be passed on for commercial use without its
permission, so steadyhand does not ship the lists. You supply the file yourself, in your data folder, with each list and the date it
took effect. A backtest uses whichever list was in effect on each day it replays.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/start.explanations.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/start.explanations.md -->
```markdown
+++
id = "start.explanations"
title = "How the explanations work"
summary = "How much steadyhand explains under its output, and how to change it or read a lesson."
explains = []
module = "start-here"
position = 2
see_also = ["start.welcome"]
sources = ["docs/superpowers/specs/2026-09-27-training-design.md §6"]
+++

The first time you set steadyhand up, it asks whether you would like explanations as you go and,
if so, how much investing experience you have. Your answer sets how much it explains under
each command's output:

- **New**: a one-line explanation of each figure and note the output showed, with the lesson to
  read for more.
- **Some**: just the names of the lessons to read.
- **Experienced**: nothing extra.
- **Off**: no explanations at all.

Your level changes only how much is explained. It never changes what steadyhand shows, suggests
or does.

You can change it at any time: `steadyhand-idx training` shows the setting, and
`steadyhand-idx training new`, `some`, `experienced` or `off` changes it.

The lessons also form a course. `steadyhand-idx learn` lists its modules in order, and
`steadyhand-idx learn <lesson>` prints one lesson, such as `steadyhand-idx learn
income.run_rate`.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/start.welcome.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/start.welcome.md -->
```markdown
+++
id = "start.welcome"
title = "Start here"
summary = "What steadyhand is, what it is not, and the one thing to know before anything else."
explains = []
module = "start-here"
position = 1
see_also = ["start.explanations", "shares.basics"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §1.3", "docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §3"]
+++

> steadyhand is example software that you run yourself, on your own account, and you make your
> own decisions with it. It is not financial advice. You can lose money.

**What it is.** steadyhand is a toolkit you run on your own computer. It tests investment
strategies on past prices (a backtest), and runs them on today's prices without real money
(paper trading), so you can see how they behave before you decide anything. It is built for one
goal in particular: growing a portfolio's dividend income over many years.

**What it is not.** It is not a service, a broker or an adviser. Nobody else sees your money or
your data. Its strategies are examples that show how a set of rules behaves, not
recommendations to follow.

**It never trades for you.** When you invest real money, you place every order yourself, in
your own broker's app. steadyhand can suggest an order and record what you actually did, and
that is all.

**You can lose money.** Share prices fall, sometimes a long way and for a long time. Companies
cut their dividends. A strategy that did well in the past can do badly next. Only invest money
you can leave alone through a bad stretch.

The lessons that follow explain the ideas behind every number steadyhand shows, one at a time.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.dividend.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.dividend.md -->
```markdown
+++
id = "tax.dividend"
title = "Tax on dividends"
summary = "Dividends from Indonesian companies carry a 10% final tax for resident individuals, which the investor pays."
explains = ["term.dividend_tax", "term.dividend_net", "term.take_home"]
module = "costs-and-tax"
position = 4
see_also = ["tax.exemption", "dividends.basics", "income.goal"]
sources = ["docs/research/t-tax.md §1", "docs/research/t-tax.md §2", "docs/superpowers/specs/2026-09-26-m4-income-design.md §2"]
+++

For a resident individual, a dividend from an Indonesian company is taxed at **10%**, and the tax
is final.

Nothing is taken off before the money reaches you: the company pays the dividend in full, and
your account receives the gross amount. If the tax is due, you pay it yourself, by the 15th of
the following month. It is not due if you reinvest the dividend in Indonesia under the rules in
the next lesson.

steadyhand's figures:

- **Dividend tax** is the tax steadyhand books. By default it books the full 10% of every
  dividend on its pay date, as if you had paid it.
- **Net dividend** is the gross dividend less the tax booked.
- **Take-home** is the gross dividend less the full 10%, whatever was booked. The income goal
  uses it, because money you live on is money you are not reinvesting, so it cannot be exempt.

A dividend of Rp1,000,000 therefore shows a take-home of Rp900,000.
```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md`** (new)

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md -->
```markdown
+++
id = "tax.exemption"
title = "The dividend tax exemption"
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = []
module = "costs-and-tax"
position = 5
see_also = ["tax.dividend"]
sources = ["docs/research/t-tax.md §3", "docs/research/t-tax.md §4", "docs/research/t-tax.md §5"]
+++

The 10% dividend tax is not due on a dividend that you invest in Indonesia. The rules, for a
resident individual:

- **The deadline.** Invest it by the end of March of the year after you received it. A dividend
  received in May 2026 must be invested by 31 March 2027.
- **What counts.** Buying shares on IDX qualifies, and so do several other Indonesian
  investments. Selling one qualifying investment to buy another keeps the exemption.
- **How long.** Keep it invested for at least three tax years. The rule counts them from the
  year the dividend was received, but whether that year itself counts is not settled, so the
  careful reading keeps it invested to the end of the second year after the one you invested
  in.
- **Paperwork.** You report the investment once a year through the tax office's online portal.
  The report is a condition of the exemption, not a formality.
- **Part of it.** Invest only part of a dividend and only that part is exempt; 10% is due on the
  rest.

If you miss a condition, the tax is owed as of the day you received the dividend, and penalties
can apply.

steadyhand cannot see your paperwork, or any investment you hold outside it. That is why it books
the full 10% by default: its income figures can only be too low, never too high. This lesson
describes the rules; whether they apply to you, and how, is a question for you or a tax adviser.
```

**`packages/steadyhand/README.md`** (changed: 1 edit)

<!-- edit: packages/steadyhand/README.md -->
Replace:
```markdown

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
```
with:
```markdown

It includes `steadyhand.training`: the lesson catalogue and the market-neutral lessons that a
front end, such as `steadyhand-idx`, shows its users.

Early development. See the [project repository](https://github.com/ShydenMcM/steadyhand).
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/backtest.basics.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/backtest.basics.md -->
```markdown
+++
id = "backtest.basics"
title = "What a backtest does"
summary = "A backtest runs a strategy day by day over past prices, with the same rules and costs as paper trading."
explains = []
module = "using-steadyhand"
position = 1
see_also = ["backtest.report", "risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §5"]
+++

A **backtest** asks: if I had run this strategy over these past years, what would have happened?

steadyhand answers it by stepping through the trading days one at a time. On each day it:

1. applies the day's corporate actions: splits, dividend entitlements, and dividends paid;
2. fills the orders it queued the day before, at today's opening price, charging the market's
   costs;
3. asks the strategy what it wants to hold, showing it prices up to today and no further;
4. turns that into orders in whole lots, and passes them through the safety limits;
5. queues those orders for tomorrow's open; and
6. values the portfolio at today's closing prices.

Deciding after today's close and filling at tomorrow's open is how a real investor would trade
on the same information, so the backtest never uses a price it could not have known. Paper
trading runs the same daily steps, so a strategy behaves the same in both.

Every backtest also runs plain buy-and-hold over the same days, so you can see whether the
strategy's extra trading added anything after its costs.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/backtest.data_gaps.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/backtest.data_gaps.md -->
```markdown
+++
id = "backtest.data_gaps"
title = "Days with missing prices"
summary = "What steadyhand does when a stock has no price for a day, and why the report warns you about it."
explains = ["data.bar.missing", "data.bar.refused"]
module = "using-steadyhand"
position = 3
see_also = ["risk.backtests_mislead"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

steadyhand needs each stock's prices for each trading day: the open, high, low and close,
together called a **bar**. Sometimes there is none.

- **A missing bar.** The data has no prices for a stock on a day. The stock may not have traded,
  or the data source may simply lack that day. steadyhand does not trade the stock that day, and
  if you hold it, values it at its last close. The report notes each such day.
- **Refused days.** In a backtest, the data source can refuse to give prices for some days
  altogether. steadyhand does not trade the stock on those days and values any holding at its
  last clean close. It lists the refused days in one warning per stock.

Both change the result. A stock that cannot be traded cannot be bought or sold when the
strategy wanted to, and a dividend whose ex-date falls on a refused day is unknown and is not
credited, so the backtest can show less income than the stock paid. If a report carries many of
these warnings, trust its figures less.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/backtest.report.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/backtest.report.md -->
```markdown
+++
id = "backtest.report"
title = "Reading a backtest's trading figures"
summary = "What turnover and the cash movements in a backtest report tell you about how much a strategy trades."
explains = ["term.turnover", "term.cash_movement"]
module = "using-steadyhand"
position = 2
see_also = ["backtest.basics", "costs.trading"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

A backtest report shows how the portfolio's value, returns and drawdown moved. Two figures in it
describe how much the strategy traded.

- **Turnover** is how much of the portfolio the strategy traded in a year: the value bought and
  the value sold, averaged, as a share of the average portfolio value, scaled to a year. A
  turnover of 100% means the strategy bought and sold about the whole portfolio once a year.
  Every trade costs money, so a high turnover needs a better result just to break even.
- **Cash movements** are every change to the portfolio's cash, one line each: a deposit, a
  purchase, a sale, a dividend, a tax, or a daily cost. Money coming in is positive and money going out
  is negative. Together they explain how the cash balance got to where it is.

Buy-and-hold has a very low turnover, because it hardly ever sells. That is part of why it is the
baseline every other strategy is compared with.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/dividends.basics.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/dividends.basics.md -->
```markdown
+++
id = "dividends.basics"
title = "Dividends"
summary = "A dividend is cash a company pays to the people who hold its shares on a given day."
explains = ["term.dividend_gross", "term.dividend_per_share"]
module = "shares-and-dividends"
position = 4
see_also = ["tax.dividend", "income.received"]
sources = ["docs/research/t-pay.md §4"]
+++

A company that makes a profit may pay part of it to its shareholders as a **dividend**. It is
announced as an amount per share: the **dividend per share**. If Stock A pays 50 a share and you
hold 400 shares, your dividend is 20,000.

Two dates matter:

- The **ex-date.** You must have bought the shares before this day. Buy on the ex-date or later
  and the dividend goes to the seller instead.
- The **pay date.** The day the cash arrives, usually some weeks after the ex-date. Price data
  gives the ex-date but not the pay date, so steadyhand models the pay date as a set number of
  trading days after the ex-date, measured from real payment schedules.

The **gross dividend** is the full amount before tax. The tax lesson explains what is taken
from it.

A dividend is paid out of the company's cash, so on the ex-date the share price usually drops by
about the dividend. A dividend is not free money on top of the price: it is part of your return,
paid to you in cash.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/income.calendar.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/income.calendar.md -->
```markdown
+++
id = "income.calendar"
title = "The payment calendar"
summary = "Which months of the year your current holdings' dividends would arrive in, and how evenly."
explains = ["term.payment_calendar", "term.evenness"]
module = "income-goal"
position = 3
see_also = ["income.run_rate", "dividends.basics"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.1"]
+++

The **payment calendar** spreads the run-rate across the twelve months of the year. Each
dividend a holding paid over the last year is placed in the month its payment would arrive,
after tax, using the same pay date steadyhand uses everywhere else. The calendar shows the
result per holding and in total, and how many months would have nothing.

If you plan to live on dividends, when they arrive matters as much as how much they are. Many
companies pay once a year, often in the same few months, which can leave long gaps.

**Evenness** is the largest month's share of the year's total:

- 1/12, about 8%, means every month pays the same;
- 1, or 100%, means the whole year's income arrives in a single month.

A lower number is a steadier income. It is left out when the run-rate is zero.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/income.goal.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/income.goal.md -->
```markdown
+++
id = "income.goal"
title = "Your income goal"
summary = "The monthly take-home income you are aiming for, and how much of it your portfolio covers today."
explains = ["term.income_target", "term.goal_share"]
module = "income-goal"
position = 5
see_also = ["income.received", "income.run_rate", "income.projection"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.4"]
+++

The **income target** is the monthly income you would like your portfolio to pay you: an amount
you choose, such as what you need to live on. steadyhand measures it on **take-home** income,
after the full dividend tax, because money you live on is money you are not reinvesting.

The goal tracker shows two ways of measuring progress, each as a share of the target:

- **Received**: the monthly average take-home of the dividends actually paid over the last year.
- **Run-rate**: the monthly take-home your current holdings would pay over a year.

With a target of 5,000,000 a month, a run-rate take-home of 1,250,000 covers 25% of it. A share
above 100% means the target is covered.

The two often differ. The run-rate moves as soon as you buy or sell; received income catches up
over the following year.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/income.growth.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/income.growth.md -->
```markdown
+++
id = "income.growth"
title = "Dividend growth"
summary = "How fast your holdings' dividends a share have grown over the last four years, as a yearly rate."
explains = ["term.dividend_growth", "income.growth.short_history"]
module = "income-goal"
position = 4
see_also = ["income.projection", "income.run_rate"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.2"]
+++

For each holding, steadyhand compares the dividends one share paid over the last year with what
it paid over the year that ended four years earlier. It turns the change into a yearly rate: a
dividend that went from 100 to 146 a share over four years grew about 10% a year.

It measures dividends **a share**, so buying more shares does not count as growth. A split is
allowed for, so it does not look like a cut.

The portfolio's **dividend growth** is each holding's growth, weighted by how much of the
run-rate that holding provides. The projection uses it for its scenarios, capped or trimmed so
that a single good stretch does not carry too far.

**When a holding's history is too short.** If a holding paid nothing in the earlier year, or the
data does not reach back four years, its growth cannot be measured. steadyhand counts it as 0%
and names the holding in a note, so its growth is never guessed upwards.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/income.projection.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/income.projection.md -->
```markdown
+++
id = "income.projection"
title = "Projection, not a promise"
summary = "How many years each scenario takes to reach your income target, under stated assumptions."
explains = ["term.contribution", "term.starting_income", "term.years_to_goal", "income.projection.costs_ignored"]
module = "income-goal"
position = 6
see_also = ["income.goal", "income.growth"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5.3"]
+++

The projection asks how long it would take your portfolio to pay your income target, if you kept
reinvesting. It works month by month from today's holdings:

- each month's take-home dividends are reinvested, and your monthly **contribution** is added;
- the new money buys more of the same holdings, at today's yield;
- once a year, the dividends grow at the scenario's rate.

It runs three scenarios:

| Scenario | Starting income | Dividend growth |
|---|---|---|
| Pessimistic | the run-rate × 0.8 | the measured growth or 0%, whichever is lower |
| Base | the run-rate | the measured growth, at most 5% a year |
| Optimistic | the run-rate | the measured growth, at most 10% a year |

Each gives the **years to the goal**, rounded up to a tenth of a year, or says the target is not
reached within 50 years. Nothing is projected from an empty portfolio or a zero run-rate.

The assumptions are deliberately cautious: share prices never rise, and only take-home income is
reinvested. **The costs of buying are left out**, which errs the other way, and a note says so on
every projection. It is a way to compare plans, not a date to count on.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/income.received.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/income.received.md -->
```markdown
+++
id = "income.received"
title = "Income received, and yield"
summary = "The dividends your portfolio was actually paid over the last year, and what they are as a share of its value and cost."
explains = ["term.received_income", "term.trailing_income", "term.current_yield", "term.yield_on_cost"]
module = "income-goal"
position = 1
see_also = ["income.run_rate", "tax.dividend", "shares.cost_basis"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §4"]
+++

**Received income** is the dividend money that actually arrived, as opposed to what the
portfolio might pay later. steadyhand shows it by month, and over the **trailing twelve months**:
the year that ends on the report's day. The income goal compares your target with the monthly
average of that year's take-home income (its total divided by 12).

A backtest also reports its **trailing income**: the dividends, after the tax booked on them,
paid in the last year of the run. It is how steadyhand compares one strategy's income with
another's.

Two ratios put the year's dividends, before tax, next to the portfolio:

- **Current yield**: the year's dividends as a share of what the portfolio is worth today. A
  portfolio worth 10,000,000 that was paid 500,000 has a current yield of 5%.
- **Yield on cost**: the same dividends as a share of what the holdings cost you. If those
  holdings cost 8,000,000, the yield on cost is 6.25%. Holdings that have risen in price show a
  yield on cost above their current yield.

Either is left out when there is nothing to divide by, such as a portfolio with no holdings.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/income.run_rate.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/income.run_rate.md -->
```markdown
+++
id = "income.run_rate"
title = "Run-rate"
summary = "What the dividends you hold now would pay over a year if nothing changed."
explains = ["term.run_rate", "term.monthly_take_home"]
module = "income-goal"
position = 2
see_also = ["income.received", "tax.dividend"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5"]
+++

The run-rate takes each holding you have today, and each dividend that stock paid a share over
the last year, and multiplies the two. Added up, that is the yearly income your current
holdings would bring if every company paid the same again and you changed nothing.

It answers a different question from received income. Received income is what arrived over the
last year, from whatever you held at the time. The run-rate is what today's holdings point to.
If you bought a stock last month, its year of dividends counts in full in the run-rate, though
you received none of them.

steadyhand shows it two ways:

- the **annual run-rate**, before tax; and
- the **monthly take-home**: the annual figure less the full dividend tax, divided by 12. This
  is the figure the income goal compares with your target.

The run-rate is an estimate, not a forecast. Companies raise, cut and skip dividends, and a
share price says nothing about next year's payment.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/risk.backtests_mislead.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/risk.backtests_mislead.md -->
```markdown
+++
id = "risk.backtests_mislead"
title = "Why backtests mislead"
summary = "A backtest shows what a strategy would have done in the past, which is not what it will do next."
explains = []
module = "risk"
position = 4
see_also = ["idx.survivorship", "backtest.basics", "backtest.data_gaps"]
+++

A backtest replays a strategy over past prices. It is a useful check and an easy one to
over-trust. Its results tend to look better than real life, for several reasons:

- **The past does not repeat.** A strategy that did well in one stretch of years can do badly in
  the next, when the market behaves differently.
- **Fitting to the past.** Try enough settings and one of them will look excellent on the
  history you tried them on, by chance. The more a strategy was tuned, the less its backtest
  says.
- **Survivorship bias.** A list of stocks chosen today leaves out the companies that failed or
  shrank. Testing on it makes the past look kinder than it was.
- **Missing or wrong data.** Prices can be missing on some days, or wrong, and a dividend on a
  missing day is never counted.
- **Perfect execution.** A backtest assumes you placed every order on time, at the modelled
  price. Real orders can fill at worse prices, or not at all.

steadyhand tries to be honest about these: it charges realistic costs, it warns when data or
the stock list has gaps, and it compares every strategy with plain buy-and-hold. Treat any
backtest as a rough guide to how a strategy behaves, never as a forecast.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/risk.drawdown.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/risk.drawdown.md -->
```markdown
+++
id = "risk.drawdown"
title = "Drawdown: how far it fell"
summary = "A drawdown is how far the portfolio fell from its highest point before it recovered."
explains = ["term.drawdown", "term.high_water"]
module = "risk"
position = 1
see_also = ["risk.returns", "risk.limits"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.1"]
+++

You can lose money. A drawdown puts a number on how much.

The **high-water mark** is the highest value the portfolio has reached so far, measured per unit
so that new deposits do not count as gains (the returns lesson explains units). A **drawdown**
is a fall from that high point, as a share of it. If the high point was 1.20 a unit and the
portfolio later fell to 0.90, the drawdown is 0.30 / 1.20 = 25%.

A backtest reports its **deepest** drawdown, with the day of the peak and the day of the low.
It is the worst stretch you would have lived through if you had run the strategy then.

Two things make a drawdown matter more than it looks:

- Getting back takes more than the fall. After a 25% fall, the portfolio needs to rise by a
  third (33%) just to return to where it was.
- The worst drawdown in a backtest is not the worst that can happen. The future can hold a
  deeper fall than the past did.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/risk.limits.md -->
```markdown
+++
id = "risk.limits"
title = "The safety limits steadyhand applies"
summary = "The limits that cut or stop a strategy's orders, whatever the strategy wants to do."
explains = []
module = "risk"
position = 3
see_also = ["risk.drawdown"]
sources = ["docs/superpowers/specs/2026-09-24-steadyhand-core-design.md §6.1"]
+++

Every strategy's orders pass through the same limits before they are placed. Each can be set in
your configuration. These are the defaults:

- **Cash only.** No borrowing and no short selling. A buy that needs more settled cash than you
  have is cut down or dropped.
- **At most 10% in one stock.** A buy that would take one stock above 10% of the portfolio's
  value is cut back to 10%.
- **Daily loss limit.** If the portfolio falls 5% in one day, the strategy **halts**: it places
  no new orders until you resume it.
- **Drawdown limit.** If the portfolio falls 25% below its high-water mark, the strategy halts
  in the same way.

A halt is not a sale. The holdings stay where they are; the strategy simply stops adding orders
until you have looked at what happened and chosen to resume.

These limits reduce some risks. They do not remove them: a portfolio can still lose a great deal
of its value, and the limits act on the day's closing prices, after the fall has happened.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/risk.returns.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/risk.returns.md -->
```markdown
+++
id = "risk.returns"
title = "Returns, counted fairly"
summary = "How steadyhand measures gain or loss so that money you pay in is never counted as profit."
explains = ["term.total_return", "term.annual_return", "term.unit_price", "term.units", "term.deposit"]
module = "risk"
position = 2
see_also = ["risk.drawdown"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

If you pay 1,000,000 into a portfolio and it is later worth 1,100,000, it looks like a 10% gain.
But if you paid in another 100,000 along the way, the portfolio gained nothing: the extra value
is your own money.

steadyhand avoids that mistake by counting the portfolio like a fund.

- A **deposit** is money you pay in: the starting capital, and any monthly top-up.
- Each deposit buys **units** at the current **unit price**. The first deposit buys units at a
  price of 1. A deposit leaves the unit price unchanged, because the money it adds is matched
  by the units it buys.
- After that the unit price moves only with the investments: price changes, dividends and
  costs.

The **total return** is how much the unit price changed over the run. A unit price that went
from 1.00 to 1.25 is a total return of 25%, however much you paid in along the way.

The **annual return** turns the total return into a yearly rate, compounded over the run's
calendar days. A 25% total return over two years is about 11.8% a year, not 12.5%, because each
year's gain builds on the one before.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/shares.basics.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/shares.basics.md -->
```markdown
+++
id = "shares.basics"
title = "What a share is"
summary = "A share is a small piece of ownership in a company that you can buy and sell on a stock exchange."
explains = []
module = "shares-and-dividends"
position = 1
see_also = ["shares.prices", "dividends.basics"]
+++

A company can split its ownership into many equal pieces called **shares**. If a company has
one million shares and you own one thousand of them, you own a thousandth of the company.

Shares of listed companies are bought and sold on a **stock exchange**. You do not buy them
from the company itself: you buy from another investor who wants to sell, and the exchange
matches the two of you. Your **broker** is the company whose app places your orders on the
exchange for you.

Owning a share gives you two possible ways to gain:

- The **price** can rise. If you bought at 1,000 and the price is now 1,200, your share is
  worth 200 more. The price can also fall below what you paid.
- The company can pay a **dividend**: a part of its profit, paid in cash to everyone who
  holds its shares on a given day.

Neither is promised. Prices move every day, and a company can cut or stop its dividend. The
examples in these lessons use made-up companies, such as "Stock A", and round numbers.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/shares.cost_basis.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/shares.cost_basis.md -->
```markdown
+++
id = "shares.cost_basis"
title = "Cost basis: what your shares cost"
summary = "The cost basis is what you paid for the shares you hold, with the costs of buying them included."
explains = ["term.cost_basis"]
module = "shares-and-dividends"
position = 3
see_also = ["shares.prices", "income.received"]
+++

When you buy shares, you pay their trade value plus the costs of the trade. The total is the
holding's **cost basis**.

Suppose you buy 100 shares of Stock A at 1,000 each, and the trade costs 150 on top. The trade
value is 100,000, so the cost basis is 100,150. If you later buy 100 more at 1,100, costing 165,
the cost basis of your 200 shares becomes 100,150 + 110,165 = 210,315.

The cost basis stays what you paid. It does not move with the price, so comparing it with the
holding's value today shows how much the holding has gained or lost.

steadyhand also uses it to work out your **yield on cost**: a year's dividends as a share of what
the holdings cost you.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/shares.prices.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/shares.prices.md -->
```markdown
+++
id = "shares.prices"
title = "Prices, and what your portfolio is worth"
summary = "How a trade's price, a stock's last close and your holdings add up to the value of your portfolio."
explains = ["term.trade_price", "term.trade_value", "term.last_close", "term.holdings_value", "term.portfolio_value"]
module = "shares-and-dividends"
position = 2
see_also = ["shares.cost_basis", "costs.trading"]
sources = ["docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md"]
+++

A stock has many prices during a day. These lessons use a few of them.

- **Trade price.** The price one of your orders was filled at: what you actually paid, or
  received, for each share.
- **Trade value.** The number of shares traded times the trade price, before any costs. Buying
  100 shares of Stock A at 1,000 is a trade value of 100,000.
- **Last close.** The price a stock closed at on the most recent day it traded. steadyhand
  values what you hold at each stock's last close.

From those, steadyhand works out what your portfolio is worth each day:

- **Holdings value.** Every stock you hold, times its last close, added up.
- **Portfolio value.** Your cash plus your holdings value. The cash includes money from a sale
  that has not arrived in your account yet.

A portfolio's value is not money in your hand. It is what the shares would fetch at today's
closing prices, before the costs of selling them, and tomorrow's prices can be lower.
```

**`packages/steadyhand/src/steadyhand/training/lessons/en/shares.splits.md`** (new)

<!-- file: packages/steadyhand/src/steadyhand/training/lessons/en/shares.splits.md -->
```markdown
+++
id = "shares.splits"
title = "Stock splits"
summary = "A split changes how many shares you hold and the price of each, without changing what the holding is worth."
explains = ["corporate.split.fraction_dropped"]
module = "shares-and-dividends"
position = 5
see_also = ["shares.cost_basis"]
+++

A company can **split** its shares. In a 5-for-1 split, every share you held becomes five, and
the price of each falls to about a fifth. You own the same part of the company as before.

A **reverse split** goes the other way: in a 1-for-5 reverse split, every five shares become one.

**When a fraction of a share is dropped.** A reverse split can leave a fraction: 1,203 shares in
a 1-for-5 reverse split make 240.6 shares. A share cannot be held in parts, so you keep 240 and
the 0.6 share is left over. In a real account that part may be paid out to you in cash,
called cash in lieu. steadyhand does not model that payment: it drops the fraction and says so
in a note, so a report shows slightly less than a real account would.
```


- [ ] **Step 6: Read every lesson against core spec §3 item 3.** For each of the 33, confirm it explains a rule, a figure or a risk and never says what to buy, sell or hold; that its examples use made-up names; and that each number it states is in the document its `sources` names. Record the check in the PR.

- [ ] **Step 7: Run the build step as CI will.** Build both wheels and run the new step's script exactly as `ci.yml` has it, from a folder holding `dist/` and a link to `packages/`:

  ```bash
  uv build --all-packages --out-dir "${TMPDIR}/wheels/dist"
  ln -s "$PWD/packages" "${TMPDIR}/wheels/packages"
  uv run python - <<'EOF' > "${TMPDIR}/step.sh"
  import sys, yaml
  steps = [s for s in yaml.safe_load(open(".github/workflows/ci.yml"))["jobs"]["build"]["steps"] if s.get("name", "").startswith("Both wheels ship every lesson")]
  assert len(steps) == 1
  sys.stdout.write(steps[0]["run"])
  EOF
  mkdir -p "${TMPDIR}/wheels/runner"
  (cd "${TMPDIR}/wheels" && RUNNER_TEMP="${TMPDIR}/wheels/runner" bash -e "${TMPDIR}/step.sh") > "${TMPDIR}/step.log" 2>&1; rc=$?
  echo "rc=${rc}"; tail -1 "${TMPDIR}/step.log"
  ```

  Expected: `rc=0`, and the log ends `33 lessons load from the installed wheels`.

- [ ] **Step 8: Run the whole gate**, as in Task 1 Step 7.

<!-- check: gate total=984 passed=984 -->
Expected: every command exits 0; 984 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 15.5 s against the 30 s budget).

- [ ] **Step 9: Mutations.** Run M132–M139, M138 by hand as **Mutation checks** says; each must turn red.
- [ ] **Step 10: Commit, push and merge** (`feat(training): T1 S4 the lessons, the course content and the built-wheel check`, ending in `(#N)`). CI's `build` job must show the new step green by name.

---

## Mutation checks

Each mutation plants one realistic defect in the story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed lines are printed before the run. The predicted catchers were written before any run; "More than predicted" lists the other tests that also went red.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M104 | 1 | `corporate.py` | the split note is built from a literal key | 836 | `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used`, `test_no_key_is_defined_twice` (2 failing) | none |
| M105 | 1 | `universe.py` | the IDX survivorship note is built from a literal key | 836 | `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used`, `test_no_key_is_defined_twice` (2 failing) | none |
| M106 | 1 | `record_golden.py` | the golden file stores the warnings as bare text | 836 | `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_recorder_writes_the_stored_file_byte_for_byte` (2 failing) | none |
| M107 | 1 | `terms.py` | a figure loses its term | 836 | `test_every_figure_has_a_term` (1 failing) | none |
| M108 | 1 | `terms.py` | FIGURES names a field that does not exist | 836 | `test_figures_names_only_fields_that_exist` (1 failing) | none |
| M109 | 1 | `metrics.py` | a nested report type gains a figure with no term | 836 | `test_every_figure_has_a_term` (1 failing) | none |
| M110 | 1 | `terms.py` | a term key loses the term prefix | 836 | `test_every_key_is_a_dotted_lowercase_identifier_named_after_itself`, `test_terms_and_only_terms_carry_the_term_prefix` (2 failing) | none |
| M111 | 1 | `notes.py` | the IDX note key repeats an engine key | 836 | `test_every_key_is_a_dotted_lowercase_identifier_named_after_itself`, `test_no_key_is_defined_twice` (2 failing) | none |
| M112 | 2 | `catalogue.py` | a two-sentence summary is accepted | 913 | `test_a_broken_lesson_names_its_file_and_field` (1 failing) | none |
| M113 | 2 | `catalogue.py` | position = true is accepted as 1 | 913 | `test_a_broken_lesson_names_its_file_and_field` (1 failing) | none |
| M114 | 2 | `catalogue.py` | two lessons may explain one key | 913 | `test_a_key_explained_by_two_lessons_names_the_second` (1 failing) | none |
| M115 | 2 | `catalogue.py` | a gap in a module's positions is accepted | 913 | `test_a_broken_lesson_names_its_file_and_field` (1 failing) | none |
| M116 | 2 | `catalogue.py` | a byte-order mark breaks the header | 913 | `test_a_byte_order_mark_is_not_part_of_the_header` (1 failing) | none |
| M117 | 2 | `catalogue.py` | a missing lesson folder is not named | 913 | `test_a_missing_root_is_named` (1 failing) | none |
| M118 | 2 | `catalogue.py` | an unresolved see_also is accepted | 913 | `test_a_broken_lesson_names_its_file_and_field` (1 failing) | none |
| M119 | 2 | `lesson_rules.py` | a folder counts as a source file | 913 | `test_a_source_that_is_not_a_repo_file_is_found` (1 failing) | none |
| M120 | 2 | `lesson_rules.py` | the disclaimer check reads raw Markdown, not what a reader sees | 913 | `test_the_fixture_passes_every_guard` (1 failing) | none |
| M121 | 2 | `catalogue.py` | the course lists its modules backwards | 913 | `test_a_disclaimer_hidden_in_a_comment_does_not_count`, `test_a_good_catalogue_loads`, `test_a_start_lesson_without_the_disclaimer_is_found`, `test_a_start_module_with_no_lesson_is_found`, `test_the_course_lists_the_eight_modules_in_order`, `test_the_fixture_passes_every_guard` (6 failing) | none |
| M122 | 3 | `engine.py` | engine.py imports training | 975 | `test_only_training_imports_training` (1 failing) | none |
| M123 | 3 | `render.py` | training imports steadyhand.risk | 975 | `test_training_imports_nothing_that_decides` (1 failing) | none |
| M124 | 3 | `fixture.lots.md` | a fixture lesson says you should buy | 975 | `test_the_fixture_lessons_carry_no_advice` (1 failing) | none |
| M125 | 3 | `render.py` | two keys of one lesson give two lines | 975 | `test_keys_may_be_read_once`, `test_new_gives_a_line_per_lesson_in_first_appearance_order`, `test_some_names_the_lessons_only`, `test_two_keys_of_one_lesson_give_one_line` (4 failing) | none |
| M126 | 3 | `render.py` | an unknown key goes unnoticed at the quiet levels | 975 | `test_an_unknown_key_is_a_bug_at_every_level` (2 failing) | none |
| M127 | 3 | `lesson_rules.py` | a ticker two words before buy is missed | 975 | `test_a_ticker_followed_by_buy_or_sell_is_found` (2 failing) | none |
| M128 | 3 | `lesson_rules.py` | a curly apostrophe hides can't lose | 975 | `test_a_phrase_is_found_across_lines_quotes_and_curly_apostrophes` (1 failing) | none |
| M129 | 3 | `test_legal_line.py` | a relative import is not resolved | 975 | `test_relative_imports_are_resolved` (1 failing) | none |
| M130 | 3 | `test_legal_line.py` | from steadyhand import training is missed | 975 | `test_relative_imports_are_resolved`, `test_the_training_import_detector` (2 failing) | none |
| M131 | 3 | `test_legal_line.py` | a dotted standard-library module is refused | 975 | `test_the_engine_training_allowlist`, `test_the_idx_training_allowlist`, `test_training_imports_nothing_that_decides` (3 failing) | none |
| M132 | 4 | `risk.drawdown.md` | a real lesson says you should buy | 984 | `test_no_lesson_carries_advice_phrasing` (1 failing) | none |
| M133 | 4 | `income.run_rate.md` | a key loses its lesson | 984 | `test_every_key_has_a_lesson` (1 failing) | none |
| M134 | 4 | `risk.drawdown.md` | a lesson explains a key that does not exist | 984 | `test_no_lesson_explains_a_key_that_does_not_exist` (1 failing) | none |
| M135 | 4 | `tax.dividend.md` | a lesson cites a source that does not exist | 984 | `test_every_source_is_a_repo_file` (1 failing) | none |
| M136 | 4 | `start.welcome.md` | the Start here lesson loses part of the disclaimer | 984 | `test_the_course_opens_with_the_disclaimer` (1 failing) | none |
| M137 | 4 | `shares.cost_basis.md` | an engine lesson quotes rupiah | 984 | `test_the_engine_lessons_are_market_neutral` (1 failing) | none |
| M139 | 4 | `__init__.py` | catalogue() loads only the IDX lessons | 984 | `test_every_key_has_a_lesson`, `test_every_lesson_file_is_loaded`, `test_every_source_is_a_repo_file`, `test_no_lesson_carries_advice_phrasing`, `test_no_lesson_explains_a_key_that_does_not_exist`, `test_the_course_opens_with_the_disclaimer`, `test_the_engine_lessons_are_market_neutral`, `test_the_modules_written_in_t1_have_lessons`, `test_the_spec_example_renders_as_written` (9 failing) | none |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M104',
  1,
  'packages/steadyhand/src/steadyhand/corporate.py',
  '                        CORPORATE_SPLIT_FRACTION_DROPPED,\n',
  '                        "corporate.split.fraction_dropped",\n'),
 ('M105',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/universe.py',
  '                        UNIVERSE_SURVIVORSHIP_GAP,\n',
  '                        "universe.survivorship.gap",\n'),
 ('M106',
  1,
  'scripts/record_golden.py',
  '        "warnings": [[note.key, note.text] for note in (*result.warnings, '
  '*outcome.warnings)],\n',
  '        "warnings": [note.text for note in (*result.warnings, *outcome.warnings)],\n'),
 ('M107',
  1,
  'packages/steadyhand/src/steadyhand/terms.py',
  '        "Costs.total": TERM_TRADING_COSTS,\n',
  ''),
 ('M108',
  1,
  'packages/steadyhand/src/steadyhand/terms.py',
  '        "Costs.fee": TERM_BROKER_FEE,\n',
  '        "Costs.fee": TERM_BROKER_FEE,\n        "Costs.stamp": TERM_DAILY_COST,\n'),
 ('M109',
  1,
  'packages/steadyhand/src/steadyhand/metrics.py',
  '    depth: Decimal\n    peak: date\n    trough: date\n',
  '    depth: Decimal\n    peak: date\n    trough: date\n    recovery: Decimal = Decimal(0)\n'),
 ('M110',
  1,
  'packages/steadyhand/src/steadyhand/terms.py',
  'TERM_UNITS = "term.units"',
  'TERM_UNITS = "units.count"'),
 ('M111',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/notes.py',
  'UNIVERSE_SURVIVORSHIP_GAP = "universe.survivorship.gap"',
  'UNIVERSE_SURVIVORSHIP_GAP = "data.bar.missing"'),
 ('M112',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  '    if not summary.endswith(".") or ". " in summary:\n',
  '    if not summary.endswith("."):\n'),
 ('M113',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  '    if position is not None and (type(position) is not int or position < 1):\n',
  '    if position is not None and (not isinstance(position, int) or position < 1):\n'),
 ('M114',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  '                    if owner is not lesson:\n',
  '                    if False:\n'),
 ('M115',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  '            if position != expected:\n',
  '            if position < expected:\n'),
 ('M116',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  'file.read_text(encoding="utf-8-sig"), origin)',
  'file.read_text(encoding="utf-8"), origin)'),
 ('M117',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  '            if not root.is_dir():\n',
  '            if False:\n'),
 ('M118',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  '                if other not in by_id:\n',
  '                if False:\n'),
 ('M119',
  2,
  'tests/meta/lesson_rules.py',
  'not (root / path).is_file():',
  'not (root / path).exists():'),
 ('M120',
  2,
  'tests/meta/lesson_rules.py',
  '    if disclaimer not in normalised(first.body):\n',
  '    if disclaimer not in first.body:\n'),
 ('M121',
  2,
  'packages/steadyhand/src/steadyhand/training/catalogue.py',
  '        for number, slug, title in course\n    )\n',
  '        for number, slug, title in reversed(course)\n    )\n'),
 ('M122',
  3,
  'packages/steadyhand/src/steadyhand/engine.py',
  'from steadyhand.money import Money\n',
  'from steadyhand.money import Money\nfrom steadyhand.training import Level  # noqa: F401\n'),
 ('M123',
  3,
  'packages/steadyhand/src/steadyhand/training/render.py',
  'from steadyhand._validate import require_type\n',
  'from steadyhand._validate import require_type\n'
  'from steadyhand.risk import RiskLimits  # noqa: F401\n'),
 ('M124',
  3,
  'tests/fixtures/training/idx/en/fixture.lots.md',
  "A fixture lesson in the other package's folder.\n",
  "A fixture lesson in the other package's folder. You should buy lots.\n"),
 ('M125',
  3,
  'packages/steadyhand/src/steadyhand/training/render.py',
  '        lessons.setdefault(lesson.id, lesson)\n',
  '        lessons[key] = lesson\n'),
 ('M126',
  3,
  'packages/steadyhand/src/steadyhand/training/render.py',
  '    lessons: dict[str, Lesson] = {}\n',
  '    if level in (Level.OFF, Level.EXPERIENCED):\n'
  '        return ""\n'
  '    lessons: dict[str, Lesson] = {}\n'),
 ('M127', 3, 'tests/meta/lesson_rules.py', '(?:\\W+\\w+){0,2}?', '(?:\\W+\\w+){0,1}?'),
 ('M128', 3, 'tests/meta/lesson_rules.py', 'text.replace("\\u2019", "\'")', 'text'),
 ('M129',
  3,
  'tests/meta/test_legal_line.py',
  '                base = f"{parent}.{base}" if base else parent\n',
  '                base = base or parent\n'),
 ('M130',
  3,
  'tests/meta/test_legal_line.py',
  ' or any(_within(f"{base}.{name}", TRAINING) for name in names)',
  ''),
 ('M131',
  3,
  'tests/meta/test_legal_line.py',
  'name.split(".", maxsplit=1)[0] in sys.stdlib_module_names',
  'name in sys.stdlib_module_names'),
 ('M132',
  4,
  'packages/steadyhand/src/steadyhand/training/lessons/en/risk.drawdown.md',
  'You can lose money. A drawdown puts a number on how much.',
  'You can lose money. You should buy Stock A anyway.'),
 ('M133',
  4,
  'packages/steadyhand/src/steadyhand/training/lessons/en/income.run_rate.md',
  'explains = ["term.run_rate", "term.monthly_take_home"]',
  'explains = ["term.run_rate"]'),
 ('M134',
  4,
  'packages/steadyhand/src/steadyhand/training/lessons/en/risk.drawdown.md',
  'explains = ["term.drawdown", "term.high_water"]',
  'explains = ["term.drawdown", "term.high_water", "term.max_drawdown"]'),
 ('M135',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.dividend.md',
  '"docs/research/t-tax.md §1", ',
  '"docs/research/t-taxes.md §1", '),
 ('M136',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/start.welcome.md',
  '> own decisions with it. It is not financial advice. You can lose money.',
  '> own decisions with it. It is not financial advice.'),
 ('M137',
  4,
  'packages/steadyhand/src/steadyhand/training/lessons/en/shares.cost_basis.md',
  'Stock A at 1,000 each',
  'Stock A at Rp1,000 each'),
 ('M139',
  4,
  'packages/steadyhand-idx/src/steadyhand_idx/training/__init__.py',
  'Catalogue.load([ENGINE_LESSONS, LESSONS], COURSE)',
  'Catalogue.load([LESSONS], COURSE)')]
```

**M138, run by hand (Task 4): a lesson missing from the built wheel.** No source-tree test can see it, so its catcher is the build step. Add a wheel exclusion to `packages/steadyhand-idx/pyproject.toml`, rebuild, and run Task 4 Step 7's script:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/steadyhand_idx"]
exclude = ["*.md"]
```

Predicted before the run: the step fails before its count check, because `Catalogue.load` refuses the first engine lesson that links into the IDX folder (`backtest.report.md`, `see_also`, `no lesson 'costs.trading'`). Observed: the step exits 1, and the IDX wheel holds 0 lesson files. The catcher was earlier than predicted: with every `.md` excluded, the installed package has no `lessons/en/` folder at all, so `load` stops on the missing root first (`LessonError: …/site-packages/steadyhand_idx/training/lessons/en: root: is not a folder`). The prediction was wrong about which check fires, and right that the step goes red where no source-tree test does.

## Carried forward

- **M5** builds what T1 §6 fixes: the `init` questions and `--training`, the `training` and `learn` commands, and the inline block under each command's output, all printed from `explain`. It parses `[training]` in the CLI's output layer and extends the legal guard: the output layer joins the modules allowed to import training (§5 item 1), and the module that parses the setting is covered (§5 item 3). It writes module 6's paper-trading lessons and adds its new report types to `test_terms.py`'s roots.
- **M4b** (S5–S8): every note it adds needs its lesson in the same PR; `test_lessons.py` now fails until it has one. `tax.exemption` should be re-read then, since M4b models the exemption this lesson describes.
- **Scope decisions 1–3 amend the T1 spec**: the error's name, the order of `LESSONS` and `catalogue()`, and the walk's properties and private names. The spec keeps its approved text; this plan is the record of the change.
- **Module 8** gets a lesson per strategy with each strategy wave (M6–M9). **Bahasa Indonesia** is its own ticket; the `en/` folders leave room for it.
- **Keys for `Tradable` reasons and the audit log** are decided in M5 (T1 §1.1).

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

**Before pass 1, while building the code (2026-09-27).** Building the code first found eight things that a reading of the spec would not have:

1. The public-API guard required every public engine name to be exported from `steadyhand`, which would make `steadyhand/__init__.py` import training, the one import T1 §5 forbids (scope decision 10).
2. ruff's N818 refuses the spec's `LessonNotFound` (scope decision 1).
3. The figure walk found 65 fields, four of them properties and one private (scope decision 3).
4. The first load of the real lessons refused `idx.lq45`: an id cannot hold a digit (scope decision 14).
5. A lesson cites the T1 spec, which `develop` does not have until Task 0 merges, so the chain's base must include it (scope decision 12).
6. Gating the four stories found a defect already on `develop`. The M4a projection rounded income down every month, so a larger contribution could take longer (hypothesis: Rp6 a month took 1.7 years where Rp5 took 1.6). It was filed as #97, fixed in PR #98 (merged as `acca50e`, develop run 36305531569 green with `publish-dev`), and the chain was rebuilt on it. `develop`'s tree at `acca50e` is byte-identical to the chain's fix commit.
7. S1's first commit carried an E501 in a docstring, caught before the chain was gated and amended.
8. M138's prediction was wrong about which check fires (see **Mutation checks**).

**Pass 1 (2026-09-27): 6 findings, all fixed.** Mechanical checks first. Every printed ad-hoc script was cut from the plan text and run as printed: Task 1 Step 6 printed `['warnings'] True ['data.bar.refused']` at S1, as claimed; Task 4 Step 7 built both wheels and its log ended `33 lessons load from the installed wheels`. Then a whole read of the prose against the T1 spec and the code.

1. Task 4 Step 7's Expected line cited `rc=0`, but the printed script never printed it. The script now prints `rc` and the log's last line.
2. The global constraint said every `pytest.raises` has a raw-string `match=`. `test_legal_line.py` has a plain `match="is not in either package"`, and the rule the repo enforces is ruff's RUF043 (raw where there is a metacharacter). The constraint now states that rule.
3. The file map left out `test_public_api.py` and `test_disclaimer.py`, which Tasks 2 and 4 change. Added.
4. T1 §10 allows splitting S4 by module; the plan did not say whether it does. It is now scope decision 16, with the measured size (871 lines, about 7,000 words).
5. Scope decision 16 as first written said 27 of the 33 lessons explain a key: a number I typed without reading it. Measured, it is 20, with the other 13 explaining none (20 + 13 = 33). Corrected.
6. M131 did not run on the first mutation pass: its anchor matched 0 times, because `ruff --fix` had rewritten `name.split(".")[0]` as `name.split(".", maxsplit=1)[0]` after the anchor was written. The runner refuses a no-op mutation, so this was a missing result, not a false catch. With the anchor corrected, M131 went red exactly as predicted (3 tests, total 975).

The replay of the trial render (`check_plan.py`) passed with 0 problems: for each task, the red count, the golden file's SHA-256, the gate count and a tree byte-identical to the story's verified commit. All 36 mutations went red, 35 by the runner exactly as predicted and M138 by hand.

**Pass 2 (2026-09-27): no findings.** Mechanical checks: the final plan text replayed with `check_plan.py` and 0 problems (red 836/11, 913/76, 975/16 and 984/9; gates 836, 913, 975 and 984; the golden file's SHA-256; every story tree byte-identical to its verified commit). The mutation table was read against the run logs: every one of the 35 was caught by exactly the tests predicted, the "More than predicted" column is `none` throughout, and each task's mutation range matches its acceptance criteria. No `close`, `fix` or `resolve` stands next to an issue number. M138's quoted error matches its log word for word. Then a whole read of the prose against the T1 spec, found nothing. The loop closes here, and the plan is approved.
