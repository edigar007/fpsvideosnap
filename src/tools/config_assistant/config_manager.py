import os
import yaml
from typing import Any, Dict, List, Optional
from src.utils.logger import get_logger

logger = get_logger("config_assistant.config_manager")

class ConfigManager:
    """
    Manages loading, updating, and saving game configuration files.
    Supports incremental updates to specific sections of the config.
    """
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.config_dir = os.path.join(project_root, "config")
        self.games_dir = os.path.join(self.config_dir, "games")
        self.template_path = os.path.join(self.config_dir, "default_game_template.yaml")
        
        # Ensure directories exist
        if not os.path.exists(self.games_dir):
            os.makedirs(self.games_dir, exist_ok=True)

    def list_games(self) -> List[str]:
        """Returns a list of available game configuration names."""
        if not os.path.exists(self.games_dir):
            return []
        
        games = []
        for filename in os.listdir(self.games_dir):
            if filename.endswith(".yaml"):
                games.append(filename[:-5]) # Remove .yaml
        return sorted(games)

    def create_game(self, game_name: str) -> bool:
        """
        Creates a new game configuration based on the default template.
        Also creates the corresponding template directory.
        """
        if not game_name:
            return False

        game_config_path = os.path.join(self.games_dir, f"{game_name}.yaml")
        if os.path.exists(game_config_path):
            logger.warning(f"Game configuration already exists: {game_name}")
            return False

        if not os.path.exists(self.template_path):
            logger.error(f"Default template not found at: {self.template_path}")
            return False

        try:
            # Read template
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            # Format template with game name
            formatted_content = template_content.replace("{game_name}", game_name)

            # Write new config
            with open(game_config_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)

            # Create template directory
            template_dir = os.path.join(self.project_root, "models", "templates", game_name)
            os.makedirs(template_dir, exist_ok=True)

            logger.info(f"Created new game config and template dir for: {game_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating game config: {e}")
            return False

    def get_config(self, game_name: str) -> Optional[Dict[str, Any]]:
        """Loads a specific game configuration."""
        game_config_path = os.path.join(self.games_dir, f"{game_name}.yaml")
        if not os.path.exists(game_config_path):
            logger.error(f"Game config not found: {game_config_path}")
            return None

        try:
            with open(game_config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading game config: {e}")
            return None

    def update_config_section(self, game_name: str, section_path: str, value: Any) -> bool:
        """
        Updates a specific section of the configuration file.
        section_path: e.g., "detection.killfeed_roi"
        """
        config = self.get_config(game_name)
        if config is None:
            return False

        try:
            # Navigate to the section to update
            parts = section_path.split('.')
            current = config
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            
            # Update the value
            current[parts[-1]] = value

            # Save the updated config
            game_config_path = os.path.join(self.games_dir, f"{game_name}.yaml")
            with open(game_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, sort_keys=False)

            logger.info(f"Updated section {section_path} for game: {game_name}")
            return True
        except Exception as e:
            logger.error(f"Error updating config section: {e}")
            return False

    def export_config_yaml(self, game_name: str) -> Optional[str]:
        """Returns the full configuration as a YAML string."""
        config = self.get_config(game_name)
        if config is None:
            return None
        
        try:
            return yaml.dump(config, allow_unicode=True, sort_keys=False)
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            return None

# Global instance
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
config_manager = ConfigManager(PROJECT_ROOT)
