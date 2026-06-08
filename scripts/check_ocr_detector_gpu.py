import sys
from pathlib import Path

# 确保从仓库根目录导入 `src.*`（与 `python main.py` 的 sys.path 行为一致）
REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT_STR = str(REPO_ROOT)
if REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, REPO_ROOT_STR)


def main() -> int:
    from src.ai.ocr_detector import OCRDetector

    print("Initializing OCRDetector (GPU)...")
    ocr = OCRDetector(lang="ch", use_gpu=True)
    print("Engine:", ocr.engine_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
