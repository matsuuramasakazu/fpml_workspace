from datetime import date

from fpml.confirmation import (
    BusinessCenter,
    BusinessCenters,
    BusinessCentersReference,
    BusinessDayAdjustments,
    BusinessDayConventionEnum,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.reference_resolver import ReferenceResolver


def test_date_adjuster_direct_centers():
    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(None)
    adjuster = DateAdjuster(calendar, resolver)

    adjustments = BusinessDayAdjustments(
        business_day_convention=BusinessDayConventionEnum.FOLLOWING,
        business_centers=BusinessCenters(
            business_center=[BusinessCenter(value="GBLO")]
        ),
    )

    sat = date(2026, 5, 30)
    adjusted = adjuster.adjust_date(sat, adjustments)
    assert adjusted == date(2026, 6, 1)


def test_date_adjuster_referenced_centers():
    calendar = BusinessCalendar(config_dir="config")
    centers = BusinessCenters(
        id="primaryBusinessCenters", business_center=[BusinessCenter(value="JPTO")]
    )
    resolver = ReferenceResolver([centers])
    adjuster = DateAdjuster(calendar, resolver)

    adjustments = BusinessDayAdjustments(
        business_day_convention=BusinessDayConventionEnum.FOLLOWING,
        business_centers_reference=BusinessCentersReference(
            href="primaryBusinessCenters"
        ),
    )

    holiday = date(2026, 2, 11)
    adjusted = adjuster.adjust_date(holiday, adjustments)
    assert adjusted == date(2026, 2, 12)


def test_date_adjuster_none_convention():
    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(None)
    adjuster = DateAdjuster(calendar, resolver)

    adjustments = BusinessDayAdjustments(
        business_day_convention=BusinessDayConventionEnum.NONE,
        business_centers=BusinessCenters(
            business_center=[BusinessCenter(value="GBLO")]
        ),
    )

    sat = date(2026, 5, 30)
    adjusted = adjuster.adjust_date(sat, adjustments)
    assert adjusted == sat
