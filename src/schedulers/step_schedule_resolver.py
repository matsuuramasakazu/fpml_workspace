from datetime import date
from decimal import Decimal

from fpml.confirmation import Schedule


class StepScheduleResolver:
    """FpML の Schedule オブジェクトから特定の日付時点の値を解決するクラス。

    初期値（initial_value）と、日付によって変化するステップ（Step）のペア群から、
    任意の基準日時点で有効な値を算出します。
    """

    def __init__(self, schedule: Schedule | None):
        """
        Args:
            schedule: 解決対象となる FpML Schedule オブジェクト、または None
        """
        self._initial_value = schedule.initial_value if schedule is not None else None

        # ステップの日付順ソートを初期化時に一度だけ実行してキャッシュ（パフォーマンス最適化）
        steps = getattr(schedule, "step", []) if schedule is not None else []
        self._sorted_steps = (
            sorted(steps, key=lambda s: s.step_date.to_date()) if steps else []
        )

    def resolve(self, ref_date: date) -> Decimal | None:
        """指定された基準日（ref_date）時点のスケジュール値を解決します。

        Args:
            ref_date: 解決基準日

        Returns:
            基準日時点で有効な Decimal 値。スケジュールが存在しない場合は None。
        """
        if self._initial_value is None and not self._sorted_steps:
            return None

        resolved_value = self._initial_value
        for step in self._sorted_steps:
            if step.step_date.to_date() <= ref_date:
                resolved_value = step.step_value
            else:
                # ソート済みのため、基準日を超えるステップに達した時点でループを終了
                break

        return resolved_value
