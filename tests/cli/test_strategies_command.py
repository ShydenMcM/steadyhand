"""``strategies`` and ``explain``, which need no configuration (M5 spec §5.5, §5.6)."""

from cli_world import Cli

from steadyhand import DISCLAIMER, guide
from steadyhand_idx.training import catalogue


def test_strategies_lists_each_name_turnover_and_summary(cli: Cli) -> None:
    turnover = catalogue().for_key("term.turnover")
    assert cli("strategies") == (
        0,
        (
            "Strategy      Turnover  What it does\n"
            "buy-and-hold  low       Buys every stock it can on its first day in equal parts, "
            "then holds and reinvests.\n\n"
            "Read a strategy's guide with: steadyhand-idx explain <strategy>\n\n"
            f"What this means\n• {turnover.title}: {turnover.summary} "
            f"More: steadyhand-idx learn {turnover.id}\n\n"
            f"{DISCLAIMER}\n"
        ),
        "",
    )
    assert not cli.home.exists()


def test_strategies_follows_the_configured_level(cli: Cli) -> None:
    cli.init(training="experienced")
    result = cli("strategies")
    assert "What this means" not in result.out
    assert result.out.endswith(f"explain <strategy>\n\n{DISCLAIMER}\n")


def test_explain_prints_the_guide_then_the_footer(cli: Cli) -> None:
    assert cli("explain", "buy-and-hold") == (
        0,
        f"{guide('buy-and-hold').rstrip()}\n\n{DISCLAIMER}\n",
        "",
    )


def test_explain_an_unknown_strategy_exits_2_naming_the_closest(cli: Cli) -> None:
    assert cli("explain", "buy-hold") == (
        2,
        "",
        "steadyhand-idx: no strategy named 'buy-hold'; the closest: buy-and-hold\n",
    )
    assert cli("explain", "momentum") == (2, "", "steadyhand-idx: no strategy named 'momentum'\n")
