# GitHub Issue #23 リファクタリング実装計画

レイヤー化アーキテクチャの適用および単一責任の原則（SRP）に基づく、リファクタリングの実装計画です。

## ユーザーレビューが必要な項目

> [!IMPORTANT]
> - `SwapStreamScheduler` クラスは完全に廃止（削除）され、その役割は `PaymentPeriodScheduler`（支払期間展開）および新設する `PrincipalExchangeScheduler`（元本交換展開）に分割されます。
> - `CashflowExpander.expand_cashflows` のシグネチャが変更され、ファイルパスではなく `DataDocument` オブジェクトを直接受け取ってインプレースで書き換えるようになります。ファイルIOは `expand_cashflows.py` およびテスト側のヘルパー関数に移行します。

## オープン質問

> [!NOTE]
> 現時点で未解決の懸念事項はありません。

## 提案される変更

---

### [Component: Schedulers]

#### [NEW] [principal_exchange_scheduler.py](file:///e:/dev/python/fpml-workspace/src/schedulers/principal_exchange_scheduler.py)
`SwapStreamScheduler` から `generate_principal_exchanges` メソッドのロジックを切り出し、元本交換スケジュールの生成に特化した新規クラス `PrincipalExchangeScheduler` を作成します。

#### [MODIFY] [payment_period_scheduler.py](file:///e:/dev/python/fpml-workspace/src/schedulers/payment_period_scheduler.py)
`SwapStreamScheduler` の残りの役割である `generate_payment_periods` メソッドを統合します。内部で `CalculationPeriodScheduler` をインスタンス化し、計算期間の生成から支払期間への集約・休日調整までを一貫して行うインターフェースを提供します。

#### [DELETE] [swap_stream_scheduler.py](file:///e:/dev/python/fpml-workspace/src/schedulers/swap_stream_scheduler.py)
役割が他のクラスに分割・統合されたため、このファイルを削除します。

---

### [Component: Core & CLI]

#### [MODIFY] [cashflow_expander.py](file:///e:/dev/python/fpml-workspace/src/cashflow_expander.py)
ファイル入出力処理（`XmlParser` によるロード、および `XmlSerializer` による保存）を排除します。`expand_cashflows` メソッドは `DataDocument` オブジェクトを引数に取り、インプレースでキャッシュフロー（支払期間および元本交換）を展開して設定するドメインサービスとします。

#### [MODIFY] [expand_cashflows.py](file:///e:/dev/python/fpml-workspace/expand_cashflows.py)
ファイル入出力の役割を引き受けます。入力ファイルをロードして `DataDocument` をパースし、`CashflowExpander.expand_cashflows` を呼び出し、結果を出力ファイルにシリアライズします。

---

### [Component: Tests]

#### [MODIFY] [test_pipeline.py](file:///e:/dev/python/fpml-workspace/tests/test_pipeline.py)
E2Eテストファイルです。テスト内でファイル入出力を行うためのヘルパー関数 `run_expansion_pipeline(input_path, output_path, config_dir)` を定義し、既存のテストコードにおける `CashflowExpander.expand_cashflows` の呼び出しをこのヘルパー関数に置換することで、既存の検証ロジックを崩さずに動作を検証します。

#### [NEW] [test_payment_period_scheduler.py](file:///e:/dev/python/fpml-workspace/tests/schedulers/test_payment_period_scheduler.py)
`tests/schedulers/test_swap_stream_scheduler.py` をリネームし、`PaymentPeriodScheduler.generate_payment_periods` の動作をテストするように修正します。

#### [MODIFY] [test_principal_exchange.py](file:///e:/dev/python/fpml-workspace/tests/schedulers/test_principal_exchange.py)
`test_swap_stream_scheduler.py` に含まれていた元本交換関連のテストケースをこちらに移動・統合し、`PrincipalExchangeScheduler.generate_exchanges` のテストとして動作するように書き換えます。

#### [DELETE] [test_swap_stream_scheduler.py](file:///e:/dev/python/fpml-workspace/tests/schedulers/test_swap_stream_scheduler.py)
`SwapStreamScheduler` の廃止に伴い削除します（内容は上記のテストファイルに再配置されます）。

---

## 検証計画

### 自動テスト
以下の pytest コマンドを実行して、リファクタリング後もすべてのテストが正常にパスすることを確認します。
- `.\.venv\Scripts\python.exe -m pytest`

また、TDDの精神に基づき、修正した単体テストファイル（`test_payment_period_scheduler.py`, `test_principal_exchange.py`）が個別に動作することを確認します。
- `.\.venv\Scripts\python.exe -m pytest tests/schedulers/test_payment_period_scheduler.py`
- `.\.venv\Scripts\python.exe -m pytest tests/schedulers/test_principal_exchange.py`

### 手動検証
- 実際に入力XMLファイル（`confirmation/products/interest-rate-derivatives/ird-ex01-vanilla-swap.xml`など）を指定して `expand_cashflows.py` を実行し、出力されたXMLが `tests/output/` ディレクトリに正しく生成されること、および差分がないことを確認します。
