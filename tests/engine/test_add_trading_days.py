"""add_trading_days: the one function behind the engine's pay date and the calendar's pay month."""

from datetime import date
from functools import cache

import pytest

from steadyhand.market import UnsupportedDateError, add_trading_days
from steadyhand_idx import IdxMarketRules


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


def test_it_skips_weekends_and_holidays_across_a_year_end() -> None:
    # From Friday 27 December 2024: Monday 30th is one; 31 December and 1 January are closed,
    # so Thursday 2 January is two and Friday 3 January is three.
    assert add_trading_days(rules(), date(2024, 12, 27), 3) == date(2025, 1, 3)


def test_it_skips_a_long_closure() -> None:
    # Idul Fitri 2025 closed the market from Friday 28 March to Monday 7 April.
    assert add_trading_days(rules(), date(2025, 3, 27), 1) == date(2025, 4, 8)


def test_it_may_start_on_a_day_the_market_is_closed() -> None:
    assert add_trading_days(rules(), date(2025, 1, 4), 1) == date(2025, 1, 6)


def test_zero_days_is_the_day_itself() -> None:
    assert add_trading_days(rules(), date(2025, 1, 4), 0) == date(2025, 1, 4)


def test_the_count_is_a_whole_number_of_days_not_below_zero() -> None:
    with pytest.raises(ValueError, match=r"^count must be at least 0, got -1$"):
        add_trading_days(rules(), date(2025, 1, 6), -1)
    with pytest.raises(TypeError, match=r"^count must be an int, got bool$"):
        add_trading_days(rules(), date(2025, 1, 6), True)


def test_a_day_past_the_holiday_data_is_refused_not_guessed() -> None:
    with pytest.raises(UnsupportedDateError, match=r"^holidays\.toml has no IDX holidays for 2028"):
        add_trading_days(rules(), date(2027, 12, 30), 3)
