from datetime import date
from decimal import Decimal
from typing import List, Tuple

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    CalculationPeriod,
    InterestRateStream,
    PaymentCalculationPeriod,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.period_date_generator import PeriodDateGenerator
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
        # 1. 支払 unadjusted dates 系列の生成
        payment_unadjusted_targets = self._generate_payment_targets(stream)

        # 2. 計算期間を支払ターゲットに集約
        return self._aggregate_to_payment_periods(
            calc_periods, payment_unadjusted_targets, stream
        )

    def _generate_payment_targets(self, stream: InterestRateStream) -> List[date]:
        """支払頻度とロール慣行に従って、集約ターゲットとなる未調整の支払期日系列を生成します。"""
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

        # 支払期間の日付系列生成 (PeriodDateGenerator に委譲)
        if last_regular is not None:
            reg_dates = PeriodDateGenerator.generate_unadjusted_dates_backward(
                reg_start,
                reg_end,
                pay_freq.period_multiplier,
                pay_freq.period.value,
                roll_conv,
            )
        else:
            reg_dates = PeriodDateGenerator.generate_unadjusted_dates(
                reg_start,
                reg_end,
                pay_freq.period_multiplier,
                pay_freq.period.value,
                roll_conv,
            )

        # 支払ターゲット期日を抽出 (開始日は除外し、各期間の終了ターゲットとする)
        payment_unadjusted_targets = []
        for d in reg_dates:
            if d != effective_date_val and d != termination_date_val:
                payment_unadjusted_targets.append(d)
        payment_unadjusted_targets.append(termination_date_val)
        return sorted(list(set(payment_unadjusted_targets)))

    def _aggregate_to_payment_periods(
        self,
        calc_periods: List[CalculationPeriod],
        payment_unadjusted_targets: List[date],
        stream: InterestRateStream,
    ) -> List[PaymentCalculationPeriod]:
        """計算期間のリストを支払ターゲット期日系列に従って集約・グループ化します。"""
        payment_periods = []
        current_group = []
        target_idx = 0

        for calc in calc_periods:
            current_group.append(calc)
            calc_end = calc.unadjusted_end_date.to_date()

            # 計算期間の unadjusted_end_date が支払ターゲット期日に達した場合
            if (
                target_idx < len(payment_unadjusted_targets)
                and calc_end >= payment_unadjusted_targets[target_idx]
            ):
                payment_periods.append(
                    self._build_payment_period(current_group, stream)
                )
                current_group = []
                target_idx += 1

        # 残りがある場合のフォールバック（通常はターゲットと完全同期するため空のはず）
        if current_group:
            payment_periods.append(self._build_payment_period(current_group, stream))

        return payment_periods

    def _build_payment_period(
        self, current_group: List[CalculationPeriod], stream: InterestRateStream
    ) -> PaymentCalculationPeriod:
        """グループ化された計算期間リストから単一の支払期間（PaymentCalculationPeriod）をビルドします。"""
        last_calc = current_group[-1]
        unadjusted_pay_date = last_calc.unadjusted_end_date

        # 支払日の休日調整
        adjusted_pay_date = self._calculate_payment_date(last_calc, stream)

        # 固定支払金額（スタブ金額）の抽出
        fixed_pay_amount, calculation_period_group = self._extract_fixed_payment_amount(
            current_group
        )

        return PaymentCalculationPeriod(
            unadjusted_payment_date=unadjusted_pay_date,
            adjusted_payment_date=XmlDate(
                adjusted_pay_date.year,
                adjusted_pay_date.month,
                adjusted_pay_date.day,
            ),
            calculation_period=calculation_period_group,
            fixed_payment_amount=fixed_pay_amount,
        )

    def _calculate_payment_date(
        self, last_calc: CalculationPeriod, stream: InterestRateStream
    ) -> date:
        """支払オフセットおよび休日調整を適用して支払日を算出します。"""
        base_date = last_calc.adjusted_end_date.to_date()
        pay_dates = stream.payment_dates

        # paymentDaysOffset の考慮
        if pay_dates.payment_days_offset is not None:
            pay_date_val = self._adjuster.resolve_relative_date_offset(
                base_date, pay_dates.payment_days_offset
            )
        else:
            pay_date_val = base_date

        # paymentDatesAdjustments の考慮
        pay_adjustments = pay_dates.payment_dates_adjustments
        if pay_adjustments is not None:
            adjusted_pay_date = self._adjuster.adjust_date(
                pay_date_val, pay_adjustments
            )
        else:
            adjusted_pay_date = pay_date_val

        return adjusted_pay_date

    def _extract_fixed_payment_amount(
        self, current_group: List[CalculationPeriod]
    ) -> Tuple[Decimal | None, List[CalculationPeriod]]:
        """計算期間グループ内からスタブなどの固定支払額（Money）が設定されているものを抽出し、支払対象の計算期間グループと共に返します。"""
        fixed_pay_amount = None
        calculation_period_group = current_group
        for c in current_group:
            if hasattr(c, "_stub_amount") and c._stub_amount is not None:
                fixed_pay_amount = c._stub_amount.amount
                calculation_period_group = []
                break
        return fixed_pay_amount, calculation_period_group
