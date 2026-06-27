from datetime import date

from fpml.confirmation import (
    CalculationParameters,
    FloatingRateDefinition,
    InterestRateStream,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.ibor_observation_scheduler import IBORObservationScheduler
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.rfr_observation_scheduler import RFRObservationScheduler
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


class FloatingRatePeriodResolver:
    """計算期間に対する浮動金利（Fixing）の解決を担当するクラス。"""

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

    def resolve_rate_def(
        self,
        astart: date,
        aend: date,
        stream: InterestRateStream,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
        ustart: date,
    ) -> FloatingRateDefinition | None:
        """指定された調整前・調整済期間に基づき浮動金利定義を解決します。"""
        calc_params = stream.calculation_period_amount.calculation
        floating_rate_calc = calc_params.floating_rate_calculation

        if floating_rate_calc is None:
            return None

        # 基準日の決定 (unadjusted_startが指定されていればそれを使用、なければadjusted_startを使用)
        ref_date = ustart if ustart is not None else astart

        # spread と multiplier
        spread = step_schedule_resolver_factory.spread_resolver.resolve(ref_date)
        multiplier = step_schedule_resolver_factory.multiplier_resolver.resolve(
            ref_date
        )

        # RFR (Modular Calculated Rate) の判定
        calculation_parameters = floating_rate_calc.calculation_parameters
        if calculation_parameters is not None:
            rate_observations = self._rfr_scheduler.generate_rate_observations(
                astart, aend, stream, calculation_parameters
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
            astart, aend, stream
        )

        return FloatingRateDefinition(
            rate_observation=rate_observations,
            spread=spread,
            floating_rate_multiplier=multiplier,
        )
