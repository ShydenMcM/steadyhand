# steadyhand M5: Paper trading and the CLI

**Status:** design approved by Shyden in conversation on 2026-09-27, in five sections, after four decisions (§2). The review loop closed on pass 8. The written spec awaits Shyden's review.
**Parent spec:** `2026-09-24-steadyhand-core-design.md` (the "core spec"): §5 (the daily run), §9.3 (cache and state), §9.5 (configuration), §9.6 (CLI), §9.7 (audit log), §9.8 (disclaimers), §13 item 5 and §14. M5 also builds what two earlier plans carried forward: the M4b plan (`2026-09-27-m4b-exemption-claim.md`, "Carried forward") and the T1 plan (`2026-09-27-t1-training-foundation.md`, "Carried forward"), whose user-facing contract is T1 spec §6.

## 1. What M5 delivers

M5 gives the operator a command-line tool, `steadyhand-idx`, for everyday use: `init` once, `backtest` and `compare` to choose a strategy, `paper run` once per trading day, and `paper status`, `report` and `resume` to follow it. The engine is not redesigned. `run_day(state, inputs, …) -> (state, report)` is already pure, and `EngineState` is documented as "M5 saves it". M5 is the shell around that core: configuration, a state database, the daily cycle, the commands and their output.

### 1.1 Delivery: one spec, two plans

As M3 and M4 were, M5 is one spec delivered by two plans (Shyden, 2026-09-27):

- **M5a, configuration and the stateless CLI** (S1–S4): `config.py`, `paths.py`, `cli.py`, `output.py`, and the commands `init`, `training`, `learn`, `backtest`, `compare`, `strategies` and `explain`.
- **M5b, paper trading** (S5–S8): the engine's `snapshot` codec, `state.py`, `paper.py`, and the commands `paper run`, `paper status`, `paper switch`, `report` and `resume`.

M5a ships a usable tool with no persistence risk. M5b puts all of that risk (idempotency, atomicity, migrations) in one plan.

### 1.2 Out of scope

- **Real orders.** Paper mode fills are simulated (core §5.1). The Confirm Fill flow for the operator's real orders belongs to sub-project B+C.
- **Scheduling.** `paper run` is run by cron or similar, as documented in M5's docs. The in-app scheduler belongs to B+C.
- **§14 AC2 in full.** `compare` is built now, but only `buy-and-hold` exists. "All 11 strategies in one table" is met by the strategy waves M6–M9.
- **The live acceptance run.** §14 AC1 against real Yahoo data is a manual run. CI runs the same journey on recorded fixtures.

## 2. Shyden's decisions (2026-09-27)

1. **One spec, two plans**, split as §1.1.
2. **Missed days are caught up in order.** When `paper run` finds trading days missed since its last run, it runs every one of them, oldest first, each in its own transaction, so the paper record matches what an unbroken daily run would have produced (§6.1).
3. **A strategy change needs an explicit command.** `paper run` refuses when the configured strategy differs from the saved one. `paper switch <name>` makes the change (§7.3).
4. **State is a snapshot plus append-only logs.** One current-state row holds the encoded `EngineState`. Append-only tables hold what people query: day reports, the audit log and the run log (§6.3).

## 3. Architecture

### 3.1 Modules

| Module | Plan | Role |
|---|---|---|
| `steadyhand/snapshot.py` | M5b | Versioned codec: `EngineState` and `DayReport` to and from a JSON-safe `dict`. Standard library only (core §4.2). |
| `steadyhand/portfolio.py` | M5b | Gains `Portfolio.restore`, so a decoded snapshot can rebuild a portfolio (§6.3). |
| `steadyhand/backtest.py` | M5b | Its fetch step becomes a public function that paper mode also calls (§6.2). |
| `steadyhand/strategies/registry.py` | M5a | Each strategy gains a one-line `summary` and a `turnover` (§5.5). |
| `steadyhand/strategies/guides/` | M5a | The strategy guides, moved from `docs/strategies/` and shipped as package data (§5.6). |
| `steadyhand_idx/paths.py` | M5a | Finds the data directory (§4.1). |
| `steadyhand_idx/config.py` | M5a | Loads and validates `steadyhand.toml` (§4.2), except the `[training]` table, which it passes on unread. |
| `steadyhand_idx/output.py` | M5a | Parses the `[training]` table and renders every command's text: the body, T1's inline training block, the disclaimer footer (§5.7). |
| `steadyhand_idx/cli.py` | M5a | `argparse` commands, the entry point, and the exit-code table (§8.1). |
| `steadyhand_idx/state.py` | M5b | `StateStore`: the SQLite state database and its migrations (§6.3). |
| `steadyhand_idx/paper.py` | M5b | The daily cycle: which days to run, their inputs, `run_day`, one transaction per day (§6). The CLI calls it, and later so will the B+C scheduler. |

The CLI uses `argparse` from the standard library. A third-party CLI library would add supply-chain surface for no behaviour the spec needs. `steadyhand-idx` keeps its runtime dependencies at `steadyhand` and `yfinance`.

### 3.2 The entry point

```python
def main(
    argv: Sequence[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    env: Mapping[str, str],
    now: Callable[[], datetime],
    source: Callable[[Path], DataSource],
) -> int: ...
```

The console script calls `main` with `sys.argv[1:]`, the real streams, `os.environ`, the real clock and a factory that opens `CachedDataSource` over Yahoo in the data directory. A command's output goes to `stdout`; every error message and the `--debug` traceback go to `stderr`, so a script capturing a report never captures an error in it. Tests call the same function with recorded fixtures and a fixed clock (§9.1). There is no test-only branch in production code.

## 4. Configuration (S1)

### 4.1 The data directory

The data directory is, in order: `--data-dir`, then `$STEADYHAND_HOME`, then `$XDG_DATA_HOME/steadyhand-idx`, then `~/.local/share/steadyhand-idx`. It holds `steadyhand.toml`, `cache.sqlite`, `state.sqlite`, the user-supplied `lq45_members.toml` and `exclusions.csv` (core §9.4), and `reports/`. `init` creates it with mode `0700`. The files M5 writes (the config, the state database and the reports) are created `0600`, because they are the operator's financial record.

### 4.2 `steadyhand.toml`

The schema is core §9.5 plus two tables:

```toml
[training]
level = "new"                         # off | new | some | experienced (T1 §6)

[consent]
disclaimer_accepted = 2026-09-27      # written by init; its absence means init has not run
```

- Validation is core §9.5's: an unknown key, a wrong type or an out-of-range value is an error that names the key, and exits 2. A rate given as a TOML float is refused, because rates are strings parsed to `Decimal`.
- Every key is optional except `[consent] disclaimer_accepted`. A missing key takes the value core §9.5 shows, and `[training] level` takes `new`.
- `config.load(path)` returns a frozen `Config`. It builds `EngineSettings`, `BacktestSettings` and the `IncomeGoal`. `broker_fees` names a preset in `fees.toml`, or `custom`.
- **`[training]` is parsed by `output.py`, not `config.py`** (T1 §5 item 3: the setting stays in the output layer). `Config` carries the table as an unread mapping, and `output.py` validates it with the same rules and turns it into T1's `Level`. So `config.py`, which every command reads, never imports `steadyhand.training`.
- Paths in `[universe]` are relative to the data directory. An absolute path is allowed.
- A missing config means `init` has not run. Every command except `init`, `learn`, `explain`, `strategies`, `--help` and `--version` then exits 2 with `run steadyhand-idx init first`. Those need no config, and with none, the training level is `new`.

## 5. The stateless commands (S2–S4)

### 5.1 `init` (S2)

1. It exits 2 if `steadyhand.toml` already exists. It never overwrites.
2. It prints `steadyhand.DISCLAIMER` and reads one line, which must be exactly `I understand`. Anything else exits 2. There is no flag to skip this: a script pipes the words in.
3. It asks T1 §6 item 1's two training questions. `--training off|new|some|experienced` answers both.
4. It asks `Claim the dividend reinvestment exemption? [y/N]`, after one plain line saying what the exemption is. The default is off. `--exemption on|off` answers it.
5. It creates the data directory (§4.1) and writes `steadyhand.toml` with every key present, each with a one-line comment saying what it does, the chosen `[training]` level and `[tax]` switch, and `[consent] disclaimer_accepted` set to today's Jakarta date.
6. It prints the config's path and says to set the starting cash, the income goal and the LQ45 file there. It does not ask for money amounts.

### 5.2 `training` and `learn` (S2)

Exactly T1 §6 items 2 and 3. `training <level>` changes only the `[training] level` line of the config, adding the table or the line when absent, and leaves every other byte of the file (comments included) unchanged. The file is reloaded and validated after the write; if it no longer validates, the original bytes are restored and the command exits 1.

### 5.3 `backtest --from --to [--strategy]` (S3)

- The strategy defaults to `[strategy] name`. Data comes through `CachedDataSource` over Yahoo, in the data directory.
- The terminal summary shows return, drawdown, costs, dividends and the income-goal figures for the strategy beside `buy-and-hold` (core §14 AC1), then the run's warnings (survivorship gaps, refused data).
- It writes `reports/backtest-<strategy>-<from>-<to>.md`, which holds the same summary, and `reports/backtest-<strategy>-<from>-<to>.csv`, one row per trading day with value, settled cash, unsettled cash, holdings value and the dividends received. A second run over the same range replaces both files.
- A start before the rules' verified date (`MarketRules.require_supported`) or before the universe's first record exits 2, naming the table or the date. A missing LQ45 file exits 2, naming `[universe] lq45_members`.

### 5.4 `compare --from --to s1 s2 …` (S3)

It fetches once and runs every named strategy over the same window, adding `buy-and-hold` as the baseline row unless it is named. It prints one table, a row per strategy with the same columns as `backtest`, and writes `reports/compare-<from>-<to>.md` and `.csv`. A repeated name, or an unknown one, exits 2.

### 5.5 `strategies` (S4)

It lists each registered strategy: name, one-line summary and turnover (`low`, `medium` or `high`). The registry's entry for each strategy gains `summary` and `turnover`, and a test fails if either is empty for any strategy.

### 5.6 `explain <strategy>` (S4)

It prints the strategy's guide. An unknown name exits 2 and names up to three close names (`difflib`), as `learn` does.

The guides move from `docs/strategies/` to `packages/steadyhand/src/steadyhand/strategies/guides/`, so they ship in the wheel as T1's lessons do. The core §10.1 guard, that every registered strategy has a complete guide, follows them, and a new test builds the wheel and checks each guide is inside it. `docs/strategies/` keeps a README pointing at the new place.

### 5.7 Output (S2)

Every command prints its body, then T1's inline training block for the keys the body showed, at the configured level (T1 §6 item 4), then the disclaimer footer. The output is plain text with no colour, so nothing depends on a terminal library. `output.py` is the only new module allowed to import `steadyhand.training`: T1 §5 item 1's allowlist gains `steadyhand_idx.output` and nothing else. Because `output.py` is also the module that parses `[training]` (§4.2), T1 §5 item 3's "cover the module that parses it" is met by the same entry (T1 plan, "Carried forward"). `config.py` and `cli.py` stay outside the allowlist, so the guard fails if either imports training.

## 6. Paper trading (M5b: S5–S7)

### 6.1 Which days `paper run` runs (S7)

- **The target** is the latest completed trading day: today in Jakarta if it is a trading day and the time there is at or after 16:30, else the previous trading day. 16:30 WIB follows core §5: after the close and after the post-closing session ends at 16:15.
- **The days to run** are every trading day after the saved `last_day`, up to the target, oldest first.
- **None to run:** it prints `already up to date for <day>` and exits 0. Running twice is safe.
- **More than 30 days to run:** it exits 2, saying how many and asking for `paper run --catch-up`, which lifts the cap. A long absence never replays unseen.
- **The first run** opens the paper account on the target day with `[account] starting_cash_idr` (`EngineState.opening`), saves the strategy's name, and runs that day.

### 6.2 Each day's inputs (S7)

`backtest`'s fetch step (`_fetch` and the `DayInputs` construction in `_run`, M3 spec §7.1) becomes one public engine function that returns every day's `DayInputs` over a range of trading days. `paper.py` calls it over the whole range from the opening day to the target, and runs only the days after `last_day`. So paper mode and the backtester build `DayInputs` in exactly the same way. That includes the `refused` and `resumed` sets, which depend on days before the one being run. History runs from the opening day, as a backtest's history runs from its start. Reading that range again on every run costs cache reads, not downloads, and §9.3 measures it.

This gives M5b its golden invariant: **a paper account opened on D1 and run day by day to Dn, with its configuration unchanged, ends in the same `EngineState` as `backtest` from D1 to Dn**, and every day's report is equal too.

### 6.3 The state database (S5, S6)

**The codec (S5)** is `steadyhand.snapshot`: `encode_state`, `decode_state`, `encode_report` and `decode_report`.

- `Money` becomes `{"amount": <int>, "currency": "<code>"}`, `Decimal` a string, a date its ISO form, an `Enum` its value, and an `Instrument` its market and symbol. A mapping keyed by `Instrument` (`Holdings.frozen`, `Holdings.last_closes`), whose keys JSON objects cannot hold, becomes a list of `[instrument, value]` pairs sorted by market then symbol. The JSON is canonical (sorted keys, no whitespace), so equal states encode to equal bytes.
- The document carries a top-level `version`. Each older version is upgraded by one explicit function per version step. A version newer than the code knows raises `SnapshotVersionError`, which exits 2: `this state was written by a newer steadyhand`.
- The whole ledger is encoded. When the snapshot is decoded, the portfolio is rebuilt once. It is never re-walked day by day (#84's design note).
- `Portfolio` has no public way to be rebuilt today: `empty`, `deposit`, `charge`, `credit_dividend`, `apply_split` and `apply_fill` only build one forwards, and the ledger does not hold the fills that made the positions. S5 adds `Portfolio.restore(currency, positions, ledger)`. It computes the balance and the open (unsettled) movements from the ledger, as the forward path does. It raises `ValueError` if anything the forward path guarantees does not hold: the ledger is in date order, every amount is in the portfolio's currency, and every position has a positive quantity and a stock of its own. A restored portfolio then behaves exactly as the original: equal `ledger`, balances and positions, and equal results from every later operation, which the round-trip tests assert.

**The schema (S6)** lives in `state.sqlite`. Migrations are versioned and applied in order, on `BarCache`'s pattern (core §9.3):

| Table | Holds |
|---|---|
| `account` | One row: `opened_on`, `strategy`, the encoded state, `last_day`, and the settings the last day ran with (for §6.5) |
| `day_reports` | `day` (primary key) and the encoded report. The primary key is core §9.3's "unique per trading date". |
| `audit` | `day`, `key`, `line`: a stable note key, so T1 can explain it, and the plain-English line of core §9.7 |
| `runs` | One row per `paper run`, written in its own transaction when the run ends: the UTC time, the target day, the days run, the outcome (`ran`, `up to date`, `stopped`, `halted`) and detail. A run killed part-way leaves no row; the days it committed are still in `day_reports`. |

A database whose schema version is newer than the code exits 2.

### 6.4 Atomicity and concurrency (S7)

- Each day is one `BEGIN IMMEDIATE` transaction. It writes the new state into `account`, the day's report and its audit lines, then commits. A crash rolls it back, and the next run redoes that day.
- Inside the transaction the store re-reads `last_day`. A second `paper run` started at the same time waits on SQLite's lock (a busy timeout, whose value the M5b plan sets), then finds the day done and does nothing. Each day is run exactly once.

### 6.5 Stops, halts and configuration changes (S7)

- **Stops.** Stale, missing or impossible data (core §5 step 1; the engine's `DataValidationError`) stops the run. That day is not saved, and nothing trades. Days already caught up earlier in the same run stay saved. The stop is recorded (the `runs` row and an audit line) in its own small transaction. Exit 3.
- **Halts.** A kill switch firing (core §6.1) is saved with its day. Later days still run: valuations, settlement and dividends continue, and no orders are made. Every `paper run` exits 3 while the account is halted, and prints the halt's audit line and the exact `resume` command. The read-only commands (`paper status`, `report`) exit 0 on a halted account and show the halt.
- **Strategy:** a configured strategy different from the saved one exits 2, naming both and `paper switch` (§2 decision 3).
- **Starting cash** is only used at opening. A later change is ignored: the first `paper run` that sees it writes one audit line saying so, and later runs, finding the value unchanged since, write nothing more.
- **Every other setting** (the contribution, risk limits, the fees preset, the exemption switch, the pay lag, the goal) follows the config from the next day run. Each change is recorded as an audit line naming the key and both values. Open exemption claims keep being settled whichever way the switch is set, because `run_day` settles claims unconditionally (M4b).

## 7. The paper commands (S8)

### 7.1 `paper status`

It shows: the opening day, the strategy, the last day run, the halt (if any, with the exact `resume` command), settled, unsettled and dividend cash, the holdings (quantity, last close, value and weight), queued orders, pending dividend entitlements, open exemption claims under `IncomeReport.claims_label`, and frozen stocks with their reasons.

### 7.2 `report [--day D] [--income]`

- `report` prints a saved day report, by default the latest: fills, orders queued, blocked orders with their reasons, cash (settled and unsettled), holdings, dividends received and upcoming, and income-goal progress (core §5 step 7). An unknown day exits 2, naming the first and last days saved.
- `report --income` prints the M4 income view. It calls `income_report` with every saved day report in order, the saved state, and the corporate-action history that function needs for the stocks held, fetched through the data source (M4 spec §3.2). It shows received income, the run-rate, the payment calendar, goal progress, the three scenarios under `Projection, not a promise` (core §14 AC7), and the open claims under their label (M4b plan, "Carried forward").

### 7.3 `resume <strategy>` and `paper switch <name>`

- `resume <strategy>` must name the saved strategy, or it exits 2. It shows the halt's day and cause, and asks the operator to type `resume`. Then it clears the halt, writes an audit line and exits 0. When nothing is halted, it says so and exits 0.
- `paper switch <name>` makes the saved strategy follow a config the operator has already edited: `<name>` must be the configured strategy and differ from the saved one, or it exits 2. The flow is: edit `[strategy] name`, `paper run` refuses and prints the exact `paper switch` command, run it. It is refused while halted (resume first). It asks the operator to type the new name. It keeps holdings and cash, clears the strategy memory (`EngineState.memory`, which means nothing to another strategy), saves the new name, and writes an audit line. From the next day run, the new strategy rebalances from the existing holdings.
- There are no `--yes` flags. Confirmations are typed, and a script pipes them in, as with `init`. Any other answer, or none (end of input), exits 2 and changes nothing.

### 7.4 Keys and lessons

Every audit line and every `Tradable.why_not` reason gets a stable note key (T1 §1.1: decided in M5), and by T1's rule each new key has its lesson in the same PR. Each reason becomes a `Note` built from a key constant with its text unchanged, as T1 §3.1 did for M3's warnings. `Halt.cause` becomes a `Note` in the same way, so a halt's audit line carries its key.

Each key ships, with its lesson, in the story that first writes it. S7 writes the day's decision lines (core §9.7: orders queued, orders skipped with their reason), stops, halts (with `Halt.cause`) and configuration changes. S8 writes the `resume` and `paper switch` lines, and the `Tradable` reasons as `report` shows them. T1's module 6 (paper trading) lessons ship in M5b, and M5's new report types join `test_terms.py`'s roots (T1 plan, "Carried forward").

## 8. Errors

### 8.1 Exit codes

`cli.main` maps each error type to core §9.6's exit codes in one table, and a test pins every row:

| Code | Meaning | Raised by, among others |
|---|---|---|
| 0 | success, including `already up to date` | |
| 2 | usage or configuration error | `argparse` errors, config validation, `init` not run, an unknown strategy or lesson, the catch-up cap, a strategy mismatch, `SnapshotVersionError`, a newer schema |
| 3 | halted, or stopped safely | `DataValidationError` and the other core §5 step 1 stops, a `paper run` on a halted account |
| 1 | unexpected error | anything not in the table |

### 8.2 Unexpected errors

An unexpected error prints one plain line and `run again with --debug for details`, then exits 1. `--debug` prints the traceback.

## 9. Testing

### 9.1 Seams, not mocks

CLI journeys call `main` in-process (§3.2) with the recorded Yahoo fixtures the golden tests already use, a temporary data directory and a fixed clock. A few journeys run the installed `steadyhand-idx` in a subprocess: `init`, `strategies`, `explain`, `learn`, `training`, and the exit codes. These need no network. No test stubs steadyhand's own code.

### 9.2 Required tests

- **Golden invariant:** paper from D1 to Dn equals `backtest(D1, Dn)`, state and reports (§6.2).
- **Idempotency:** running `paper run` twice leaves `account`, `day_reports` and `audit` identical, and `runs` gains exactly one `up to date` row.
- **Atomicity:** a real SQLite trigger in the test's database, `BEFORE INSERT ON day_reports … RAISE(ABORT)`, makes the day's transaction fail after `account` was updated. The database is left at the previous day. With the trigger dropped, the next run completes the day. No steadyhand code is stubbed.
- **Concurrency:** two `paper run` processes started together run each day exactly once.
- **The 16:30 boundary:** 16:29:59 against 16:30:00 WIB, on a trading day, a weekend and a holiday.
- **The catch-up cap:** 30 days to run proceeds, 31 exits 2, and 31 with `--catch-up` proceeds.
- **Migrations:** a fresh database reaches the pinned schema version, and a newer version exits 2.
- **Codec:** a hypothesis round-trip property over generated states and reports, a round-trip of every day of the golden backtest, a version upgrade, and a newer version refused.
- **Configuration:** boundary values for every key, an unknown key, a wrong type, and a float where a rate string belongs.
- **Legal guard:** T1 §5's import allowlist gains `steadyhand_idx.output` only, and a mutation adding a training import to `config.py` goes red.
- **Permissions:** the data directory is `0700`, and the files M5 writes are `0600`.
- **Guides:** every registered strategy's guide is inside the built wheel.

Every new guard is mutation-verified in its plan, as in M3, M4 and T1.

### 9.3 Non-functional

- **Performance budgets are measured, not guessed.** Each plan measures, in its scratch build: one day's `paper run` on a five-year state, a 30-day catch-up, CLI start-up, and the snapshot's size after five years. It then pins each budget with headroom, as M3's 30-second budget was. The measurements go in the plan.
- **Security.** SQL is parameterised only. The configuration is TOML, parsed and never evaluated. File modes are as §4.1.

## 10. Stories

| Story | Plan | Delivers |
|---|---|---|
| S1 | M5a | `paths.py`, `config.py` and the `Config` type, with every validation rule and boundary test |
| S2 | M5a | `cli.py`'s shell and exit-code table, `output.py`, `init`, `training`, `learn`, and the legal guard's extension |
| S3 | M5a | `backtest` and `compare`, with their terminal output and report files |
| S4 | M5a | Guides moved into the wheel, the registry's `summary` and `turnover`, `strategies`, `explain`, and the M5a CLI journeys |
| S5 | M5b | `Portfolio.restore`, `steadyhand.snapshot`, and their round-trip tests |
| S6 | M5b | `state.py`: schema, migrations and `StateStore` |
| S7 | M5b | `paper.py` and `paper run`: day selection, catch-up, the public fetch, atomicity, stops, halts and configuration changes, the golden invariant, and the audit keys it writes with their lessons (§7.4) |
| S8 | M5b | `paper status`, `report`, `resume` and `paper switch`, their audit keys and the `Tradable` keys with their lessons, T1 module 6, and the M5b journeys |

## 11. Risks

- **The snapshot grows with the ledger.** It is rewritten once per day, so its size sets the cost of each day's write. The M5b plan measures it (§9.3). If the five-year size is too large, the fallback is to move the ledger into an append-only table, which the codec's `version` allows without breaking saved accounts.
- **Yahoo lags the close.** At 16:30 WIB, Yahoo may not yet have the day's bar. The run then stops with exit 3 (stale data) and trades nothing, and the next run catches the day up. The docs suggest a cron time with margin.
- **Configuration drift between days breaks the golden invariant** by design. The invariant is asserted only with the configuration unchanged, and every change is visible in the audit log.

## Spec review log

**Pass 1 (2026-09-27): 11 findings, all fixed.** Mechanical checks: every internal section reference resolves, and every core, M3 and T1 section cited exists with the content claimed. Every code name cited was read from the code at `24545c5`: `EngineState.opening`, `EngineState.memory`, `MarketRules.require_supported`, `DataValidationError`, `Tradable.why_not`, `Halt.cause`, `IncomeReport.claims_label` (a property), `CachedDataSource`, `jakarta_today`, `BarCache`, `steadyhand.DISCLAIMER`, `Level`, `backtest._fetch` and `_run`, `tests/meta/test_terms.py`. Then a whole read.
1. §4.2 had `config.py` parse `[training]`, against T1 §5 item 3 (the setting stays in the output layer). `output.py` now parses it, and `config.py` stays outside the import allowlist (§3.1, §5.7, §9.2).
2. §8.1 mapped "an account that is halted" to exit 3 for every command. Only `paper run` exits 3; `paper status` and `report` exit 0 (§6.5).
3. §6.4 wrote `runs` detail in each day's transaction, while §6.3 made `runs` one row per invocation. `runs` is now written once, when the run ends, in its own transaction.
4. §9.2's idempotency test said the database is identical after a second run, but that run adds a `runs` row. The test now names the three tables that stay identical.
5. §9.2's atomicity test had no mechanism that avoids stubbing. It now uses a real SQLite trigger.
6. §5.4 added `buy-and-hold` even when it was named, which would give two rows. It is added only when not named.
7. §6.2 did not say the public function covers the range from the opening day. `refused` and `resumed` depend on earlier days, so running only the new days would break the golden invariant.
8. §5.2 did not say what happens when the `[training]` line is absent, or when the rewrite breaks the file.
9. §4.2 did not say which keys are required. Only `[consent] disclaimer_accepted` is; the rest take core §9.5's values.
10. §4.2 required a config for `strategies`, `--help` and `--version`, which need none.
11. §6.4's waiting second run needs a busy timeout, which is now named, with its value left to the M5b plan.

**Pass 2 (2026-09-27): 4 findings, all fixed.** A whole read, then a check of `income_report`'s signature and T1 §3.1's wording against the code and the T1 spec.
1. §7.2 said `report --income` works "from the saved state". `income_report` also needs every day report in order and a corporate-action history for the stocks held (M4 spec §3.2), which is fetched through the data source. It now says so.
2. §7.3 saved the name given to `paper switch` without saying how it relates to the config. With the config unchanged, the next `paper run` would have refused again. `<name>` must now be the configured strategy, and the flow is spelled out.
3. §7.4 said `Halt.cause` and the `Tradable` reasons "become keyed" without saying how. Each becomes a `Note` from a key constant, as T1 §3.1 did for M3's warnings.
4. §5.1 step 5's "every key present and commented" could mean commented out. It now says each key carries a one-line comment.

**Pass 3 (2026-09-27): 1 finding, fixed.** A whole read.
1. §7.4 and §10 put every audit key in S8. But S7 is the story that first writes most audit lines (decisions, stops, halts, configuration changes), and T1's rule wants each key's lesson in the PR that adds the key. Each key now ships in the story that first writes it, and the S7 and S8 rows say which.

**Pass 4 (2026-09-27): 2 findings, fixed.** Mechanical checks: all 17 internal section references resolve; the cross-spec references (M3 §7.1, M4 §3.2, T1 §1.1, §3.1, §5 items 1 and 3, §6 items 1 and 4) exist, and T1 §1.1 does leave the `Tradable` and audit-log keys to M5. Then a whole read.
1. §3.2's `main` had no `stderr`, so error messages would have gone into a report a script captures. `main` now takes `stderr`, and errors and `--debug` output go there.
2. §7.3 did not say what a wrong typed confirmation does. Any other answer, or end of input, exits 2 and changes nothing.

**Pass 5 (2026-09-27): 1 finding, fixed.** A whole read, then a check of `Portfolio`'s public API against the codec's "rebuilt once".
1. §6.3 said the decoded portfolio is "rebuilt once" without naming how. `Portfolio` has no public constructor from saved parts, and its ledger cannot be replayed forwards because it does not hold the fills. S5 adds `Portfolio.restore` with its checks (§3.1, §6.3, §10).

**Pass 6 (2026-09-27): 1 finding, fixed.** Every paragraph changed since pass 4's whole read was read again, and every type the codec must build was checked in the code: `Note`, `Rejected`, `Cut`, `Instrument`, `Split`, `Order`, `Fill` and `Position` are public frozen dataclasses with no private fields, so only `Portfolio` needs a new constructor (pass 5).
1. §6.3 did not say how `Holdings.frozen` and `Holdings.last_closes` are encoded. They are keyed by `Instrument`, which a JSON object key cannot be, and canonical bytes need a fixed order. They become sorted lists of pairs.

**Pass 7 (2026-09-27): 1 finding, fixed.** Mechanical checks: every internal reference resolves (§1.1–§9.3), and the §9.5–§9.8 references are the core spec's, all present. Then a whole read of the body.
1. §6.5 said `paper run` reports a changed starting cash "once", which could mean once per run or once ever. It is once ever: the first run that sees the change writes one audit line, because the settings saved with each day then hold the new value.

**Pass 8 (2026-09-27): no findings.** The mechanical checks were re-run with the same result. A `diff` of the body against pass 7's whole read shows exactly one changed line, pass 7's fix, and it was read in context against §6.3's `account` row, which saves the settings each day ran with. The loop closes here.
