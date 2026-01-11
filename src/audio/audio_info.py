import json
import subprocess
import os
from typing import Dict, Any, Optional
from src.utils.logger import logger

class AudioInfo:
    """Extracts and validates audio metadata using ffprobe."""
    
    SUPPORTED_FORMATS = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg'}

    def __init__(self, audio_path: str):
        self.audio_path = os.path.abspath(audio_path)
        self.metadata: Optional[Dict[str, Any]] = None
        
        if not os.path.exists(self.audio_path):
            raise FileNotFoundError(f"Audio file not found: {self.audio_path}")
            
        self._validate_format()
        self.metadata = self.get_metadata()

    def _validate_format(self):
        """Validates if the audio format is supported."""
        _, ext = os.path.splitext(self.audio_path)
        if ext.lower() not in self.SUPPORTED_FORMATS:
            # We also check if it might be a video file containing audio
            from src.video.video_info import VideoInfo
            try:
                VideoInfo.SUPPORTED_FORMATS
                if ext.lower() in VideoInfo.SUPPORTED_FORMATS:
                    return # Allow video files as audio sources
            except:
                pass
            logger.warning(f"Audio format {ext} not in standard list, but attempting to probe.")

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
            self.audio_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Find the audio stream
            audio_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), None)
            if not audio_stream:
                raise ValueError(f"No audio stream found in the file: {self.audio_path}")
            
            format_info = data.get('format', {})
            
            self.metadata = {
                'duration': float(format_info.get('duration', 0)),
                'format': format_info.get('format_name'),
                'sample_rate': int(audio_stream.get('sample_rate', 0)),
                'channels': int(audio_stream.get('channels', 0)),
                'bit_rate': int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else 0,
                'codec': audio_stream.get('codec_name')
            }
            return self.metadata
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to get audio metadata for {self.audio_path}: {e}")
            raise RuntimeError(f"Could not probe audio file: {e}")

    @property
    def duration(self) -> float:
        return self.metadata.get('duration', 0.0) if self.metadata else 0.0

    @property
    def sample_rate(self) -> int:
        return self.metadata.get('sample_rate', 0) if self.metadata else 0

    @property
    def format_name(self) -> str:
        return self.metadata.get('format', 'unknown') if self.metadata else 'unknown'
