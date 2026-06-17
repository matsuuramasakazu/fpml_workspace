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
