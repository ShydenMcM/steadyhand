"""The reinvestment exemption's claims and their bookkeeping (M4 spec §6)."""

from dataclasses import replace
from datetime import date, timedelta
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.exemption import ClaimDay, DividendClaim, Protection, cover_claims, settle_claims
from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money
from steadyhand.notes import EXEMPTION_CLAIM_BROKEN, EXEMPTION_DEADLINE_MISSED, Note
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
    covered = cover_claims(claims, fills, market)
    return settle_claims(Portfolio.empty(IDR), covered, None, day, market)


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


JUL1, JUL2, JUL3 = date(2025, 7, 1), date(2025, 7, 2), date(2025, 7, 3)  # 1 July settles 3 July
UNTIL = date(2027, 12, 31)


def invested(amount: int) -> Portfolio:
    """A portfolio whose one position cost *amount*, bought before any day below."""
    book = Portfolio.empty(IDR)
    if amount == 0:
        return book
    fill = buy(date(2025, 6, 2), amount)
    return book.deposit(rp(amount), fill.day).apply_fill(fill, fill.day)


def close(
    claims: tuple[DividendClaim, ...],
    day: date,
    held: int,
    since: date | None = None,
    market: IdxMarketRules | None = None,
) -> ClaimDay:
    market = rules() if market is None else market
    return settle_claims(invested(held), claims, since, day, market)


def test_protections_past_their_date_fall_away_and_close_the_claim() -> None:
    ending = Protection(rp(600), JUL1)
    after = close((claim(0, ending),), JUL1, 0)  # protected through 1 July, so still counted
    assert (after.claims, after.shortfall_since) == ((claim(0, ending),), JUL1)
    after = close((claim(0, ending),), JUL2, 0, JUL1)
    assert (after.claims, after.shortfall_since, after.tax) == ((), None, rp(0))


def test_a_shortfall_within_the_settlement_grace_keeps_the_claim() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    first = close((held,), JUL1, 400)
    assert (first.claims, first.shortfall_since, first.tax) == ((held,), JUL1, rp(0))
    second = close((held,), JUL2, 400, JUL1)  # the shortfall's first day is kept
    assert (second.claims, second.shortfall_since, second.tax) == ((held,), JUL1, rp(0))


def test_a_shortfall_gone_before_the_grace_ends_clears_its_day() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), JUL2, 1_000, JUL1)  # a rotation: bought back within the cycle
    assert (after.claims, after.shortfall_since, after.tax) == ((held,), None, rp(0))


def test_a_shortfall_still_there_at_the_settlement_close_breaks() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), JUL3, 400, JUL1)
    # 1,000 protected against 400 invested: 600 breaks, and 10% of it is booked today.
    assert (after.tax, after.shortfall_since) == (rp(60), None)
    assert after.claims == (claim(0, Protection(rp(400), UNTIL)),)
    ledger = after.portfolio.ledger
    assert [(m.kind, m.amount, m.day) for m in ledger][-1] == (MovementKind.TAX, rp(-60), JUL3)
    assert after.notes == (
        Note(
            EXEMPTION_CLAIM_BROKEN,
            "BBCA: IDR 600 reinvested from the dividend paid on 2025-06-24 was no longer invested "
            "when the settlement grace ended, so its tax of IDR 60, owed from 2025-06-24, is "
            "booked today",
        ),
    )


def test_breaks_take_the_latest_protection_first() -> None:
    older = DividendClaim(
        BBCA,
        date(2025, 5, 20),
        date(2025, 6, 10),
        rp(1_000),
        DEADLINE,
        rp(500),
        (Protection(rp(500), UNTIL),),
    )
    later = claim(500, Protection(rp(500), date(2028, 12, 31)))
    after = close((older, later), JUL3, 300, JUL1)
    # 1,000 protected against 300 invested: 700 breaks, the 2028 protection's 500 first, then
    # 200 of the 2027 one. Tax is 10% of each claim's part, 20 and 50, in the claims' order.
    assert after.claims == (
        replace(older, protections=(Protection(rp(300), UNTIL),)),
        replace(later, protections=()),
    )
    assert after.tax == rp(70)
    assert [note.text.split(":")[0] for note in after.notes] == ["BBCA", "BBCA"]
    assert ["IDR 200 " in after.notes[0].text, "IDR 500 " in after.notes[1].text] == [True, True]


def test_equal_dates_break_the_newest_claim_and_its_last_protection_first() -> None:
    older = DividendClaim(
        BBCA,
        date(2025, 5, 20),
        date(2025, 6, 10),
        rp(1_000),
        DEADLINE,
        rp(0),
        (Protection(rp(1_000), UNTIL),),
    )
    newer = claim(0, Protection(rp(600), UNTIL), Protection(rp(400), UNTIL))
    after = close((older, newer), JUL3, 1_700, JUL1)
    # 2,000 protected against 1,700: 300 breaks from the newer claim's last protection.
    assert after.claims == (
        older,
        claim(0, Protection(rp(600), UNTIL), Protection(rp(100), UNTIL)),
    )


def test_a_broken_claim_is_taxed_at_its_pay_day_rate() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), date(2026, 7, 3), 400, date(2026, 7, 1), _RateRises())
    assert after.tax == rp(60)  # 10% as on 24 June 2025, not 2026's 20%


def test_an_untaxed_market_breaks_the_claim_without_booking_or_a_note() -> None:
    held = claim(0, Protection(rp(1_000), UNTIL))
    after = close((held,), JUL3, 400, JUL1, _TaxFree())
    assert (after.tax, after.notes) == (rp(0), ())
    assert after.claims == (claim(0, Protection(rp(400), UNTIL)),)


def test_each_booking_rounds_up_on_its_own() -> None:
    # M4 spec §9 and its pass 3: Rp2 taxed in two pieces of 1 books 1 + 1 = 2, where the full
    # tax on Rp2 is 0.2 rounded up to 1.
    split = DividendClaim(BBCA, EX, PAY, rp(2), JUL1, rp(1), (Protection(rp(1), UNTIL),))
    after = close((split,), JUL3, 0, JUL1)
    assert (after.tax, len(after.notes), after.claims) == (rp(2), 2, ())
    assert rules().dividend_tax(rp(2), on=PAY) == rp(1)


TRADING = tuple(
    day for day in (JUL1 + timedelta(days=n) for n in range(16)) if rules().is_trading_day(day)
)


def test_the_property_below_runs_over_twelve_trading_days() -> None:
    assert (len(TRADING), TRADING[0], TRADING[-1]) == (12, JUL1, date(2025, 7, 16))


@given(
    gross=st.integers(1, 100_000),
    steps=st.lists(
        st.tuples(st.integers(0, 100), st.integers(0, 150)), min_size=1, max_size=len(TRADING)
    ),
    last_day=st.integers(0, len(TRADING) - 1),
)
def test_a_claims_tax_never_exceeds_its_full_tax_plus_one_unit_per_extra_booking(
    gross: int, steps: list[tuple[int, int]], last_day: int
) -> None:
    # M4 spec §9: each booking rounds up on its own, so pieces may add up to a unit more each.
    # Each day buys and holds a percentage of the gross, so claims are covered in parts and
    # shortfalls last long enough to break.
    opened = DividendClaim(BBCA, EX, PAY, rp(gross), TRADING[last_day], rp(gross))
    claims: tuple[DividendClaim, ...] = (opened,)
    since: date | None = None
    tax, bookings = rp(0), 0
    for day, (bought_percent, held_percent) in zip(TRADING, steps, strict=False):
        bought, held = gross * bought_percent // 100, gross * held_percent // 100
        fills = [buy(day, bought)] if bought else []
        covered = cover_claims(claims, fills, rules())
        after = settle_claims(invested(held), covered, since, day, rules())
        claims, since = after.claims, after.shortfall_since
        tax += after.tax
        bookings += len(after.notes)
    full = rules().dividend_tax(rp(gross), on=PAY)
    assert tax.amount <= full.amount + max(bookings - 1, 0)
