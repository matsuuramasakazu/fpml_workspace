import dataclasses
from typing import Any, Dict, Generator, Tuple


class ReferenceResolver:
    """FpMLモデル内のhref参照を解決するためのリゾルバー。"""

    def __init__(self, document: Any):
        """指定されたFpMLドキュメント（または任意のツリー）をトラバースする準備を行います。"""
        self._id_map: Dict[str, Any] = {}
        self._generator = self._traverse(document)
        self._generator_finished = False

    def _traverse(self, obj: Any) -> Generator[Tuple[str, Any], None, None]:
        """再帰的にオブジェクトを探索し、id属性を持つものをyieldします。"""
        if obj is None:
            return

        # 基本的なオブジェクト（文字列、数値、真偽値等）は探索をスキップ
        if isinstance(obj, (str, int, float, bool, bytes)):
            return

        if dataclasses.is_dataclass(obj):
            # id属性のチェック
            obj_id = getattr(obj, "id", None)
            if obj_id is not None:
                yield obj_id, obj

            # フィールドの再帰的探索
            for field_def in dataclasses.fields(obj):
                val = getattr(obj, field_def.name)
                yield from self._traverse(val)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._traverse(item)
        elif isinstance(obj, dict):
            for item in obj.values():
                yield from self._traverse(item)

    def resolve(self, reference: Any) -> Any:
        """ReferenceAbstractオブジェクトのhrefを元に対象オブジェクトを返します。"""
        # 実際のFpMLモデル以外のダミーRefオブジェクトも通すため、href属性を持つかチェックする
        href = getattr(reference, "href", None)
        if href is None:
            raise ValueError("Reference has no href attribute")

        # キャッシュにあれば即時返却
        if href in self._id_map:
            return self._id_map[href]

        # キャッシュになく、ジェネレータが終了していなければ探索を進める
        if not self._generator_finished:
            try:
                while href not in self._id_map:
                    obj_id, obj = next(self._generator)
                    if obj_id in self._id_map:
                        raise ValueError(f"Duplicate ID '{obj_id}' found in document.")
                    self._id_map[obj_id] = obj
                return self._id_map[href]
            except StopIteration:
                self._generator_finished = True

        raise KeyError(f"Reference ID '{href}' could not be resolved.")
