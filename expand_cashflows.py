import argparse
import logging
import sys

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
        success = CashflowExpander.expand_cashflows(
            args.input, args.output, args.config
        )
        if success:
            logger.info("Cashflow expansion completed successfully.")
            sys.exit(0)
        else:
            logger.error("Cashflow expansion failed.")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error during cashflow expansion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
