"""The M5a journeys through the installed ``steadyhand-idx``, each in its own process as a user
runs it (M5 spec §9.1). None reads market data, so none needs the network."""

import stat
from pathlib import Path

from cli_world import SCRIPT, installed

from steadyhand import DISCLAIMER
from steadyhand_idx import __version__


def test_the_console_script_is_installed() -> None:
    assert SCRIPT.is_file()


def test_a_first_time_users_journey(tmp_path: Path) -> None:
    home = tmp_path / "home"
    started = installed(home, "init", stdin="I understand\ny\n1\nn\n")
    assert started.code == 0, started.err
    assert started.out.startswith(DISCLAIMER)
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert stat.S_IMODE((home / "steadyhand.toml").stat().st_mode) == 0o600

    listed = installed(home, "strategies")
    assert listed.code == 0
    assert "buy-and-hold  low" in listed.out
    assert "What this means" in listed.out

    explained = installed(home, "explain", "buy-and-hold")
    assert explained.code == 0
    assert explained.out.startswith("# buy-and-hold\n")

    course = installed(home, "learn")
    assert course.code == 0
    assert course.out.startswith("Module 1: Start here\n")
    assert installed(home, "learn", "start.welcome").code == 0

    assert installed(home, "training", "experienced").code == 0
    quiet = installed(home, "strategies")
    assert "What this means" not in quiet.out
    assert installed(home, "training").out.startswith("Training level: experienced\n")


def test_the_exit_codes_and_their_messages(tmp_path: Path) -> None:
    home = tmp_path / "home"
    assert installed(home, "--version") == (0, f"steadyhand-idx {__version__}\n", "")
    helped = installed(home, "--help")
    assert (helped.code, helped.err) == (0, "")
    assert helped.out.startswith("usage: steadyhand-idx ")
    unknown = installed(home, "nonsense")
    assert unknown.code == 2
    assert unknown.err.startswith("steadyhand-idx: argument command: invalid choice: 'nonsense'")
    assert installed(home, "explain", "nothing") == (
        2,
        "",
        "steadyhand-idx: no strategy named 'nothing'\n",
    )
    assert installed(home, "learn", "nothing") == (
        2,
        "",
        "steadyhand-idx: no lesson named 'nothing'\n",
    )
    assert installed(home, "training") == (
        2,
        "",
        (
            f"steadyhand-idx: there is no configuration at {home / 'steadyhand.toml'}; "
            "run steadyhand-idx init first\n"
        ),
    )
    refused = installed(home, "init", stdin="no\n")
    assert refused.code == 2
    assert (
        refused.err == "steadyhand-idx: the disclaimer was not accepted, so nothing was written\n"
    )
    assert not home.exists()
