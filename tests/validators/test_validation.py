from decimal import Decimal
from pathlib import Path

import pytest
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.models.datatype import XmlDate

from fpml.confirmation import (
    DataDocument,
    RollConventionEnum,
    Schedule,
)
from src.validators import FpmlValidator
from src.validators.exceptions import (
    DateMismatchError,
    InvalidConfigurationError,
    MissingRequiredFieldError,
)
from src.validators.rules.ird_rules import (
    Ird1Rule,
    Ird10Rule,
    Ird11Rule,
    Ird12Rule,
    Ird14Rule,
    Ird21Rule,
    Ird22Rule,
)


def get_base_doc() -> DataDocument:
    # ird-ex01-vanilla-swap.xml をベースとしてパースする
    xml_path = (
        Path(__file__).parent.parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    parser = XmlParser()
    return parser.from_path(xml_path, DataDocument)


def test_ird_1_rule_valid_vanilla_swap():
    # 正常な vanilla-swap (固定と浮動レグがあり、浮動レグには resetDates がある) は通過する
    doc = get_base_doc()
    rule = Ird1Rule()
    # 正常データなので例外が発生しないこと
    rule.validate(doc)


def test_ird_1_rule_invalid_floating_leg_missing_reset_dates():
    # 浮動レグ（O/N RFR以外）で resetDates を削除した場合、MissingRequiredFieldError がスローされること
    doc = get_base_doc()
    # ird-ex01 の最初のレグは浮動レグ (floatingRateCalculation がある)
    floating_stream = doc.trade[0].swap.swap_stream[0]
    assert (
        floating_stream.calculation_period_amount.calculation.floating_rate_calculation
        is not None
    )

    # resetDates を None にして、O/N RFR でもないように設定
    floating_stream.reset_dates = None
    floating_stream.calculation_period_amount.calculation.floating_rate_calculation.calculation_parameters = None

    rule = Ird1Rule()
    with pytest.raises(MissingRequiredFieldError) as excinfo:
        rule.validate(doc)

    assert "resetDates" in str(excinfo.value)
    assert rule.rule_id == "ird-1"


def test_ird_10_rule_valid():
    # rollConvention = 14 で開始日が14日の場合は通過する
    doc = get_base_doc()
    rule = Ird10Rule()
    rule.validate(doc)


def test_ird_10_rule_invalid_mismatch():
    # rollConvention = 15 で開始日が14日の場合はエラー
    doc = get_base_doc()
    floating_stream = doc.trade[0].swap.swap_stream[0]
    floating_stream.calculation_period_dates.calculation_period_frequency.roll_convention = RollConventionEnum.VALUE_15

    rule = Ird10Rule()
    with pytest.raises(InvalidConfigurationError) as excinfo:
        rule.validate(doc)
    assert "rollConvention" in str(excinfo.value)
    assert rule.rule_id == "ird-10"


def test_ird_11_rule_valid():
    # rollConvention = 14 で終了日が14日の場合は通過する
    doc = get_base_doc()
    rule = Ird11Rule()
    rule.validate(doc)


def test_ird_11_rule_invalid_mismatch():
    # rollConvention = 15 で終了日が14日の場合はエラー
    doc = get_base_doc()
    floating_stream = doc.trade[0].swap.swap_stream[0]
    floating_stream.calculation_period_dates.calculation_period_frequency.roll_convention = RollConventionEnum.VALUE_15

    rule = Ird11Rule()
    with pytest.raises(InvalidConfigurationError) as excinfo:
        rule.validate(doc)
    assert "rollConvention" in str(excinfo.value)
    assert rule.rule_id == "ird-11"


def test_ird_12_rule_valid():
    # 計算頻度と支払頻度が整合している場合は通過する (6M と 6M)
    doc = get_base_doc()
    rule = Ird12Rule()
    rule.validate(doc)


def test_ird_12_rule_invalid_mismatch():
    # 計算頻度と支払頻度が整合していない場合はエラー (7M と 6M)
    doc = get_base_doc()
    floating_stream = doc.trade[0].swap.swap_stream[0]
    floating_stream.calculation_period_dates.calculation_period_frequency.period_multiplier = 7

    rule = Ird12Rule()
    with pytest.raises(InvalidConfigurationError) as excinfo:
        rule.validate(doc)
    assert "frequency" in str(excinfo.value)
    assert rule.rule_id == "ird-12"


def test_ird_21_rule_valid():
    # 2つのレグの開始日（未調整）が一致している場合は通過する
    doc = get_base_doc()
    rule = Ird21Rule()
    rule.validate(doc)


def test_ird_21_rule_invalid_mismatch():
    # 2つのレグの開始日（未調整）が一致していない場合はエラー
    doc = get_base_doc()
    # 2番目のレグ (固定レグ) の開始日を変更する
    fixed_stream = doc.trade[0].swap.swap_stream[1]
    fixed_stream.calculation_period_dates.effective_date.unadjusted_date.value = (
        XmlDate(1994, 12, 15)
    )

    rule = Ird21Rule()
    with pytest.raises(DateMismatchError) as excinfo:
        rule.validate(doc)
    assert "effectiveDate" in str(excinfo.value)
    assert rule.rule_id == "ird-21"


def test_ird_22_rule_valid():
    # 2つのレグの終了日（未調整）が一致している場合は通過する
    doc = get_base_doc()
    rule = Ird22Rule()
    rule.validate(doc)


def test_ird_22_rule_invalid_mismatch():
    # 2つのレグの終了日（未調整）が一致していない場合はエラー
    doc = get_base_doc()
    # 2番目のレグ (固定レグ) の終了日を変更する
    fixed_stream = doc.trade[0].swap.swap_stream[1]
    fixed_stream.calculation_period_dates.termination_date.unadjusted_date.value = (
        XmlDate(1999, 12, 15)
    )

    rule = Ird22Rule()
    with pytest.raises(DateMismatchError) as excinfo:
        rule.validate(doc)
    assert "terminationDate" in str(excinfo.value)
    assert rule.rule_id == "ird-22"


def test_ird_14_rule_valid():
    # terminationDate >= effectiveDate の場合は通過する
    doc = get_base_doc()
    rule = Ird14Rule()
    rule.validate(doc)


def test_ird_14_rule_invalid_mismatch():
    # terminationDate < effectiveDate の場合はエラー
    doc = get_base_doc()
    floating_stream = doc.trade[0].swap.swap_stream[0]
    floating_stream.calculation_period_dates.termination_date.unadjusted_date.value = (
        XmlDate(1994, 12, 13)
    )

    rule = Ird14Rule()
    with pytest.raises(DateMismatchError) as excinfo:
        rule.validate(doc)
    assert "terminationDate" in str(excinfo.value)
    assert rule.rule_id == "ird-14"


def test_fpml_validator_integration_valid():
    # デフォルトの FpmlValidator ですべてのルールをパスすることを検証
    doc = get_base_doc()
    validator = FpmlValidator()
    validator.validate(doc)


def test_fpml_validator_integration_invalid():
    # いずれかのルール（例: ird-10）に引っかかる場合にエラーが投げられることを検証
    doc = get_base_doc()
    # ird-10 違反を起こす
    doc.trade[0].swap.swap_stream[
        0
    ].calculation_period_dates.calculation_period_frequency.roll_convention = (
        RollConventionEnum.VALUE_15
    )

    validator = FpmlValidator()
    with pytest.raises(InvalidConfigurationError):
        validator.validate(doc)


def test_multiplicity_min_occurs_violation():
    doc = get_base_doc()
    # swapStream は min_occurs=1 なので空にするとエラー
    doc.trade[0].swap.swap_stream = []

    validator = FpmlValidator()
    with pytest.raises(MissingRequiredFieldError) as excinfo:
        validator.validate(doc)
    assert "swap_stream" in str(excinfo.value)
    assert "requires at least 1" in str(excinfo.value)


def test_choice_violation_multiple_set():
    doc = get_base_doc()
    # calculation の floatingRateCalculation と fixedRateSchedule の両方を設定して重複させる
    calc = doc.trade[0].swap.swap_stream[0].calculation_period_amount.calculation
    calc.fixed_rate_schedule = Schedule(initial_value=Decimal("0.05"))

    validator = FpmlValidator()
    with pytest.raises(InvalidConfigurationError) as excinfo:
        validator.validate(doc)
    assert "Choice constraint violated" in str(excinfo.value)
    assert "floating_rate_calculation" in str(excinfo.value)
    assert "fixed_rate_schedule" in str(excinfo.value)


def test_choice_violation_missing_required():
    doc = get_base_doc()
    # calculation の floatingRateCalculation と fixedRateSchedule を両方 None にして必須Choice違反を起こす
    calc = doc.trade[0].swap.swap_stream[0].calculation_period_amount.calculation
    calc.floating_rate_calculation = None
    calc.fixed_rate_schedule = None

    validator = FpmlValidator()
    with pytest.raises(MissingRequiredFieldError) as excinfo:
        validator.validate(doc)
    assert "Required choice" in str(excinfo.value)
    assert "Calculation" in str(excinfo.value)
