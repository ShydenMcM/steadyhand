# M3a Engine Day Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the `steadyhand` engine one complete, pure trading day: `run_day(state, inputs, strategy, rules, settings) -> (state, report)`, with the simulated fill, sizing, risk controls, the fund-style unit value, corporate actions, the no-look-ahead market view and the `buy-and-hold` baseline, all standard-library only.

**Architecture:** Every stage is a pure function over frozen values. `run_day` validates today's prices, applies corporate actions to `Holdings`, fills yesterday's orders through `SimulatedBroker`, values the portfolio and its `UnitValue`, checks for a halt, deposits any top-up, then (unless halted) asks the strategy for weights through a `MarketView` that refuses later dates, sizes them into whole lots with `CompoundingSizer`, and passes them through `RiskManager`. Nothing is changed in place; M3b's backtest repeats the day, and M5 will save each new `EngineState`.

**Tech Stack:** Python ≥ 3.12 (CI on 3.12 and 3.13), uv 0.12.18, pytest + hypothesis, mypy `--strict`, ruff. The engine gains no dependency. Tests run against the real `IdxMarketRules` shipped in M2.

**Spec:** `docs/superpowers/specs/2026-09-26-m3-engine-and-backtester-design.md` (the "M3 spec"), stories 1–6 of its §10, on top of `docs/superpowers/specs/2026-09-24-steadyhand-core-design.md` (the "core spec"). Every code block below was generated from a tree that passed the whole gate, not typed; the plan review log says how it was checked.

## Global Constraints

- The engine (`steadyhand`) stays standard-library only at runtime (core §4.2, M3 §3.2). No task adds a dependency.
- `float` never appears in the engine. `tests/meta/test_no_float.py` now scans every engine module found on disk (Task 2), not a list.
- Money is integer minor units (`Money`); rates, weights and unit values are `Decimal`. Rounding goes against the investor: a buy's price and costs round up, sale prices, proceeds and dividends round down, and weights round down so they never sum above 1 (core §4.4).
- Defaults, verbatim from the specs: slippage **0.10%**; volume cap **10%** of the day's volume; maximum weight **10%** per stock; minimum buy **1 lot**; daily loss limit **5%**; drawdown kill switch **25%** below the high-water mark; dividend pay lag **14** trading days; `monthly_contribution` **0** (none).
- Every order that is dropped or cut carries a reason (core §6.1). Every `*Error` a task adds is raised by a test that asserts its message (core §10.2).
- TDD (core §10): tests first, then stubs whose new bodies raise `NotImplementedError("<name>")`, a red run of the **whole** suite, then the implementation. A test that passes against the stubs is listed with its reason in its task. Every `pytest.raises` has a `match=` written as a raw string.
- No test computes a shared value from new code at module level; shared values come from `functools.cache` helpers called inside each test, so a stub fails the test that uses it, not the whole file at collection.
- 100% branch coverage (core §10.5). No new `# pragma: no cover`.
- Test file basenames are unique across `tests/`.
- English only. The phrase "robot trading" never appears (core §1.3). Every user-facing doc carries the disclaimer verbatim: `steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.`
- Each story gets its own branch and PR into `develop`; nothing merges into `main` (core §11).

## Review Focus

1. **A fully invested portfolio that sells on a day stamp duty is due.** Settled cash may be below Rp10,000. Expected: the sale goes ahead and the charge settles with its proceeds at T+2, so settled cash never goes negative and a rebalancing strategy is never stuck. Pinned in Task 3 (`test_a_sales_only_day_nets_its_stamp_duty_with_the_sales`, `test_fills_keep_cash_whole_lots_ticks_and_bands`).
2. **A stock priced under Rp200**, where the tick is Rp1 and slippage alone decides the price. Expected: a buy at an open of 150 pays 151 and a sale receives 149. Pinned in Task 3 (`test_slippage_rounds_against_the_trader_before_the_tick`).
3. **A reverse split that leaves a holding with a fraction of a share, or with none.** Expected: the fraction is dropped with a warning naming both share counts, and a holding that rounds to nothing is removed. Pinned in Task 1 (`test_a_holding_that_rounds_to_nothing_is_removed`) and Task 5 (`test_a_split_that_leaves_no_whole_share_warns_with_zero`).
4. **A held stock with no bar today and no stored close at all.** Expected: the day stops with `MissingPriceError` naming the stock; it is never valued at zero. Pinned in Task 6 (`test_a_held_stock_with_no_price_at_all_stops_the_day`).
5. **A deposit on a day the market falls.** Expected: the deposit buys units at today's price, so it neither hides the fall from the daily loss limit nor looks like a gain. Pinned in Task 4 (`test_a_deposit_never_moves_the_price`) and Task 6 (`test_the_monthly_contribution_arrives_on_the_months_first_trading_day`).

## Scope decisions (read before starting)

1. **Spendable cash, and stamp duty netted with the day's trades.** M3 §5 step 4 caps a buy at "settled cash". The day's stamp duty is charged once, after the last fill, so on a day with sales only it could push settled cash below zero, and refusing the sale instead would leave a fully invested portfolio unable to sell for want of Rp10,000. So the charge settles with the trades: on the day when anything was bought, at T+2 on a day of sales only. To stop that later-settling debit being spent twice, `Portfolio` gains `spendable_cash(on)`: credits settled by then, less **every** debit whatever its settlement date. Buys (the broker's, the risk manager's and `Portfolio`'s own guard) are capped at spendable cash and reserve the day's charge; a sale is refused only when even its own proceeds could not pay it. `settled_cash` keeps its meaning and never goes negative (Task 3's property test).
2. **`Portfolio.apply_split(split)`** takes a `Split` rather than M3 §3.3's `(instrument, old_shares, new_shares, on)`, so the ratio is validated in one place.
3. **The strategy protocol keeps a memory.** Core §4.3's `target_weights(view, portfolio)` becomes `decide(view, portfolio, memory) -> Decision(weights, memory)`. `buy-and-hold` must remember the set it fixed on its first day; keeping that in the strategy object would make `run_day` impure and lose the set on a restart. The memory is text (`Mapping[str, str]`), so M5 can save it with the state.
4. **The sizer only does the arithmetic; the risk manager owns every limit.** M3 §6.2 has the sizer cap buys at settled cash; core §6.1 lists "cash only" as a risk control. Cash, the tradable set, the 10% cap and the minimum buy are all applied in `RiskManager.check`, so every dropped or cut order gets its reason from one place.
5. **`DayInputs` carries a `PriceHistory`, not a `MarketView`.** The view needs today's tradable set, which depends on frozen stocks held in the state, so `run_day` builds it. `DayInputs.resumed` names the stocks whose data is clean again today after refused days: the band check skips them (M3 §7.4), and M3b's backtest fills it in.
6. **A limit reached is a limit breached.** A daily fall of exactly 5% halts, and so does a drawdown of exactly 25% (core §10.2 tests each limit at its threshold and one step past it).
7. **The minimum size applies to buys.** It is a minimum *position* size (core §6.1); a sale is never refused for being small.
8. **Refused days are not freezes.** A stock whose data is refused today is outside the tradable set today only. An exclusion of a held stock and any `OtherAction` freeze it for the rest of the run, as the specs say.
9. **Running a day twice raises `DayOrderError`.** M5 turns that into the "already ran" report (core §6.1).
10. **Two guards are tightened on the way.** The no-float guard scans the whole engine package found on disk (Task 2); the disclaimer guard covers every user-facing doc under `docs/` and ignores a disclaimer hidden in an HTML comment (Task 1), which a reader never sees.
11. **Engine tests use the real IDX rules.** Ticks, bands, fees, stamp duty, T+2 and the holiday calendar are M2's shipped data, so every price and cost in a test is a real one. One test subclasses `IdxMarketRules` with no dividend tax, to reach the branch where no tax is booked.
12. **`Lq45Universe` is story 1's** (M3 §7.2's adapter), so the `Universe` protocol has a real implementation from the start. The `survivorship_warnings` change stays in M3b's story 7.
13. **A dividend and a split on the same ex-date:** the dividend is earned on the shares held at the previous close, before the split.

## File map

| File | Task | Responsibility |
|---|---|---|
| `packages/steadyhand/src/steadyhand/data.py` | 1 | `UnavailableDaysError` |
| `.../steadyhand/universe.py` | 1 | The `Universe` protocol |
| `.../steadyhand/portfolio.py` | 1 | Dividend, tax and daily-cost movements; `spendable_cash`; `apply_split` |
| `.../steadyhand-idx/src/steadyhand_idx/universe.py`, `yahoo.py` | 1 | `Lq45Universe`; `UnrecoverablePricesError` becomes an `UnavailableDaysError` |
| `.../steadyhand/_ratio.py`, `view.py` | 2 | `ratio_down`; `PriceHistory`, `Tradable`, `MarketView`, `LookAheadError`, `PortfolioView` |
| `.../steadyhand/strategies/` | 2 | `Strategy`, `Decision`, `Memory`, `BuyAndHold`, `STRATEGIES` |
| `docs/strategies/buy-and-hold.md` | 2 | The strategy's plain-English guide |
| `.../steadyhand/outcomes.py`, `broker/simulated.py` | 3 | `Rejected`, `Cut`; `SimulatedBroker`, `FillSettings`, `Opening`, `FillResult` |
| `.../steadyhand/sizing.py`, `risk.py` | 4 | `Sizer`, `CompoundingSizer`; `RiskLimits`, `RiskManager`, `Halt`, `UnitValue`, `Checked` |
| `.../steadyhand/corporate.py` | 5 | `Entitlement`, `Holdings`, `apply_actions` |
| `.../steadyhand/engine.py` | 6 | `EngineState`, `DayInputs`, `DayReport`, `EngineSettings`, `run_day`, the two errors |
| `.../steadyhand/__init__.py`, `broker/__init__.py`, `steadyhand_idx/__init__.py` | 1–6 | The public API, growing with each story |
| `tests/meta/test_disclaimer.py`, `test_no_float.py`, `test_strategy_guides.py` | 1, 2 | The guards |

## Stories

Each task below is one story on the `steadyhand` board, filed with its acceptance criteria before work starts (Task 0). The "Acceptance criteria" block in each task is the text of the story.

| Task | Story | Branch |
|---|---|---|
| 0 | The M3a plan and the stories (docs) | `m3/spec` |
| 1 | S1 Engine additions: Universe, unavailable days, portfolio movements, disclaimer guard | `m3/s1-engine-additions` |
| 2 | S2 MarketView, the Strategy protocol and buy-and-hold | `m3/s2-view-strategy` |
| 3 | S3 SimulatedBroker | `m3/s3-broker` |
| 4 | S4 Sizing, risk and the unit value | `m3/s4-sizing-risk` |
| 5 | S5 Corporate actions | `m3/s5-corporate` |
| 6 | S6 run_day with validation | `m3/s6-run-day` |

Stories merge in order: each one's code imports the ones before it.

**Merging a story (every task):** push the branch and open a PR into `develop` whose body says `Refs #<story>`. Never put `close`, `fix` or `resolve` next to an issue number, not even in a negation. Write the PR head SHA to a file so it is never retyped: `gh pr view <pr> --json headRefOid --jq .headRefOid > "${TMPDIR}/head-sha"`. Find the CI run for exactly that SHA with `gh run list --branch <branch> --json databaseId,headSha,status,conclusion`, matching `headSha` against the file yourself. Poll `gh run view <id> --json status,jobs` until `status` is `completed`, then read every job by name; each must be `success`. Then ask Shyden to approve the merge with `AskUserQuestion`, naming the PR, the head SHA **as read from the file in that same turn** (`cut -c1-7 "${TMPDIR}/head-sha"`), and the CI state. Merge with `gh pr merge <pr> --squash --delete-branch --match-head-commit "$(cat "${TMPDIR}/head-sha")"`. **Deploy:** the `develop` run that follows publishes both packages to TestPyPI; find it the same way, by the merge commit's SHA, and read `publish-dev` by name. Then close the story with a comment linking the PR and the develop run, and move its card to Done, reading the card back through its `PVTI_` node (not `gh project item-list`, which lags).

**Pushing:** agent sessions push, open PRs and merge as the `steadyhand-agent` GitHub App. The board stays on the operator's login.

**Running a step's commands:** the shell is zsh. Capture a command's exit status with no pipe in between (`uv run pytest … > out.txt 2>&1; rc=$?`), then read the file: a status read through `| tail` is `tail`'s, and it always looks like success.

---

### Task 0: The M3a plan and the stories

Documentation only, on `m3/spec`, whose PR carries the M3 spec, this plan and `HANDOVER.md` (#61).

- [ ] **Step 1: File the stories.** Create one issue per task 1–6, titled as in the Stories table, whose body is that task's acceptance criteria. Add each to the board with `gh project item-add 1 --owner ShydenMcM --url <issue url> --format json`, set Status to Todo, and read each card back through its `PVTI_` node, asserting `project.title` is `steadyhand`.
- [ ] **Step 2: Open the PR** from `m3/spec` into `develop` (`Refs #61`), and merge it as **Merging a story** says.

---

### Task 1: S1 Engine additions: Universe, unavailable days, portfolio movements, disclaimer guard

**Acceptance criteria (story text):**
1. `steadyhand.Universe` is a runtime-checkable protocol with `members_on(day) -> frozenset[Instrument]`, `excluded_on(day) -> Mapping[Instrument, str]` and `first_day() -> date` (M3 §7.2). `steadyhand_idx.Lq45Universe(membership, exclusions=None)` implements it: members are IDX instruments from the list in force, exclusions carry their reasons, the first day is the first list's effective date, and a day before it raises `MembershipUnknownError`.
2. `steadyhand.UnavailableDaysError(message, days)` is a `DataUnavailableError` whose `days` holds at least one day, all different and in order. `UnrecoverablePricesError` is one.
3. `MovementKind` gains `DIVIDEND`, `TAX` and `DAILY_COST`. `Portfolio.credit_dividend(gross, on)` books a positive dividend settled that day. `Portfolio.charge(kind, amount, on, *, settles_on=None)` books tax or a daily cost, and refuses any other kind.
4. `Portfolio.spendable_cash(on)` is the credits settled by *on* less every debit, whatever its settlement date, and a buy is refused when it needs more (scope decision 1).
5. `Portfolio.apply_split(split)` scales the holding by the ratio, rounding down, keeps the total cost basis, removes a holding that rounds to no shares, and refuses a stock not held. A hypothesis property holds the basis over any ratio.
6. The disclaimer guard covers every Markdown file under `docs/` outside `superpowers/` and `research/`, found on disk, and ignores text inside HTML comments.
7. The engine exports `Universe` and `UnavailableDaysError`; the IDX package exports `Lq45Universe`. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M1–M6 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/universe.py`
- Modify: `packages/steadyhand/src/steadyhand/data.py`, `.../steadyhand/portfolio.py`, `.../steadyhand/__init__.py`, `packages/steadyhand-idx/src/steadyhand_idx/universe.py`, `.../steadyhand_idx/yahoo.py`, `.../steadyhand_idx/__init__.py`
- Test: create `tests/engine/test_data_errors.py`, `tests/engine/test_portfolio_actions.py`, `tests/idx/test_lq45_universe.py`; modify `tests/engine/test_portfolio.py`, `tests/engine/test_protocols.py`, `tests/idx/test_yahoo.py`, `tests/meta/test_disclaimer.py`

**Interfaces:**
- Consumes: M1's `Portfolio`, `Split`, `Money`; M2's `Lq45Membership`, `Exclusions`, `UnrecoverablePricesError`.
- Produces: `UnavailableDaysError(message: str, days: Sequence[date])` with `.days: tuple[date, ...]`; `Universe` (`members_on`, `excluded_on`, `first_day`); `MovementKind.DIVIDEND`, `.TAX`, `.DAILY_COST`; `Portfolio.spendable_cash(on: date) -> Money`, `.credit_dividend(gross: Money, on: date) -> Portfolio`, `.charge(kind: MovementKind, amount: Money, on: date, *, settles_on: date | None = None) -> Portfolio`, `.apply_split(split: Split) -> Portfolio`; `Lq45Universe(membership: Lq45Membership, exclusions: Exclusions | None = None)`.

- [ ] **Step 1: Branch.** `git switch -c m3/s1-engine-additions origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_data_errors.py`** (new)

<!-- file: tests/engine/test_data_errors.py -->
```python
"""UnavailableDaysError: a source's refusal of particular days, which a backtest can skip."""

from datetime import date

import pytest

from steadyhand.data import DataUnavailableError, UnavailableDaysError

DAYS = (date(2021, 9, 6), date(2021, 9, 7))


def test_it_names_the_days_and_keeps_the_message() -> None:
    message = "BBRI: two days refused"
    with pytest.raises(UnavailableDaysError, match=r"^BBRI: two days refused$") as caught:
        raise UnavailableDaysError(message, list(DAYS))
    assert caught.value.days == DAYS
    assert isinstance(caught.value, DataUnavailableError)


def test_it_needs_at_least_one_day() -> None:
    with pytest.raises(ValueError, match=r"^an unavailable-days error must name at least one day$"):
        UnavailableDaysError("nothing", [])


@pytest.mark.parametrize("days", [DAYS[::-1], (DAYS[0], DAYS[0])])
def test_the_days_are_different_and_in_order(days: tuple[date, ...]) -> None:
    with pytest.raises(ValueError, match=r"^the unavailable days must be different and in date"):
        UnavailableDaysError("bad", days)
```

**`tests/engine/test_portfolio.py`** (changed: 1 edit)

<!-- edit: tests/engine/test_portfolio.py -->
Replace:
```python
            InsufficientCashError,
            match="2026-01-05: needs IDR 1,245,450 but only IDR 1,245,449 is settled",
        ):
```
with:
```python
            InsufficientCashError,
            match="2026-01-05: needs IDR 1,245,450 but only IDR 1,245,449 can be spent",
        ):
```

**`tests/engine/test_portfolio_actions.py`** (new)

<!-- file: tests/engine/test_portfolio_actions.py -->
```python
"""Portfolio: dividends, tax and daily costs as cash movements, and splits (M3 spec §3.3)."""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import ChronologyError, InsufficientCashError, MovementKind, Portfolio
from steadyhand.types import Costs, Fill, Instrument, Order, Side, Split

D0 = date(2026, 1, 5)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
USD = Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(quantity: int, cost: int, stock: Instrument = BBRI) -> Portfolio:
    """A portfolio that bought *quantity* shares for exactly *cost*, with nothing left over."""
    order = Order(stock, Side.BUY, quantity, D0)
    price, remainder = divmod(cost, quantity)
    fill = Fill(order, D0, quantity, rp(price), Costs(rp(remainder), rp(0), rp(0)))
    return Portfolio.empty(IDR).deposit(rp(cost), D0).apply_fill(fill, D0)


def test_the_new_movement_kinds() -> None:
    kinds = {kind.name: kind.value for kind in MovementKind}
    assert kinds == {
        "DEPOSIT": "deposit",
        "BUY": "buy",
        "SELL": "sell",
        "DIVIDEND": "dividend",
        "TAX": "tax",
        "DAILY_COST": "daily cost",
    }


def test_a_dividend_is_settled_cash_on_the_day_it_is_paid() -> None:
    paid = holding(100, 400_000).credit_dividend(rp(12_345), D0 + timedelta(days=1))
    movement = paid.ledger[-1]
    assert (movement.kind, movement.amount, movement.settles_on) == (
        MovementKind.DIVIDEND,
        rp(12_345),
        D0 + timedelta(days=1),
    )
    assert paid.settled_cash(D0 + timedelta(days=1)) == rp(12_345)
    assert paid.positions == holding(100, 400_000).positions


@pytest.mark.parametrize("kind", [MovementKind.TAX, MovementKind.DAILY_COST])
def test_a_charge_is_debited_on_its_day(kind: MovementKind) -> None:
    charged = Portfolio.empty(IDR).deposit(rp(50_000), D0).charge(kind, rp(10_000), D0)
    movement = charged.ledger[-1]
    assert (movement.kind, movement.amount, movement.settles_on) == (kind, rp(-10_000), D0)
    assert charged.settled_cash(D0) == rp(40_000)
    assert charged.cash_balance() == rp(40_000)


def test_a_deferred_charge_is_held_back_from_spending_at_once() -> None:
    later = D0 + timedelta(days=2)
    charged = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    charged = charged.charge(MovementKind.DAILY_COST, rp(10_000), D0, settles_on=later)
    assert (charged.settled_cash(D0), charged.spendable_cash(D0)) == (rp(50_000), rp(40_000))
    assert (charged.settled_cash(later), charged.spendable_cash(later)) == (rp(40_000), rp(40_000))
    order = Order(BBRI, Side.BUY, 45, D0)
    buy = Fill(order, D0, 45, rp(1_000), Costs.zero(IDR))
    with pytest.raises(
        InsufficientCashError,
        match=r"^2026-01-05: needs IDR 45,000 but only IDR 40,000 can be spent$",
    ):
        charged.apply_fill(buy, later)


def test_sale_proceeds_are_spendable_once_settled() -> None:
    later = D0 + timedelta(days=2)
    order = Order(BBRI, Side.SELL, 100, D0)
    sold = holding(100, 100_000).apply_fill(Fill(order, D0, 100, rp(1_000), Costs.zero(IDR)), later)
    assert (sold.spendable_cash(D0), sold.spendable_cash(later)) == (rp(0), rp(100_000))


def test_a_charge_cannot_settle_before_it_is_made() -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(
        ValueError, match=r"^settles on 2026-01-04, before the trade on 2026-01-05$"
    ):
        funded.charge(MovementKind.TAX, rp(1), D0, settles_on=D0 - timedelta(days=1))


@pytest.mark.parametrize("kind", [MovementKind.DEPOSIT, MovementKind.DIVIDEND, MovementKind.BUY])
def test_only_tax_and_daily_costs_are_charges(kind: MovementKind) -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(
        ValueError, match=rf"^charge books tax or a daily cost, not a {kind.value}$"
    ):
        funded.charge(kind, rp(1), D0)


def test_a_charge_kind_must_be_a_movement_kind() -> None:
    with pytest.raises(TypeError, match=r"^kind must be a MovementKind, got str$"):
        Portfolio.empty(IDR).charge("tax", rp(1), D0)  # type: ignore[arg-type]


@pytest.mark.parametrize("amount", [0, -1])
def test_dividends_and_charges_must_be_positive(amount: int) -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(ValueError, match=rf"^a dividend must be positive, got IDR {amount}$"):
        funded.credit_dividend(rp(amount), D0)
    with pytest.raises(ValueError, match=rf"^a tax must be positive, got IDR {amount}$"):
        funded.charge(MovementKind.TAX, rp(amount), D0)


def test_dividends_and_charges_check_currency_type_and_date() -> None:
    funded = Portfolio.empty(IDR).deposit(rp(50_000), D0)
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        funded.credit_dividend(Money(100, USD), D0)
    with pytest.raises(TypeError, match=r"^amount must be a Money, got int$"):
        funded.charge(MovementKind.DAILY_COST, 10_000, D0)  # type: ignore[arg-type]
    with pytest.raises(ChronologyError, match=r"^2026-01-04 is before the last recorded"):
        funded.credit_dividend(rp(1), D0 - timedelta(days=1))


def test_a_split_scales_the_quantity_and_keeps_the_basis() -> None:
    split = holding(300, 1_200_000).apply_split(Split(BBRI, D0, 1, 5))
    only = split.positions[0]
    assert (only.quantity, only.cost_basis) == (1_500, rp(1_200_000))
    assert split.ledger == holding(300, 1_200_000).ledger


def test_a_reverse_split_drops_the_fraction_of_a_share() -> None:
    split = holding(1_203, 1_203_000).apply_split(Split(BBRI, D0, 5, 1))
    only = split.positions[0]
    assert (only.quantity, only.cost_basis) == (240, rp(1_203_000))


def test_a_holding_that_rounds_to_nothing_is_removed() -> None:
    split = holding(4, 4_000).apply_split(Split(BBRI, D0, 5, 1))
    assert split.positions == ()
    assert split.cash_balance() == rp(0)


def test_a_split_leaves_other_holdings_alone() -> None:
    both = holding(100, 100_000).deposit(rp(200_000), D0)
    order = Order(TLKM, Side.BUY, 200, D0)
    both = both.apply_fill(Fill(order, D0, 200, rp(1_000), Costs.zero(IDR)), D0)
    split = both.apply_split(Split(TLKM, D0, 1, 2))
    assert [(p.instrument.symbol, p.quantity) for p in split.positions] == [
        ("BBRI", 100),
        ("TLKM", 400),
    ]


def test_a_split_needs_a_holding_a_split_and_a_date_in_order() -> None:
    with pytest.raises(ValueError, match=r"^2026-01-05: no TLKM is held to split$"):
        holding(100, 100_000).apply_split(Split(TLKM, D0, 1, 5))
    with pytest.raises(TypeError, match=r"^split must be a Split, got tuple$"):
        holding(100, 100_000).apply_split((BBRI, D0, 1, 5))  # type: ignore[arg-type]
    with pytest.raises(ChronologyError, match=r"^2026-01-04 is before the last recorded"):
        holding(100, 100_000).apply_split(Split(BBRI, D0 - timedelta(days=1), 1, 5))


@given(
    quantity=st.integers(min_value=1, max_value=10**6),
    cost=st.integers(min_value=10**6, max_value=10**9),
    ratio=st.tuples(st.integers(1, 20), st.integers(1, 20)).filter(lambda r: r[0] != r[1]),
)
def test_splits_keep_the_total_cost_basis(quantity: int, cost: int, ratio: tuple[int, int]) -> None:
    before = holding(quantity, cost)
    after = before.apply_split(Split(BBRI, D0, *ratio))
    expected = quantity * ratio[1] // ratio[0]
    if expected == 0:
        assert after.positions == ()
    else:
        assert (after.positions[0].quantity, after.positions[0].cost_basis) == (expected, rp(cost))
    assert after.cash_balance() == before.cash_balance()
```

**`tests/engine/test_protocols.py`** (changed: 3 edits)

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python

from collections.abc import Sequence
from datetime import date, timedelta
```
with:
```python

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
```

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python
from steadyhand.types import Bar, CorporateAction, Costs, Fill, Instrument, Order, OrderAck, Side

```
with:
```python
from steadyhand.types import Bar, CorporateAction, Costs, Fill, Instrument, Order, OrderAck, Side
from steadyhand.universe import Universe

```

<!-- edit: tests/engine/test_protocols.py -->
Replace:
```python
        raise DataUnavailableError(message)
```
with:
```python
        raise DataUnavailableError(message)


class _MinimalUniverse:
    def members_on(self, day: date) -> frozenset[Instrument]:
        return frozenset({Instrument("BBRI", "IDX", IDR)})

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        return {}

    def first_day(self) -> date:
        return date(2021, 1, 4)


def test_a_minimal_class_satisfies_universe() -> None:
    universe: Universe = _MinimalUniverse()
    assert isinstance(universe, Universe)
    assert not isinstance(_MinimalSource(), Universe)
```

**`tests/idx/test_lq45_universe.py`** (new)

<!-- file: tests/idx/test_lq45_universe.py -->
```python
"""Lq45Universe: the user's LQ45 lists and exclusions, as the engine's Universe (M3 spec §7.2)."""

from datetime import date
from itertools import product

import pytest

from steadyhand import IDR, Instrument, Universe
from steadyhand_idx.universe import (
    Exclusion,
    Exclusions,
    Lq45Membership,
    Lq45Record,
    Lq45Universe,
    MembershipUnknownError,
)

CODES = ["Z" + "".join(letters) for letters in product("ABCDEFGHIJ", repeat=3)][:46]
FIRST = date(2021, 2, 1)
SECOND = date(2021, 8, 2)


def membership() -> Lq45Membership:
    return Lq45Membership(
        [
            Lq45Record(FIRST, date(2021, 1, 25), "Peng-1", "review", frozenset(CODES[:45])),
            Lq45Record(SECOND, date(2021, 7, 26), "Peng-2", "review", frozenset(CODES[1:])),
        ]
    )


def stock(code: str) -> Instrument:
    return Instrument(code, "IDX", IDR)


def test_it_is_the_engines_universe() -> None:
    universe: Universe = Lq45Universe(membership())
    assert isinstance(universe, Universe)


def test_members_are_idx_instruments_from_the_list_in_force() -> None:
    universe = Lq45Universe(membership())
    assert universe.members_on(FIRST) == frozenset(stock(code) for code in CODES[:45])
    assert universe.members_on(SECOND) == frozenset(stock(code) for code in CODES[1:])
    assert stock(CODES[0]) in universe.members_on(date(2021, 8, 1))


def test_the_first_day_is_the_first_list_and_nothing_before_it_is_guessed() -> None:
    universe = Lq45Universe(membership())
    assert universe.first_day() == FIRST
    with pytest.raises(MembershipUnknownError, match=r"no LQ45 list in force on 2021-01-29"):
        universe.members_on(date(2021, 1, 29))


def test_exclusions_are_instruments_with_their_reasons() -> None:
    kept_out = Exclusions([Exclusion(CODES[3], FIRST, date(2021, 3, 31), "Special Monitoring")])
    universe = Lq45Universe(membership(), kept_out)
    assert universe.excluded_on(date(2021, 3, 31)) == {stock(CODES[3]): "Special Monitoring"}
    assert universe.excluded_on(date(2021, 4, 1)) == {}


def test_no_exclusions_by_default() -> None:
    assert Lq45Universe(membership()).excluded_on(FIRST) == {}
```

**`tests/idx/test_yahoo.py`** (changed: 2 edits)

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python
    Split,
)
```
with:
```python
    Split,
    UnavailableDaysError,
)
```

<!-- edit: tests/idx/test_yahoo.py -->
Replace:
```python
        unadjust(history, BBRI, calendar(), date(2021, 8, 2), date(2021, 9, 30))
    assert isinstance(caught.value, DataUnavailableError)
    assert caught.value.days == calendar().trading_days(date(2021, 8, 2), date(2021, 9, 7))
```
with:
```python
        unadjust(history, BBRI, calendar(), date(2021, 8, 2), date(2021, 9, 30))
    assert isinstance(caught.value, UnavailableDaysError)
    assert caught.value.days == calendar().trading_days(date(2021, 8, 2), date(2021, 9, 7))
```

**`tests/meta/test_disclaimer.py`** (changed: 4 edits)

<!-- edit: tests/meta/test_disclaimer.py -->
Replace:
```python

from pathlib import Path
```
with:
```python

import re
from pathlib import Path
```

<!-- edit: tests/meta/test_disclaimer.py -->
Replace:
```python
ROOT = Path(__file__).resolve().parents[2]


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, with quote markers removed."""
    lines = (line.strip().removeprefix(">").strip() for line in markdown.splitlines())
    return " ".join(" ".join(lines).split())

```
with:
```python
ROOT = Path(__file__).resolve().parents[2]
# Plans, specs and research notes are for the people building steadyhand, not its users.
INTERNAL = frozenset({"superpowers", "research"})
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, quote markers and comments removed.

    A disclaimer inside an HTML comment is never shown to a reader, so it does not count.
    """
    shown = _COMMENT.sub(" ", markdown)
    lines = (line.strip().removeprefix(">").strip() for line in shown.splitlines())
    return " ".join(" ".join(lines).split())


def user_docs(docs: Path) -> list[Path]:
    """Every Markdown file under *docs* except the internal folders, found on disk."""
    return sorted(
        path for path in docs.rglob("*.md") if path.relative_to(docs).parts[0] not in INTERNAL
    )


def missing_disclaimer(paths: list[Path]) -> list[str]:
    return [
        path.relative_to(ROOT).as_posix()
        for path in paths
        if DISCLAIMER not in normalised(path.read_text(encoding="utf-8"))
    ]

```

<!-- edit: tests/meta/test_disclaimer.py -->
Replace:
```python

def test_every_readme_carries_the_disclaimer() -> None:
```
with:
```python

def test_normalising_drops_html_comments() -> None:
    assert normalised("one <!-- hidden\nstill hidden --> two") == "one two"


def test_user_docs_skip_only_the_internal_folders(tmp_path: Path) -> None:
    for name in ("guide.md", "strategies/a.md", "superpowers/plan.md", "research/t.md", "x.txt"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("text", encoding="utf-8")
    found = [path.relative_to(tmp_path).as_posix() for path in user_docs(tmp_path)]
    assert found == ["guide.md", "strategies/a.md"]


def test_every_readme_carries_the_disclaimer() -> None:
```

<!-- edit: tests/meta/test_disclaimer.py -->
Replace:
```python
    assert len(readmes) == 3
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in readmes
        if DISCLAIMER not in normalised(path.read_text(encoding="utf-8"))
    ]
    assert missing == []
```
with:
```python
    assert len(readmes) == 3
    assert missing_disclaimer(readmes) == []


def test_every_user_facing_doc_carries_the_disclaimer() -> None:
    docs = user_docs(ROOT / "docs")
    assert ROOT / "docs/lq45-members.md" in docs
    assert missing_disclaimer(docs) == []
```


- [ ] **Step 3: Write the stubs.** New names only; everything that existed keeps its current body.

**`packages/steadyhand-idx/src/steadyhand_idx/__init__.py`** (changed, new names stubbed: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
Replace:
```python
from steadyhand_idx.rules import IdxMarketRules, RuleTables
from steadyhand_idx.universe import Exclusions, Lq45Membership, MembershipUnknownError
from steadyhand_idx.yahoo import UnrecoverablePricesError, YahooDataSource
```
with:
```python
from steadyhand_idx.rules import IdxMarketRules, RuleTables
from steadyhand_idx.universe import (
    Exclusions,
    Lq45Membership,
    Lq45Universe,
    MembershipUnknownError,
)
from steadyhand_idx.yahoo import UnrecoverablePricesError, YahooDataSource
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/__init__.py -->
Replace:
```python
    "Lq45Membership",
    "MembershipUnknownError",
```
with:
```python
    "Lq45Membership",
    "Lq45Universe",
    "MembershipUnknownError",
```

**`packages/steadyhand-idx/src/steadyhand_idx/universe.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python
    return Exclusion(symbol, start, end, reason)
```
with:
```python
    return Exclusion(symbol, start, end, reason)


class Lq45Universe:
    """The engine's ``Universe`` for IDX: the LQ45 on each day, and the operator's exclusions."""

    def __init__(self, membership: Lq45Membership, exclusions: Exclusions | None = None) -> None:
        raise NotImplementedError("Lq45Universe.__init__")

    def members_on(self, day: date) -> frozenset[Instrument]:
        raise NotImplementedError("Lq45Universe.members_on")

    def excluded_on(self, day: date) -> dict[Instrument, str]:
        raise NotImplementedError("Lq45Universe.excluded_on")

    def first_day(self) -> date:
        raise NotImplementedError("Lq45Universe.first_day")
```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    Split,
)
```
with:
```python
    Split,
    UnavailableDaysError,
)
```

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError
from steadyhand.disclaimer import DISCLAIMER
```
with:
```python
from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
from steadyhand.disclaimer import DISCLAIMER
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    Split,
)

__version__: str = version("steadyhand")
```
with:
```python
    Split,
)
from steadyhand.universe import Universe

__version__: str = version("steadyhand")
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Split",
    "UnsupportedDateError",
```
with:
```python
    "Split",
    "UnavailableDaysError",
    "Universe",
    "UnsupportedDateError",
```

**`packages/steadyhand/src/steadyhand/data.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/data.py -->
Replace:
```python
    """A data source could not supply what was asked for. The daily run stops without trading."""

```
with:
```python
    """A data source could not supply what was asked for. The daily run stops without trading."""


class UnavailableDaysError(DataUnavailableError):
    """A data source refuses particular days for one stock, and ``days`` names every one.

    A backtest leaves the stock untraded on those days and fetches the clean days around them
    (M3 spec §7.3). Any other ``DataUnavailableError`` stops the run.
    """

    def __init__(self, message: str, days: Sequence[date]) -> None:
        raise NotImplementedError("UnavailableDaysError.__init__")

```

**`packages/steadyhand/src/steadyhand/portfolio.py`** (changed, new names stubbed: 8 edits)

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
balance to keep in step. Buys are debited on the trade date, which is conservative: the broker
takes the money at settlement, but the cash is never available to spend twice.
"""
```
with:
```python
balance to keep in step. Buys are debited on the trade date, which is conservative: the broker
takes the money at settlement, but the cash is never available to spend twice. A debit that
settles later, such as a day's stamp duty netted with its trades, is held back the same way:
``spendable_cash`` subtracts every debit at once and adds a credit only once it has settled.
"""
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
from steadyhand.money import Currency, CurrencyMismatchError, Money
from steadyhand.types import Fill, Instrument, Position, Side

```
with:
```python
from steadyhand.money import Currency, CurrencyMismatchError, Money
from steadyhand.types import Fill, Instrument, Position, Side, Split

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
    SELL = "sell"

```
with:
```python
    SELL = "sell"
    DIVIDEND = "dividend"
    TAX = "tax"
    DAILY_COST = "daily cost"


_CHARGES = frozenset({MovementKind.TAX, MovementKind.DAILY_COST})
"""The movements ``Portfolio.charge`` books: money taken that buys nothing."""

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
class InsufficientCashError(ValueError):
    """A buy needs more settled cash than the portfolio has."""

```
with:
```python
class InsufficientCashError(ValueError):
    """A buy needs more cash than the portfolio can spend."""

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python

    def unsettled_cash(self, on: date) -> Money:
```
with:
```python

    def spendable_cash(self, on: date) -> Money:
        """What can be spent on *on* without ever overdrawing: settled credits, less every debit."""
        raise NotImplementedError("Portfolio.spendable_cash")

    def unsettled_cash(self, on: date) -> Money:
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python

    def apply_fill(self, fill: Fill, settles_on: date) -> Portfolio:
```
with:
```python

    def credit_dividend(self, gross: Money, on: date) -> Portfolio:
        """Book a dividend paid on *on*. It settles that day, so the next decision can spend it."""
        raise NotImplementedError("Portfolio.credit_dividend")

    def charge(
        self, kind: MovementKind, amount: Money, on: date, *, settles_on: date | None = None
    ) -> Portfolio:
        """Take *amount* for tax or a daily cost on *on*, settling on *settles_on* (default *on*).

        Either way it is held back from ``spendable_cash`` at once.
        """
        raise NotImplementedError("Portfolio.charge")

    def apply_split(self, split: Split) -> Portfolio:
        """Turn every ``old_shares`` held into ``new_shares``, keeping the total cost basis.

        A fraction of a share left by the ratio is dropped (cash in lieu is not modelled), and a
        holding that rounds to no shares at all is removed with its basis. The caller reports it.
        """
        raise NotImplementedError("Portfolio.apply_split")

    def apply_fill(self, fill: Fill, settles_on: date) -> Portfolio:
```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
        return self._sell(fill, settles_on)

```
with:
```python
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
        raise NotImplementedError("Portfolio._book")

```

<!-- edit: packages/steadyhand/src/steadyhand/portfolio.py -->
Replace:
```python
        return Portfolio(self.currency, positions, (*self.ledger, movement))
```
with:
```python
        return Portfolio(self.currency, positions, (*self.ledger, movement))

    def _replaced(
        self, instrument: Instrument, position: Position | None, ledger: tuple[CashMovement, ...]
    ) -> Portfolio:
        raise NotImplementedError("Portfolio._replaced")
```

**`packages/steadyhand/src/steadyhand/universe.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/universe.py -->
```python
"""The Universe protocol: which stocks a strategy may buy on each day (M3 spec §7.2)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Protocol, runtime_checkable

from steadyhand.types import Instrument


@runtime_checkable
class Universe(Protocol):
    """The stocks a strategy may choose from, as they stood on each day.

    A backtest refuses a start before ``first_day()``: before it, membership is unknown, and
    guessing it would hide survivorship bias (M3 spec, decision 3).
    """

    def members_on(self, day: date) -> frozenset[Instrument]:
        """Every member on *day*. Raises ``LookupError`` for a day before ``first_day()``."""
        ...

    def excluded_on(self, day: date) -> Mapping[Instrument, str]:
        """Each stock the operator keeps out on *day*, with the reason given for it."""
        ...

    def first_day(self) -> date:
        """The first day whose membership is known."""
        ...
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=555 failed=30 -->
Expected: 555 run (the 4 `live` tests deselected), 30 failed. 28 fail on `NotImplementedError`. Two fail on their assertions, as they must before the implementation: `TestBuy::test_one_rupiah_short_is_refused` (the message still says "is settled") and `test_an_unreported_adjustment_is_refused_with_every_day_named` (Yahoo's error is not yet an `UnavailableDaysError`). Six new or changed tests pass against the stubs, each for a reason: `test_the_new_movement_kinds` (enum members are declarations, not code), `test_a_minimal_class_satisfies_universe` (a Protocol has no body to stub), and the four disclaimer tests, whose subject, the docs, already complies. M4 proves that guard bites.

- [ ] **Step 5: Implement.**

**`packages/steadyhand-idx/src/steadyhand_idx/universe.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/universe.py -->
Replace:
```python
    def __init__(self, membership: Lq45Membership, exclusions: Exclusions | None = None) -> None:
        raise NotImplementedError("Lq45Universe.__init__")

    def members_on(self, day: date) -> frozenset[Instrument]:
        raise NotImplementedError("Lq45Universe.members_on")

    def excluded_on(self, day: date) -> dict[Instrument, str]:
        raise NotImplementedError("Lq45Universe.excluded_on")

    def first_day(self) -> date:
        raise NotImplementedError("Lq45Universe.first_day")
```
with:
```python
    def __init__(self, membership: Lq45Membership, exclusions: Exclusions | None = None) -> None:
        self._membership = membership
        self._exclusions = Exclusions() if exclusions is None else exclusions

    def members_on(self, day: date) -> frozenset[Instrument]:
        return frozenset(Instrument(code, "IDX", IDR) for code in self._membership.members_on(day))

    def excluded_on(self, day: date) -> dict[Instrument, str]:
        excluded = self._exclusions.excluded_on(day)
        return {Instrument(symbol, "IDX", IDR): reason for symbol, reason in excluded.items()}

    def first_day(self) -> date:
        return self._membership.records[0].effective
```

**`packages/steadyhand-idx/src/steadyhand_idx/yahoo.py`** (implemented: 2 edits)

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python

class UnrecoverablePricesError(DataUnavailableError):
    """Yahoo's prices for these days carry an adjustment it does not report, so the traded
```
with:
```python

class UnrecoverablePricesError(UnavailableDaysError):
    """Yahoo's prices for these days carry an adjustment it does not report, so the traded
```

<!-- edit: packages/steadyhand-idx/src/steadyhand_idx/yahoo.py -->
Replace:
```python
    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        self.days = tuple(days)
        super().__init__(
            f"{ticker}: Yahoo's prices for {len(self.days)} day(s) from "
            f"{self.days[0].isoformat()} to {self.days[-1].isoformat()} carry an adjustment it "
            "does not report as a split (for example a rights issue), so the prices traded on "
            "those days cannot be recovered"
        )
```
with:
```python
    def __init__(self, ticker: str, days: Sequence[date]) -> None:
        found = tuple(days)
        super().__init__(
            f"{ticker}: Yahoo's prices for {len(found)} day(s) from "
            f"{found[0].isoformat()} to {found[-1].isoformat()} carry an adjustment it "
            "does not report as a split (for example a rights issue), so the prices traded on "
            "those days cannot be recovered",
            found,
        )
```

**`packages/steadyhand/src/steadyhand/data.py`** (implemented: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/data.py -->
Replace:
```python
    def __init__(self, message: str, days: Sequence[date]) -> None:
        raise NotImplementedError("UnavailableDaysError.__init__")

```
with:
```python
    def __init__(self, message: str, days: Sequence[date]) -> None:
        found = tuple(days)
        if not found:
            msg = "an unavailable-days error must name at least one day"
            raise ValueError(msg)
        if list(found) != sorted(set(found)):
            msg = "the unavailable days must be different and in date order"
            raise ValueError(msg)
        self.days = found
        super().__init__(message)

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
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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

    def __post_init__(self) -> None:
        require_type(self.currency, Currency, "currency")
        require_type(self.positions, tuple, "positions")
        require_type(self.ledger, tuple, "ledger")
        for position in self.positions:
            require_type(position, Position, "position")
        for movement in self.ledger:
            require_type(movement, CashMovement, "ledger entry")
        keys = [_sort_key(p) for p in self.positions]
        if keys != sorted(set(keys)):
            msg = "positions must be unique and sorted by market, then symbol"
            raise ValueError(msg)
        for position in self.positions:
            if position.instrument.currency != self.currency:
                raise CurrencyMismatchError(self.currency, position.instrument.currency)
        previous: date | None = None
        for movement in self.ledger:
            if movement.amount.currency != self.currency:
                raise CurrencyMismatchError(self.currency, movement.amount.currency)
            if previous is not None and movement.day < previous:
                raise ChronologyError(movement.day, previous)
            previous = movement.day

    @classmethod
    def empty(cls, currency: Currency) -> Portfolio:
        return cls(currency)

    @property
    def last_day(self) -> date | None:
        return self.ledger[-1].day if self.ledger else None

    def cash_balance(self) -> Money:
        return sum((m.amount for m in self.ledger), start=Money.zero(self.currency))

    def settled_cash(self, on: date) -> Money:
        require_date(on, "on")
        settled = (m.amount for m in self.ledger if m.settles_on <= on)
        return sum(settled, start=Money.zero(self.currency))

    def spendable_cash(self, on: date) -> Money:
        """What can be spent on *on* without ever overdrawing: settled credits, less every debit."""
        require_date(on, "on")
        kept = (m.amount for m in self.ledger if m.amount.amount < 0 or m.settles_on <= on)
        return sum(kept, start=Money.zero(self.currency))

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
        return Portfolio(self.currency, self.positions, (*self.ledger, movement))

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
        return self._replaced(held.instrument, updated, self.ledger)

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
        return Portfolio(self.currency, self.positions, (*self.ledger, movement))

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
        return self._replaced(instrument, position, (*self.ledger, movement))

    def _replaced(
        self, instrument: Instrument, position: Position | None, ledger: tuple[CashMovement, ...]
    ) -> Portfolio:
        others = [p for p in self.positions if p.instrument != instrument]
        if position is not None:
            others.append(position)
        return Portfolio(self.currency, tuple(sorted(others, key=_sort_key)), ledger)
```


- [ ] **Step 6: Run the whole gate.** `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, then `HYPOTHESIS_PROFILE=ci uv run pytest -W error --cov --cov-report=term-missing`, each with its exit status read as above.

<!-- check: gate total=555 passed=555 -->
Expected: every command exits 0; 555 passed, 4 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M1–M6 from **Mutation checks**; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S1 …`), as **Merging a story** says.

---

### Task 2: S2 MarketView, the Strategy protocol and buy-and-hold

**Acceptance criteria (story text):**
1. `PriceHistory(bars)` groups bars by stock, sorts them by day, refuses two bars for one stock on one day, and answers `between(stock, start, end)`, `on(stock, day)` and `before(stock, day)` (the last bar strictly earlier) for any day.
2. `MarketView(history, today, tradable)` shows bars dated on or before `today` only: `bar`, `history` and `last_close`. Asking `bar` or `history` for a later date raises `LookAheadError` naming both dates (core §4.3).
3. `Tradable(day, buyable, sellable, reasons)` refuses a stock that is both tradable and kept out, and `why_not(stock, side)` gives the reason, or "not in the universe on <day>" for a buy and "not held" for a sale.
4. `PortfolioView(value, spendable, holdings)` refuses negative spendable cash and holdings plus spendable cash above the value. `weight(stock)` is the holding's share of the value, rounded down, and 0 for a stock not held or a value of 0.
5. `Decision(weights, memory)` refuses a weight that is not a finite, non-negative `Decimal`, and weights that sum above 1 (`InvalidWeightsError`). `Strategy` is a runtime-checkable protocol with `name` and `decide(view, portfolio, memory) -> Decision` (scope decision 3).
6. `BuyAndHold` fixes its set on its first day (the buyable stocks), never targets a holding below its current weight, and splits spendable cash equally across the stocks of its set that are buyable today. A hypothesis property holds "never sells, buys only its set" over any holdings, cash, set and buyable stocks.
7. `STRATEGIES` registers `buy-and-hold`. `docs/strategies/buy-and-hold.md` has the six sections of core §8 and the disclaimer. A guard fails on a registered strategy without a complete guide (every section present and non-empty, "you can lose money" and "fee" under Risks, HTML comments ignored), and on a guide with no registered strategy.
8. The no-float guard scans every engine module found on disk.
9. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M7–M13 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/_ratio.py`, `.../steadyhand/view.py`, `.../steadyhand/strategies/__init__.py`, `.../strategies/protocol.py`, `.../strategies/buy_and_hold.py`, `.../strategies/registry.py`, `docs/strategies/buy-and-hold.md`
- Modify: `packages/steadyhand/src/steadyhand/__init__.py`
- Test: create `tests/engine/test_view.py`, `tests/engine/test_buy_and_hold.py`, `tests/meta/test_strategy_guides.py`; modify `tests/meta/test_no_float.py`

**Interfaces:**
- Consumes: `Bar`, `Instrument`, `Money`, `Side` (M1).
- Produces: `steadyhand._ratio.ratio_down(part: int | Decimal, whole: int | Decimal) -> Decimal`; `LookAheadError(asked: date, today: date)`; `PriceHistory(bars: Iterable[Bar])` with `.instruments`, `.between(instrument, start: date | None, end: date) -> tuple[Bar, ...]`, `.on(instrument, day) -> Bar | None`, `.before(instrument, day) -> Bar | None`; `Tradable(day: date, buyable: frozenset[Instrument], sellable: frozenset[Instrument], reasons: Mapping[Instrument, str])` with `.why_not(instrument, side) -> str | None`; `MarketView(history, today, tradable)` with `.today`, `.tradable`, `.bar(instrument, day=None)`, `.history(instrument, start=None, end=None)`, `.last_close(instrument) -> Money | None`; `PortfolioView(value: Money, spendable: Money, holdings: Mapping[Instrument, Money])` with `.weight(instrument) -> Decimal`; `type Memory = Mapping[str, str]`; `Decision(weights: Mapping[Instrument, Decimal], memory: Memory = {})`; `InvalidWeightsError(ValueError)`; `Strategy` (`name: str`, `decide(view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision`); `BuyAndHold()`; `STRATEGIES: Mapping[str, Callable[[], Strategy]]`.

- [ ] **Step 1: Branch.** `git switch -c m3/s2-view-strategy origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_buy_and_hold.py`** (new)

<!-- file: tests/engine/test_buy_and_hold.py -->
```python
"""Decision and buy-and-hold: fix the day-one set, never sell, reinvest equally (M3 spec §6.6)."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money
from steadyhand.strategies import BuyAndHold, Decision, InvalidWeightsError, Strategy
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView, PriceHistory, Tradable

D0 = date(2025, 6, 2)
STOCKS = [Instrument(code, "IDX", IDR) for code in ("ASII", "BBCA", "BBRI", "TLKM", "UNVR")]
ASII, BBCA, BBRI, TLKM, UNVR = STOCKS


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def view(buyable: set[Instrument], sellable: set[Instrument] | None = None) -> MarketView:
    tradable = Tradable(D0, frozenset(buyable), frozenset(sellable or set()), {})
    return MarketView(PriceHistory([]), D0, tradable)


def test_a_decision_holds_weights_and_memory() -> None:
    decision = Decision({BBCA: Decimal("0.6"), BBRI: Decimal("0.4")})
    assert decision.memory == {}
    assert sum(decision.weights.values()) == 1


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({BBCA: 0.5}, r"^BBCA: a weight must be a Decimal, got float$"),
        ({BBCA: Decimal("-0.1")}, r"^BBCA: a weight must be finite and not negative, got -0\.1$"),
        ({BBCA: Decimal("NaN")}, r"^BBCA: a weight must be finite and not negative, got NaN$"),
        (
            {BBCA: Decimal("0.6"), BBRI: Decimal("0.4000001")},
            r"^weights sum to 1\.0000001, more than 1$",
        ),
    ],
)
def test_weights_that_cannot_be_a_portfolio_are_refused(weights: object, message: str) -> None:
    with pytest.raises(InvalidWeightsError, match=message):
        Decision(weights)  # type: ignore[arg-type]


def test_a_decision_checks_its_keys_and_memory() -> None:
    with pytest.raises(TypeError, match=r"^weighted stock must be an Instrument, got str$"):
        Decision({"BBCA": Decimal("0.5")})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match=r"^memory value must be a str, got int$"):
        Decision({}, {"set": 1})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match=r"^memory key must be a str, got int$"):
        Decision({}, {1: "x"})  # type: ignore[dict-item]


def test_it_is_a_strategy_named_buy_and_hold() -> None:
    strategy: Strategy = BuyAndHold()
    assert isinstance(strategy, Strategy)
    assert strategy.name == "buy-and-hold"


def test_day_one_fixes_the_set_and_splits_the_cash_equally() -> None:
    portfolio = PortfolioView(rp(9_000_000), rp(9_000_000), {})
    decision = BuyAndHold().decide(view({BBCA, BBRI, TLKM}), portfolio, {})
    third = Decimal("0.3333333333333333333333333333")
    assert decision.weights == {BBCA: third, BBRI: third, TLKM: third}
    assert decision.memory == {"set": "IDX:BBCA IDX:BBRI IDX:TLKM"}


def test_later_days_keep_holdings_and_buy_only_the_set() -> None:
    portfolio = PortfolioView(
        rp(10_000_000), rp(900_000), {BBCA: rp(4_000_000), BBRI: rp(5_000_000)}
    )
    memory = {"set": "IDX:BBCA IDX:BBRI IDX:TLKM"}
    decision = BuyAndHold().decide(view({BBCA, TLKM, ASII}, {BBCA, BBRI}), portfolio, memory)
    each = Decimal("0.045")
    assert decision.weights == {BBCA: Decimal("0.4") + each, BBRI: Decimal("0.5"), TLKM: each}
    assert decision.memory == memory


def test_an_empty_first_day_leaves_an_empty_set() -> None:
    portfolio = PortfolioView(rp(1_000_000), rp(1_000_000), {})
    first = BuyAndHold().decide(view(set()), portfolio, {})
    assert first.weights == {}
    later = BuyAndHold().decide(view({BBCA}), portfolio, first.memory)
    assert later.weights == {}


@given(
    held=st.dictionaries(st.sampled_from(STOCKS), st.integers(1, 10**10), max_size=5),
    spendable=st.integers(0, 10**10),
    unsettled=st.integers(0, 10**10),
    chosen=st.sets(st.sampled_from(STOCKS)),
    buyable=st.sets(st.sampled_from(STOCKS)),
)
def test_it_never_sells_and_buys_only_its_set(
    held: dict[Instrument, int],
    spendable: int,
    unsettled: int,
    chosen: set[Instrument],
    buyable: set[Instrument],
) -> None:
    value = sum(held.values()) + spendable + unsettled
    portfolio = PortfolioView(rp(value), rp(spendable), {i: rp(v) for i, v in held.items()})
    memory = {"set": " ".join(sorted(f"IDX:{i.symbol}" for i in chosen))}
    decision = BuyAndHold().decide(view(buyable), portfolio, memory)
    for instrument in held:
        assert decision.weights[instrument] >= portfolio.weight(instrument)
    bought = {i for i, weight in decision.weights.items() if weight > portfolio.weight(i)}
    assert bought <= chosen & buyable
    assert decision.memory == memory
```

**`tests/engine/test_view.py`** (new)

<!-- file: tests/engine/test_view.py -->
```python
"""MarketView and PriceHistory: prices up to the decision day, and nothing later (M3 spec §6.1)."""

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest

from steadyhand._ratio import ratio_down
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import Bar, Instrument, Side
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

D0 = date(2025, 6, 2)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bar(stock: Instrument, day: date, close: int) -> Bar:
    return Bar(stock, day, rp(close), rp(close), rp(close), rp(close), 1_000)


def history() -> PriceHistory:
    days = [D0 + timedelta(days=n) for n in range(4)]
    return PriceHistory(
        [bar(BBCA, day, 9_000 + 25 * n) for n, day in reversed(list(enumerate(days)))]
        + [bar(BBRI, days[1], 4_000), bar(BBRI, days[3], 4_010)]
    )


def nothing_tradable(day: date) -> Tradable:
    return Tradable(day, frozenset(), frozenset(), {})


def view_on(offset: int) -> MarketView:
    today = D0 + timedelta(days=offset)
    return MarketView(history(), today, nothing_tradable(today))


def test_history_sorts_each_stock_by_day_and_answers_for_any_day() -> None:
    prices = history()
    assert prices.instruments == frozenset({BBCA, BBRI})
    assert [b.close.amount for b in prices.between(BBCA, None, D0 + timedelta(days=3))] == [
        9_000,
        9_025,
        9_050,
        9_075,
    ]
    assert [
        b.day.day for b in prices.between(BBCA, D0 + timedelta(days=1), D0 + timedelta(days=2))
    ] == [3, 4]
    assert prices.on(BBRI, D0 + timedelta(days=1)) == bar(BBRI, D0 + timedelta(days=1), 4_000)
    assert prices.on(BBRI, D0 + timedelta(days=2)) is None


def test_before_is_the_last_bar_strictly_earlier() -> None:
    prices = history()
    assert prices.before(BBRI, D0 + timedelta(days=3)) == bar(BBRI, D0 + timedelta(days=1), 4_000)
    assert prices.before(BBRI, D0 + timedelta(days=1)) is None
    assert prices.before(TLKM, D0) is None


def test_an_unknown_stock_has_no_bars() -> None:
    assert history().between(TLKM, None, D0) == ()
    assert history().on(TLKM, D0) is None


def test_history_refuses_two_bars_on_one_day_and_anything_but_bars() -> None:
    with pytest.raises(ValueError, match=r"^two bars for BBCA on 2025-06-02$"):
        PriceHistory([bar(BBCA, D0, 9_000), bar(BBCA, D0, 9_025)])
    with pytest.raises(TypeError, match=r"^bar must be a Bar, got str$"):
        PriceHistory(["BBCA"])  # type: ignore[list-item]


def test_the_view_shows_today_and_earlier() -> None:
    view = view_on(2)
    assert view.today == D0 + timedelta(days=2)
    assert view.bar(BBCA) == bar(BBCA, D0 + timedelta(days=2), 9_050)
    assert view.bar(BBCA, D0) == bar(BBCA, D0, 9_000)
    assert [b.day for b in view.history(BBCA)] == [D0 + timedelta(days=n) for n in range(3)]
    assert [b.day for b in view.history(BBCA, start=D0 + timedelta(days=1))] == [
        D0 + timedelta(days=1),
        D0 + timedelta(days=2),
    ]
    assert view.last_close(BBRI) == rp(4_000)
    assert view.last_close(TLKM) is None


@pytest.mark.parametrize(
    "ask",
    [
        lambda view, later: view.bar(BBCA, later),
        lambda view, later: view.history(BBCA, end=later),
    ],
    ids=["bar", "history"],
)
def test_asking_about_a_later_day_is_look_ahead(ask: Callable[[MarketView, date], object]) -> None:
    view = view_on(2)
    message = r"^asked for 2025-06-05 while deciding on 2025-06-04: a decision may use nothing"
    with pytest.raises(LookAheadError, match=message):
        ask(view, D0 + timedelta(days=3))


def test_the_view_checks_its_arguments() -> None:
    with pytest.raises(TypeError, match=r"^history must be a PriceHistory, got list$"):
        MarketView([], D0, nothing_tradable(D0))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^the tradable set is for 2025-06-03, not 2025-06-02$"):
        MarketView(history(), D0, nothing_tradable(D0 + timedelta(days=1)))
    with pytest.raises(TypeError, match=r"^day must be a date, got str$"):
        view_on(1).bar(BBCA, "2025-06-02")  # type: ignore[arg-type]


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


def test_a_stock_cannot_be_both_tradable_and_kept_out() -> None:
    with pytest.raises(ValueError, match=r"^BBCA, BBRI cannot be both tradable and kept out$"):
        Tradable(D0, frozenset({BBCA}), frozenset({BBRI}), {BBRI: "no bar", BBCA: "no bar"})
    with pytest.raises(TypeError, match=r"^buyable must be a frozenset, got set$"):
        Tradable(D0, {BBCA}, frozenset(), {})  # type: ignore[arg-type]


def test_a_weight_is_the_share_of_value_rounded_down() -> None:
    portfolio = PortfolioView(rp(3_000_000), rp(1_000_000), {BBCA: rp(1_000_000)})
    assert portfolio.weight(BBCA) == Decimal("0.3333333333333333333333333333")
    assert portfolio.weight(BBRI) == 0
    assert PortfolioView(rp(0), rp(0), {}).weight(BBCA) == 0


def test_the_portfolio_view_must_add_up() -> None:
    with pytest.raises(ValueError, match=r"^spendable cash cannot be negative, got IDR -1$"):
        PortfolioView(rp(0), rp(-1), {})
    with pytest.raises(
        ValueError, match=r"^holdings IDR 2 and spendable IDR 1 exceed the value IDR 2$"
    ):
        PortfolioView(rp(2), rp(1), {BBCA: rp(2)})
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        PortfolioView(rp(5), rp(0), {BBCA: Money(1, Currency("USD", 2))})
    with pytest.raises(TypeError, match=r"^value must be a Money, got int$"):
        PortfolioView(5, rp(0), {})  # type: ignore[arg-type]


def test_ratios_round_down_and_a_zero_whole_is_zero() -> None:
    assert ratio_down(2, 3) == Decimal("0.6666666666666666666666666666")
    assert ratio_down(Decimal("1.5"), 1) == Decimal("1.5")
    assert ratio_down(7, 0) == 0
```

**`tests/meta/test_no_float.py`** (changed: 2 edits)

<!-- edit: tests/meta/test_no_float.py -->
Replace:
```python
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"
GUARDED = ("money.py", "portfolio.py", "sizing.py", "risk.py", "income.py", "metrics.py", "broker")


def guarded_files() -> list[Path]:
    files: list[Path] = []
    for entry in GUARDED:
        path = ENGINE / entry
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        elif path.is_file():
            files.append(path)
    return files

```
with:
```python
ENGINE = ROOT / "packages/steadyhand/src/steadyhand"


def guarded_files() -> list[Path]:
    """Every module of the engine, found on disk: money, weights and ledgers run through it all."""
    return sorted(ENGINE.rglob("*.py"))

```

<!-- edit: tests/meta/test_no_float.py -->
Replace:
```python
    names = {path.relative_to(ENGINE).as_posix() for path in files}
    assert {"money.py", "portfolio.py", "broker/__init__.py", "broker/protocol.py"} <= names
    findings = {
```
with:
```python
    names = {path.relative_to(ENGINE).as_posix() for path in files}
    assert {"money.py", "portfolio.py", "view.py", "strategies/buy_and_hold.py"} <= names
    findings = {
```

**`tests/meta/test_strategy_guides.py`** (new)

<!-- file: tests/meta/test_strategy_guides.py -->
```python
"""Every registered strategy has a complete plain-English guide (core spec §8, §10.1).

The guide is read with its HTML comments removed, so a section commented out is missing.
"""

import re
from pathlib import Path

import pytest

from steadyhand.strategies import STRATEGIES, Strategy

ROOT = Path(__file__).resolve().parents[2]
GUIDES = ROOT / "docs/strategies"
SECTIONS = (
    "What it does",
    "Why people use it",
    "When it tends to do badly",
    "Risks",
    "How often it trades",
    "Settings you can change",
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def sections(markdown: str) -> dict[str, str]:
    """Each ``## `` heading's text, mapped to the words under it, comments removed."""
    found: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in _COMMENT.sub("", markdown).splitlines():
        if line.startswith("## "):
            current = found.setdefault(line.removeprefix("## ").strip(), [])
        elif current is not None:
            current.append(line)
    return {heading: " ".join(" ".join(lines).split()) for heading, lines in found.items()}


def problems(name: str, markdown: str) -> list[str]:
    found = sections(markdown)
    wrong = [f"missing or empty: {section}" for section in SECTIONS if not found.get(section)]
    risks = found.get("Risks", "").lower()
    wrong += [
        f"Risks must say {phrase!r}"
        for phrase in ("you can lose money", "fee")
        if phrase not in risks
    ]
    if not markdown.startswith(f"# {name}\n"):
        wrong.append(f"the first line must be '# {name}'")
    return wrong


def complete(name: str) -> str:
    body = "".join(f"## {section}\nWords. You can lose money. Fee drag.\n" for section in SECTIONS)
    return f"# {name}\n{body}"


def test_a_complete_guide_has_no_problems() -> None:
    assert problems("x", complete("x")) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (("## Risks\n", "## Risk\n"), "missing or empty: Risks"),
        (
            ("## Why people use it\nWords.", "<!-- ## Why people use it -->\nWords."),
            "missing or empty: Why people use it",
        ),
        (
            (
                "## How often it trades\nWords. You can lose money. Fee drag.\n",
                "## How often it trades\n<!-- hidden -->\n",
            ),
            "missing or empty: How often it trades",
        ),
        (
            ("You can lose money. Fee drag.\n## How", "Fee drag.\n## How"),
            "Risks must say 'you can lose money'",
        ),
        (("# x\n", "# y\n"), "the first line must be '# x'"),
    ],
)
def test_the_checker_finds_each_problem(change: tuple[str, str], problem: str) -> None:
    guide = complete("x")
    assert guide.count(change[0]) >= 1
    assert problem in problems("x", guide.replace(change[0], change[1], 1))


def test_every_registered_strategy_has_a_complete_guide() -> None:
    assert "buy-and-hold" in STRATEGIES
    missing = [name for name in STRATEGIES if not (GUIDES / f"{name}.md").is_file()]
    assert missing == []
    found = {
        name: wrong
        for name in STRATEGIES
        if (wrong := problems(name, (GUIDES / f"{name}.md").read_text(encoding="utf-8")))
    }
    assert found == {}


def test_every_guide_is_for_a_registered_strategy() -> None:
    guides = sorted(path.stem for path in GUIDES.glob("*.md"))
    assert "buy-and-hold" in guides
    assert [name for name in guides if name not in STRATEGIES] == []


def test_each_registered_name_is_the_strategys_own() -> None:
    for name, make in STRATEGIES.items():
        strategy = make()
        assert isinstance(strategy, Strategy)
        assert strategy.name == name
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.types import (
```
with:
```python
)
from steadyhand.strategies import (
    STRATEGIES,
    BuyAndHold,
    Decision,
    InvalidWeightsError,
    Memory,
    Strategy,
)
from steadyhand.types import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
from steadyhand.universe import Universe

```
with:
```python
from steadyhand.universe import Universe
from steadyhand.view import LookAheadError, MarketView, PortfolioView, PriceHistory, Tradable

```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "MAX_MINOR_UNITS",
    "Bar",
    "Broker",
    "CashDividend",
```
with:
```python
    "MAX_MINOR_UNITS",
    "STRATEGIES",
    "Bar",
    "Broker",
    "BuyAndHold",
    "CashDividend",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "DataUnavailableError",
    "Fill",
```
with:
```python
    "DataUnavailableError",
    "Decision",
    "Fill",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "InvalidBarError",
    "MarketRules",
    "MissingPriceError",
```
with:
```python
    "InvalidBarError",
    "InvalidWeightsError",
    "LookAheadError",
    "MarketRules",
    "MarketView",
    "Memory",
    "MissingPriceError",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Portfolio",
    "Position",
    "Rounding",
    "Side",
    "Split",
    "UnavailableDaysError",
```
with:
```python
    "Portfolio",
    "PortfolioView",
    "Position",
    "PriceHistory",
    "Rounding",
    "Side",
    "Split",
    "Strategy",
    "Tradable",
    "UnavailableDaysError",
```

**`packages/steadyhand/src/steadyhand/_ratio.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/_ratio.py -->
```python
"""Ratios as ``Decimal``, rounded down, for weights and fund-style unit values."""

from decimal import ROUND_FLOOR, Decimal, localcontext


def ratio_down(part: int | Decimal, whole: int | Decimal) -> Decimal:
    """*part* / *whole*, rounded down at the context's precision. Zero when *whole* is zero.

    Rounding down means weights built from these ratios never sum above 1.
    """
    raise NotImplementedError("ratio_down")
```

**`packages/steadyhand/src/steadyhand/strategies/__init__.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/__init__.py -->
```python
"""Strategies: the Strategy protocol, the shipped strategies and their registry."""

from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Decision, InvalidWeightsError, Memory, Strategy
from steadyhand.strategies.registry import STRATEGIES

__all__ = ["STRATEGIES", "BuyAndHold", "Decision", "InvalidWeightsError", "Memory", "Strategy"]
```

**`packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py -->
```python
"""``buy-and-hold``: the baseline every other strategy is measured against (core spec §8).

On its first day it fixes its set: the stocks buyable that day. It never sells. Each day it keeps
every holding at its current weight, so nothing is traded against it, and it splits the cash it
may spend equally across the stocks in its set that are buyable today. Dividends and top-ups are
reinvested the same way. A stock that leaves the universe stays held (M3 spec §6.6).
"""

from __future__ import annotations

from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand.money import Currency
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

_SET_KEY = "set"
"""The memory key holding the set, written as ``MARKET:SYMBOL`` separated by spaces."""


class BuyAndHold:
    """Buy the day-one universe in equal parts and hold it."""

    @property
    def name(self) -> str:
        raise NotImplementedError("BuyAndHold.name")

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        raise NotImplementedError("BuyAndHold.decide")


def _write(chosen: frozenset[Instrument]) -> str:
    raise NotImplementedError("_write")


def _read(text: str, currency: Currency) -> frozenset[Instrument]:
    raise NotImplementedError("_read")
```

**`packages/steadyhand/src/steadyhand/strategies/protocol.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/protocol.py -->
```python
"""The Strategy protocol: a strategy says what share of the portfolio each stock should be.

Strategies return target weights, not orders (core spec §4.3). The sizer and the risk manager
turn weights into legal orders, so every rule about lots, ticks, cash and caps lives in one
tested place.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

from steadyhand._validate import require_type
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

type Memory = Mapping[str, str]
"""What a strategy keeps from one day to the next, as text, so M5 can save it with the state."""


class InvalidWeightsError(ValueError):
    """A strategy returned weights that cannot be a portfolio. It is a bug in the strategy."""


@dataclass(frozen=True, slots=True)
class Decision:
    """A strategy's answer for one day: target weights, and what to remember until tomorrow.

    A stock missing from ``weights`` is targeted at zero. Weights are ``Decimal``, none is
    negative, and together they are at most 1; the rest is held as cash.
    """

    weights: Mapping[Instrument, Decimal]
    memory: Memory = field(default_factory=dict)

    def __post_init__(self) -> None:
        raise NotImplementedError("Decision.__post_init__")


@runtime_checkable
class Strategy(Protocol):
    """A way of choosing stocks. Each registered strategy has a plain-English guide (core §8)."""

    @property
    def name(self) -> str:
        """The name the configuration and the guide use, such as ``buy-and-hold``."""
        ...

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        """Today's target weights, given the market up to today and yesterday's memory."""
        ...
```

**`packages/steadyhand/src/steadyhand/strategies/registry.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/registry.py -->
```python
"""Every strategy steadyhand ships, by the name the configuration uses.

Each one must have a complete guide at ``docs/strategies/<name>.md`` (core spec §8, §10.1).
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Final

from steadyhand.strategies.buy_and_hold import BuyAndHold
from steadyhand.strategies.protocol import Strategy

STRATEGIES: Final[Mapping[str, Callable[[], Strategy]]] = MappingProxyType(
    {"buy-and-hold": BuyAndHold}
)
```

**`packages/steadyhand/src/steadyhand/view.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/view.py -->
```python
"""What a strategy may see on a decision day: prices up to that day, and nothing later.

``PriceHistory`` holds every bar a run can use and is built once. Each day gets a cheap
``MarketView`` over it, which refuses any date after its own day with ``LookAheadError`` (core
spec §4.3). A backtest that peeks at tomorrow's price looks brilliant and means nothing.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Bar, Instrument, Side


class LookAheadError(LookupError):
    """A strategy asked for data dated after the day it is deciding on."""

    def __init__(self, asked: date, today: date) -> None:
        raise NotImplementedError("LookAheadError.__init__")


class PriceHistory:
    """Every bar a run can use, indexed by instrument and day. It answers for any day."""

    def __init__(self, bars: Iterable[Bar]) -> None:
        raise NotImplementedError("PriceHistory.__init__")

    @property
    def instruments(self) -> frozenset[Instrument]:
        raise NotImplementedError("PriceHistory.instruments")

    def between(self, instrument: Instrument, start: date | None, end: date) -> tuple[Bar, ...]:
        """The instrument's bars from *start* (or its first) to *end*, both inclusive."""
        raise NotImplementedError("PriceHistory.between")

    def on(self, instrument: Instrument, day: date) -> Bar | None:
        raise NotImplementedError("PriceHistory.on")

    def before(self, instrument: Instrument, day: date) -> Bar | None:
        """The instrument's last bar dated strictly before *day*."""
        raise NotImplementedError("PriceHistory.before")


@dataclass(frozen=True, slots=True)
class Tradable:
    """Today's buyable and sellable stocks, and why a stock is neither (M3 spec §6.4).

    ``reasons`` explains stocks kept out for a cause (frozen, excluded, refused data, no bar).
    Any other stock is out because it is not in the universe (for a buy) or not held (a sell).
    """

    day: date
    buyable: frozenset[Instrument]
    sellable: frozenset[Instrument]
    reasons: Mapping[Instrument, str]

    def __post_init__(self) -> None:
        raise NotImplementedError("Tradable.__post_init__")

    def why_not(self, instrument: Instrument, side: Side) -> str | None:
        """Why *instrument* cannot be traded on *side* today, or ``None`` when it can."""
        raise NotImplementedError("Tradable.why_not")


class MarketView:
    """The market as a strategy sees it on ``today``."""

    def __init__(self, history: PriceHistory, today: date, tradable: Tradable) -> None:
        raise NotImplementedError("MarketView.__init__")

    @property
    def today(self) -> date:
        raise NotImplementedError("MarketView.today")

    @property
    def tradable(self) -> Tradable:
        raise NotImplementedError("MarketView.tradable")

    def bar(self, instrument: Instrument, day: date | None = None) -> Bar | None:
        """The bar for *day* (today by default), or ``None`` if the stock has none that day."""
        raise NotImplementedError("MarketView.bar")

    def history(
        self, instrument: Instrument, start: date | None = None, end: date | None = None
    ) -> tuple[Bar, ...]:
        """Bars from *start* (or the first) to *end* (today by default), both inclusive."""
        raise NotImplementedError("MarketView.history")

    def last_close(self, instrument: Instrument) -> Money | None:
        """The most recent close on or before today."""
        raise NotImplementedError("MarketView.last_close")

    def _checked(self, day: date) -> date:
        raise NotImplementedError("MarketView._checked")


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
        raise NotImplementedError("PortfolioView.__post_init__")

    def weight(self, instrument: Instrument) -> Decimal:
        """The instrument's share of the value, rounded down so weights never sum above 1."""
        raise NotImplementedError("PortfolioView.weight")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=588 failed=27 -->
Expected: 588 run (the 4 `live` tests deselected), 27 failed. 25 fail on `NotImplementedError`. The two guide tests fail on their assertions, because the guide is written in Step 5. The guide checker's own tests and the no-float guard pass against the stubs: they test guards whose subjects already comply, and M11, M12 and M13 prove each one bites.

- [ ] **Step 5: Implement.**

**`docs/strategies/buy-and-hold.md`** (new)

<!-- file: docs/strategies/buy-and-hold.md -->
```markdown
# buy-and-hold

> steadyhand is example software that you run yourself, on your own account, and you make your
> own decisions with it. It is not financial advice. You can lose money.

## What it does

On the first day it runs, it takes every stock in the universe that can be bought that day (by
default the LQ45, IDX's list of 45 large, easily traded stocks) and buys them in equal amounts
of money. After that it never sells. Whenever new cash arrives, from a dividend (a share of a
company's profit paid to its shareholders) or from a monthly top-up, it spreads that cash
equally across the same stocks again.

It keeps the stocks it chose on the first day. A stock that later leaves the LQ45 stays in the
portfolio, and a stock that joins later is never bought.

## Why people use it

It is the simplest way to own a slice of a whole market, and it costs very little in fees
because it hardly ever trades. steadyhand runs it next to every other strategy as the
**baseline**: if a cleverer strategy cannot beat plain buying and holding after its costs, the
cleverness is not worth paying for.

## When it tends to do badly

When the market as a whole falls, this strategy falls with it, because it never moves to cash.
It also keeps holding a company whose business is getting worse, since it never sells, and
because it only reinvests new cash equally it never trims a stock that has grown to a large part
of the portfolio.

## Risks

- **You can lose money.** Share prices can fall a long way and stay down for years.
- **Fee drag:** every purchase pays a broker commission, the exchange levy and, on some days,
  stamp duty. Buying small amounts often, for example reinvesting small dividends, pays these
  costs many times over.
- Every stock is bought in whole lots of 100 shares, so some cash can stay uninvested when a lot
  of a stock costs more than an equal share of the cash.
- A stock can be suspended, or its prices can be missing. steadyhand then does not trade it and
  values it at its last known price, which may turn out to be wrong.

## How often it trades

Very rarely. It buys on its first day, then only when a dividend or a top-up arrives, and it
never sells.

## Settings you can change

This strategy has no settings of its own. These engine settings change what it does:

- `monthly_contribution`: cash added on the first trading day of each month and spread across
  the stocks. The default is 0.
- The risk limits: the most any one stock may be of the portfolio (10% by default), which caps
  each purchase, and the daily loss and drawdown limits that stop all trading when they are
  reached.
```

**`packages/steadyhand/src/steadyhand/_ratio.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/_ratio.py -->
```python
"""Ratios as ``Decimal``, rounded down, for weights and fund-style unit values."""

from decimal import ROUND_FLOOR, Decimal, localcontext


def ratio_down(part: int | Decimal, whole: int | Decimal) -> Decimal:
    """*part* / *whole*, rounded down at the context's precision. Zero when *whole* is zero.

    Rounding down means weights built from these ratios never sum above 1.
    """
    if whole == 0:
        return Decimal(0)
    with localcontext() as context:
        context.rounding = ROUND_FLOOR
        return Decimal(part) / Decimal(whole)
```

**`packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py -->
```python
"""``buy-and-hold``: the baseline every other strategy is measured against (core spec §8).

On its first day it fixes its set: the stocks buyable that day. It never sells. Each day it keeps
every holding at its current weight, so nothing is traded against it, and it splits the cash it
may spend equally across the stocks in its set that are buyable today. Dividends and top-ups are
reinvested the same way. A stock that leaves the universe stays held (M3 spec §6.6).
"""

from __future__ import annotations

from decimal import Decimal

from steadyhand._ratio import ratio_down
from steadyhand.money import Currency
from steadyhand.strategies.protocol import Decision, Memory
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

_SET_KEY = "set"
"""The memory key holding the set, written as ``MARKET:SYMBOL`` separated by spaces."""


class BuyAndHold:
    """Buy the day-one universe in equal parts and hold it."""

    @property
    def name(self) -> str:
        return "buy-and-hold"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        currency = portfolio.value.currency
        chosen = _read(memory[_SET_KEY], currency) if _SET_KEY in memory else view.tradable.buyable
        weights = {instrument: portfolio.weight(instrument) for instrument in portfolio.holdings}
        buying = chosen & view.tradable.buyable
        if buying:
            each = ratio_down(portfolio.spendable.amount // len(buying), portfolio.value.amount)
            for instrument in buying:
                weights[instrument] = weights.get(instrument, Decimal(0)) + each
        return Decision(weights, {_SET_KEY: _write(chosen)})


def _write(chosen: frozenset[Instrument]) -> str:
    return " ".join(sorted(f"{i.market}:{i.symbol}" for i in chosen))


def _read(text: str, currency: Currency) -> frozenset[Instrument]:
    stocks = (entry.split(":") for entry in text.split())
    return frozenset(Instrument(symbol, market, currency) for market, symbol in stocks)
```

**`packages/steadyhand/src/steadyhand/strategies/protocol.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/strategies/protocol.py -->
```python
"""The Strategy protocol: a strategy says what share of the portfolio each stock should be.

Strategies return target weights, not orders (core spec §4.3). The sizer and the risk manager
turn weights into legal orders, so every rule about lots, ticks, cash and caps lives in one
tested place.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

from steadyhand._validate import require_type
from steadyhand.types import Instrument
from steadyhand.view import MarketView, PortfolioView

type Memory = Mapping[str, str]
"""What a strategy keeps from one day to the next, as text, so M5 can save it with the state."""


class InvalidWeightsError(ValueError):
    """A strategy returned weights that cannot be a portfolio. It is a bug in the strategy."""


@dataclass(frozen=True, slots=True)
class Decision:
    """A strategy's answer for one day: target weights, and what to remember until tomorrow.

    A stock missing from ``weights`` is targeted at zero. Weights are ``Decimal``, none is
    negative, and together they are at most 1; the rest is held as cash.
    """

    weights: Mapping[Instrument, Decimal]
    memory: Memory = field(default_factory=dict)

    def __post_init__(self) -> None:
        total = Decimal(0)
        for instrument, weight in self.weights.items():
            require_type(instrument, Instrument, "weighted stock")
            if not isinstance(weight, Decimal):
                msg = (
                    f"{instrument.symbol}: a weight must be a Decimal, got {type(weight).__name__}"
                )
                raise InvalidWeightsError(msg)
            if not weight.is_finite() or weight < 0:
                msg = f"{instrument.symbol}: a weight must be finite and not negative, got {weight}"
                raise InvalidWeightsError(msg)
            total += weight
        if total > 1:
            msg = f"weights sum to {total}, more than 1"
            raise InvalidWeightsError(msg)
        for key, value in self.memory.items():
            require_type(key, str, "memory key")
            require_type(value, str, "memory value")


@runtime_checkable
class Strategy(Protocol):
    """A way of choosing stocks. Each registered strategy has a plain-English guide (core §8)."""

    @property
    def name(self) -> str:
        """The name the configuration and the guide use, such as ``buy-and-hold``."""
        ...

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        """Today's target weights, given the market up to today and yesterday's memory."""
        ...
```

**`packages/steadyhand/src/steadyhand/view.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/view.py -->
```python
"""What a strategy may see on a decision day: prices up to that day, and nothing later.

``PriceHistory`` holds every bar a run can use and is built once. Each day gets a cheap
``MarketView`` over it, which refuses any date after its own day with ``LookAheadError`` (core
spec §4.3). A backtest that peeks at tomorrow's price looks brilliant and means nothing.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_type
from steadyhand.money import CurrencyMismatchError, Money
from steadyhand.types import Bar, Instrument, Side


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
class Tradable:
    """Today's buyable and sellable stocks, and why a stock is neither (M3 spec §6.4).

    ``reasons`` explains stocks kept out for a cause (frozen, excluded, refused data, no bar).
    Any other stock is out because it is not in the universe (for a buy) or not held (a sell).
    """

    day: date
    buyable: frozenset[Instrument]
    sellable: frozenset[Instrument]
    reasons: Mapping[Instrument, str]

    def __post_init__(self) -> None:
        require_date(self.day, "tradable day")
        for name, group in (("buyable", self.buyable), ("sellable", self.sellable)):
            require_type(group, frozenset, name)
        clash = sorted(i.symbol for i in (self.buyable | self.sellable) if i in self.reasons)
        if clash:
            msg = f"{', '.join(clash)} cannot be both tradable and kept out"
            raise ValueError(msg)

    def why_not(self, instrument: Instrument, side: Side) -> str | None:
        """Why *instrument* cannot be traded on *side* today, or ``None`` when it can."""
        allowed = self.buyable if side is Side.BUY else self.sellable
        if instrument in allowed:
            return None
        if instrument in self.reasons:
            return self.reasons[instrument]
        if side is Side.BUY:
            return f"not in the universe on {self.day.isoformat()}"
        return "not held"


class MarketView:
    """The market as a strategy sees it on ``today``."""

    def __init__(self, history: PriceHistory, today: date, tradable: Tradable) -> None:
        require_type(history, PriceHistory, "history")
        require_date(today, "today")
        require_type(tradable, Tradable, "tradable")
        if tradable.day != today:
            msg = f"the tradable set is for {tradable.day.isoformat()}, not {today.isoformat()}"
            raise ValueError(msg)
        self._history = history
        self._today = today
        self._tradable = tradable

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


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=588 passed=588 -->
Expected: every command exits 0; 588 passed, 4 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M7–M13; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S2 …`).

---

### Task 3: S3 SimulatedBroker

**Acceptance criteria (story text):**
1. `SimulatedBroker(rules, settings).fill(portfolio, orders, opening)` fills every sell, then every buy, each in the order given, at the day's open (M3 §5).
2. The price is the open × (1 + slippage) rounded up for a buy, × (1 − slippage) rounded down for a sale, then rounded to a tick against the trader. The order is rejected, with its reason, if the stock is frozen, has no bar, traded nothing, has no previous close to set the band, or the price falls outside the band; a price on the band's edge is accepted.
3. The quantity is cut to the configured share of the day's volume (10%), rounded down to whole lots, with the cut reported; less than a lot is a rejection.
4. A buy is cut to the whole lots that spendable cash pays for, costs and the day's charge included, or rejected if none. The day's `daily_costs` is charged once, on everything traded, only on a day with trades: settled that day if anything was bought, and with the sales at T+2 on a day of sales only (scope decision 1). A sale is refused only when its own proceeds and the cash could not pay the day's charge.
5. A hypothesis property holds over random cash, holdings, orders, opens and volumes: settled cash is never negative on the day or the two after it; every fill is whole lots, on a tick and inside its band; each buy moves cash by exactly minus its gross plus its costs and each sale by its gross less its costs; the day's charge appears once, and only when due; every order either fills or is rejected.
6. `FillSettings` defaults to 0.10% slippage and a 10% volume cap and refuses values outside [0, 1) and (0, 1]. `Rejected` and `Cut` refuse a blank reason, and a `Cut` must leave fewer shares than its order.
7. The `Broker` protocol's docstring says it is M5's manual broker, which the pure core does not call.
8. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M14–M19 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/outcomes.py`, `.../steadyhand/broker/simulated.py`
- Modify: `.../steadyhand/broker/__init__.py`, `.../steadyhand/broker/protocol.py`, `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_outcomes.py`, `tests/engine/test_simulated_broker.py`

**Interfaces:**
- Consumes: `Portfolio.spendable_cash`, `.charge(..., settles_on=)`, `MovementKind.DAILY_COST` (Task 1); `MarketRules` (M2).
- Produces: `Rejected(order: Order, reason: str)`; `Cut(order: Order, quantity: int, reason: str)`; `FillSettings(slippage: Decimal = Decimal("0.001"), volume_cap: Decimal = Decimal("0.10"))`; `Opening(day: date, bars: Mapping[Instrument, Bar], references: Mapping[Instrument, Money], frozen: Mapping[Instrument, str])`; `FillResult(portfolio, fills, rejected, cuts, daily_cost)`; `SimulatedBroker(rules: MarketRules, settings: FillSettings | None = None).fill(portfolio: Portfolio, orders: Sequence[Order], opening: Opening) -> FillResult`.

- [ ] **Step 1: Branch.** `git switch -c m3/s3-broker origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_outcomes.py`** (new)

<!-- file: tests/engine/test_outcomes.py -->
```python
"""Rejected and Cut: every order that does not go through as placed says why."""

from datetime import date

import pytest

from steadyhand.money import IDR
from steadyhand.outcomes import Cut, Rejected
from steadyhand.types import Instrument, Order, Side

ORDER = Order(Instrument("BBCA", "IDX", IDR), Side.BUY, 500, date(2025, 6, 2))


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


def test_a_cut_leaves_fewer_shares_than_the_order() -> None:
    with pytest.raises(ValueError, match=r"^a cut must leave fewer than 500 shares, got 500$"):
        Cut(ORDER, 500, "no change")
    with pytest.raises(ValueError, match=r"^cut quantity must be at least 1, got 0$"):
        Cut(ORDER, 0, "nothing left")


def test_outcomes_check_their_types() -> None:
    with pytest.raises(TypeError, match=r"^order must be an Order, got str$"):
        Rejected("BBCA", "no bar")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^reason must be a str, got int$"):
        Rejected(ORDER, 3)  # type: ignore[arg-type]
```

**`tests/engine/test_simulated_broker.py`** (new)

<!-- file: tests/engine/test_simulated_broker.py -->
```python
"""SimulatedBroker: yesterday's orders fill at today's open (M3 spec §5), on real IDX rules."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.broker import FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.money import IDR, Money
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Bar, Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

YESTERDAY = date(2025, 6, 2)
TODAY = date(2025, 6, 3)
SETTLES = date(2025, 6, 5)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
REFERENCES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR)}


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bar(stock: Instrument, open_: int, volume: int = 1_000_000, day: date = TODAY) -> Bar:
    return Bar(stock, day, rp(open_), rp(open_ * 2), rp(1), rp(open_), volume)


def portfolio(cash: int, held: dict[Instrument, int] | None = None) -> Portfolio:
    """*cash* spendable today, plus *held* shares bought yesterday at no cost."""
    book = Portfolio.empty(IDR)
    if cash:
        book = book.deposit(rp(cash), YESTERDAY)
    for stock, quantity in (held or {}).items():
        book = book.deposit(rp(quantity), YESTERDAY)
        order = Order(stock, Side.BUY, quantity, YESTERDAY)
        book = book.apply_fill(Fill(order, YESTERDAY, quantity, rp(1), Costs.zero(IDR)), SETTLES)
    return book


def buy(quantity: int, stock: Instrument = BBCA) -> Order:
    return Order(stock, Side.BUY, quantity, YESTERDAY)


def sell(quantity: int, stock: Instrument = BBCA) -> Order:
    return Order(stock, Side.SELL, quantity, YESTERDAY)


def run(
    book: Portfolio, *orders: Order, bars: list[Bar] | None = None, **frozen: str
) -> FillResult:
    """Fill *orders* today. Keyword arguments freeze a stock by symbol, with the reason."""
    today = {b.instrument: b for b in (bars if bars is not None else [bar(BBCA, 9_000)])}
    stocks = {stock.symbol: stock for stock in (BBCA, BBRI)}
    kept = {stocks[symbol]: reason for symbol, reason in frozen.items()}
    return SimulatedBroker(rules()).fill(
        book, list(orders), Opening(TODAY, today, REFERENCES, kept)
    )


def test_a_buy_pays_the_open_plus_slippage_rounded_up_to_a_tick() -> None:
    result = run(portfolio(10_000_000), buy(100))
    (only,) = result.fills
    assert (only.day, only.quantity, only.price) == (TODAY, 100, rp(9_025))
    assert only.costs == Costs(rp(1_504), rp(390), rp(0))
    assert result.portfolio.cash_balance() == rp(10_000_000 - 902_500 - 1_894)
    assert (result.rejected, result.cuts, result.daily_cost) == ((), (), rp(0))


def test_a_sale_receives_the_open_less_slippage_rounded_down_and_settles_at_t_plus_2() -> None:
    result = run(portfolio(0, {BBCA: 100}), sell(100))
    (only,) = result.fills
    assert (only.quantity, only.price) == (100, rp(8_975))
    assert only.costs.total == rp(2_781)
    assert result.portfolio.spendable_cash(TODAY) == rp(0)
    assert result.portfolio.spendable_cash(SETTLES) == rp(897_500 - 2_781)
    assert result.portfolio.position(BBCA) is None


def test_slippage_rounds_against_the_trader_before_the_tick() -> None:
    stock = Instrument("WIKA", "IDX", IDR)
    today = {stock: bar(stock, 150)}
    references = {stock: rp(150)}
    bought = SimulatedBroker(rules()).fill(
        portfolio(100_000), [buy(100, stock)], Opening(TODAY, today, references, {})
    )
    sold = SimulatedBroker(rules()).fill(
        portfolio(0, {stock: 100}), [sell(100, stock)], Opening(TODAY, today, references, {})
    )
    assert [f.price for f in bought.fills] == [rp(151)]
    assert [f.price for f in sold.fills] == [rp(149)]


def test_every_sell_fills_before_any_buy() -> None:
    orders = (buy(100, BBRI), sell(100), buy(100))
    bars = [bar(BBCA, 9_000), bar(BBRI, 4_000)]
    result = run(portfolio(2_000_000, {BBCA: 100}), *orders, bars=bars)
    assert [(f.order.side, f.order.instrument) for f in result.fills] == [
        (Side.SELL, BBCA),
        (Side.BUY, BBRI),
        (Side.BUY, BBCA),
    ]


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
        ),
    ],
)
def test_an_order_that_cannot_trade_is_rejected_with_its_reason(
    bars: list[Bar], frozen: dict[str, str], reason: str
) -> None:
    result = run(portfolio(10_000_000), buy(100), bars=bars, **frozen)
    assert result.fills == ()
    assert [(r.order, r.reason) for r in result.rejected] == [(buy(100), reason)]
    assert result.portfolio == portfolio(10_000_000)


def test_a_price_band_needs_a_previous_close() -> None:
    stock = Instrument("GOTO", "IDX", IDR)
    result = run(portfolio(10_000_000), buy(100, stock), bars=[bar(stock, 60)])
    assert [r.reason for r in result.rejected] == [
        "no previous close for GOTO to set the price band"
    ]


def test_a_price_on_the_band_edge_is_accepted() -> None:
    result = run(portfolio(0, {BBCA: 100}), sell(100), bars=[bar(BBCA, 7_665)])
    assert [f.price for f in result.fills] == [rp(7_650)]


def test_an_order_is_cut_to_a_tenth_of_the_volume_in_whole_lots() -> None:
    result = run(portfolio(10_000_000), buy(500), bars=[bar(BBCA, 9_000, volume=1_999)])
    assert [f.quantity for f in result.fills] == [100]
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (100, "cut to 10% of the day's 1,999 shares traded")
    ]


def test_an_order_is_rejected_when_a_tenth_of_the_volume_is_under_a_lot() -> None:
    result = run(portfolio(10_000_000), buy(100), bars=[bar(BBCA, 9_000, volume=999)])
    assert [r.reason for r in result.rejected] == [
        "10% of the day's 999 shares traded is less than a lot"
    ]


def test_a_buy_is_cut_to_the_lots_the_cash_pays_for() -> None:
    cash = 2 * (902_500 + 1_894)
    result = run(portfolio(cash), buy(300))
    assert [f.quantity for f in result.fills] == [200]
    assert [(c.quantity, c.reason) for c in result.cuts] == [
        (200, "cut to the IDR 1,808,788 that can be spent")
    ]
    # The costs of a trade round once, so two lots cost a rupiah less than two single lots.
    assert result.fills[0].costs.total == rp(3_787)
    assert result.portfolio.spendable_cash(TODAY) == rp(1)


def test_a_buy_the_cash_cannot_pay_for_is_rejected() -> None:
    result = run(portfolio(902_500 + 1_893), buy(100))
    assert [r.reason for r in result.rejected] == ["not enough cash: IDR 904,393 can be spent"]


def test_the_days_stamp_duty_is_held_back_from_a_buy_and_charged_once() -> None:
    cash = 10_830_000 + 22_722 + 10_000
    exact = run(portfolio(cash), buy(1_200))
    assert [f.quantity for f in exact.fills] == [1_200]
    assert exact.daily_cost == rp(10_000)
    assert exact.portfolio.spendable_cash(TODAY) == rp(0)
    assert exact.portfolio.ledger[-1].kind is MovementKind.DAILY_COST
    assert exact.portfolio.ledger[-1].settles_on == TODAY
    short = run(portfolio(cash - 1), buy(1_200))
    assert [f.quantity for f in short.fills] == [1_100]


def test_no_stamp_duty_on_a_day_of_ten_million_or_less() -> None:
    result = run(portfolio(10_000_000), buy(100))
    assert result.daily_cost == rp(0)
    assert MovementKind.DAILY_COST not in {m.kind for m in result.portfolio.ledger}


def test_a_sales_only_day_nets_its_stamp_duty_with_the_sales() -> None:
    result = run(portfolio(0, {BBCA: 1_200}), sell(1_200))
    assert result.daily_cost == rp(10_000)
    charge = result.portfolio.ledger[-1]
    assert (charge.kind, charge.amount, charge.settles_on) == (
        MovementKind.DAILY_COST,
        rp(-10_000),
        SETTLES,
    )
    assert result.portfolio.settled_cash(TODAY) == rp(0)
    assert result.portfolio.settled_cash(SETTLES) == rp(10_770_000 - 33_366 - 10_000)


def test_a_sale_is_refused_when_even_its_proceeds_cannot_pay_the_days_charge() -> None:
    day = date(2021, 6, 2)
    stock = Instrument("XXXX", "IDX", IDR)
    book = Portfolio.empty(IDR).deposit(rp(100), date(2021, 6, 1))
    order = Order(stock, Side.BUY, 100, date(2021, 6, 1))
    book = book.apply_fill(Fill(order, date(2021, 6, 1), 100, rp(1), Costs.zero(IDR)), day)
    today = {stock: bar(stock, 60, day=day)}
    result = SimulatedBroker(rules()).fill(
        book,
        [Order(stock, Side.SELL, 100, date(2021, 6, 1))],
        Opening(day, today, {stock: rp(60)}, {}),
    )
    assert [r.reason for r in result.rejected] == [
        "the day's charges of IDR 10,000 exceed the IDR 5,881 that could pay them"
    ]
    assert result.daily_cost == rp(0)


def test_settings_change_the_slippage_and_the_volume_cap() -> None:
    settings = FillSettings(slippage=Decimal(0), volume_cap=Decimal(1))
    today = {BBCA: bar(BBCA, 9_000, volume=500)}
    result = SimulatedBroker(rules(), settings).fill(
        portfolio(10_000_000), [buy(500)], Opening(TODAY, today, REFERENCES, {})
    )
    assert [(f.quantity, f.price) for f in result.fills] == [(500, rp(9_000))]


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"slippage": 0.001}, TypeError, r"^slippage must be a finite Decimal, got 0\.001$"),
        ({"volume_cap": Decimal("Infinity")}, TypeError, r"^volume_cap must be a finite Decimal"),
        ({"slippage": Decimal(1)}, ValueError, r"^slippage must be at least 0 and below 1, got 1$"),
        ({"slippage": Decimal(-1)}, ValueError, r"^slippage must be at least 0 and below 1"),
        (
            {"volume_cap": Decimal(0)},
            ValueError,
            r"^volume_cap must be above 0 and at most 1, got 0$",
        ),
        ({"volume_cap": Decimal("1.1")}, ValueError, r"^volume_cap must be above 0 and at most 1"),
    ],
)
def test_settings_are_checked(
    kwargs: dict[str, object], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        FillSettings(**kwargs)  # type: ignore[arg-type]


def test_the_defaults_are_the_specs() -> None:
    assert FillSettings() == FillSettings(Decimal("0.001"), Decimal("0.10"))


@given(
    cash=st.integers(0, 30_000_000),
    held=st.integers(0, 40),
    orders=st.lists(
        st.tuples(
            st.sampled_from([Side.BUY, Side.SELL]),
            st.sampled_from([BBCA, BBRI]),
            st.integers(1, 30),
        ),
        max_size=6,
    ),
    opens=st.tuples(st.integers(7_700, 10_700), st.integers(3_450, 4_950)),
    volumes=st.tuples(st.integers(0, 50_000), st.integers(0, 50_000)),
)
def test_fills_keep_cash_whole_lots_ticks_and_bands(
    cash: int,
    held: int,
    orders: list[tuple[Side, Instrument, int]],
    opens: tuple[int, int],
    volumes: tuple[int, int],
) -> None:
    book = portfolio(cash, {BBCA: held * 100, BBRI: held * 100} if held else {})
    selling = dict.fromkeys((BBCA, BBRI), 0)
    placed = []
    for side, stock, lots in orders:
        if side is Side.SELL:
            if selling[stock] + lots > held:
                continue  # the sizer never sells more than is held
            selling[stock] += lots
        placed.append(Order(stock, side, lots * 100, YESTERDAY))
    bars = [bar(BBCA, opens[0], volumes[0]), bar(BBRI, opens[1], volumes[1])]
    result = run(book, *placed, bars=bars)
    for probe in (TODAY, date(2025, 6, 4), SETTLES):
        assert result.portfolio.settled_cash(probe).amount >= 0
    movements = result.portfolio.ledger[len(book.ledger) :]
    expected = [
        -(f.gross + f.costs.total) if f.order.side is Side.BUY else f.gross - f.costs.total
        for f in result.fills
    ]
    traded = sum((f.gross for f in result.fills), rp(0))
    daily = rules().daily_costs(traded, TODAY) if result.fills else rp(0)
    if daily.amount:
        expected.append(-daily)
    assert [m.amount for m in movements] == expected
    assert result.daily_cost == daily
    for f in result.fills:
        assert f.quantity % 100 == 0
        assert rules().round_to_tick(f.order.instrument, f.price, f.order.side, TODAY) == f.price
        low, high = rules().price_band(f.order.instrument, REFERENCES[f.order.instrument], TODAY)
        assert low <= f.price <= high
    assert len(result.fills) + len(result.rejected) == len(placed)
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python

from steadyhand.broker import Broker
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
```
with:
```python

from steadyhand.broker import Broker, FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.portfolio import (
```
with:
```python
)
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "CurrencyMismatchError",
    "DataSource",
```
with:
```python
    "CurrencyMismatchError",
    "Cut",
    "DataSource",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Fill",
    "Instrument",
```
with:
```python
    "Fill",
    "FillResult",
    "FillSettings",
    "Instrument",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "NegativeProceedsError",
    "Order",
```
with:
```python
    "NegativeProceedsError",
    "Opening",
    "Order",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "PriceHistory",
    "Rounding",
    "Side",
    "Split",
```
with:
```python
    "PriceHistory",
    "Rejected",
    "Rounding",
    "Side",
    "SimulatedBroker",
    "Split",
```

**`packages/steadyhand/src/steadyhand/broker/__init__.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/broker/__init__.py -->
Replace:
```python
"""Brokers: the Broker protocol."""

from steadyhand.broker.protocol import Broker

__all__ = ["Broker"]
```
with:
```python
"""Brokers: the Broker protocol, and the simulated fill the backtest and paper modes use."""

from steadyhand.broker.protocol import Broker
from steadyhand.broker.simulated import FillResult, FillSettings, Opening, SimulatedBroker

__all__ = ["Broker", "FillResult", "FillSettings", "Opening", "SimulatedBroker"]
```

**`packages/steadyhand/src/steadyhand/broker/protocol.py`** (changed, new names stubbed: 1 edit)

<!-- edit: packages/steadyhand/src/steadyhand/broker/protocol.py -->
Replace:
```python
class Broker(Protocol):
    """Accepts orders and reports what filled. The simulated broker arrives in M3."""

```
with:
```python
class Broker(Protocol):
    """Accepts orders and reports what filled: M5's manual "Confirm Fill" broker.

    The engine's pure core does not call it. Backtests and paper runs fill orders with
    ``SimulatedBroker``, which is a function of the day's prices rather than a place orders go.
    """

```

**`packages/steadyhand/src/steadyhand/broker/simulated.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/broker/simulated.py -->
```python
"""The simulated fill: yesterday's orders trade at today's open (core spec §5.1, M3 spec §5).

It is a pure function of the portfolio, the orders and today's prices, so a backtest can rerun a
day and get the same answer. It is not a ``Broker``: that protocol is for M5's manual broker,
where orders leave the program and fills come back.

Every fill is checked so cash never runs short. The day's stamp duty is charged once, after the
last fill, and settles with the day's trades (T+2), the way a broker nets it on the confirmation.
A buy therefore holds back the day's charge from the cash it may spend, and a sale is refused
only if even its own proceeds could not pay the day's charge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Bar, Fill, Instrument, Order, Side


def _percent(rate: Decimal) -> str:
    raise NotImplementedError("_percent")


@dataclass(frozen=True, slots=True)
class FillSettings:
    """How optimistic the simulated fill may be. Both defaults are core spec §5.1's."""

    slippage: Decimal = Decimal("0.001")
    """Buys pay this much above the open and sales receive this much below it."""
    volume_cap: Decimal = Decimal("0.10")
    """The largest share of a day's traded volume one order may take."""

    def __post_init__(self) -> None:
        raise NotImplementedError("FillSettings.__post_init__")


@dataclass(frozen=True, slots=True)
class Opening:
    """What the market shows at today's open, for the stocks with orders.

    ``bars`` holds today's bar for each stock that has one, ``references`` the previous close
    that sets each stock's price band, and ``frozen`` each frozen stock with its reason.
    """

    day: date
    bars: Mapping[Instrument, Bar]
    references: Mapping[Instrument, Money]
    frozen: Mapping[Instrument, str]


@dataclass(frozen=True, slots=True)
class FillResult:
    """One day's fills: the new portfolio, what traded, what did not and why."""

    portfolio: Portfolio
    fills: tuple[Fill, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]
    daily_cost: Money


class SimulatedBroker:
    """Fills queued orders at the next open, after slippage, ticks, bands, volume and cash."""

    def __init__(self, rules: MarketRules, settings: FillSettings | None = None) -> None:
        raise NotImplementedError("SimulatedBroker.__init__")

    def fill(self, portfolio: Portfolio, orders: Sequence[Order], opening: Opening) -> FillResult:
        """Fill *orders* at the open: every sell first, then every buy, each in its order."""
        raise NotImplementedError("SimulatedBroker.fill")

    def _price(self, order: Order, opening: Opening) -> Money | str:
        raise NotImplementedError("SimulatedBroker._price")

    def _volume_capped(self, order: Order, opening: Opening, session: _Session) -> int | str:
        raise NotImplementedError("SimulatedBroker._volume_capped")


class _Session:
    """One day's fills in progress: the portfolio so far, and the day's running totals."""

    def __init__(self, rules: MarketRules, portfolio: Portfolio, day: date) -> None:
        raise NotImplementedError("_Session.__init__")

    def reject(self, order: Order, reason: str) -> None:
        raise NotImplementedError("_Session.reject")

    def cut(self, order: Order, quantity: int, reason: str) -> None:
        raise NotImplementedError("_Session.cut")

    def buy(self, order: Order, wanted: int, price: Money) -> None:
        """Buy the most whole lots, up to *wanted*, whose cost and the day's charge are paid."""
        raise NotImplementedError("_Session.buy")

    def sell(self, order: Order, quantity: int, price: Money) -> None:
        """Sell, unless the day's charge would exceed the cash and proceeds that could pay it."""
        raise NotImplementedError("_Session.sell")

    def close(self) -> FillResult:
        """Charge the day's costs once, on everything traded, and report the day."""
        raise NotImplementedError("_Session.close")

    def _cost(self, gross: Money) -> Money:
        """A buy's cost with the day's charge on everything traded so far, this buy included."""
        raise NotImplementedError("_Session._cost")

    def _book(self, order: Order, quantity: int, price: Money) -> None:
        raise NotImplementedError("_Session._book")

    def _daily(self, traded: Money) -> Money:
        raise NotImplementedError("_Session._daily")
```

**`packages/steadyhand/src/steadyhand/outcomes.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/outcomes.py -->
```python
"""What happened to an order that did not go through as it was placed.

The broker, the sizer and the risk manager all report the same two things, each with a reason
that the day's report prints (core spec §6.1: every dropped or cut order carries a reason).
"""

from __future__ import annotations

from dataclasses import dataclass

from steadyhand._validate import require_int, require_type
from steadyhand.types import Order


def _require_reason(reason: object, order: Order) -> None:
    raise NotImplementedError("_require_reason")


@dataclass(frozen=True, slots=True)
class Rejected:
    """An order that will not trade at all, and why."""

    order: Order
    reason: str

    def __post_init__(self) -> None:
        raise NotImplementedError("Rejected.__post_init__")


@dataclass(frozen=True, slots=True)
class Cut:
    """An order made smaller, to ``quantity`` shares, and why."""

    order: Order
    quantity: int
    reason: str

    def __post_init__(self) -> None:
        raise NotImplementedError("Cut.__post_init__")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=620 failed=32 -->
Expected: 620 run (the 4 `live` tests deselected), 32 failed. Every one fails on `NotImplementedError`; no new test passes against the stubs.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/broker/simulated.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/broker/simulated.py -->
```python
"""The simulated fill: yesterday's orders trade at today's open (core spec §5.1, M3 spec §5).

It is a pure function of the portfolio, the orders and today's prices, so a backtest can rerun a
day and get the same answer. It is not a ``Broker``: that protocol is for M5's manual broker,
where orders leave the program and fills come back.

Every fill is checked so cash never runs short. The day's stamp duty is charged once, after the
last fill, and settles with the day's trades (T+2), the way a broker nets it on the confirmation.
A buy therefore holds back the day's charge from the cash it may spend, and a sale is refused
only if even its own proceeds could not pay the day's charge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Bar, Fill, Instrument, Order, Side


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).normalize():f}%"


@dataclass(frozen=True, slots=True)
class FillSettings:
    """How optimistic the simulated fill may be. Both defaults are core spec §5.1's."""

    slippage: Decimal = Decimal("0.001")
    """Buys pay this much above the open and sales receive this much below it."""
    volume_cap: Decimal = Decimal("0.10")
    """The largest share of a day's traded volume one order may take."""

    def __post_init__(self) -> None:
        for name, rate in (("slippage", self.slippage), ("volume_cap", self.volume_cap)):
            if not isinstance(rate, Decimal) or not rate.is_finite():
                msg = f"{name} must be a finite Decimal, got {rate!r}"
                raise TypeError(msg)
        if not 0 <= self.slippage < 1:
            msg = f"slippage must be at least 0 and below 1, got {self.slippage}"
            raise ValueError(msg)
        if not 0 < self.volume_cap <= 1:
            msg = f"volume_cap must be above 0 and at most 1, got {self.volume_cap}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Opening:
    """What the market shows at today's open, for the stocks with orders.

    ``bars`` holds today's bar for each stock that has one, ``references`` the previous close
    that sets each stock's price band, and ``frozen`` each frozen stock with its reason.
    """

    day: date
    bars: Mapping[Instrument, Bar]
    references: Mapping[Instrument, Money]
    frozen: Mapping[Instrument, str]


@dataclass(frozen=True, slots=True)
class FillResult:
    """One day's fills: the new portfolio, what traded, what did not and why."""

    portfolio: Portfolio
    fills: tuple[Fill, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]
    daily_cost: Money


class SimulatedBroker:
    """Fills queued orders at the next open, after slippage, ticks, bands, volume and cash."""

    def __init__(self, rules: MarketRules, settings: FillSettings | None = None) -> None:
        self._rules = rules
        self._settings = FillSettings() if settings is None else settings

    def fill(self, portfolio: Portfolio, orders: Sequence[Order], opening: Opening) -> FillResult:
        """Fill *orders* at the open: every sell first, then every buy, each in its order."""
        session = _Session(self._rules, portfolio, opening.day)
        for order in sorted(orders, key=lambda order: order.side is Side.BUY):
            price = self._price(order, opening)
            if isinstance(price, str):
                session.reject(order, price)
                continue
            wanted = self._volume_capped(order, opening, session)
            if isinstance(wanted, str):
                session.reject(order, wanted)
            elif order.side is Side.BUY:
                session.buy(order, wanted, price)
            else:
                session.sell(order, wanted, price)
        return session.close()

    def _price(self, order: Order, opening: Opening) -> Money | str:
        instrument = order.instrument
        day = opening.day
        bar = opening.bars.get(instrument)
        if instrument in opening.frozen:
            return f"frozen: {opening.frozen[instrument]}"
        if bar is None:
            return f"no bar for {instrument.symbol} on {day.isoformat()}"
        if bar.volume == 0:
            return f"{instrument.symbol} did not trade on {day.isoformat()}"
        slippage = self._settings.slippage
        if order.side is Side.BUY:
            slipped = bar.open.times(1 + slippage, Rounding.UP)
        else:
            slipped = bar.open.times(1 - slippage, Rounding.DOWN)
        price = self._rules.round_to_tick(instrument, slipped, order.side, day)
        reference = opening.references.get(instrument)
        if reference is None:
            return f"no previous close for {instrument.symbol} to set the price band"
        low, high = self._rules.price_band(instrument, reference, day)
        if not low <= price <= high:
            return f"fill price {price} is outside the band {low} to {high}"
        return price

    def _volume_capped(self, order: Order, opening: Opening, session: _Session) -> int | str:
        cap = self._settings.volume_cap
        volume = opening.bars[order.instrument].volume
        lot = self._rules.lot_size(order.instrument, opening.day)
        allowed = int((volume * cap).to_integral_value(rounding=ROUND_FLOOR)) // lot * lot
        if allowed == 0:
            return f"{_percent(cap)} of the day's {volume:,} shares traded is less than a lot"
        if order.quantity <= allowed:
            return order.quantity
        session.cut(order, allowed, f"cut to {_percent(cap)} of the day's {volume:,} shares traded")
        return allowed


class _Session:
    """One day's fills in progress: the portfolio so far, and the day's running totals."""

    def __init__(self, rules: MarketRules, portfolio: Portfolio, day: date) -> None:
        self._rules = rules
        self._portfolio = portfolio
        self._day = day
        self._fills: list[Fill] = []
        self._rejected: list[Rejected] = []
        self._cuts: list[Cut] = []
        self._traded = Money.zero(portfolio.currency)
        self._proceeds = Money.zero(portfolio.currency)
        self._bought = False

    def reject(self, order: Order, reason: str) -> None:
        self._rejected.append(Rejected(order, reason))

    def cut(self, order: Order, quantity: int, reason: str) -> None:
        self._cuts.append(Cut(order, quantity, reason))

    def buy(self, order: Order, wanted: int, price: Money) -> None:
        """Buy the most whole lots, up to *wanted*, whose cost and the day's charge are paid."""
        available = self._portfolio.spendable_cash(self._day)
        lot = self._rules.lot_size(order.instrument, self._day)
        quantity = min(wanted, max(available.amount, 0) // (price * lot).amount * lot)
        while quantity > 0 and self._cost(price * quantity) > available:
            quantity -= lot
        if quantity == 0:
            self.reject(order, f"not enough cash: {available} can be spent")
            return
        if quantity < wanted:
            self.cut(order, quantity, f"cut to the {available} that can be spent")
        self._book(order, quantity, price)
        self._bought = True

    def sell(self, order: Order, quantity: int, price: Money) -> None:
        """Sell, unless the day's charge would exceed the cash and proceeds that could pay it."""
        gross = price * quantity
        net = gross - self._rules.costs(Side.SELL, gross, self._day).total
        daily = self._daily(self._traded + gross)
        covering = self._portfolio.spendable_cash(self._day) + self._proceeds + net
        if daily > covering:
            self.reject(
                order, f"the day's charges of {daily} exceed the {covering} that could pay them"
            )
            return
        self._book(order, quantity, price)
        self._proceeds += net

    def close(self) -> FillResult:
        """Charge the day's costs once, on everything traded, and report the day."""
        daily = self._daily(self._traded)
        portfolio = self._portfolio
        if daily.amount > 0:
            settles = self._day if self._bought else self._rules.settlement_date(self._day)
            portfolio = portfolio.charge(
                MovementKind.DAILY_COST, daily, self._day, settles_on=settles
            )
        return FillResult(
            portfolio, tuple(self._fills), tuple(self._rejected), tuple(self._cuts), daily
        )

    def _cost(self, gross: Money) -> Money:
        """A buy's cost with the day's charge on everything traded so far, this buy included."""
        buying = self._rules.costs(Side.BUY, gross, self._day).total
        return gross + buying + self._daily(self._traded + gross)

    def _book(self, order: Order, quantity: int, price: Money) -> None:
        gross = price * quantity
        fill = Fill(
            order, self._day, quantity, price, self._rules.costs(order.side, gross, self._day)
        )
        settles = self._rules.settlement_date(self._day)
        self._portfolio = self._portfolio.apply_fill(fill, settles)
        self._fills.append(fill)
        self._traded += gross

    def _daily(self, traded: Money) -> Money:
        if traded.amount == 0:
            return Money.zero(traded.currency)
        return self._rules.daily_costs(traded, self._day)
```

**`packages/steadyhand/src/steadyhand/outcomes.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/outcomes.py -->
```python
"""What happened to an order that did not go through as it was placed.

The broker, the sizer and the risk manager all report the same two things, each with a reason
that the day's report prints (core spec §6.1: every dropped or cut order carries a reason).
"""

from __future__ import annotations

from dataclasses import dataclass

from steadyhand._validate import require_int, require_type
from steadyhand.types import Order


def _require_reason(reason: object, order: Order) -> None:
    require_type(reason, str, "reason")
    if not str(reason).strip():
        msg = f"a {order.side.value} order for {order.instrument.symbol} needs a reason"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Rejected:
    """An order that will not trade at all, and why."""

    order: Order
    reason: str

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        _require_reason(self.reason, self.order)


@dataclass(frozen=True, slots=True)
class Cut:
    """An order made smaller, to ``quantity`` shares, and why."""

    order: Order
    quantity: int
    reason: str

    def __post_init__(self) -> None:
        require_type(self.order, Order, "order")
        require_int(self.quantity, "cut quantity", minimum=1)
        if self.quantity >= self.order.quantity:
            msg = f"a cut must leave fewer than {self.order.quantity} shares, got {self.quantity}"
            raise ValueError(msg)
        _require_reason(self.reason, self.order)
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=620 passed=620 -->
Expected: every command exits 0; 620 passed, 4 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M14–M19; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S3 …`).

---

### Task 4: S4 Sizing, risk and the unit value

**Acceptance criteria (story text):**
1. `CompoundingSizer(rules).size(weights, portfolio, held, prices, day)` targets weight × the portfolio's value for each weighted or held stock (a stock missing from the weights is targeted at zero) and turns the difference from the holding into whole lots at the last close, rounded towards zero, so a target within a lot of the holding places no order. A sale never exceeds the whole lots held. Sells come first, then buys, each by market and symbol. A stock with no price raises `LookupError` naming it. A hypothesis property: no buy overshoots its target and no sale undershoots it.
2. `RiskLimits` defaults to core §6.1 (10% per stock, 1 lot, 5% daily loss, 25% drawdown) and refuses values outside their ranges.
3. `RiskManager.check(orders, portfolio, tradable, prices)` drops an order outside the tradable set with the set's reason; cuts a buy to the per-stock limit, or drops it when the stock is already there; drops a buy below the minimum lots; and caps buys together at spendable cash, costs included, cutting or dropping the rest. Sales pass and their proceeds fund nothing. Each limit is tested at its edge and one step past.
4. `UnitValue` starts with no units at a price of 1; a deposit buys units at the current price and leaves it unchanged, and `revalue` sets the price and raises the high-water mark. A hypothesis property: valued again with the deposit in it, the price is the same to 20 decimal places.
5. `RiskManager.halt(before, after, day)` returns a `Halt` naming the cause when the day's fall reaches the daily loss limit or the price reaches the drawdown limit below the high-water mark, and nothing before there are units.
6. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M20–M24 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/sizing.py`, `.../steadyhand/risk.py`
- Modify: `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_sizing.py`, `tests/engine/test_risk.py`

**Interfaces:**
- Consumes: `PortfolioView`, `Tradable`, `ratio_down` (Task 2); `Rejected`, `Cut` (Task 3).
- Produces: `Sizer` (protocol) and `CompoundingSizer(rules: MarketRules)` with `.size(weights: Mapping[Instrument, Decimal], portfolio: PortfolioView, held: Mapping[Instrument, int], prices: Mapping[Instrument, Money], day: date) -> tuple[Order, ...]`; `RiskLimits(max_weight: Decimal = Decimal("0.10"), min_lots: int = 1, daily_loss: Decimal = Decimal("0.05"), max_drawdown: Decimal = Decimal("0.25"))`; `Halt(day: date, cause: str)`; `UnitValue(units: Decimal = 0, price: Decimal = 1, high_water: Decimal = 1)` with `.revalue(value: Money)`, `.deposit(amount: Money)`; `Checked(orders, rejected, cuts)`; `RiskManager(rules: MarketRules, limits: RiskLimits | None = None)` with `.limits`, `.check(orders, portfolio, tradable, prices) -> Checked`, `.halt(before: UnitValue, after: UnitValue, day: date) -> Halt | None`.

- [ ] **Step 1: Branch.** `git switch -c m3/s4-sizing-risk origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_risk.py`** (new)

<!-- file: tests/engine/test_risk.py -->
```python
"""RiskManager, RiskLimits and the unit value: every limit at its threshold and one step past."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView, Tradable
from steadyhand_idx import IdxMarketRules

DAY = date(2025, 6, 2)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
PRICES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR)}
OPEN = Tradable(DAY, frozenset({BBCA, BBRI}), frozenset({BBCA, BBRI}), {TLKM: "frozen: merger"})


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def buy(quantity: int, stock: Instrument = BBCA) -> Order:
    return Order(stock, Side.BUY, quantity, DAY)


def check(
    *orders: Order,
    value: int = 100_000_000,
    spendable: int | None = None,
    held: dict[Instrument, int] | None = None,
    limits: RiskLimits | None = None,
) -> tuple[list[Order], list[tuple[Order, str]], list[tuple[int, str]]]:
    """Check *orders* for a portfolio worth *value*, spending all of it not *held* by default."""
    holdings = {stock: rp(amount) for stock, amount in (held or {}).items()}
    cash = value - sum((held or {}).values()) if spendable is None else spendable
    portfolio = PortfolioView(rp(value), rp(cash), holdings)
    result = RiskManager(rules(), limits).check(orders, portfolio, OPEN, PRICES)
    rejected = [(r.order, r.reason) for r in result.rejected]
    return list(result.orders), rejected, [(c.quantity, c.reason) for c in result.cuts]


def test_the_defaults_are_the_core_specs() -> None:
    limits = RiskManager(rules()).limits
    assert limits == RiskLimits(Decimal("0.10"), 1, Decimal("0.05"), Decimal("0.25"))


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"max_weight": 0.1}, TypeError, r"^max_weight must be a finite Decimal, got 0\.1$"),
        ({"daily_loss": Decimal("NaN")}, TypeError, r"^daily_loss must be a finite Decimal"),
        ({"min_lots": 0}, ValueError, r"^min_lots must be at least 1, got 0$"),
        ({"max_weight": Decimal(0)}, ValueError, r"^max_weight must be above 0 and at most 1"),
        ({"max_weight": Decimal("1.01")}, ValueError, r"^max_weight must be above 0 and at most"),
        (
            {"daily_loss": Decimal(1)},
            ValueError,
            r"^daily_loss must be above 0 and below 1, got 1$",
        ),
        ({"max_drawdown": Decimal(0)}, ValueError, r"^max_drawdown must be above 0 and below 1"),
    ],
)
def test_limits_are_checked(
    kwargs: dict[str, object], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        RiskLimits(**kwargs)  # type: ignore[arg-type]


def test_a_stock_outside_the_tradable_set_is_dropped_with_its_reason() -> None:
    sell = Order(TLKM, Side.SELL, 100, DAY)
    stranger = buy(100, Instrument("ASII", "IDX", IDR))
    passed, rejected, _ = check(buy(100, TLKM), sell, stranger)
    assert passed == []
    assert rejected == [
        (buy(100, TLKM), "frozen: merger"),
        (sell, "frozen: merger"),
        (stranger, "not in the universe on 2025-06-02"),
    ]


def test_sales_pass_and_their_proceeds_fund_nothing() -> None:
    sell = Order(BBCA, Side.SELL, 1_000, DAY)
    passed, rejected, _ = check(sell, buy(100), spendable=0)
    assert passed == [sell]
    assert rejected == [(buy(100), "not enough cash: IDR 0 can be spent")]


def test_a_buy_is_cut_to_the_limit_per_stock_exactly_at_its_edge() -> None:
    passed, _, cuts = check(buy(300), value=18_000_000)
    assert passed == [buy(200)]
    assert cuts == [(200, "cut to the 10.00% limit per stock")]
    passed, _, cuts = check(buy(300), value=17_999_990)
    assert passed == [buy(100)]


def test_a_buy_for_a_stock_already_at_the_limit_is_dropped() -> None:
    _, rejected, _ = check(buy(100), value=10_000_000, held={BBCA: 900_001})
    assert rejected == [(buy(100), "already at the 10.00% limit per stock")]


def test_a_buy_below_the_minimum_lots_is_dropped() -> None:
    limits = RiskLimits(min_lots=2)
    passed, rejected, _ = check(buy(100), buy(200, BBRI), limits=limits)
    assert rejected == [(buy(100), "below the minimum buy of 2 lot(s)")]
    assert passed == [buy(200, BBRI)]


def test_buys_together_spend_no_more_than_the_cash_costs_included() -> None:
    limits = RiskLimits(max_weight=Decimal(1))
    passed, rejected, _ = check(buy(100), buy(100, BBRI), spendable=1_000_000, limits=limits)
    assert passed == [buy(100)]
    assert rejected == [(buy(100, BBRI), "not enough cash: IDR 98,111 can be spent")]
    passed, _, cuts = check(buy(300), spendable=1_803_777, limits=limits)
    assert passed == [buy(200)]
    assert cuts == [(200, "cut to the IDR 1,803,777 that can be spent")]
    passed, _, _ = check(buy(300), spendable=1_803_776, limits=limits)
    assert passed == [buy(100)]


def test_the_first_deposit_buys_units_at_one() -> None:
    funded = UnitValue().deposit(rp(10_000_000))
    assert funded == UnitValue(Decimal(10_000_000), Decimal(1), Decimal(1))


def test_a_deposit_leaves_the_unit_value_unchanged() -> None:
    fund = UnitValue().deposit(rp(10_000_000)).revalue(rp(12_000_000))
    topped = fund.deposit(rp(1_200_000))
    assert (topped.units, topped.price) == (Decimal(11_000_000), Decimal("1.2"))
    assert topped.revalue(rp(13_200_000)).price == Decimal("1.2")


def test_revaluing_moves_the_price_and_the_high_water_mark() -> None:
    fund = UnitValue().deposit(rp(1_000)).revalue(rp(1_500)).revalue(rp(1_200))
    assert (fund.price, fund.high_water) == (Decimal("1.2"), Decimal("1.5"))
    assert UnitValue().revalue(rp(5)) == UnitValue()


def test_units_cannot_be_bought_at_nothing_and_are_never_negative() -> None:
    worthless = UnitValue(Decimal(10), Decimal(0), Decimal(1))
    with pytest.raises(ValueError, match=r"^no units can be bought at a price of 0$"):
        worthless.deposit(rp(1))
    with pytest.raises(ValueError, match=r"^units cannot be negative, got -1$"):
        UnitValue(Decimal(-1))
    with pytest.raises(TypeError, match=r"^price must be a finite Decimal, got 1$"):
        UnitValue(Decimal(1), 1)  # type: ignore[arg-type]


@given(
    units=st.integers(1, 10**12),
    value=st.integers(1, 10**13),
    deposit=st.integers(1, 10**12),
)
def test_a_deposit_never_moves_the_price(units: int, value: int, deposit: int) -> None:
    fund = UnitValue(Decimal(units)).revalue(rp(value))
    topped = fund.deposit(rp(deposit))
    assert topped.price == fund.price
    # Valued again with the deposit in it, the fund is worth what it was per unit: a deposit
    # is neither a gain nor a loss. Decimal rounding at 28 digits may move it either way, by
    # far less than any limit could notice.
    after = topped.revalue(rp(value + deposit)).price
    assert abs(after - fund.price) <= fund.price * Decimal("1e-20")


def fund(price: str, high_water: str = "1") -> UnitValue:
    return UnitValue(Decimal(100), Decimal(price), Decimal(high_water))


def test_a_daily_loss_at_the_limit_halts() -> None:
    halt = RiskManager(rules()).halt(fund("1"), fund("0.95"), DAY)
    assert halt == Halt(DAY, "daily loss limit: the unit value fell 5.00%, the limit is 5.00%")
    assert RiskManager(rules()).halt(fund("1"), fund("0.9501"), DAY) is None


def test_a_drawdown_at_the_kill_switch_halts() -> None:
    manager = RiskManager(rules())
    halt = manager.halt(fund("0.76", "1"), fund("0.75", "1"), DAY)
    assert halt == Halt(
        DAY,
        "drawdown kill switch: the unit value is 25.00% below its high-water mark, "
        "the limit is 25.00%",
    )
    assert manager.halt(fund("0.76", "1"), fund("0.7501", "1"), DAY) is None


def test_no_halt_before_there_are_units() -> None:
    empty = UnitValue()
    assert RiskManager(rules()).halt(empty, UnitValue(Decimal(0), Decimal("0.1")), DAY) is None
    assert RiskManager(rules()).halt(empty, fund("0.96"), DAY) is None


def test_a_halt_needs_a_day_and_a_cause() -> None:
    with pytest.raises(ValueError, match=r"^a halt needs a cause$"):
        Halt(DAY, " ")
    with pytest.raises(TypeError, match=r"^halt day must be a date, got str$"):
        Halt("2025-06-02", "x")  # type: ignore[arg-type]
```

**`tests/engine/test_sizing.py`** (new)

<!-- file: tests/engine/test_sizing.py -->
```python
"""CompoundingSizer: target weights to whole lots, rounded towards zero (M3 spec §6.2)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Money, Rounding
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView
from steadyhand_idx import IdxMarketRules

DAY = date(2025, 6, 2)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
TLKM = Instrument("TLKM", "IDX", IDR)
PRICES = {BBCA: Money(9_000, IDR), BBRI: Money(4_000, IDR), TLKM: Money(2_500, IDR)}


@cache
def sizer() -> CompoundingSizer:
    return CompoundingSizer(IdxMarketRules())


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def view(value: int, held: dict[Instrument, int]) -> PortfolioView:
    holdings = {stock: PRICES[stock] * shares for stock, shares in held.items()}
    return PortfolioView(rp(value), rp(0), holdings)


def size(weights: dict[Instrument, str], value: int, held: dict[Instrument, int]) -> list[Order]:
    decimals = {stock: Decimal(weight) for stock, weight in weights.items()}
    return list(sizer().size(decimals, view(value, held), held, PRICES, DAY))


def test_it_is_a_sizer() -> None:
    assert isinstance(sizer(), Sizer)


def test_a_weight_becomes_whole_lots_at_the_last_close_rounded_down() -> None:
    assert size({BBCA: "0.5"}, 10_000_000, {}) == [Order(BBCA, Side.BUY, 500, DAY)]
    assert size({BBCA: "0.54"}, 10_000_000, {}) == [Order(BBCA, Side.BUY, 600, DAY)]
    assert size({BBCA: "0.53999"}, 10_000_000, {}) == [Order(BBCA, Side.BUY, 500, DAY)]


def test_sizes_grow_with_the_portfolio() -> None:
    assert size({BBCA: "0.5"}, 20_000_000, {}) == [Order(BBCA, Side.BUY, 1_100, DAY)]


def test_a_stock_missing_from_the_weights_is_sold() -> None:
    assert size({}, 10_000_000, {BBCA: 200}) == [Order(BBCA, Side.SELL, 200, DAY)]


def test_a_target_within_a_lot_of_the_holding_places_no_order() -> None:
    assert size({BBCA: "0.18"}, 10_000_000, {BBCA: 200}) == []
    assert size({BBCA: "0.26999"}, 10_000_000, {BBCA: 200}) == []
    assert size({BBCA: "0.27"}, 10_000_000, {BBCA: 200}) == [Order(BBCA, Side.BUY, 100, DAY)]
    assert size({BBCA: "0.09"}, 10_000_000, {BBCA: 200}) == [Order(BBCA, Side.SELL, 100, DAY)]


def test_a_sale_is_whole_lots_of_what_is_held() -> None:
    assert size({}, 10_000_000, {BBCA: 150}) == [Order(BBCA, Side.SELL, 100, DAY)]
    assert size({}, 10_000_000, {BBCA: 50}) == []


def test_sells_come_first_then_buys_each_by_symbol() -> None:
    orders = size({TLKM: "0.1", BBCA: "0.2"}, 10_000_000, {BBRI: 500})
    assert [(o.side, o.instrument.symbol) for o in orders] == [
        (Side.SELL, "BBRI"),
        (Side.BUY, "BBCA"),
        (Side.BUY, "TLKM"),
    ]


def test_a_stock_with_no_price_cannot_be_sized() -> None:
    stock = Instrument("GOTO", "IDX", IDR)
    with pytest.raises(LookupError, match=r"^no price for GOTO on 2025-06-02 to size it with$"):
        sizer().size({stock: Decimal("0.1")}, view(10_000_000, {}), {}, PRICES, DAY)


@given(
    value=st.integers(0, 10**10),
    weights=st.lists(st.integers(0, 1_000), min_size=3, max_size=3),
    held=st.lists(st.integers(0, 5_000), min_size=3, max_size=3),
)
def test_orders_are_whole_lots_that_never_overshoot_the_target(
    value: int, weights: list[int], held: list[int]
) -> None:
    stocks = (BBCA, BBRI, TLKM)
    total = sum(weights) or 1
    decimals = {s: Decimal(w) / total / 2 for s, w in zip(stocks, weights, strict=True)}
    shares = {s: h for s, h in zip(stocks, held, strict=True) if h}
    worth = sum(PRICES[s].amount * n for s, n in shares.items())
    portfolio = view(worth + value, shares)
    orders = sizer().size(decimals, portfolio, shares, PRICES, DAY)
    for order in orders:
        stock = order.instrument
        assert order.quantity % 100 == 0
        target = portfolio.value.times(decimals[stock], rounding=Rounding.DOWN).amount
        current = PRICES[stock].amount * shares.get(stock, 0)
        traded = PRICES[stock].amount * order.quantity
        if order.side is Side.BUY:
            assert current + traded <= target
        else:
            assert order.quantity <= shares[stock]
            assert current - traded >= target
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 5 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
)
from steadyhand.strategies import (
```
with:
```python
)
from steadyhand.risk import Checked, Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer, Sizer
from steadyhand.strategies import (
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "CashMovement",
    "ChronologyError",
    "CorporateAction",
```
with:
```python
    "CashMovement",
    "Checked",
    "ChronologyError",
    "CompoundingSizer",
    "CorporateAction",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "FillSettings",
    "Instrument",
```
with:
```python
    "FillSettings",
    "Halt",
    "Instrument",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Rejected",
    "Rounding",
    "Side",
    "SimulatedBroker",
    "Split",
```
with:
```python
    "Rejected",
    "RiskLimits",
    "RiskManager",
    "Rounding",
    "Side",
    "SimulatedBroker",
    "Sizer",
    "Split",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "UnavailableDaysError",
    "Universe",
```
with:
```python
    "UnavailableDaysError",
    "UnitValue",
    "Universe",
```

**`packages/steadyhand/src/steadyhand/risk.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/risk.py -->
```python
"""Risk controls: what may be ordered, and when all ordering stops (core spec §6.1, M3 §6.3).

Losses are read from a fund-style unit value, not the portfolio's value, so a top-up never
looks like a gain and never hides a loss: a deposit buys units at today's price per unit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView, Tradable


def _percent(rate: Decimal) -> str:
    raise NotImplementedError("_percent")


def _rate(value: object, name: str) -> None:
    raise NotImplementedError("_rate")


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Every limit the risk manager applies. The defaults are core spec §6.1's."""

    max_weight: Decimal = Decimal("0.10")
    """The most one stock may be of the portfolio's value. A buy is cut to it."""
    min_lots: int = 1
    """The smallest buy, in lots. A smaller buy is dropped."""
    daily_loss: Decimal = Decimal("0.05")
    """A fall in the unit value this large in one day halts ordering."""
    max_drawdown: Decimal = Decimal("0.25")
    """A fall this far below the unit value's high-water mark halts ordering."""

    def __post_init__(self) -> None:
        raise NotImplementedError("RiskLimits.__post_init__")


@dataclass(frozen=True, slots=True)
class Halt:
    """Ordering stopped on ``day``, for ``cause``. In a backtest it lasts to the end of the run."""

    day: date
    cause: str

    def __post_init__(self) -> None:
        raise NotImplementedError("Halt.__post_init__")


@dataclass(frozen=True, slots=True)
class UnitValue:
    """The portfolio as a fund: ``units`` outstanding, each worth ``price`` at the last valuation.

    Before the first deposit there are no units and the price is 1.
    """

    units: Decimal = Decimal(0)
    price: Decimal = Decimal(1)
    high_water: Decimal = Decimal(1)

    def __post_init__(self) -> None:
        raise NotImplementedError("UnitValue.__post_init__")

    def revalue(self, value: Money) -> UnitValue:
        """The price per unit when the portfolio is worth *value*. Nothing changes before units."""
        raise NotImplementedError("UnitValue.revalue")

    def deposit(self, amount: Money) -> UnitValue:
        """Buy units with *amount* at the current price, which the deposit leaves unchanged."""
        raise NotImplementedError("UnitValue.deposit")


@dataclass(frozen=True, slots=True)
class Checked:
    """Orders the risk manager passed, and those it dropped or cut, each with its reason."""

    orders: tuple[Order, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]


class RiskManager:
    """Applies ``RiskLimits`` to sized orders, and decides when to halt."""

    def __init__(self, rules: MarketRules, limits: RiskLimits | None = None) -> None:
        raise NotImplementedError("RiskManager.__init__")

    @property
    def limits(self) -> RiskLimits:
        raise NotImplementedError("RiskManager.limits")

    def check(
        self,
        orders: Sequence[Order],
        portfolio: PortfolioView,
        tradable: Tradable,
        prices: Mapping[Instrument, Money],
    ) -> Checked:
        """Drop or cut *orders* placed on the tradable set's day, in the order given.

        Buys are sized at the last close in *prices*, costs included, and together never spend
        more than ``portfolio.spendable``. Sale proceeds are not counted: they are not settled.
        """
        raise NotImplementedError("RiskManager.check")

    def halt(self, before: UnitValue, after: UnitValue, day: date) -> Halt | None:
        """A halt when today's unit value breaches a limit, reaching it included; else ``None``."""
        raise NotImplementedError("RiskManager.halt")

    def _affordable(
        self, instrument: Instrument, quantity: int, price: Money, budget: Money, day: date
    ) -> int:
        raise NotImplementedError("RiskManager._affordable")

    def _cost(self, quantity: int, price: Money, day: date) -> Money:
        raise NotImplementedError("RiskManager._cost")
```

**`packages/steadyhand/src/steadyhand/sizing.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/sizing.py -->
```python
"""Sizing: turning target weights into orders of whole lots (core spec §6.2, M3 spec §6.2).

The sizer only does the arithmetic. Every limit that can drop or cut an order, cash included,
is the risk manager's, so each carries a reason in one place.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView


@runtime_checkable
class Sizer(Protocol):
    """Turns a strategy's target weights into orders."""

    def size(
        self,
        weights: Mapping[Instrument, Decimal],
        portfolio: PortfolioView,
        held: Mapping[Instrument, int],
        prices: Mapping[Instrument, Money],
        day: date,
    ) -> tuple[Order, ...]:
        """Orders placed on *day*: every sell first, then every buy, each by market and symbol.

        *held* is the shares of each holding and *prices* the last close of every stock that
        is weighted or held. A stock missing from *weights* is targeted at zero.
        """
        ...


class CompoundingSizer:
    """Sizes from the portfolio's current value, so gains and dividends grow later orders.

    Each stock's target is its weight times the value (all cash plus holdings at the last
    close). The difference from what is held becomes whole lots at the last close, always
    rounded towards zero, so a target within a lot of the holding places no order.
    """

    def __init__(self, rules: MarketRules) -> None:
        raise NotImplementedError("CompoundingSizer.__init__")

    def size(
        self,
        weights: Mapping[Instrument, Decimal],
        portfolio: PortfolioView,
        held: Mapping[Instrument, int],
        prices: Mapping[Instrument, Money],
        day: date,
    ) -> tuple[Order, ...]:
        raise NotImplementedError("CompoundingSizer.size")


def _by_symbol(instrument: Instrument) -> tuple[str, str]:
    raise NotImplementedError("_by_symbol")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=652 failed=32 -->
Expected: 652 run (the 4 `live` tests deselected), 32 failed. Every one fails on `NotImplementedError`; no new test passes against the stubs.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/risk.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/risk.py -->
```python
"""Risk controls: what may be ordered, and when all ordering stops (core spec §6.1, M3 §6.3).

Losses are read from a fund-style unit value, not the portfolio's value, so a top-up never
looks like a gain and never hides a loss: a deposit buys units at today's price per unit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from steadyhand._ratio import ratio_down
from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.outcomes import Cut, Rejected
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView, Tradable


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)}%"


def _rate(value: object, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        msg = f"{name} must be a finite Decimal, got {value!r}"
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Every limit the risk manager applies. The defaults are core spec §6.1's."""

    max_weight: Decimal = Decimal("0.10")
    """The most one stock may be of the portfolio's value. A buy is cut to it."""
    min_lots: int = 1
    """The smallest buy, in lots. A smaller buy is dropped."""
    daily_loss: Decimal = Decimal("0.05")
    """A fall in the unit value this large in one day halts ordering."""
    max_drawdown: Decimal = Decimal("0.25")
    """A fall this far below the unit value's high-water mark halts ordering."""

    def __post_init__(self) -> None:
        for name in ("max_weight", "daily_loss", "max_drawdown"):
            _rate(getattr(self, name), name)
        require_int(self.min_lots, "min_lots", minimum=1)
        if not 0 < self.max_weight <= 1:
            msg = f"max_weight must be above 0 and at most 1, got {self.max_weight}"
            raise ValueError(msg)
        for name in ("daily_loss", "max_drawdown"):
            if not 0 < getattr(self, name) < 1:
                msg = f"{name} must be above 0 and below 1, got {getattr(self, name)}"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class UnitValue:
    """The portfolio as a fund: ``units`` outstanding, each worth ``price`` at the last valuation.

    Before the first deposit there are no units and the price is 1.
    """

    units: Decimal = Decimal(0)
    price: Decimal = Decimal(1)
    high_water: Decimal = Decimal(1)

    def __post_init__(self) -> None:
        for name in ("units", "price", "high_water"):
            _rate(getattr(self, name), name)
            if getattr(self, name) < 0:
                msg = f"{name} cannot be negative, got {getattr(self, name)}"
                raise ValueError(msg)

    def revalue(self, value: Money) -> UnitValue:
        """The price per unit when the portfolio is worth *value*. Nothing changes before units."""
        if self.units == 0:
            return self
        price = ratio_down(value.amount, self.units)
        return UnitValue(self.units, price, max(self.high_water, price))

    def deposit(self, amount: Money) -> UnitValue:
        """Buy units with *amount* at the current price, which the deposit leaves unchanged."""
        if self.price == 0:
            msg = "no units can be bought at a price of 0"
            raise ValueError(msg)
        return UnitValue(
            self.units + ratio_down(amount.amount, self.price), self.price, self.high_water
        )


@dataclass(frozen=True, slots=True)
class Checked:
    """Orders the risk manager passed, and those it dropped or cut, each with its reason."""

    orders: tuple[Order, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]


class RiskManager:
    """Applies ``RiskLimits`` to sized orders, and decides when to halt."""

    def __init__(self, rules: MarketRules, limits: RiskLimits | None = None) -> None:
        self._rules = rules
        self._limits = RiskLimits() if limits is None else limits

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def check(
        self,
        orders: Sequence[Order],
        portfolio: PortfolioView,
        tradable: Tradable,
        prices: Mapping[Instrument, Money],
    ) -> Checked:
        """Drop or cut *orders* placed on the tradable set's day, in the order given.

        Buys are sized at the last close in *prices*, costs included, and together never spend
        more than ``portfolio.spendable``. Sale proceeds are not counted: they are not settled.
        """
        day = tradable.day
        passed: list[Order] = []
        rejected: list[Rejected] = []
        cuts: list[Cut] = []
        budget = portfolio.spendable
        cap = portfolio.value.times(self._limits.max_weight, Rounding.DOWN)
        for order in orders:
            reason = tradable.why_not(order.instrument, order.side)
            if reason is not None:
                rejected.append(Rejected(order, reason))
                continue
            if order.side is Side.SELL:
                passed.append(order)
                continue
            lot = self._rules.lot_size(order.instrument, day)
            price = prices[order.instrument]
            held = portfolio.holdings.get(order.instrument, Money.zero(price.currency))
            room = (cap - held).amount // (price * lot).amount * lot
            quantity = min(order.quantity, max(room, 0))
            if quantity < order.quantity:
                limit = _percent(self._limits.max_weight)
                if quantity == 0:
                    rejected.append(Rejected(order, f"already at the {limit} limit per stock"))
                    continue
                cuts.append(Cut(order, quantity, f"cut to the {limit} limit per stock"))
            smallest = self._limits.min_lots * lot
            if quantity < smallest:
                reason = f"below the minimum buy of {self._limits.min_lots} lot(s)"
                rejected.append(Rejected(order, reason))
                continue
            affordable = self._affordable(order.instrument, quantity, price, budget, day)
            if affordable == 0:
                rejected.append(Rejected(order, f"not enough cash: {budget} can be spent"))
                continue
            if affordable < quantity:
                cuts.append(Cut(order, affordable, f"cut to the {budget} that can be spent"))
            budget -= self._cost(affordable, price, day)
            passed.append(Order(order.instrument, order.side, affordable, order.placed_on))
        return Checked(tuple(passed), tuple(rejected), tuple(cuts))

    def halt(self, before: UnitValue, after: UnitValue, day: date) -> Halt | None:
        """A halt when today's unit value breaches a limit, reaching it included; else ``None``."""
        if before.units > 0:
            fall = 1 - ratio_down(after.price, before.price)
            if fall >= self._limits.daily_loss:
                limit = _percent(self._limits.daily_loss)
                cause = (
                    f"daily loss limit: the unit value fell {_percent(fall)}, the limit is {limit}"
                )
                return Halt(day, cause)
        drawdown = 1 - ratio_down(after.price, after.high_water)
        if after.units > 0 and drawdown >= self._limits.max_drawdown:
            limit = _percent(self._limits.max_drawdown)
            cause = (
                f"drawdown kill switch: the unit value is {_percent(drawdown)} below its "
                f"high-water mark, the limit is {limit}"
            )
            return Halt(day, cause)
        return None

    def _affordable(
        self, instrument: Instrument, quantity: int, price: Money, budget: Money, day: date
    ) -> int:
        lot = self._rules.lot_size(instrument, day)
        quantity = min(quantity, max(budget.amount, 0) // (price * lot).amount * lot)
        while quantity > 0 and self._cost(quantity, price, day) > budget:
            quantity -= lot
        return quantity

    def _cost(self, quantity: int, price: Money, day: date) -> Money:
        gross = price * quantity
        return gross + self._rules.costs(Side.BUY, gross, day).total
```

**`packages/steadyhand/src/steadyhand/sizing.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/sizing.py -->
```python
"""Sizing: turning target weights into orders of whole lots (core spec §6.2, M3 spec §6.2).

The sizer only does the arithmetic. Every limit that can drop or cut an order, cash included,
is the risk manager's, so each carries a reason in one place.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from steadyhand.market import MarketRules
from steadyhand.money import Money, Rounding
from steadyhand.types import Instrument, Order, Side
from steadyhand.view import PortfolioView


@runtime_checkable
class Sizer(Protocol):
    """Turns a strategy's target weights into orders."""

    def size(
        self,
        weights: Mapping[Instrument, Decimal],
        portfolio: PortfolioView,
        held: Mapping[Instrument, int],
        prices: Mapping[Instrument, Money],
        day: date,
    ) -> tuple[Order, ...]:
        """Orders placed on *day*: every sell first, then every buy, each by market and symbol.

        *held* is the shares of each holding and *prices* the last close of every stock that
        is weighted or held. A stock missing from *weights* is targeted at zero.
        """
        ...


class CompoundingSizer:
    """Sizes from the portfolio's current value, so gains and dividends grow later orders.

    Each stock's target is its weight times the value (all cash plus holdings at the last
    close). The difference from what is held becomes whole lots at the last close, always
    rounded towards zero, so a target within a lot of the holding places no order.
    """

    def __init__(self, rules: MarketRules) -> None:
        self._rules = rules

    def size(
        self,
        weights: Mapping[Instrument, Decimal],
        portfolio: PortfolioView,
        held: Mapping[Instrument, int],
        prices: Mapping[Instrument, Money],
        day: date,
    ) -> tuple[Order, ...]:
        sells: list[Order] = []
        buys: list[Order] = []
        for instrument in sorted(set(weights) | set(held), key=_by_symbol):
            price = prices.get(instrument)
            if price is None:
                msg = f"no price for {instrument.symbol} on {day.isoformat()} to size it with"
                raise LookupError(msg)
            weight = weights.get(instrument, Decimal(0))
            target = portfolio.value.times(weight, Rounding.DOWN)
            current = portfolio.holdings.get(instrument, Money.zero(portfolio.value.currency))
            lot = self._rules.lot_size(instrument, day)
            lots = abs((target - current).amount) // (price * lot).amount
            if target < current:
                quantity = min(lots * lot, held.get(instrument, 0) // lot * lot)
                if quantity:
                    sells.append(Order(instrument, Side.SELL, quantity, day))
            elif lots:
                buys.append(Order(instrument, Side.BUY, lots * lot, day))
        return (*sells, *buys)


def _by_symbol(instrument: Instrument) -> tuple[str, str]:
    return (instrument.market, instrument.symbol)
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=652 passed=652 -->
Expected: every command exits 0; 652 passed, 4 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M20–M24; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S4 …`).

---

### Task 5: S5 Corporate actions

**Acceptance criteria (story text):**
1. `apply_actions(holdings, actions, day, rules, pay_lag_trading_days=14)` refuses an action not dated `day` and a lag below 1, and applies, in order: splits, dividend entitlements, payments due, then other actions (M3 §4).
2. A split scales the holding (`Portfolio.apply_split`), scales the stored last close by old ÷ new shares rounded down, cancels every pending order for the stock with the reason "split on ex-date", and warns, naming both share counts, when a fraction of a share is dropped.
3. A cash dividend entitles the shares held at the previous close (before today's splits and fills) to their quantity × the amount per share, rounded down to a whole rupiah; nothing below a rupiah. The pay date is the ex-date plus 14 IDX trading days (`PAY_LAG_TRADING_DAYS`).
4. On or after its pay date an entitlement is credited as a dividend and `rules.dividend_tax(gross, reinvested_by_deadline=False, on=day)` is booked as tax when it is above zero, even if the stock has been sold.
5. An other action on a held stock freezes it with the action's description, once; one on a stock not held changes nothing.
6. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M25–M28 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/corporate.py`
- Modify: `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_corporate.py`

**Interfaces:**
- Consumes: `Portfolio.apply_split`, `.credit_dividend`, `.charge`, `MovementKind.TAX` (Task 1); `Rejected` (Task 3); `MarketRules.is_trading_day`, `.dividend_tax` (M2).
- Produces: `PAY_LAG_TRADING_DAYS = 14`; `Entitlement(instrument, ex_date, pay_date, gross)`; `Holdings(portfolio: Portfolio, pending: tuple[Order, ...] = (), entitlements: tuple[Entitlement, ...] = (), frozen: Mapping[Instrument, str] = {}, last_closes: Mapping[Instrument, Money] = {})`; `CorporateOutcome(holdings, cancelled, entitled, paid, tax, frozen, warnings)`; `apply_actions(holdings, actions: Sequence[CorporateAction], day, rules, pay_lag_trading_days: int = 14) -> CorporateOutcome`.

- [ ] **Step 1: Branch.** `git switch -c m3/s5-corporate origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_corporate.py`** (new)

<!-- file: tests/engine/test_corporate.py -->
```python
"""Corporate actions: splits, dividend entitlements and payments, freezes (M3 spec §4)."""

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.portfolio import MovementKind, Portfolio
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

EX = date(2025, 6, 2)
PAY = date(2025, 6, 24)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


class _TaxFree(IdxMarketRules):
    """IDX, but in a market that taxes no dividend."""

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        return Money.zero(gross.currency)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def holding(**shares: int) -> Portfolio:
    """A portfolio holding the given shares of BBCA and BBRI, bought before the ex-date."""
    book = Portfolio.empty(IDR)
    for symbol, quantity in shares.items():
        stock = Instrument(symbol, "IDX", IDR)
        order = Order(stock, Side.BUY, quantity, date(2025, 5, 28))
        fill = Fill(order, date(2025, 5, 28), quantity, rp(1_000), Costs.zero(IDR))
        book = book.deposit(rp(quantity * 1_000), date(2025, 5, 28)).apply_fill(fill, EX)
    return book


def shares(portfolio: Portfolio, stock: Instrument) -> int:
    position = portfolio.position(stock)
    return 0 if position is None else position.quantity


def test_the_pay_lag_is_the_specs() -> None:
    assert PAY_LAG_TRADING_DAYS == 14


def test_a_split_scales_the_holding_and_the_last_close_and_cancels_its_orders() -> None:
    pending = (
        Order(BBCA, Side.SELL, 100, date(2025, 5, 30)),
        Order(BBRI, Side.BUY, 100, date(2025, 5, 30)),
    )
    before = Holdings(holding(BBCA=300), pending, last_closes={BBCA: rp(9_001)})
    outcome = apply_actions(before, [Split(BBCA, EX, 1, 5)], EX, rules())
    assert shares(outcome.holdings.portfolio, BBCA) == 1_500
    assert outcome.holdings.last_closes == {BBCA: rp(1_800)}
    assert outcome.holdings.pending == (pending[1],)
    assert [(r.order, r.reason) for r in outcome.cancelled] == [(pending[0], "split on ex-date")]
    assert outcome.warnings == ()


def test_a_split_of_a_stock_not_held_still_cancels_its_orders() -> None:
    pending = (Order(BBCA, Side.BUY, 100, date(2025, 5, 30)),)
    outcome = apply_actions(Holdings(holding(), pending), [Split(BBCA, EX, 1, 2)], EX, rules())
    assert outcome.holdings.pending == ()
    assert outcome.holdings.last_closes == {}


def test_a_reverse_split_warns_about_the_dropped_fraction() -> None:
    outcome = apply_actions(Holdings(holding(BBCA=1_203)), [Split(BBCA, EX, 5, 1)], EX, rules())
    assert shares(outcome.holdings.portfolio, BBCA) == 240
    assert outcome.warnings == (
        (
            "BBCA: the 1-for-5 split on 2025-06-02 turned 1203 shares into 240; the fraction of "
            "a share left over is dropped (cash in lieu is not modelled)"
        ),
    )


def test_a_split_that_leaves_no_whole_share_warns_with_zero() -> None:
    outcome = apply_actions(Holdings(holding(BBCA=4)), [Split(BBCA, EX, 5, 1)], EX, rules())
    assert outcome.holdings.portfolio.positions == ()
    assert "turned 4 shares into 0" in outcome.warnings[0]


def test_a_dividend_entitles_what_was_held_at_the_previous_close() -> None:
    dividend = CashDividend(BBCA, EX, Decimal("12.5"))
    outcome = apply_actions(Holdings(holding(BBCA=333, BBRI=100)), [dividend], EX, rules())
    assert outcome.entitled == (Entitlement(BBCA, EX, PAY, rp(4_162)),)
    assert outcome.holdings.entitlements == outcome.entitled
    assert outcome.paid == ()


def test_a_dividend_on_a_stock_not_held_entitles_nothing() -> None:
    outcome = apply_actions(
        Holdings(holding(BBRI=100)), [CashDividend(BBCA, EX, Decimal(50))], EX, rules()
    )
    assert outcome.entitled == ()


def test_a_dividend_worth_less_than_a_rupiah_entitles_nothing() -> None:
    outcome = apply_actions(
        Holdings(holding(BBCA=1)), [CashDividend(BBCA, EX, Decimal("0.5"))], EX, rules()
    )
    assert outcome.entitled == ()


def test_a_same_day_split_and_dividend_pays_on_the_shares_before_the_split() -> None:
    actions: list[CorporateAction] = [CashDividend(BBCA, EX, Decimal(10)), Split(BBCA, EX, 1, 5)]
    outcome = apply_actions(Holdings(holding(BBCA=100)), actions, EX, rules())
    assert [e.gross for e in outcome.entitled] == [rp(1_000)]
    assert shares(outcome.holdings.portfolio, BBCA) == 500


def test_an_entitlement_is_paid_and_taxed_on_its_pay_date_even_after_a_sale() -> None:
    due = Entitlement(BBCA, EX, PAY, rp(12_500))
    later = Entitlement(BBRI, EX, date(2025, 6, 25), rp(7_000))
    outcome = apply_actions(Holdings(holding(), entitlements=(due, later)), [], PAY, rules())
    assert outcome.paid == (due,)
    assert outcome.holdings.entitlements == (later,)
    assert outcome.tax == rp(1_250)
    kinds = [(m.kind, m.amount, m.settles_on) for m in outcome.holdings.portfolio.ledger]
    assert kinds == [(MovementKind.DIVIDEND, rp(12_500), PAY), (MovementKind.TAX, rp(-1_250), PAY)]


def test_an_untaxed_dividend_books_no_tax() -> None:
    due = Entitlement(BBCA, EX, PAY, rp(12_500))
    outcome = apply_actions(Holdings(holding(), entitlements=(due,)), [], PAY, _TaxFree())
    assert outcome.tax == rp(0)
    assert [m.kind for m in outcome.holdings.portfolio.ledger] == [MovementKind.DIVIDEND]


def test_another_action_freezes_a_held_stock_once() -> None:
    rights = OtherAction(BBCA, EX, "rights issue")
    outcome = apply_actions(
        Holdings(holding(BBCA=100)), [rights, OtherAction(BBRI, EX, "merger")], EX, rules()
    )
    assert outcome.holdings.frozen == {BBCA: "rights issue"}
    assert outcome.frozen == ((BBCA, "rights issue"),)
    again = apply_actions(
        outcome.holdings, [OtherAction(BBCA, date(2025, 6, 3), "second")], date(2025, 6, 3), rules()
    )
    assert again.holdings.frozen == {BBCA: "rights issue"}
    assert again.frozen == ()


def test_actions_must_be_dated_today_and_the_lag_positive() -> None:
    with pytest.raises(
        ValueError, match=r"^BBCA: an action dated 2025-06-03 applied on 2025-06-02$"
    ):
        apply_actions(Holdings(holding()), [Split(BBCA, date(2025, 6, 3), 1, 2)], EX, rules())
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        apply_actions(Holdings(holding()), [], EX, rules(), 0)


def test_an_entitlement_must_be_a_positive_amount_paid_after_its_ex_date() -> None:
    with pytest.raises(ValueError, match=r"^BBCA: paid 2025-06-02, not after its ex-date$"):
        Entitlement(BBCA, EX, EX, rp(1))
    with pytest.raises(ValueError, match=r"^BBCA: an entitlement must be positive, got IDR 0$"):
        Entitlement(BBCA, EX, PAY, rp(0))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        Entitlement(BBCA, EX, PAY, Money(1, Currency("USD", 2)))


def test_holdings_check_their_parts() -> None:
    with pytest.raises(TypeError, match=r"^portfolio must be a Portfolio, got NoneType$"):
        Holdings(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^pending order must be an Order, got str$"):
        Holdings(holding(), ("BBCA",))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^entitlement must be an Entitlement, got str$"):
        Holdings(holding(), entitlements=("BBCA",))  # type: ignore[arg-type]
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 6 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
from steadyhand.broker import Broker, FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
```
with:
```python
from steadyhand.broker import Broker, FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import (
    PAY_LAG_TRADING_DAYS,
    CorporateOutcome,
    Entitlement,
    Holdings,
    apply_actions,
)
from steadyhand.data import DataSource, DataUnavailableError, UnavailableDaysError
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "MAX_MINOR_UNITS",
    "STRATEGIES",
```
with:
```python
    "MAX_MINOR_UNITS",
    "PAY_LAG_TRADING_DAYS",
    "STRATEGIES",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "CorporateAction",
    "Costs",
```
with:
```python
    "CorporateAction",
    "CorporateOutcome",
    "Costs",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Decision",
    "Fill",
```
with:
```python
    "Decision",
    "Entitlement",
    "Fill",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "Halt",
    "Instrument",
```
with:
```python
    "Halt",
    "Holdings",
    "Instrument",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "__version__",
]
```
with:
```python
    "__version__",
    "apply_actions",
]
```

**`packages/steadyhand/src/steadyhand/corporate.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/corporate.py -->
```python
"""Corporate actions on their ex-date, before anything fills (core spec §5 step 2, M3 spec §4).

In order: splits change the share count, cash dividends create entitlements for what was held
at the previous close, entitlements due today are paid (and taxed), and any other action on a
held stock freezes it for the rest of the run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules
from steadyhand.money import CurrencyMismatchError, Money, Rounding
from steadyhand.outcomes import Rejected
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Order, OtherAction, Split

PAY_LAG_TRADING_DAYS = 14
"""Trading days from ex-date to the modelled pay date: the 90th percentile of 47 KSEI-scheduled
dividends in 2025-2026 (core spec §5 step 2, docs/research/t-pay.md §4)."""


@dataclass(frozen=True, slots=True)
class Entitlement:
    """A cash dividend earned on ``ex_date`` by the shares then held, paid on ``pay_date``."""

    instrument: Instrument
    ex_date: date
    pay_date: date
    gross: Money

    def __post_init__(self) -> None:
        raise NotImplementedError("Entitlement.__post_init__")


@dataclass(frozen=True, slots=True)
class Holdings:
    """The portfolio and what the engine keeps about its stocks from one day to the next.

    ``pending`` holds the orders queued for the next open, ``frozen`` each frozen stock with
    its reason, and ``last_closes`` the last close of each held stock, which values it on a
    day with no bar.
    """

    portfolio: Portfolio
    pending: tuple[Order, ...] = ()
    entitlements: tuple[Entitlement, ...] = ()
    frozen: Mapping[Instrument, str] = field(default_factory=dict)
    last_closes: Mapping[Instrument, Money] = field(default_factory=dict)

    def __post_init__(self) -> None:
        raise NotImplementedError("Holdings.__post_init__")


@dataclass(frozen=True, slots=True)
class CorporateOutcome:
    """The holdings after today's actions, and what the day's report says about them."""

    holdings: Holdings
    cancelled: tuple[Rejected, ...]
    entitled: tuple[Entitlement, ...]
    paid: tuple[Entitlement, ...]
    tax: Money
    frozen: tuple[tuple[Instrument, str], ...]
    warnings: tuple[str, ...]


def apply_actions(
    holdings: Holdings,
    actions: Sequence[CorporateAction],
    day: date,
    rules: MarketRules,
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS,
) -> CorporateOutcome:
    """Apply *actions*, every one of them with its ex-date on *day*, to *holdings*."""
    raise NotImplementedError("apply_actions")


class _Actions:
    """One day's actions in progress. Dividends are earned on the shares held at the previous
    close, which is ``holdings.portfolio`` as it came in, before today's splits."""

    def __init__(self, holdings: Holdings, day: date) -> None:
        raise NotImplementedError("_Actions.__init__")

    def split(self, split: Split) -> None:
        raise NotImplementedError("_Actions.split")

    def entitle(self, dividend: CashDividend, pay_date: date) -> None:
        raise NotImplementedError("_Actions.entitle")

    def pay(self, rules: MarketRules) -> None:
        raise NotImplementedError("_Actions.pay")

    def freeze(self, action: OtherAction) -> None:
        raise NotImplementedError("_Actions.freeze")

    def outcome(self) -> CorporateOutcome:
        raise NotImplementedError("_Actions.outcome")


def _add_trading_days(rules: MarketRules, day: date, count: int) -> date:
    raise NotImplementedError("_add_trading_days")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=667 failed=14 -->
Expected: 667 run (the 4 `live` tests deselected), 14 failed. Every one fails on `NotImplementedError`. One new test passes against the stubs: `test_the_pay_lag_is_the_specs` pins a constant, which has no body to stub.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/corporate.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/corporate.py -->
```python
"""Corporate actions on their ex-date, before anything fills (core spec §5 step 2, M3 spec §4).

In order: splits change the share count, cash dividends create entitlements for what was held
at the previous close, entitlements due today are paid (and taxed), and any other action on a
held stock freezes it for the rest of the run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.market import MarketRules
from steadyhand.money import CurrencyMismatchError, Money, Rounding
from steadyhand.outcomes import Rejected
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import CashDividend, CorporateAction, Instrument, Order, OtherAction, Split

PAY_LAG_TRADING_DAYS = 14
"""Trading days from ex-date to the modelled pay date: the 90th percentile of 47 KSEI-scheduled
dividends in 2025-2026 (core spec §5 step 2, docs/research/t-pay.md §4)."""


@dataclass(frozen=True, slots=True)
class Entitlement:
    """A cash dividend earned on ``ex_date`` by the shares then held, paid on ``pay_date``."""

    instrument: Instrument
    ex_date: date
    pay_date: date
    gross: Money

    def __post_init__(self) -> None:
        require_type(self.instrument, Instrument, "instrument")
        require_date(self.ex_date, "ex_date")
        require_date(self.pay_date, "pay_date")
        require_type(self.gross, Money, "gross")
        if self.pay_date <= self.ex_date:
            msg = f"{self.instrument.symbol}: paid {self.pay_date}, not after its ex-date"
            raise ValueError(msg)
        if self.gross.currency != self.instrument.currency:
            raise CurrencyMismatchError(self.instrument.currency, self.gross.currency)
        if self.gross.amount <= 0:
            msg = f"{self.instrument.symbol}: an entitlement must be positive, got {self.gross}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Holdings:
    """The portfolio and what the engine keeps about its stocks from one day to the next.

    ``pending`` holds the orders queued for the next open, ``frozen`` each frozen stock with
    its reason, and ``last_closes`` the last close of each held stock, which values it on a
    day with no bar.
    """

    portfolio: Portfolio
    pending: tuple[Order, ...] = ()
    entitlements: tuple[Entitlement, ...] = ()
    frozen: Mapping[Instrument, str] = field(default_factory=dict)
    last_closes: Mapping[Instrument, Money] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_type(self.portfolio, Portfolio, "portfolio")
        for order in self.pending:
            require_type(order, Order, "pending order")
        for entitlement in self.entitlements:
            require_type(entitlement, Entitlement, "entitlement")


@dataclass(frozen=True, slots=True)
class CorporateOutcome:
    """The holdings after today's actions, and what the day's report says about them."""

    holdings: Holdings
    cancelled: tuple[Rejected, ...]
    entitled: tuple[Entitlement, ...]
    paid: tuple[Entitlement, ...]
    tax: Money
    frozen: tuple[tuple[Instrument, str], ...]
    warnings: tuple[str, ...]


def apply_actions(
    holdings: Holdings,
    actions: Sequence[CorporateAction],
    day: date,
    rules: MarketRules,
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS,
) -> CorporateOutcome:
    """Apply *actions*, every one of them with its ex-date on *day*, to *holdings*."""
    require_int(pay_lag_trading_days, "pay_lag_trading_days", minimum=1)
    for action in actions:
        if action.ex_date != day:
            msg = f"{action.instrument.symbol}: an action dated {action.ex_date} applied on {day}"
            raise ValueError(msg)
    run = _Actions(holdings, day)
    for action in actions:
        if isinstance(action, Split):
            run.split(action)
    for action in actions:
        if isinstance(action, CashDividend):
            run.entitle(action, _add_trading_days(rules, day, pay_lag_trading_days))
    run.pay(rules)
    for action in actions:
        if isinstance(action, OtherAction):
            run.freeze(action)
    return run.outcome()


class _Actions:
    """One day's actions in progress. Dividends are earned on the shares held at the previous
    close, which is ``holdings.portfolio`` as it came in, before today's splits."""

    def __init__(self, holdings: Holdings, day: date) -> None:
        self._before = holdings.portfolio
        self._portfolio = holdings.portfolio
        self._day = day
        self._pending = list(holdings.pending)
        self._entitlements = list(holdings.entitlements)
        self._frozen = dict(holdings.frozen)
        self._closes = dict(holdings.last_closes)
        self._cancelled: list[Rejected] = []
        self._entitled: list[Entitlement] = []
        self._paid: list[Entitlement] = []
        self._tax = Money.zero(holdings.portfolio.currency)
        self._newly_frozen: list[tuple[Instrument, str]] = []
        self._warnings: list[str] = []

    def split(self, split: Split) -> None:
        stock = split.instrument
        held = self._portfolio.position(stock)
        if held is not None:
            self._portfolio = self._portfolio.apply_split(split)
            if held.quantity * split.new_shares % split.old_shares:
                after = self._portfolio.position(stock)
                kept = 0 if after is None else after.quantity
                self._warnings.append(
                    f"{stock.symbol}: the {split.new_shares}-for-{split.old_shares} split on "
                    f"{self._day.isoformat()} turned {held.quantity} shares into {kept}; the "
                    "fraction of a share left over is dropped (cash in lieu is not modelled)"
                )
        close = self._closes.get(stock)
        if close is not None:
            scaled = close.amount * split.old_shares // split.new_shares
            self._closes[stock] = Money(scaled, close.currency)
        for order in [order for order in self._pending if order.instrument == stock]:
            self._pending.remove(order)
            self._cancelled.append(Rejected(order, "split on ex-date"))

    def entitle(self, dividend: CashDividend, pay_date: date) -> None:
        held = self._before.position(dividend.instrument)
        if held is None:
            return
        unit = Money(10**self._before.currency.minor_units, self._before.currency)
        gross = unit.times(dividend.per_share * held.quantity, Rounding.DOWN)
        if gross.amount > 0:
            entitlement = Entitlement(dividend.instrument, self._day, pay_date, gross)
            self._entitlements.append(entitlement)
            self._entitled.append(entitlement)

    def pay(self, rules: MarketRules) -> None:
        for entitlement in [e for e in self._entitlements if e.pay_date <= self._day]:
            self._entitlements.remove(entitlement)
            self._portfolio = self._portfolio.credit_dividend(entitlement.gross, self._day)
            tax = rules.dividend_tax(entitlement.gross, reinvested_by_deadline=False, on=self._day)
            if tax.amount > 0:
                self._portfolio = self._portfolio.charge(MovementKind.TAX, tax, self._day)
                self._tax += tax
            self._paid.append(entitlement)

    def freeze(self, action: OtherAction) -> None:
        stock = action.instrument
        if self._portfolio.position(stock) is not None and stock not in self._frozen:
            self._frozen[stock] = action.description
            self._newly_frozen.append((stock, action.description))

    def outcome(self) -> CorporateOutcome:
        holdings = Holdings(
            self._portfolio,
            tuple(self._pending),
            tuple(self._entitlements),
            self._frozen,
            self._closes,
        )
        return CorporateOutcome(
            holdings,
            tuple(self._cancelled),
            tuple(self._entitled),
            tuple(self._paid),
            self._tax,
            tuple(self._newly_frozen),
            tuple(self._warnings),
        )


def _add_trading_days(rules: MarketRules, day: date, count: int) -> date:
    current = day
    for _ in range(count):
        current += timedelta(days=1)
        while not rules.is_trading_day(current):
            current += timedelta(days=1)
    return current
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=667 passed=667 -->
Expected: every command exits 0; 667 passed, 4 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M25–M28; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S5 …`).

---

### Task 6: S6 run_day with validation

**Acceptance criteria (story text):**
1. `run_day(state, inputs, strategy, rules, settings)` returns a new `EngineState` and a `DayReport` and changes nothing in place; run twice from the same state, it gives the same result. A day not after the last one run, or not a trading day, raises `DayOrderError`.
2. Before anything trades, a close outside `rules.price_band(stock, previous close, day)` raises `DataValidationError` naming the stock, the day and the check. The check is skipped on a stock's first bar, on a stock in `inputs.resumed`, and on a split's ex-date (M3 §7.4).
3. In order: held stocks excluded today are frozen and reported; corporate actions apply; yesterday's orders fill; held stocks are valued at today's close, or their last close when they have no bar; the unit value is revalued and, unless a halt is already in force, checked for a halt; the monthly contribution is deposited on the month's first trading day; then, unless halted, the strategy decides through a `MarketView`, and its weights are sized and checked into tomorrow's orders.
4. The tradable set (M3 §6.4): buyable are members not excluded, frozen, refused or without a bar; sellable are held stocks not frozen, refused or without a bar. A member or held stock with no bar gets a warning, which for a held one names the close it is valued at. A held stock with no price at all stops the day with `MissingPriceError`.
5. After a halt no orders are queued and the strategy is not asked, for the rest of the run; holdings are kept and dividends still arrive (M3 decision 4).
6. `EngineState.opening(capital, day)` deposits the capital and buys units at 1. `EngineSettings` defaults to the core spec's values and refuses a non-positive contribution.
7. A hypothesis property over random four-day price paths with `buy-and-hold`: settled cash is never negative, the value is always cash plus holdings, every holding is whole lots, and the day's charge is booked at most once.
8. Every quality gate is green at 100% branch coverage, the red phase is recorded in the PR, and mutations M29–M33 each turn the whole suite red.

**Files:**
- Create: `packages/steadyhand/src/steadyhand/engine.py`
- Modify: `.../steadyhand/__init__.py`
- Test: create `tests/engine/test_engine.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `DataValidationError(instrument, day, check)`; `DayOrderError(ValueError)`; `EngineSettings(fills: FillSettings = FillSettings(), limits: RiskLimits = RiskLimits(), monthly_contribution: Money | None = None, pay_lag_trading_days: int = 14)`; `EngineState(holdings: Holdings, units: UnitValue = UnitValue(), halt: Halt | None = None, last_day: date | None = None, memory: Memory = {})` with `.opening(capital: Money, day: date)`; `DayInputs(day, history: PriceHistory, actions: tuple[CorporateAction, ...] = (), members: frozenset[Instrument] = frozenset(), excluded: Mapping[Instrument, str] = {}, refused: frozenset[Instrument] = frozenset(), resumed: frozenset[Instrument] = frozenset())`; `DayReport(day, fills, rejected, cuts, queued, entitled, paid, tax, daily_cost, deposit, frozen, halt, settled, unsettled, holdings_value, value, warnings)`; `run_day(state, inputs, strategy, rules, settings: EngineSettings | None = None) -> tuple[EngineState, DayReport]`.

- [ ] **Step 1: Branch.** `git switch -c m3/s6-run-day origin/develop`

- [ ] **Step 2: Write the failing tests.**

**`tests/engine/test_engine.py`** (new)

<!-- file: tests/engine/test_engine.py -->
```python
"""run_day: one pure trading day, from yesterday's state to today's (M3 spec §3, §4-§7.4)."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from steadyhand.corporate import Entitlement, Holdings
from steadyhand.engine import (
    DataValidationError,
    DayInputs,
    DayOrderError,
    DayReport,
    EngineSettings,
    EngineState,
    run_day,
)
from steadyhand.money import IDR, Money
from steadyhand.portfolio import MissingPriceError, MovementKind
from steadyhand.risk import Halt, RiskLimits
from steadyhand.strategies import BuyAndHold, Decision, Memory
from steadyhand.types import Bar, CashDividend, Instrument, Order, Side, Split
from steadyhand.view import MarketView, PortfolioView, PriceHistory
from steadyhand_idx import IdxMarketRules

D1, D2, D3, D4 = date(2025, 6, 2), date(2025, 6, 3), date(2025, 6, 4), date(2025, 6, 5)
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)
MEMBERS = frozenset({BBCA, BBRI})


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


@cache
def half() -> EngineSettings:
    """At most half the portfolio in one stock, so two stocks can be fully invested."""
    return EngineSettings(limits=RiskLimits(max_weight=Decimal("0.5")))


class _Fixed:
    """A strategy that always asks for the same weights."""

    def __init__(self, weights: Mapping[Instrument, Decimal]) -> None:
        self._weights = weights

    @property
    def name(self) -> str:
        return "fixed"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        return Decision(self._weights)


class _Untouchable:
    """A strategy that must not be asked: ordering has halted."""

    @property
    def name(self) -> str:
        return "untouchable"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        msg = "a halted run asked its strategy to decide"
        raise AssertionError(msg)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def bar(stock: Instrument, day: date, open_: int, close: int | None = None) -> Bar:
    shut = open_ if close is None else close
    return Bar(stock, day, rp(open_), rp(max(open_, shut)), rp(min(open_, shut)), rp(shut), 10**6)


def market(bbca: list[tuple[int, int]], bbri: list[tuple[int, int]]) -> PriceHistory:
    """Bars from D1 on, one (open, close) pair per day for each stock."""
    days = [D1, D2, D3, D4]
    return PriceHistory(
        [bar(BBCA, day, *pair) for day, pair in zip(days, bbca, strict=False)]
        + [bar(BBRI, day, *pair) for day, pair in zip(days, bbri, strict=False)]
    )


def steady() -> PriceHistory:
    return market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 9_100)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)],
    )


def day_one() -> tuple[EngineState, DayReport]:
    state = EngineState.opening(rp(10_000_000), D1)
    return run_day(state, DayInputs(D1, steady(), members=MEMBERS), BuyAndHold(), rules(), half())


def day_two() -> tuple[EngineState, DayReport]:
    state, _ = day_one()
    return run_day(state, DayInputs(D2, steady(), members=MEMBERS), BuyAndHold(), rules(), half())


def test_day_one_queues_buy_and_holds_orders_and_remembers_its_set() -> None:
    state, report = day_one()
    assert report.fills == ()
    assert report.queued == (Order(BBCA, Side.BUY, 500, D1), Order(BBRI, Side.BUY, 1_200, D1))
    assert (report.value, report.holdings_value, report.settled) == (
        rp(10_000_000),
        rp(0),
        rp(10_000_000),
    )
    assert state.holdings.pending == report.queued
    assert state.memory == {"set": "IDX:BBCA IDX:BBRI"}
    assert (state.last_day, state.halt) == (D1, None)
    assert state.units.price == 1


def test_orders_fill_at_the_next_open_and_the_day_is_valued_at_the_close() -> None:
    state, report = day_two()
    assert [(f.order.instrument, f.quantity, f.price) for f in report.fills] == [
        (BBCA, 500, rp(9_025)),
        (BBRI, 1_200, rp(4_010)),
    ]
    spent = sum((f.gross + f.costs.total for f in report.fills), rp(0))
    assert report.holdings_value == rp(500 * 9_100 + 1_200 * 4_050)
    assert report.value == rp(10_000_000) - spent + report.holdings_value
    assert report.settled == rp(10_000_000) - spent
    assert report.daily_cost == rp(0)
    assert state.holdings.last_closes == {BBCA: rp(9_100), BBRI: rp(4_050)}
    assert state.units.price == Decimal(report.value.amount) / Decimal(10_000_000)


def test_run_day_is_pure_and_repeatable() -> None:
    before, _ = day_one()
    snapshot = repr(before)
    inputs = DayInputs(D2, steady(), members=MEMBERS)
    first = run_day(before, inputs, BuyAndHold(), rules(), half())
    second = run_day(before, inputs, BuyAndHold(), rules(), half())
    assert repr(before) == snapshot
    assert first == second


def test_a_day_must_follow_the_last_and_be_a_trading_day() -> None:
    state, _ = day_one()
    with pytest.raises(
        DayOrderError, match=r"^2025-06-02 is not after the last day run, 2025-06-02$"
    ):
        run_day(state, DayInputs(D1, steady()), BuyAndHold(), rules())
    with pytest.raises(DayOrderError, match=r"^2025-06-06 is not a trading day$"):
        run_day(state, DayInputs(date(2025, 6, 6), steady()), BuyAndHold(), rules())


def test_a_close_outside_the_band_stops_the_day() -> None:
    history = market([(9_000, 9_000), (9_000, 7_625)], [])
    state = EngineState.opening(rp(1_000_000), D2)
    with pytest.raises(
        DataValidationError,
        match=(
            r"^BBCA on 2025-06-03: the close IDR 7,625 is outside the band IDR 7,650 to "
            r"IDR 10,800 around the previous close IDR 9,000$"
        ),
    ):
        run_day(state, DayInputs(D2, history), BuyAndHold(), rules())


@pytest.mark.parametrize(
    "exempt",
    [
        {"resumed": frozenset({BBCA})},
        {"actions": (Split(BBCA, D2, 1, 5),)},
    ],
    ids=["resumed after refused days", "split ex-date"],
)
def test_the_band_check_skips_resumed_stocks_and_split_ex_dates(exempt: dict[str, object]) -> None:
    history = market([(9_000, 9_000), (1_800, 1_800)], [])
    state = EngineState.opening(rp(1_000_000), D2)
    _, report = run_day(state, DayInputs(D2, history, **exempt), BuyAndHold(), rules())  # type: ignore[arg-type]
    assert report.day == D2


def test_a_stocks_first_bar_is_not_band_checked() -> None:
    history = PriceHistory([bar(BBCA, D2, 1_800)])
    _, report = run_day(
        EngineState.opening(rp(1_000_000), D2), DayInputs(D2, history), BuyAndHold(), rules()
    )
    assert report.value == rp(1_000_000)


def test_a_loss_at_the_limit_halts_ordering_for_the_rest_of_the_run() -> None:
    state, _ = day_two()
    crash = market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 7_900)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 3_450)],
    )
    state, report = run_day(
        state, DayInputs(D3, crash, members=MEMBERS), BuyAndHold(), rules(), half()
    )
    assert report.halt is not None
    assert report.halt.day == D3
    assert report.halt.cause.startswith("daily loss limit: the unit value fell ")
    assert (report.queued, state.holdings.pending) == ((), ())
    assert state.halt == report.halt
    later = market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 7_900), (7_900, 8_000)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 3_450), (3_450, 3_500)],
    )
    state, report = run_day(
        state, DayInputs(D4, later, members=MEMBERS), _Untouchable(), rules(), half()
    )
    assert (report.halt, report.queued) == (None, ())
    assert state.halt is not None
    assert state.halt.day == D3
    assert [p.quantity for p in state.holdings.portfolio.positions] == [500, 1_200]


def test_dividends_still_arrive_while_halted() -> None:
    state, _ = day_one()
    due = Entitlement(BBCA, D1, D2, rp(12_500))
    halted = EngineState(
        Holdings(state.holdings.portfolio, (), (due,)), state.units, Halt(D1, "test"), D1
    )
    after, report = run_day(
        halted, DayInputs(D2, steady(), members=MEMBERS), _Untouchable(), rules()
    )
    assert report.paid == (due,)
    assert (report.tax, report.fills, report.queued) == (rp(1_250), (), ())
    assert after.holdings.portfolio.cash_balance() == rp(10_000_000 + 12_500 - 1_250)


def test_a_stock_bought_at_todays_open_has_no_entitlement() -> None:
    state, _ = day_one()
    dividend = CashDividend(BBCA, D2, Decimal(100))
    inputs = DayInputs(D2, steady(), actions=(dividend,), members=MEMBERS)
    _, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    assert report.entitled == ()
    assert [f.order.instrument for f in report.fills] == [BBCA, BBRI]


def test_a_dividend_on_a_holding_is_entitled_on_its_ex_date() -> None:
    state, _ = day_two()
    inputs = DayInputs(
        D3, steady(), actions=(CashDividend(BBCA, D3, Decimal(100)),), members=MEMBERS
    )
    after, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    assert report.entitled == (Entitlement(BBCA, D3, date(2025, 6, 26), rp(50_000)),)
    assert after.holdings.entitlements == report.entitled


def test_a_split_cancels_pending_orders_and_rescales_the_last_close() -> None:
    state, _ = day_two()
    pending = Order(BBCA, Side.SELL, 100, D2)
    state = EngineState(
        Holdings(state.holdings.portfolio, (pending,), (), {}, state.holdings.last_closes),
        state.units,
        None,
        D2,
        state.memory,
    )
    history = market(
        [(9_000, 9_000), (9_000, 9_100)], [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)]
    )
    inputs = DayInputs(D3, history, actions=(Split(BBCA, D3, 1, 5),), members=MEMBERS)
    after, report = run_day(state, inputs, BuyAndHold(), rules(), half())
    assert (report.rejected[0].order, report.rejected[0].reason) == (pending, "split on ex-date")
    assert after.holdings.last_closes[BBCA] == rp(1_820)
    assert report.holdings_value == rp(2_500 * 1_820 + 1_200 * 4_050)


def test_a_held_stock_without_a_bar_is_valued_at_its_last_close_and_not_sold() -> None:
    state, _ = day_two()
    history = market(
        [(9_000, 9_000), (9_000, 9_100)], [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)]
    )
    seller = _Fixed({BBRI: Decimal("0.4")})
    _, report = run_day(state, DayInputs(D3, history, members=MEMBERS), seller, rules(), half())
    assert report.warnings == (
        (
            "BBCA has no bar on 2025-06-04, so it is not traded; it is valued at its last "
            "close, IDR 9,100"
        ),
    )
    assert report.holdings_value == rp(500 * 9_100 + 1_200 * 4_050)
    assert [(r.order.side, r.reason) for r in report.rejected] == [
        (Side.SELL, "no bar on 2025-06-04")
    ]


def test_a_held_stock_that_becomes_excluded_is_frozen_and_not_sold() -> None:
    state, _ = day_two()
    inputs = DayInputs(D3, steady(), members=MEMBERS, excluded={BBCA: "Special Monitoring Board"})
    after, report = run_day(state, inputs, _Fixed({}), rules(), half())
    assert report.frozen == ((BBCA, "excluded: Special Monitoring Board"),)
    assert after.holdings.frozen == {BBCA: "excluded: Special Monitoring Board"}
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, "frozen: excluded: Special Monitoring Board")
    ]
    assert [o.instrument for o in report.queued] == [BBRI]


def test_an_exclusion_freezes_only_a_held_stock_and_only_once() -> None:
    state, _ = day_two()
    inputs = DayInputs(D3, steady(), members=MEMBERS, excluded={BBCA: "board"})
    state, _ = run_day(state, inputs, BuyAndHold(), rules(), half())
    history = market(
        [(9_000, 9_000), (9_000, 9_100), (9_100, 9_100), (9_100, 9_100)],
        [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050), (4_050, 4_050)],
    )
    later = DayInputs(D4, history, members=MEMBERS, excluded={BBCA: "board"})
    _, report = run_day(state, later, BuyAndHold(), rules(), half())
    assert report.frozen == ()
    fresh = EngineState.opening(rp(10_000_000), D1)
    inputs = DayInputs(D1, steady(), members=MEMBERS, excluded={BBRI: "board"})
    after, report = run_day(fresh, inputs, _Fixed({BBRI: Decimal("0.1")}), rules(), half())
    assert (report.frozen, after.holdings.frozen) == ((), {})
    assert [r.reason for r in report.rejected] == ["excluded: board"]


def test_a_member_without_a_bar_is_not_bought_and_is_warned_about() -> None:
    history = PriceHistory([bar(BBCA, D1, 9_000)])
    state = EngineState.opening(rp(10_000_000), D1)
    _, report = run_day(
        state, DayInputs(D1, history, members=MEMBERS), BuyAndHold(), rules(), half()
    )
    assert report.warnings == ("BBRI has no bar on 2025-06-02, so it is not traded",)
    assert [o.instrument for o in report.queued] == [BBCA]


def test_a_held_stock_with_no_price_at_all_stops_the_day() -> None:
    state, _ = day_two()
    blind = EngineState(Holdings(state.holdings.portfolio), state.units, None, D2)
    history = market(
        [(9_000, 9_000), (9_000, 9_100)], [(4_000, 4_000), (4_000, 4_050), (4_050, 4_050)]
    )
    with pytest.raises(MissingPriceError, match=r"^no close price for BBCA$"):
        run_day(blind, DayInputs(D3, history, members=MEMBERS), BuyAndHold(), rules(), half())


def test_a_refused_stock_is_neither_bought_nor_sold() -> None:
    state, _ = day_two()
    inputs = DayInputs(D3, steady(), members=MEMBERS, refused=frozenset({BBRI}))
    _, report = run_day(state, inputs, _Fixed({}), rules(), half())
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBRI, "the data source refused 2025-06-04")
    ]


def test_a_weight_on_a_stock_outside_the_universe_is_dropped_with_its_reason() -> None:
    state = EngineState.opening(rp(10_000_000), D1)
    inputs = DayInputs(D1, steady(), members=frozenset({BBRI}))
    _, report = run_day(state, inputs, _Fixed({BBCA: Decimal("0.3")}), rules(), half())
    assert [(r.order.instrument, r.reason) for r in report.rejected] == [
        (BBCA, "not in the universe on 2025-06-02")
    ]


def test_the_monthly_contribution_arrives_on_the_months_first_trading_day() -> None:
    topped = EngineSettings(
        limits=RiskLimits(max_weight=Decimal("0.5")), monthly_contribution=rp(1_000_000)
    )
    state = EngineState.opening(rp(10_000_000), D1)
    state, report = run_day(
        state, DayInputs(D1, steady(), members=MEMBERS), BuyAndHold(), rules(), topped
    )
    assert report.deposit == rp(1_000_000)
    assert report.value == rp(11_000_000)
    assert (state.units.units, state.units.price) == (Decimal(11_000_000), Decimal(1))
    _, report = run_day(
        state, DayInputs(D2, steady(), members=MEMBERS), BuyAndHold(), rules(), topped
    )
    assert report.deposit == rp(0)


def test_settings_and_state_check_their_parts() -> None:
    with pytest.raises(ValueError, match=r"^a monthly contribution must be positive, got IDR 0$"):
        EngineSettings(monthly_contribution=rp(0))
    with pytest.raises(ValueError, match=r"^pay_lag_trading_days must be at least 1, got 0$"):
        EngineSettings(pay_lag_trading_days=0)
    with pytest.raises(TypeError, match=r"^limits must be a RiskLimits, got NoneType$"):
        EngineSettings(limits=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^holdings must be a Holdings, got NoneType$"):
        EngineState(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^halt must be a Halt, got str$"):
        EngineState(day_one()[0].holdings, halt="halted")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^members must be a frozenset, got set$"):
        DayInputs(D1, steady(), members={BBCA})  # type: ignore[arg-type]


@settings(max_examples=40)
@given(
    moves=st.lists(st.tuples(st.integers(-12, 12), st.integers(-12, 12)), min_size=3, max_size=3),
    capital=st.integers(1_000_000, 50_000_000),
)
def test_every_day_keeps_cash_whole_and_the_value_adding_up(
    moves: list[tuple[int, int]], capital: int
) -> None:
    closes = {BBCA: [9_000], BBRI: [4_000]}
    for bbca, bbri in moves:
        closes[BBCA].append(closes[BBCA][-1] // 25 * 25 + 25 * bbca)
        closes[BBRI].append(closes[BBRI][-1] // 10 * 10 + 10 * bbri)
    days = [D1, D2, D3, D4]
    history = PriceHistory(
        [
            bar(stock, day, path[n - 1] if n else path[0], path[n])
            for stock, path in closes.items()
            for n, day in enumerate(days)
        ]
    )
    state = EngineState.opening(rp(capital), D1)
    for day in days:
        state, report = run_day(
            state, DayInputs(day, history, members=MEMBERS), BuyAndHold(), rules(), half()
        )
        portfolio = state.holdings.portfolio
        assert report.settled.amount >= 0
        assert report.value == portfolio.cash_balance() + report.holdings_value
        assert all(p.quantity % 100 == 0 for p in portfolio.positions)
        charges = [
            m for m in portfolio.ledger if m.kind is MovementKind.DAILY_COST and m.day == day
        ]
        assert len(charges) == (1 if report.daily_cost.amount else 0)
```


- [ ] **Step 3: Write the stubs.**

**`packages/steadyhand/src/steadyhand/__init__.py`** (changed, new names stubbed: 3 edits)

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
from steadyhand.disclaimer import DISCLAIMER
from steadyhand.market import MarketRules, UnsupportedDateError
```
with:
```python
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
from steadyhand.market import MarketRules, UnsupportedDateError
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "DataUnavailableError",
    "Decision",
    "Entitlement",
```
with:
```python
    "DataUnavailableError",
    "DataValidationError",
    "DayInputs",
    "DayOrderError",
    "DayReport",
    "Decision",
    "EngineSettings",
    "EngineState",
    "Entitlement",
```

<!-- edit: packages/steadyhand/src/steadyhand/__init__.py -->
Replace:
```python
    "apply_actions",
]
```
with:
```python
    "apply_actions",
    "run_day",
]
```

**`packages/steadyhand/src/steadyhand/engine.py`** (new, as stubs)

<!-- file: packages/steadyhand/src/steadyhand/engine.py -->
```python
"""One trading day, from yesterday's state to today's (core spec §5, M3 spec §3).

``run_day`` is pure: it takes the previous ``EngineState`` and the day's ``DayInputs`` and returns
a new state and a ``DayReport``, changing nothing in place. A backtest repeats it over the
trading days; M5 will save each new state in one transaction, so a crash leaves yesterday's
state and a second run of the same day is refused rather than repeated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.broker.simulated import FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.market import MarketRules
from steadyhand.money import Money
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import Portfolio
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer
from steadyhand.strategies.protocol import Memory, Strategy
from steadyhand.types import CorporateAction, Fill, Instrument, Order, Split
from steadyhand.view import MarketView, PortfolioView, PriceHistory, Tradable


class DataValidationError(ValueError):
    """Today's prices are impossible, so nothing trades (M3 spec §7.4). M5 exits with code 3."""

    def __init__(self, instrument: Instrument, day: date, check: str) -> None:
        raise NotImplementedError("DataValidationError.__init__")


class DayOrderError(ValueError):
    """A day was run out of order: not after the last day run, or not a trading day."""


@dataclass(frozen=True, slots=True)
class EngineSettings:
    """How the engine runs a day. Every default is the core spec's."""

    fills: FillSettings = field(default_factory=FillSettings)
    limits: RiskLimits = field(default_factory=RiskLimits)
    monthly_contribution: Money | None = None
    """Cash deposited on the first trading day of each month, before the decision."""
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS

    def __post_init__(self) -> None:
        raise NotImplementedError("EngineSettings.__post_init__")


@dataclass(frozen=True, slots=True)
class EngineState:
    """Everything the engine carries from one day to the next. M5 saves it."""

    holdings: Holdings
    units: UnitValue = field(default_factory=UnitValue)
    halt: Halt | None = None
    last_day: date | None = None
    memory: Memory = field(default_factory=dict)

    def __post_init__(self) -> None:
        raise NotImplementedError("EngineState.__post_init__")

    @classmethod
    def opening(cls, capital: Money, day: date) -> EngineState:
        """A run's first state: *capital* deposited on *day*, the first day to run."""
        raise NotImplementedError("EngineState.opening")


@dataclass(frozen=True, slots=True)
class DayInputs:
    """What the world supplies for one day.

    ``history`` holds every bar the run may use; today's bars are the ones dated ``day``.
    ``actions`` are the corporate actions with today's ex-date. ``members`` and ``excluded`` come
    from the universe. ``refused`` names the stocks whose data source refused today (M3 spec
    §7.3), and ``resumed`` those whose data is clean again today after refused days, which have
    no usable previous close for the band check.
    """

    day: date
    history: PriceHistory
    actions: tuple[CorporateAction, ...] = ()
    members: frozenset[Instrument] = frozenset()
    excluded: Mapping[Instrument, str] = field(default_factory=dict)
    refused: frozenset[Instrument] = frozenset()
    resumed: frozenset[Instrument] = frozenset()

    def __post_init__(self) -> None:
        raise NotImplementedError("DayInputs.__post_init__")


@dataclass(frozen=True, slots=True)
class DayReport:
    """What happened on one day, for the report and the audit log (core spec §5 step 7)."""

    day: date
    fills: tuple[Fill, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]
    queued: tuple[Order, ...]
    entitled: tuple[Entitlement, ...]
    paid: tuple[Entitlement, ...]
    tax: Money
    daily_cost: Money
    deposit: Money
    frozen: tuple[tuple[Instrument, str], ...]
    halt: Halt | None
    settled: Money
    unsettled: Money
    holdings_value: Money
    value: Money
    warnings: tuple[str, ...]


def run_day(
    state: EngineState,
    inputs: DayInputs,
    strategy: Strategy,
    rules: MarketRules,
    settings: EngineSettings | None = None,
) -> tuple[EngineState, DayReport]:
    """Run *inputs.day*: validate, apply corporate actions, fill, value, decide and queue."""
    raise NotImplementedError("run_day")


def _fill(
    holdings: Holdings, inputs: DayInputs, rules: MarketRules, settings: FillSettings
) -> FillResult:
    """Fill yesterday's orders at today's open, each banded around its previous close."""
    raise NotImplementedError("_fill")


def _validate(inputs: DayInputs, rules: MarketRules) -> None:
    """Refuse a close outside the band around the previous close, where that close applies."""
    raise NotImplementedError("_validate")


def _freeze_excluded(
    holdings: Holdings, excluded: Mapping[Instrument, str]
) -> tuple[Holdings, tuple[tuple[Instrument, str], ...]]:
    """Freeze each held stock that is excluded today (core spec §6.1)."""
    raise NotImplementedError("_freeze_excluded")


def _closes(
    portfolio: Portfolio, last: Mapping[Instrument, Money], history: PriceHistory, day: date
) -> dict[Instrument, Money]:
    """Each held stock's close today, or its last close when it has no bar today."""
    raise NotImplementedError("_closes")


def _tradable(
    inputs: DayInputs,
    held: frozenset[Instrument],
    frozen: Mapping[Instrument, str],
    closes: Mapping[Instrument, Money],
) -> tuple[Tradable, list[str]]:
    """Today's buyable and sellable stocks (M3 spec §6.4), and a warning for each missing bar."""
    raise NotImplementedError("_tradable")


def _top_up(
    portfolio: Portfolio,
    units: UnitValue,
    contribution: Money | None,
    rules: MarketRules,
    day: date,
) -> tuple[Portfolio, UnitValue, Money]:
    """Deposit the monthly contribution on the month's first trading day (M3 spec §6.5)."""
    raise NotImplementedError("_top_up")


def _first_trading_day_of_month(rules: MarketRules, day: date) -> bool:
    raise NotImplementedError("_first_trading_day_of_month")
```


- [ ] **Step 4: Run the whole suite and watch it fail.** `uv run pytest -p no:cacheprovider > red.txt 2>&1; rc=$?`

<!-- check: red total=690 failed=23 -->
Expected: 690 run (the 4 `live` tests deselected), 23 failed. Every one fails on `NotImplementedError`; no new test passes against the stubs.

- [ ] **Step 5: Implement.**

**`packages/steadyhand/src/steadyhand/engine.py`** (replaces the stubs)

<!-- file: packages/steadyhand/src/steadyhand/engine.py -->
```python
"""One trading day, from yesterday's state to today's (core spec §5, M3 spec §3).

``run_day`` is pure: it takes the previous ``EngineState`` and the day's ``DayInputs`` and returns
a new state and a ``DayReport``, changing nothing in place. A backtest repeats it over the
trading days; M5 will save each new state in one transaction, so a crash leaves yesterday's
state and a second run of the same day is refused rather than repeated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from steadyhand._validate import require_date, require_int, require_type
from steadyhand.broker.simulated import FillResult, FillSettings, Opening, SimulatedBroker
from steadyhand.corporate import PAY_LAG_TRADING_DAYS, Entitlement, Holdings, apply_actions
from steadyhand.market import MarketRules
from steadyhand.money import Money
from steadyhand.outcomes import Cut, Rejected
from steadyhand.portfolio import Portfolio
from steadyhand.risk import Halt, RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer
from steadyhand.strategies.protocol import Memory, Strategy
from steadyhand.types import CorporateAction, Fill, Instrument, Order, Split
from steadyhand.view import MarketView, PortfolioView, PriceHistory, Tradable


class DataValidationError(ValueError):
    """Today's prices are impossible, so nothing trades (M3 spec §7.4). M5 exits with code 3."""

    def __init__(self, instrument: Instrument, day: date, check: str) -> None:
        super().__init__(f"{instrument.symbol} on {day.isoformat()}: {check}")


class DayOrderError(ValueError):
    """A day was run out of order: not after the last day run, or not a trading day."""


@dataclass(frozen=True, slots=True)
class EngineSettings:
    """How the engine runs a day. Every default is the core spec's."""

    fills: FillSettings = field(default_factory=FillSettings)
    limits: RiskLimits = field(default_factory=RiskLimits)
    monthly_contribution: Money | None = None
    """Cash deposited on the first trading day of each month, before the decision."""
    pay_lag_trading_days: int = PAY_LAG_TRADING_DAYS

    def __post_init__(self) -> None:
        require_type(self.fills, FillSettings, "fills")
        require_type(self.limits, RiskLimits, "limits")
        if self.monthly_contribution is not None:
            require_type(self.monthly_contribution, Money, "monthly_contribution")
            if self.monthly_contribution.amount <= 0:
                msg = f"a monthly contribution must be positive, got {self.monthly_contribution}"
                raise ValueError(msg)
        require_int(self.pay_lag_trading_days, "pay_lag_trading_days", minimum=1)


@dataclass(frozen=True, slots=True)
class EngineState:
    """Everything the engine carries from one day to the next. M5 saves it."""

    holdings: Holdings
    units: UnitValue = field(default_factory=UnitValue)
    halt: Halt | None = None
    last_day: date | None = None
    memory: Memory = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_type(self.holdings, Holdings, "holdings")
        require_type(self.units, UnitValue, "units")
        if self.halt is not None:
            require_type(self.halt, Halt, "halt")
        if self.last_day is not None:
            require_date(self.last_day, "last_day")

    @classmethod
    def opening(cls, capital: Money, day: date) -> EngineState:
        """A run's first state: *capital* deposited on *day*, the first day to run."""
        portfolio = Portfolio.empty(capital.currency).deposit(capital, day)
        return cls(Holdings(portfolio), UnitValue().deposit(capital))


@dataclass(frozen=True, slots=True)
class DayInputs:
    """What the world supplies for one day.

    ``history`` holds every bar the run may use; today's bars are the ones dated ``day``.
    ``actions`` are the corporate actions with today's ex-date. ``members`` and ``excluded`` come
    from the universe. ``refused`` names the stocks whose data source refused today (M3 spec
    §7.3), and ``resumed`` those whose data is clean again today after refused days, which have
    no usable previous close for the band check.
    """

    day: date
    history: PriceHistory
    actions: tuple[CorporateAction, ...] = ()
    members: frozenset[Instrument] = frozenset()
    excluded: Mapping[Instrument, str] = field(default_factory=dict)
    refused: frozenset[Instrument] = frozenset()
    resumed: frozenset[Instrument] = frozenset()

    def __post_init__(self) -> None:
        require_date(self.day, "day")
        require_type(self.history, PriceHistory, "history")
        for name in ("members", "refused", "resumed"):
            require_type(getattr(self, name), frozenset, name)


@dataclass(frozen=True, slots=True)
class DayReport:
    """What happened on one day, for the report and the audit log (core spec §5 step 7)."""

    day: date
    fills: tuple[Fill, ...]
    rejected: tuple[Rejected, ...]
    cuts: tuple[Cut, ...]
    queued: tuple[Order, ...]
    entitled: tuple[Entitlement, ...]
    paid: tuple[Entitlement, ...]
    tax: Money
    daily_cost: Money
    deposit: Money
    frozen: tuple[tuple[Instrument, str], ...]
    halt: Halt | None
    settled: Money
    unsettled: Money
    holdings_value: Money
    value: Money
    warnings: tuple[str, ...]


def run_day(
    state: EngineState,
    inputs: DayInputs,
    strategy: Strategy,
    rules: MarketRules,
    settings: EngineSettings | None = None,
) -> tuple[EngineState, DayReport]:
    """Run *inputs.day*: validate, apply corporate actions, fill, value, decide and queue."""
    settings = EngineSettings() if settings is None else settings
    day = inputs.day
    if state.last_day is not None and day <= state.last_day:
        msg = f"{day.isoformat()} is not after the last day run, {state.last_day.isoformat()}"
        raise DayOrderError(msg)
    if not rules.is_trading_day(day):
        msg = f"{day.isoformat()} is not a trading day"
        raise DayOrderError(msg)
    history = inputs.history
    _validate(inputs, rules)

    holdings, newly_excluded = _freeze_excluded(state.holdings, inputs.excluded)
    corporate = apply_actions(holdings, inputs.actions, day, rules, settings.pay_lag_trading_days)
    holdings = corporate.holdings
    filled = _fill(holdings, inputs, rules, settings.fills)
    portfolio = filled.portfolio

    closes = _closes(portfolio, holdings.last_closes, history, day)
    holdings_value = portfolio.holdings_value(closes)
    units = state.units.revalue(portfolio.cash_balance() + holdings_value)
    risk = RiskManager(rules, settings.limits)
    new_halt = None if state.halt is not None else risk.halt(state.units, units, day)
    halt = state.halt or new_halt

    portfolio, units, deposit = _top_up(portfolio, units, settings.monthly_contribution, rules, day)
    value = portfolio.cash_balance() + holdings_value

    held = {position.instrument: position.quantity for position in portfolio.positions}
    tradable, warnings = _tradable(inputs, frozenset(held), holdings.frozen, closes)
    queued: tuple[Order, ...] = ()
    rejected = [*corporate.cancelled, *filled.rejected]
    cuts = list(filled.cuts)
    memory = state.memory
    if halt is None:
        spendable = max(portfolio.spendable_cash(day), Money.zero(portfolio.currency))
        worth = {stock: closes[stock] * quantity for stock, quantity in held.items()}
        seen = PortfolioView(value, spendable, worth)
        view = MarketView(history, day, tradable)
        decision = strategy.decide(view, seen, state.memory)
        prices = dict(closes)
        for stock in decision.weights:
            if stock not in prices and (close := view.last_close(stock)) is not None:
                prices[stock] = close
        sized = CompoundingSizer(rules).size(decision.weights, seen, held, prices, day)
        checked = risk.check(sized, seen, tradable, prices)
        queued = checked.orders
        rejected += checked.rejected
        cuts += checked.cuts
        memory = decision.memory

    new_holdings = Holdings(portfolio, queued, holdings.entitlements, holdings.frozen, closes)
    report = DayReport(
        day=day,
        fills=filled.fills,
        rejected=tuple(rejected),
        cuts=tuple(cuts),
        queued=queued,
        entitled=corporate.entitled,
        paid=corporate.paid,
        tax=corporate.tax,
        daily_cost=filled.daily_cost,
        deposit=deposit,
        frozen=(*newly_excluded, *corporate.frozen),
        halt=new_halt,
        settled=portfolio.settled_cash(day),
        unsettled=portfolio.unsettled_cash(day),
        holdings_value=holdings_value,
        value=value,
        warnings=(*corporate.warnings, *warnings),
    )
    return EngineState(new_holdings, units, halt, day, memory), report


def _fill(
    holdings: Holdings, inputs: DayInputs, rules: MarketRules, settings: FillSettings
) -> FillResult:
    """Fill yesterday's orders at today's open, each banded around its previous close."""
    day = inputs.day
    ordered = {order.instrument for order in holdings.pending}
    opening = Opening(
        day,
        {i: bar for i in ordered if (bar := inputs.history.on(i, day)) is not None},
        {i: bar.close for i in ordered if (bar := inputs.history.before(i, day)) is not None},
        holdings.frozen,
    )
    return SimulatedBroker(rules, settings).fill(holdings.portfolio, holdings.pending, opening)


def _validate(inputs: DayInputs, rules: MarketRules) -> None:
    """Refuse a close outside the band around the previous close, where that close applies."""
    day = inputs.day
    split = {action.instrument for action in inputs.actions if isinstance(action, Split)}
    exempt = split | inputs.resumed
    for instrument in sorted(inputs.history.instruments, key=lambda i: (i.market, i.symbol)):
        bar = inputs.history.on(instrument, day)
        previous = inputs.history.before(instrument, day)
        if bar is None or previous is None or instrument in exempt:
            continue
        low, high = rules.price_band(instrument, previous.close, day)
        if not low <= bar.close <= high:
            check = (
                f"the close {bar.close} is outside the band {low} to {high} around the "
                f"previous close {previous.close}"
            )
            raise DataValidationError(instrument, day, check)


def _freeze_excluded(
    holdings: Holdings, excluded: Mapping[Instrument, str]
) -> tuple[Holdings, tuple[tuple[Instrument, str], ...]]:
    """Freeze each held stock that is excluded today (core spec §6.1)."""
    frozen = dict(holdings.frozen)
    newly: list[tuple[Instrument, str]] = []
    for instrument in sorted(excluded, key=lambda i: (i.market, i.symbol)):
        if holdings.portfolio.position(instrument) is not None and instrument not in frozen:
            frozen[instrument] = f"excluded: {excluded[instrument]}"
            newly.append((instrument, frozen[instrument]))
    return replace(holdings, frozen=frozen), tuple(newly)


def _closes(
    portfolio: Portfolio, last: Mapping[Instrument, Money], history: PriceHistory, day: date
) -> dict[Instrument, Money]:
    """Each held stock's close today, or its last close when it has no bar today."""
    closes: dict[Instrument, Money] = {}
    for position in portfolio.positions:
        bar = history.on(position.instrument, day)
        close = bar.close if bar is not None else last.get(position.instrument)
        if close is not None:
            closes[position.instrument] = close
    return closes


def _tradable(
    inputs: DayInputs,
    held: frozenset[Instrument],
    frozen: Mapping[Instrument, str],
    closes: Mapping[Instrument, Money],
) -> tuple[Tradable, list[str]]:
    """Today's buyable and sellable stocks (M3 spec §6.4), and a warning for each missing bar."""
    day = inputs.day
    reasons: dict[Instrument, str] = {}
    for instrument in inputs.refused:
        reasons[instrument] = f"the data source refused {day.isoformat()}"
    for instrument, reason in frozen.items():
        reasons.setdefault(instrument, f"frozen: {reason}")
    for instrument, reason in inputs.excluded.items():
        reasons.setdefault(instrument, f"excluded: {reason}")
    warnings: list[str] = []
    for instrument in sorted(inputs.members | held, key=lambda i: (i.market, i.symbol)):
        if instrument in reasons or inputs.history.on(instrument, day) is not None:
            continue
        reasons[instrument] = f"no bar on {day.isoformat()}"
        warning = f"{instrument.symbol} has no bar on {day.isoformat()}, so it is not traded"
        if instrument in held:
            warning += f"; it is valued at its last close, {closes[instrument]}"
        warnings.append(warning)
    buyable = frozenset(inputs.members - reasons.keys())
    sellable = frozenset(held - reasons.keys())
    return Tradable(day, buyable, sellable, reasons), warnings


def _top_up(
    portfolio: Portfolio,
    units: UnitValue,
    contribution: Money | None,
    rules: MarketRules,
    day: date,
) -> tuple[Portfolio, UnitValue, Money]:
    """Deposit the monthly contribution on the month's first trading day (M3 spec §6.5)."""
    if contribution is None or not _first_trading_day_of_month(rules, day):
        return portfolio, units, Money.zero(portfolio.currency)
    return portfolio.deposit(contribution, day), units.deposit(contribution), contribution


def _first_trading_day_of_month(rules: MarketRules, day: date) -> bool:
    earlier = day.replace(day=1)
    while earlier < day:
        if rules.is_trading_day(earlier):
            return False
        earlier += timedelta(days=1)
    return True
```


- [ ] **Step 6: Run the whole gate**, as in Task 1 Step 6.

<!-- check: gate total=690 passed=690 -->
Expected: every command exits 0; 690 passed, 4 deselected, 100% branch coverage.

- [ ] **Step 7: Mutations.** Run M29–M33; each must turn the whole suite red with the total unchanged.
- [ ] **Step 8: Commit, push and merge** (`feat(engine): S6 …`). Then update `HANDOVER.md` for the M3b plan.

---

## Mutation checks

Each mutation plants one realistic defect in its own story's finished tree, runs the **whole** suite, and must turn it red. Plant it exactly as the block after the table says: the anchor must match exactly once, and the changed line is printed before the run. Revert with `git checkout -- <path>` only after the story is committed. The total must not move. The "caught by" column is what the run showed, not only what was predicted: every prediction was written before the run, and a run that caught more is recorded in full.

| # | Task | Defect planted | Caught by |
|---|---|---|---|
| M1 | 1 | `portfolio.py`: `spendable_cash` counts a debit only once it settles | `test_a_deferred_charge_is_held_back_from_spending_at_once` |
| M2 | 1 | `portfolio.py`: a split's ratio applied upside down | `test_a_holding_that_rounds_to_nothing_is_removed`, `test_a_reverse_split_drops_the_fraction_of_a_share`, `test_a_split_leaves_other_holdings_alone`, `test_a_split_scales_the_quantity_and_keeps_the_basis`, `test_splits_keep_the_total_cost_basis` |
| M3 | 1 | `portfolio.py`: `charge` accepts a deposit | `test_only_tax_and_daily_costs_are_charges` |
| M4 | 1 | `docs/lq45-members.md`: the disclaimer moved into an HTML comment | `test_every_user_facing_doc_carries_the_disclaimer` |
| M5 | 1 | `data.py`: unavailable days accepted out of order | `test_the_days_are_different_and_in_order` |
| M6 | 1 | `steadyhand_idx/universe.py`: the first day read from the last list | `test_the_first_day_is_the_first_list_and_nothing_before_it_is_guessed` |
| M7 | 2 | `view.py`: `history` does not check its end date | `test_asking_about_a_later_day_is_look_ahead` |
| M8 | 2 | `view.py`: `before` returns the bar on the day itself | `test_before_is_the_last_bar_strictly_earlier` |
| M9 | 2 | `buy_and_hold.py`: the set chosen again every day | `test_an_empty_first_day_leaves_an_empty_set`, `test_it_never_sells_and_buys_only_its_set`, `test_later_days_keep_holdings_and_buy_only_the_set` |
| M10 | 2 | `_ratio.py`: ratios rounded half-even instead of down | `test_ratios_round_down_and_a_zero_whole_is_zero` |
| M11 | 2 | `test_strategy_guides.py`: HTML comments no longer stripped | `test_the_checker_finds_each_problem` |
| M12 | 2 | `strategies/buy_and_hold.py`: a float constant, in a module the old list missed | `test_guarded_engine_modules_contain_no_float` |
| M13 | 2 | `docs/strategies/buy-and-hold.md`: the Risks heading misspelled | `test_every_registered_strategy_has_a_complete_guide` |
| M14 | 3 | `broker/simulated.py`: orders filled in the order given, buys before sells | `test_every_sell_fills_before_any_buy` |
| M15 | 3 | `broker/simulated.py`: a buy's slippage rounded down | `test_slippage_rounds_against_the_trader_before_the_tick` |
| M16 | 3 | `broker/simulated.py`: the volume cap not rounded to whole lots | `test_an_order_is_cut_to_a_tenth_of_the_volume_in_whole_lots`, `test_an_order_is_rejected_when_a_tenth_of_the_volume_is_under_a_lot`, `test_fills_keep_cash_whole_lots_ticks_and_bands` |
| M17 | 3 | `broker/simulated.py`: a buy does not hold back the day's charge | `test_the_days_stamp_duty_is_held_back_from_a_buy_and_charged_once` |
| M18 | 3 | `broker/simulated.py`: a sales-only day's charge debited on the day | `test_a_sales_only_day_nets_its_stamp_duty_with_the_sales`, `test_fills_keep_cash_whole_lots_ticks_and_bands` |
| M19 | 3 | `broker/simulated.py`: a price on the band's lower edge rejected | `test_a_price_on_the_band_edge_is_accepted` |
| M20 | 4 | `sizing.py`: lots rounded away from zero | `test_a_target_within_a_lot_of_the_holding_places_no_order`, `test_a_weight_becomes_whole_lots_at_the_last_close_rounded_down`, `test_orders_are_whole_lots_that_never_overshoot_the_target`, `test_sizes_grow_with_the_portfolio` |
| M21 | 4 | `risk.py`: the per-stock limit ignores what is already held | `test_a_buy_for_a_stock_already_at_the_limit_is_dropped` |
| M22 | 4 | `risk.py`: a daily loss exactly at the limit does not halt | `test_a_daily_loss_at_the_limit_halts` |
| M23 | 4 | `risk.py`: a deposit buys units at 1, not at the price | `test_a_deposit_leaves_the_unit_value_unchanged`, `test_a_deposit_never_moves_the_price` |
| M24 | 4 | `risk.py`: the buying budget never goes down | `test_buys_together_spend_no_more_than_the_cash_costs_included` |
| M25 | 5 | `corporate.py`: a dividend earned on the shares after today's split | `test_a_same_day_split_and_dividend_pays_on_the_shares_before_the_split` |
| M26 | 5 | `corporate.py`: entitlements paid on their ex-date | `test_a_dividend_entitles_what_was_held_at_the_previous_close`, `test_an_entitlement_is_paid_and_taxed_on_its_pay_date_even_after_a_sale` |
| M27 | 5 | `corporate.py`: the last close not scaled by a split | `test_a_split_scales_the_holding_and_the_last_close_and_cancels_its_orders` |
| M28 | 5 | `corporate.py`: an other action freezes a stock not held | `test_another_action_freezes_a_held_stock_once` |
| M29 | 6 | `engine.py`: the band check not skipped on a split's ex-date | `test_the_band_check_skips_resumed_stocks_and_split_ex_dates` |
| M30 | 6 | `engine.py`: a halt forgotten the next day | `test_a_loss_at_the_limit_halts_ordering_for_the_rest_of_the_run`, `test_dividends_still_arrive_while_halted` |
| M31 | 6 | `engine.py`: the contribution deposited every day | `test_the_monthly_contribution_arrives_on_the_months_first_trading_day` |
| M32 | 6 | `engine.py`: an excluded held stock not frozen | `test_a_held_stock_that_becomes_excluded_is_frozen_and_not_sold` |
| M33 | 6 | `engine.py`: a held stock without a bar not valued at its last close | `test_a_held_stock_without_a_bar_is_valued_at_its_last_close_and_not_sold`, `test_a_split_cancels_pending_orders_and_rescales_the_last_close` |

Each story's total, which a mutation must not move: Task 1: 555, Task 2: 588, Task 3: 620, Task 4: 652, Task 5: 667, Task 6: 690 (plus the 4 deselected `live` tests).

Planted exactly (Python string literals, so a newline shows as `\n`):

```text
M1  packages/steadyhand/src/steadyhand/portfolio.py
    replace 'if m.amount.amount < 0 or m.settles_on <= on)'
    with    'if m.settles_on <= on)'
M2  packages/steadyhand/src/steadyhand/portfolio.py
    replace 'held.quantity * split.new_shares // split.old_shares'
    with    'held.quantity * split.old_shares // split.new_shares'
M3  packages/steadyhand/src/steadyhand/portfolio.py
    replace 'frozenset({MovementKind.TAX, MovementKind.DAILY_COST})'
    with    'frozenset({MovementKind.TAX, MovementKind.DAILY_COST, MovementKind.DEPOSIT})'
M4  docs/lq45-members.md
    replace '> steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money.'
    with    '<!-- > steadyhand is example software that you run yourself, on your own account, and you make your own decisions with it. It is not financial advice. You can lose money. -->'
M5  packages/steadyhand/src/steadyhand/data.py
    replace 'if list(found) != sorted(set(found)):'
    with    'if len(found) != len(set(found)):'
M6  packages/steadyhand-idx/src/steadyhand_idx/universe.py
    replace 'return self._membership.records[0].effective'
    with    'return self._membership.records[-1].effective'
M7  packages/steadyhand/src/steadyhand/view.py
    replace 'last = self._today if end is None else self._checked(end)'
    with    'last = self._today if end is None else end'
M8  packages/steadyhand/src/steadyhand/view.py
    replace 'index = bisect_left(days, day)'
    with    'index = bisect_right(days, day)'
M9  packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py
    replace 'if _SET_KEY in memory else'
    with    'if False else'
M10  packages/steadyhand/src/steadyhand/_ratio.py
    replace '        context.rounding = ROUND_FLOOR\n'
    with    ''
M11  tests/meta/test_strategy_guides.py
    replace 'for line in _COMMENT.sub("", markdown).splitlines():'
    with    'for line in markdown.splitlines():'
M12  packages/steadyhand/src/steadyhand/strategies/buy_and_hold.py
    replace '_SET_KEY = "set"\n'
    with    '_SET_KEY = "set"\n_SCALE = 0.5\n'
M13  docs/strategies/buy-and-hold.md
    replace '## Risks\n'
    with    '## Risk\n'
M14  packages/steadyhand/src/steadyhand/broker/simulated.py
    replace 'for order in sorted(orders, key=lambda order: order.side is Side.BUY):'
    with    'for order in orders:'
M15  packages/steadyhand/src/steadyhand/broker/simulated.py
    replace 'slipped = bar.open.times(1 + slippage, Rounding.UP)'
    with    'slipped = bar.open.times(1 + slippage, Rounding.DOWN)'
M16  packages/steadyhand/src/steadyhand/broker/simulated.py
    replace 'int((volume * cap).to_integral_value(rounding=ROUND_FLOOR)) // lot * lot'
    with    'int((volume * cap).to_integral_value(rounding=ROUND_FLOOR))'
M17  packages/steadyhand/src/steadyhand/broker/simulated.py
    replace 'return gross + buying + self._daily(self._traded + gross)'
    with    'return gross + buying'
M18  packages/steadyhand/src/steadyhand/broker/simulated.py
    replace 'settles = self._day if self._bought else self._rules.settlement_date(self._day)'
    with    'settles = self._day'
M19  packages/steadyhand/src/steadyhand/broker/simulated.py
    replace 'if not low <= price <= high:'
    with    'if not low < price <= high:'
M20  packages/steadyhand/src/steadyhand/sizing.py
    replace 'lots = abs((target - current).amount) // (price * lot).amount'
    with    'lots = -(-abs((target - current).amount) // (price * lot).amount)'
M21  packages/steadyhand/src/steadyhand/risk.py
    replace 'room = (cap - held).amount // (price * lot).amount * lot'
    with    'room = cap.amount // (price * lot).amount * lot'
M22  packages/steadyhand/src/steadyhand/risk.py
    replace 'if fall >= self._limits.daily_loss:'
    with    'if fall > self._limits.daily_loss:'
M23  packages/steadyhand/src/steadyhand/risk.py
    replace 'self.units + ratio_down(amount.amount, self.price)'
    with    'self.units + Decimal(amount.amount)'
M24  packages/steadyhand/src/steadyhand/risk.py
    replace 'budget -= self._cost(affordable, price, day)'
    with    'budget -= Money.zero(budget.currency)'
M25  packages/steadyhand/src/steadyhand/corporate.py
    replace 'held = self._before.position(dividend.instrument)'
    with    'held = self._portfolio.position(dividend.instrument)'
M26  packages/steadyhand/src/steadyhand/corporate.py
    replace 'if e.pay_date <= self._day]'
    with    'if e.ex_date <= self._day]'
M27  packages/steadyhand/src/steadyhand/corporate.py
    replace 'self._closes[stock] = Money(scaled, close.currency)'
    with    'self._closes[stock] = close'
M28  packages/steadyhand/src/steadyhand/corporate.py
    replace 'if self._portfolio.position(stock) is not None and stock not in self._frozen:'
    with    'if stock not in self._frozen:'
M29  packages/steadyhand/src/steadyhand/engine.py
    replace 'exempt = split | inputs.resumed'
    with    'exempt = inputs.resumed'
M30  packages/steadyhand/src/steadyhand/engine.py
    replace 'halt = state.halt or new_halt'
    with    'halt = new_halt'
M31  packages/steadyhand/src/steadyhand/engine.py
    replace 'if contribution is None or not _first_trading_day_of_month(rules, day):'
    with    'if contribution is None:'
M32  packages/steadyhand/src/steadyhand/engine.py
    replace 'if holdings.portfolio.position(instrument) is not None and instrument not in frozen:'
    with    'if False:'
M33  packages/steadyhand/src/steadyhand/engine.py
    replace 'close = bar.close if bar is not None else last.get(position.instrument)'
    with    'close = bar.close if bar is not None else None'
```

## Carried forward to M3b and later

- **M3b, the backtest's first state** is `EngineState.opening(capital, first_day)`, and each later day passes the previous state to `run_day`.
- **M3b, refused days (M3 §7.3):** remove a stock's refused days' bars from the `PriceHistory`, list the stock in `DayInputs.refused` on those days and in `DayInputs.resumed` on its first clean day after them, and print one warning per stock naming its refused days. `run_day` already keeps a refused stock out of the tradable set and values it at its last close.
- **M3b, the fetch** needs every instrument `Universe.members_on` returns on any trading day in the window, plus the `Universe.first_day()` check before day one (M3 decision 3).
- **M3b, metrics** read `DayReport`: fills' `costs` split into fee, levy and tax; `daily_cost`; `paid` and `tax` for dividends; `value` and `deposit`; and `EngineState.units` for the time-weighted return.
- **M3b, `buy-and-hold` as the baseline** runs with the same `EngineSettings` as the strategy; its guide already exists.
- **M5:** save `EngineState` whole (its `Holdings`, `UnitValue`, `Halt` and `memory`) in one transaction per day, and turn `DayOrderError` for a day already run into the "already ran" report; `resume` clears `EngineState.halt`.
- **M6:** price history from before the backtest's start, for strategies with a look-back window.

## Plan review log

(Passes are recorded below. The loop ends on a pass with zero findings, and then the plan is approved.)

- **Pass 1 (2026-09-26):** mechanical, then a full read of the prose. Every code block was rendered by `render.py` from six story commits that each passed CI's gate (`ruff check`, `ruff format --check`, `mypy`, `HYPOTHESIS_PROFILE=ci pytest -W error --cov`) at 100% branch coverage. `check_plan.py` then replayed the plan from its own text, task by task on top of the previous task's replay: it wrote the blocks before each red marker, ran the whole suite, wrote the rest, required the tree to be byte-identical to the story's commit, and ran the whole suite again. All six trees were identical and all twelve red and gate claims matched. The red phases were run from stubs generated by `stubgen.py`; every test that passed against them is listed with its reason in its task. All 33 mutations were run over the whole suite in their own story's tree, with predictions written first: every one turned the suite red with the total unchanged. The first run found two mutations the suite missed, and both became tests before this pass: a buy's slippage rounded down (M15; at Rp9,000 the Rp25 tick hid it, so a Rp150 stock now pins it) and a deposit buying units at 1 (M23; the property now revalues after the deposit). Writing that property found its own comment wrong: Decimal rounding can move the revalued price either way, so the bound is symmetric. Designing the mutations also found the disclaimer guard satisfied by a disclaimer inside an HTML comment; it now strips comments (M4). Spec coverage was checked section by section against M3 §3–§7.4, §9 and §10; every deviation is a numbered scope decision. Placeholder scan clean. The read found three things, all fixed: (1) the red and gate expectations said "collected" where pytest collects the 4 `live` tests too and deselects them; (2) Task 6's property runs four days, not three; (3) the mutation table did not give the exact anchors, so an executor could not reproduce a mutation from the plan alone. It now prints every one exactly, generated from the list that was run.
- **Pass 2 (2026-09-26):** mechanical, on the re-rendered plan: `check_plan.py` again rebuilt all six story trees byte-identical to the verified commits, and all twelve red and gate claims matched; the "Planted exactly" block, parsed back into Python values, equals the 33 mutations that were run. Read: every line pass 1 changed (the six red expectations, the six gate expectations beside them, Task 6's acceptance criterion 7, the mutation section's instructions and its planted block) against the counts in the runs and the tests they name. **0 findings. Loop closed; the plan is approved.**
