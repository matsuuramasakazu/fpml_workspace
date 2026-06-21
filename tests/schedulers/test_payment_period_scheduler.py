from datetime import date

from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.payment_period_scheduler import PaymentPeriodScheduler
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


def test_swap_stream_scheduler_vanilla_swap_fixed_leg():
    """Test PaymentPeriodScheduler schedule generation for fixed leg using ird-ex01."""
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
    scheduler = PaymentPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(fixed_stream, resolver)

    periods = scheduler.generate_payment_periods(
        fixed_stream, step_schedule_resolver_factory
    )

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
    """Test PaymentPeriodScheduler schedule generation for floating leg using ird-ex01."""
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
    scheduler = PaymentPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )

    periods = scheduler.generate_payment_periods(
        floating_stream, step_schedule_resolver_factory
    )

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
    """Test PaymentPeriodScheduler schedule generation for FX-linked notional leg using ird-ex25."""
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
    scheduler = PaymentPeriodScheduler(calendar, resolver)
    step_schedule_resolver_factory = StepScheduleResolverFactory(usd_stream, resolver)

    periods = scheduler.generate_payment_periods(
        usd_stream, step_schedule_resolver_factory
    )

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
