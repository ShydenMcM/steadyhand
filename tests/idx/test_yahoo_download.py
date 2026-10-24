"""The one function that asks Yahoo, with yfinance stood in (#374 AC7): no line is excluded from
coverage any more (Shyden 2026-10-22, "Count them as unrun"), so what it asks and what it does
with the answer and with a failure are tested here; the real network run stays in the
yahoo-shape workflow (``tests/idx/test_yahoo_live.py``) and the real import in the integration
suite (``tests/integration/idx/test_yfinance_loads.py``)."""

from dataclasses import dataclass, field
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from steadyhand import DataUnavailableError
from steadyhand_idx import yahoo


@dataclass
class FakeTicker:
    """yfinance.Ticker stood in: keeps each history request, answers with set objects."""

    symbol: str
    asked: list[dict[str, Any]] = field(default_factory=list)
    frame: object = "the frame"
    splits: object = "the splits"
    error: Exception | None = None

    def history(self, **kwargs: Any) -> object:  # noqa: ANN401 - yfinance's frame is untyped
        self.asked.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.frame


def fake_yfinance(ticker: FakeTicker) -> SimpleNamespace:
    """yfinance stood in: its debug switch, and a Ticker that answers for *ticker* alone."""

    def make(symbol: str) -> FakeTicker:
        assert symbol == ticker.symbol, symbol
        return ticker

    debug = SimpleNamespace(hide_exceptions=True)
    return SimpleNamespace(config=SimpleNamespace(debug=debug), Ticker=make)


def test_it_asks_for_the_unadjusted_history_through_the_last_day_with_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticker = FakeTicker("BBCA.JK")
    module = fake_yfinance(ticker)
    seen: list[tuple[object, ...]] = []
    made = object()

    def history_from_frames(*given: object) -> object:
        seen.append(given)
        return made

    monkeypatch.setattr(yahoo, "history_from_frames", history_from_frames)
    returned = yahoo.download_history(
        "BBCA.JK", date(2024, 1, 2), date(2024, 1, 31), yahoo=lambda: module
    )
    assert returned is made
    # yfinance's end is exclusive, so it is asked for the day after the last one wanted.
    assert ticker.asked == [
        {"start": "2024-01-02", "end": "2024-02-01", "auto_adjust": False, "actions": True}
    ]
    assert seen == [("BBCA.JK", "the frame", "the splits")]


def test_it_makes_yfinance_raise_rather_than_log_a_failure() -> None:
    ticker = FakeTicker("BBCA.JK")
    module = fake_yfinance(ticker)
    ticker.error = RuntimeError("stop before the frames are read")
    with pytest.raises(DataUnavailableError):
        yahoo.download_history("BBCA.JK", date(2024, 1, 2), date(2024, 1, 2), yahoo=lambda: module)
    assert module.config.debug.hide_exceptions is False


def test_a_failure_is_raised_as_the_tickers_unavailable_data() -> None:
    ticker = FakeTicker("SRIL.JK", error=RuntimeError("HTTP Error 404: Not Found"))
    with pytest.raises(DataUnavailableError, match=r"SRIL\.JK") as raised:
        yahoo.download_history(
            "SRIL.JK", date(2024, 1, 2), date(2024, 1, 2), yahoo=lambda: fake_yfinance(ticker)
        )
    assert isinstance(raised.value.__cause__, RuntimeError)
