from datetime import date
from typing import List

from fpml.confirmation import (
    BusinessCenters,
    BusinessDayAdjustments,
    RelativeDateOffset,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.reference_resolver import ReferenceResolver


class DateAdjuster:
    """FpML の BusinessDayAdjustments を解釈し、BusinessCalendar を用いて日付を調整するクラス。"""

    def __init__(self, calendar: BusinessCalendar, ref_resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            ref_resolver: FpMLドキュメント内のhref参照を解決するReferenceResolverインスタンス
        """
        self._calendar = calendar
        self._ref_resolver = ref_resolver

    def _resolve_business_centers(
        self, adjustments: BusinessDayAdjustments
    ) -> List[str]:
        """BusinessDayAdjustments から、ビジネスセンターコードのリストを返します。

        直接の business_centers がある場合はそれを使用し、
        business_centers_reference がある場合は ReferenceResolver を用いて解決します。
        """
        centers: BusinessCenters | None = None

        if adjustments.business_centers is not None:
            centers = adjustments.business_centers
        elif adjustments.business_centers_reference is not None:
            centers = self._ref_resolver.resolve(adjustments.business_centers_reference)

        if centers is None:
            # センターが未指定の場合はそのまま返す（調整なし）
            return []

        return [bc.value for bc in centers.business_center if bc.value]

    def adjust_date(self, val_date: date, adjustments: BusinessDayAdjustments) -> date:
        """FpML の BusinessDayAdjustments に従って日付を調整します。

        Args:
            val_date: 調整対象の日付
            adjustments: FpML の BusinessDayAdjustments オブジェクト

        Returns:
            調整後の日付
        """
        convention = adjustments.business_day_convention.value
        centers = self._resolve_business_centers(adjustments)

        if not centers:
            # ビジネスセンターが未指定の場合は NONE 扱い
            return val_date

        return self._calendar.adjust_date(val_date, convention, centers)

    def resolve_relative_date_offset(
        self, base_date: date, offset: RelativeDateOffset
    ) -> date:
        """RelativeDateOffset パラメータに基づいて、base_date からの相対調整日を算出します。

        Args:
            base_date: 基準日
            offset: FpML の RelativeDateOffset オブジェクト

        Returns:
            相対調整日
        """
        offset_days = offset.period_multiplier

        # ビジネスセンターの取得
        centers = []
        business_centers = getattr(offset, "business_centers", None)
        business_centers_reference = getattr(offset, "business_centers_reference", None)

        if business_centers is not None:
            centers = [bc.value for bc in business_centers.business_center if bc.value]
        elif business_centers_reference is not None:
            centers_obj = self._ref_resolver.resolve(business_centers_reference)
            centers = [bc.value for bc in centers_obj.business_center if bc.value]

        day_type = getattr(offset, "day_type", None)
        day_type_val = day_type.value if day_type is not None else "Business"

        if day_type_val == "Business":
            return self._calendar.add_business_days(base_date, offset_days, centers)
        else:
            # カレンダー日での加算
            from datetime import timedelta

            unadjusted = base_date + timedelta(days=offset_days)
            convention = getattr(offset, "business_day_convention", None)
            if convention is not None:
                conv = convention.value
                if conv != "NONE":
                    return self._calendar.adjust_date(unadjusted, conv, centers)
            return unadjusted
