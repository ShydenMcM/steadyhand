"""What every Yahoo recording restores to, pinned as recorded before the restoring step was sped
up (#296 AC 1): the same runs, bars, refusals and actions, exactly."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

import pytest

from steadyhand import IDR, Bar, CashDividend, CorporateAction, Instrument, Split
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import Run, find_runs
from steadyhand_idx.yahoo import (
    UnrecoverablePricesError,
    YahooHistory,
    actions_in,
    evidence,
    history_from_json,
    unadjust,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
RECORDINGS = sorted(FIXTURES.glob("*.json"))


@cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


@dataclass(frozen=True, slots=True)
class Answers:
    """One recording's answers. Long lists are kept as a count and a SHA-256 of their lines."""

    runs: tuple[tuple[str, str, int, int, str | None], ...]
    """Each run's first and last day, day count, price count and factor (``None``: unproven)."""
    run_days: str
    refused: tuple[int, str, str]
    """How many days ``unadjust`` refuses over the recording, with the first and last (or "")."""
    refused_days: str
    bars: int
    bars_digest: str
    actions: int
    actions_digest: str


def digest(lines: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _bar_line(bar: Bar) -> str:
    prices = (bar.open, bar.high, bar.low, bar.close)
    return ",".join(
        [bar.day.isoformat(), *(str(price.amount) for price in prices), str(bar.volume)]
    )


def _action_line(action: CorporateAction) -> str:
    if isinstance(action, Split):
        return f"split,{action.ex_date.isoformat()},{action.old_shares},{action.new_shares}"
    assert isinstance(action, CashDividend)
    return f"dividend,{action.ex_date.isoformat()},{action.per_share}"


def _bars_around(
    history: YahooHistory,
    instrument: Instrument,
    span: tuple[date, date],
    runs: Sequence[Run],
    refused: Sequence[date],
) -> list[Bar]:
    """The bars of every stretch of trading days between the refused ones."""
    bars: list[Bar] = []
    stretch: list[date] = []
    for day in [*calendar().trading_days(*span), None]:
        if day is not None and day not in refused:
            stretch.append(day)
            continue
        if stretch:
            bars += unadjust(history, instrument, calendar(), (stretch[0], stretch[-1]), runs)[0]
        stretch = []
    return bars


def answers(path: Path) -> Answers:
    """*path*'s answers over its recorded span, cut to the days the calendar covers."""
    symbol, first, last = path.stem.split("_")
    instrument = Instrument(symbol.removesuffix(".JK"), "IDX", IDR)
    span = (
        max(date.fromisoformat(first), calendar().first_day),
        min(date.fromisoformat(last), calendar().last_day),
    )
    history = history_from_json(path)
    runs = find_runs(evidence(history))
    try:
        bars = unadjust(history, instrument, calendar(), span, runs)[0]
        refused: tuple[date, ...] = ()
    except UnrecoverablePricesError as error:
        refused = error.days
        bars = _bars_around(history, instrument, span, runs, refused)
    actions = actions_in(history, instrument, *span, runs)
    return Answers(
        runs=tuple(
            (
                run.first.isoformat(),
                run.last.isoformat(),
                len(run.days),
                run.prices,
                None if run.factor is None else str(run.factor),
            )
            for run in runs
        ),
        run_days=digest([",".join(day.isoformat() for day in run.days) for run in runs]),
        refused=(
            len(refused),
            *((refused[0].isoformat(), refused[-1].isoformat()) if refused else ("", "")),
        ),
        refused_days=digest([day.isoformat() for day in refused]),
        bars=len(bars),
        bars_digest=digest([_bar_line(bar) for bar in bars]),
        actions=len(actions),
        actions_digest=digest([_action_line(action) for action in actions]),
    )


PINNED: dict[str, Answers] = {
    "ASII.JK_2017-01-31_2022-01-31.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1212,
        bars_digest="26018c2074a8507c7ecd9821828cd48b33fd601ac1dfdac072f547fcd5b63af8",
        actions=10,
        actions_digest="3e49d120c7b92b59081fc9cc41f8ed6a0cdb437dd07431a2d4d92bb03fed06e0",
    ),
    "ASII.JK_2017-01-31_2022-04-29.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1271,
        bars_digest="a5b0911d8797576299e9e50994ae64f6834fcfb59bceb73673dc5b96bf625bf6",
        actions=10,
        actions_digest="3e49d120c7b92b59081fc9cc41f8ed6a0cdb437dd07431a2d4d92bb03fed06e0",
    ),
    "BBCA.JK_2017-01-31_2022-01-31.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1213,
        bars_digest="e25591de8f2b7a8193569167c2779ceabe88f39a3f200925d8c5a2b5b30654ef",
        actions=11,
        actions_digest="f0f64b6bcd6ad4c0c25a8467130b83d69d51212c9e057693a439d96f254f52c4",
    ),
    "BBCA.JK_2017-01-31_2022-04-29.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1272,
        bars_digest="1b1e19300cfecd81eb81154f22ff2a04969c26ac87a9c75ffbf3af794fd0b278",
        actions=12,
        actions_digest="51ce6d8db8d01b5566c3e1a361e763cd18a9e4d195dcf0bd63edbea27284e509",
    ),
    "BBCA.JK_2021-09-01_2021-11-30.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=64,
        bars_digest="f5b9a3442b7fe39661663f4b37e3577908ad1e98b0fbbfb09476af824214a209",
        actions=2,
        actions_digest="50c3efadff9114de5816cd12788e3ac1b29ef854fab06ea2e842e4cd7a5f57da",
    ),
    "BBRI.JK_2014-01-06_2026-10-01.json": Answers(
        runs=(("2014-01-06", "2021-09-07", 1845, 7380, "1.100019"),),
        run_days="af9854bf935f9286427d50466e6489844cc292394db07857056b3147181b20e7",
        refused=(358, "2016-01-04", "2017-11-09"),
        refused_days="1613eeb5f1dfa25b2daedab04f28b91644894a8b0134d889dbd5d8c529635abd",
        bars=2235,
        bars_digest="b5b12471ad7f1a3527be4a25fec93b6d4391f8a7e03d79fcd8f95b422fbffb69",
        actions=16,
        actions_digest="42cfd11a4e29a76de73311a982f55f6d2bdc6ea9681ce96fbafa1c7f5f712e44",
    ),
    "BBRI.JK_2017-01-31_2022-01-31.json": Answers(
        runs=(("2017-01-31", "2021-09-07", 1103, 4412, "1.100019"),),
        run_days="9600ffab4694fb34931a4f9008b9c77a2c5ce6e1d6a893783755adb5809f8ac0",
        refused=(153, "2017-01-31", "2017-11-09"),
        refused_days="5a9046a2c74f16a2540dc038cac82c93b432e9f84a17f22fe7a1ed2028672daa",
        bars=1060,
        bars_digest="7b8cccc3d03f421ecc2430dd6e3ce43fbbfbb8be2a2ff0f97e3f1ae3fc94f7db",
        actions=6,
        actions_digest="735ded1c44c1d4a487ccb9a460f41a6a5d6a5b97ddd799a8d8f833857636f6a7",
    ),
    "BBRI.JK_2017-01-31_2022-04-29.json": Answers(
        runs=(("2017-01-31", "2021-09-07", 1103, 4412, "1.100019"),),
        run_days="9600ffab4694fb34931a4f9008b9c77a2c5ce6e1d6a893783755adb5809f8ac0",
        refused=(153, "2017-01-31", "2017-11-09"),
        refused_days="5a9046a2c74f16a2540dc038cac82c93b432e9f84a17f22fe7a1ed2028672daa",
        bars=1119,
        bars_digest="77779aa775c62fcced80e3edad92b8615e28db4ab4929c782aa7f69c232eb399",
        actions=7,
        actions_digest="fa273c2362ebf143de2cb5f75aa5c521c028c184376574d81933dcb39b92790b",
    ),
    "BBRI.JK_2021-08-02_2021-09-30.json": Answers(
        runs=(("2021-08-02", "2021-09-07", 25, 100, "1.100019"),),
        run_days="fc63c950362cccdd383027e24a4a5deaa229663d6433e71b2cae29ecae1a2910",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=42,
        bars_digest="cb43983f951d121b0df5a2fc333297ef030feb33cd55b065e4fdf82d457b0c9b",
        actions=0,
        actions_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
    "TLKM.JK_2017-01-31_2022-01-31.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1212,
        bars_digest="dbe5a0ae8883d7d19bbe19f89922839de34b61a2afb2d0fbcae93f558cc5c410",
        actions=5,
        actions_digest="1c18cbfca8f35b90bd246fb182e9922c1df5405fd8265d56804a6587712d564d",
    ),
    "TLKM.JK_2017-01-31_2022-04-29.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1271,
        bars_digest="63b82a2cf46c3f53f2f96be49715ae51b8cde791ccf46195cf6c4446670a8dd6",
        actions=5,
        actions_digest="1c18cbfca8f35b90bd246fb182e9922c1df5405fd8265d56804a6587712d564d",
    ),
    "UNVR.JK_2017-01-31_2022-01-31.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1213,
        bars_digest="11a36758e320a4a2a5b56c7c1276b51470d4aa0c3dfc618f26b1dd8dbcf5bf84",
        actions=11,
        actions_digest="443d7ddd6cb33ee4c8c260738cc84d4f908b437de49927ab2a32d61ec86550a2",
    ),
    "UNVR.JK_2017-01-31_2022-04-29.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=1272,
        bars_digest="49e6702f64d3c8f0ff62e2d18c2a98ffe86879e448ccec5d129c2719e9024390",
        actions=11,
        actions_digest="443d7ddd6cb33ee4c8c260738cc84d4f908b437de49927ab2a32d61ec86550a2",
    ),
    "UNVR.JK_2023-05-15_2023-06-09.json": Answers(
        runs=(),
        run_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        refused=(0, "", ""),
        refused_days="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        bars=17,
        bars_digest="1afaa62cbe28db1bc9b06515c9bd526195fe08ee95425f8f7e7e0575e70789bd",
        actions=0,
        actions_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
}


def test_every_recording_has_its_answers_pinned() -> None:
    assert sorted(PINNED) == [path.name for path in RECORDINGS]
    assert len(RECORDINGS) == 14


@pytest.mark.parametrize("path", RECORDINGS, ids=lambda path: path.stem)
def test_a_recording_restores_to_its_pinned_answers(path: Path) -> None:
    assert answers(path) == PINNED[path.name]
