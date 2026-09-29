"""The shell: parsing, streams, the exit-code table and the console script (M5 spec §3.2, §8)."""

import io
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from cli_world import Cli, mode, umask

from steadyhand import (
    IDR,
    RISK_HALT_DAILY_LOSS,
    DataUnavailableError,
    DataValidationError,
    Halt,
    Instrument,
    InvalidBarError,
    Note,
    NoTradingDaysError,
    SnapshotError,
    SnapshotVersionError,
    UnavailableDaysError,
    UniverseCoverageError,
    UnsupportedDateError,
)
from steadyhand_idx import CachedDataSource, __version__
from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.cli import (
    EXIT_CODES,
    ConfigRewriteError,
    UsageError,
    exit_code,
    open_source,
    run,
)
from steadyhand_idx.config import ConfigMissingError
from steadyhand_idx.output import UnknownNameError
from steadyhand_idx.paper import (
    AccountHaltedError,
    CatchUpError,
    StaleDataError,
    StrategyChangedError,
)
from steadyhand_idx.state import StateSchemaError

BBCA = Instrument("BBCA", "IDX", IDR)


def test_the_exit_code_table_is_pinned_row_by_row() -> None:
    assert (
        (UsageError, 2),
        (ConfigMissingError, 2),
        (DataFileError, 2),
        (UnknownNameError, 2),
        (UnsupportedDateError, 2),
        (UniverseCoverageError, 2),
        (NoTradingDaysError, 2),
        (SnapshotVersionError, 2),
        (StateSchemaError, 2),
        (CatchUpError, 2),
        (StrategyChangedError, 2),
        (DataUnavailableError, 3),
        (DataValidationError, 3),
        (InvalidBarError, 3),
        (StaleDataError, 3),
        (AccountHaltedError, 3),
    ) == EXIT_CODES


# Each error is made inside the test, never while collecting: a stub raising in its constructor
# would otherwise stop the whole run before a single test.
@pytest.mark.parametrize(
    ("make", "code"),
    [
        (lambda: UsageError("x"), 2),
        (lambda: ConfigMissingError(Path("steadyhand.toml")), 2),
        (lambda: DataFileError("x"), 2),
        (lambda: UnknownNameError("x", (), kind="lesson"), 2),
        (lambda: UnsupportedDateError("x"), 2),
        (lambda: UniverseCoverageError(date(2021, 1, 4), date(2021, 2, 1)), 2),
        (lambda: NoTradingDaysError("x"), 2),
        (lambda: SnapshotVersionError(2, 1), 2),
        (lambda: StateSchemaError("x"), 2),
        (lambda: CatchUpError(31, date(2021, 2, 1)), 2),
        (lambda: StrategyChangedError("buy-and-hold", "retired"), 2),
        (lambda: DataUnavailableError("x"), 3),
        (lambda: UnavailableDaysError("x", [date(2021, 2, 1)]), 3),
        (lambda: DataValidationError(BBCA, date(2021, 2, 1), "x"), 3),
        (lambda: InvalidBarError("x"), 3),
        (lambda: StaleDataError(date(2021, 2, 1)), 3),
        (
            lambda: AccountHaltedError(
                Halt(date(2021, 2, 1), Note(RISK_HALT_DAILY_LOSS, "x")), "buy-and-hold"
            ),
            3,
        ),
        (lambda: SnapshotError("x"), 1),
        (lambda: ConfigRewriteError("x"), 1),
        (lambda: RuntimeError("x"), 1),
        (lambda: KeyError("x"), 1),
    ],
)
def test_each_error_maps_to_its_exit_code(make: Callable[[], Exception], code: int) -> None:
    assert exit_code(make()) == code


def test_the_version(cli: Cli) -> None:
    assert cli("--version") == (0, f"steadyhand-idx {__version__}\n", "")


def test_help_goes_to_stdout_and_exits_0(cli: Cli) -> None:
    result = cli("--help")
    assert result.code == 0
    assert result.out.startswith("usage: steadyhand-idx ")
    for command in ("init", "training", "learn"):
        assert f"    {command} " in result.out
    assert result.err == ""


def test_a_commands_help_goes_to_stdout(cli: Cli) -> None:
    result = cli("init", "--help")
    assert result.code == 0
    assert result.out.startswith("usage: steadyhand-idx init ")
    assert "--exemption {on,off}" in result.out
    assert result.err == ""


def test_no_command_is_a_usage_error(cli: Cli) -> None:
    assert cli() == (2, "", "steadyhand-idx: choose a command; steadyhand-idx --help lists them\n")


def test_an_unknown_command_is_a_usage_error_on_stderr(cli: Cli) -> None:
    result = cli("pape")
    assert result.code == 2
    assert result.out == ""
    lines = result.err.splitlines()
    assert lines[0].startswith("steadyhand-idx: argument command: invalid choice: 'pape'")
    assert lines[1].startswith("usage: steadyhand-idx ")


def test_a_command_that_needs_the_configuration_says_to_run_init_first(cli: Cli) -> None:
    result = cli("training")
    assert result.code == 2
    assert result.out == ""
    assert result.err == (
        f"steadyhand-idx: there is no configuration at {cli.config}; "
        "run steadyhand-idx init first\n"
    )


def test_an_unexpected_error_is_one_line_and_a_hint(cli: Cli) -> None:
    cli.config.mkdir(parents=True)  # a directory where the configuration file belongs
    result = cli("training")
    assert result.code == 1
    assert result.out == ""
    assert result.err == (
        f"steadyhand-idx: [Errno 21] Is a directory: '{cli.config}'\n"
        "run again with --debug for details\n"
    )


def test_debug_prints_the_traceback_instead_of_the_hint(cli: Cli) -> None:
    cli.config.mkdir(parents=True)
    result = cli("--debug", "training")
    assert result.code == 1
    lines = result.err.splitlines()
    assert lines[0] == f"steadyhand-idx: [Errno 21] Is a directory: '{cli.config}'"
    assert lines[1] == "Traceback (most recent call last):"
    assert lines[-1] == f"IsADirectoryError: [Errno 21] Is a directory: '{cli.config}'"
    assert "run again with --debug" not in result.err


def test_debug_prints_the_traceback_of_an_expected_error_too(cli: Cli) -> None:
    result = cli("--debug", "training")
    assert result.code == 2
    assert result.err.splitlines()[-1].startswith("steadyhand_idx.config.ConfigMissingError: ")


def test_the_console_script_runs_main_with_the_real_world(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["steadyhand-idx", "init", "--training", "off"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("I understand\n\n"))
    monkeypatch.setenv("STEADYHAND_HOME", str(tmp_path / "home"))
    with pytest.raises(SystemExit) as done:
        run()
    assert done.value.code == 0
    assert f"Wrote {tmp_path / 'home' / 'steadyhand.toml'}" in capsys.readouterr().out


def test_the_real_source_is_yahoo_through_the_cache_in_the_data_directory(
    tmp_path: Path,
) -> None:
    with open_source(tmp_path) as source:
        assert isinstance(source, CachedDataSource)
    assert (tmp_path / "cache.sqlite").is_file()


@pytest.mark.parametrize("value", [0o000, 0o022, 0o277])
def test_the_bar_cache_is_0600_whatever_the_umask(tmp_path: Path, value: int) -> None:
    with umask(value), open_source(tmp_path):
        pass
    assert mode(tmp_path / "cache.sqlite") == 0o600


def test_an_existing_bar_cache_is_made_0600_when_a_command_opens_it(tmp_path: Path) -> None:
    with open_source(tmp_path):
        pass
    (tmp_path / "cache.sqlite").chmod(0o644)
    with open_source(tmp_path):
        pass
    assert mode(tmp_path / "cache.sqlite") == 0o600
