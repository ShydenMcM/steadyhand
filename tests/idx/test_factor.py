"""Recovering Yahoo's unreported price factor from the IDX tick grid (#160 spec §4, §9.1)."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from steadyhand import IDR, Instrument, Money
from steadyhand.notes import Note
from steadyhand_idx._datafile import Dated, Where, load_shipped
from steadyhand_idx.factor import (
    FIT_TOLERANCE,
    GRID_START,
    MIN_PRICES,
    Grid,
    PriceRow,
    Restoration,
    Run,
    candidates,
    find_runs,
    is_noise,
    restore_dividend,
    restore_price,
)
from steadyhand_idx.notes import DATA_PRICES_RESTORED
from steadyhand_idx.ticks import TickRow, TickTier, parse_ticks


def grid() -> Grid:
    """The shipped grid, read inside each test so a stub cannot fail the module's collection."""
    return Grid.shipped()


VERIFIED_DAY = date(2021, 3, 1)


def days_from(first: date, count: int) -> list[date]:
    return [first + timedelta(days=offset) for offset in range(count)]


def recorded(
    true_days: Sequence[Sequence[int]],
    factor: Decimal,
    first: date = VERIFIED_DAY,
    noise: Decimal = Decimal(0),
) -> list[PriceRow]:
    """What Yahoo would show for *true_days*, each a day's four traded prices, over *factor*."""
    return [
        PriceRow(day, tuple(Decimal(price) / factor + noise for price in prices))
        for day, prices in zip(days_from(first, len(true_days)), true_days, strict=True)
    ]


def restored(rows: Sequence[PriceRow], run: Run) -> list[list[int]]:
    assert run.factor is not None
    return [[restore_price(p, run.factor, row.day).amount for p in row.prices] for row in rows]


# Six days on the Rp10 and Rp25 tiers of the five-tier grid: 24 prices, enough for a proof.
TRUE_DAYS = [
    [3550, 3600, 3520, 3580],
    [3580, 3620, 3560, 3610],
    [3610, 3640, 3590, 3600],
    [5025, 5100, 4990, 5075],
    [5075, 5150, 5050, 5125],
    [5125, 5175, 5100, 5150],
]


def test_true_grid_prices_scaled_by_a_known_factor_recover_it() -> None:
    rows = recorded(TRUE_DAYS, Decimal("1.100019"))
    (run,) = find_runs(rows)
    assert run.factor == Decimal("1.100019")
    assert (run.first, run.last, run.prices) == (VERIFIED_DAY, VERIFIED_DAY + timedelta(5), 24)
    assert restored(rows, run) == TRUE_DAYS


def test_a_run_crossing_tiers_is_proven_on_each_price_s_own_tier() -> None:
    crossing = [[480, 505, 476, 498], [1995, 2010, 1990, 2000], [4990, 5025, 4980, 5000]]
    rows = recorded(crossing * 2, Decimal("1.3"))
    (run,) = find_runs(rows)
    assert run.factor == Decimal("1.300000")
    assert restored(rows, run) == crossing * 2
    # Each price on its own tier's tick: Rp5 below Rp2,000, Rp10 from it.
    fitting = [grid().fits(Decimal(p), Decimal(1), VERIFIED_DAY) for p in (1995, 2005, 2010)]
    assert fitting == [True, False, True]


def test_the_window_rejects_half_and_double_the_factor_although_both_fit_the_grid() -> None:
    # Multiples of Rp100: halved they sit on the Rp5 or Rp10 tier, doubled on the Rp10 or Rp25 tier.
    true_days = [
        [3500, 8400, 6300, 7100],
        [4200, 9500, 6400, 8600],
        [8300, 8800, 4700, 7400],
        [8000, 2100, 5500, 3500],
        [6200, 2600, 4900, 2600],
        [7500, 7300, 8500, 6700],
    ]
    rows = recorded(true_days, Decimal("1.7"))
    half, double = Decimal("0.85"), Decimal("3.4")
    assert all(
        grid().fits(p, half, row.day) and grid().fits(p, double, row.day)
        for row in rows
        for p in row.prices
    )
    (run,) = find_runs(rows)
    assert run.factor == Decimal("1.700000")


def test_two_fitting_candidates_leave_the_run_refused() -> None:
    # Odd multiples of Rp50 on the Rp25 tier also fit 1.5 times the factor, which is inside [1, 2).
    true_days = [
        [6350, 6450, 6550, 6650],
        [6850, 6950, 7050, 7150],
        [7350, 7450, 7550, 7650],
        [6350, 7150, 6450, 7050],
        [7650, 6550, 6950, 7350],
        [6650, 7450, 6850, 7550],
    ]
    rows = recorded(true_days, Decimal("1.2"))
    assert [round(f, 6) for f in candidates(rows[-1], grid())] == [
        Decimal("1.200000"),
        Decimal("1.800000"),
    ]
    (run,) = find_runs(rows)
    assert run.factor is None
    assert run.prices == 24


def test_fewer_than_twenty_prices_stay_refused() -> None:
    rows = recorded(TRUE_DAYS[:4], Decimal("1.1"))
    (run,) = find_runs(rows)
    assert run.prices == MIN_PRICES - 4
    assert run.factor is None
    assert find_runs(recorded(TRUE_DAYS[:5], Decimal("1.1")))[0].factor == Decimal("1.100000")


def test_two_stacked_adjustments_split_on_the_day_the_factor_changes() -> None:
    older = recorded(TRUE_DAYS, Decimal("1.3"))
    newer = recorded(TRUE_DAYS, Decimal("1.1"), first=VERIFIED_DAY + timedelta(6))
    first, second = find_runs([*older, *newer])
    assert (first.first, first.last, first.factor) == (
        VERIFIED_DAY,
        VERIFIED_DAY + timedelta(5),
        Decimal("1.300000"),
    )
    assert (second.first, second.last, second.factor) == (
        VERIFIED_DAY + timedelta(6),
        VERIFIED_DAY + timedelta(11),
        Decimal("1.100000"),
    )


def test_a_row_that_no_candidate_fits_is_a_single_unprovable_day() -> None:
    rows = [
        *recorded(TRUE_DAYS, Decimal("1.1")),
        PriceRow(VERIFIED_DAY + timedelta(6), (Decimal("0.4"),) * 4),
    ]
    proven, odd = find_runs(rows)
    assert proven.factor == Decimal("1.100000")
    assert (odd.days, odd.prices, odd.factor) == ((VERIFIED_DAY + timedelta(6),), 4, None)
    assert candidates(rows[-1], grid()) == []


def test_a_day_before_the_first_grid_is_never_provable() -> None:
    before = GRID_START - timedelta(days=len(TRUE_DAYS))
    rows = recorded(TRUE_DAYS, Decimal("1.1"), first=before)
    assert grid().tiers_on(GRID_START - timedelta(1)) is None
    assert all(run.factor is None and len(run.days) == 1 for run in find_runs(rows))
    with pytest.raises(ValueError, match=r"no tick grid for 2013-12-31, before 2014-01-06"):
        restore_price(Decimal(3550), Decimal(1), date(2013, 12, 31))


@pytest.mark.parametrize(
    ("price", "fits_on"),
    [
        # 2,015 is on the old Rp5 grid but off the five-tier Rp10 grid; 301 is on the old Rp1 grid
        # but off the five-tier Rp2 grid (t-hist.md §3).
        (2015, {date(2014, 1, 6), date(2016, 4, 29)}),
        (301, {date(2014, 1, 6), date(2016, 4, 29)}),
        # 2,010 is on both grids; 5,010 on neither.
        (
            2010,
            {
                date(2014, 1, 6),
                date(2016, 4, 29),
                date(2016, 5, 2),
                date(2020, 3, 12),
                date(2020, 3, 13),
            },
        ),
        (5010, set()),
    ],
)
def test_each_grid_era_is_used_on_its_own_days(price: int, fits_on: set[date]) -> None:
    edges = [
        date(2014, 1, 6),
        date(2016, 4, 29),
        date(2016, 5, 2),
        date(2020, 3, 12),
        date(2020, 3, 13),
    ]
    assert {day for day in edges if grid().fits(Decimal(price), Decimal(1), day)} == fits_on


def test_the_verified_era_reads_the_shipped_tick_table() -> None:
    table = parse_ticks(load_shipped("tick_sizes.toml"))
    assert grid().tiers_on(date(2020, 3, 13)) == table.on(date(2020, 3, 13)).tiers
    assert Grid.shipped() is Grid.shipped()


def test_the_verified_table_takes_over_on_its_own_first_day() -> None:
    sevens = (TickTier(1, 7),)
    verified = Dated(Where("test", "ticks"), (date(2020, 3, 13),), (TickRow("test", 100, sevens),))
    grid = Grid(verified)
    assert grid.tiers_on(date(2020, 3, 13)) == sevens
    assert grid.tiers_on(date(2020, 3, 12)) != sevens
    assert not grid.fits(Decimal(8), Decimal(1), date(2020, 3, 13))
    assert grid.fits(Decimal(8), Decimal(1), date(2020, 3, 12))


def test_a_price_below_the_first_tier_uses_the_first_tick() -> None:
    assert grid().nearest(Decimal("0.6"), VERIFIED_DAY) == 1
    assert grid().nearest(Decimal("0.4"), VERIFIED_DAY) == 0


def test_a_fit_is_within_one_rupiah_cent() -> None:
    assert grid().fits(Decimal(3550) + FIT_TOLERANCE, Decimal(1), VERIFIED_DAY)
    assert not grid().fits(
        Decimal(3550) + FIT_TOLERANCE + Decimal("0.0001"), Decimal(1), VERIFIED_DAY
    )


def test_a_noise_run_is_restored_onto_the_grid_it_almost_sits_on() -> None:
    rows = recorded(TRUE_DAYS, Decimal(1), noise=Decimal("0.0006"))
    (run,) = find_runs(rows)
    assert run.factor == Decimal("0.9999999")  # noise: it rounds to 1.000000
    assert restored(rows, run) == TRUE_DAYS


# TINS 2014 (spec §3.5): reversing an odd split leaves Rp0.0006 of upward noise, and on the old
# three-tier grid twice every price is on the Rp5 tier too.
TINS_DAYS = [[1965, 1975, 1960, 1970], [1910, 1925, 1905, 1915], [2045, 2050, 2040, 2045]] * 2


def test_upward_noise_at_the_first_price_keeps_one_as_a_candidate() -> None:
    rows = recorded(TINS_DAYS, Decimal(1), first=date(2014, 3, 3), noise=Decimal("0.0006"))
    assert rows[-1].prices[0] == Decimal("2045.0006")
    assert [round(f, 6) for f in candidates(rows[-1], grid())] == [
        Decimal("1.000000"),
        Decimal("1.999999"),
    ]
    (run,) = find_runs(rows)
    assert run.factor is None


def test_downward_noise_at_the_first_price_keeps_one_as_a_candidate() -> None:
    rows = recorded(TRUE_DAYS, Decimal(1), noise=Decimal("-0.0006"))
    assert round(candidates(rows[-1], grid())[0], 6) == 1
    assert find_runs(rows)[0].factor == 1


# The upper edge (plan scope decision 19): downward noise at p1 puts 2 * p1 just below the true
# whole rupiah when the true factor is near 2. Here true prices of Rp50 and Rp82 on the 2015 grid,
# recorded over 1.9999201 with Rp0.001 of downward noise, give p1 = 24.9999988: the true price,
# Rp50, is above 2 * p1, so a window that stopped below 2 * p1 left f = 1 alone and "proved" it.
EDGE_DAYS = [[50, 50, 50, 50]] * 4 + [[50, 50, 50, 82]]


def test_downward_noise_near_a_factor_of_two_keeps_the_true_factor_a_candidate() -> None:
    rows = recorded(
        EDGE_DAYS, Decimal("1.9999201"), first=date(2015, 3, 2), noise=Decimal("-0.001")
    )
    assert [round(f, 6) for f in candidates(rows[-1], grid())] == [
        Decimal("1.000000"),
        Decimal("2.000000"),
    ]
    (run,) = find_runs(rows)
    assert run.factor is None


def test_restored_prices_are_whole_rupiah_on_their_tick() -> None:
    assert restore_price(Decimal("3227.2706"), Decimal("1.100019"), VERIFIED_DAY) == Money(
        3550, IDR
    )
    assert restore_price(Decimal("4568.10"), Decimal("1.100019"), VERIFIED_DAY) == Money(5025, IDR)


def test_restored_dividends_are_quantised_to_one_hundredth_of_a_rupiah_cent() -> None:
    assert restore_dividend(Decimal("89.91268"), Decimal("1.100019")) == Decimal("98.9057")
    assert restore_dividend(Decimal("10.00005"), Decimal(1)) == Decimal("10.0000")
    assert restore_dividend(Decimal("10.00015"), Decimal(1)) == Decimal("10.0002")


def test_no_rows_form_no_runs() -> None:
    assert find_runs([]) == ()


ERAS = (date(2015, 3, 2), date(2017, 3, 1), VERIFIED_DAY)


@st.composite
def true_run(draw: st.DrawFn) -> tuple[date, list[list[int]]]:
    """Five to eight days of traded prices on one era's grid, within a factor of two."""
    first = draw(st.sampled_from(ERAS))
    base = draw(st.integers(min_value=50, max_value=20_000))
    days = draw(st.integers(min_value=5, max_value=8))
    prices: list[list[int]] = []
    for offset in range(days):
        day = first + timedelta(offset)
        raw = draw(st.lists(st.integers(base, 2 * base), min_size=4, max_size=4))
        nearest = [grid().nearest(Decimal(p), day) for p in raw]
        prices.append([int(n) for n in nearest if n is not None])
    return first, prices


@example(drawn=(date(2015, 3, 2), EDGE_DAYS), factor=Decimal("1.9999201"), noise=Decimal("-0.001"))
@given(
    true_run(),
    st.decimals(min_value=1, max_value=Decimal("1.9999999"), places=7),
    st.sampled_from([Decimal(0), Decimal("0.001"), Decimal("-0.001"), Decimal("0.0004")]),
)
def test_a_proven_factor_restores_the_true_prices(
    drawn: tuple[date, list[list[int]]], factor: Decimal, noise: Decimal
) -> None:
    """The safety claim (spec §4.4): a run is either proven at the true factor or left refused."""
    first, true_days = drawn
    rows = recorded(true_days, factor, first=first, noise=noise)
    for run in find_runs(rows):
        if run.factor is not None:
            members = [row for row in rows if run.first <= row.day <= run.last]
            want = [true_days[rows.index(row)] for row in members]
            assert restored(members, run) == want


@pytest.mark.parametrize(
    ("factor", "noise"),
    [
        (Decimal("0.9999995"), True),
        (Decimal("0.9999999"), True),
        (Decimal("1.0000004"), True),
        (Decimal("1.000001"), False),
        (Decimal("0.9999994"), False),
    ],
)
def test_a_noise_factor_is_one_that_rounds_to_one(factor: Decimal, *, noise: bool) -> None:
    assert is_noise(factor) is noise


def test_noise_is_judged_at_six_decimal_places() -> None:
    assert is_noise(Decimal("1.0000005"))
    assert not is_noise(Decimal("1.0000015"))


BBRI = Instrument("BBRI", "IDX", IDR)


def test_a_restoration_s_note_names_its_span_factor_and_proof() -> None:
    run = Restoration(BBRI, date(2017, 1, 31), date(2021, 9, 7), Decimal("1.100019"), 4_412)
    assert not run.noise
    assert run.note == Note(
        DATA_PRICES_RESTORED,
        "BBRI: Yahoo's prices from 2017-01-31 to 2021-09-07 carry an adjustment Yahoo does not "
        "report, so steadyhand restored them: every price and dividend in that span is "
        "multiplied by 1.100019, proven by 4,412 prices that fit the IDX tick grid at that "
        "factor and at no other.",
    )


def test_a_noise_restoration_s_note_says_it_is_a_rounding_error() -> None:
    run = Restoration(BBRI, date(2019, 1, 2), date(2019, 3, 29), Decimal("0.9999999"), 240)
    assert run.noise
    assert run.note == Note(
        DATA_PRICES_RESTORED,
        "BBRI: Yahoo's prices from 2019-01-02 to 2019-03-29 miss whole rupiah by a rounding "
        "error after its reported splits are reversed, so steadyhand put each one on the IDX "
        "tick grid, proven by 240 prices that fit it with no other factor.",
    )
