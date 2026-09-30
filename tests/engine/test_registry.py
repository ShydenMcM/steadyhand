"""The strategy registry: each entry's summary and turnover, and the guides it ships (M5 spec
§5.5, §5.6)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from steadyhand import (
    GUIDES,
    STRATEGIES,
    BuyAndHold,
    Decision,
    MarketView,
    Memory,
    PortfolioView,
    Registered,
    Setting,
    Turnover,
    guide,
)


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


@dataclass(frozen=True)
class _Rounds:
    """A strategy made from two settings, to test the registry without a shipped one."""

    rounds: int
    pause: int

    @property
    def name(self) -> str:
        return "rounds"

    def decide(self, view: MarketView, portfolio: PortfolioView, memory: Memory) -> Decision:
        del view, portfolio, memory
        return Decision({})


ROUNDS = Setting("rounds", 3, 1, 9, "How many rounds to play.")
PAUSE = Setting("pause", 0, 0, 5, "Days to wait between rounds.")
ENTRY = Registered(
    _Rounds, "Plays rounds.", Turnover.LOW, (ROUNDS, PAUSE), lambda values: values["rounds"] + 1
)


def test_a_setting_is_a_named_bounded_whole_number_with_one_line_of_help() -> None:
    assert (ROUNDS.name, ROUNDS.default, ROUNDS.minimum, ROUNDS.maximum) == ("rounds", 3, 1, 9)
    assert ROUNDS.help == "How many rounds to play."
    assert Setting("growth_years", 1, 1, 1, "x").default == 1


@pytest.mark.parametrize(
    ("fields", "error", "message"),
    [
        (
            ("Rounds", 3, 1, 9, "x"),
            ValueError,
            r"^a setting's name is a lowercase identifier, got 'Rounds'$",
        ),
        (
            ("two words", 3, 1, 9, "x"),
            ValueError,
            r"^a setting's name is a lowercase identifier, got 'two words'$",
        ),
        (
            ("rounds_", 3, 1, 9, "x"),
            ValueError,
            r"^a setting's name is a lowercase identifier, got 'rounds_'$",
        ),
        ((5, 3, 1, 9, "x"), ValueError, r"^a setting's name is a lowercase identifier, got 5$"),
        (("rounds", 10, 1, 9, "x"), ValueError, r"^rounds: the default 10 must be from 1 to 9$"),
        (("rounds", 0, 1, 9, "x"), ValueError, r"^rounds: the default 0 must be from 1 to 9$"),
        (("rounds", 3, True, 9, "x"), TypeError, r"^rounds: the minimum must be an int, got bool$"),
        (("rounds", "3", 1, 9, "x"), TypeError, r"^rounds: the default must be an int, got str$"),
        (("rounds", 3, 1, 9.0, "x"), TypeError, r"^rounds: the maximum must be an int, got float$"),
        (("rounds", 3, 1, 9, " "), ValueError, r"^rounds: the help is one line of text$"),
        (("rounds", 3, 1, 9, "one\ntwo"), ValueError, r"^rounds: the help is one line of text$"),
        (("rounds", 3, 1, 9, 7), TypeError, r"^rounds help must be a str, got int$"),
    ],
)
def test_a_setting_refuses_a_bad_name_bound_default_or_help(
    fields: tuple[object, ...], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        Setting(*fields)  # type: ignore[arg-type]


def test_a_setting_takes_a_whole_number_within_its_bounds() -> None:
    assert [ROUNDS.check(value) for value in (1, 5, 9)] == [1, 5, 9]
    with pytest.raises(ValueError, match=r"^rounds must be from 1 to 9, got 0$"):
        ROUNDS.check(0)
    with pytest.raises(ValueError, match=r"^rounds must be from 1 to 9, got 10$"):
        ROUNDS.check(10)
    with pytest.raises(TypeError, match=r"^rounds must be a whole number, got bool$"):
        ROUNDS.check(True)
    with pytest.raises(TypeError, match=r"^rounds must be a whole number, got str$"):
        ROUNDS.check("3")


def test_an_entry_makes_its_strategy_from_the_defaults_or_from_given_values() -> None:
    assert ENTRY.values() == {"rounds": 3, "pause": 0}
    assert ENTRY() == _Rounds(3, 0)
    # The flat [strategy] table holds every strategy's settings: each entry takes its own.
    assert ENTRY({"rounds": 5, "pause": 2, "instalments": 12}) == _Rounds(5, 2)


def test_an_entry_refuses_a_missing_or_bad_value() -> None:
    with pytest.raises(ValueError, match=r"^missing the setting pause$"):
        ENTRY({"rounds": 5})
    with pytest.raises(ValueError, match=r"^rounds must be from 1 to 9, got 10$"):
        ENTRY({"rounds": 10, "pause": 0})
    with pytest.raises(ValueError, match=r"^pause must be from 0 to 5, got 6$"):
        ENTRY.lookback_years({"rounds": 1, "pause": 6})


def test_the_look_back_reads_the_same_values() -> None:
    assert ENTRY.lookback_years() == 4
    assert ENTRY.lookback_years({"rounds": 7, "pause": 0}) == 8


def test_buy_and_hold_has_no_settings_and_reads_nothing_before_a_run() -> None:
    entry = STRATEGIES["buy-and-hold"]
    assert entry.settings == ()
    assert entry.values() == {}
    assert entry.lookback_years() == 0
    assert entry.lookback_years({"rounds": 3}) == 0
    assert isinstance(entry({"rounds": 3}), BuyAndHold)


def test_an_entry_refuses_a_setting_twice_or_one_that_is_not_a_setting() -> None:
    with pytest.raises(ValueError, match=r"^the setting rounds is registered twice$"):
        Registered(_Rounds, "x", Turnover.LOW, (ROUNDS, ROUNDS))
    with pytest.raises(TypeError, match=r"^settings must be a tuple, got list$"):
        Registered(_Rounds, "x", Turnover.LOW, [ROUNDS])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^setting must be a Setting, got str$"):
        Registered(_Rounds, "x", Turnover.LOW, ("rounds",))  # type: ignore[arg-type]
