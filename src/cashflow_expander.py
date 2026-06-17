from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from fpml.confirmation import Cashflows, DataDocument
from src.calendars.business_calendar import BusinessCalendar
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.swap_stream_scheduler import SwapStreamScheduler


class CashflowExpander:
    @staticmethod
    def expand_cashflows(input_file: str, output_file: str, config_dir: str) -> bool:
        """FpML XMLファイルを読み込み、キャッシュフローを展開した上で、シリアライズして指定されたパスに出力します。

        Args:
            input_file: 入力となるFpML XMLファイルのパス
            output_file: 出力先となるFpML XMLファイルのパス
            config_dir: カレンダー等の設定ディレクトリパス

        Returns:
            bool: 処理が正常に完了した場合はTrue
        """
        input_path = Path(input_file)
        output_path = Path(output_file)

        # 1. XMLパーサの初期化とロード
        parser = XmlParser()
        data_document = parser.from_path(input_path, DataDocument)

        # 2. カレンダー、リゾルバー、スケジューラーの初期化
        calendar = BusinessCalendar(config_dir=config_dir)
        resolver = ReferenceResolver(data_document)
        scheduler = SwapStreamScheduler(calendar, resolver)

        # 3. キャッシュフローの展開と埋め込み
        if data_document.trade:
            for trade in data_document.trade:
                if trade.swap is not None:
                    for stream in trade.swap.swap_stream:
                        payment_periods = scheduler.generate_payment_periods(stream)
                        stream.cashflows = Cashflows(
                            cashflows_match_parameters=True,
                            payment_calculation_period=payment_periods,
                            principal_exchange=[],
                        )

        # 4. XMLシリアライザの初期化と書き出し
        config = SerializerConfig(indent="  ")
        serializer = XmlSerializer(config=config)

        # 出力先ディレクトリの確保
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            serializer.write(f, data_document)

        return True
