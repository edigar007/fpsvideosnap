import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Tuple

import cv2


def _add_cuda_dll_paths_on_windows() -> None:
    if sys.platform != "win32":
        return

    try:
        import site

        site_packages_list = site.getsitepackages()
        site_packages = None
        for sp in site_packages_list:
            if os.path.exists(os.path.join(sp, "nvidia")):
                site_packages = sp
                break

        if not site_packages:
            return

        nvidia_dirs = [
            "nvidia\\cudnn\\bin",
            "nvidia\\cublas\\bin",
            "nvidia\\cuda_runtime\\bin",
            "nvidia\\cufft\\bin",
            "nvidia\\curand\\bin",
            "nvidia\\cusolver\\bin",
            "nvidia\\cusparse\\bin",
            "nvidia\\nvjitlink\\bin",
        ]

        current_path = os.environ.get("PATH", "")
        for nvidia_dir in nvidia_dirs:
            nvidia_path = os.path.join(site_packages, nvidia_dir)
            if os.path.exists(nvidia_path) and nvidia_path not in current_path:
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(nvidia_path)
                    except Exception:
                        pass
                os.environ["PATH"] = nvidia_path + os.pathsep + current_path
                current_path = os.environ["PATH"]
    except Exception:
        # worker 内不抛出，避免影响主流程；具体错误会在 paddle 导入时报出
        return


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _send(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _load_image(path: str) -> Any:
    img = cv2.imread(path)
    if img is None:
        raise RuntimeError(f"Failed to read image: {path}")
    return img


_OCR_CACHE: Dict[Tuple[str, str], Any] = {}


def _get_ocr(lang: str, device: str):
    key = (lang, device)
    if key in _OCR_CACHE:
        return _OCR_CACHE[key]

    # 尽量避免 PaddleX 的模型源检查拖慢启动
    os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")

    from paddleocr import PaddleOCR

    ocr = PaddleOCR(
        lang=lang,
        device=device,
        use_angle_cls=True,
    )
    _OCR_CACHE[key] = ocr
    return ocr


def _predict(
    image_path: str,
    lang: str,
    device: str,
    offset_x: int = 0,
    offset_y: int = 0,
) -> list:
    ocr = _get_ocr(lang, device)
    img = _load_image(image_path)

    # PaddleOCR 3.x predict: list[dict]
    result = ocr.predict(img)
    detections = []

    if result and len(result) > 0:
        page_result = result[0]
        rec_texts = page_result.get("rec_texts", [])
        rec_scores = page_result.get("rec_scores", [])
        rec_polys = page_result.get("rec_polys", [])

        for i, text in enumerate(rec_texts):
            confidence = float(rec_scores[i]) if i < len(rec_scores) else 1.0
            bbox = rec_polys[i] if i < len(rec_polys) else [[0, 0], [0, 0], [0, 0], [0, 0]]
            detections.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "bbox": [[float(p[0] + offset_x), float(p[1] + offset_y)] for p in bbox],
                }
            )

    return detections


def main() -> int:
    # 确保 cwd 在 repo 根目录，便于相对路径（可选）
    try:
        os.chdir(_repo_root())
    except Exception:
        pass

    _add_cuda_dll_paths_on_windows()

    _send({"type": "ready", "pid": os.getpid()})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
            req_id = req.get("id")
            cmd = req.get("cmd")

            if cmd == "ping":
                _send({"id": req_id, "ok": True, "result": "pong"})
                continue

            if cmd == "predict_path":
                image_path = req["image_path"]
                lang = req.get("lang", "ch")
                device = req.get("device", "gpu:0")
                offset = req.get("offset", [0, 0])
                offset_x, offset_y = int(offset[0]), int(offset[1])

                detections = _predict(
                    image_path=image_path,
                    lang=lang,
                    device=device,
                    offset_x=offset_x,
                    offset_y=offset_y,
                )
                _send({"id": req_id, "ok": True, "detections": detections})
                continue

            _send({"id": req_id, "ok": False, "error": f"Unknown cmd: {cmd}"})

        except Exception as e:
            _send(
                {
                    "id": req.get("id") if isinstance(locals().get("req"), dict) else None,
                    "ok": False,
                    "error": repr(e),
                    "traceback": traceback.format_exc(),
                }
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
