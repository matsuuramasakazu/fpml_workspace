from abc import ABC, abstractmethod

from fpml.confirmation import DataDocument


class ValidationRule(ABC):
    """すべてのFpMLバリデーションルールが継承する基底クラス。"""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """ルールID（例: 'ird-10'）を返します。"""
        pass

    @abstractmethod
    def validate(self, data_document: DataDocument) -> None:
        """DataDocumentの検証を行います。違反がある場合は FpmlValidationError を送出します。"""
        pass
