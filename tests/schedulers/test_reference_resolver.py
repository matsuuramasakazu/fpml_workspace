from dataclasses import dataclass, field

import pytest

from fpml.confirmation import DataDocument, Party, PartyReference
from src.schedulers.reference_resolver import ReferenceResolver


@dataclass
class DummyChild:
    id: str | None = None
    value: str = ""


@dataclass
class DummyRoot:
    id: str | None = None
    child: DummyChild | None = None
    children: list[DummyChild] = field(default_factory=list)


def test_reference_resolver_dummy_dataclass():
    # ダミーのデータクラス構造を用いたテスト
    child1 = DummyChild(id="c1", value="hello")
    child2 = DummyChild(id="c2", value="world")
    root = DummyRoot(id="r1", child=child1, children=[child2])

    resolver = ReferenceResolver(root)

    # 疑似的な参照オブジェクト
    @dataclass
    class DummyRef:
        href: str

    assert resolver.resolve(DummyRef(href="c1")) is child1
    assert resolver.resolve(DummyRef(href="c2")) is child2
    assert resolver.resolve(DummyRef(href="r1")) is root

    with pytest.raises(KeyError):
        resolver.resolve(DummyRef(href="nonexistent"))


def test_reference_resolver_fpml_objects():
    # 実際のFpMLモデルを用いたテスト
    party1 = Party(id="partyA")
    party2 = Party(id="partyB")

    doc = DataDocument(fpml_version="5-12", party=[party1, party2])

    resolver = ReferenceResolver(doc)

    ref = PartyReference(href="partyA")
    assert resolver.resolve(ref) is party1

    ref_b = PartyReference(href="partyB")
    assert resolver.resolve(ref_b) is party2

    with pytest.raises(KeyError):
        resolver.resolve(PartyReference(href="partyC"))


def test_reference_resolver_lazy_evaluation():
    # 遅延評価の検証
    child1 = DummyChild(id="c1", value="hello")
    child2 = DummyChild(id="c2", value="world")
    root = DummyRoot(id="r1", child=child1, children=[child2])

    resolver = ReferenceResolver(root)

    @dataclass
    class DummyRef:
        href: str

    # 初期化時点ではキャッシュは空
    assert len(resolver._id_map) == 0

    # c1を解決すると、r1とc1まで走査される
    # (走査順序は rootのid("r1") -> child("c1") -> children[0]("c2"))
    # まず "r1" が見つかり、次に "c1" が見つかる
    assert resolver.resolve(DummyRef(href="c1")) is child1
    assert "r1" in resolver._id_map
    assert "c1" in resolver._id_map
    assert "c2" not in resolver._id_map  # c2はまだ走査されていない

    # c2を解決すると、c2も走査されキャッシュに載る
    assert resolver.resolve(DummyRef(href="c2")) is child2
    assert "c2" in resolver._id_map


def test_reference_resolver_duplicate_id_detection():
    # 重複IDの検出テスト
    child1 = DummyChild(id="dup", value="first")
    child2 = DummyChild(id="dup", value="second")  # 重複ID
    root = DummyRoot(id="r1", child=child1, children=[child2])

    resolver = ReferenceResolver(root)

    @dataclass
    class DummyRef:
        href: str

    # 1つ目の "dup" は解決できる（この時点では2つ目の重複は走査されていないため）
    assert resolver.resolve(DummyRef(href="dup")) is child1

    # さらに走査を進める必要のある操作（存在しないIDの解決）を行うと、
    # 走査中に2つ目の "dup" に遭遇して ValueError が送出される
    with pytest.raises(ValueError) as excinfo:
        resolver.resolve(DummyRef(href="nonexistent"))
    assert "Duplicate ID 'dup' found in document" in str(excinfo.value)
