"""``steadyhand.toml``: the operator's settings, loaded and checked (M5 spec §4.2, core spec §9.5).

Every key but ``[consent] disclaimer_accepted`` is optional and takes the value ``KEYS`` gives it.
An unknown key, a wrong type or an out-of-range value is a ``DataFileError`` that names the table
and the key. Rates are strings parsed to ``Decimal``, so a TOML float is refused.

The ``[training]`` table is carried on unread: ``steadyhand_idx.output`` parses it (T1 spec §5
item 3), so this module, which every command reads, never imports training.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Final, cast

from steadyhand import (
    IDR,
    STRATEGIES,
    BacktestSettings,
    EngineSettings,
    FillSettings,
    IncomeGoal,
    Money,
    RiskLimits,
)
from steadyhand_idx._datafile import (
    DataFileError,
    Row,
    Where,
    get_date,
    get_decimal,
    get_int,
    get_str,
    load_path,
    only_keys,
)
from steadyhand_idx.fees import FeeSchedule
from steadyhand_idx.paths import APP

EXCLUSIONS_FILE: Final = "exclusions.csv"
"""The operator's exclusions, in the data directory; no file means none (core spec §9.4)."""

MAX_PAY_LAG: Final = 250
"""A pay lag longer than a trading year is a typing mistake, not a dividend."""


@dataclass(frozen=True, slots=True)
class Key:
    """One setting: its name, the value it takes when it is left out, and the comment ``init``
    writes above it. ``default`` is ``None`` only for a key ``init`` fills in itself."""

    name: str
    default: int | str | bool | None
    comment: str


KEYS: Final[Mapping[str, tuple[Key, ...]]] = MappingProxyType(
    {
        "account": (
            Key(
                "starting_cash_idr",
                10_000_000,
                "The cash the paper account opens with, in whole rupiah. Used only at opening.",
            ),
            Key(
                "monthly_contribution_idr",
                0,
                "Cash added on the first trading day of each month, in whole rupiah; 0 adds none.",
            ),
            Key(
                "broker_fees",
                "custom",
                "Your broker's fee preset in steadyhand-idx's fees.toml, or \"custom\".",
            ),
        ),
        "goal": (
            Key(
                "monthly_income_target_idr",
                10_000_000,
                "The monthly take-home dividend income you are working towards, in whole rupiah.",
            ),
        ),
        "strategy": (
            Key("name", "buy-and-hold", "The strategy to run: see steadyhand-idx strategies."),
        ),
        "risk": (
            Key(
                "max_weight",
                "0.10",
                "The most one stock may be of the portfolio's value: above 0, at most 1.",
            ),
            Key(
                "daily_loss_limit",
                "0.05",
                "A fall this large in one day halts ordering: above 0, below 1.",
            ),
            Key(
                "max_drawdown",
                "0.25",
                "A fall this far below the high-water mark halts ordering: above 0, below 1.",
            ),
            Key(
                "max_volume_participation",
                "0.10",
                "The most of a day's traded volume one order may take: above 0, at most 1.",
            ),
        ),
        "universe": (
            Key(
                "lq45_members",
                "lq45_members.toml",
                "Your LQ45 membership file, relative to this folder. steadyhand ships none: "
                "docs/lq45-members.md says where IDX publishes each list.",
            ),
        ),
        "dividends": (
            Key(
                "pay_lag_trading_days",
                14,
                f"Trading days from a dividend's ex-date to its payment: 1 to {MAX_PAY_LAG}.",
            ),
        ),
        "tax": (
            Key(
                "dividend_reinvestment_exemption",
                default=False,
                comment="Claim the dividend reinvestment exemption, as an estimate: true or false.",
            ),
        ),
        "training": (
            Key(
                "level",
                "new",
                "How much each command explains: off, new, some or experienced.",
            ),
        ),
        "consent": (
            Key(
                "disclaimer_accepted",
                None,
                "The day you accepted the disclaimer. Written by init.",
            ),
        ),
    }
)
"""Every table and key ``steadyhand.toml`` may hold, in the order ``init`` writes them."""


class ConfigMissingError(LookupError):
    """There is no ``steadyhand.toml``: ``init`` has not run (M5 spec §4.2)."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"there is no configuration at {path}; run {APP} init first")
        self.path = path


@dataclass(frozen=True, slots=True)
class Config:
    """``steadyhand.toml``, checked. ``settings`` carries the engine settings, the starting cash
    and the income goal; ``training`` is the ``[training]`` table, unread."""

    path: Path
    settings: BacktestSettings
    broker_fees: str
    strategy: str
    lq45_members: Path
    exclusions: Path
    training: Mapping[str, object]
    disclaimer_accepted: date

    @property
    def data_dir(self) -> Path:
        """The directory the configuration is in, which holds everything else."""
        return self.path.parent


def load(path: Path) -> Config:
    """Read and check the configuration at *path*."""
    try:
        document = load_path(path)
    except FileNotFoundError:
        raise ConfigMissingError(path) from None
    file = path.name
    unknown = sorted(set(document) - set(KEYS))
    if unknown:
        msg = f"{file}: unknown table {unknown[0]!r}; the tables are {', '.join(KEYS)}"
        raise DataFileError(msg)
    tables = {name: _table(document, name, file) for name in KEYS}
    account, risk = tables["account"], tables["risk"]
    where = {name: Where(file, name) for name in KEYS}
    contribution = get_int(account, "monthly_contribution_idr", where["account"], minimum=0)
    engine = EngineSettings(
        fills=FillSettings(
            volume_cap=_rate(risk, "max_volume_participation", where["risk"], at_most_one=True)
        ),
        limits=RiskLimits(
            max_weight=_rate(risk, "max_weight", where["risk"], at_most_one=True),
            daily_loss=_rate(risk, "daily_loss_limit", where["risk"], at_most_one=False),
            max_drawdown=_rate(risk, "max_drawdown", where["risk"], at_most_one=False),
        ),
        monthly_contribution=Money(contribution, IDR) if contribution else None,
        pay_lag_trading_days=_pay_lag(tables["dividends"], where["dividends"]),
        dividend_reinvestment_exemption=_bool(
            tables["tax"], "dividend_reinvestment_exemption", where["tax"]
        ),
    )
    settings = BacktestSettings(
        capital=Money(get_int(account, "starting_cash_idr", where["account"], minimum=1), IDR),
        engine=engine,
        goal=IncomeGoal(
            Money(
                get_int(tables["goal"], "monthly_income_target_idr", where["goal"], minimum=1),
                IDR,
            )
        ),
    )
    return Config(
        path=path,
        settings=settings,
        broker_fees=_choice(
            account, "broker_fees", where["account"], FeeSchedule.shipped().presets
        ),
        strategy=_choice(tables["strategy"], "name", where["strategy"], STRATEGIES),
        lq45_members=path.parent / get_str(tables["universe"], "lq45_members", where["universe"]),
        exclusions=path.parent / EXCLUSIONS_FILE,
        training=MappingProxyType(dict(tables["training"])),
        disclaimer_accepted=_consent(tables["consent"], where["consent"]),
    )


def starter(level: str, *, exemption: bool, accepted: date) -> str:
    """The configuration ``init`` writes: every key, each under a one-line comment, with the
    training level and exemption switch chosen and the day the disclaimer was accepted."""
    chosen: dict[tuple[str, str], int | str | bool | date] = {
        ("training", "level"): level,
        ("tax", "dividend_reinvestment_exemption"): exemption,
        ("consent", "disclaimer_accepted"): accepted,
    }
    blocks = []
    for table, keys in KEYS.items():
        lines = [f"[{table}]"]
        for key in keys:
            if key.default is None:
                value = chosen[(table, key.name)]
            else:
                value = chosen.get((table, key.name), key.default)
            lines += [f"# {key.comment}", f"{key.name} = {_toml(value)}"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def _toml(value: int | str | date) -> str:
    """*value* as TOML. A ``bool`` is an ``int`` to the type checker, so it is caught first."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:_}"
    if isinstance(value, date):
        return value.isoformat()
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _table(document: Row, name: str, file: str) -> Row:
    """Table *name* with the defaults under what the file gives. The ``[training]`` table is
    only checked to be a table: ``steadyhand_idx.output`` reads it."""
    found = document.get(name, {})
    where = Where(file, name)
    if not isinstance(found, dict):
        msg = f"{where} must be a table, got {found!r}"
        raise DataFileError(msg)
    given = cast("Row", found)
    if name == "training":
        return given
    only_keys(given, [key.name for key in KEYS[name]], where)
    defaults = {key.name: key.default for key in KEYS[name] if key.default is not None}
    return {**defaults, **given}


def _rate(row: Row, key: str, where: Where, *, at_most_one: bool) -> Decimal:
    rate = get_decimal(row, key, where)
    upper = "at most 1" if at_most_one else "below 1"
    if rate <= 0 or rate > 1 or (rate == 1 and not at_most_one):
        msg = f'{where}: {key} must be above 0 and {upper}, got "{row[key]}"'
        raise DataFileError(msg)
    return rate


def _pay_lag(row: Row, where: Where) -> int:
    lag = get_int(row, "pay_lag_trading_days", where, minimum=1)
    if lag > MAX_PAY_LAG:
        msg = f"{where}: pay_lag_trading_days must be at most {MAX_PAY_LAG}, got {lag}"
        raise DataFileError(msg)
    return lag


def _bool(row: Row, key: str, where: Where) -> bool:
    value = row[key]
    if type(value) is not bool:
        msg = f"{where}: {key} must be true or false, got {value!r}"
        raise DataFileError(msg)
    return value


def _choice(row: Row, key: str, where: Where, known: Mapping[str, object]) -> str:
    value = get_str(row, key, where)
    if value not in known:
        msg = f"{where}: {key} must be one of {', '.join(sorted(known))}, got {value!r}"
        raise DataFileError(msg)
    return value


def _consent(row: Row, where: Where) -> date:
    if "disclaimer_accepted" not in row:
        msg = (
            f"{where}: missing key 'disclaimer_accepted', which {APP} init writes once the "
            "disclaimer is accepted"
        )
        raise DataFileError(msg)
    return get_date(row, "disclaimer_accepted", where)
