# Handoff Document: キャッシュフロー展開ツールの TDD 実装

## 次のセッションの目標
- `e:\dev\python\fpml-workspace\PRD_CASHFLOW_EXPANSION.md`の要件を分割して GitHub に登録した Issue #9 から #15 のうち、次は **Issue #14** を **TDD (テスト駆動開発) アプローチで実装** する。

---

### クラス構造と役割
FpMLのドメイン概念（計算期間、決定日、支払期間）に対応する形で、以下のクラス階層（階層型コラボレーション）を構築しています。

```mermaid
graph TD
    SwapStreamScheduler --> CalculationPeriodScheduler
    SwapStreamScheduler --> PaymentPeriodScheduler
    CalculationPeriodScheduler --> FixingScheduler
    
    CalculationPeriodScheduler --> DateAdjuster
    PaymentPeriodScheduler --> DateAdjuster
    FixingScheduler --> DateAdjuster
```

- **`DateAdjuster`**: FpMLの `BusinessDayAdjustments` を用いた単一の日付の休日調整（`adjust_date`）に特化。
- **`FixingScheduler`**: 浮動金利レグのFixing日程（`FloatingRateDefinition` / `RateObservation`）の決定。
- **`CalculationPeriodScheduler`**: 計算期間（`CalculationPeriod`）の日程決定および想定元本・金利情報の付与（内部で `FixingScheduler` を呼び出す）。
- **`PaymentPeriodScheduler`**: 計算期間をグループ化し、支払期間（`PaymentCalculationPeriod`）に集約・支払日の休日調整を行う。
- **`SwapStreamScheduler`**: `InterestRateStream` を受け取って上記をオーケストレートするメインエントリポイント。

---

## 関連リソース
- **PRD**: [PRD_CASHFLOW_EXPANSION.md](file:///e:/dev/python/fpml-workspace/PRD_CASHFLOW_EXPANSION.md)
- **ADR**: [0003-refactor-date-scheduler-to-schedulers.md](file:///e:/dev/python/fpml-workspace/docs/adr/0003-refactor-date-scheduler-to-schedulers.md)
- **検証済みテスト**: [test_swap_stream_scheduler.py](file:///e:/dev/python/fpml-workspace/tests/schedulers/test_swap_stream_scheduler.py) などの `tests/schedulers/` 配下のテスト群。

---

## 提案されるスキル (Suggested Skills)
- **`tdd`**: Issue #12 の実装を進めるメインの Red-Green-Refactor 開発サイクル。
- **`git-auto-closer`**: 実装完了後、コミット・プッシュ・GitHub Issue のクローズを一括で行う。
