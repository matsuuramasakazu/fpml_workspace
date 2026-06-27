from datetime import date

from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    InterestRateStream,
    RateObservation,
)
from src.schedulers.date_adjuster import DateAdjuster


class IBORObservationScheduler:
    """従来の IBOR レグに対する rate_observation の生成を担当するクラス。"""

    def __init__(self, adjuster: DateAdjuster):
        self._adjuster = adjuster

    def generate_rate_observations(
        self,
        adjusted_start: date,
        adjusted_end: date,
        stream: InterestRateStream,
    ) -> list[RateObservation]:
        """従来の IBOR レグに対する rate_observation を生成します。"""
        reset_dates = stream.reset_dates
        assert reset_dates is not None

        # resetRelativeToがStartDateまたはNoneなら計算期間開始日を基準にする
        reset_date_val = adjusted_start
        reset_rel = reset_dates.reset_relative_to
        if reset_rel is not None and reset_rel.value == "CalculationPeriodEndDate":
            reset_date_val = adjusted_end

        # Fixing日の算出
        fixing_dates = reset_dates.fixing_dates
        adjusted_fixing = self._adjuster.resolve_relative_date_offset(
            reset_date_val, fixing_dates
        )

        obs = RateObservation(
            reset_date=XmlDate(
                reset_date_val.year, reset_date_val.month, reset_date_val.day
            ),
            adjusted_fixing_date=XmlDate(
                adjusted_fixing.year, adjusted_fixing.month, adjusted_fixing.day
            ),
            observation_weight=1,
        )

        return [obs]
