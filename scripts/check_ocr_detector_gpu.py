import os
import sys

# 确保从仓库根目录导入 `src.*`（与 `python main.py` 的 sys.path 行为一致）
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.ai.ocr_detector import OCRDetector


def main() -> int:
    print("Initializing OCRDetector (GPU)...")
    ocr = OCRDetector(lang="ch", use_gpu=True)
    print("Engine:", ocr.engine_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
