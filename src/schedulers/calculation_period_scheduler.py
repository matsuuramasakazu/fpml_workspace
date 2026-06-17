import calendar
from datetime import date
from typing import List

from xsdata.models.datatype import XmlDate

from fpml.confirmation import CalculationPeriod, InterestRateStream
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
        self._resolver = resolver
        self._adjuster = DateAdjuster(calendar, resolver)
        self._fixing_scheduler = FixingScheduler(calendar, resolver)

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

        unadjusted_dates = self._generate_unadjusted_dates(
            effective_date_val,
            termination_date_val,
            freq.period_multiplier,
            freq.period.value,
            roll_conv,
        )

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

        # 元本の取得
        notional_schedule = calc_params.notional_schedule
        if notional_schedule.notional_step_schedule is not None:
            notional = notional_schedule.notional_step_schedule.initial_value
        else:
            resolved_notional = self._resolver.resolve(
                notional_schedule.notional_step_parameters_reference
            )
            notional = resolved_notional.initial_value

        # 固定利率（ある場合）
        fixed_rate = None
        if calc_params.fixed_rate_schedule is not None:
            fixed_rate = calc_params.fixed_rate_schedule.initial_value

        calc_periods = []
        for i in range(len(unadjusted_dates) - 1):
            ustart = unadjusted_dates[i]
            uend = unadjusted_dates[i + 1]
            astart = adjusted_dates[i]
            aend = adjusted_dates[i + 1]

            num_days = (aend - astart).days
            year_fraction = day_count_calc.calculate_year_fraction(astart, aend)

            # 浮動金利パラメータ（ある場合）の取得
            floating_rate_def = self._fixing_scheduler.calculate_fixing(
                astart, aend, stream
            )

            calc_period = CalculationPeriod(
                unadjusted_start_date=XmlDate(ustart.year, ustart.month, ustart.day),
                unadjusted_end_date=XmlDate(uend.year, uend.month, uend.day),
                adjusted_start_date=XmlDate(astart.year, astart.month, astart.day),
                adjusted_end_date=XmlDate(aend.year, aend.month, aend.day),
                calculation_period_number_of_days=num_days,
                notional_amount=notional,
                day_count_year_fraction=year_fraction,
                fixed_rate=fixed_rate,
                floating_rate_definition=floating_rate_def,
            )
            calc_periods.append(calc_period)

        return calc_periods
