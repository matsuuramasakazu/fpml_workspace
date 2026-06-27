import dataclasses
from typing import Any

from fpml.confirmation import DataDocument
from src.validators.base import ValidationRule
from src.validators.exceptions import (
    InvalidConfigurationError,
    MissingRequiredFieldError,
)
from src.validators.rules.choice_constraints import CHOICE_CONSTRAINTS


class ChoiceAndMultiplicityRule(ValidationRule):
    """XSD由来のChoice制約および多重度制約を検証するルール。

    オブジェクトを再帰的に走査し、メタデータに定義された多重度（min_occurs / max_occurs）と、
    自動生成された CHOICE_CONSTRAINTS に基づいてChoice排他制約をチェックします。
    """

    @property
    def rule_id(self) -> str:
        return "choice-and-multiplicity"

    def validate(self, data_document: DataDocument) -> None:
        self._validate_object(data_document, "DataDocument")

    def _validate_object(self, obj: Any, path: str) -> None:
        if not dataclasses.is_dataclass(obj):
            return

        class_name = obj.__class__.__name__

        # 1. Choice制約のチェック
        if class_name in CHOICE_CONSTRAINTS:
            for constraint in CHOICE_CONSTRAINTS[class_name]:
                options = constraint["options"]
                required = constraint["required"]

                # 設定されている choice 対象フィールドの特定
                # 各オプションに対して、そのオプションに含まれるフィールドで値が設定されているものを集める
                val_all = set()
                for opt in options:
                    for field_name in opt:
                        val = getattr(obj, field_name, None)
                        if val is not None:
                            # リスト型の場合は空でないことも条件
                            if isinstance(val, list) and len(val) == 0:
                                continue
                            val_all.add(field_name)

                if len(val_all) == 0:
                    if required:
                        raise MissingRequiredFieldError(
                            f"Validation failed for rule [{self.rule_id}]: "
                            f"Required choice in {path} ({class_name}) is missing. "
                            f"One of the following options must be set: {options}"
                        )
                else:
                    # 設定されている値の集合 (val_all) が、いずれかのオプションに完全に包含されているかチェック
                    valid_option_found = False
                    for opt in options:
                        if val_all.issubset(set(opt)):
                            valid_option_found = True
                            break

                    if not valid_option_found:
                        raise InvalidConfigurationError(
                            f"Validation failed for rule [{self.rule_id}]: "
                            f"Choice constraint violated in {path} ({class_name}). "
                            f"Conflicting fields are set: {list(val_all)}. "
                            f"Allowed mutually exclusive options are: {options}"
                        )

        # 2. 各フィールドの多重度チェックと再帰走査
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            min_occurs = f.metadata.get("min_occurs")
            max_occurs = f.metadata.get("max_occurs")

            # 多重度チェック
            if isinstance(val, list):
                actual_count = len(val)
                if min_occurs is not None and actual_count < min_occurs:
                    raise MissingRequiredFieldError(
                        f"Validation failed for rule [{self.rule_id}]: "
                        f"Field '{f.name}' in {path} ({class_name}) requires at least {min_occurs} elements, "
                        f"but got {actual_count}."
                    )
                if max_occurs is not None and max_occurs != "unbounded":
                    if actual_count > int(max_occurs):
                        raise InvalidConfigurationError(
                            f"Validation failed for rule [{self.rule_id}]: "
                            f"Field '{f.name}' in {path} ({class_name}) allows at most {max_occurs} elements, "
                            f"but got {actual_count}."
                        )
            else:
                # 非リスト型の必須チェック (min_occursが明示的に1、またはデフォルト値がなくかつChoice対象外でNoneの場合)
                is_choice_field = False
                if class_name in CHOICE_CONSTRAINTS:
                    for constraint in CHOICE_CONSTRAINTS[class_name]:
                        for opt in constraint["options"]:
                            if f.name in opt:
                                is_choice_field = True
                                break

                # choice対象外であり、かつデフォルト値がなく、値がNoneの場合は必須エラー
                if not is_choice_field and val is None:
                    is_required = False
                    if min_occurs is not None and min_occurs >= 1:
                        is_required = True
                    elif (
                        f.default is dataclasses.MISSING
                        and f.default_factory is dataclasses.MISSING
                    ):
                        is_required = True

                    if is_required:
                        raise MissingRequiredFieldError(
                            f"Validation failed for rule [{self.rule_id}]: "
                            f"Required field '{f.name}' in {path} ({class_name}) is missing."
                        )

            # 再帰的に子オブジェクトを走査
            if val is not None:
                if isinstance(val, list):
                    for i, item in enumerate(val):
                        self._validate_object(item, f"{path}.{f.name}[{i}]")
                else:
                    self._validate_object(val, f"{path}.{f.name}")
