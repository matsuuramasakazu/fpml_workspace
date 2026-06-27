from datetime import date
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import (
    BusinessCenter,
    BusinessCenters,
    DataDocument,
    ObservationOffset,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.rfr_observation_scheduler import RFRObservationScheduler


def test_rfr_observation_scheduler_lookback():
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex45-rfr-compound-swap-lookback.xml"
    )
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)
    floating_stream = doc.trade[0].swap.swap_stream[0]

    # カレンダーを GBLO に強制
    calc_params = floating_stream.calculation_period_amount.calculation
    calc_params.floating_rate_calculation.calculation_parameters.applicable_business_days.business_centers = BusinessCenters(
        business_center=[BusinessCenter(value="GBLO")]
    )

    calendar = BusinessCalendar(config_dir="config")
    resolver = ReferenceResolver(doc)
    scheduler = RFRObservationScheduler(calendar, resolver)

    adjusted_start = date(2024, 12, 16)
    adjusted_end = date(2025, 1, 16)

    # 5営業日ルックバック
    calc_params.floating_rate_calculation.calculation_parameters.lookback = (
        ObservationOffset(offset_days=5)
    )
    calc_params.floating_rate_calculation.calculation_parameters.observation_shift = (
        None
    )
    calc_params.floating_rate_calculation.calculation_parameters.lockout = None

    observations = scheduler.generate_rate_observations(
        adjusted_start,
        adjusted_end,
        floating_stream,
        calc_params.floating_rate_calculation.calculation_parameters,
    )

    assert observations is not None
    assert len(observations) == 20

    obs = {o.reset_date.to_date(): o for o in observations}
    assert date(2024, 12, 24) in obs
    o_1224 = obs[date(2024, 12, 24)]
    assert o_1224.observation_weight == 3
    assert o_1224.adjusted_fixing_date.to_date() == date(2024, 12, 17)
