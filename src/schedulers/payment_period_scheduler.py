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
        pay_freq = stream.payment_dates.payment_frequency
        pay_months = pay_freq.period_multiplier
        if pay_freq.period.value == "Y":
            pay_months *= 12

        calc_dates = stream.calculation_period_dates
        calc_freq = calc_dates.calculation_period_frequency
        calc_months = calc_freq.period_multiplier
        if calc_freq.period.value == "Y":
            calc_months *= 12

        periods_per_payment = max(1, pay_months // calc_months)

        payment_periods = []
        for i in range(0, len(calc_periods), periods_per_payment):
            group = calc_periods[i : i + periods_per_payment]
            last_calc = group[-1]
            unadjusted_pay_date = last_calc.unadjusted_end_date

            # paymentDatesAdjustments
            pay_adjustments = stream.payment_dates.payment_dates_adjustments
            base_date = last_calc.adjusted_end_date.to_date()
            adjusted_pay_date = self._adjuster.adjust_date(base_date, pay_adjustments)

            payment_periods.append(
                PaymentCalculationPeriod(
                    unadjusted_payment_date=unadjusted_pay_date,
                    adjusted_payment_date=XmlDate(
                        adjusted_pay_date.year,
                        adjusted_pay_date.month,
                        adjusted_pay_date.day,
                    ),
                    calculation_period=group,
                )
            )

        return payment_periods
