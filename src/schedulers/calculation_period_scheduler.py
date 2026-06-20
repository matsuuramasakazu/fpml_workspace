import calendar
from datetime import date
from decimal import Decimal
from typing import List

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
from src.schedulers.reference_resolver import ReferenceResolver


class CalculationPeriodScheduler:
    """計算期間（CalculationPeriod）のスケジュールの生成を担当するクラス。"""

    def __init__(self, calendar: BusinessCalendar, resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            resolver: 参照解決を行うReferenceResolverインスタンス
        """
        self._calendar = calendar
        self._resolver = resolver
        self._adjuster = DateAdjuster(calendar, resolver)
        self._fixing_scheduler = FixingScheduler(calendar, resolver)

    def _resolve_schedule_value(
        self, schedule: Schedule | None, ref_date: date
    ) -> Decimal | None:
        """指定された基準日（ref_date）時点のスケジュール値を解決します。"""
        if schedule is None:
            return None

        initial_value = schedule.initial_value
        steps = getattr(schedule, "step", [])
        if not steps:
            return initial_value

        # step_date でソート
        sorted_steps = sorted(steps, key=lambda s: s.step_date.to_date())

        resolved_value = initial_value
        for step in sorted_steps:
            if step.step_date.to_date() <= ref_date:
                resolved_value = step.step_value
            else:
                break

        return resolved_value

    def _add_months(self, start_date: date, months: int, roll_convention: str) -> date:
        """指定された月数だけ日付を進めます（ロールコンベンション考慮）。"""
        y = start_date.year + (start_date.month + months - 1) // 12
        m = (start_date.month + months - 1) % 12 + 1

        last_day = calendar.monthrange(y, m)[1]

        if roll_convention == "EOM" or roll_convention == "31":
            return date(y, m, last_day)

        try:
            day_num = int(roll_convention)
            if 1 <= day_num <= 30:
                return date(y, m, min(day_num, last_day))
        except ValueError:
            pass

        return date(y, m, min(start_date.day, last_day))

    def _generate_unadjusted_dates(
        self,
        start_date: date,
        end_date: date,
        multiplier: int,
        period: str,
        roll_convention: str,
    ) -> List[date]:
        """unadjusted な計算期日のリストを生成します。"""
        dates = [start_date]
        months_to_add = multiplier
        if period == "Y":
            months_to_add *= 12

        i = 1
        while True:
            next_date = self._add_months(start_date, i * months_to_add, roll_convention)
            if next_date >= end_date:
                break
            dates.append(next_date)
            i += 1

        dates.append(end_date)
        return dates

    def _generate_unadjusted_dates_backward(
        self,
        start_date: date,
        end_date: date,
        multiplier: int,
        period: str,
        roll_convention: str,
    ) -> List[date]:
        """後退的に unadjusted な計算期日のリストを生成します。"""
        dates = [end_date]
        months_to_subtract = multiplier
        if period == "Y":
            months_to_subtract *= 12

        i = 1
        while True:
            next_date = self._add_months(
                end_date, -i * months_to_subtract, roll_convention
            )
            if next_date <= start_date:
                break
            dates.append(next_date)
            i += 1

        dates.append(start_date)
        return sorted(list(set(dates)))

    def resolve_notional(self, calc_params, ref_date: date) -> Decimal | None:
        """指定された基準日（ref_date）時点の想定元本を解決します。"""
        if calc_params.fx_linked_notional_schedule is not None:
            return None

        notional_schedule = calc_params.notional_schedule
        if notional_schedule is None:
            return None

        step_schedule = None
        if notional_schedule.notional_step_schedule is not None:
            step_schedule = notional_schedule.notional_step_schedule
        elif notional_schedule.notional_step_parameters_reference is not None:
            step_schedule = self._resolver.resolve(
                notional_schedule.notional_step_parameters_reference
            )

        if step_schedule is None:
            return None

        return self._resolve_schedule_value(step_schedule, ref_date)

    def generate_periods(self, stream: InterestRateStream) -> List[CalculationPeriod]:
        """InterestRateStream パラメータから CalculationPeriod スケジュールを展開します。

        Args:
            stream: 金利ストリーム情報

        Returns:
            生成された CalculationPeriod のリスト
        """
        calc_dates = stream.calculation_period_dates
        effective_date_val = calc_dates.effective_date.unadjusted_date.value.to_date()
        termination_date_val = (
            calc_dates.termination_date.unadjusted_date.value.to_date()
        )

        # 調整された開始日と終了日の計算
        effective_adjusted = self._adjuster.adjust_date(
            effective_date_val, calc_dates.effective_date.date_adjustments
        )
        termination_adjusted = self._adjuster.adjust_date(
            termination_date_val, calc_dates.termination_date.date_adjustments
        )

        freq = calc_dates.calculation_period_frequency
        roll_conv = freq.roll_convention.value

        # スタブ日付の取得
        first_regular = None
        if calc_dates.first_regular_period_start_date is not None:
            first_regular = calc_dates.first_regular_period_start_date.to_date()

        last_regular = None
        if calc_dates.last_regular_period_end_date is not None:
            last_regular = calc_dates.last_regular_period_end_date.to_date()

        # レギュラー期間の基準日
        reg_start = first_regular if first_regular is not None else effective_date_val
        reg_end = last_regular if last_regular is not None else termination_date_val

        # レギュラー期間の日付生成
        if last_regular is not None:
            reg_dates = self._generate_unadjusted_dates_backward(
                reg_start,
                reg_end,
                freq.period_multiplier,
                freq.period.value,
                roll_conv,
            )
        else:
            reg_dates = self._generate_unadjusted_dates(
                reg_start,
                reg_end,
                freq.period_multiplier,
                freq.period.value,
                roll_conv,
            )

        # 全体の日付リストを作成
        unadjusted_dates = [effective_date_val]
        for d in reg_dates:
            if d != effective_date_val and d != termination_date_val:
                unadjusted_dates.append(d)
        unadjusted_dates.append(termination_date_val)
        unadjusted_dates = sorted(list(set(unadjusted_dates)))

        # 計算期間日付の調整ルール
        calc_adjustments = calc_dates.calculation_period_dates_adjustments

        # 中間期日の休日調整
        adjusted_dates = [effective_adjusted]
        for d in unadjusted_dates[1:-1]:
            adjusted_dates.append(self._adjuster.adjust_date(d, calc_adjustments))
        adjusted_dates.append(termination_adjusted)

        # 金利計算パラメータの抽出
        calc_params = stream.calculation_period_amount.calculation
        day_count_fraction = calc_params.day_count_fraction.value
        day_count_calc = DayCountCalculator(day_count_fraction)

        fx_linked_notional_schedule = calc_params.fx_linked_notional_schedule

        # 固定利率（ある場合）
        fixed_rate_schedule = calc_params.fixed_rate_schedule

        calc_periods = []
        for i in range(len(unadjusted_dates) - 1):
            ustart = unadjusted_dates[i]
            uend = unadjusted_dates[i + 1]
            astart = adjusted_dates[i]
            aend = adjusted_dates[i + 1]

            num_days = (aend - astart).days
            year_fraction = day_count_calc.calculate_year_fraction(astart, aend)

            # 想定元本の解決
            notional = self.resolve_notional(calc_params, ustart)

            # 浮動金利パラメータ（ある場合）の取得
            floating_rate_def = self._fixing_scheduler.calculate_fixing(
                astart, aend, stream, ustart
            )

            # スタブ期間の判定と解決
            is_initial_stub = first_regular is not None and ustart < first_regular
            is_final_stub = last_regular is not None and uend > last_regular

            stub_info = None
            if (
                is_initial_stub or is_final_stub
            ) and stream.stub_calculation_period_amount is not None:
                stub_amount_info = stream.stub_calculation_period_amount
                if is_initial_stub and stub_amount_info.initial_stub is not None:
                    stub_info = stub_amount_info.initial_stub
                elif is_final_stub and stub_amount_info.final_stub is not None:
                    stub_info = stub_amount_info.final_stub

            period_fixed_rate = self._resolve_schedule_value(
                fixed_rate_schedule, ustart
            )
            period_floating_rate_def = floating_rate_def
            period_stub_amount = None

            if stub_info is not None:
                if stub_info.stub_rate is not None:
                    period_fixed_rate = stub_info.stub_rate
                    period_floating_rate_def = None
                elif stub_info.stub_amount is not None:
                    period_fixed_rate = None
                    period_floating_rate_def = None
                    period_stub_amount = stub_info.stub_amount

            # FxLinkedNotionalAmountの構築
            fx_linked_notional_amount = None
            if fx_linked_notional_schedule is not None:
                # リセット日の特定（一般には `adjusted_start`）
                reset_date_val = astart
                if stream.reset_dates is not None:
                    reset_rel = stream.reset_dates.reset_relative_to
                    if (
                        reset_rel is not None
                        and reset_rel.value == "CalculationPeriodEndDate"
                    ):
                        reset_date_val = aend

                # FX決定日の算出
                fixing_dates = fx_linked_notional_schedule.varying_notional_fixing_dates
                adjusted_fx_spot_fixing = self._adjuster.resolve_relative_date_offset(
                    reset_date_val, fixing_dates
                )

                fx_linked_notional_amount = FxLinkedNotionalAmount(
                    reset_date=XmlDate(
                        reset_date_val.year, reset_date_val.month, reset_date_val.day
                    ),
                    adjusted_fx_spot_fixing_date=XmlDate(
                        adjusted_fx_spot_fixing.year,
                        adjusted_fx_spot_fixing.month,
                        adjusted_fx_spot_fixing.day,
                    ),
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
                fixed_rate=period_fixed_rate,
                floating_rate_definition=period_floating_rate_def,
            )
            if period_stub_amount is not None:
                calc_period._stub_amount = period_stub_amount
            calc_periods.append(calc_period)

        return calc_periods
