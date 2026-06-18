class FpmlValidationError(Exception):
    """すべてのFpMLバリデーションエラーの基底例外。"""

    pass


class DateMismatchError(FpmlValidationError):
    """有効日と終了日の矛盾、またはレグ間での不一致などの日付系エラー。"""

    pass


class MissingRequiredFieldError(FpmlValidationError):
    """キャッシュフロー生成に必要な必須パラメータの欠落エラー。"""

    pass


class InvalidConfigurationError(FpmlValidationError):
    """頻度の不整合や金利定義重複などの設定不整合エラー。"""

    pass
