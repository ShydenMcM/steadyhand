"""``steadyhand.toml``: defaults, every validation rule and its boundaries (M5 spec §4.2)."""

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from steadyhand import (
    IDR,
    BacktestSettings,
    BuyAndHold,
    EngineSettings,
    FillSettings,
    IncomeGoal,
    Money,
    Registered,
    RiskLimits,
    Setting,
    Turnover,
)
from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.config import (
    KEYS,
    Config,
    ConfigMissingError,
    load,
    starter,
    strategy_keys,
)

ACCEPTED = date(2026, 9, 27)
CONSENT = "[consent]\ndisclaimer_accepted = 2026-09-27\n"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "steadyhand.toml"
    path.write_text(text, encoding="utf-8")
    return path


def load_text(tmp_path: Path, text: str) -> Config:
    return load(write(tmp_path, text))


def with_key(table: str, line: str) -> str:
    return f"[{table}]\n{line}\n\n{CONSENT}"


def test_a_file_with_only_the_consent_takes_every_default(tmp_path: Path) -> None:
    config = load_text(tmp_path, CONSENT)
    assert config.settings == BacktestSettings(
        capital=Money(10_000_000, IDR),
        engine=EngineSettings(
            fills=FillSettings(volume_cap=Decimal("0.10")),
            limits=RiskLimits(
                max_weight=Decimal("0.10"),
                daily_loss=Decimal("0.05"),
                max_drawdown=Decimal("0.25"),
            ),
            monthly_contribution=None,
            pay_lag_trading_days=14,
            dividend_reinvestment_exemption=False,
        ),
        goal=IncomeGoal(Money(10_000_000, IDR)),
    )
    assert config.broker_fees == "custom"
    assert config.strategy == "dividend-growth"
    assert config.strategy_settings == {
        "instalments": 12,
        "min_stocks": 15,
        "max_stocks": 25,
        "growth_years": 5,
    }
    assert config.lq45_members == tmp_path / "lq45_members.toml"
    assert config.exclusions == tmp_path / "exclusions.csv"
    assert config.training == {}
    assert config.disclaimer_accepted == ACCEPTED
    assert config.data_dir == tmp_path
    assert config.path == tmp_path / "steadyhand.toml"


def test_the_starter_file_loads_to_the_defaults_and_the_choices(tmp_path: Path) -> None:
    config = load_text(tmp_path, starter("some", exemption=True, accepted=ACCEPTED))
    defaults = load_text(tmp_path, CONSENT)
    assert config.settings.engine.dividend_reinvestment_exemption is True
    assert config.settings.capital == defaults.settings.capital
    assert config.settings.goal == defaults.settings.goal
    assert config.settings.engine.limits == defaults.settings.engine.limits
    assert config.settings.engine.fills == defaults.settings.engine.fills
    assert config.training == {"level": "some"}
    assert config.disclaimer_accepted == ACCEPTED


def test_the_starter_file_writes_every_key_under_its_comment() -> None:
    lines = starter("new", exemption=False, accepted=ACCEPTED).splitlines()
    written = 0
    for table, keys in KEYS.items():
        assert f"[{table}]" in lines
        for key in keys:
            (index,) = [i for i, line in enumerate(lines) if line.startswith(f"{key.name} = ")]
            assert lines[index - 1] == f"# {key.comment}"
            written += 1
    assert written == 18
    assert "# The months monthly-savings spreads the starting cash over: 1 to 120.\n" in "\n".join(
        lines
    )
    assert "instalments = 12" in lines
    assert 'name = "dividend-growth"' in lines
    (index,) = [i for i, line in enumerate(lines) if line == "max_stocks = 25"]
    assert lines[index - 1] == (
        "# The most stocks dividend-growth holds: 1 to 45, and at least min_stocks."
    )
    assert "min_stocks = 15" in lines
    assert "growth_years = 5" in lines


def test_the_starter_file_writes_toml_values_a_person_can_read() -> None:
    text = starter("experienced", exemption=False, accepted=ACCEPTED)
    assert "starting_cash_idr = 10_000_000\n" in text
    assert 'max_weight = "0.10"\n' in text
    assert "dividend_reinvestment_exemption = false\n" in text
    assert 'level = "experienced"\n' in text
    assert "disclaimer_accepted = 2026-09-27\n" in text
    assert text.endswith("disclaimer_accepted = 2026-09-27\n")


def test_a_quote_in_a_starter_value_is_escaped(tmp_path: Path) -> None:
    config = load_text(tmp_path, starter('a "b" \\ c', exemption=False, accepted=ACCEPTED))
    assert config.training == {"level": 'a "b" \\ c'}


def test_a_missing_file_means_init_has_not_run(tmp_path: Path) -> None:
    path = tmp_path / "steadyhand.toml"
    with pytest.raises(ConfigMissingError) as caught:
        load(path)
    assert str(caught.value) == (
        f"there is no configuration at {path}; run steadyhand-idx init first"
    )
    assert caught.value.path == path


def test_a_file_that_is_not_toml_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DataFileError, match=r"^steadyhand\.toml is not valid TOML: "):
        load_text(tmp_path, "[account\n")


def test_the_consent_is_required(tmp_path: Path) -> None:
    message = (
        "steadyhand.toml [consent]: missing key 'disclaimer_accepted', which steadyhand-idx "
        "init writes once the disclaimer is accepted"
    )
    with pytest.raises(DataFileError, match=f"^{re.escape(message)}$"):
        load_text(tmp_path, "[account]\nstarting_cash_idr = 5\n")
    with pytest.raises(DataFileError, match=f"^{re.escape(message)}$"):
        load_text(tmp_path, "[consent]\n")


def test_the_consent_is_a_date_not_a_time(tmp_path: Path) -> None:
    with pytest.raises(DataFileError, match=r"disclaimer_accepted must be a TOML date"):
        load_text(tmp_path, "[consent]\ndisclaimer_accepted = 2026-09-27T10:00:00\n")


def test_an_unknown_table_is_refused(tmp_path: Path) -> None:
    message = (
        "steadyhand.toml: unknown table 'acount'; the tables are account, goal, strategy, risk, "
        "universe, dividends, tax, training, consent"
    )
    with pytest.raises(DataFileError, match=f"^{re.escape(message)}$"):
        load_text(tmp_path, "[acount]\nstarting_cash_idr = 5\n" + CONSENT)


def test_a_key_outside_any_table_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DataFileError, match=r"^steadyhand\.toml: unknown table 'name'"):
        load_text(tmp_path, 'name = "x"\n' + CONSENT)


def test_an_unknown_key_is_refused(tmp_path: Path) -> None:
    with pytest.raises(
        DataFileError, match=r"^steadyhand\.toml \[risk\]: unknown key 'max_wieght'$"
    ):
        load_text(tmp_path, with_key("risk", 'max_wieght = "0.2"'))


def test_a_strategy_parameter_is_an_unknown_key_until_a_strategy_has_one(tmp_path: Path) -> None:
    with pytest.raises(DataFileError, match=r"\[strategy\]: unknown key 'lookback'$"):
        load_text(tmp_path, with_key("strategy", "lookback = 20"))


@pytest.mark.parametrize("table", ["risk", "training"])
def test_a_table_given_as_a_value_is_refused(tmp_path: Path, table: str) -> None:
    with pytest.raises(
        DataFileError, match=rf"^steadyhand\.toml \[{table}\] must be a table, got 3$"
    ):
        load_text(tmp_path, f"{table} = 3\n" + CONSENT)


GOOD: list[tuple[str, str, Callable[[Config], bool]]] = [
    ("account", "starting_cash_idr = 1", lambda c: c.settings.capital == Money(1, IDR)),
    (
        "account",
        "monthly_contribution_idr = 0",
        lambda c: c.settings.engine.monthly_contribution is None,
    ),
    (
        "account",
        "monthly_contribution_idr = 1",
        lambda c: c.settings.engine.monthly_contribution == Money(1, IDR),
    ),
    ("account", 'broker_fees = "ajaib"', lambda c: c.broker_fees == "ajaib"),
    (
        "goal",
        "monthly_income_target_idr = 1",
        lambda c: c.settings.goal == IncomeGoal(Money(1, IDR)),
    ),
    ("risk", 'max_weight = "1"', lambda c: c.settings.engine.limits.max_weight == 1),
    (
        "risk",
        'max_weight = "0.0001"',
        lambda c: c.settings.engine.limits.max_weight == Decimal("0.0001"),
    ),
    (
        "risk",
        'daily_loss_limit = "0.9999"',
        lambda c: c.settings.engine.limits.daily_loss == Decimal("0.9999"),
    ),
    (
        "risk",
        'max_drawdown = "0.9999"',
        lambda c: c.settings.engine.limits.max_drawdown == Decimal("0.9999"),
    ),
    ("risk", 'max_volume_participation = "1"', lambda c: c.settings.engine.fills.volume_cap == 1),
    (
        "dividends",
        "pay_lag_trading_days = 1",
        lambda c: c.settings.engine.pay_lag_trading_days == 1,
    ),
    (
        "dividends",
        "pay_lag_trading_days = 250",
        lambda c: c.settings.engine.pay_lag_trading_days == 250,
    ),
    (
        "tax",
        "dividend_reinvestment_exemption = true",
        lambda c: c.settings.engine.dividend_reinvestment_exemption,
    ),
    ("strategy", "instalments = 1", lambda c: c.strategy_settings["instalments"] == 1),
    ("strategy", "instalments = 120", lambda c: c.strategy_settings["instalments"] == 120),
    ("strategy", 'name = "monthly-savings"', lambda c: c.strategy == "monthly-savings"),
    ("strategy", 'name = "buy-and-hold"', lambda c: c.strategy == "buy-and-hold"),
    ("strategy", "min_stocks = 1", lambda c: c.strategy_settings["min_stocks"] == 1),
    # max_stocks equal to min_stocks is allowed: both at the default max, then the default min.
    ("strategy", "min_stocks = 25", lambda c: c.strategy_settings["min_stocks"] == 25),
    ("strategy", "max_stocks = 15", lambda c: c.strategy_settings["max_stocks"] == 15),
    ("strategy", "max_stocks = 45", lambda c: c.strategy_settings["max_stocks"] == 45),
    ("strategy", "growth_years = 1", lambda c: c.strategy_settings["growth_years"] == 1),
    ("strategy", "growth_years = 10", lambda c: c.strategy_settings["growth_years"] == 10),
]


@pytest.mark.parametrize(("table", "line", "check"), GOOD, ids=[line for _, line, _ in GOOD])
def test_each_value_at_its_boundary_is_accepted(
    tmp_path: Path, table: str, line: str, check: Callable[[Config], bool]
) -> None:
    config = load_text(tmp_path, with_key(table, line))
    assert check(config) is True


BAD = [
    (
        "account",
        "starting_cash_idr = 0",
        "starting_cash_idr must be an integer of at least 1, got 0",
    ),
    (
        "account",
        "starting_cash_idr = true",
        "starting_cash_idr must be an integer of at least 1, got True",
    ),
    (
        "account",
        'starting_cash_idr = "5"',
        "starting_cash_idr must be an integer of at least 1, got '5'",
    ),
    (
        "account",
        "starting_cash_idr = 5.0",
        "starting_cash_idr must be an integer of at least 1, got 5.0",
    ),
    (
        "account",
        "monthly_contribution_idr = -1",
        "monthly_contribution_idr must be an integer of at least 0, got -1",
    ),
    (
        "account",
        'broker_fees = "cheapest"',
        "broker_fees must be one of ajaib, custom, got 'cheapest'",
    ),
    ("account", 'broker_fees = ""', "broker_fees must be a non-empty string, got ''"),
    (
        "goal",
        "monthly_income_target_idr = 0",
        "monthly_income_target_idr must be an integer of at least 1, got 0",
    ),
    (
        "strategy",
        'name = "momentum"',
        "name must be one of buy-and-hold, dividend-growth, monthly-savings, got 'momentum'",
    ),
    ("strategy", "min_stocks = 0", "min_stocks must be an integer of at least 1, got 0"),
    ("strategy", "min_stocks = 46", "min_stocks must be at most 45, got 46"),
    ("strategy", "max_stocks = 0", "max_stocks must be an integer of at least 1, got 0"),
    ("strategy", "max_stocks = 46", "max_stocks must be at most 45, got 46"),
    ("strategy", "growth_years = 0", "growth_years must be an integer of at least 1, got 0"),
    ("strategy", "growth_years = 11", "growth_years must be at most 10, got 11"),
    # The rule across two settings names both, whichever one moved.
    ("strategy", "max_stocks = 14", "max_stocks must be at least min_stocks (15), got 14"),
    ("strategy", "min_stocks = 26", "max_stocks must be at least min_stocks (26), got 25"),
    # ... and holds while another strategy runs (M6 spec §4.5).
    (
        "strategy",
        'name = "buy-and-hold"\nmin_stocks = 20\nmax_stocks = 19',
        "max_stocks must be at least min_stocks (20), got 19",
    ),
    # A setting of a strategy that is not running is checked all the same (M6 spec §4.5).
    ("strategy", "instalments = 0", "instalments must be an integer of at least 1, got 0"),
    ("strategy", "instalments = 121", "instalments must be at most 120, got 121"),
    ("strategy", 'instalments = "12"', "instalments must be an integer of at least 1, got '12'"),
    ("strategy", "instalments = true", "instalments must be an integer of at least 1, got True"),
    ("strategy", "instalment = 12", "unknown key 'instalment'"),
    ("risk", 'max_weight = "0"', 'max_weight must be above 0 and at most 1, got "0"'),
    ("risk", 'max_weight = "1.0001"', 'max_weight must be above 0 and at most 1, got "1.0001"'),
    ("risk", 'daily_loss_limit = "1"', 'daily_loss_limit must be above 0 and below 1, got "1"'),
    ("risk", 'daily_loss_limit = "0"', 'daily_loss_limit must be above 0 and below 1, got "0"'),
    ("risk", 'max_drawdown = "1"', 'max_drawdown must be above 0 and below 1, got "1"'),
    (
        "risk",
        'max_volume_participation = "1.5"',
        'max_volume_participation must be above 0 and at most 1, got "1.5"',
    ),
    (
        "risk",
        "max_weight = 0.1",
        'max_weight must be a decimal written as a string, such as "0.018", got 0.1',
    ),
    ("risk", 'max_weight = "ten"', "max_weight must be a decimal number, got 'ten'"),
    ("risk", 'max_weight = "NaN"', "max_weight must be a finite decimal of at least 0, got 'NaN'"),
    (
        "risk",
        'max_weight = "-0.1"',
        "max_weight must be a finite decimal of at least 0, got '-0.1'",
    ),
    ("universe", 'lq45_members = ""', "lq45_members must be a non-empty string, got ''"),
    (
        "dividends",
        "pay_lag_trading_days = 0",
        "pay_lag_trading_days must be an integer of at least 1, got 0",
    ),
    (
        "dividends",
        "pay_lag_trading_days = 251",
        "pay_lag_trading_days must be at most 250, got 251",
    ),
    (
        "tax",
        'dividend_reinvestment_exemption = "yes"',
        "dividend_reinvestment_exemption must be true or false, got 'yes'",
    ),
    (
        "tax",
        "dividend_reinvestment_exemption = 1",
        "dividend_reinvestment_exemption must be true or false, got 1",
    ),
]


@pytest.mark.parametrize(("table", "line", "problem"), BAD, ids=[line for _, line, _ in BAD])
def test_each_bad_value_is_refused_naming_its_table_and_key(
    tmp_path: Path, table: str, line: str, problem: str
) -> None:
    message = f"steadyhand.toml [{table}]: {problem}"
    with pytest.raises(DataFileError, match=f"^{re.escape(message)}$"):
        load_text(tmp_path, with_key(table, line))


def test_the_lq45_file_is_relative_to_the_data_directory_unless_absolute(tmp_path: Path) -> None:
    relative = load_text(tmp_path, with_key("universe", 'lq45_members = "lists/lq45.toml"'))
    assert relative.lq45_members == tmp_path / "lists" / "lq45.toml"
    absolute = load_text(tmp_path, with_key("universe", 'lq45_members = "/srv/lq45.toml"'))
    assert absolute.lq45_members == Path("/srv/lq45.toml")


def test_the_training_table_is_carried_unread_and_read_only(tmp_path: Path) -> None:
    config = load_text(tmp_path, with_key("training", 'level = 7\nother = "x"'))
    assert config.training == {"level": 7, "other": "x"}
    with pytest.raises(TypeError):
        config.training["level"] = "new"  # type: ignore[index]


def test_a_setting_name_may_belong_to_one_strategy_only() -> None:
    rounds = Setting("rounds", 3, 1, 9, "How many rounds.")
    one = Registered(BuyAndHold, "One.", Turnover.LOW, (rounds,))
    assert [key.name for key in strategy_keys({"one": one})] == ["name", "rounds"]
    with pytest.raises(
        ValueError, match=r"^\[strategy\] rounds would be the key of more than one setting$"
    ):
        strategy_keys({"one": one, "two": Registered(BuyAndHold, "Two.", Turnover.LOW, (rounds,))})
    named = Registered(BuyAndHold, "Named.", Turnover.LOW, (Setting("name", 1, 1, 1, "x"),))
    with pytest.raises(ValueError, match=r"^\[strategy\] name would be the key of more than"):
        strategy_keys({"named": named})
    assert [key.name for key in KEYS["strategy"]] == [
        "name",
        "instalments",
        "min_stocks",
        "max_stocks",
        "growth_years",
    ]
