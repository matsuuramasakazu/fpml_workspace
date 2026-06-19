# FpML キャッシュフロー展開ツール - プロダクト要求仕様書 (PRD)

## Problem Statement

### ユーザーの課題

FpML形式のスワップ契約データから、キャッシュフロー展開を行うためのツールが必要である。

**現状の問題点：**
1. スワップの契約パラメータ（金利、期間、ロール慣行など）が記述されているが、**キャッシュフロー要素（cashflows）が生成されていない**
2. FpML XSD スキーマに準拠したキャッシュフロー XML を生成する手段がない

### 対象となるユースケース

- RFR O/N Index（SOFR, TONA, EONIA など）の金利スワップのFpML XMLファイルにキャッシュフロー追加
- IBOR系Index（EURIBOR, TIBORなど）の金利スワップのFpML XMLファイルにキャッシュフロー追加
- 元本リセット型を含む通貨スワップのFpML XMLファイルにキャッシュフロー追加
- 通貨（USD, JPY, EURなど）および通貨ペアの多様性（USD-JPY, EUR-USD など）への対応
- 営業日調整ルール（Following/Modified Following/Preceding/Modified Preceding, 複数Business center）への対応
- RFR O/N IndexのFixingルール（Observation period shift, Lookback, Lockout, Payment lag）への対応

---

## Solution

### 提案ソリューション

FpML確認書から**パラメータベースのキャッシュフロー要素を自動生成する Python ツール**を開発する。

**主要機能：**
1. **入力**: FpML XML ファイル（スワップ契約パラメータを含む）
2. **処理**:
   - paymentFrequencyに基づいてPaymentCalculationPeriodのコレクションに展開してCashflowsに設定
   - calculationPeriodDatesから計算期間スケジュールをCalculationPeriodのコレクションとして展開してPaymentCalculationPeriodに設定
   - Compoundingの場合複数のCalculationPeriodをPaymentCalculationPeriodに設定
   - Floating LegのFixingスケジュールをRateObservationのコレクションとして展開してCalculationPeriodのFloatingRateDefinitionに設定
   - 営業日カレンダーと営業日調整ルールを適用して日付を調整
   - Fixed/Floating legを自動判定し、パラメータを抽出
   - cashflows 要素を生成
3. **出力**: キャッシュフロー要素を含む FpML XML ファイル

**特徴：**
- **XSD準拠**: FpML 5.12 Confirmation View 仕様に完全準拠
- **自動判定**: Leg の順序に依存しない固定/浮動判定
- **マルチ通貨対応**: leg の currency から自動取得
- **祝祭日対応**: TOML形式の祝祭日カレンダーで複数営業日センターをサポート
- **厳密エラーハンドリング**: 金融データ精度を優先

---

## User Stories

1. 入力 FpML XML ファイルを指定して、キャッシュフロー拡張を実行できる

2. 複数の通貨ペア（USD-JPY, EUR-USD など）に対応した自動キャッシュフローを生成できる

3. 生成されたキャッシュフロー要素が FpML XSD スキーマに準拠していることを確認できる

4. 営業日カレンダーを TOML ファイルで管理・更新できる

5. キャッシュフロー生成ロジックが独立したモジュール（DateScheduler, BusinessCalendar）として実装されている

6. 入力データの不正（スキーマ違反、日付矛盾など）を検出して詳細なエラーメッセージを得られる

7. ird-ex052 などのサンプル FpML ファイルで、leg の順序を入れ替えても正しくキャッシュフロー生成できる

8. 生成されたキャッシュフロー要素が、法定の日数カウント方式（ACT/360, ACT/365.FIXED など）に従って計算されていることを検証できる

9. 固定/浮動 leg の自動判定が動的に行われる（leg の位置順序に依存しない）

10. 元本交換（principalExchange）が正確に識別されたキャッシュフロー要素を得られる

11. 複数ビジネスセンター（GBLO, USNY, JPTO など）の営業日ルールが統合的に処理される

12. キャッシュフロー生成時に、入力パラメータの整合性チェック（terminationDate >= effectiveDate など）が実施される

13. xsdata ライブラリを使用して、FpML Python モデルと XML シリアライザが統合されている

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

#### 3. **ReferenceResolver モジュール**
   - **責務**: Referenceクラスが参照する要素を取得する機能の実装
   - **インターフェース**:
     - `resolve(reference: Reference) -> Any`
   - **テスト対象**: ✓（Referenceクラスが参照する要素の正確性）

#### 4. **DateScheduler モジュール**
   - **責務**: スケジュール展開エンジン。元本交換スケジュール、クーポン支払スケジュール、計算期間スケジュール、fixingRateObservationスケジュールの生成
   - **インターフェース**:
     - `generate_principal_exchanges(...) -> List[PrincipalExchange]`
     - `generate_payment_periods(...) -> List[PaymentCalculationPeriod]`
     - `generate_calculation_periods(...) -> List[CalculationPeriod]`
     - `generate_fixing_rate_observations(...) -> List[RateObservation]`
   - **依存関係**: BusinessCalendar
   - **テスト対象**: ✓（スケジュール生成の正確性、期間集約）

#### 5. **CashflowExpander モジュール（メイン処理）**
   - **責務**: FpML パースから cashflows が追加された XML 生成までの統合ロジック
   - **プロセス**:
     1. xsdata で FpML XML を parse して Python dataclass に変換
     2. swap/swapStream を反復処理
     3. swapStream のfixed or floating を自動判定（swap/swapStream/calculationPeriodAmount/calculation の構造を検査）
     4. swapStream に cashflows 要素を構築
     5. cashflows に principalExchange 要素を構築（swap/swapStream/principalExchange の構造を検査）
     6. cashflows に paymentCalculationPeriod 要素を構築（swap/swapStream/paymentDates の構造を検査）
     7. cashflows/paymentCalculationPeriod に calculationPeriod 要素を構築（swap/swapStream/CalculationPeriodDates の構造を検査）
     8. cashflows/paymentCalculationPeriod/calculationPeriod に fxLinkedNotionalAmount 要素を構築（swap/swapStream/calculation/fxLinkedNotionalSchedule の構造を検査）
     9. cashflows/paymentCalculationPeriod/calculationPeriod に floatingRateDefinition 要素を構築（swap/swapStream/calculation/floatingRateCalculation の構造を検査）
     10. cashflows/paymentCalculationPeriod/calculationPeriod/floatingRateDefinition に rateObservation 要素を構築（swap/swapStream/calculation/floatingRateCalculation/calculationParameters の構造を検査）
     11. xsdata で swap/swapStreamにcashflows が追加された FpML XML をファイルに出力
   - **インターフェース**:
     - `expand_cashflows(input_file: str, output_file: str, config_dir: str) -> bool`
   - **テスト対象**: ✓（E2E 統合テスト）

#### 6. **メインスクリプト (expand_cashflows.py)**
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
│  ├─ unadjustedPrincipalExchangeDate: date (optional)
│  ├─ adjustedPrincipalExchangeDate: date
│  └─ principalExchangeAmount: decimal
└─ paymentCalculationPeriod (0..*)
   ├─ unadjustedPaymentDate: date (optional)
   ├─ adjustedPaymentDate: date
   └─ calculationPeriod (1..*)
      ├─ unadjustedStartDate: date (optional)
      ├─ unadjustedEndDate: date (optional)
      ├─ adjustedStartDate: date
      ├─ adjustedEndDate: date
      ├─ calculationPeriodNumberOfDays: integer
      ├─ notionalAmount: decimal
      ├─ fxLinkedNotionalAmount: FxLinkedNotionalAmount
        ├─ resetDate: Date
        ├─ adjustedFxSpotFixingDate: Date
        └─ notionalAmount: NonNegativeDecimalNumber
      ├─ dayCountYearFraction: decimal
      ├─ fixedRate: decimal
      └─ floatingRateDefinition
         ├─ calculatedRate: decimal
         ├─ floatingRateMultiplier: decimal
         ├─ spread: decimal
         └─ rateObservation (1..*)
            ├─ resetDate: date
            ├─ adjustedFixingDate: date
            ├─ observedRate: decimal
            ├─ treatedRate: decimal
            └─ observationWeight: integer
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
   c. adjusted_start = adjust_date(current_date, convention, centers)
   d. adjusted_end = adjust_date(next_date, convention, centers)
   e. add_calc_period(adjusted_start, adjusted_end)
   f. current_date = next_date
3. group_by_payment_frequency(calc_periods) → payment_schedules
4. for each payment_schedule:
   a. set payment_date = adjusted_end of last calc_period
   b. apply payment_date_adjustment(payment_date, convention, centers)
```

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

- **単体テスト**: TDD駆動開発で各モジュールの機能テスト（境界条件含む）を実装する。
- **統合テスト**: DateScheduler + BusinessCalendar 組み合わせで実装する。
- **E2E テスト**: 実際の FpML ファイル（ird-ex01, ird-ex44, ird-ex45, ird-ex052, ird-ex25）でのキャッシュフロー生成を検証するテストを実装する。

### テスト対象外

- メインスクリプト の CLI インターフェース（手動テスト）
- xsdata ライブラリ自体の動作（標準ライブラリとして信頼）
