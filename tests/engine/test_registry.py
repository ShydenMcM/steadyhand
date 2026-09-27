"""The strategy registry: each entry's summary and turnover, and the guides it ships (M5 spec
§5.5, §5.6)."""

from pathlib import Path

import pytest

from steadyhand import GUIDES, STRATEGIES, BuyAndHold, Turnover, guide


def test_every_registered_strategy_has_a_summary_and_a_turnover() -> None:
    assert len(STRATEGIES) >= 1
    for entry in STRATEGIES.values():
        assert entry.summary.strip()
        assert "\n" not in entry.summary
        assert entry.turnover in Turnover


def test_the_baselines_entry() -> None:
    entry = STRATEGIES["buy-and-hold"]
    assert entry.make is BuyAndHold
    assert entry.turnover is Turnover.LOW
    assert entry.summary == (
        "Buys every stock it can on its first day in equal parts, then holds and reinvests."
    )


def test_calling_an_entry_makes_its_strategy() -> None:
    made = STRATEGIES["buy-and-hold"]()
    assert isinstance(made, BuyAndHold)
    assert made.name == "buy-and-hold"


def test_the_turnover_values_are_what_the_strategy_list_shows() -> None:
    assert [level.value for level in Turnover] == ["low", "medium", "high"]


def test_the_guides_ship_inside_the_package() -> None:
    root = Path(__file__).resolve().parents[2]
    assert Path(str(GUIDES)) == root / "packages/steadyhand/src/steadyhand/strategies/guides"


def test_guide_reads_a_registered_strategys_guide() -> None:
    assert guide("buy-and-hold").startswith("# buy-and-hold\n")


def test_guide_refuses_a_name_that_is_not_registered() -> None:
    with pytest.raises(KeyError, match="no registered strategy is named 'nothing'"):
        guide("nothing")
