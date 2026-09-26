"""UnavailableDaysError: a source's refusal of particular days, which a backtest can skip."""

from datetime import date

import pytest

from steadyhand.data import DataUnavailableError, UnavailableDaysError

DAYS = (date(2021, 9, 6), date(2021, 9, 7))


def test_it_names_the_days_and_keeps_the_message() -> None:
    message = "BBRI: two days refused"
    with pytest.raises(UnavailableDaysError, match=r"^BBRI: two days refused$") as caught:
        raise UnavailableDaysError(message, list(DAYS))
    assert caught.value.days == DAYS
    assert isinstance(caught.value, DataUnavailableError)


def test_it_needs_at_least_one_day() -> None:
    with pytest.raises(ValueError, match=r"^an unavailable-days error must name at least one day$"):
        UnavailableDaysError("nothing", [])


@pytest.mark.parametrize("days", [DAYS[::-1], (DAYS[0], DAYS[0])])
def test_the_days_are_different_and_in_order(days: tuple[date, ...]) -> None:
    with pytest.raises(ValueError, match=r"^the unavailable days must be different and in date"):
        UnavailableDaysError("bad", days)
