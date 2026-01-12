import os
import sys
import unittest
import yaml

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from config.config_loader import ConfigLoader

class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        # We assume the config files exist relative to the test file
        self.config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        self.loader = ConfigLoader(config_dir=self.config_dir)

    def test_load_default_config(self):
        config = self.loader.load_config()
        self.assertIn('global', config)
        self.assertEqual(config['global']['device'], 'cuda')
        self.assertIn('video', config)
        self.assertIn('detection', config)

    def test_load_game_config(self):
        # battlefield6 should exist from previous steps
        config = self.loader.load_config(game_name="battlefield6")
        self.assertIn('game_name', config)
        self.assertEqual(config['game_name'], "Battlefield 6")
        # Check deep merge: 'device' from default should still be there
        self.assertEqual(config['global']['device'], 'cuda')
        # Check game-specific override
        self.assertEqual(config['highlights']['pre_kill_time'], 5.0)

    def test_invalid_game(self):
        with self.assertRaises(FileNotFoundError):
            self.loader.load_config(game_name="non_existent_game")

    def test_validation(self):
        # Valid config
        config = self.loader.load_config()
        self.loader._validate_config(config) # Should not raise
        
        # Invalid OCR enabled type
        config['detection']['ocr']['enabled'] = "yes"
        with self.assertRaises(ValueError):
            self.loader._validate_config(config)
            
        # Invalid similarity threshold
        config['detection']['ocr']['enabled'] = True
        config['detection']['ocr']['similarity_threshold'] = 1.5
        with self.assertRaises(ValueError):
            self.loader._validate_config(config)

if __name__ == '__main__':
    unittest.main()
