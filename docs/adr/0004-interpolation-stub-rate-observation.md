# 4. Rate Observation Structure for Interpolated Stubs

## Status

Accepted

## Context

FpMLスワップ契約において、スタブ期間（Stub Period）の浮動金利レッグに線形補間（Linear Interpolation）が適用される場合、`stubCalculationPeriodAmount` 内に2つの `floatingRate`（異なるテナーの金利指標、例：`EUR-LIBOR-BBA 4M` と `EUR-LIBOR-BBA 5M`）が指定されます。

このとき、キャッシュフロー展開（FpML Confirmationビューの `cashflows` 要素）において、この補間対象の金利観測（`rateObservation`）をどのように表現するべきかが議論となりました。以下の3つのアプローチが検討されました：

1. **単一の `rateObservation` に代表させる（提案方式）**
   - 補間された「仮想的な1つのインデックス」とみなし、スタブ期間に対して1つの `RateObservation`（Fixing日）を出力する。
2. **複数の `rateObservation` を並列出力する**
   - 補間元である2つのインデックスに対応させて、2つの `RateObservation` を並べて出力する。
3. **`rateObservation` を出力しない**
   - スタブ期間のFixingは特殊であるため、`floatingRateDefinition` の枠のみを作成し、`rateObservation` は出力しない。

## Decision

FpMLの公式サンプル（`ird-ex02-stub-amort-swap.xml`）のベストプラクティスに準拠し、**「1. 単一の `rateObservation` に代表させる」** アプローチを採用しました。

理由は以下の通りです：
- FpMLの `RateObservation` 型には「どのテナー/インデックスの観測値か」を明示する属性（`indexTenor` など）が存在しないため、選択肢2のように2つの観測値を並列に出力しても、データを受け取る側でどちらがどのテナーに対応するのか識別できないという致命的な制限があります。
- したがって、スタブ期間の開始日を基準に、通常の `resetDates` で規定されたオフセットルールを適用した1つのFixing日（`adjustedFixingDate`）を持つ単一の `RateObservation` を出力し、評価エンジン側でそのFixing日における補間レート（`observedRate`）を算出して格納する前提とします。

## Consequences

### Positive (良い影響)
- FpML標準サンプルおよびスキーマ仕様との整合性が完全に保たれます。
- 後段の評価システムなどが、通常の計算期間と同様に「1つの期間 ＝ 1つのFixing（`RateObservation`）」としてシンプルに処理できます。

### Negative (懸念される影響)
- キャッシュフロー展開結果だけを見ると、補間元となった2つの具体的なテナー情報（例：4M, 5M）が欠落するため、補間の計算根拠を追跡するためには元の契約パラメータ（`stubCalculationPeriodAmount`）を参照する必要があります。
