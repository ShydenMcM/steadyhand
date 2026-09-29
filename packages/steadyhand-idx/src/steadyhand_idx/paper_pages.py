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


def status_page(account: Account, report: DayReport) -> Page:
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


def day_report_page(report: DayReport, account: Account | None) -> Page:
    """One saved day (M5 spec §7.2). Holdings are listed when *report* is *account*'s last day:
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


def income_page(income: IncomeReport) -> Page:
    """The M4 income view of the account (M5 spec §7.2): received income, the run-rate, the
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


def _holdings(page: Page, holdings: Holdings, value: Money) -> None:
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


def _claims(page: Page, claims: Sequence[DividendClaim]) -> None:
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


def _section(page: Page, title: str, items: Sequence[Item]) -> None:
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


def _rate(value: Decimal | None) -> str:
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
