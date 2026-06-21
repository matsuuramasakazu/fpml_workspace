from fpml.confirmation import Cashflows, DataDocument
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.payment_period_scheduler import PaymentPeriodScheduler
from src.schedulers.principal_exchange_scheduler import PrincipalExchangeScheduler
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver_factory import StepScheduleResolverFactory
from src.validators import FpmlValidator


class CashflowExpander:
    """FpMLのキャッシュフロー展開ロジックを担当するドメインサービス。

    ファイル入出力等のインフラ処理は本クラスの責務外とし、DataDocument
    オブジェクトに対する展開ロジックのみを提供します。
    """

    @staticmethod
    def expand_cashflows(data_document: DataDocument, config_dir: str) -> None:
        """FpML XMLドキュメントオブジェクトを受け取り、キャッシュフローを展開した上でインプレースで更新します。

        Args:
            data_document: 展開対象となる FpML DataDocument オブジェクト
            config_dir: カレンダー等の設定ディレクトリパス
        """
        # 1. 入力データのバリデーション
        validator = FpmlValidator()
        validator.validate(data_document)

        # 2. カレンダー、リゾルバー、スケジューラーの初期化
        calendar = BusinessCalendar(config_dir=config_dir)
        ref_resolver = ReferenceResolver(data_document)
        payment_scheduler = PaymentPeriodScheduler(calendar, ref_resolver)
        principal_scheduler = PrincipalExchangeScheduler(calendar, ref_resolver)

        # 3. キャッシュフローの展開と埋め込み
        if data_document.trade:
            for trade in data_document.trade:
                if trade.swap is not None:
                    for stream in trade.swap.swap_stream:
                        step_schedule_resolver_factory = StepScheduleResolverFactory(
                            stream, ref_resolver
                        )
                        payment_periods = payment_scheduler.generate_payment_periods(
                            stream, step_schedule_resolver_factory
                        )
                        principal_exchanges = principal_scheduler.generate_exchanges(
                            stream, step_schedule_resolver_factory
                        )
                        stream.cashflows = Cashflows(
                            cashflows_match_parameters=True,
                            payment_calculation_period=payment_periods,
                            principal_exchange=principal_exchanges,
                        )
