from datetime import date
from decimal import Decimal

from src.schedulers.fixed_rate_period_resolver import FixedRatePeriodResolver


class MockFixedRateResolver:
    def resolve(self, ustart: date) -> Decimal:
        return Decimal("0.05")


def test_fixed_rate_period_resolver():
    mock_resolver = MockFixedRateResolver()
    resolver = FixedRatePeriodResolver(mock_resolver)

    assert resolver.resolve_rate(date(2026, 1, 1)) == Decimal("0.05")


def test_fixed_rate_period_resolver_none():
    resolver = FixedRatePeriodResolver(None)
    assert resolver.resolve_rate(date(2026, 1, 1)) is None
