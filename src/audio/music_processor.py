import subprocess
import os
from src.utils.logger import logger
from src.utils.temp_manager import temp_manager
from src.audio.audio_info import AudioInfo

class MusicProcessor:
    """Processes background music to match target video duration."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def process_music(self, music_path: str, target_duration: float, output_path: str = None) -> str:
        """
        Adjusts music to match target duration.
        Loops if short, trims with fade-out if long.
        """
        if not os.path.exists(music_path):
            raise FileNotFoundError(f"Music file not found: {music_path}")

        if output_path is None:
            output_path = temp_manager.get_temp_path("processed_music.wav")

        info = AudioInfo(music_path)
        music_duration = info.duration
        
        logger.info(f"Processing music: {music_path} ({music_duration}s) -> {target_duration}s")

        # Command to loop and trim
        # -stream_loop -1 loops the input indefinitely
        # -t target_duration stops the output at target_duration
        # afade=t=out:st=...:d=... adds fade out
        
        fade_duration = 2.0  # Default 2 seconds fade out
        if target_duration < fade_duration:
            fade_duration = target_duration * 0.2
            
        fade_start = target_duration - fade_duration
        
        # We use a complex filter to handle looping and fading
        # 'aloop=loop=-1:size=2e9' is another way, but simpler is -stream_loop -1 on input
        
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-stream_loop', '-1',  # Loop input infinitely
            '-i', music_path,
            '-t', str(target_duration),
            '-filter_complex', f'afade=t=out:st={fade_start}:d={fade_duration}',
            '-c:a', 'pcm_s16le', # Use WAV for intermediate to avoid quality loss/encoding issues
            output_path
        ]
        
        try:
            logger.debug(f"Running ffmpeg music processing: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg music processing failed: {e.stderr.decode()}")
            raise RuntimeError(f"Music processing failed: {e}")

    def validate_music(self, music_path: str) -> bool:
        """Validates if music file exists and is readable."""
        if not music_path or not os.path.exists(music_path):
            return False
        try:
            AudioInfo(music_path)
            return True
        except Exception:
            return False
