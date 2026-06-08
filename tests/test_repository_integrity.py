import importlib
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_history_manager_source_exists() -> None:
    assert (ROOT_DIR / "src" / "history" / "history_manager.py").is_file()


def test_core_modules_are_importable() -> None:
    importlib.import_module("src.history.history_manager")
    importlib.import_module("src.pipeline.pipeline")


def test_key_source_directories_are_not_gitignored() -> None:
    paths = [
        "src/history/history_manager.py",
        "src/pipeline/pipeline.py",
        "src/ai/kill_detector.py",
    ]

    result = subprocess.run(
        ["git", "check-ignore", "-v", "--", *paths],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
