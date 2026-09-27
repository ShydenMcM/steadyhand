# steadyhand T1: Training foundation

**Status:** design approved by Shyden in conversation on 2026-09-27, in four parts. The review loop closed on pass 3. The written spec awaits Shyden's review.
**Parent spec:** `2026-09-24-steadyhand-core-design.md` (the "core spec"). Training is a sub-project Shyden asked for on 2026-09-26: newbie-friendly training for everything, with an opt-out and a first-launch question on competency. It was deferred until the M4 spec was approved, which happened on 2026-09-26. The legal findings (core spec §3, item 3) and the disclaimer (§9.8) still hold. The stable-key hook it builds on is M4 spec §7.

## 1. What T1 delivers

T1 is the training **foundation**. It is one milestone, built before M4b:

- M3's plain-string warnings become keyed `Note`s, so every sentence a report says beyond its figures carries a stable key.
- Figures get stable **term** keys too, so a report's labels can be explained as well as its notes.
- It defines a lesson file format. Lessons ship inside both wheels and are loaded by a stdlib-only library, `steadyhand.training`.
- A renderer decides, from the user's level, how much explanation goes under a command's output.
- CI guards keep the catalogue complete (every key has exactly one lesson) and keep the legal line structural (§5).
- It writes the first content: a lesson for every key that exists at the end of T1, and course modules 1 to 5 and 7, plus the backtest half of module 6.

After T1, any story that adds a note or a term cannot merge without its lesson. The lesson is written by whoever adds the key, in the same PR.

### 1.1 Out of scope

| Item | Where it goes | Why |
|---|---|---|
| The `init` questions, the `training` and `learn` commands, and the inline block under command output | M5 (the CLI) | There is no CLI before M5. T1 builds the library those commands call, and §6 fixes how they behave. |
| Parsing the `[training]` section of `steadyhand.toml` | M5 | The config loader arrives with the CLI. |
| The paper-trading half of course module 6 | M5 | It explains commands that do not exist yet. |
| Course module 8 (strategies) | Each strategy wave (M6–M9) | Each wave adds the course entry for its own guides. |
| Bahasa Indonesia | Later, as its own ticket | Decision 2 (§2). The folder layout already allows it. |
| The dashboard rendering of lessons | Sub-projects B and C | The files are plain Markdown, so a dashboard can render them without a separate copy. |
| Keys for `Tradable` reasons (`excluded: …`, `no bar on …`) and for audit-log lines | M5 decides | Neither reaches a report today. The audit log is built in M5. |
| Progress tracking, quizzes, or gating an action on a lesson | Not planned | Decision 1, assumption 4: nothing stops a user from doing anything. |

## 2. Shyden's decisions (2026-09-27)

1. **The brief** (confirmed as written): newbie-friendly training for everything, and an opt-out. A first-launch question asks for competency level and whether the user wants training. There are both contextual explanations and a lesson course. Content is written once as Markdown in the repo, shown by the CLI from M5 and later by the dashboard. **Competency changes how much is explained, never what the tool suggests trading.** Four assumptions were confirmed with it:
   1. Success means that someone who has never bought a share can run `init`, a backtest and paper trading, and understand every number, warning and note they are shown.
   2. Lessons attach to the stable keys, and M3's warnings get keys as part of this work.
   3. The first-launch answer can be changed later.
   4. There are no quizzes, no progress tracking and no gating.
2. **Audience:** any self-hosting first-time investor, in English only. Lessons sit under a language folder (`en/`), so Indonesian can be added later without code changes.
3. **Levels:** three levels, plus off.
   - `new`: a short explanation of each item, plus the lesson command.
   - `some`: the lesson command only.
   - `experienced`: nothing inline.
   - `off` (training declined): nothing inline, at any level.
4. **Timing:** the foundation is built now, before M4b. From then on, content grows with the code.
5. **The content model, the structural legal line, the user view, and the guards and stories:** approved as design parts 1 to 4. They are written out in §3 to §9.

## 3. Keys: notes and terms

### 3.1 Note keys for M3's warnings (S1)

Four producers emit plain strings today. Each becomes a `Note` built from a key constant, and the rendered text stays the same, character for character:

| Producer | Today | Key | Constant's home |
|---|---|---|---|
| `corporate.py`: a split leaves a fraction of a share | `str` in `CorporateOutcome.warnings` | `corporate.split.fraction_dropped` | `steadyhand/notes.py` |
| `engine.py` `_tradable`: a member or holding has no bar that day | `str` in `DayReport.warnings` | `data.bar.missing` | `steadyhand/notes.py` |
| `backtest.py` `_refused_warnings`: the data source refused days | `str` in `BacktestResult.warnings` | `data.bar.refused` | `steadyhand/notes.py` |
| `steadyhand_idx/universe.py` `survivorship_warnings`: a gap between LQ45 lists | `str`, through the engine's `Universe` protocol | `universe.survivorship.gap` | `steadyhand_idx/notes.py` (new) |

The `warnings` fields of `CorporateOutcome`, `DayReport` and `BacktestResult`, the `RunResult.warnings` property that gathers the daily ones, and `Universe.survivorship_warnings` all change from strings to `Note`s. That is a change to the engine's public API, including a protocol that `steadyhand-idx` implements, so S1 updates both packages in one PR. The IDX package imports `Note` from the engine's public API only (core spec §4.2). Golden files keep their figures. If a golden file serialises the warnings, its text is unchanged and only its shape moves from a string to a key and text.

M4's key meta-test (`tests/meta/test_note_keys.py`) walks the engine today. S1 widens it to **both packages**. Every key constant still matches `^[a-z]+(\.[a-z_]+)+$`, no key value is defined twice anywhere, and no `Note(...)` takes a literal key.

### 3.2 Term keys (S1)

A **term** is a figure a report can show, such as total return, drawdown or run-rate. Term keys follow the same rules as note keys and live in `steadyhand/terms.py`, one module-level constant each, under the `term.` prefix (for example `term.run_rate`). `steadyhand/terms.py` also holds `FIGURES`, a mapping from `"Class.field"` to a term key.

A meta-test derives the figure fields itself and asserts that each one is in `FIGURES`. It starts from the three report types that exist today, `DayReport`, `BacktestResult` and `IncomeReport`, and follows their fields recursively into every dataclass they contain, including through tuples, mappings and optionals. Every field typed `Money` or `Decimal`, optional or not, is a figure field. The walk follows types rather than modules, so a figure added to `Metrics`, `DayReport` or any nested dataclass is found without a list of files. A new report type (M5's CLI adds some) is added to the roots in the story that creates it. The test also asserts that `FIGURES` names no field that does not exist. Several fields may share one term: `IncomeFigures.gross` and `DividendTotals.gross` are both "gross dividend". **The term list is derived from the dataclasses at S1's commit, not listed here.** A new figure in a later story fails CI until it has a term, and a new term fails CI until it has a lesson (§8).

## 4. Lessons

### 4.1 The file

A lesson is one Markdown file, `<id>.md`, with a TOML header between `+++` lines. TOML is used because `tomllib` is in the standard library, and the engine depends on nothing else at runtime (core spec §4.2).

```markdown
+++
id = "income.run_rate"
title = "Run-rate"
summary = "What the dividends you hold now would pay over a year if nothing changed."
explains = ["term.run_rate"]
module = "income-goal"
position = 2
see_also = ["income.received", "tax.dividend"]
sources = ["docs/superpowers/specs/2026-09-26-m4-income-design.md §5"]
+++

The run-rate takes each holding you have today...
```

| Field | Required | Rule |
|---|---|---|
| `id` | yes | The same shape as a key, and equal to the file name without `.md`. Unique across both packages. |
| `title` | yes | 1–60 characters. |
| `summary` | yes | One sentence of at most 160 characters, ending in `.`, with no `. ` inside it. This is the line a `new`-level user sees inline. |
| `explains` | yes (may be empty) | The note and term keys this lesson explains. Each must exist, and each key appears in exactly one lesson across both packages. A course lesson that explains no key (such as "Start here") has an empty list. |
| `module`, `position` | together or neither | The course module's slug, and the lesson's place in it (1, 2, 3 … with no gap and no repeat). |
| `see_also` | no | Other lesson ids. Each must resolve. |
| `sources` | no | Repo paths, with an optional `§` section, for the facts the lesson states. Each path must exist. |

No other header field is allowed. The body is plain Markdown, written in the style of the strategy guides (core spec §8): no jargon, or jargon explained where it first appears.

### 4.2 Where lessons live

Lessons are in two homes, matching the two packages:

- **Engine**, `packages/steadyhand/src/steadyhand/training/lessons/en/`: market-neutral lessons (shares and dividends, drawdown, compounding, why backtests mislead, the income notes and figures).
- **IDX**, `packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/`: IDX lessons (lots of 100 shares, tick sizes, auto-reject bands, T+2 settlement, trading sessions, the Special Monitoring Board, broker fees, the 0.1% sale tax, and the 10% dividend tax and its exemption).

Both homes ship inside their wheel, as the IDX rule data already does, so an installed copy prints lessons offline. The catalogue is loaded from both homes at once. Ids, keys and course slots are checked across the union, so a lesson can link to one in the other package.

### 4.3 The course

The course is every lesson that has a `module` and a `position`, read in order. The module list is `course.toml` in the IDX training folder, because the course belongs to the IDX distribution. It holds each module's slug, number and title:

| # | Slug | Title | Written in |
|---|---|---|---|
| 1 | `start-here` | Start here | T1 |
| 2 | `shares-and-dividends` | Shares and dividends | T1 |
| 3 | `how-idx-works` | How IDX works | T1 |
| 4 | `costs-and-tax` | Costs and tax | T1 |
| 5 | `risk` | Risk, and why backtests mislead | T1 |
| 6 | `using-steadyhand` | Using steadyhand | T1 (backtesting); M5 (paper trading) |
| 7 | `income-goal` | The income goal | T1 |
| 8 | `strategies` | Strategies | M6–M9 (each lesson points at the strategy's existing guide rather than copying it) |

"Start here" covers what steadyhand is and is not, that orders are placed by hand in the user's broker app, and that the user can lose money. It carries the disclaimer verbatim (core spec §9.8). An empty module (8 during T1) is allowed and is listed as "coming later".

## 5. The legal line, kept structural

The level decides how much is **explained**, never what is **suggested**. Code structure enforces this; a promise would not.

1. **Only the output layer may import training.** A CI meta-test walks every import in both packages and fails if any module outside `steadyhand.training`, `steadyhand_idx.training` and (from M5) the CLI's output layer imports either training package. This is stricter than listing the deciding modules. Any new module, such as a strategy, a sizer or a broker, is covered without anyone adding it to a list.
2. **Training imports nothing that decides.** `steadyhand.training` may import the standard library, `steadyhand.notes`, `steadyhand.terms` and `steadyhand._validate`, and nothing else. `steadyhand_idx.training` may import those, plus `steadyhand.training` and `steadyhand_idx.notes`.
3. **The settings stay in the output layer.** The `[training]` section of `steadyhand.toml` (`level = "new" | "some" | "experienced" | "off"`) is parsed in the CLI's output layer only. M5 extends guard 1 to cover the module that parses it.
4. **The advice-phrase backstop.** A CI check scans every lesson's title, summary and body for advice phrasing. These phrases are matched case-insensitively: `you should buy`, `you should sell`, `we recommend`, `recommended stock`, `best stock`, `guaranteed`, `can't lose` and `cannot lose`. One more pattern is matched case-sensitively: a word of exactly four capital letters followed, within three words, by `buy` or `sell` in any case. A hit fails CI and names the file and the phrase. Lessons use made-up names in examples ("Stock A"), never a real ticker. The phrase list is a backstop; the import rule is the control.

## 6. What the user sees (built in M5, fixed here)

T1 builds `steadyhand.training.explain(...)`, which returns the text; M5 prints it. The behaviour below is the contract M5 implements and T1's renderer tests pin.

1. **First launch.** `init` shows the disclaimer and requires `I understand`, as it does now. It then asks `Would you like explanations as you go? [Y/n]`. On yes, it asks `How much investing experience do you have? 1 New / 2 Some / 3 Experienced`, with New as the default. For scripts, `init --training off|new|some|experienced` answers both.
2. **Changing it later.** `steadyhand-idx training` shows the setting, and `steadyhand-idx training new|some|experienced|off` changes it.
3. **The course.** `steadyhand-idx learn` lists the modules and their lessons in order. `steadyhand-idx learn <id>` prints one lesson: its title, then its body, then its "see also" ids. An unknown id exits 2 and names up to three of the closest ids (`difflib`, standard library).
4. **Inline, at the end of a command's output**, from the keys the output showed, in the order they first appeared, with one line per lesson (two keys that share a lesson give one line):
   - `new`:
     ```
     What this means
     • Run-rate: What the dividends you hold now would pay over a year if nothing changed. More: steadyhand-idx learn income.run_rate
     ```
   - `some`: `Learn more with steadyhand-idx learn: income.run_rate, tax.dividend`
   - `experienced` and `off`: nothing.
   - No keys: nothing, at every level.

   The disclaimer footer is the same at every level. The program name is passed in by the caller, because the engine does not know it.

## 7. The library (`steadyhand.training`)

It uses the standard library only. Everything in it is pure except `Catalogue.load`, which reads only the directories and file it is given, and `steadyhand_idx.training.catalogue()`, which calls `Catalogue.load`.

- `Level`: an enum with `OFF`, `NEW`, `SOME` and `EXPERIENCED`.
- `Lesson`: a frozen dataclass with the header fields, `body` and `origin` (the file it came from, used in errors).
- `Module`: number, slug, title, and its lessons in order.
- `Catalogue.load(roots, course)`: parses every `*.md` under each root and the course file. It returns a `Catalogue`, or raises `LessonError` naming the file and the field for any rule in §4.1 that is broken.
- `Catalogue.lesson(id)` returns the lesson, or raises `LessonNotFound` carrying the closest ids. `Catalogue.for_key(key)` returns the lesson that explains a key. `Catalogue.course()` returns the modules in order.
- `explain(catalogue, keys, level, program) -> str`: the §6 item 4 text, or `""`.
- `steadyhand.training.LESSONS` and `steadyhand_idx.training.LESSONS` are each package's lesson root, found with `importlib.resources`. `steadyhand_idx.training.COURSE` is the course file. `steadyhand_idx.training.catalogue()` loads both roots.

A key with no lesson raises `LessonNotFound` at runtime, because it is a bug. The catalogue guard (§8) makes it unreachable in a released build.

## 8. Guards and tests

Every guard is mutation-proven: its mutation is predicted in writing, run, and seen red. Mutation numbers continue from M4a's last, M103.

**Catalogue guards** load a catalogue from both lesson roots and check the rules below. Until S4 they run against fixture catalogues. S4 points them at the real lesson folders, where they stay:

- every note and term key has exactly one lesson;
- no lesson explains a key that does not exist;
- ids are unique across both packages and each equals its file name;
- every `see_also` resolves and every `sources` path exists;
- course positions within each module run from 1 with no gap and no repeat, and every module slug is in `course.toml`;
- the "Start here" lesson carries `steadyhand.DISCLAIMER` verbatim.

The key sets are derived by the same AST walk as §3.1, not listed.

**Loader tests:** one malformed fixture per rule in §4.1. Each asserts that the `LessonError` names the file and the field, not just that an error was raised.

**Renderer tests:** hand-written expected text for each level. They cover dedup (two keys, one lesson), first-appearance ordering, keys from both packages, no keys, and an unknown key.

**Legal guards:** §5 items 1, 2 and 4, each checked by its own mutation (an import added to `engine.py`; an import of `steadyhand.risk` added to training; `you should buy` added to a lesson).

**The built-wheel check** is a step in CI's `build` job, which runs on pull requests. It installs both wheels into a clean venv, loads `steadyhand_idx.training.catalogue()` from the installed packages, and asserts that its lesson count equals the count of `*.md` files in both source lesson folders. A lesson missing from a wheel is a failure no source-tree test can see.

The existing gates hold: 100% branch coverage, mypy strict, ruff, and the perf budget.

## 9. Stories (milestone T1)

| Story | Delivers | Depends on |
|---|---|---|
| S1 keys | §3: M3's warnings become `Note`s in both packages, `terms.py` with `FIGURES` and its derived guard, and the key meta-test widened to both packages | — |
| S2 catalogue | §4 and §7: the file format, `Lesson`, `Module`, `Catalogue.load`, `course.toml`, the loader tests, and the catalogue guards (run against fixtures, because the real content lands in S4) | S1 |
| S3 renderer and legal line | `Level`, `explain`, the renderer tests, and §5's import guards and advice-phrase scan | S2 |
| S4 content | Every lesson needed for S1's keys and terms, course modules 1–5 and 7 and the backtest half of 6, the catalogue guards switched on over the real content, and the built-wheel check | S3 |

S4 updates `README.md` and both package READMEs to mention the course and the `learn` command that M5 adds. It also adds a short "Contributing" section to `README.md` stating the lesson rule: a new note or term key needs its lesson in the same PR. The repo has no `CONTRIBUTING` file today.

## 10. Risks

- **Lessons state facts that can go stale.** Tax rates, lot sizes and fee rules change by regulation. Every IDX lesson that states a rule value lists its research doc in `sources`, and the value is copied from that doc, never written from memory. If a rule changes, the research doc and its data file change first, and a grep of `sources` finds the lessons to update.
- **Advice by implication.** Plain-English teaching can drift into "what to do". The import rule keeps the level away from decisions, and the phrase scan catches the obvious wording. Each lesson PR is also read against core spec §3 item 3 before merge.
- **Content volume.** Modules 1–5 and 7 are a lot of prose for one story. If S4's PR grows past a reviewable size, it splits by module (S4a, S4b …). The guards already require every key's lesson, so the split changes only the order of work, not the result.

## Spec review log

**Pass 1 (2026-09-27): 6 findings, all fixed.**
1. §3.1 named a class `CorporateResult`; the class is `CorporateOutcome` (read from `corporate.py`).
2. §3.1 said "the four `warnings` fields" but did not list them. It missed `RunResult.warnings` and did not say that `DayReport.warnings` also carries the corporate ones. The fields are now named.
3. §3.2 limited figure fields to `metrics.py` and `income.py`. That missed `DayReport`'s cash and value fields and `BacktestResult`'s nested ones (found with a grep of `Money`/`Decimal` fields in both packages). It is now a walk over types from the report roots.
4. §3.2's example of a shared term named one field twice. It now names two fields.
5. §5 item 4 said "case-insensitively" and then described a capital-letter pattern. The case rule is now stated for each part.
6. §8 said the guards load the real catalogue, while §9 said S2 runs them on fixtures. It now says when each applies. §9 also made the README change conditional on a `CONTRIBUTING` file, which does not exist, so the change is now stated outright.

**Pass 2 (2026-09-27): 1 finding, fixed.** §7 said `load` was the only function that reads files, but `steadyhand_idx.training.catalogue()` reads them too, through `load`. It is now named.

**Pass 3 (2026-09-27): no findings.** Mechanical checks: every section cited (core spec §3, §4.2, §8, §9.8; M4 spec §5, §7) exists with the content claimed. Every existing path cited exists, and the two lesson folders are marked as new. The class and field names in §3.1 match the code at `9d26f16`. The public names in §7 (`Level`, `Lesson`, `Module`, `Catalogue`, `LessonError`, `LessonNotFound`, `explain`, `LESSONS`, `COURSE`, `catalogue`) are used the same way in §5, §6 and §8. Then a whole read. The loop closes here.
