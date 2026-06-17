"""Unit tests for day count calculators."""

from datetime import date
from decimal import Decimal

import pytest

from src.schedulers.day_count_calculator import DayCountCalculator


class TestACT360:
    """Test ACT/360 day count method (tracer bullet)."""

    def test_act_360_simple_period(self):
        """
        Tracer bullet: ACT/360 calculates year fraction correctly.

        Period: 2024-01-01 to 2024-02-01 (31 days)
        Expected: 31 / 360 = 0.086111
        """
        calculator = DayCountCalculator("ACT/360")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2024, 2, 1))

        # 31 days / 360 days = 0.086111...
        expected = Decimal("31") / Decimal("360")
        # Verify to 6 decimal places (0.086111)
        assert round(result, 6) == round(expected, 6)
        assert result > 0

    def test_act_360_full_year(self):
        """ACT/360 for 2024 (leap year) = 366 days / 360."""
        calculator = DayCountCalculator("ACT/360")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2025, 1, 1))
        # 2024 is leap year: 366 days / 360 = 1.016667
        expected = Decimal("366") / Decimal("360")
        assert round(result, 6) == round(expected, 6)

    def test_act_360_leap_year(self):
        """ACT/360 handles leap years correctly (counts actual days)."""
        calculator = DayCountCalculator("ACT/360")
        result = calculator.calculate_year_fraction(
            date(2024, 2, 29),  # Leap day
            date(2024, 3, 29),
        )
        # 29 days / 360
        expected = Decimal("29") / Decimal("360")
        assert round(result, 6) == round(expected, 6)

    def test_act_360_same_date(self):
        """ACT/360 for same date returns 0."""
        calculator = DayCountCalculator("ACT/360")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2024, 1, 1))
        assert result == Decimal("0")


class TestACT365Fixed:
    """Test ACT/365.FIXED day count method."""

    def test_act_365_fixed_simple_period(self):
        """
        ACT/365.FIXED: Jan 1 to Feb 1 (31 days) / 365.
        Expected: 31 / 365 = 0.084931
        """
        calculator = DayCountCalculator("ACT/365.FIXED")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2024, 2, 1))
        expected = Decimal("31") / Decimal("365")
        assert round(result, 6) == round(expected, 6)

    def test_act_365_fixed_full_year(self):
        """ACT/365.FIXED for 2024 leap year (366 days) / 365."""
        calculator = DayCountCalculator("ACT/365.FIXED")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2025, 1, 1))
        # 2024 is leap year: 366 days / 365 = 1.002739...
        expected = Decimal("366") / Decimal("365")
        assert round(result, 6) == round(expected, 6)

    def test_act_365_fixed_leap_year(self):
        """ACT/365.FIXED: 2024-01-01 to 2024-12-31 is 365 days (leap year spans 366 calendar days)."""
        calculator = DayCountCalculator("ACT/365.FIXED")
        result = calculator.calculate_year_fraction(
            date(2024, 1, 1), date(2024, 12, 31)
        )
        # 365 days / 365 = 1.0
        expected = Decimal("365") / Decimal("365")
        assert result == expected

    def test_act_365_fixed_same_date(self):
        """ACT/365.FIXED for same date returns 0."""
        calculator = DayCountCalculator("ACT/365.FIXED")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2024, 1, 1))
        assert result == Decimal("0")


class TestThirtyBy360:
    """Test 30/360 day count method."""

    def test_thirty_360_simple_period(self):
        """
        30/360: Jan 1 to Feb 1 (standardized as 30 days).
        Expected: 30 / 360 = 0.083333
        """
        calculator = DayCountCalculator("30/360")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2024, 2, 1))
        # Standardized: (360*(0-0) + 30*(2-1) + (1-1)) = 30
        expected = Decimal("30") / Decimal("360")
        assert round(result, 6) == round(expected, 6)

    def test_thirty_360_end_of_month(self):
        """
        30/360: Jan 31 to Feb 29.
        d1=30 (31→30), d2=29 (not adjusted)
        Day count: 360*0 + 30*1 + (29-30) = 29
        """
        calculator = DayCountCalculator("30/360")
        result = calculator.calculate_year_fraction(
            date(2024, 1, 31), date(2024, 2, 29)
        )
        expected = Decimal("29") / Decimal("360")
        assert round(result, 6) == round(expected, 6)

    def test_thirty_360_full_year(self):
        """30/360 for 12 months (each 30 days) = 360 / 360 = 1.0."""
        calculator = DayCountCalculator("30/360")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2025, 1, 1))
        # 360 * (2025-2024) + 30 * (1-1) + (1-1) = 360
        expected = Decimal("360") / Decimal("360")
        assert result == expected

    def test_thirty_360_month_boundary(self):
        """30/360: Jun 30 to Jul 31 (30 + 30 = 60 days standardized)."""
        calculator = DayCountCalculator("30/360")
        result = calculator.calculate_year_fraction(
            date(2024, 6, 30), date(2024, 8, 31)
        )
        # Day count: 360*(0) + 30*(8-6) + (30-30) = 60
        expected = Decimal("60") / Decimal("360")
        assert round(result, 6) == round(expected, 6)

    def test_thirty_360_same_date(self):
        """30/360 for same date returns 0."""
        calculator = DayCountCalculator("30/360")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2024, 1, 1))
        assert result == Decimal("0")

    def test_thirty_360_isda_strict(self):
        """30/360: D2 is 31, but D1 < 30. D2 should NOT be adjusted to 30."""
        calculator = DayCountCalculator("30/360")
        # 2026-02-27 to 2026-08-31
        # D1 = 27 (no change), D2 = 31 (no change since D1 < 30)
        # Standardized days: 360*0 + 30*6 + (31 - 27) = 184
        result = calculator.calculate_year_fraction(
            date(2026, 2, 27), date(2026, 8, 31)
        )
        expected = Decimal("184") / Decimal("360")
        assert result == expected


class TestThirtyEBy360:
    """Test 30E/360 day count method."""

    def test_thirty_e_360_unconditional_d2(self):
        """30E/360: D2 is 31, unconditionally adjusted to 30."""
        calculator = DayCountCalculator("30E/360")
        # 2026-02-27 to 2026-08-31
        # D1 = 27, D2 = 31 -> adjusted to 30
        # Standardized days: 360*0 + 30*6 + (30 - 27) = 183
        result = calculator.calculate_year_fraction(
            date(2026, 2, 27), date(2026, 8, 31)
        )
        expected = Decimal("183") / Decimal("360")
        assert round(result, 6) == round(expected, 6)

    def test_thirty_e_360_d1_adjustment(self):
        """30E/360: D1 is 31, adjusted to 30."""
        calculator = DayCountCalculator("30E/360")
        # 2026-08-31 to 2027-02-28
        # D1 = 31 -> adjusted to 30, D2 = 28
        # Standardized days: 360*0 + 30*6 + (28 - 30) = 178
        result = calculator.calculate_year_fraction(
            date(2026, 8, 31), date(2027, 2, 28)
        )
        expected = Decimal("178") / Decimal("360")
        assert result == expected


class TestDayCountCalculatorFactory:
    """Test DayCountCalculator factory and method selection."""

    def test_factory_invalid_method(self):
        """Factory raises ValueError for unknown method."""
        with pytest.raises(ValueError, match="Unknown day count method"):
            DayCountCalculator("INVALID/360")

    def test_factory_all_methods_supported(self):
        """Factory can instantiate all supported methods."""
        methods = ["ACT/360", "ACT/365.FIXED", "30/360", "30E/360"]
        for method in methods:
            calc = DayCountCalculator(method)
            assert calc is not None

    def test_decimal_precision(self):
        """Results maintain Decimal precision (no float conversion)."""
        calculator = DayCountCalculator("ACT/360")
        result = calculator.calculate_year_fraction(date(2024, 1, 1), date(2024, 1, 2))
        # Result should be Decimal, not float
        assert isinstance(result, Decimal)
        assert result == Decimal("1") / Decimal("360")

    def test_all_methods_return_decimal(self):
        """All methods return Decimal type for precision."""
        methods = ["ACT/360", "ACT/365.FIXED", "30/360", "30E/360"]
        for method_name in methods:
            calculator = DayCountCalculator(method_name)
            result = calculator.calculate_year_fraction(
                date(2024, 1, 1), date(2024, 1, 31)
            )
            assert isinstance(result, Decimal)
            assert result > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_negative_date_span_act_360(self):
        """ACT/360 with end date before start date returns negative."""
        calculator = DayCountCalculator("ACT/360")
        result = calculator.calculate_year_fraction(date(2024, 2, 1), date(2024, 1, 1))
        assert result < 0

    def test_negative_date_span_act_365(self):
        """ACT/365.FIXED with end date before start date returns negative."""
        calculator = DayCountCalculator("ACT/365.FIXED")
        result = calculator.calculate_year_fraction(date(2024, 2, 1), date(2024, 1, 1))
        assert result < 0

    def test_negative_date_span_30_360(self):
        """30/360 with end date before start date returns negative."""
        calculator = DayCountCalculator("30/360")
        result = calculator.calculate_year_fraction(date(2024, 2, 1), date(2024, 1, 1))
        assert result < 0

    def test_very_short_periods(self):
        """Single-day periods calculated consistently."""
        act360 = DayCountCalculator("ACT/360")
        act365 = DayCountCalculator("ACT/365.FIXED")
        thirty360 = DayCountCalculator("30/360")

        result_360 = act360.calculate_year_fraction(date(2024, 1, 1), date(2024, 1, 2))
        result_365 = act365.calculate_year_fraction(date(2024, 1, 1), date(2024, 1, 2))
        result_30 = thirty360.calculate_year_fraction(
            date(2024, 1, 1), date(2024, 1, 2)
        )

        # All should be positive and less than 1
        assert 0 < result_360 < 1
        assert 0 < result_365 < 1
        assert 0 < result_30 < 1

        # 360-day convention should be larger than 365-day
        assert result_360 > result_365
