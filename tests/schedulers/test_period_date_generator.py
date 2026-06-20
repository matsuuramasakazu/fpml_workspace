from datetime import date

from src.schedulers.period_date_generator import PeriodDateGenerator


def test_add_months():
    # 通常の加算
    assert PeriodDateGenerator.add_months(date(2024, 1, 15), 1, "15") == date(
        2024, 2, 15
    )
    # 2月月末調整
    assert PeriodDateGenerator.add_months(date(2024, 1, 31), 1, "EOM") == date(
        2024, 2, 29
    )  # 2024年は閏年
    assert PeriodDateGenerator.add_months(date(2023, 1, 31), 1, "EOM") == date(
        2023, 2, 28
    )
    # ロールコンベンションによる調整
    assert PeriodDateGenerator.add_months(date(2024, 1, 31), 1, "30") == date(
        2024, 2, 29
    )  # 30指定だが2月は29日まで
    assert PeriodDateGenerator.add_months(date(2024, 1, 15), 1, "31") == date(
        2024, 2, 29
    )  # 31（EOMと同様）を指定


def test_generate_unadjusted_dates():
    start = date(2024, 1, 15)
    end = date(2025, 1, 15)
    # 前進で6ヶ月ごと
    dates = PeriodDateGenerator.generate_unadjusted_dates(start, end, 6, "M", "15")
    assert dates == [date(2024, 1, 15), date(2024, 7, 15), date(2025, 1, 15)]


def test_generate_unadjusted_dates_backward():
    start = date(2024, 1, 15)
    end = date(2025, 1, 15)
    # 後退で6ヶ月ごと
    dates = PeriodDateGenerator.generate_unadjusted_dates_backward(
        start, end, 6, "M", "15"
    )
    assert dates == [date(2024, 1, 15), date(2024, 7, 15), date(2025, 1, 15)]
