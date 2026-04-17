import subprocess
import os
from typing import Dict, Any
from src.utils.logger import logger
from src.utils.temp_manager import temp_manager
from src.audio.music_processor import MusicProcessor
from src.video.video_info import VideoInfo


class AudioMixer:
    """Mixes video audio with background music using FFmpeg."""

    def __init__(self, config: Dict[str, Any], ffmpeg_path: str = "ffmpeg"):
        self.config = config
        self.ffmpeg_path = ffmpeg_path
        self.music_processor = MusicProcessor(ffmpeg_path)

    def mix_audio(self, video_path: str, output_path: str = None) -> str:
        """
        Mixes original video audio with configured background music.
        """
        highlights_cfg = self.config.get('highlights', {})
        music_enabled = highlights_cfg.get('music_enabled', True)
        music_path = highlights_cfg.get('music_path')
        game_vol = highlights_cfg.get('game_volume', 0.5)
        music_vol = highlights_cfg.get('music_volume', 0.5)

        if not music_enabled or not music_path:
            logger.info("Music is disabled or path not provided, skipping audio mixing.")
            return video_path

        if not os.path.exists(music_path):
            logger.warning(f"Music file not found: {music_path}. Using original video audio.")
            return video_path

        if output_path is None:
            output_path = temp_manager.get_temp_path("mixed_video.mp4")

        try:
            v_info = VideoInfo(video_path)
            duration = v_info.duration
            processed_music = self.music_processor.process_music(music_path, duration)

            cmd = [
                self.ffmpeg_path,
                '-y',
                '-fflags', '+genpts',
                '-i', video_path,
                '-i', processed_music,
                '-filter_complex',
                f'[0:a]volume={game_vol}[a1];[1:a]volume={music_vol}[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=0[aout]',
                '-map', '0:v',
                '-map', '[aout]',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-movflags', '+faststart',
                '-avoid_negative_ts', 'make_zero',
                '-max_interleave_delta', '0',
                output_path
            ]

            logger.info(f"Mixing audio for {video_path} with {music_path}...")
            logger.debug(f"Running ffmpeg audio mixing: {' '.join(cmd)}")

            subprocess.run(cmd, check=True, capture_output=True)
            return output_path

        except Exception as e:
            logger.error(f"Audio mixing failed: {e}")
            raise RuntimeError(f"Audio mixing failed: {e}")
