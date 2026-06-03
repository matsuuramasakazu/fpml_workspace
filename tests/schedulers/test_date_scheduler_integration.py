import pytest
from datetime import date
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_scheduler import DateScheduler

@pytest.fixture
def calendar():
    return BusinessCalendar(config_dir="config")

@pytest.fixture
def scheduler(calendar):
    return DateScheduler(calendar)

def test_generate_calculation_periods_integration(scheduler):
    """
    Test calculation period generation with real BusinessCalendar
    across multiple business centers.
    """
    # 2024-02-03 (Saturday) -> +3M -> 2024-05-03
    # 2024-05-03 is a JP holiday, 2024-05-04/05 are weekends/holidays.
    # So FOLLOWING should roll to 2024-05-06.
    
    effective_date = date(2024, 2, 3)
    termination_date = date(2024, 8, 3)
    
    periods = scheduler.generate_calculation_periods(
        effective_date=effective_date,
        termination_date=termination_date,
        frequency="3M",
        roll_convention="3",
        business_day_convention="FOLLOWING",
        business_centers=["JPTO", "USNY"]
    )
    
    assert len(periods) == 2
    
    # Period 1: Feb 3 to May 3
    # Unadjusted start: 2024-02-03. Adjusted start: Feb 3 is Sat -> Feb 5 (Mon).
    assert periods[0].unadjusted_start == date(2024, 2, 3)
    assert periods[0].adjusted_start == date(2024, 2, 5)
    
    # Unadjusted end: 2024-05-03. Adjusted end: May 3 is JP holiday (Friday), May 4-5 weekend, May 6 (Mon) business day.
    assert periods[0].unadjusted_end == date(2024, 5, 3)
    assert periods[0].adjusted_end == date(2024, 5, 6)
    
    # Period 2: May 3 to Aug 3
    assert periods[1].unadjusted_start == date(2024, 5, 3)
    assert periods[1].adjusted_start == date(2024, 5, 6)
    
    # Unadjusted end: 2024-08-03. Adjusted end: Aug 3 is Sat -> Aug 5 (Mon).
    assert periods[1].unadjusted_end == date(2024, 8, 3)
    assert periods[1].adjusted_end == date(2024, 8, 5)

def test_generate_payment_schedule_integration(scheduler):
    """
    Test payment schedule generation combining multiple calculation periods
    and evaluating roll/business day conventions using real Calendar.
    """
    # 6M payment frequency, 3M calc frequency
    # 2024-01-01 to 2025-01-01
    effective_date = date(2024, 1, 1)
    termination_date = date(2025, 1, 1)
    
    schedules = scheduler.generate_payment_schedule(
        effective_date=effective_date,
        termination_date=termination_date,
        frequency="3M",
        payment_frequency="6M",
        roll_convention="1",
        business_day_convention="MODFOLLOWING",
        business_centers=["JPTO", "GBLO"]
    )
    
    assert len(schedules) == 2
    
    # Schedule 1: Jan 1 to Jul 1
    # 2024-01-01 is a holiday (JP & GB). MODFOLLOWING for Jan 1:
    # 2024-01-01 -> Jan 2 (Tuesday).
    # 2024-07-01 is a normal business day.
    assert len(schedules[0].calculation_periods) == 2
    assert schedules[0].unadjusted_payment_date == date(2024, 7, 1)
    assert schedules[0].adjusted_payment_date == date(2024, 7, 1)
    
    # Schedule 2: Jul 1 to Jan 1
    # 2025-01-01 is a holiday. MODFOLLOWING for Jan 1 rolls to Jan 2 (Thu).
    assert len(schedules[1].calculation_periods) == 2
    assert schedules[1].unadjusted_payment_date == date(2025, 1, 1)
    assert schedules[1].adjusted_payment_date == date(2025, 1, 2)

def test_generate_calculation_periods_12m(scheduler):
    """
    Test 12M frequency calculation period generation.
    """
    effective_date = date(2024, 2, 29) # Leap year
    termination_date = date(2026, 2, 28)
    
    periods = scheduler.generate_calculation_periods(
        effective_date=effective_date,
        termination_date=termination_date,
        frequency="12M",
        roll_convention="EOM",
        business_day_convention="PRECEDING",
        business_centers="USNY"
    )
    
    assert len(periods) == 2
    
    # Period 1: Feb 2024 to Feb 2025
    # Unadjusted start: 2024-02-29. EOM roll on start should be 2024-02-29.
    # 2024-02-29 is Thursday. Adjusted start = 2024-02-29.
    assert periods[0].unadjusted_start == date(2024, 2, 29)
    assert periods[0].adjusted_start == date(2024, 2, 29)
    
    # Unadjusted end: 2025-02-28. EOM roll -> 2025-02-28 (Friday, business day).
    assert periods[0].unadjusted_end == date(2025, 2, 28)
    assert periods[0].adjusted_end == date(2025, 2, 28)
    
    # Period 2: Feb 2025 to Feb 2026
    # Unadjusted end: 2026-02-28 (Saturday). PRECEDING roll -> 2026-02-27 (Friday).
    assert periods[1].unadjusted_end == date(2026, 2, 28)
    assert periods[1].adjusted_end == date(2026, 2, 27)
