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
        _require_rupiah(gross, "gross")
        rates = self.percentages(preset, side, on)
        total = gross.times((rates.fee + rates.levy + rates.tax) / _HUNDRED, Rounding.UP)
        levy = gross.times(rates.levy / _HUNDRED, Rounding.DOWN)
        tax = gross.times(rates.tax / _HUNDRED, Rounding.DOWN)
        return Costs(fee=total - levy - tax, levy=levy, tax=tax)

    def daily_costs(self, traded: Money, on: date) -> Money:
        """Stamp duty on the day's trade confirmation, given the day's buys plus sells."""
        _require_rupiah(traded, "traded")
        duty = self.stamp_duty.on(on)
        if traded.amount <= duty.exempt_up_to:
            return Money.zero(IDR)
        return Money(duty.amount, IDR)

    def dividend_tax(self, gross: Money, *, reinvested_by_deadline: bool, on: date) -> Money:
        """10% of a gross dividend, or nothing when it is reinvested by the deadline.

        M4 replaces the flag with a read of the dividend's exemption claim (spec §6.2).
        """
        _require_rupiah(gross, "gross")
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


def _require_rupiah(money: Money, name: str) -> None:
    if money.currency != IDR or money.amount < 0:
        msg = f"{name} must be a non-negative IDR amount, got {money}"
        raise ValueError(msg)


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
