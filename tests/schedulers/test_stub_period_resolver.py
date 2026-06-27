from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from fpml.confirmation import InterestRateStream
from src.schedulers.stub_period_resolver import StubPeriodResolver


class DummyXmlDate:
    def __init__(self, d: date):
        self._d = d

    def to_date(self) -> date:
        return self._d


class DummyCalculationPeriodDates:
    def __init__(
        self,
        first_reg_start: date | None = None,
        last_reg_end: date | None = None,
    ):
        self.first_regular_period_start_date = (
            DummyXmlDate(first_reg_start) if first_reg_start else None
        )
        self.first_compounding_period_end_date = None
        self.last_regular_period_end_date = (
            DummyXmlDate(last_reg_end) if last_reg_end else None
        )


def test_stub_period_resolver_is_stub():
    resolver = StubPeriodResolver()

    # レギュラー期間が 2026-03-01 〜 2026-12-01
    calc_dates = DummyCalculationPeriodDates(
        first_reg_start=date(2026, 3, 1), last_reg_end=date(2026, 12, 1)
    )

    # 初期スタブ (2026-01-01 から 2026-03-01)
    is_initial, is_final = resolver.is_stub(
        date(2026, 1, 1), date(2026, 3, 1), calc_dates
    )
    assert is_initial is True
    assert is_final is False

    # レギュラー期間内 (2026-03-01 から 2026-06-01)
    is_initial, is_final = resolver.is_stub(
        date(2026, 3, 1), date(2026, 6, 1), calc_dates
    )
    assert is_initial is False
    assert is_final is False

    # 期末スタブ (2026-12-01 から 2027-01-01)
    is_initial, is_final = resolver.is_stub(
        date(2026, 12, 1), date(2027, 1, 1), calc_dates
    )
    assert is_initial is False
    assert is_final is True


def test_stub_period_resolver_resolve_stub_overrides():
    resolver = StubPeriodResolver()

    # モック stream
    stream = MagicMock(spec=InterestRateStream)
    stub_amount_info = MagicMock()
    stream.stub_calculation_period_amount = stub_amount_info

    initial_stub = MagicMock()
    initial_stub.stub_rate = Decimal("0.045")
    initial_stub.stub_amount = None

    stub_amount_info.initial_stub = initial_stub
    stub_amount_info.final_stub = None

    # 初期スタブの上書き解決
    rate, amount = resolver.resolve_stub_overrides(True, False, stream)
    assert rate == Decimal("0.045")
    assert amount is None

    # スタブ量の上書き解決
    final_stub = MagicMock()
    final_stub.stub_rate = None
    final_stub.stub_amount = Decimal("100000")
    stub_amount_info.final_stub = final_stub

    rate, amount = resolver.resolve_stub_overrides(False, True, stream)
    assert rate is None
    assert amount == Decimal("100000")
