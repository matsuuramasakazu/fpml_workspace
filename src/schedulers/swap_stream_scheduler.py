from typing import List

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    InterestRateStream,
    PaymentCalculationPeriod,
    PrincipalExchange,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.calculation_period_scheduler import CalculationPeriodScheduler
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.payment_period_scheduler import PaymentPeriodScheduler
from src.schedulers.reference_resolver import ReferenceResolver


class SwapStreamScheduler:
    """FpML の InterestRateStream から支払計算期間のスケジュール全体を展開するオーケストレーター。"""

    def __init__(self, calendar: BusinessCalendar, resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            resolver: FpMLドキュメント内のhref参照を解決するReferenceResolverインスタンス
        """
        self._calculation_period_scheduler = CalculationPeriodScheduler(
            calendar, resolver
        )
        self._payment_period_scheduler = PaymentPeriodScheduler(calendar, resolver)
        self._adjuster = DateAdjuster(calendar, resolver)
        self._resolver = resolver

    def generate_payment_periods(
        self, stream: InterestRateStream
    ) -> List[PaymentCalculationPeriod]:
        """InterestRateStream パラメータから PaymentCalculationPeriod スケジュールを展開します。

        Args:
            stream: FpML の金利ストリーム（レグ）情報

        Returns:
            展開・調整された支払計算期間（PaymentCalculationPeriod）のリスト
        """
        # 1. 計算期間スケジュールの生成 (内部で FixingScheduler も処理)
        calc_periods = self._calculation_period_scheduler.generate_periods(stream)

        # 2. 支払期間への集約と休日調整
        return self._payment_period_scheduler.aggregate_periods(calc_periods, stream)

    def generate_principal_exchanges(
        self, stream: InterestRateStream
    ) -> List[PrincipalExchange]:
        """InterestRateStream パラメータから元本交換スケジュールを展開します。

        Args:
            stream: FpML の金利ストリーム（レグ）情報

        Returns:
            元本交換（PrincipalExchange）のリスト
        """
        if stream.principal_exchanges is None:
            return []

        # 元本 (Notional) の取得
        calc_params = stream.calculation_period_amount.calculation
        notional_schedule = calc_params.notional_schedule
        if notional_schedule.notional_step_schedule is not None:
            notional = notional_schedule.notional_step_schedule.initial_value
        else:
            resolved_notional = self._resolver.resolve(
                notional_schedule.notional_step_parameters_reference
            )
            notional = resolved_notional.initial_value

        exchanges = []
        calc_dates = stream.calculation_period_dates

        # 初期元本交換 (Initial Exchange)
        if stream.principal_exchanges.initial_exchange:
            eff_date = calc_dates.effective_date
            unadjusted_date = eff_date.unadjusted_date.value.to_date()
            adjusted_date = self._adjuster.adjust_date(
                unadjusted_date, eff_date.date_adjustments
            )
            exchanges.append(
                PrincipalExchange(
                    unadjusted_principal_exchange_date=XmlDate(
                        unadjusted_date.year, unadjusted_date.month, unadjusted_date.day
                    ),
                    adjusted_principal_exchange_date=XmlDate(
                        adjusted_date.year, adjusted_date.month, adjusted_date.day
                    ),
                    principal_exchange_amount=-notional,
                )
            )

        # 最終元本交換 (Final Exchange)
        if stream.principal_exchanges.final_exchange:
            term_date = calc_dates.termination_date
            unadjusted_date = term_date.unadjusted_date.value.to_date()
            adjusted_date = self._adjuster.adjust_date(
                unadjusted_date, term_date.date_adjustments
            )
            exchanges.append(
                PrincipalExchange(
                    unadjusted_principal_exchange_date=XmlDate(
                        unadjusted_date.year, unadjusted_date.month, unadjusted_date.day
                    ),
                    adjusted_principal_exchange_date=XmlDate(
                        adjusted_date.year, adjusted_date.month, adjusted_date.day
                    ),
                    principal_exchange_amount=notional,
                )
            )

        return exchanges
