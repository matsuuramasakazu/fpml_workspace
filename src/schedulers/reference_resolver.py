import dataclasses
from typing import Any, Dict


class ReferenceResolver:
    """FpMLモデル内のhref参照を解決するためのリゾルバー。"""

    def __init__(self, document: Any):
        """指定されたFpMLドキュメント（または任意のツリー）をトラバースしてidインデックスを作成します。"""
        self._id_map: Dict[str, Any] = {}
        self._build_index(document)

    def _build_index(self, obj: Any) -> None:
        """再帰的にオブジェクトを探索し、id属性を持つものをマップに登録します。"""
        if obj is None:
            return

        # 基本的なオブジェクト（文字列、数値、真偽値等）は探索をスキップ
        if isinstance(obj, (str, int, float, bool, bytes)):
            return

        if dataclasses.is_dataclass(obj):
            # id属性のチェック
            obj_id = getattr(obj, "id", None)
            if obj_id is not None:
                self._id_map[obj_id] = obj

            # フィールドの再帰的探索
            for field_def in dataclasses.fields(obj):
                val = getattr(obj, field_def.name)
                self._build_index(val)
        elif isinstance(obj, list):
            for item in obj:
                self._build_index(item)
        elif isinstance(obj, dict):
            for item in obj.values():
                self._build_index(item)

    def resolve(self, reference: Any) -> Any:
        """ReferenceAbstractオブジェクトのhrefを元に対象オブジェクトを返します。"""
        # 実際のFpMLモデル以外のダミーRefオブジェクトも通すため、href属性を持つかチェックする
        href = getattr(reference, "href", None)
        if href is None:
            raise ValueError("Reference has no href attribute")

        if href not in self._id_map:
            raise KeyError(f"Reference ID '{href}' could not be resolved.")

        return self._id_map[href]
