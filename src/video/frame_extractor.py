import os
import subprocess
from typing import List, Optional
from src.utils.logger import logger

class FrameExtractor:
    """Extracts frames from video using FFmpeg with hardware acceleration support."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", hwaccel: Optional[str] = "cuda"):
        self.ffmpeg_path = ffmpeg_path
        self.hwaccel = hwaccel

    def extract_frames(self, video_path: str, output_dir: str, interval_ms: int = 100) -> List[str]:
        """
        Extracts frames at regular intervals with precise timestamps.
        Naming convention: frame_{timestamp_ms}.jpg
        
        使用循环的 -ss 参数来确保每帧的时间戳完全准确。
        这比过滤器方法慢，但可以保证时间戳的绝对精确性，避免累积误差。
        """
        video_path = os.path.abspath(video_path)
        output_dir = os.path.abspath(output_dir)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 首先获取视频时长
        try:
            probe_cmd = [
                "ffprobe",
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
            raise RuntimeError("Cannot determine video duration")
        
        interval_sec = interval_ms / 1000.0
        total_frames = int(duration_sec / interval_sec) + 1
        
        logger.info(f"Extracting {total_frames} frames from {os.path.basename(video_path)} with interval {interval_ms}ms...")
        logger.info("Using precise timestamp extraction (may take longer but ensures accuracy)")
        
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
