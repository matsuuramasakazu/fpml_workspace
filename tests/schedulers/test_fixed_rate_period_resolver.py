from datetime import date
from decimal import Decimal

from src.schedulers.fixed_rate_period_resolver import FixedRatePeriodResolver


class MockFixedRateResolver:
    def resolve(self, ustart: date) -> Decimal:
        return Decimal("0.05")

class MockStepScheduleResolverFactory:
    def __init__(self, fixed_resolver: MockFixedRateResolver | None):
        self.fixed_rate_resolver = fixed_resolver


def test_fixed_rate_period_resolver():
    step_schedule_resolver_factory = MockStepScheduleResolverFactory(MockFixedRateResolver())

    fixed_rate_resolver = FixedRatePeriodResolver()

    assert fixed_rate_resolver.resolve_rate(date(2026, 1, 1), step_schedule_resolver_factory) == Decimal("0.05")


def test_fixed_rate_period_resolver_none():
    step_schedule_resolver_factory = MockStepScheduleResolverFactory(None)

    fixed_rate_resolver = FixedRatePeriodResolver()
    assert fixed_rate_resolver.resolve_rate(date(2026, 1, 1), step_schedule_resolver_factory) is None
