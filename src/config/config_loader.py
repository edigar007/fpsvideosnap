import os
import yaml
from typing import Any, Dict

class ConfigLoader:
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
        if 'detection' not in config:
            return
            
        det = config['detection']
        
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
            for k, v in weights.items():
                if not isinstance(v, (int, float)) or v < 0:
                    raise ValueError(f"Weight for {k} must be a non-negative number")
                    
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

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]):
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

def get_config(game_name: str = None, override_path: str = None) -> Dict[str, Any]:
    loader = ConfigLoader()
    return loader.load_config(game_name, override_path)
