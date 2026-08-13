import os
import sys
import unittest
import yaml
import tempfile
import shutil

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

    def test_game_detection_sections_replace_default_detection_sections(self):
        if not os.path.exists(os.path.join(self.config_dir, "games", "battlefield_1.yaml")):
            self.skipTest("battlefield_1.yaml is not present")

        config = self.loader.load_config(game_name="battlefield_1")
        detection = config["detection"]

        templates = detection["templates"]
        self.assertIn("killicon", templates)
        self.assertNotIn("skull_icon", templates)
        self.assertNotIn("kill_icon", templates)

        self.assertEqual(detection["ocr"], {
            "enabled": False,
            "keywords": [],
            "similarity_threshold": 0.8,
            "required": False,
        })
        self.assertEqual(list(detection["colors"].keys()), ["red_name"])
        self.assertEqual(detection["weights"], {
            "ocr": 0.0,
            "template": 0.9,
            "color": 0.1,
            "yolo": 0.0,
        })
        self.assertEqual(detection["prefilter"], {
            "enabled": True,
            "color_threshold": 0.005,
        })
        self.assertEqual(detection["killfeed_roi"], [
            0.4293561490006595,
            0.5554773873888226,
            0.15080691183907463,
            0.1806974675198949,
        ])

        # Other nested defaults should still be preserved by deep merge.
        self.assertEqual(config["global"]["device"], "cuda")
        self.assertEqual(config["video"]["ffmpeg_path"], "ffmpeg")

    def test_detection_sections_replace_defaults_with_temp_config(self):
        temp_dir = tempfile.mkdtemp()
        try:
            games_dir = os.path.join(temp_dir, "games")
            os.makedirs(games_dir, exist_ok=True)

            with open(os.path.join(temp_dir, "default_config.yaml"), "w", encoding="utf-8") as f:
                yaml.dump({
                    "global": {"device": "cuda"},
                    "video": {"ffmpeg_path": "ffmpeg"},
                    "detection": {
                        "ocr": {
                            "enabled": True,
                            "keywords": ["DEFAULT"],
                            "similarity_threshold": 0.8,
                            "lang": "ch",
                            "use_gpu": True,
                        },
                        "templates": {
                            "skull_icon": {"path": "skull.png", "threshold": 0.7},
                            "kill_icon": {"path": "kill.png", "threshold": 0.7},
                        },
                        "colors": {
                            "default_red": {
                                "hsv_lower": [0, 0, 0],
                                "hsv_upper": [10, 255, 255],
                            },
                        },
                        "weights": {
                            "ocr": 0.4,
                            "template": 0.3,
                            "color": 0.2,
                            "yolo": 0.1,
                        },
                        "prefilter": {
                            "enabled": False,
                            "color_threshold": 0.02,
                        },
                        "killfeed_roi": [0, 0, 1, 1],
                    },
                }, f)

            with open(os.path.join(games_dir, "test_game.yaml"), "w", encoding="utf-8") as f:
                yaml.dump({
                    "detection": {
                        "ocr": {
                            "enabled": False,
                            "keywords": [],
                            "similarity_threshold": 0.9,
                        },
                        "templates": {
                            "game_icon": {
                                "path": "models/templates/test_game/game_icon.png",
                                "threshold": 0.8,
                            },
                        },
                        "colors": {
                            "game_blue": {
                                "hsv_lower": [100, 100, 100],
                                "hsv_upper": [120, 255, 255],
                            },
                        },
                        "weights": {
                            "ocr": 0.0,
                            "template": 1.0,
                        },
                        "prefilter": {
                            "enabled": True,
                            "color_threshold": 0.01,
                        },
                        "killfeed_roi": [0.1, 0.2, 0.3, 0.4],
                    },
                }, f)

            config = ConfigLoader(config_dir=temp_dir).load_config(game_name="test_game")
            detection = config["detection"]

            self.assertEqual(detection["ocr"], {
                "enabled": False,
                "keywords": [],
                "similarity_threshold": 0.9,
            })
            self.assertEqual(list(detection["templates"].keys()), ["game_icon"])
            self.assertEqual(list(detection["colors"].keys()), ["game_blue"])
            self.assertEqual(detection["weights"], {"ocr": 0.0, "template": 1.0})
            self.assertEqual(detection["prefilter"], {"enabled": True, "color_threshold": 0.01})
            self.assertEqual(detection["killfeed_roi"], [0.1, 0.2, 0.3, 0.4])
            self.assertEqual(config["global"]["device"], "cuda")
            self.assertEqual(config["video"]["ffmpeg_path"], "ffmpeg")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_manual_override_deep_merges_detection_sections(self):
        temp_dir = tempfile.mkdtemp()
        try:
            games_dir = os.path.join(temp_dir, "games")
            os.makedirs(games_dir, exist_ok=True)

            with open(os.path.join(temp_dir, "default_config.yaml"), "w", encoding="utf-8") as f:
                yaml.dump({
                    "detection": {
                        "ocr": {
                            "enabled": False,
                            "keywords": ["DEFAULT"],
                            "similarity_threshold": 0.8,
                            "lang": "ch",
                            "use_gpu": True,
                        },
                        "prefilter": {
                            "enabled": True,
                            "color_threshold": 0.01,
                        },
                        "weights": {
                            "ocr": 0.4,
                            "template": 0.3,
                            "color": 0.2,
                            "yolo": 0.1,
                        },
                    },
                }, f)

            override_path = os.path.join(temp_dir, "override.yaml")
            with open(override_path, "w", encoding="utf-8") as f:
                yaml.dump({
                    "detection": {
                        "ocr": {
                            "enabled": True,
                        },
                        "prefilter": {
                            "color_threshold": 0.05,
                        },
                    },
                }, f)

            config = ConfigLoader(config_dir=temp_dir).load_config(override_path=override_path)

            self.assertEqual(config["detection"]["ocr"], {
                "enabled": True,
                "keywords": ["DEFAULT"],
                "similarity_threshold": 0.8,
                "lang": "ch",
                "use_gpu": True,
            })
            self.assertEqual(config["detection"]["prefilter"], {
                "enabled": True,
                "color_threshold": 0.05,
            })
            self.assertEqual(config["detection"]["weights"], {
                "ocr": 0.4,
                "template": 0.3,
                "color": 0.2,
                "yolo": 0.1,
            })
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_invalid_game(self):
        with self.assertRaises(FileNotFoundError):
            self.loader.load_config(game_name="non_existent_game")

    def test_game_configs_output_dir_is_relative(self):
        """Committed game configs must not contain machine-specific absolute output dirs."""
        for game_name in ("battlefield4", "battlefield6"):
            config = self.loader.load_config(game_name=game_name)
            output_dir = config["global"]["output_dir"]
            self.assertFalse(
                os.path.isabs(output_dir),
                f"{game_name} output_dir must be relative, got: {output_dir}",
            )

    def test_default_config_has_no_dangling_template_paths(self):
        """Default config must not reference template images that do not exist in the repo."""
        config = self.loader.load_config()
        templates = config["detection"].get("templates", {})
        for name in ("skull_icon", "kill_icon"):
            self.assertNotIn(name, templates)

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
