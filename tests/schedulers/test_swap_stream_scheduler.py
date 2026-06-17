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
