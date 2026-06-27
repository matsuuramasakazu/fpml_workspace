from datetime import date, timedelta

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    CalculationParameters,
    InterestRateStream,
    RateObservation,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.reference_resolver import ReferenceResolver


class RFRObservationScheduler:
    """RFR (Modular Calculated Rate) に対する rate_observation リストの生成を担当するクラス。"""

    def __init__(self, calendar: BusinessCalendar, ref_resolver: ReferenceResolver):
        self._calendar = calendar
        self._ref_resolver = ref_resolver

    def generate_rate_observations(
        self,
        adjusted_start: date,
        adjusted_end: date,
        stream: InterestRateStream,
        calculation_parameters: CalculationParameters,
    ) -> list[RateObservation]:
        """RFR (Modular Calculated Rate) に対する rate_observation リストを生成します。"""
        centers = self._resolve_business_centers(stream, calculation_parameters)
        business_days = self._get_business_days(adjusted_start, adjusted_end, centers)
        return self._create_rate_observations(
            business_days, adjusted_end, calculation_parameters, centers
        )

    def _resolve_business_centers(
        self,
        stream: InterestRateStream,
        calculation_parameters: CalculationParameters,
    ) -> list[str]:
        """適用対象のビジネスセンターコードリストを解決します。"""
        centers = []
        if calculation_parameters.applicable_business_days is not None:
            abd = calculation_parameters.applicable_business_days
            if abd.business_centers is not None:
                centers = [
                    bc.value for bc in abd.business_centers.business_center if bc.value
                ]
            elif abd.business_centers_reference is not None:
                centers_obj = self._ref_resolver.resolve(abd.business_centers_reference)
                centers = [bc.value for bc in centers_obj.business_center if bc.value]

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
        return centers

    def _get_business_days(
        self,
        start: date,
        end: date,
        centers: list[str],
    ) -> list[date]:
        """指定された期間内の営業日リストを抽出します。"""
        business_days = []
        curr = start
        while curr < end:
            if self._calendar.is_business_day(curr, centers):
                business_days.append(curr)
            curr += timedelta(days=1)
        return business_days

    def _create_rate_observations(
        self,
        business_days: list[date],
        adjusted_end: date,
        calculation_parameters: CalculationParameters,
        centers: list[str],
    ) -> list[RateObservation]:
        """営業日リストに基づき、Fixing日とウェイトを算出して RateObservation リストを生成します。"""
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
                curr_obs = self._calendar.add_business_days(d_i, -shift_offset, centers)
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

        return rate_observations
