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


def test_pipeline_cross_currency_principal_exchange():
    """E2E test to verify cross-currency swap cashflow and principal exchange expansion using ird-ex052."""
    from datetime import date
    from decimal import Decimal

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

    input_path = (
        Path(__file__).parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex052-xccy-swap-OIS.xml"
    )
    assert input_path.exists(), f"Input file not found: {input_path}"

    config_dir = Path(__file__).parent.parent / "config"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output_xccy.xml"

        result = CashflowExpander.expand_cashflows(
            str(input_path), str(output_file), str(config_dir)
        )

        assert result is True
        assert output_file.exists()

        parser = XmlParser()
        doc = parser.from_path(output_file, DataDocument)

        swap = doc.trade[0].swap
        assert len(swap.swap_stream) == 2

        # 最初のストリーム: USD Floating Leg
        usd_stream = swap.swap_stream[0]
        assert usd_stream.cashflows is not None
        assert usd_stream.cashflows.cashflows_match_parameters is True
        assert len(usd_stream.cashflows.principal_exchange) == 2

        usd_init = usd_stream.cashflows.principal_exchange[0]
        assert usd_init.unadjusted_principal_exchange_date.to_date() == date(
            2018, 9, 10
        )
        assert usd_init.adjusted_principal_exchange_date.to_date() == date(2018, 9, 10)
        assert usd_init.principal_exchange_amount == Decimal("-121700000")

        usd_final = usd_stream.cashflows.principal_exchange[1]
        assert usd_final.unadjusted_principal_exchange_date.to_date() == date(
            2023, 9, 10
        )
        assert usd_final.adjusted_principal_exchange_date.to_date() == date(2023, 9, 11)
        assert usd_final.principal_exchange_amount == Decimal("121700000")

        # 2番目のストリーム: JPY Fixed Leg
        jpy_stream = swap.swap_stream[1]
        assert jpy_stream.cashflows is not None
        assert jpy_stream.cashflows.cashflows_match_parameters is True
        assert len(jpy_stream.cashflows.principal_exchange) == 2

        jpy_init = jpy_stream.cashflows.principal_exchange[0]
        assert jpy_init.unadjusted_principal_exchange_date.to_date() == date(
            2018, 9, 10
        )
        assert jpy_init.adjusted_principal_exchange_date.to_date() == date(2018, 9, 10)
        assert jpy_init.principal_exchange_amount == Decimal("-100500000")

        jpy_final = jpy_stream.cashflows.principal_exchange[1]
        assert jpy_final.unadjusted_principal_exchange_date.to_date() == date(
            2023, 9, 10
        )
        assert jpy_final.principal_exchange_amount == Decimal("100500000")


def test_pipeline_fx_linked_notional_swap():
    """E2E test to verify FX-linked notional swap cashflow expansion using ird-ex25."""
    from datetime import date

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

    input_path = (
        Path(__file__).parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex25-fxnotional-swap.xml"
    )
    assert input_path.exists(), f"Input file not found: {input_path}"

    config_dir = Path(__file__).parent.parent / "config"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output_fxnotional.xml"

        result = CashflowExpander.expand_cashflows(
            str(input_path), str(output_file), str(config_dir)
        )

        assert result is True
        assert output_file.exists()

        parser = XmlParser()
        doc = parser.from_path(output_file, DataDocument)

        swap = doc.trade[0].swap
        assert len(swap.swap_stream) == 2

        # 1番目のストリーム JPY 固定レグ (Fixed)
        fixed_stream = swap.swap_stream[0]
        assert fixed_stream.cashflows is not None
        assert len(fixed_stream.cashflows.payment_calculation_period) > 0

        # 2番目のストリーム USD 浮動レグ (Floating with FX-Linked Notional)
        float_stream = swap.swap_stream[1]
        assert float_stream.cashflows is not None

        # 期数チェック (5年間、3ヶ月ごと = 20期)
        periods = float_stream.cashflows.payment_calculation_period
        assert len(periods) == 20

        # 1期目 (2006-01-11 から 2006-04-11)
        p1 = periods[0]
        calc1 = p1.calculation_period[0]
        assert calc1.notional_amount is None
        assert calc1.fx_linked_notional_amount is not None
        assert calc1.fx_linked_notional_amount.reset_date.to_date() == date(2006, 1, 11)
        assert (
            calc1.fx_linked_notional_amount.adjusted_fx_spot_fixing_date.to_date()
            == date(2006, 1, 9)
        )

        # 2期目 (2006-04-11 から 2006-07-11)
        p2 = periods[1]
        calc2 = p2.calculation_period[0]
        assert calc2.notional_amount is None
        assert calc2.fx_linked_notional_amount is not None
        assert calc2.fx_linked_notional_amount.reset_date.to_date() == date(2006, 4, 11)
        assert (
            calc2.fx_linked_notional_amount.adjusted_fx_spot_fixing_date.to_date()
            == date(2006, 4, 7)
        )


def test_pipeline_rfr_observation_shift_ex44():
    """E2E test for RFR compound swap with Observation Shift using ird-ex44."""
    from datetime import date

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

    input_path = (
        Path(__file__).parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex44-rfr-compound-swap-obs-period-shift.xml"
    )
    assert input_path.exists(), f"Input file not found: {input_path}"

    config_dir = Path(__file__).parent.parent / "config"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output_ex44.xml"

        result = CashflowExpander.expand_cashflows(
            str(input_path), str(output_file), str(config_dir)
        )

        assert result is True
        assert output_file.exists()

        parser = XmlParser()
        doc = parser.from_path(output_file, DataDocument)

        swap = doc.trade[0].swap
        assert len(swap.swap_stream) == 2

        # 最初のレグ (Floating EONIA Leg)
        float_stream = swap.swap_stream[0]
        assert float_stream.cashflows is not None
        assert len(float_stream.cashflows.payment_calculation_period) == 36

        # 第1期の支払日 (2021-08-16 〜 2021-09-16)
        # 終了日 2021-09-16 (木) + 1営業日 (EUTA) = 2021-09-17 (金)
        p1 = float_stream.cashflows.payment_calculation_period[0]
        assert p1.adjusted_payment_date.to_date() == date(2021, 9, 17)

        # 第1期の計算期間と金利観測
        calc1 = p1.calculation_period[0]
        assert calc1.adjusted_start_date.to_date() == date(2021, 8, 16)
        assert calc1.adjusted_end_date.to_date() == date(2021, 9, 16)
        assert calc1.day_count_year_fraction is not None

        floating_def = calc1.floating_rate_definition
        assert floating_def is not None
        # 営業日数は 23日 (TARGET カレンダー)
        assert len(floating_def.rate_observation) == 23

        obs1 = floating_def.rate_observation[0]
        assert obs1.reset_date.to_date() == date(2021, 8, 16)
        # Shift 5営業日: 2021-08-16 の5営業日前 -> 2021-08-09
        assert obs1.adjusted_fixing_date.to_date() == date(2021, 8, 9)
        assert obs1.observation_weight == 1


def test_pipeline_rfr_lookback_ex45():
    """E2E test for RFR compound swap with Lookback using ird-ex45."""
    from datetime import date

    from xsdata.formats.dataclass.parsers import XmlParser

    from fpml.confirmation import DataDocument

    input_path = (
        Path(__file__).parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex45-rfr-compound-swap-lookback.xml"
    )
    assert input_path.exists(), f"Input file not found: {input_path}"

    config_dir = Path(__file__).parent.parent / "config"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output_ex45.xml"

        result = CashflowExpander.expand_cashflows(
            str(input_path), str(output_file), str(config_dir)
        )

        assert result is True
        assert output_file.exists()

        parser = XmlParser()
        doc = parser.from_path(output_file, DataDocument)

        swap = doc.trade[0].swap
        assert len(swap.swap_stream) == 2

        # 最初のレグ (Floating EONIA Leg with Lookback)
        float_stream = swap.swap_stream[0]
        assert float_stream.cashflows is not None
        assert len(float_stream.cashflows.payment_calculation_period) == 36

        # 第1期の支払日: 2021-09-17 (金)
        p1 = float_stream.cashflows.payment_calculation_period[0]
        assert p1.adjusted_payment_date.to_date() == date(2021, 9, 17)

        # 第1期の計算期間と金利観測
        calc1 = p1.calculation_period[0]
        floating_def = calc1.floating_rate_definition
        assert floating_def is not None
        assert len(floating_def.rate_observation) == 23

        obs1 = floating_def.rate_observation[0]
        assert obs1.reset_date.to_date() == date(2021, 8, 16)
        # Lookback 5営業日: 2021-08-16 の5営業日前 -> 2021-08-09
        assert obs1.adjusted_fixing_date.to_date() == date(2021, 8, 9)
        assert obs1.observation_weight == 1
