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
from src.schedulers.calculation_period_scheduler import CalculationPeriodScheduler
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.period_date_generator import PeriodDateGenerator
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


class PaymentPeriodScheduler:
    """計算期間（CalculationPeriod）を支払期間（PaymentCalculationPeriod）に集約し、支払日の調整を担当するクラス。"""

    def __init__(self, calendar: BusinessCalendar, ref_resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            ref_resolver: 参照解決を行うReferenceResolverインスタンス
        """
        self._adjuster = DateAdjuster(calendar, ref_resolver)
        self._calculation_period_scheduler = CalculationPeriodScheduler(
            calendar, ref_resolver
        )

    def generate_payment_periods(
        self,
        stream: InterestRateStream,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> List[PaymentCalculationPeriod]:
        """InterestRateStream パラメータから PaymentCalculationPeriod スケジュールを展開します。

        Args:
            stream: FpML の金利ストリーム（レグ）情報
            step_schedule_resolver_factory: 各種ステップスケジュールリゾルバーを保持するFactory

        Returns:
            展開・調整された支払計算期間（PaymentCalculationPeriod）のリスト
        """
        # 1. 計算期間スケジュールの生成
        calc_periods = self._calculation_period_scheduler.generate_periods(
            stream, step_schedule_resolver_factory
        )

        # 2. 支払日サイクル基準日系列の生成
        payment_cycle_dates = self._generate_payment_cycle_dates(stream)

        # 3. 計算期間を支払日サイクル基準日で集約し、休日調整を適用
        return self._aggregate_to_payment_periods(
            calc_periods, payment_cycle_dates, stream
        )

    def _generate_payment_cycle_dates(
        self, stream: InterestRateStream
    ) -> List[date]:
        """支払頻度とロール慣行に従って、支払日サイクル基準日系列を生成します。"""
        pay_dates = stream.payment_dates
        calc_dates = stream.calculation_period_dates
        effective_date_val = calc_dates.effective_date.unadjusted_date.value.to_date()
        termination_date_val = (
            calc_dates.termination_date.unadjusted_date.value.to_date()
        )

        first_reg_pay_date_val = None
        if pay_dates.first_payment_date is not None:
            first_reg_pay_date_val = pay_dates.first_payment_date.to_date()
        elif calc_dates.first_regular_period_start_date is not None:
            first_reg_pay_date_val = calc_dates.first_regular_period_start_date.to_date()
        elif calc_dates.first_compounding_period_end_date is not None:
            first_reg_pay_date_val = calc_dates.first_compounding_period_end_date.to_date()

        last_reg_pay_date_val = None
        if pay_dates.last_regular_payment_date is not None:
            last_reg_pay_date_val = pay_dates.last_regular_payment_date.to_date()
        elif calc_dates.last_regular_period_end_date is not None:
            last_reg_pay_date_val = calc_dates.last_regular_period_end_date.to_date()

        pay_freq = pay_dates.payment_frequency
        roll_conv = calc_dates.calculation_period_frequency.roll_convention.value

        reg_start_date_val = first_reg_pay_date_val if first_reg_pay_date_val is not None else effective_date_val
        reg_end_date_val = last_reg_pay_date_val if last_reg_pay_date_val is not None else termination_date_val

        # 支払日サイクル基準日系列の生成
        if last_reg_pay_date_val is not None:
            reg_pay_dates = PeriodDateGenerator.generate_unadjusted_dates_backward(
                reg_start_date_val,
                reg_end_date_val,
                pay_freq.period_multiplier,
                pay_freq.period.value,
                roll_conv,
            )
        else:
            reg_pay_dates = PeriodDateGenerator.generate_unadjusted_dates(
                reg_start_date_val,
                reg_end_date_val,
                pay_freq.period_multiplier,
                pay_freq.period.value,
                roll_conv,
            )

        # 支払日サイクル基準日を抽出（開始日は除外し、各支払期間の終了日とする）
        pay_cycle_dates = []
        for reg_pay_date in reg_pay_dates:
            if reg_pay_date != effective_date_val and reg_pay_date != termination_date_val:
                pay_cycle_dates.append(reg_pay_date)
        pay_cycle_dates.append(termination_date_val)
        return sorted(list(set(pay_cycle_dates)))

    def _aggregate_to_payment_periods(
        self,
        calc_periods: List[CalculationPeriod],
        payment_cycle_dates: List[date],
        stream: InterestRateStream,
    ) -> List[PaymentCalculationPeriod]:
        """計算期間のリストを支払日サイクル基準日系列に従って支払期間にグループ化します。"""
        payment_periods = []
        calc_period_group = []
        payment_date_idx = 0

        for calc_period in calc_periods:
            calc_period_group.append(calc_period)
            calc_end = calc_period.unadjusted_end_date.to_date()

            # 計算期間の unadjusted_end_date が支払日サイクル基準日に達した場合
            if (
                payment_date_idx < len(payment_cycle_dates)
                and calc_end >= payment_cycle_dates[payment_date_idx]
            ):
                payment_periods.append(
                    self._build_payment_period(calc_period_group, stream)
                )
                calc_period_group = []
                payment_date_idx += 1

        # 残りがある場合のフォールバック（通常は支払日サイクル基準日と完全同期するため空のはず）
        if calc_period_group:
            payment_periods.append(self._build_payment_period(calc_period_group, stream))

        return payment_periods

    def _build_payment_period(
        self, calc_period_group: List[CalculationPeriod], stream: InterestRateStream
    ) -> PaymentCalculationPeriod:
        """グループ化された計算期間リストから単一の支払期間（PaymentCalculationPeriod）をビルドします。"""
        pay_dates = stream.payment_dates
        pay_relative_to = pay_dates.pay_relative_to.value

        if pay_relative_to == "CalculationPeriodEndDate":
            unadjusted_pay_date = calc_period_group[-1].unadjusted_end_date
        elif pay_relative_to == "CalculationPeriodStartDate":
            unadjusted_pay_date = calc_period_group[0].unadjusted_start_date
        else:
            raise NotImplementedError(f"Unsupported pay_relative_to: {pay_relative_to}")

        # 支払日のオフセットおよび休日調整
        adjusted_pay_date = self._adjust_payment_date(calc_period_group, stream)

        # 固定支払金額（スタブ金額）の抽出
        fixed_pay_amount, calculation_period_group = self._extract_fixed_payment_amount(
            calc_period_group
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

    def _adjust_payment_date(
        self, calc_period_group: List[CalculationPeriod], stream: InterestRateStream
    ) -> date:
        """支払オフセットおよび休日調整を適用して支払日を算出します。"""
        pay_dates = stream.payment_dates
        pay_relative_to = pay_dates.pay_relative_to.value

        if pay_relative_to == "CalculationPeriodEndDate":
            unadjusted_pay_date_val = calc_period_group[-1].unadjusted_end_date.to_date()
        elif pay_relative_to == "CalculationPeriodStartDate":
            unadjusted_pay_date_val = calc_period_group[0].unadjusted_start_date.to_date()
        else:
            raise NotImplementedError(f"Unsupported pay_relative_to: {pay_relative_to}")

        # paymentDaysOffset の考慮
        if pay_dates.payment_days_offset is not None:
            offset_pay_date_val = self._adjuster.resolve_relative_date_offset(
                unadjusted_pay_date_val, pay_dates.payment_days_offset
            )
        else:
            offset_pay_date_val = unadjusted_pay_date_val

        # paymentDatesAdjustments の考慮
        pay_adjustments = pay_dates.payment_dates_adjustments
        if pay_adjustments is not None:
            adjusted_pay_date = self._adjuster.adjust_date(
                offset_pay_date_val, pay_adjustments
            )
        else:
            adjusted_pay_date = offset_pay_date_val

        return adjusted_pay_date

    def _extract_fixed_payment_amount(
        self, calc_period_group: List[CalculationPeriod]
    ) -> Tuple[Decimal | None, List[CalculationPeriod]]:
        """計算期間グループ内からスタブなどの固定支払額（Money）が設定されているものを抽出し、支払対象の計算期間グループと共に返します。"""
        fixed_pay_amount = None
        calculation_period_group = calc_period_group
        for c in calc_period_group:
            if hasattr(c, "_stub_amount") and c._stub_amount is not None:
                fixed_pay_amount = c._stub_amount.amount
                calculation_period_group = []
                break
        return fixed_pay_amount, calculation_period_group
