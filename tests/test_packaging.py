import importlib
import subprocess
import sys


def test_runtime_modules_importable():
    assert importlib.import_module("main")
    assert importlib.import_module("src.pipeline.pipeline")
    assert importlib.import_module("src.tools.config_assistant.server")


def test_main_help_smoke():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "FPS Video Snap" in result.stdout
