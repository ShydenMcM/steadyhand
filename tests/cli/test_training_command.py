"""``training``: show the level, or change only its line of the configuration (M5 spec §5.2)."""

import stat

import pytest
from cli_world import Cli

from steadyhand import DISCLAIMER
from steadyhand_idx.output import with_training_level

CONSENT = "[consent]\ndisclaimer_accepted = 2026-09-27\n"


def test_training_shows_the_level(cli: Cli) -> None:
    cli.init(training="some")
    assert cli("training") == (
        0,
        (
            "Training level: some\n"
            "Change it with: steadyhand-idx training off|new|some|experienced\n\n"
            f"{DISCLAIMER}\n"
        ),
        "",
    )


def test_changing_the_level_rewrites_only_its_line(cli: Cli) -> None:
    cli.init(training="new")
    before = cli.config.read_text(encoding="utf-8")
    result = cli("training", "experienced")
    assert result.code == 0, result.err
    assert result.out == f"Training level: experienced (was new)\n\n{DISCLAIMER}\n"
    after = cli.config.read_text(encoding="utf-8")
    assert after == before.replace('level = "new"\n', 'level = "experienced"\n')
    assert after.count("level = ") == 1
    assert stat.S_IMODE(cli.config.stat().st_mode) == 0o600


def test_the_operators_own_comments_and_layout_survive(cli: Cli) -> None:
    cli.home.mkdir()
    text = (
        "# my settings\n[account]\nstarting_cash_idr = 5_000_000   # five million\n\n"
        "[training]   # how chatty\n  level   =   'new'   # was new\n\n" + CONSENT
    )
    cli.config.write_text(text, encoding="utf-8")
    assert cli("training", "off").code == 0
    assert cli.config.read_text(encoding="utf-8") == text.replace(
        "  level   =   'new'   # was new", '  level   =   "off"   # was new'
    )


def test_a_missing_training_table_is_added(cli: Cli) -> None:
    cli.home.mkdir()
    cli.config.write_text(CONSENT, encoding="utf-8")
    assert cli("training", "some").code == 0
    assert cli.config.read_text(encoding="utf-8") == CONSENT + '\n[training]\nlevel = "some"\n'


def test_a_missing_level_line_is_added_under_the_table(cli: Cli) -> None:
    cli.home.mkdir()
    cli.config.write_text("[training]\n\n" + CONSENT, encoding="utf-8")
    assert cli("training", "some").code == 0
    assert cli.config.read_text(encoding="utf-8") == '[training]\nlevel = "some"\n\n' + CONSENT


def test_a_rewrite_that_breaks_the_file_puts_the_old_bytes_back(cli: Cli) -> None:
    cli.home.mkdir()
    text = 'training = { level = "new" }\n' + CONSENT  # an inline table the rewrite cannot see
    cli.config.write_text(text, encoding="utf-8")
    result = cli("training", "off")
    assert result.code == 1
    assert result.out == ""
    assert result.err == (
        "steadyhand-idx: could not change the training level (steadyhand.toml is not valid "
        "TOML: Cannot declare ('training',) twice (at line 5, column 10)); steadyhand.toml is "
        "unchanged\nrun again with --debug for details\n"
    )
    assert cli.config.read_text(encoding="utf-8") == text


def test_a_level_the_file_already_gets_wrong_is_refused_before_any_write(cli: Cli) -> None:
    cli.home.mkdir()
    text = '[training]\nlevel = "expert"\n\n' + CONSENT
    cli.config.write_text(text, encoding="utf-8")
    result = cli("training", "new")
    assert result.code == 2
    assert result.err == (
        "steadyhand-idx: steadyhand.toml [training]: level must be one of off, new, some, "
        "experienced, got 'expert'\n"
    )
    assert cli.config.read_text(encoding="utf-8") == text


def test_an_unknown_level_is_a_usage_error(cli: Cli) -> None:
    cli.init()
    result = cli("training", "expert")
    assert result.code == 2
    assert "argument level: invalid choice: 'expert'" in result.err


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", '\n[training]\nlevel = "off"\n'),
        ("[consent]\na = 1", '[consent]\na = 1\n\n[training]\nlevel = "off"\n'),
        ('[training]\nlevel = "new"', '[training]\nlevel = "off"'),
        ('[ training ] # x\nlevel="new"\n', '[ training ] # x\nlevel="off"\n'),
        ('[training]\nlevel = "n\\"ew"\n', '[training]\nlevel = "off"\n'),
        (
            '[training]\n[consent]\nlevel = "new"\n',
            '[training]\nlevel = "off"\n[consent]\nlevel = "new"\n',
        ),
        (
            '[trainings]\nlevel = "new"\n',
            '[trainings]\nlevel = "new"\n\n[training]\nlevel = "off"\n',
        ),
        ('[training]\nlevels = "new"\n', '[training]\nlevel = "off"\nlevels = "new"\n'),
    ],
)
def test_the_rewrite_edge_cases(text: str, expected: str) -> None:
    assert with_training_level(text, "off") == expected


def test_the_rewrite_takes_only_a_known_level() -> None:
    with pytest.raises(ValueError, match="'loud' is not a valid Level"):
        with_training_level("", "loud")
