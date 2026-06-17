from datetime import date
from decimal import Decimal
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import DataDocument
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.swap_stream_scheduler import SwapStreamScheduler


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
    scheduler = SwapStreamScheduler(calendar, resolver)

    exchanges = scheduler.generate_principal_exchanges(stream)
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
    scheduler = SwapStreamScheduler(calendar, resolver)

    exchanges = scheduler.generate_principal_exchanges(usd_stream)

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
    jpy_exchanges = scheduler.generate_principal_exchanges(jpy_stream)

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
