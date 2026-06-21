import argparse
import logging
import sys
from pathlib import Path

from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from fpml.confirmation import DataDocument
from src.cashflow_expander import CashflowExpander

# ロガーの設定
logger = logging.getLogger("expand_cashflows")


def main():
    parser = argparse.ArgumentParser(
        prog="expand_cashflows.py",
        description="FpML キャッシュフロー展開ツール CLI",
    )
    parser.add_argument("input", help="入力 FpML XML ファイルのパス")
    parser.add_argument("output", help="出力先 FpML XML ファイルのパス")
    parser.add_argument("--config", help="設定ディレクトリのパス", default="config")
    parser.add_argument(
        "--verbose", action="store_true", help="デバッグログを出力します"
    )

    args = parser.parse_args()

    # ログレベルの設定
    log_level = logging.DEBUG if args.verbose else logging.INFO

    # ログハンドラ・フォーマット設定 (sys.stderr へ出力)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info(
        f"Starting cashflow expansion. Input: {args.input}, Output: {args.output}"
    )
    logger.debug(f"Config directory: {args.config}")

    try:
        input_path = Path(args.input)
        output_path = Path(args.output)

        parser = XmlParser()
        data_document = parser.from_path(input_path, DataDocument)

        # ドメインモデルに対してキャッシュフローを展開
        CashflowExpander.expand_cashflows(data_document, args.config)

        # XMLとして書き出し
        config = SerializerConfig(indent="  ")
        serializer = XmlSerializer(config=config)
        ns_map = {
            "": "http://www.fpml.org/FpML-5/confirmation",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            serializer.write(f, data_document, ns_map=ns_map)

        logger.info("Cashflow expansion completed successfully.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error during cashflow expansion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
