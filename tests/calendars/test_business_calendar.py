"""Tests for BusinessCalendar."""

from datetime import date

import pytest

from src.calendars.business_calendar import BusinessCalendar


def test_is_business_day_weekend_and_weekday_without_holidays():
    """Test that weekends are holidays and weekdays are business days when no holidays are loaded."""
    # 実際のconfigディレクトリを指定
    calendar = BusinessCalendar(config_dir="config")

    # 2026-05-30 (土曜日) -> 休日
    # 2026-05-31 (日曜日) -> 休日
    # 2026-06-01 (月曜日、GBLOで祝祭日なし) -> 営業日
    sat = date(2026, 5, 30)
    sun = date(2026, 5, 31)
    mon = date(2026, 6, 1)

    # "GBLO" センターを指定。
    assert not calendar.is_business_day(sat, "GBLO")
    assert not calendar.is_business_day(sun, "GBLO")
    assert calendar.is_business_day(mon, "GBLO")


def test_is_business_day_with_loaded_holidays():
    """Test that loaded holidays are treated as non-business days."""
    # 実際のconfigディレクトリを指定
    calendar = BusinessCalendar(config_dir="config")

    # 2026-05-04 (月曜日、JPTOではみどりの日) -> 休日
    # 2026-05-08 (金曜日、平日かつJPTOで祝祭日なし) -> 営業日
    # 2026-05-03 (日曜日、JPTOでは憲法記念日) -> 休日
    holiday_mon = date(2026, 5, 4)
    weekday_fri = date(2026, 5, 8)
    holiday_sun = date(2026, 5, 3)

    assert not calendar.is_business_day(holiday_mon, "JPTO")
    assert calendar.is_business_day(weekday_fri, "JPTO")
    assert not calendar.is_business_day(holiday_sun, "JPTO")


def test_invalid_business_center_raises_error():
    """Test that an invalid business center raises FileNotFoundError."""
    calendar = BusinessCalendar(config_dir="config")
    with pytest.raises(FileNotFoundError):
        calendar.is_business_day(date(2026, 5, 8), "INVALID")


def test_is_business_day_multiple_centers():
    """Test that multiple business centers are joined with AND logic (holiday in either makes it a holiday)."""
    calendar = BusinessCalendar(config_dir="config")

    # 2026-02-11 (水曜日)
    # - JPTO: 建国記念の日 (祝祭日 -> 休日)
    # - GBLO: 祝祭日なし (営業日)
    # - USNY: 祝祭日なし (営業日)
    test_date = date(2026, 2, 11)

    assert calendar.is_business_day(test_date, "GBLO")
    assert calendar.is_business_day(test_date, "USNY")
    assert not calendar.is_business_day(test_date, "JPTO")

    # 複数センターの指定。片方が休日なので全体としても非営業日
    assert not calendar.is_business_day(test_date, ["GBLO", "JPTO"])
    assert not calendar.is_business_day(test_date, ["JPTO", "USNY"])
    # 両方が営業日なら営業日
    assert calendar.is_business_day(test_date, ["GBLO", "USNY"])


def test_adjust_date_following_preceding_none():
    """Test standard adjust conventions: FOLLOWING, PRECEDING, and NONE."""
    calendar = BusinessCalendar(config_dir="config")

    # 2026-05-30 は土曜日
    sat = date(2026, 5, 30)

    # FOLLOWING -> 2026-06-01 (月曜日、営業日)
    assert calendar.adjust_date(sat, "FOLLOWING", "GBLO") == date(2026, 6, 1)

    # PRECEDING -> 2026-05-29 (金曜日、営業日)
    assert calendar.adjust_date(sat, "PRECEDING", "GBLO") == date(2026, 5, 29)

    # NONE -> 2026-05-30 (そのまま)
    assert calendar.adjust_date(sat, "NONE", "GBLO") == date(2026, 5, 30)

    # 祝祭日による調整テスト: 2026-02-11 (水曜日、JPTO祝祭日)
    jpto_holiday = date(2026, 2, 11)
    # FOLLOWING -> 2026-02-12 (木曜日)
    assert calendar.adjust_date(jpto_holiday, "FOLLOWING", "JPTO") == date(2026, 2, 12)
    # PRECEDING -> 2026-02-10 (火曜日)
    assert calendar.adjust_date(jpto_holiday, "PRECEDING", "JPTO") == date(2026, 2, 10)


def test_adjust_date_modified_conventions():
    """Test modified adjust conventions: MODFOLLOWING and MODPRECEDING."""
    calendar = BusinessCalendar(config_dir="config")

    # --- MODFOLLOWING テスト ---
    # 2026-05-31 は日曜日 (5月の最終日)
    # FOLLOWING だと 2026-06-01 (月曜日) になり翌月に跨ぐため、
    # MODFOLLOWING では前営業日の 2026-05-29 (金曜日) に調整されるべき
    sun_may_end = date(2026, 5, 31)
    assert calendar.adjust_date(sun_may_end, "MODFOLLOWING", "GBLO") == date(
        2026, 5, 29
    )

    # 2026-05-24 は日曜日 (中旬)
    # FOLLOWING だと 2026-05-25 (月曜日) で同じ5月のため、
    # MODFOLLOWING でも 2026-05-25 になるべき
    sun_may_mid = date(2026, 5, 24)
    assert calendar.adjust_date(sun_may_mid, "MODFOLLOWING", "GBLO") == date(
        2026, 5, 25
    )

    # --- MODPRECEDING テスト ---
    # 2026-08-01 は土曜日 (8月の最初の日)
    # PRECEDING だと 2026-07-31 (金曜日) になり前月に跨ぐため、
    # MODPRECEDING では翌営業日の 2026-08-03 (月曜日) に調整されるべき
    sat_aug_start = date(2026, 8, 1)
    assert calendar.adjust_date(sat_aug_start, "MODPRECEDING", "GBLO") == date(
        2026, 8, 3
    )

    # 2026-08-09 は日曜日 (中旬)
    # PRECEDING だと 2026-08-07 (金曜日) で同じ8月のため、
    # MODPRECEDING でも 2026-08-07 になるべき
    sun_aug_mid = date(2026, 8, 9)
    assert calendar.adjust_date(sun_aug_mid, "MODPRECEDING", "GBLO") == date(2026, 8, 7)


def test_add_business_days():
    """Test add_business_days method for shifting dates by business days."""
    calendar = BusinessCalendar(config_dir="config")

    # 0営業日加算
    assert calendar.add_business_days(date(2026, 5, 29), 0, "GBLO") == date(2026, 5, 29)

    # +1営業日 (2026-05-29金曜 -> 2026-06-01月曜)
    assert calendar.add_business_days(date(2026, 5, 29), 1, "GBLO") == date(2026, 6, 1)

    # -2営業日 (2026-06-01月曜 -> 2026-05-28木曜)
    assert calendar.add_business_days(date(2026, 6, 1), -2, "GBLO") == date(2026, 5, 28)

    # 祝日跨ぎ (2026-02-10火曜 -> +2営業日 -> JPTO。2/11は祝日、2/12が1日後、2/13が2日後)
    assert calendar.add_business_days(date(2026, 2, 10), 2, "JPTO") == date(2026, 2, 13)
