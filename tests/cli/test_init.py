"""``init``: the disclaimer, three questions, and the configuration it writes (M5 spec §5.1)."""

import stat
from datetime import date

import pytest
from cli_world import Cli

from steadyhand import DISCLAIMER
from steadyhand_idx.config import load, starter

JAKARTA_TODAY = date(2026, 9, 28)
EXPLAIN = "Would you like explanations as you go? [Y/n] "
EXPERIENCE = "How much investing experience do you have? 1 New / 2 Some / 3 Experienced [1] "
EXEMPTION = "Claim the dividend reinvestment exemption? [y/N] "


def test_answering_every_question_writes_the_starter_configuration(cli: Cli) -> None:
    result = cli("init", stdin="I understand\n\n\n\n")
    assert result.code == 0, result.err
    assert result.err == ""
    assert cli.config.read_text(encoding="utf-8") == starter(
        "new", exemption=False, accepted=JAKARTA_TODAY
    )
    assert result.out.startswith(
        f"{DISCLAIMER}\n\nType 'I understand' to accept this and continue: {EXPLAIN}{EXPERIENCE}"
        "The dividend reinvestment exemption: a resident individual's dividend is free of the 10% "
        "tax if it is reinvested in Indonesia in time and kept invested. steadyhand can estimate "
        f"it for you; it cannot claim it.\n{EXEMPTION}Wrote {cli.config}\n\n"
        "Before your first backtest, set your starting cash"
    )
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")


def test_the_configuration_loads_and_is_dated_in_jakarta(cli: Cli) -> None:
    cli.init()
    assert load(cli.config).disclaimer_accepted == JAKARTA_TODAY


def test_the_data_directory_is_0700_and_the_configuration_0600(cli: Cli) -> None:
    cli.init()
    assert stat.S_IMODE(cli.home.stat().st_mode) == 0o700
    assert stat.S_IMODE(cli.config.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    ("answers", "level"),
    [
        ("n\n", "off"),
        ("no\n", "off"),
        ("N\n", "off"),
        ("y\n2\n", "some"),
        ("YES\n3\n", "experienced"),
        ("\n1\n", "new"),
        ("\n\n", "new"),
    ],
)
def test_the_two_training_questions(cli: Cli, answers: str, level: str) -> None:
    result = cli("init", "--exemption", "off", stdin=f"I understand\n{answers}")
    assert result.code == 0, result.err
    assert load(cli.config).training == {"level": level}
    assert (EXPERIENCE in result.out) is (level != "off")


@pytest.mark.parametrize(("answer", "exempt"), [("y\n", True), ("Yes\n", True), ("n\n", False)])
def test_the_exemption_question(cli: Cli, answer: str, *, exempt: bool) -> None:
    result = cli("init", "--training", "off", stdin=f"I understand\n{answer}")
    assert result.code == 0, result.err
    assert load(cli.config).settings.engine.dividend_reinvestment_exemption is exempt


def test_the_flags_answer_the_questions_for_a_script(cli: Cli) -> None:
    result = cli.init(training="some", exemption="on")
    assert EXPLAIN not in result.out
    assert EXEMPTION not in result.out
    config = load(cli.config)
    assert config.training == {"level": "some"}
    assert config.settings.engine.dividend_reinvestment_exemption is True


def test_windows_line_endings_are_accepted(cli: Cli) -> None:
    result = cli("init", stdin="I understand\r\nn\r\n\r\n")
    assert result.code == 0, result.err


@pytest.mark.parametrize("answer", ["", "i understand\n", "I understand \n", "yes\n"])
def test_anything_but_i_understand_writes_nothing(cli: Cli, answer: str) -> None:
    result = cli("init", "--training", "new", "--exemption", "off", stdin=answer)
    assert result.code == 2
    assert result.err == (
        "steadyhand-idx: the disclaimer was not accepted, so nothing was written\n"
    )
    assert not cli.home.exists()


@pytest.mark.parametrize(
    ("args", "answers", "problem"),
    [
        ((), "maybe\n", "answer y or n, not 'maybe'"),
        ((), "y\n4\n", "answer 1, 2 or 3, not '4'"),
        (("--training", "new"), "sometimes\n", "answer y or n, not 'sometimes'"),
    ],
)
def test_an_answer_it_cannot_read_writes_nothing(
    cli: Cli, args: tuple[str, ...], answers: str, problem: str
) -> None:
    result = cli("init", *args, stdin=f"I understand\n{answers}")
    assert result.code == 2
    assert result.err == f"steadyhand-idx: {problem}; nothing was written\n"
    assert not cli.home.exists()


def test_init_never_overwrites(cli: Cli) -> None:
    cli.init()
    before = cli.config.read_bytes()
    result = cli("init", "--training", "off", "--exemption", "on", stdin="I understand\n")
    assert result.code == 2
    assert result.out == ""
    assert result.err == (
        f"steadyhand-idx: {cli.config} already exists, and init never overwrites it; "
        "edit it instead\n"
    )
    assert cli.config.read_bytes() == before


def test_a_bad_flag_value_is_a_usage_error(cli: Cli) -> None:
    result = cli("init", "--exemption", "maybe")
    assert result.code == 2
    assert "argument --exemption: invalid choice: 'maybe'" in result.err
    assert not cli.home.exists()
