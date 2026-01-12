import os
import subprocess
from typing import Optional
from src.utils.logger import logger

class ClipCutter:
    """Handles precise video segment cutting using FFmpeg."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", hwaccel: Optional[str] = "cuda"):
        self.ffmpeg_path = ffmpeg_path
        self.hwaccel = hwaccel

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
        
        logger.info(f"Cutting segment (re-encode): {start_sec}s for {duration_sec}s -> {os.path.basename(output_path)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"FFmpeg output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg cut failed: {e.stderr}")
            raise RuntimeError(f"Failed to cut video segment: {e}")
    
    def _try_stream_copy(self, input_path: str, output_path: str, start_sec: float, duration_sec: float) -> bool:
        """
        TASK-009: Attempt fast stream copy cutting.
        Returns True if successful, False if it fails (caller should re-encode).
        """
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss", f"{start_sec:.3f}",
            "-t", f"{duration_sec:.3f}",
            "-i", input_path,
            "-c", "copy",
            output_path
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug("Stream copy successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.debug(f"Stream copy failed: {e.stderr}")
            return False
