"""Regression check: extract one frame from a video and run OCRDetector.find_keywords.

This is meant to validate the full OCR path with real game configs.
On Windows, it also validates the Torch↔Paddle GPU DLL workaround by importing torch first.

Usage examples (from repo root):
  .venv\\Scripts\\python.exe scripts\\check_find_keywords_on_video_frame.py \
    --video "G:\\Video\\...\\input.mp4" --game battlefield6 --timestamp-ms 123456
  .venv\\Scripts\\python.exe scripts\\check_find_keywords_on_video_frame.py \
    --video "..." --game battlefield6 --timestamp-ms 123456 --use-gpu

Notes:
  - If --use-gpu is set and torch is loaded, OCRDetector should auto-switch
    to subprocess PaddleOCR (requires .venv_paddle).
"""

import argparse
import os
import sys
import json
import shutil

import cv2


try:
    from fuzzywuzzy import fuzz  # type: ignore
except Exception:
    from difflib import SequenceMatcher

    class _Fuzz:
        @staticmethod
        def ratio(a: str, b: str) -> int:
            return int(SequenceMatcher(None, a, b).ratio() * 100)

    fuzz = _Fuzz()


# Ensure repo-root imports (consistent with main.py behavior)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--game", required=True)
    p.add_argument("--timestamp-ms", type=float, required=True)
    p.add_argument("--use-gpu", action="store_true", help="Enable GPU OCR (may use subprocess on Windows)")
    p.add_argument(
        "--frames-dir",
        default=None,
        help=(
            "Optional directory containing pre-extracted frames named "
            "frame_{timestamp_ms}.jpg (e.g. temp/pipeline_xxx/frames)."
        ),
    )
    p.add_argument(
        "--checkpoint",
        default=None,
        help="Optional checkpoint JSON path; if provided, frames-dir will be inferred from results.frames[0].",
    )
    p.add_argument(
        "--window-ms",
        type=int,
        default=0,
        help="Scan around timestamp +/-window_ms (0 disables scanning).",
    )
    p.add_argument(
        "--step-ms",
        type=int,
        default=100,
        help="Step size for scanning window.",
    )
    p.add_argument(
        "--roi",
        default=None,
        help="Optional ROI override as rel coords: x,y,w,h (0-1). If omitted, uses detection.killfeed_roi from config.",
    )
    p.add_argument(
        "--keywords",
        default=None,
        help="Override keywords (comma-separated), e.g. \"击杀,爆头,KILL\".",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override similarity threshold (0-1).",
    )
    p.add_argument(
        "--print-detections",
        action="store_true",
        help="Print top detections for the best frame.",
    )
    p.add_argument(
        "--save-best-frame-dir",
        default=None,
        help="If set, save the best (or center) extracted frame into this directory for manual inspection.",
    )
    return p.parse_args()


def _build_timestamps(center_ms: int, window_ms: int, step_ms: int) -> list[int]:
    if window_ms <= 0:
        return [int(center_ms)]
    step_ms = max(1, int(step_ms))
    start = max(0, int(center_ms) - int(window_ms))
    end = int(center_ms) + int(window_ms)
    return list(range(start, end + 1, step_ms))


def _infer_frames_dir_from_checkpoint(checkpoint_path: str) -> str | None:
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        frames = d.get("results", {}).get("frames", [])
        if not frames:
            return None
        return os.path.dirname(frames[0])
    except Exception:
        return None


def _try_load_preextracted_frame(frames_dir: str, ts: int):
    for ext in (".jpg", ".png", ".jpeg"):
        p = os.path.join(frames_dir, f"frame_{ts}{ext}")
        if os.path.exists(p):
            img = cv2.imread(p)
            return p, img
    return None, None


def main() -> int:
    args = _parse_args()

    # Import torch first to simulate real pipeline (YOLO loads torch)
    import torch  # noqa: F401

    from src.config.config_loader import get_config
    from src.video.frame_extractor import FrameExtractor
    from src.utils.temp_manager import temp_manager
    from src.ai.ocr_detector import OCRDetector

    config = get_config(game_name=args.game)
    det_cfg = config.get("detection", {})
    ocr_cfg = det_cfg.get("ocr", {})

    roi_rel = None
    if args.roi:
        parts = [float(x.strip()) for x in args.roi.split(",")]
        if len(parts) != 4:
            raise ValueError("--roi must be x,y,w,h")
        roi_rel = parts
    else:
        roi_rel = det_cfg.get("killfeed_roi", None)

    keywords = ocr_cfg.get("keywords", ["击杀", "KILL"])

    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    similarity_threshold = float(ocr_cfg.get("similarity_threshold", 0.8))
    if args.threshold is not None:
        similarity_threshold = float(args.threshold)

    frames_dir = args.frames_dir
    if args.checkpoint and not frames_dir:
        frames_dir = _infer_frames_dir_from_checkpoint(args.checkpoint)

    if frames_dir:
        frames_dir = os.path.abspath(frames_dir)
        print(f"frames_dir={frames_dir}")

    extractor = None
    if not frames_dir:
        extractor = FrameExtractor(
            ffmpeg_path=config.get("video", {}).get("ffmpeg_path", "ffmpeg"),
            hwaccel=config.get("video", {}).get("hwaccel", "cuda"),
        )

    ocr = OCRDetector(lang=ocr_cfg.get("lang", "ch"), use_gpu=bool(args.use_gpu))
    try:
        print(f"engine_type={getattr(ocr, 'engine_type', None)}")
        print(f"roi_rel={roi_rel}")
        print(f"keywords={keywords}")
        print(f"similarity_threshold={similarity_threshold}")

        timestamps = _build_timestamps(int(args.timestamp_ms), int(args.window_ms), int(args.step_ms))
        print(f"scan_timestamps_ms={timestamps[:5]}... total={len(timestamps)}")

        best = {
            "found": False,
            "matched_keyword": None,
            "text": None,
            "confidence": 0.0,
            "similarity": 0.0,
            "bbox": None,
            "timestamp_ms": None,
        }
        best_detections = []

        extracted_ok = 0
        read_ok = 0
        frames_with_detections = 0
        total_detections = 0

        best_frame_path = None

        for ts in timestamps:
            frame_path = None
            try:
                frame = None
                if frames_dir:
                    frame_path, frame = _try_load_preextracted_frame(frames_dir, int(ts))
                    if frame_path and frame is not None:
                        extracted_ok += 1
                        read_ok += 1
                else:
                    assert extractor is not None
                    frame_path = temp_manager.get_temp_path(f"ocr_frame_{ts}.jpg", subdir="ocr_regression")
                    extractor.extract_single_frame(args.video, float(ts), frame_path)
                    if not os.path.exists(frame_path):
                        continue
                    extracted_ok += 1
                    frame = cv2.imread(frame_path)
                if frame is None:
                    continue
                if not frames_dir:
                    read_ok += 1

                h, w = frame.shape[:2]
                roi_px = None
                if roi_rel:
                    x, y, rw, rh = roi_rel
                    roi_px = [int(x * w), int(y * h), int(rw * w), int(rh * h)]

                detections = ocr.detect_text(frame, roi=roi_px)
                if not detections:
                    continue

                frames_with_detections += 1
                total_detections += len(detections)

                for det in detections:
                    text = (det.get("text") or "").strip()
                    if not text:
                        continue
                    for kw in keywords:
                        sim = fuzz.ratio(text.lower(), kw.lower()) / 100.0
                        if sim > best["similarity"]:
                            best.update(
                                {
                                    "found": sim >= similarity_threshold,
                                    "matched_keyword": kw,
                                    "text": text,
                                    "confidence": float(det.get("confidence") or 0.0),
                                    "similarity": float(sim),
                                    "bbox": det.get("bbox"),
                                    "timestamp_ms": int(ts),
                                }
                            )
                            best_detections = detections
                            best_frame_path = frame_path
            finally:
                try:
                    # 如果需要保存最佳帧，则先不删；最后统一处理
                    if frames_dir:
                        # pre-extracted frames are not owned by this script
                        pass
                    elif args.save_best_frame_dir and best_frame_path == frame_path:
                        pass
                    else:
                        if frame_path:
                            os.remove(frame_path)
                except Exception:
                    pass

        print(
            {
                "extracted_ok": extracted_ok,
                "read_ok": read_ok,
                "frames_with_detections": frames_with_detections,
                "total_detections": total_detections,
            }
        )
        print("best=", best)

        # 保存最佳（或中心）帧，方便人工确认 ROI/文字位置
        if args.save_best_frame_dir:
            os.makedirs(args.save_best_frame_dir, exist_ok=True)
            save_ts = best.get("timestamp_ms")
            if save_ts is None:
                save_ts = int(args.timestamp_ms)

            out_path = os.path.join(args.save_best_frame_dir, f"frame_{save_ts}.jpg")
            if frames_dir:
                src, _img = _try_load_preextracted_frame(frames_dir, int(save_ts))
                if src and os.path.exists(src):
                    shutil.copyfile(src, out_path)
                else:
                    print(f"warning: pre-extracted frame not found for {save_ts}ms")
            else:
                assert extractor is not None
                extractor.extract_single_frame(args.video, float(save_ts), out_path)
            print(f"saved_frame={out_path}")

        if args.print_detections and best_detections:
            # Print top 10 by confidence
            top = sorted(best_detections, key=lambda d: float(d.get("confidence") or 0.0), reverse=True)[:10]
            print("top_detections=")
            for d in top:
                print(
                    {
                        "text": d.get("text"),
                        "confidence": d.get("confidence"),
                        "bbox": d.get("bbox"),
                    }
                )

        # 如果完全没有 detections，额外对中心帧做一次全图 OCR（帮助判断是不是 ROI/阈值问题）
        if args.print_detections and not best_detections:
            debug_path = temp_manager.get_temp_path("ocr_debug_center.jpg", subdir="ocr_regression")
            try:
                frame = None
                if frames_dir:
                    _p, frame = _try_load_preextracted_frame(frames_dir, int(args.timestamp_ms))
                else:
                    assert extractor is not None
                    extractor.extract_single_frame(args.video, float(args.timestamp_ms), debug_path)
                    frame = cv2.imread(debug_path)
                if frame is not None:
                    dets = ocr.detect_text(frame, roi=None)
                    print(f"center_frame_full_detections={len(dets)}")
                    for d in sorted(dets, key=lambda x: float(x.get("confidence") or 0.0), reverse=True)[:10]:
                        print({"text": d.get("text"), "confidence": d.get("confidence"), "bbox": d.get("bbox")})
            finally:
                try:
                    if not frames_dir:
                        os.remove(debug_path)
                except Exception:
                    pass

        return 0
    finally:
        ocr.close()


if __name__ == "__main__":
    raise SystemExit(main())
