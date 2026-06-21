from datetime import date
from decimal import Decimal
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import DataDocument
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.principal_exchange_scheduler import PrincipalExchangeScheduler
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


def test_generate_principal_exchanges_no_exchanges():
    """元本交換の指定がないストリームで空リストが返ることをテスト"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)
    stream = doc.trade[0].swap.swap_stream[0]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = PrincipalExchangeScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(stream, resolver)

    exchanges = scheduler.generate_exchanges(stream, step_schedule_resolver_factory)
    assert exchanges == []


def test_generate_principal_exchanges_with_exchanges():
    """ird-ex052 のクロス通貨スワップで元本交換スケジュールが生成されることをテスト"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex052-xccy-swap-OIS.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 最初のストリーム (USD, Floating)
    usd_stream = doc.trade[0].swap.swap_stream[0]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = PrincipalExchangeScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(usd_stream, resolver)

    exchanges = scheduler.generate_exchanges(usd_stream, step_schedule_resolver_factory)

    # 期待される元本交換は2つ (初期・最終)
    assert len(exchanges) == 2

    # 初期元本交換
    init_exch = exchanges[0]
    assert init_exch.unadjusted_principal_exchange_date.to_date() == date(2018, 9, 10)
    assert init_exch.adjusted_principal_exchange_date.to_date() == date(2018, 9, 10)
    assert init_exch.principal_exchange_amount == Decimal("-121700000")

    # 最終元本交換
    final_exch = exchanges[1]
    assert final_exch.unadjusted_principal_exchange_date.to_date() == date(2023, 9, 10)
    # 2023-09-10 (日) -> 2023-09-11 (月) (MODFOLLOWING, GBLO/USNY/JPTO)
    assert final_exch.adjusted_principal_exchange_date.to_date() == date(2023, 9, 11)
    assert final_exch.principal_exchange_amount == Decimal("121700000")

    # 2番目のストリーム (JPY, Fixed)
    jpy_stream = doc.trade[0].swap.swap_stream[1]
    jpy_step_schedule_resolver_factory = StepScheduleResolverFactory(
        jpy_stream, resolver
    )
    jpy_exchanges = scheduler.generate_exchanges(
        jpy_stream, jpy_step_schedule_resolver_factory
    )

    assert len(jpy_exchanges) == 2

    # JPY 初期元本交換
    jpy_init = jpy_exchanges[0]
    assert jpy_init.unadjusted_principal_exchange_date.to_date() == date(2018, 9, 10)
    assert jpy_init.adjusted_principal_exchange_date.to_date() == date(2018, 9, 10)
    assert jpy_init.principal_exchange_amount == Decimal("-100500000")

    # JPY 最終元本交換
    jpy_final = jpy_exchanges[1]
    assert jpy_final.unadjusted_principal_exchange_date.to_date() == date(2023, 9, 10)
    assert jpy_final.adjusted_principal_exchange_date.to_date() == date(2023, 9, 11)
    assert jpy_final.principal_exchange_amount == Decimal("100500000")


def test_generate_principal_exchanges_fx_linked_notional():
    """ird-ex25 の元本リセット型レグ（initialValueなし）で元本交換スケジュールが生成され、金額が None になることをテスト"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex25-fxnotional-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 2番目のストリーム (USD, Floating with FX-Linked Notional)
    usd_stream = doc.trade[0].swap.swap_stream[1]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = PrincipalExchangeScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(usd_stream, resolver)

    exchanges = scheduler.generate_exchanges(usd_stream, step_schedule_resolver_factory)

    # 生成されるのは初期と最終の2つ
    assert len(exchanges) == 2

    # 初期元本交換
    init_exch = exchanges[0]
    assert init_exch.unadjusted_principal_exchange_date.to_date() == date(2006, 1, 11)
    assert init_exch.adjusted_principal_exchange_date.to_date() == date(2006, 1, 11)
    assert init_exch.principal_exchange_amount is None

    # 最終元本交換
    final_exch = exchanges[1]
    assert final_exch.unadjusted_principal_exchange_date.to_date() == date(2011, 1, 11)
    assert final_exch.adjusted_principal_exchange_date.to_date() == date(2011, 1, 11)
    assert final_exch.principal_exchange_amount is None


def test_generate_principal_exchanges_notional_amortization():
    """Test PrincipalExchangeScheduler principal exchange generation for notional amortization schedule using ird-ex02."""
    from decimal import Decimal
    from pathlib import Path

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument, PrincipalExchanges

    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 浮動レッグストリームを取得し、元本交換を設定する
    floating_stream = doc.trade[0].swap.swap_stream[0]
    floating_stream.principal_exchanges = PrincipalExchanges(
        initial_exchange=True,
        final_exchange=True,
        intermediate_exchange=False,
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = PrincipalExchangeScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    exchanges = scheduler.generate_exchanges(
        floating_stream, step_schedule_resolver_factory
    )

    assert len(exchanges) == 2

    # 初期元本交換: 開始日 1995-01-16 時点の元本 (50,000,000.00)
    # 元本交換量はマイナスになるため、-50,000,000.00
    assert exchanges[0].unadjusted_principal_exchange_date.to_date() == date(
        1995, 1, 16
    )
    assert exchanges[0].principal_exchange_amount == Decimal("-50000000.00")

    # 最終元本交換: 終了日 1999-12-14 時点の元本 (10,000,000.00)
    # 元本削減後の最終元本 10,000,000.00
    assert exchanges[1].unadjusted_principal_exchange_date.to_date() == date(
        1999, 12, 14
    )
    assert exchanges[1].principal_exchange_amount == Decimal("10000000.00")


def test_generate_principal_exchanges_intermediate_amortization():
    """Test PrincipalExchangeScheduler principal exchange generation for notional amortization with intermediate exchange."""
    from decimal import Decimal
    from pathlib import Path

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument, PrincipalExchanges

    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 浮動レッグストリームを取得し、中間元本交換を有効にする
    floating_stream = doc.trade[0].swap.swap_stream[0]
    floating_stream.principal_exchanges = PrincipalExchanges(
        initial_exchange=True,
        final_exchange=True,
        intermediate_exchange=True,
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = PrincipalExchangeScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    exchanges = scheduler.generate_exchanges(
        floating_stream, step_schedule_resolver_factory
    )

    # 初期 (1) + 中間 (4) + 最終 (1) = 6 個の元本交換が発生
    assert len(exchanges) == 6

    # 1. 初期元本交換: 1995-01-16
    assert exchanges[0].unadjusted_principal_exchange_date.to_date() == date(
        1995, 1, 16
    )
    assert exchanges[0].adjusted_principal_exchange_date.to_date() == date(1995, 1, 16)
    assert exchanges[0].principal_exchange_amount == Decimal("-50000000.00")

    # 2. 中間元本交換1: 1995-12-14 (木)
    assert exchanges[1].unadjusted_principal_exchange_date.to_date() == date(
        1995, 12, 14
    )
    assert exchanges[1].adjusted_principal_exchange_date.to_date() == date(1995, 12, 14)
    assert exchanges[1].principal_exchange_amount == Decimal("10000000.00")

    # 3. 中間元本交換2: 1996-12-14 (土) -> 1996-12-16 (月) に調整
    assert exchanges[2].unadjusted_principal_exchange_date.to_date() == date(
        1996, 12, 14
    )
    assert exchanges[2].adjusted_principal_exchange_date.to_date() == date(1996, 12, 16)
    assert exchanges[2].principal_exchange_amount == Decimal("10000000.00")

    # 4. 中間元本交換3: 1997-12-14 (日) -> 1997-12-15 (月) に調整
    assert exchanges[3].unadjusted_principal_exchange_date.to_date() == date(
        1997, 12, 14
    )
    assert exchanges[3].adjusted_principal_exchange_date.to_date() == date(1997, 12, 15)
    assert exchanges[3].principal_exchange_amount == Decimal("10000000.00")

    # 5. 中間元本交換4: 1998-12-14 (月)
    assert exchanges[4].unadjusted_principal_exchange_date.to_date() == date(
        1998, 12, 14
    )
    assert exchanges[4].adjusted_principal_exchange_date.to_date() == date(1998, 12, 14)
    assert exchanges[4].principal_exchange_amount == Decimal("10000000.00")

    # 6. 最終元本交換: 1999-12-14 (火)
    assert exchanges[5].unadjusted_principal_exchange_date.to_date() == date(
        1999, 12, 14
    )
    assert exchanges[5].adjusted_principal_exchange_date.to_date() == date(1999, 12, 14)
    assert exchanges[5].principal_exchange_amount == Decimal("10000000.00")
