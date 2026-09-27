"""The reinvestment exemption's claims and their bookkeeping (M4 spec §6)."""

from dataclasses import replace
from datetime import date
from functools import cache

import pytest

from steadyhand.exemption import ClaimDay, DividendClaim, Protection, cover_claims, settle_claims
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_DEADLINE_MISSED, Note
from steadyhand.portfolio import MovementKind, Portfolio
from steadyhand.types import Costs, Fill, Instrument, Order, Side
from steadyhand_idx import IdxMarketRules

BBCA = Instrument("BBCA", "IDX", IDR)
EX = date(2025, 6, 2)
PAY = date(2025, 6, 24)
DEADLINE = date(2026, 3, 31)
USD = Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


@cache
def rules() -> IdxMarketRules:
    return IdxMarketRules()


class _RateRises(IdxMarketRules):
    """IDX, but the dividend tax doubles to 20% from 2026."""

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        tax = super().dividend_tax(gross, on=on)
        return tax + tax if on.year >= 2026 else tax


class _TaxFree(IdxMarketRules):
    """IDX, but in a market that taxes no dividend."""

    def dividend_tax(self, gross: Money, *, on: date) -> Money:
        return Money.zero(gross.currency)


def buy(day: date, value: int, side: Side = Side.BUY, costs: int = 0) -> Fill:
    """One share of BBRI bought (or sold) on *day* for *value*, with *costs* on top."""
    order = Order(Instrument("BBRI", "IDX", IDR), side, 1, day)
    return Fill(order, day, 1, rp(value), Costs(fee=rp(costs), levy=rp(0), tax=rp(0)))


def settle(
    claims: tuple[DividendClaim, ...],
    day: date,
    *fills: Fill,
    market: IdxMarketRules | None = None,
) -> ClaimDay:
    market = rules() if market is None else market
    return settle_claims(Portfolio.empty(IDR), cover_claims(claims, fills, market), day, market)


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


def test_a_buy_covers_a_claim_with_its_value_before_costs() -> None:
    day = date(2025, 7, 1)
    after = settle((claim(),), day, buy(day, 600, costs=5))
    # 1,000 - 600 = 400 still to reinvest; a 2025 purchase is held through 31 Dec 2027.
    assert after.claims == (claim(400, Protection(rp(600), date(2027, 12, 31))),)
    assert (after.tax, after.notes, after.portfolio.ledger) == (rp(0), (), ())


def test_buys_cover_the_oldest_pay_date_first_and_spill_into_the_next() -> None:
    newer = claim()  # paid 24 June 2025
    older = DividendClaim(
        BBCA, date(2025, 5, 20), date(2025, 6, 10), rp(1_000), DEADLINE, rp(1_000)
    )
    day = date(2025, 7, 1)
    after = settle((newer, older), day, buy(day, 1_200), buy(day, 300))
    until = date(2027, 12, 31)
    # The 1,200 buy covers the older claim's 1,000 and 200 of the newer; the 300 buy covers 300.
    assert after.claims == (
        claim(500, Protection(rp(200), until), Protection(rp(300), until)),
        DividendClaim(
            BBCA,
            date(2025, 5, 20),
            date(2025, 6, 10),
            rp(1_000),
            DEADLINE,
            rp(0),
            (Protection(rp(1_000), until),),
        ),
    )


def test_a_buy_larger_than_every_claim_leaves_the_rest_unclaimed() -> None:
    day = date(2025, 7, 1)
    after = settle((claim(),), day, buy(day, 5_000))
    assert after.claims == (claim(0, Protection(rp(1_000), date(2027, 12, 31))),)


@pytest.mark.parametrize(
    ("fill", "covered"),
    [
        (buy(date(2025, 6, 23), 600), 0),  # the day before the dividend was paid
        (buy(PAY, 600), 600),  # the pay day itself
        (buy(DEADLINE, 600), 600),  # the deadline itself
        (buy(date(2025, 7, 1), 600, Side.SELL), 0),  # a sale reinvests nothing
    ],
)
def test_only_a_buy_from_the_pay_day_to_the_deadline_covers(fill: Fill, covered: int) -> None:
    after = settle((claim(),), fill.day, fill)
    assert after.claims[0].uncovered == rp(1_000 - covered)


def test_what_misses_the_deadline_is_taxed_the_next_day_and_the_claim_keeps_its_protection() -> (
    None
):
    protected = Protection(rp(600), date(2027, 12, 31))
    day = date(2026, 4, 1)
    after = settle((claim(400, protected),), day)
    assert after.tax == rp(40)  # 10% of the 400 not reinvested
    ledger = after.portfolio.ledger
    assert [(m.kind, m.amount, m.day) for m in ledger] == [(MovementKind.TAX, rp(-40), day)]
    assert after.notes == (
        Note(
            EXEMPTION_DEADLINE_MISSED,
            "BBCA: IDR 400 of the dividend paid on 2025-06-24 was not reinvested by 2026-03-31, "
            "so its tax of IDR 40, owed from 2025-06-24, is booked today",
        ),
    )
    assert after.claims == (claim(0, protected),)


def test_nothing_is_taxed_on_the_deadline_itself() -> None:
    after = settle((claim(),), DEADLINE)
    assert (after.tax, after.notes, after.claims) == (rp(0), (), (claim(),))


def test_a_claim_with_nothing_left_after_its_deadline_is_closed() -> None:
    after = settle((claim(999),), date(2026, 4, 1))
    assert after.tax == rp(100)  # 99.9 rounds up
    assert after.claims == ()


def test_a_claim_fully_reinvested_by_its_deadline_books_nothing() -> None:
    protected = Protection(rp(1_000), date(2027, 12, 31))
    after = settle((claim(0, protected),), date(2026, 4, 1))
    assert (after.tax, after.notes, after.claims) == (rp(0), (), (claim(0, protected),))


def test_the_deadline_tax_is_at_the_rate_in_force_on_the_pay_day() -> None:
    after = settle((claim(400),), date(2026, 4, 1), market=_RateRises())
    assert after.tax == rp(40)  # 10% as on 24 June 2025, not 2026's 20%


def test_an_untaxed_market_books_no_zero_tax_and_emits_no_note() -> None:
    after = settle((claim(400),), date(2026, 4, 1), market=_TaxFree())
    assert (after.tax, after.notes, after.claims, after.portfolio.ledger) == (rp(0), (), (), ())


def test_a_buy_used_up_by_an_older_claim_leaves_the_newer_one_untouched() -> None:
    older = DividendClaim(
        BBCA, date(2025, 5, 20), date(2025, 6, 10), rp(1_000), DEADLINE, rp(1_000)
    )
    day = date(2025, 7, 1)
    after = settle((claim(), older), day, buy(day, 1_000))
    protected = Protection(rp(1_000), date(2027, 12, 31))
    assert after.claims == (claim(), replace(older, uncovered=rp(0), protections=(protected,)))
