"""Money: integer minor units, explicit rounding, no silent currency mixing."""

import operator
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from steadyhand.money import IDR, Currency, CurrencyMismatchError, Money, Rounding


def usd() -> Currency:
    return Currency("USD", 2)


def rp(amount: int) -> Money:
    return Money(amount, IDR)


class TestCurrency:
    def test_idr_has_no_minor_unit(self) -> None:
        assert IDR.code == "IDR"
        assert IDR.minor_units == 0

    @pytest.mark.parametrize("code", ["idr", "ID", "IDRX", "", "I1R"])
    def test_code_must_be_three_capital_letters(self, code: str) -> None:
        with pytest.raises(ValueError, match="currency code must be three capital letters"):
            Currency(code, 0)

    def test_code_must_be_a_string(self) -> None:
        with pytest.raises(TypeError, match="currency code must be a str, got NoneType"):
            Currency(None, 0)  # type: ignore[arg-type]

    @pytest.mark.parametrize("minor_units", [-1, 5, True])
    def test_minor_units_must_be_an_int_from_0_to_4(self, minor_units: int) -> None:
        with pytest.raises(ValueError, match="minor_units must be an int from 0 to 4"):
            Currency("USD", minor_units)

    @pytest.mark.parametrize("minor_units", [0, 4])
    def test_minor_units_boundaries_are_accepted(self, minor_units: int) -> None:
        assert Currency("XTS", minor_units).minor_units == minor_units


class TestConstruction:
    @pytest.mark.parametrize("amount", [Decimal(1), True, "1", 1.0])
    def test_amount_must_be_an_int(self, amount: object) -> None:
        with pytest.raises(TypeError, match="Money amount must be an int of minor units, got"):
            Money(amount, IDR)  # type: ignore[arg-type]

    def test_currency_must_be_a_currency(self) -> None:
        with pytest.raises(TypeError, match="Money currency must be a Currency, got str"):
            Money(1, "IDR")  # type: ignore[arg-type]

    def test_zero(self) -> None:
        assert Money.zero(usd()) == Money(0, usd())

    def test_equality_and_hash_include_the_currency(self) -> None:
        assert Money(0, IDR) != Money(0, usd())
        assert hash(rp(5)) == hash(rp(5))


class TestArithmetic:
    def test_add_subtract_negate(self) -> None:
        assert rp(7) + rp(5) == rp(12)
        assert rp(7) - rp(12) == rp(-5)
        assert -rp(7) == rp(-7)

    @pytest.mark.parametrize("name", ["add", "sub", "lt", "le", "gt", "ge"])
    def test_mixing_currencies_raises(self, name: str) -> None:
        with pytest.raises(CurrencyMismatchError, match="cannot combine IDR with USD"):
            getattr(operator, name)(rp(1), Money(1, usd()))

    @pytest.mark.parametrize(
        ("name", "message"),
        [
            ("add", r"unsupported operand type\(s\) for \+"),
            ("sub", r"unsupported operand type\(s\) for -"),
            ("lt", "'<' not supported"),
            ("le", "'<=' not supported"),
            ("gt", "'>' not supported"),
            ("ge", "'>=' not supported"),
        ],
    )
    def test_non_money_operands_are_refused(self, name: str, message: str) -> None:
        with pytest.raises(TypeError, match=message):
            getattr(operator, name)(rp(1), 1)

    def test_ordering(self) -> None:
        assert rp(1) < rp(2)
        assert rp(2) <= rp(2)
        assert rp(3) > rp(2)
        assert rp(2) >= rp(2)
        assert not rp(2) < rp(2)
        assert not rp(2) > rp(2)

    def test_multiply_by_a_share_count_on_either_side(self) -> None:
        assert rp(4_150) * 300 == rp(1_245_000)
        assert 300 * rp(4_150) == rp(1_245_000)

    @pytest.mark.parametrize("factor", [Decimal("1.5"), True, 1.5])
    def test_multiply_refuses_anything_but_an_int(self, factor: object) -> None:
        with pytest.raises(TypeError, match=r"multiply Money by an int quantity, got .*use times"):
            _ = rp(10) * factor  # type: ignore[operator]


class TestTimes:
    def test_rounds_up_for_what_you_pay(self) -> None:
        # A 0.15% fee on Rp 1,000,001 is Rp 1,500.0015 before rounding.
        assert rp(1_000_001).times(Decimal("0.0015"), Rounding.UP) == rp(1_501)

    def test_rounds_down_for_what_you_receive(self) -> None:
        assert rp(1_000_001).times(Decimal("0.0015"), Rounding.DOWN) == rp(1_500)

    def test_exact_results_are_not_moved(self) -> None:
        assert rp(1_000_000).times(Decimal("0.001"), Rounding.UP) == rp(1_000)
        assert rp(1_000_000).times(Decimal("0.001"), Rounding.DOWN) == rp(1_000)

    def test_direction_is_by_value_not_by_magnitude(self) -> None:
        assert rp(-3).times(Decimal("0.5"), Rounding.UP) == rp(-1)
        assert rp(-3).times(Decimal("0.5"), Rounding.DOWN) == rp(-2)

    def test_huge_amounts_are_exact(self) -> None:
        # 29+ significant digits: Decimal's default 28-digit context would drop the 0.0015.
        amount = 10**40 + 1
        assert rp(amount).times(Decimal("0.0015"), Rounding.UP) == rp(15 * 10**36 + 1)
        assert rp(amount).times(Decimal("0.0015"), Rounding.DOWN) == rp(15 * 10**36)

    @pytest.mark.parametrize("rate", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
    def test_rate_must_be_finite(self, rate: Decimal) -> None:
        with pytest.raises(ValueError, match="rate must be finite"):
            rp(1).times(rate, Rounding.UP)

    def test_rate_must_be_a_decimal(self) -> None:
        with pytest.raises(TypeError, match="rate must be a Decimal, got int"):
            rp(1).times(1, Rounding.UP)  # type: ignore[arg-type]

    @given(
        amount=st.integers(min_value=0, max_value=10**15),
        rate=st.decimals(min_value=0, max_value=1, places=6, allow_nan=False, allow_infinity=False),
    )
    def test_up_and_down_bracket_the_exact_value(self, amount: int, rate: Decimal) -> None:
        up = rp(amount).times(rate, Rounding.UP)
        down = rp(amount).times(rate, Rounding.DOWN)
        exact = amount * rate
        assert down.amount <= exact <= up.amount
        assert up.amount - down.amount <= 1


class TestFormatting:
    @pytest.mark.parametrize(
        ("amount", "code", "minor_units", "text"),
        [
            (1_500_000, "IDR", 0, "IDR 1,500,000"),
            (-1_500, "IDR", 0, "IDR -1,500"),
            (0, "IDR", 0, "IDR 0"),
            (1_205, "USD", 2, "USD 12.05"),
            (-5, "USD", 2, "USD -0.05"),
        ],
    )
    def test_str(self, amount: int, code: str, minor_units: int, text: str) -> None:
        assert str(Money(amount, Currency(code, minor_units))) == text
