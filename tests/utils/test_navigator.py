from dataclasses import dataclass
from typing import List, Optional

import pytest

from src.utils.navigator import SafeNavigator


# テスト用のネストされたデータクラスを定義
@dataclass
class CalculationPeriodAmount:
    currency: Optional[str] = None
    amount: Optional[float] = None


@dataclass
class SwapStream:
    calculation_period_amount: Optional[CalculationPeriodAmount] = None


@dataclass
class Swap:
    swap_stream: Optional[List[SwapStream]] = None


@dataclass
class Trade:
    swap: Optional[Swap] = None


def test_safe_navigator_success():
    # 全てのデータが揃っている正常系テスト
    amount = CalculationPeriodAmount(currency="JPY", amount=1000000.0)
    stream = SwapStream(calculation_period_amount=amount)
    swap = Swap(swap_stream=[stream])
    trade = Trade(swap=swap)

    nav = SafeNavigator(trade)

    # 正常な属性およびインデックスアクセス
    assert nav.swap.value == swap
    assert nav.swap.swap_stream.value == [stream]
    assert nav.swap.swap_stream[0].value == stream
    assert nav.swap.swap_stream[0].calculation_period_amount.value == amount
    assert nav.swap.swap_stream[0].calculation_period_amount.currency.value == "JPY"
    assert nav.swap.swap_stream[0].calculation_period_amount.amount.value == 1000000.0

    # 正常系では失敗情報はNoneまたは空
    assert nav.swap.swap_stream[0].calculation_period_amount.failed_at is None
    assert nav.swap.swap_stream[0].calculation_period_amount.last_valid_object is None


def test_safe_navigator_none_middle():
    # 途中の要素がNoneである場合
    swap = Swap(swap_stream=None)  # swap_streamがNone
    trade = Trade(swap=swap)

    nav = SafeNavigator(trade)
    endpoint = nav.swap.swap_stream[0].calculation_period_amount.currency

    # 途中でNoneがあるので、最終値はNone
    assert endpoint.value is None

    # 最初にNoneになったのは swap_stream 属性
    assert endpoint.failed_at == "swap_stream"
    # その時点での親オブジェクトは swap
    assert endpoint.last_valid_object == swap
    # パスが正しく構築されていること
    assert (
        endpoint.failed_path == "swap.swap_stream[0].calculation_period_amount.currency"
    )


def test_safe_navigator_index_out_of_range():
    # リストが空でインデックス範囲外になる場合
    swap = Swap(swap_stream=[])  # 空リスト
    trade = Trade(swap=swap)

    nav = SafeNavigator(trade)
    endpoint = nav.swap.swap_stream[0].calculation_period_amount

    # 範囲外なので値はNone
    assert endpoint.value is None
    # 最初に失敗したのはインデックス 0
    assert endpoint.failed_at == 0
    # 最後の有効な親オブジェクトは swap_stream (空リスト)
    assert endpoint.last_valid_object == []
    # パスが正しく構築されていること
    assert endpoint.failed_path == "swap.swap_stream[0].calculation_period_amount"


def test_safe_navigator_attribute_error():
    # 定義されていない属性（タイポ）へのアクセスはAttributeErrorになるべき
    trade = Trade(swap=Swap(swap_stream=[]))
    nav = SafeNavigator(trade)

    with pytest.raises(AttributeError) as exc_info:
        _ = nav.swapppp  # タイポ
    assert "object has no attribute 'swapppp'" in str(exc_info.value)


def test_safe_navigator_type_error_for_non_indexable():
    # インデックスに対応していないオブジェクトにインデックスアクセスした場合
    trade = Trade(swap=Swap(swap_stream=[]))
    nav = SafeNavigator(trade)

    with pytest.raises(TypeError) as exc_info:
        # swapはリストではないので[0]はTypeErrorになるべき
        _ = nav.swap[0]
    assert "is not indexable" in str(exc_info.value)


def test_safe_navigator_root_is_none():
    # ルートオブジェクト自体がNoneの場合
    nav = SafeNavigator(None)
    endpoint = nav.swap.swap_stream[0]

    assert endpoint.value is None
    # ルート自体がNoneの場合は failed_at, last_valid_object ともに None
    assert endpoint.failed_at is None
    assert endpoint.last_valid_object is None
    assert endpoint.failed_path == "swap.swap_stream[0]"
