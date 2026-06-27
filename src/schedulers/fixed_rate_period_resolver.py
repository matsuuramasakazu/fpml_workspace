from datetime import date
from decimal import Decimal

from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


class FixedRatePeriodResolver:
    """計算期間に対する固定金利の解決を担当するクラス。"""

    def resolve_rate(
        self,
        ustart: date,
        step_schedule_resolver_factory: StepScheduleResolverFactory,
    ) -> Decimal | None:
        """指定された調整前開始日に基づき固定金利を解決します。"""
        if step_schedule_resolver_factory.fixed_rate_resolver is None:
            return None
        return step_schedule_resolver_factory.fixed_rate_resolver.resolve(ustart)
