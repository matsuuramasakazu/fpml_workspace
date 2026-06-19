# FpML キャッシュフロー展開ツール - 拡張要求仕様書 (PRD)

## Problem Statement

FpML形式のスワップ契約データからキャッシュフロー（`cashflows`）を生成する際、現状の実装では標準的なバニラスワップおよび基本的な通貨スワップのみに対応しており、より実務的で複雑な契約仕様に対応できていません。

具体的には、以下の契約仕様に対応するキャッシュフローの期間構造や日付・パラメータを正確に展開し、FpML XSD スキーマに準拠したXMLを出力する手段がありません。
1. **Stub（スタブ期間）**: 契約開始・終了時に発生する変則期間の日付展開と、それに適用される金利解決（線形補間、固定レート、固定金額）。
2. **Amortization（想定元本削減/変動）**: 想定元本が期間中に段階的に変動するスケジュール（`notionalStepSchedule`）のルックアップと割り当て。
3. **Rate/Spread Step Schedule（固定金利・スプレッドの段階的変更）**: 固定金利や浮動レッグのスプレッドが段階的に変更されるスケジュールのルックアップと割り当て。
4. **Reset in Arrears（アリアーズ/期末金利決定）**: 金利決定日（Fixing Date）を計算期間の終了日を基準に決定する仕様。
5. **Compounding（複利計算の詳細解釈）**: 支払期間内の複数計算期間の集約と、複利属性の考慮。

---

## Solution

キャッシュフロー展開エンジン（`CalculationPeriodScheduler`, `FixingScheduler`, `PaymentPeriodScheduler`）を拡張し、FpMLの契約パラメータに基づいてこれら5つの仕様を正確に自動展開し、FpML 5.12 Confirmation仕様に完全準拠したキャッシュフロー構造を出力するPythonモジュールを実装します。

本ツールは「構造展開（オプションA）」の原則に特化し、実際の市場金利データの入力や数理的な利息金額の算出は行わず、FpMLの `cashflows` 要素内に適合する日付・期間構造・割り当てられたパラメータの解決を行います。

---

## User Stories

1. As a quant analyst, I want to expand cashflows for swaps with initial and final stubs, so that irregular periods at the start and end of the trade are correctly generated as per the contract.
2. As a quant analyst, I want to apply linear interpolation to stubs using two designated index tenors, so that the correct interpolated fixing date is determined.
3. As a quant analyst, I want to apply a negotiated fixed stub rate (stubRate) to a floating leg stub, so that the stub period uses a fixed rate instead of a floating index.
4. As a quant analyst, I want to apply a stub amount (stubAmount) directly to a stub period, so that the cashflow amount is set to the negotiated amount without calculating interest.
5. As a quant analyst, I want to expand cashflows for swaps with amortizing notionals, so that each calculation period is assigned the correct notional value corresponding to the step date.
6. As a quant analyst, I want to apply step schedules for fixed rates (fixedRateSchedule) and floating spreads (spreadSchedule), so that the coupon calculation reflects the correct rates for each period.
7. As a quant analyst, I want to support Reset in Arrears swaps, so that the fixing dates and reset dates are calculated relative to the calculation period end dates instead of start dates.
8. As a quant analyst, I want to support compounding (compoundingMethod like Flat/Straight), so that multiple calculation periods are aggregated under a single payment period with the correct structure.
9. As a software developer, I want all generated cashflow structures to fully comply with FpML 5.12 Confirmation schema, so that the output files pass XSD validation without error.
10. As a software developer, I want comprehensive unit tests for stubs, step schedules, arrears, and compounding, so that I can prevent regressions during future development.

---

## Implementation Decisions

### 1. Stub（スタブ）の日付展開と金利解決
- **日付の展開**:
  - `firstRegularPeriodStartDate` (Initial Stub) が存在する場合、前進的（Forward）に展開し、`lastRegularPeriodEndDate` (Final Stub) が存在する場合、後退的（Backward）に期日を逆算して展開する。Long Stubは単一の計算期間として展開する。
- **補間スタブの構造**:
  - 補間（2つの `floatingRate`）が指定された場合、FpMLの `RateObservation` の仕様上、テナー識別属性がないため、単一の `RateObservation` を出力し、Fixing日は通常通り算出する。
- **固定レート/金額の適用**:
  - `stubRate` 指定時は `fixedRate` を優先割り当てし、`floatingRateDefinition` は出力しない。
  - `stubAmount` 指定時は金額情報を適用する。

### 2. ステップスケジュールの解決 (Amortization, Rate, Spread)
- **ルックアップの判定基準**:
  - 各計算期間の「調整前開始日（`unadjusted_start_date`）」を基準とし、`stepDate` の昇順ソートから該当する最新値を適用する。
  - **前提**: `stepDate` は計算期間の開始日と一致している前提（期中でのステップによる期間分割はサポート外）とする。

### 3. Reset in Arrears（期末金利決定）
- **金利決定基準**:
  - `resetRelativeTo` が `CalculationPeriodEndDate` の場合、基準日（`reset_date_val`）を調整後終了日（`adjusted_end`）とし、Fixing日および `RateObservation/resetDate` も期末日基準で算出する。既存のタイポバグも修正する。

### 4. Compounding（複利計算の属性詳細解釈）
- **期間集約**:
  - `compoundingMethod` が `Flat` または `Straight`（`None` 以外）に指定されている場合、計算頻度と支払頻度の比率に基づいて適切に計算期間を集約する。`firstCompoundingPeriodEndDate` に基づく最初の変則複利期日の境界を考慮して unadjusted dates を展開する。

---

## Testing Decisions

- **単体テストの整備**:
  - `tests/schedulers/test_calculation_period_scheduler.py` を新規作成し、`CalculationPeriodScheduler` のパブリックインターフェースを対象とする単体テストケース（Stub日付展開、Stub金利解決、Amortization元本適用、金利・スプレッドステップ、期末金利決定、変則複利スケジュール）をTDDプロセスで実装し、挙動を保証する。
- **結合・E2E検証**:
  - `ird-ex02-stub-amort-swap.xml`（Stub & Amortization）、`ird-ex03-compound-swap.xml`（Compounding）、`ird-ex04-arrears-stepup-fee-swap.xml`（Arrears & Step-up）のサンプルFpMLファイルを用い、生成されたキャッシュフロー構造が期待通りであるかを検証する。
- **スキーマ検証**:
  - 生成されたXMLファイルに対し、FpML 5.12 XSDによるスキーマバリデーションを自動テストの一環として実行し、互換性を保証する。

---

## Out of Scope

- 実際の市場金利（Fixingレート）を取得した上での、具体的な `observedRate` の補間計算や `amount` の金額計算機能。
- 計算期間の途中で元本がステップするような特殊契約における「期間分割（Sub-periods）」の自動スケジュール構築。
- バニラ・通貨スワップ以外の複雑なエキゾチックオプションやハイブリッド商品の展開。
