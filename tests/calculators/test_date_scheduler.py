from datetime import date

from fpml.confirmation import (
    BusinessCenter,
    BusinessCenters,
    BusinessCentersReference,
    BusinessDayAdjustments,
    BusinessDayConventionEnum,
)
from src.calculators.date_scheduler import DateScheduler
from src.calculators.reference_resolver import ReferenceResolver
from src.calendars.business_calendar import BusinessCalendar


def test_date_scheduler_adjust_date_direct_centers():
    calendar = BusinessCalendar(config_dir="config")

    # 参照解決なしのダミー
    resolver = ReferenceResolver(None)
    scheduler = DateScheduler(calendar, resolver)

    # BusinessDayAdjustments の作成 (直接 centers を持つ場合)
    adjustments = BusinessDayAdjustments(
        business_day_convention=BusinessDayConventionEnum.FOLLOWING,
        business_centers=BusinessCenters(
            business_center=[BusinessCenter(value="GBLO")]
        ),
    )

    # GBLO 休日 (2026-05-30 は土曜日) -> FOLLOWING により 2026-06-01 (月曜日)
    sat = date(2026, 5, 30)
    adjusted = scheduler.adjust_date(sat, adjustments)
    assert adjusted == date(2026, 6, 1)


def test_date_scheduler_adjust_date_referenced_centers():
    calendar = BusinessCalendar(config_dir="config")

    # 参照解決あり
    centers = BusinessCenters(
        id="primaryBusinessCenters", business_center=[BusinessCenter(value="JPTO")]
    )

    # ルートオブジェクトとしてリストに格納してインデックス化
    resolver = ReferenceResolver([centers])
    scheduler = DateScheduler(calendar, resolver)

    # BusinessDayAdjustments の作成 (参照を持つ場合)
    adjustments = BusinessDayAdjustments(
        business_day_convention=BusinessDayConventionEnum.FOLLOWING,
        business_centers_reference=BusinessCentersReference(
            href="primaryBusinessCenters"
        ),
    )

    # 2026-02-11 (水曜日) は JPTO の祝祭日 -> FOLLOWING により 2026-02-12 (木曜日)
    holiday = date(2026, 2, 11)
    adjusted = scheduler.adjust_date(holiday, adjustments)
    assert adjusted == date(2026, 2, 12)


def test_date_scheduler_adjust_date_none_convention():
    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(None)
    scheduler = DateScheduler(calendar, resolver)

    adjustments = BusinessDayAdjustments(
        business_day_convention=BusinessDayConventionEnum.NONE,
        business_centers=BusinessCenters(
            business_center=[BusinessCenter(value="GBLO")]
        ),
    )

    sat = date(2026, 5, 30)
    adjusted = scheduler.adjust_date(sat, adjustments)
    # NONE の場合は調整されない
    assert adjusted == sat
