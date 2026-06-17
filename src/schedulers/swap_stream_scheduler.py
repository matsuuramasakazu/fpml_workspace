from typing import List

from fpml.confirmation import InterestRateStream, PaymentCalculationPeriod
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.calculation_period_scheduler import CalculationPeriodScheduler
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
