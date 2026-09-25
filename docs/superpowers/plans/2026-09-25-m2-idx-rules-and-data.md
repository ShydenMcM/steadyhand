# M2 IDX Rules and Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `steadyhand-idx` everything the engine needs to know about the Indonesia Stock Exchange and its prices: dated, primary-verified rule tables (holidays, ticks, lots, settlement, auto-rejection bands, fees and taxes) behind `IdxMarketRules`, unadjusted Yahoo `.JK` prices behind `YahooDataSource`, a local SQLite cache in front of it, and the user-supplied LQ45 universe.

**Architecture:** Every market value is a row in a TOML file under `steadyhand_idx/data/`, with the date it takes effect and the document it comes from. A shared reader (`_datafile.py`) turns each table into a `Dated[T]` that refuses any day before its first row, naming the table. `IdxMarketRules` composes the calendar, tick, band and fee tables, and derives `verified_from` (the first day every table can answer for) from the files. `YahooDataSource` converts Yahoo's split-adjusted history back into traded prices, and refuses any day it cannot recover. `CachedDataSource` fetches only what the SQLite cache is missing, and stores a day only once it is over. The universe module reads the user's own LQ45 and exclusion files; nothing is downloaded from IDX.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, `yfinance==1.7.0` (the IDX package's one third-party dependency), `pandas-stubs` (dev, for typing yfinance's DataFrames), `sqlite3`, `tomllib`, pytest + hypothesis, mypy `--strict`, ruff, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md`. M2 is §13 item 2. It implements §3.6, §4.1 (the IDX modules), §4.3 (`MarketRules` final form, `DataSource`), §5.1 (costs), §9.1–9.4, §10.2 (rule properties and boundaries) and §10.3 (recorded real data). The research it rests on is in `docs/research/t-*.md`; each data row names its source.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (§4.2). `steadyhand-idx` depends on `steadyhand` and `yfinance`, pinned exactly: `yfinance==1.7.0` (§9.2).
- `float` never enters money or rate code (§4.4). The IDX package meets floats only at the Yahoo boundary and converts each at once with `Decimal(repr(float(x)))`. Rates in data files are percentages written as strings (`"0.018"` is 0.018%).
- **Every market value is dated data in a file, never a constant in code** (§3.6, §9.1). **Only primary-verified rows ship** (Shyden, 2026-09-25). A lookup before a table's first row raises `UnsupportedDateError` naming the file and table.
- `IdxMarketRules.verified_from` is **derived** as the latest first date of any table in `tick_sizes.toml`, `auto_reject.toml`, `fees.toml` and `holidays.toml` (§9.1). With these files it is **2021-01-01, set by `fees.toml [stamp_duty]`**. No code names that date.
- Stamp duty is charged **as the law imposed it** (Shyden, 2026-09-25): Rp10,000 per trade confirmation, one per trading day with trades, from 2021-01-01; from 2022-01-12 only on a day whose buys plus sells exceed Rp10,000,000 (UU 10/2020, PP 3/2022).
- Rounding happens once per trade, against the trader: the cost total rounds up (§4.4, §5.1).
- TDD (§10): tests are written first and run against stubs that raise `NotImplementedError("<name>")`. A test that passes against a stub is a finding, fixed or listed with its reason. Every `pytest.raises` has a `match=`, written as a raw string (ruff RUF043).
- **No test computes a shared value at module level.** Shared values come from `functools.cache` helpers called inside each test, so a stub fails the test that uses it rather than the whole file at collection (CLAUDE.md, 2026-09-23).
- 100% branch coverage (§10.5). Exactly **one** piece of shipped code is excluded: `yahoo.download_history`, the only network call. `tests/meta/test_coverage_exclusions.py` holds it to that.
- Pull-request CI never talks to Yahoo. Live tests carry the `live` marker, which `addopts` deselects; only the daily `yahoo-shape` workflow runs them.
- Nothing is downloaded from idx.co.id, and no LQ45 list is ever written into the repository. Test lists are synthetic (§9.4, `docs/research/t-lq45.md` §5).
- Test file basenames are unique across `tests/` (mypy maps each to a top-level module name).
- English only. The phrase "robot trading" never appears (§1.3). Every user-facing doc carries the disclaimer verbatim: `steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.`
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (§11).

## Review Focus

1. **A stock whose Yahoo history carries a rights issue.** Yahoo scales every earlier price by an unpublished factor. Measured on 2026-09-25 over 25 large IDX stocks for 2021–2025: BBRI to 2021-09-07, SMGR to 2022-12-12, MDKA to 2022-04-13 and five INCO days in June 2024 cannot be turned back into traded prices. Expected: the request is refused with every such day named, and nothing is cached. Pinned in Task 5 (`test_an_unreported_adjustment_is_refused_with_every_day_named`) and Task 6 (`test_unrecoverable_prices_are_never_cached`).
2. **A split after the requested range.** Asking in 2026 for BBCA in September 2021 returns prices Yahoo has divided by five for the October 2021 split. Expected: the traded prices (Rp32,750, not 6,550). Pinned in Task 5 (`test_splits_are_reversed_using_the_whole_split_history`).
3. **A date outside the verified data**, before 2021-01-01 or in 2028. Expected: every rule refuses it, naming the table, and never falls back to "today's rules" or "no holidays". Pinned in Task 4 (`test_every_rule_refuses_an_unverified_day`, `test_a_year_past_the_holiday_data_is_refused`).
4. **A cache request that ends on a Friday, or includes today.** Expected: a weekend-only gap is not fetched (Yahoo would answer "no rows" and fail the run), and today's unfinished bar is never stored. Pinned in Task 6 (`test_only_the_missing_trading_days_are_fetched`, `test_today_is_always_fetched_and_never_stored`).
5. **A value exactly on a boundary**: a price of 200 or 5,000 (the higher tier for ticks, the lower for bands), a day's trading of exactly Rp10,000,000 on 12 Jan 2022 (exempt). Pinned in Task 2 (`test_every_tier_boundary_on_both_sides`, `test_the_tier_edges_are_inclusive_of_the_upper_bound`) and Task 3 (`test_stamp_duty_is_charged_as_the_law_imposed_it`).

## Scope decisions (read before starting)

1. **Stamp duty is a per-day charge, through a new protocol member.** §4.3's `costs(side, gross, on)` is per trade and cannot charge a per-confirmation amount. `MarketRules` gains `daily_costs(traded, on)`: the charges made once per trading day, given the day's buys plus sells. M3's engine calls it once per day with trades. `costs` stays per trade.
2. **The refusal date is a protocol property, derived from the data.** `MarketRules` gains `verified_from` and `require_supported(day)`. The IDX implementation takes the latest first date of every table in the four files, and its error names the table (today `fees.toml [stamp_duty]`). M3's backtest calls `require_supported(start)` before its first day.
3. **T+2 is data too, and it is now primary-verified.** No research doc verified the settlement cycle, so this plan did: POJK 21/POJK.04/2018 Pasal 2(2) sets T+2 for the regular market, in force on promulgation, 21 Nov 2018 (Pasal 13; BPK status *Berlaku*). The market's first T+2 trade day is 26 Nov 2018 according to the press (Bareksa, 26 Nov 2018, and Hukumonline; **secondary**), so the `[[settlement]]` row in `tick_sizes.toml` starts on that later date, where both readings agree. `docs/research/t-rules.md` records this in the plan PR (Task 0).
4. **Broker presets: `ajaib` and `custom` only.** Ajaib's page states what its all-in rate includes. Stockbit and Indo Premier do not, so their `includes` list would be a guess, and a wrong guess either charges the levy twice or drops the sale tax. That conflicts with the rule that only verified rows ship. A Stockbit or IPOT user sets up `custom` (configurable in M5). The `min_fee` field is dropped, because no broker publishes one; M5's config can add it.
5. **VAT is its own dated table,** because it applies to the levy and to a broker's commission. Dividend tax is a dated table in `fees.toml` too. `dividend_tax` keeps M1's signature; M4 reshapes it (§6.2).
6. **`sessions.toml` is deferred to M5,** where paper-run scheduling first reads it. A data file with no reader is untested data.
7. **The "impossible data" check is M3's,** in `run_day` step 1, with the other stop conditions. Its contract, from `docs/research/t-verify.md` §4.2: from 7 Sep 2020 (so on every day from `verified_from`) the reference price is the previous close, except on a stock's first trading day (the IPO price) and a split's ex-date (the theoretical price). Task 5 already runs exactly that check over the recorded real data.
8. **Yahoo is converted, not trusted.** Reported splits are reversed using the stock's whole split history. A day whose reversed prices are not whole rupiah raises `UnrecoverablePricesError` (a `DataUnavailableError`) listing every such day. Zero-volume bars on trading days stay, as "did not trade", and §5.1 rejects orders on them. UNVR on 2023-05-24 shows why that is the cautious reading: its open and close differ, so Yahoo simply lost the volume. A flat, empty bar on a holiday is a placeholder and is dropped. Trading on a holiday contradicts the calendar and is refused.
9. **Cache semantics.** The cache records which ranges were fetched, not which days have bars, so a Yahoo gap is not re-fetched forever. A day counts as fetched only once it is over in Jakarta. A value that differs from one already cached refuses the whole fetch. The schema is versioned with `PRAGMA user_version`.
10. **`universe.py` is in M2.** No milestone names it, but §4.1 puts it in `steadyhand-idx` and M3's backtests need it. **`exclusions.csv` is user-supplied**, like the LQ45 file. §4.1 listed it under the package's `data/`, but the Special Monitoring Board list is IDX data, and an operator's own exclusions are personal. There is **no LQ45 PDF importer**. §8's "another universe" config key is M5's.
11. **Typing yfinance.** `pandas-stubs` joins the dev group. yfinance ships no types, so one mypy override covers that module only, and it is imported only inside `download_history`.
12. **One M1 test changes:** `tests/scripts/test_set_dev_version.py` asserted the IDX package's dependencies were exactly the engine pin. It now derives the expected list, so a yfinance bump cannot break it. This is the M1 plan's carry-forward, which checked that `set_dev_version.py` still finds the engine line once `uv add` rewrites the dependencies: it does.

## File map

| File | Task | Responsibility |
|---|---|---|
| `packages/steadyhand/src/steadyhand/market.py` | 1, 4 | `UnsupportedDateError` (1); `verified_from`, `require_supported`, `daily_costs` on `MarketRules` (4) |
| `packages/steadyhand/src/steadyhand/__init__.py` | 1 | Exports `UnsupportedDateError` |
| `packages/steadyhand-idx/src/steadyhand_idx/_datafile.py` | 1 | TOML reading, typed getters naming file/row/key, `Where`, `Dated[T]` |
| `.../steadyhand_idx/calendar.py`, `data/holidays.toml` | 1 | IDX trading days 2016–2027, each year's arithmetic checked on load |
| `.../steadyhand_idx/ticks.py`, `data/tick_sizes.toml` | 2 | Tick tiers, board lot, settlement cycle |
| `.../steadyhand_idx/bands.py`, `data/auto_reject.toml` | 2 | Auto-rejection bands and minimum price |
| `.../steadyhand_idx/fees.py`, `data/fees.toml` | 3 | Levy, VAT, sale tax, stamp duty, dividend tax, broker presets |
| `.../steadyhand_idx/rules.py` | 4 | `IdxMarketRules`, `RuleTables`, the derived `verified_from` |
| `.../steadyhand_idx/yahoo.py` | 5 | `YahooDataSource`, split reversal, recording format, the one network call |
| `scripts/record_yahoo_fixture.py`, `tests/fixtures/yahoo/*.json` | 5 | Recording real responses; three recorded ranges |
| `.github/workflows/yahoo-shape.yml` | 5 | Daily live check that opens an issue on failure |
| `.../steadyhand_idx/cache.py` | 6 | `BarCache` (SQLite) and `CachedDataSource` |
| `.../steadyhand_idx/universe.py`, `docs/lq45-members.md` | 7 | User-supplied LQ45 membership, survivorship warnings, exclusions |
| `.../steadyhand_idx/__init__.py` | 1, 3–7 | The IDX public API, growing with each story |
| `.github/workflows/ci.yml` | 3 | The build job checks the IDX wheel carries its data |
| `pyproject.toml`, `packages/steadyhand-idx/pyproject.toml`, `uv.lock` | 5 | yfinance, pandas-stubs, the mypy override, the `live` marker |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | The plan, spec pass 14 and the stories (docs) | `plan/m2-idx-rules-and-data` |
| 1 | S1 Data-file reader and IDX calendar | `m2/s1-calendar` |
| 2 | S2 Tick table, lot, settlement and auto-rejection bands | `m2/s2-ticks-bands` |
| 3 | S3 Fees, taxes and broker presets | `m2/s3-fees` |
| 4 | S4 IdxMarketRules and the final MarketRules protocol | `m2/s4-rules` |
| 5 | S5 Yahoo data source, recorded fixtures and the daily shape check | `m2/s5-yahoo` |
| 6 | S6 SQLite cache and cached data source | `m2/s6-cache` |
| 7 | S7 LQ45 universe and exclusions | `m2/s7-universe` |

Stories merge in order: each one's code imports the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Then ask Shyden to approve the merge with `AskUserQuestion`, naming the PR, the head SHA **as read from the file in that same turn** (`cut -c1-7 "${TMPDIR}/head-sha"`), and the CI state. Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI. Find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

---

### Task 0: The plan, spec pass 14 and the stories

This task is documentation only, on `plan/m2-idx-rules-and-data`. Its PR carries this plan, the spec edits below, the T+2 research note and `HANDOVER.md`.

- [ ] **Step 0: File the plan ticket.** Create an issue titled "M2 plan: IDX rules and data" whose acceptance criteria are: the plan is reviewed to zero findings and self-approved (logged in its review log); spec pass 14 is applied; the T+2 research note is added; S1–S7 are filed with their acceptance criteria and are on the board as Todo. Add it to the board and read the card back.
- [ ] **Step 1: Spec pass 14.** Edit `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` so it matches the scope decisions above: §3.6 cites POJK 21/POJK.04/2018 for T+2; §4.1's tree lists `ticks.py`, `bands.py`, `fees.py` and no shipped `exclusions.csv`; §4.3 shows `verified_from`, `require_supported` and `daily_costs`; §5.1 states that stamp duty is charged per trading day through `daily_costs`, as the law imposed it; §9.1 names `ajaib` and `custom` as the presets, puts the lot and settlement cycle in `tick_sizes.toml`, and defers `sessions.toml` to M5; §9.2 records Yahoo's adjusted prices, the split reversal, the unrecoverable-day refusal and the zero-volume rule; §9.4 makes `exclusions.csv` user-supplied; §13's M2 line names `universe.py`. Log the pass in Appendix B.
- [ ] **Step 2: Research note.** Add a "Settlement cycle" section to `docs/research/t-rules.md` with the POJK 21/POJK.04/2018 quote, its in-force clause, its BPK status and the 26 Nov 2018 row date.
- [ ] **Step 3: File the stories.** Create one issue per task 1–7, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 4: Open the plan PR** into `develop` (`Refs` the plan ticket), and merge it as **Merging a story** says.

---

### Task 1: S1 Data-file reader and IDX calendar

**Acceptance criteria (story text):**
1. `steadyhand_idx/data/holidays.toml` holds every IDX non-trading weekday for 2016–2027, generated from the research docs' lists (`t-hist.md` §1, `t-pay.md` §2, `t-rules.md` §4). Each year names its source document and IDX's stated trading-day total.
2. The loader recomputes each year's total (weekdays less holidays) and refuses a mismatch, naming the year. It also refuses a weekend date, a date outside its year, a repeated or out-of-order date and a non-consecutive year. A test that drops one holiday proves the check.
3. `IdxCalendar` answers `is_trading_day`, `next_trading_day`, `previous_trading_day`, `add_trading_days(day, n)` for n ≥ 1, `trading_days(start, end)` and `require_covered(day)`. A year with no data raises `UnsupportedDateError` naming `holidays.toml` and the years it covers.
4. The known days hold: 22 Sep 2026 open (Yahoo's `^JKSE` gap), 27 Jun 2018 open (Peng-00504), 4 May 2022 and 18 Aug 2025 closed. 2021–2025 has 1,205 trading days, the bar count measured on Yahoo.
5. The data-file reader names the file, table, row and key in every error; refuses unknown keys; reads decimals only from strings; and its `Dated[T]` refuses a day before its first row, naming the table.
6. The engine exports `UnsupportedDateError`.
7. Every quality gate is green at 100% branch coverage, and the red phase is recorded in the PR.

**Files:**
- Modify: `packages/steadyhand/src/steadyhand/market.py`, `packages/steadyhand/src/steadyhand/__init__.py`
- Create: `packages/steadyhand-idx/src/steadyhand_idx/_datafile.py`, `.../calendar.py`, `.../data/holidays.toml`
- Modify: `packages/steadyhand-idx/src/steadyhand_idx/__init__.py`
- Test: `tests/idx/test_datafile.py`, `tests/idx/test_calendar.py`

**Interfaces:**
- Consumes: nothing new from the engine.
- Produces: `steadyhand.UnsupportedDateError(LookupError)`. In `steadyhand_idx._datafile`: `DataFileError(ValueError)`; `Where(file, table, row=None, part=None)` with `.at(row)`, `.within(part)`; `type Row = Mapping[str, object]`; `load_shipped(name) -> dict[str, object]`; `load_path(path) -> dict[str, object]`; `require_schema(document, file, version)`; `rows(document, table, where) -> list[Row]`; `only_keys(row, allowed, where)`; `get_date`, `get_int(..., minimum=)`, `get_str`, `get_decimal`, `get_list`, `get_tables(row, key, where, label=) -> list[tuple[Row, Where]]`, `as_date(value, what)`; `Dated[T](where, starts, values)` with `.first` and `.on(day) -> T`. In `steadyhand_idx.calendar`: `HOLIDAYS_FILE`, `HolidayYear`, `parse_holidays(document, file=...)`, `IdxCalendar(years, file=...)` with `.shipped()`, `.first_day`, `.last_day`, `.source(year)`, `.require_covered(day)`, `.is_trading_day(day)`, `.next_trading_day(day)`, `.previous_trading_day(day)`, `.add_trading_days(day, count)`, `.trading_days(start, end)`.

- [ ] **Step 1: Branch.** `git switch -c m2/s1-calendar origin/develop`

- [ ] **Step 2: Write the failing tests.**

<!-- file: tests/idx/test_datafile.py -->
**`tests/idx/test_datafile.py`**

```python
"""The data-file reader: typed getters whose errors name the file, row and key."""

import tomllib
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Where,
    as_date,
    get_date,
    get_decimal,
    get_int,
    get_list,
    get_str,
    get_tables,
    load_path,
    load_shipped,
    only_keys,
    require_schema,
    rows,
)

HERE = Where("fees.toml", "levy", 2)


def test_where_names_the_file_table_and_row() -> None:
    assert str(HERE) == "fees.toml [[levy]] row 2"
    assert str(Where("fees.toml", "presets")) == "fees.toml [presets]"
    assert str(Where("fees.toml", "levy").at(3)) == "fees.toml [[levy]] row 3"


def test_shipped_files_are_read_from_the_package() -> None:
    assert load_shipped("holidays.toml")["schema"] == 1


def test_invalid_toml_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "lq45_members.toml"
    path.write_text("schema = \n", encoding="utf-8")
    with pytest.raises(DataFileError, match=r"^lq45_members\.toml is not valid TOML"):
        load_path(path)


def test_a_missing_user_file_names_its_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"nothing\.toml"):
        load_path(tmp_path / "nothing.toml")


def test_user_files_parse(tmp_path: Path) -> None:
    path = tmp_path / "x.toml"
    path.write_text("schema = 1\n", encoding="utf-8")
    assert load_path(path) == {"schema": 1}


def test_schema_must_match() -> None:
    require_schema({"schema": 1}, "x.toml", 1)
    with pytest.raises(DataFileError, match=r"^x\.toml: schema must be 1, got 2$"):
        require_schema({"schema": 2}, "x.toml", 1)
    with pytest.raises(DataFileError, match="got None"):
        require_schema({}, "x.toml", 1)


def test_rows_must_be_a_non_empty_array_of_tables() -> None:
    where = Where("x.toml", "levy")
    assert rows({"levy": [{"a": 1}]}, "levy", where) == [{"a": 1}]
    bad_documents: list[dict[str, object]] = [{}, {"levy": []}, {"levy": {"a": 1}}]
    for bad in bad_documents:
        with pytest.raises(DataFileError, match=r"x\.toml \[levy\] must be a non-empty array"):
            rows(bad, "levy", where)
    with pytest.raises(DataFileError, match=r"x\.toml \[\[levy\]\] row 2 must be a table"):
        rows({"levy": [{"a": 1}, 5]}, "levy", where)


def test_unknown_keys_are_refused() -> None:
    only_keys({"from": 1}, {"from", "rate"}, HERE)
    with pytest.raises(DataFileError, match=r"row 2: unknown key 'rat'$"):
        only_keys({"from": 1, "rat": 2}, {"from", "rate"}, HERE)


def test_missing_keys_are_named() -> None:
    with pytest.raises(DataFileError, match=r"row 2: missing key 'rate'$"):
        get_decimal({}, "rate", HERE)


def test_dates_must_be_plain_toml_dates() -> None:
    document = tomllib.loads("a = 2021-01-04\nb = 2021-01-04T09:00:00\nc = '2021-01-04'")
    assert get_date(document, "a", HERE) == date(2021, 1, 4)
    for key in ("b", "c"):
        with pytest.raises(DataFileError, match=rf"row 2: {key} must be a TOML date"):
            get_date(document, key, HERE)
    assert as_date(date(2021, 1, 4), "x") == date(2021, 1, 4)
    with pytest.raises(DataFileError, match=r"^holiday 3 must be a TOML date"):
        as_date(datetime(2021, 1, 4, 9, 0), "holiday 3")  # noqa: DTZ001 - naive on purpose


def test_ints_must_be_ints_at_or_above_the_minimum() -> None:
    assert get_int({"n": 100}, "n", HERE, minimum=1) == 100
    for bad in (0, True, "100", 1.0):
        with pytest.raises(DataFileError, match="n must be an integer of at least 1"):
            get_int({"n": bad}, "n", HERE, minimum=1)


def test_strings_must_be_non_empty() -> None:
    assert get_str({"s": "IDX"}, "s", HERE) == "IDX"
    for bad in ("", "  ", 5):
        with pytest.raises(DataFileError, match="s must be a non-empty string"):
            get_str({"s": bad}, "s", HERE)


def test_decimals_are_written_as_strings_and_never_negative() -> None:
    assert get_decimal({"r": "0.018"}, "r", HERE) == Decimal("0.018")
    assert get_decimal({"r": "0"}, "r", HERE) == 0
    with pytest.raises(DataFileError, match="r must be a decimal written as a string"):
        get_decimal({"r": 0.018}, "r", HERE)
    with pytest.raises(DataFileError, match="r must be a decimal number, got 'abc'"):
        get_decimal({"r": "abc"}, "r", HERE)
    for bad in ("NaN", "Infinity", "-0.1"):
        with pytest.raises(DataFileError, match="r must be a finite decimal of at least 0"):
            get_decimal({"r": bad}, "r", HERE)


def test_lists_must_be_arrays() -> None:
    assert get_list({"l": [1]}, "l", HERE) == [1]
    with pytest.raises(DataFileError, match="l must be an array"):
        get_list({"l": "a"}, "l", HERE)


def test_a_dated_table_answers_from_each_row_until_the_next() -> None:
    table = Dated(Where("t.toml", "t"), (date(2020, 3, 13), date(2023, 6, 5)), ("a", "b"))
    assert table.first == date(2020, 3, 13)
    assert table.on(date(2020, 3, 13)) == "a"
    assert table.on(date(2023, 6, 4)) == "a"
    assert table.on(date(2023, 6, 5)) == "b"
    assert table.on(date(2040, 1, 1)) == "b"


def test_a_dated_table_refuses_a_day_before_its_first_row() -> None:
    table = Dated(Where("tick_sizes.toml", "ticks"), (date(2020, 3, 13),), ("a",))
    with pytest.raises(
        UnsupportedDateError,
        match=(
            r"^tick_sizes\.toml \[ticks\] has no verified row for 2020-03-12: "
            r"its first row applies from 2020-03-13$"
        ),
    ):
        table.on(date(2020, 3, 12))


def test_a_dated_table_needs_increasing_dates_and_one_value_each() -> None:
    where = Where("t.toml", "t")
    with pytest.raises(DataFileError, match="from dates must increase, got 2020-01-01 after"):
        Dated(where, (date(2020, 1, 1), date(2020, 1, 1)), ("a", "b"))
    with pytest.raises(DataFileError, match="needs one value per start date, and at least one"):
        Dated(where, (), ())
    with pytest.raises(DataFileError, match="needs one value per start date"):
        Dated(where, (date(2020, 1, 1),), ("a", "b"))


def test_a_part_of_a_row_is_named_after_the_row() -> None:
    assert str(HERE.within("tier 2")) == "fees.toml [[levy]] row 2, tier 2"


def test_inline_tables_come_with_their_place() -> None:
    row = {"tiers": [{"tick": 1}, {"tick": 2}]}
    found = get_tables(row, "tiers", HERE, label="tier")
    assert [(table, str(place)) for table, place in found] == [
        ({"tick": 1}, "fees.toml [[levy]] row 2, tier 1"),
        ({"tick": 2}, "fees.toml [[levy]] row 2, tier 2"),
    ]
    with pytest.raises(
        DataFileError, match=r"^fees\.toml \[\[levy\]\] row 2, tier 1 must be an inline table$"
    ):
        get_tables({"tiers": [5]}, "tiers", HERE, label="tier")
```

<!-- file: tests/idx/test_calendar.py -->
**`tests/idx/test_calendar.py`**

```python
"""The IDX trading calendar: IDX's own holiday lists, each year's arithmetic checked on load."""

import copy
from datetime import date
from functools import cache

import pytest

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, load_shipped
from steadyhand_idx.calendar import HolidayYear, IdxCalendar, parse_holidays


@cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


# Holidays and IDX's stated trading-day total per year, copied from the research docs
# (t-hist.md §1, t-pay.md §2, t-rules.md §4). A literal pin: the loader's own arithmetic check
# derives from the file, so it cannot notice a year that went missing with its total.
RESEARCH = {
    2016: (15, 246), 2017: (22, 238), 2018: (21, 240), 2019: (16, 245),
    2020: (20, 242), 2021: (14, 247), 2022: (14, 246), 2023: (21, 239),
    2024: (25, 237), 2025: (25, 236), 2026: (22, 239), 2027: (20, 241),
}  # fmt: skip


def weekdays(year: int) -> int:
    days = range(date(year, 1, 1).toordinal(), date(year + 1, 1, 1).toordinal())
    return sum(1 for day in days if date.fromordinal(day).weekday() < 5)


def test_the_shipped_calendar_covers_2016_to_2027() -> None:
    assert calendar().first_day == date(2016, 1, 1)
    assert calendar().last_day == date(2027, 12, 31)


@pytest.mark.parametrize(("year", "expected"), sorted(RESEARCH.items()))
def test_each_year_matches_the_research(year: int, expected: tuple[int, int]) -> None:
    holidays, trading_days = expected
    days = calendar().trading_days(date(year, 1, 1), date(year, 12, 31))
    assert len(days) == trading_days
    assert weekdays(year) - len(days) == holidays


def test_the_2021_to_2025_window_has_the_1205_days_yahoo_has_bars_for() -> None:
    # Measured on 2026-09-25: 25 large IDX stocks each had exactly 1,205 Yahoo bars in this window.
    assert len(calendar().trading_days(date(2021, 1, 1), date(2025, 12, 31))) == 1205


@pytest.mark.parametrize(
    ("day", "status", "why"),
    [
        (date(2026, 9, 22), "open", "Yahoo's ^JKSE has no bar, but IDX traded (t-pay.md §2)"),
        (date(2018, 6, 27), "open", "election-day holiday, but Peng-00504 kept IDX open"),
        (date(2022, 5, 4), "closed", "Eid leave added by the 2022 calendar's version 2"),
        (date(2025, 8, 18), "closed", "added to 2025 by Peng-00149/BEI.POP/08-2025"),
        (date(2026, 12, 31), "closed", "the exchange's year-end holiday"),
        (date(2026, 9, 26), "closed", "a Saturday"),
        (date(2026, 9, 27), "closed", "a Sunday"),
        (date(2026, 9, 28), "open", "an ordinary Monday"),
    ],
)
def test_known_days(day: date, status: str, why: str) -> None:
    assert calendar().is_trading_day(day) is (status == "open"), why


@pytest.mark.parametrize("day", [date(2015, 12, 31), date(2028, 1, 3)])
def test_a_year_without_holiday_data_is_refused(day: date) -> None:
    with pytest.raises(
        UnsupportedDateError,
        match=(
            rf"^holidays\.toml has no IDX holidays for {day.year}, so its trading days are "
            r"unknown; it covers 2016 to 2027$"
        ),
    ):
        calendar().is_trading_day(day)


def test_next_and_previous_cross_holidays_weekends_and_the_year_end() -> None:
    assert calendar().next_trading_day(date(2026, 12, 30)) == date(2027, 1, 4)
    assert calendar().previous_trading_day(date(2027, 1, 4)) == date(2026, 12, 30)
    assert calendar().next_trading_day(date(2026, 9, 25)) == date(2026, 9, 28)
    assert calendar().previous_trading_day(date(2026, 9, 28)) == date(2026, 9, 25)


def test_add_trading_days_counts_from_the_day_after() -> None:
    # Eid 2026: 18-20 and 23-24 March are holidays, 21-22 a weekend.
    assert calendar().add_trading_days(date(2026, 3, 17), 1) == date(2026, 3, 25)
    assert calendar().add_trading_days(date(2026, 3, 17), 2) == date(2026, 3, 26)
    # A non-trading start day is allowed: the count starts on the day after it.
    assert calendar().add_trading_days(date(2026, 3, 21), 1) == date(2026, 3, 25)


def test_counting_past_the_last_year_is_refused() -> None:
    with pytest.raises(UnsupportedDateError, match="no IDX holidays for 2028"):
        calendar().add_trading_days(date(2027, 12, 30), 2)


@pytest.mark.parametrize("count", [0, -1, True])
def test_add_trading_days_needs_a_positive_int(count: int) -> None:
    with pytest.raises(ValueError, match=rf"^count must be an int of at least 1, got {count!r}$"):
        calendar().add_trading_days(date(2026, 3, 17), count)


def test_trading_days_is_inclusive_and_refuses_a_reversed_range() -> None:
    assert calendar().trading_days(date(2026, 9, 25), date(2026, 9, 28)) == (
        date(2026, 9, 25),
        date(2026, 9, 28),
    )
    with pytest.raises(ValueError, match=r"^end 2026-09-24 is before start 2026-09-25$"):
        calendar().trading_days(date(2026, 9, 25), date(2026, 9, 24))


def test_each_year_names_its_source() -> None:
    assert calendar().source(2026) == "Peng-00171/BEI.POP/09-2025"
    with pytest.raises(UnsupportedDateError, match="no IDX holidays for 2030"):
        calendar().source(2030)


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("holidays.toml"))


def _years(document: dict[str, object]) -> list[dict[str, object]]:
    found = document["year"]
    assert isinstance(found, list)
    return found


def test_a_dropped_holiday_fails_the_arithmetic_check() -> None:
    document = _document()
    first = _years(document)[0]
    holidays = first["holidays"]
    assert isinstance(holidays, list)
    first["holidays"] = holidays[1:]
    with pytest.raises(
        DataFileError,
        match=(
            r"^holidays\.toml \[\[year\]\] row 1: 2016 has 247 weekdays that are not holidays, "
            r"but the calendar states 246 trading days$"
        ),
    ):
        parse_holidays(document)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"holidays": [date(2017, 1, 2)]}, r"2017-01-02 is not in 2016"),
        ({"holidays": [date(2016, 1, 2)]}, r"2016-01-02 is a weekend"),
        (
            {"holidays": [date(2016, 1, 4), date(2016, 1, 4)]},
            r"holidays must be listed once each, in order; 2016-01-04 is not",
        ),
        ({"holidays": ["2016-01-04"]}, r"holiday 1 must be a TOML date"),
        ({"source": ""}, r"source must be a non-empty string"),
        ({"note": "x"}, r"unknown key 'note'"),
    ],
)
def test_bad_year_rows_are_refused(change: dict[str, object], message: str) -> None:
    document = _document()
    _years(document)[0].update(change)
    with pytest.raises(DataFileError, match=message):
        parse_holidays(document)


def test_years_must_be_consecutive() -> None:
    document = _document()
    del _years(document)[1]
    with pytest.raises(DataFileError, match="years must be consecutive, got 2018 after 2016"):
        parse_holidays(document)


def test_the_top_level_is_checked() -> None:
    document = _document()
    document["extra"] = 1
    with pytest.raises(DataFileError, match=r"holidays\.toml \[top level\]: unknown key 'extra'"):
        parse_holidays(document)
    with pytest.raises(DataFileError, match="schema must be 1"):
        parse_holidays({"schema": 2})


def test_a_calendar_needs_a_year() -> None:
    with pytest.raises(DataFileError, match="a calendar needs at least one year"):
        IdxCalendar([])


def test_a_calendar_built_by_hand_uses_its_own_years() -> None:
    year = HolidayYear(2030, "test", 261, frozenset())
    calendar = IdxCalendar([year], file="mine.toml")
    assert calendar.is_trading_day(date(2030, 1, 1))
    with pytest.raises(UnsupportedDateError, match=r"^mine\.toml has no IDX holidays for 2031"):
        calendar.is_trading_day(date(2031, 1, 1))


def test_require_covered_refuses_a_year_without_data() -> None:
    calendar().require_covered(date(2027, 12, 31))
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2028"):
        calendar().require_covered(date(2028, 1, 3))
```

- [ ] **Step 3: Add the engine error, and stubs for the two IDX modules.** The engine change is the whole of this story's engine work, so it goes in now:

<!-- file@1: packages/steadyhand/src/steadyhand/market.py -->
**`packages/steadyhand/src/steadyhand/market.py` (this story adds only the error)**

```python
"""The MarketRules protocol: everything that differs between stock exchanges."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.money import Currency, Money
from steadyhand.types import Costs, Instrument, Side


class UnsupportedDateError(LookupError):
    """A market's rule data does not cover a date.

    Raised instead of guessing: a year with no holiday data, or a day before a rule table's
    first verified row, must stop the run. It is never read as "no holidays" or "today's rules".
    """


@runtime_checkable
class MarketRules(Protocol):
    """One market's trading rules. Every rule is looked up for a date, because rules change.

    An implementation reads its values from dated data (spec §9.1), never from constants, so a
    backtest over past dates uses the rules that applied on those dates.
    """

    @property
    def currency(self) -> Currency:
        """The currency every price and cost in this market is quoted in."""
        ...

    def lot_size(self, instrument: Instrument, on: date) -> int:
        """Shares per board lot. Orders are whole lots."""
        ...

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        """The nearest valid price against the trader: up for a BUY, down for a SELL."""
        ...

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        """The (lowest, highest) price the exchange accepts, given the reference price."""
        ...

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        """Fee, levy and tax for one trade of *gross* value. Never negative."""
        ...

    def settlement_date(self, trade_date: date) -> date:
        """The trading day on which a trade made on *trade_date* settles."""
        ...

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """The tax due on a *gross* dividend paid on *on*.

        IDX issuers withhold nothing from resident individuals; see docs/research/t-tax.md.
        """
        ...

    def is_trading_day(self, day: date) -> bool:
        """Whether the market is open on *day*. Raises for a year with no holiday data."""
        ...
```

<!-- file: packages/steadyhand/src/steadyhand/__init__.py -->
**`packages/steadyhand/src/steadyhand/__init__.py`**

```python
"""steadyhand: a market-neutral engine for self-hosted, dividend-first portfolio bots."""

from importlib.metadata import version

from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError
from steadyhand.disclaimer import DISCLAIMER
from steadyhand.market import MarketRules, UnsupportedDateError
from steadyhand.money import (
    IDR,
    MAX_MINOR_UNITS,
    Currency,
    CurrencyMismatchError,
    Money,
    Rounding,
)
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

__version__: str = version("steadyhand")

__all__ = [
    "DISCLAIMER",
    "IDR",
    "MAX_MINOR_UNITS",
    "Bar",
    "Broker",
    "CashDividend",
    "CashMovement",
    "ChronologyError",
    "CorporateAction",
    "Costs",
    "Currency",
    "CurrencyMismatchError",
    "DataSource",
    "DataUnavailableError",
    "Fill",
    "Instrument",
    "InsufficientCashError",
    "InsufficientSharesError",
    "InvalidBarError",
    "MarketRules",
    "MissingPriceError",
    "Money",
    "MovementKind",
    "NegativeProceedsError",
    "Order",
    "OrderAck",
    "OtherAction",
    "Portfolio",
    "Position",
    "Rounding",
    "Side",
    "Split",
    "UnsupportedDateError",
    "__version__",
]
```

Stubs, which keep every signature and raise `NotImplementedError` naming the function:

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/_datafile.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/_datafile.py` (stub)**

```python
"""Reading the TOML data files: the ones shipped in ``data/`` and the ones a user supplies.

Every value is read through a typed getter that names the file, the table, the row and the key
in its error, so a bad file says exactly where it is bad. Unknown keys are refused, because a
misspelt key would otherwise be silently ignored and its default used instead.
"""

from __future__ import annotations
import tomllib
from bisect import bisect_right
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import resources
from itertools import pairwise
from pathlib import Path
from typing import cast
from steadyhand import UnsupportedDateError

type Row = Mapping[str, object]


class DataFileError(ValueError):
    """A data file is malformed. The message names the file, the row and the key."""


@dataclass(frozen=True, slots=True)
class Where:
    """A position in a data file, for error messages: ``fees.toml [[levy]] row 2``."""

    file: str
    table: str
    row: int | None = None
    part: str | None = None

    def __str__(self) -> str:
        raise NotImplementedError("Where.__str__")

    def at(self, row: int) -> Where:
        """The same table, at *row* (counted from 1)."""
        raise NotImplementedError("Where.at")

    def within(self, part: str) -> Where:
        """A named part of this row, such as ``tier 2``."""
        raise NotImplementedError("Where.within")


def load_shipped(name: str) -> dict[str, object]:
    """Parse ``steadyhand_idx/data/<name>``."""
    raise NotImplementedError("load_shipped")


def load_path(path: Path) -> dict[str, object]:
    """Parse a user-supplied file. A missing file is a ``FileNotFoundError`` naming the path."""
    raise NotImplementedError("load_path")


def _parse(text: str, name: str) -> dict[str, object]:
    raise NotImplementedError("_parse")


def require_schema(document: Row, file: str, version: int) -> None:
    raise NotImplementedError("require_schema")


def rows(document: Row, table: str, where: Where) -> list[Row]:
    """The rows of an array of tables, at least one of them, each a mapping."""
    raise NotImplementedError("rows")


def only_keys(row: Row, allowed: Collection[str], where: Where) -> None:
    raise NotImplementedError("only_keys")


def _get(row: Row, key: str, where: Where) -> object:
    raise NotImplementedError("_get")


def _wrong(where: Where, key: str, expected: str, value: object) -> DataFileError:
    raise NotImplementedError("_wrong")


def as_date(value: object, what: str) -> date:
    """*value* as a plain ``date``; TOML gives a ``datetime`` for a value with a time, refused."""
    raise NotImplementedError("as_date")


def get_date(row: Row, key: str, where: Where) -> date:
    raise NotImplementedError("get_date")


def get_int(row: Row, key: str, where: Where, *, minimum: int) -> int:
    raise NotImplementedError("get_int")


def get_str(row: Row, key: str, where: Where) -> str:
    raise NotImplementedError("get_str")


def get_decimal(row: Row, key: str, where: Where) -> Decimal:
    """A rate written as a string (``"0.018"``), so no float is ever involved (spec §9.5)."""
    raise NotImplementedError("get_decimal")


def get_list(row: Row, key: str, where: Where) -> Sequence[object]:
    raise NotImplementedError("get_list")


def get_tables(row: Row, key: str, where: Where, *, label: str) -> list[tuple[Row, Where]]:
    """An array of inline tables, each paired with its place (``..., tier 2``) for errors."""
    raise NotImplementedError("get_tables")


@dataclass(frozen=True, slots=True)
class Dated[T]:
    """Rows that each apply from their ``from`` date until the next row's.

    The first row's date is the first day the table can answer for. An earlier day raises
    ``UnsupportedDateError`` naming the table: a rule is never assumed for a date nobody verified.
    """

    where: Where
    starts: tuple[date, ...]
    values: tuple[T, ...]

    def __post_init__(self) -> None:
        raise NotImplementedError("Dated.__post_init__")

    @property
    def first(self) -> date:
        raise NotImplementedError("Dated.first")

    def on(self, day: date) -> T:
        raise NotImplementedError("Dated.on")
```

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/calendar.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/calendar.py` (stub)**

```python
"""IDX trading days, from the holiday calendars in ``data/holidays.toml`` (spec §9.1).

Trading days come from IDX's own calendars and never from which days have price bars: Yahoo's
index series has no bar for 22 Sep 2026, which was a trading day (docs/research/t-pay.md §2).
A year with no holiday data is refused rather than assumed to have no holidays.
"""

from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from itertools import pairwise
from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import (
    DataFileError,
    Row,
    Where,
    as_date,
    get_int,
    get_list,
    get_str,
    load_shipped,
    only_keys,
    require_schema,
    rows,
)

HOLIDAYS_FILE = "holidays.toml"
_SATURDAY = 5
_ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class HolidayYear:
    """One year's IDX non-trading weekdays, the document they come from, and IDX's stated total."""

    year: int
    source: str
    trading_days: int
    holidays: frozenset[date]


def _weekdays(year: int) -> int:
    raise NotImplementedError("_weekdays")


def _parse_year(row: Row, where: Where) -> HolidayYear:
    raise NotImplementedError("_parse_year")


def parse_holidays(document: Row, file: str = HOLIDAYS_FILE) -> tuple[HolidayYear, ...]:
    """Validate a holidays document: consecutive years, each one's arithmetic checked."""
    raise NotImplementedError("parse_holidays")


class IdxCalendar:
    """Which days the IDX regular market is open, for the years it has holiday data."""

    def __init__(self, years: Iterable[HolidayYear], *, file: str = HOLIDAYS_FILE) -> None:
        raise NotImplementedError("IdxCalendar.__init__")

    @classmethod
    def shipped(cls) -> IdxCalendar:
        """The calendar from the package's own ``data/holidays.toml``."""
        raise NotImplementedError("IdxCalendar.shipped")

    @property
    def first_day(self) -> date:
        raise NotImplementedError("IdxCalendar.first_day")

    @property
    def last_day(self) -> date:
        raise NotImplementedError("IdxCalendar.last_day")

    def source(self, year: int) -> str:
        """The IDX document a year's holidays come from."""
        raise NotImplementedError("IdxCalendar.source")

    def _year(self, year: int) -> HolidayYear:
        raise NotImplementedError("IdxCalendar._year")

    def require_covered(self, day: date) -> None:
        """Raise ``UnsupportedDateError`` unless *day*'s year has holiday data."""
        raise NotImplementedError("IdxCalendar.require_covered")

    def is_trading_day(self, day: date) -> bool:
        raise NotImplementedError("IdxCalendar.is_trading_day")

    def next_trading_day(self, day: date) -> date:
        """The first trading day strictly after *day*."""
        raise NotImplementedError("IdxCalendar.next_trading_day")

    def previous_trading_day(self, day: date) -> date:
        """The last trading day strictly before *day*."""
        raise NotImplementedError("IdxCalendar.previous_trading_day")

    def add_trading_days(self, day: date, count: int) -> date:
        """The *count*-th trading day after *day* (``count`` of at least 1).

        *day* itself need not be a trading day: the count starts on the day after it.
        """
        raise NotImplementedError("IdxCalendar.add_trading_days")

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        """Every trading day from *start* to *end*, inclusive."""
        raise NotImplementedError("IdxCalendar.trading_days")


@cache
def _shipped_calendar() -> IdxCalendar:
    raise NotImplementedError("_shipped_calendar")
```

- [ ] **Step 4: Run the tests and watch them fail.**

Run: `uv run --locked pytest -W error -q tests/idx/test_datafile.py tests/idx/test_calendar.py`
Expected: `63 failed`, each on a `NotImplementedError`. None passes.

- [ ] **Step 5: Write the implementation and the data.** `holidays.toml` was generated from the research docs' date lists by a script that asserted each year's stated total before writing; copy it as given, and its loader re-checks every total:

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/data/holidays.toml -->
**`packages/steadyhand-idx/src/steadyhand_idx/data/holidays.toml`**

```toml
# IDX non-trading days (weekdays only), one record per year. Spec §9.1.
#
# Every year comes from an IDX calendar or announcement: 2016-2024 docs/research/t-hist.md §1,
# 2025 docs/research/t-pay.md §2, 2026-2027 docs/research/t-rules.md §4. `trading_days` is the
# calendar's own stated total (Jumlah Hari Bursa). The loader recomputes it as the year's
# weekdays less the holidays, so a mistyped or missing date fails the load.
# A year that is not here has no trading days as far as steadyhand is concerned: the calendar
# refuses it rather than assume the market was open.

schema = 1

[[year]]
year = 2016
source = "IDX, Kalender Libur Bursa Tahun 2016 (PDF; Internet Archive capture 20190917224753)"
trading_days = 246
holidays = [
    2016-01-01, 2016-02-08, 2016-03-09, 2016-03-25, 2016-05-05, 2016-05-06,
    2016-07-04, 2016-07-05, 2016-07-06, 2016-07-07, 2016-07-08, 2016-08-17,
    2016-09-12, 2016-12-12, 2016-12-26,
]

[[year]]
year = 2017
source = "IDX, Kalender Libur Bursa Tahun 2017 (PDF; Internet Archive capture 20170713123347)"
trading_days = 238
holidays = [
    2017-01-02, 2017-02-15, 2017-03-28, 2017-04-14, 2017-04-19, 2017-04-24,
    2017-05-01, 2017-05-11, 2017-05-25, 2017-06-01, 2017-06-23, 2017-06-26,
    2017-06-27, 2017-06-28, 2017-06-29, 2017-06-30, 2017-08-17, 2017-09-01,
    2017-09-21, 2017-12-01, 2017-12-25, 2017-12-26,
]

[[year]]
year = 2018
source = "IDX, Kalender Libur Bursa Tahun 2018 (2018ind.jpg; Internet Archive capture 20220307151816)"
trading_days = 240
holidays = [
    2018-01-01, 2018-02-16, 2018-03-30, 2018-05-01, 2018-05-10, 2018-05-29,
    2018-06-01, 2018-06-11, 2018-06-12, 2018-06-13, 2018-06-14, 2018-06-15,
    2018-06-18, 2018-06-19, 2018-08-17, 2018-08-22, 2018-09-11, 2018-11-20,
    2018-12-24, 2018-12-25, 2018-12-31,
]

[[year]]
year = 2019
source = "IDX, Kalender Libur Bursa Tahun 2019, revised (2019_rev.jpg; Internet Archive capture 20220307151816)"
trading_days = 245
holidays = [
    2019-01-01, 2019-02-05, 2019-03-07, 2019-04-03, 2019-04-17, 2019-04-19,
    2019-05-01, 2019-05-30, 2019-06-03, 2019-06-04, 2019-06-05, 2019-06-06,
    2019-06-07, 2019-12-24, 2019-12-25, 2019-12-31,
]

[[year]]
year = 2020
source = "IDX, Kalender Libur Bursa Tahun 2020, version 3 (2020_ind-v3.jpg; Internet Archive capture 20221007193429)"
trading_days = 242
holidays = [
    2020-01-01, 2020-03-25, 2020-04-10, 2020-05-01, 2020-05-07, 2020-05-21,
    2020-05-22, 2020-05-25, 2020-06-01, 2020-07-31, 2020-08-17, 2020-08-20,
    2020-08-21, 2020-10-28, 2020-10-29, 2020-10-30, 2020-12-09, 2020-12-24,
    2020-12-25, 2020-12-31,
]

[[year]]
year = 2021
source = "IDX, Kalender Libur Bursa Tahun 2021, version 3 (2021_ind-v3.jpg; Internet Archive capture 20221008133601)"
trading_days = 247
holidays = [
    2021-01-01, 2021-02-12, 2021-03-11, 2021-04-02, 2021-05-12, 2021-05-13,
    2021-05-14, 2021-05-26, 2021-06-01, 2021-07-20, 2021-08-11, 2021-08-17,
    2021-10-20, 2021-12-31,
]

[[year]]
year = 2022
source = "IDX, Kalender Libur Bursa Tahun 2022, version 2 (2022_ind-v2.jpg; idx.co.id)"
trading_days = 246
holidays = [
    2022-02-01, 2022-02-28, 2022-03-03, 2022-04-15, 2022-04-29, 2022-05-02,
    2022-05-03, 2022-05-04, 2022-05-05, 2022-05-06, 2022-05-16, 2022-05-26,
    2022-06-01, 2022-08-17,
]

[[year]]
year = 2023
source = "IDX, Kalender Libur Bursa Tahun 2023, version 3 (2023_ind-v3_page-0001.jpg; idx.co.id)"
trading_days = 239
holidays = [
    2023-01-23, 2023-03-22, 2023-03-23, 2023-04-07, 2023-04-19, 2023-04-20,
    2023-04-21, 2023-04-24, 2023-04-25, 2023-05-01, 2023-05-18, 2023-06-01,
    2023-06-02, 2023-06-28, 2023-06-29, 2023-06-30, 2023-07-19, 2023-08-17,
    2023-09-28, 2023-12-25, 2023-12-26,
]

[[year]]
year = 2024
source = "IDX, Kalender Libur Bursa Tahun 2024, version 3 (2024_ind-v3_new.jpg; Internet Archive capture 20250830095302)"
trading_days = 237
holidays = [
    2024-01-01, 2024-02-08, 2024-02-09, 2024-02-14, 2024-03-11, 2024-03-12,
    2024-03-29, 2024-04-08, 2024-04-09, 2024-04-10, 2024-04-11, 2024-04-12,
    2024-04-15, 2024-05-01, 2024-05-09, 2024-05-10, 2024-05-23, 2024-05-24,
    2024-06-17, 2024-06-18, 2024-09-16, 2024-11-27, 2024-12-25, 2024-12-26,
    2024-12-31,
]

[[year]]
year = 2025
source = "Peng-00213/BEI.POP/10-2024, amended by Peng-00149/BEI.POP/08-2025"
trading_days = 236
holidays = [
    2025-01-01, 2025-01-27, 2025-01-28, 2025-01-29, 2025-03-28, 2025-03-31,
    2025-04-01, 2025-04-02, 2025-04-03, 2025-04-04, 2025-04-07, 2025-04-18,
    2025-05-01, 2025-05-12, 2025-05-13, 2025-05-29, 2025-05-30, 2025-06-06,
    2025-06-09, 2025-06-27, 2025-08-18, 2025-09-05, 2025-12-25, 2025-12-26,
    2025-12-31,
]

[[year]]
year = 2026
source = "Peng-00171/BEI.POP/09-2025"
trading_days = 239
holidays = [
    2026-01-01, 2026-01-16, 2026-02-16, 2026-02-17, 2026-03-18, 2026-03-19,
    2026-03-20, 2026-03-23, 2026-03-24, 2026-04-03, 2026-05-01, 2026-05-14,
    2026-05-15, 2026-05-27, 2026-05-28, 2026-06-01, 2026-06-16, 2026-08-17,
    2026-08-25, 2026-12-24, 2026-12-25, 2026-12-31,
]

[[year]]
year = 2027
source = "Peng-00169/BEI.POP/09-2026 (Peng-00171/BEI.POP/09-2026 corrects one description only)"
trading_days = 241
holidays = [
    2027-01-01, 2027-01-05, 2027-02-05, 2027-03-08, 2027-03-09, 2027-03-10,
    2027-03-11, 2027-03-12, 2027-03-15, 2027-03-25, 2027-03-26, 2027-05-06,
    2027-05-17, 2027-05-18, 2027-05-19, 2027-05-20, 2027-06-01, 2027-08-17,
    2027-12-24, 2027-12-31,
]
```

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/_datafile.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/_datafile.py`**

```python
"""Reading the TOML data files: the ones shipped in ``data/`` and the ones a user supplies.

Every value is read through a typed getter that names the file, the table, the row and the key
in its error, so a bad file says exactly where it is bad. Unknown keys are refused, because a
misspelt key would otherwise be silently ignored and its default used instead.
"""

from __future__ import annotations

import tomllib
from bisect import bisect_right
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import resources
from itertools import pairwise
from pathlib import Path
from typing import cast

from steadyhand import UnsupportedDateError

type Row = Mapping[str, object]


class DataFileError(ValueError):
    """A data file is malformed. The message names the file, the row and the key."""


@dataclass(frozen=True, slots=True)
class Where:
    """A position in a data file, for error messages: ``fees.toml [[levy]] row 2``."""

    file: str
    table: str
    row: int | None = None
    part: str | None = None

    def __str__(self) -> str:
        if self.row is None:
            place = f"{self.file} [{self.table}]"
        else:
            place = f"{self.file} [[{self.table}]] row {self.row}"
        return place if self.part is None else f"{place}, {self.part}"

    def at(self, row: int) -> Where:
        """The same table, at *row* (counted from 1)."""
        return Where(self.file, self.table, row)

    def within(self, part: str) -> Where:
        """A named part of this row, such as ``tier 2``."""
        return Where(self.file, self.table, self.row, part)


def load_shipped(name: str) -> dict[str, object]:
    """Parse ``steadyhand_idx/data/<name>``."""
    text = resources.files("steadyhand_idx").joinpath("data", name).read_text(encoding="utf-8")
    return _parse(text, name)


def load_path(path: Path) -> dict[str, object]:
    """Parse a user-supplied file. A missing file is a ``FileNotFoundError`` naming the path."""
    return _parse(path.read_text(encoding="utf-8"), path.name)


def _parse(text: str, name: str) -> dict[str, object]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        msg = f"{name} is not valid TOML: {error}"
        raise DataFileError(msg) from error


def require_schema(document: Row, file: str, version: int) -> None:
    found = document.get("schema")
    if found != version:
        msg = f"{file}: schema must be {version}, got {found!r}"
        raise DataFileError(msg)


def rows(document: Row, table: str, where: Where) -> list[Row]:
    """The rows of an array of tables, at least one of them, each a mapping."""
    found = document.get(table)
    if not isinstance(found, list) or not found:
        msg = f"{where} must be a non-empty array of tables"
        raise DataFileError(msg)
    for index, row in enumerate(found, start=1):
        if not isinstance(row, dict):
            msg = f"{where.at(index)} must be a table"
            raise DataFileError(msg)
    return cast("list[Row]", found)


def only_keys(row: Row, allowed: Collection[str], where: Where) -> None:
    unknown = sorted(set(row) - set(allowed))
    if unknown:
        msg = f"{where}: unknown key {unknown[0]!r}"
        raise DataFileError(msg)


def _get(row: Row, key: str, where: Where) -> object:
    if key not in row:
        msg = f"{where}: missing key {key!r}"
        raise DataFileError(msg)
    return row[key]


def _wrong(where: Where, key: str, expected: str, value: object) -> DataFileError:
    return DataFileError(f"{where}: {key} must be {expected}, got {value!r}")


def as_date(value: object, what: str) -> date:
    """*value* as a plain ``date``; TOML gives a ``datetime`` for a value with a time, refused."""
    if isinstance(value, datetime) or not isinstance(value, date):
        msg = f"{what} must be a TOML date such as 2021-01-04, got {value!r}"
        raise DataFileError(msg)
    return value


def get_date(row: Row, key: str, where: Where) -> date:
    return as_date(_get(row, key, where), f"{where}: {key}")


def get_int(row: Row, key: str, where: Where, *, minimum: int) -> int:
    value = _get(row, key, where)
    if type(value) is not int or value < minimum:
        raise _wrong(where, key, f"an integer of at least {minimum}", value)
    return value


def get_str(row: Row, key: str, where: Where) -> str:
    value = _get(row, key, where)
    if not isinstance(value, str) or not value.strip():
        raise _wrong(where, key, "a non-empty string", value)
    return value


def get_decimal(row: Row, key: str, where: Where) -> Decimal:
    """A rate written as a string (``"0.018"``), so no float is ever involved (spec §9.5)."""
    value = _get(row, key, where)
    if not isinstance(value, str):
        raise _wrong(where, key, 'a decimal written as a string, such as "0.018"', value)
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise _wrong(where, key, "a decimal number", value) from None
    if not number.is_finite() or number < 0:
        raise _wrong(where, key, "a finite decimal of at least 0", value)
    return number


def get_list(row: Row, key: str, where: Where) -> Sequence[object]:
    value = _get(row, key, where)
    if not isinstance(value, list):
        raise _wrong(where, key, "an array", value)
    return cast("list[object]", value)


def get_tables(row: Row, key: str, where: Where, *, label: str) -> list[tuple[Row, Where]]:
    """An array of inline tables, each paired with its place (``..., tier 2``) for errors."""
    found: list[tuple[Row, Where]] = []
    for index, value in enumerate(get_list(row, key, where), start=1):
        place = where.within(f"{label} {index}")
        if not isinstance(value, dict):
            msg = f"{place} must be an inline table"
            raise DataFileError(msg)
        found.append((cast("Row", value), place))
    return found


@dataclass(frozen=True, slots=True)
class Dated[T]:
    """Rows that each apply from their ``from`` date until the next row's.

    The first row's date is the first day the table can answer for. An earlier day raises
    ``UnsupportedDateError`` naming the table: a rule is never assumed for a date nobody verified.
    """

    where: Where
    starts: tuple[date, ...]
    values: tuple[T, ...]

    def __post_init__(self) -> None:
        if not self.starts or len(self.starts) != len(self.values):
            msg = f"{self.where}: needs one value per start date, and at least one"
            raise DataFileError(msg)
        for earlier, later in pairwise(self.starts):
            if later <= earlier:
                msg = f"{self.where}: from dates must increase, got {later} after {earlier}"
                raise DataFileError(msg)

    @property
    def first(self) -> date:
        return self.starts[0]

    def on(self, day: date) -> T:
        if day < self.first:
            msg = (
                f"{self.where} has no verified row for {day.isoformat()}: "
                f"its first row applies from {self.first.isoformat()}"
            )
            raise UnsupportedDateError(msg)
        return self.values[bisect_right(self.starts, day) - 1]
```

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/calendar.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/calendar.py`**

```python
"""IDX trading days, from the holiday calendars in ``data/holidays.toml`` (spec §9.1).

Trading days come from IDX's own calendars and never from which days have price bars: Yahoo's
index series has no bar for 22 Sep 2026, which was a trading day (docs/research/t-pay.md §2).
A year with no holiday data is refused rather than assumed to have no holidays.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from itertools import pairwise

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import (
    DataFileError,
    Row,
    Where,
    as_date,
    get_int,
    get_list,
    get_str,
    load_shipped,
    only_keys,
    require_schema,
    rows,
)

HOLIDAYS_FILE = "holidays.toml"
_SATURDAY = 5
_ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class HolidayYear:
    """One year's IDX non-trading weekdays, the document they come from, and IDX's stated total."""

    year: int
    source: str
    trading_days: int
    holidays: frozenset[date]


def _weekdays(year: int) -> int:
    first = date(year, 1, 1)
    length = (date(year + 1, 1, 1) - first).days
    return sum(1 for offset in range(length) if (first + timedelta(offset)).weekday() < _SATURDAY)


def _parse_year(row: Row, where: Where) -> HolidayYear:
    only_keys(row, {"year", "source", "trading_days", "holidays"}, where)
    year = get_int(row, "year", where, minimum=1)
    listed = get_list(row, "holidays", where)
    days: list[date] = []
    for position, value in enumerate(listed, start=1):
        day = as_date(value, f"{where}: holiday {position}")
        if day.year != year:
            msg = f"{where}: {day.isoformat()} is not in {year}"
            raise DataFileError(msg)
        if day.weekday() >= _SATURDAY:
            msg = f"{where}: {day.isoformat()} is a weekend, which is never a trading day anyway"
            raise DataFileError(msg)
        if days and day <= days[-1]:
            msg = f"{where}: holidays must be listed once each, in order; {day.isoformat()} is not"
            raise DataFileError(msg)
        days.append(day)
    stated = get_int(row, "trading_days", where, minimum=0)
    counted = _weekdays(year) - len(days)
    if counted != stated:
        msg = (
            f"{where}: {year} has {counted} weekdays that are not holidays, "
            f"but the calendar states {stated} trading days"
        )
        raise DataFileError(msg)
    return HolidayYear(year, get_str(row, "source", where), stated, frozenset(days))


def parse_holidays(document: Row, file: str = HOLIDAYS_FILE) -> tuple[HolidayYear, ...]:
    """Validate a holidays document: consecutive years, each one's arithmetic checked."""
    require_schema(document, file, 1)
    only_keys(document, {"schema", "year"}, Where(file, "top level"))
    where = Where(file, "year")
    years = tuple(
        _parse_year(row, where.at(i)) for i, row in enumerate(rows(document, "year", where), 1)
    )
    for earlier, later in pairwise(years):
        if later.year != earlier.year + 1:
            msg = f"{file}: years must be consecutive, got {later.year} after {earlier.year}"
            raise DataFileError(msg)
    return years


class IdxCalendar:
    """Which days the IDX regular market is open, for the years it has holiday data."""

    def __init__(self, years: Iterable[HolidayYear], *, file: str = HOLIDAYS_FILE) -> None:
        self._years = {year.year: year for year in years}
        if not self._years:
            msg = f"{file}: a calendar needs at least one year"
            raise DataFileError(msg)
        self._file = file

    @classmethod
    def shipped(cls) -> IdxCalendar:
        """The calendar from the package's own ``data/holidays.toml``."""
        return _shipped_calendar()

    @property
    def first_day(self) -> date:
        return date(min(self._years), 1, 1)

    @property
    def last_day(self) -> date:
        return date(max(self._years), 12, 31)

    def source(self, year: int) -> str:
        """The IDX document a year's holidays come from."""
        return self._year(year).source

    def _year(self, year: int) -> HolidayYear:
        found = self._years.get(year)
        if found is None:
            msg = (
                f"{self._file} has no IDX holidays for {year}, so its trading days are unknown; "
                f"it covers {self.first_day.year} to {self.last_day.year}"
            )
            raise UnsupportedDateError(msg)
        return found

    def require_covered(self, day: date) -> None:
        """Raise ``UnsupportedDateError`` unless *day*'s year has holiday data."""
        self._year(day.year)

    def is_trading_day(self, day: date) -> bool:
        holidays = self._year(day.year).holidays
        return day.weekday() < _SATURDAY and day not in holidays

    def next_trading_day(self, day: date) -> date:
        """The first trading day strictly after *day*."""
        return self.add_trading_days(day, 1)

    def previous_trading_day(self, day: date) -> date:
        """The last trading day strictly before *day*."""
        day -= _ONE_DAY
        while not self.is_trading_day(day):
            day -= _ONE_DAY
        return day

    def add_trading_days(self, day: date, count: int) -> date:
        """The *count*-th trading day after *day* (``count`` of at least 1).

        *day* itself need not be a trading day: the count starts on the day after it.
        """
        if type(count) is not int or count < 1:
            msg = f"count must be an int of at least 1, got {count!r}"
            raise ValueError(msg)
        while count:
            day += _ONE_DAY
            if self.is_trading_day(day):
                count -= 1
        return day

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        """Every trading day from *start* to *end*, inclusive."""
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        found: list[date] = []
        day = start
        while day <= end:
            if self.is_trading_day(day):
                found.append(day)
            day += _ONE_DAY
        return tuple(found)


@cache
def _shipped_calendar() -> IdxCalendar:
    return IdxCalendar(parse_holidays(load_shipped(HOLIDAYS_FILE)))
```

<!-- file@1: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py` (after this story)**

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.calendar import IdxCalendar

__version__: str = version("steadyhand-idx")

__all__ = [
    "DataFileError",
    "IdxCalendar",
    "__version__",
]
```

- [ ] **Step 6: Run the whole gate.**

Run: `uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy && uv run --locked pytest -W error --cov -q`
Expected: every check passes; `319 passed`; `Required test coverage of 100.0% reached`.

- [ ] **Step 7: Mutations M17 and M18** (see **Mutation checks**). Each must turn the whole suite red.

- [ ] **Step 8: Commit, push and merge.**

```bash
git add packages/steadyhand packages/steadyhand-idx tests/idx
git commit -m "feat(idx): data-file reader and IDX trading calendar, 2016-2027 (#<S1>)"
```

Then follow **Merging a story**.

---

### Task 2: S2 Tick table, lot, settlement and auto-rejection bands

**Acceptance criteria (story text):**
1. `data/tick_sizes.toml` carries the five-tier tick table and the 100-share lot from 13 Mar 2020 (Kep-00025/BEI/03-2020), and T+2 settlement from 26 Nov 2018 (POJK 21/POJK.04/2018 Pasal 2(2)). Nothing earlier ships.
2. A tick tier's lower bound is inclusive and the tier is chosen by the price itself: 199 is on a Rp1 grid, 200 on Rp2, 500 on Rp5, 2,000 on Rp10, 5,000 on Rp25. Every boundary is tested on both sides.
3. Rounding up and down lands on the grid and is tight: a hypothesis property finds no valid price between the rounded value and the input.
4. The loader refuses a table whose tier boundaries are not multiples of both neighbouring ticks, which is the property that keeps rounding up inside the next tier.
5. `data/auto_reject.toml` carries the six verified periods (13 Mar 2020, 5 Jun 2023, 4 Sep 2023, 8 Apr 2025, 28 Sep 2026, 1 Jan 2027), each pinned literally against `t-hist.md` §4 and `t-rules.md` §3, with the minimum price (Rp50, then Rp1).
6. A band tier's upper bound is inclusive and chosen by the reference price: 200 and 5,000 fall in the lower tier. From 28 Sep 2026 the Rp1–10 tier moves Rp1 either way.
7. A day before 13 Mar 2020 (or 26 Nov 2018 for settlement) raises `UnsupportedDateError` naming the table.
8. Every quality gate is green at 100% branch coverage, and the red phase is recorded in the PR.

**Files:**
- Create: `.../steadyhand_idx/ticks.py`, `.../steadyhand_idx/bands.py`, `.../data/tick_sizes.toml`, `.../data/auto_reject.toml`
- Test: `tests/idx/test_ticks.py`, `tests/idx/test_bands.py`

**Interfaces:**
- Consumes: `_datafile` (Task 1).
- Produces: in `steadyhand_idx.ticks`: `TICKS_FILE`, `TickTier(from_price, tick)`, `TickRow(source, lot_size, tiers)` with `.tick_for(price)`, `.is_valid(price)`, `.round_up(price)`, `.round_down(price)` (all `int` rupiah); `parse_ticks(document, file=...) -> Dated[TickRow]`; `parse_settlement(document, file=...) -> Dated[int]`. In `steadyhand_idx.bands`: `BANDS_FILE`, `BandTier(up_to, up, down, in_rupiah)` with `.limits(reference) -> tuple[Decimal, Decimal]`; `BandRow(source, min_price, tiers)` with `.tier_for(reference)`, `.limits(reference)`; `parse_bands(document, file=...) -> Dated[BandRow]`.

- [ ] **Step 1: Branch.** `git switch -c m2/s2-ticks-bands origin/develop` (after S1 is merged).

- [ ] **Step 2: Write the failing tests.**

<!-- file: tests/idx/test_ticks.py -->
**`tests/idx/test_ticks.py`**

```python
"""The IDX tick table: tiers chosen by the price itself, lower bounds inclusive (t-rules.md §1)."""

import copy
from datetime import date
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, Dated, load_shipped
from steadyhand_idx.ticks import TickRow, parse_settlement, parse_ticks


@cache
def table() -> Dated[TickRow]:
    return parse_ticks(load_shipped("tick_sizes.toml"))


@cache
def row() -> TickRow:
    return table().on(date(2026, 9, 25))


def test_the_table_is_verified_from_13_march_2020() -> None:
    assert table().first == date(2020, 3, 13)
    assert table().on(date(2020, 3, 13)) is row()
    with pytest.raises(UnsupportedDateError, match=r"tick_sizes\.toml \[ticks\] has no verified"):
        table().on(date(2020, 3, 12))


def test_the_lot_is_100_shares() -> None:
    assert row().lot_size == 100


@pytest.mark.parametrize(
    ("price", "tick"),
    [
        (1, 1), (199, 1), (200, 2), (499, 2), (500, 5), (1_995, 5),
        (1_999, 5), (2_000, 10), (4_990, 10), (4_999, 10), (5_000, 25), (1_000_000, 25),
    ],
)  # fmt: skip
def test_every_tier_boundary_on_both_sides(price: int, tick: int) -> None:
    assert row().tick_for(price) == tick


@pytest.mark.parametrize(
    ("price", "valid"),
    [(199, True), (200, True), (201, False), (4_990, True), (4_995, False), (5_000, True),
     (5_010, False), (5_025, True)],
)  # fmt: skip
def test_validity_uses_the_tier_of_the_price_itself(price: int, valid: object) -> None:
    assert row().is_valid(price) is valid


@pytest.mark.parametrize(
    ("price", "down", "up"),
    [
        (200, 200, 200), (201, 200, 202), (499, 498, 500), (1_999, 1_995, 2_000),
        (4_999, 4_990, 5_000), (5_001, 5_000, 5_025), (5_024, 5_000, 5_025),
    ],
)  # fmt: skip
def test_rounding_lands_on_the_grid(price: int, down: int, up: int) -> None:
    assert row().round_down(price) == down
    assert row().round_up(price) == up


@given(st.integers(min_value=1, max_value=2_000_000))
def test_rounding_is_tight_and_valid(price: int) -> None:
    low, high = row().round_down(price), row().round_up(price)
    assert low <= price <= high
    assert row().is_valid(low)
    assert row().is_valid(high)
    assert not any(row().is_valid(p) for p in range(low + 1, price))
    assert not any(row().is_valid(p) for p in range(price + 1, high))


@pytest.mark.parametrize("price", [0, -5, True, "200"])
def test_a_price_must_be_a_positive_int(price: object) -> None:
    with pytest.raises(ValueError, match=r"price must be a whole number of rupiah of at least 1"):
        row().tick_for(price)  # type: ignore[arg-type]


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("tick_sizes.toml"))


def _row(document: dict[str, object]) -> dict[str, object]:
    found = document["ticks"]
    assert isinstance(found, list)
    row = found[0]
    assert isinstance(row, dict)
    return row


@pytest.mark.parametrize(
    ("tiers", "message"),
    [
        ([], r"row 1: the first tier must start at a price of 1$"),
        ([{"from_price": 2, "tick": 1}], "the first tier must start at a price of 1"),
        (
            [{"from_price": 1, "tick": 1}, {"from_price": 1, "tick": 2}],
            "tiers must rise, got 1 after 1",
        ),
        (
            [{"from_price": 1, "tick": 2}, {"from_price": 201, "tick": 1}],
            r"the tier boundary 201 must be a multiple of both ticks around it \(2 and 1\)",
        ),
        (
            [{"from_price": 1, "tick": 1}, {"from_price": 499, "tick": 5}],
            r"the tier boundary 499 must be a multiple of both ticks around it \(1 and 5\)",
        ),
        ([{"from_price": 1, "tick": 0}], r"row 1, tier 1: tick must be an integer of at least 1"),
        ([{"from_price": 1, "tick": 1, "x": 1}], r"row 1, tier 1: unknown key 'x'"),
        ([5], r"row 1, tier 1 must be an inline table"),
    ],
)
def test_bad_tiers_are_refused(tiers: list[object], message: str) -> None:
    document = _document()
    _row(document)["tiers"] = tiers
    with pytest.raises(DataFileError, match=message):
        parse_ticks(document)


def test_bad_rows_and_documents_are_refused() -> None:
    document = _document()
    _row(document)["lot_size"] = 0
    with pytest.raises(DataFileError, match="lot_size must be an integer of at least 1"):
        parse_ticks(document)
    document = _document()
    document["other"] = 1
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'other'"):
        parse_ticks(document)
    with pytest.raises(DataFileError, match="schema must be 1"):
        parse_ticks({})


def test_settlement_is_t_plus_2_from_26_november_2018() -> None:
    settlement = parse_settlement(load_shipped("tick_sizes.toml"))
    assert settlement.on(date(2018, 11, 26)) == 2
    assert settlement.on(date(2026, 9, 25)) == 2
    with pytest.raises(UnsupportedDateError, match=r"tick_sizes\.toml \[settlement\] has no"):
        settlement.on(date(2018, 11, 23))


def test_bad_settlement_rows_are_refused() -> None:
    document = _document()
    settlement = document["settlement"]
    assert isinstance(settlement, list)
    settlement[0]["trading_days"] = 0
    with pytest.raises(DataFileError, match="trading_days must be an integer of at least 1"):
        parse_settlement(document)
    settlement[0]["trading_days"] = 2
    settlement[0]["note"] = "x"
    with pytest.raises(DataFileError, match=r"\[\[settlement\]\] row 1: unknown key 'note'"):
        parse_settlement(document)
```

<!-- file: tests/idx/test_bands.py -->
**`tests/idx/test_bands.py`**

```python
"""IDX auto-rejection bands: tier by reference price, upper bounds inclusive (t-rules.md §3)."""

import copy
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand import UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, Dated, load_shipped
from steadyhand_idx.bands import BandRow, parse_bands


@cache
def table() -> Dated[BandRow]:
    return parse_bands(load_shipped("auto_reject.toml"))


type Tier = tuple[int | None, str, str, bool]


def pct(up_to: int | None, up: str, down: str) -> Tier:
    return (up_to, up, down, False)


RUPIAH_1: Tier = (10, "1", "1", True)

# Every period, copied from t-hist.md §4 and t-rules.md §3: (from, minimum price, tiers), each tier
# (inclusive upper reference, up, down, in rupiah). A literal pin against the research.
RESEARCH = [
    (date(2020, 3, 13), 50, [pct(200, "35", "7"), pct(5000, "25", "7"), pct(None, "20", "7")]),
    (date(2023, 6, 5), 50, [pct(200, "35", "15"), pct(5000, "25", "15"), pct(None, "20", "15")]),
    (date(2023, 9, 4), 50, [pct(200, "35", "35"), pct(5000, "25", "25"), pct(None, "20", "20")]),
    (date(2025, 4, 8), 50, [pct(200, "35", "15"), pct(5000, "25", "15"), pct(None, "20", "15")]),
    (
        date(2026, 9, 28),
        1,
        [RUPIAH_1, pct(200, "35", "15"), pct(5000, "25", "15"), pct(None, "20", "15")],
    ),
    (
        date(2027, 1, 1),
        1,
        [RUPIAH_1, pct(200, "35", "35"), pct(5000, "25", "25"), pct(None, "20", "20")],
    ),
]


def test_every_period_matches_the_research() -> None:
    assert table().starts == tuple(start for start, _, _ in RESEARCH)
    for start, min_price, tiers in RESEARCH:
        row = table().on(start)
        assert row.min_price == min_price, start
        found = [(t.up_to, str(t.up), str(t.down), t.in_rupiah) for t in row.tiers]
        assert found == tiers, start


def test_the_table_is_verified_from_13_march_2020() -> None:
    with pytest.raises(UnsupportedDateError, match=r"auto_reject\.toml \[bands\] has no verified"):
        table().on(date(2020, 3, 12))


@pytest.mark.parametrize(
    ("on", "reference", "up"),
    [
        (date(2025, 4, 8), 200, "35"),  # 200 is in the LOWER tier here, unlike the tick table
        (date(2025, 4, 8), 201, "25"),
        (date(2025, 4, 8), 5_000, "25"),
        (date(2025, 4, 8), 5_001, "20"),
        (date(2026, 9, 28), 10, "1"),
        (date(2026, 9, 28), 11, "35"),
    ],
)
def test_the_tier_edges_are_inclusive_of_the_upper_bound(on: date, reference: int, up: str) -> None:
    assert table().on(on).tier_for(reference).up == Decimal(up)


def test_percentage_limits_are_exact() -> None:
    assert table().on(date(2025, 4, 8)).limits(1_000) == (Decimal(850), Decimal(1_250))
    assert table().on(date(2020, 3, 13)).limits(155) == (Decimal("144.15"), Decimal("209.25"))


def test_rupiah_limits_are_one_either_way() -> None:
    assert table().on(date(2026, 9, 28)).limits(7) == (Decimal(6), Decimal(8))


@pytest.mark.parametrize("reference", [0, -1, True])
def test_a_reference_must_be_a_positive_int(reference: int) -> None:
    with pytest.raises(
        ValueError, match="reference must be a whole number of rupiah of at least 1"
    ):
        table().on(date(2025, 4, 8)).tier_for(reference)


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("auto_reject.toml"))


def _first_row(document: dict[str, object]) -> dict[str, object]:
    found = document["bands"]
    assert isinstance(found, list)
    row = found[0]
    assert isinstance(row, dict)
    return row


TOP = {"up_percent": "20", "down_percent": "7"}


@pytest.mark.parametrize(
    ("tiers", "message"),
    [
        ([{"up_to": 200, **TOP}], r"row 1, tier 1: the top tier has no up_to"),
        ([{"up_percent": "20"}, TOP], r"row 1, tier 1: missing key 'up_to'"),
        (
            [{"up_to": 200, "up_percent": "35", "down_rupiah": 1}, TOP],
            "give the band in percent or in rupiah, not both",
        ),
        ([{"up_to": 10, "down_rupiah": 1}, TOP], "missing key 'up_rupiah'"),
        (
            [{"up_percent": "0", "down_percent": "7"}],
            "percentages must be above 0, and down below 100",
        ),
        ([{"up_percent": "20", "down_percent": "100"}], "percentages must be above 0"),
        ([{"up_to": 20, **TOP}, TOP], "the first tier ends at 20, below the minimum price 50"),
        (
            [{"up_to": 200, **TOP}, {"up_to": 200, **TOP}, TOP],
            "tier bounds must rise, got 200 after 200",
        ),
        ([{**TOP, "note": "x"}], "unknown key 'note'"),
    ],
)
def test_bad_tiers_are_refused(tiers: list[dict[str, object]], message: str) -> None:
    document = _document()
    _first_row(document)["tiers"] = tiers
    with pytest.raises(DataFileError, match=message):
        parse_bands(document)


def test_bad_documents_are_refused() -> None:
    document = _document()
    document["x"] = 1
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'x'"):
        parse_bands(document)
    document = _document()
    _first_row(document)["min_price"] = 0
    with pytest.raises(DataFileError, match="min_price must be an integer of at least 1"):
        parse_bands(document)
```

- [ ] **Step 3: Write the stubs.**

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/ticks.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/ticks.py` (stub)**

```python
"""The IDX tick table, board lot and settlement cycle, from ``data/tick_sizes.toml`` (spec §9.1).

Prices here are whole rupiah (``int``). A tier's lower bound is inclusive and the tier is chosen
by the price itself (docs/research/t-rules.md §1).
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_int,
    get_str,
    get_tables,
    only_keys,
    require_schema,
    rows,
)

TICKS_FILE = "tick_sizes.toml"


@dataclass(frozen=True, slots=True)
class TickTier:
    """Prices from ``from_price`` (inclusive) up to the next tier trade on multiples of ``tick``."""

    from_price: int
    tick: int


@dataclass(frozen=True, slots=True)
class TickRow:
    """One period's tick tiers and board lot."""

    source: str
    lot_size: int
    tiers: tuple[TickTier, ...]

    def tick_for(self, price: int) -> int:
        """The tick of the tier *price* falls in."""
        raise NotImplementedError("TickRow.tick_for")

    def is_valid(self, price: int) -> bool:
        raise NotImplementedError("TickRow.is_valid")

    def round_down(self, price: int) -> int:
        """The highest valid price at or below *price*."""
        raise NotImplementedError("TickRow.round_down")

    def round_up(self, price: int) -> int:
        """The lowest valid price at or above *price*.

        Rounding up within a tier never passes the next tier's lower bound, because the loader
        requires every lower bound to be a multiple of the tick below it.
        """
        raise NotImplementedError("TickRow.round_up")


def _parse_tier(tier: Row, where: Where) -> TickTier:
    raise NotImplementedError("_parse_tier")


def _parse_row(row: Row, where: Where) -> TickRow:
    raise NotImplementedError("_parse_row")


def parse_ticks(document: Row, file: str = TICKS_FILE) -> Dated[TickRow]:
    raise NotImplementedError("parse_ticks")


def parse_settlement(document: Row, file: str = TICKS_FILE) -> Dated[int]:
    """Settlement, in trading days after the trade day, effective-dated."""
    raise NotImplementedError("parse_settlement")
```

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/bands.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/bands.py` (stub)**

```python
"""IDX auto-rejection bands and the minimum price, from ``data/auto_reject.toml`` (spec §9.1).

The tier is chosen by the reference price, and each tier's ``up_to`` is inclusive: 200 and 5,000
fall in the lower tier, unlike the tick table (docs/research/t-rules.md §3). This module gives
the band's exact limits. Turning them into prices an order can carry, on the tick grid and not
below the minimum price, is ``IdxMarketRules.price_band``'s job, because it needs both tables.
"""

from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise
from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_decimal,
    get_int,
    get_str,
    get_tables,
    only_keys,
    require_schema,
    rows,
)

BANDS_FILE = "auto_reject.toml"
_HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class BandTier:
    """How far a price may move from a reference in this tier, by percentage or in rupiah.

    ``up_to`` is the highest reference price in the tier (inclusive), or ``None`` for the top tier.
    """

    up_to: int | None
    up: Decimal
    down: Decimal
    in_rupiah: bool

    def limits(self, reference: int) -> tuple[Decimal, Decimal]:
        """The exact (lowest, highest) accepted prices, before tick rounding."""
        raise NotImplementedError("BandTier.limits")


@dataclass(frozen=True, slots=True)
class BandRow:
    """One period's minimum price and band tiers."""

    source: str
    min_price: int
    tiers: tuple[BandTier, ...]

    def tier_for(self, reference: int) -> BandTier:
        raise NotImplementedError("BandRow.tier_for")

    def limits(self, reference: int) -> tuple[Decimal, Decimal]:
        """The exact (lowest, highest) prices the band accepts around *reference*."""
        raise NotImplementedError("BandRow.limits")


def _parse_tier(tier: Row, where: Where, *, last: bool) -> BandTier:
    raise NotImplementedError("_parse_tier")


def _parse_row(row: Row, where: Where) -> BandRow:
    raise NotImplementedError("_parse_row")


def parse_bands(document: Row, file: str = BANDS_FILE) -> Dated[BandRow]:
    raise NotImplementedError("parse_bands")
```

- [ ] **Step 4: Run the tests and watch them fail.**

Run: `uv run --locked pytest -W error -q tests/idx/test_ticks.py tests/idx/test_bands.py`
Expected: `68 failed`, each on a `NotImplementedError`. None passes.

- [ ] **Step 5: Write the data and the implementation.**

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/data/tick_sizes.toml -->
**`packages/steadyhand-idx/src/steadyhand_idx/data/tick_sizes.toml`**

```toml
# IDX price fractions (fraksi harga), the board lot and the settlement cycle, effective-dated.
# Spec §3.6 and §9.1.
#
# The tier is chosen by the order price itself, and each tier's lower bound is inclusive:
# II-A VI.5.2 sets the tiers and VI.5.4 moves them with the order price (docs/research/t-rules.md
# §1). So 199 is on a Rp1 grid, 200 on Rp2, 500 on Rp5, 2,000 on Rp10 and 5,000 on Rp25.
# These tiers differ from the auto-rejection tiers in auto_reject.toml, where 200 and 5,000 sit
# in the LOWER tier; the two files never share a tier rule.
#
# Only primary-verified rows are shipped (spec §9.1). The five-tier table is verified from
# 13 Mar 2020 (Kep-00025/BEI/03-2020; docs/research/t-hist.md §3) and unchanged in every II-A
# since. Its earlier history is supported by prices but has no IDX text, so it is not here.

schema = 1

[[ticks]]
from = 2020-03-13
source = "Kep-00025/BEI/03-2020, Rule II-A VI.4.2 and VI.5.2 (unchanged through Kep-00136/BEI/09-2026)"
lot_size = 100
tiers = [
    { from_price = 1, tick = 1 },
    { from_price = 200, tick = 2 },
    { from_price = 500, tick = 5 },
    { from_price = 2000, tick = 10 },
    { from_price = 5000, tick = 25 },
]

# Settlement in IDX trading days after the trade day. POJK 21/POJK.04/2018 Pasal 2(2): "Penyelesaian
# atas Transaksi Bursa di pasar reguler dilaksanakan pada Hari Bursa ke-2 (kedua) setelah hari
# pelaksanaan Transaksi Bursa (T+2)". It was in force on promulgation, 21 Nov 2018 (Pasal 13), and
# the market's first T+2 trade day is reported as 26 Nov 2018. The row starts on the later date,
# the one both readings agree on.
[[settlement]]
from = 2018-11-26
source = "POJK 21/POJK.04/2018 Pasal 2(2) (peraturan.bpk.go.id/Details/128635, status Berlaku)"
trading_days = 2
```

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/data/auto_reject.toml -->
**`packages/steadyhand-idx/src/steadyhand_idx/data/auto_reject.toml`**

```toml
# IDX auto-rejection (ARA/ARB) bands and the minimum price, effective-dated. Spec §9.1.
#
# An order is rejected when its price is MORE than the stated amount above or below the
# reference price (Acuan Harga), so a price exactly on the limit is accepted. The tier is chosen
# by the reference price, and `up_to` is inclusive: 200 and 5,000 sit in the LOWER tier here,
# unlike the tick table (docs/research/t-rules.md §3). A tier gives either percentages or, for
# the lowest prices from 28 Sep 2026, a fixed number of rupiah either way.
#
# The reference price is the previous close from 7 Sep 2020, and the opening price from 13 Mar to
# 6 Sep 2020 (docs/research/t-verify.md §4). The caller supplies it; this file only says how far
# a price may move from it. Rows repeat every field, so no row depends on the one before it.
#
# Only primary-verified rows are shipped (spec §9.1): the bands are verified from 13 Mar 2020
# (docs/research/t-hist.md §4). Kep-00108 (7 Dec 2020), Kep-00061 (26 Jul 2021) and Kep-00055's
# first phase (3 Apr 2023) kept the same values, so they need no row of their own.

schema = 1

[[bands]]
from = 2020-03-13
source = "Kep-00025/BEI/03-2020, Memutuskan 1 and II-A VI.7.1.1"
min_price = 50
tiers = [
    { up_to = 200, up_percent = "35", down_percent = "7" },
    { up_to = 5000, up_percent = "25", down_percent = "7" },
    { up_percent = "20", down_percent = "7" },
]

[[bands]]
from = 2023-06-05
source = "Kep-00055/BEI/03-2023, Memutuskan 4.b"
min_price = 50
tiers = [
    { up_to = 200, up_percent = "35", down_percent = "15" },
    { up_to = 5000, up_percent = "25", down_percent = "15" },
    { up_percent = "20", down_percent = "15" },
]

[[bands]]
from = 2023-09-04
source = "Kep-00055/BEI/03-2023, Memutuskan 4.c and II-A VI.7.1.2"
min_price = 50
tiers = [
    { up_to = 200, up_percent = "35", down_percent = "35" },
    { up_to = 5000, up_percent = "25", down_percent = "25" },
    { up_percent = "20", down_percent = "20" },
]

[[bands]]
from = 2025-04-08
source = "Kep-00003/BEI/04-2025, Memutuskan 2 and II-A VI.6.1"
min_price = 50
tiers = [
    { up_to = 200, up_percent = "35", down_percent = "15" },
    { up_to = 5000, up_percent = "25", down_percent = "15" },
    { up_percent = "20", down_percent = "15" },
]

[[bands]]
from = 2026-09-28
source = "Kep-00136/BEI/09-2026, Memutuskan 2-3 and II-A VI.6"
min_price = 1
tiers = [
    { up_to = 10, up_rupiah = 1, down_rupiah = 1 },
    { up_to = 200, up_percent = "35", down_percent = "15" },
    { up_to = 5000, up_percent = "25", down_percent = "15" },
    { up_percent = "20", down_percent = "15" },
]

[[bands]]
from = 2027-01-01
source = "Kep-00136/BEI/09-2026, II-A VI.7.1.1"
min_price = 1
tiers = [
    { up_to = 10, up_rupiah = 1, down_rupiah = 1 },
    { up_to = 200, up_percent = "35", down_percent = "35" },
    { up_to = 5000, up_percent = "25", down_percent = "25" },
    { up_percent = "20", down_percent = "20" },
]
```

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/ticks.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/ticks.py`**

```python
"""The IDX tick table, board lot and settlement cycle, from ``data/tick_sizes.toml`` (spec §9.1).

Prices here are whole rupiah (``int``). A tier's lower bound is inclusive and the tier is chosen
by the price itself (docs/research/t-rules.md §1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_int,
    get_str,
    get_tables,
    only_keys,
    require_schema,
    rows,
)

TICKS_FILE = "tick_sizes.toml"


@dataclass(frozen=True, slots=True)
class TickTier:
    """Prices from ``from_price`` (inclusive) up to the next tier trade on multiples of ``tick``."""

    from_price: int
    tick: int


@dataclass(frozen=True, slots=True)
class TickRow:
    """One period's tick tiers and board lot."""

    source: str
    lot_size: int
    tiers: tuple[TickTier, ...]

    def tick_for(self, price: int) -> int:
        """The tick of the tier *price* falls in."""
        if type(price) is not int or price < 1:
            msg = f"price must be a whole number of rupiah of at least 1, got {price!r}"
            raise ValueError(msg)
        return next(tier.tick for tier in reversed(self.tiers) if tier.from_price <= price)

    def is_valid(self, price: int) -> bool:
        return price % self.tick_for(price) == 0

    def round_down(self, price: int) -> int:
        """The highest valid price at or below *price*."""
        return price - price % self.tick_for(price)

    def round_up(self, price: int) -> int:
        """The lowest valid price at or above *price*.

        Rounding up within a tier never passes the next tier's lower bound, because the loader
        requires every lower bound to be a multiple of the tick below it.
        """
        remainder = price % self.tick_for(price)
        return price if remainder == 0 else price + self.tick_for(price) - remainder


def _parse_tier(tier: Row, where: Where) -> TickTier:
    only_keys(tier, {"from_price", "tick"}, where)
    return TickTier(
        get_int(tier, "from_price", where, minimum=1), get_int(tier, "tick", where, minimum=1)
    )


def _parse_row(row: Row, where: Where) -> TickRow:
    only_keys(row, {"from", "source", "lot_size", "tiers"}, where)
    tiers = tuple(
        _parse_tier(tier, place) for tier, place in get_tables(row, "tiers", where, label="tier")
    )
    if not tiers or tiers[0].from_price != 1:
        msg = f"{where}: the first tier must start at a price of 1"
        raise DataFileError(msg)
    for lower, upper in pairwise(tiers):
        if upper.from_price <= lower.from_price:
            msg = f"{where}: tiers must rise, got {upper.from_price} after {lower.from_price}"
            raise DataFileError(msg)
        if upper.from_price % lower.tick or upper.from_price % upper.tick:
            msg = (
                f"{where}: the tier boundary {upper.from_price} must be a multiple of both "
                f"ticks around it ({lower.tick} and {upper.tick})"
            )
            raise DataFileError(msg)
    return TickRow(get_str(row, "source", where), get_int(row, "lot_size", where, minimum=1), tiers)


def parse_ticks(document: Row, file: str = TICKS_FILE) -> Dated[TickRow]:
    require_schema(document, file, 1)
    only_keys(document, {"schema", "ticks", "settlement"}, Where(file, "top level"))
    where = Where(file, "ticks")
    found = rows(document, "ticks", where)
    return Dated(
        where,
        tuple(get_date(row, "from", where.at(i)) for i, row in enumerate(found, start=1)),
        tuple(_parse_row(row, where.at(i)) for i, row in enumerate(found, start=1)),
    )


def parse_settlement(document: Row, file: str = TICKS_FILE) -> Dated[int]:
    """Settlement, in trading days after the trade day, effective-dated."""
    where = Where(file, "settlement")
    starts: list[date] = []
    days: list[int] = []
    for index, row in enumerate(rows(document, "settlement", where), start=1):
        place = where.at(index)
        only_keys(row, {"from", "source", "trading_days"}, place)
        get_str(row, "source", place)
        starts.append(get_date(row, "from", place))
        days.append(get_int(row, "trading_days", place, minimum=1))
    return Dated(where, tuple(starts), tuple(days))
```

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/bands.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/bands.py`**

```python
"""IDX auto-rejection bands and the minimum price, from ``data/auto_reject.toml`` (spec §9.1).

The tier is chosen by the reference price, and each tier's ``up_to`` is inclusive: 200 and 5,000
fall in the lower tier, unlike the tick table (docs/research/t-rules.md §3). This module gives
the band's exact limits. Turning them into prices an order can carry, on the tick grid and not
below the minimum price, is ``IdxMarketRules.price_band``'s job, because it needs both tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_decimal,
    get_int,
    get_str,
    get_tables,
    only_keys,
    require_schema,
    rows,
)

BANDS_FILE = "auto_reject.toml"
_HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class BandTier:
    """How far a price may move from a reference in this tier, by percentage or in rupiah.

    ``up_to`` is the highest reference price in the tier (inclusive), or ``None`` for the top tier.
    """

    up_to: int | None
    up: Decimal
    down: Decimal
    in_rupiah: bool

    def limits(self, reference: int) -> tuple[Decimal, Decimal]:
        """The exact (lowest, highest) accepted prices, before tick rounding."""
        if self.in_rupiah:
            return reference - self.down, reference + self.up
        return (
            reference * (_HUNDRED - self.down) / _HUNDRED,
            reference * (_HUNDRED + self.up) / _HUNDRED,
        )


@dataclass(frozen=True, slots=True)
class BandRow:
    """One period's minimum price and band tiers."""

    source: str
    min_price: int
    tiers: tuple[BandTier, ...]

    def tier_for(self, reference: int) -> BandTier:
        if type(reference) is not int or reference < 1:
            msg = f"reference must be a whole number of rupiah of at least 1, got {reference!r}"
            raise ValueError(msg)
        return next(t for t in self.tiers if t.up_to is None or reference <= t.up_to)

    def limits(self, reference: int) -> tuple[Decimal, Decimal]:
        """The exact (lowest, highest) prices the band accepts around *reference*."""
        return self.tier_for(reference).limits(reference)


def _parse_tier(tier: Row, where: Where, *, last: bool) -> BandTier:
    only_keys(tier, {"up_to", "up_percent", "down_percent", "up_rupiah", "down_rupiah"}, where)
    up_to = None if last else get_int(tier, "up_to", where, minimum=1)
    if last and "up_to" in tier:
        msg = f"{where}: the top tier has no up_to"
        raise DataFileError(msg)
    in_rupiah = "up_rupiah" in tier or "down_rupiah" in tier
    if in_rupiah and ("up_percent" in tier or "down_percent" in tier):
        msg = f"{where}: give the band in percent or in rupiah, not both"
        raise DataFileError(msg)
    if in_rupiah:
        up = Decimal(get_int(tier, "up_rupiah", where, minimum=1))
        down = Decimal(get_int(tier, "down_rupiah", where, minimum=1))
    else:
        up = get_decimal(tier, "up_percent", where)
        down = get_decimal(tier, "down_percent", where)
        if not (up > 0 and 0 < down < _HUNDRED):
            msg = f"{where}: percentages must be above 0, and down below 100"
            raise DataFileError(msg)
    return BandTier(up_to, up, down, in_rupiah)


def _parse_row(row: Row, where: Where) -> BandRow:
    only_keys(row, {"from", "source", "min_price", "tiers"}, where)
    listed = get_tables(row, "tiers", where, label="tier")
    tiers = tuple(
        _parse_tier(tier, place, last=index == len(listed))
        for index, (tier, place) in enumerate(listed, start=1)
    )
    min_price = get_int(row, "min_price", where, minimum=1)
    bounds = [tier.up_to for tier in tiers if tier.up_to is not None]
    if bounds and bounds[0] < min_price:
        msg = f"{where}: the first tier ends at {bounds[0]}, below the minimum price {min_price}"
        raise DataFileError(msg)
    for lower, upper in pairwise(bounds):
        if upper <= lower:
            msg = f"{where}: tier bounds must rise, got {upper} after {lower}"
            raise DataFileError(msg)
    return BandRow(get_str(row, "source", where), min_price, tiers)


def parse_bands(document: Row, file: str = BANDS_FILE) -> Dated[BandRow]:
    require_schema(document, file, 1)
    only_keys(document, {"schema", "bands"}, Where(file, "top level"))
    where = Where(file, "bands")
    found = rows(document, "bands", where)
    return Dated(
        where,
        tuple(get_date(row, "from", where.at(i)) for i, row in enumerate(found, start=1)),
        tuple(_parse_row(row, where.at(i)) for i, row in enumerate(found, start=1)),
    )
```

- [ ] **Step 6: Run the whole gate.**

Run: `uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy && uv run --locked pytest -W error --cov -q`
Expected: every check passes; `387 passed`; 100% coverage.

- [ ] **Step 7: Mutations M1 and M2.**

- [ ] **Step 8: Commit, push and merge.**

```bash
git add packages/steadyhand-idx tests/idx
git commit -m "feat(idx): tick table, lot, T+2 settlement and auto-rejection bands (#<S2>)"
```

---

### Task 3: S3 Fees, taxes and broker presets

**Acceptance criteria (story text):**
1. `data/fees.toml` carries the levy's four components from 13 Mar 2020 (with the guarantee fund at 0.005% from 18 Jun to 17 Dec 2020), VAT (10%, then 11% from 1 Apr 2022), the 0.1% sale tax, stamp duty from 2021-01-01 (every confirmation) and from 2022-01-12 (above Rp10,000,000), and the 10% dividend tax. Every row names its source.
2. The levy with VAT matches `t-fees.md` §1.5 on each period's edges: 0.043%, 0.038%, 0.043%, 0.0433%. VAT is charged on the IDX, KPEI and KSEI fees and on the commission, never on the guarantee fund.
3. A trade's costs are summed exactly and rounded once, up. On Rp10,000,000 today: `custom` 20,980 buy and 30,980 sell; `ajaib` 15,130 and 25,130. A hypothesis property pins the total to the ceiling of the literal all-in rate, and pins the tax line to 0.1% rounded down on every sale.
4. An all-in preset keeps its quoted total when the levy was lower (Ajaib in July 2020 still costs 0.1513%), and the loader refuses a preset whose quote is smaller than what it says it includes.
5. `daily_costs` charges Rp10,000 on any day with trades from 2021-01-01, nothing on 12 Jan 2022 for exactly Rp10,000,000 and Rp10,000 for Rp10,000,001, and refuses 2020-12-31 naming `fees.toml [stamp_duty]`.
6. Only `ajaib` and `custom` ship; asking for `stockbit` names the presets that exist.
7. CI's build job checks that the IDX wheel carries all four data files.
8. Every quality gate is green at 100% branch coverage, and the red phase is recorded in the PR.

**Files:**
- Create: `.../steadyhand_idx/fees.py`, `.../data/fees.toml`
- Modify: `.../steadyhand_idx/__init__.py`, `.github/workflows/ci.yml`
- Test: `tests/idx/test_fees.py`

**Interfaces:**
- Consumes: `_datafile` (Task 1); engine `IDR`, `Costs`, `Money`, `Rounding`, `Side`.
- Produces: in `steadyhand_idx.fees`: `FEES_FILE`, `INCLUDABLE`; `Levy(exchange, clearing, settlement, guarantee_fund)` with `.with_vat(vat) -> Decimal`; `StampDuty(amount, exempt_up_to)`; `BrokerPreset(name, source, buy, sell, includes)`; `Percentages(fee, levy, tax)`; `FeeSchedule(levy, vat, sale_tax, stamp_duty, dividend_tax_rate, presets)` with `.shipped()`, `.tables`, `.preset(name)`, `.percentages(preset, side, on)`, `.trade_costs(preset, side, gross, on) -> Costs`, `.daily_costs(traded, on) -> Money`, `.dividend_tax(gross, *, reinvested_by_deadline, on) -> Money`; `parse_fees(document, file=...) -> FeeSchedule`.

- [ ] **Step 1: Branch.** `git switch -c m2/s3-fees origin/develop` (after S2 is merged).

- [ ] **Step 2: Write the failing tests.**

<!-- file: tests/idx/test_fees.py -->
**`tests/idx/test_fees.py`**

```python
"""IDX trading costs: levy, VAT, sale tax, stamp duty, dividend tax and broker presets."""

import copy
import math
from datetime import date
from decimal import Decimal
from fractions import Fraction
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import IDR, Currency, Money, Side, UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, load_shipped
from steadyhand_idx.fees import BrokerPreset, FeeSchedule, parse_fees


@cache
def fees() -> FeeSchedule:
    return FeeSchedule.shipped()


@cache
def ajaib() -> BrokerPreset:
    return fees().preset("ajaib")


@cache
def custom() -> BrokerPreset:
    return fees().preset("custom")


TODAY = date(2026, 9, 25)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


@pytest.mark.parametrize(
    ("on", "levy"),
    [
        # t-fees.md §1.5 and t-verify.md §2: the levy per side, VAT included.
        (date(2020, 3, 13), "0.0430"),
        (date(2020, 6, 17), "0.0430"),
        (date(2020, 6, 18), "0.0380"),
        (date(2020, 12, 17), "0.0380"),
        (date(2020, 12, 18), "0.0430"),
        (date(2022, 3, 31), "0.0430"),
        (date(2022, 4, 1), "0.0433"),
        (date(2025, 1, 1), "0.0433"),
    ],
)
def test_the_levy_matches_the_research(on: date, levy: str) -> None:
    assert fees().levy.on(on).with_vat(fees().vat.on(on)) == Decimal(levy)


def test_the_tables_start_where_their_rows_are_verified() -> None:
    assert [table.first for table in fees().tables] == [
        date(2020, 3, 13),  # levy
        date(2016, 1, 1),  # VAT
        date(2016, 1, 1),  # sale tax
        date(2021, 1, 1),  # stamp duty
        date(2009, 1, 1),  # dividend tax
    ]


@pytest.mark.parametrize(
    ("preset", "side", "total"),
    [
        ("custom", Side.BUY, 20_980),  # 0.15% x 1.11 + 0.0433% = 0.2098%
        ("custom", Side.SELL, 30_980),  # plus the 0.1% sale tax
        ("ajaib", Side.BUY, 15_130),  # all-in 0.1513%
        ("ajaib", Side.SELL, 25_130),  # all-in 0.2513%
    ],
)
def test_worked_examples_on_ten_million(preset: str, side: Side, total: int) -> None:
    costs = fees().trade_costs(fees().preset(preset), side, rp(10_000_000), TODAY)
    assert costs.total == rp(total)
    assert costs.levy == rp(4_330)
    assert costs.tax == rp(10_000 if side is Side.SELL else 0)


def test_an_all_in_quote_keeps_its_total_when_the_levy_was_lower() -> None:
    # 18 Jun - 17 Dec 2020 the levy was 0.038%, so more of Ajaib's 0.1513% is commission.
    costs = fees().trade_costs(ajaib(), Side.BUY, rp(10_000_000), date(2020, 7, 1))
    assert costs.total == rp(15_130)
    assert costs.levy == rp(3_800)


def test_a_small_trade_rounds_the_total_up_once() -> None:
    # 1,001 x 0.2098% = 2.100098: the total rounds up to 3; the levy line (0.433) rounds down.
    costs = fees().trade_costs(custom(), Side.BUY, rp(1_001), TODAY)
    assert (costs.fee, costs.levy, costs.tax) == (rp(3), rp(0), rp(0))


# Each preset's all-in rate today, in percent, worked out by hand above: a literal pin.
TOTAL_PERCENT = {
    ("custom", Side.BUY): "0.2098",
    ("custom", Side.SELL): "0.3098",
    ("ajaib", Side.BUY): "0.1513",
    ("ajaib", Side.SELL): "0.2513",
}


@given(
    gross=st.integers(min_value=0, max_value=10**12),
    key=st.sampled_from(sorted(TOTAL_PERCENT, key=str)),
)
def test_costs_round_once_against_the_trader(gross: int, key: tuple[str, Side]) -> None:
    preset, side = key
    costs = fees().trade_costs(fees().preset(preset), side, rp(gross), TODAY)
    exact = Fraction(gross) * Fraction(TOTAL_PERCENT[key]) / 100
    assert costs.total.amount == math.ceil(exact)
    assert min(costs.fee.amount, costs.levy.amount, costs.tax.amount) >= 0
    expected_tax = gross // 1000 if side is Side.SELL else 0  # every sale pays 0.1%, rounded down
    assert costs.tax.amount == expected_tax


def test_gross_must_be_a_non_negative_rupiah_amount() -> None:
    with pytest.raises(ValueError, match=r"^gross must be a non-negative IDR amount, got IDR -1$"):
        fees().trade_costs(custom(), Side.BUY, rp(-1), TODAY)
    with pytest.raises(ValueError, match=r"got USD 1\.00"):
        fees().trade_costs(custom(), Side.BUY, Money(100, Currency("USD", 2)), TODAY)


def test_costs_before_the_levy_is_verified_are_refused() -> None:
    with pytest.raises(UnsupportedDateError, match=r"^fees\.toml \[levy\] has no verified row"):
        fees().trade_costs(custom(), Side.BUY, rp(1_000), date(2020, 3, 12))


@pytest.mark.parametrize(
    ("on", "traded", "duty"),
    [
        (date(2021, 1, 4), 0, 0),  # nothing traded, no confirmation
        (date(2021, 1, 4), 1, 10_000),  # every confirmation, however small, until 11 Jan 2022
        (date(2022, 1, 11), 1, 10_000),
        (date(2022, 1, 12), 1, 0),  # PP 3/2022's exemption from 12 Jan 2022
        (date(2022, 1, 12), 10_000_000, 0),  # "paling banyak Rp10.000.000" is exempt
        (date(2022, 1, 12), 10_000_001, 10_000),
    ],
)
def test_stamp_duty_is_charged_as_the_law_imposed_it(on: date, traded: int, duty: int) -> None:
    assert fees().daily_costs(rp(traded), on) == rp(duty)


def test_stamp_duty_before_2021_is_refused() -> None:
    with pytest.raises(
        UnsupportedDateError,
        match=r"^fees\.toml \[stamp_duty\] has no verified row for 2020-12-31",
    ):
        fees().daily_costs(rp(1), date(2020, 12, 31))
    with pytest.raises(ValueError, match=r"^traded must be a non-negative IDR amount"):
        fees().daily_costs(rp(-1), TODAY)


def test_dividend_tax_is_ten_percent_rounded_up_unless_reinvested() -> None:
    assert fees().dividend_tax(rp(1_000_000), reinvested_by_deadline=False, on=TODAY) == rp(100_000)
    assert fees().dividend_tax(rp(999), reinvested_by_deadline=False, on=TODAY) == rp(100)
    assert fees().dividend_tax(rp(999), reinvested_by_deadline=True, on=TODAY) == rp(0)


def test_only_presets_that_state_what_they_include_are_shipped() -> None:
    assert sorted(fees().presets) == ["ajaib", "custom"]
    assert ajaib().includes == {"levy", "commission_vat", "sale_tax"}
    assert custom().includes == frozenset()
    with pytest.raises(
        ValueError, match=r"^no broker fee preset named 'stockbit'; fees\.toml has ajaib, custom$"
    ):
        fees().preset("stockbit")


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("fees.toml"))


def _table(document: dict[str, object], name: str) -> dict[str, object]:
    found = document[name]
    assert isinstance(found, dict)
    return found


def _first_row(document: dict[str, object], name: str) -> dict[str, object]:
    found = document[name]
    assert isinstance(found, list)
    row = found[0]
    assert isinstance(row, dict)
    return row


def test_an_all_in_quote_smaller_than_what_it_includes_is_refused() -> None:
    document = _document()
    _table(_table(document, "presets"), "ajaib")["buy_percent"] = "0.04"
    with pytest.raises(
        DataFileError,
        match=(
            r"^fees\.toml preset 'ajaib': its buy quote is smaller than the costs it says it "
            r"includes on 2020-03-13$"
        ),
    ):
        parse_fees(document)


@pytest.mark.parametrize(
    ("includes", "message"),
    [
        (["levy", "levy"], "includes may list each of commission_vat, levy, sale_tax once"),
        (["broker"], "got 'broker'"),
    ],
)
def test_includes_is_checked(includes: list[str], message: str) -> None:
    document = _document()
    _table(_table(document, "presets"), "custom")["includes"] = includes
    with pytest.raises(DataFileError, match=message):
        parse_fees(document)


def test_bad_documents_are_refused() -> None:
    document = _document()
    _table(document, "presets")["broken"] = 5
    with pytest.raises(DataFileError, match=r"fees\.toml \[presets\.broken\] must be a table"):
        parse_fees(document)
    document = _document()
    document["presets"] = {}
    with pytest.raises(DataFileError, match=r"\[presets\] must be a table with at least one"):
        parse_fees(document)
    document = _document()
    _first_row(document, "levy")["exchange"] = "0.018"
    with pytest.raises(DataFileError, match=r"\[\[levy\]\] row 1: unknown key 'exchange'"):
        parse_fees(document)
    document = _document()
    del _first_row(document, "vat")["source"]
    with pytest.raises(DataFileError, match=r"\[\[vat\]\] row 1: missing key 'source'"):
        parse_fees(document)
    document = _document()
    _table(_table(document, "presets"), "ajaib")["checked"] = "2026-09-25"
    with pytest.raises(DataFileError, match="checked must be a TOML date"):
        parse_fees(document)
    document = _document()
    document["levies"] = []
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'levies'"):
        parse_fees(document)
```

- [ ] **Step 3: Write the stub.**

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/fees.py` (stub)**

```python
"""IDX trading costs and taxes, from ``data/fees.toml`` (spec §5.1, docs/research/t-fees.md).

Every component is worked out exactly as a percentage of the gross value, the components are
summed, and the total is rounded once to the rupiah, against the trader (spec §4.4). The levy and
tax lines of ``Costs`` are rounded down and the broker line takes the rest, so the three lines
always add up to the rounded total and none of them is negative.
"""

from __future__ import annotations
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from types import MappingProxyType
from steadyhand import IDR, Costs, Money, Rounding, Side
from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_decimal,
    get_int,
    get_list,
    get_str,
    load_shipped,
    only_keys,
    require_schema,
    rows,
)

FEES_FILE = "fees.toml"
INCLUDABLE = frozenset({"levy", "commission_vat", "sale_tax"})
_HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class Levy:
    """The exchange-side charges per side, in percent of the gross value."""

    exchange: Decimal
    clearing: Decimal
    settlement: Decimal
    guarantee_fund: Decimal

    def with_vat(self, vat: Decimal) -> Decimal:
        """The levy in percent, VAT included on every part except the guarantee fund."""
        raise NotImplementedError("Levy.with_vat")


@dataclass(frozen=True, slots=True)
class StampDuty:
    """``amount`` rupiah on a day's trade confirmation worth more than ``exempt_up_to``."""

    amount: int
    exempt_up_to: int


@dataclass(frozen=True, slots=True)
class BrokerPreset:
    """A broker's quoted rate per side, in percent, and what that quote already contains."""

    name: str
    source: str
    buy: Decimal
    sell: Decimal
    includes: frozenset[str]


@dataclass(frozen=True, slots=True)
class Percentages:
    """One trade's costs in percent of its gross value, before any rounding."""

    fee: Decimal
    levy: Decimal
    tax: Decimal


@dataclass(frozen=True, slots=True)
class FeeSchedule:
    """The dated cost tables and the broker presets from one ``fees.toml``."""

    levy: Dated[Levy]
    vat: Dated[Decimal]
    sale_tax: Dated[Decimal]
    stamp_duty: Dated[StampDuty]
    dividend_tax_rate: Dated[Decimal]
    presets: Mapping[str, BrokerPreset]

    def __post_init__(self) -> None:
        raise NotImplementedError("FeeSchedule.__post_init__")

    @classmethod
    def shipped(cls) -> FeeSchedule:
        """The schedule from the package's own ``data/fees.toml``."""
        raise NotImplementedError("FeeSchedule.shipped")

    @property
    def tables(self) -> tuple[Dated[object], ...]:
        """Every dated table, for working out the first day all of them are verified."""
        raise NotImplementedError("FeeSchedule.tables")

    def preset(self, name: str) -> BrokerPreset:
        raise NotImplementedError("FeeSchedule.preset")

    def percentages(self, preset: BrokerPreset, side: Side, on: date) -> Percentages:
        """The fee, levy and tax on one trade, in percent of its gross value."""
        raise NotImplementedError("FeeSchedule.percentages")

    def trade_costs(self, preset: BrokerPreset, side: Side, gross: Money, on: date) -> Costs:
        """The costs of one trade worth *gross*, rounded once, against the trader."""
        raise NotImplementedError("FeeSchedule.trade_costs")

    def daily_costs(self, traded: Money, on: date) -> Money:
        """Stamp duty on the day's trade confirmation, given the day's buys plus sells."""
        raise NotImplementedError("FeeSchedule.daily_costs")

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """10% of a gross dividend, or nothing when it is reinvested by the deadline.

        M4 replaces the flag with a read of the dividend's exemption claim (spec §6.2).
        """
        raise NotImplementedError("FeeSchedule.dividend_tax")

    def _check_quote_covers_what_it_includes(self, preset: BrokerPreset) -> None:
        """An all-in quote smaller than the levy and tax it claims to contain is a data error."""
        raise NotImplementedError("FeeSchedule._check_quote_covers_what_it_includes")


def _dated[T](
    document: Row, table: str, keys: set[str], parse: Callable[[Row, Where], T], file: str
) -> Dated[T]:
    """Read an array of dated rows, each with ``from``, ``source`` and the table's own *keys*."""
    raise NotImplementedError("_dated")


def _levy(row: Row, where: Where) -> Levy:
    raise NotImplementedError("_levy")


def _rate(row: Row, where: Where) -> Decimal:
    raise NotImplementedError("_rate")


def _stamp_duty(row: Row, where: Where) -> StampDuty:
    raise NotImplementedError("_stamp_duty")


def _preset(name: str, row: object, file: str) -> BrokerPreset:
    raise NotImplementedError("_preset")


def parse_fees(document: Row, file: str = FEES_FILE) -> FeeSchedule:
    raise NotImplementedError("parse_fees")


@cache
def _shipped_schedule() -> FeeSchedule:
    raise NotImplementedError("_shipped_schedule")
```

- [ ] **Step 4: Run the tests and watch them fail.**

Run: `uv run --locked pytest -W error -q tests/idx/test_fees.py`
Expected: `31 failed`, each on a `NotImplementedError`. None passes.

- [ ] **Step 5: Write the data and the implementation, and export the new names.**

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/data/fees.toml -->
**`packages/steadyhand-idx/src/steadyhand_idx/data/fees.toml`**

```toml
# IDX trading costs and taxes, effective-dated, and the broker fee presets. Spec §5.1 and §9.1.
#
# Rates are PERCENTAGES written as strings, so "0.018" is 0.018% and no float is involved.
# Every dated table answers from each row's `from` until the next row's, and refuses any day
# before its first row. Only primary-verified rows are shipped (spec §9.1): the sources are in
# docs/research/t-fees.md and docs/research/t-verify.md.
#
# The levy is charged per side on the gross trade value. VAT is charged on the IDX, KPEI and KSEI
# fees and on a broker's commission, but not on the guarantee fund (t-fees.md §1).

schema = 1

[[levy]]
from = 2020-03-13
source = "IDX 0.018%: Kep-00025/BEI/03-2020, II-A XI.1.1. KPEI 0.009%: KPEI AR 2019. KSEI 0.003%: SE-0002/DIR-EKS/KSEI/1211, KSEI AR 2019 and 2020 note 27a. Guarantee fund 0.01%: SEOJK 23/SEOJK.04/2015"
exchange_percent = "0.018"
clearing_percent = "0.009"
settlement_percent = "0.003"
guarantee_fund_percent = "0.010"

[[levy]]
from = 2020-06-18
source = "KEP-019/DIR/KPEI/0620 halved the guarantee fund from 18 Jun to 17 Dec 2020 (KPEI AR 2021, guarantee-fund note)"
exchange_percent = "0.018"
clearing_percent = "0.009"
settlement_percent = "0.003"
guarantee_fund_percent = "0.005"

[[levy]]
from = 2020-12-18
source = "KEP-019/DIR/KPEI/0620 ended on 17 Dec 2020; KSEI Rule VI-A (KEP-0005/DIR/KSEI/0121, 20 Jan 2021) kept 0.003%"
exchange_percent = "0.018"
clearing_percent = "0.009"
settlement_percent = "0.003"
guarantee_fund_percent = "0.010"

[[vat]]
from = 2016-01-01
source = "UU 42/2009 Pasal 7(1)"
rate_percent = "10"

[[vat]]
from = 2022-04-01
source = "UU 7/2021 (HPP) Pasal 7(1)a. From 1 Jan 2025, PMK 131/2024 charges 12% on 11/12 of the base, which is still 11%"
rate_percent = "11"

[[sale_tax]]
from = 2016-01-01
source = "PP 41/1994 Pasal 1(2)a as amended by PP 14/1997: 0.1% of the gross value of every share sale"
rate_percent = "0.1"

# Stamp duty on the trade confirmation, which brokers issue once per trading day. It is charged
# as the law imposed it (Shyden, 2026-09-25), not from each broker's collection date: every
# confirmation from 1 Jan 2021, and from 12 Jan 2022 only one worth more than Rp10,000,000.
# Before 2021 it is unverified, so this table starts in 2021 and sets the earliest backtest date.
[[stamp_duty]]
from = 2021-01-01
source = "UU 10/2020 Pasal 3(2)e and Pasal 5; its elucidation names the trade confirmation"
amount_rupiah = 10000
exempt_up_to_rupiah = 0

[[stamp_duty]]
from = 2022-01-12
source = "PP 3/2022 Pasal 5 huruf b and Pasal 7: confirmations worth at most Rp10,000,000 are exempt"
amount_rupiah = 10000
exempt_up_to_rupiah = 10000000

[[dividend_tax]]
from = 2009-01-01
source = "PP 19/2009 and UU PPh Pasal 17(2c): 10% final for resident individuals (docs/research/t-tax.md)"
rate_percent = "10"

# Broker presets. `includes` lists what the quoted rate already contains, from "levy",
# "commission_vat" and "sale_tax", so nothing is charged twice. Anything not included is added.
# Only a broker whose own page states what its quote includes is shipped (t-fees.md §4): Stockbit
# and Indo Premier do not say, so a user of theirs sets up `custom`. Check any preset against your
# broker's fee schedule.

[presets.ajaib]
source = "ajaib.co.id/biaya: 'Sudah termasuk biaya broker, biaya levy (BEI, KPEI, KSEI) 0,0433%, PPN Biaya Broker 12% ..., dan PPh final untuk transaksi jual 0,1%'"
checked = 2026-09-25
buy_percent = "0.1513"
sell_percent = "0.2513"
includes = ["levy", "commission_vat", "sale_tax"]

[presets.custom]
source = "steadyhand's default: a 0.15% commission each way, with VAT, the levy and the sale tax added"
buy_percent = "0.15"
sell_percent = "0.15"
includes = []
```

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/fees.py`**

```python
"""IDX trading costs and taxes, from ``data/fees.toml`` (spec §5.1, docs/research/t-fees.md).

Every component is worked out exactly as a percentage of the gross value, the components are
summed, and the total is rounded once to the rupiah, against the trader (spec §4.4). The levy and
tax lines of ``Costs`` are rounded down and the broker line takes the rest, so the three lines
always add up to the rounded total and none of them is negative.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from types import MappingProxyType

from steadyhand import IDR, Costs, Money, Rounding, Side
from steadyhand_idx._datafile import (
    DataFileError,
    Dated,
    Row,
    Where,
    get_date,
    get_decimal,
    get_int,
    get_list,
    get_str,
    load_shipped,
    only_keys,
    require_schema,
    rows,
)

FEES_FILE = "fees.toml"
INCLUDABLE = frozenset({"levy", "commission_vat", "sale_tax"})
_HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class Levy:
    """The exchange-side charges per side, in percent of the gross value."""

    exchange: Decimal
    clearing: Decimal
    settlement: Decimal
    guarantee_fund: Decimal

    def with_vat(self, vat: Decimal) -> Decimal:
        """The levy in percent, VAT included on every part except the guarantee fund."""
        taxed = self.exchange + self.clearing + self.settlement
        return taxed + taxed * vat / _HUNDRED + self.guarantee_fund


@dataclass(frozen=True, slots=True)
class StampDuty:
    """``amount`` rupiah on a day's trade confirmation worth more than ``exempt_up_to``."""

    amount: int
    exempt_up_to: int


@dataclass(frozen=True, slots=True)
class BrokerPreset:
    """A broker's quoted rate per side, in percent, and what that quote already contains."""

    name: str
    source: str
    buy: Decimal
    sell: Decimal
    includes: frozenset[str]


@dataclass(frozen=True, slots=True)
class Percentages:
    """One trade's costs in percent of its gross value, before any rounding."""

    fee: Decimal
    levy: Decimal
    tax: Decimal


@dataclass(frozen=True, slots=True)
class FeeSchedule:
    """The dated cost tables and the broker presets from one ``fees.toml``."""

    levy: Dated[Levy]
    vat: Dated[Decimal]
    sale_tax: Dated[Decimal]
    stamp_duty: Dated[StampDuty]
    dividend_tax_rate: Dated[Decimal]
    presets: Mapping[str, BrokerPreset]

    def __post_init__(self) -> None:
        for preset in self.presets.values():
            self._check_quote_covers_what_it_includes(preset)

    @classmethod
    def shipped(cls) -> FeeSchedule:
        """The schedule from the package's own ``data/fees.toml``."""
        return _shipped_schedule()

    @property
    def tables(self) -> tuple[Dated[object], ...]:
        """Every dated table, for working out the first day all of them are verified."""
        return (self.levy, self.vat, self.sale_tax, self.stamp_duty, self.dividend_tax_rate)

    def preset(self, name: str) -> BrokerPreset:
        found = self.presets.get(name)
        if found is None:
            known = ", ".join(sorted(self.presets))
            msg = f"no broker fee preset named {name!r}; {FEES_FILE} has {known}"
            raise ValueError(msg)
        return found

    def percentages(self, preset: BrokerPreset, side: Side, on: date) -> Percentages:
        """The fee, levy and tax on one trade, in percent of its gross value."""
        vat = self.vat.on(on)
        levy = self.levy.on(on).with_vat(vat)
        tax = self.sale_tax.on(on) if side is Side.SELL else Decimal(0)
        quoted = preset.buy if side is Side.BUY else preset.sell
        commission = quoted
        if "levy" in preset.includes:
            commission -= levy
        if "sale_tax" in preset.includes:
            commission -= tax
        if "commission_vat" not in preset.includes:
            commission += commission * vat / _HUNDRED
        return Percentages(commission, levy, tax)

    def trade_costs(self, preset: BrokerPreset, side: Side, gross: Money, on: date) -> Costs:
        """The costs of one trade worth *gross*, rounded once, against the trader."""
        if gross.currency != IDR or gross.amount < 0:
            msg = f"gross must be a non-negative IDR amount, got {gross}"
            raise ValueError(msg)
        rates = self.percentages(preset, side, on)
        total = gross.times((rates.fee + rates.levy + rates.tax) / _HUNDRED, Rounding.UP)
        levy = gross.times(rates.levy / _HUNDRED, Rounding.DOWN)
        tax = gross.times(rates.tax / _HUNDRED, Rounding.DOWN)
        return Costs(fee=total - levy - tax, levy=levy, tax=tax)

    def daily_costs(self, traded: Money, on: date) -> Money:
        """Stamp duty on the day's trade confirmation, given the day's buys plus sells."""
        if traded.currency != IDR or traded.amount < 0:
            msg = f"traded must be a non-negative IDR amount, got {traded}"
            raise ValueError(msg)
        duty = self.stamp_duty.on(on)
        if traded.amount <= duty.exempt_up_to:
            return Money.zero(IDR)
        return Money(duty.amount, IDR)

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """10% of a gross dividend, or nothing when it is reinvested by the deadline.

        M4 replaces the flag with a read of the dividend's exemption claim (spec §6.2).
        """
        rate = self.dividend_tax_rate.on(on)
        if reinvested_by_deadline:
            return Money.zero(gross.currency)
        return gross.times(rate / _HUNDRED, Rounding.UP)

    def _check_quote_covers_what_it_includes(self, preset: BrokerPreset) -> None:
        """An all-in quote smaller than the levy and tax it claims to contain is a data error."""
        tables = (self.levy, self.vat, self.sale_tax)
        first = max(table.first for table in tables)
        changes = {start for table in tables for start in table.starts if start >= first}
        for day in sorted({first, *changes}):
            for side in Side:
                if self.percentages(preset, side, day).fee < 0:
                    msg = (
                        f"{FEES_FILE} preset {preset.name!r}: its {side.value} quote is smaller "
                        f"than the costs it says it includes on {day.isoformat()}"
                    )
                    raise DataFileError(msg)


def _dated[T](
    document: Row, table: str, keys: set[str], parse: Callable[[Row, Where], T], file: str
) -> Dated[T]:
    """Read an array of dated rows, each with ``from``, ``source`` and the table's own *keys*."""
    where = Where(file, table)
    starts: list[date] = []
    values: list[T] = []
    for index, row in enumerate(rows(document, table, where), start=1):
        place = where.at(index)
        only_keys(row, {"from", "source", *keys}, place)
        get_str(row, "source", place)
        starts.append(get_date(row, "from", place))
        values.append(parse(row, place))
    return Dated(where, tuple(starts), tuple(values))


def _levy(row: Row, where: Where) -> Levy:
    return Levy(
        exchange=get_decimal(row, "exchange_percent", where),
        clearing=get_decimal(row, "clearing_percent", where),
        settlement=get_decimal(row, "settlement_percent", where),
        guarantee_fund=get_decimal(row, "guarantee_fund_percent", where),
    )


def _rate(row: Row, where: Where) -> Decimal:
    return get_decimal(row, "rate_percent", where)


def _stamp_duty(row: Row, where: Where) -> StampDuty:
    return StampDuty(
        amount=get_int(row, "amount_rupiah", where, minimum=1),
        exempt_up_to=get_int(row, "exempt_up_to_rupiah", where, minimum=0),
    )


def _preset(name: str, row: object, file: str) -> BrokerPreset:
    where = Where(file, f"presets.{name}")
    if not isinstance(row, dict):
        msg = f"{where} must be a table"
        raise DataFileError(msg)
    only_keys(row, {"source", "checked", "buy_percent", "sell_percent", "includes"}, where)
    if "checked" in row:
        get_date(row, "checked", where)
    includes: set[str] = set()
    for item in get_list(row, "includes", where):
        if item not in INCLUDABLE or item in includes:
            allowed = ", ".join(sorted(INCLUDABLE))
            msg = f"{where}: includes may list each of {allowed} once, got {item!r}"
            raise DataFileError(msg)
        includes.add(str(item))
    return BrokerPreset(
        name=name,
        source=get_str(row, "source", where),
        buy=get_decimal(row, "buy_percent", where),
        sell=get_decimal(row, "sell_percent", where),
        includes=frozenset(includes),
    )


def parse_fees(document: Row, file: str = FEES_FILE) -> FeeSchedule:
    require_schema(document, file, 1)
    tables = {"levy", "vat", "sale_tax", "stamp_duty", "dividend_tax", "presets"}
    only_keys(document, {"schema", *tables}, Where(file, "top level"))
    presets = document.get("presets")
    if not isinstance(presets, dict) or not presets:
        msg = f"{file} [presets] must be a table with at least one preset"
        raise DataFileError(msg)
    levy_keys = {"exchange_percent", "clearing_percent", "settlement_percent"}
    return FeeSchedule(
        levy=_dated(document, "levy", {*levy_keys, "guarantee_fund_percent"}, _levy, file),
        vat=_dated(document, "vat", {"rate_percent"}, _rate, file),
        sale_tax=_dated(document, "sale_tax", {"rate_percent"}, _rate, file),
        stamp_duty=_dated(
            document, "stamp_duty", {"amount_rupiah", "exempt_up_to_rupiah"}, _stamp_duty, file
        ),
        dividend_tax_rate=_dated(document, "dividend_tax", {"rate_percent"}, _rate, file),
        presets=MappingProxyType({name: _preset(name, row, file) for name, row in presets.items()}),
    )


@cache
def _shipped_schedule() -> FeeSchedule:
    return parse_fees(load_shipped(FEES_FILE))
```

<!-- file@3: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py` (after this story)**

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.fees import BrokerPreset, FeeSchedule

__version__: str = version("steadyhand-idx")

__all__ = [
    "BrokerPreset",
    "DataFileError",
    "FeeSchedule",
    "IdxCalendar",
    "__version__",
]
```

In `.github/workflows/ci.yml`, the `build` job gains this step after "Both packages built a wheel and an sdist":

<!-- excerpt: .github/workflows/ci.yml -->
```yaml
      - name: The IDX wheel carries its rule data
        run: |
          unzip -l dist/steadyhand_idx-*.whl > "${RUNNER_TEMP}/idx-wheel.txt"
          for table in tick_sizes auto_reject fees holidays; do
            grep -q "steadyhand_idx/data/${table}.toml" "${RUNNER_TEMP}/idx-wheel.txt"
          done
```

- [ ] **Step 6: Run the whole gate, and build.**

Run: `uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy && uv run --locked pytest -W error --cov -q && uv build --all-packages --out-dir dist`
Expected: every check passes; `418 passed`; 100% coverage. `unzip -l dist/steadyhand_idx-*.whl` lists the four `data/*.toml` files, and not `data/sessions.toml` (the negative control).

- [ ] **Step 7: Mutations M4, M5 and M6.**

- [ ] **Step 8: Commit, push and merge.**

```bash
git add packages/steadyhand-idx tests/idx .github/workflows/ci.yml
git commit -m "feat(idx): levy, VAT, sale tax, stamp duty, dividend tax and broker presets (#<S3>)"
```

---

### Task 4: S4 IdxMarketRules and the final MarketRules protocol

**Acceptance criteria (story text):**
1. `MarketRules` gains `verified_from`, `require_supported(day)` and `daily_costs(traded, on)`. A class missing any one of them is not `MarketRules` (one test per member).
2. `IdxMarketRules()` is `MarketRules`, reads the shipped files, and takes `broker_fees` (default `custom`).
3. `verified_from` is 2021-01-01, and `require_supported(2020-12-31)` names `fees.toml [stamp_duty]`. Moving stamp duty's first row earlier moves `verified_from` to the next-latest table (13 Mar 2020, named `tick_sizes.toml [ticks]`), which proves the date is derived.
4. Every rule method refuses a day before `verified_from`, and a day in 2028.
5. `price_band` gives the widest tick-valid prices inside the band and not below the minimum price, pinned on eight worked cases and by a hypothesis property.
6. `settlement_date` is two trading days later across a weekend, Eid 2026 and the year end, and refuses a non-trading day.
7. Other markets and currencies are refused, naming them.
8. Every quality gate is green at 100% branch coverage, and the red phase is recorded in the PR.

**Files:**
- Modify: `packages/steadyhand/src/steadyhand/market.py`, `tests/engine/test_protocols.py`, `.../steadyhand_idx/__init__.py`
- Create: `.../steadyhand_idx/rules.py`
- Test: `tests/idx/test_rules.py`

**Interfaces:**
- Consumes: `IdxCalendar` (Task 1), `parse_ticks`, `parse_settlement`, `parse_bands` (Task 2), `FeeSchedule` (Task 3).
- Produces: `MarketRules.verified_from: date`, `.require_supported(day) -> None`, `.daily_costs(traded: Money, on: date) -> Money`. In `steadyhand_idx.rules`: `MARKET`; `RuleTables(calendar, ticks, settlement, bands, fees)` with `.shipped()` and `.first_dates() -> list[tuple[date, str]]`; `IdxMarketRules(tables=None, *, broker_fees="custom")`, implementing every `MarketRules` member.

- [ ] **Step 1: Branch.** `git switch -c m2/s4-rules origin/develop` (after S3 is merged).

- [ ] **Step 2: Write the failing tests.** The protocol test's minimal class gains the three members, and one test proves each is required:

<!-- file: tests/engine/test_protocols.py -->
**`tests/engine/test_protocols.py`**

```python
"""The engine's plug-in points are structural Protocols: anything with the right methods fits.

Each ``_Minimal*`` class is the smallest conforming implementation. Assigning it to a variable
typed as the protocol makes ``mypy --strict`` check every signature; ``isinstance`` checks the
runtime view that plug-in loading will use.
"""

from collections.abc import Sequence
from datetime import date, timedelta

import pytest

from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError
from steadyhand.market import MarketRules
from steadyhand.money import IDR, Currency, Money
from steadyhand.types import Bar, CorporateAction, Costs, Fill, Instrument, Order, OrderAck, Side


class _MinimalRules:
    @property
    def currency(self) -> Currency:
        return IDR

    @property
    def verified_from(self) -> date:
        return date(2021, 1, 1)

    def require_supported(self, day: date) -> None:
        return None

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        return price

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        return (reference, reference)

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        return Costs.zero(gross.currency)

    def daily_costs(self, traded: Money, on: date) -> Money:
        return Money.zero(traded.currency)

    def settlement_date(self, trade_date: date) -> date:
        return trade_date + timedelta(days=2)

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5


class _MinimalSource:
    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return ()

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return ()


class _MinimalBroker:
    def submit(self, orders: Sequence[Order], on: date) -> Sequence[OrderAck]:
        return [OrderAck(order, accepted=True) for order in orders]

    def fills(self, on: date) -> Sequence[Fill]:
        return ()


class _RulesWithoutTax:
    currency = IDR

    def lot_size(self, instrument: Instrument, on: date) -> int:
        return 100


def test_a_minimal_class_satisfies_market_rules() -> None:
    rules: MarketRules = _MinimalRules()
    assert isinstance(rules, MarketRules)


def test_a_class_missing_methods_is_not_market_rules() -> None:
    assert not isinstance(_RulesWithoutTax(), MarketRules)


@pytest.mark.parametrize("member", ["verified_from", "require_supported", "daily_costs"])
def test_each_member_added_in_m2_is_required(member: str) -> None:
    members = {name: value for name, value in vars(_MinimalRules).items() if name != member}
    assert not isinstance(type("Partial", (), members)(), MarketRules)


def test_a_minimal_class_satisfies_data_source() -> None:
    source: DataSource = _MinimalSource()
    assert isinstance(source, DataSource)
    assert not isinstance(_MinimalBroker(), DataSource)


def test_a_minimal_class_satisfies_broker() -> None:
    broker: Broker = _MinimalBroker()
    assert isinstance(broker, Broker)
    assert not isinstance(_MinimalSource(), Broker)


def test_data_unavailable_keeps_the_callers_message() -> None:
    message = "BBRI.JK bars after 3 attempts"
    with pytest.raises(DataUnavailableError, match=r"^BBRI\.JK bars after 3 attempts$"):
        raise DataUnavailableError(message)
```

<!-- file: tests/idx/test_rules.py -->
**`tests/idx/test_rules.py`**

```python
"""IdxMarketRules: the IDX tables behind the engine's MarketRules protocol."""

import copy
import math
from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import (
    IDR,
    Currency,
    Instrument,
    MarketRules,
    Money,
    Side,
    UnsupportedDateError,
)
from steadyhand_idx._datafile import load_shipped
from steadyhand_idx.fees import parse_fees
from steadyhand_idx.rules import IdxMarketRules, RuleTables


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


BBCA = Instrument("BBCA", "IDX", IDR)
TODAY = date(2026, 9, 25)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def test_it_is_the_engines_market_rules() -> None:
    market: MarketRules = rules()
    assert isinstance(market, MarketRules)
    assert market.currency == IDR


def test_the_verified_date_is_2021_set_by_stamp_duty() -> None:
    assert rules().verified_from == date(2021, 1, 1)
    rules().require_supported(date(2021, 1, 1))
    with pytest.raises(
        UnsupportedDateError,
        match=(
            r"^steadyhand's IDX rules are primary-verified from 2021-01-01, the first date of "
            r"fees\.toml \[stamp_duty\]; 2020-12-31 is earlier$"
        ),
    ):
        rules().require_supported(date(2020, 12, 31))


def test_the_verified_date_is_derived_from_the_files() -> None:
    document = copy.deepcopy(load_shipped("fees.toml"))
    stamp_duty = document["stamp_duty"]
    assert isinstance(stamp_duty, list)
    stamp_duty[0]["from"] = date(2019, 1, 1)
    tables = replace(RuleTables.shipped(), fees=parse_fees(document))
    rules = IdxMarketRules(tables)
    # The next-latest first date is 13 Mar 2020, shared by three tables; the first listed names it.
    assert rules.verified_from == date(2020, 3, 13)
    with pytest.raises(UnsupportedDateError, match=r"first date of tick_sizes\.toml \[ticks\];"):
        rules.require_supported(date(2020, 3, 12))


def test_a_year_past_the_holiday_data_is_refused() -> None:
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2028"):
        rules().require_supported(date(2028, 1, 3))


@pytest.mark.parametrize(
    "call",
    [
        lambda: rules().lot_size(BBCA, date(2020, 12, 31)),
        lambda: rules().round_to_tick(BBCA, rp(201), Side.BUY, date(2020, 12, 31)),
        lambda: rules().price_band(BBCA, rp(1000), date(2020, 12, 31)),
        lambda: rules().costs(Side.BUY, rp(1000), date(2020, 12, 31)),
        lambda: rules().daily_costs(rp(1000), date(2020, 12, 31)),
        lambda: rules().settlement_date(date(2020, 12, 30)),
        lambda: rules().dividend_tax(rp(1000), reinvested_by_deadline=False, on=date(2020, 12, 31)),
        lambda: rules().is_trading_day(date(2020, 12, 31)),
    ],
)
def test_every_rule_refuses_an_unverified_day(call: object) -> None:
    assert callable(call)
    with pytest.raises(UnsupportedDateError, match="primary-verified from 2021-01-01"):
        call()


def test_other_markets_and_currencies_are_refused() -> None:
    usd = Currency("USD", 2)
    with pytest.raises(
        ValueError, match=r"^AAPL is a NASDAQ USD instrument; these rules are for IDX"
    ):
        rules().lot_size(Instrument("AAPL", "NASDAQ", usd), TODAY)
    with pytest.raises(ValueError, match=r"^price must be in IDR, got USD 2\.01$"):
        rules().round_to_tick(BBCA, Money(201, usd), Side.BUY, TODAY)
    with pytest.raises(ValueError, match=r"^gross must be in IDR"):
        rules().dividend_tax(Money(1, usd), reinvested_by_deadline=False, on=TODAY)


def test_lots_and_ticks() -> None:
    assert rules().lot_size(BBCA, TODAY) == 100
    assert rules().round_to_tick(BBCA, rp(5_001), Side.BUY, TODAY) == rp(5_025)
    assert rules().round_to_tick(BBCA, rp(5_001), Side.SELL, TODAY) == rp(5_000)


@pytest.mark.parametrize(
    ("on", "reference", "low", "high", "why"),
    [
        (TODAY, 1_000, 850, 1_250, "25% up and 15% down, both on the Rp5 grid"),
        (TODAY, 200, 170, 270, "200 is in the 35% tier for bands"),
        (TODAY, 5_000, 4_250, 6_250, "5,000 is in the 25% tier for bands"),
        (
            TODAY,
            5_025,
            4_280,
            6_025,
            "6,030 is off the Rp25 grid; 4,271.25 rounds up to Rp10's 4,280",
        ),
        (TODAY, 50, 50, 67, "the bottom (42.5) is raised to the Rp50 minimum"),
        (date(2026, 9, 28), 7, 6, 8, "the Rp1-10 tier moves Rp1 either way"),
        (date(2026, 9, 28), 1, 1, 2, "never below the Rp1 minimum"),
        (date(2027, 1, 1), 1_000, 750, 1_250, "symmetric 25% from 2027"),
    ],
)
def test_band_edges_come_from_the_band_and_the_tick_grid_together(
    on: date, reference: int, low: int, high: int, why: str
) -> None:
    assert rules().price_band(BBCA, rp(reference), on) == (rp(low), rp(high)), why


def test_a_reference_below_the_minimum_price_is_refused() -> None:
    with pytest.raises(ValueError, match=r"^reference IDR 40 is below the minimum price, Rp50$"):
        rules().price_band(BBCA, rp(40), TODAY)


@given(
    reference=st.integers(min_value=50, max_value=1_000_000),
    on=st.sampled_from([date(2021, 1, 4), date(2023, 6, 5), date(2023, 9, 4), TODAY]),
)
def test_band_edges_are_the_widest_valid_prices_inside_the_band(reference: int, on: date) -> None:
    low, high = rules().price_band(BBCA, rp(reference), on)
    tables = RuleTables.shipped()
    ticks, band = tables.ticks.on(on), tables.bands.on(on)
    bottom, top = band.limits(reference)
    assert ticks.is_valid(low.amount)
    assert ticks.is_valid(high.amount)
    assert low.amount >= max(bottom, Decimal(band.min_price))
    assert high.amount <= top
    assert not any(ticks.is_valid(p) for p in range(high.amount + 1, math.floor(top) + 1))
    floor_price = max(math.ceil(bottom), band.min_price)
    assert not any(ticks.is_valid(p) for p in range(floor_price, low.amount))


def test_costs_use_the_chosen_broker_preset() -> None:
    ajaib = IdxMarketRules(broker_fees="ajaib")
    assert ajaib.costs(Side.BUY, rp(10_000_000), TODAY).total == rp(15_130)
    assert rules().costs(Side.BUY, rp(10_000_000), TODAY).total == rp(20_980)
    with pytest.raises(ValueError, match="no broker fee preset named 'ipot'"):
        IdxMarketRules(broker_fees="ipot")


def test_daily_costs_are_the_stamp_duty() -> None:
    assert rules().daily_costs(rp(1), date(2021, 1, 4)) == rp(10_000)
    assert rules().daily_costs(rp(10_000_000), date(2022, 1, 12)) == rp(0)


@pytest.mark.parametrize(
    ("trade", "settles"),
    [
        (date(2026, 9, 24), date(2026, 9, 28)),  # Thursday: across the weekend
        (date(2026, 3, 17), date(2026, 3, 26)),  # across Eid al-Fitr's five holidays
        (date(2026, 12, 29), date(2027, 1, 4)),  # across the year-end holidays
        (date(2021, 1, 4), date(2021, 1, 6)),  # the first verified trading day
    ],
)
def test_settlement_is_two_trading_days_later(trade: date, settles: date) -> None:
    assert rules().settlement_date(trade) == settles


def test_nothing_settles_from_a_non_trading_day() -> None:
    with pytest.raises(ValueError, match=r"^2026-09-26 is not an IDX trading day"):
        rules().settlement_date(date(2026, 9, 26))


def test_dividend_tax_and_trading_days() -> None:
    assert rules().dividend_tax(rp(1_000), reinvested_by_deadline=False, on=TODAY) == rp(100)
    assert rules().is_trading_day(date(2021, 1, 4))
    assert not rules().is_trading_day(date(2026, 12, 31))
```

- [ ] **Step 3: Write the stub.** The protocol is not changed yet, so the three new protocol tests fail against M1's `MarketRules`.

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/rules.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/rules.py` (stub)**

```python
"""``IdxMarketRules``: the Indonesia Stock Exchange's ``MarketRules``, read from ``data/*.toml``.

Every value is looked up for the date it applies to (spec §9.1). The rules refuse any day before
``verified_from``, the latest first date of any table in ``tick_sizes.toml``, ``auto_reject.toml``,
``fees.toml`` and ``holidays.toml``, and the refusal names the table that sets it. The date is
derived from the files and never written into code.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import date
from steadyhand import IDR, Costs, Currency, Instrument, Money, Side, UnsupportedDateError
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.bands import BANDS_FILE, BandRow, parse_bands
from steadyhand_idx.calendar import HOLIDAYS_FILE, IdxCalendar
from steadyhand_idx.fees import FeeSchedule
from steadyhand_idx.ticks import TICKS_FILE, TickRow, parse_settlement, parse_ticks

MARKET = "IDX"


@dataclass(frozen=True, slots=True)
class RuleTables:
    """Every dated table the IDX rules read. ``shipped()`` loads the package's own files."""

    calendar: IdxCalendar
    ticks: Dated[TickRow]
    settlement: Dated[int]
    bands: Dated[BandRow]
    fees: FeeSchedule

    @classmethod
    def shipped(cls) -> RuleTables:
        raise NotImplementedError("RuleTables.shipped")

    def first_dates(self) -> list[tuple[date, str]]:
        """Each table's first day, with the table's name, calendar first."""
        raise NotImplementedError("RuleTables.first_dates")


class IdxMarketRules:
    """IDX rules for one broker fee preset (``custom`` by default; spec §9.5 ``broker_fees``)."""

    def __init__(self, tables: RuleTables | None = None, *, broker_fees: str = "custom") -> None:
        raise NotImplementedError("IdxMarketRules.__init__")

    @property
    def currency(self) -> Currency:
        raise NotImplementedError("IdxMarketRules.currency")

    @property
    def verified_from(self) -> date:
        raise NotImplementedError("IdxMarketRules.verified_from")

    def require_supported(self, day: date) -> None:
        raise NotImplementedError("IdxMarketRules.require_supported")

    def lot_size(self, instrument: Instrument, on: date) -> int:
        raise NotImplementedError("IdxMarketRules.lot_size")

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        raise NotImplementedError("IdxMarketRules.round_to_tick")

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        """The lowest and highest prices the exchange accepts around *reference*.

        II-A gives the band as a percentage (or, for the lowest prices, rupiah) and states no
        rounding. A price must also sit on the tick grid, so the highest accepted price is the
        highest valid price at or below the band's top, and the lowest is the lowest valid price
        at or above its bottom and the minimum price (docs/research/t-rules.md §3).
        """
        raise NotImplementedError("IdxMarketRules.price_band")

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        raise NotImplementedError("IdxMarketRules.costs")

    def daily_costs(self, traded: Money, on: date) -> Money:
        raise NotImplementedError("IdxMarketRules.daily_costs")

    def settlement_date(self, trade_date: date) -> date:
        """The trading day, ``settlement`` trading days after *trade_date*, when a trade settles."""
        raise NotImplementedError("IdxMarketRules.settlement_date")

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        raise NotImplementedError("IdxMarketRules.dividend_tax")

    def is_trading_day(self, day: date) -> bool:
        raise NotImplementedError("IdxMarketRules.is_trading_day")

    def _check(self, instrument: Instrument, on: date) -> None:
        raise NotImplementedError("IdxMarketRules._check")

    @staticmethod
    def _check_money(amount: Money, what: str) -> None:
        raise NotImplementedError("IdxMarketRules._check_money")
```

- [ ] **Step 4: Run the tests and watch them fail.**

Run: `uv run --locked pytest -W error -q tests/idx/test_rules.py tests/engine/test_protocols.py`
Expected: `35 failed, 5 passed`. The 32 rules tests fail on `NotImplementedError`. The three `test_each_member_added_in_m2_is_required` cases fail because M1's protocol lacks the member. The five that pass are M1's existing protocol tests.

- [ ] **Step 5: Write the implementation and export the new names.**

<!-- file: packages/steadyhand/src/steadyhand/market.py -->
**`packages/steadyhand/src/steadyhand/market.py`**

```python
"""The MarketRules protocol: everything that differs between stock exchanges."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.money import Currency, Money
from steadyhand.types import Costs, Instrument, Side


class UnsupportedDateError(LookupError):
    """A market's rule data does not cover a date.

    Raised instead of guessing: a year with no holiday data, or a day before a rule table's
    first verified row, must stop the run. It is never read as "no holidays" or "today's rules".
    """


@runtime_checkable
class MarketRules(Protocol):
    """One market's trading rules. Every rule is looked up for a date, because rules change.

    An implementation reads its values from dated data (spec §9.1), never from constants, so a
    backtest over past dates uses the rules that applied on those dates.
    """

    @property
    def currency(self) -> Currency:
        """The currency every price and cost in this market is quoted in."""
        ...

    @property
    def verified_from(self) -> date:
        """The first day on which every rule is verified. A backtest may not start earlier."""
        ...

    def require_supported(self, day: date) -> None:
        """Raise ``UnsupportedDateError`` for a day the rule data does not cover.

        The message names the rule table that sets the limit. Every other method checks this.
        """
        ...

    def lot_size(self, instrument: Instrument, on: date) -> int:
        """Shares per board lot. Orders are whole lots."""
        ...

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        """The nearest valid price against the trader: up for a BUY, down for a SELL."""
        ...

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        """The (lowest, highest) price the exchange accepts, given the reference price."""
        ...

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        """Fee, levy and tax for one trade of *gross* value. Never negative."""
        ...

    def daily_costs(self, traded: Money, on: date) -> Money:
        """Charges made once per trading day, given the day's buys plus sells.

        Stamp duty on a trade confirmation is the example: brokers issue one confirmation a day,
        so it cannot be charged per trade. Never negative, and nothing when nothing traded.
        """
        ...

    def settlement_date(self, trade_date: date) -> date:
        """The trading day on which a trade made on *trade_date* settles."""
        ...

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """The tax due on a *gross* dividend paid on *on*.

        IDX issuers withhold nothing from resident individuals; see docs/research/t-tax.md.
        """
        ...

    def is_trading_day(self, day: date) -> bool:
        """Whether the market is open on *day*. Raises for a year with no holiday data."""
        ...
```

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/rules.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/rules.py`**

```python
"""``IdxMarketRules``: the Indonesia Stock Exchange's ``MarketRules``, read from ``data/*.toml``.

Every value is looked up for the date it applies to (spec §9.1). The rules refuse any day before
``verified_from``, the latest first date of any table in ``tick_sizes.toml``, ``auto_reject.toml``,
``fees.toml`` and ``holidays.toml``, and the refusal names the table that sets it. The date is
derived from the files and never written into code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from steadyhand import (
    IDR,
    Costs,
    Currency,
    Instrument,
    Money,
    Side,
    UnsupportedDateError,
)
from steadyhand_idx._datafile import Dated, load_shipped
from steadyhand_idx.bands import BANDS_FILE, BandRow, parse_bands
from steadyhand_idx.calendar import HOLIDAYS_FILE, IdxCalendar
from steadyhand_idx.fees import FeeSchedule
from steadyhand_idx.ticks import TICKS_FILE, TickRow, parse_settlement, parse_ticks

MARKET = "IDX"


@dataclass(frozen=True, slots=True)
class RuleTables:
    """Every dated table the IDX rules read. ``shipped()`` loads the package's own files."""

    calendar: IdxCalendar
    ticks: Dated[TickRow]
    settlement: Dated[int]
    bands: Dated[BandRow]
    fees: FeeSchedule

    @classmethod
    def shipped(cls) -> RuleTables:
        tick_document = load_shipped(TICKS_FILE)
        return cls(
            calendar=IdxCalendar.shipped(),
            ticks=parse_ticks(tick_document),
            settlement=parse_settlement(tick_document),
            bands=parse_bands(load_shipped(BANDS_FILE)),
            fees=FeeSchedule.shipped(),
        )

    def first_dates(self) -> list[tuple[date, str]]:
        """Each table's first day, with the table's name, calendar first."""
        dated: list[Dated[object]] = [self.ticks, self.settlement, self.bands, *self.fees.tables]
        return [
            (self.calendar.first_day, f"{HOLIDAYS_FILE} [year]"),
            *((table.first, str(table.where)) for table in dated),
        ]


class IdxMarketRules:
    """IDX rules for one broker fee preset (``custom`` by default; spec §9.5 ``broker_fees``)."""

    def __init__(self, tables: RuleTables | None = None, *, broker_fees: str = "custom") -> None:
        self._tables = RuleTables.shipped() if tables is None else tables
        self._preset = self._tables.fees.preset(broker_fees)
        self._verified_from, self._set_by = max(self._tables.first_dates(), key=lambda p: p[0])

    @property
    def currency(self) -> Currency:
        return IDR

    @property
    def verified_from(self) -> date:
        return self._verified_from

    def require_supported(self, day: date) -> None:
        if day < self._verified_from:
            msg = (
                f"steadyhand's IDX rules are primary-verified from "
                f"{self._verified_from.isoformat()}, the first date of {self._set_by}; "
                f"{day.isoformat()} is earlier"
            )
            raise UnsupportedDateError(msg)
        self._tables.calendar.require_covered(day)

    def lot_size(self, instrument: Instrument, on: date) -> int:
        self._check(instrument, on)
        return self._tables.ticks.on(on).lot_size

    def round_to_tick(self, instrument: Instrument, price: Money, side: Side, on: date) -> Money:
        self._check(instrument, on)
        self._check_money(price, "price")
        row = self._tables.ticks.on(on)
        rounded = row.round_up(price.amount) if side is Side.BUY else row.round_down(price.amount)
        return Money(rounded, IDR)

    def price_band(self, instrument: Instrument, reference: Money, on: date) -> tuple[Money, Money]:
        """The lowest and highest prices the exchange accepts around *reference*.

        II-A gives the band as a percentage (or, for the lowest prices, rupiah) and states no
        rounding. A price must also sit on the tick grid, so the highest accepted price is the
        highest valid price at or below the band's top, and the lowest is the lowest valid price
        at or above its bottom and the minimum price (docs/research/t-rules.md §3).
        """
        self._check(instrument, on)
        self._check_money(reference, "reference")
        band = self._tables.bands.on(on)
        if reference.amount < band.min_price:
            msg = f"reference {reference} is below the minimum price, Rp{band.min_price}"
            raise ValueError(msg)
        ticks = self._tables.ticks.on(on)
        bottom, top = band.limits(reference.amount)
        low = ticks.round_up(max(math.ceil(bottom), band.min_price))
        high = ticks.round_down(math.floor(top))
        return Money(low, IDR), Money(high, IDR)

    def costs(self, side: Side, gross: Money, on: date) -> Costs:
        self.require_supported(on)
        return self._tables.fees.trade_costs(self._preset, side, gross, on)

    def daily_costs(self, traded: Money, on: date) -> Money:
        self.require_supported(on)
        return self._tables.fees.daily_costs(traded, on)

    def settlement_date(self, trade_date: date) -> date:
        """The trading day, ``settlement`` trading days after *trade_date*, when a trade settles."""
        self.require_supported(trade_date)
        if not self._tables.calendar.is_trading_day(trade_date):
            msg = f"{trade_date.isoformat()} is not an IDX trading day, so nothing trades on it"
            raise ValueError(msg)
        lag = self._tables.settlement.on(trade_date)
        return self._tables.calendar.add_trading_days(trade_date, lag)

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        self.require_supported(on)
        self._check_money(gross, "gross")
        return self._tables.fees.dividend_tax(
            gross, reinvested_by_deadline=reinvested_by_deadline, on=on
        )

    def is_trading_day(self, day: date) -> bool:
        self.require_supported(day)
        return self._tables.calendar.is_trading_day(day)

    def _check(self, instrument: Instrument, on: date) -> None:
        self.require_supported(on)
        if instrument.market != MARKET or instrument.currency != IDR:
            msg = (
                f"{instrument.symbol} is a {instrument.market} {instrument.currency.code} "
                f"instrument; these rules are for IDX IDR"
            )
            raise ValueError(msg)

    @staticmethod
    def _check_money(amount: Money, what: str) -> None:
        if amount.currency != IDR:
            msg = f"{what} must be in IDR, got {amount}"
            raise ValueError(msg)
```

<!-- file@4: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py` (after this story)**

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.fees import BrokerPreset, FeeSchedule
from steadyhand_idx.rules import IdxMarketRules, RuleTables

__version__: str = version("steadyhand-idx")

__all__ = [
    "BrokerPreset",
    "DataFileError",
    "FeeSchedule",
    "IdxCalendar",
    "IdxMarketRules",
    "RuleTables",
    "__version__",
]
```

- [ ] **Step 6: Run the whole gate.**

Run: `uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy && uv run --locked pytest -W error --cov -q`
Expected: every check passes; `453 passed`; 100% coverage.

- [ ] **Step 7: Mutations M3, M7 and M8.**

- [ ] **Step 8: Commit, push and merge.**

```bash
git add packages tests
git commit -m "feat(idx): IdxMarketRules; MarketRules gains verified_from and daily_costs (#<S4>)"
```

---

### Task 5: S5 Yahoo data source, recorded fixtures and the daily shape check

**Acceptance criteria (story text):**
1. `steadyhand-idx` depends on `yfinance==1.7.0`, pinned exactly, and `pip-audit --strict` over the locked set is clean.
2. `YahooDataSource` is a `DataSource`. It reverses every split Yahoo reports, using the stock's whole split history, so BBCA on 1 Sep 2021 opens at Rp32,750 with a volume of 13,472,500, and its split and dividend come back as `Split(1, 5)` on 2021-10-13 and `CashDividend(25.0)` on 2021-11-17.
3. A day whose reversed prices are not whole rupiah raises `UnrecoverablePricesError` listing every such day: BBRI's 25 trading days from 2021-08-02 to 2021-09-07. From 2021-09-08 BBRI converts normally.
4. There is exactly one bar per trading day. A zero-volume trading day is kept (UNVR 2023-05-24), a flat empty bar on a holiday is dropped, and trading on a holiday is refused.
5. On all three recordings, every recovered price is on the tick grid, and every day's prices lie inside the band around the previous close, except across a split.
6. A failed request is retried with backoff (1 s, then 2 s) and a third failure raises `DataUnavailableError`. Requests after the first pause for a second. `bars` then `corporate_actions` for one range download once.
7. Three real responses are recorded under `tests/fixtures/yahoo/` by `scripts/record_yahoo_fixture.py`, and a live test (marker `live`, deselected by default) checks that Yahoo still gives the same unadjusted result. The daily `yahoo-shape` workflow runs it and opens an issue, once, when it fails.
8. `download_history` is the only code excluded from coverage, and a meta-guard fails on any second exclusion.
9. Every quality gate is green at 100% branch coverage, and the red phase is recorded in the PR.

**Files:**
- Modify: `pyproject.toml`, `packages/steadyhand-idx/pyproject.toml`, `uv.lock`, `.../steadyhand_idx/__init__.py`, `tests/scripts/test_set_dev_version.py`
- Create: `.../steadyhand_idx/yahoo.py`, `scripts/record_yahoo_fixture.py`, `tests/fixtures/yahoo/*.json` (recorded), `.github/workflows/yahoo-shape.yml`
- Test: `tests/idx/test_yahoo.py`, `tests/idx/test_yahoo_live.py`, `tests/scripts/test_record_yahoo_fixture.py`, `tests/meta/test_coverage_exclusions.py`

**Interfaces:**
- Consumes: `IdxCalendar` (Task 1); `IdxMarketRules` (Task 4, in tests); engine `Bar`, `CashDividend`, `Split`, `DataSource`, `DataUnavailableError`, `InvalidBarError`.
- Produces: in `steadyhand_idx.yahoo`: `SUFFIX`, `REQUIRED_COLUMNS`, `YAHOO_TIMEZONE`, `WHOLE_RUPIAH_TOLERANCE`; `UnrecoverablePricesError(DataUnavailableError)` with `.days: tuple[date, ...]`; `YahooRow`; `YahooHistory(ticker, rows, splits)`; `type Downloader = Callable[[str, date, date], YahooHistory]`; `ticker_for(instrument)`; `history_from_frames(ticker, frame, splits)`; `history_to_json(history, *, recorded, source) -> str`; `history_from_json(path) -> YahooHistory`; `unadjust(history, instrument, calendar, start, end) -> tuple[list[Bar], list[CorporateAction]]`; `RequestPolicy(attempts=3, backoff_seconds=1.0, pause_seconds=1.0)`; `YahooDataSource(calendar=None, *, download=None, sleep=time.sleep, policy=RequestPolicy())`; `download_history(ticker, start, end) -> YahooHistory`. In `scripts/record_yahoo_fixture.py`: `fixture_path(symbol, start, end, folder=...)`, `record(symbol, start, end, *, folder=..., download=...) -> Path`, `main(argv) -> int`.

- [ ] **Step 1: Branch and dependencies.**

```bash
git switch -c m2/s5-yahoo origin/develop   # after S4 is merged
uv add --package steadyhand-idx "yfinance==1.7.0"
uv add --dev "pandas-stubs>=3.0.5.260914"
```

`uv add` rewrites the IDX package's dependencies to `["steadyhand", "yfinance==1.7.0"]`. Then give the root `pyproject.toml` the mypy override and the `live` marker. The whole file after this step:

<!-- file: pyproject.toml -->
**`pyproject.toml`**

```toml
[project]
name = "steadyhand-workspace"
version = "0.0.0"
description = "Development workspace for steadyhand and steadyhand-idx. Not published."
requires-python = ">=3.12"
dependencies = ["steadyhand", "steadyhand-idx"]

[tool.uv]
package = false
required-version = "==0.12.18"

[tool.uv.workspace]
members = ["packages/steadyhand", "packages/steadyhand-idx"]

[tool.uv.sources]
steadyhand = { workspace = true }
steadyhand-idx = { workspace = true }

[tool.ruff]
target-version = "py312"
line-length = 100
# Specs and plans hold hand-aligned sketches for reading, not shipped code; READMEs stay checked.
extend-exclude = ["docs/superpowers"]

[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "RUF", "S", "PT", "PL", "ANN",
    "ERA", "T20", "DTZ", "PIE", "RET", "TRY", "FBT", "PTH", "ISC", "Q", "TID", "ARG",
    "BLE", "EM",
]
ignore = [
    "TRY003",  # messages are the contract (spec §10): every error names what went wrong
]

[tool.ruff.lint.isort]
known-first-party = ["steadyhand", "steadyhand_idx", "set_dev_version"]

[tool.ruff.lint.per-file-ignores]
# Tests assert, use literal values, pass bools on purpose, and implement interfaces minimally.
"tests/**" = ["S101", "PLR2004", "FBT003", "ARG002", "PLR0913", "PLR0917"]
"scripts/**" = ["T201"]

[tool.mypy]
strict = true
python_version = "3.12"
files = ["packages", "tests", "scripts"]

[[tool.mypy.overrides]]
# yfinance ships no type information. It is imported in one place, yahoo.download_history, whose
# result is converted at once into steadyhand's own typed values.
module = ["yfinance"]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["scripts"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra", "-m", "not live"]
markers = [
    "live: talks to Yahoo; run by the daily yahoo-shape workflow with -m live, never on a PR",
]
filterwarnings = ["error"]
xfail_strict = true

[tool.coverage.run]
branch = true
source_pkgs = ["steadyhand", "steadyhand_idx"]

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = true
# A Protocol method body is a bare `...` that never runs; it is not untested code.
exclude_also = ['^\s*\.\.\.$']

[dependency-groups]
dev = [
    "hypothesis>=6.168.1",
    "mypy>=2.3.1",
    "pandas-stubs>=3.0.5.260914",
    "pip-audit>=2.10.1",
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
    "pyyaml>=6.0.3",
    "ruff>=0.16.9",
    "types-pyyaml>=6.0.12.20260906",
]
```

- [ ] **Step 2: Write the failing tests.** `test_set_dev_version.py` now fails on the new dependency (M1's carry-forward), so fix that test first, in its `test_rewrites_both_versions_and_pins_the_engine`:

<!-- excerpt: tests/scripts/test_set_dev_version.py -->
```python
    engine, idx = copies
    before = project(idx)["dependencies"]
    assert isinstance(before, list)
    assert "steadyhand" in before
    assert set_dev_version.set_dev_version(7, engine, idx) == "0.1.0.dev7"
    assert project(engine)["version"] == "0.1.0.dev7"
    assert project(idx)["version"] == "0.1.0.dev7"
    # Only the engine entry changes; every other dependency (yfinance) is left as it was.
    pinned = ["steadyhand==0.1.0.dev7" if entry == "steadyhand" else entry for entry in before]
    assert project(idx)["dependencies"] == pinned
```

<!-- file: tests/idx/test_yahoo.py -->
**`tests/idx/test_yahoo.py`**

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
)
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.yahoo import (
    RequestPolicy,
    UnrecoverablePricesError,
    YahooDataSource,
    YahooHistory,
    YahooRow,
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
        history_from_json(BBCA_FILE), BBCA, calendar(), date(2021, 9, 1), date(2021, 11, 30)
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
    bars, _ = unadjust(history_from_json(BBCA_FILE), BBCA, calendar(), start, end)
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
    bars, actions = unadjust(history_from_json(path), instrument, calendar(), start, end)
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
        unadjust(history, BBRI, calendar(), date(2021, 8, 2), date(2021, 9, 30))
    assert isinstance(caught.value, DataUnavailableError)
    assert caught.value.days == calendar().trading_days(date(2021, 8, 2), date(2021, 9, 7))
    bars, _ = unadjust(history, BBRI, calendar(), date(2021, 9, 8), date(2021, 9, 30))
    assert bars[0].close == rp(3_730)


def test_a_zero_volume_trading_day_is_kept() -> None:
    bars, _ = unadjust(
        history_from_json(UNVR_FILE), UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9)
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
    bars, _ = unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))
    assert date(2023, 5, 18) not in {bar.day for bar in bars}


def test_trading_on_a_holiday_is_refused() -> None:
    traded = YahooRow(date(2023, 5, 18), *(Decimal(4450),) * 4, volume=100, dividend=Decimal(0))
    history = _with_row(history_from_json(UNVR_FILE), traded)
    with pytest.raises(
        DataUnavailableError,
        match=r"^UNVR\.JK: Yahoo shows trading on 2023-05-18, which the IDX calendar says",
    ):
        unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))


def test_an_inconsistent_bar_is_refused() -> None:
    history = history_from_json(UNVR_FILE)
    broken = replace(history.rows[0], high=Decimal(1))
    with pytest.raises(
        DataUnavailableError, match=r"^UNVR\.JK: UNVR 2023-05-15: .* do not bracket"
    ):
        unadjust(
            replace(history, rows=(broken,)), UNVR, calendar(), date(2023, 5, 15), date(2023, 5, 15)
        )


@pytest.mark.parametrize(("ratio", "old", "new"), [("5.0", 1, 5), ("0.2", 5, 1), ("1.5", 2, 3)])
def test_split_ratios_become_whole_share_counts(ratio: str, old: int, new: int) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    _, actions = unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))
    assert actions == [Split(UNVR, date(2023, 5, 22), old, new)]


@pytest.mark.parametrize("ratio", ["0.3333", "0", "-2"])
def test_an_unusable_split_ratio_is_refused(ratio: str) -> None:
    history = YahooHistory("X.JK", (), ((date(2023, 5, 22), Decimal(ratio)),))
    with pytest.raises(DataUnavailableError, match=rf"^UNVR: Yahoo's split ratio {ratio} on"):
        unadjust(history, UNVR, calendar(), date(2023, 5, 15), date(2023, 6, 9))


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


def test_the_default_source_uses_the_shipped_calendar() -> None:
    source = YahooDataSource(download=Replay(UNVR_FILE))
    assert len(source.bars(UNVR, date(2023, 5, 15), date(2023, 6, 9))) == 17
```

<!-- file: tests/scripts/test_record_yahoo_fixture.py -->
**`tests/scripts/test_record_yahoo_fixture.py`**

```python
"""The fixture recorder writes exactly what the conversion reads back."""

from datetime import date
from pathlib import Path

import pytest
import record_yahoo_fixture

from steadyhand_idx.yahoo import YahooHistory, history_from_json

RECORDED = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
UNVR = RECORDED / "UNVR.JK_2023-05-15_2023-06-09.json"


def test_the_file_name_carries_the_ticker_and_range(tmp_path: Path) -> None:
    path = record_yahoo_fixture.fixture_path("UNVR", date(2023, 5, 15), date(2023, 6, 9), tmp_path)
    assert path == tmp_path / "UNVR.JK_2023-05-15_2023-06-09.json"


def test_a_recording_reads_back_as_the_history_it_was_given(tmp_path: Path) -> None:
    history = history_from_json(UNVR)
    asked: list[tuple[str, date, date]] = []

    def download(ticker: str, start: date, end: date) -> YahooHistory:
        asked.append((ticker, start, end))
        return history

    before = date.today()  # noqa: DTZ011 - brackets the recorder's own date.today()
    path = record_yahoo_fixture.record(
        "UNVR", date(2023, 5, 15), date(2023, 6, 9), folder=tmp_path / "new", download=download
    )
    after = date.today()  # noqa: DTZ011
    assert asked == [("UNVR.JK", date(2023, 5, 15), date(2023, 6, 9))]
    assert history_from_json(path) == history
    text = path.read_text(encoding="utf-8")
    assert '"source": "yfinance ' in text
    assert any(f'"recorded": "{day.isoformat()}"' in text for day in {before, after})


def test_usage_is_printed_for_the_wrong_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert record_yahoo_fixture.main(["UNVR"]) == 2
    assert "record_yahoo_fixture.py BBCA 2021-09-01 2021-11-30" in capsys.readouterr().out
```

<!-- file: tests/meta/test_coverage_exclusions.py -->
**`tests/meta/test_coverage_exclusions.py`**

```python
"""Coverage may skip exactly one piece of shipped code: the one function that talks to Yahoo.

Spec §10.5 asks for 100% branch coverage. The network call cannot run on a pull request, so it is
excluded and run instead by the daily yahoo-shape workflow. Any second exclusion is a hole in
the 100%, so this guard fails on it. It reads comments on purpose: the pragma is a comment.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRAGMA = "pragma: no cover"


def pragma_lines(root: Path) -> list[str]:
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PRAGMA in line:
                found.append(f"{path.relative_to(root).as_posix()}:{number}: {line.strip()}")
    return found


def test_the_detector_sees_a_pragma(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\ny = 2  # pragma: no cover\n", encoding="utf-8")
    assert pragma_lines(tmp_path) == ["a.py:2: y = 2  # pragma: no cover"]


def test_only_the_yahoo_download_is_excluded() -> None:
    found = pragma_lines(ROOT / "packages")
    assert len(found) == 1, found
    assert found[0].startswith("steadyhand-idx/src/steadyhand_idx/yahoo.py:")
    assert "def download_history(" in found[0]


def test_the_only_other_exclusion_is_a_protocol_body() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    report = pyproject["tool"]["coverage"]["report"]
    assert report["exclude_also"] == [r"^\s*\.\.\.$"]
    assert "exclude_lines" not in report
```

<!-- file: tests/idx/test_yahoo_live.py -->
**`tests/idx/test_yahoo_live.py`**

```python
"""Yahoo still answers the way the recorded fixtures say it did (spec §9.2).

Marked ``live``: it talks to Yahoo, so it never runs on a pull request. The daily yahoo-shape
workflow runs it and opens an issue when it fails. The comparison is on the UNADJUSTED result,
so a split Yahoo applies after the recording does not break it; a changed format, changed
prices or a new unreported adjustment does.
"""

from pathlib import Path

import pytest

from steadyhand import IDR, Instrument
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.yahoo import (
    SUFFIX,
    UnrecoverablePricesError,
    YahooHistory,
    download_history,
    history_from_json,
    unadjust,
)

pytestmark = pytest.mark.live
FIXTURES = sorted((Path(__file__).resolve().parents[1] / "fixtures" / "yahoo").glob("*.json"))


def outcome(history: YahooHistory) -> object:
    first, last = history.rows[0].day, history.rows[-1].day
    instrument = Instrument(history.ticker.removesuffix(SUFFIX), "IDX", IDR)
    try:
        return unadjust(history, instrument, IdxCalendar.shipped(), first, last)
    except UnrecoverablePricesError as error:
        return error.days


def test_there_are_fixtures_to_check() -> None:
    assert len(FIXTURES) >= 3


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda path: path.stem)
def test_yahoo_still_gives_what_was_recorded(fixture: Path) -> None:
    recorded = history_from_json(fixture)
    live = download_history(recorded.ticker, recorded.rows[0].day, recorded.rows[-1].day)
    assert outcome(live) == outcome(recorded)
```

- [ ] **Step 3: Write the stubs.**

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py` (stub)**

```python
"""``YahooDataSource``: unadjusted IDX prices from Yahoo Finance's ``.JK`` tickers (spec §9.2).

Yahoo's "unadjusted" history is not unadjusted (docs/research/t-hist.md §6). Even with
``auto_adjust=False`` every price before a split is divided by the split ratio, and every
dividend with it. Splits are reported, so their adjustment is reversed exactly here, using the
stock's full split history (a split after the requested range still adjusts the prices in it).

Some adjustments are not reported. A rights issue, for one, scales every earlier price by a
factor nobody publishes, so after reversing the reported splits those prices are no longer whole
rupiah. They cannot be recovered, and a day like that raises ``UnrecoverablePricesError`` naming
it (fail closed, spec §9.2). Measured on 2026-09-25 over 25 large IDX stocks for 2021-2025: BBRI
up to 2021-09-07, SMGR up to 2022-12-12, MDKA up to 2022-04-13 and five INCO days in June 2024.

Trading days come from ``holidays.toml``, never from which days have bars. A flat bar with no
volume on a holiday is a Yahoo placeholder and is dropped. A bar with trading on a holiday
contradicts the calendar, and is refused.
"""

from __future__ import annotations
import json
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
)
from steadyhand_idx.calendar import IdxCalendar

if TYPE_CHECKING:
    import pandas as pd
SUFFIX = ".JK"
PRICE_COLUMNS = ("Open", "High", "Low", "Close")
REQUIRED_COLUMNS = (*PRICE_COLUMNS, "Volume", "Dividends")
YAHOO_TIMEZONE = "Asia/Jakarta"
WHOLE_RUPIAH_TOLERANCE = Decimal("0.0001")
_SPLIT_DENOMINATOR_LIMIT = 1000


class UnrecoverablePricesError(DataUnavailableError):
    """Yahoo's prices for these days carry an adjustment it does not report, so the traded
    prices cannot be worked out. ``days`` lists every such day in the requested range."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        raise NotImplementedError("UnrecoverablePricesError.__init__")


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
    raise NotImplementedError("ticker_for")


def _decimal(value: object) -> Decimal:
    """A pandas/numpy number as the Decimal of its shortest float spelling."""
    raise NotImplementedError("_decimal")


def history_from_frames(ticker: str, frame: pd.DataFrame, splits: pd.Series) -> YahooHistory:
    """Convert ``Ticker.history(auto_adjust=False, actions=True)`` and ``Ticker.splits``."""
    raise NotImplementedError("history_from_frames")


def history_to_json(history: YahooHistory, *, recorded: date, source: str) -> str:
    """A recorded response, as committed under ``tests/fixtures/yahoo`` (spec §10.3)."""
    raise NotImplementedError("history_to_json")


def history_from_json(path: Path) -> YahooHistory:
    """Load a recorded response written by ``history_to_json``."""
    raise NotImplementedError("history_from_json")


def _split(instrument: Instrument, day: date, ratio: Decimal) -> Split:
    raise NotImplementedError("_split")


def _whole(value: Decimal) -> int | None:
    raise NotImplementedError("_whole")


def unadjust(
    history: YahooHistory, instrument: Instrument, calendar: IdxCalendar, start: date, end: date
) -> tuple[list[Bar], list[CorporateAction]]:
    """The bars and actions from *start* to *end*, with Yahoo's split adjustments reversed."""
    raise NotImplementedError("unadjust")


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
        policy: RequestPolicy = RequestPolicy(),
    ) -> None:
        raise NotImplementedError("YahooDataSource.__init__")

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        raise NotImplementedError("YahooDataSource.bars")

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        raise NotImplementedError("YahooDataSource.corporate_actions")

    def _unadjusted(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[list[Bar], list[CorporateAction]]:
        raise NotImplementedError("YahooDataSource._unadjusted")

    def _fetch(self, ticker: str, start: date, end: date) -> YahooHistory:
        """One download per range: ``bars`` then ``corporate_actions`` reuse it."""
        raise NotImplementedError("YahooDataSource._fetch")


def download_history(ticker: str, start: date, end: date) -> YahooHistory:
    """Ask Yahoo for one ticker's history (network; run daily by the yahoo-shape workflow).

    This is the only function that talks to Yahoo, and the only code excluded from coverage:
    ``tests/meta/test_coverage_exclusions.py`` holds it to that. Everything it returns goes
    through ``history_from_frames``, which the tests run on real recorded data.
    """
    raise NotImplementedError("download_history")
```

<!-- stub: scripts/record_yahoo_fixture.py -->
**`scripts/record_yahoo_fixture.py` (stub)**

```python
"""Record one real Yahoo response as a test fixture (spec §10.3).

    uv run python scripts/record_yahoo_fixture.py BBCA 2021-09-01 2021-11-30

writes ``tests/fixtures/yahoo/BBCA.JK_2021-09-01_2021-11-30.json``: the rows exactly as Yahoo gave
them, plus the stock's split history. Tests replay it through the same conversion as live data.
Nothing is edited by hand, and a re-recording is reviewed like any other change.
"""

from __future__ import annotations
import sys
from datetime import date
from importlib.metadata import version
from pathlib import Path
from steadyhand_idx.yahoo import SUFFIX, Downloader, download_history, history_to_json

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "yahoo"


def fixture_path(symbol: str, start: date, end: date, folder: Path = FIXTURES) -> Path:
    raise NotImplementedError("fixture_path")


def record(
    symbol: str,
    start: date,
    end: date,
    *,
    folder: Path = FIXTURES,
    download: Downloader = download_history,
) -> Path:
    raise NotImplementedError("record")


def main(argv: list[str]) -> int:
    raise NotImplementedError("main")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests and watch them fail.** The fixtures do not exist yet, and the stub cannot record them, so the Yahoo tests fail at their first use of a fixture or a stub.

Run: `uv run --locked pytest -W error -q tests/idx/test_yahoo.py tests/scripts/test_record_yahoo_fixture.py tests/meta/test_coverage_exclusions.py`
Expected: `30 failed, 2 passed`. The two passes are expected and are not findings: `test_the_detector_sees_a_pragma` tests the guard's own detector on a scratch file, and `test_the_only_other_exclusion_is_a_protocol_body` pins M1's coverage configuration. Neither reads `yahoo.py`. `test_only_the_yahoo_download_is_excluded` fails because the stub carries no pragma, which is the defect that guard exists to catch.

- [ ] **Step 5: Write the implementation, record the fixtures, and add the workflow.**

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`**

```python
"""``YahooDataSource``: unadjusted IDX prices from Yahoo Finance's ``.JK`` tickers (spec §9.2).

Yahoo's "unadjusted" history is not unadjusted (docs/research/t-hist.md §6). Even with
``auto_adjust=False`` every price before a split is divided by the split ratio, and every
dividend with it. Splits are reported, so their adjustment is reversed exactly here, using the
stock's full split history (a split after the requested range still adjusts the prices in it).

Some adjustments are not reported. A rights issue, for one, scales every earlier price by a
factor nobody publishes, so after reversing the reported splits those prices are no longer whole
rupiah. They cannot be recovered, and a day like that raises ``UnrecoverablePricesError`` naming
it (fail closed, spec §9.2). Measured on 2026-09-25 over 25 large IDX stocks for 2021-2025: BBRI
up to 2021-09-07, SMGR up to 2022-12-12, MDKA up to 2022-04-13 and five INCO days in June 2024.

Trading days come from ``holidays.toml``, never from which days have bars. A flat bar with no
volume on a holiday is a Yahoo placeholder and is dropped. A bar with trading on a holiday
contradicts the calendar, and is refused.
"""

from __future__ import annotations

import json
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
)
from steadyhand_idx.calendar import IdxCalendar

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


class UnrecoverablePricesError(DataUnavailableError):
    """Yahoo's prices for these days carry an adjustment it does not report, so the traded
    prices cannot be worked out. ``days`` lists every such day in the requested range."""

    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        self.days = tuple(days)
        super().__init__(
            f"{ticker}: Yahoo's prices for {len(self.days)} day(s) from "
            f"{self.days[0].isoformat()} to {self.days[-1].isoformat()} carry an adjustment it "
            "does not report as a split (for example a rights issue), so the prices traded on "
            "those days cannot be recovered"
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
            day=cast("pd.Timestamp", stamp).date(),
            open=_decimal(record["Open"]),
            high=_decimal(record["High"]),
            low=_decimal(record["Low"]),
            close=_decimal(record["Close"]),
            volume=int(record["Volume"]),
            dividend=_decimal(record["Dividends"]),
        )
        for stamp, record in frame.iterrows()
    )
    split_rows = tuple(
        (cast("pd.Timestamp", stamp).date(), _decimal(ratio)) for stamp, ratio in splits.items()
    )
    return YahooHistory(ticker, rows, split_rows)


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


def unadjust(
    history: YahooHistory, instrument: Instrument, calendar: IdxCalendar, start: date, end: date
) -> tuple[list[Bar], list[CorporateAction]]:
    """The bars and actions from *start* to *end*, with Yahoo's split adjustments reversed."""
    splits = [(day, ratio) for day, ratio in history.splits]
    bars: list[Bar] = []
    actions: list[CorporateAction] = [
        _split(instrument, day, ratio) for day, ratio in splits if start <= day <= end
    ]
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
        factor = Decimal(1)
        for day, ratio in splits:
            if day > row.day:
                factor *= ratio
        prices = [_whole(value * factor) for value in (row.open, row.high, row.low, row.close)]
        volume = _whole(row.volume / factor)
        if None in prices or volume is None:
            unrecoverable.append(row.day)
            continue
        opening, high, low, closing = (Money(cast("int", price), IDR) for price in prices)
        try:
            bars.append(Bar(instrument, row.day, opening, high, low, closing, volume))
        except InvalidBarError as error:
            msg = f"{history.ticker}: {error}"
            raise DataUnavailableError(msg) from error
        if row.dividend > 0:
            actions.append(CashDividend(instrument, row.day, row.dividend * factor))
    if unrecoverable:
        raise UnrecoverablePricesError(history.ticker, unrecoverable)
    actions.sort(key=lambda action: action.ex_date)
    return bars, actions


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
    ) -> None:
        self._calendar = IdxCalendar.shipped() if calendar is None else calendar
        self._download = download_history if download is None else download
        self._sleep = sleep
        self._policy = policy
        self._requests = 0
        self._last: tuple[tuple[str, date, date], YahooHistory] | None = None

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        return self._unadjusted(instrument, start, end)[0]

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        return self._unadjusted(instrument, start, end)[1]

    def _unadjusted(
        self, instrument: Instrument, start: date, end: date
    ) -> tuple[list[Bar], list[CorporateAction]]:
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        ticker = ticker_for(instrument)
        return unadjust(self._fetch(ticker, start, end), instrument, self._calendar, start, end)

    def _fetch(self, ticker: str, start: date, end: date) -> YahooHistory:
        """One download per range: ``bars`` then ``corporate_actions`` reuse it."""
        key = (ticker, start, end)
        if self._last is not None and self._last[0] == key:
            return self._last[1]
        failure: DataUnavailableError | None = None
        for attempt in range(self._policy.attempts):
            if attempt:
                self._sleep(self._policy.backoff_seconds * 2 ** (attempt - 1))
            elif self._requests:
                self._sleep(self._policy.pause_seconds)
            self._requests += 1
            try:
                history = self._download(ticker, start, end)
            except DataUnavailableError as error:
                failure = error
                continue
            self._last = (key, history)
            return history
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

<!-- file: scripts/record_yahoo_fixture.py -->
**`scripts/record_yahoo_fixture.py`**

```python
"""Record one real Yahoo response as a test fixture (spec §10.3).

    uv run python scripts/record_yahoo_fixture.py BBCA 2021-09-01 2021-11-30

writes ``tests/fixtures/yahoo/BBCA.JK_2021-09-01_2021-11-30.json``: the rows exactly as Yahoo gave
them, plus the stock's split history. Tests replay it through the same conversion as live data.
Nothing is edited by hand, and a re-recording is reviewed like any other change.
"""

from __future__ import annotations

import sys
from datetime import date
from importlib.metadata import version
from pathlib import Path

from steadyhand_idx.yahoo import SUFFIX, Downloader, download_history, history_to_json

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "yahoo"


def fixture_path(symbol: str, start: date, end: date, folder: Path = FIXTURES) -> Path:
    return folder / f"{symbol}{SUFFIX}_{start.isoformat()}_{end.isoformat()}.json"


def record(
    symbol: str,
    start: date,
    end: date,
    *,
    folder: Path = FIXTURES,
    download: Downloader = download_history,
) -> Path:
    history = download(symbol + SUFFIX, start, end)
    source = (
        f"yfinance {version('yfinance')}: Ticker.history(auto_adjust=False, actions=True) "
        "and Ticker.splits"
    )
    path = fixture_path(symbol, start, end, folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    recorded = date.today()  # noqa: DTZ011 - the day of recording, a label for the reader
    path.write_text(history_to_json(history, recorded=recorded, source=source), encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    if len(argv) != 3:  # noqa: PLR2004 - symbol, start, end
        print(__doc__)
        return 2
    symbol, start, end = argv
    print(record(symbol, date.fromisoformat(start), date.fromisoformat(end)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Record the three ranges, each chosen for one measured behaviour: BBCA's 5-for-1 split of 13 Oct 2021 and a dividend, BBRI's unreported rights-issue adjustment, and UNVR's zero-volume day among holidays.

```bash
uv run --locked python scripts/record_yahoo_fixture.py BBCA 2021-09-01 2021-11-30
uv run --locked python scripts/record_yahoo_fixture.py BBRI 2021-08-02 2021-09-30
uv run --locked python scripts/record_yahoo_fixture.py UNVR 2023-05-15 2023-06-09
```

Commit the three JSON files as recorded; never edit one by hand. Yahoo's adjusted values in them may differ from a later recording if a stock splits again, which is why every test asserts on the **unadjusted** result.

<!-- file: .github/workflows/yahoo-shape.yml -->
**`.github/workflows/yahoo-shape.yml`**

```yaml
name: yahoo-shape

# Spec §9.2: once a day, ask Yahoo for the recorded fixture ranges and check that the answer still
# converts to the same unadjusted prices. A changed format, changed prices or a new unreported
# adjustment opens an issue, so it is noticed before it breaks a user's run. It is not a PR gate:
# Yahoo being down must not block a merge.

on:
  schedule:
    - cron: "30 1 * * *" # 08:30 WIB, before the market opens
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: yahoo-shape
  cancel-in-progress: false

env:
  UV_VERSION: "0.12.18"

jobs:
  shape:
    name: shape
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked
      - name: Yahoo still gives what the fixtures recorded
        run: uv run --locked pytest -W error -m live -p no:cacheprovider tests/idx/test_yahoo_live.py
      - name: Open an issue, unless one is already open
        if: failure()
        env:
          GH_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: |
          title="Yahoo response check failed"
          open=$(gh issue list --repo "$GITHUB_REPOSITORY" --state open --search "\"$title\" in:title" --json number --jq length)
          if [ "$open" = "0" ]; then
            gh issue create --repo "$GITHUB_REPOSITORY" --title "$title" --body "The daily yahoo-shape run failed: $RUN_URL. Yahoo's answer for a recorded fixture range no longer converts to the recorded unadjusted prices. Read the failing test's diff before trusting new data (spec §9.2)."
          else
            echo "An issue is already open; not opening another."
          fi
```

<!-- file@5: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py` (after this story)**

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.fees import BrokerPreset, FeeSchedule
from steadyhand_idx.rules import IdxMarketRules, RuleTables
from steadyhand_idx.yahoo import UnrecoverablePricesError, YahooDataSource

__version__: str = version("steadyhand-idx")

__all__ = [
    "BrokerPreset",
    "DataFileError",
    "FeeSchedule",
    "IdxCalendar",
    "IdxMarketRules",
    "RuleTables",
    "UnrecoverablePricesError",
    "YahooDataSource",
    "__version__",
]
```

- [ ] **Step 6: Run the whole gate, the audit, and the live test once.**

```bash
uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy
uv run --locked pytest -W error --cov -q
uv export --locked --format requirements-txt --no-emit-workspace --output-file "${TMPDIR}/req.txt"
uv run --locked pip-audit --strict --disable-pip -r "${TMPDIR}/req.txt"
uv run --locked pytest -W error -m live -p no:cacheprovider tests/idx/test_yahoo_live.py
```

Expected: every check passes; `485 passed, 4 deselected`; 100% coverage; `No known vulnerabilities found`; the live run `4 passed`. yfinance 1.7.0 deprecates `history(raise_errors=True)`, and `-W error` turns that into a failure, which is why `download_history` sets `yfinance.config.debug.hide_exceptions = False` instead.

- [ ] **Step 7: Mutations M9, M10, M11, M16 and M19.**

- [ ] **Step 8: Commit, push and merge.**

```bash
git add pyproject.toml uv.lock packages scripts tests .github/workflows/yahoo-shape.yml
git commit -m "feat(idx): Yahoo data source with split reversal, fixtures and daily shape check (#<S5>)"
```

---

### Task 6: S6 SQLite cache and cached data source

**Acceptance criteria (story text):**
1. `BarCache` stores a fetched range (its bars, its actions and the fact that it was fetched) in one transaction, and reads bars and actions back exactly, `OtherAction` included.
2. Storing the same data twice changes nothing. A fetch with any value that differs from one already cached raises `CacheConflictError`, naming the stock, day and both values, and writes nothing from that fetch.
3. The schema is versioned: a new file runs every migration, an older file is upgraded in place with its data kept, and a file from a newer release is refused.
4. `CachedDataSource` is a `DataSource` that fetches a range once, then serves it from the cache. Only the missing trading days are fetched: a weekend or holiday gap is not.
5. Today (in Jakarta) is fetched on every request and never stored; a request past today is refused.
6. An unrecoverable Yahoo range is never cached.
7. Every quality gate is green at 100% branch coverage, and the red phase is recorded in the PR.

**Files:**
- Create: `.../steadyhand_idx/cache.py`
- Modify: `.../steadyhand_idx/__init__.py`
- Test: `tests/idx/test_cache.py`

**Interfaces:**
- Consumes: `IdxCalendar` (Task 1); `YahooDataSource`, `history_from_json`, `unadjust` (Task 5, in tests).
- Produces: in `steadyhand_idx.cache`: `JAKARTA`, `MIGRATIONS`; `CacheConflictError`, `CacheSchemaError`; `BarCache(path)` (a context manager) with `.schema_version`, `.store(instrument, span, bars, actions)`, `.bars(instrument, start, end)`, `.actions(instrument, start, end)`, `.fetched(instrument) -> list[tuple[date, date]]`, `.close()`; `jakarta_today() -> date`; `CachedDataSource(upstream, cache, calendar=None, *, today=jakarta_today)` with `.missing(instrument, start, end)`.

- [ ] **Step 1: Branch.** `git switch -c m2/s6-cache origin/develop` (after S5 is merged).

- [ ] **Step 2: Write the failing tests.**

<!-- file: tests/idx/test_cache.py -->
**`tests/idx/test_cache.py`**

```python
"""The SQLite cache and the cached data source, on real recorded Yahoo data."""

import functools
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    DataSource,
    DataUnavailableError,
    Instrument,
    Money,
    OtherAction,
    Split,
)
from steadyhand_idx.cache import (
    MIGRATIONS,
    BarCache,
    CacheConflictError,
    CachedDataSource,
    CacheSchemaError,
    jakarta_today,
)
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.yahoo import YahooDataSource, YahooHistory, history_from_json, unadjust

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)


@functools.cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


SEP = (date(2021, 9, 1), date(2021, 9, 30))
OCT = (date(2021, 10, 1), date(2021, 10, 29))


def bbca(start: date, end: date) -> tuple[list[Bar], list[CorporateAction]]:
    history = history_from_json(FIXTURES / "BBCA.JK_2021-09-01_2021-11-30.json")
    return unadjust(history, BBCA, calendar(), start, end)


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[BarCache]:
    with BarCache(tmp_path / "cache.sqlite") as opened:
        yield opened


def test_a_new_cache_runs_every_migration(tmp_path: Path) -> None:
    with BarCache(tmp_path / "c.sqlite") as fresh:
        assert fresh.schema_version == len(MIGRATIONS)
    with BarCache(tmp_path / "c.sqlite") as reopened:
        assert reopened.schema_version == len(MIGRATIONS)


def test_a_cache_from_a_newer_release_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "c.sqlite"
    with closing(sqlite3.connect(path)) as raw:
        raw.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    with pytest.raises(CacheSchemaError, match=r"c\.sqlite is at cache schema 2, newer than this"):
        BarCache(path)


def test_an_older_cache_is_upgraded_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.sqlite"
    with BarCache(path) as old:
        old.store(BBCA, SEP, *bbca(*SEP))
    extra = "CREATE TABLE notes (text TEXT NOT NULL) STRICT;"
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", (*MIGRATIONS, extra))
    with BarCache(path) as upgraded:
        assert upgraded.schema_version == len(MIGRATIONS) + 1
        assert len(upgraded.bars(BBCA, *SEP)) == len(calendar().trading_days(*SEP))


def test_bars_and_actions_round_trip(cache: BarCache) -> None:
    bars, actions = bbca(date(2021, 10, 1), date(2021, 11, 30))
    other = OtherAction(BBCA, date(2021, 11, 1), "rights issue, entered by hand")
    cache.store(BBCA, (date(2021, 10, 1), date(2021, 11, 30)), bars, [*actions, other])
    assert cache.bars(BBCA, date(2021, 10, 1), date(2021, 11, 30)) == bars
    assert cache.actions(BBCA, date(2021, 10, 1), date(2021, 11, 30)) == [
        Split(BBCA, date(2021, 10, 13), 1, 5),
        other,
        CashDividend(BBCA, date(2021, 11, 17), Decimal("25.0")),
    ]


def test_storing_the_same_data_twice_changes_nothing(cache: BarCache) -> None:
    span = (date(2021, 10, 1), date(2021, 11, 30))
    cache.store(BBCA, span, *bbca(*span))
    cache.store(BBCA, span, *bbca(*span))
    assert cache.bars(BBCA, *span) == bbca(*span)[0]
    assert cache.actions(BBCA, *span) == bbca(*span)[1]


def test_a_conflicting_fetch_stores_nothing(cache: BarCache) -> None:
    bars, actions = bbca(*SEP)
    cache.store(BBCA, (SEP[0], date(2021, 9, 15)), bars[:11], [])
    kept = bars[3]
    changed = replace(kept, close=Money(kept.close.amount + 25, IDR))
    cached = (kept.open.amount, kept.high.amount, kept.low.amount, kept.close.amount, kept.volume)
    expected = rf"^BBCA {kept.day.isoformat()}: cached bar \({', '.join(map(str, cached))}\)"
    with pytest.raises(CacheConflictError, match=expected + " differs from fetched"):
        cache.store(BBCA, SEP, [*bars[:3], changed, *bars[4:]], actions)
    assert len(cache.bars(BBCA, *SEP)) == 11  # the later bars in that fetch were not written
    assert cache.fetched(BBCA) == [(SEP[0], date(2021, 9, 15))]


def test_a_conflicting_action_stores_nothing(cache: BarCache) -> None:
    dividend = CashDividend(BBCA, date(2021, 11, 17), Decimal("25.0"))
    cache.store(BBCA, (date(2021, 11, 17), date(2021, 11, 17)), [], [dividend])
    with pytest.raises(CacheConflictError, match=r"^BBCA 2021-11-17: cached dividend"):
        cache.store(
            BBCA,
            (date(2021, 11, 17), date(2021, 11, 17)),
            [],
            [replace(dividend, per_share=Decimal(26))],
        )


def test_rows_outside_the_range_or_for_another_stock_are_refused(cache: BarCache) -> None:
    bars, _ = bbca(*SEP)
    with pytest.raises(
        ValueError, match=r"^BBCA 2021-09-01 is not BBCA in 2021-09-02 to 2021-09-30$"
    ):
        cache.store(BBCA, (date(2021, 9, 2), SEP[1]), bars, [])
    with pytest.raises(ValueError, match=r"^BBCA 2021-09-01 is not BBRI in"):
        cache.store(BBRI, SEP, bars, [])
    with pytest.raises(ValueError, match=r"^this cache holds IDX IDR stocks, not X on ASX$"):
        cache.bars(Instrument("X", "ASX", IDR), *SEP)


def test_fetched_ranges_merge_where_they_touch(cache: BarCache) -> None:
    cache.store(BBCA, (date(2021, 9, 1), date(2021, 9, 10)), [], [])
    cache.store(BBCA, (date(2021, 9, 11), date(2021, 9, 20)), [], [])
    cache.store(BBCA, (date(2021, 9, 15), date(2021, 9, 17)), [], [])
    cache.store(BBCA, (date(2021, 10, 1), date(2021, 10, 5)), [], [])
    assert cache.fetched(BBCA) == [
        (date(2021, 9, 1), date(2021, 9, 20)),
        (date(2021, 10, 1), date(2021, 10, 5)),
    ]


def test_missing_skips_stored_ranges_and_non_trading_gaps(cache: BarCache) -> None:
    for span in [
        (date(2021, 9, 1), date(2021, 9, 10)),
        (date(2021, 9, 20), date(2021, 9, 24)),
        (date(2021, 10, 1), date(2021, 10, 5)),
        (date(2021, 11, 1), date(2021, 11, 5)),
    ]:
        cache.store(BBCA, span, [], [])
    source = CachedDataSource(YahooDataSource(calendar()), cache, calendar())
    assert source.missing(BBCA, date(2021, 9, 13), date(2021, 10, 15)) == [
        (date(2021, 9, 13), date(2021, 9, 17)),  # a hole between two stored ranges
        (date(2021, 9, 27), date(2021, 9, 30)),  # 25-26 Sep is a weekend
        (date(2021, 10, 6), date(2021, 10, 15)),  # after the last range that overlaps
    ]


class Counting:
    """A real YahooDataSource on a recording, counting what reaches it."""

    def __init__(self, name: str) -> None:
        self.history = history_from_json(FIXTURES / name)
        self.asked: list[tuple[date, date]] = []
        self.source = YahooDataSource(calendar(), download=self._download, sleep=lambda _: None)

    def _download(self, ticker: str, start: date, end: date) -> YahooHistory:
        self.asked.append((start, end))
        return self.history


def source_for(cache: BarCache, name: str, today: date) -> tuple[CachedDataSource, Counting]:
    counting = Counting(name)
    return CachedDataSource(counting.source, cache, calendar(), today=lambda: today), counting


def test_a_range_is_fetched_once_then_served_from_the_cache(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    assert isinstance(source, DataSource)
    first = source.bars(BBCA, *OCT)
    assert source.corporate_actions(BBCA, *OCT) == [Split(BBCA, date(2021, 10, 13), 1, 5)]
    assert source.bars(BBCA, *OCT) == first
    assert counting.asked == [OCT]


def test_only_the_missing_trading_days_are_fetched(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    source.bars(BBCA, date(2021, 9, 1), date(2021, 9, 24))  # ends on a Friday
    assert source.missing(BBCA, date(2021, 9, 1), date(2021, 9, 26)) == []  # only a weekend left
    source.bars(BBCA, date(2021, 9, 1), date(2021, 10, 8))
    assert counting.asked == [
        (date(2021, 9, 1), date(2021, 9, 24)),
        (date(2021, 9, 27), date(2021, 10, 8)),
    ]


def test_today_is_always_fetched_and_never_stored(cache: BarCache) -> None:
    today = date(2021, 10, 13)
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", today)
    bars = source.bars(BBCA, date(2021, 10, 11), today)
    assert [bar.day for bar in bars] == [date(2021, 10, 11), date(2021, 10, 12), today]
    source.bars(BBCA, date(2021, 10, 11), today)
    assert counting.asked == [(date(2021, 10, 11), date(2021, 10, 12)), (today, today)]
    assert source.corporate_actions(BBCA, date(2021, 10, 11), today) == [Split(BBCA, today, 1, 5)]
    assert cache.fetched(BBCA) == [(date(2021, 10, 11), date(2021, 10, 12))]
    assert [bar.day for bar in source.bars(BBCA, today, today)] == [today]  # nothing to fill
    assert len(counting.asked) == 2


def test_a_request_past_today_or_reversed_is_refused(cache: BarCache) -> None:
    source, _ = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2021, 10, 13))
    with pytest.raises(
        ValueError, match=r"^no bars exist yet after today \(2021-10-13\); asked for 2021-10-14$"
    ):
        source.bars(BBCA, date(2021, 10, 1), date(2021, 10, 14))
    with pytest.raises(ValueError, match=r"^end 2021-10-01 is before start 2021-10-02$"):
        source.bars(BBCA, date(2021, 10, 2), date(2021, 10, 1))


def test_unrecoverable_prices_are_never_cached(cache: BarCache) -> None:
    source, _ = source_for(cache, "BBRI.JK_2021-08-02_2021-09-30.json", date(2026, 9, 25))
    with pytest.raises(DataUnavailableError, match="cannot be recovered"):
        source.bars(BBRI, date(2021, 9, 1), date(2021, 9, 30))
    assert cache.fetched(BBRI) == []
    assert len(source.bars(BBRI, date(2021, 9, 8), date(2021, 9, 30))) == 17


def test_the_default_clock_is_jakartas_date() -> None:
    assert abs((jakarta_today() - date.today()).days) <= 1  # noqa: DTZ011 - comparing two clocks
```

- [ ] **Step 3: Write the stub.**

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/cache.py` (stub)**

```python
"""A local SQLite cache of bars and corporate actions, keyed by (ticker, date) (spec §9.3).

``BarCache`` stores what a data source returned, one range at a time, in one transaction: the
bars, the actions and the fact that the range was fetched. A stored row is never overwritten.
A different value for a row already stored is a ``CacheConflictError`` and nothing is written,
so good cached data survives a bad fetch (spec §5 step 1).

``CachedDataSource`` puts the cache in front of another ``DataSource`` and fetches only the
ranges it is missing (spec §9.2). A day counts as fetched only once it is over in Jakarta, so
today's bar is always fetched afresh and never stored here: M5's daily run stores it after it
passes validation.
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
)
from steadyhand_idx.calendar import IdxCalendar

JAKARTA = ZoneInfo("Asia/Jakarta")
_ONE_DAY = timedelta(days=1)
_BUSY_TIMEOUT_SECONDS = 30.0
MIGRATIONS: tuple[str, ...] = (
    "\n    CREATE TABLE bars (\n        symbol TEXT NOT NULL,\n        day TEXT NOT NULL,\n        open INTEGER NOT NULL,\n        high INTEGER NOT NULL,\n        low INTEGER NOT NULL,\n        close INTEGER NOT NULL,\n        volume INTEGER NOT NULL,\n        PRIMARY KEY (symbol, day)\n    ) STRICT;\n    CREATE TABLE actions (\n        symbol TEXT NOT NULL,\n        ex_date TEXT NOT NULL,\n        kind TEXT NOT NULL CHECK (kind IN ('split', 'dividend', 'other')),\n        old_shares INTEGER,\n        new_shares INTEGER,\n        per_share TEXT,\n        description TEXT,\n        PRIMARY KEY (symbol, ex_date, kind)\n    ) STRICT;\n    CREATE TABLE fetched (\n        symbol TEXT NOT NULL,\n        start TEXT NOT NULL,\n        end TEXT NOT NULL,\n        PRIMARY KEY (symbol, start, end)\n    ) STRICT;\n    ",
)


class CacheConflictError(RuntimeError):
    """A fetched value differs from the one already cached. Nothing from that fetch is stored."""


class CacheSchemaError(RuntimeError):
    """The cache file was written by a newer steadyhand-idx than this one."""


type _BarRow = tuple[int, int, int, int, int]
type _ActionRow = tuple[int | None, int | None, str | None, str | None]


def _action_row(action: CorporateAction) -> tuple[str, _ActionRow]:
    raise NotImplementedError("_action_row")


class BarCache:
    """The cache file. Use it as a context manager, or call ``close()``."""

    def __init__(self, path: Path) -> None:
        raise NotImplementedError("BarCache.__init__")

    def __enter__(self) -> BarCache:
        raise NotImplementedError("BarCache.__enter__")

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        raise NotImplementedError("BarCache.__exit__")

    def close(self) -> None:
        raise NotImplementedError("BarCache.close")

    @property
    def schema_version(self) -> int:
        raise NotImplementedError("BarCache.schema_version")

    def _migrate(self) -> None:
        raise NotImplementedError("BarCache._migrate")

    @contextmanager
    def _write(self) -> Iterator[None]:
        """One transaction, taking the write lock at once, rolled back on any error."""
        raise NotImplementedError("BarCache._write")

    def store(
        self,
        instrument: Instrument,
        span: tuple[date, date],
        bars: Sequence[Bar],
        actions: Sequence[CorporateAction],
    ) -> None:
        """Store one fetched range, all of it or none of it, and mark the range as fetched."""
        raise NotImplementedError("BarCache.store")

    def _insert_bar(self, symbol: str, day: date, row: _BarRow) -> None:
        raise NotImplementedError("BarCache._insert_bar")

    def _insert_action(self, symbol: str, day: date, kind: str, values: _ActionRow) -> None:
        raise NotImplementedError("BarCache._insert_action")

    def bars(self, instrument: Instrument, start: date, end: date) -> list[Bar]:
        raise NotImplementedError("BarCache.bars")

    def actions(self, instrument: Instrument, start: date, end: date) -> list[CorporateAction]:
        raise NotImplementedError("BarCache.actions")

    def fetched(self, instrument: Instrument) -> list[tuple[date, date]]:
        """Every range stored for *instrument*, merged where they touch or overlap."""
        raise NotImplementedError("BarCache.fetched")

    @staticmethod
    def _symbol(instrument: Instrument) -> str:
        raise NotImplementedError("BarCache._symbol")


def jakarta_today() -> date:
    """Today's date in Jakarta, where the IDX trading day is counted."""
    raise NotImplementedError("jakarta_today")


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
        raise NotImplementedError("CachedDataSource.__init__")

    def bars(self, instrument: Instrument, start: date, end: date) -> Sequence[Bar]:
        raise NotImplementedError("CachedDataSource.bars")

    def corporate_actions(
        self, instrument: Instrument, start: date, end: date
    ) -> Sequence[CorporateAction]:
        raise NotImplementedError("CachedDataSource.corporate_actions")

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
        """The parts of *start* to *end* not yet stored, trimmed to trading days.

        A gap holding no trading day (a weekend, a holiday) is not missing: there is nothing
        there to fetch, and asking Yahoo for it would fail.
        """
        raise NotImplementedError("CachedDataSource.missing")

    def _fill(self, instrument: Instrument, start: date, end: date) -> date:
        """Fetch and store every missing range that is over, and return today."""
        raise NotImplementedError("CachedDataSource._fill")
```

- [ ] **Step 4: Run the tests and watch them fail.**

Run: `uv run --locked pytest -W error -q tests/idx/test_cache.py`
Expected: `4 failed, 12 errors`. The 12 errors are tests whose `cache` fixture calls the stubbed `BarCache.__init__`; every failure and error is a `NotImplementedError`. None passes.

- [ ] **Step 5: Write the implementation and export the new names.**

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/cache.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/cache.py`**

```python
"""A local SQLite cache of bars and corporate actions, keyed by (ticker, date) (spec §9.3).

``BarCache`` stores what a data source returned, one range at a time, in one transaction: the
bars, the actions and the fact that the range was fetched. A stored row is never overwritten.
A different value for a row already stored is a ``CacheConflictError`` and nothing is written,
so good cached data survives a bad fetch (spec §5 step 1).

``CachedDataSource`` puts the cache in front of another ``DataSource`` and fetches only the
ranges it is missing (spec §9.2). A day counts as fetched only once it is over in Jakarta, so
today's bar is always fetched afresh and never stored here: M5's daily run stores it after it
passes validation.
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
        for owner, day in located:
            if owner != instrument or not start <= day <= end:
                msg = f"{owner.symbol} {day.isoformat()} is not {symbol} in {start} to {end}"
                raise ValueError(msg)
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
        merged: list[tuple[date, date]] = []
        for first, last in rows:
            start, end = date.fromisoformat(first), date.fromisoformat(last)
            if merged and start <= merged[-1][1] + _ONE_DAY:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    @staticmethod
    def _symbol(instrument: Instrument) -> str:
        if instrument.market != "IDX" or instrument.currency != IDR:
            msg = f"this cache holds IDX IDR stocks, not {instrument.symbol} on {instrument.market}"
            raise ValueError(msg)
        return instrument.symbol


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
        today = self._fill(instrument, start, end)
        cached = self._cache.actions(instrument, start, min(end, today - _ONE_DAY))
        if end < today:
            return cached
        return [*cached, *self._upstream.corporate_actions(instrument, today, today)]

    def missing(self, instrument: Instrument, start: date, end: date) -> list[tuple[date, date]]:
        """The parts of *start* to *end* not yet stored, trimmed to trading days.

        A gap holding no trading day (a weekend, a holiday) is not missing: there is nothing
        there to fetch, and asking Yahoo for it would fail.
        """
        gaps: list[tuple[date, date]] = []
        cursor = start
        for first, last in self._cache.fetched(instrument):
            if last < cursor:
                continue
            if first > end:
                break
            if first > cursor:
                gaps.append((cursor, first - _ONE_DAY))
            cursor = last + _ONE_DAY
        if cursor <= end:
            gaps.append((cursor, end))
        trimmed: list[tuple[date, date]] = []
        for first, last in gaps:
            days = self._calendar.trading_days(first, last)
            if days:
                trimmed.append((days[0], days[-1]))
        return trimmed

    def _fill(self, instrument: Instrument, start: date, end: date) -> date:
        """Fetch and store every missing range that is over, and return today."""
        if end < start:
            msg = f"end {end.isoformat()} is before start {start.isoformat()}"
            raise ValueError(msg)
        today = self._today()
        if end > today:
            msg = (
                f"no bars exist yet after today ({today.isoformat()}); asked for {end.isoformat()}"
            )
            raise ValueError(msg)
        complete = min(end, today - _ONE_DAY)
        if start <= complete:
            for first, last in self.missing(instrument, start, complete):
                bars = self._upstream.bars(instrument, first, last)
                actions = self._upstream.corporate_actions(instrument, first, last)
                self._cache.store(instrument, (first, last), bars, actions)
        return today
```

<!-- file@6: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py` (after this story)**

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.cache import BarCache, CacheConflictError, CachedDataSource, CacheSchemaError
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.fees import BrokerPreset, FeeSchedule
from steadyhand_idx.rules import IdxMarketRules, RuleTables
from steadyhand_idx.yahoo import UnrecoverablePricesError, YahooDataSource

__version__: str = version("steadyhand-idx")

__all__ = [
    "BarCache",
    "BrokerPreset",
    "CacheConflictError",
    "CacheSchemaError",
    "CachedDataSource",
    "DataFileError",
    "FeeSchedule",
    "IdxCalendar",
    "IdxMarketRules",
    "RuleTables",
    "UnrecoverablePricesError",
    "YahooDataSource",
    "__version__",
]
```

- [ ] **Step 6: Run the whole gate.**

Run: `uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy && uv run --locked pytest -W error --cov -q`
Expected: every check passes; `501 passed, 4 deselected`; 100% coverage.

- [ ] **Step 7: Mutations M12, M13 and M14.**

- [ ] **Step 8: Commit, push and merge.**

```bash
git add packages/steadyhand-idx tests/idx
git commit -m "feat(idx): SQLite bar cache that fetches only what is missing (#<S6>)"
```

---

### Task 7: S7 LQ45 universe and exclusions

**Acceptance criteria (story text):**
1. `Lq45Membership.load(path)` reads the user's `lq45_members.toml` in the `t-lq45.md` §4 format. Each record must have exactly 45 different four-letter codes, an `announced` date on or before `effective`, a kind of `review` or `replacement`, and records in date order. Each refusal names the row.
2. Membership on a date is the latest record in force; a date before the first record raises `MembershipUnknownError`.
3. A gap is two consecutive records more than one review apart: six months before May 2024, three from then. `survivorship_warnings(start, end)` warns for a start before the first record and for each gap the range spans.
4. A missing LQ45 file raises `FileNotFoundError` naming `[universe] lq45_members` and pointing to `docs/lq45-members.md`.
5. `Exclusions.load(path)` reads the user's `exclusions.csv` (`symbol,from,to,reason`, `to` inclusive and optional, a reason required); no file means no exclusions.
6. `docs/lq45-members.md` tells a user where IDX publishes each list, the format, why nothing is shipped, and how exclusions work, with the disclaimer. Every list in the tests is synthetic.
7. Every quality gate is green at 100% branch coverage, and the red phase is recorded in the PR.

**Files:**
- Create: `.../steadyhand_idx/universe.py`, `docs/lq45-members.md`
- Modify: `.../steadyhand_idx/__init__.py`
- Test: `tests/idx/test_universe.py`

**Interfaces:**
- Consumes: `_datafile` (Task 1); engine `IDR`, `Instrument` (for symbol validation).
- Produces: in `steadyhand_idx.universe`: `LQ45_SIZE`, `REVIEW_KINDS`, `QUARTERLY_FROM`; `MembershipUnknownError(LookupError)`; `Lq45Record(effective, announced, source, kind, members)`; `Lq45Membership(records, *, file=...)` with `.load(path)`, `.records`, `.members_on(day) -> frozenset[str]`, `.gaps()`, `.survivorship_warnings(start, end) -> list[str]`; `Exclusion(symbol, start, end, reason)` with `.covers(day)`; `Exclusions(entries=())` with `.load(path)` and `.excluded_on(day) -> dict[str, str]`.

- [ ] **Step 1: Branch.** `git switch -c m2/s7-universe origin/develop` (after S6 is merged).

- [ ] **Step 2: Write the failing tests.**

<!-- file: tests/idx/test_universe.py -->
**`tests/idx/test_universe.py`**

```python
"""The user-supplied LQ45 file and exclusions. Every list here is synthetic (t-lq45.md §5)."""

from datetime import date
from itertools import product
from pathlib import Path

import pytest

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.universe import (
    Exclusions,
    Lq45Membership,
    Lq45Record,
    MembershipUnknownError,
)

# 45 made-up four-letter codes. No real LQ45 list is ever written into this repository.
CODES = ["Z" + "".join(letters) for letters in product("ABCDEFGHIJ", repeat=3)][:60]


def record_toml(effective: str, announced: str, members: list[str], kind: str = "review") -> str:
    quoted = ", ".join(f'"{code}"' for code in members)
    return (
        f"[[record]]\neffective = {effective}\nannounced = {announced}\n"
        f'source = "Peng-test/{effective}"\nkind = "{kind}"\nmembers = [{quoted}]\n'
    )


def write(tmp_path: Path, *records: str) -> Path:
    path = tmp_path / "lq45_members.toml"
    path.write_text("schema = 1\n\n" + "\n".join(records), encoding="utf-8")
    return path


# Semi-annual until January 2024, quarterly from May 2024; Feb 2023 is missing on purpose.
DATES = [
    ("2022-08-01", "2022-07-25"),
    ("2023-08-01", "2023-07-25"),
    ("2024-02-01", "2024-01-25"),
    ("2024-05-02", "2024-04-24"),
    ("2024-08-01", "2024-07-25"),
    ("2025-02-03", "2025-01-22"),
]


@pytest.fixture
def membership(tmp_path: Path) -> Lq45Membership:
    records = [record_toml(e, a, CODES[i : i + 45]) for i, (e, a) in enumerate(DATES)]
    return Lq45Membership.load(write(tmp_path, *records))


def test_membership_is_the_latest_list_in_force(membership: Lq45Membership) -> None:
    assert membership.members_on(date(2022, 8, 1)) == frozenset(CODES[0:45])
    assert membership.members_on(date(2024, 1, 31)) == frozenset(CODES[1:46])
    assert membership.members_on(date(2024, 2, 1)) == frozenset(CODES[2:47])
    with pytest.raises(
        MembershipUnknownError,
        match=r"^lq45_members\.toml has no LQ45 list in force on 2022-07-29; its first takes",
    ):
        membership.members_on(date(2022, 7, 29))


def test_gaps_are_records_more_than_one_review_apart(membership: Lq45Membership) -> None:
    # Aug 2022 -> Aug 2023 skips Feb 2023 (12 months > 6); Aug 2024 -> Feb 2025 skips Nov 2024
    # (6 months > 3 once reviews are quarterly). Jan 2024 -> May 2024 is 3 months: no gap.
    assert [(a.effective, b.effective) for a, b in membership.gaps()] == [
        (date(2022, 8, 1), date(2023, 8, 1)),
        (date(2024, 8, 1), date(2025, 2, 3)),
    ]


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
    later = membership.survivorship_warnings(date(2024, 9, 2), date(2025, 3, 3))
    assert [w.split(" between ")[1][:10] for w in later] == ["2024-08-01"]


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (
            record_toml("2024-02-01", "2024-02-02", CODES[:45]),
            "announced 2024-02-02 is after effective",
        ),
        (record_toml("2024-02-01", "2024-01-25", CODES[:45], "annual"), "kind must be 'review' or"),
        (
            record_toml("2024-02-01", "2024-01-25", CODES[:44]),
            "members must list 45 different codes, got 44 of 44",
        ),
        (
            record_toml("2024-02-01", "2024-01-25", [*CODES[:44], CODES[0]]),
            "members must list 45 different codes, got 44 of 45",
        ),
        (
            record_toml("2024-02-01", "2024-01-25", [*CODES[:44], "BBCA.JK"]),
            r"members must be four-letter IDX codes, got 'BBCA\.JK'",
        ),
    ],
    ids=["announced-late", "kind", "44-codes", "duplicate", "not-a-code"],
)
def test_bad_records_are_refused(tmp_path: Path, record: str, message: str) -> None:
    with pytest.raises(
        DataFileError, match=rf"^lq45_members\.toml \[\[record\]\] row 1: {message}"
    ):
        Lq45Membership.load(write(tmp_path, record))


def test_records_must_be_in_order(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        record_toml("2024-05-02", "2024-04-24", CODES[:45]),
        record_toml("2024-02-01", "2024-01-25", CODES[:45]),
    )
    with pytest.raises(
        DataFileError, match="must be in effective-date order, got 2024-02-01 after"
    ):
        Lq45Membership.load(path)
    with pytest.raises(DataFileError, match=r"^mine\.toml: needs at least one record$"):
        Lq45Membership([], file="mine.toml")


def test_a_missing_file_names_the_config_key(tmp_path: Path) -> None:
    with pytest.raises(
        FileNotFoundError,
        match=r"^\[universe\] lq45_members points to .*nothing\.toml, which does not exist\. "
        r"steadyhand does not ship LQ45 lists",
    ):
        Lq45Membership.load(tmp_path / "nothing.toml")


def test_the_records_are_kept(membership: Lq45Membership) -> None:
    first = membership.records[0]
    assert first == Lq45Record(
        date(2022, 8, 1), date(2022, 7, 25), "Peng-test/2022-08-01", "review", frozenset(CODES[:45])
    )


def exclusions(tmp_path: Path, text: str) -> Exclusions:
    path = tmp_path / "exclusions.csv"
    path.write_text(text, encoding="utf-8")
    return Exclusions.load(path)


def test_exclusions_apply_between_their_dates(tmp_path: Path) -> None:
    found = exclusions(
        tmp_path,
        "symbol,from,to,reason\n"
        "ZAAA,2024-01-02,2024-06-28,Special Monitoring Board\n"
        "ZAAB,2025-01-02,,I do not want to own it\n",
    )
    assert found.excluded_on(date(2024, 1, 1)) == {}
    assert found.excluded_on(date(2024, 6, 28)) == {"ZAAA": "Special Monitoring Board"}
    assert found.excluded_on(date(2026, 9, 25)) == {"ZAAB": "I do not want to own it"}


def test_no_exclusions_file_means_no_exclusions(tmp_path: Path) -> None:
    assert Exclusions.load(tmp_path / "absent.csv").excluded_on(date(2026, 9, 25)) == {}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", r"the first line must be symbol,from,to,reason"),
        ("sym,from,to,reason\n", r"the first line must be symbol,from,to,reason"),
        ("symbol,from,to,reason\nZAAA,2024-01-02\n", r"line 2: needs 4 fields, got 2"),
        ("symbol,from,to,reason\nzaaa,2024-01-02,,x\n", r"line 2: 'zaaa' is not an IDX symbol"),
        (
            "symbol,from,to,reason\nZAAA,02/01/2024,,x\n",
            r"line 2: dates must be written 2026-09-25",
        ),
        (
            "symbol,from,to,reason\nZAAA,2024-01-02,2023-01-02,x\n",
            r"line 2: to 2023-01-02 is before",
        ),
        ("symbol,from,to,reason\nZAAA,2024-01-02,, \n", r"line 2: give a reason"),
    ],
)
def test_bad_exclusions_are_refused(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(DataFileError, match=rf"^exclusions\.csv.*{message}"):
        exclusions(tmp_path, text)
```

- [ ] **Step 3: Write the stub.**

<!-- stub: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/universe.py` (stub)**

```python
"""Which stocks a strategy may hold: dated LQ45 membership and the exclusions (spec §9.4).

Both files are supplied by the user, and steadyhand ships neither. IDX's Terms of Use bar
redistributing its data for commercial use without written permission, and Apache-2.0 would pass
on rights we do not hold (docs/research/t-lq45.md §5). docs/lq45-members.md tells a user where IDX
publishes each list; nothing here downloads anything.
"""

from __future__ import annotations
import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path
from steadyhand import IDR, Instrument
from steadyhand_idx._datafile import (
    DataFileError,
    Row,
    Where,
    get_date,
    get_list,
    get_str,
    load_path,
    only_keys,
    require_schema,
    rows,
)

LQ45_SIZE = 45
REVIEW_KINDS = frozenset({"review", "replacement"})
QUARTERLY_FROM = date(2024, 5, 1)
_CODE = re.compile("[A-Z]{4}")
_EXCLUSION_HEADER = ["symbol", "from", "to", "reason"]


class MembershipUnknownError(LookupError):
    """No LQ45 list in the user's file covers the day asked about."""


@dataclass(frozen=True, slots=True)
class Lq45Record:
    """One IDX document's full list of 45, in force from ``effective`` until the next record."""

    effective: date
    announced: date
    source: str
    kind: str
    members: frozenset[str]


def _months_between(earlier: date, later: date) -> int:
    raise NotImplementedError("_months_between")


def _parse_record(row: Row, where: Where) -> Lq45Record:
    raise NotImplementedError("_parse_record")


class Lq45Membership:
    """LQ45 membership on each date: the latest record in force on or before it."""

    def __init__(self, records: Sequence[Lq45Record], *, file: str = "lq45_members.toml") -> None:
        raise NotImplementedError("Lq45Membership.__init__")

    @classmethod
    def load(cls, path: Path) -> Lq45Membership:
        """Read the user's file. A missing file names the config key that points to it."""
        raise NotImplementedError("Lq45Membership.load")

    @property
    def records(self) -> tuple[Lq45Record, ...]:
        raise NotImplementedError("Lq45Membership.records")

    def members_on(self, day: date) -> frozenset[str]:
        raise NotImplementedError("Lq45Membership.members_on")

    def gaps(self) -> list[tuple[Lq45Record, Lq45Record]]:
        """Consecutive records more than one review apart: at least one list is missing."""
        raise NotImplementedError("Lq45Membership.gaps")

    def survivorship_warnings(self, start: date, end: date) -> list[str]:
        """What a backtest from *start* to *end* must print about missing lists (spec §9.4)."""
        raise NotImplementedError("Lq45Membership.survivorship_warnings")


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A stock the operator keeps out of the portfolio, from ``start`` to ``end`` inclusive."""

    symbol: str
    start: date
    end: date | None
    reason: str

    def covers(self, day: date) -> bool:
        raise NotImplementedError("Exclusion.covers")


class Exclusions:
    """The operator's ``exclusions.csv``: stocks never bought, and frozen if held (spec §6.1).

    Yahoo cannot tell which stocks are on the Special Monitoring Board, so the user lists them
    here by hand, with the dates they were on it. No file means no exclusions.
    """

    def __init__(self, entries: Sequence[Exclusion] = ()) -> None:
        raise NotImplementedError("Exclusions.__init__")

    @classmethod
    def load(cls, path: Path) -> Exclusions:
        raise NotImplementedError("Exclusions.load")

    def excluded_on(self, day: date) -> dict[str, str]:
        """Each symbol excluded on *day*, with the reason given for it."""
        raise NotImplementedError("Exclusions.excluded_on")


def _exclusion(line: list[str], where: str) -> Exclusion:
    raise NotImplementedError("_exclusion")
```

- [ ] **Step 4: Run the tests and watch them fail.**

Run: `uv run --locked pytest -W error -q tests/idx/test_universe.py`
Expected: `16 failed, 4 errors`. The four errors are tests whose `membership` fixture calls the stubbed loader; every failure and error is a `NotImplementedError`. None passes.

- [ ] **Step 5: Write the implementation, the guide, and export the new names.**

<!-- file: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/universe.py`**

```python
"""Which stocks a strategy may hold: dated LQ45 membership and the exclusions (spec §9.4).

Both files are supplied by the user, and steadyhand ships neither. IDX's Terms of Use bar
redistributing its data for commercial use without written permission, and Apache-2.0 would pass
on rights we do not hold (docs/research/t-lq45.md §5). docs/lq45-members.md tells a user where IDX
publishes each list; nothing here downloads anything.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path

from steadyhand import IDR, Instrument
from steadyhand_idx._datafile import (
    DataFileError,
    Row,
    Where,
    get_date,
    get_list,
    get_str,
    load_path,
    only_keys,
    require_schema,
    rows,
)

LQ45_SIZE = 45
REVIEW_KINDS = frozenset({"review", "replacement"})
# LQ45 reviews were semi-annual until January 2024 and quarterly from May 2024 (t-lq45.md §3).
QUARTERLY_FROM = date(2024, 5, 1)
_CODE = re.compile(r"[A-Z]{4}")
_EXCLUSION_HEADER = ["symbol", "from", "to", "reason"]


class MembershipUnknownError(LookupError):
    """No LQ45 list in the user's file covers the day asked about."""


@dataclass(frozen=True, slots=True)
class Lq45Record:
    """One IDX document's full list of 45, in force from ``effective`` until the next record."""

    effective: date
    announced: date
    source: str
    kind: str
    members: frozenset[str]


def _months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def _parse_record(row: Row, where: Where) -> Lq45Record:
    only_keys(row, {"effective", "announced", "source", "kind", "members"}, where)
    effective = get_date(row, "effective", where)
    announced = get_date(row, "announced", where)
    if announced > effective:
        msg = f"{where}: announced {announced} is after effective {effective}"
        raise DataFileError(msg)
    kind = get_str(row, "kind", where)
    if kind not in REVIEW_KINDS:
        msg = f"{where}: kind must be 'review' or 'replacement', got {kind!r}"
        raise DataFileError(msg)
    codes = get_list(row, "members", where)
    bad = [code for code in codes if not (isinstance(code, str) and _CODE.fullmatch(code))]
    if bad:
        msg = f"{where}: members must be four-letter IDX codes, got {bad[0]!r}"
        raise DataFileError(msg)
    members = frozenset(str(code) for code in codes)
    if len(codes) != LQ45_SIZE or len(members) != LQ45_SIZE:
        msg = (
            f"{where}: members must list {LQ45_SIZE} different codes, "
            f"got {len(members)} of {len(codes)}"
        )
        raise DataFileError(msg)
    return Lq45Record(effective, announced, get_str(row, "source", where), kind, members)


class Lq45Membership:
    """LQ45 membership on each date: the latest record in force on or before it."""

    def __init__(self, records: Sequence[Lq45Record], *, file: str = "lq45_members.toml") -> None:
        if not records:
            msg = f"{file}: needs at least one record"
            raise DataFileError(msg)
        for earlier, later in pairwise(records):
            if later.effective <= earlier.effective:
                msg = (
                    f"{file}: records must be in effective-date order, "
                    f"got {later.effective} after {earlier.effective}"
                )
                raise DataFileError(msg)
        self._records = tuple(records)
        self._file = file

    @classmethod
    def load(cls, path: Path) -> Lq45Membership:
        """Read the user's file. A missing file names the config key that points to it."""
        if not path.exists():
            msg = (
                f"[universe] lq45_members points to {path}, which does not exist. steadyhand does "
                "not ship LQ45 lists: docs/lq45-members.md says where IDX publishes each one"
            )
            raise FileNotFoundError(msg)
        document = load_path(path)
        require_schema(document, path.name, 1)
        only_keys(document, {"schema", "record"}, Where(path.name, "top level"))
        where = Where(path.name, "record")
        records = [
            _parse_record(row, where.at(index))
            for index, row in enumerate(rows(document, "record", where), start=1)
        ]
        return cls(records, file=path.name)

    @property
    def records(self) -> tuple[Lq45Record, ...]:
        return self._records

    def members_on(self, day: date) -> frozenset[str]:
        found = [record for record in self._records if record.effective <= day]
        if not found:
            msg = (
                f"{self._file} has no LQ45 list in force on {day.isoformat()}; "
                f"its first takes effect on {self._records[0].effective.isoformat()}"
            )
            raise MembershipUnknownError(msg)
        return found[-1].members

    def gaps(self) -> list[tuple[Lq45Record, Lq45Record]]:
        """Consecutive records more than one review apart: at least one list is missing."""
        found: list[tuple[Lq45Record, Lq45Record]] = []
        for earlier, later in pairwise(self._records):
            allowed = 3 if later.effective >= QUARTERLY_FROM else 6
            if _months_between(earlier.effective, later.effective) > allowed:
                found.append((earlier, later))
        return found

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
            if start < later.effective and earlier.effective <= end:
                warnings.append(
                    f"Survivorship bias: {self._file} has no LQ45 list between "
                    f"{earlier.effective.isoformat()} ({earlier.source}) and "
                    f"{later.effective.isoformat()} ({later.source}), more than one review apart. "
                    "The backtest uses the earlier list until the later one."
                )
        return warnings


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A stock the operator keeps out of the portfolio, from ``start`` to ``end`` inclusive."""

    symbol: str
    start: date
    end: date | None
    reason: str

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)


class Exclusions:
    """The operator's ``exclusions.csv``: stocks never bought, and frozen if held (spec §6.1).

    Yahoo cannot tell which stocks are on the Special Monitoring Board, so the user lists them
    here by hand, with the dates they were on it. No file means no exclusions.
    """

    def __init__(self, entries: Sequence[Exclusion] = ()) -> None:
        self._entries = tuple(entries)

    @classmethod
    def load(cls, path: Path) -> Exclusions:
        if not path.exists():
            return cls()
        with path.open(encoding="utf-8", newline="") as handle:
            lines = list(csv.reader(handle))
        if not lines or lines[0] != _EXCLUSION_HEADER:
            msg = f"{path.name}: the first line must be {','.join(_EXCLUSION_HEADER)}"
            raise DataFileError(msg)
        return cls(
            [_exclusion(line, f"{path.name} line {n}") for n, line in enumerate(lines[1:], 2)]
        )

    def excluded_on(self, day: date) -> dict[str, str]:
        """Each symbol excluded on *day*, with the reason given for it."""
        return {entry.symbol: entry.reason for entry in self._entries if entry.covers(day)}


def _exclusion(line: list[str], where: str) -> Exclusion:
    if len(line) != len(_EXCLUSION_HEADER):
        msg = f"{where}: needs {len(_EXCLUSION_HEADER)} fields, got {len(line)}"
        raise DataFileError(msg)
    symbol, first, last, reason = (field.strip() for field in line)
    try:
        Instrument(symbol, "IDX", IDR)
    except ValueError:
        msg = f"{where}: {symbol!r} is not an IDX symbol"
        raise DataFileError(msg) from None
    try:
        start = date.fromisoformat(first)
        end = date.fromisoformat(last) if last else None
    except ValueError:
        msg = f"{where}: dates must be written 2026-09-25, got {first!r} and {last!r}"
        raise DataFileError(msg) from None
    if end is not None and end < start:
        msg = f"{where}: to {end} is before from {start}"
        raise DataFileError(msg)
    if not reason:
        msg = f"{where}: give a reason, so the report can say why {symbol} was skipped"
        raise DataFileError(msg)
    return Exclusion(symbol, start, end, reason)
```

<!-- file: docs/lq45-members.md -->
**`docs/lq45-members.md`**

````markdown
# Supplying your own LQ45 list

> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.

steadyhand-idx picks stocks from the **LQ45**, IDX's list of 45 large, liquid stocks, as it stood on each date. It does **not** ship those lists. IDX's Terms of Use bar redistributing its data for a commercial purpose without written permission, and steadyhand's Apache-2.0 licence would pass on rights the project does not hold (`docs/research/t-lq45.md` §5). So you build the file yourself, from IDX's own documents, and it stays on your machine. steadyhand never downloads anything from idx.co.id.

## Where the file goes

Put it in your steadyhand data directory and point the config at it:

```toml
[universe]
lq45_members = "lq45_members.toml"   # relative to the data directory
```

If the file is missing, steadyhand stops and names this key.

## The format

One record per IDX document, each carrying the **full** list of 45 in force from its `effective` date. Membership on a date is the latest record whose `effective` is on or before it, so a record ends where the next begins and two records can never overlap.

```toml
schema = 1

[[record]]
effective = 2026-05-04              # the first trading day the list applies
announced = 2026-04-24              # the date on IDX's announcement
source = "Peng-00067/BEI.POP/04-2026"
kind = "review"                     # "review", or "replacement" for a mid-period change
members = ["AADI", "ADMR", "ADRO"]  # all 45 four-letter codes; shortened here
```

The loader refuses a record that does not have exactly 45 different four-letter codes, whose `announced` date is after its `effective` date, or that is out of order.

## Where IDX publishes each list

- **Reviews from 2024 on:** IDX announces each review as an announcement numbered `Peng-…/BEI.POP/…`, titled *Evaluasi Mayor* or *Evaluasi Minor Indeks LQ45*, on the announcements page of idx.co.id. The announcement gives the exact effective day.
- **Earlier reviews:** the same announcements (`Peng-…/BEI.OPP/…` before 2019), and IDX's *IDX LQ45* fact-sheet booklets for each period. `docs/research/t-lq45.md` §3 lists the document for every review from February 2016 to November 2025, and which ones were found.
- Before 2024 the documents name the month, not the day: use the first IDX trading day of that month.
- IDX's Terms ask that you cite the source and the date you accessed it when you quote a list. The `source` field is there for that.

## Gaps and survivorship bias

A backtest that starts before your first record, or runs across two records more than one review apart, prints a **survivorship-bias warning**. Reviews were every six months until January 2024 and every three months from May 2024. A gap means stocks that joined and left the LQ45 inside it never appear in the backtest, so its results look better than a real investor's would have. Five reviews between 2016 and 2025 have no primary list anyone has found (`t-lq45.md` §3).

## Exclusions

`exclusions.csv`, also in the data directory and also yours, lists stocks steadyhand must never buy, and freezes them if held. Use it for stocks on IDX's Special Monitoring Board (Papan Pemantauan Khusus), which Yahoo cannot report, or any stock you choose to avoid:

```csv
symbol,from,to,reason
ABCD,2024-01-02,2024-06-28,Special Monitoring Board
WXYZ,2025-01-02,,I do not want to own it
```

`to` is inclusive and may be left empty. Every row needs a reason, which the daily report shows. No file means no exclusions.
````

<!-- file@7: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py` (after this story)**

```python
"""steadyhand-idx: the Indonesia Stock Exchange distribution of steadyhand."""

from importlib.metadata import version

from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.cache import BarCache, CacheConflictError, CachedDataSource, CacheSchemaError
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.fees import BrokerPreset, FeeSchedule
from steadyhand_idx.rules import IdxMarketRules, RuleTables
from steadyhand_idx.universe import Exclusions, Lq45Membership, MembershipUnknownError
from steadyhand_idx.yahoo import UnrecoverablePricesError, YahooDataSource

__version__: str = version("steadyhand-idx")

__all__ = [
    "BarCache",
    "BrokerPreset",
    "CacheConflictError",
    "CacheSchemaError",
    "CachedDataSource",
    "DataFileError",
    "Exclusions",
    "FeeSchedule",
    "IdxCalendar",
    "IdxMarketRules",
    "Lq45Membership",
    "MembershipUnknownError",
    "RuleTables",
    "UnrecoverablePricesError",
    "YahooDataSource",
    "__version__",
]
```

- [ ] **Step 6: Run the whole gate, and build.**

Run: `uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy && uv run --locked pytest -W error --cov -q && uv build --all-packages --out-dir dist`
Expected: every check passes; `521 passed, 4 deselected`; 100% coverage; both wheels build.

- [ ] **Step 7: Mutation M15.**

- [ ] **Step 8: Commit, push and merge.**

```bash
git add packages/steadyhand-idx tests/idx docs/lq45-members.md
git commit -m "feat(idx): user-supplied LQ45 membership, survivorship warnings and exclusions (#<S7>)"
```

---

## Mutation checks

Each mutation plants one realistic defect, runs the **whole** suite, and must turn it red. The anchor must match exactly once and the change is printed before the run. The test total must not move: 525 collected, of which 521 run and the 4 `live` tests are deselected. The live mutation needs the network.

| # | Task | Defect planted | Caught by |
|---|---|---|---|
| M1 | 2 | `ticks.py`: a tier's lower bound made exclusive | `test_every_tier_boundary_on_both_sides` (and 6 more) |
| M2 | 2 | `bands.py`: a tier's upper bound made exclusive | `test_the_tier_edges_are_inclusive_of_the_upper_bound` (5) |
| M3 | 4 | `rules.py`: the band's top not snapped to the tick grid | `test_band_edges_come_from_the_band_and_the_tick_grid_together`, the hypothesis property |
| M4 | 3 | `fees.py`: the total rounded down (for the trader) | `test_costs_round_once_against_the_trader`, `test_a_small_trade_rounds_the_total_up_once` |
| M5 | 3 | `fees.py`: no VAT on the commission | `test_worked_examples_on_ten_million` (and 3 more) |
| M6 | 3 | `fees.py`: the stamp-duty exemption made exclusive | `test_stamp_duty_is_charged_as_the_law_imposed_it`, `test_daily_costs_are_the_stamp_duty` |
| M7 | 4 | `rules.py`: `verified_from` hard-coded to 2021-01-01 | `test_the_verified_date_is_derived_from_the_files` |
| M8 | 4 | `rules.py`: settlement lag hard-coded to 3 | `test_settlement_is_two_trading_days_later` (4) |
| M9 | 5 | `yahoo.py`: a split applied on its own ex-date | `test_splits_are_reversed_using_the_whole_split_history`, the ticks-and-bands check |
| M10 | 5 | `yahoo.py`: any fraction accepted as whole rupiah | `test_an_unreported_adjustment_is_refused_with_every_day_named`, `test_unrecoverable_prices_are_never_cached` |
| M11 | 5 | `yahoo.py`: holiday placeholder bars kept | `test_a_flat_empty_bar_on_a_holiday_is_dropped` |
| M12 | 6 | `cache.py`: a differing value overwritten silently | `test_a_conflicting_fetch_stores_nothing` |
| M13 | 6 | `cache.py`: today's bar stored | `test_today_is_always_fetched_and_never_stored` |
| M14 | 6 | `cache.py`: weekend-only gaps fetched | `test_missing_skips_stored_ranges_and_non_trading_gaps`, `test_only_the_missing_trading_days_are_fetched` |
| M15 | 7 | `universe.py`: quarterly reviews read as semi-annual | `test_gaps_are_records_more_than_one_review_apart`, `test_warnings_for_an_early_start_and_each_gap_spanned` |
| M16 | 5 | `yahoo.py`: a second `# pragma: no cover`, on `ticker_for` | `test_only_the_yahoo_download_is_excluded` |
| M17 | 1 | `calendar.py`: the year arithmetic check skipped | `test_a_dropped_holiday_fails_the_arithmetic_check` |
| M18 | 1 | `_datafile.py`: `Dated.on` no longer refuses a day before the first row | `test_a_dated_table_refuses_a_day_before_its_first_row` (and 5 more) |
| M19 | 5 | a recorded BBCA close changed from 6565.0 to 6570.0 (live, needs the network) | `test_yahoo_still_gives_what_was_recorded[BBCA...]` |

## Carried forward to later plans

- **M3, the backtest start:** call `rules.require_supported(start)` before the first day, and print the error, which names the table.
- **M3, daily costs:** call `rules.daily_costs(day's buys + sells, day)` once per trading day with trades, and book the result as cash movement (stamp duty).
- **M3, the impossible-data check:** use `price_band(instrument, previous close, day)` except on a first trading day and a split's ex-date (scope decision 7).
- **M3, rights issues are invisible from Yahoo.** `UnrecoverablePricesError.days` ends the day before the unreported action's ex-date (BBRI 2021-09-08, SMGR 2022-12-13, MDKA 2022-04-14 by the measurement above), but Yahoo never reports the action itself, so §5 step 2's freeze cannot fire from Yahoo data. M3 must choose a source for `OtherAction`, for example a user-maintained actions file or an inference from that boundary, and a policy for LQ45 members whose early prices are unrecoverable. BBRI, SMGR and MDKA are all in the 2021 window of §14 AC1.
- **M3, the universe before the first LQ45 record:** `members_on` raises `MembershipUnknownError`; the backtest decides whether to start later or use the first list with its survivorship warning.
- **M4:** `dividend_tax`'s `reinvested_by_deadline` flag is replaced by the exemption claim (§6.2).
- **M5:** `sessions.toml`; configurable `custom` preset rates and a minimum fee; the `[universe]` key for another universe and the exclusions path; the daily run storing today's validated bar with `BarCache.store`.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

- **Pass 1 (2026-09-25):** mechanical, then a full read of the prose. Every code block was generated from a verified tree, not typed. `check_plan.py` then replayed the plan from its own text, task by task on top of the previous story's verified tree. It wrote the blocks before Step 4, ran Step 4's command, wrote the rest, ran the plan's own `uv add` and recording commands, and ran the gate. All 14 red and green claims reproduced exactly (63, 68, 31, 35+5, 30+2, 4+12 and 16+4 red; 319, 387, 418, 453, 485, 501 and 521 green), with ruff, format, mypy and pytest at rc 0 in every task. Each rebuilt tree was byte-identical to its verified story tree, re-recorded fixtures and `uv.lock` included. Both excerpts are in their final files. All 73 names in the Interfaces blocks exist in the code. pip-audit is clean. 19 of 19 mutations turn the whole suite red, with the test total unchanged. The placeholder scan's only hit is the board status "Todo". Four findings, all fixed: (1) the mutation section said 521 tests were collected, while 525 are and 521 run; (2) Task 0's PR cited a plan ticket that no step filed, so Step 0 now files it; (3) M16 planted its pragma in `cache.py`, which does not exist until Task 6, though it is Task 5's mutation, so it now plants it in `yahoo.py` and was re-run (red); (4) scope decision 3 gave the market's first T+2 day without saying where it came from, and now cites the press as secondary.
- **Pass 2 (2026-09-25):** mechanical, on the re-rendered plan. `check_plan.py` again rebuilt all seven story trees byte-identical to the verified ones, and all 14 red and green claims matched. Every mutation was run again, this time inside its owning story's tree rather than the final one, and all 18 code mutations turned that story's whole suite red, with the story's own total unchanged (319, 387, 418, 453, 485, 501 or 521). M19 is the live one and needs the network; it was proven red on the story-5 fixture. Read: every prose line pass 1 changed (Task 0 Step 0, scope decision 3, the mutation count, M16's row, the pass 1 entry). **0 findings. Loop closed. Plan approved 2026-09-25** (self-approval, per the operator's standing rule of 2026-09-24).
- **Pass 3 (2026-09-25, while executing Task 0):** one finding, fixed. Scope decision 3 dated both press reports of the first T+2 day to 26 Nov 2018, but only Bareksa's carries that date in what was read; Hukumonline's did not show one. It now reads "Bareksa, 26 Nov 2018, and Hukumonline". The same wording was corrected in `t-rules.md` §7 before commit. The approval above is withdrawn until a clean pass.
- **Pass 4 (2026-09-25):** mechanical: `check_plan.py` on the re-rendered plan rebuilt all seven story trees byte-identical to the verified ones, and all 14 red and green claims matched. Read: the lines pass 3 changed (scope decision 3 and the pass 3 entry), plus the spec's §3.6 sentence on the same date, which already said "press, secondary" without dating both reports. **0 findings. Loop closed. Plan approved 2026-09-25** (self-approval, per the operator's standing rule of 2026-09-24).
