"""IDX trading costs: levy, VAT, sale tax, stamp duty, dividend tax and broker presets."""

import copy
import math
from datetime import date
from decimal import Decimal
from fractions import Fraction
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand import IDR, Currency, Money, Side, UnsupportedDateError
from steadyhand_idx._datafile import DataFileError, load_shipped
from steadyhand_idx.fees import BrokerPreset, FeeSchedule, parse_fees


@cache
def fees() -> FeeSchedule:
    return FeeSchedule.shipped()


@cache
def ajaib() -> BrokerPreset:
    return fees().preset("ajaib")


@cache
def custom() -> BrokerPreset:
    return fees().preset("custom")


TODAY = date(2026, 9, 25)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


@pytest.mark.parametrize(
    ("on", "levy"),
    [
        # t-fees.md §1.5 and t-verify.md §2: the levy per side, VAT included.
        (date(2020, 3, 13), "0.0430"),
        (date(2020, 6, 17), "0.0430"),
        (date(2020, 6, 18), "0.0380"),
        (date(2020, 12, 17), "0.0380"),
        (date(2020, 12, 18), "0.0430"),
        (date(2022, 3, 31), "0.0430"),
        (date(2022, 4, 1), "0.0433"),
        (date(2025, 1, 1), "0.0433"),
    ],
)
def test_the_levy_matches_the_research(on: date, levy: str) -> None:
    assert fees().levy.on(on).with_vat(fees().vat.on(on)) == Decimal(levy)


def test_the_tables_start_where_their_rows_are_verified() -> None:
    assert [table.first for table in fees().tables] == [
        date(2020, 3, 13),  # levy
        date(2016, 1, 1),  # VAT
        date(2016, 1, 1),  # sale tax
        date(2021, 1, 1),  # stamp duty
        date(2009, 1, 1),  # dividend tax
    ]


@pytest.mark.parametrize(
    ("preset", "side", "total"),
    [
        ("custom", Side.BUY, 20_980),  # 0.15% x 1.11 + 0.0433% = 0.2098%
        ("custom", Side.SELL, 30_980),  # plus the 0.1% sale tax
        ("ajaib", Side.BUY, 15_130),  # all-in 0.1513%
        ("ajaib", Side.SELL, 25_130),  # all-in 0.2513%
    ],
)
def test_worked_examples_on_ten_million(preset: str, side: Side, total: int) -> None:
    costs = fees().trade_costs(fees().preset(preset), side, rp(10_000_000), TODAY)
    assert costs.total == rp(total)
    assert costs.levy == rp(4_330)
    assert costs.tax == rp(10_000 if side is Side.SELL else 0)


def test_an_all_in_quote_keeps_its_total_when_the_levy_was_lower() -> None:
    # 18 Jun - 17 Dec 2020 the levy was 0.038%, so more of Ajaib's 0.1513% is commission.
    costs = fees().trade_costs(ajaib(), Side.BUY, rp(10_000_000), date(2020, 7, 1))
    assert costs.total == rp(15_130)
    assert costs.levy == rp(3_800)


def test_a_small_trade_rounds_the_total_up_once() -> None:
    # 1,001 x 0.2098% = 2.100098: the total rounds up to 3; the levy line (0.433) rounds down.
    costs = fees().trade_costs(custom(), Side.BUY, rp(1_001), TODAY)
    assert (costs.fee, costs.levy, costs.tax) == (rp(3), rp(0), rp(0))


# Each preset's all-in rate today, in percent, worked out by hand above: a literal pin.
TOTAL_PERCENT = {
    ("custom", Side.BUY): "0.2098",
    ("custom", Side.SELL): "0.3098",
    ("ajaib", Side.BUY): "0.1513",
    ("ajaib", Side.SELL): "0.2513",
}


@given(
    gross=st.integers(min_value=0, max_value=10**12),
    key=st.sampled_from(sorted(TOTAL_PERCENT, key=str)),
)
def test_costs_round_once_against_the_trader(gross: int, key: tuple[str, Side]) -> None:
    preset, side = key
    costs = fees().trade_costs(fees().preset(preset), side, rp(gross), TODAY)
    exact = Fraction(gross) * Fraction(TOTAL_PERCENT[key]) / 100
    assert costs.total.amount == math.ceil(exact)
    assert min(costs.fee.amount, costs.levy.amount, costs.tax.amount) >= 0
    expected_tax = gross // 1000 if side is Side.SELL else 0  # every sale pays 0.1%, rounded down
    assert costs.tax.amount == expected_tax


def test_gross_must_be_a_non_negative_rupiah_amount() -> None:
    with pytest.raises(ValueError, match=r"^gross must be a non-negative IDR amount, got IDR -1$"):
        fees().trade_costs(custom(), Side.BUY, rp(-1), TODAY)
    with pytest.raises(ValueError, match=r"got USD 1\.00"):
        fees().trade_costs(custom(), Side.BUY, Money(100, Currency("USD", 2)), TODAY)


def test_costs_before_the_levy_is_verified_are_refused() -> None:
    with pytest.raises(UnsupportedDateError, match=r"^fees\.toml \[levy\] has no verified row"):
        fees().trade_costs(custom(), Side.BUY, rp(1_000), date(2020, 3, 12))


@pytest.mark.parametrize(
    ("on", "traded", "duty"),
    [
        (date(2021, 1, 4), 0, 0),  # nothing traded, no confirmation
        (date(2021, 1, 4), 1, 10_000),  # every confirmation, however small, until 11 Jan 2022
        (date(2022, 1, 11), 1, 10_000),
        (date(2022, 1, 12), 1, 0),  # PP 3/2022's exemption from 12 Jan 2022
        (date(2022, 1, 12), 10_000_000, 0),  # "paling banyak Rp10.000.000" is exempt
        (date(2022, 1, 12), 10_000_001, 10_000),
    ],
)
def test_stamp_duty_is_charged_as_the_law_imposed_it(on: date, traded: int, duty: int) -> None:
    assert fees().daily_costs(rp(traded), on) == rp(duty)


def test_stamp_duty_before_2021_is_refused() -> None:
    with pytest.raises(
        UnsupportedDateError,
        match=r"^fees\.toml \[stamp_duty\] has no verified row for 2020-12-31",
    ):
        fees().daily_costs(rp(1), date(2020, 12, 31))
    with pytest.raises(ValueError, match=r"^traded must be a non-negative IDR amount"):
        fees().daily_costs(rp(-1), TODAY)


def test_dividend_tax_is_ten_percent_rounded_up_unless_reinvested() -> None:
    assert fees().dividend_tax(rp(1_000_000), reinvested_by_deadline=False, on=TODAY) == rp(100_000)
    assert fees().dividend_tax(rp(999), reinvested_by_deadline=False, on=TODAY) == rp(100)
    assert fees().dividend_tax(rp(999), reinvested_by_deadline=True, on=TODAY) == rp(0)


def test_only_presets_that_state_what_they_include_are_shipped() -> None:
    assert sorted(fees().presets) == ["ajaib", "custom"]
    assert ajaib().includes == {"levy", "commission_vat", "sale_tax"}
    assert custom().includes == frozenset()
    with pytest.raises(
        ValueError, match=r"^no broker fee preset named 'stockbit'; fees\.toml has ajaib, custom$"
    ):
        fees().preset("stockbit")


def _document() -> dict[str, object]:
    return copy.deepcopy(load_shipped("fees.toml"))


def _table(document: dict[str, object], name: str) -> dict[str, object]:
    found = document[name]
    assert isinstance(found, dict)
    return found


def _first_row(document: dict[str, object], name: str) -> dict[str, object]:
    found = document[name]
    assert isinstance(found, list)
    row = found[0]
    assert isinstance(row, dict)
    return row


def test_an_all_in_quote_smaller_than_what_it_includes_is_refused() -> None:
    document = _document()
    _table(_table(document, "presets"), "ajaib")["buy_percent"] = "0.04"
    with pytest.raises(
        DataFileError,
        match=(
            r"^fees\.toml preset 'ajaib': its buy quote is smaller than the costs it says it "
            r"includes on 2020-03-13$"
        ),
    ):
        parse_fees(document)


@pytest.mark.parametrize(
    ("includes", "message"),
    [
        (["levy", "levy"], "includes may list each of commission_vat, levy, sale_tax once"),
        (["broker"], "got 'broker'"),
    ],
)
def test_includes_is_checked(includes: list[str], message: str) -> None:
    document = _document()
    _table(_table(document, "presets"), "custom")["includes"] = includes
    with pytest.raises(DataFileError, match=message):
        parse_fees(document)


def test_bad_documents_are_refused() -> None:
    document = _document()
    _table(document, "presets")["broken"] = 5
    with pytest.raises(DataFileError, match=r"fees\.toml \[presets\.broken\] must be a table"):
        parse_fees(document)
    document = _document()
    document["presets"] = {}
    with pytest.raises(DataFileError, match=r"\[presets\] must be a table with at least one"):
        parse_fees(document)
    document = _document()
    _first_row(document, "levy")["exchange"] = "0.018"
    with pytest.raises(DataFileError, match=r"\[\[levy\]\] row 1: unknown key 'exchange'"):
        parse_fees(document)
    document = _document()
    del _first_row(document, "vat")["source"]
    with pytest.raises(DataFileError, match=r"\[\[vat\]\] row 1: missing key 'source'"):
        parse_fees(document)
    document = _document()
    _table(_table(document, "presets"), "ajaib")["checked"] = "2026-09-25"
    with pytest.raises(DataFileError, match="checked must be a TOML date"):
        parse_fees(document)
    document = _document()
    document["levies"] = []
    with pytest.raises(DataFileError, match=r"\[top level\]: unknown key 'levies'"):
        parse_fees(document)
