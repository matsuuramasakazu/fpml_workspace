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


def test_resolve_relative_date_offset_business():
    # ケース1: 営業日ベースのマイナスオフセット（JPTO + USNY）
    from fpml.confirmation import (
        BusinessCenter,
        BusinessCenters,
        BusinessDayConventionEnum,
        DateReference,
        DayTypeEnum,
        RelativeDateOffset,
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(None)
    adjuster = DateAdjuster(calendar, resolver)

    offset = RelativeDateOffset(
        period_multiplier=-2,
        period=None,  # デフォルトで日単位扱いに
        day_type=DayTypeEnum.BUSINESS,
        business_day_convention=BusinessDayConventionEnum.NONE,
        date_relative_to=DateReference(href="dummy"),
        business_centers=BusinessCenters(
            business_center=[
                BusinessCenter(value="JPTO"),
                BusinessCenter(value="USNY"),
            ]
        ),
    )

    base = date(2006, 1, 11)
    adjusted = adjuster.resolve_relative_date_offset(base, offset)
    assert adjusted == date(2006, 1, 9)


def test_resolve_relative_date_offset_calendar_following():
    # ケース2: カレンダー日ベースのオフセット（建国記念の日 JPTO 祝日 -> FOLLOWING で翌日）
    from fpml.confirmation import (
        BusinessCenter,
        BusinessCenters,
        BusinessDayConventionEnum,
        DateReference,
        DayTypeEnum,
        RelativeDateOffset,
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(None)
    adjuster = DateAdjuster(calendar, resolver)

    offset = RelativeDateOffset(
        period_multiplier=1,
        period=None,
        day_type=DayTypeEnum.CALENDAR,
        business_day_convention=BusinessDayConventionEnum.FOLLOWING,
        date_relative_to=DateReference(href="dummy"),
        business_centers=BusinessCenters(
            business_center=[BusinessCenter(value="JPTO")]
        ),
    )

    base = date(2026, 2, 10)
    adjusted = adjuster.resolve_relative_date_offset(base, offset)
    assert adjusted == date(2026, 2, 12)


def test_resolve_relative_date_offset_zero():
    # ケース3: オフセット0日（調整なし）
    from fpml.confirmation import (
        BusinessDayConventionEnum,
        DateReference,
        RelativeDateOffset,
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(None)
    adjuster = DateAdjuster(calendar, resolver)

    offset = RelativeDateOffset(
        period_multiplier=0,
        period=None,
        day_type=None,
        business_day_convention=BusinessDayConventionEnum.NONE,
        date_relative_to=DateReference(href="dummy"),
    )

    base = date(2026, 5, 30)
    adjusted = adjuster.resolve_relative_date_offset(base, offset)
    assert adjusted == base
