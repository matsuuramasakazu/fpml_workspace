import calendar
from datetime import date
from decimal import Decimal
from typing import Any, List, Tuple

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    CalculationPeriod,
    CalculationPeriodDates,
    FxLinkedNotionalAmount,
    InterestRateStream,
    RelativeDateOffset,
    ResetDates,
    ResetRelativeToEnum,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.day_count_calculator import DayCountCalculator
from src.schedulers.fixed_rate_period_resolver import FixedRatePeriodResolver
from src.schedulers.floating_rate_period_resolver import FloatingRatePeriodResolver
from src.schedulers.period_date_generator import PeriodDateGenerator
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver import StepScheduleResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory
from src.schedulers.stub_period_resolver import StubPeriodResolver


class CalculationPeriodScheduler:
    """計算期間（CalculationPeriod）のスケジュールの生成を担当するクラス。"""

    def __init__(self, calendar: BusinessCalendar, ref_resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            ref_resolver: 参照解決を行うReferenceResolverインスタンス
        """
        self._calendar = calendar
        self._ref_resolver = ref_resolver
        self._adjuster = DateAdjuster(calendar, ref_resolver)
        self._floating_resolver = FloatingRatePeriodResolver(calendar, ref_resolver)

    def generate_periods(
        self,
        stream: InterestRateStream,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> List[CalculationPeriod]:
        """InterestRateStream パラメータから CalculationPeriod スケジュールを展開します。

        Args:
            stream: 金利ストリーム情報
            step_schedule_resolver_factory: 各種ステップスケジュールリゾルバーを保持するFactory

        Returns:
            生成された CalculationPeriod のリスト
        """
        # 1. unadjusted dates 系列の生成
        unadjusted_dates = self._generate_unadjusted_schedule_dates(stream)

        # 2. 開始日と終了日の休日調整
        adjusted_start, adjusted_end = self._adjust_boundary_dates(stream)

        # 3. 中間期日の休日調整
        adjusted_intermediate_dates = self._adjust_intermediate_dates(
            unadjusted_dates, stream
        )

        adjusted_dates = [adjusted_start, *adjusted_intermediate_dates, adjusted_end]

        # 4. 各計算期間の構築
        return self._build_calculation_periods(
            unadjusted_dates, adjusted_dates, stream, step_schedule_resolver_factory
        )

    def _generate_unadjusted_schedule_dates(
        self, stream: InterestRateStream
    ) -> List[date]:
        """スタブ設定を考慮した unadjusted な日付の期日系列を生成します。"""
        calc_dates = stream.calculation_period_dates
        effective_date_val = calc_dates.effective_date.unadjusted_date.value.to_date()
        termination_date_val = (
            calc_dates.termination_date.unadjusted_date.value.to_date()
        )

        freq = calc_dates.calculation_period_frequency
        roll_conv = freq.roll_convention.value

        first_reg_calc_date_val = None
        if calc_dates.first_regular_period_start_date is not None:
            first_reg_calc_date_val = (
                calc_dates.first_regular_period_start_date.to_date()
            )
        elif calc_dates.first_compounding_period_end_date is not None:
            first_reg_calc_date_val = (
                calc_dates.first_compounding_period_end_date.to_date()
            )

        last_reg_calc_date_val = None
        if calc_dates.last_regular_period_end_date is not None:
            last_reg_calc_date_val = calc_dates.last_regular_period_end_date.to_date()

        # レギュラー期間の基準日
        reg_start_date_val = (
            first_reg_calc_date_val
            if first_reg_calc_date_val is not None
            else effective_date_val
        )
        reg_end_date_val = (
            last_reg_calc_date_val
            if last_reg_calc_date_val is not None
            else termination_date_val
        )

        # レギュラー期間の日付生成 (PeriodDateGenerator に委譲)
        if last_reg_calc_date_val is not None:
            reg_calc_dates = PeriodDateGenerator.generate_unadjusted_dates_backward(
                reg_start_date_val,
                reg_end_date_val,
                freq.period_multiplier,
                freq.period.value,
                roll_conv,
            )
        else:
            reg_calc_dates = PeriodDateGenerator.generate_unadjusted_dates(
                reg_start_date_val,
                reg_end_date_val,
                freq.period_multiplier,
                freq.period.value,
                roll_conv,
            )

        # 全体の日付リストを作成
        if calc_dates.first_period_start_date is not None:
            start_calc_date_val = (
                calc_dates.first_period_start_date.unadjusted_date.to_date()
            )
        else:
            start_calc_date_val = effective_date_val

        unadjusted_calc_dates = [start_calc_date_val]

        for reg_calc_date in reg_calc_dates:
            if (
                reg_calc_date != start_calc_date_val
                and reg_calc_date != termination_date_val
            ):
                unadjusted_calc_dates.append(reg_calc_date)

        unadjusted_calc_dates.append(termination_date_val)

        return sorted(list(set(unadjusted_calc_dates)))

    def _adjust_boundary_dates(self, stream: InterestRateStream) -> Tuple[date, date]:
        """開始日と終了日の調整日を算出します。"""
        calc_dates = stream.calculation_period_dates
        effective_date_val = calc_dates.effective_date.unadjusted_date.value.to_date()
        termination_date_val = (
            calc_dates.termination_date.unadjusted_date.value.to_date()
        )

        if calc_dates.first_period_start_date is not None:
            actual_start = (
                calc_dates.first_period_start_date.unadjusted_date.value.to_date()
            )
            start_adjustments = calc_dates.first_period_start_date.date_adjustments
        else:
            actual_start = effective_date_val
            start_adjustments = calc_dates.effective_date.date_adjustments

        actual_start_adjusted = self._adjuster.adjust_date(
            actual_start, start_adjustments
        )
        termination_adjusted = self._adjuster.adjust_date(
            termination_date_val, calc_dates.termination_date.date_adjustments
        )
        return actual_start_adjusted, termination_adjusted

    def _adjust_intermediate_dates(
        self,
        unadjusted_dates: List[date],
        stream: InterestRateStream,
    ) -> List[date]:
        """中間期日の休日調整を行います。"""
        calc_dates = stream.calculation_period_dates
        calc_adjustments = calc_dates.calculation_period_dates_adjustments

        adjusted_dates = [
            self._adjuster.adjust_date(d, calc_adjustments)
            for d in unadjusted_dates[1:-1]
        ]
        return adjusted_dates

    def _build_calculation_periods(
        self,
        unadjusted_dates: List[date],
        adjusted_dates: List[date],
        stream: InterestRateStream,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> List[CalculationPeriod]:
        """計算期間オブジェクト（CalculationPeriod）のリストを構築します。"""
        calc_params = stream.calculation_period_amount.calculation
        day_count_fraction = calc_params.day_count_fraction.value
        day_count_calc = DayCountCalculator(day_count_fraction)

        fx_linked_notional_schedule = calc_params.fx_linked_notional_schedule

        # 各金利・スタブ解決用リゾルバーの生成
        fixed_resolver = FixedRatePeriodResolver(
            step_schedule_resolver_factory.fixed_rate_resolver
        )
        floating_resolver = self._floating_resolver
        stub_resolver = StubPeriodResolver()

        calc_periods = []
        for i in range(len(unadjusted_dates) - 1):
            ustart = unadjusted_dates[i]
            uend = unadjusted_dates[i + 1]
            astart = adjusted_dates[i]
            aend = adjusted_dates[i + 1]

            num_days = (aend - astart).days
            year_fraction = round(
                day_count_calc.calculate_year_fraction(astart, aend), 12
            )

            # 想定元本の解決 (ループ外で生成されたリゾルバーを利用)
            notional = step_schedule_resolver_factory.notional_resolver.resolve(ustart)

            # FxLinkedNotionalAmountの構築
            fx_linked_notional_amount = self._build_fx_linked_notional(
                astart, aend, fx_linked_notional_schedule, stream
            )

            # 各金利タイプの解決
            # 通常金利の解決
            fixed_rate = fixed_resolver.resolve_rate(ustart)
            floating_rate_def = floating_resolver.resolve_rate_def(
                astart, aend, stream, step_schedule_resolver_factory, ustart
            )
            stub_amount = None

            # スタブ判定および上書き適用
            is_initial, is_final = stub_resolver.is_stub(
                ustart, uend, stream.calculation_period_dates
            )
            if is_initial or is_final:
                stub_rate, s_amount = stub_resolver.resolve_stub_overrides(
                    is_initial, is_final, stream
                )
                if stub_rate is not None:
                    fixed_rate = stub_rate
                    floating_rate_def = None
                elif s_amount is not None:
                    fixed_rate = None
                    floating_rate_def = None
                    stub_amount = s_amount

            calc_period = CalculationPeriod(
                unadjusted_start_date=XmlDate(ustart.year, ustart.month, ustart.day),
                unadjusted_end_date=XmlDate(uend.year, uend.month, uend.day),
                adjusted_start_date=XmlDate(astart.year, astart.month, astart.day),
                adjusted_end_date=XmlDate(aend.year, aend.month, aend.day),
                calculation_period_number_of_days=num_days,
                notional_amount=notional,
                fx_linked_notional_amount=fx_linked_notional_amount,
                day_count_year_fraction=year_fraction,
                fixed_rate=fixed_rate,
                floating_rate_definition=floating_rate_def,
            )
            if stub_amount is not None:
                calc_period._stub_amount = stub_amount
            calc_periods.append(calc_period)

        return calc_periods

    def _build_fx_linked_notional(
        self,
        astart: date,
        aend: date,
        fx_linked_notional_schedule: Any | None,
        stream: InterestRateStream,
    ) -> FxLinkedNotionalAmount | None:
        """FX-linked 想定元本オブジェクトを構築します。"""
        if fx_linked_notional_schedule is None:
            return None

        fixing_dates: RelativeDateOffset = (
            fx_linked_notional_schedule.varying_notional_fixing_dates
        )
        resolved_anchor = self._ref_resolver.resolve(fixing_dates.date_relative_to)
        if isinstance(resolved_anchor, ResetDates):
            if (
                resolved_anchor.reset_relative_to
                == ResetRelativeToEnum.CALCULATION_PERIOD_START_DATE
            ):
                reset_date_val = astart
            elif (
                resolved_anchor.reset_relative_to
                == ResetRelativeToEnum.CALCULATION_PERIOD_END_DATE
            ):
                reset_date_val = aend
            else:
                raise ValueError(
                    f"Unknown reset relative to: {resolved_anchor.reset_relative_to}"
                )
        elif isinstance(resolved_anchor, CalculationPeriodDates):
            reset_date_val = astart
        else:
            raise ValueError(f"Unknown reset anchor: {resolved_anchor}")

        adjusted_fx_spot_fixing = self._adjuster.resolve_relative_date_offset(
            reset_date_val, fixing_dates
        )

        return FxLinkedNotionalAmount(
            # reset_dateは設定しないのが一般的（CalculationPeriodのadjustedStartDateと同じタイミング）
            reset_date=XmlDate(astart.year, astart.month, astart.day),
            adjusted_fx_spot_fixing_date=XmlDate(
                adjusted_fx_spot_fixing.year,
                adjusted_fx_spot_fixing.month,
                adjusted_fx_spot_fixing.day,
            ),
        )
