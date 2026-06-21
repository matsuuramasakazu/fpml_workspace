from datetime import date, timedelta
from decimal import Decimal

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    FloatingRateDefinition,
    InterestRateStream,
    RateObservation,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.reference_resolver import ReferenceResolver
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
            # A. ビジネスセンターの特定
            centers = []
            if calculation_parameters.applicable_business_days is not None:
                abd = calculation_parameters.applicable_business_days
                if abd.business_centers is not None:
                    centers = [
                        bc.value
                        for bc in abd.business_centers.business_center
                        if bc.value
                    ]
                elif abd.business_centers_reference is not None:
                    centers_obj = self._ref_resolver.resolve(
                        abd.business_centers_reference
                    )
                    centers = [
                        bc.value for bc in centers_obj.business_center if bc.value
                    ]

            if not centers:
                # フォールバック: calculationPeriodDatesAdjustments
                calc_dates = stream.calculation_period_dates
                if calc_dates.calculation_period_dates_adjustments is not None:
                    adj = calc_dates.calculation_period_dates_adjustments
                    if adj.business_centers is not None:
                        centers = [
                            bc.value
                            for bc in adj.business_centers.business_center
                            if bc.value
                        ]
                    elif adj.business_centers_reference is not None:
                        centers_obj = self._ref_resolver.resolve(
                            adj.business_centers_reference
                        )
                        centers = [
                            bc.value for bc in centers_obj.business_center if bc.value
                        ]

            # B. 営業日リストの抽出 (adjusted_start から adjusted_end - 1日 まで)
            business_days = []
            curr = adjusted_start
            while curr < adjusted_end:
                if self._calendar.is_business_day(curr, centers):
                    business_days.append(curr)
                curr += timedelta(days=1)

            # C. パラメータの特定
            lookback = calculation_parameters.lookback
            shift = calculation_parameters.observation_shift
            lockout = calculation_parameters.lockout

            is_lookback = lookback is not None
            is_shift = shift is not None
            is_lockout = lockout is not None

            lookback_offset = (
                lookback.offset_days
                if (is_lookback and lookback.offset_days is not None)
                else 5
            )
            shift_offset = (
                shift.offset_days if (is_shift and shift.offset_days is not None) else 5
            )
            lockout_offset = (
                lockout.offset_days
                if (is_lockout and lockout.offset_days is not None)
                else 5
            )

            # D. Fixing日とウェイトの算出
            rate_observations = []
            m = len(business_days)
            for i in range(m):
                d_i = business_days[i]

                # adjusted_fixing_date の算出
                if is_lookback:
                    adjusted_fixing = self._calendar.add_business_days(
                        d_i, -lookback_offset, centers
                    )
                elif is_shift:
                    adjusted_fixing = self._calendar.add_business_days(
                        d_i, -shift_offset, centers
                    )
                elif is_lockout:
                    d_lock = self._calendar.add_business_days(
                        adjusted_end, -lockout_offset, centers
                    )
                    adjusted_fixing = d_i if d_i < d_lock else d_lock
                else:
                    # Plain
                    adjusted_fixing = d_i

                # observation_weight の算出
                if is_shift:
                    # 観測日基準の翌観測日
                    curr_obs = self._calendar.add_business_days(
                        d_i, -shift_offset, centers
                    )
                    if i + 1 < m:
                        next_obs = self._calendar.add_business_days(
                            business_days[i + 1], -shift_offset, centers
                        )
                    else:
                        next_obs = self._calendar.add_business_days(
                            adjusted_end, -shift_offset, centers
                        )
                    weight = (next_obs - curr_obs).days
                else:
                    # 適用日基準の翌適用日
                    next_applied = business_days[i + 1] if i + 1 < m else adjusted_end
                    weight = (next_applied - d_i).days

                obs = RateObservation(
                    reset_date=XmlDate(d_i.year, d_i.month, d_i.day),
                    adjusted_fixing_date=XmlDate(
                        adjusted_fixing.year,
                        adjusted_fixing.month,
                        adjusted_fixing.day,
                    ),
                    observation_weight=weight,
                )
                rate_observations.append(obs)

            return FloatingRateDefinition(
                rate_observation=rate_observations,
                spread=spread,
                floating_rate_multiplier=multiplier,
            )

        # 従来の IBOR レグの処理
        if stream.reset_dates is None:
            return None

        reset_dates = stream.reset_dates

        # resetRelativeToがStartDateまたはNoneなら計算期間開始日を基準にする
        reset_date_val = adjusted_start
        reset_rel = reset_dates.reset_relative_to
        if reset_rel is not None and reset_rel.value == "CalculationPeriodEndDate":
            reset_date_val = adjusted_end

        # Fixing日の算出
        fixing_dates = reset_dates.fixing_dates
        adjusted_fixing = self._adjuster.resolve_relative_date_offset(
            reset_date_val, fixing_dates
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
