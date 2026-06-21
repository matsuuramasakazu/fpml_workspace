from datetime import date
from decimal import Decimal

from src.schedulers.step_schedule_resolver import StepScheduleResolver
from xsdata.models.datatype import XmlDate

from fpml.confirmation import Schedule, Step


def test_resolve_none_schedule():
    """None が渡された場合に None が返されることをテスト"""
    resolver = StepScheduleResolver(None)
    assert resolver.resolve(date(2026, 6, 1)) is None


def test_resolve_initial_value_only():
    """ステップがないスケジュールで常に初期値が解決されることをテスト"""
    schedule = Schedule(initial_value=Decimal("0.05"))
    resolver = StepScheduleResolver(schedule)

    assert resolver.resolve(date(2026, 1, 1)) == Decimal("0.05")
    assert resolver.resolve(date(2026, 12, 31)) == Decimal("0.05")


def test_resolve_with_steps():
    """ステップが存在するスケジュールで、日付遷移に伴って正しい値が解決されることをテスト"""
    # 日付はソートされていない状態で定義
    schedule = Schedule(
        initial_value=Decimal("0.05"),
        step=[
            Step(step_date=XmlDate(2026, 12, 1), step_value=Decimal("0.07")),
            Step(step_date=XmlDate(2026, 6, 1), step_value=Decimal("0.06")),
        ],
    )
    resolver = StepScheduleResolver(schedule)

    # 1. 第一ステップの前 -> 初期値
    assert resolver.resolve(date(2026, 5, 31)) == Decimal("0.05")

    # 2. 第一ステップの適用日 -> 新しい値
    assert resolver.resolve(date(2026, 6, 1)) == Decimal("0.06")

    # 3. 第一ステップと第二ステップの間 -> 第一ステップの値
    assert resolver.resolve(date(2026, 11, 30)) == Decimal("0.06")

    # 4. 第二ステップの適用日 -> 新しい値
    assert resolver.resolve(date(2026, 12, 1)) == Decimal("0.07")

    # 5. 第二ステップの後 -> 第二ステップの値
    assert resolver.resolve(date(2027, 1, 1)) == Decimal("0.07")
