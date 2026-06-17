import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from src.cashflow_expander import CashflowExpander


def test_basic_pipeline_roundtrip():
    # 入力ファイルパスの設定 (ird-ex01-vanilla-swap.xml)
    input_path = (
        Path(__file__).parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    assert input_path.exists(), f"Input file not found: {input_path}"

    config_dir = Path(__file__).parent.parent / "config"

    # 一時出力ファイルの準備
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output_roundtrip.xml"

        # 基本パイプラインの実行
        result = CashflowExpander.expand_cashflows(
            str(input_path), str(output_file), str(config_dir)
        )

        # 戻り値の確認
        assert result is True

        # 出力ファイルの存在確認
        assert output_file.exists()

        # 出力されたXMLがパース可能であることを検証
        try:
            tree = ET.parse(output_file)
            root = tree.getroot()
            # FpMLのNamespaceは "http://www.fpml.org/FpML-5/confirmation"
            assert "dataDocument" in root.tag
        except ET.ParseError as e:
            assert False, f"Failed to parse generated XML: {e}"


def test_pipeline_cashflow_expansion():
    """E2E test to verify cashflow expansion is executed and XML is schema-conformant."""
    from datetime import date
    from decimal import Decimal

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

    input_path = (
        Path(__file__).parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    assert input_path.exists(), f"Input file not found: {input_path}"

    config_dir = Path(__file__).parent.parent / "config"

    # 一時出力ファイルの準備
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output_expanded.xml"

        # キャッシュフロー展開の実行
        result = CashflowExpander.expand_cashflows(
            str(input_path), str(output_file), str(config_dir)
        )

        assert result is True
        assert output_file.exists()

        # 出力されたXMLをパースして中身を検証
        parser = XmlParser()
        doc = parser.from_path(output_file, DataDocument)

        swap = doc.trade[0].swap

        # 各Legにcashflowsが追加されているか
        for stream in swap.swap_stream:
            assert stream.cashflows is not None
            assert stream.cashflows.cashflows_match_parameters is True
            assert len(stream.cashflows.payment_calculation_period) > 0

        # 浮動レグの検証
        floating_stream = swap.swap_stream[0]
        p1_float = floating_stream.cashflows.payment_calculation_period[0]
        calc1_float = p1_float.calculation_period[0]
        assert calc1_float.floating_rate_definition is not None
        assert len(calc1_float.floating_rate_definition.rate_observation) > 0
        obs1 = calc1_float.floating_rate_definition.rate_observation[0]
        assert obs1.reset_date.to_date() == date(1994, 12, 14)
        assert obs1.adjusted_fixing_date.to_date() == date(1994, 12, 12)

        # 固定レグの検証
        fixed_stream = swap.swap_stream[1]
        p1_fixed = fixed_stream.cashflows.payment_calculation_period[0]
        calc1_fixed = p1_fixed.calculation_period[0]
        assert calc1_fixed.fixed_rate == Decimal("0.06")
        assert calc1_fixed.notional_amount == Decimal("50000000.00")
