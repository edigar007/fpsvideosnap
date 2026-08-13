import os
import subprocess
import json
import re
from typing import List, Optional
from src.utils.logger import logger

class FrameExtractor:
    """Extracts frames from video using FFmpeg with hardware acceleration support."""
    
    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        hwaccel: Optional[str] = "cuda",
        mode: str = "bulk",
        ffprobe_path: str = "ffprobe",
    ):
        self.ffmpeg_path = ffmpeg_path
        self.hwaccel = hwaccel
        self.mode = mode
        self.ffprobe_path = ffprobe_path

    def _ffmpeg_base_cmd(self) -> List[str]:
        cmd = [self.ffmpeg_path]
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
        return cmd

    def _extract_frames_bulk(
        self,
        video_path: str,
        output_dir: str,
        interval_ms: int = 100,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[str]:
        """Bulk extract frames in a single ffmpeg run.

        Strategy:
        - Use ffmpeg filter fps to sample frames at a fixed interval.
        - Use showinfo to read actual pts_time for each output frame.
        - Rename output to frame_{timestamp_ms}.jpg, using parsed pts_time.

        This avoids per-frame ffmpeg startup cost while keeping accurate timestamp mapping.
        """
        video_path = os.path.abspath(video_path)
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # Temporary sequential names; we rename using showinfo mapping afterwards
        tmp_pattern = os.path.join(output_dir, "tmp_%06d.jpg")

        fps = 1000.0 / float(interval_ms)
        vf = f"fps={fps},showinfo"

        cmd = self._ffmpeg_base_cmd()
        if start_ms is not None and start_ms > 0:
            cmd.extend(["-ss", str(float(start_ms) / 1000.0)])
        cmd.extend(
            [
                "-hide_banner",
                "-loglevel",
                "info",
                "-i",
                video_path,
            ]
        )
        if end_ms is not None and start_ms is not None and end_ms > start_ms:
            duration_s = float(end_ms - start_ms) / 1000.0
            cmd.extend(["-t", str(duration_s)])

        cmd.extend(
            [
                "-vf",
                vf,
                "-vsync",
                "vfr",
                "-q:v",
                "2",
                "-start_number",
                "0",
                "-y",
                tmp_pattern,
            ]
        )

        logger.info(
            f"Extracting frames (bulk) from {os.path.basename(video_path)} "
            f"interval={interval_ms}ms via ffmpeg filter..."
        )

        # Parse showinfo lines from stderr
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            logger.error(f"FFmpeg bulk extraction failed: {proc.stderr[-2000:]}")
            raise RuntimeError("FFmpeg bulk extraction failed")

        # Try multiple regex patterns for ffmpeg showinfo compatibility
        showinfo_patterns = [
            re.compile(r"showinfo.*? n:\s*(\d+).*? pts_time:\s*([0-9\.]+)"),
            re.compile(r"\[showinfo\].*?n:\s*(\d+).*?pts_time:\s*([0-9\.]+)"),
            re.compile(r"n:\s*(\d+).*?pts_time:\s*([0-9\.]+)"),
        ]
        mapping = []
        offset_ms = int(start_ms) if start_ms is not None else 0
        for line in (proc.stderr or "").splitlines():
            for pat in showinfo_patterns:
                m = pat.search(line)
                if m:
                    n = int(m.group(1))
                    pts_time = float(m.group(2))
                    ts_ms = offset_ms + int(round(pts_time * 1000.0))
                    mapping.append({"n": n, "pts_time": pts_time, "timestamp_ms": ts_ms})
                    break

        if not mapping:
            logger.warning("No showinfo mapping parsed from bulk extraction; falling back to precise mode")
            raise RuntimeError("Bulk showinfo mapping failed")

        # Rename tmp_%06d.jpg -> frame_{timestamp_ms}.jpg
        final_files: List[str] = []
        used_names = set()
        for item in mapping:
            n = item["n"]
            ts_ms = item["timestamp_ms"]
            src = os.path.join(output_dir, f"tmp_{n:06d}.jpg")
            if not os.path.exists(src):
                # If ffmpeg skipped writing due to filter nuances, skip
                continue

            base_name = f"frame_{ts_ms}.jpg"
            dst = os.path.join(output_dir, base_name)
            if dst in used_names or os.path.exists(dst):
                # Collision safety
                k = 1
                while True:
                    alt = os.path.join(output_dir, f"frame_{ts_ms}_{k}.jpg")
                    if alt not in used_names and not os.path.exists(alt):
                        dst = alt
                        break
                    k += 1

            os.replace(src, dst)
            used_names.add(dst)
            final_files.append(dst)

        # Cleanup any remaining tmp files
        for name in os.listdir(output_dir):
            if name.startswith("tmp_") and name.lower().endswith(".jpg"):
                try:
                    os.remove(os.path.join(output_dir, name))
                except OSError as exc:
                    logger.debug(f"Failed to remove temporary frame {name}: {exc}")

        # Save mapping for debugging
        try:
            mapping_path = os.path.join(output_dir, "frames_mapping.json")
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.debug(f"Failed to save frame timestamp mapping: {exc}")

        logger.info(f"Bulk extracted {len(final_files)} frames")
        return final_files

    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        interval_ms: int = 100,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[str]:
        """
        Extracts frames at regular intervals with precise timestamps.
        Naming convention: frame_{timestamp_ms}.jpg
        
        使用循环的 -ss 参数来确保每帧的时间戳完全准确。
        这比过滤器方法慢，但可以保证时间戳的绝对精确性，避免累积误差。
        """
        if self.mode == "bulk":
            try:
                return self._extract_frames_bulk(
                    video_path,
                    output_dir,
                    interval_ms=interval_ms,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            except Exception as e:
                logger.warning(f"Bulk extraction failed, falling back to precise mode: {e}")

        video_path = os.path.abspath(video_path)
        output_dir = os.path.abspath(output_dir)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 首先获取视频时长
        try:
            probe_cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-of", "csv=p=0",
                video_path
            ]
            probe_result = subprocess.run(probe_cmd, check=True, capture_output=True, text=True)
            duration_sec = float(probe_result.stdout.strip())
            logger.debug(f"Video duration: {duration_sec:.2f}s")
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
            raise RuntimeError("Cannot determine video duration") from e
        
        interval_sec = interval_ms / 1000.0
        total_frames = int(duration_sec / interval_sec) + 1
        
        logger.info(
            f"Extracting {total_frames} frames from {os.path.basename(video_path)} "
            f"with interval {interval_ms}ms..."
        )
        logger.warning(
            "Using precise timestamp extraction. This is ~10-100x slower than bulk mode "
            f"because it spawns {total_frames} separate ffmpeg processes. "
            "Consider fixing bulk mode or reducing frame interval."
        )
        
        final_files = []
        timestamp_ms = 0
        frame_count = 0
        
        # 使用进度条
        from src.utils.progress import create_progress_bar
        pbar = create_progress_bar(total=total_frames, desc="Extracting Frames")
        
        while timestamp_ms < duration_sec * 1000:
            timestamp_sec = timestamp_ms / 1000.0
            frame_filename = f"frame_{timestamp_ms}.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            
            # 使用 -ss 精确定位并提取单帧
            # -ss 在 -i 之前可以快速定位（关键帧），在 -i 之后可以精确定位
            # 使用双重 -ss 策略：先快速定位到附近，再精确提取
            cmd = [self.ffmpeg_path]
            
            cmd.extend(["-ss", str(timestamp_sec)])  # 快速定位到附近的关键帧
            
            if self.hwaccel == "cuda":
                cmd.extend(["-hwaccel", "cuda"])
            
            cmd.extend([
                "-i", video_path,
                "-ss", "0",  # 从定位点开始精确提取第一帧
                "-frames:v", "1",
                "-q:v", "2",
                "-y",  # 覆盖已存在的文件
                frame_path
            ])
            
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
                final_files.append(frame_path)
                frame_count += 1
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                logger.warning(f"Failed to extract frame at {timestamp_ms}ms: {e}")
            
            timestamp_ms += interval_ms
            pbar.update(1)
        
        pbar.close()
        
        logger.info(f"Successfully extracted {frame_count} frames")
        logger.debug(f"Time range: 0ms to {timestamp_ms - interval_ms}ms")
        return final_files

    def extract_single_frame(self, video_path: str, timestamp_ms: float, output_path: str):
        """Extracts a single frame at a specific timestamp."""
        ss_time = timestamp_ms / 1000.0
        
        cmd = [self.ffmpeg_path]
        
        # 使用双重 -ss 策略确保精确性
        cmd.extend(["-ss", str(ss_time)])
        
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend([
            "-i", video_path,
            "-ss", "0",
            "-frames:v", "1",
            "-q:v", "2",
            "-y",
            output_path
        ])
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg single frame extraction failed at {timestamp_ms}ms: {e.stderr}")
            raise
