import os
import yaml
from typing import Any, Dict

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
                self._deep_merge(config, game_config)
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
        video = config.get('video', {})
        frame_extraction_mode = video.get('frame_extraction_mode')
        if frame_extraction_mode is not None and frame_extraction_mode not in {'bulk', 'precise'}:
            raise ValueError("video.frame_extraction_mode must be 'bulk' or 'precise'")

        highlights = config.get('highlights', {})
        for key in ('pre_kill_time', 'post_kill_time'):
            if key in highlights and (
                not isinstance(highlights[key], (int, float)) or highlights[key] < 0
            ):
                raise ValueError(f"highlights.{key} must be a non-negative number")

        for key in ('game_volume', 'music_volume'):
            if key in highlights and (
                not isinstance(highlights[key], (int, float)) or not 0 <= highlights[key] <= 1
            ):
                raise ValueError(f"highlights.{key} must be between 0 and 1")

        if 'detection' not in config:
            return
            
        det = config['detection']

        if 'killfeed_roi' in det:
            self._validate_roi(det['killfeed_roi'], 'detection.killfeed_roi')

        if 'templates' in det and isinstance(det['templates'], dict):
            for name, template_cfg in det['templates'].items():
                if isinstance(template_cfg, dict) and 'roi' in template_cfg:
                    self._validate_roi(template_cfg['roi'], f"detection.templates.{name}.roi")

        if 'colors' in det and isinstance(det['colors'], dict):
            for name, color_cfg in det['colors'].items():
                if not isinstance(color_cfg, dict):
                    raise ValueError(f"detection.colors.{name} must be a dict")
                for key in ('hsv_lower', 'hsv_upper'):
                    if key in color_cfg:
                        self._validate_hsv(color_cfg[key], f"detection.colors.{name}.{key}")
        
        # Validate OCR settings
        if 'ocr' in det:
            ocr = det['ocr']
            if not isinstance(ocr.get('enabled'), bool):
                raise ValueError("detection.ocr.enabled must be a boolean")
            if not isinstance(ocr.get('keywords'), list):
                raise ValueError("detection.ocr.keywords must be a list")
            if not (0 <= ocr.get('similarity_threshold', 0) <= 1):
                raise ValueError("detection.ocr.similarity_threshold must be between 0 and 1")

        # Validate Weights (must sum to approx 1.0 or just be positive)
        if 'weights' in det:
            weights = det['weights']
            positive_count = 0
            for k, v in weights.items():
                if not isinstance(v, (int, float)) or v < 0:
                    raise ValueError(f"Weight for {k} must be a non-negative number")
                if v > 0:
                    positive_count += 1
            if weights and positive_count == 0:
                raise ValueError("detection.weights must contain at least one positive value")
                    
        # Validate Prefilter
        if 'prefilter' in det:
            pre = det['prefilter']
            if 'color_threshold' in pre and not (0 <= pre['color_threshold'] <= 1):
                raise ValueError("detection.prefilter.color_threshold must be between 0 and 1")

        # Validate Rules (OR-of-AND kill detection rules)
        if 'rules' in det:
            rules = det['rules']
            
            # Rules must be a list
            if not isinstance(rules, list):
                raise ValueError("detection.rules must be a list")
            
            # Allowed signal names
            allowed_signals = {'ocr', 'template', 'color', 'yolo'}
            
            # Track names for uniqueness check
            seen_names = set()
            
            for i, rule in enumerate(rules):
                prefix = f"detection.rules[{i}]"
                
                # Each rule must be a dict
                if not isinstance(rule, dict):
                    raise ValueError(f"{prefix} must be a dict")
                
                # Validate name (required, non-empty string)
                name = rule.get('name')
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"{prefix}.name must be a non-empty string")
                
                # Check name uniqueness
                if name in seen_names:
                    raise ValueError(f"detection.rules: duplicate name '{name}'")
                seen_names.add(name)
                
                # Validate enabled (must be bool)
                enabled = rule.get('enabled')
                if not isinstance(enabled, bool):
                    raise ValueError(f"{prefix}.enabled must be a boolean")
                
                # Validate require (must be non-empty list of valid signals)
                require = rule.get('require')
                if not isinstance(require, list):
                    raise ValueError(f"{prefix}.require must be a list")
                
                if len(require) == 0:
                    raise ValueError(f"{prefix}.require must not be empty")
                
                for j, signal in enumerate(require):
                    if not isinstance(signal, str) or signal not in allowed_signals:
                        raise ValueError(
                            f"{prefix}.require[{j}] '{signal}' is not a valid signal. "
                            f"Allowed: {', '.join(sorted(allowed_signals))}"
                        )

                overrides = rule.get('detection_overrides', {})
                if overrides:
                    if not isinstance(overrides, dict):
                        raise ValueError(f"{prefix}.detection_overrides must be a dict")
                    if 'killfeed_roi' in overrides:
                        self._validate_roi(overrides['killfeed_roi'], f"{prefix}.detection_overrides.killfeed_roi")
                    if 'ocr' in overrides:
                        ocr_override = overrides['ocr']
                        if not isinstance(ocr_override, dict):
                            raise ValueError(f"{prefix}.detection_overrides.ocr must be a dict")
                        threshold = ocr_override.get('similarity_threshold')
                        if threshold is not None and not 0 <= threshold <= 1:
                            raise ValueError(
                                f"{prefix}.detection_overrides.ocr.similarity_threshold "
                                "must be between 0 and 1"
                            )
                    if 'colors' in overrides and isinstance(overrides['colors'], dict):
                        for color_name, color_cfg in overrides['colors'].items():
                            if not isinstance(color_cfg, dict):
                                raise ValueError(f"{prefix}.detection_overrides.colors.{color_name} must be a dict")
                            for key in ('hsv_lower', 'hsv_upper'):
                                if key in color_cfg:
                                    self._validate_hsv(
                                        color_cfg[key],
                                        f"{prefix}.detection_overrides.colors.{color_name}.{key}",
                                    )

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

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any], path: str = ""):
        for key, value in update.items():
            current_path = f"{path}.{key}" if path else key
            if current_path in self.DETECTION_REPLACE_PATHS:
                base[key] = value
                continue

            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value, current_path)
            else:
                base[key] = value

def get_config(game_name: str = None, override_path: str = None) -> Dict[str, Any]:
    loader = ConfigLoader()
    return loader.load_config(game_name, override_path)
