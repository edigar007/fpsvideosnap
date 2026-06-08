"""Compare old pipeline frames vs new bulk-extracted frames.

Goal:
- Run the new bulk extraction into a new directory.
- Compare selected timestamps against an existing pipeline frames directory.

Usage (from repo root):
  .venv\\Scripts\\python.exe scripts\\compare_frame_extraction.py \
    --video "G:\\Video\\...\\input.mp4" \
    --checkpoint "temp\\checkpoint_....json" \
    --out-dir "temp\\frame_compare" \
    --start-ms 60000 --end-ms 72000

Output:
- Prints per-frame diff stats (MAE) and summary.
- Saves a few side-by-side previews for the worst mismatches.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np


# Ensure repo-root imports (consistent with main.py behavior)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--checkpoint", required=True, help="Checkpoint JSON to infer old frames dir")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--interval-ms", type=int, default=1000)
    p.add_argument("--start-ms", type=int, default=0)
    p.add_argument("--end-ms", type=int, default=120000)
    p.add_argument("--max-previews", type=int, default=6)
    return p.parse_args()


def _infer_old_frames_dir(checkpoint_path: str) -> Path:
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    frames = d.get("results", {}).get("frames", [])
    if not frames:
        raise RuntimeError("checkpoint has no results.frames")
    return Path(frames[0]).parent


def _load_frame(path: Path) -> np.ndarray | None:
    img = cv2.imread(str(path))
    return img


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))))


def _side_by_side(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return np.concatenate([a, b], axis=1)


def main() -> int:
    args = _parse_args()

    old_dir = _infer_old_frames_dir(args.checkpoint)

    out_dir = Path(args.out_dir)
    new_dir = out_dir / "new_frames"
    previews_dir = out_dir / "previews"
    new_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    # Run new bulk extraction
    from src.video.frame_extractor import FrameExtractor
    from src.config.config_loader import get_config

    # Use config hwaccel/ffmpeg_path if present
    cfg = get_config(game_name=None)
    video_cfg = cfg.get("video", {})

    extractor = FrameExtractor(
        ffmpeg_path=video_cfg.get("ffmpeg_path", "ffmpeg"),
        hwaccel=video_cfg.get("hwaccel", "cuda"),
        mode="bulk",
    )

    print(f"old_frames_dir={old_dir}")
    print(f"new_frames_dir={new_dir}")

    extractor.extract_frames(
        args.video,
        str(new_dir),
        interval_ms=args.interval_ms,
        start_ms=args.start_ms,
        end_ms=args.end_ms,
    )

    # Build lookup for new frames by timestamp
    new_by_ts: dict[int, Path] = {}
    for p in new_dir.glob("frame_*.jpg"):
        stem = p.stem  # frame_12345 or frame_12345_1
        parts = stem.split("_")
        if len(parts) < 2:
            continue
        try:
            ts = int(parts[1])
        except Exception:
            continue
        new_by_ts.setdefault(ts, p)

    results = []
    for ts in range(args.start_ms, args.end_ms + 1, args.interval_ms):
        old_path = old_dir / f"frame_{ts}.jpg"
        if not old_path.exists():
            continue

        old_img = _load_frame(old_path)
        if old_img is None:
            continue

        # Find exact match first, else nearest within half-interval
        new_path = new_by_ts.get(ts)
        if new_path is None:
            tol = max(1, args.interval_ms // 2)
            candidates = [k for k in new_by_ts.keys() if abs(k - ts) <= tol]
            if candidates:
                nearest = min(candidates, key=lambda k: abs(k - ts))
                new_path = new_by_ts[nearest]

        if new_path is None or not new_path.exists():
            continue

        new_img = _load_frame(new_path)
        if new_img is None:
            continue

        mae = _mae(old_img, new_img)
        results.append((ts, int(new_path.stem.split("_")[1]), mae, old_path, new_path))

    if not results:
        print("No comparable frames found.")
        return 0

    results.sort(key=lambda x: x[2], reverse=True)
    maes = [r[2] for r in results]
    print(
        f"compared={len(results)} "
        f"mae_avg={float(np.mean(maes)):.3f} "
        f"mae_p95={float(np.percentile(maes, 95)):.3f} "
        f"mae_max={maes[0]:.3f}"
    )

    for ts, new_ts, mae, old_path, new_path in results[: args.max_previews]:
        print({"old_ts": ts, "new_ts": new_ts, "mae": mae, "old": str(old_path), "new": str(new_path)})
        old_img = _load_frame(old_path)
        new_img = _load_frame(new_path)
        if old_img is None or new_img is None:
            continue
        preview = _side_by_side(old_img, new_img)
        out = previews_dir / f"compare_old_{ts}_new_{new_ts}_mae_{mae:.2f}.jpg"
        cv2.imwrite(str(out), preview)

    print(f"previews_dir={previews_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
