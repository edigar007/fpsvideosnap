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
        Extracts frames at regular intervals.
        Naming convention: frame_{timestamp_ms}.jpg
        """
        video_path = os.path.abspath(video_path)
        output_dir = os.path.abspath(output_dir)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # FFmpeg command for interval-based extraction
        # Use fps filter to select frames based on interval
        # interval_ms = 100 -> 10 frames per second
        fps_filter = f"fps=1/({interval_ms}/1000)"
        
        cmd = [self.ffmpeg_path]
        
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend([
            "-i", video_path,
            "-vf", fps_filter,
            "-vsync", "vfr",
            "-q:v", "2", # High quality
            os.path.join(output_dir, "frame_%d.jpg")
        ])
        
        # Note: FFmpeg's sequential numbering doesn't directly give us timestamp_ms easily 
        # unless we do math or extract all frames.
        # But wait, TASK-013 says frame_{timestamp_ms}.jpg.
        # To get precise millisecond timestamps, we can use the 'setts' and 'frame_pts' or 
        # use a more complex output name. 
        # Actually, using '-vf fps=...' will give us frames at roughly that interval.
        # If we want exact timestamps in filenames, we might need a different approach 
        # or rename them after extraction based on index * interval.
        
        logger.info(f"Extracting frames from {os.path.basename(video_path)} with interval {interval_ms}ms...")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Now we rename to match frame_{timestamp_ms}.jpg
            # frame_1.jpg -> frame_0.jpg (0ms)
            # frame_2.jpg -> frame_100.jpg (100ms) ...
            extracted_files = sorted([f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")])
            final_files = []
            
            for i, filename in enumerate(extracted_files):
                timestamp_ms = i * interval_ms
                new_name = f"frame_{timestamp_ms}.jpg"
                old_path = os.path.join(output_dir, filename)
                new_path = os.path.join(output_dir, new_name)
                os.rename(old_path, new_path)
                final_files.append(new_path)
                
            return final_files
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg frame extraction failed: {e.stderr}")
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
