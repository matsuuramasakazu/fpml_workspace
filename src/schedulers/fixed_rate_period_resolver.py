from datetime import date
from decimal import Decimal


class FixedRatePeriodResolver:
    """計算期間に対する固定金利の解決を担当するクラス。"""

    def __init__(self, fixed_rate_resolver):
        """
        Args:
            fixed_rate_resolver: 金利の解決を行うリゾルバーインスタンス
        """
        self._fixed_rate_resolver = fixed_rate_resolver

    def resolve_rate(self, ustart: date) -> Decimal | None:
        """指定された調整前開始日に基づき固定金利を解決します。"""
        if self._fixed_rate_resolver is None:
            return None
        return self._fixed_rate_resolver.resolve(ustart)
