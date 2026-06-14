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
