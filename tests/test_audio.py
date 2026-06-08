import os
import sys
import unittest
import shutil
import subprocess

# Add project root to python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.audio.audio_info import AudioInfo
from src.audio.music_processor import MusicProcessor
from src.audio.audio_mixer import AudioMixer
from src.config.config_loader import ConfigLoader


class TestAudioProcessing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create test audio and video files."""
        cls.test_dir = os.path.abspath("test_audio_output")
        os.makedirs(cls.test_dir, exist_ok=True)

        cls.test_music = os.path.join(cls.test_dir, "test_music.mp3")
        cls.test_video = os.path.join(cls.test_dir, "test_video.mp4")

        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
            '-acodec', 'libmp3lame', cls.test_music
        ], check=True, capture_output=True)

        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=5:size=1280x720:rate=60',
            '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=5',
            '-vcodec', 'libx264', '-acodec', 'aac', cls.test_video
        ], check=True, capture_output=True)

        cls.config_loader = ConfigLoader()
        cls.config = cls.config_loader.load_config()
        cls.config['highlights']['music_path'] = cls.test_music
        cls.config['highlights']['music_enabled'] = True
        cls.config['highlights']['game_volume'] = 0.5
        cls.config['highlights']['music_volume'] = 0.5

    @classmethod
    def tearDownClass(cls):
        """Cleanup test files."""
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def test_audio_info(self):
        """Test AudioInfo extraction."""
        info = AudioInfo(self.test_music)
        self.assertGreater(info.duration, 0)
        self.assertEqual(info.sample_rate, 44100)
        self.assertIn('mp3', info.format_name.lower())

    def test_music_processor_loop(self):
        """Test looping music to match longer duration."""
        processor = MusicProcessor()
        target_duration = 5.0
        output = os.path.join(self.test_dir, "looped_music.wav")
        result = processor.process_music(self.test_music, target_duration, output)

        self.assertTrue(os.path.exists(result))
        info = AudioInfo(result)
        self.assertAlmostEqual(info.duration, target_duration, delta=0.1)

    def test_music_processor_trim(self):
        """Test trimming music to match shorter duration."""
        processor = MusicProcessor()
        target_duration = 1.0
        output = os.path.join(self.test_dir, "trimmed_music.wav")
        result = processor.process_music(self.test_music, target_duration, output)

        self.assertTrue(os.path.exists(result))
        info = AudioInfo(result)
        self.assertAlmostEqual(info.duration, target_duration, delta=0.1)

    def test_audio_mixer(self):
        """Test mixing video audio with music."""
        mixer = AudioMixer(self.config)
        output = os.path.join(self.test_dir, "mixed_output.mp4")
        result = mixer.mix_audio(self.test_video, output)

        self.assertTrue(os.path.exists(result))
        cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a', result]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertIn('codec_type=audio', res.stdout)

    def test_music_disabled(self):
        """Test that mixing is skipped when music is disabled."""
        config_disabled = self.config.copy()
        config_disabled['highlights']['music_enabled'] = False
        mixer = AudioMixer(config_disabled)

        result = mixer.mix_audio(self.test_video)
        self.assertEqual(result, self.test_video)


if __name__ == "__main__":
    unittest.main()
