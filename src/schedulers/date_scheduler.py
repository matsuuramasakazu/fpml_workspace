"""
DateScheduler: Schedule expansion engine for FpML swap calculations.

Generates:
- CalculationPeriod: Individual interest calculation periods
- PaymentSchedule: Grouped payment periods from multiple calculation periods

Designed to be independent of BusinessCalendar implementation details
(uses dependency injection for testability).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Protocol


class BusinessCalendar(Protocol):
    """Protocol for business calendar (enables mocking in tests)."""
    
    def is_business_day(self, val_date: date, business_centers: str | List[str]) -> bool:
        """Check if date is a business day."""
        ...
    
    def adjust_date(self, val_date: date, convention: str, business_centers: str | List[str]) -> date:
        """Adjust date according to business day convention."""
        ...


@dataclass
class CalculationPeriod:
    """
    Represents a single interest calculation period.
    
    Attributes:
        unadjusted_start: Unadjusted period start date.
        unadjusted_end: Unadjusted period end date.
        adjusted_start: Business-day-adjusted start date.
        adjusted_end: Business-day-adjusted end date.
    """
    unadjusted_start: date
    unadjusted_end: date
    adjusted_start: date
    adjusted_end: date


@dataclass
class PaymentSchedule:
    """
    Represents a payment period containing one or more calculation periods.
    
    Attributes:
        unadjusted_payment_date: Unadjusted payment date.
        adjusted_payment_date: Business-day-adjusted payment date.
        calculation_periods: List of calculation periods grouped into this payment.
    """
    unadjusted_payment_date: date
    adjusted_payment_date: date
    calculation_periods: List[CalculationPeriod]


class DateScheduler:
    """
    Schedule expansion engine for generating calculation and payment periods.
    
    Responsibilities:
    - Generate calculation periods from effective date to termination date
    - Apply roll conventions (e.g., 11th of month)
    - Group calculation periods into payment schedules
    - Validate parameters (e.g., termination_date >= effective_date)
    """
    
    def __init__(self, calendar: BusinessCalendar):
        """
        Initialize DateScheduler.
        
        Args:
            calendar: Business calendar for date adjustments.
        """
        self.calendar = calendar
    
    def generate_calculation_periods(
        self,
        effective_date: date,
        termination_date: date,
        frequency: str,  # "3M", "6M", etc.
        roll_convention: str,  # "11", "EOM", etc.
        business_day_convention: str,  # "FOLLOWING", "MODFOLLOWING", etc.
        business_centers: str | List[str],
    ) -> List[CalculationPeriod]:
        """
        Generate calculation periods.
        
        Args:
            effective_date: Swap effective date.
            termination_date: Swap termination date.
            frequency: Payment frequency (e.g., "3M", "6M").
            roll_convention: Roll convention (e.g., "11", "EOM").
            business_day_convention: Date adjustment convention.
            business_centers: Business center(s) for date adjustments.
            
        Returns:
            List of CalculationPeriod objects.
            
        Raises:
            ValueError: If parameters are inconsistent.
        """
        # Parameter validation
        if termination_date < effective_date:
            raise ValueError(
                f"termination_date ({termination_date}) must be >= effective_date ({effective_date})"
            )
        
        # Parse frequency
        frequency_months = self._parse_frequency(frequency)
        
        periods = []
        current_start = effective_date
        
        while current_start < termination_date:
            # Calculate unadjusted end date
            current_end = self._add_months(current_start, frequency_months)
            
            # Ensure we don't exceed termination date
            if current_end > termination_date:
                current_end = termination_date
            
            # Apply roll convention to start and end dates
            adjusted_start = self._apply_roll_convention(
                current_start, roll_convention, business_day_convention, business_centers
            )
            adjusted_end = self._apply_roll_convention(
                current_end, roll_convention, business_day_convention, business_centers
            )
            
            period = CalculationPeriod(
                unadjusted_start=current_start,
                unadjusted_end=current_end,
                adjusted_start=adjusted_start,
                adjusted_end=adjusted_end,
            )
            periods.append(period)
            
            # Move to next period
            current_start = current_end
        
        return periods
    
    def _parse_frequency(self, frequency: str) -> int:
        """
        Parse frequency string to months.
        
        Args:
            frequency: Frequency string (e.g., "3M", "6M").
            
        Returns:
            Number of months.
            
        Raises:
            ValueError: If frequency format is invalid.
        """
        if not frequency.endswith("M"):
            raise ValueError(f"Invalid frequency format: {frequency}")
        
        try:
            months = int(frequency[:-1])
            if months <= 0:
                raise ValueError(f"Frequency must be positive: {frequency}")
            return months
        except ValueError as e:
            raise ValueError(f"Invalid frequency: {frequency}") from e
    
    def _add_months(self, base_date: date, months: int) -> date:
        """
        Add months to a date (day-of-month preserving).
        
        Args:
            base_date: Base date.
            months: Number of months to add.
            
        Returns:
            Date with months added.
        """
        year = base_date.year
        month = base_date.month + months
        day = base_date.day
        
        # Handle month overflow
        while month > 12:
            month -= 12
            year += 1
        
        # Handle day overflow (e.g., Jan 31 + 1 month -> Feb 28/29)
        while True:
            try:
                return date(year, month, day)
            except ValueError:
                day -= 1
    
    def _apply_roll_convention(
        self,
        base_date: date,
        roll_convention: str,
        business_day_convention: str,
        business_centers: str | List[str],
    ) -> date:
        """
        Apply roll convention and business day convention to a date.
        
        Args:
            base_date: Base date.
            roll_convention: Roll convention (e.g., "11", "EOM").
            business_day_convention: Business day convention.
            business_centers: Business center(s).
            
        Returns:
            Adjusted date.
        """
        # Roll convention application
        rolled_date = self._apply_roll(base_date, roll_convention)
        
        # Business day adjustment
        adjusted_date = self.calendar.adjust_date(
            rolled_date, business_day_convention, business_centers
        )
        
        return adjusted_date
    
    def _apply_roll(self, base_date: date, roll_convention: str) -> date:
        """
        Apply roll convention to a date.
        
        Args:
            base_date: Base date.
            roll_convention: Roll convention (e.g., "11", "EOM").
            
        Returns:
            Rolled date.
        """
        if roll_convention == "EOM":
            # End of month
            if base_date.month == 12:
                next_month = date(base_date.year + 1, 1, 1)
            else:
                next_month = date(base_date.year, base_date.month + 1, 1)
            return next_month - timedelta(days=1)
        
        elif roll_convention.isdigit():
            # Numeric roll (e.g., "11" = 11th of month)
            day_of_month = int(roll_convention)
            return self._set_day_of_month(base_date, day_of_month)
        
        else:
            raise ValueError(f"Unknown roll convention: {roll_convention}")
    
    def _set_day_of_month(self, base_date: date, day: int) -> date:
        """
        Set day of month, handling month boundaries.
        
        Args:
            base_date: Base date.
            day: Desired day of month.
            
        Returns:
            Date with updated day of month.
        """
        year = base_date.year
        month = base_date.month
        
        try:
            return date(year, month, day)
        except ValueError:
            # Day overflow (e.g., Feb 31 -> Feb 28/29)
            if month == 2:
                return date(year, month, 28) if year % 4 != 0 else date(year, month, 29)
            elif month in [4, 6, 9, 11]:
                return date(year, month, 30)
            else:
                return date(year, month, 31)
    
    def generate_payment_schedule(
        self,
        effective_date: date,
        termination_date: date,
        frequency: str,
        payment_frequency: str,
        roll_convention: str,
        business_day_convention: str,
        business_centers: str | List[str],
    ) -> List[PaymentSchedule]:
        """
        Generate payment schedule (groups calculation periods).
        
        Args:
            effective_date: Swap effective date.
            termination_date: Swap termination date.
            frequency: Calculation period frequency (e.g., "3M").
            payment_frequency: Payment period frequency (e.g., "6M").
            roll_convention: Roll convention.
            business_day_convention: Business day convention.
            business_centers: Business center(s).
            
        Returns:
            List of PaymentSchedule objects.
        """
        # Generate calculation periods
        calc_periods = self.generate_calculation_periods(
            effective_date, termination_date, frequency, roll_convention,
            business_day_convention, business_centers
        )
        
        # Parse payment frequency
        payment_months = self._parse_frequency(payment_frequency)
        calc_months = self._parse_frequency(frequency)
        
        # Group calculation periods into payment periods
        periods_per_payment = payment_months // calc_months
        if payment_months % calc_months != 0:
            raise ValueError(
                f"Payment frequency ({payment_frequency}) must be a multiple of "
                f"calculation frequency ({frequency})"
            )
        
        payment_schedules = []
        for i in range(0, len(calc_periods), periods_per_payment):
            grouped_periods = calc_periods[i:i + periods_per_payment]
            
            # Payment date is the end of the last calculation period
            last_period = grouped_periods[-1]
            unadjusted_payment = last_period.unadjusted_end
            adjusted_payment = last_period.adjusted_end
            
            payment_schedule = PaymentSchedule(
                unadjusted_payment_date=unadjusted_payment,
                adjusted_payment_date=adjusted_payment,
                calculation_periods=grouped_periods,
            )
            payment_schedules.append(payment_schedule)
        
        return payment_schedules
