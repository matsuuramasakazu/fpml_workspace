from datetime import date, timedelta
from decimal import Decimal

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    CalculationParameters,
    FloatingRateDefinition,
    InterestRateStream,
    RateObservation,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.ibor_observation_scheduler import IBORObservationScheduler
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.rfr_observation_scheduler import RFRObservationScheduler
from src.schedulers.step_schedule_resolver import StepScheduleResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


class FixingScheduler:
    """浮動金利レグに対する Fixing（金利決定）スケジュールの決定を担当するクラス。"""

    def __init__(self, calendar: BusinessCalendar, ref_resolver: ReferenceResolver):
        """
        Args:
            calendar: 祝祭日カレンダーやビジネス営業日算出を行うBusinessCalendarインスタンス
            ref_resolver: 参照解決を行うReferenceResolverインスタンス
        """
        self._calendar = calendar
        self._ref_resolver = ref_resolver
        self._adjuster = DateAdjuster(calendar, ref_resolver)
        self._rfr_scheduler = RFRObservationScheduler(calendar, ref_resolver)
        self._ibor_scheduler = IBORObservationScheduler(self._adjuster)

    def calculate_fixing(
        self,
        adjusted_start: date,
        adjusted_end: date,
        stream: InterestRateStream,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
        unadjusted_start: date | None = None,
    ) -> FloatingRateDefinition | None:
        """計算期間の調整日を基準に、Fixing日を算出して FloatingRateDefinition を生成します。

        Args:
            adjusted_start: 計算期間の調整済開始日
            adjusted_end: 計算期間の調整済終了日
            stream: FpML の金利ストリーム情報
            step_schedule_resolver_factory: 各種ステップスケジュールリゾルバーを保持するFactory
            unadjusted_start: 計算期間の調整前開始日

        Returns:
            構築された FloatingRateDefinition、または浮動金利情報がない場合は None
        """
        calc_params = stream.calculation_period_amount.calculation
        floating_rate_calc = calc_params.floating_rate_calculation

        if floating_rate_calc is None:
            return None

        # 基準日の決定 (unadjusted_startが指定されていればそれを使用、なければadjusted_startを使用)
        ref_date = unadjusted_start if unadjusted_start is not None else adjusted_start

        # spread と multiplier
        spread = step_schedule_resolver_factory.spread_resolver.resolve(ref_date)
        multiplier = step_schedule_resolver_factory.multiplier_resolver.resolve(
            ref_date
        )

        # RFR (Modular Calculated Rate) の判定
        calculation_parameters = floating_rate_calc.calculation_parameters
        if calculation_parameters is not None:
            rate_observations = self._rfr_scheduler.generate_rate_observations(
                adjusted_start, adjusted_end, stream, calculation_parameters
            )
            return FloatingRateDefinition(
                rate_observation=rate_observations,
                spread=spread,
                floating_rate_multiplier=multiplier,
            )

        # 従来の IBOR レグの処理
        if stream.reset_dates is None:
            return None

        rate_observations = self._ibor_scheduler.generate_rate_observations(
            adjusted_start, adjusted_end, stream
        )

        return FloatingRateDefinition(
            rate_observation=rate_observations,
            spread=spread,
            floating_rate_multiplier=multiplier,
        )
