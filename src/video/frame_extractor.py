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
        
        使用精确的 select 过滤器来确保帧时间戳的准确性。
        select 表达式: 'eq(n,0)+gte(t-prev_selected_t,{interval_sec})'
        这会在时间轴上精确选择间隔为 interval_ms 的帧。
        """
        video_path = os.path.abspath(video_path)
        output_dir = os.path.abspath(output_dir)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 首先获取视频信息
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
            logger.warning(f"Failed to get video duration: {e}")
            duration_sec = None
        
        # 使用 select 过滤器配合 setpts 来精确提取帧
        # select='eq(n,0)+gte(t-prev_selected_t,{interval_sec})' 
        # 会在第 0 帧和之后每隔 interval_sec 秒选择一帧
        interval_sec = interval_ms / 1000.0
        
        # 使用 select 过滤器来精确选择帧
        select_filter = f"select='eq(n,0)+gte(t-prev_selected_t,{interval_sec})',setpts=N/FRAME_RATE/TB"
        
        cmd = [self.ffmpeg_path]
        
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend([
            "-i", video_path,
            "-vf", select_filter,
            "-vsync", "vfr",  # 可变帧率，保持精确时间戳
            "-q:v", "2",  # 高质量
            os.path.join(output_dir, "frame_%d.jpg")
        ])
        
        logger.info(f"Extracting frames from {os.path.basename(video_path)} with interval {interval_ms}ms...")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # 获取提取的帧文件列表
            extracted_files = sorted(
                [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")],
                key=lambda x: int(x.replace("frame_", "").replace(".jpg", ""))  # 按数字排序
            )
            
            final_files = []
            
            # 重命名为精确的时间戳
            # 关键修复：使用严格的时间戳计算，确保与检测时使用的时间戳一致
            for i, filename in enumerate(extracted_files):
                # 精确的时间戳计算：第 i 帧对应 i * interval_ms 毫秒
                timestamp_ms = i * interval_ms
                new_name = f"frame_{timestamp_ms}.jpg"
                old_path = os.path.join(output_dir, filename)
                new_path = os.path.join(output_dir, new_name)
                
                # 避免重复重命名
                if old_path != new_path:
                    try:
                        os.rename(old_path, new_path)
                    except FileExistsError:
                        # 如果目标文件已存在，先删除
                        os.remove(new_path)
                        os.rename(old_path, new_path)
                
                final_files.append(new_path)
            
            logger.info(f"Extracted {len(final_files)} frames")
            if len(final_files) > 0:
                logger.debug(f"Time range: 0ms to {(len(final_files)-1) * interval_ms}ms")
            
            return final_files
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg frame extraction failed: {e.stderr}")
            # 回退到简单的 fps 方法
            logger.warning("Falling back to simple fps filter method...")
            return self._extract_frames_simple(video_path, output_dir, interval_ms)
    
    def _extract_frames_simple(self, video_path: str, output_dir: str, interval_ms: int) -> List[str]:
        """简单的 fps 过滤器方法作为回退"""
        interval_sec = interval_ms / 1000.0
        target_fps = 1.0 / interval_sec
        fps_filter = f"fps={target_fps}"
        
        cmd = [self.ffmpeg_path]
        
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend([
            "-i", video_path,
            "-vf", fps_filter,
            "-vsync", "vfr",
            "-q:v", "2",
            os.path.join(output_dir, "frame_%d.jpg")
        ])
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            extracted_files = sorted(
                [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")],
                key=lambda x: int(x.replace("frame_", "").replace(".jpg", ""))
            )
            
            final_files = []
            for i, filename in enumerate(extracted_files):
                timestamp_ms = i * interval_ms
                new_name = f"frame_{timestamp_ms}.jpg"
                old_path = os.path.join(output_dir, filename)
                new_path = os.path.join(output_dir, new_name)
                
                if old_path != new_path:
                    try:
                        os.rename(old_path, new_path)
                    except FileExistsError:
                        os.remove(new_path)
                        os.rename(old_path, new_path)
                
                final_files.append(new_path)
            
            return final_files
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Fallback extraction also failed: {e.stderr}")
            raise RuntimeError(f"FFmpeg tool failed: {e}")

    def extract_single_frame(self, video_path: str, timestamp_ms: float, output_path: str):
        """Extracts a single frame at a specific timestamp."""
        ss_time = timestamp_ms / 1000.0
        
        cmd = [self.ffmpeg_path]
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend([
            "-ss", str(ss_time),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            output_path
        ])
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg single frame extraction failed at {timestamp_ms}ms: {e.stderr}")
            raise
