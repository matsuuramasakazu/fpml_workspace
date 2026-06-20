import calendar
from datetime import date
from typing import List


class PeriodDateGenerator:
    """スケジュール期日（unadjusted dates）の生成を担当するクラス。"""

    @staticmethod
    def add_months(start_date: date, months: int, roll_convention: str) -> date:
        """指定された月数だけ日付を進めます（ロールコンベンション考慮）。"""
        y = start_date.year + (start_date.month + months - 1) // 12
        m = (start_date.month + months - 1) % 12 + 1

        last_day = calendar.monthrange(y, m)[1]

        if roll_convention == "EOM" or roll_convention == "31":
            return date(y, m, last_day)

        try:
            day_num = int(roll_convention)
            if 1 <= day_num <= 30:
                return date(y, m, min(day_num, last_day))
        except ValueError:
            pass

        return date(y, m, min(start_date.day, last_day))

    @classmethod
    def generate_unadjusted_dates(
        cls,
        start_date: date,
        end_date: date,
        multiplier: int,
        period: str,
        roll_convention: str,
    ) -> List[date]:
        """unadjusted な計算期日のリストを前進的に生成します。"""
        dates = [start_date]
        months_to_add = multiplier
        if period == "Y":
            months_to_add *= 12

        i = 1
        while True:
            next_date = cls.add_months(start_date, i * months_to_add, roll_convention)
            if next_date >= end_date:
                break
            dates.append(next_date)
            i += 1

        dates.append(end_date)
        return dates

    @classmethod
    def generate_unadjusted_dates_backward(
        cls,
        start_date: date,
        end_date: date,
        multiplier: int,
        period: str,
        roll_convention: str,
    ) -> List[date]:
        """unadjusted な計算期日のリストを後退的に生成します。"""
        dates = [end_date]
        months_to_subtract = multiplier
        if period == "Y":
            months_to_subtract *= 12

        i = 1
        while True:
            next_date = cls.add_months(
                end_date, -i * months_to_subtract, roll_convention
            )
            if next_date <= start_date:
                break
            dates.append(next_date)
            i += 1

        dates.append(start_date)
        return sorted(list(set(dates)))
