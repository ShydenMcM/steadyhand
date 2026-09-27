# M4b Exemption Claim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model the Indonesian dividend reinvestment exemption as an engine switch, off by default: with it on, a dividend that can be exempt books no tax at pay and opens a claim. Buys made by the deadline cover it and must stay invested through three tax years, with a settlement-cycle grace for selling one stock to buy another, and tax is booked when reinvestment or protection fails. The income report shows the open claims as an estimate, and a switch-on golden run on real data pins one claim of each kind.

**Architecture:** `MarketRules` loses `dividend_tax`'s flag and gains `reinvestment_deadline(ex_date)` and `protection_end(purchase_day)`, read by IDX from a dated `dividend_exemption` table in `fees.toml` (S5). A new `steadyhand.exemption` module holds `Protection` and `DividendClaim` (S5), `cover_claims`, which matches each day's buys to open claims (S6), and `settle_claims`, which books the deadline tax (S6) and the tax on a broken protection (S7) at the day's close. `corporate.apply_actions` opens claims at pay when `Payout.exemption` is on; `run_day` covers and settles them after the fills and before valuation, and carries them in `Holdings.claims` and `Holdings.shortfall_since`. `IncomeReport.claims` shows them (S8).

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-26-m4-income-design.md` (the "M4 spec"), stories S5–S8 of its §10, on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec") and `docs/superpowers/specs/2026-09-27-training-design.md` (the "T1 spec"). It cites M4a's scope decisions 4 and 5 (a split on a dividend's own ex-date restates it; restatement is exact in integers), which this plan does not change. Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how each claim was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2). No task adds a dependency. The engine stays market-neutral: every Indonesian date and rate comes through `MarketRules` (M4 §3.1).
- Every money figure is `Money` in integer minor units; tax rounds up, once per booking (core §4.4, M4 §9). No `float` anywhere in the engine (`tests/meta/test_no_float.py`).
- With the switch off, every figure and ledger entry the S9 golden test checks is unchanged (M4 §6.2). Each task's gate runs that test.
- Every note is a `Note` built from a key constant in `steadyhand/notes.py`, and every figure a report can show has a term in `steadyhand/terms.py` (M4 §7, T1 §3). Every key has a lesson in the same PR: `tests/meta/test_lessons.py` fails until it does.
- Every `*Error` a task raises is raised by a test that asserts its message or its fields. A `pytest.raises` names what it expects with `match=`, and a `match=` holding a regex metacharacter is a raw string (ruff RUF043).
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A function that already existed keeps its old body in the red phase, and a class that already existed keeps its old fields, so every constructor call keeps matching; only new names are stubs.
- 100% branch coverage (core §10.5). No new `# pragma: no cover` and no new `noqa` in package code.
- Test file basenames are unique across `tests/`. English only. The phrase "robot trading" never appears (core §1.3).
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **A buy used up by an older claim while a newer one is still open.** Expected: the newer claim is left untouched, with no zero-value protection built for it (which `Protection` would refuse). Pinned in Task 2 (`test_a_buy_used_up_by_an_older_claim_leaves_the_newer_one_untouched`).
2. **A reinvestment deadline before the pay day**, possible only with a pay lag of more than about three months, the shortest gap from an ex-date (31 December) to its deadline (31 March). Expected: no claim opens, and the tax is booked at pay as with the switch off. Pinned in Task 1 (`test_a_claim_opens_only_while_its_deadline_can_still_be_met`; mutation M144).
3. **Protections with the same end date when a shortfall breaks some of them.** Expected: a total order, newest claim first and then its protection added last, so a break never depends on tuple order. Pinned in Task 3 (`test_equal_dates_break_the_newest_claim_and_its_last_protection_first`; mutation M163).
4. **A claim taxed in pieces.** Each booking rounds up on its own, so the pieces can add up to more than the full tax on the gross. Expected: at most one rupiah more per extra booking (M4 §9). Pinned in Task 3 (`test_each_booking_rounds_up_on_its_own` and the property `test_a_claims_tax_never_exceeds_its_full_tax_plus_one_unit_per_extra_booking`).
5. **A rotation: one stock sold and another bought inside the settlement cycle.** Expected: the claim survives, and the shortfall's day is cleared (M4 decision 6). Pinned in Task 3 (`test_a_shortfall_gone_before_the_grace_ends_clears_its_day`).

## Scope decisions (read before starting)

1. **The rule starts on 17 February 2021.** M4 §6.1 left PMK 18/2021's in-force date to S5. Its Pasal 119 says *"Peraturan Menteri ini mulai berlaku pada tanggal diundangkan"*, and page 158 dates the promulgation 17 February 2021 (BPK Download/155338). The transitional Pasal 109 also lets tax withheld on dividends received since UU 11/2020 (2 November 2020) be reclaimed; that is a refund route, not the claim the engine models, so it is recorded in `docs/research/t-tax.md` §6 and not modelled. A dividend whose **ex-date** is on or after 17 February 2021 can be claimed. Both choices, the later start and the ex-date where the law says the day received, can only tax more than the law requires.
2. **The rows live in `fees.toml`, in a `dividend_exemption` table that starts in 2009 with a row giving no exemption.** A table first dated 2021 would move `IdxMarketRules.verified_from`, the latest first date of any table, from 1 January 2021 to 17 February 2021 and forbid every earlier backtest. A row gives both counts (`reinvest_by_month`, `hold_tax_years`) or neither; one without the other is refused.
3. **`apply_actions` takes a `Payout(pay_lag_trading_days, exemption)`** instead of a sixth argument, which ruff's PLR0913 refuses (and a positional bool is FBT001). One test passed the lag positionally; it now builds `Payout(0)`.
4. **`DividendClaim` carries `uncovered` from S5.** M4 §6.2 lists the claim's parts as instrument, ex-date, pay date, gross, deadline and protections; the part still to reinvest is the state S6 matches against, so it is there from the start rather than added to the type in a later story.
5. **A claim opens only while its deadline can still be met**, on or after the pay day. A dividend whose deadline has already passed at pay is taxed at pay, as one with no deadline is (M4 §6.2 names only `None`).
6. **The bookkeeping is two functions, run after the fills and before valuation.** `cover_claims(claims, fills, rules)` and `settle_claims(portfolio, claims, shortfall_since, day, rules) -> ClaimDay`: one would need six arguments. The tax they book changes cash, so it must land before the day's value and unit price are taken; `DayReport.tax` includes it. They run every day; with the switch off there are no claims, and they change nothing.
7. **Breaks remove the latest `until` first; ties go to the newest claim** (latest pay date, then ex-date, market and symbol), **then to its protection added last.** M4 §6.4 fixes only the first key; the rest makes the order total.
8. **`Holdings.claims` and `Holdings.shortfall_since` are its last fields, with defaults, and `DayReport.notes` defaults to `()`.** Every existing positional construction keeps working.
9. **The new figures get terms and a lesson (T1).** The figure walk reaches `DividendClaim` through `RunResult.final`: `DividendClaim.gross` is `term.dividend_gross`, `DividendClaim.uncovered` is `term.claim_to_reinvest` and `Protection.amount` is `term.claim_protected`. The IDX lesson `tax.exemption` explains them and the two note keys, a paragraph per story.
10. **`IncomeReport.claims` is the final holdings' `DividendClaim`s, with `claims_label`** (`CLAIMS_LABEL`). A separate view type would repeat the same fields, which already have terms.
11. **The switch-on golden run needs longer recordings and a scripted trader.** Buy-and-hold never sells, so it cannot break a claim, and the recorded window ends on 31 January 2022, before the first deadline (31 March 2022). Task 0's PR adds Yahoo recordings of the same five stocks to 29 April 2022 (below); S8 adds `ExemptionScript` to `scripts/record_golden.py`, a test fixture that trades on three set days and is not a registered strategy. The buy-and-hold golden file gains the keys `taxes`, `notes`, `claims` and `income.claims`; Task 4 checks that none of its existing values moves.
12. **`protection_end` on a day the exemption does not cover raises `ValueError`.** In a run it cannot: a claim exists only when its ex-date is under the rule, and a purchase that covers it is later still.

## File map

| File | Task | Responsibility |
|---|---|---|
| `tests/fixtures/yahoo/{ASII,BBCA,BBRI,TLKM,UNVR}.JK_2017-01-31_2022-04-29.json` | 0 | The longer recordings for the switch-on golden run |
| `.../steadyhand/market.py`, `.../steadyhand_idx/rules.py`, `fees.py`, `data/fees.toml` | 1 | The reshaped `dividend_tax`, the two date rules and their rows |
| `docs/research/t-tax.md` | 1 | PMK 18/2021's in-force date |
| `.../steadyhand/exemption.py` | 1–3 | `Protection`, `DividendClaim`; `cover_claims`, `settle_claims`, `ClaimDay` |
| `.../steadyhand/corporate.py` | 1, 3 | `Payout`; claims opened at pay; `Holdings.claims` and `shortfall_since` |
| `.../steadyhand/engine.py` | 1–3 | The switch; claims covered and settled each day and carried to the next state |
| `.../steadyhand/terms.py` | 1 | The two claim terms |
| `.../steadyhand/notes.py` | 2, 3 | The two note keys |
| `.../steadyhand/__init__.py` | 1–4 | The exports |
| `.../steadyhand/income.py` | 1, 4 | Calls off the flag; `IncomeReport.claims`, `CLAIMS_LABEL` |
| `.../steadyhand_idx/training/lessons/en/tax.exemption.md` | 1–3 | The claim terms and notes explained |
| `scripts/record_golden.py`, `tests/fixtures/golden/*.json` | 4 | `ExemptionScript`, the switch-on run, the new keys |
| `tests/engine/test_exemption.py` | 1–3 | The claim, cover, deadline, grace and break tests |
| `tests/engine/test_{corporate,engine,income_report,protocols,income_projection}.py`, `tests/idx/test_{fees,rules}.py`, `tests/perf/test_performance.py`, `tests/golden/test_golden_backtest.py` | 1–4 | The switch through the engine, the rules, the fakes, the golden runs |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | This plan, the recordings and the stories | `m4/m4b-plan` |
| 1 | M4b S5 The exemption rules, the switch and the claim | `m4/s5-rules` |
| 2 | M4b S6 Reinvestment matching and the deadline tax | `m4/s6-reinvestment` |
| 3 | M4b S7 Protection, the settlement grace and breaks | `m4/s7-protection` |
| 4 | M4b S8 Claims in the income report and the switch-on golden run | `m4/s8-report` |

Stories merge in order: each one's code builds on the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Merge without asking: Shyden's standing rule of 2026-09-27 covers every green PR into `develop` (never `main`). Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: This plan, the recordings and the stories

On `m4/m4b-plan`, whose PR carries this plan, the five recordings and `HANDOVER.md` (#86).

- [ ] **Step 1: Add the recordings this plan was built from.** They were made on 27 September 2026 with `uv run python scripts/record_yahoo_fixture.py <SYMBOL> 2017-01-31 2022-04-29` for ASII, BBCA, BBRI, TLKM and UNVR, about four seconds apart, and are never edited. Do not record them again: Yahoo cannot be relied on to answer the same way twice, and each file stores the day it was recorded, so a new recording is a different file and moves every figure below. Commit these files and check them against their SHA-256s:

  ```bash
  shasum -a 256 tests/fixtures/yahoo/*_2017-01-31_2022-04-29.json
  ```

  Expected:

  ```text
  15fa960e0faffe6e55cd17e86d88eb1d01797cd81b1c0c26584c5c1c617dc46e  tests/fixtures/yahoo/ASII.JK_2017-01-31_2022-04-29.json
  702b75b37f1248257a2c26dcb2b513d11ecb81949134c45b9c22eb9972460942  tests/fixtures/yahoo/BBCA.JK_2017-01-31_2022-04-29.json
  31188263bcb5e493055c23ad33446da147d337f90838d2d67b610aa4958eebd1  tests/fixtures/yahoo/BBRI.JK_2017-01-31_2022-04-29.json
  cc389ccd88c00dfa260293be1b0faf073934cd86f9d529ce1108047459222a40  tests/fixtures/yahoo/TLKM.JK_2017-01-31_2022-04-29.json
  b7da0598bf3a5ba5e3e5b0f3eb52052aef636bdd9045c4bd9daeee41ed78d7fb  tests/fixtures/yahoo/UNVR.JK_2017-01-31_2022-04-29.json
  ```

- [ ] **Step 2: File the stories.** Create one issue per task 1–4, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 3: Open the PR** from `m4/m4b-plan` into `develop` (`Refs #86`), and merge it as **Merging a story** says.

---

### Task 1: M4b S5 The exemption rules, the switch and the claim

**Acceptance criteria (story text):**
1. PMK 18/2021's in-force date is read from BPK and recorded in `docs/research/t-tax.md`: 17 February 2021 under its Pasal 119, with Pasal 109's refund route noted as not modelled (scope decision 1).
2. `MarketRules.dividend_tax(gross, *, on)` has no flag and returns the full tax. `MarketRules` gains `reinvestment_deadline(ex_date) -> date | None` and `protection_end(purchase_day) -> date` (M4 §6.1). Every test double and `income.py`'s two calls are moved off the flag.
3. IDX reads both from a `dividend_exemption` table in `fees.toml`: no exemption from 2009-01-01, and from 2021-02-17 a deadline at the end of month 3 of the year after the ex-date's and a protection through 31 December of the purchase year + 2, with `verified_from` unchanged (scope decision 2). A row with only one count, a month outside 1–12 or a count below 1 is refused, naming the row.
4. `EngineSettings.dividend_reinvestment_exemption: bool = False`. With it on, a paid dividend whose deadline is on or after the pay day books no tax and opens a `DividendClaim` (instrument, ex-date, pay date, gross, deadline, the part still to reinvest, protections) in `Holdings.claims`; one with no deadline, or a deadline already past, is taxed at pay. `apply_actions` takes a `Payout` (scope decision 3).
5. `DayReport.notes` exists and is empty. With the switch off, every figure and ledger entry the S9 golden test checks is unchanged.
6. `DividendClaim` and `Protection` refuse inconsistent values (dates out of order, a currency other than the stock's, a gross that is not positive, parts that exceed the gross), each with a named message. The new figures have terms, which `tax.exemption` explains.
7. The engine exports the new names. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M140–M148 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/exemption.py`, `tests/engine/test_exemption.py`
- Modify: `.../steadyhand/market.py`, `corporate.py`, `engine.py`, `income.py`, `terms.py`, `__init__.py`; `.../steadyhand_idx/fees.py`, `rules.py`, `data/fees.toml`, `training/lessons/en/tax.exemption.md`; `docs/research/t-tax.md`
- Test: `tests/idx/test_{fees,rules}.py`, `tests/engine/test_{corporate,engine,protocols,income_projection}.py`, `tests/perf/test_performance.py`

**Interfaces:**
- Consumes: M3's `apply_actions`, `Holdings`, `EngineSettings`, `DayReport`; M4a's `income.py`; T1's `FIGURES` and lessons.
- Produces: `MarketRules.dividend_tax(gross, *, on)`, `reinvestment_deadline(ex_date) -> date | None`, `protection_end(purchase_day) -> date`; in `steadyhand_idx.fees`: `Exemption(reinvest_by_month, hold_tax_years)` and `FeeSchedule.dividend_exemption: Dated[Exemption | None]`; `Protection(amount, until)`, `DividendClaim(instrument, ex_date, pay_date, gross, deadline, uncovered, protections=())` (in `steadyhand.exemption`); `Payout(pay_lag_trading_days=14, exemption=False)` and `Holdings.claims` (in `steadyhand.corporate`); `EngineSettings.dividend_reinvestment_exemption`, `DayReport.notes`; `TERM_CLAIM_PROTECTED`, `TERM_CLAIM_TO_REINVEST`.

- [ ] **Step 1: Branch.** `git switch -c m4/s5-rules origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_corporate.py`** (changed: 5 edits)

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python

from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
```
with:
```python

from steadyhand.corporate import (
    PAY_LAG_TRADING_DAYS,
    Entitlement,
    Holdings,
    Payout,
    apply_actions,
)
from steadyhand.exemption import DividendClaim
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
```

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)

```
with:
```python

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return Money.zero(gross.currency)


class _Deadline(IdxMarketRules):
    """IDX, but every dividend's reinvestment deadline is one fixed day."""

    def __init__(self, deadline: date) -> None:
        super().__init__()
        self._deadline = deadline

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        return self._deadline

```

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
    assert kinds == [(MovementKind.DIVIDEND, rp(12_500), PAY), (MovementKind.TAX, rp(-1_250), PAY)]

```
with:
```python
    assert kinds == [(MovementKind.DIVIDEND, rp(12_500), PAY), (MovementKind.TAX, rp(-1_250), PAY)]
    assert outcome.holdings.claims == ()


def test_with_the_exemption_a_paid_dividend_opens_a_claim_instead_of_booking_tax() -> None:
    due = Entitlement(BBCA, EX, PAY, rp(12_500))
    payout = Payout(exemption=True)
    outcome = apply_actions(Holdings(holding(), entitlements=(due,)), [], PAY, rules(), payout)
    assert outcome.paid == (due,)
    assert outcome.tax == rp(0)
    # Ex-date 2 June 2025: reinvest by 31 March 2026, and nothing is reinvested yet.
    claim = DividendClaim(BBCA, EX, PAY, rp(12_500), date(2026, 3, 31), rp(12_500))
    assert outcome.holdings.claims == (claim,)
    ledger = outcome.holdings.portfolio.ledger
    assert [(m.kind, m.amount) for m in ledger] == [(MovementKind.DIVIDEND, rp(12_500))]


def test_a_dividend_from_before_the_rule_is_taxed_at_pay_with_the_switch_on() -> None:
    pay = date(2021, 3, 9)
    early = Entitlement(BBCA, date(2021, 2, 16), pay, rp(12_500))  # the day before PMK 18/2021
    before = Holdings(holding(), entitlements=(early,))
    outcome = apply_actions(before, [], pay, rules(), Payout(exemption=True))
    assert outcome.tax == rp(1_250)
    assert outcome.holdings.claims == ()


@pytest.mark.parametrize(
    ("deadline", "claims", "tax"),
    [(PAY, 1, 0), (date(2025, 6, 23), 0, 1_250)],  # a deadline before the pay day cannot be met
)
def test_a_claim_opens_only_while_its_deadline_can_still_be_met(
    deadline: date, claims: int, tax: int
) -> None:
    due = Entitlement(BBCA, EX, PAY, rp(12_500))
    before = Holdings(holding(), entitlements=(due,))
    outcome = apply_actions(before, [], PAY, _Deadline(deadline), Payout(exemption=True))
    assert len(outcome.holdings.claims) == claims
    assert outcome.tax == rp(tax)


def test_open_claims_are_carried_through_a_day_unchanged() -> None:
    claim = DividendClaim(BBCA, EX, PAY, rp(12_500), date(2026, 3, 31), rp(12_500))
    outcome = apply_actions(Holdings(holding(), claims=(claim,)), [], PAY, rules())
    assert outcome.holdings.claims == (claim,)

```

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        apply_actions(Holdings(holding()), [], EX, rules(), 0)

```
with:
```python
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        Payout(0)
    with pytest.raises(TypeError, match=r"^exemption must be a bool, got int$"):
        Payout(exemption=1)  # type: ignore[arg-type]

```

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
        Holdings(holding(), entitlements=("BBCA",))  # type: ignore[arg-type]
```
with:
```python
        Holdings(holding(), entitlements=("BBCA",))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^claim must be a DividendClaim, got str$"):
        Holdings(holding(), claims=("BBCA",))  # type: ignore[arg-type]
```

**`tests/engine/test_engine.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
)
from steadyhand.money import IDR, Money
```
with:
```python
)
from steadyhand.exemption import DividendClaim
from steadyhand.money import IDR, Money
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
    assert after.holdings.portfolio.cash_balance() == rp(10_000_000 + 12_500 - 1_250)

```
with:
```python
    assert after.holdings.portfolio.cash_balance() == rp(10_000_000 + 12_500 - 1_250)
    assert (report.notes, after.holdings.claims) == ((), ())


def test_with_the_exemption_on_a_dividend_opens_a_claim_the_next_state_keeps() -> None:
    state, _ = day_one()
    due = Entitlement(BBCA, D1, D2, rp(12_500))
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)), state.units, Halt(D1, "test"), D1
    )
    exempt = EngineSettings(dividend_reinvestment_exemption=True)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    after, report = run_day(halted, inputs, _Untouchable(), rules(), exempt)
    assert (report.paid, report.tax, report.notes) == ((due,), rp(0), ())
    assert after.holdings.portfolio.cash_balance() == rp(10_000_000 + 12_500)  # no tax booked
    claim = DividendClaim(BBCA, D1, D2, rp(12_500), date(2026, 3, 31), rp(12_500))
    assert after.holdings.claims == (claim,)
    later, _ = run_day(after, DayInputs(D3, steady(), members=MEMBERS), _Untouchable(), rules())
    assert later.holdings.claims == (claim,)

```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
        EngineSettings(limits=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^holdings must be a Holdings, got NoneType$"):
```
with:
```python
        EngineSettings(limits=None)  # type: ignore[arg-type]
    with pytest.raises(
        TypeError, match=r"^dividend_reinvestment_exemption must be a bool, got str$"
    ):
        EngineSettings(dividend_reinvestment_exemption="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^holdings must be a Holdings, got NoneType$"):
```

**`tests/engine/test_exemption.py`** (new)

<!-- file: tests/engine/test_exemption.py -->
```python
"""The reinvestment exemption's claims and their bookkeeping (M4 spec §6)."""

from datetime import date

import pytest

from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import Instrument

BBCA = Instrument("BBCA", "IDX", IDR)
EX = date(2025, 6, 2)
PAY = date(2025, 6, 24)
DEADLINE = date(2026, 3, 31)
USD = Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def claim(uncovered: int = 1_000, *protections: Protection) -> DividendClaim:
    return DividendClaim(BBCA, EX, PAY, rp(1_000), DEADLINE, rp(uncovered), protections)


def test_a_claim_may_be_split_between_uncovered_and_protected_parts() -> None:
    until = date(2027, 12, 31)
    split = claim(400, Protection(rp(250), until), Protection(rp(350), until))
    assert split.uncovered == rp(400)
    assert sum(p.amount.amount for p in split.protections) == 600  # 400 + 600 = the gross 1,000


def test_a_protection_is_a_positive_amount_with_a_date() -> None:
    with pytest.raises(ValueError, match=r"^a protection must be positive, got IDR 0$"):
        Protection(rp(0), DEADLINE)
    with pytest.raises(TypeError, match=r"^amount must be a Money, got int$"):
        Protection(1, DEADLINE)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^until must be a date"):
        Protection(rp(1), "2027-12-31")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("ex_date", "pay_date", "deadline"),
    [(PAY, PAY, DEADLINE), (EX, PAY, date(2025, 6, 23))],
)
def test_a_claim_is_paid_after_its_ex_date_and_no_later_than_its_deadline(
    ex_date: date, pay_date: date, deadline: date
) -> None:
    with pytest.raises(ValueError, match=r"^BBCA: a claim needs ex-date < pay date <= deadline"):
        DividendClaim(BBCA, ex_date, pay_date, rp(1_000), deadline, rp(1_000))


def test_a_claim_on_its_deadline_day_is_valid() -> None:
    assert DividendClaim(BBCA, EX, PAY, rp(1_000), PAY, rp(1_000)).deadline == PAY


def test_a_claims_amounts_are_in_its_stocks_currency() -> None:
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        DividendClaim(BBCA, EX, PAY, Money(1_000, USD), DEADLINE, rp(1_000))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        DividendClaim(BBCA, EX, PAY, rp(1_000), DEADLINE, Money(1_000, USD))
    with pytest.raises(CurrencyMismatchError):
        claim(0, Protection(Money(1, USD), DEADLINE))


@pytest.mark.parametrize(("gross", "uncovered"), [(0, 0), (1_000, -1)])
def test_a_claims_gross_is_positive_and_its_uncovered_part_not_negative(
    gross: int, uncovered: int
) -> None:
    with pytest.raises(
        ValueError,
        match=r"^BBCA: a claim's gross must be positive and its uncovered part not negative$",
    ):
        DividendClaim(BBCA, EX, PAY, rp(gross), DEADLINE, rp(uncovered))


def test_a_claims_parts_cannot_exceed_its_gross() -> None:
    until = date(2027, 12, 31)
    with pytest.raises(
        ValueError,
        match=(
            r"^BBCA: uncovered IDR 401 and protected IDR 600 exceed the gross dividend "
            r"IDR 1,000$"
        ),
    ):
        claim(401, Protection(rp(600), until))
    with pytest.raises(TypeError, match=r"^protection must be a Protection, got str$"):
        claim(0, "all of it")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^instrument must be an Instrument"):
        DividendClaim("BBCA", EX, PAY, rp(1_000), DEADLINE, rp(1_000))  # type: ignore[arg-type]
```

**`tests/engine/test_income_projection.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_income_projection.py -->
Replace:
```python

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)
```
with:
```python

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return Money.zero(gross.currency)
```

**`tests/engine/test_protocols.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)

```
with:
```python

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return Money.zero(gross.currency)

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        return None

    def protection_end(self, purchase_day: date) -> date:
        return purchase_day

```

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python

def test_a_minimal_class_satisfies_data_source() -> None:
```
with:
```python

@pytest.mark.parametrize("member", ["reinvestment_deadline", "protection_end"])
def test_each_member_added_in_m4_is_required(member: str) -> None:
    members = {name: value for name, value in vars(_MinimalRules).items() if name != member}
    assert not isinstance(type("Partial", (), members)(), MarketRules)


def test_a_minimal_class_satisfies_data_source() -> None:
```

**`tests/idx/test_fees.py`** (changed: 5 edits)

<!-- edit: tests/idx/test_fees.py -->
Replace:
```python
from steadyhand_idx._datafile import DataFileError, load_shipped
from steadyhand_idx.fees import BrokerPreset, FeeSchedule, parse_fees

```
with:
```python
from steadyhand_idx._datafile import DataFileError, load_shipped
from steadyhand_idx.fees import BrokerPreset, Exemption, FeeSchedule, parse_fees

```

<!-- edit: tests/idx/test_fees.py -->
Replace:
```python
        date(2009, 1, 1),  # dividend tax
    ]
```
with:
```python
        date(2009, 1, 1),  # dividend tax
        date(2009, 1, 1),  # dividend exemption: none until PMK 18/2021
    ]
```

<!-- edit: tests/idx/test_fees.py -->
Replace:
```python
    with pytest.raises(ValueError, match=r"^gross must be a non-negative IDR amount, got IDR -1$"):
        fees().dividend_tax(rp(-1), reinvested_by_deadline=False, on=TODAY)
    with pytest.raises(ValueError, match=r"got USD 1\.00"):
        fees().dividend_tax(Money(100, Currency("USD", 2)), reinvested_by_deadline=True, on=TODAY)

```
with:
```python
    with pytest.raises(ValueError, match=r"^gross must be a non-negative IDR amount, got IDR -1$"):
        fees().dividend_tax(rp(-1), on=TODAY)
    with pytest.raises(ValueError, match=r"got USD 1\.00"):
        fees().dividend_tax(Money(100, Currency("USD", 2)), on=TODAY)

```

<!-- edit: tests/idx/test_fees.py -->
Replace:
```python

def test_dividend_tax_is_ten_percent_rounded_up_unless_reinvested() -> None:
    assert fees().dividend_tax(rp(1_000_000), reinvested_by_deadline=False, on=TODAY) == rp(100_000)
    assert fees().dividend_tax(rp(999), reinvested_by_deadline=False, on=TODAY) == rp(100)
    assert fees().dividend_tax(rp(999), reinvested_by_deadline=True, on=TODAY) == rp(0)

```
with:
```python

def test_dividend_tax_is_the_full_ten_percent_rounded_up() -> None:
    assert fees().dividend_tax(rp(1_000_000), on=TODAY) == rp(100_000)
    assert fees().dividend_tax(rp(999), on=TODAY) == rp(100)  # 99.9 rounds up to 100
    assert fees().dividend_tax(rp(0), on=TODAY) == rp(0)


def test_the_exemption_starts_when_pmk_18_2021_came_into_force() -> None:
    # PMK 18/PMK.03/2021 Pasal 119: in force when promulgated, on 17 February 2021.
    assert fees().dividend_exemption.starts == (date(2009, 1, 1), date(2021, 2, 17))
    assert fees().dividend_exemption.values == (None, Exemption(3, 3))


@pytest.mark.parametrize(
    ("ex_date", "deadline"),
    [
        (date(2021, 2, 16), None),  # the day before PMK 18/2021
        (date(2021, 2, 17), date(2022, 3, 31)),
        (date(2026, 5, 20), date(2027, 3, 31)),  # t-tax.md §4's worked example
        (date(2026, 12, 31), date(2027, 3, 31)),
        (date(2027, 1, 4), date(2028, 3, 31)),
    ],
)
def test_the_reinvestment_deadline_is_the_end_of_march_after_the_ex_date_year(
    ex_date: date, deadline: date | None
) -> None:
    assert fees().reinvestment_deadline(ex_date) == deadline


def test_the_deadline_is_the_last_day_of_its_month() -> None:
    document = _document()
    exemption = document["dividend_exemption"]
    assert isinstance(exemption, list)
    exemption[1]["reinvest_by_month"] = 2
    february = parse_fees(document)
    assert february.reinvestment_deadline(date(2023, 6, 1)) == date(2024, 2, 29)  # a leap year
    assert february.reinvestment_deadline(date(2024, 6, 1)) == date(2025, 2, 28)


@pytest.mark.parametrize(
    ("purchase", "until"),
    [
        (date(2021, 2, 17), date(2023, 12, 31)),
        (date(2027, 3, 10), date(2029, 12, 31)),  # M4 spec §2's correction: 2027, 2028 and 2029
        (date(2026, 12, 31), date(2028, 12, 31)),
    ],
)
def test_protection_lasts_three_tax_years_counting_the_purchase_year(
    purchase: date, until: date
) -> None:
    assert fees().protection_end(purchase) == until


def test_no_protection_ends_for_a_purchase_the_exemption_does_not_cover() -> None:
    with pytest.raises(
        ValueError, match=r"^no reinvestment exemption applies to a purchase on 2021-02-16$"
    ):
        fees().protection_end(date(2021, 2, 16))
    with pytest.raises(
        UnsupportedDateError, match=r"^fees\.toml \[dividend_exemption\] has no verified row"
    ):
        fees().reinvestment_deadline(date(2008, 12, 31))

```

<!-- edit: tests/idx/test_fees.py -->
Replace:
```python
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'levies'"):
        parse_fees(document)
```
with:
```python
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'levies'"):
        parse_fees(document)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"hold_tax_years": None},
            r"row 2: an exemption row gives both counts or neither, and lacks 'hold_tax_years'$",
        ),
        (
            {"reinvest_by_month": None},
            r"row 2: an exemption row gives both counts or neither, and lacks 'reinvest_by_month'$",
        ),
        (
            {"reinvest_by_month": 13},
            r"row 2: reinvest_by_month must be a month from 1 to 12, got 13$",
        ),
        ({"reinvest_by_month": 0}, r"row 2: reinvest_by_month must be an integer of at least 1"),
        ({"hold_tax_years": 0}, r"row 2: hold_tax_years must be an integer of at least 1"),
        ({"months": 3}, r"row 2: unknown key 'months'$"),
    ],
)
def test_bad_exemption_rows_are_refused(change: dict[str, object], message: str) -> None:
    document = _document()
    exemption = document["dividend_exemption"]
    assert isinstance(exemption, list)
    row = exemption[1]
    for key, value in change.items():
        if value is None:
            del row[key]
        else:
            row[key] = value
    with pytest.raises(DataFileError, match=r"^fees\.toml \[\[dividend_exemption\]\] " + message):
        parse_fees(document)
```

**`tests/idx/test_rules.py`** (changed: 3 edits)

<!-- edit: tests/idx/test_rules.py -->
Replace:
```python
        lambda: rules().settlement_date(date(2020, 12, 30)),
        lambda: rules().dividend_tax(rp(1000), reinvested_by_deadline=False, on=date(2020, 12, 31)),
        lambda: rules().is_trading_day(date(2020, 12, 31)),
```
with:
```python
        lambda: rules().settlement_date(date(2020, 12, 30)),
        lambda: rules().dividend_tax(rp(1000), on=date(2020, 12, 31)),
        lambda: rules().reinvestment_deadline(date(2020, 12, 31)),
        lambda: rules().protection_end(date(2020, 12, 31)),
        lambda: rules().is_trading_day(date(2020, 12, 31)),
```

<!-- edit: tests/idx/test_rules.py -->
Replace:
```python
    with pytest.raises(ValueError, match=r"^gross must be in IDR"):
        rules().dividend_tax(Money(1, usd), reinvested_by_deadline=False, on=TODAY)

```
with:
```python
    with pytest.raises(ValueError, match=r"^gross must be in IDR"):
        rules().dividend_tax(Money(1, usd), on=TODAY)


def test_the_exemption_dates_come_from_the_fee_tables() -> None:
    assert rules().reinvestment_deadline(date(2021, 2, 16)) is None
    assert rules().reinvestment_deadline(TODAY) == date(2027, 3, 31)
    assert rules().protection_end(TODAY) == date(2028, 12, 31)

```

<!-- edit: tests/idx/test_rules.py -->
Replace:
```python
def test_dividend_tax_and_trading_days() -> None:
    assert rules().dividend_tax(rp(1_000), reinvested_by_deadline=False, on=TODAY) == rp(100)
    assert rules().is_trading_day(date(2021, 1, 4))
```
with:
```python
def test_dividend_tax_and_trading_days() -> None:
    assert rules().dividend_tax(rp(1_000), on=TODAY) == rp(100)
    assert rules().is_trading_day(date(2021, 1, 4))
```

**`tests/perf/test_performance.py`** (changed: 1 edit)

<!-- edit: tests/perf/test_performance.py -->
Replace:
```python

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return gross.times(Decimal("0.1"), Rounding.UP)

```
with:
```python

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return gross.times(Decimal("0.1"), Rounding.UP)

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        return None

    def protection_end(self, purchase_day: date) -> date:
        return purchase_day

```


- [ ] **Step 3: Write the stubs.** New names only: every function that existed keeps its current body, and every class that existed its current fields.

**`packages/steadyhand-idx/src/steadyhand_idx/fees.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python

from collections.abc import Callable, Mapping
```
with:
```python

import calendar
from collections.abc import Callable, Mapping
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
_HUNDRED = Decimal(100)

```
with:
```python
_HUNDRED = Decimal(100)
_MONTHS = 12

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
    tax: Decimal

```
with:
```python
    tax: Decimal


@dataclass(frozen=True, slots=True)
class Exemption:
    """The reinvestment exemption's two counts (docs/research/t-tax.md §3).

    A dividend is exempt when it is reinvested by the end of month ``reinvest_by_month`` of the
    year after it is received, and the investment is held for ``hold_tax_years`` tax years,
    counting the year it is made.
    """

    reinvest_by_month: int
    hold_tax_years: int

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python

    def _check_quote_covers_what_it_includes(self, preset: BrokerPreset) -> None:
```
with:
```python

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        """The last day to reinvest a dividend with *ex_date*, or ``None`` if it cannot be exempt.

        The deadline counts from the ex-date's year, which is never later than the year the
        dividend is really paid (docs/research/t-pay.md §4), so it errs early.
        """
        raise NotImplementedError("FeeSchedule.reinvestment_deadline")

    def protection_end(self, purchase_day: date) -> date:
        """The last day an investment made on *purchase_day* must stay held to keep its claim."""
        raise NotImplementedError("FeeSchedule.protection_end")

    def _check_quote_covers_what_it_includes(self, preset: BrokerPreset) -> None:
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
    return get_decimal(row, "rate_percent", where)

```
with:
```python
    return get_decimal(row, "rate_percent", where)


def _exemption(row: Row, where: Where) -> Exemption | None:
    raise NotImplementedError("_exemption")

```

**`packages/steadyhand-idx/src/steadyhand_idx/rules.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/rules.py -->
Replace:
```python

    def is_trading_day(self, day: date) -> bool:
```
with:
```python

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        raise NotImplementedError("IdxMarketRules.reinvestment_deadline")

    def protection_end(self, purchase_day: date) -> date:
        raise NotImplementedError("IdxMarketRules.protection_end")

    def is_trading_day(self, day: date) -> bool:
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 7 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    Holdings,
    apply_actions,
```
with:
```python
    Holdings,
    Payout,
    apply_actions,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.income import (
```
with:
```python
)
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.income import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    TERM_CASH_MOVEMENT,
    TERM_CONTRIBUTION,
```
with:
```python
    TERM_CASH_MOVEMENT,
    TERM_CLAIM_PROTECTED,
    TERM_CLAIM_TO_REINVEST,
    TERM_CONTRIBUTION,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "TERM_CASH_MOVEMENT",
    "TERM_CONTRIBUTION",
```
with:
```python
    "TERM_CASH_MOVEMENT",
    "TERM_CLAIM_PROTECTED",
    "TERM_CLAIM_TO_REINVEST",
    "TERM_CONTRIBUTION",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Decision",
    "DividendGrowth",
```
with:
```python
    "Decision",
    "DividendClaim",
    "DividendGrowth",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "PaymentCalendar",
    "Portfolio",
```
with:
```python
    "PaymentCalendar",
    "Payout",
    "Portfolio",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "ProjectionOutcome",
    "ReceivedIncome",
```
with:
```python
    "ProjectionOutcome",
    "Protection",
    "ReceivedIncome",
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules, add_trading_days
```
with:
```python
from steadyhand._validate import require_date, require_int, require_type
from steadyhand.exemption import DividendClaim
from steadyhand.market import MarketRules, add_trading_days
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
            raise ValueError(msg)

```
with:
```python
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Payout:
    """How dividends are paid: trading days from ex-date to pay date, and whether the tax on
    one that can be exempt waits on a ``DividendClaim`` (M4 spec §6.2) instead of being booked.
    """

    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS
    exemption: bool = False

    def __post_init__(self) -> None:
        raise NotImplementedError("Payout.__post_init__")

```

**`packages/steadyhand/src/steadyhand/engine.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
from steadyhand.broker.simulated import FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.market import MarketRules
```
with:
```python
from steadyhand.broker.simulated import FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import (
    PAY_LAG_TRADING_DAYS,
    Entitlement,
    Holdings,
    Payout,
    apply_actions,
)
from steadyhand.market import MarketRules
```

**`packages/steadyhand/src/steadyhand/exemption.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/exemption.py -->
```python
"""The dividend reinvestment exemption as claims the engine keeps (M4 spec §6).

With ``EngineSettings.dividend_reinvestment_exemption`` on, a dividend that can be exempt books no
tax when it is paid. It opens a ``DividendClaim`` instead, which the engine carries in
``Holdings.claims`` until its reinvestment and holding conditions are met or broken. Every figure
a claim gives is an estimate: it assumes the investor files the annual realisation reports
(docs/research/t-tax.md §7), which the engine cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Instrument


@dataclass(frozen=True, slots=True)
class Protection:
    """Part of a claim reinvested by one purchase, which must stay invested through ``until``."""

    amount: Money
    until: date

    def __post_init__(self) -> None:
        raise NotImplementedError("Protection.__post_init__")


@dataclass(frozen=True, slots=True)
class DividendClaim:
    """A paid dividend whose tax waits on its reinvestment (M4 spec §6.2).

    ``uncovered`` is the part of ``gross`` not yet reinvested. ``protections`` are the reinvested
    parts, each held through its own date. Together they never exceed ``gross``.
    """

    instrument: Instrument
    ex_date: date
    pay_date: date
    gross: Money
    deadline: date
    uncovered: Money
    protections: tuple[Protection, ...] = ()

    def __post_init__(self) -> None:
        raise NotImplementedError("DividendClaim.__post_init__")
```

**`packages/steadyhand/src/steadyhand/market.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python

    def is_trading_day(self, day: date) -> bool:
```
with:
```python

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        """The last day a dividend with *ex_date* may be reinvested to be exempt from its tax.

        ``None`` where the market has no such exemption for that ex-date (M4 spec §6.1).
        """
        ...

    def protection_end(self, purchase_day: date) -> date:
        """The last day an investment made on *purchase_day* must stay held to keep its claim."""
        ...

    def is_trading_day(self, day: date) -> bool:
```

**`packages/steadyhand/src/steadyhand/terms.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/terms.py -->
Replace:
```python
"""One change to cash: positive when money comes in, negative when it goes out."""

```
with:
```python
"""One change to cash: positive when money comes in, negative when it goes out."""

TERM_CLAIM_PROTECTED = "term.claim_protected"
"""Part of a dividend claim reinvested by a purchase, which must stay invested until a date."""

TERM_CLAIM_TO_REINVEST = "term.claim_to_reinvest"
"""The part of a dividend claim not yet reinvested, which is taxed if its deadline passes."""

```

<!-- edit: packages/steadyhand/src/steadyhand/terms.py -->
Replace:
```python
        "DayReport.value": TERM_PORTFOLIO_VALUE,
        "DividendGrowth.portfolio": TERM_DIVIDEND_GROWTH,
```
with:
```python
        "DayReport.value": TERM_PORTFOLIO_VALUE,
        "DividendClaim.gross": TERM_DIVIDEND_GROSS,
        "DividendClaim.uncovered": TERM_CLAIM_TO_REINVEST,
        "DividendGrowth.portfolio": TERM_DIVIDEND_GROWTH,
```

<!-- edit: packages/steadyhand/src/steadyhand/terms.py -->
Replace:
```python
        "Projection.target": TERM_INCOME_TARGET,
        "ReceivedIncome.current_yield": TERM_CURRENT_YIELD,
```
with:
```python
        "Projection.target": TERM_INCOME_TARGET,
        "Protection.amount": TERM_CLAIM_PROTECTED,
        "ReceivedIncome.current_yield": TERM_CURRENT_YIELD,
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1021 failed=51 -->
Expected: 1021 run, 51 failed, each on its own line. 27 are `NotImplementedError`: `DividendClaim` and `Protection` are stubs, and so are `Payout` and the two new rules. The other 24 are the new shape meeting old code, since every pre-existing function and class keeps its base text: nine `TypeError`s, eight where a test calls `dividend_tax` without the flag or the base code calls a test double's new signature with it (in `test_fees.py`, `test_rules.py`, `test_corporate.py` and `test_income_projection.py`) and one where `EngineSettings` refuses the new keyword; seven `KeyError: 'dividend_exemption'` from the shipped `fees.toml`, which gains the table in Step 5; three `AttributeError`s (`FeeSchedule.dividend_exemption`, `Holdings.claims`, `DayReport.notes`); and five `AssertionError`s: the tables' first dates, two `pytest.raises` whose message does not match, a term with no lesson yet, and a `FIGURES` entry the walk cannot reach until `Holdings` carries claims. Nine cases pass against the stubs by design: seven are the unchanged cases of `test_every_rule_refuses_an_unverified_day`, whose list gained two, and two are `test_each_member_added_in_m4_is_required`, since a protocol's `...` members are declarations, not stubs.

- [ ] **Step 5: Implement.** The data rows, the research record and the lesson are part of this step.

**`docs/research/t-tax.md`** (changed: 3 edits)

<!-- edit: docs/research/t-tax.md -->
Replace:
```markdown
| PP 9/2021 | PP 9/2021 (the Cipta Kerja income tax regulation that first implemented the exemption UU 11/2020 created) | 2021 | partially revoked | Details/161839 · Download/244291 |
| **PMK 18/2021** | PMK 18/PMK.03/2021, implementing UU 11/2020 (Cipta Kerja) for income tax | 2021 | | Details/162653 · Download/155338 and 155339 |
| **PMK 81/2024** | PMK 81 Tahun 2024 (tax administration, consolidating earlier PMKs) | set 14 Oct 2024, promulgated 18 Oct 2024 | **1 Jan 2025** | Details/306614 · Download/366884 |
```
with:
```markdown
| PP 9/2021 | PP 9/2021 (the Cipta Kerja income tax regulation that first implemented the exemption UU 11/2020 created) | 2021 | partially revoked | Details/161839 · Download/244291 |
| **PMK 18/2021** | PMK 18/PMK.03/2021, implementing UU 11/2020 (Cipta Kerja) for income tax | set and promulgated 17 Feb 2021 | on promulgation, **17 Feb 2021** (Pasal 119) | Details/162653 · Download/155338 and 155339 |
| **PMK 81/2024** | PMK 81 Tahun 2024 (tax administration, consolidating earlier PMKs) | set 14 Oct 2024, promulgated 18 Oct 2024 | **1 Jan 2025** | Details/306614 · Download/366884 |
```

<!-- edit: docs/research/t-tax.md -->
Replace:
```markdown

**Also unverified:** that a dividend is "received" (*diterima atau diperoleh*) on its **pay date**. UU HPP delegates *"penetapan saat diperolehnya dividen"* to a government regulation, and that text was not read for this ticket. The engine uses the pay date.
```
with:
```markdown

**PMK 18/2021's start (read 2026-09-27 for M4b S5).** Pasal 119: *"Peraturan Menteri ini mulai berlaku pada tanggal diundangkan."* Page 158: *"Diundangkan di Jakarta pada tanggal 17 Februari 2021"*, Berita Negara 2021 Nomor 153. BPK's page gives the same date for setting, promulgation and entry into force. The transitional Pasal 109(1) reaches back further: tax withheld on a domestic dividend *"yang diterima atau diperoleh Wajib Pajak sejak berlakunya Undang-Undang Nomor 11 Tahun 2020 tentang Cipta Kerja"* and exempt under Pasal 15 may be reclaimed as tax not owed. The PMK's own attachment dates UU 11/2020's entry into force to *"tanggal 2 November 2020"*. That is a refund route for tax already withheld, not the claim the engine models, so steadyhand's rule starts on 17 Feb 2021 and applies to a dividend whose ex-date is on or after it. Both choices can only tax more than the law requires.

**Also unverified:** that a dividend is "received" (*diterima atau diperoleh*) on its **pay date**. UU HPP delegates *"penetapan saat diperolehnya dividen"* to a government regulation, and that text was not read for this ticket. The engine uses the pay date.
```

<!-- edit: docs/research/t-tax.md -->
Replace:
```markdown
- **Pass 4 (2026-09-25):** mechanical checks re-run (24 of 24 quotes with the negative control missing; every AC tag present), then a full read. **0 findings. Loop closed.**
```
with:
```markdown
- **Pass 4 (2026-09-25):** mechanical checks re-run (24 of 24 quotes with the negative control missing; every AC tag present), then a full read. **0 findings. Loop closed.**
- **Addendum (2026-09-27, M4b S5):** PMK 18/2021's in-force date, left blank above, was read from BPK's Download/155338 (158 pages, `%%EOF` present): Pasal 119 and page 158, quoted in §6. Pasal 109's transitional refund is recorded there too.
```

**`packages/steadyhand-idx/src/steadyhand_idx/data/fees.toml`** (changed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/data/fees.toml -->
Replace:
```toml

# Broker presets. `includes` lists what the quoted rate already contains, from "levy",
```
with:
```toml

# The reinvestment exemption (docs/research/t-tax.md §3). A row with neither count means no
# exemption applies to a dividend whose ex-date falls on or after its `from`. A row with both
# gives the deadline, the end of month `reinvest_by_month` of the year after the ex-date's year,
# and the holding period, `hold_tax_years` tax years counting the purchase year.

[[dividend_exemption]]
from = 2009-01-01
source = "No reinvestment exemption for resident individuals before PMK 18/2021 (docs/research/t-tax.md §6)"

[[dividend_exemption]]
from = 2021-02-17
source = "PMK 18/PMK.03/2021 Pasal 36(1)(a) and 36(2), in force 17 Feb 2021 under its Pasal 119 (docs/research/t-tax.md §2, §3)"
reinvest_by_month = 3
hold_tax_years = 3

# Broker presets. `includes` lists what the quoted rate already contains, from "levy",
```

**`packages/steadyhand-idx/src/steadyhand_idx/fees.py`** (implemented: 7 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
    dividend_tax_rate: Dated[Decimal]
    presets: Mapping[str, BrokerPreset]
```
with:
```python
    dividend_tax_rate: Dated[Decimal]
    dividend_exemption: Dated[Exemption | None]
    presets: Mapping[str, BrokerPreset]
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
        """Every dated table, for working out the first day all of them are verified."""
        return (self.levy, self.vat, self.sale_tax, self.stamp_duty, self.dividend_tax_rate)

```
with:
```python
        """Every dated table, for working out the first day all of them are verified."""
        return (
            self.levy,
            self.vat,
            self.sale_tax,
            self.stamp_duty,
            self.dividend_tax_rate,
            self.dividend_exemption,
        )

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """10% of a gross dividend, or nothing when it is reinvested by the deadline.

        M4 replaces the flag with a read of the dividend's exemption claim (spec §6.2).
        """
        _require_rupiah(gross, "gross")
        rate = self.dividend_tax_rate.on(on)
        if reinvested_by_deadline:
            return Money.zero(gross.currency)
        return gross.times(rate / _HUNDRED, Rounding.UP)
```
with:
```python

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        """The full tax on a gross dividend paid on *on*, rounded up to the rupiah.

        The reinvestment exemption is the engine's claim bookkeeping, not a discount here.
        """
        _require_rupiah(gross, "gross")
        rate = self.dividend_tax_rate.on(on)
        return gross.times(rate / _HUNDRED, Rounding.UP)
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
        """
        raise NotImplementedError("FeeSchedule.reinvestment_deadline")

    def protection_end(self, purchase_day: date) -> date:
        """The last day an investment made on *purchase_day* must stay held to keep its claim."""
        raise NotImplementedError("FeeSchedule.protection_end")

```
with:
```python
        """
        exemption = self.dividend_exemption.on(ex_date)
        if exemption is None:
            return None
        year = ex_date.year + 1
        month = exemption.reinvest_by_month
        return date(year, month, calendar.monthrange(year, month)[1])

    def protection_end(self, purchase_day: date) -> date:
        """The last day an investment made on *purchase_day* must stay held to keep its claim."""
        exemption = self.dividend_exemption.on(purchase_day)
        if exemption is None:
            msg = f"no reinvestment exemption applies to a purchase on {purchase_day.isoformat()}"
            raise ValueError(msg)
        return date(purchase_day.year + exemption.hold_tax_years - 1, 12, 31)

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
def _exemption(row: Row, where: Where) -> Exemption | None:
    raise NotImplementedError("_exemption")

```
with:
```python
def _exemption(row: Row, where: Where) -> Exemption | None:
    counts = {"reinvest_by_month", "hold_tax_years"}
    present = counts & set(row)
    if not present:
        return None
    if present != counts:
        missing = sorted(counts - present)[0]
        msg = f"{where}: an exemption row gives both counts or neither, and lacks {missing!r}"
        raise DataFileError(msg)
    month = get_int(row, "reinvest_by_month", where, minimum=1)
    if month > _MONTHS:
        msg = f"{where}: reinvest_by_month must be a month from 1 to 12, got {month}"
        raise DataFileError(msg)
    return Exemption(month, get_int(row, "hold_tax_years", where, minimum=1))

```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
    require_schema(document, file, 1)
    tables = {"levy", "vat", "sale_tax", "stamp_duty", "dividend_tax", "presets"}
    only_keys(document, {"schema", *tables}, Where(file, "top level"))
```
with:
```python
    require_schema(document, file, 1)
    tables = {
        "levy",
        "vat",
        "sale_tax",
        "stamp_duty",
        "dividend_tax",
        "dividend_exemption",
        "presets",
    }
    only_keys(document, {"schema", *tables}, Where(file, "top level"))
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/fees.py -->
Replace:
```python
        dividend_tax_rate=_dated(document, "dividend_tax", {"rate_percent"}, _rate, file),
        presets=MappingProxyType({name: _preset(name, row, file) for name, row in presets.items()}),
```
with:
```python
        dividend_tax_rate=_dated(document, "dividend_tax", {"rate_percent"}, _rate, file),
        dividend_exemption=_dated(
            document,
            "dividend_exemption",
            {"reinvest_by_month", "hold_tax_years"},
            _exemption,
            file,
        ),
        presets=MappingProxyType({name: _preset(name, row, file) for name, row in presets.items()}),
```

**`packages/steadyhand-idx/src/steadyhand_idx/rules.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/rules.py -->
Replace:
```python

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        self.require_supported(on)
        self._check_money(gross, "gross")
        return self._tables.fees.dividend_tax(
            gross, reinvested_by_deadline=reinvested_by_deadline, on=on
        )

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        raise NotImplementedError("IdxMarketRules.reinvestment_deadline")

    def protection_end(self, purchase_day: date) -> date:
        raise NotImplementedError("IdxMarketRules.protection_end")

```
with:
```python

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        self.require_supported(on)
        self._check_money(gross, "gross")
        return self._tables.fees.dividend_tax(gross, on=on)

    def reinvestment_deadline(self, ex_date: date) -> date | None:
        self.require_supported(ex_date)
        return self._tables.fees.reinvestment_deadline(ex_date)

    def protection_end(self, purchase_day: date) -> date:
        self.require_supported(purchase_day)
        return self._tables.fees.protection_end(purchase_day)

```

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md`** (changed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md -->
Replace:
```markdown
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = []
module = "costs-and-tax"
position = 5
see_also = ["tax.dividend"]
sources = ["docs/research/t-tax.md §3", "docs/research/t-tax.md §4", "docs/research/t-tax.md §5"]
+++
```
with:
```markdown
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = ["term.claim_to_reinvest", "term.claim_protected"]
module = "costs-and-tax"
position = 5
see_also = ["tax.dividend"]
sources = ["docs/research/t-tax.md §3", "docs/research/t-tax.md §4", "docs/research/t-tax.md §5", "docs/superpowers/specs/2026-09-26-m4-income-design.md §6"]
+++
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md -->
Replace:
```markdown
steadyhand cannot see your paperwork, or any investment you hold outside it. That is why it books
the full 10% by default: its income figures can only be too low, never too high. This lesson
describes the rules; whether they apply to you, and how, is a question for you or a tax adviser.
```
with:
```markdown
steadyhand cannot see your paperwork, or any investment you hold outside it. That is why it books
the full 10% by default: its income figures can only be too low, never too high.

With the exemption switch on, steadyhand books no tax when a dividend is paid. It opens a claim
for the dividend instead, and every figure the claim gives is an estimate:

- **To reinvest** is the part of the dividend not yet invested. A dividend whose ex-date is
  before 17 February 2021, when the rule came into force, gets no claim and is taxed as usual.
- **Protected** is a part that a purchase has reinvested, with the last day it must stay
  invested: 31 December of the second year after the purchase.

This lesson describes the rules; whether they apply to you, and how, is a question for you or a
tax adviser.
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (implemented: 9 edits)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
    def __post_init__(self) -> None:
        raise NotImplementedError("Payout.__post_init__")

```
with:
```python
    def __post_init__(self) -> None:
        require_int(self.pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
        require_type(self.exemption, bool, "exemption")

```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
    its reason, and ``last_closes`` the last close of each held stock, which values it on a
    day with no bar.
    """
```
with:
```python
    its reason, and ``last_closes`` the last close of each held stock, which values it on a
    day with no bar. ``claims`` are the open reinvestment-exemption claims (M4 spec §6.2).
    """
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
    last_closes: Mapping[Instrument, Money] = field(default_factory=dict)

```
with:
```python
    last_closes: Mapping[Instrument, Money] = field(default_factory=dict)
    claims: tuple[DividendClaim, ...] = ()

```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
            require_type(entitlement, Entitlement, "entitlement")

```
with:
```python
            require_type(entitlement, Entitlement, "entitlement")
        for claim in self.claims:
            require_type(claim, DividendClaim, "claim")

```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
    rules: MarketRules,
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS,
) -> CorporateOutcome:
    """Apply *actions*, every one of them with its ex-date on *day*, to *holdings*."""
    require_int(pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
    for action in actions:
```
with:
```python
    rules: MarketRules,
    payout: Payout | None = None,
) -> CorporateOutcome:
    """Apply *actions*, every one of them with its ex-date on *day*, to *holdings*."""
    payout = Payout() if payout is None else payout
    for action in actions:
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
        if isinstance(action, CashDividend):
            run.entitle(action, add_trading_days(rules, day, pay_lag_trading_days))
    run.pay(rules)
    for action in actions:
```
with:
```python
        if isinstance(action, CashDividend):
            run.entitle(action, add_trading_days(rules, day, payout.pay_lag_trading_days))
    run.pay(rules, exemption=payout.exemption)
    for action in actions:
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
        self._entitlements = list(holdings.entitlements)
        self._frozen = dict(holdings.frozen)
```
with:
```python
        self._entitlements = list(holdings.entitlements)
        self._claims = list(holdings.claims)
        self._frozen = dict(holdings.frozen)
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python

    def pay(self, rules: MarketRules) -> None:
        for entitlement in [e for e in self._entitlements if e.pay_date <= self._day]:
            self._entitlements.remove(entitlement)
            self._portfolio = self._portfolio.credit_dividend(entitlement.gross, self._day)
            tax = rules.dividend_tax(entitlement.gross, reinvested_by_deadline=False, on=self._day)
            if tax.amount > 0:
                self._portfolio = self._portfolio.charge(MovementKind.TAX, tax, self._day)
                self._tax += tax
            self._paid.append(entitlement)

```
with:
```python

    def pay(self, rules: MarketRules, *, exemption: bool) -> None:
        for entitlement in [e for e in self._entitlements if e.pay_date <= self._day]:
            self._entitlements.remove(entitlement)
            self._portfolio = self._portfolio.credit_dividend(entitlement.gross, self._day)
            self._paid.append(entitlement)
            deadline = rules.reinvestment_deadline(entitlement.ex_date) if exemption else None
            if deadline is not None and deadline >= self._day:
                gross = entitlement.gross
                claim = DividendClaim(
                    entitlement.instrument, entitlement.ex_date, self._day, gross, deadline, gross
                )
                self._claims.append(claim)
                continue
            tax = rules.dividend_tax(entitlement.gross, on=self._day)
            if tax.amount > 0:
                self._portfolio = self._portfolio.charge(MovementKind.TAX, tax, self._day)
                self._tax += tax

```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
            self._closes,
        )
```
with:
```python
            self._closes,
            tuple(self._claims),
        )
```

**`packages/steadyhand/src/steadyhand/engine.py`** (implemented: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS

```
with:
```python
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS
    dividend_reinvestment_exemption: bool = False
    """Claim the reinvestment exemption instead of booking dividend tax at pay (M4 spec §6)."""

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        require_int(self.pay_lag_trading_days, "pay_lag_trading_days", minimum=1)

```
with:
```python
        require_int(self.pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
        require_type(self.dividend_reinvestment_exemption, bool, "dividend_reinvestment_exemption")

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    warnings: tuple[Note, ...]

```
with:
```python
    warnings: tuple[Note, ...]
    notes: tuple[Note, ...] = ()
    """The day's exemption-claim events (M4 spec §6.3, §6.4). Empty with the switch off."""

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    holdings, newly_excluded = _freeze_excluded(state.holdings, inputs.excluded)
    corporate = apply_actions(holdings, inputs.actions, day, rules, settings.pay_lag_trading_days)
    holdings = corporate.holdings
```
with:
```python
    holdings, newly_excluded = _freeze_excluded(state.holdings, inputs.excluded)
    payout = Payout(settings.pay_lag_trading_days, settings.dividend_reinvestment_exemption)
    corporate = apply_actions(holdings, inputs.actions, day, rules, payout)
    holdings = corporate.holdings
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python

    new_holdings = Holdings(portfolio, queued, holdings.entitlements, holdings.frozen, closes)
    report = DayReport(
```
with:
```python

    new_holdings = Holdings(
        portfolio, queued, holdings.entitlements, holdings.frozen, closes, holdings.claims
    )
    report = DayReport(
```

**`packages/steadyhand/src/steadyhand/exemption.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/exemption.py -->
```python
"""The dividend reinvestment exemption as claims the engine keeps (M4 spec §6).

With ``EngineSettings.dividend_reinvestment_exemption`` on, a dividend that can be exempt books no
tax when it is paid. It opens a ``DividendClaim`` instead, which the engine carries in
``Holdings.claims`` until its reinvestment and holding conditions are met or broken. Every figure
a claim gives is an estimate: it assumes the investor files the annual realisation reports
(docs/research/t-tax.md §7), which the engine cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Instrument


@dataclass(frozen=True, slots=True)
class Protection:
    """Part of a claim reinvested by one purchase, which must stay invested through ``until``."""

    amount: Money
    until: date

    def __post_init__(self) -> None:
        require_type(self.amount, Money, "amount")
        require_date(self.until, "until")
        if self.amount.amount <= 0:
            msg = f"a protection must be positive, got {self.amount}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DividendClaim:
    """A paid dividend whose tax waits on its reinvestment (M4 spec §6.2).

    ``uncovered`` is the part of ``gross`` not yet reinvested. ``protections`` are the reinvested
    parts, each held through its own date. Together they never exceed ``gross``.
    """

    instrument: Instrument
    ex_date: date
    pay_date: date
    gross: Money
    deadline: date
    uncovered: Money
    protections: tuple[Protection, ...] = ()

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.ex_date, "ex_date")
        require_date(self.pay_date, "pay_date")
        require_date(self.deadline, "deadline")
        require_type(self.gross, Money, "gross")
        require_type(self.uncovered, Money, "uncovered")
        symbol = self.instrument.symbol
        if not self.ex_date < self.pay_date <= self.deadline:
            msg = (
                f"{symbol}: a claim needs ex-date < pay date <= deadline, got "
                f"{self.ex_date}, {self.pay_date} and {self.deadline}"
            )
            raise ValueError(msg)
        for amount in (self.gross, self.uncovered):
            if amount.currency != self.instrument.currency:
                raise CurrencyMismatchError(self.instrument.currency, amount.currency)
        covered = Money.zero(self.gross.currency)
        for protection in self.protections:
            require_type(protection, Protection, "protection")
            covered += protection.amount
        if self.gross.amount <= 0 or self.uncovered.amount < 0:
            msg = f"{symbol}: a claim's gross must be positive and its uncovered part not negative"
            raise ValueError(msg)
        if self.uncovered + covered > self.gross:
            msg = (
                f"{symbol}: uncovered {self.uncovered} and protected {covered} exceed the gross "
                f"dividend {self.gross}"
            )
            raise ValueError(msg)
```

**`packages/steadyhand/src/steadyhand/income.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    def _tax(self, gross: Money) -> Money:
        return self.rules.dividend_tax(gross, reinvested_by_deadline=False, on=self.as_of)

```
with:
```python
    def _tax(self, gross: Money) -> Money:
        return self.rules.dividend_tax(gross, on=self.as_of)

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    """What the full dividend tax on *on* leaves of *gross* (decision 2)."""
    return gross - rules.dividend_tax(gross, reinvested_by_deadline=False, on=on)

```
with:
```python
    """What the full dividend tax on *on* leaves of *gross* (decision 2)."""
    return gross - rules.dividend_tax(gross, on=on)

```

**`packages/steadyhand/src/steadyhand/market.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/market.py -->
Replace:
```python

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """The tax due on a *gross* dividend paid on *on*.

```
with:
```python

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        """The full tax due on a *gross* dividend paid on *on*, before any exemption.

```


- [ ] **Step 6: Run the whole gate:** `uv run --locked ruff check`, `uv run --locked ruff format --check`, `uv run --locked mypy`, `HYPOTHESIS_PROFILE=ci uv run --locked pytest -W error --cov --cov-report=term-missing -p no:cacheprovider`, then the performance step `uv run --locked pytest -W error -m perf -p no:cacheprovider`.

<!-- check: gate total=1021 passed=1021 -->
Expected: every command exits 0; 1021 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 7.6 s against the 30 s budget).

- [ ] **Step 7: Mutations.** Run M140–M148 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M4b S5 the exemption rules, the switch and the claim`, ending in the story's issue number as `(#N)`), as **Merging a story** says.

---

### Task 2: M4b S6 Reinvestment matching and the deadline tax

**Acceptance criteria (story text):**
1. `cover_claims(claims, fills, rules)`: each buy fill's gross, not its costs, covers the open claims with `pay_date ≤ fill day ≤ deadline` that still have something uncovered, oldest pay date first, and each covered amount becomes a `Protection(amount, until=protection_end(fill day))` (M4 §6.3). A sale covers nothing, and a buy used up by an older claim leaves the newer ones untouched.
2. `settle_claims(portfolio, claims, day, rules) -> ClaimDay`: on the first day after a claim's deadline, its uncovered part is taxed at the rate in force on its pay date and booked as `TAX` that day, with a note keyed `exemption.deadline_missed` saying the tax was owed from the pay date. Nothing is taxed on the deadline itself. A claim fully covered by then books nothing and says nothing, and so does a zero tax. A claim with nothing left to reinvest and nothing protected is closed.
3. `run_day` covers and settles the claims after the fills and before valuation; `DayReport.tax` includes the claims' tax and `DayReport.notes` their notes (scope decision 6).
4. `tax.exemption` explains the new key. The engine exports `cover_claims`, `settle_claims`, `ClaimDay` and `EXEMPTION_DEADLINE_MISSED`.
5. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M149–M159 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand/exemption.py`, `engine.py`, `notes.py`, `__init__.py`; `.../steadyhand_idx/training/lessons/en/tax.exemption.md`
- Test: `tests/engine/test_exemption.py`, `tests/engine/test_engine.py`

**Interfaces:**
- Consumes: Task 1's claim, `Holdings.claims`, `MarketRules.protection_end` and `dividend_tax`; `Portfolio.charge`.
- Produces: `cover_claims(claims, fills, rules) -> tuple[DividendClaim, ...]`, `settle_claims(portfolio, claims, day, rules) -> ClaimDay`, `ClaimDay(portfolio, claims, tax, notes)`, `EXEMPTION_DEADLINE_MISSED`.

- [ ] **Step 1: Branch.** `git switch -c m4/s6-reinvestment origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_engine.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
from collections.abc import Mapping
from datetime import date
```
with:
```python
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
)
from steadyhand.exemption import DividendClaim
from steadyhand.money import IDR, Money
from steadyhand.notes import DATA_BAR_MISSING, Note
from steadyhand.portfolio import MissingPriceError, MovementKind
```
with:
```python
)
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Money
from steadyhand.notes import DATA_BAR_MISSING, EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MissingPriceError, MovementKind
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python

def test_a_stock_bought_at_todays_open_has_no_entitlement() -> None:
```
with:
```python

def with_claim(state: EngineState, claim: DividendClaim) -> EngineState:
    return replace(state, holdings=replace(state.holdings, claims=(claim,)))


def test_with_the_exemption_on_todays_buys_cover_an_open_claim() -> None:
    state, _ = day_one()
    claim = DividendClaim(BBCA, date(2025, 5, 28), D1, rp(12_500), date(2026, 3, 31), rp(12_500))
    exempt = replace(half(), dividend_reinvestment_exemption=True)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    after, report = run_day(with_claim(state, claim), inputs, BuyAndHold(), rules(), exempt)
    assert [fill.order.instrument for fill in report.fills] == [BBCA, BBRI]
    # The first buy, BBCA's 500 shares at about 9,000, covers all 12,500; held through 2027.
    protected = (Protection(rp(12_500), date(2027, 12, 31)),)
    assert after.holdings.claims == (replace(claim, uncovered=rp(0), protections=protected),)
    assert (report.tax, report.notes) == (rp(0), ())


def test_a_missed_deadline_adds_its_tax_and_note_to_the_days_report() -> None:
    state, _ = day_one()
    claim = DividendClaim(BBCA, date(2025, 5, 27), date(2025, 5, 28), rp(12_500), D1, rp(12_500))
    exempt = replace(half(), dividend_reinvestment_exemption=True)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    after, report = run_day(with_claim(state, claim), inputs, BuyAndHold(), rules(), exempt)
    assert report.tax == rp(1_250)  # the day's buys come after the 2 June deadline
    assert [note.key for note in report.notes] == [EXEMPTION_DEADLINE_MISSED]
    assert after.holdings.claims == ()
    taxes = [m for m in after.holdings.portfolio.ledger if m.kind is MovementKind.TAX]
    assert [(m.amount, m.day) for m in taxes] == [(rp(-1_250), D2)]


def test_a_stock_bought_at_todays_open_has_no_entitlement() -> None:
```

**`tests/engine/test_exemption.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_exemption.py -->
Replace:
```python

from datetime import date

import pytest

from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import Instrument

```
with:
```python

from dataclasses import replace
from datetime import date
from functools import cache

import pytest

from steadyhand.exemption import ClaimDay, DividendClaim, Protection, cover_claims, settle_claims
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

```

<!-- edit: tests/engine/test_exemption.py -->
Replace:
```python
    return Money(amount, IDR)

```
with:
```python
    return Money(amount, IDR)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


class _RateRises(IdxMarketRules):
    """IDX, but the dividend tax doubles to 20% from 2026."""

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        tax = super().dividend_tax(gross, on=on)
        return tax + tax if on.year >= 2026 else tax


class _TaxFree(IdxMarketRules):
    """IDX, but in a market that taxes no dividend."""

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return Money.zero(gross.currency)


def buy(day: date, value: int, side: Side = Side.BUY, costs: int = 0) -> Fill:
    """One share of BBRI bought (or sold) on *day* for *value*, with *costs* on top."""
    order = Order(Instrument("BBRI", "IDX", IDR), side, 1, day)
    return Fill(order, day, 1, rp(value), Costs(fee=rp(costs), levy=rp(0), tax=rp(0)))


def settle(
    claims: tuple[DividendClaim, ...],
    day: date,
    *fills: Fill,
    market: IdxMarketRules | None = None,
) -> ClaimDay:
    market = rules() if market is None else market
    return settle_claims(Portfolio.empty(IDR), cover_claims(claims, fills, market), day, market)

```

<!-- edit: tests/engine/test_exemption.py -->
Replace:
```python
        DividendClaim("BBCA", EX, PAY, rp(1_000), DEADLINE, rp(1_000))  # type: ignore[arg-type]
```
with:
```python
        DividendClaim("BBCA", EX, PAY, rp(1_000), DEADLINE, rp(1_000))  # type: ignore[arg-type]


def test_a_buy_covers_a_claim_with_its_value_before_costs() -> None:
    day = date(2025, 7, 1)
    after = settle((claim(),), day, buy(day, 600, costs=5))
    # 1,000 - 600 = 400 still to reinvest; a 2025 purchase is held through 31 Dec 2027.
    assert after.claims == (claim(400, Protection(rp(600), date(2027, 12, 31))),)
    assert (after.tax, after.notes, after.portfolio.ledger) == (rp(0), (), ())


def test_buys_cover_the_oldest_pay_date_first_and_spill_into_the_next() -> None:
    newer = claim()  # paid 24 June 2025
    older = DividendClaim(
        BBCA, date(2025, 5, 20), date(2025, 6, 10), rp(1_000), DEADLINE, rp(1_000)
    )
    day = date(2025, 7, 1)
    after = settle((newer, older), day, buy(day, 1_200), buy(day, 300))
    until = date(2027, 12, 31)
    # The 1,200 buy covers the older claim's 1,000 and 200 of the newer; the 300 buy covers 300.
    assert after.claims == (
        claim(500, Protection(rp(200), until), Protection(rp(300), until)),
        DividendClaim(
            BBCA,
            date(2025, 5, 20),
            date(2025, 6, 10),
            rp(1_000),
            DEADLINE,
            rp(0),
            (Protection(rp(1_000), until),),
        ),
    )


def test_a_buy_larger_than_every_claim_leaves_the_rest_unclaimed() -> None:
    day = date(2025, 7, 1)
    after = settle((claim(),), day, buy(day, 5_000))
    assert after.claims == (claim(0, Protection(rp(1_000), date(2027, 12, 31))),)


@pytest.mark.parametrize(
    ("fill", "covered"),
    [
        (buy(date(2025, 6, 23), 600), 0),  # the day before the dividend was paid
        (buy(PAY, 600), 600),  # the pay day itself
        (buy(DEADLINE, 600), 600),  # the deadline itself
        (buy(date(2025, 7, 1), 600, Side.SELL), 0),  # a sale reinvests nothing
    ],
)
def test_only_a_buy_from_the_pay_day_to_the_deadline_covers(fill: Fill, covered: int) -> None:
    after = settle((claim(),), fill.day, fill)
    assert after.claims[0].uncovered == rp(1_000 - covered)


def test_what_misses_the_deadline_is_taxed_the_next_day_and_the_claim_keeps_its_protection() -> (
    None
):
    protected = Protection(rp(600), date(2027, 12, 31))
    day = date(2026, 4, 1)
    after = settle((claim(400, protected),), day)
    assert after.tax == rp(40)  # 10% of the 400 not reinvested
    ledger = after.portfolio.ledger
    assert [(m.kind, m.amount, m.day) for m in ledger] == [(MovementKind.TAX, rp(-40), day)]
    assert after.notes == (
        Note(
            EXEMPTION_DEADLINE_MISSED,
            "BBCA: IDR 400 of the dividend paid on 2025-06-24 was not reinvested by 2026-03-31, "
            "so its tax of IDR 40, owed from 2025-06-24, is booked today",
        ),
    )
    assert after.claims == (claim(0, protected),)


def test_nothing_is_taxed_on_the_deadline_itself() -> None:
    after = settle((claim(),), DEADLINE)
    assert (after.tax, after.notes, after.claims) == (rp(0), (), (claim(),))


def test_a_claim_with_nothing_left_after_its_deadline_is_closed() -> None:
    after = settle((claim(999),), date(2026, 4, 1))
    assert after.tax == rp(100)  # 99.9 rounds up
    assert after.claims == ()


def test_a_claim_fully_reinvested_by_its_deadline_books_nothing() -> None:
    protected = Protection(rp(1_000), date(2027, 12, 31))
    after = settle((claim(0, protected),), date(2026, 4, 1))
    assert (after.tax, after.notes, after.claims) == (rp(0), (), (claim(0, protected),))


def test_the_deadline_tax_is_at_the_rate_in_force_on_the_pay_day() -> None:
    after = settle((claim(400),), date(2026, 4, 1), market=_RateRises())
    assert after.tax == rp(40)  # 10% as on 24 June 2025, not 2026's 20%


def test_an_untaxed_market_books_no_zero_tax_and_emits_no_note() -> None:
    after = settle((claim(400),), date(2026, 4, 1), market=_TaxFree())
    assert (after.tax, after.notes, after.claims, after.portfolio.ledger) == (rp(0), (), (), ())


def test_a_buy_used_up_by_an_older_claim_leaves_the_newer_one_untouched() -> None:
    older = DividendClaim(
        BBCA, date(2025, 5, 20), date(2025, 6, 10), rp(1_000), DEADLINE, rp(1_000)
    )
    day = date(2025, 7, 1)
    after = settle((claim(), older), day, buy(day, 1_000))
    protected = Protection(rp(1_000), date(2027, 12, 31))
    assert after.claims == (claim(), replace(older, uncovered=rp(0), protections=(protected,)))
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.income import (
```
with:
```python
)
from steadyhand.exemption import (
    ClaimDay,
    DividendClaim,
    Protection,
    cover_claims,
    settle_claims,
)
from steadyhand.income import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    DATA_BAR_REFUSED,
    INCOME_GROWTH_SHORT_HISTORY,
```
with:
```python
    DATA_BAR_REFUSED,
    EXEMPTION_DEADLINE_MISSED,
    INCOME_GROWTH_SHORT_HISTORY,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "DISCLAIMER",
    "FIGURES",
```
with:
```python
    "DISCLAIMER",
    "EXEMPTION_DEADLINE_MISSED",
    "FIGURES",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "ChronologyError",
    "CompoundingSizer",
```
with:
```python
    "ChronologyError",
    "ClaimDay",
    "CompoundingSizer",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "backtest",
    "dividend_growth",
```
with:
```python
    "backtest",
    "cover_claims",
    "dividend_growth",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "run_rate",
    "year_window_start",
```
with:
```python
    "run_rate",
    "settle_claims",
    "year_window_start",
```

**`packages/steadyhand/src/steadyhand/engine.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
)
from steadyhand.market import MarketRules
```
with:
```python
)
from steadyhand.exemption import cover_claims, settle_claims
from steadyhand.market import MarketRules
```

**`packages/steadyhand/src/steadyhand/exemption.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python

from dataclasses import dataclass
from datetime import date

from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Instrument

```
with:
```python

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from steadyhand._validate import require_date, require_type
from steadyhand.market import MarketRules
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Fill, Instrument, Side

```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
                f"dividend {self.gross}"
            )
            raise ValueError(msg)
```
with:
```python
                f"dividend {self.gross}"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ClaimDay:
    """The claims after a day's bookkeeping, with the tax it booked and what it has to say."""

    portfolio: Portfolio
    claims: tuple[DividendClaim, ...]
    tax: Money
    notes: tuple[Note, ...]


def settle_claims(
    portfolio: Portfolio, claims: tuple[DividendClaim, ...], day: date, rules: MarketRules
) -> ClaimDay:
    """Tax what missed its deadline at the day's close (M4 spec §6.3), booking it on *day*.

    A claim with nothing left to reinvest and nothing protected is closed.
    """
    raise NotImplementedError("settle_claims")


def cover_claims(
    claims: tuple[DividendClaim, ...], fills: Sequence[Fill], rules: MarketRules
) -> tuple[DividendClaim, ...]:
    """Cover open claims with the day's buys (M4 spec §6.3).

    Each buy's gross, not its costs, covers the claims paid on or before its day whose deadline
    it meets, oldest pay date first. Each amount covered is protected until the market's
    ``protection_end`` of the buy's day.
    """
    raise NotImplementedError("cover_claims")


def _age(claim: DividendClaim) -> tuple[date, date, str, str]:
    """The order claims are covered in: oldest pay date first, then a fixed tie-break."""
    raise NotImplementedError("_age")


def _deadline_missed(claim: DividendClaim, tax: Money) -> Note:
    raise NotImplementedError("_deadline_missed")
```

**`packages/steadyhand/src/steadyhand/notes.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/notes.py -->
Replace:
```python

INCOME_GROWTH_SHORT_HISTORY = "income.growth.short_history"
```
with:
```python

EXEMPTION_DEADLINE_MISSED = "exemption.deadline_missed"
"""Part of a dividend claim was not reinvested by its deadline, so its tax is booked now."""

INCOME_GROWTH_SHORT_HISTORY = "income.growth.short_history"
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1037 failed=18 -->
Expected: 1037 run, 18 failed. 14 are `NotImplementedError` from the stubbed `cover_claims` and `settle_claims`. Four are `AssertionError`s on their own lines: the two engine tests, because `run_day` does not yet cover or settle; `test_every_key_has_a_lesson`, for `exemption.deadline_missed`; and `test_every_note_is_built_from_a_note_key_and_every_note_key_is_used`, because the key's only `Note(...)` is inside a stub.

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md`** (changed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md -->
Replace:
```markdown
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = ["term.claim_to_reinvest", "term.claim_protected"]
module = "costs-and-tax"
```
with:
```markdown
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = ["term.claim_to_reinvest", "term.claim_protected", "exemption.deadline_missed"]
module = "costs-and-tax"
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md -->
Replace:
```markdown
- **Protected** is a part that a purchase has reinvested, with the last day it must stay
  invested: 31 December of the second year after the purchase.

```
with:
```markdown
- **Protected** is a part that a purchase has reinvested, with the last day it must stay
  invested: 31 December of the second year after the purchase. A purchase counts towards the
  claims that are open on its day, oldest dividend first, up to its value before costs.

If part of a dividend is still to reinvest after its deadline, steadyhand books 10% of that part
on the first trading day after the deadline, at the rate in force when the dividend was paid. It
cannot book tax on a past date, so a note records that the tax was owed from the pay date.

```

**`packages/steadyhand/src/steadyhand/engine.py`** (implemented: 4 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    filled = _fill(holdings, inputs, rules, settings.fills)
    portfolio = filled.portfolio

```
with:
```python
    filled = _fill(holdings, inputs, rules, settings.fills)
    covered = cover_claims(holdings.claims, filled.fills, rules)
    claimed = settle_claims(filled.portfolio, covered, day, rules)
    portfolio = claimed.portfolio

```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    new_holdings = Holdings(
        portfolio, queued, holdings.entitlements, holdings.frozen, closes, holdings.claims
    )
```
with:
```python
    new_holdings = Holdings(
        portfolio, queued, holdings.entitlements, holdings.frozen, closes, claimed.claims
    )
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        paid=corporate.paid,
        tax=corporate.tax,
        daily_cost=filled.daily_cost,
```
with:
```python
        paid=corporate.paid,
        tax=corporate.tax + claimed.tax,
        daily_cost=filled.daily_cost,
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
        warnings=(*corporate.warnings, *warnings),
    )
```
with:
```python
        warnings=(*corporate.warnings, *warnings),
        notes=claimed.notes,
    )
```

**`packages/steadyhand/src/steadyhand/exemption.py`** (implemented: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
    """
    raise NotImplementedError("settle_claims")

```
with:
```python
    """
    tax = Money.zero(portfolio.currency)
    notes: list[Note] = []
    settled: list[DividendClaim] = []
    for claim in claims:
        if day <= claim.deadline or claim.uncovered.amount == 0:
            settled.append(claim)
            continue
        owed = rules.dividend_tax(claim.uncovered, on=claim.pay_date)
        if owed.amount > 0:
            portfolio = portfolio.charge(MovementKind.TAX, owed, day)
            tax += owed
            notes.append(_deadline_missed(claim, owed))
        settled.append(replace(claim, uncovered=Money.zero(claim.uncovered.currency)))
    kept = tuple(c for c in settled if c.uncovered.amount > 0 or c.protections)
    return ClaimDay(portfolio, kept, tax, tuple(notes))

```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
    """
    raise NotImplementedError("cover_claims")

```
with:
```python
    """
    current = list(claims)
    order = sorted(range(len(current)), key=lambda i: _age(current[i]))
    for fill in fills:
        if fill.order.side is not Side.BUY:
            continue
        left = fill.gross
        for index in order:
            claim = current[index]
            if left.amount == 0:
                break
            if not claim.pay_date <= fill.day <= claim.deadline or claim.uncovered.amount == 0:
                continue
            taken = min(left, claim.uncovered)
            protection = Protection(taken, rules.protection_end(fill.day))
            current[index] = replace(
                claim,
                uncovered=claim.uncovered - taken,
                protections=(*claim.protections, protection),
            )
            left -= taken
    return tuple(current)

```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
    """The order claims are covered in: oldest pay date first, then a fixed tie-break."""
    raise NotImplementedError("_age")


def _deadline_missed(claim: DividendClaim, tax: Money) -> Note:
    raise NotImplementedError("_deadline_missed")
```
with:
```python
    """The order claims are covered in: oldest pay date first, then a fixed tie-break."""
    return (claim.pay_date, claim.ex_date, claim.instrument.market, claim.instrument.symbol)


def _deadline_missed(claim: DividendClaim, tax: Money) -> Note:
    pay = claim.pay_date.isoformat()
    return Note(
        EXEMPTION_DEADLINE_MISSED,
        f"{claim.instrument.symbol}: {claim.uncovered} of the dividend paid on {pay} was not "
        f"reinvested by {claim.deadline.isoformat()}, so its tax of {tax}, owed from {pay}, is "
        "booked today",
    )
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=1037 passed=1037 -->
Expected: every command exits 0; 1037 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 7.7 s against the 30 s budget).

- [ ] **Step 7: Mutations.** Run M149–M159; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M4b S6 reinvestment matching and the deadline tax`, ending in `(#N)`).

---

### Task 3: M4b S7 Protection, the settlement grace and breaks

**Acceptance criteria (story text):**
1. At each day's close, protections whose `until` is before the day fall away. The protected sum is compared with the sum of `cost_basis` over the portfolio's positions (M4 §6.4).
2. A shortfall's first day is kept in `Holdings.shortfall_since`, and cleared on a day the shortfall has gone. A shortfall still present at the close of `rules.settlement_date(first day)` breaks: protections are removed, latest `until` first with the tie-break of scope decision 7, until the removed amount covers it, the last one partly.
3. Each broken claim's removed amount is taxed at its pay-date rate, booked as `TAX` that day, with a note keyed `exemption.claim_broken` saying the tax was owed from the pay date. A zero tax books nothing and says nothing.
4. The tax booked for any one claim never exceeds the full tax on its gross plus one rupiah per booking after the first (M4 §9), as a hand-worked test and a hypothesis property show.
5. `tax.exemption` explains the new key and says the grace is steadyhand's assumption. The engine exports `EXEMPTION_CLAIM_BROKEN`.
6. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M160–M169 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand/exemption.py`, `corporate.py`, `engine.py`, `notes.py`, `__init__.py`; `.../steadyhand_idx/training/lessons/en/tax.exemption.md`
- Test: `tests/engine/test_exemption.py`, `tests/engine/test_engine.py`, `tests/engine/test_corporate.py`

**Interfaces:**
- Consumes: Task 2's `settle_claims`; `MarketRules.settlement_date`; `Portfolio.positions`.
- Produces: `settle_claims(portfolio, claims, shortfall_since, day, rules) -> ClaimDay`, `ClaimDay.shortfall_since`, `Holdings.shortfall_since`, `EXEMPTION_CLAIM_BROKEN`.

- [ ] **Step 1: Branch.** `git switch -c m4/s7-protection origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_corporate.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_corporate.py -->
Replace:
```python
        Holdings(holding(), claims=("BBCA",))  # type: ignore[arg-type]
```
with:
```python
        Holdings(holding(), claims=("BBCA",))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^shortfall_since must be a date"):
        Holdings(holding(), shortfall_since="2025-06-02")  # type: ignore[arg-type]
```

**`tests/engine/test_engine.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python
from steadyhand.money import IDR, Money
from steadyhand.notes import DATA_BAR_MISSING, EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MissingPriceError, MovementKind
```
with:
```python
from steadyhand.money import IDR, Money
from steadyhand.notes import (
    DATA_BAR_MISSING,
    EXEMPTION_CLAIM_BROKEN,
    EXEMPTION_DEADLINE_MISSED,
    Note,
)
from steadyhand.portfolio import MissingPriceError, MovementKind
```

<!-- edit: tests/engine/test_engine.py -->
Replace:
```python

def test_a_stock_bought_at_todays_open_has_no_entitlement() -> None:
```
with:
```python

def test_a_shortfall_is_kept_across_days_and_breaks_when_its_trade_would_settle() -> None:
    state, _ = day_one()  # cash only: nothing is invested
    protected = (Protection(rp(12_500), date(2027, 12, 31)),)
    claim = DividendClaim(
        BBCA, date(2025, 5, 27), date(2025, 5, 28), rp(12_500), date(2026, 3, 31), rp(0), protected
    )
    holdings = Holdings(state.holdings.portfolio, claims=(claim,))
    current = EngineState(holdings, state.units, Halt(D1, "test"), D1)
    kept: list[tuple[date | None, Money]] = []
    for day in (D2, D3, D4):  # D2's trade would settle on D4
        current, report = run_day(
            current, DayInputs(day, steady(), members=MEMBERS), _Untouchable(), rules()
        )
        kept.append((current.holdings.shortfall_since, report.tax))
    assert kept == [(D2, rp(0)), (D2, rp(0)), (None, rp(1_250))]
    assert [note.key for note in report.notes] == [EXEMPTION_CLAIM_BROKEN]
    assert current.holdings.claims == ()


def test_a_stock_bought_at_todays_open_has_no_entitlement() -> None:
```

**`tests/engine/test_exemption.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_exemption.py -->
Replace:
```python
from dataclasses import replace
from datetime import date
from functools import cache

import pytest

from steadyhand.exemption import ClaimDay, DividendClaim, Protection, cover_claims, settle_claims
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
```
with:
```python
from dataclasses import replace
from datetime import date, timedelta
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.exemption import ClaimDay, DividendClaim, Protection, cover_claims, settle_claims
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_CLAIM_BROKEN, EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
```

<!-- edit: tests/engine/test_exemption.py -->
Replace:
```python
    market = rules() if market is None else market
    return settle_claims(Portfolio.empty(IDR), cover_claims(claims, fills, market), day, market)

```
with:
```python
    market = rules() if market is None else market
    covered = cover_claims(claims, fills, market)
    return settle_claims(Portfolio.empty(IDR), covered, None, day, market)

```

<!-- edit: tests/engine/test_exemption.py -->
Replace:
```python
    assert after.claims == (claim(), replace(older, uncovered=rp(0), protections=(protected,)))
```
with:
```python
    assert after.claims == (claim(), replace(older, uncovered=rp(0), protections=(protected,)))


JUL1, JUL2, JUL3 = date(2025, 7, 1), date(2025, 7, 2), date(2025, 7, 3)  # 1 July settles 3 July
UNTIL = date(2027, 12, 31)


def invested(amount: int) -> Portfolio:
    """A portfolio whose one position cost *amount*, bought before any day below."""
    book = Portfolio.empty(IDR)
    if amount == 0:
        return book
    fill = buy(date(2025, 6, 2), amount)
    return book.deposit(rp(amount), fill.day).apply_fill(fill, fill.day)


def close(
    claims: tuple[DividendClaim, ...],
    day: date,
    held: int,
    since: date | None = None,
    market: IdxMarketRules | None = None,
) -> ClaimDay:
    market = rules() if market is None else market
    return settle_claims(invested(held), claims, since, day, market)


def test_protections_past_their_date_fall_away_and_close_the_claim() -> None:
    ending = Protection(rp(600), JUL1)
    after = close((claim(0, ending),), JUL1, 0)  # protected through 1 July, so still counted
    assert (after.claims, after.shortfall_since) == ((claim(0, ending),), JUL1)
    after = close((claim(0, ending),), JUL2, 0, JUL1)
    assert (after.claims, after.shortfall_since, after.tax) == ((), None, rp(0))


def test_a_shortfall_within_the_settlement_grace_keeps_the_claim() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    first = close((held,), JUL1, 400)
    assert (first.claims, first.shortfall_since, first.tax) == ((held,), JUL1, rp(0))
    second = close((held,), JUL2, 400, JUL1)  # the shortfall's first day is kept
    assert (second.claims, second.shortfall_since, second.tax) == ((held,), JUL1, rp(0))


def test_a_shortfall_gone_before_the_grace_ends_clears_its_day() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), JUL2, 1_000, JUL1)  # a rotation: bought back within the cycle
    assert (after.claims, after.shortfall_since, after.tax) == ((held,), None, rp(0))


def test_a_shortfall_still_there_at_the_settlement_close_breaks() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), JUL3, 400, JUL1)
    # 1,000 protected against 400 invested: 600 breaks, and 10% of it is booked today.
    assert (after.tax, after.shortfall_since) == (rp(60), None)
    assert after.claims == (claim(0, Protection(rp(400), UNTIL)),)
    ledger = after.portfolio.ledger
    assert [(m.kind, m.amount, m.day) for m in ledger][-1] == (MovementKind.TAX, rp(-60), JUL3)
    assert after.notes == (
        Note(
            EXEMPTION_CLAIM_BROKEN,
            "BBCA: IDR 600 reinvested from the dividend paid on 2025-06-24 was no longer invested "
            "when the settlement grace ended, so its tax of IDR 60, owed from 2025-06-24, is "
            "booked today",
        ),
    )


def test_breaks_take_the_latest_protection_first() -> None:
    older = DividendClaim(
        BBCA,
        date(2025, 5, 20),
        date(2025, 6, 10),
        rp(1_000),
        DEADLINE,
        rp(500),
        (Protection(rp(500), UNTIL),),
    )
    later = claim(500, Protection(rp(500), date(2028, 12, 31)))
    after = close((older, later), JUL3, 300, JUL1)
    # 1,000 protected against 300 invested: 700 breaks, the 2028 protection's 500 first, then
    # 200 of the 2027 one. Tax is 10% of each claim's part, 20 and 50, in the claims' order.
    assert after.claims == (
        replace(older, protections=(Protection(rp(300), UNTIL),)),
        replace(later, protections=()),
    )
    assert after.tax == rp(70)
    assert [note.text.split(":")[0] for note in after.notes] == ["BBCA", "BBCA"]
    assert ["IDR 200 " in after.notes[0].text, "IDR 500 " in after.notes[1].text] == [True, True]


def test_equal_dates_break_the_newest_claim_and_its_last_protection_first() -> None:
    older = DividendClaim(
        BBCA,
        date(2025, 5, 20),
        date(2025, 6, 10),
        rp(1_000),
        DEADLINE,
        rp(0),
        (Protection(rp(1_000), UNTIL),),
    )
    newer = claim(0, Protection(rp(600), UNTIL), Protection(rp(400), UNTIL))
    after = close((older, newer), JUL3, 1_700, JUL1)
    # 2,000 protected against 1,700: 300 breaks from the newer claim's last protection.
    assert after.claims == (
        older,
        claim(0, Protection(rp(600), UNTIL), Protection(rp(100), UNTIL)),
    )


def test_a_broken_claim_is_taxed_at_its_pay_day_rate() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), date(2026, 7, 3), 400, date(2026, 7, 1), _RateRises())
    assert after.tax == rp(60)  # 10% as on 24 June 2025, not 2026's 20%


def test_an_untaxed_market_breaks_the_claim_without_booking_or_a_note() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), JUL3, 400, JUL1, _TaxFree())
    assert (after.tax, after.notes) == (rp(0), ())
    assert after.claims == (claim(0, Protection(rp(400), UNTIL)),)


def test_each_booking_rounds_up_on_its_own() -> None:
    # M4 spec §9 and its pass 3: Rp2 taxed in two pieces of 1 books 1 + 1 = 2, where the full
    # tax on Rp2 is 0.2 rounded up to 1.
    split = DividendClaim(BBCA, EX, PAY, rp(2), JUL1, rp(1), (Protection(rp(1), UNTIL),))
    after = close((split,), JUL3, 0, JUL1)
    assert (after.tax, len(after.notes), after.claims) == (rp(2), 2, ())
    assert rules().dividend_tax(rp(2), on=PAY) == rp(1)


TRADING = tuple(
    day for day in (JUL1 + timedelta(days=n) for n in range(16)) if rules().is_trading_day(day)
)


def test_the_property_below_runs_over_twelve_trading_days() -> None:
    assert (len(TRADING), TRADING[0], TRADING[-1]) == (12, JUL1, date(2025, 7, 16))


@given(
    gross=st.integers(1, 100_000),
    steps=st.lists(
        st.tuples(st.integers(0, 100), st.integers(0, 150)), min_size=1, max_size=len(TRADING)
    ),
    last_day=st.integers(0, len(TRADING) - 1),
)
def test_a_claims_tax_never_exceeds_its_full_tax_plus_one_unit_per_extra_booking(
    gross: int, steps: list[tuple[int, int]], last_day: int
) -> None:
    # M4 spec §9: each booking rounds up on its own, so pieces may add up to a unit more each.
    # Each day buys and holds a percentage of the gross, so claims are covered in parts and
    # shortfalls last long enough to break.
    opened = DividendClaim(BBCA, EX, PAY, rp(gross), TRADING[last_day], rp(gross))
    claims: tuple[DividendClaim, ...] = (opened,)
    since: date | None = None
    tax, bookings = rp(0), 0
    for day, (bought_percent, held_percent) in zip(TRADING, steps, strict=False):
        bought, held = gross * bought_percent // 100, gross * held_percent // 100
        fills = [buy(day, bought)] if bought else []
        covered = cover_claims(claims, fills, rules())
        after = settle_claims(invested(held), covered, since, day, rules())
        claims, since = after.claims, after.shortfall_since
        tax += after.tax
        bookings += len(after.notes)
    full = rules().dividend_tax(rp(gross), on=PAY)
    assert tax.amount <= full.amount + max(bookings - 1, 0)
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    DATA_BAR_REFUSED,
    EXEMPTION_DEADLINE_MISSED,
```
with:
```python
    DATA_BAR_REFUSED,
    EXEMPTION_CLAIM_BROKEN,
    EXEMPTION_DEADLINE_MISSED,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "DISCLAIMER",
    "EXEMPTION_DEADLINE_MISSED",
```
with:
```python
    "DISCLAIMER",
    "EXEMPTION_CLAIM_BROKEN",
    "EXEMPTION_DEADLINE_MISSED",
```

**`packages/steadyhand/src/steadyhand/exemption.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
```
with:
```python
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_CLAIM_BROKEN, EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python

def cover_claims(
```
with:
```python

class _Close:
    """One day's claim bookings in progress: the portfolio they charge, and what they said."""

    def __init__(self, portfolio: Portfolio, day: date, rules: MarketRules) -> None:
        raise NotImplementedError("_Close.__init__")

    def deadline(self, claim: DividendClaim) -> DividendClaim:
        """Tax the part of *claim* still to reinvest once its deadline has passed."""
        raise NotImplementedError("_Close.deadline")

    def breaks(self, claims: list[DividendClaim], shortfall: Money) -> list[DividendClaim]:
        """Remove protections, latest ``until`` first, until *shortfall* is covered.

        Ties go to the newest claim, then to its protection added last, so the order is total.
        """
        raise NotImplementedError("_Close.breaks")

    def _book(self, claim: DividendClaim, amount: Money) -> Money:
        """Book the tax on *amount* of *claim* today, at the rate of the claim's pay date."""
        raise NotImplementedError("_Close._book")


def _unexpired(protections: tuple[Protection, ...], day: date) -> tuple[Protection, ...]:
    raise NotImplementedError("_unexpired")


def cover_claims(
```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python

def _deadline_missed(claim: DividendClaim, tax: Money) -> Note:
```
with:
```python

def _claim_broken(claim: DividendClaim, amount: Money, tax: Money) -> Note:
    raise NotImplementedError("_claim_broken")


def _deadline_missed(claim: DividendClaim, tax: Money) -> Note:
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

EXEMPTION_CLAIM_BROKEN = "exemption.claim_broken"
"""Protected dividend money left the portfolio past the settlement grace, so its tax is booked."""

```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1049 failed=28 -->
Expected: 1049 run, 28 failed, none of them `NotImplementedError`: S7's new functions are private helpers that the old `settle_claims` never calls, and its public change is a new parameter on that existing function. 24 are `TypeError: settle_claims() takes 4 positional arguments but 5 were given`, since the tests' helper passes the shortfall's day to the S6 function (every `settle_claims` test, S6's included). The other four are on their own lines: `Holdings` refusing `shortfall_since` (a `pytest.raises` whose message does not match, and an `AttributeError` in the engine test), `test_every_key_has_a_lesson` for `exemption.claim_broken`, and the note-key guard, whose `Note(...)` for the new key is not written yet. One test passes against the stubs by design: `test_the_property_below_runs_over_twelve_trading_days` checks the property's own day list.

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md`** (changed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md -->
Replace:
```markdown
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = ["term.claim_to_reinvest", "term.claim_protected", "exemption.deadline_missed"]
module = "costs-and-tax"
```
with:
```markdown
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = ["term.claim_to_reinvest", "term.claim_protected", "exemption.deadline_missed", "exemption.claim_broken"]
module = "costs-and-tax"
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/training/lessons/en/tax.exemption.md -->
Replace:
```markdown

This lesson describes the rules; whether they apply to you, and how, is a question for you or a
```
with:
```markdown

Each day at the close, steadyhand compares the amount protected with what the portfolio still
has invested, at cost. Selling one stock and buying another within the settlement cycle keeps
the claim: the rules allow it, and how long the gap may last is not settled, so this grace is
steadyhand's assumption. If the portfolio still holds less than the protected amount when the
settlement cycle ends, the difference is broken, starting with the protection that runs latest.
10% of what broke is booked that day, at the rate in force when each dividend was paid, with a
note that the tax was owed from the pay date.

This lesson describes the rules; whether they apply to you, and how, is a question for you or a
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (implemented: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
    its reason, and ``last_closes`` the last close of each held stock, which values it on a
    day with no bar. ``claims`` are the open reinvestment-exemption claims (M4 spec §6.2).
    """
```
with:
```python
    its reason, and ``last_closes`` the last close of each held stock, which values it on a
    day with no bar. ``claims`` are the open reinvestment-exemption claims (M4 spec §6.2), and
    ``shortfall_since`` the day their protected amount first exceeded what is invested (§6.4).
    """
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
    claims: tuple[DividendClaim, ...] = ()

```
with:
```python
    claims: tuple[DividendClaim, ...] = ()
    shortfall_since: date | None = None

```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
            require_type(claim, DividendClaim, "claim")

```
with:
```python
            require_type(claim, DividendClaim, "claim")
        if self.shortfall_since is not None:
            require_date(self.shortfall_since, "shortfall_since")

```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
        self._claims = list(holdings.claims)
        self._frozen = dict(holdings.frozen)
```
with:
```python
        self._claims = list(holdings.claims)
        self._shortfall_since = holdings.shortfall_since
        self._frozen = dict(holdings.frozen)
```

<!-- edit: packages/steadyhand/src/steadyhand/corporate.py -->
Replace:
```python
            tuple(self._claims),
        )
```
with:
```python
            tuple(self._claims),
            self._shortfall_since,
        )
```

**`packages/steadyhand/src/steadyhand/engine.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    covered = cover_claims(holdings.claims, filled.fills, rules)
    claimed = settle_claims(filled.portfolio, covered, day, rules)
    portfolio = claimed.portfolio
```
with:
```python
    covered = cover_claims(holdings.claims, filled.fills, rules)
    claimed = settle_claims(filled.portfolio, covered, holdings.shortfall_since, day, rules)
    portfolio = claimed.portfolio
```

<!-- edit: packages/steadyhand/src/steadyhand/engine.py -->
Replace:
```python
    new_holdings = Holdings(
        portfolio, queued, holdings.entitlements, holdings.frozen, closes, claimed.claims
    )
```
with:
```python
    new_holdings = Holdings(
        portfolio,
        queued,
        holdings.entitlements,
        holdings.frozen,
        closes,
        claimed.claims,
        claimed.shortfall_since,
    )
```

**`packages/steadyhand/src/steadyhand/exemption.py`** (implemented: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
    claims: tuple[DividendClaim, ...]
    tax: Money
```
with:
```python
    claims: tuple[DividendClaim, ...]
    shortfall_since: date | None
    tax: Money
```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
def settle_claims(
    portfolio: Portfolio, claims: tuple[DividendClaim, ...], day: date, rules: MarketRules
) -> ClaimDay:
    """Tax what missed its deadline at the day's close (M4 spec §6.3), booking it on *day*.

    A claim with nothing left to reinvest and nothing protected is closed.
    """
    tax = Money.zero(portfolio.currency)
    notes: list[Note] = []
    settled: list[DividendClaim] = []
    for claim in claims:
        if day <= claim.deadline or claim.uncovered.amount == 0:
            settled.append(claim)
            continue
        owed = rules.dividend_tax(claim.uncovered, on=claim.pay_date)
        if owed.amount > 0:
            portfolio = portfolio.charge(MovementKind.TAX, owed, day)
            tax += owed
            notes.append(_deadline_missed(claim, owed))
        settled.append(replace(claim, uncovered=Money.zero(claim.uncovered.currency)))
    kept = tuple(c for c in settled if c.uncovered.amount > 0 or c.protections)
    return ClaimDay(portfolio, kept, tax, tuple(notes))

```
with:
```python
def settle_claims(
    portfolio: Portfolio,
    claims: tuple[DividendClaim, ...],
    shortfall_since: date | None,
    day: date,
    rules: MarketRules,
) -> ClaimDay:
    """The claims at the day's close, with any tax they book on *day*.

    What missed its deadline is taxed (M4 spec §6.3). Protections past their date fall away.
    Then the protected amount is compared with the cost basis still invested: a shortfall that
    lasts to the close of the settlement date of its first day breaks, latest protection first
    (§6.4). A claim with nothing left to reinvest and nothing protected is closed.
    """
    close = _Close(portfolio, day, rules)
    current = [close.deadline(claim) for claim in claims]
    current = [replace(c, protections=_unexpired(c.protections, day)) for c in current]
    protected = sum(
        (p.amount for c in current for p in c.protections), Money.zero(portfolio.currency)
    )
    invested = sum((p.cost_basis for p in portfolio.positions), Money.zero(portfolio.currency))
    since = None
    if protected > invested:
        since = day if shortfall_since is None else shortfall_since
        if day >= rules.settlement_date(since):
            current = close.breaks(current, protected - invested)
            since = None
    kept = tuple(c for c in current if c.uncovered.amount > 0 or c.protections)
    return ClaimDay(close.portfolio, kept, since, close.tax, tuple(close.notes))

```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
    def __init__(self, portfolio: Portfolio, day: date, rules: MarketRules) -> None:
        raise NotImplementedError("_Close.__init__")

    def deadline(self, claim: DividendClaim) -> DividendClaim:
        """Tax the part of *claim* still to reinvest once its deadline has passed."""
        raise NotImplementedError("_Close.deadline")

```
with:
```python
    def __init__(self, portfolio: Portfolio, day: date, rules: MarketRules) -> None:
        self.portfolio = portfolio
        self.tax = Money.zero(portfolio.currency)
        self.notes: list[Note] = []
        self._day = day
        self._rules = rules

    def deadline(self, claim: DividendClaim) -> DividendClaim:
        """Tax the part of *claim* still to reinvest once its deadline has passed."""
        if self._day <= claim.deadline or claim.uncovered.amount == 0:
            return claim
        owed = self._book(claim, claim.uncovered)
        if owed.amount > 0:
            self.notes.append(_deadline_missed(claim, owed))
        return replace(claim, uncovered=Money.zero(claim.uncovered.currency))

```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
        """
        raise NotImplementedError("_Close.breaks")

    def _book(self, claim: DividendClaim, amount: Money) -> Money:
        """Book the tax on *amount* of *claim* today, at the rate of the claim's pay date."""
        raise NotImplementedError("_Close._book")


def _unexpired(protections: tuple[Protection, ...], day: date) -> tuple[Protection, ...]:
    raise NotImplementedError("_unexpired")

```
with:
```python
        """
        amounts = [[protection.amount for protection in claim.protections] for claim in claims]
        removed = [Money.zero(shortfall.currency) for _ in claims]
        pieces = [
            (protection.until, _age(claim), place, index)
            for index, claim in enumerate(claims)
            for place, protection in enumerate(claim.protections)
        ]
        left = shortfall
        for _, _, place, index in sorted(pieces, reverse=True):
            if left.amount == 0:
                break
            taken = min(amounts[index][place], left)
            amounts[index][place] -= taken
            removed[index] += taken
            left -= taken
        broken: list[DividendClaim] = []
        for claim, rests, amount in zip(claims, amounts, removed, strict=True):
            if amount.amount > 0:
                owed = self._book(claim, amount)
                if owed.amount > 0:
                    self.notes.append(_claim_broken(claim, amount, owed))
            protections = zip(claim.protections, rests, strict=True)
            left_over = tuple(replace(p, amount=rest) for p, rest in protections if rest.amount)
            broken.append(replace(claim, protections=left_over))
        return broken

    def _book(self, claim: DividendClaim, amount: Money) -> Money:
        """Book the tax on *amount* of *claim* today, at the rate of the claim's pay date."""
        owed = self._rules.dividend_tax(amount, on=claim.pay_date)
        if owed.amount > 0:
            self.portfolio = self.portfolio.charge(MovementKind.TAX, owed, self._day)
            self.tax += owed
        return owed


def _unexpired(protections: tuple[Protection, ...], day: date) -> tuple[Protection, ...]:
    return tuple(protection for protection in protections if protection.until >= day)

```

<!-- edit: packages/steadyhand/src/steadyhand/exemption.py -->
Replace:
```python
def _claim_broken(claim: DividendClaim, amount: Money, tax: Money) -> Note:
    raise NotImplementedError("_claim_broken")

```
with:
```python
def _claim_broken(claim: DividendClaim, amount: Money, tax: Money) -> Note:
    pay = claim.pay_date.isoformat()
    return Note(
        EXEMPTION_CLAIM_BROKEN,
        f"{claim.instrument.symbol}: {amount} reinvested from the dividend paid on {pay} was no "
        f"longer invested when the settlement grace ended, so its tax of {tax}, owed from {pay}, "
        "is booked today",
    )

```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=1049 passed=1049 -->
Expected: every command exits 0; 1049 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 8.4 s against the 30 s budget).

- [ ] **Step 7: Mutations.** Run M160–M169; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): M4b S7 protection, the settlement grace and breaks`, ending in `(#N)`).

---

### Task 4: M4b S8 Claims in the income report and the switch-on golden run

**Acceptance criteria (story text):**
1. `IncomeReport.claims` holds the final holdings' open claims, with `claims_label` equal to `CLAIMS_LABEL`, *"Estimate: assumes the yearly realisation reports are filed"*; it is empty with the switch off (M4 §6.5, scope decision 10).
2. `scripts/record_golden.py` also runs `ExemptionScript` with the switch on from 1 February 2021 to 29 April 2022 over Task 0's recordings, and writes `tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json`; the golden file pins each day's booked tax, the notes and the open claims (scope decision 11).
3. A golden test works by hand one claim of each kind (M4 §9): reinvested by its deadline (BBCA, ASII and UNVR), broken after reinvestment (TLKM, Rp224,491 of Rp504,030, tax Rp22,450 on 4 November 2021) and taxed at its deadline (ASII Rp157,500 and BBCA Rp2,500, tax Rp16,000 on 1 April 2022). The tax shows in the month it was booked.
4. The buy-and-hold golden file gains only the new keys; every existing value is unchanged.
5. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M170–M171 each turn the whole suite red.

**Files:**
- Modify: `.../steadyhand/income.py`, `__init__.py`; `scripts/record_golden.py`; `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json`
- Create: `tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json`
- Test: `tests/engine/test_income_report.py`, `tests/golden/test_golden_backtest.py`

**Interfaces:**
- Consumes: Tasks 1–3; Task 0's recordings.
- Produces: `IncomeReport.claims`, `IncomeReport.claims_label`, `CLAIMS_LABEL`; in `scripts/record_golden.py`: `ExemptionScript`, `EXEMPT_GOLDEN`, `EXEMPT_END`, `TOP_UP`, `SELL_DOWN`, `recorded(ticker, start, end, *, last=END)`, `recorded_to_exempt_end`, `run_exempt`, `record_exempt`.

- [ ] **Step 1: Branch.** `git switch -c m4/s8-report origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_income_report.py`** (changed: 2 edits)

<!-- edit: tests/engine/test_income_report.py -->
Replace:
```python
from steadyhand.engine import DayReport, EngineState
from steadyhand.income import (
    GROWTH_YEARS,
```
with:
```python
from steadyhand.engine import DayReport, EngineState
from steadyhand.exemption import DividendClaim, Protection
from steadyhand.income import (
    CLAIMS_LABEL,
    GROWTH_YEARS,
```

<!-- edit: tests/engine/test_income_report.py -->
Replace:
```python

def test_the_projection_starts_from_the_holdings_not_the_idle_cash() -> None:
```
with:
```python

def test_the_report_shows_the_open_claims_as_an_estimate() -> None:
    settings = IncomeSettings(IncomeGoal(rp(10_000)), rp(1_000))
    assert income_report(run(), final(), history(), rules(), settings).claims == ()
    protected = (Protection(rp(30_000), date(2027, 12, 31)),)
    claim = DividendClaim(
        BBCA,
        date(2025, 4, 21),
        date(2025, 5, 14),
        rp(50_000),
        date(2026, 3, 31),
        rp(20_000),
        protected,
    )
    state = final()
    claimed = EngineState(Holdings(state.holdings.portfolio, claims=(claim,)))
    got = income_report(run(), claimed, history(), rules(), settings)
    assert got.claims == (claim,)
    assert (
        got.claims_label
        == CLAIMS_LABEL
        == ("Estimate: assumes the yearly realisation reports are filed")
    )


def test_the_projection_starts_from_the_holdings_not_the_idle_cash() -> None:
```

**`tests/golden/test_golden_backtest.py`** (changed: 2 edits)

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
import pytest
from record_golden import END, GOLDEN, HISTORY_START, STOCKS, main, record, recorded, run, summary

from steadyhand import DATA_BAR_REFUSED, HISTORY_YEARS, IDR, STRATEGIES, Money, years_before
from steadyhand_idx import IdxMarketRules
```
with:
```python
import pytest
from record_golden import (
    END,
    EXEMPT_GOLDEN,
    GOLDEN,
    HISTORY_START,
    STOCKS,
    main,
    record,
    record_exempt,
    recorded,
    run,
    run_exempt,
    summary,
)

from steadyhand import (
    CLAIMS_LABEL,
    DATA_BAR_REFUSED,
    EXEMPTION_CLAIM_BROKEN,
    EXEMPTION_DEADLINE_MISSED,
    HISTORY_YEARS,
    IDR,
    STRATEGIES,
    Money,
    years_before,
)
from steadyhand_idx import IdxMarketRules
```

<!-- edit: tests/golden/test_golden_backtest.py -->
Replace:
```python
    assert written.read_bytes() == GOLDEN.read_bytes()

```
with:
```python
    assert written.read_bytes() == GOLDEN.read_bytes()


def test_the_switch_on_run_reproduces_its_stored_results_exactly(tmp_path: Path) -> None:
    stored = json.loads(EXEMPT_GOLDEN.read_text(encoding="utf-8"))
    assert summary(run_exempt(tmp_path)) == stored


def test_the_recorder_writes_the_switch_on_file_byte_for_byte(tmp_path: Path) -> None:
    written = record_exempt(tmp_path / "cache", tmp_path / "exempt.json")
    assert written.read_bytes() == EXEMPT_GOLDEN.read_bytes()


def test_the_switch_on_run_holds_a_claim_of_each_kind_as_worked_by_hand() -> None:
    stored = json.loads(EXEMPT_GOLDEN.read_text(encoding="utf-8"))
    # Each [quantity, price, fee, levy, sale tax]: the cost basis is 200 x 34,875 + 11,509 + 2,999
    # = 6,989,508 and 300 x 30,400 + 15,049 + 3,921 = 9,138,970, together 16,128,478.
    assert [f[3:8] for f in stored["fills"] if f[1] == "BBCA" and f[2] == "buy"] == [
        [200, 34_875, 11_509, 2_999, 0],
        [300, 30_400, 15_049, 3_921, 0],
    ]
    until = "2023-12-31"  # a 2021 purchase is protected through its third tax year
    assert stored["claims"] == [
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
        ["2021-11-04", EXEMPTION_CLAIM_BROKEN],
        ["2022-04-01", EXEMPTION_DEADLINE_MISSED],
        ["2022-04-01", EXEMPTION_DEADLINE_MISSED],
    ]
    assert stored["income"]["claims"] == [CLAIMS_LABEL, stored["claims"]]
    # Tax shows in the month it was booked, not the month its dividend was paid (M4 spec §6.5).
    taxed = {month[0]: month[2] for month in stored["income"]["received"]["by_month"] if month[2]}
    assert taxed == {"2021-11-01": 22_450, "2022-04-01": 16_000}

```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    BASE_GROWTH_CAP,
    GROWTH_YEARS,
```
with:
```python
    BASE_GROWTH_CAP,
    CLAIMS_LABEL,
    GROWTH_YEARS,
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "BASE_GROWTH_CAP",
    "CORPORATE_SPLIT_FRACTION_DROPPED",
```
with:
```python
    "BASE_GROWTH_CAP",
    "CLAIMS_LABEL",
    "CORPORATE_SPLIT_FRACTION_DROPPED",
```

**`packages/steadyhand/src/steadyhand/income.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
from steadyhand.engine import DayReport, EngineState
from steadyhand.market import MarketRules, add_trading_days
```
with:
```python
from steadyhand.engine import DayReport, EngineState
from steadyhand.exemption import DividendClaim
from steadyhand.market import MarketRules, add_trading_days
```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
"""Carried by every projection: it reports years, never a date (core spec §7)."""

```
with:
```python
"""Carried by every projection: it reports years, never a date (core spec §7)."""

CLAIMS_LABEL = "Estimate: assumes the yearly realisation reports are filed"
"""Carried by the exemption claims: steadyhand cannot see the investor's reports (M4 §6.4)."""

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    goal: GoalProgress

```
with:
```python
    goal: GoalProgress
    @property
    def claims_label(self) -> str:
        raise NotImplementedError("IncomeReport.claims_label")

```

**`scripts/record_golden.py`** (changed, new names stubbed: 10 edits)

<!-- edit: scripts/record_golden.py -->
Replace:
```python
"""Record the golden backtest's results (M3 spec §9).

```
with:
```python
"""Record the golden backtests' results (M3 spec §9, M4 spec §9).

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
rights issue). The recordings reach back to 31 January 2017, five years before the run ends, for
the income report's dividend growth (M4 spec §9). Run it only after a change that moves the
numbers on purpose, and review the diff: the file is never edited by hand.
"""
```
with:
```python
rights issue). The recordings reach back to 31 January 2017, five years before the run ends, for
the income report's dividend growth (M4 spec §9).

It then runs ``ExemptionScript`` with the dividend reinvestment exemption on, from 1 February 2021
to 29 April 2022, over longer recordings of the same stocks, and writes
``tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json``. That window passes the
31 March 2022 deadline of the 2021 dividends, so the run holds a claim of each kind.

Run it only after a change that moves the numbers on purpose, and review the diff: the files are
never edited by hand.
"""
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
import tempfile
from datetime import date
```
with:
```python
import tempfile
from collections.abc import Callable
from datetime import date
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    BacktestSettings,
    EngineSettings,
```
with:
```python
    BacktestSettings,
    Decision,
    DividendClaim,
    EngineSettings,
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    Market,
    Money,
    RiskLimits,
    backtest,
```
with:
```python
    Market,
    MarketView,
    Memory,
    Money,
    PortfolioView,
    RiskLimits,
    Strategy,
    backtest,
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
START, END = date(2021, 2, 1), date(2022, 1, 31)
HISTORY_START = date(2017, 1, 31)
```
with:
```python
START, END = date(2021, 2, 1), date(2022, 1, 31)
EXEMPT_GOLDEN = TESTS / "fixtures" / "golden" / "exemption-script_2021-02-01_2022-04-29.json"
EXEMPT_END = date(2022, 4, 29)
"""The switch-on run's last day, past the 31 March 2022 deadline of every 2021 dividend."""
TOP_UP, SELL_DOWN = date(2021, 7, 1), date(2021, 11, 1)
HISTORY_START = date(2017, 1, 31)
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
    return history_from_json(FIXTURES / name)

```
with:
```python
    return history_from_json(FIXTURES / name)


def recorded_to_exempt_end(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer from the longer recordings the switch-on run reads."""
    raise NotImplementedError("recorded_to_exempt_end")


class ExemptionScript:
    """The switch-on golden run's trader: it trades on three set days only (M4 spec §9).

    On its first day it buys what it can at 10% each. On ``TOP_UP`` it raises that to 19% each,
    which reinvests the dividends paid since. On ``SELL_DOWN`` it keeps half a percent in BBCA and
    sells the rest, so less is invested than is protected and part of a claim breaks. The
    dividends paid after that are never reinvested, so they are taxed at their deadline. On any
    other day it keeps what it holds. It is a test fixture, not a strategy anyone should run.
    """

    @property
    def name(self) -> str:
        raise NotImplementedError("ExemptionScript.name")

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        raise NotImplementedError("ExemptionScript.decide")

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python
        return backtest(STRATEGIES[strategy](), market, START, end, settings(income=income))

```
with:
```python
        return backtest(STRATEGIES[strategy](), market, START, end, settings(income=income))


def run_exempt(folder: Path) -> BacktestResult:
    """Back-test ``ExemptionScript`` from ``START`` to ``EXEMPT_END`` with the exemption on."""
    raise NotImplementedError("run_exempt")


def _backtest(
    folder: Path,
    strategy: Strategy,
    end: date,
    backtest_settings: BacktestSettings,
    download: Callable[[str, date, date], YahooHistory],
) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules."""
    raise NotImplementedError("_backtest")

```

<!-- edit: scripts/record_golden.py -->
Replace:
```python

def _figures(figures: IncomeFigures) -> list[int]:
```
with:
```python

def _claim(claim: DividendClaim) -> list[object]:
    raise NotImplementedError("_claim")


def _figures(figures: IncomeFigures) -> list[int]:
```

<!-- edit: scripts/record_golden.py -->
Replace:
```python

def main(argv: list[str]) -> int:
```
with:
```python

def record_exempt(folder: Path, golden: Path = EXEMPT_GOLDEN) -> Path:
    """Run the switch-on golden backtest with its cache in *folder*, and write its summary."""
    raise NotImplementedError("record_exempt")


def _write(pinned: dict[str, object], golden: Path) -> Path:
    raise NotImplementedError("_write")


def main(argv: list[str]) -> int:
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=1053 failed=4 -->
Expected: 1053 run, 4 failed: `AttributeError` for `IncomeReport.claims`; `NotImplementedError` from the stubbed `record_exempt`; and `FileNotFoundError` twice, because the switch-on golden file is written by Step 5's recording. The buy-and-hold golden tests pass, since its file and `summary` keep their base versions until Step 5.

- [ ] **Step 5: Implement, then record the golden files.**

**`packages/steadyhand/src/steadyhand/income.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
    goal: GoalProgress
    @property
    def claims_label(self) -> str:
        raise NotImplementedError("IncomeReport.claims_label")

```
with:
```python
    goal: GoalProgress
    claims: tuple[DividendClaim, ...]
    """The open reinvestment-exemption claims (M4 spec §6.5): what is left to reinvest and by
    when, and what is protected and until when. Empty with the exemption switch off."""

    @property
    def claims_label(self) -> str:
        return CLAIMS_LABEL

```

<!-- edit: packages/steadyhand/src/steadyhand/income.py -->
Replace:
```python
        goal_progress(settings.goal, received, rate),
    )
```
with:
```python
        goal_progress(settings.goal, received, rate),
        final.holdings.claims,
    )
```

**`scripts/record_golden.py`** (implemented, rewritten whole)

<!-- file: scripts/record_golden.py -->
```python
"""Record the golden backtests' results (M3 spec §9, M4 spec §9).

    uv run python scripts/record_golden.py

runs ``buy-and-hold`` over the recorded Yahoo fixtures for ASII, BBCA, BBRI, TLKM and UNVR from
1 February 2021 to 31 January 2022, with an income goal, and writes everything the golden test pins,
its income report included, to
``tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json``. The window holds BBCA's
1-for-5 split, seven cash dividends, and 146 days of BBRI prices that Yahoo cannot unadjust (its
rights issue). The recordings reach back to 31 January 2017, five years before the run ends, for
the income report's dividend growth (M4 spec §9).

It then runs ``ExemptionScript`` with the dividend reinvestment exemption on, from 1 February 2021
to 29 April 2022, over longer recordings of the same stocks, and writes
``tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json``. That window passes the
31 March 2022 deadline of the 2021 dividends, so the run holds a claim of each kind.

Run it only after a change that moves the numbers on purpose, and review the diff: the files are
never edited by hand.
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestResult,
    BacktestSettings,
    Decision,
    DividendClaim,
    EngineSettings,
    IncomeFigures,
    IncomeGoal,
    IncomeReport,
    Market,
    MarketView,
    Memory,
    Money,
    PortfolioView,
    RiskLimits,
    Strategy,
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
EXEMPT_GOLDEN = TESTS / "fixtures" / "golden" / "exemption-script_2021-02-01_2022-04-29.json"
EXEMPT_END = date(2022, 4, 29)
"""The switch-on run's last day, past the 31 March 2022 deadline of every 2021 dividend."""
TOP_UP, SELL_DOWN = date(2021, 7, 1), date(2021, 11, 1)
HISTORY_START = date(2017, 1, 31)
"""Where the recordings start: five years before the run ends (M4 spec §9)."""
STOCKS = ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")
RECORDED = date(2026, 9, 27)
"""The day the fixtures were recorded; the cache treats it as today."""


def settings(*, income: bool = True, exemption: bool = False) -> BacktestSettings:
    """Rp100,000,000, 25% a stock so that five stocks can be fully invested (M3 spec §9), and a
    goal of Rp1,000,000 a month, so that the run carries an income report (M4 spec §9)."""
    limits = RiskLimits(max_weight=Decimal("0.25"))
    goal = IncomeGoal(Money(1_000_000, IDR)) if income else None
    engine = EngineSettings(limits=limits, dividend_reinvestment_exemption=exemption)
    return BacktestSettings(Money(100_000_000, IDR), engine, goal)


def recorded(ticker: str, start: date, end: date, *, last: date = END) -> YahooHistory:
    """Yahoo's recorded answer from the recordings ending on *last*. A range outside the
    recording is refused, never invented."""
    if start < HISTORY_START or end > last:
        msg = f"{ticker}: the fixture covers {HISTORY_START} to {last}, not {start} to {end}"
        raise ValueError(msg)
    name = f"{ticker}_{HISTORY_START.isoformat()}_{last.isoformat()}.json"
    return history_from_json(FIXTURES / name)


def recorded_to_exempt_end(ticker: str, start: date, end: date) -> YahooHistory:
    """Yahoo's recorded answer from the longer recordings the switch-on run reads."""
    return recorded(ticker, start, end, last=EXEMPT_END)


class ExemptionScript:
    """The switch-on golden run's trader: it trades on three set days only (M4 spec §9).

    On its first day it buys what it can at 10% each. On ``TOP_UP`` it raises that to 19% each,
    which reinvests the dividends paid since. On ``SELL_DOWN`` it keeps half a percent in BBCA and
    sells the rest, so less is invested than is protected and part of a claim breaks. The
    dividends paid after that are never reinvested, so they are taxed at their deadline. On any
    other day it keeps what it holds. It is a test fixture, not a strategy anyone should run.
    """

    @property
    def name(self) -> str:
        return "exemption-script"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        del memory
        day, buyable = view.today, view.tradable.buyable
        if not portfolio.holdings and day < TOP_UP:
            return Decision(dict.fromkeys(buyable, Decimal("0.10")))
        if day == TOP_UP:
            return Decision(dict.fromkeys(buyable, Decimal("0.19")))
        if day == SELL_DOWN:
            return Decision(
                {stock: Decimal("0.005") for stock in buyable if stock.symbol == "BBCA"}
            )
        return Decision({stock: portfolio.weight(stock) for stock in portfolio.holdings})


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


def run(
    folder: Path, strategy: str = "buy-and-hold", end: date = END, *, income: bool = True
) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules.

    Without *income* there is no goal, so no history is fetched before ``START``: an earlier
    *end* would need recordings from before ``HISTORY_START``.
    """
    return _backtest(folder, STRATEGIES[strategy](), end, settings(income=income), recorded)


def run_exempt(folder: Path) -> BacktestResult:
    """Back-test ``ExemptionScript`` from ``START`` to ``EXEMPT_END`` with the exemption on."""
    exempt = settings(exemption=True)
    return _backtest(folder, ExemptionScript(), EXEMPT_END, exempt, recorded_to_exempt_end)


def _backtest(
    folder: Path,
    strategy: Strategy,
    end: date,
    backtest_settings: BacktestSettings,
    download: Callable[[str, date, date], YahooHistory],
) -> BacktestResult:
    """Back-test *strategy* from ``START`` to *end* through the real source, cache and rules."""
    folder.mkdir(parents=True, exist_ok=True)
    yahoo = YahooDataSource(download=download, sleep=_no_wait)
    with BarCache(folder / "bars.sqlite") as store:
        source = CachedDataSource(yahoo, store, today=lambda: RECORDED)
        market = Market(universe(), source, IdxMarketRules())
        return backtest(strategy, market, START, end, backtest_settings)


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
        "taxes": [[r.day.isoformat(), r.tax.amount] for r in outcome.reports if r.tax.amount],
        "notes": [
            [r.day.isoformat(), note.key, note.text] for r in outcome.reports for note in r.notes
        ],
        "claims": [_claim(claim) for claim in outcome.final.holdings.claims],
        "positions": {p.instrument.symbol: p.quantity for p in portfolio.positions},
        "cash": portfolio.cash_balance().amount,
        "halt": None
        if outcome.halt is None
        else [outcome.halt.day.isoformat(), outcome.halt.cause],
        "warnings": [[note.key, note.text] for note in (*result.warnings, *outcome.warnings)],
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
        "income": _income(outcome.income),
    }


def _income(report: IncomeReport | None) -> object:
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
        "claims": [report.claims_label, [_claim(claim) for claim in report.claims]],
    }


def _claim(claim: DividendClaim) -> list[object]:
    return [
        claim.instrument.symbol,
        claim.ex_date.isoformat(),
        claim.pay_date.isoformat(),
        claim.gross.amount,
        claim.deadline.isoformat(),
        claim.uncovered.amount,
        [[p.amount.amount, p.until.isoformat()] for p in claim.protections],
    ]


def _figures(figures: IncomeFigures) -> list[int]:
    return [
        figures.gross.amount,
        figures.tax.amount,
        figures.net.amount,
        figures.take_home.amount,
    ]


def record(folder: Path, golden: Path = GOLDEN) -> Path:
    """Run the golden backtest with its cache in *folder*, and write its summary to *golden*."""
    return _write(summary(run(folder)), golden)


def record_exempt(folder: Path, golden: Path = EXEMPT_GOLDEN) -> Path:
    """Run the switch-on golden backtest with its cache in *folder*, and write its summary."""
    return _write(summary(run_exempt(folder)), golden)


def _write(pinned: dict[str, object], golden: Path) -> Path:
    text = json.dumps(pinned, indent=1, sort_keys=True) + "\n"
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(text, encoding="utf-8")
    return golden


def main(argv: list[str]) -> int:
    if argv:
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as scratch:
        print(record(Path(scratch) / "buy-and-hold"))
        print(record_exempt(Path(scratch) / "exemption"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Generate `tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json sha256=195e959e386bce22782ff1de7f2077af9e96ad7bc894e0da29e50820c1306a9b -->
```bash
uv run python scripts/record_golden.py
```

Generate `tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json` by running the recorder, then check its SHA-256:

<!-- run: tests/fixtures/golden/exemption-script_2021-02-01_2022-04-29.json sha256=06cf1f5cf355903586efc681c63c81456d42462d7e29639d0e2545ded604a0f4 -->
```bash
uv run python scripts/record_golden.py
```


- [ ] **Step 6: Check the buy-and-hold figures did not move.** Only new keys may appear:

  ```bash
  uv run python - <<'EOF'
  import json, subprocess
  path = "tests/fixtures/golden/buy-and-hold_2021-02-01_2022-01-31.json"
  old = json.loads(subprocess.run(["git", "show", f"origin/develop:{path}"], capture_output=True, text=True, check=True).stdout)
  new = json.loads(open(path, encoding="utf-8").read())
  moved = sorted(k for k in old if k != "income" and old[k] != new[k])
  moved += sorted(f"income.{k}" for k in old["income"] if old["income"][k] != new["income"][k])
  added = sorted([k for k in new if k not in old] + [f"income.{k}" for k in new["income"] if k not in old["income"]])
  print(moved, added)
  EOF
  ```

  Expected: `[] ['claims', 'income.claims', 'notes', 'taxes']`.

- [ ] **Step 7: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=1053 passed=1053 -->
Expected: every command exits 0; 1053 passed, 100% branch coverage; the performance test passes (on the machine that wrote this plan, 8.0 s against the 30 s budget).

- [ ] **Step 8: Mutations.** Run M170–M171; each must turn the whole suite red with the total unchanged.
- [ ] **Step 9: Commit, push and merge** (`feat(income): M4b S8 claims in the income report and the switch-on golden run`, ending in `(#N)`).

---

## Mutation checks

Each mutation plants one realistic defect in the story's finished tree, runs the **whole** suite under `HYPOTHESIS_PROFILE=ci`, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed lines are printed before the run. The predicted catchers were written before any run; "More than predicted" lists the other tests that also went red.

| ID | Task | File | Defect planted | Total | Caught by | More than predicted |
|---|---|---|---|---|---|---|
| M140 | 1 | `fees.py` | The deadline is the 28th of its month, not the month's last day | 1021 | `test_the_deadline_is_the_last_day_of_its_month`, `test_the_exemption_dates_come_from_the_fee_tables`, `test_the_reinvestment_deadline_is_the_end_of_march_after_the_ex_date_year`, `test_with_the_exemption_a_paid_dividend_opens_a_claim_instead_of_booking_tax`, `test_with_the_exemption_on_a_dividend_opens_a_claim_the_next_state_keeps` (8 failing) | none |
| M141 | 1 | `fees.py` | Protection runs one tax year too long | 1021 | `test_protection_lasts_three_tax_years_counting_the_purchase_year`, `test_the_exemption_dates_come_from_the_fee_tables` (4 failing) | none |
| M142 | 1 | `fees.py` | A `reinvest_by_month` of 13 is accepted | 1021 | `test_bad_exemption_rows_are_refused` (1 failing) | none |
| M143 | 1 | `fees.toml` | The rule starts a day late, on 18 February 2021 | 1021 | `test_protection_lasts_three_tax_years_counting_the_purchase_year`, `test_the_exemption_starts_when_pmk_18_2021_came_into_force`, `test_the_reinvestment_deadline_is_the_end_of_march_after_the_ex_date_year` (3 failing) | none |
| M144 | 1 | `corporate.py` | A claim whose deadline is the pay day is not opened | 1021 | `test_a_claim_opens_only_while_its_deadline_can_still_be_met` (1 failing) | none |
| M145 | 1 | `engine.py` | The engine never passes the switch to the corporate step | 1021 | `test_with_the_exemption_on_a_dividend_opens_a_claim_the_next_state_keeps` (1 failing) | none |
| M146 | 1 | `engine.py` | The next day's holdings drop the open claims | 1021 | `test_with_the_exemption_on_a_dividend_opens_a_claim_the_next_state_keeps` (1 failing) | none |
| M147 | 1 | `exemption.py` | A claim's parts may add up to twice its gross | 1021 | `test_a_claims_parts_cannot_exceed_its_gross` (1 failing) | none |
| M148 | 1 | `terms.py` | `Protection.amount` has no term | 1021 | `test_every_figure_has_a_term`, `test_every_term_is_a_figures_value_and_every_value_is_a_term` (2 failing) | none |
| M149 | 2 | `exemption.py` | A buy's costs count as reinvestment | 1037 | `test_a_buy_covers_a_claim_with_its_value_before_costs` (1 failing) | none |
| M150 | 2 | `exemption.py` | Buys cover the newest claim first | 1037 | `test_a_buy_used_up_by_an_older_claim_leaves_the_newer_one_untouched`, `test_buys_cover_the_oldest_pay_date_first_and_spill_into_the_next` (2 failing) | none |
| M151 | 2 | `exemption.py` | A buy before the pay day covers the claim | 1037 | `test_only_a_buy_from_the_pay_day_to_the_deadline_covers` (1 failing) | none |
| M152 | 2 | `exemption.py` | A buy on the deadline itself does not cover | 1037 | `test_only_a_buy_from_the_pay_day_to_the_deadline_covers` (1 failing) | none |
| M153 | 2 | `exemption.py` | A sale covers claims | 1037 | `test_only_a_buy_from_the_pay_day_to_the_deadline_covers` (1 failing) | none |
| M154 | 2 | `exemption.py` | The deadline tax uses the rate in force on the day it is booked | 1037 | `test_the_deadline_tax_is_at_the_rate_in_force_on_the_pay_day` (1 failing) | none |
| M155 | 2 | `exemption.py` | The deadline tax is booked on the deadline itself | 1037 | `test_nothing_is_taxed_on_the_deadline_itself` (2 failing) | `test_only_a_buy_from_the_pay_day_to_the_deadline_covers` |
| M156 | 2 | `exemption.py` | A zero deadline tax is booked, with a note | 1037 | `test_an_untaxed_market_books_no_zero_tax_and_emits_no_note` (1 failing) | none |
| M157 | 2 | `exemption.py` | Claims with nothing left are never closed | 1037 | `test_a_claim_with_nothing_left_after_its_deadline_is_closed`, `test_a_missed_deadline_adds_its_tax_and_note_to_the_days_report`, `test_an_untaxed_market_books_no_zero_tax_and_emits_no_note` (3 failing) | none |
| M158 | 2 | `engine.py` | The day's report leaves out the claims' tax | 1037 | `test_a_missed_deadline_adds_its_tax_and_note_to_the_days_report` (1 failing) | none |
| M159 | 2 | `engine.py` | The day's report leaves out the claims' notes | 1037 | `test_a_missed_deadline_adds_its_tax_and_note_to_the_days_report` (1 failing) | none |
| M160 | 3 | `exemption.py` | A protection falls away on its last day | 1049 | `test_protections_past_their_date_fall_away_and_close_the_claim` (1 failing) | none |
| M161 | 3 | `exemption.py` | A shortfall breaks a day after its settlement date | 1049 | `test_a_broken_claim_is_taxed_at_its_pay_day_rate`, `test_a_shortfall_is_kept_across_days_and_breaks_when_its_trade_would_settle`, `test_a_shortfall_still_there_at_the_settlement_close_breaks`, `test_an_untaxed_market_breaks_the_claim_without_booking_or_a_note`, `test_breaks_take_the_latest_protection_first`, `test_each_booking_rounds_up_on_its_own`, `test_equal_dates_break_the_newest_claim_and_its_last_protection_first` (7 failing) | none |
| M162 | 3 | `exemption.py` | Each day of a shortfall restarts its grace | 1049 | `test_a_broken_claim_is_taxed_at_its_pay_day_rate`, `test_a_shortfall_is_kept_across_days_and_breaks_when_its_trade_would_settle`, `test_a_shortfall_still_there_at_the_settlement_close_breaks`, `test_a_shortfall_within_the_settlement_grace_keeps_the_claim`, `test_an_untaxed_market_breaks_the_claim_without_booking_or_a_note`, `test_breaks_take_the_latest_protection_first`, `test_each_booking_rounds_up_on_its_own`, `test_equal_dates_break_the_newest_claim_and_its_last_protection_first` (8 failing) | none |
| M163 | 3 | `exemption.py` | Breaks remove the earliest `until` first | 1049 | `test_breaks_take_the_latest_protection_first`, `test_equal_dates_break_the_newest_claim_and_its_last_protection_first` (2 failing) | none |
| M164 | 3 | `exemption.py` | A break is taxed at the rate in force on the day it is booked | 1049 | `test_a_broken_claim_is_taxed_at_its_pay_day_rate`, `test_the_deadline_tax_is_at_the_rate_in_force_on_the_pay_day` (2 failing) | none |
| M165 | 3 | `exemption.py` | The shortfall's day is kept after it breaks | 1049 | `test_a_shortfall_is_kept_across_days_and_breaks_when_its_trade_would_settle`, `test_a_shortfall_still_there_at_the_settlement_close_breaks` (2 failing) | none |
| M166 | 3 | `exemption.py` | A break removes whole protections, however small the shortfall | 1049 | `test_a_broken_claim_is_taxed_at_its_pay_day_rate`, `test_a_shortfall_still_there_at_the_settlement_close_breaks`, `test_an_untaxed_market_breaks_the_claim_without_booking_or_a_note`, `test_breaks_take_the_latest_protection_first`, `test_equal_dates_break_the_newest_claim_and_its_last_protection_first` (5 failing) | none |
| M167 | 3 | `exemption.py` | A zero break tax gets a note | 1049 | `test_an_untaxed_market_breaks_the_claim_without_booking_or_a_note` (1 failing) | none |
| M168 | 3 | `engine.py` | The engine drops the shortfall's day between days | 1049 | `test_a_shortfall_is_kept_across_days_and_breaks_when_its_trade_would_settle` (1 failing) | none |
| M169 | 3 | `corporate.py` | The corporate step drops the shortfall's day | 1049 | `test_a_shortfall_is_kept_across_days_and_breaks_when_its_trade_would_settle` (1 failing) | none |
| M170 | 4 | `income.py` | The income report shows no claims | 1053 | `test_the_recorder_writes_the_switch_on_file_byte_for_byte`, `test_the_report_shows_the_open_claims_as_an_estimate`, `test_the_switch_on_run_reproduces_its_stored_results_exactly` (3 failing) | none |
| M171 | 4 | `income.py` | The claims' label says only "Estimate" | 1053 | `test_buy_and_hold_reproduces_the_stored_results_exactly`, `test_the_recorder_writes_the_stored_file_byte_for_byte`, `test_the_recorder_writes_the_switch_on_file_byte_for_byte`, `test_the_report_shows_the_open_claims_as_an_estimate`, `test_the_switch_on_run_holds_a_claim_of_each_kind_as_worked_by_hand`, `test_the_switch_on_run_reproduces_its_stored_results_exactly` (6 failing) | none |

Planted exactly (id, task, path, anchor, replacement), as run:

```python
[('M140',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/fees.py',
  '        return date(year, month, calendar.monthrange(year, month)[1])\n',
  '        return date(year, month, 28)\n'),
 ('M141',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/fees.py',
  '        return date(purchase_day.year + exemption.hold_tax_years - 1, 12, 31)\n',
  '        return date(purchase_day.year + exemption.hold_tax_years, 12, 31)\n'),
 ('M142',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/fees.py',
  '    if month > _MONTHS:\n',
  '    if month > _MONTHS + 1:\n'),
 ('M143',
  1,
  'packages/steadyhand-idx/src/steadyhand_idx/data/fees.toml',
  'from = 2021-02-17\n',
  'from = 2021-02-18\n'),
 ('M144',
  1,
  'packages/steadyhand/src/steadyhand/corporate.py',
  '            if deadline is not None and deadline >= self._day:\n',
  '            if deadline is not None and deadline > self._day:\n'),
 ('M145',
  1,
  'packages/steadyhand/src/steadyhand/engine.py',
  '    payout = Payout(settings.pay_lag_trading_days, settings.dividend_reinvestment_exemption)\n',
  '    payout = Payout(settings.pay_lag_trading_days)\n'),
 ('M146',
  1,
  'packages/steadyhand/src/steadyhand/engine.py',
  '        portfolio, queued, holdings.entitlements, holdings.frozen, closes, holdings.claims\n',
  '        portfolio, queued, holdings.entitlements, holdings.frozen, closes\n'),
 ('M147',
  1,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        if self.uncovered + covered > self.gross:\n',
  '        if self.uncovered + covered > self.gross + self.gross:\n'),
 ('M148',
  1,
  'packages/steadyhand/src/steadyhand/terms.py',
  '        "Protection.amount": TERM_CLAIM_PROTECTED,\n',
  ''),
 ('M149',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        left = fill.gross\n',
  '        left = fill.gross + fill.costs.total\n'),
 ('M150',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '    order = sorted(range(len(current)), key=lambda i: _age(current[i]))\n',
  '    order = sorted(range(len(current)), key=lambda i: _age(current[i]), reverse=True)\n'),
 ('M151',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '            if not claim.pay_date <= fill.day <= claim.deadline or claim.uncovered.amount == '
  '0:\n',
  '            if not fill.day <= claim.deadline or claim.uncovered.amount == 0:\n'),
 ('M152',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '            if not claim.pay_date <= fill.day <= claim.deadline or claim.uncovered.amount == '
  '0:\n',
  '            if not claim.pay_date <= fill.day < claim.deadline or claim.uncovered.amount == '
  '0:\n'),
 ('M153',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        if fill.order.side is not Side.BUY:\n            continue\n',
  '        if fill.order.side is not Side.BUY:\n            pass\n'),
 ('M154',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        owed = rules.dividend_tax(claim.uncovered, on=claim.pay_date)\n',
  '        owed = rules.dividend_tax(claim.uncovered, on=day)\n'),
 ('M155',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        if day <= claim.deadline or claim.uncovered.amount == 0:\n',
  '        if day < claim.deadline or claim.uncovered.amount == 0:\n'),
 ('M156',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        if owed.amount > 0:\n',
  '        if owed.amount >= 0:\n'),
 ('M157',
  2,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '    kept = tuple(c for c in settled if c.uncovered.amount > 0 or c.protections)\n',
  '    kept = tuple(settled)\n'),
 ('M158',
  2,
  'packages/steadyhand/src/steadyhand/engine.py',
  '        tax=corporate.tax + claimed.tax,\n',
  '        tax=corporate.tax,\n'),
 ('M159',
  2,
  'packages/steadyhand/src/steadyhand/engine.py',
  '        notes=claimed.notes,\n',
  '        notes=(),\n'),
 ('M160',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '    return tuple(protection for protection in protections if protection.until >= day)\n',
  '    return tuple(protection for protection in protections if protection.until > day)\n'),
 ('M161',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        if day >= rules.settlement_date(since):\n',
  '        if day > rules.settlement_date(since):\n'),
 ('M162',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        since = day if shortfall_since is None else shortfall_since\n',
  '        since = day\n'),
 ('M163',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        for _, _, place, index in sorted(pieces, reverse=True):\n',
  '        for _, _, place, index in sorted(pieces):\n'),
 ('M164',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '        owed = self._rules.dividend_tax(amount, on=claim.pay_date)\n',
  '        owed = self._rules.dividend_tax(amount, on=self._day)\n'),
 ('M165',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '            current = close.breaks(current, protected - invested)\n            since = None\n',
  '            current = close.breaks(current, protected - invested)\n'),
 ('M166',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '            taken = min(amounts[index][place], left)\n',
  '            taken = amounts[index][place]\n'),
 ('M167',
  3,
  'packages/steadyhand/src/steadyhand/exemption.py',
  '                if owed.amount > 0:\n'
  '                    self.notes.append(_claim_broken(claim, amount, owed))\n',
  '                if owed.amount >= 0:\n'
  '                    self.notes.append(_claim_broken(claim, amount, owed))\n'),
 ('M168',
  3,
  'packages/steadyhand/src/steadyhand/engine.py',
  '        claimed.shortfall_since,\n',
  '        None,\n'),
 ('M169',
  3,
  'packages/steadyhand/src/steadyhand/corporate.py',
  '            self._shortfall_since,\n',
  '            None,\n'),
 ('M170',
  4,
  'packages/steadyhand/src/steadyhand/income.py',
  '        final.holdings.claims,\n',
  '        (),\n'),
 ('M171',
  4,
  'packages/steadyhand/src/steadyhand/income.py',
  'CLAIMS_LABEL = "Estimate: assumes the yearly realisation reports are filed"\n',
  'CLAIMS_LABEL = "Estimate"\n')]
```

## Carried forward

- **M5** saves `Holdings.claims` and `shortfall_since` with the rest of the state, renders `IncomeReport.claims` under its label, and offers the switch in `init`. A saved claim needs its `DividendClaim` and `Protection` fields; nothing else.
- **The pay-date override file** (`dividend_pay_dates.csv`, M4 §1.1) would move a claim's pay date, and with it the start of the window its buys may cover. The deadline counts from the ex-date's year and would not move unless a later spec chose the real pay year instead. It stays out of M4.
- **All twelve scope decisions amend or fill in the M4 spec.** The spec keeps its approved text; this plan is the record of each change.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

- **Pass 1 (2026-09-27): 3 findings, all fixed.** Mechanical checks first: the plan replayed from its own text (`check_plan.py`), each task's red count (51, 18, 28, 4) and gate count (1021, 1037, 1049, 1053) matched, each tree was byte-identical to its verified commit, and both golden files' SHA-256s matched; each task's **Files** list equals its story's diff (20, 7, 9 and 7 files); all 43 test names cited outside code blocks exist in the final tree; the fixtures' SHA-256s and the Task 4 golden check were run exactly as printed; the M4 spec's §6.1–§6.5, §7, §9 and §10 rows S5–S8 each map to an acceptance criterion and a test. Findings: (1) Task 0 Step 1 told the executor to record the fixtures again and then check SHA-256s that a new recording can never match (each file stores the day it was recorded); it now adds the files the plan was built from and forbids re-recording. (2) The File map grouped `corporate.py` with `engine.py` under tasks 1–3 and `__init__.py` with `notes.py` and `terms.py` under 1–3; each now has its own row with the tasks that change it. (3) "Carried forward" named scope decisions 1–5 and 10–12 as the spec changes, while 6–9 fill it in too; it now points at all of them.
- **Pass 2 (2026-09-27): 4 findings, all fixed.** Mechanical checks re-run on the rebuilt plan: the replay again matched every red and gate count, all four trees were byte-identical, and both golden SHA-256s matched (0 problems). Then a read of the header, constraints, review focus and scope decisions (the rest was read in pass 3). Findings: (1) the Goal said the settlement-cycle grace "protects through three tax years", mixing the holding period with the grace for a rotation; it now states them apart. (2) The TDD constraint gave the red-phase rule for functions only; a class that already existed also keeps its old fields (the stub rule `stubgen` follows, found when S5's first red run failed 241 unrelated tests on a constructor), and the constraint now says so. (3) Review Focus 2 said a deadline before the pay day needs "a pay lag longer than the whole window"; the condition is a lag of more than about three months, the gap from 31 December to 31 March. (4) Scope decision 1 said "Both choices" after naming one; it now names both.
- **Pass 3 (2026-09-27): 3 findings, all fixed.** Mechanical checks re-run (replay: every count matched, four trees byte-identical, 0 problems), then a read of the file map, the stories and all four tasks to the end. Findings: (1) Task 1 Step 3 still gave the stub rule for functions only; it now names classes too. (2) "Carried forward" said the pay-date override file would move a claim's deadline year, but the deadline counts from the ex-date's year (M4 §1.1, §6.1); it now says the override would move the pay date and the start of the window buys may cover. (3) "Carried forward" counted the scope decisions from 1 to 11; there are twelve.
- **Pass 4 (2026-09-27): 1 finding, fixed.** Mechanical checks re-run (replay: every count matched, four trees byte-identical, 0 problems), then a read of the whole template and every fill. Each count in the red fills was re-added from the red logs (Task 1: 27 + 9 + 7 + 3 + 5 = 51; Task 3: 24 + 4 = 28). Finding: the Task 3 red fill said S7 "changes the signature of an existing function rather than adding one", but S7 does add functions; they are private helpers the old `settle_claims` never calls, which is why no `NotImplementedError` appears. It now says that.
- **Pass 5 (2026-09-27): no findings.** Mechanical checks re-run on the rebuilt plan (replay: red 51, 18, 28 and 4 and gate 1021, 1037, 1049 and 1053 matched, four trees byte-identical, both golden SHA-256s matched, 0 problems), then a read of the whole rendered plan outside its code blocks: every task's criteria, files, interfaces and steps, the fills as rendered, the merge rules, the mutation table and the carried-forward notes. The loop closes, and the plan is approved.
