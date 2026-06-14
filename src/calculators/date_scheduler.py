from datetime import date
from typing import List

from fpml.confirmation import BusinessCenters, BusinessDayAdjustments
from src.calculators.reference_resolver import ReferenceResolver
from src.calendars.business_calendar import BusinessCalendar


class DateScheduler:
    """FpML の BusinessDayAdjustments を解釈し、BusinessCalendar を用いて日付を調整するスケジューラー。"""

    def __init__(self, calendar: BusinessCalendar, resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            resolver: FpMLドキュメント内のhref参照を解決するReferenceResolverインスタンス
        """
        self._calendar = calendar
        self._resolver = resolver

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
            centers = self._resolver.resolve(adjustments.business_centers_reference)

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
