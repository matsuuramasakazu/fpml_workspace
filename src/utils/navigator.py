from typing import Any, List, Optional, Union


class SafeNavigator:
    """FpMLのデータクラスなどの深い階層構造に安全にアクセスするためのプロキシクラス。"""

    __slots__ = (
        "_obj",
        "_path_segments",
        "_parent_navigator",
        "_last_valid_object",
        "_failed_at",
    )

    def __init__(
        self,
        obj: Any,
        path_segments: Optional[List[Union[str, int]]] = None,
        parent_navigator: Optional["SafeNavigator"] = None,
        last_valid_object: Any = None,
        failed_at: Optional[Union[str, int]] = None,
    ):
        self._obj = obj
        self._path_segments = path_segments or []
        self._parent_navigator = parent_navigator
        self._last_valid_object = last_valid_object
        self._failed_at = failed_at

    @property
    def value(self) -> Any:
        """ラップされている実際の値を返します。"""
        return self._obj

    @property
    def failed_path(self) -> str:
        """アクセスしたパスの文字列表現を返します（例: 'swap.swapStream[0].calculationPeriodAmount'）。"""
        result = []
        for i, seg in enumerate(self._path_segments):
            if isinstance(seg, int):
                result.append(f"[{seg}]")
            else:
                if i > 0:
                    result.append(".")
                result.append(seg)
        return "".join(result)

    @property
    def failed_segments(self) -> List[Union[str, int]]:
        """アクセスしたパスのセグメントのリストを返します。"""
        return self._path_segments

    @property
    def failed_at(self) -> Optional[Union[str, int]]:
        """最初に None または範囲外になった属性名またはインデックスを返します。"""
        return self._failed_at

    @property
    def last_valid_object(self) -> Any:
        """None に遭遇する直前の、実在した最後の親オブジェクトを返します。"""
        return self._last_valid_object

    def __getattr__(self, name: str) -> "SafeNavigator":
        if name.startswith("_"):
            raise AttributeError(name)

        current_path = self._path_segments + [name]

        if self._obj is None:
            return SafeNavigator(
                obj=None,
                path_segments=current_path,
                parent_navigator=self,
                last_valid_object=self._last_valid_object,
                failed_at=self._failed_at,
            )

        try:
            val = getattr(self._obj, name)
        except AttributeError:
            raise AttributeError(
                f"'{type(self._obj).__name__}' object has no attribute '{name}'"
            )

        if val is None:
            return SafeNavigator(
                obj=None,
                path_segments=current_path,
                parent_navigator=self,
                last_valid_object=self._obj,
                failed_at=name,
            )

        return SafeNavigator(
            obj=val,
            path_segments=current_path,
            parent_navigator=self,
            last_valid_object=None,
            failed_at=None,
        )

    def __getitem__(self, index: Union[int, slice]) -> "SafeNavigator":
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")

        current_path = self._path_segments + [index]

        if self._obj is None:
            return SafeNavigator(
                obj=None,
                path_segments=current_path,
                parent_navigator=self,
                last_valid_object=self._last_valid_object,
                failed_at=self._failed_at,
            )

        if not hasattr(self._obj, "__getitem__") or isinstance(self._obj, (str, bytes)):
            raise TypeError(
                f"Object of type '{type(self._obj).__name__}' is not indexable"
            )

        try:
            val = self._obj[index]
        except IndexError:
            return SafeNavigator(
                obj=None,
                path_segments=current_path,
                parent_navigator=self,
                last_valid_object=self._obj,
                failed_at=index,
            )

        if val is None:
            return SafeNavigator(
                obj=None,
                path_segments=current_path,
                parent_navigator=self,
                last_valid_object=self._obj,
                failed_at=index,
            )

        return SafeNavigator(
            obj=val,
            path_segments=current_path,
            parent_navigator=self,
            last_valid_object=None,
            failed_at=None,
        )

    def __repr__(self) -> str:
        return f"SafeNavigator(value={self._obj!r}, path={self.failed_path})"
