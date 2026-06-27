import copy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.models.datatype import XmlDate as ModelXmlDate

from fpml.confirmation import (
    # CalculationPeriodDates,
    DataDocument,
    DateReference,
    FxLinkedNotionalSchedule,
    # RelativeDateOffset,
    # ResetDates,
    ResetRelativeToEnum,
    Stub,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.calculation_period_scheduler import CalculationPeriodScheduler
from src.schedulers.payment_period_scheduler import PaymentPeriodScheduler
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


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
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

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
    floating_stream.stub_calculation_period_amount.initial_stub = Stub(
        stub_rate=Decimal("0.035")
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

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
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    from src.schedulers.payment_period_scheduler import PaymentPeriodScheduler

    scheduler = PaymentPeriodScheduler(calendar, resolver)

    periods = scheduler.generate_payment_periods(
        floating_stream, step_schedule_resolver_factory
    )

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
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

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
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

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
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

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
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

    assert len(periods) == 10
    p1 = periods[0]
    obs1 = p1.floating_rate_definition.rate_observation[0]
    # デフォルトである CalculationPeriodStartDate 基準なので、開始日 1995-01-16 から算出される
    assert obs1.reset_date.to_date() == date(1995, 1, 16)


def test_generate_periods_fixed_rate_step_schedule():
    """Test CalculationPeriodScheduler for fixed rate step schedule resolution."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 固定レッグ（2番目のストリーム）を取得
    fixed_stream = doc.trade[0].swap.swap_stream[1]
    calc_params = fixed_stream.calculation_period_amount.calculation

    # fixedRateSchedule を書き換え、ステップスケジュールを設定
    from xsdata.models.datatype import XmlDate as ModelXmlDate

    from fpml.confirmation import Schedule, Step

    # 契約期間: 1995-01-16 から 1999-12-14
    # 6M ごとで 10 期間
    # initialValue = 0.05
    # step 1: 1996-06-14 -> 0.055
    # step 2: 1998-06-15 -> 0.060
    calc_params.fixed_rate_schedule = Schedule(
        initial_value=Decimal("0.05"),
        step=[
            Step(step_date=ModelXmlDate(1996, 6, 14), step_value=Decimal("0.055")),
            Step(step_date=ModelXmlDate(1998, 6, 15), step_value=Decimal("0.060")),
        ],
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(fixed_stream, resolver)

    periods = scheduler.generate_periods(fixed_stream, step_schedule_resolver_factory)

    assert len(periods) == 5

    # 1期目 (1995-01-16 to 1995-12-14) -> 0.05
    assert periods[0].fixed_rate == Decimal("0.05")

    # 2期目 (1995-12-14 to 1996-12-16) -> 0.05 (ステップ日は1996-06-14なので、2期目開始日の1995-12-14時点ではまだ適用されない)
    assert periods[1].fixed_rate == Decimal("0.05")

    # 3期目 (1996-12-16 to 1997-12-15) -> 0.055 (1996-06-14にステップした0.055が適用される)
    assert periods[2].fixed_rate == Decimal("0.055")

    # 4期目 (1997-12-15 to 1998-12-14) -> 0.055 (ステップ日は1998-06-15なので、4期目開始日の1997-12-15時点ではまだ適用されない)
    assert periods[3].fixed_rate == Decimal("0.055")

    # 5期目 (1998-12-14 to 1999-12-14) -> 0.060 (1998-06-15にステップした0.060が適用される)
    assert periods[4].fixed_rate == Decimal("0.060")


def test_generate_periods_floating_spread_step_schedule():
    """Test CalculationPeriodScheduler for floating spread step schedule resolution."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex02-stub-amort-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 浮動レッグ（1番目のストリーム）を取得
    floating_stream = doc.trade[0].swap.swap_stream[0]
    floating_calc = (
        floating_stream.calculation_period_amount.calculation.floating_rate_calculation
    )

    # spreadSchedule を書き換え、ステップスケジュールを設定
    # 元々の ird-ex02 はスプレッドスケジュールがなく、LIBOR のみ
    # ここで Schedule と Step を使って動的にスプレッドステップを設定する
    from xsdata.models.datatype import XmlDate as ModelXmlDate

    from fpml.confirmation import Schedule, Step

    # 契約期間: 1995-01-16 から 1999-12-14
    # 頻度 6M、初期スタブありで全体で 10 期間
    # initialValue = 0.001 (10 bps)
    # step 1: 1996-06-14 -> 0.002 (20 bps)
    # step 2: 1998-06-15 -> 0.003 (30 bps)
    floating_calc.spread_schedule = [
        Schedule(
            initial_value=Decimal("0.001"),
            step=[
                Step(step_date=ModelXmlDate(1996, 6, 14), step_value=Decimal("0.002")),
                Step(step_date=ModelXmlDate(1998, 6, 15), step_value=Decimal("0.003")),
            ],
        )
    ]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

    assert len(periods) == 10

    # 1期目 (1995-01-16 to 1995-06-14) -> 0.001
    assert periods[0].floating_rate_definition.spread == Decimal("0.001")

    # 3期目 (1995-12-14 to 1996-06-14) -> 0.001 (ステップ日は1996-06-14なので、3期目開始日1995-12-14時点ではまだ適用されない)
    assert periods[2].floating_rate_definition.spread == Decimal("0.001")

    # 4期目 (1996-06-14 to 1996-12-16) -> 0.002 (1996-06-14にステップ)
    assert periods[3].floating_rate_definition.spread == Decimal("0.002")

    # 7期目 (1997-12-15 to 1998-06-15) -> 0.002 (ステップ日は1998-06-15なので、7期目開始日1997-12-15時点ではまだ適用されない)
    assert periods[6].floating_rate_definition.spread == Decimal("0.002")

    # 8期目 (1998-06-14 to 1998-12-14) -> 0.002 (ステップ日は1998-06-15なので、8期目開始日1998-06-14時点ではまだ適用されない)
    assert periods[7].floating_rate_definition.spread == Decimal("0.002")

    # 9期目 (1998-12-14 to 1999-06-14) -> 0.003 (1998-06-15にステップした0.003が適用される)
    assert periods[8].floating_rate_definition.spread == Decimal("0.003")

    # 10期目 (1999-06-14 to 1999-12-14) -> 0.003
    assert periods[9].floating_rate_definition.spread == Decimal("0.003")


def test_compounding_schedule_with_first_compounding_period_end_date():
    """Test CalculationPeriodScheduler & SwapStreamScheduler for compounding swap with firstCompoundingPeriodEndDate."""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex03-compound-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    floating_stream = doc.trade[0].swap.swap_stream[0]
    calc_dates = floating_stream.calculation_period_dates

    # firstCompoundingPeriodEndDate を設定 (2000-06-27)
    calc_dates.first_compounding_period_end_date = ModelXmlDate(2000, 6, 27)

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

    # 期待される計算期間の数: 9期
    assert len(periods) == 9

    # C1: 2000-04-27 to 2000-06-27 (unadjusted)
    assert periods[0].unadjusted_start_date.to_date() == date(2000, 4, 27)
    assert periods[0].unadjusted_end_date.to_date() == date(2000, 6, 27)

    # C2: 2000-06-27 to 2000-09-27
    assert periods[1].unadjusted_start_date.to_date() == date(2000, 6, 27)
    assert periods[1].unadjusted_end_date.to_date() == date(2000, 9, 27)

    # 2. SwapStreamScheduler (PaymentPeriodScheduler) の集約テスト
    stream_scheduler = PaymentPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory_pay = StepScheduleResolverFactory(
        floating_stream, resolver
    )
    payment_periods = stream_scheduler.generate_payment_periods(
        floating_stream, step_schedule_resolver_factory_pay
    )

    # 期待される支払期間の数: 5期
    assert len(payment_periods) == 5

    # P1 unadjusted end = 2000-06-27
    # P1 calculation periods: C1 (1期のみ)
    assert len(payment_periods[0].calculation_period) == 1
    assert payment_periods[0].calculation_period[
        0
    ].unadjusted_start_date.to_date() == date(2000, 4, 27)
    assert payment_periods[0].calculation_period[
        0
    ].unadjusted_end_date.to_date() == date(2000, 6, 27)

    # P2 unadjusted end = 2000-12-27
    # P2 calculation periods: C2, C3 (2期)
    assert len(payment_periods[1].calculation_period) == 2
    assert payment_periods[1].calculation_period[
        0
    ].unadjusted_start_date.to_date() == date(2000, 6, 27)
    assert payment_periods[1].calculation_period[
        1
    ].unadjusted_end_date.to_date() == date(2000, 12, 27)


def test_generate_periods_fx_linked_notional_floating_leg():
    """varyingNotionalFixingDates が ResetDates を参照する変動金利元本リセットレッグのテスト"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex25-fxnotional-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 第2レッグ (変動金利 / 元本リセットサイド)
    floating_stream = doc.trade[0].swap.swap_stream[1]

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_periods(
        floating_stream, step_schedule_resolver_factory
    )

    assert len(periods) > 0

    for period in periods:
        fx_amount = period.fx_linked_notional_amount
        assert fx_amount is not None
        # reset_date は常に計算期間の調整済開始日と一致することを確認
        assert fx_amount.reset_date.to_date() == period.adjusted_start_date.to_date()


def test_generate_periods_fx_linked_notional_fixed_leg():
    """varyingNotionalFixingDates が CalculationPeriodDates を参照する固定金利元本リセットレッグのテスト"""

    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex25-fxnotional-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 第1レッグ (固定金利サイド) と 第2レッグ (変動金利サイド)
    fixed_stream = doc.trade[0].swap.swap_stream[0]
    floating_stream = doc.trade[0].swap.swap_stream[1]

    # floating_stream から必須となる項目を借用する
    floating_fx_schedule = floating_stream.calculation_period_amount.calculation.fx_linked_notional_schedule

    # varyingNotionalFixingDates をディープコピーし、基準日を calculationPeriodDates (fixedCalcPeriodDates) に変更
    varying_fixing = copy.deepcopy(floating_fx_schedule.varying_notional_fixing_dates)
    varying_fixing.date_relative_to = DateReference(href="fixedCalcPeriodDates")

    fixed_stream.calculation_period_amount.calculation.fx_linked_notional_schedule = FxLinkedNotionalSchedule(
        constant_notional_schedule_reference=fixed_stream.calculation_period_amount.calculation.notional_schedule,
        varying_notional_currency="USD",
        varying_notional_fixing_dates=varying_fixing,
        fx_spot_rate_source=floating_fx_schedule.fx_spot_rate_source,
        varying_notional_interim_exchange_payment_dates=floating_fx_schedule.varying_notional_interim_exchange_payment_dates,
    )
    # 元本スケジュールを choice 構成に合わせて削除
    fixed_stream.calculation_period_amount.calculation.notional_schedule = None

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = CalculationPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(fixed_stream, resolver)

    # resetDates が存在しない状態での期間生成
    periods = scheduler.generate_periods(fixed_stream, step_schedule_resolver_factory)

    assert len(periods) > 0
    for period in periods:
        fx_amount = period.fx_linked_notional_amount
        assert fx_amount is not None
        # resetDates がなくても、reset_date は計算期間の調整済開始日と一致することを確認
        assert fx_amount.reset_date.to_date() == period.adjusted_start_date.to_date()


def test_generate_periods_fx_linked_notional_invalid_anchor():
    """varyingNotionalFixingDates.dateRelativeTo が未対応の要素を参照している場合の例外テスト"""

    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex25-fxnotional-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)

    # 第2レッグ
    floating_stream = doc.trade[0].swap.swap_stream[1]

    # アンカーを PaymentDates に差し替える
    # (PaymentDates は ResetDates や CalculationPeriodDates ではないため、解決された段階で ValueError になるはず)
    floating_stream.payment_dates.id = "dummyPaymentDates"
    varying_fixing = floating_stream.calculation_period_amount.calculation.fx_linked_notional_schedule.varying_notional_fixing_dates
    varying_fixing.date_relative_to = DateReference(href="dummyPaymentDates")

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    # ダミーで PaymentDates を解決できるようにリゾルバーの内部マップに登録
    resolver._id_map["dummyPaymentDates"] = floating_stream.payment_dates

    scheduler = CalculationPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    with pytest.raises(ValueError, match="Unknown reset anchor"):
        scheduler.generate_periods(floating_stream, step_schedule_resolver_factory)
