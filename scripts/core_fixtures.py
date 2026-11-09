"""Write what the extension's core reads from Python (#223, spec §4.1, §4.2).

The rule files become JSON in ``extension/packages/core/rules/``, each read and checked by
Python's own reader first, so a file Python refuses is never converted. Whole numbers, dates and
times are written as strings: core never holds a ``number``, and reads each as a ``bigint``, a
date or a time.
The ratio fixture holds Python's digits for seeded inputs, which core's ratios must give exactly,
and the rules fixture holds what ``IdxMarketRules`` answers for seeded days, prices and trades,
which core's rules must give exactly (#224). The parity fixture holds seeded portfolios, weights,
limits and tradable sets with the orders, cuts and rejections Python's ``CompoundingSizer`` and
``RiskManager`` give them, which core's sizing and risk must give exactly (#228, spec §14.4).

Run from the repository root: ``uv run --locked python scripts/core_fixtures.py``. CI runs it again
and fails if a committed file differs (tests/integration/scripts/test_core_fixtures.py).
"""

import argparse
import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal
from pathlib import Path
from typing import Any, TypedDict

from steadyhand import IDR, Instrument, Money, Side
from steadyhand._ratio import ratio_down
from steadyhand.corporate import PAY_LAG_TRADING_DAYS
from steadyhand.income import (
    HISTORY_YEARS,
    IncomeGoal,
    IncomeSettings,
    ProjectionOutcome,
    _restated_gross,
    _share,
    dividend_growth,
    payment_calendar,
    project,
    run_rate,
    years_before,
)
from steadyhand.market import PayDates
from steadyhand.metrics import _rounded
from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, TRADE_EXCLUDED, TRADE_FROZEN, Note
from steadyhand.portfolio import Portfolio
from steadyhand.risk import RiskLimits, RiskManager, UnitValue
from steadyhand.sizing import CompoundingSizer
from steadyhand.strategies import BuyAndHold, DividendGrowthStrategy, MonthlySavings
from steadyhand.strategies.protocol import Strategy
from steadyhand.types import Bar, CashDividend, Costs, Fill, Order, Split
from steadyhand.view import ActionHistory, MarketView, PortfolioView, PriceHistory, Tradable
from steadyhand_idx._datafile import Row, load_shipped
from steadyhand_idx.bands import BANDS_FILE, parse_bands
from steadyhand_idx.calendar import HOLIDAYS_FILE, IdxCalendar, parse_holidays
from steadyhand_idx.fees import FEES_FILE, parse_fees
from steadyhand_idx.rules import IdxMarketRules
from steadyhand_idx.sessions import SESSIONS_FILE, parse_sessions
from steadyhand_idx.ticks import TICKS_FILE, parse_settlement, parse_ticks

ROOT = Path(__file__).resolve().parents[1]
RULES = Path("extension/packages/core/rules")
RATIOS = Path("extension/packages/core/test/ratios.json")
RULES_CASES = Path("extension/packages/core/test/rules.json")
PARITY = Path("extension/packages/core/test/parity.json")
STRATEGY_PARITY = Path("extension/packages/core/test/parity-strategies.json")
RESTATED_PARITY = Path("extension/packages/core/test/parity-restated.json")
GROWTH_PARITY = Path("extension/packages/core/test/parity-dividend-growth.json")
INCOME_PARITY = Path("extension/packages/core/test/parity-income.json")
PROJECTION_PARITY = Path("extension/packages/core/test/parity-projection.json")
HALT_PARITY = Path("extension/packages/core/test/parity-halts.json")

# Each rule file and the Python readers that must accept it before it is converted.
READERS: dict[str, tuple[Callable[[Row], object], ...]] = {
    TICKS_FILE: (parse_ticks, parse_settlement),
    BANDS_FILE: (parse_bands,),
    HOLIDAYS_FILE: (parse_holidays,),
    FEES_FILE: (parse_fees,),
    SESSIONS_FILE: (parse_sessions,),
}

SEED = 223
CASES = 200
# Fifty significant digits, half-even: the context the engine's ratios are worked out in.
WIDE = Context(prec=50, rounding=ROUND_HALF_EVEN)


def plain(value: object) -> object:
    """*value* with every whole number, date and time written as a string, keys in order."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, date | time):
        return value.isoformat()
    return value


def rule_files() -> dict[Path, object]:
    """Each rule file as JSON, once every reader of it accepts it."""
    written: dict[Path, object] = {}
    for name, readers in READERS.items():
        document = load_shipped(name)
        for reader in readers:
            reader(document)
        written[RULES / name.replace(".toml", ".json")] = plain(document)
    return written


def ratio_cases() -> dict[str, list[list[str]]]:
    """Python's ``ratio_down`` and its eight-place rounding on seeded inputs and their edges."""
    draw = random.Random(SEED)  # noqa: S311 - seeded test inputs, not secrets
    pairs = [(0, 1), (1, 3), (2, 3), (-1, 3), (5, 0), (10**15, 7), (1, 10**15), (7, 7)]
    pairs += [(draw.randrange(10**15), draw.randrange(1, 10**15)) for _ in range(CASES)]
    down = [[str(part), str(whole), str(ratio_down(part, whole))] for part, whole in pairs]
    values = [Decimal(text) for text in ("0.000000005", "0.000000015", "-0.000000025", "1e30")]
    values += [Decimal("123456789012345678901234567890.123456785")]
    values += [WIDE.divide(Decimal(part), Decimal(whole)) for part, whole in pairs if whole]
    rounded = [[str(value), str(_rounded(value))] for value in values]
    return {"ratio_down": down, "rounded": rounded}


RULE_SEED = 224
RULE_CASES = 300
PRESETS = ("custom", "ajaib")
_ANY = Instrument("BBCA", "IDX", IDR)


def rule_cases() -> list[dict[str, str]]:
    """``IdxMarketRules`` on seeded trading days from ``verified_from``, prices and trade values.

    The days run to two weeks before the end of the holiday data; prices span every tick tier,
    references every band tier (from 50, the highest minimum price), and trade values every
    rounding, for each preset and side. Every answer is written as text, as core reads it.
    """
    draw = random.Random(RULE_SEED)  # noqa: S311 - seeded test inputs, not secrets
    rules = {name: IdxMarketRules(broker_fees=name) for name in PRESETS}
    first = rules["custom"].verified_from
    # Two weeks short of the holiday data's end, so every trade's settlement day is covered too.
    last = IdxCalendar.shipped().last_day - timedelta(days=14)
    cases: list[dict[str, str]] = []
    while len(cases) < RULE_CASES:
        day = first + timedelta(days=draw.randrange((last - first).days + 1))
        if not rules["custom"].is_trading_day(day):
            continue
        preset = draw.choice(PRESETS)
        side = draw.choice(list(Side))
        market = rules[preset]
        price = Money(draw.choice((draw.randrange(1, 600), draw.randrange(1, 2_000_000))), IDR)
        reference = Money(
            draw.choice((draw.randrange(50, 600), draw.randrange(50, 2_000_000))), IDR
        )
        gross = Money(draw.choice((draw.randrange(10_000), draw.randrange(10**12))), IDR)
        low, high = market.price_band(_ANY, reference, day)
        costs = market.costs(side, gross, day)
        cases.append({
            "day": day.isoformat(),
            "preset": preset,
            "side": side.value,
            "price": str(price.amount),
            "tick": str(market.round_to_tick(_ANY, price, side, day).amount),
            "reference": str(reference.amount),
            "low": str(low.amount),
            "high": str(high.amount),
            "gross": str(gross.amount),
            "fee": str(costs.fee.amount),
            "levy": str(costs.levy.amount),
            "tax": str(costs.tax.amount),
            "stamp_duty": str(market.daily_costs(gross, day).amount),
            "dividend_tax": str(market.dividend_tax(gross, on=day).amount),
            "settles": market.settlement_date(day).isoformat(),
        })  # fmt: skip
    return cases


PARITY_SEED = 228
PARITY_CASES = 300
PARITY_DAY = date(2025, 6, 2)
PARITY_STOCKS = ("ASII", "BBCA", "BBRI", "BMRI", "TLKM", "UNVR")
# Each limit per stock and minimum buy a case may draw: the default, tighter, looser and none.
MAX_WEIGHTS = ("0.05", "0.10", "0.25", "1")
FLAGS = ("frozen: suspended", "frozen: on the Special Monitoring Board")
# How often a drawn stock is held, weighted, in the universe, frozen, and frozen or excluded.
HELD, WEIGHTED, MEMBER, FROZEN, KEPT_OUT = 0.5, 0.7, 0.85, 0.1, 0.2
# How often a weight is drawn to put its target on a whole-lot edge, where rounding the target
# down rather than up decides the lots (a harness without them missed that change, 2026-11-02).
ON_AN_EDGE = 0.3


class ParityCases(TypedDict):
    seed: str
    cases: list[dict[str, Any]]


def _order(order: Order) -> dict[str, str]:
    return {
        "symbol": order.instrument.symbol,
        "side": order.side.value,
        "quantity": str(order.quantity),
        "day": order.placed_on.isoformat(),
    }


def _parity_case(draw: random.Random, rules: IdxMarketRules, name: str) -> dict[str, Any]:
    """One seeded portfolio and what Python's sizer, then its risk manager, make of it.

    Some stocks are held (a few with an odd lot over), some weighted, some both; some are out of
    the universe, frozen or excluded; the cash runs from none, or less than none, to more than
    every target; some weights put a target on a whole-lot edge; and the limits vary, so every
    cut and rejection comes up across the cases.
    The sizer only sells what is held, so a case may add orders of its own for the risk manager
    (``extra``), a sale of a stock not held among them.
    """
    stocks = sorted(draw.sample(PARITY_STOCKS, draw.randint(1, len(PARITY_STOCKS))))
    stock = {symbol: Instrument(symbol, "IDX", IDR) for symbol in stocks}
    prices = {
        symbol: draw.choice((draw.randrange(50, 1_000), draw.randrange(1_000, 50_000)))
        for symbol in stocks
    }
    held = {
        symbol: draw.randrange(1, 300) * 100 + draw.choice((0, 0, 0, 50))
        for symbol in stocks
        if draw.random() < HELD
    }
    raw = {symbol: draw.randrange(1_000) for symbol in stocks if draw.random() < WEIGHTED}
    total = sum(raw.values()) or 1
    scale = Decimal(draw.choice(("0.5", "0.9", "1")))
    weights = {symbol: Decimal(share) / total * scale for symbol, share in raw.items()}
    worth = {symbol: prices[symbol] * shares for symbol, shares in held.items()}
    cash = draw.choice((0, draw.randrange(10**7), draw.randrange(10**10)))
    value = cash + sum(worth.values())
    for symbol in weights:
        if value and draw.random() < ON_AN_EDGE:
            weights[symbol] = Decimal(draw.randrange(1, 50) * prices[symbol] * 100) / value
    spendable = draw.choice((cash, cash // 2, 0))
    limits = {"max_weight": draw.choice(MAX_WEIGHTS), "min_lots": str(draw.randint(1, 3))}
    members = [symbol for symbol in stocks if draw.random() < MEMBER]
    reasons: dict[str, dict[str, str]] = {}
    for symbol in stocks:
        roll = draw.random()
        if roll < FROZEN:
            reasons[symbol] = {"code": TRADE_FROZEN, "text": draw.choice(FLAGS)}
        elif roll < KEPT_OUT:
            reasons[symbol] = {"code": TRADE_EXCLUDED, "text": "excluded: the user's own reason"}
    view = PortfolioView(
        Money(value, IDR),
        Money(spendable, IDR),
        {stock[symbol]: Money(amount, IDR) for symbol, amount in worth.items()},
    )
    tradable = Tradable(
        PARITY_DAY,
        frozenset(stock[symbol] for symbol in members if symbol not in reasons),
        frozenset(stock[symbol] for symbol in held if symbol not in reasons),
        {stock[symbol]: Note(note["code"], note["text"]) for symbol, note in reasons.items()},
        frozenset(stock[symbol] for symbol in members),
    )
    money = {stock[symbol]: Money(price, IDR) for symbol, price in prices.items()}
    shares = {stock[symbol]: amount for symbol, amount in held.items()}
    weighted = {stock[symbol]: weight for symbol, weight in weights.items()}
    sized = CompoundingSizer(rules).size(weighted, view, shares, money, PARITY_DAY)
    extra = [
        Order(
            stock[draw.choice(stocks)],
            draw.choice(list(Side)),
            draw.randrange(1, 50) * 100,
            PARITY_DAY,
        )
        for _ in range(draw.choice((0, 0, 1, 2)))
    ]
    risk = RiskManager(
        rules, RiskLimits(Decimal(limits["max_weight"]), min_lots=int(limits["min_lots"]))
    )
    checked = risk.check([*sized, *extra], view, tradable, money)
    return {
        "name": name,
        "day": PARITY_DAY.isoformat(),
        "prices": {symbol: str(price) for symbol, price in prices.items()},
        "held": {symbol: str(amount) for symbol, amount in held.items()},
        "weights": {symbol: str(weight) for symbol, weight in weights.items()},
        "value": str(view.value.amount),
        "spendable": str(spendable),
        "holdings": {symbol: str(amount) for symbol, amount in worth.items()},
        "limits": limits,
        "extra": [_order(order) for order in extra],
        "members": members,
        "reasons": reasons,
        "expected": {
            "sized": [_order(order) for order in sized],
            "orders": [_order(order) for order in checked.orders],
            "rejected": [
                {"order": _order(r.order), "code": r.reason.key, "text": r.reason.text}
                for r in checked.rejected
            ],
            "cuts": [
                {
                    "order": _order(c.order),
                    "quantity": str(c.quantity),
                    "code": c.reason.key,
                    "text": c.reason.text,
                }
                for c in checked.cuts
            ],
        },
    }


def parity_cases(seed: int = PARITY_SEED, count: int = PARITY_CASES) -> ParityCases:
    """*count* cases drawn from *seed*, each with Python's answer (spec §14.4)."""
    if count < 1:
        msg = f"the parity harness needs a case, got {count}"
        raise ValueError(msg)
    draw = random.Random(seed)  # noqa: S311 - seeded test inputs, not secrets
    rules = IdxMarketRules()
    return {
        "seed": str(seed),
        "cases": [_parity_case(draw, rules, f"case {n}") for n in range(count)],
    }


STRATEGY_SEED = 229
STRATEGY_JOURNEYS = 60
# The instalments a monthly-savings journey may draw: the bounds Settings allows and between.
INSTALMENT_CHOICES = (1, 2, 3, 12, 24, 120)


def _strategy_day(
    draw: random.Random,
    strategy: Strategy,
    day: date,
    memory: dict[str, str],
    pay_dates: PayDates,
) -> dict[str, Any]:
    """One advice day of a journey: a drawn portfolio and buyable set, the memory the day before
    ended with, and what Python's strategy decides."""
    buyable = sorted(draw.sample(PARITY_STOCKS, draw.randint(0, len(PARITY_STOCKS))))
    held = {symbol: draw.randrange(1, 10**9) for symbol in PARITY_STOCKS if draw.random() < HELD}
    spendable = draw.choice((0, draw.randrange(10**6), draw.randrange(10**10)))
    unsettled = draw.choice((0, draw.randrange(10**6)))
    stock = {symbol: Instrument(symbol, "IDX", IDR) for symbol in PARITY_STOCKS}
    portfolio = PortfolioView(
        Money(spendable + unsettled + sum(held.values()), IDR),
        Money(spendable, IDR),
        {stock[symbol]: Money(amount, IDR) for symbol, amount in held.items()},
    )
    chosen = frozenset(stock[symbol] for symbol in buyable)
    view = MarketView(
        PriceHistory([]),
        day,
        Tradable(day, chosen, frozenset(), {}, chosen),
        ActionHistory(),
        pay_dates,
    )
    decision = strategy.decide(view, portfolio, memory)
    return {
        "day": day.isoformat(),
        "buyable": buyable,
        "holdings": {symbol: str(amount) for symbol, amount in held.items()},
        "value": str(portfolio.value.amount),
        "spendable": str(spendable),
        "memory": dict(memory),
        "expected": {
            "weights": dict(sorted((i.symbol, str(w)) for i, w in decision.weights.items())),
            "memory": dict(decision.memory),
            "notes": [{"code": n.key, "text": n.text} for n in decision.notes],
        },
    }


def strategy_cases(seed: int = STRATEGY_SEED, journeys: int = STRATEGY_JOURNEYS) -> ParityCases:
    """*journeys* runs of buy-and-hold and monthly-savings drawn from *seed* (#229 AC6): each a few
    advice days, days or months apart, each day starting from the memory the last one ended with,
    as the extension advises. Every day is a case."""
    if journeys < 1:
        msg = f"the strategy parity harness needs a journey, got {journeys}"
        raise ValueError(msg)
    draw = random.Random(seed)  # noqa: S311 - seeded test inputs, not secrets
    pay_dates = PayDates(IdxMarketRules(), 14)
    cases: list[dict[str, Any]] = []
    for journey in range(journeys):
        instalments = draw.choice(INSTALMENT_CHOICES)
        strategy: Strategy = draw.choice((BuyAndHold(), MonthlySavings(instalments)))
        day = date(2025, 1, 1) + timedelta(days=draw.randrange(365))
        memory: dict[str, str] = {}
        for step in range(draw.randint(1, 6)):
            case = _strategy_day(draw, strategy, day, memory, pay_dates)
            case = {
                "name": f"journey {journey} day {step}",
                "strategy": strategy.name,
                "instalments": str(instalments),
                **case,
            }
            cases.append(case)
            memory = case["expected"]["memory"]
            day += timedelta(days=draw.choice((0, 1, 3, 20, 31, 45)))
    return {"seed": str(seed), "cases": cases}


GROWTH_SEED = 230
GROWTH_JOURNEYS = 30
# The gaps between a journey's advice days: the same day, the next, a month or more within a
# year, and into the next year, where a review falls.
GROWTH_STEPS = (0, 1, 30, 200, 365)


def _growth_actions(draw: random.Random, day: date) -> dict[str, list[CashDividend | Split]]:
    """Every stock's dividends and splits for a journey starting on *day*."""
    actions: dict[str, list[CashDividend | Split]] = {}
    for symbol in PARITY_STOCKS:
        stock = Instrument(symbol, "IDX", IDR)
        level = Decimal(draw.randrange(5, 500))
        record: list[CashDividend | Split] = []
        each_year = draw.choice((1, 1, 2))
        for year in range(day.year - 4, day.year + 2):
            if draw.random() < 0.08:  # noqa: PLR2004 - a year with no dividend
                level = level * Decimal(draw.choice(("0.97", "1", "1.05")))
                continue
            for _ in range(each_year):
                ex_date = date(year, 1, 1) + timedelta(days=draw.randrange(365))
                share = (level * Decimal(draw.choice(("0.9", "1", "1")))).quantize(Decimal("0.01"))
                record.append(CashDividend(stock, ex_date, share))
            level = level * Decimal(draw.choice(("0.9", "1", "1.02", "1.05", "1.1")))
        if draw.random() < 0.3:  # noqa: PLR2004 - a split somewhere in the record
            ex_date = date(day.year - 4, 1, 1) + timedelta(days=draw.randrange(365 * 6))
            record.append(Split(stock, ex_date, *draw.sample(SPLIT_SHARES, 2)))
        actions[symbol] = record
    return actions


@dataclass(frozen=True, slots=True)
class _GrowthJourney:
    """What stays the same across a dividend-growth journey's days."""

    strategy: DividendGrowthStrategy
    actions: dict[str, list[CashDividend | Split]]
    pay_dates: PayDates


def _growth_day(
    draw: random.Random, journey: _GrowthJourney, day: date, memory: dict[str, str]
) -> dict[str, Any]:
    """One advice day of a dividend-growth journey: a drawn universe, buyable set, portfolio and
    closes, every stock's record, and what Python's strategy decides."""
    strategy, actions, pay_dates = journey.strategy, journey.actions, journey.pay_dates
    members = sorted(draw.sample(PARITY_STOCKS, draw.randint(3, len(PARITY_STOCKS))))
    buyable = sorted(symbol for symbol in members if draw.random() < 0.8)  # noqa: PLR2004
    held = {symbol: draw.randrange(1, 10**9) for symbol in PARITY_STOCKS if draw.random() < HELD}
    spendable = draw.choice((0, draw.randrange(10**6), draw.randrange(10**10)))
    closes = {
        symbol: draw.randrange(50, 50_000)
        for symbol in PARITY_STOCKS
        if draw.random() < 0.9  # noqa: PLR2004
    }
    stock = {symbol: Instrument(symbol, "IDX", IDR) for symbol in PARITY_STOCKS}
    portfolio = PortfolioView(
        Money(spendable + sum(held.values()), IDR),
        Money(spendable, IDR),
        {stock[symbol]: Money(amount, IDR) for symbol, amount in held.items()},
    )
    price_of = {symbol: Money(price, IDR) for symbol, price in closes.items()}
    bars = [
        Bar(stock[symbol], day, price, price, price, price, 1_000)
        for symbol, price in price_of.items()
    ]
    view = MarketView(
        PriceHistory(bars),
        day,
        Tradable(
            day,
            frozenset(stock[symbol] for symbol in buyable),
            frozenset(),
            {},
            frozenset(stock[symbol] for symbol in members),
        ),
        ActionHistory([action for record in actions.values() for action in record]),
        pay_dates,
    )
    decision = strategy.decide(view, portfolio, memory)
    # Between reviews it reads no dividends, so only a review day carries the record.
    read = memory.get("year") != str(day.year)
    every = [action for record in actions.values() for action in record] if read else []
    dividends = [action for action in every if isinstance(action, CashDividend)]
    splits = [action for action in every if isinstance(action, Split)]
    return {
        "day": day.isoformat(),
        "members": members,
        "buyable": buyable,
        "holdings": {symbol: str(amount) for symbol, amount in held.items()},
        "value": str(portfolio.value.amount),
        "spendable": str(spendable),
        "closes": {symbol: str(price) for symbol, price in closes.items()},
        "dividends": [
            {
                "symbol": dividend.instrument.symbol,
                "exDate": dividend.ex_date.isoformat(),
                "paymentDate": pay_dates.of(dividend.ex_date).isoformat(),
                "grossPerShare": str(dividend.per_share),
            }
            for dividend in dividends
        ],
        "splits": [
            {
                "symbol": split.instrument.symbol,
                "exDate": split.ex_date.isoformat(),
                "from": str(split.old_shares),
                "to": str(split.new_shares),
            }
            for split in splits
        ],
        "read": read,
        "memory": dict(memory),
        "expected": {
            "weights": dict(sorted((i.symbol, str(w)) for i, w in decision.weights.items())),
            "memory": dict(decision.memory),
            "notes": [{"code": n.key, "text": n.text} for n in decision.notes],
        },
    }


def growth_cases(seed: int = GROWTH_SEED, journeys: int = GROWTH_JOURNEYS) -> ParityCases:
    """*journeys* runs of dividend-growth drawn from *seed* (#230 AC5): each a few advice days,
    each day starting from the memory the last one ended with, with settings drawn small enough
    that a review sometimes has more passers than ``max_stocks`` and sometimes fewer than
    ``min_stocks``. Every day is a case."""
    if journeys < 1:
        msg = f"the dividend-growth parity harness needs a journey, got {journeys}"
        raise ValueError(msg)
    draw = random.Random(seed)  # noqa: S311 - seeded test inputs, not secrets
    pay_dates = PayDates(IdxMarketRules(), 14)
    cases: list[dict[str, Any]] = []
    for journey in range(journeys):
        min_stocks = draw.randint(1, 2)
        strategy = DividendGrowthStrategy(
            min_stocks, draw.randint(min_stocks, min_stocks + 1), draw.randint(1, 3)
        )
        day = date(2024, 1, 1) + timedelta(days=draw.randrange(365))
        journey_days = _GrowthJourney(strategy, _growth_actions(draw, day), pay_dates)
        memory: dict[str, str] = {}
        for step in range(draw.randint(1, 4)):
            case = _growth_day(draw, journey_days, day, memory)
            case = {
                "name": f"journey {journey} day {step}",
                "minStocks": str(strategy.min_stocks),
                "maxStocks": str(strategy.max_stocks),
                "growthYears": str(strategy.growth_years),
                **case,
            }
            cases.append(case)
            memory = case["expected"]["memory"]
            day += timedelta(days=draw.choice(GROWTH_STEPS))
    return {"seed": str(seed), "cases": cases}


RESTATED_SEED = 232
RESTATED_CASES = 300
# The share counts a drawn split may turn from and into: forward, reverse and odd ratios.
SPLIT_SHARES = (1, 2, 3, 4, 5, 10)


def _restated_case(draw: random.Random, name: str) -> dict[str, Any]:
    """A dividend, its stock's splits around it and a day it is read for, and the gross Python's
    ``_restated_gross`` gives on a number of today's shares (#232 AC4)."""
    stock = Instrument("BBCA", "IDX", IDR)
    other = Instrument("TLKM", "IDX", IDR)
    start = date(2024, 1, 1)
    ex_date = start + timedelta(days=draw.randrange(400))
    places = draw.choice((0, 1, 2, 4))
    per_share = Decimal(draw.randrange(1, 10**6)) / 10**places
    splits = [
        Split(
            draw.choice((stock, stock, stock, other)),
            start + timedelta(days=draw.randrange(800)),
            *draw.sample(SPLIT_SHARES, 2),
        )
        for _ in range(draw.randint(0, 3))
    ]
    as_of = ex_date + timedelta(days=draw.randrange(400))
    shares = draw.choice((1, draw.randrange(1, 10**4), draw.randrange(1, 10**9)))
    # Python's callers pass one stock's own actions; core is handed every split and picks the
    # dividend stock's, so Python is given the stock's splits alone.
    own = [split for split in splits if split.instrument == stock]
    gross = _restated_gross(CashDividend(stock, ex_date, per_share), shares, own, as_of)
    return {
        "name": name,
        "exDate": ex_date.isoformat(),
        "grossPerShare": str(per_share),
        "shares": str(shares),
        "splits": [
            {
                "symbol": split.instrument.symbol,
                "exDate": split.ex_date.isoformat(),
                "from": str(split.old_shares),
                "to": str(split.new_shares),
            }
            for split in splits
        ],
        "asOf": as_of.isoformat(),
        "gross": str(gross.amount),
    }


def restated_cases(seed: int = RESTATED_SEED, count: int = RESTATED_CASES) -> ParityCases:
    """*count* dividends restated by Python from *seed*, for core's ``restatedGross``."""
    if count < 1:
        msg = f"the restated parity harness needs a case, got {count}"
        raise ValueError(msg)
    draw = random.Random(seed)  # noqa: S311 - seeded test inputs, not secrets
    return {"seed": str(seed), "cases": [_restated_case(draw, f"case {n}") for n in range(count)]}


INCOME_SEED = 237
INCOME_CASES = 150
INCOME_STOCKS = ("BBCA", "BBRI", "TLKM", "ASII", "UNVR")
INCOME_BOUGHT = date(2022, 1, 3)
# How many of the holdings also split inside the window.
INCOME_SPLITS = 0.3


def _income_case(draw: random.Random, name: str) -> dict[str, Any]:
    """Holdings with dividends around the trailing year and splits after some of them, and the
    run rate, goal share and payment calendar Python's ``run_rate``, ``_share`` and
    ``payment_calendar`` give (spec §9, #237). Each dividend's payment date is the one Python
    models, which core reads from the broker instead."""
    rules = IdxMarketRules()
    calendar = IdxCalendar.shipped()
    as_of = date(2023, 6, 1) + timedelta(days=draw.randrange(700))
    book = Portfolio.empty(IDR)
    history: dict[Instrument, list[CashDividend | Split]] = {}
    stocks: list[dict[str, Any]] = []
    for symbol in sorted(draw.sample(INCOME_STOCKS, draw.randrange(0, 4))):
        stock = Instrument(symbol, "IDX", IDR)
        shares = draw.choice((1, draw.randrange(1, 10**4), draw.randrange(1, 10**7)))
        order = Order(stock, Side.BUY, shares, INCOME_BOUGHT)
        fill = Fill(order, INCOME_BOUGHT, shares, Money(1, IDR), Costs.zero(IDR))
        book = book.deposit(Money(shares, IDR), INCOME_BOUGHT).apply_fill(fill, INCOME_BOUGHT)
        actions: list[CashDividend | Split] = []
        for _ in range(draw.randrange(0, 5)):
            ex_date = as_of - timedelta(days=draw.randrange(-30, 450))
            cents = draw.choice((draw.randrange(1, 100), draw.randrange(1, 50_000)))
            actions.append(CashDividend(stock, ex_date, Decimal(cents) / 100))
        if draw.random() < INCOME_SPLITS:
            ex_date = as_of - timedelta(days=draw.randrange(0, 400))
            actions.append(Split(stock, ex_date, 1, draw.choice((2, 5, 10))))
        history[stock] = actions
        stocks.append(
            {
                "symbol": symbol,
                "shares": str(shares),
                "dividends": [
                    {
                        "exDate": action.ex_date.isoformat(),
                        "paymentDate": calendar.add_trading_days(
                            action.ex_date, PAY_LAG_TRADING_DAYS
                        ).isoformat(),
                        "perShare": str(action.per_share),
                    }
                    for action in actions
                    if isinstance(action, CashDividend)
                ],
                "splits": [
                    {
                        "exDate": action.ex_date.isoformat(),
                        "from": "1",
                        "to": str(action.new_shares),
                    }
                    for action in actions
                    if isinstance(action, Split)
                ],
            }
        )
    rate = run_rate(book, history, rules, as_of, PAY_LAG_TRADING_DAYS)
    months = payment_calendar(rate, rules)
    target = Money(draw.randrange(1, 10**9), IDR)
    return {
        "name": name,
        "asOf": as_of.isoformat(),
        "target": str(target.amount),
        "stocks": stocks,
        "holdings": [
            [str(holding.annual_gross.amount), str(holding.monthly_take_home.amount)]
            for holding in rate.holdings
        ],
        "annualGross": str(rate.annual_gross.amount),
        "monthlyTakeHome": str(rate.monthly_take_home.amount),
        "share": str(_share(rate.monthly_take_home, target)),
        "months": [str(month.amount) for month in months.months],
        "emptyMonths": str(months.empty_months),
        "evenness": None if months.evenness is None else str(months.evenness),
    }


def income_cases(seed: int = INCOME_SEED, count: int = INCOME_CASES) -> ParityCases:
    """*count* portfolios drawn from *seed*, each with Python's run rate, goal share and payment
    calendar, for core's ``runRate``, ``goalProgress`` and ``paymentCalendar``."""
    if count < 1:
        msg = f"the income parity harness needs a case, got {count}"
        raise ValueError(msg)
    draw = random.Random(seed)  # noqa: S311 - seeded test inputs, not secrets
    return {"seed": str(seed), "cases": [_income_case(draw, f"case {n}") for n in range(count)]}


PROJECTION_SEED = 254
PROJECTION_CASES = 80
# Each year's dividend a share against the year before, as a factor: falls, steady growth and
# growth past the optimistic cap.
PROJECTION_GROWTH = (
    (Decimal("0.70"), Decimal("0.98")),
    (Decimal("1.00"), Decimal("1.06")),
    (Decimal("1.08"), Decimal("1.40")),
)
PROJECTION_SHORT = 0.2
PROJECTION_NO_VALUE = 0.1
PROJECTION_OUTCOMES = {
    ProjectionOutcome.REACHED: "reached",
    ProjectionOutcome.NOT_WITHIN: "not-within",
    ProjectionOutcome.CANNOT: "cannot",
}


def _projection_case(draw: random.Random, name: str) -> dict[str, Any]:
    """Holdings with five years of dividends, some growing, some falling, some with nothing in
    the earlier year, and a split between the years for some, with the dividend growth and
    projection Python's ``dividend_growth`` and ``project`` give (spec §9.1, #254)."""
    rules = IdxMarketRules()
    calendar = IdxCalendar.shipped()
    as_of = date(2024, 6, 1) + timedelta(days=draw.randrange(500))
    since = years_before(as_of, HISTORY_YEARS)
    book = Portfolio.empty(IDR)
    history: dict[Instrument, list[CashDividend | Split]] = {}
    stocks: list[dict[str, Any]] = []
    for symbol in sorted(draw.sample(INCOME_STOCKS, draw.randrange(0, 4))):
        stock = Instrument(symbol, "IDX", IDR)
        shares = draw.choice((1, draw.randrange(1, 10**4), draw.randrange(1, 10**7)))
        order = Order(stock, Side.BUY, shares, INCOME_BOUGHT)
        fill = Fill(order, INCOME_BOUGHT, shares, Money(1, IDR), Costs.zero(IDR))
        book = book.deposit(Money(shares, IDR), INCOME_BOUGHT).apply_fill(fill, INCOME_BOUGHT)
        low, high = draw.choice(PROJECTION_GROWTH)
        per_share = Decimal(draw.choice((draw.randrange(1, 100), draw.randrange(100, 50_000))))
        first_year = 2 if draw.random() < PROJECTION_SHORT else 0
        actions: list[CashDividend | Split] = []
        for year in range(first_year, HISTORY_YEARS):
            factor = low + (high - low) * Decimal(draw.randrange(101)) / 100
            per_share = (per_share * factor).quantize(Decimal("0.01"))
            for _ in range(draw.randrange(1, 3)):
                day = since + timedelta(days=365 * year + draw.randrange(365))
                if day <= as_of and per_share > 0:
                    actions.append(CashDividend(stock, day, per_share / 100))
        if draw.random() < INCOME_SPLITS:
            ex_date = as_of - timedelta(days=draw.randrange(0, 4 * 365))
            actions.append(Split(stock, ex_date, 1, draw.choice((2, 5, 10))))
        history[stock] = actions
        stocks.append(
            {
                "symbol": symbol,
                "shares": str(shares),
                "dividends": [
                    {
                        "exDate": action.ex_date.isoformat(),
                        "paymentDate": calendar.add_trading_days(
                            action.ex_date, PAY_LAG_TRADING_DAYS
                        ).isoformat(),
                        "perShare": str(action.per_share),
                    }
                    for action in actions
                    if isinstance(action, CashDividend)
                ],
                "splits": [
                    {
                        "exDate": action.ex_date.isoformat(),
                        "from": "1",
                        "to": str(action.new_shares),
                    }
                    for action in actions
                    if isinstance(action, Split)
                ],
            }
        )
    rate = run_rate(book, history, rules, as_of, PAY_LAG_TRADING_DAYS)
    growth = dividend_growth(rate, history)
    value = Money(0 if draw.random() < PROJECTION_NO_VALUE else draw.randrange(10**5, 10**11), IDR)
    target = Money(draw.choice((1, draw.randrange(1, 10**7), draw.randrange(10**7, 10**12))), IDR)
    given = draw.choice((None, Money(draw.randrange(1, 10**8), IDR)))
    projection = project(rate, growth, value, IncomeSettings(IncomeGoal(target), given), rules)
    return {
        "name": name,
        "asOf": as_of.isoformat(),
        "holdingsValue": str(value.amount),
        "target": str(target.amount),
        "contribution": str(projection.contribution.amount),
        "stocks": stocks,
        "growth": [
            [found.instrument.symbol, str(found.recent), str(found.earlier), str(found.growth)]
            for found in growth.holdings
        ],
        "portfolioGrowth": str(growth.portfolio),
        "shortHistory": [
            note.text.split(":")[0]
            for note in growth.notes
            if note.key == INCOME_GROWTH_SHORT_HISTORY
        ],
        "scenarios": [
            {
                "scenario": found.scenario.value,
                "start": str(found.starting_gross.amount),
                "growth": str(found.growth),
                "outcome": PROJECTION_OUTCOMES[found.outcome],
                "years": None if found.years is None else str(found.years),
            }
            for found in projection.scenarios
        ],
    }


def projection_cases(seed: int = PROJECTION_SEED, count: int = PROJECTION_CASES) -> ParityCases:
    """*count* portfolios drawn from *seed*, each with Python's dividend growth and projection,
    for core's ``incomeGrowth`` and ``project``."""
    if count < 1:
        msg = f"the projection parity harness needs a case, got {count}"
        raise ValueError(msg)
    draw = random.Random(seed)  # noqa: S311 - seeded test inputs, not secrets
    return {
        "seed": str(seed),
        "cases": [_projection_case(draw, f"case {n}") for n in range(count)],
    }


HALT_SEED = 236
HALT_JOURNEYS = 60
# Each draw's daily move of the market value, as a factor: mostly small, with falls large enough
# to reach a daily loss limit and runs of small falls that reach a drawdown.
# How often a run changes its kind of move, and how many of its cash movements are deposits.
HALT_SWITCH = 0.2
HALT_DEPOSITS = 0.6
HALT_MOVES = (
    (Decimal("0.97"), Decimal("1.03")),
    (Decimal("0.90"), Decimal("0.97")),
    (Decimal("0.96"), Decimal("1.00")),
)


def _halt_journey(draw: random.Random, name: str) -> dict[str, Any]:
    """After-close reads on trading days, some days skipped, with deposits and withdrawals on
    calendar days between them, and the unit value and the first halt Python's `UnitValue` and
    `RiskManager.halt` give (spec §8, #236). A move dated on a read's day is in that read."""
    calendar = IdxCalendar.shipped()
    limits = RiskLimits(
        daily_loss=draw.choice((Decimal("0.03"), Decimal("0.05"), Decimal("0.1"))),
        max_drawdown=draw.choice((Decimal("0.15"), Decimal("0.25"))),
    )
    manager = RiskManager(IdxMarketRules(), limits)
    day = calendar.next_trading_day(date(2023, 1, 2) + timedelta(days=draw.randrange(900)))
    market = draw.choice((10**6, 10**8, draw.randrange(1, 10**11)))
    reads = [{"day": day.isoformat(), "value": str(market)}]
    movements: list[dict[str, str]] = []
    units = UnitValue().deposit(Money(market, IDR))
    halt: dict[str, str] | None = None
    low, high = draw.choice(HALT_MOVES)
    for _ in range(draw.randrange(3, 16)):
        if draw.random() < HALT_SWITCH:
            low, high = draw.choice(HALT_MOVES)
        previous = day
        day = calendar.add_trading_days(day, draw.choice((1, 1, 1, 2, 3)))
        factor = low + (high - low) * Decimal(draw.randrange(10**6)) / Decimal(10**6)
        market = int(market * factor)
        net = 0
        for _ in range(draw.choice((0, 0, 1, 2))):
            on = previous + timedelta(days=draw.randrange(1, (day - previous).days + 1))
            if draw.random() < HALT_DEPOSITS:
                amount = draw.randrange(1, max(2, market // 5))
                kind = "deposit"
                net += amount
            else:
                amount = draw.randrange(1, max(2, market // 10))
                kind = "withdrawal"
                net -= amount
            movements.append({"day": on.isoformat(), "kind": kind, "amount": str(amount)})
        value = market + net
        reads.append({"day": day.isoformat(), "value": str(value)})
        after = units.revalue(Money(market, IDR))
        if halt is None:
            found = manager.halt(units, after, day)
            if found is not None:
                gap = calendar.previous_trading_day(day) != previous
                halt = {"day": day.isoformat(), "code": found.cause.key}
                if not gap:
                    halt["text"] = found.cause.text
        units = after.deposit(Money(net, IDR))
        market = value
    return {
        "name": name,
        "dailyLoss": str(limits.daily_loss),
        "maxDrawdown": str(limits.max_drawdown),
        "reads": reads,
        "movements": movements,
        "units": str(units.units),
        "price": str(units.price),
        "highWater": str(units.high_water),
        "halt": halt,
    }


def halt_cases(seed: int = HALT_SEED, journeys: int = HALT_JOURNEYS) -> ParityCases:
    """*journeys* runs of after-close reads drawn from *seed*, each with Python's unit value and
    first halt, for core's ``riskState``."""
    if journeys < 1:
        msg = f"the halt parity harness needs a journey, got {journeys}"
        raise ValueError(msg)
    draw = random.Random(seed)  # noqa: S311 - seeded test inputs, not secrets
    return {
        "seed": str(seed),
        "cases": [_halt_journey(draw, f"journey {n}") for n in range(journeys)],
    }


def text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def one_case_a_line(document: ParityCases) -> str:
    """The parity fixture with each case on a line of its own: 57% of the size of indented JSON
    (measured 2026-11-02), and a changed case is one changed line."""
    lines = ",\n".join(json.dumps(case, ensure_ascii=False) for case in document["cases"])
    return f'{{"seed": {json.dumps(document["seed"])}, "cases": [\n{lines}\n]}}\n'


def outputs() -> dict[Path, str]:
    """Every file this script writes, by its path from the repository root."""
    files = {path: text(document) for path, document in rule_files().items()}
    files[RATIOS] = text(ratio_cases())
    files[RULES_CASES] = text(rule_cases())
    files[PARITY] = one_case_a_line(parity_cases())
    files[STRATEGY_PARITY] = one_case_a_line(strategy_cases())
    files[RESTATED_PARITY] = one_case_a_line(restated_cases())
    files[GROWTH_PARITY] = one_case_a_line(growth_cases())
    files[INCOME_PARITY] = one_case_a_line(income_cases())
    files[PROJECTION_PARITY] = one_case_a_line(projection_cases())
    files[HALT_PARITY] = one_case_a_line(halt_cases())
    return files


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="where to write the files")
    root: Path = parser.parse_args(argv).root
    for path, content in outputs().items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
