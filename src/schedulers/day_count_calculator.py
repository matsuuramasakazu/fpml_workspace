"""
Day count calculators for ISDA conventions.

Implements standard day count methods used in financial calculations:
- ACT/360: Actual days / 360-day year (US convention)
- ACT/365.FIXED: Actual days / 365-day year (fixed denominator)
- 30/360: Standardized 30-day months / 360-day year (Bond market)

These methods calculate Year Fraction / Day Count Fraction, essential for:
- Interest accrual calculations
- Swap and derivative pricing
- Bond yield calculations

Strategy Pattern Implementation:
- Abstract base DayCountMethod for common interface
- Concrete implementations for each convention
- Factory pattern via DayCountCalculator for method selection
- Extensible design for custom methods via register_method()

All calculations use Decimal type to maintain precision required for
financial instruments (typically 6+ decimal places).

Example:
    >>> from datetime import date
    >>> calc = DayCountCalculator("ACT/360")
    >>> year_fraction = calc.calculate_year_fraction(
    ...     date(2024, 1, 1),
    ...     date(2024, 1, 31)
    ... )
    >>> print(year_fraction)
    0.086111...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Dict, Type


class DayCountMethod(ABC):
    """Abstract base class for day count calculation methods."""

    @abstractmethod
    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        """
        Calculate year fraction between two dates.

        Args:
            start: Start date (inclusive).
            end: End date (exclusive per ISDA).

        Returns:
            Year fraction as Decimal with high precision.
        """
        pass


class ACT360(DayCountMethod):
    """
    ACT/360 method: actual/360.

    Calculates day count based on actual calendar days,
    dividing by 360 (ISDA convention).
    """

    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        """
        Calculate actual/360 year fraction.

        Period: Jan 1 to Feb 1 = 31 days (actual)
        Year fraction = 31 / 360
        """
        actual_days = (end - start).days
        return Decimal(actual_days) / Decimal(360)


class ACT365Fixed(DayCountMethod):
    """
    ACT/365.FIXED method: actual/365 fixed.

    Calculates day count based on actual calendar days,
    dividing by 365 (no leap year adjustment).
    """

    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        """Calculate actual/365 fixed year fraction."""
        actual_days = (end - start).days
        return Decimal(actual_days) / Decimal(365)


class ThirtyBy360(DayCountMethod):
    """
    30/360 method: thirty/360 (ISDA convention).

    Calculates using a standardized 30-day month convention,
    dividing by 360. Implements ISDA 30/360 rules for day count.

    Rules:
    1. If D1 is 31, set D1 to 30
    2. If D2 is 31 and D1 is 30, set D2 to 30
    """

    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        """
        Calculate 30/360 year fraction using ISDA convention.

        Args:
            start: Start date
            end: End date

        Returns:
            Year fraction as (standardized_day_count / 360)
        """
        # Extract components from dates
        d1, m1, y1 = start.day, start.month, start.year
        d2, m2, y2 = end.day, end.month, end.year

        # ISDA 30/360 adjustment rules
        # Rule 1: If D1 is 31, set D1 to 30
        if d1 == 31:
            d1 = 30

        # Rule 2: If D2 is 31 and D1 is 30, set D2 to 30
        if d2 == 31 and d1 == 30:
            d2 = 30

        # Calculate standardized day count
        day_count = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return Decimal(day_count) / Decimal(360)


class ThirtyEBy360(DayCountMethod):
    """
    30E/360 method: thirtyE/360 (Eurobond Basis).

    Calculates using standardized 30-day month convention,
    where both D1 and D2 are unconditionally adjusted if they are 31.

    Rules:
    1. If D1 is 31, set D1 to 30
    2. If D2 is 31, set D2 to 30
    """

    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        """Calculate 30E/360 year fraction."""
        d1, m1, y1 = start.day, start.month, start.year
        d2, m2, y2 = end.day, end.month, end.year

        if d1 == 31:
            d1 = 30
        if d2 == 31:
            d2 = 30

        day_count = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return Decimal(day_count) / Decimal(360)


class DayCountCalculator:
    """
    Factory for day count calculations.

    Provides unified interface to select day count method
    using Strategy pattern.
    """

    _methods: Dict[str, Type[DayCountMethod]] = {
        "ACT/360": ACT360,
        "ACT/365.FIXED": ACT365Fixed,
        "30/360": ThirtyBy360,
        "30E/360": ThirtyEBy360,
    }

    def __init__(self, method_name: str):
        """
        Initialize calculator with specified method.

        Args:
            method_name: One of "ACT/360", "ACT/365.FIXED", "30/360", "30E/360".

        Raises:
            ValueError: If method_name is not recognized.
        """
        if method_name not in self._methods:
            raise ValueError(
                f"Unknown day count method: {method_name}. "
                f"Supported: {', '.join(self._methods.keys())}"
            )
        self._method = self._methods[method_name]()

    def calculate_year_fraction(self, start: date, end: date) -> Decimal:
        """
        Calculate year fraction using selected method.

        Args:
            start: Start date.
            end: End date.

        Returns:
            Year fraction as Decimal.
        """
        return self._method.calculate_year_fraction(start, end)

    @classmethod
    def register_method(cls, name: str, method_class: Type[DayCountMethod]) -> None:
        """
        Register a custom day count method.

        Args:
            name: Method name identifier.
            method_class: Class implementing DayCountMethod.
        """
        cls._methods[name] = method_class
