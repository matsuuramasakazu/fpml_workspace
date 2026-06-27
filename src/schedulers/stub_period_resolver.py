from datetime import date
from decimal import Decimal
from typing import Any, Tuple

from fpml.confirmation import InterestRateStream


class StubPeriodResolver:
    """計算期間がスタブ（端数期間）である場合の判定および金利・金額の解決を担当するクラス。"""

    def is_stub(self, ustart: date, uend: date, calc_dates: Any) -> Tuple[bool, bool]:
        """指定された期間が初期スタブまたは期末スタブであるかを判定します。"""
        first_reg_calc_date_val = None
        if calc_dates.first_regular_period_start_date is not None:
            first_reg_calc_date_val = (
                calc_dates.first_regular_period_start_date.to_date()
            )
        elif calc_dates.first_compounding_period_end_date is not None:
            first_reg_calc_date_val = (
                calc_dates.first_compounding_period_end_date.to_date()
            )

        last_reg_calc_date_val = None
        if calc_dates.last_regular_period_end_date is not None:
            last_reg_calc_date_val = calc_dates.last_regular_period_end_date.to_date()

        is_initial_stub = (
            first_reg_calc_date_val is not None and ustart < first_reg_calc_date_val
        )
        is_final_stub = (
            last_reg_calc_date_val is not None and uend > last_reg_calc_date_val
        )
        return is_initial_stub, is_final_stub

    def resolve_stub_overrides(
        self,
        is_initial_stub: bool,
        is_final_stub: bool,
        stream: InterestRateStream,
    ) -> Tuple[Decimal | None, Any | None]:
        """スタブ定義に基づき、通常金利の上書き用のスタブ金利(stubRate)またはスタブ金額(stubAmount)を解決します。

        Returns:
            Tuple[stub_rate, stub_amount]
        """
        stub_amount_info = stream.stub_calculation_period_amount
        if stub_amount_info is None:
            return None, None

        stub_info = None
        if is_initial_stub and stub_amount_info.initial_stub is not None:
            stub_info = stub_amount_info.initial_stub
        elif is_final_stub and stub_amount_info.final_stub is not None:
            stub_info = stub_amount_info.final_stub

        if stub_info is None:
            return None, None

        stub_rate = stub_info.stub_rate
        stub_amount = stub_info.stub_amount
        return stub_rate, stub_amount
