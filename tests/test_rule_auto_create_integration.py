import pytest
import yaml
from src.tools.config_assistant.config_manager import ConfigManager
from src.tools.config_assistant.api import api_bp
from flask import Flask

@pytest.fixture
def temp_project(tmp_path):
    project_root = tmp_path
    config_dir = project_root / "config"
    games_dir = config_dir / "games"
    games_dir.mkdir(parents=True)
    
    # Create a dummy template without rules
    template_path = config_dir / "default_game_template.yaml"
    template_content = {
        "game_name": "{game_name}",
        "detection": {
            "killfeed_roi": [0.1, 0.1, 0.2, 0.2],
            "ocr": {"enabled": True, "keywords": ["kill"], "similarity_threshold": 0.8},
            "templates": {},
            "colors": {},
            # No rules initially
        }
    }
    with open(template_path, "w") as f:
        yaml.dump(template_content, f)
        
    return project_root

@pytest.fixture
def config_manager(temp_project):
    return ConfigManager(str(temp_project))

@pytest.fixture
def app(config_manager, temp_project):
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.config['UPLOAD_FOLDER'] = str(temp_project / "uploads")
    app.config["CONFIG_MANAGER"] = config_manager
    
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_api_auto_create_rule_on_roi_save(client, config_manager):
    config_manager.create_game("test_game")
    
    # Verify no rules exist initially
    config = config_manager.get_config("test_game")
    assert "rules" not in config.get("detection", {}) or not config["detection"]["rules"]
    
    # Call ROI API with a new rule name
    rule_name = "auto_rule_roi"
    roi = [0.3, 0.3, 0.2, 0.2]
    
    response = client.put("/api/config/test_game/roi", json={
        "roi": roi,
        "rule_name": rule_name
    })
    
    assert response.status_code == 200
    
    # Verify rule was created and ROI set
    config = config_manager.get_config("test_game")
    rules = config["detection"]["rules"]
    assert len(rules) == 1
    assert rules[0]["name"] == rule_name
    assert rules[0]["detection_overrides"]["killfeed_roi"] == roi

def test_api_auto_create_rule_on_ocr_save(client, config_manager):
    config_manager.create_game("test_game")
    
    rule_name = "auto_rule_ocr"
    response = client.put("/api/config/test_game/ocr", json={
        "enabled": False,
        "keywords": ["TEST"],
        "rule_name": rule_name
    })
    
    assert response.status_code == 200
    
    config = config_manager.get_config("test_game")
    rules = config["detection"]["rules"]
    target_rule = next((r for r in rules if r["name"] == rule_name), None)
    
    assert target_rule is not None
    assert target_rule["detection_overrides"]["ocr"]["enabled"] is False
    assert target_rule["detection_overrides"]["ocr"]["keywords"] == ["TEST"]

def test_api_auto_create_rule_on_color_save(client, config_manager):
    config_manager.create_game("test_game")
    
    rule_name = "auto_rule_color"
    response = client.post("/api/config/test_game/colors", json={
        "name": "red",
        "hsv_lower": [0, 100, 100],
        "hsv_upper": [10, 255, 255],
        "rule_name": rule_name
    })
    
    assert response.status_code == 200
    
    config = config_manager.get_config("test_game")
    rules = config["detection"]["rules"]
    target_rule = next((r for r in rules if r["name"] == rule_name), None)
    
    assert target_rule is not None
    assert "red" in target_rule["detection_overrides"]["colors"]

def test_api_auto_create_rule_on_template_save(client, config_manager):
    config_manager.create_game("test_game")
    
    rule_name = "auto_rule_template"
    response = client.post("/api/config/test_game/templates", json={
        "name": "t1",
        "roi": [0,0,1,1],
        "rule_name": rule_name
    })
    
    assert response.status_code == 200
    
    config = config_manager.get_config("test_game")
    rules = config["detection"]["rules"]
    target_rule = next((r for r in rules if r["name"] == rule_name), None)
    
    assert target_rule is not None
    assert "t1" in target_rule["detection_overrides"]["templates"]
