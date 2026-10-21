"""The real yfinance, imported as the Yahoo download imports it (#374 AC7): the module loads and
holds what ``download_history`` uses. Too heavy an import for a unit test; no network is asked."""

from steadyhand_idx.yahoo import _yfinance


def test_the_real_yfinance_loads_with_what_the_download_uses() -> None:
    module = _yfinance()
    assert module.__name__ == "yfinance"
    assert callable(module.Ticker)
    assert isinstance(module.config.debug.hide_exceptions, bool)
