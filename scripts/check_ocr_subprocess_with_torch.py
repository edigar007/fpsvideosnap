"""Sanity check: import torch first, then run OCRDetector with subprocess PaddleOCR.

This validates the Windows Torch↔Paddle DLL conflict workaround.

Usage (from repo root):
  .venv\\Scripts\\python.exe scripts\\check_ocr_subprocess_with_torch.py

Prereqs:
  - .venv_paddle exists and can run PaddleOCR on GPU.
"""

import numpy as np
import cv2
import os
import sys


# 确保从仓库根目录导入 `src.*`（与 `python main.py` 的 sys.path 行为一致）
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
  sys.path.insert(0, REPO_ROOT)


def main() -> int:
    import torch  # noqa: F401

    from src.ai.ocr_detector import OCRDetector

    # Create a simple synthetic image with text; OCR accuracy may vary,
    # but this script primarily verifies we don't crash.
    img = np.zeros((240, 640, 3), dtype=np.uint8)
    cv2.putText(img, "KILL +100", (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 4)

    ocr = OCRDetector(lang="en", use_gpu=True)
    print(f"engine_type={getattr(ocr, 'engine_type', None)}")

    detections = ocr.detect_text(img)
    print(f"detections={len(detections)}")
    if detections:
        print(detections[0])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
