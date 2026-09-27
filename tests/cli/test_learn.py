"""``learn``: the course and one lesson, with or without a configuration (T1 spec §6 item 3)."""

from cli_world import Cli

from steadyhand import DISCLAIMER
from steadyhand_idx.training import catalogue


def test_learn_lists_every_lesson_of_the_course_in_order_with_no_configuration(cli: Cli) -> None:
    result = cli("learn")
    assert result.code == 0, result.err
    listed = [
        line.split(":")[0].strip() for line in result.out.splitlines() if line.startswith("  ")
    ]
    course = [lesson.id for module in catalogue().course() for lesson in module.lessons]
    assert listed[: len(course)] == course
    assert len(course) >= 33
    assert result.out.startswith("Module 1: Start here\n")
    assert result.out.endswith(f"Read one with: steadyhand-idx learn <id>\n\n{DISCLAIMER}\n")
    assert not cli.home.exists()


def test_learn_prints_one_lesson(cli: Cli) -> None:
    run_rate = catalogue().lesson("income.run_rate")
    result = cli("learn", "income.run_rate")
    assert result.code == 0, result.err
    assert result.out.startswith(f"{run_rate.title}\n\n{run_rate.body.strip()}\n\nSee also: ")
    assert result.out.endswith(f"\n\n{DISCLAIMER}\n")


def test_an_unknown_lesson_exits_2_naming_the_closest(cli: Cli) -> None:
    assert cli("learn", "income.run_rat") == (
        2,
        "",
        (
            "steadyhand-idx: no lesson named 'income.run_rat'; the closest: income.run_rate, "
            "income.growth, income.goal\n"
        ),
    )


def test_learn_reads_the_configured_level_when_there_is_a_configuration(cli: Cli) -> None:
    cli.init(training="off")
    assert cli("learn", "income.run_rate").code == 0
    cli.config.write_text(
        cli.config.read_text(encoding="utf-8").replace('level = "off"', 'level = "loud"'),
        encoding="utf-8",
    )
    result = cli("learn")
    assert result.code == 2
    assert result.err == (
        "steadyhand-idx: steadyhand.toml [training]: level must be one of off, new, some, "
        "experienced, got 'loud'\n"
    )
