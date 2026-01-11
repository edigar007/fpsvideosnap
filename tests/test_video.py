import os
import sys
import unittest
import shutil
import subprocess

# Add project root to python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.video.video_info import VideoInfo
from src.video.frame_extractor import FrameExtractor
from src.video.clip_cutter import ClipCutter
from src.utils.temp_manager import TempManager
from src.config.config_loader import ConfigLoader

class TestVideoProcessing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create a dummy video for testing."""
        cls.test_dir = os.path.abspath("test_output")
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.dummy_video = os.path.join(cls.test_dir, "dummy.mp4")
        
        # Load config to get default values
        cls.config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        cls.loader = ConfigLoader(config_dir=cls.config_dir)
        cls.config = cls.loader.load_config()
        
        # Generate a 2-second dummy video (black screen with moving text)
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=2:size=640x360:rate=30',
            '-c:v', 'libx264', '-t', '2',
            cls.dummy_video
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        """Cleanup test files."""
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        # Use config's temp_dir
        temp_dir = os.path.join(self.test_dir, self.config['global']['temp_dir'])
        self.temp_manager = TempManager(base_temp_dir=temp_dir)

    def tearDown(self):
        self.temp_manager.clean_all()

    def test_integration_with_config(self):
        """Verify that we can use ConfigLoader values with our modules."""
        ffmpeg_path = self.config['video']['ffmpeg_path']
        hwaccel = self.config['video']['hwaccel']
        
        extractor = FrameExtractor(ffmpeg_path=ffmpeg_path, hwaccel=hwaccel)
        self.assertEqual(extractor.ffmpeg_path, "ffmpeg")
        # In default config it is 'cuda'
        self.assertEqual(extractor.hwaccel, "cuda")

    def test_video_info_metadata(self):
        """TASK-010: Extract video metadata."""
        vinfo = VideoInfo(self.dummy_video)
        self.assertEqual(vinfo.width, 640)
        self.assertEqual(vinfo.height, 360)
        self.assertAlmostEqual(vinfo.fps, 30.0, places=1)
        self.assertGreater(vinfo.duration, 1.9)

    def test_video_info_validation(self):
        """TASK-011: Video format validation."""
        # Valid format
        VideoInfo(self.dummy_video)
        
        # Invalid format
        invalid_file = os.path.join(self.test_dir, "test.txt")
        with open(invalid_file, 'w') as f: f.write("not a video")
        
        with self.assertRaises(ValueError):
            VideoInfo(invalid_file)

    def test_frame_extraction(self):
        """TASK-012 & TASK-013: Frame extraction with naming convention."""
        extractor = FrameExtractor(hwaccel=None) # Use CPU for stable tests
        out_dir = self.temp_manager.create_temp_dir("frames_")
        
        # Extract frames every 500ms (should get 0, 500, 1000, 1500)
        frames = extractor.extract_frames(self.dummy_video, out_dir, interval_ms=500)
        
        self.assertGreaterEqual(len(frames), 4)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "frame_0.jpg")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "frame_500.jpg")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "frame_1000.jpg")))

    def test_clip_cutting(self):
        """TASK-014: Precise clip cutting."""
        cutter = ClipCutter(hwaccel=None) # Use CPU for stable tests
        output_clip = os.path.join(self.test_dir, "cut.mp4")
        
        # Cut 1 second starting from 0.5s
        cutter.cut_segment(self.dummy_video, output_clip, start_sec=0.5, duration_sec=1.0)
        
        self.assertTrue(os.path.exists(output_clip))
        vinfo = VideoInfo(output_clip)
        self.assertAlmostEqual(vinfo.duration, 1.0, delta=0.1)

    def test_temp_manager(self):
        """TASK-015: Temp manager logic."""
        temp_path = self.temp_manager.create_temp_dir("test_")
        full_filepath = self.temp_manager.get_temp_path("test.file", subdir="sub")
        
        with open(full_filepath, 'w') as f: f.write("data")
        
        self.assertTrue(os.path.exists(temp_path))
        self.assertTrue(os.path.exists(full_filepath))
        
        self.temp_manager.clean_all()
        
        self.assertFalse(os.path.exists(temp_path))
        self.assertFalse(os.path.exists(full_filepath))

if __name__ == '__main__':
    unittest.main()
