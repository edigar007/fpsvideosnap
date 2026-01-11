import json
import subprocess
import os
from typing import Dict, Any, Optional
from src.utils.logger import logger

class VideoInfo:
    """Extracts and validates video metadata using ffprobe."""
    
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mkv', '.mov'}

    def __init__(self, video_path: str):
        self.video_path = os.path.abspath(video_path)
        self.metadata: Optional[Dict[str, Any]] = None
        
        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"Video file not found: {self.video_path}")
            
        self._validate_format()
        self.metadata = self.get_metadata()

    def _validate_format(self):
        """Validates if the video format is supported."""
        _, ext = os.path.splitext(self.video_path)
        if ext.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported video format: {ext}. Supported: {self.SUPPORTED_FORMATS}")

    def get_metadata(self) -> Dict[str, Any]:
        """Fetches metadata using ffprobe and returns it as a dictionary."""
        if self.metadata:
            return self.metadata
            
        cmd = [
            'ffprobe', 
            '-v', 'quiet', 
            '-print_format', 'json', 
            '-show_format', 
            '-show_streams', 
            self.video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Find the video stream
            video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
            if not video_stream:
                raise ValueError("No video stream found in the file.")
                
            format_info = data.get('format', {})
            
            # Extract common properties
            metadata = {
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'fps': self._parse_fps(video_stream.get('r_frame_rate', '0/0')),
                'duration': float(format_info.get('duration', 0.0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'codec': video_stream.get('codec_name', 'unknown'),
                'total_frames': int(video_stream.get('nb_frames', 0)) if video_stream.get('nb_frames', 'N/A') != 'N/A' else None
            }
            
            logger.debug(f"Video Metadata for {os.path.basename(self.video_path)}: {metadata}")
            return metadata
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe failed for {self.video_path}: {e.stderr}")
            raise RuntimeError(f"Failed to extract video metadata: {e}")
        except Exception as e:
            logger.error(f"Error parsing metadata: {e}")
            raise

    def _parse_fps(self, fps_str: str) -> float:
        """Parses FFmpeg's fractional frame rate (e.g., '60/1' or '30000/1001')."""
        try:
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                return num / den if den != 0 else 0.0
            return float(fps_str)
        except (ValueError, ZeroDivisionError):
            return 0.0

    @property
    def width(self) -> int: return self.metadata['width']
    
    @property
    def height(self) -> int: return self.metadata['height']
    
    @property
    def fps(self) -> float: return self.metadata['fps']
    
    @property
    def duration(self) -> float: return self.metadata['duration']
