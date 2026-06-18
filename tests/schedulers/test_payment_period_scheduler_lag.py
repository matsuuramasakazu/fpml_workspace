from datetime import date
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import (
    BusinessDayConventionEnum,
    DataDocument,
    DateReference,
    DayTypeEnum,
    PeriodEnum,
    RelativeDateOffset,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.calculation_period_scheduler import CalculationPeriodScheduler
from src.schedulers.payment_period_scheduler import PaymentPeriodScheduler
from src.schedulers.reference_resolver import ReferenceResolver


def test_payment_period_scheduler_lag():
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

    # paymentDaysOffset を設定 (2営業日遅延)
    offset = RelativeDateOffset(
        period_multiplier=2,
        period=PeriodEnum.D,
        day_type=DayTypeEnum.BUSINESS,
        business_day_convention=BusinessDayConventionEnum.NONE,
        date_relative_to=DateReference(href="calculationPeriodDates-64209468-681"),
    )
    fixed_stream.payment_dates.payment_days_offset = offset

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)

    # 計算期間を展開
    calc_scheduler = CalculationPeriodScheduler(calendar, resolver)
    calc_periods = calc_scheduler.generate_periods(fixed_stream)

    # 支払期間を集約
    pay_scheduler = PaymentPeriodScheduler(calendar, resolver)
    periods = pay_scheduler.aggregate_periods(calc_periods, fixed_stream)

    assert len(periods) == 5
    # 第1期の終了日 1995-12-14 (木) に対して 2営業日 (GBLO, USNY) の支払遅延
    # 期待値: 1995-12-18 (月)
    assert periods[0].adjusted_payment_date.to_date() == date(1995, 12, 18)
