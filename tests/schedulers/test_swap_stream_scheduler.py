from datetime import date

from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.swap_stream_scheduler import SwapStreamScheduler


def test_swap_stream_scheduler_vanilla_swap_fixed_leg():
    """Test SwapStreamScheduler schedule generation for fixed leg using ird-ex01."""
    from decimal import Decimal
    from pathlib import Path

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    fixed_stream = doc.trade[0].swap.swap_stream[1]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = SwapStreamScheduler(calendar, resolver)

    periods = scheduler.generate_payment_periods(fixed_stream)

    # 5年物、年1回支払
    assert len(periods) == 5

    # 各支払期間を検証
    expected_payment_dates = [
        date(1995, 12, 14),
        date(1996, 12, 16),  # 14日土曜 -> 16日月曜調整 (MODFOLLOWING DEFR)
        date(1997, 12, 15),  # 14日日曜 -> 15日月曜調整
        date(1998, 12, 14),
        date(1999, 12, 14),
    ]

    for i, p in enumerate(periods):
        assert p.adjusted_payment_date.to_date() == expected_payment_dates[i]
        assert len(p.calculation_period) == 1
        calc = p.calculation_period[0]
        # 固定金利レグの固定利率検証
        assert calc.fixed_rate == Decimal("0.06")
        assert calc.notional_amount == Decimal("50000000.00")


def test_swap_stream_scheduler_vanilla_swap_floating_leg():
    """Test SwapStreamScheduler schedule generation for floating leg using ird-ex01."""
    from decimal import Decimal
    from pathlib import Path

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = SwapStreamScheduler(calendar, resolver)

    periods = scheduler.generate_payment_periods(floating_stream)

    # 5年物、半年1回支払 -> 10期間
    assert len(periods) == 10

    # 第1期を検証
    p1 = periods[0]
    # 1994-12-14 to 1995-06-14 (182 days, ACT/360)
    assert len(p1.calculation_period) == 1
    calc1 = p1.calculation_period[0]
    assert calc1.adjusted_start_date.to_date() == date(1994, 12, 14)
    assert calc1.adjusted_end_date.to_date() == date(1995, 6, 14)
    assert calc1.calculation_period_number_of_days == 182

    # Day count fraction: 182 / 360 = 0.505556
    expected_fraction = Decimal("182") / Decimal("360")
    assert round(calc1.day_count_year_fraction, 6) == round(expected_fraction, 6)

    # Fixing スケジュールの検証 (rateObservation)
    floating_def = calc1.floating_rate_definition
    assert floating_def is not None
    assert len(floating_def.rate_observation) == 1
    obs1 = floating_def.rate_observation[0]

    # resetDate = adjustedStartDate of period (1994-12-14)
    assert obs1.reset_date.to_date() == date(1994, 12, 14)
    # adjustedFixingDate = resetDate - 2 business days (GBLO) -> 1994-12-12
    assert obs1.adjusted_fixing_date.to_date() == date(1994, 12, 12)


def test_swap_stream_scheduler_fx_linked_notional_leg():
    """Test SwapStreamScheduler schedule generation for FX-linked notional leg using ird-ex25."""
    from pathlib import Path

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

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
    scheduler = SwapStreamScheduler(calendar, resolver)

    periods = scheduler.generate_payment_periods(usd_stream)

    # 5年物、3ヶ月に1回支払 -> 20期
    assert len(periods) == 20

    # 1期目の検証 (2006-01-11 から 2006-04-11)
    p1 = periods[0]
    assert len(p1.calculation_period) == 1
    calc1 = p1.calculation_period[0]
    assert calc1.adjusted_start_date.to_date() == date(2006, 1, 11)
    assert calc1.adjusted_end_date.to_date() == date(2006, 4, 11)
    assert calc1.notional_amount is None
    assert calc1.fx_linked_notional_amount is not None
    assert calc1.fx_linked_notional_amount.reset_date.to_date() == date(2006, 1, 11)
    assert (
        calc1.fx_linked_notional_amount.adjusted_fx_spot_fixing_date.to_date()
        == date(2006, 1, 9)
    )

    # 2期目の検証 (2006-04-11 から 2006-07-11)
    p2 = periods[1]
    assert len(p2.calculation_period) == 1
    calc2 = p2.calculation_period[0]
    assert calc2.adjusted_start_date.to_date() == date(2006, 4, 11)
    assert calc2.adjusted_end_date.to_date() == date(2006, 7, 11)
    assert calc2.notional_amount is None
    assert calc2.fx_linked_notional_amount is not None
    assert calc2.fx_linked_notional_amount.reset_date.to_date() == date(2006, 4, 11)
    assert (
        calc2.fx_linked_notional_amount.adjusted_fx_spot_fixing_date.to_date()
        == date(2006, 4, 7)
    )


def test_generate_principal_exchanges_notional_amortization():
    """Test SwapStreamScheduler principal exchange generation for notional amortization schedule using ird-ex02."""
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
    scheduler = SwapStreamScheduler(calendar, resolver)

    exchanges = scheduler.generate_principal_exchanges(floating_stream)

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
    """Test SwapStreamScheduler principal exchange generation for notional amortization with intermediate exchange."""
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
    scheduler = SwapStreamScheduler(calendar, resolver)

    exchanges = scheduler.generate_principal_exchanges(floating_stream)

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
