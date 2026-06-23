import calendar
from datetime import date
from decimal import Decimal
from typing import Any, List, Tuple

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    CalculationPeriod,
    FxLinkedNotionalAmount,
    InterestRateStream,
    Schedule,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.day_count_calculator import DayCountCalculator
from src.schedulers.fixing_scheduler import FixingScheduler
from src.schedulers.period_date_generator import PeriodDateGenerator
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver import StepScheduleResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


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
        self._fixing_scheduler = FixingScheduler(calendar, ref_resolver)

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
        # 1. 開始日と終了日の休日調整
        adjusted_start, adjusted_end = self._resolve_adjusted_boundaries(stream)

        # 2. unadjusted dates 系列の生成
        unadjusted_dates = self._generate_unadjusted_schedule_dates(stream)

        # 3. 中間期日の休日調整
        adjusted_dates = self._adjust_intermediate_dates(
            unadjusted_dates, adjusted_start, adjusted_end, stream
        )

        # 4. 各計算期間の構築
        return self._build_calculation_periods(
            unadjusted_dates, adjusted_dates, stream, step_schedule_resolver_factory
        )

    def _resolve_adjusted_boundaries(
        self, stream: InterestRateStream
    ) -> Tuple[date, date]:
        """開始日と終了日の調整日を算出します。"""
        calc_dates = stream.calculation_period_dates
        effective_date_val = calc_dates.effective_date.unadjusted_date.value.to_date()
        termination_date_val = calc_dates.termination_date.unadjusted_date.value.to_date()

        if calc_dates.first_period_start_date is not None:
            actual_start = calc_dates.first_period_start_date.unadjusted_date.value.to_date()
        else:
            actual_start = effective_date_val

        actual_start_adjusted = self._adjuster.adjust_date(
            actual_start, calc_dates.effective_date.date_adjustments
        )
        termination_adjusted = self._adjuster.adjust_date(
            termination_date_val, calc_dates.termination_date.date_adjustments
        )
        return actual_start_adjusted, termination_adjusted

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

        first_regular = None
        if calc_dates.first_regular_period_start_date is not None:
            first_regular = calc_dates.first_regular_period_start_date.to_date()
        elif calc_dates.first_compounding_period_end_date is not None:
            first_regular = calc_dates.first_compounding_period_end_date.to_date()

        last_regular = None
        if calc_dates.last_regular_period_end_date is not None:
            last_regular = calc_dates.last_regular_period_end_date.to_date()

        # レギュラー期間の基準日
        reg_start = first_regular if first_regular is not None else effective_date_val
        reg_end = last_regular if last_regular is not None else termination_date_val

        # レギュラー期間の日付生成 (PeriodDateGenerator に委譲)
        if last_regular is not None:
            reg_dates = PeriodDateGenerator.generate_unadjusted_dates_backward(
                reg_start,
                reg_end,
                freq.period_multiplier,
                freq.period.value,
                roll_conv,
            )
        else:
            reg_dates = PeriodDateGenerator.generate_unadjusted_dates(
                reg_start,
                reg_end,
                freq.period_multiplier,
                freq.period.value,
                roll_conv,
            )

        # 全体の日付リストを作成
        if calc_dates.first_period_start_date is not None:
            actual_start = calc_dates.first_period_start_date.unadjusted_date.to_date()
        else:
            actual_start = effective_date_val

        unadjusted_dates = [actual_start]
        for d in reg_dates:
            if d != actual_start and d != termination_date_val:
                unadjusted_dates.append(d)
        unadjusted_dates.append(termination_date_val)
        return sorted(list(set(unadjusted_dates)))

    def _adjust_intermediate_dates(
        self,
        unadjusted_dates: List[date],
        adjusted_start: date,
        adjusted_end: date,
        stream: InterestRateStream,
    ) -> List[date]:
        """中間期日の休日調整を行います。"""
        calc_dates = stream.calculation_period_dates
        calc_adjustments = calc_dates.calculation_period_dates_adjustments

        adjusted_dates = [adjusted_start]
        for d in unadjusted_dates[1:-1]:
            adjusted_dates.append(self._adjuster.adjust_date(d, calc_adjustments))
        adjusted_dates.append(adjusted_end)
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

            # 固定金利、浮動金利、スタブの解決
            fixed_rate, floating_rate_def, stub_amount = self._resolve_rates_for_period(
                ustart, uend, astart, aend, stream, step_schedule_resolver_factory
            )

            # FxLinkedNotionalAmountの構築
            fx_linked_notional_amount = self._build_fx_linked_notional(
                astart, aend, fx_linked_notional_schedule, stream
            )

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

    def _resolve_rates_for_period(
        self,
        ustart: date,
        uend: date,
        astart: date,
        aend: date,
        stream: InterestRateStream,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> Tuple[Decimal | None, Any | None, Any | None]:
        """各期間に応じた適用金利（固定／浮動／スタブ設定）を解決します。"""
        calc_dates = stream.calculation_period_dates
        first_regular = None
        if calc_dates.first_regular_period_start_date is not None:
            first_regular = calc_dates.first_regular_period_start_date.to_date()
        elif calc_dates.first_compounding_period_end_date is not None:
            first_regular = calc_dates.first_compounding_period_end_date.to_date()

        last_regular = None
        if calc_dates.last_regular_period_end_date is not None:
            last_regular = calc_dates.last_regular_period_end_date.to_date()

        is_initial_stub = first_regular is not None and ustart < first_regular
        is_final_stub = last_regular is not None and uend > last_regular

        # デフォルトの金利設定 (ループ外で生成されたリゾルバーを利用)
        fixed_rate = step_schedule_resolver_factory.fixed_rate_resolver.resolve(ustart)
        floating_rate_def = self._fixing_scheduler.calculate_fixing(
            astart, aend, stream, step_schedule_resolver_factory, ustart
        )
        stub_amount = None

        # スタブ情報の適用
        stub_info = None
        if (
            is_initial_stub or is_final_stub
        ) and stream.stub_calculation_period_amount is not None:
            stub_amount_info = stream.stub_calculation_period_amount
            if is_initial_stub and stub_amount_info.initial_stub is not None:
                stub_info = stub_amount_info.initial_stub
            elif is_final_stub and stub_amount_info.final_stub is not None:
                stub_info = stub_amount_info.final_stub

        if stub_info is not None:
            if stub_info.stub_rate is not None:
                fixed_rate = stub_info.stub_rate
                floating_rate_def = None
            elif stub_info.stub_amount is not None:
                fixed_rate = None
                floating_rate_def = None
                stub_amount = stub_info.stub_amount

        return fixed_rate, floating_rate_def, stub_amount

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

        reset_date_val = astart
        if stream.reset_dates is not None:
            reset_rel = stream.reset_dates.reset_relative_to
            if reset_rel is not None and reset_rel.value == "CalculationPeriodEndDate":
                reset_date_val = aend

        fixing_dates = fx_linked_notional_schedule.varying_notional_fixing_dates
        adjusted_fx_spot_fixing = self._adjuster.resolve_relative_date_offset(
            reset_date_val, fixing_dates
        )

        return FxLinkedNotionalAmount(
            reset_date=XmlDate(
                reset_date_val.year, reset_date_val.month, reset_date_val.day
            ),
            adjusted_fx_spot_fixing_date=XmlDate(
                adjusted_fx_spot_fixing.year,
                adjusted_fx_spot_fixing.month,
                adjusted_fx_spot_fixing.day,
            ),
        )
