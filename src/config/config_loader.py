import os
import yaml
from typing import Any, Dict

from src.config.validation import validate_config

class ConfigLoader:
    DETECTION_REPLACE_PATHS = {
        "detection.ocr",
        "detection.templates",
        "detection.colors",
        "detection.weights",
        "detection.prefilter",
    }

    def __init__(self, config_dir: str = "config"):
        self.config_dir = os.path.abspath(config_dir)
        self.default_config_path = os.path.join(self.config_dir, "default_config.yaml")
        self.games_config_dir = os.path.join(self.config_dir, "games")
        
    def load_config(self, game_name: str = None, override_path: str = None) -> Dict[str, Any]:
        """Loads configuration merging default, game-specific, and manual overrides."""
        # 1. Load default
        config = self._load_yaml(self.default_config_path)
        
        # 2. Load game-specific
        if game_name:
            game_config_path = os.path.join(self.games_config_dir, f"{game_name}.yaml")
            if os.path.exists(game_config_path):
                game_config = self._load_yaml(game_config_path)
                self._deep_merge(config, game_config, replace_paths=self.DETECTION_REPLACE_PATHS)
            else:
                raise FileNotFoundError(f"Game configuration for '{game_name}' not found at {game_config_path}")
                
        # 3. Load override
        if override_path:
            if os.path.exists(override_path):
                override_config = self._load_yaml(override_path)
                self._deep_merge(config, override_config)
            else:
                raise FileNotFoundError(f"Override configuration not found at {override_path}")
                
        self._validate_config(config)
        return config

    def _validate_config(self, config: Dict[str, Any]):
        """Validates critical configuration fields."""
        validate_config(config)

    def _validate_roi(self, roi: Any, field_name: str):
        if (
            not isinstance(roi, list)
            or len(roi) != 4
            or not all(isinstance(value, (int, float)) for value in roi)
        ):
            raise ValueError(f"{field_name} must be a list of 4 numbers")

        _x, _y, width, height = roi
        if not all(0.0 <= value <= 1.0 for value in roi):
            raise ValueError(f"{field_name} values must be between 0.0 and 1.0")
        if width <= 0 or height <= 0:
            raise ValueError(f"{field_name} width and height must be greater than 0")

    def _validate_hsv(self, hsv: Any, field_name: str):
        if (
            not isinstance(hsv, list)
            or len(hsv) != 3
            or not all(isinstance(value, (int, float)) for value in hsv)
        ):
            raise ValueError(f"{field_name} must be a list of 3 numbers")

        hue, saturation, value = hsv
        if not 0 <= hue <= 180:
            raise ValueError(f"{field_name}[0] hue must be between 0 and 180")
        if not 0 <= saturation <= 255:
            raise ValueError(f"{field_name}[1] saturation must be between 0 and 255")
        if not 0 <= value <= 255:
            raise ValueError(f"{field_name}[2] value must be between 0 and 255")

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _deep_merge(
        self,
        base: Dict[str, Any],
        update: Dict[str, Any],
        path: str = "",
        replace_paths: set[str] = None,
    ):
        replace_paths = replace_paths or set()
        for key, value in update.items():
            current_path = f"{path}.{key}" if path else key
            if current_path in replace_paths:
                base[key] = value
                continue

            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value, current_path, replace_paths=replace_paths)
            else:
                base[key] = value

def get_config(game_name: str = None, override_path: str = None) -> Dict[str, Any]:
    loader = ConfigLoader()
    return loader.load_config(game_name, override_path)
