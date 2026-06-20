import subprocess
import sys
import tempfile
from pathlib import Path


def test_cli_missing_args():
    # 引数が足りない場合、exit code 2 でエラーになること
    result = subprocess.run(
        [sys.executable, "expand_cashflows.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    # argparseの標準的なエラーメッセージが含まれること
    assert "error" in result.stderr


def test_cli_execution_and_verbose():
    input_file = (
        Path(__file__).parent.parent
        / "confirmation"
        / "products"
        / "interest-rate-derivatives"
        / "ird-ex01-vanilla-swap.xml"
    )
    config_dir = Path(__file__).parent.parent / "config"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "output_cli.xml"

        # --verboseなしでの実行
        result = subprocess.run(
            [
                sys.executable,
                "expand_cashflows.py",
                str(input_file),
                str(output_file),
                "--config",
                str(config_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert output_file.exists()
        # デフォルトはINFOログのはず。DEBUGログは出力されないはず
        assert "DEBUG" not in result.stderr

        # --verboseありでの実行
        output_file_verbose = Path(tmpdir) / "output_cli_verbose.xml"
        result_verbose = subprocess.run(
            [
                sys.executable,
                "expand_cashflows.py",
                str(input_file),
                str(output_file_verbose),
                "--config",
                str(config_dir),
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )
        assert result_verbose.returncode == 0
        assert output_file_verbose.exists()
        # --verbose ありのときは DEBUG レベルのログを出力するはず
        # CLIの実装で `logger.debug` で何か出力されることを期待する
        assert "DEBUG" in result_verbose.stderr
