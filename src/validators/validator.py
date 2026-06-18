import logging
from typing import List

from fpml.confirmation import DataDocument
from src.validators.base import ValidationRule
from src.validators.rules.ird_rules import (
    Ird1Rule,
    Ird10Rule,
    Ird11Rule,
    Ird12Rule,
    Ird14Rule,
    Ird21Rule,
    Ird22Rule,
)

logger = logging.getLogger("expand_cashflows")


class FpmlValidator:
    """FpMLのバリデーションを実行するクラス。

    登録された ValidationRule を順次実行し、エラーが発生した場合はロギングして例外をスローします。
    """

    def __init__(self, rules: List[ValidationRule] = None):
        """
        Args:
            rules: 検証に使用するルールのリスト。Noneの場合はデフォルトのルールセットが使用されます。
        """
        if rules is None:
            self._rules = [
                Ird1Rule(),
                Ird10Rule(),
                Ird11Rule(),
                Ird12Rule(),
                Ird14Rule(),
                Ird21Rule(),
                Ird22Rule(),
            ]
        else:
            self._rules = rules

    def validate(self, data_document: DataDocument) -> None:
        """DataDocumentに対してすべての登録されたルールを実行します。

        Args:
            data_document: 検証対象 of DataDocument

        Raises:
            FpmlValidationError: バリデーションに失敗した場合
        """
        for rule in self._rules:
            try:
                rule.validate(data_document)
            except Exception as e:
                logger.error(f"Validation failed for rule [{rule.rule_id}]: {e}")
                raise e
