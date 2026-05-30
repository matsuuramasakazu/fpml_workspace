# FpML キャッシュフロー展開ツール - プロダクト要求仕様書 (PRD)

## Problem Statement

### ユーザーの課題

金融機関の営業・リスク管理部門では、FpML形式のスワップ契約データから、キャッシュフロー予測を行う必要がある。

**現状の問題点：**
1. スワップの契約パラメータ（金利、期間、ロール慣行など）が定義されていても、**キャッシュフロー要素（cashflows）が生成されていない**場合がある
2. スワップの計算期間（calculationPeriod）から支払期間（paymentCalculationPeriod）への集約が手作業であり、エラー・誤漏れのリスクが高い
3. 複数通貨ペア、複数営業日調整ルールに対応するため、マニュアル計算では負荷が大きい
4. FpML XSD スキーマに準拠したキャッシュフロー XML を確実に生成する手段がない

### 対象となるユースケース

- RFR O/N Index（SOFR-OIS, EONIA など）の新型スワップ
- 通貨ペアの多様性（USD-JPY, EUR-USD など）
- 営業日調整ルールの複雑性（GBLO, USNY, JPTO など複数センター）

---

## Solution

### 提案ソリューション

FpML確認書から**パラメータベースのキャッシュフロー要素を自動生成する Python ツール**を開発する。

**主要機能：**
1. **入力**: FpML XML ファイル（スワップ契約パラメータを含む）
2. **処理**:
   - 営業日カレンダーを参照して、calculationPeriodDates から計算期間スケジュールを展開
   - businessDayConvention を適用して日付を調整
   - paymentFrequency に基づいて複数計算期間を支払期間にグループ化
   - 固定/浮動 leg を自動判定し、パラメータを抽出
   - cashflows XML 要素を生成
3. **出力**: 拡張キャッシュフロー要素を含む FpML XML ファイル

**特徴：**
- **XSD準拠**: FpML 5.12 Confirmation View 仕様に完全準拠
- **自動判定**: Leg の順序に依存しない固定/浮動判定
- **マルチ通貨対応**: leg の currency から自動取得
- **祝祭日対応**: TOML形式の祝祭日カレンダーで複数営業日センターをサポート
- **厳密エラーハンドリング**: 金融データ精度を優先

---

## User Stories

1. As a **リスク管理アナリスト**, I want to **入力 FpML XML ファイルを指定して、キャッシュフロー拡張を実行できる**, so that **手作業による計算ミスを削減できる**

2. As a **Front Office トレーダー**, I want to **複数の通貨ペア（USD-JPY, EUR-USD など）に対応した自動キャッシュフロー生成**, so that **契約確認の時間を短縮できる**

3. As a **コンプライアンス部門**, I want to **生成されたキャッシュフロー要素が FpML XSD スキーマに準拠していることを確認できる**, so that **規制要件への適合性を確保できる**

4. As a **システム管理者**, I want to **営業日カレンダーを TOML ファイルで管理・更新できる**, so that **新しい祝祭日対応を容易に反映できる**

5. As a **開発者**, I want to **キャッシュフロー生成ロジックが独立したモジュール（DateScheduler, BusinessCalendar）として実装されている**, so that **他のプロジェクトで再利用できる**

6. As a **品質保証担当**, I want to **入力データの不正（スキーマ違反、日付矛盾など）を検出して詳細なエラーメッセージを得られる**, so that **問題を迅速に修正できる**

7. As a **営業部門**, I want to **ird-ex052 などのサンプル FpML ファイルで、leg の順序を入れ替えても正しくキャッシュフロー生成ができる**, so that **柔軟なデータフォーマットに対応できる**

8. As a **定量分析チーム**, I want to **生成されたキャッシュフロー要素が、法定の日数カウント方式（ACT/360, ACT/365.FIXED など）に従って計算されていることを検証できる**, so that **バックテスト・検証プロセスが確実になる**

9. As a **システム管理者**, I want to **実行時ログレベル（`--verbose` フラグなど）を指定できる**, so that **デバッグ時に詳細な動作情報を取得できる**

10. As a **プロダクト責任者**, I want to **複数通貨ペアでのテストケースが実装されている**, so that **本番稼働時の信頼性が確保される**

11. As a **リスク計算エンジン開発チーム**, I want to **固定/浮動 leg の自動判定が動的に行われる**（leg の位置順序に依存しない）, so that **異なるスワップ構造にも対応できる**

12. As a **経理部門**, I want to **元本交換（principalExchange）が正確に識別されたキャッシュフロー要素を得られる**, so that **仕訳計上の根拠を確保できる**

13. As a **営業日調整専門家**, I want to **複数ビジネスセンター（GBLO, USNY, JPTO など）の営業日ルールが統合的に処理される**, so that **国際スワップの複雑な営業日調整に対応できる**

14. As a **データ品質チーム**, I want to **キャッシュフロー生成時に、入力パラメータの整合性チェック**（terminationDate >= effectiveDate など）**が実施される**, so that **不正なキャッシュフロー出力を防止できる**

15. As a **プロダクト開発チーム**, I want to **xsdata ライブラリを使用して、FpML Python モデルと XML シリアライザが統合されている**, so that **型安全なキャッシュフロー生成が実現される**

---

## Implementation Decisions

### モジュール構成

#### 1. **BusinessCalendar モジュール**
   - **責務**: 営業日判定、日付調整、ISDA ビジネスデー慣行の実装
   - **インターフェース**:
     - `is_business_day(date, centers: List[str]) -> bool`
     - `adjust_date(date, convention: BusinessDayConvention, centers) -> date`
   - **依存関係**: TOML 祝祭日カレンダー
   - **テスト対象**: ✓（営業日判定、日付調整の正確性）

#### 2. **DayCountCalculator モジュール**
   - **責務**: ISDA 日数カウント方式（ACT/360, ACT/365.FIXED など）の実装
   - **インターフェース**:
     - `calculate_year_fraction(start_date, end_date, method) -> Decimal`
   - **テスト対象**: ✓（各カウント方式の正確性）

#### 3. **DateScheduler モジュール**
   - **責務**: スケジュール展開エンジン。計算期間スケジュール、支払スケジュールの生成
   - **インターフェース**:
     - `generate_calculation_periods(...) -> List[CalculationPeriod]`
     - `generate_payment_schedule(...) -> List[PaymentSchedule]`
   - **依存関係**: BusinessCalendar
   - **テスト対象**: ✓（スケジュール生成の正確性、期間集約）

#### 4. **CashflowExpander モジュール（メイン処理）**
   - **責務**: FpML パースから cashflows XML 生成までの統合ロジック
   - **プロセス**:
     1. xsdata で FpML XML を parse して Python dataclass に変換
     2. swap/swapStream を反復処理
     3. 固定/浮動 leg を自動判定（calculationPeriodAmount/calculation の構造を検査）
     4. DateScheduler で支払スケジュール生成
     5. calculationPeriod 要素を構築
     6. principalExchange 要素を生成
     7. xsdata で cashflows XML 要素をシリアライズ
   - **インターフェース**:
     - `expand_cashflows(input_file: str, output_file: str, config_dir: str) -> bool`
   - **テスト対象**: ✓（E2E 統合テスト）

#### 5. **メインスクリプト (expand_cashflows.py)**
   - **責務**: CLI インターフェース、引数パース、エラーハンドリング
   - **仕様**:
     - コマンドライン: `python expand_cashflows.py <input.xml> <output.xml> [--config <dir>] [--verbose]`
     - ロギング: `logging` モジュール、ログレベル制御
   - **テスト対象**: 別途 (CLI 統合テスト)

### 技術選定

| 項目 | 選択肢 | 根拠 |
|------|--------|------|
| **XML パース・生成** | xsdata | FpML 5.12 XSD との一貫性、型安全性 |
| **日付計算** | dateutil + 手作り営業日 | 祝祭日カレンダーの柔軟管理 |
| **設定管理** | TOML (tomllib) | 人間が読みやすい、構造化 |
| **エラーハンドリング** | 厳密モード | 金融データ精度重視 |
| **ロギング** | logging モジュール | Python 標準、レベル制御 |

### キャッシュフロー要素の構造（XSD準拠）

```
cashflows
├─ cashflowsMatchParameters: boolean
├─ principalExchange (0..*)
│  ├─ unadjustedPrincipalExchangeDate: date
│  └─ principalExchangeAmount: decimal
└─ paymentCalculationPeriod (0..*)
   ├─ unadjustedPaymentDate: date (optional)
   ├─ adjustedPaymentDate: date
   └─ calculationPeriod (1..*)
      ├─ unadjustedStartDate: date
      ├─ unadjustedEndDate: date
      ├─ adjustedStartDate: date
      ├─ adjustedEndDate: date
      ├─ calculationPeriodNumberOfDays: integer
      ├─ notionalAmount: decimal
      ├─ dayCountYearFraction: decimal
      └─ [fixedRate | floatingRateDefinition]
```

### 設計パターン

1. **Builder パターン**: calculationPeriod の段階的構築
2. **Strategy パターン**: ビジネスデー慣行（FOLLOWING, MODFOLLOWING など）
3. **Composition パターン**: モジュール間の疎結合

### スケジュール展開アルゴリズム

```
1. effectiveDate = apply_business_day_adjustment(unadjustedDate, convention, centers)
2. while current_date < terminationDate:
   a. next_date = frequency.add_months(current_date)
   b. next_date = apply_roll_convention(next_date, roll_day)
   c. next_date = cap_at(next_date, terminationDate)
   d. adjusted_start = adjust_date(current_date, convention, centers)
   e. adjusted_end = adjust_date(next_date, convention, centers)
   f. add_calc_period(adjusted_start, adjusted_end)
   g. current_date = next_date
3. group_by_payment_frequency(calc_periods) → payment_schedules
4. for each payment_schedule:
   a. set payment_date = adjusted_end of last calc_period
   b. apply payment_date_adjustment(payment_date, convention, centers)
```

---

## Testing Decisions

### テスト対象モジュール

1. **BusinessCalendar** - ✓ ユニットテスト
   - GBLO（ロンドン）, USNY（ニューヨーク）, JPTO（東京）の営業日判定
   - 各 BusinessDayConvention（FOLLOWING, MODFOLLOWING など）の動作確認
   - 祝祭日カレンダーの TOML ロード・パース

2. **DayCountCalculator** - ✓ ユニットテスト
   - ACT/360, ACT/365.FIXED, 30/360 の計算正確性
   - 既知の例（ISDA テスト事例）との一致

3. **DateScheduler** - ✓ ユニットテスト
   - 計算期間スケジュール生成（3M, 6M など）
   - ロール慣行（11日など）の適用
   - 支払期間への集約（複数計算期間の正確な集約）

4. **CashflowExpander** - ✓ E2E 統合テスト
   - ird-ex052（USD-JPY） でのキャッシュフロー生成
   - leg 順序入れ替え対応の確認
   - XSD 準拠性の検証

### テスト戦略

- **単体テスト**: 各モジュールの機能テスト（境界条件含む）
- **統合テスト**: DateScheduler + BusinessCalendar 組み合わせ
- **E2E テスト**: 実際の FpML ファイル（ird-ex052）でのキャッシュフロー生成・検証
- **リグレッション**: 複数通貨ペア（USD-JPY, EUR-USD など）での一貫性

### テスト対象外

- メインスクリプト の CLI インターフェース（手動テスト）
- xsdata ライブラリ自体の動作（標準ライブラリとして信頼）

---

## Out of Scope

以下の項目はこの PRD の対象外です：

1. **マーケットデータの実装**: キャッシュフロー金額の計算（fixed rate, floating rate 確定）
   - → 金利 fixture または外部マーケットデータが必要な場合は別プロジェクト

2. **複雑なスワップ商品**: 
   - コーラス（Exotic Options）
   - 条件付きキャッシュフロー
   - → 基本的なバニラスワップ（Fixed-Float）に限定

3. **複数 leg （3本以上）への対応**:
   - → 通常のクロスカレンシースワップ（2 leg）が前提

4. **キャッシュフロー PV 計算**: 割引係数の適用など
   - → キャッシュフロー項目の生成のみ

5. **GUI・Web UI**: 
   - → コマンドラインツール（Python スクリプト）

6. **パフォーマンス最適化**: 
   - → 正確性と保守性を優先

---

## Further Notes

### 今後の拡張性

1. **ロードマップ**:
   - Phase 1（現在）: バニラスワップ、2 leg（固定-浮動）
   - Phase 2: 複数通貨オプション、コーラス対応
   - Phase 3: マーケットデータ統合による PV 計算

2. **再利用可能なモジュール**:
   - `BusinessCalendar`: 他の金融計算プロジェクトで流用可能
   - `DateScheduler`: 任意のスケジュール生成に応用可能
   - `DayCountCalculator`: 金利スワップ以外でも利用可能

3. **ドメイン言語の統一**:
   - CONTEXT.md で定義した用語を全コードに適用
   - Leg = SwapStream, calculationPeriod = Calc Period など、用語を一貫

4. **QA・監査対応**:
   - 生成されたキャッシュフロー要素とスケジュール出力を CSV export （別要件）
   - 監査ログ（誰が、いつ、どのファイルを処理したか）の記録

---

**作成日**: 2026-05-30  
**バージョン**: 1.0  
**ステータス**: 実装前レビュー待機
