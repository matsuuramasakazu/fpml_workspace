from datetime import date
from decimal import Decimal
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import DataDocument
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.calculation_period_scheduler import CalculationPeriodScheduler
from src.schedulers.reference_resolver import ReferenceResolver


def test_generate_periods_initial_stub_interpolation():
    """Test CalculationPeriodScheduler for initial stub with linear interpolation using ird-ex02."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)

    periods = scheduler.generate_periods(floating_stream)

    # ird-ex02 has 10 calculation periods
    assert len(periods) == 10

    # First period is the initial stub (1995-01-16 to 1995-06-14)
    p1 = periods[0]
    assert p1.adjusted_start_date.to_date() == date(1995, 1, 16)
    assert p1.adjusted_end_date.to_date() == date(1995, 6, 14)
    assert (
        p1.calculation_period_number_of_days == 149
    )  # 1995-01-16 to 1995-06-14 is 149 days

    # Fixing validation for the stub period
    floating_def = p1.floating_rate_definition
    assert floating_def is not None
    assert len(floating_def.rate_observation) == 1
    obs1 = floating_def.rate_observation[0]
    assert obs1.reset_date.to_date() == date(1995, 1, 16)
    assert obs1.adjusted_fixing_date.to_date() == date(1995, 1, 12)

    # Second period is a regular period (1995-06-14 to 1995-12-14)
    p2 = periods[1]
    assert p2.adjusted_start_date.to_date() == date(1995, 6, 14)
    assert p2.adjusted_end_date.to_date() == date(1995, 12, 14)


def test_generate_periods_initial_stub_rate():
    """Test CalculationPeriodScheduler for initial stub with stubRate (fixed rate)."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]

    # stubCalculationPeriodAmount を上書きし、stub_rate = 0.035 (3.5%) を設定
    from fpml.confirmation import Stub

    floating_stream.stub_calculation_period_amount.initial_stub = Stub(
        stub_rate=Decimal("0.035")
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)

    periods = scheduler.generate_periods(floating_stream)

    p1 = periods[0]
    assert p1.adjusted_start_date.to_date() == date(1995, 1, 16)
    assert p1.adjusted_end_date.to_date() == date(1995, 6, 14)
    # fixed_rate が設定され、floating_rate_definition は None
    assert p1.fixed_rate == Decimal("0.035")
    assert p1.floating_rate_definition is None

    # レギュラー期間は通常の浮動金利
    p2 = periods[1]
    assert p2.fixed_rate is None
    assert p2.floating_rate_definition is not None


def test_generate_periods_initial_stub_amount():
    """Test SwapStreamScheduler for initial stub with stubAmount (fixed payment amount)."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]

    # stubCalculationPeriodAmount を上書きし、stub_amount = 123456.78 を設定
    from fpml.confirmation import Money, Stub

    floating_stream.stub_calculation_period_amount.initial_stub = Stub(
        stub_amount=Money(currency="EUR", amount=Decimal("123456.78"))
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)

    from src.schedulers.swap_stream_scheduler import SwapStreamScheduler

    scheduler = SwapStreamScheduler(calendar, resolver)

    periods = scheduler.generate_payment_periods(floating_stream)

    p1 = periods[0]
    assert p1.adjusted_payment_date.to_date() == date(1995, 6, 14)
    # fixed_payment_amount が設定され、calculation_period は空リストになっていること
    assert p1.fixed_payment_amount == Decimal("123456.78")
    assert len(p1.calculation_period) == 0

    # 2期目は通常通り calculation_period が設定されていること
    p2 = periods[1]
    assert p2.fixed_payment_amount is None
    assert len(p2.calculation_period) == 1
    assert p2.calculation_period[0].fixed_rate is None
    assert p2.calculation_period[0].floating_rate_definition is not None


def test_generate_periods_final_stub():
    """Test CalculationPeriodScheduler for final stub (backward date generation & stubRate)."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]
    calc_dates = floating_stream.calculation_period_dates

    # 1. Final Stub 用に日付定義を変更
    calc_dates.first_regular_period_start_date = None
    from xsdata.models.datatype import XmlDate as ModelXmlDate

    calc_dates.last_regular_period_end_date = ModelXmlDate(1999, 7, 14)

    # 2. stubCalculationPeriodAmount を上書きし、final_stub に stub_rate = 0.045 を設定
    from fpml.confirmation import Stub

    floating_stream.stub_calculation_period_amount.final_stub = Stub(
        stub_rate=Decimal("0.045")
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)

    periods = scheduler.generate_periods(floating_stream)

    # 頻度 6M で 1995-01-16 から 1999-07-14 まで 9 期間 + 最終スタブ 1 期間 = 計 10 期間
    assert len(periods) == 10

    # 1期目 (レギュラー期間: 1995-01-16 to 1995-07-14)
    p1 = periods[0]
    assert p1.unadjusted_start_date.to_date() == date(1995, 1, 16)
    assert p1.unadjusted_end_date.to_date() == date(1995, 7, 14)
    assert p1.fixed_rate is None

    # 9期目 (レギュラー期間の最後: 1999-01-14 to 1999-07-14)
    p9 = periods[8]
    assert p9.unadjusted_start_date.to_date() == date(1999, 1, 14)
    assert p9.unadjusted_end_date.to_date() == date(1999, 7, 14)
    assert p9.fixed_rate is None

    # 10期目 (Final Stub 期間: 1999-07-14 to 1999-12-14)
    p10 = periods[9]
    assert p10.unadjusted_start_date.to_date() == date(1999, 7, 14)
    assert p10.unadjusted_end_date.to_date() == date(1999, 12, 14)
    # final_stub の stub_rate (4.5%) が適用されていること
    assert p10.fixed_rate == Decimal("0.045")
    assert p10.floating_rate_definition is None


def test_generate_periods_notional_amortization():
    """Test CalculationPeriodScheduler for notional amortization using ird-ex02."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 浮動レッグストリームを取得
    floating_stream = doc.trade[0].swap.swap_stream[0]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)

    periods = scheduler.generate_periods(floating_stream)

    assert len(periods) == 10

    # 1期目 (1995-01-16 to 1995-06-14) - 初期想定元本 50,000,000.00
    assert periods[0].notional_amount == Decimal("50000000.00")

    # 2期目 (1995-06-14 to 1995-12-14) - 想定元本 50,000,000.00
    assert periods[1].notional_amount == Decimal("50000000.00")

    # 3期目 (1995-12-14 to 1996-06-14) - 元本削減ステップ反映 (1995-12-14に40,000,000.00へ)
    assert periods[2].notional_amount == Decimal("40000000.00")

    # 4期目 (1996-06-14 to 1996-12-16) - 想定元本 40,000,000.00
    assert periods[3].notional_amount == Decimal("40000000.00")

    # 5期目 (1996-12-16 to 1997-06-16) - 元本削減ステップ反映 (1996-12-14に30,000,000.00へ)
    assert periods[4].notional_amount == Decimal("30000000.00")

    # 7期目 (1997-12-15 to 1998-06-15) - 元本削減ステップ反映 (1997-12-14に20,000,000.00へ)
    assert periods[6].notional_amount == Decimal("20000000.00")

    # 9期目 (1998-12-14 to 1999-06-14) - 元本削減ステップ反映 (1998-12-14に10,000,000.00へ)
    assert periods[8].notional_amount == Decimal("10000000.00")

    # 10期目 (1999-06-14 to 1999-12-14) - 想定元本 10,000,000.00
    assert periods[9].notional_amount == Decimal("10000000.00")


def test_generate_periods_reset_in_arrears():
    """Test CalculationPeriodScheduler for Reset in Arrears (resetRelativeTo = CalculationPeriodEndDate)."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]

    # resetRelativeTo を CalculationPeriodEndDate に変更
    from fpml.confirmation import ResetRelativeToEnum

    floating_stream.reset_dates.reset_relative_to = (
        ResetRelativeToEnum.CALCULATION_PERIOD_END_DATE
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)

    periods = scheduler.generate_periods(floating_stream)

    assert len(periods) == 10

    # 1期目 (1995-01-16 to 1995-06-14)
    # 期末日は 1995-06-14 (水)
    # Fixingは 2営業日前 (GBLO) -> 1995-06-12 (月)
    p1 = periods[0]
    assert p1.adjusted_start_date.to_date() == date(1995, 1, 16)
    assert p1.adjusted_end_date.to_date() == date(1995, 6, 14)

    floating_def = p1.floating_rate_definition
    assert floating_def is not None
    assert len(floating_def.rate_observation) == 1
    obs1 = floating_def.rate_observation[0]

    # resetDate は期末日 (adjusted_end_date)
    assert obs1.reset_date.to_date() == date(1995, 6, 14)
    # adjusted_fixing_date も期末日から2営業日前
    assert obs1.adjusted_fixing_date.to_date() == date(1995, 6, 12)


def test_generate_periods_reset_relative_to_none():
    """Test CalculationPeriodScheduler when resetRelativeTo is None (defaulting to CalculationPeriodStartDate)."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]

    # reset_relative_to を None に設定
    floating_stream.reset_dates.reset_relative_to = None

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)

    periods = scheduler.generate_periods(floating_stream)

    assert len(periods) == 10
    p1 = periods[0]
    obs1 = p1.floating_rate_definition.rate_observation[0]
    # デフォルトである CalculationPeriodStartDate 基準なので、開始日 1995-01-16 から算出される
    assert obs1.reset_date.to_date() == date(1995, 1, 16)
