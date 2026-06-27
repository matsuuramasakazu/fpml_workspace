import calendar

from fpml.confirmation import DataDocument
from src.validators.base import ValidationRule
from src.validators.exceptions import (
    DateMismatchError,
    InvalidConfigurationError,
    MissingRequiredFieldError,
)


class Ird1Rule(ValidationRule):
    """IRD-1 ルール: 変動金利レッグのresetDates存在チェック。

    変動金利レッグ（floatingRateCalculationが存在する）において、
    O/N RFR（Override/New Risk-Free Rate、calculationParametersが存在する）の場合を除き、
    resetDatesが設定されていることを検証します。
    """

    @property
    def rule_id(self) -> str:
        return "ird-1"

    def validate(self, data_document: DataDocument) -> None:
        if not data_document.trade:
            return

        for trade in data_document.trade:
            if not trade.swap:
                continue

            for stream in trade.swap.swap_stream:
                calc_amount = stream.calculation_period_amount
                if not calc_amount or not calc_amount.calculation:
                    continue

                floating_rate_calc = calc_amount.calculation.floating_rate_calculation
                if floating_rate_calc is not None:
                    # O/N RFR でない場合 (calculation_parametersがない場合)
                    if floating_rate_calc.calculation_parameters is None:
                        if stream.reset_dates is None:
                            raise MissingRequiredFieldError(
                                f"Validation failed for rule [{self.rule_id}]: "
                                f"Floating rate leg (swapStream ID: {stream.id}) requires resetDates "
                                f"unless it is an O/N RFR index."
                            )


class Ird10Rule(ValidationRule):
    """IRD-10 ルール: 開始日とrollConventionの整合性チェック。

    スワップストリームの開始日（firstRegularPeriodStartDate または調整前 effectiveDate）の「日」が、
    rollConventionで指定された値（数値表現）と一致していることを検証します。
    ただし、rollConventionの値が開始日を含む月の最終日より大きい場合は、最終日を期待値とします。
    数値以外のrollConvention（EOM, IMM等）の場合は検証をスキップします。
    """

    @property
    def rule_id(self) -> str:
        return "ird-10"

    def validate(self, data_document: DataDocument) -> None:
        if not data_document.trade:
            return

        for trade in data_document.trade:
            if not trade.swap:
                continue

            for stream in trade.swap.swap_stream:
                cp_dates = stream.calculation_period_dates
                if not cp_dates or not cp_dates.calculation_period_frequency:
                    continue

                roll_conv = cp_dates.calculation_period_frequency.roll_convention
                if not roll_conv:
                    continue

                try:
                    rc_val = int(roll_conv.value)
                except ValueError:
                    # 数値でない場合 (EOM, IMM 等) は検証スキップ
                    continue

                # 開始日の特定
                if cp_dates.first_regular_period_start_date is not None:
                    start_date = cp_dates.first_regular_period_start_date.to_date()
                else:
                    if (
                        not cp_dates.effective_date
                        or not cp_dates.effective_date.unadjusted_date
                    ):
                        continue
                    start_date = cp_dates.effective_date.unadjusted_date.value.to_date()

                # 月の最終日との小さい方を期待値とする
                last_day = calendar.monthrange(start_date.year, start_date.month)[1]
                expected_day = min(rc_val, last_day)

                if start_date.day != expected_day:
                    raise InvalidConfigurationError(
                        f"Validation failed for rule [{self.rule_id}]: "
                        f"Start date day ({start_date.day}) must match rollConvention ({expected_day}) "
                        f"in swapStream ID: {stream.id}."
                    )


class Ird11Rule(ValidationRule):
    """IRD-11 ルール: 終了日とrollConventionの整合性チェック。

    スワップストリームの終了日（lastRegularPeriodEndDate または調整前 terminationDate）の「日」が、
    rollConventionで指定された値（数値表現）と一致していることを検証します。
    ただし、rollConventionの値が終了日を含む月の最終日より大きい場合は、最終日を期待値とします。
    数値以外のrollConvention（EOM, IMM等）の場合は検証をスキップします。
    """

    @property
    def rule_id(self) -> str:
        return "ird-11"

    def validate(self, data_document: DataDocument) -> None:
        if not data_document.trade:
            return

        for trade in data_document.trade:
            if not trade.swap:
                continue

            for stream in trade.swap.swap_stream:
                cp_dates = stream.calculation_period_dates
                if not cp_dates or not cp_dates.calculation_period_frequency:
                    continue

                roll_conv = cp_dates.calculation_period_frequency.roll_convention
                if not roll_conv:
                    continue

                try:
                    rc_val = int(roll_conv.value)
                except ValueError:
                    # 数値でない場合は検証スキップ
                    continue

                # 終了日の特定
                if cp_dates.last_regular_period_end_date is not None:
                    end_date = cp_dates.last_regular_period_end_date.to_date()
                else:
                    if (
                        not cp_dates.termination_date
                        or not cp_dates.termination_date.unadjusted_date
                    ):
                        continue
                    end_date = cp_dates.termination_date.unadjusted_date.value.to_date()

                # 月の最終日との小さい方を期待値とする
                last_day = calendar.monthrange(end_date.year, end_date.month)[1]
                expected_day = min(rc_val, last_day)

                if end_date.day != expected_day:
                    raise InvalidConfigurationError(
                        f"Validation failed for rule [{self.rule_id}]: "
                        f"Termination date day ({end_date.day}) must match rollConvention ({expected_day}) "
                        f"in swapStream ID: {stream.id}."
                    )


class Ird12Rule(ValidationRule):
    """IRD-12 ルール: 計算頻度と支払頻度の整合性チェック。

    スワップストリームの計算頻度（calculationPeriodFrequency）と支払頻度（paymentFrequency）の
    単位が互換（月ベース同士、または日ベース同士など）であり、かつ数学的に一方が他方を
    割り切れる（整数倍の関係にある）ことを検証します。
    """

    @property
    def rule_id(self) -> str:
        return "ird-12"

    def _get_months(self, multiplier: int, period: str) -> int | None:
        if period == "M":
            return multiplier
        if period == "Y":
            return multiplier * 12
        return None

    def _get_days(self, multiplier: int, period: str) -> int | None:
        if period == "D":
            return multiplier
        if period == "W":
            return multiplier * 7
        return None

    def validate(self, data_document: DataDocument) -> None:
        if not data_document.trade:
            return

        for trade in data_document.trade:
            if not trade.swap:
                continue

            for stream in trade.swap.swap_stream:
                cp_dates = stream.calculation_period_dates
                payment_dates = stream.payment_dates
                if not cp_dates or not payment_dates:
                    continue

                freq_cp = cp_dates.calculation_period_frequency
                freq_pay = payment_dates.payment_frequency
                if not freq_cp or not freq_pay:
                    continue

                mult_c = freq_cp.period_multiplier
                period_c = freq_cp.period.value if freq_cp.period else None
                mult_p = freq_pay.period_multiplier
                period_p = freq_pay.period.value if freq_pay.period else None

                if not mult_c or not period_c or not mult_p or not period_p:
                    continue

                # 単位換算（月ベースまたは日ベース）
                val_c = self._get_months(mult_c, period_c)
                val_p = self._get_months(mult_p, period_p)

                if val_c is None or val_p is None:
                    # 月ベースでない場合は日ベースで換算
                    val_c = self._get_days(mult_c, period_c)
                    val_p = self._get_days(mult_p, period_p)

                if val_c is None or val_p is None:
                    # 換算できない組み合わせ（例：一方が月ベースで他方が日ベース）は不整合
                    raise InvalidConfigurationError(
                        f"Validation failed for rule [{self.rule_id}]: "
                        f"Calculation frequency ({mult_c}{period_c}) and payment frequency ({mult_p}{period_p}) "
                        f"have incompatible periods in swapStream ID: {stream.id}."
                    )

                # 数学的整合性チェック（一方が他方の整数倍であること）
                if val_c % val_p != 0 and val_p % val_c != 0:
                    raise InvalidConfigurationError(
                        f"Validation failed for rule [{self.rule_id}]: "
                        f"Calculation frequency ({mult_c}{period_c}) and payment frequency ({mult_p}{period_p}) "
                        f"are mathematically incompatible (one must divide the other) in swapStream ID: {stream.id}."
                    )


class Ird21Rule(ValidationRule):
    """IRD-21 ルール: 複数レッグ間の調整前有効日の同一性チェック。

    スワップ取引に含まれるすべてのスワップストリーム（レッグ）間で、
    調整前の有効日（effectiveDate.unadjustedDate）が一致していることを検証します。
    """

    @property
    def rule_id(self) -> str:
        return "ird-21"

    def validate(self, data_document: DataDocument) -> None:
        if not data_document.trade:
            return

        for trade in data_document.trade:
            if not trade.swap:
                continue

            effective_dates = []
            for stream in trade.swap.swap_stream:
                cp_dates = stream.calculation_period_dates
                if (
                    cp_dates
                    and cp_dates.effective_date
                    and cp_dates.effective_date.unadjusted_date
                ):
                    effective_dates.append(
                        (
                            stream.id,
                            cp_dates.effective_date.unadjusted_date.value.to_date(),
                        )
                    )

            if len(effective_dates) > 1:
                base_stream_id, base_date = effective_dates[0]
                for stream_id, eff_date in effective_dates[1:]:
                    if eff_date != base_date:
                        raise DateMismatchError(
                            f"Validation failed for rule [{self.rule_id}]: "
                            f"Mismatched unadjusted effectiveDate found between legs. "
                            f"swapStream {base_stream_id} has {base_date}, "
                            f"but swapStream {stream_id} has {eff_date}."
                        )


class Ird22Rule(ValidationRule):
    """IRD-22 ルール: 複数レッグ間の調整前終了日の同一性チェック。

    スワップ取引に含まれるすべてのスワップストリーム（レッグ）間で、
    調整前の終了日（terminationDate.unadjustedDate）が一致していることを検証します。
    """

    @property
    def rule_id(self) -> str:
        return "ird-22"

    def validate(self, data_document: DataDocument) -> None:
        if not data_document.trade:
            return

        for trade in data_document.trade:
            if not trade.swap:
                continue

            termination_dates = []
            for stream in trade.swap.swap_stream:
                cp_dates = stream.calculation_period_dates
                if (
                    cp_dates
                    and cp_dates.termination_date
                    and cp_dates.termination_date.unadjusted_date
                ):
                    termination_dates.append(
                        (
                            stream.id,
                            cp_dates.termination_date.unadjusted_date.value.to_date(),
                        )
                    )

            if len(termination_dates) > 1:
                base_stream_id, base_date = termination_dates[0]
                for stream_id, term_date in termination_dates[1:]:
                    if term_date != base_date:
                        raise DateMismatchError(
                            f"Validation failed for rule [{self.rule_id}]: "
                            f"Mismatched unadjusted terminationDate found between legs. "
                            f"swapStream {base_stream_id} has {base_date}, "
                            f"but swapStream {stream_id} has {term_date}."
                        )


class Ird14Rule(ValidationRule):
    """IRD-14 ルール: 有効日と終了日の前後関係チェック。

    スワップストリームにおいて、調整前の終了日（terminationDate.unadjustedDate）が
    調整前の有効日（effectiveDate.unadjustedDate）より前の日付になっていないことを検証します。
    """

    @property
    def rule_id(self) -> str:
        return "ird-14"

    def validate(self, data_document: DataDocument) -> None:
        if not data_document.trade:
            return

        for trade in data_document.trade:
            if not trade.swap:
                continue

            for stream in trade.swap.swap_stream:
                cp_dates = stream.calculation_period_dates
                if (
                    not cp_dates
                    or not cp_dates.effective_date
                    or not cp_dates.effective_date.unadjusted_date
                    or not cp_dates.termination_date
                    or not cp_dates.termination_date.unadjusted_date
                ):
                    continue

                eff_date = cp_dates.effective_date.unadjusted_date.value.to_date()
                term_date = cp_dates.termination_date.unadjusted_date.value.to_date()

                if term_date < eff_date:
                    raise DateMismatchError(
                        f"Validation failed for rule [{self.rule_id}]: "
                        f"terminationDate ({term_date}) cannot be before effectiveDate ({eff_date}) "
                        f"in swapStream ID: {stream.id}."
                    )
