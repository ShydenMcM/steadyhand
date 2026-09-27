"""The reinvestment exemption's claims and their bookkeeping (M4 spec §6)."""

from datetime import date

import pytest

from steadyhand.exemption import DividendClaim, Protection
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.types import Instrument

BBCA = Instrument("BBCA", "IDX", IDR)
EX = date(2025, 6, 2)
PAY = date(2025, 6, 24)
DEADLINE = date(2026, 3, 31)
USD = Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


def claim(uncovered: int = 1_000, *protections: Protection) -> DividendClaim:
    return DividendClaim(BBCA, EX, PAY, rp(1_000), DEADLINE, rp(uncovered), protections)


def test_a_claim_may_be_split_between_uncovered_and_protected_parts() -> None:
    until = date(2027, 12, 31)
    split = claim(400, Protection(rp(250), until), Protection(rp(350), until))
    assert split.uncovered == rp(400)
    assert sum(p.amount.amount for p in split.protections) == 600  # 400 + 600 = the gross 1,000


def test_a_protection_is_a_positive_amount_with_a_date() -> None:
    with pytest.raises(ValueError, match=r"^a protection must be positive, got IDR 0$"):
        Protection(rp(0), DEADLINE)
    with pytest.raises(TypeError, match=r"^amount must be a Money, got int$"):
        Protection(1, DEADLINE)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^until must be a date"):
        Protection(rp(1), "2027-12-31")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("ex_date", "pay_date", "deadline"),
    [(PAY, PAY, DEADLINE), (EX, PAY, date(2025, 6, 23))],
)
def test_a_claim_is_paid_after_its_ex_date_and_no_later_than_its_deadline(
    ex_date: date, pay_date: date, deadline: date
) -> None:
    with pytest.raises(ValueError, match=r"^BBCA: a claim needs ex-date < pay date <= deadline"):
        DividendClaim(BBCA, ex_date, pay_date, rp(1_000), deadline, rp(1_000))


def test_a_claim_on_its_deadline_day_is_valid() -> None:
    assert DividendClaim(BBCA, EX, PAY, rp(1_000), PAY, rp(1_000)).deadline == PAY


def test_a_claims_amounts_are_in_its_stocks_currency() -> None:
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        DividendClaim(BBCA, EX, PAY, Money(1_000, USD), DEADLINE, rp(1_000))
    with pytest.raises(CurrencyMismatchError, match=r"^cannot combine IDR with USD$"):
        DividendClaim(BBCA, EX, PAY, rp(1_000), DEADLINE, Money(1_000, USD))
    with pytest.raises(CurrencyMismatchError):
        claim(0, Protection(Money(1, USD), DEADLINE))


@pytest.mark.parametrize(("gross", "uncovered"), [(0, 0), (1_000, -1)])
def test_a_claims_gross_is_positive_and_its_uncovered_part_not_negative(
    gross: int, uncovered: int
) -> None:
    with pytest.raises(
        ValueError,
        match=r"^BBCA: a claim's gross must be positive and its uncovered part not negative$",
    ):
        DividendClaim(BBCA, EX, PAY, rp(gross), DEADLINE, rp(uncovered))


def test_a_claims_parts_cannot_exceed_its_gross() -> None:
    until = date(2027, 12, 31)
    with pytest.raises(
        ValueError,
        match=(
            r"^BBCA: uncovered IDR 401 and protected IDR 600 exceed the gross dividend "
            r"IDR 1,000$"
        ),
    ):
        claim(401, Protection(rp(600), until))
    with pytest.raises(TypeError, match=r"^protection must be a Protection, got str$"):
        claim(0, "all of it")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^instrument must be an Instrument"):
        DividendClaim("BBCA", EX, PAY, rp(1_000), DEADLINE, rp(1_000))  # type: ignore[arg-type]
