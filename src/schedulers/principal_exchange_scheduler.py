from datetime import date
from decimal import Decimal
from typing import List

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    InterestRateStream,
    PrincipalExchange,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver import StepScheduleResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


class PrincipalExchangeScheduler:
    """InterestRateStream パラメータから元本交換スケジュールを展開するクラス。"""

    def __init__(self, calendar: BusinessCalendar, ref_resolver: ReferenceResolver):
        """
        Args:
            calendar: 営業日判定・日付調整を行うBusinessCalendarインスタンス
            ref_resolver: FpMLドキュメント内のhref参照を解決するReferenceResolverインスタンス
        """
        self._adjuster = DateAdjuster(calendar, ref_resolver)
        self._ref_resolver = ref_resolver

    def generate_exchanges(
        self,
        stream: InterestRateStream,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> List[PrincipalExchange]:
        """InterestRateStream パラメータから元本交換スケジュールを展開します。

        Args:
            stream: FpML の金利ストリーム（レグ）情報
            step_schedule_resolver_factory: 各種ステップスケジュールリゾルバーを保持するFactory

        Returns:
            元本交換（PrincipalExchange）のリスト
        """
        if stream.principal_exchanges is None:
            return []

        # 元本 (Notional) およびスケジュールの取得
        calc_params = stream.calculation_period_amount.calculation
        fx_linked_notional_schedule = calc_params.fx_linked_notional_schedule

        exchanges = []

        # 1. 初期元本交換 (Initial Exchange)
        if stream.principal_exchanges.initial_exchange:
            init_exch = self._generate_initial_exchange(
                stream,
                calc_params,
                fx_linked_notional_schedule,
                step_schedule_resolver_factory,
            )
            if init_exch is not None:
                exchanges.append(init_exch)

        # 2. 中間元本交換 (Intermediate Exchange)
        if stream.principal_exchanges.intermediate_exchange:
            exchanges.extend(
                self._generate_intermediate_exchanges(
                    stream, calc_params, fx_linked_notional_schedule
                )
            )

        # 3. 最終元本交換 (Final Exchange)
        if stream.principal_exchanges.final_exchange:
            final_exch = self._generate_final_exchange(
                stream,
                calc_params,
                fx_linked_notional_schedule,
                step_schedule_resolver_factory,
            )
            if final_exch is not None:
                exchanges.append(final_exch)

        # 日付順（unadjusted）にソートして返却
        exchanges.sort(key=lambda x: x.unadjusted_principal_exchange_date.to_date())
        return exchanges

    def _generate_initial_exchange(
        self,
        stream: InterestRateStream,
        calc_params,
        fx_linked_notional_schedule,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> PrincipalExchange | None:
        """初期元本交換 (Initial Exchange) を生成します。"""
        calc_dates = stream.calculation_period_dates
        eff_date = calc_dates.effective_date
        unadjusted_date = eff_date.unadjusted_date.value.to_date()
        adjusted_date = self._adjuster.adjust_date(
            unadjusted_date, eff_date.date_adjustments
        )

        if fx_linked_notional_schedule is not None:
            notional = fx_linked_notional_schedule.initial_value
        else:
            notional = step_schedule_resolver_factory.notional_resolver.resolve(
                unadjusted_date
            )

        return PrincipalExchange(
            unadjusted_principal_exchange_date=XmlDate(
                unadjusted_date.year, unadjusted_date.month, unadjusted_date.day
            ),
            adjusted_principal_exchange_date=XmlDate(
                adjusted_date.year, adjusted_date.month, adjusted_date.day
            ),
            principal_exchange_amount=-notional if notional is not None else None,
        )

    def _generate_intermediate_exchanges(
        self, stream: InterestRateStream, calc_params, fx_linked_notional_schedule
    ) -> List[PrincipalExchange]:
        """中間元本交換 (Intermediate Exchange) スケジュールを生成します。"""
        if fx_linked_notional_schedule is not None:
            # FX連動元本スワップの場合は中間元本交換が発生しない（または対象外）
            return []

        notional_schedule = calc_params.notional_schedule
        if notional_schedule is None:
            return []

        step_schedule = None
        if notional_schedule.notional_step_schedule is not None:
            step_schedule = notional_schedule.notional_step_schedule
        elif notional_schedule.notional_step_parameters_reference is not None:
            step_schedule = self._ref_resolver.resolve(
                notional_schedule.notional_step_parameters_reference
            )

        if step_schedule is None:
            return []

        initial_value = step_schedule.initial_value
        steps = getattr(step_schedule, "step", [])
        if not steps:
            return []

        exchanges = []
        sorted_steps = sorted(steps, key=lambda s: s.step_date.to_date())
        prev_value = initial_value

        for step in sorted_steps:
            step_date = step.step_date.to_date()
            pay_adjustments = None
            if stream.payment_dates is not None:
                pay_adjustments = stream.payment_dates.payment_dates_adjustments

            adjusted_date = self._adjuster.adjust_date(step_date, pay_adjustments)
            step_value = step.step_value
            diff_amount = prev_value - step_value

            exchanges.append(
                PrincipalExchange(
                    unadjusted_principal_exchange_date=XmlDate(
                        step_date.year,
                        step_date.month,
                        step_date.day,
                    ),
                    adjusted_principal_exchange_date=XmlDate(
                        adjusted_date.year,
                        adjusted_date.month,
                        adjusted_date.day,
                    ),
                    principal_exchange_amount=diff_amount,
                )
            )
            prev_value = step_value

        return exchanges

    def _generate_final_exchange(
        self,
        stream: InterestRateStream,
        calc_params,
        fx_linked_notional_schedule,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> PrincipalExchange | None:
        """最終元本交換 (Final Exchange) を生成します。"""
        calc_dates = stream.calculation_period_dates
        term_date = calc_dates.termination_date
        unadjusted_date = term_date.unadjusted_date.value.to_date()
        adjusted_date = self._adjuster.adjust_date(
            unadjusted_date, term_date.date_adjustments
        )

        if fx_linked_notional_schedule is not None:
            notional = fx_linked_notional_schedule.initial_value
        else:
            notional = step_schedule_resolver_factory.notional_resolver.resolve(
                unadjusted_date
            )

        return PrincipalExchange(
            unadjusted_principal_exchange_date=XmlDate(
                unadjusted_date.year, unadjusted_date.month, unadjusted_date.day
            ),
            adjusted_principal_exchange_date=XmlDate(
                adjusted_date.year, adjusted_date.month, adjusted_date.day
            ),
            principal_exchange_amount=notional if notional is not None else None,
        )
