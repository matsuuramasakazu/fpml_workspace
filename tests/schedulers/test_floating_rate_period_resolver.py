from datetime import date
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser

from fpml.confirmation import (
    BusinessCenter,
    BusinessCenters,
    DataDocument,
    ObservationOffset,
    ObservationPeriodDatesEnum,
    ObservationShiftParameters,
)
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.floating_rate_period_resolver import FloatingRatePeriodResolver
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory


def setup_stream_with_parameters(xml_path):
    parser = XmlParser()
    doc = parser.from_path(xml_path, DataDocument)
    floating_stream = doc.trade[0].swap.swap_stream[0]

    # カレンダーを GBLO に強制
    calc_params = floating_stream.calculation_period_amount.calculation
    calc_params.floating_rate_calculation.calculation_parameters.applicable_business_days.business_centers = BusinessCenters(
        business_center=[BusinessCenter(value="GBLO")]
    )
    return floating_stream, doc


def test_floating_rate_period_resolver_rfr_lookback():
    """Lookback (GBLOカレンダーでの祝日を挟む期間での検証)。"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex45-rfr-compound-swap-lookback.xml"
    )
    calendar = BusinessCalendar(config_dir="config")
    floating_stream, doc = setup_stream_with_parameters(xml_path)
    resolver = ReferenceResolver(doc)
    scheduler = FloatingRatePeriodResolver(calendar, resolver)

    # 年末年始の祝日を挟むテスト期間 (2024-12-16 から 2025-01-16)
    unadjusted_start = date(2024, 12, 16)
    adjusted_start = date(2024, 12, 16)
    adjusted_end = date(2025, 1, 16)

    # 5営業日ルックバック
    calc_params = floating_stream.calculation_period_amount.calculation
    calc_params.floating_rate_calculation.calculation_parameters.lookback = (
        ObservationOffset(offset_days=5)
    )
    calc_params.floating_rate_calculation.calculation_parameters.observation_shift = (
        None
    )
    calc_params.floating_rate_calculation.calculation_parameters.lockout = None

    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )
    floating_def = scheduler.resolve_rate_def(
        unadjusted_start,
        adjusted_start,
        adjusted_end,
        floating_stream,
        step_schedule_resolver_factory,
    )
    assert floating_def is not None

    # GBLO 営業日数は：20営業日
    assert len(floating_def.rate_observation) == 20

    obs = {o.reset_date.to_date(): o for o in floating_def.rate_observation}

    # 12/24 (火) の検証 (次の営業日は 12/27 金)
    assert date(2024, 12, 24) in obs
    o_1224 = obs[date(2024, 12, 24)]
    assert o_1224.observation_weight == 3
    # 観測日: 12/24 の 5営業日前 -> 12/17 (火)
    assert o_1224.adjusted_fixing_date.to_date() == date(2024, 12, 17)


def test_floating_rate_period_resolver_rfr_observation_shift():
    """Observation Shift (Standard 5営業日)。"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex44-rfr-compound-swap-obs-period-shift.xml"
    )
    calendar = BusinessCalendar(config_dir="config")
    floating_stream, doc = setup_stream_with_parameters(xml_path)
    resolver = ReferenceResolver(doc)
    scheduler = FloatingRatePeriodResolver(calendar, resolver)

    unadjusted_start = date(2024, 12, 16)
    adjusted_start = date(2024, 12, 16)
    adjusted_end = date(2025, 1, 16)

    # 5営業日シフト
    calc_params = floating_stream.calculation_period_amount.calculation
    calc_params.floating_rate_calculation.calculation_parameters.lookback = None
    calc_params.floating_rate_calculation.calculation_parameters.observation_shift = (
        ObservationShiftParameters(
            offset_days=5,
            observation_period_dates=ObservationPeriodDatesEnum.STANDARD,
        )
    )
    calc_params.floating_rate_calculation.calculation_parameters.lockout = None

    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )
    floating_def = scheduler.resolve_rate_def(
        unadjusted_start,
        adjusted_start,
        adjusted_end,
        floating_stream,
        step_schedule_resolver_factory,
    )
    assert floating_def is not None
    assert len(floating_def.rate_observation) == 20

    obs = {o.reset_date.to_date(): o for o in floating_def.rate_observation}

    # 12/24 (火) の検証 (次の営業日は 12/27 金)
    assert date(2024, 12, 24) in obs
    o_1224 = obs[date(2024, 12, 24)]
    assert o_1224.observation_weight == 1
    # 観測日: 12/24 の 5営業日前 -> 12/17 (火)
    assert o_1224.adjusted_fixing_date.to_date() == date(2024, 12, 17)


def test_floating_rate_period_resolver_rfr_lockout():
    """Lockout (5営業日)。"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex45-rfr-compound-swap-lookback.xml"
    )
    calendar = BusinessCalendar(config_dir="config")
    floating_stream, doc = setup_stream_with_parameters(xml_path)
    resolver = ReferenceResolver(doc)
    scheduler = FloatingRatePeriodResolver(calendar, resolver)

    unadjusted_start = date(2024, 12, 16)
    adjusted_start = date(2024, 12, 16)
    adjusted_end = date(2025, 1, 16)

    # 5営業日 lockout
    calc_params = floating_stream.calculation_period_amount.calculation
    calc_params.floating_rate_calculation.calculation_parameters.lookback = None
    calc_params.floating_rate_calculation.calculation_parameters.observation_shift = (
        None
    )
    calc_params.floating_rate_calculation.calculation_parameters.lockout = (
        ObservationOffset(offset_days=5)
    )

    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, resolver
    )
    floating_def = scheduler.resolve_rate_def(
        unadjusted_start,
        adjusted_start,
        adjusted_end,
        floating_stream,
        step_schedule_resolver_factory,
    )
    assert floating_def is not None
    assert len(floating_def.rate_observation) == 20

    obs = {o.reset_date.to_date(): o for o in floating_def.rate_observation}

    # lockout 日は 1/16 の 5営業日前 -> 1/9 (木)
    # 1/15 (水) の適用日について、観測日は lockout日 (1/9) に固定される
    assert date(2025, 1, 15) in obs
    o_115 = obs[date(2025, 1, 15)]
    assert o_115.adjusted_fixing_date.to_date() == date(2025, 1, 9)


def test_floating_rate_period_resolver_rfr_plain():
    """Plain (デイリーの Compounding オプションなし)。"""
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex45-rfr-compound-swap-lookback.xml"
    )
    calendar = BusinessCalendar(config_dir="config")
    floating_stream, doc = setup_stream_with_parameters(xml_path)
    ref_resolver = ReferenceResolver(doc)
    scheduler = FloatingRatePeriodResolver(calendar, ref_resolver)

    unadjusted_start = date(2024, 12, 16)
    adjusted_start = date(2024, 12, 16)
    adjusted_end = date(2025, 1, 16)

    # オプションなし
    calc_params = floating_stream.calculation_period_amount.calculation
    calc_params.floating_rate_calculation.calculation_parameters.lookback = None
    calc_params.floating_rate_calculation.calculation_parameters.observation_shift = (
        None
    )
    calc_params.floating_rate_calculation.calculation_parameters.lockout = None

    step_schedule_resolver_factory = StepScheduleResolverFactory(
        floating_stream, ref_resolver
    )
    floating_def = scheduler.resolve_rate_def(
        unadjusted_start,
        adjusted_start,
        adjusted_end,
        floating_stream,
        step_schedule_resolver_factory,
    )
    assert floating_def is not None
    assert len(floating_def.rate_observation) == 20

    obs = {o.reset_date.to_date(): o for o in floating_def.rate_observation}

    assert date(2024, 12, 24) in obs
    o_1224 = obs[date(2024, 12, 24)]
    assert o_1224.adjusted_fixing_date.to_date() == date(2024, 12, 24)
