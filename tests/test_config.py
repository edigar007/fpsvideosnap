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
        self.assertEqual(config['game_name'], "battlefield6")
        # Check deep merge: 'device' from default should still be there
        self.assertEqual(config['global']['device'], 'cuda')
        # Check game-specific override
        self.assertEqual(config['highlights']['pre_kill_time'], 5.0)

    def test_invalid_game(self):
        with self.assertRaises(FileNotFoundError):
            self.loader.load_config(game_name="non_existent_game")

    def test_validation(self):
        """Test that basic OCR validation works."""
        # Valid config
        config = self.loader.load_config()
        self.loader._validate_config(config)  # Should not raise

        # Invalid OCR enabled type
        config['detection']['ocr']['enabled'] = "yes"
        with self.assertRaises(ValueError):
            self.loader._validate_config(config)

        # Invalid similarity threshold
        config['detection']['ocr']['enabled'] = True
        config['detection']['ocr']['similarity_threshold'] = 1.5
        with self.assertRaises(ValueError):
            self.loader._validate_config(config)

    def test_rules_must_be_list(self):
        """Test that detection.rules must be a list if present."""
        config = self.loader.load_config()
        config['detection']['rules'] = "not a list"
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules", str(context.exception))

    def test_rules_item_must_be_dict(self):
        """Test that each rule item must be a dict."""
        config = self.loader.load_config()
        config['detection']['rules'] = ["not a dict"]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules[0]", str(context.exception))

    def test_rules_name_required_and_nonempty(self):
        """Test that rule name must be present and non-empty string."""
        config = self.loader.load_config()
        config['detection']['rules'] = [
            {"enabled": True, "require": ["ocr"]}
        ]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules[0]", str(context.exception))
        self.assertIn("name", str(context.exception))

        # Test empty string name
        config['detection']['rules'] = [
            {"name": "", "enabled": True, "require": ["ocr"]}
        ]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules[0]", str(context.exception))
        self.assertIn("name", str(context.exception))

    def test_rules_enabled_must_be_bool(self):
        """Test that rule enabled must be a boolean."""
        config = self.loader.load_config()
        config['detection']['rules'] = [
            {"name": "test_rule", "enabled": "yes", "require": ["ocr"]}
        ]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules[0]", str(context.exception))
        self.assertIn("enabled", str(context.exception))

    def test_rules_require_must_be_nonempty_list(self):
        """Test that rule require must be a non-empty list of strings."""
        config = self.loader.load_config()

        # Test require not a list
        config['detection']['rules'] = [
            {"name": "test_rule", "enabled": True, "require": "ocr"}
        ]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules[0]", str(context.exception))
        self.assertIn("require", str(context.exception))

        # Test empty list
        config['detection']['rules'] = [
            {"name": "test_rule", "enabled": True, "require": []}
        ]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules[0]", str(context.exception))
        self.assertIn("require", str(context.exception))

    def test_rules_require_invalid_signal(self):
        """Test that require signals must be in allowed set: ocr|template|color|yolo."""
        config = self.loader.load_config()
        config['detection']['rules'] = [
            {"name": "test_rule", "enabled": True, "require": ["invalid_signal"]}
        ]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules[0]", str(context.exception))
        self.assertIn("require[0]", str(context.exception))

    def test_rules_name_must_be_unique(self):
        """Test that rule names must be unique across all rules."""
        config = self.loader.load_config()
        config['detection']['rules'] = [
            {"name": "duplicate_rule", "enabled": True, "require": ["ocr"]},
            {"name": "duplicate_rule", "enabled": True, "require": ["template"]}
        ]
        with self.assertRaises(ValueError) as context:
            self.loader._validate_config(config)
        self.assertIn("detection.rules", str(context.exception))
        self.assertIn("duplicate_rule", str(context.exception))

if __name__ == '__main__':
    unittest.main()
