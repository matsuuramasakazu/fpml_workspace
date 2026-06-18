from datetime import date

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    FloatingRateDefinition,
    InterestRateStream,
    RateObservation,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.reference_resolver import ReferenceResolver


class FixingScheduler:
    """浮動金利レグに対する Fixing（金利決定）スケジュールの決定を担当するクラス。"""

    def __init__(self, calendar: BusinessCalendar, resolver: ReferenceResolver):
        """
        Args:
            calendar: 祝祭日カレンダーやビジネス営業日算出を行うBusinessCalendarインスタンス
            resolver: 参照解決を行うReferenceResolverインスタンス
        """
        self._calendar = calendar
        self._resolver = resolver
        self._adjuster = DateAdjuster(calendar, resolver)

    def calculate_fixing(
        self, adjusted_start: date, adjusted_end: date, stream: InterestRateStream
    ) -> FloatingRateDefinition | None:
        """計算期間の調整日を基準に、Fixing日を算出して FloatingRateDefinition を生成します。

        Args:
            adjusted_start: 計算期間の調整済開始日
            adjusted_end: 計算期間の調整済終了日
            stream: FpML の金利ストリーム情報

        Returns:
            構築された FloatingRateDefinition、または浮動金利情報がない場合は None
        """
        calc_params = stream.calculation_period_amount.calculation
        floating_rate_calc = calc_params.floating_rate_calculation

        if floating_rate_calc is None or stream.reset_dates is None:
            return None

        reset_dates = stream.reset_dates

        # resetRelativeToがStartDateなら計算期間開始日を基準にする
        reset_date_val = adjusted_start
        if reset_dates.reset_relative_to.value != "CalculationPeriodStartDate":
            reset_date_val = adjusted_end  # フォールバック

        # Fixing日の算出
        fixing_dates = reset_dates.fixing_dates
        adjusted_fixing = self._adjuster.resolve_relative_date_offset(
            reset_date_val, fixing_dates
        )

        # spread と multiplier
        spread = None
        if floating_rate_calc.spread_schedule:
            if isinstance(floating_rate_calc.spread_schedule, list):
                if len(floating_rate_calc.spread_schedule) > 0:
                    spread = floating_rate_calc.spread_schedule[0].initial_value
            else:
                spread = floating_rate_calc.spread_schedule.initial_value

        multiplier = None
        if floating_rate_calc.floating_rate_multiplier_schedule:
            if isinstance(floating_rate_calc.floating_rate_multiplier_schedule, list):
                if len(floating_rate_calc.floating_rate_multiplier_schedule) > 0:
                    multiplier = floating_rate_calc.floating_rate_multiplier_schedule[
                        0
                    ].initial_value
            else:
                multiplier = (
                    floating_rate_calc.floating_rate_multiplier_schedule.initial_value
                )

        obs = RateObservation(
            reset_date=XmlDate(
                reset_date_val.year, reset_date_val.month, reset_date_val.day
            ),
            adjusted_fixing_date=XmlDate(
                adjusted_fixing.year, adjusted_fixing.month, adjusted_fixing.day
            ),
            observation_weight=1,
        )

        return FloatingRateDefinition(
            rate_observation=[obs],
            spread=spread,
            floating_rate_multiplier=multiplier,
        )
