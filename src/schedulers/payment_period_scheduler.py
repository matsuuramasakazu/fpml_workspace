import calendar as py_calendar
from datetime import date
from typing import List

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    CalculationPeriod,
    InterestRateStream,
    PaymentCalculationPeriod,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.reference_resolver import ReferenceResolver


class PaymentPeriodScheduler:
    """計算期間（CalculationPeriod）を支払期間（PaymentCalculationPeriod）に集約し、支払日の調整を担当するクラス。"""

    def __init__(self, calendar: BusinessCalendar, resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            resolver: 参照解決を行うReferenceResolverインスタンス
        """
        self._adjuster = DateAdjuster(calendar, resolver)

    def _add_months(self, start_date: date, months: int, roll_convention: str) -> date:
        """指定された月数だけ日付を進めます（ロールコンベンション考慮）。"""
        y = start_date.year + (start_date.month + months - 1) // 12
        m = (start_date.month + months - 1) % 12 + 1

        last_day = py_calendar.monthrange(y, m)[1]

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

    def aggregate_periods(
        self, calc_periods: List[CalculationPeriod], stream: InterestRateStream
    ) -> List[PaymentCalculationPeriod]:
        """計算期間のリストを支払頻度に合わせて集約し、支払日の休日調整を行って支払期間のリストを返します。

        Args:
            calc_periods: 計算済みの CalculationPeriod オブジェクトのリスト
            stream: 金利ストリーム情報

        Returns:
            集約・調整された PaymentCalculationPeriod オブジェクトのリスト
        """
        # 1. 支払 unadjusted dates 系列の生成
        calc_dates = stream.calculation_period_dates
        effective_date_val = calc_dates.effective_date.unadjusted_date.value.to_date()
        termination_date_val = (
            calc_dates.termination_date.unadjusted_date.value.to_date()
        )

        first_regular = None
        if calc_dates.first_regular_period_start_date is not None:
            first_regular = calc_dates.first_regular_period_start_date.to_date()
        elif calc_dates.first_compounding_period_end_date is not None:
            first_regular = calc_dates.first_compounding_period_end_date.to_date()

        last_regular = None
        if calc_dates.last_regular_period_end_date is not None:
            last_regular = calc_dates.last_regular_period_end_date.to_date()

        pay_freq = stream.payment_dates.payment_frequency
        roll_conv = calc_dates.calculation_period_frequency.roll_convention.value

        reg_start = first_regular if first_regular is not None else effective_date_val
        reg_end = last_regular if last_regular is not None else termination_date_val

        if last_regular is not None:
            reg_dates = self._generate_unadjusted_dates_backward(
                reg_start,
                reg_end,
                pay_freq.period_multiplier,
                pay_freq.period.value,
                roll_conv,
            )
        else:
            reg_dates = self._generate_unadjusted_dates(
                reg_start,
                reg_end,
                pay_freq.period_multiplier,
                pay_freq.period.value,
                roll_conv,
            )

        # 支払 unadjusted dates (effective_date は除外し、ターゲット期日とする)
        payment_unadjusted_targets = []
        for d in reg_dates:
            if d != effective_date_val and d != termination_date_val:
                payment_unadjusted_targets.append(d)
        payment_unadjusted_targets.append(termination_date_val)
        payment_unadjusted_targets = sorted(list(set(payment_unadjusted_targets)))

        # 2. 計算期間を支払ターゲットに集約
        payment_periods = []
        current_group = []
        target_idx = 0

        for calc in calc_periods:
            current_group.append(calc)
            calc_end = calc.unadjusted_end_date.to_date()

            # もし現在の計算期間の unadjusted_end_date が現在の支払ターゲット期日に達した場合
            if (
                target_idx < len(payment_unadjusted_targets)
                and calc_end >= payment_unadjusted_targets[target_idx]
            ):
                last_calc = current_group[-1]
                unadjusted_pay_date = last_calc.unadjusted_end_date

                # paymentDaysOffset の考慮
                base_date = last_calc.adjusted_end_date.to_date()
                pay_dates = stream.payment_dates
                if pay_dates.payment_days_offset is not None:
                    pay_date_val = self._adjuster.resolve_relative_date_offset(
                        base_date, pay_dates.payment_days_offset
                    )
                else:
                    pay_date_val = base_date

                # paymentDatesAdjustments
                pay_adjustments = pay_dates.payment_dates_adjustments
                if pay_adjustments is not None:
                    adjusted_pay_date = self._adjuster.adjust_date(
                        pay_date_val, pay_adjustments
                    )
                else:
                    adjusted_pay_date = pay_date_val

                # stub_amount のチェック
                fixed_pay_amount = None
                calculation_period_group = current_group
                for c in current_group:
                    if hasattr(c, "_stub_amount") and c._stub_amount is not None:
                        fixed_pay_amount = c._stub_amount.amount
                        calculation_period_group = []
                        break

                payment_periods.append(
                    PaymentCalculationPeriod(
                        unadjusted_payment_date=unadjusted_pay_date,
                        adjusted_payment_date=XmlDate(
                            adjusted_pay_date.year,
                            adjusted_pay_date.month,
                            adjusted_pay_date.day,
                        ),
                        calculation_period=calculation_period_group,
                        fixed_payment_amount=fixed_pay_amount,
                    )
                )

                current_group = []
                target_idx += 1

        # 残りがあれば（通常はターゲットと完全同期するはずだが安全のため）
        if current_group:
            last_calc = current_group[-1]
            unadjusted_pay_date = last_calc.unadjusted_end_date
            base_date = last_calc.adjusted_end_date.to_date()
            pay_dates = stream.payment_dates
            if pay_dates.payment_days_offset is not None:
                pay_date_val = self._adjuster.resolve_relative_date_offset(
                    base_date, pay_dates.payment_days_offset
                )
            else:
                pay_date_val = base_date

            pay_adjustments = pay_dates.payment_dates_adjustments
            if pay_adjustments is not None:
                adjusted_pay_date = self._adjuster.adjust_date(
                    pay_date_val, pay_adjustments
                )
            else:
                adjusted_pay_date = pay_date_val

            fixed_pay_amount = None
            calculation_period_group = current_group
            for c in current_group:
                if hasattr(c, "_stub_amount") and c._stub_amount is not None:
                    fixed_pay_amount = c._stub_amount.amount
                    calculation_period_group = []
                    break

            payment_periods.append(
                PaymentCalculationPeriod(
                    unadjusted_payment_date=unadjusted_pay_date,
                    adjusted_payment_date=XmlDate(
                        adjusted_pay_date.year,
                        adjusted_pay_date.month,
                        adjusted_pay_date.day,
                    ),
                    calculation_period=calculation_period_group,
                    fixed_payment_amount=fixed_pay_amount,
                )
            )

        return payment_periods
