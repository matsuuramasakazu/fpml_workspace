# Handoff: FpML Cashflow Expander Phase 2 Implementation

本セッションでは、金利スワップ（IRS）および通貨スワップ（CCS）のキャッシュフロー展開ツールにおける拡張機能（Phase 2）の要件定義と設計方針の合意を完了しました。

次のセッションでは、起票された個別タスクの **Issue #17**（Stub対応）から順番に実装（TDDサイクル）を開始します。

---

## 関連アーティファクトとドキュメント

- **要件定義 (PRD)**: 
  - [PRD_CASHFLOW_EXPANSION.md](file:///e:/dev/python/fpml-workspace/PRD_CASHFLOW_EXPANSION.md)
- **アーキテクチャ意思決定 (ADR)**:
  - [ADR 0004: Rate Observation Structure for Interpolated Stubs](file:///e:/dev/python/fpml-workspace/docs/adr/0004-interpolation-stub-rate-observation.md)
  - [ADR 0005: Notional Amortization Resolution for Calculation Periods](file:///e:/dev/python/fpml-workspace/docs/adr/0005-notional-amortization-resolution.md)

---

## 現在のステータスと次のセッションのタスク

当初の計画であった **Stub（スタブ）** と **Amortization（想定元本削減）** に加え、議論により決定した追加の3要件（**Rate/Spread Step Schedule**, **Reset in Arrears**, **Compounding**）を加え、以下の5つの垂直スライス（Tracer Bullet）に分割して GitHub に起票済みです。

### 実施対象タスク
1. **[GitHub Issue #17](https://github.com/matsuuramasakazu/fpml_workspace/issues/17) (次のセッションのフォーカス)**
   - **内容**: Stub (Initial/Final) Date Expansion and Rate Resolution
   - **状態**: ready-for-agent
2. **[GitHub Issue #18](https://github.com/matsuuramasakazu/fpml_workspace/issues/18)**
   - **内容**: Amortization (Notional Step Schedule) Resolution
   - **状態**: ready-for-agent
3. **[GitHub Issue #19](https://github.com/matsuuramasakazu/fpml_workspace/issues/19)**
   - **内容**: Reset in Arrears (CalculationPeriodEndDate) Fixing
   - **状態**: ready-for-agent
4. **[GitHub Issue #20](https://github.com/matsuuramasakazu/fpml_workspace/issues/20)**
   - **内容**: Rate and Spread Step Schedule Resolution (Blocked by #18)
   - **状態**: ready-for-agent
5. **[GitHub Issue #21](https://github.com/matsuuramasakazu/fpml_workspace/issues/21)**
   - **内容**: Compounding Aggregation and Initial Period End Date Support (Blocked by #17)
   - **状態**: ready-for-agent

---

## 次のセッションへの引き継ぎ手順（推奨スキル）

次のセッションを開始するエージェントは、以下のスキルを使用して作業を進めてください。

1. **`tdd` スキルの起動**:
   - TDD（テスト駆動開発）のプロセスに従い、`tests/schedulers/test_calculation_period_scheduler.py` を新規作成して、[Issue #17](https://github.com/matsuuramasakazu/fpml_workspace/issues/17) のスタブ挙動に対するユニットテスト（REDテスト）を追加し、Red-Green-Refactor サイクルを開始してください。
2. **`diagnose` スキル (必要時)**:
   - スケジュール生成や既存ロジック（日付調整や休日判定）との競合バグに直面した場合は、`diagnose` ループに従って問題を特定し、修正してください。
