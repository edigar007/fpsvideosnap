import os
import subprocess
from typing import Optional
from src.utils.logger import logger

class ClipCutter:
    """Handles precise video segment cutting using FFmpeg."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", hwaccel: Optional[str] = "cuda"):
        self.ffmpeg_path = ffmpeg_path
        self.hwaccel = hwaccel

    def cut_segment(self, input_path: str, output_path: str, start_sec: float, duration_sec: float):
        """
        Cuts a segment from the video.
        Uses fast seek and re-encoding for precision.
        """
        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Optimization: We use hwaccel if available for decoding.
        # For cutting highlights, we usually want to re-encode to ensure 
        # frames are accurate (especially if we want to add transitions later).
        
        cmd = [self.ffmpeg_path]
        
        if self.hwaccel == "cuda":
            cmd.extend(["-hwaccel", "cuda"])
            
        cmd.extend([
            "-ss", f"{start_sec:.3f}",
            "-t", f"{duration_sec:.3f}",
            "-i", input_path,
        ])
        
        # Audio/Video encoding settings
        if self.hwaccel == "cuda":
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "medium"])
            
        cmd.extend([
            "-b:v", "15M",   # High bitrate for quality
            "-c:a", "aac",    # Ensure audio is compatible
            "-y",             # Overwrite output
            output_path
        ])
        
        logger.info(f"Cutting segment: {start_sec}s for {duration_sec}s -> {os.path.basename(output_path)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"FFmpeg output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg cut failed: {e.stderr}")
            raise RuntimeError(f"Failed to cut video segment: {e}")
