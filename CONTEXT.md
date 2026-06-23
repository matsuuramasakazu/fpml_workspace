# FpML キャッシュフロー展開プロジェクト - ドメイン用語辞書

## プロジェクト概要

FpML（Financial Products Markup Language）形式のスワップ契約データから、パラメータベースの**キャッシュフロー要素**を自動生成するツール。特に RFR O/N Index（Reference Rate Framework Overnight Index）を含む通貨スワップを対象とする。

## 用語定義

### 金融商品

| 用語 | 定義 | 英語 |
|------|------|------|
| **クロスカレンシースワップ** | 異なる2つの通貨間の金利交換契約。初期・最終元本交換を含む | Cross Currency Interest Rate Swap |
| **RFR** | Reference Rate Framework。従来の LIBOR に代わる新しい基準金利（SOFR, SONIA, EONIA など） | Reference Rate Framework |
| **O/N Index** | Overnight Index。営業日ベースの変動金利指標 | Overnight Index |
| **Leg** | スワップを構成する単一の支払責務フロー。固定 leg と浮動 leg の2本から構成 | Swap Stream |

### スケジュール・計算

| 用語 | 定義 | 英語 |
|------|------|------|
| **計算期間** | 金利が計算される期間。3M（3ヶ月）や6M（6ヶ月）単位で設定 | Calculation Period |
| **支払期間** | 計算された金利を支払う期間。計算期間と同じまたはそれ以上の長さ | Payment Period |
| **営業日調整** | 計算期間や支払日が営業日でない場合に調整するルール（FOLLOWING, MODFOLLOWING など） | Business Day Adjustment |
| **ロール慣行** | 月単位で期間をロールする際の基準日（例：11日） | Roll Convention |
| **支払サイクル日** | 支払頻度に基づき生成され、計算期間を支払期間にグループ化する境界となる。| Payment Cycle Date |
| **調整済支払日** | 営業日調整および`paymentDaysOffset`適用後の実際の支払日。FpMLの`adjustedPaymentDate`要素に対応 | Adjusted Payment Date |

### キャッシュフロー

| 用語 | 定義 | 英語 |
|------|------|------|
| **キャッシュフロー** | 将来に発生する支払。日付・金額・計算根拠を含む | Cashflow |
| **想定元本** | キャッシュフロー計算の基準となる元本額。通貨ペアごとに異なる | Notional Amount |
| **元本交換** | 初期・最終・中間段階で行われる元本の実際の交換 | Principal Exchange |
| **年分率** | 日数を年単位に換算した値（ACT/360, ACT/365.FIXED など） | Year Fraction / Day Count Fraction |

### ビジネスセンター・祝祭日

| 用語 | 定義 | コード例 |
|------|------|---------|
| **ビジネスセンター** | 営業日判定の基準となる金融市場都市 | GBLO（ロンドン）, USNY（ニューヨーク）, JPTO（東京） |
| **祝祭日カレンダー** | 各ビジネスセンターの営業日でない日付リスト | TOML形式で提供 |

## 設計原則

1. **XSD準拠**: FpML 5.12 Confirmation View の `cashflows` 複合型定義に従う
2. **パラメータ駆動**: スケジュール展開は契約パラメータ（frequency, convention など）から自動生成
3. **通貨自動取得**: leg の `currency` 要素から想定元本の通貨を自動判定
4. **Leg順序非依存**: 固定/浮動 leg の順序を気にしない（パラメータから動的判定）
5. **厳密エラーハンドリング**: 金融データの精度重視。不正な入力ではプロセス停止
