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
    """The settings a day runs with, by configuration key, as the audit log shows them: the
    engine's, and the settings of the strategy that runs (M6 spec §4.5)."""
    engine = config.settings.engine
    contribution = engine.monthly_contribution
    strategy = {
        f"strategy.{setting.name}": str(config.strategy_settings[setting.name])
        for setting in STRATEGIES[config.strategy].settings
    }
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
        **strategy,
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
    strategy = STRATEGIES[config.strategy](config.strategy_settings)
    state, report = run_day(state, inputs, strategy, rules, config.settings.engine)
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
    """An audit line for each setting that changed since the last day run (M5 spec §6.5).

    A strategy's setting is recorded the first time a day runs with it, as after ``paper
    switch``, and its guide, not this line, says when a change takes effect: ``monthly-savings``
    fixes its instalments on its first day (M6 spec §5).
    """
    lines: list[AuditLine] = []
    for key in sorted(after):
        old, new = before.get(key), after[key]
        if old == new:
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
