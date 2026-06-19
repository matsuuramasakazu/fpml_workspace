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
