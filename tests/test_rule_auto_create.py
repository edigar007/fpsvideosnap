import pytest
import os
import shutil
import yaml
from src.tools.config_assistant.config_manager import ConfigManager

class TestRuleAutoCreate:
    @pytest.fixture
    def config_manager(self, tmp_path):
        # Setup a temporary config environment
        config_dir = tmp_path / "config"
        games_dir = config_dir / "games"
        games_dir.mkdir(parents=True)
        
        # Create a dummy game config without rules
        game_name = "test_game_auto_create"
        config_content = {
            "game_name": game_name,
            "detection": {
                "killfeed_roi": [0, 0, 1, 1]
            }
        }
        
        with open(games_dir / f"{game_name}.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config_content, f)
            
        return ConfigManager(str(tmp_path))

    def test_auto_create_rule_on_override(self, config_manager):
        game_name = "test_game_auto_create"
        rule_name = "new_auto_rule"
        
        # Ensure rule doesn't exist initially
        config = config_manager.get_config(game_name)
        rules = config.get("detection", {}).get("rules", [])
        assert len(rules) == 0
        
        # Attempt to update override for non-existent rule
        roi_value = [0.1, 0.1, 0.2, 0.2]
        success = config_manager.update_rule_override(
            game_name, 
            rule_name, 
            "killfeed_roi", 
            roi_value
        )
        
        # Verify success
        assert success is True
        
        # Reload config and verify rule existence and content
        config = config_manager.get_config(game_name)
        rules = config.get("detection", {}).get("rules", [])
        assert len(rules) == 1
        
        new_rule = rules[0]
        assert new_rule["name"] == rule_name
        assert new_rule["enabled"] is True
        assert new_rule["require"] == ["color"]
        assert "detection_overrides" in new_rule
        assert new_rule["detection_overrides"]["killfeed_roi"] == roi_value

    def test_auto_create_rule_nested_override(self, config_manager):
        game_name = "test_game_auto_create"
        rule_name = "nested_rule"
        
        # Update nested property (e.g. ocr.enabled)
        success = config_manager.update_rule_override(
            game_name,
            rule_name,
            "ocr.enabled",
            True
        )
        
        assert success is True
        
        config = config_manager.get_config(game_name)
        # Should be the second rule now if run after previous test, 
        # but fixture resets state so it should be the only one or we need to check list
        # Actually fixture creates fresh env for each test method if scope is default (function)
        
        rules = config.get("detection", {}).get("rules", [])
        target_rule = next((r for r in rules if r["name"] == rule_name), None)
        
        assert target_rule is not None
        assert target_rule["detection_overrides"]["ocr"]["enabled"] is True
