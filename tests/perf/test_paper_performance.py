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
