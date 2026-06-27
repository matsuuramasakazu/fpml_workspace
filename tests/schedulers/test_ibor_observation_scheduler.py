from datetime import date
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import DataDocument
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.date_adjuster import DateAdjuster
from src.schedulers.ibor_observation_scheduler import IBORObservationScheduler
from src.schedulers.reference_resolver import ReferenceResolver


def test_ibor_observation_scheduler():
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)
    floating_stream = doc.trade[0].swap.swap_stream[0]  # 浮動金利レグ

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    adjuster = DateAdjuster(calendar, resolver)
    scheduler = IBORObservationScheduler(adjuster)

    # テスト期間 (2018-12-14 から 2019-06-14)
    adjusted_start = date(2018, 12, 14)
    adjusted_end = date(2019, 6, 14)

    observations = scheduler.generate_rate_observations(
        adjusted_start,
        adjusted_end,
        floating_stream,
    )

    assert observations is not None
    assert len(observations) == 1
    obs = observations[0]

    assert obs.reset_date.to_date() == date(2018, 12, 14)
    # London 2 営業日前 (2018-12-14 金 の 2営業日前は 2018-12-12 水)
    assert obs.adjusted_fixing_date.to_date() == date(2018, 12, 12)
    assert obs.observation_weight == 1
