"""Tests for DateScheduler."""

import pytest
from datetime import date
from unittest.mock import Mock

from src.schedulers.date_scheduler import DateScheduler, CalculationPeriod, PaymentSchedule


class TestDateSchedulerCalculationPeriodGeneration:
    """Tests for calculation period generation."""
    
    @pytest.fixture
    def mock_calendar(self):
        """Create a mock BusinessCalendar that returns dates unchanged."""
        calendar = Mock()
        calendar.adjust_date = Mock(side_effect=lambda val_date, *args: val_date)
        calendar.is_business_day = Mock(return_value=True)
        return calendar
    
    def test_generate_calculation_periods_3m_simple(self, mock_calendar):
        """Test generation of 3M calculation periods."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2026, 1, 1)
        termination = date(2026, 7, 1)
        
        periods = scheduler.generate_calculation_periods(
            effective_date=effective,
            termination_date=termination,
            frequency="3M",
            roll_convention="EOM",
            business_day_convention="NONE",
            business_centers="GBLO",
        )
        
        # Expected 2 periods: Jan 1 - Apr 1, Apr 1 - Jul 1
        assert len(periods) == 2
        
        # First period
        assert periods[0].unadjusted_start == date(2026, 1, 1)
        assert periods[0].unadjusted_end == date(2026, 4, 1)
        
        # Second period
        assert periods[1].unadjusted_start == date(2026, 4, 1)
        assert periods[1].unadjusted_end == date(2026, 7, 1)
    
    def test_generate_calculation_periods_6m_simple(self, mock_calendar):
        """Test generation of 6M calculation periods."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2026, 1, 1)
        termination = date(2026, 12, 31)
        
        periods = scheduler.generate_calculation_periods(
            effective_date=effective,
            termination_date=termination,
            frequency="6M",
            roll_convention="EOM",
            business_day_convention="NONE",
            business_centers="GBLO",
        )
        
        # Expected 2 periods: Jan 1 - Jul 1, Jul 1 - Dec 31
        assert len(periods) == 2
        assert periods[0].unadjusted_start == date(2026, 1, 1)
        assert periods[0].unadjusted_end == date(2026, 7, 1)
        assert periods[1].unadjusted_start == date(2026, 7, 1)
        assert periods[1].unadjusted_end == date(2026, 12, 31)
    
    def test_generate_calculation_periods_parameter_validation(self, mock_calendar):
        """Test parameter validation (termination_date >= effective_date)."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2026, 7, 1)
        termination = date(2026, 1, 1)  # Before effective
        
        with pytest.raises(ValueError, match="termination_date.*must be >= effective_date"):
            scheduler.generate_calculation_periods(
                effective_date=effective,
                termination_date=termination,
                frequency="3M",
                roll_convention="EOM",
                business_day_convention="NONE",
                business_centers="GBLO",
            )
    
    def test_generate_calculation_periods_invalid_frequency(self, mock_calendar):
        """Test validation of frequency format."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2026, 1, 1)
        termination = date(2026, 7, 1)
        
        with pytest.raises(ValueError, match="Invalid frequency"):
            scheduler.generate_calculation_periods(
                effective_date=effective,
                termination_date=termination,
                frequency="3W",  # Invalid format
                roll_convention="EOM",
                business_day_convention="NONE",
                business_centers="GBLO",
            )


class TestDateSchedulerRollConvention:
    """Tests for roll convention application."""
    
    @pytest.fixture
    def mock_calendar(self):
        """Create a mock BusinessCalendar that returns dates unchanged."""
        calendar = Mock()
        calendar.adjust_date = Mock(side_effect=lambda val_date, *args: val_date)
        return calendar
    
    def test_roll_convention_eom(self, mock_calendar):
        """Test EOM (end of month) roll convention."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        # Jan 15 -> Jan 31 (EOM)
        rolled = scheduler._apply_roll(date(2026, 1, 15), "EOM")
        assert rolled == date(2026, 1, 31)
        
        # Feb 15 -> Feb 28 (EOM, non-leap year)
        rolled = scheduler._apply_roll(date(2026, 2, 15), "EOM")
        assert rolled == date(2026, 2, 28)
        
        # Feb 15 -> Feb 29 (EOM, leap year)
        rolled = scheduler._apply_roll(date(2024, 2, 15), "EOM")
        assert rolled == date(2024, 2, 29)
    
    def test_roll_convention_numeric_11th(self, mock_calendar):
        """Test numeric roll convention (11th of month)."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        # Any day in Jan -> Jan 11
        rolled = scheduler._apply_roll(date(2026, 1, 15), "11")
        assert rolled == date(2026, 1, 11)
        
        rolled = scheduler._apply_roll(date(2026, 1, 5), "11")
        assert rolled == date(2026, 1, 11)
    
    def test_roll_convention_numeric_31st_overflow(self, mock_calendar):
        """Test numeric roll convention with day-of-month overflow."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        # Feb 31 -> Feb 28 (no 31st in Feb)
        rolled = scheduler._apply_roll(date(2026, 2, 15), "31")
        assert rolled == date(2026, 2, 28)
        
        # Apr 31 -> Apr 30 (no 31st in Apr)
        rolled = scheduler._apply_roll(date(2026, 4, 15), "31")
        assert rolled == date(2026, 4, 30)


class TestDateSchedulerPaymentSchedule:
    """Tests for payment schedule generation and period aggregation."""
    
    @pytest.fixture
    def mock_calendar(self):
        """Create a mock BusinessCalendar that returns dates unchanged."""
        calendar = Mock()
        calendar.adjust_date = Mock(side_effect=lambda val_date, *args: val_date)
        return calendar
    
    def test_generate_payment_schedule_3m_calc_6m_payment(self, mock_calendar):
        """Test grouping 3M calculation periods into 6M payment periods."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2026, 1, 1)
        termination = date(2026, 12, 31)
        
        payment_schedules = scheduler.generate_payment_schedule(
            effective_date=effective,
            termination_date=termination,
            frequency="3M",
            payment_frequency="6M",
            roll_convention="EOM",
            business_day_convention="NONE",
            business_centers="GBLO",
        )
        
        # Expected 2 payment schedules
        # Payment 1: 2 x 3M calc periods (Jan 1 - Apr 1, Apr 1 - Jul 1)
        # Payment 2: 2 x 3M calc periods (Jul 1 - Oct 1, Oct 1 - Dec 31)
        assert len(payment_schedules) == 2
        
        # First payment
        assert payment_schedules[0].unadjusted_payment_date == date(2026, 7, 1)
        assert len(payment_schedules[0].calculation_periods) == 2
        assert payment_schedules[0].calculation_periods[0].unadjusted_start == date(2026, 1, 1)
        assert payment_schedules[0].calculation_periods[1].unadjusted_end == date(2026, 7, 1)
        
        # Second payment
        assert payment_schedules[1].unadjusted_payment_date == date(2026, 12, 31)
        assert len(payment_schedules[1].calculation_periods) == 2
    
    def test_generate_payment_schedule_invalid_frequency_multiple(self, mock_calendar):
        """Test validation: payment_frequency must be multiple of calculation frequency."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2026, 1, 1)
        termination = date(2026, 12, 31)
        
        # 3M calculation, 5M payment (5 is not multiple of 3)
        with pytest.raises(ValueError, match="must be a multiple"):
            scheduler.generate_payment_schedule(
                effective_date=effective,
                termination_date=termination,
                frequency="3M",
                payment_frequency="5M",
                roll_convention="EOM",
                business_day_convention="NONE",
                business_centers="GBLO",
            )


class TestDateSchedulerEdgeCases:
    """Tests for edge cases and special scenarios."""
    
    @pytest.fixture
    def mock_calendar(self):
        """Create a mock BusinessCalendar that returns dates unchanged."""
        calendar = Mock()
        calendar.adjust_date = Mock(side_effect=lambda val_date, *args: val_date)
        return calendar
    
    def test_single_period_equals_effective_to_termination(self, mock_calendar):
        """Test when effective to termination is exactly one period."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2026, 1, 1)
        termination = date(2026, 4, 1)
        
        periods = scheduler.generate_calculation_periods(
            effective_date=effective,
            termination_date=termination,
            frequency="3M",
            roll_convention="EOM",
            business_day_convention="NONE",
            business_centers="GBLO",
        )
        
        assert len(periods) == 1
        assert periods[0].unadjusted_start == effective
        assert periods[0].unadjusted_end == termination
    
    def test_multiple_periods_many_cycles(self, mock_calendar):
        """Test generation over extended period (multiple years)."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        effective = date(2024, 1, 1)
        termination = date(2026, 12, 31)
        
        periods = scheduler.generate_calculation_periods(
            effective_date=effective,
            termination_date=termination,
            frequency="3M",
            roll_convention="EOM",
            business_day_convention="NONE",
            business_centers="GBLO",
        )
        
        # 3 years * 4 quarters = 12 periods
        assert len(periods) == 12
        assert periods[0].unadjusted_start == date(2024, 1, 1)
        assert periods[-1].unadjusted_end == date(2026, 12, 31)
    
    def test_frequency_parsing_edge_cases(self, mock_calendar):
        """Test frequency parsing with various valid formats."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        # Test 1M
        assert scheduler._parse_frequency("1M") == 1
        
        # Test 12M
        assert scheduler._parse_frequency("12M") == 12
        
        # Test 24M
        assert scheduler._parse_frequency("24M") == 24
    
    def test_frequency_parsing_invalid_formats(self, mock_calendar):
        """Test frequency parsing error handling."""
        scheduler = DateScheduler(calendar=mock_calendar)
        
        with pytest.raises(ValueError):
            scheduler._parse_frequency("0M")  # Zero not allowed
        
        with pytest.raises(ValueError):
            scheduler._parse_frequency("-3M")  # Negative not allowed
        
        with pytest.raises(ValueError):
            scheduler._parse_frequency("ABC")  # No unit
