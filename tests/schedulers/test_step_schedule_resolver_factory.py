from datetime import date
from decimal import Decimal
from pathlib import Path

from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory
from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import DataDocument
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.reference_resolver import ReferenceResolver


def test_step_schedule_resolver_factory_creation():
    """InterestRateStreamからStepScheduleResolverFactoryが各リゾルバーを正しく生成することを検証"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 1. 浮動レッグストリームを取得
    floating_stream = doc.trade[0].swap.swap_stream[0]
    ref_resolver = ReferenceResolver(doc)

    # Factoryの生成
    factory = StepScheduleResolverFactory(floating_stream, ref_resolver)

    # 各リゾルバーが正しく生成されていること
    assert factory.notional_resolver is not None
    assert factory.fixed_rate_resolver is not None
    assert factory.spread_resolver is not None
    assert factory.multiplier_resolver is not None

    # 想定元本の解決 (ird-ex02は初期元本50,000,000.00)
    assert factory.notional_resolver.resolve(date(1995, 1, 16)) == Decimal(
        "50000000.00"
    )
    # 元本削減ステップ反映 (1995-12-14に40,000,000.00へ)
    assert factory.notional_resolver.resolve(date(1995, 12, 14)) == Decimal(
        "40000000.00"
    )

    # 浮動レッグなので、固定金利はNone
    assert factory.fixed_rate_resolver.resolve(date(1995, 1, 16)) is None


def test_step_schedule_resolver_factory_with_empty_schedules():
    """各種スケジュールがNoneの場合でも適切にNoneを解決するリゾルバーを生成することを検証"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 固定レッグストリームを取得 (ird-ex02の固定レッグはスプレッドやマルチプライヤーなし)
    fixed_stream = doc.trade[0].swap.swap_stream[1]
    ref_resolver = ReferenceResolver(doc)

    factory = StepScheduleResolverFactory(fixed_stream, ref_resolver)

    # 各リゾルバーが存在すること
    assert factory.notional_resolver is not None
    assert factory.fixed_rate_resolver is not None
    assert factory.spread_resolver is not None
    assert factory.multiplier_resolver is not None

    # 固定金利は初期値0.06
    assert factory.fixed_rate_resolver.resolve(date(1995, 1, 16)) == Decimal("0.06")

    # 固定レッグなので、スプレッドおよびマルチプライヤーはNone解決
    assert factory.spread_resolver.resolve(date(1995, 1, 16)) is None
    assert factory.multiplier_resolver.resolve(date(1995, 1, 16)) is None
