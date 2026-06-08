import os
import subprocess
from typing import Optional, Dict, Tuple
from src.utils.logger import logger

class ClipCutter:
    """Handles precise video segment cutting using FFmpeg."""
    
    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        hwaccel: Optional[str] = "cuda",
        ffprobe_path: str = "ffprobe",
        align_to_keyframes: bool = False,
        keyframe_scan_window_s: float = 10.0,
    ):
        self.ffmpeg_path = ffmpeg_path
        self.hwaccel = hwaccel
        self.ffprobe_path = ffprobe_path
        self.align_to_keyframes = align_to_keyframes
        self.keyframe_scan_window_s = float(keyframe_scan_window_s)
        self._keyframe_cache: Dict[Tuple[str, int], Optional[float]] = {}

    def _get_previous_keyframe_time(self, input_path: str, target_sec: float) -> Optional[float]:
        """Find the nearest keyframe time <= target_sec.

        Uses ffprobe with a sliding window near target_sec to avoid scanning the whole file.
        """
        if target_sec <= 0:
            return 0.0

        cache_key = (input_path, int(target_sec * 10))  # 100ms buckets
        if cache_key in self._keyframe_cache:
            return self._keyframe_cache[cache_key]

        window = max(0.5, self.keyframe_scan_window_s)
        start = max(0.0, target_sec - window)
        duration = (target_sec - start) + 0.25  # small epsilon to include target

        # Use packet flags ("K") to find key packets. This tends to be more reliable
        # across codecs/containers than relying on decoded frame metadata.
        cmd = [
            self.ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-read_intervals",
            f"{start:.3f}%+{duration:.3f}",
            "-show_packets",
            "-show_entries",
            "packet=pts_time,flags",
            "-of",
            "csv=p=0",
            input_path,
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            key_times = []
            for line in (result.stdout or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2:
                    continue
                pts_s, flags = parts[0], parts[1]
                if pts_s in ("N/A", ""):
                    continue
                if "K" not in flags:
                    continue
                try:
                    key_times.append(float(pts_s))
                except ValueError:
                    continue

            # Prefer the last key packet not after target
            epsilon = 0.10
            candidates = [t for t in key_times if t <= (target_sec + epsilon)]
            keyframe_time = max(candidates) if candidates else None
            self._keyframe_cache[cache_key] = keyframe_time
            return keyframe_time
        except subprocess.CalledProcessError as e:
            logger.debug(f"ffprobe keyframe query failed: {e.stderr}")
            self._keyframe_cache[cache_key] = None
            return None

    def cut_segment(self, input_path: str, output_path: str, start_sec: float, duration_sec: float, 
                    use_stream_copy: bool = False):
        """
        Cuts a segment from the video.
        
        Args:
            input_path: Source video file
            output_path: Destination clip file
            start_sec: Start time in seconds
            duration_sec: Duration in seconds
            use_stream_copy: If True, use '-c copy' for fast cutting (TASK-009)
        
        TASK-009: Prefer stream copy when transition_type is 'none' or single-clip exports.
        Falls back to re-encode if stream copy fails.
        """
        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)

        # When stream-copying, we must start on a keyframe to avoid corruption.
        # When re-encoding, we can keep the requested start time but should decode from a keyframe.
        decode_from_keyframe = None
        if self.align_to_keyframes and start_sec > 0 and duration_sec > 0:
            decode_from_keyframe = self._get_previous_keyframe_time(input_path, start_sec)
            if decode_from_keyframe is not None:
                logger.info(
                    f"Keyframe near {start_sec:.3f}s: {decode_from_keyframe:.3f}s (for clean start)"
                )

        if use_stream_copy and decode_from_keyframe is not None and decode_from_keyframe < (start_sec - 0.001):
            # For stream copy, shift the clip start earlier to land on a keyframe.
            end_sec = start_sec + duration_sec
            delta = start_sec - decode_from_keyframe
            logger.info(
                f"Aligning stream-copy clip start to keyframe: {start_sec:.3f}s -> {decode_from_keyframe:.3f}s "
                f"(extend duration by +{delta:.3f}s)"
            )
            start_sec = decode_from_keyframe
            duration_sec = max(0.001, end_sec - start_sec)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Try stream copy first if requested
        if use_stream_copy:
            logger.info(f"Attempting stream copy for fast cutting: {start_sec}s for {duration_sec}s")
            if self._try_stream_copy(input_path, output_path, start_sec, duration_sec):
                return
            logger.warning("Stream copy failed, falling back to re-encode")
        
        # Standard re-encode path
        cmd = [self.ffmpeg_path]
        
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])

        # Decode starting point: prefer the previous keyframe (more robust for open-GOP sources).
        # Keep output clip start at the originally requested start_sec via the 2nd -ss.
        if decode_from_keyframe is not None and decode_from_keyframe > 0:
            demux_seek = decode_from_keyframe
        else:
            demux_seek = max(0.0, start_sec - 10.0)  # conservative fallback warmup

        precise_seek = max(0.0, start_sec - demux_seek)

        cmd.extend([
            "-ss", f"{demux_seek:.3f}",
            "-i", input_path,
            "-ss", f"{precise_seek:.3f}",
            "-t", f"{duration_sec:.3f}",
        ])
        
        # Audio/Video encoding settings
        if self.hwaccel == "cuda":
            cmd.extend([
                "-c:v", "h264_nvenc", 
                "-preset", "p4",
                "-g", "120",      # GOP size: 每2秒一个关键帧(60fps*2)
                "-bf", "0",       # 禁用B帧，确保更好的随机访问
                "-forced-idr", "1",  # 强制关键帧为IDR，避免VLC开头花屏直到下一个IDR
                "-strict_gop", "1",  # 尽量保持稳定GOP结构
            ])
        else:
            cmd.extend([
                "-c:v", "libx264", 
                "-preset", "medium",
                "-g", "120",
                "-bf", "0",
            ])
            
        cmd.extend([
            "-b:v", "15M",    # High bitrate for quality
            "-pix_fmt", "yuv420p",  # 确保像素格式一致
            # Force the first frame of the output to be a keyframe/IDR for maximum compatibility.
            "-force_key_frames", "0",
            "-c:a", "aac",    # Ensure audio is compatible
            "-y",             # Overwrite output
            output_path
        ])
        
        logger.info(f"Cutting segment (re-encode): {start_sec}s for {duration_sec}s -> {os.path.basename(output_path)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"FFmpeg output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg cut failed: {e.stderr}")
            raise RuntimeError(f"Failed to cut video segment: {e}") from e
    
    def _try_stream_copy(self, input_path: str, output_path: str, start_sec: float, duration_sec: float) -> bool:
        """
        TASK-009: Attempt fast stream copy cutting.
        Returns True if successful, False if it fails (caller should re-encode).
        """
        cmd = [
            self.ffmpeg_path,
            "-y",
            # Input seek: aligns to nearest keyframe (fast). With align_to_keyframes enabled,
            # we already try to snap start_sec to an actual keyframe time.
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            input_path,
            # Output duration (more accurate than using -t as input option for stream copy)
            "-t",
            f"{duration_sec:.3f}",
            "-c",
            "copy",
        ]

        # Improve player compatibility (notably VLC) when we are explicitly in
        # keyframe-aligned stream copy mode.
        if self.align_to_keyframes:
            cmd.extend(
                [
                    "-fflags",
                    "+genpts",
                    "-avoid_negative_ts",
                    "make_zero",
                    "-max_interleave_delta",
                    "0",
                    "-movflags",
                    "+faststart",
                ]
            )

        cmd.append(output_path)
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug("Stream copy successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.debug(f"Stream copy failed: {e.stderr}")
            return False
