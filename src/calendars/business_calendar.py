from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Set, Union

import tomllib


class BusinessCalendar:
    """Business calendar for checking business days and adjusting dates."""

    def __init__(self, config_dir: str = "config"):
        """Initialize the BusinessCalendar with config directory path."""
        self.config_dir = Path(config_dir)
        self._holiday_cache: Dict[str, Set[date]] = {}

    def _load_holidays(self, center: str) -> Set[date]:
        """Load and cache holidays for a specific business center."""
        center_upper = center.upper()
        if center_upper in self._holiday_cache:
            return self._holiday_cache[center_upper]

        file_path = self.config_dir / f"holidays_{center_upper}.toml"
        if not file_path.exists():
            raise FileNotFoundError(f"Holiday calendar file not found: {file_path}")

        with open(file_path, "rb") as f:
            data = tomllib.load(f)

        holidays_dict = data.get("holidays", {})
        holidays_set = {date.fromisoformat(d) for d in holidays_dict.keys()}
        self._holiday_cache[center_upper] = holidays_set
        return holidays_set

    def is_business_day(
        self, val_date: date, business_centers: Union[str, List[str]]
    ) -> bool:
        """Check if the date is a business day (not a weekend or holiday)."""
        # Saturday is 5, Sunday is 6
        if val_date.weekday() >= 5:
            return False

        if isinstance(business_centers, str):
            centers = [business_centers]
        else:
            centers = business_centers

        for center in centers:
            holidays = self._load_holidays(center)
            if val_date in holidays:
                return False

        return True

    def adjust_date(
        self, val_date: date, convention: str, business_centers: Union[str, List[str]]
    ) -> date:
        """
        Adjust date according to the business day convention.

        Args:
            val_date: The base date to adjust.
            convention: Business day convention ("FOLLOWING", "MODFOLLOWING", "PRECEDING", "MODPRECEDING", "NONE").
            business_centers: Business center code(s).

        Returns:
            The adjusted date.
        """
        conv_upper = convention.upper()
        if conv_upper == "NONE":
            return val_date

        if conv_upper == "FOLLOWING":
            current_date = val_date
            while not self.is_business_day(current_date, business_centers):
                current_date = current_date + timedelta(days=1)
            return current_date

        elif conv_upper == "PRECEDING":
            current_date = val_date
            while not self.is_business_day(current_date, business_centers):
                current_date = current_date - timedelta(days=1)
            return current_date

        elif conv_upper == "MODFOLLOWING":
            # 基本は FOLLOWING
            following_date = val_date
            while not self.is_business_day(following_date, business_centers):
                following_date = following_date + timedelta(days=1)

            # 月が変わってしまった場合は PRECEDING に切り替える
            if following_date.month != val_date.month:
                preceding_date = val_date
                while not self.is_business_day(preceding_date, business_centers):
                    preceding_date = preceding_date - timedelta(days=1)
                return preceding_date
            return following_date

        elif conv_upper == "MODPRECEDING":
            # 基本は PRECEDING
            preceding_date = val_date
            while not self.is_business_day(preceding_date, business_centers):
                preceding_date = preceding_date - timedelta(days=1)

            # 月が変わってしまった場合は FOLLOWING に切り替える
            if preceding_date.month != val_date.month:
                following_date = val_date
                while not self.is_business_day(following_date, business_centers):
                    following_date = following_date + timedelta(days=1)
                return following_date
            return preceding_date

        else:
            raise ValueError(f"Unknown business day convention: {convention}")

    def add_business_days(
        self, val_date: date, days: int, business_centers: Union[str, List[str]]
    ) -> date:
        """
        Add or subtract business days to a date using specified business centers.

        Args:
            val_date: The base date.
            days: Number of business days to add (positive) or subtract (negative).
            business_centers: Business center code(s).

        Returns:
            The shifted date which is a business day.
        """
        if days == 0:
            return val_date

        step = 1 if days > 0 else -1
        remaining = abs(days)
        current_date = val_date

        while remaining > 0:
            current_date = current_date + timedelta(days=step)
            if self.is_business_day(current_date, business_centers):
                remaining -= 1

        return current_date
