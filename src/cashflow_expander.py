from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from fpml.confirmation import DataDocument


class CashflowExpander:
    @staticmethod
    def expand_cashflows(input_file: str, output_file: str, config_dir: str) -> bool:
        """FpML XMLファイルを読み込み、再シリアライズして指定されたパスに出力します。

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

        # 2. XMLシリアライザの初期化と書き出し
        config = SerializerConfig(indent="  ")
        serializer = XmlSerializer(config=config)

        # 出力先ディレクトリの確保
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            serializer.write(f, data_document)

        return True
